import time
import uuid
import asyncio
import logging
from datetime import datetime, UTC
from typing import List, Optional, Dict, Any, AsyncGenerator
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, Request, status
from backend.users.models import User
from backend.chatbot.models import ChatThread, ChatMessage
from backend.chatbot.schemas import (
    MessageSchema,
    ChatResponse,
    StreamTokenData,
    StreamMetadata,
    StreamErrorData,
    StreamInterruptData,
    StreamEvent,
)
from backend.chatbot.graph_workflow import get_chat_app
from backend.core.database import get_db
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command

logger = logging.getLogger("app.chatbot")


async def _watch_disconnect(request: Request, task: asyncio.Task, poll_interval: float = 0.5) -> None:
    """Cancels *task* as soon as the HTTP client disconnects."""
    try:
        while not task.done():
            if await request.is_disconnected():
                logger.info("Client disconnected — cancelling stream task")
                task.cancel()
                return
            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        pass


def _extract_text(raw) -> str:
    """Extract plain text from an AIMessage content (str or list of content parts)."""
    if isinstance(raw, list):
        return "".join(
            p.get("text", "") for p in raw
            if isinstance(p, dict)
            and not p.get("thought")
            and p.get("type") not in ("thought", "thinking")
        )
    return raw if isinstance(raw, str) else str(raw)


class ChatbotService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    # ─────────────────────────────────────────────
    # DB helpers
    # ─────────────────────────────────────────────

    async def _save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        user_id: int,
        user_query: Optional[str] = None,
    ) -> None:
        try:
            res = await self.db.execute(
                select(ChatThread).where(ChatThread.thread_id == session_id)
            )
            thread = res.scalar_one_or_none()
            if not thread:
                preview = (user_query or content)[:100]
                thread = ChatThread(
                    thread_id=session_id,
                    preview=preview,
                    updated_at=datetime.now(UTC).replace(tzinfo=None),
                    user_id=user_id,
                )
                self.db.add(thread)
                await self.db.flush()
            self.db.add(ChatMessage(thread_id=session_id, role=role, content=content))
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to save message [thread=%s role=%s]: %s", session_id, role, e, exc_info=True)

    async def _update_thread_metadata(self, session_id: str, intent: str) -> None:
        try:
            res = await self.db.execute(
                select(ChatThread).where(ChatThread.thread_id == session_id)
            )
            thread = res.scalar_one_or_none()
            if thread:
                thread.intent = intent
                thread.updated_at = datetime.now(UTC).replace(tzinfo=None)
                await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to update thread metadata [thread=%s]: %s", session_id, e, exc_info=True)

    # ─────────────────────────────────────────────
    # chat_stream  (initial user message)
    # ─────────────────────────────────────────────

    async def chat_stream(
        self,
        user_message: str,
        user: User,
        thread_id: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        SSE events:
          status    — pipeline working (coding path)
          token     — text chunk (conversational path)
          interrupt — graph paused at human_review_node
          metadata  — final stats
          error     — something went wrong
        """
        user_id = user.id
        session_id = thread_id or str(uuid.uuid4())
        active_thread_id = f"user_{user_id}_{session_id}"
        logger.info("chat_stream | session=%s", session_id)

        await self._save_message(session_id, "user", user_message, user_id, user_message)

        graph_config = {"configurable": {"thread_id": active_thread_id}}
        new_input = {"messages": [HumanMessage(content=user_message)]}
        start_time = time.perf_counter()

        # Nodes whose tokens are suppressed from the user
        suppress = {
            "router", "router_node",
            "planner", "planner_node",
            "re_planner", "re_planner_node",
            "coding",
            "code_tester", "code_tester_node",
            "code_reflection", "code_reflection_node",
        }

        app = await get_chat_app()
        status_emitted = False
        full_response: list[str] = []
        total_tokens = 0
        final_state: Dict[str, Any] = {}
        got_interrupt = False
        detected_intent = "Conversational"

        async def _run_stream():
            nonlocal status_emitted, full_response, total_tokens, final_state, got_interrupt, detected_intent
            async for event in app.astream_events(new_input, config=graph_config, version="v2"):
                event_type = event.get("event")
                name = event.get("name")
                node_name = event.get("metadata", {}).get("langgraph_node", "")

                # ── Detect intent from router ──────────────────────────────
                if event_type == "on_chain_end" and node_name == "router":
                    raw_out = event.get("data", {}).get("output")
                    out = raw_out if isinstance(raw_out, dict) else {}
                    detected_intent = out.get("intent", "Conversational")
                    if str(detected_intent).lower() == "coding" and not status_emitted:
                        status_emitted = True
                        stream_queue.put_nowait({"event": "status", "data": {
                            "message": "⚙️ Generating your code, please wait…"
                        }})

                # ── Code tester started ────────────────────────────────────
                elif event_type == "on_chain_start" and node_name == "code_tester":
                    stream_queue.put_nowait({"event": "status", "data": {
                        "message": "🧪 Running tests on the generated code…"
                    }})

                # ── Graph end / interrupt ──────────────────────────────────
                elif event_type == "on_chain_end" and name == "LangGraph":
                    raw_output = event.get("data", {}).get("output")
                    output = raw_output if isinstance(raw_output, dict) else {}
                    interrupts = output.get("__interrupt__", [])

                    if interrupts:
                        got_interrupt = True
                        logger.info(
                            "chat_stream | interrupt detected [thread=%s], fetching checkpoint…",
                            active_thread_id,
                        )
                        try:
                            snap = await app.aget_state(graph_config)
                            vals = snap.values if snap else {}
                        except Exception as snap_err:
                            logger.error("Failed to fetch checkpoint: %s", snap_err)
                            vals = {}

                        code = vals.get("generated_code", "")
                        test_results = vals.get("test_results", "")
                        tests_passed = bool(vals.get("tests_passed", False))

                        await self._update_thread_metadata(session_id, "Coding")
                        stream_queue.put_nowait(StreamEvent(
                            event="interrupt",
                            data=StreamInterruptData(
                                thread_id=session_id,
                                generated_code=code,
                                test_results=test_results,
                                tests_passed=tests_passed,
                                message="Please review the generated code and test results.",
                            ).model_dump(),
                        ).model_dump())
                        return

                    final_state.update(output)

                # ── Token streaming ────────────────────────────────────────
                elif event_type == "on_chat_model_stream":
                    if node_name in suppress:
                        continue
                    chunk = event.get("data", {}).get("chunk")
                    raw = chunk.content if hasattr(chunk, "content") else getattr(chunk, "text", "")
                    token = _extract_text(raw)
                    if token:
                        full_response.append(token)
                        stream_queue.put_nowait(StreamEvent(
                            event="token",
                            data=StreamTokenData(token=token).model_dump(),
                        ).model_dump())

                # ── Token usage ────────────────────────────────────────────
                elif event_type == "on_chat_model_end":
                    out = event.get("data", {}).get("output")
                    if out:
                        usage = getattr(out, "usage_metadata", None)
                        if isinstance(usage, dict):
                            total_tokens += usage.get("total_tokens", 0)
                        else:
                            resp_meta = getattr(out, "response_metadata", None)
                            if isinstance(resp_meta, dict):
                                token_usage = resp_meta.get("token_usage")
                                if isinstance(token_usage, dict):
                                    total_tokens += token_usage.get("total_tokens", 0)

        # Use a queue to pass events from the stream task to this generator
        stream_queue: asyncio.Queue = asyncio.Queue()
        _DONE = object()

        async def _run_and_signal():
            try:
                await _run_stream()
            except asyncio.CancelledError:
                logger.info("chat_stream task cancelled (client disconnected) [thread=%s]", active_thread_id)
            except Exception as e:
                stream_queue.put_nowait({"__error__": e})
            finally:
                stream_queue.put_nowait(_DONE)

        stream_task = asyncio.create_task(_run_and_signal())

        # Spin up disconnect watcher if we have a request object
        watcher_task = None
        if request is not None:
            watcher_task = asyncio.create_task(_watch_disconnect(request, stream_task))

        try:
            while True:
                item = await stream_queue.get()
                if item is _DONE:
                    break
                if isinstance(item, dict) and "__error__" in item:
                    raise item["__error__"]
                yield item
        finally:
            stream_task.cancel()
            if watcher_task:
                watcher_task.cancel()

        if stream_task.cancelled():
            # Client disconnected mid-stream — don't emit metadata, just return
            return

        if got_interrupt:
            return

        # ── LangGraph ≥1.0: interrupt() does NOT put __interrupt__ in the
        # event stream. The stream simply ends and the interrupt is stored in
        # the checkpoint. Detect it by checking state.next after the stream.
        try:
            snap = await app.aget_state(graph_config)
            logger.info(
                "chat_stream | post-stream state.next=%s [thread=%s]",
                getattr(snap, "next", None),
                active_thread_id,
            )
            if snap and snap.next:
                # Graph is paused — extract state and emit interrupt event
                vals = snap.values or {}
                logger.info(
                    "chat_stream | interrupt via aget_state: code_len=%d tests_passed=%s",
                    len(vals.get("generated_code", "")),
                    vals.get("tests_passed"),
                )
                await self._update_thread_metadata(session_id, "Coding")
                yield StreamEvent(
                    event="interrupt",
                    data=StreamInterruptData(
                        thread_id=session_id,
                        generated_code=vals.get("generated_code", ""),
                        test_results=vals.get("test_results", ""),
                        tests_passed=bool(vals.get("tests_passed", False)),
                        message="Please review the generated code and test results.",
                    ).model_dump(),
                ).model_dump()
                return
            # Not interrupted — use final state from checkpoint if not from stream
            if not final_state and snap and snap.values:
                final_state = snap.values
        except Exception as e:
            logger.error("Failed to fetch post-stream state: %s", e)

        intent = final_state.get("intent", detected_intent)
        normalized_intent = "Coding" if str(intent).strip().lower() == "coding" else "Conversational"

        assistant_response = ""
        for msg in reversed(final_state.get("messages", [])):
            if isinstance(msg, AIMessage):
                assistant_response = _extract_text(msg.content)
                if assistant_response:
                    break
        if not assistant_response:
            assistant_response = (
                final_state.get("final_response")
                or final_state.get("generated_code")
                or "".join(full_response)
            )

        if assistant_response:
            await self._save_message(session_id, "assistant", assistant_response, user_id)
        await self._update_thread_metadata(session_id, normalized_intent)

        execution_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        if total_tokens == 0:
            try:
                import tiktoken
                enc = tiktoken.get_encoding("cl100k_base")
                total_tokens = len(enc.encode(user_message)) + len(enc.encode(assistant_response or ""))
            except Exception:
                total_tokens = max(1, len(full_response) + len(user_message.split()))

        yield StreamEvent(
            event="metadata",
            data=StreamMetadata(
                thread_id=session_id,
                total_tokens=total_tokens,
                execution_time_ms=execution_time_ms,
                intent=normalized_intent,
            ).model_dump(),
        ).model_dump()

    # ─────────────────────────────────────────────
    # resume_stream  (after human review)
    # ─────────────────────────────────────────────

    async def resume_stream(
        self,
        thread_id: str,
        user: User,
        approved: bool,
        feedback: str = "",
        request: Optional[Request] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        user_id = user.id
        active_thread_id = f"user_{user_id}_{thread_id}"
        graph_config = {"configurable": {"thread_id": active_thread_id}}
        start_time = time.perf_counter()
        full_response: list[str] = []
        total_tokens = 0
        final_state: Dict[str, Any] = {}
        got_interrupt = False

        suppress = {
            "router", "router_node",
            "planner", "planner_node",
            "re_planner", "re_planner_node",
            "coding",
            "code_tester", "code_tester_node",
            "code_reflection", "code_reflection_node",
        }

        if not approved:
            yield {"event": "status", "data": {
                "message": "⚙️ Regenerating with your feedback, please wait…"
            }}

        app = await get_chat_app()

        async def _run_resume():
            nonlocal full_response, total_tokens, final_state, got_interrupt
            async for event in app.astream_events(
                Command(resume={"approved": approved, "feedback": feedback}),
                config=graph_config,
                version="v2",
            ):
                event_type = event.get("event")
                name = event.get("name")
                node_name = event.get("metadata", {}).get("langgraph_node", "")

                if event_type == "on_chain_end" and name == "LangGraph":
                    raw_output = event.get("data", {}).get("output")
                    output = raw_output if isinstance(raw_output, dict) else {}
                    interrupts = output.get("__interrupt__", [])

                    if interrupts:
                        got_interrupt = True
                        try:
                            snap = await app.aget_state(graph_config)
                            vals = snap.values if snap else {}
                        except Exception:
                            vals = {}

                        resume_queue.put_nowait(StreamEvent(
                            event="interrupt",
                            data=StreamInterruptData(
                                thread_id=thread_id,
                                generated_code=vals.get("generated_code", ""),
                                test_results=vals.get("test_results", ""),
                                tests_passed=bool(vals.get("tests_passed", False)),
                                message="Please review the regenerated code and test results.",
                            ).model_dump(),
                        ).model_dump())
                        return

                    final_state.update(output)

                elif event_type == "on_chat_model_stream":
                    if node_name in suppress:
                        continue
                    chunk = event.get("data", {}).get("chunk")
                    raw = chunk.content if hasattr(chunk, "content") else getattr(chunk, "text", "")
                    token = _extract_text(raw)
                    if token:
                        full_response.append(token)
                        resume_queue.put_nowait(StreamEvent(
                            event="token",
                            data=StreamTokenData(token=token).model_dump(),
                        ).model_dump())

                elif event_type == "on_chat_model_end":
                    out = event.get("data", {}).get("output")
                    if out:
                        usage = getattr(out, "usage_metadata", None)
                        if isinstance(usage, dict):
                            total_tokens += usage.get("total_tokens", 0)
                        else:
                            resp_meta = getattr(out, "response_metadata", None)
                            if isinstance(resp_meta, dict):
                                token_usage = resp_meta.get("token_usage")
                                if isinstance(token_usage, dict):
                                    total_tokens += token_usage.get("total_tokens", 0)

        resume_queue: asyncio.Queue = asyncio.Queue()
        _DONE = object()

        async def _run_and_signal():
            try:
                await _run_resume()
            except asyncio.CancelledError:
                logger.info("resume_stream task cancelled (client disconnected) [thread=%s]", active_thread_id)
            except Exception as e:
                resume_queue.put_nowait({"__error__": e})
            finally:
                resume_queue.put_nowait(_DONE)

        resume_task = asyncio.create_task(_run_and_signal())

        watcher_task = None
        if request is not None:
            watcher_task = asyncio.create_task(_watch_disconnect(request, resume_task))

        try:
            while True:
                item = await resume_queue.get()
                if item is _DONE:
                    break
                if isinstance(item, dict) and "__error__" in item:
                    err_msg = f"An error occurred during resume: {item['__error__']}"
                    await self._save_message(thread_id, "assistant", err_msg, user_id)
                    yield StreamEvent(event="error", data=StreamErrorData(message=err_msg).model_dump()).model_dump()
                    return
                yield item
        finally:
            resume_task.cancel()
            if watcher_task:
                watcher_task.cancel()

        if resume_task.cancelled():
            return

        if got_interrupt:
            return

        # LangGraph ≥1.0: interrupt() may not emit __interrupt__ in the event stream.
        # Check state.next after stream ends to catch it.
        try:
            snap = await app.aget_state(graph_config)
            if snap and snap.next:
                vals = snap.values or {}
                yield StreamEvent(
                    event="interrupt",
                    data=StreamInterruptData(
                        thread_id=thread_id,
                        generated_code=vals.get("generated_code", ""),
                        test_results=vals.get("test_results", ""),
                        tests_passed=bool(vals.get("tests_passed", False)),
                        message="Please review the regenerated code and test results.",
                    ).model_dump(),
                ).model_dump()
                return
            if not final_state and snap and snap.values:
                final_state = snap.values
        except Exception as e:
            logger.error("Failed to fetch post-stream state (resume): %s", e)

        assistant_response = ""
        for msg in reversed(final_state.get("messages", [])):
            if isinstance(msg, AIMessage):
                assistant_response = _extract_text(msg.content)
                if assistant_response:
                    break
        if not assistant_response:
            assistant_response = final_state.get("final_response") or "".join(full_response)

        if assistant_response:
            await self._save_message(thread_id, "assistant", assistant_response, user_id)
            # final_response_node is not an LLM — it produces no token events.
            # Emit the full response as one token so the frontend can render it.
            if not full_response:
                yield StreamEvent(
                    event="token",
                    data=StreamTokenData(token=assistant_response).model_dump(),
                ).model_dump()
        await self._update_thread_metadata(thread_id, "Coding")

        execution_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        if total_tokens == 0:
            total_tokens = max(1, len(full_response) + len(assistant_response.split()))

        yield StreamEvent(
            event="metadata",
            data=StreamMetadata(
                thread_id=thread_id,
                total_tokens=total_tokens,
                execution_time_ms=execution_time_ms,
                intent="Coding",
            ).model_dump(),
        ).model_dump()

    # ─────────────────────────────────────────────
    # Remaining methods
    # ─────────────────────────────────────────────

    async def chat(self, user_message: str, user: User, thread_id: Optional[str] = None) -> ChatResponse:
        start_time = time.perf_counter()
        session_id = thread_id or str(uuid.uuid4())
        active_thread_id = f"user_{user.id}_{session_id}"
        await self._save_message(session_id, "user", user_message, user.id, user_message)
        graph_config = {"configurable": {"thread_id": active_thread_id}}
        new_input = {"messages": [HumanMessage(content=user_message)]}
        app = await get_chat_app()
        final_state = await app.ainvoke(new_input, config=graph_config)
        intent = final_state.get("intent", "Conversational")
        normalized_intent = "Coding" if str(intent).strip().lower() == "coding" else "Conversational"
        assistant_response = ""
        for msg in reversed(final_state.get("messages", [])):
            if isinstance(msg, AIMessage):
                assistant_response = _extract_text(msg.content)
                if assistant_response:
                    break
        if not assistant_response:
            assistant_response = final_state.get("final_response") or final_state.get("generated_code") or ""
        if assistant_response:
            await self._save_message(session_id, "assistant", assistant_response, user.id)
        await self._update_thread_metadata(session_id, normalized_intent)
        execution_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            total_tokens = len(enc.encode(user_message)) + len(enc.encode(assistant_response))
        except Exception:
            total_tokens = max(1, len(user_message.split()) + len(assistant_response.split()))
        return ChatResponse(
            response=assistant_response,
            intent=normalized_intent,
            thread_id=session_id,
            metadata=StreamMetadata(
                thread_id=session_id,
                total_tokens=total_tokens,
                execution_time_ms=execution_time_ms,
                intent=normalized_intent,
            ),
        )

    async def get_history(self, thread_id: str, user: User) -> List[MessageSchema]:
        try:
            thread_res = await self.db.execute(
                select(ChatThread).where(ChatThread.thread_id == thread_id, ChatThread.user_id == user.id)
            )
            if not thread_res.scalar_one_or_none():
                return []
            msg_res = await self.db.execute(
                select(ChatMessage)
                .where(ChatMessage.thread_id == thread_id)
                .order_by(ChatMessage.timestamp.asc(), ChatMessage.id.asc())
            )
            return [
                MessageSchema(role=m.role, content=m.content, timestamp=m.timestamp)
                for m in msg_res.scalars().all()
            ]
        except Exception as e:
            logger.error("Failed to retrieve history for thread=%s: %s", thread_id, e)
            return []

    async def get_threads(self, user: User) -> List[Dict[str, Any]]:
        try:
            res = await self.db.execute(
                select(ChatThread)
                .where(ChatThread.user_id == user.id)
                .order_by(ChatThread.updated_at.desc())
            )
            return [
                {"thread_id": t.thread_id, "preview": t.preview or "New Conversation",
                 "intent": t.intent, "updated_at": t.updated_at}
                for t in res.scalars().all()
            ]
        except Exception as e:
            logger.error("Failed to query threads for user=%s: %s", user.id, e)
            return []

    async def delete_chat(self, thread_id: str, user: User) -> None:
        try:
            await self.db.execute(
                delete(ChatThread).where(ChatThread.thread_id == thread_id, ChatThread.user_id == user.id)
            )
            await self.db.commit()
        except Exception as e:
            logger.error("Failed to delete chat thread=%s: %s", thread_id, e)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    async def new_chat(self, user: User, thread_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            new_thread_id = thread_id or str(uuid.uuid4())
            self.db.add(ChatThread(thread_id=new_thread_id, user_id=user.id))
            await self.db.commit()
            return {"thread_id": new_thread_id}
        except Exception as e:
            logger.error("Failed to create new chat for user=%s: %s", user.id, e)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
