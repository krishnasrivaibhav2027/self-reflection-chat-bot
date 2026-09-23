from backend.prompts.coding import CODING_PROMPT
from typing import TypedDict, Annotated, Sequence, Literal, List
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
import warnings
warnings.filterwarnings("ignore", message="Pydantic serializer warnings", category=UserWarning)
import psycopg
import logging
import re
import json
import asyncio as _asyncio
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.output_parsers import StrOutputParser
from backend.chatbot.schemas import TestResult, QueryIntent, ImplementationPlan, ReflectionResult
from langgraph.types import interrupt
from backend.core.config import settings
from backend.prompts.route_classification import CLASSIFY_QUERY_INTENT
from backend.prompts.conversation import CONVERSATIONAL_PROMPT
from backend.prompts.test_generation import TEST_GENERATION_PROMPT
from backend.prompts.reflection import REFLECTION_PROMPT
from backend.prompts.planning import PLANNING_PROMPT
from backend.prompts.re_planning import RE_PLANNING_PROMPT
from backend.sandbox.unified_runner import sandbox
from langchain_openai import ChatOpenAI

logger = logging.getLogger("app.chatbot")

CODING_MODEL_NAME = "mistralai/codestral-2508"
DEFAULT_MODEL_NAME = "minimax/minimax-m2.1-highspeed:free"

XKIRO_BASE_URL = "https://api.xkiro.com/v1"

default_model = ChatOpenAI(
    model=DEFAULT_MODEL_NAME,
    api_key=settings.XKIRO_API_KEY,
    base_url=XKIRO_BASE_URL,
    temperature=0.2,
)

coding_model = ChatOpenAI(
    model=CODING_MODEL_NAME,
    api_key=settings.XKIRO_API_KEY,
    base_url=XKIRO_BASE_URL,
    temperature=0.2,
)


default_model_json = ChatOpenAI(
    model=DEFAULT_MODEL_NAME,
    api_key=settings.XKIRO_API_KEY,
    base_url=XKIRO_BASE_URL,
    temperature=0.2,
    model_kwargs={"response_format": {"type": "json_object"}},
)


def _parse_json_from_text(text: str) -> dict:
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    brace_match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from model output: {text[:200]!r}")

class ChatState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    query: str
    intent: str
    plan: dict
    dependencies: List[str]
    generated_code: str
    test_results: str
    tests_passed: bool
    reflection: str
    retry_count: int
    max_retries: int
    human_feedback: str
    human_approved: bool
    final_response: str

async def router_node(state: ChatState):
    messages = state.get("messages", [])
    query = state.get("query") or (messages[-1].content if messages else "")

    chain = CLASSIFY_QUERY_INTENT | default_model_json | StrOutputParser()

    last_err = None
    for attempt in range(10):
        try:
            if attempt > 0:
                await _asyncio.sleep(min(2 ** attempt, 8))

            raw = await chain.ainvoke({"query": query})
            data = _parse_json_from_text(raw)
            result = QueryIntent(**data)

            logger.info("Router classified intent: %s (attempt %d)", result.intent, attempt + 1)
            return {"intent": result.intent}

        except Exception as e:
            last_err = e
            logger.warning("Router attempt %d failed: %s", attempt + 1, e)

    logger.error("Router failed after 10 attempts (%s), defaulting to Conversational", last_err)
    return {"intent": "Conversational"}

def route_after_intent(state: ChatState):
    intent = state.get("intent", "")
    if intent == "Conversational":
        return "conversational"
    return "planner"

async def conversation_node(state: ChatState):
    messages = list(state.get("messages", []))
    query = state.get("query") or (messages[-1].content if messages else "")

    if query and (not messages or messages[-1].content != query):
        messages.append(HumanMessage(content=query))

    conversation_chain = CONVERSATIONAL_PROMPT | default_model | StrOutputParser()

    last_err = None
    for attempt in range(10):
        try:
            if attempt > 0:
                await _asyncio.sleep(min(2 ** attempt, 8))
            response = await conversation_chain.ainvoke({"messages": messages})
            return {
                "messages": [AIMessage(content=response)],
                "final_response": response,
            }
        except Exception as e:
            last_err = e
            logger.warning("conversation_node attempt %d failed: %s", attempt + 1, e)

    raise RuntimeError(f"Conversation model failed after 10 attempts: {last_err}") from last_err

async def planner_node(state: ChatState):
    messages = state.get("messages", [])
    query = state.get("query") or (messages[-1].content if messages else "")

    logger.info("planner_node | analyzing requirements...")

    chain = PLANNING_PROMPT | default_model_json | StrOutputParser()

    last_err = None
    for attempt in range(5):
        try:
            if attempt > 0:
                await _asyncio.sleep(min(2 ** attempt, 4))

            raw = await chain.ainvoke({
                "query": query,
                "messages": messages,
            })
            data = _parse_json_from_text(raw)
            plan = ImplementationPlan(**data)

            logger.info(
                "planner_node | plan created: complexity=%s, deps=%s",
                plan.complexity, plan.dependencies
            )

            return {
                "plan": plan.model_dump(),
                "dependencies": plan.dependencies,
            }

        except Exception as e:
            last_err = e
            logger.warning("planner_node attempt %d failed: %s", attempt + 1, e)

    logger.error("planner_node failed after 5 attempts: %s, using empty plan", last_err)
    default_plan = ImplementationPlan(
        dependencies=[],
        logic_steps=["Implement solution based on requirements"],
        complexity="moderate",
        edge_cases=[],
        approach="Standard implementation"
    )

    return {
        "plan": default_plan.model_dump(),
        "dependencies": [],
    }
async def coding_node(state: ChatState):
    messages = state.get("messages", [])
    query = state.get("query") or (messages[-1].content if messages else "")
    feedback = state.get("human_feedback", "")
    reflection = state.get("reflection", "")
    coding_chain = CODING_PROMPT | coding_model | StrOutputParser()

    raw_plan = state.get("plan") or {}
    if raw_plan:
        plan_text = (
            f"Approach: {raw_plan.get('approach', '')}\n"
            f"Complexity: {raw_plan.get('complexity', '')}\n"
            f"Dependencies: {', '.join(raw_plan.get('dependencies', [])) or 'none'}\n"
            f"Steps:\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(raw_plan.get('logic_steps', []))) + "\n"
            f"Edge cases: {', '.join(raw_plan.get('edge_cases', [])) or 'none'}"
        )
    else:
        plan_text = ""

    last_err = None
    for attempt in range(10):
        try:
            if attempt > 0:
                await _asyncio.sleep(min(2 ** attempt, 8))
            code = await coding_chain.ainvoke({
                "query": query,
                "messages": messages,
                "feedback": feedback,
                "reflection": reflection,
                "plan": plan_text,
            })
            if not code or not code.strip():
                raise RuntimeError(f"Coding model ({CODING_MODEL_NAME}) returned empty response.")
            return {"generated_code": code}
        except Exception as e:
            last_err = e
            logger.warning("coding_node attempt %d failed: %s", attempt + 1, e)

    raise RuntimeError(f"Coding model failed after 10 attempts: {last_err}") from last_err

def _extract_code_block(text: str) -> str:
    """Strip markdown fences from a model response, returning only the code inside."""
    match = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


async def code_tester_node(state: ChatState):
    generated_code = state.get("generated_code", "")
    dependencies = state.get("dependencies", [])

    logger.info("code_tester_node | generating test suite…")

    test_chain = TEST_GENERATION_PROMPT | coding_model | StrOutputParser()
    raw_test_output = await test_chain.ainvoke({"code": generated_code})

    test_code = _extract_code_block(raw_test_output)

    logger.info("code_tester_node | running pytest with dependencies=%s", dependencies)

    sandbox_result = await sandbox.run_tests(
        code=generated_code,
        tests=test_code,
        dependencies=dependencies
    )

    logger.info(
        "code_tester_node | pytest result: passed=%s exit_code=%s duration=%.0fms\n%s",
        sandbox_result.passed,
        sandbox_result.exit_code,
        sandbox_result.duration_ms,
        sandbox_result.output,
    )

    current_retry = state.get("retry_count", 0)
    test_result = TestResult(
        test_result=sandbox_result.output,
        tests_passed=sandbox_result.passed,
        retry_count=current_retry + 1,
    )

    return {
        "test_results": test_result.test_result,
        "tests_passed": test_result.tests_passed,
        "retry_count": test_result.retry_count,
    }

async def code_reflection_node(state: ChatState):
    tests_passed = state.get("tests_passed", False)

    if tests_passed:
        return {"reflection": ""}

    test_results = state.get("test_results", "")
    generated_code = state.get("generated_code", "")
    messages = state.get("messages", [])
    query = state.get("query") or (messages[-1].content if messages else "")

    chain = REFLECTION_PROMPT | default_model_json | StrOutputParser()

    last_err = None
    for attempt in range(5):
        try:
            if attempt > 0:
                await _asyncio.sleep(min(2 ** attempt, 4))

            raw = await chain.ainvoke({
                "test_results": test_results,
                "messages": messages,
                "query": query,
                "generated_code": generated_code,
            })
            data = _parse_json_from_text(raw)
            result = ReflectionResult(**data)

            reflection_text = (
                f"**Summary of Failures**\n{result.summary_of_failures}\n\n"
                f"**Root Cause Analysis**\n{result.root_cause_analysis}\n\n"
                f"**Remediation Plan**\n{result.remediation_plan}"
            )
            return {"reflection": reflection_text}

        except Exception as e:
            last_err = e
            logger.warning("code_reflection_node attempt %d failed: %s", attempt + 1, e)

    logger.error("code_reflection_node failed after 5 attempts: %s", last_err)
    return {"reflection": f"Tests failed. Please review and fix the code.\n\nTest output:\n{test_results}"}

async def re_planner_node(state: ChatState):
    messages = state.get("messages", [])
    query = state.get("query") or (messages[-1].content if messages else "")
    reflection = state.get("reflection", "")
    raw_plan = state.get("plan") or {}

    previous_plan_text = (
        f"Approach: {raw_plan.get('approach', '')}\n"
        f"Complexity: {raw_plan.get('complexity', '')}\n"
        f"Dependencies: {', '.join(raw_plan.get('dependencies', [])) or 'none'}\n"
        f"Steps:\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(raw_plan.get('logic_steps', []))) + "\n"
        f"Edge cases: {', '.join(raw_plan.get('edge_cases', [])) or 'none'}"
    ) if raw_plan else "No previous plan."

    logger.info("re_planner_node | revising plan based on test failures...")

    chain = RE_PLANNING_PROMPT | default_model_json | StrOutputParser()

    last_err = None
    for attempt in range(5):
        try:
            if attempt > 0:
                await _asyncio.sleep(min(2 ** attempt, 4))

            raw = await chain.ainvoke({
                "query": query,
                "previous_plan": previous_plan_text,
                "reflection": reflection,
            })
            data = _parse_json_from_text(raw)
            plan = ImplementationPlan(**data)

            logger.info(
                "re_planner_node | revised plan: complexity=%s, deps=%s",
                plan.complexity, plan.dependencies,
            )

            return {
                "plan": plan.model_dump(),
                "dependencies": plan.dependencies,
            }

        except Exception as e:
            last_err = e
            logger.warning("re_planner_node attempt %d failed: %s", attempt + 1, e)

    logger.error("re_planner_node failed after 5 attempts: %s, keeping existing plan", last_err)
    return {"plan": raw_plan, "dependencies": raw_plan.get("dependencies", [])}


async def human_review_node(state: ChatState):
    generated_code = state.get("generated_code", "")
    test_results = state.get("test_results", "")
    tests_passed = state.get("tests_passed", False)

    logger.info(
        "human_review_node | PAUSING for human review | tests_passed=%s | code_len=%d",
        tests_passed, len(generated_code),
    )

    review_data = interrupt({
        "type": "human_review",
        "code": generated_code,
        "test_results": test_results,
        "tests_passed": tests_passed,
        "message": "Please review the generated code and test results",
    })

    logger.info("human_review_node | RESUMED with: %r", review_data)

    approved = review_data.get("approved", False) if isinstance(review_data, dict) else bool(review_data)
    feedback = (review_data.get("feedback") or "") if isinstance(review_data, dict) else ""

    return {
        "human_approved": approved,
        "human_feedback": feedback,
    }

def route_after_reflection(state: ChatState) -> Literal["human_review", "re_planner"]:
    """Route to human review if tests pass or retries exhausted, otherwise re-plan."""
    if state.get("tests_passed", False):
        return "human_review"
    if state.get("retry_count", 0) >= state.get("max_retries", 5):
        return "human_review"
    return "re_planner"

def route_after_human_review(state:ChatState) -> Literal["approved","regenerate"]:
    if state.get("human_approved", False):
        return "approved"
    return "regenerate"

async def final_response_node(state: ChatState):
    generated_code = state.get("generated_code", "").strip()
    if not generated_code.startswith("```"):
        final_code_block = f"```python\n{generated_code}\n```"
    else:
        final_code_block = generated_code

    kind_message = (
        "Great news! Your code has been reviewed, all tests passed, and it's ready to use. "
        "Here's the final version:\n\n"
        + final_code_block
        + "\n\nFeel free to ask if you need any modifications or have questions!"
    )

    return {
        "final_response": kind_message,
        "messages": [AIMessage(content=kind_message)],
    }

workflow = StateGraph(ChatState)

workflow.add_node("router", router_node)
workflow.add_node("conversational", conversation_node)
workflow.add_node("planner", planner_node)
workflow.add_node("coding", coding_node)
workflow.add_node("code_tester", code_tester_node)
workflow.add_node("code_reflection", code_reflection_node)
workflow.add_node("re_planner", re_planner_node)
workflow.add_node("human_review", human_review_node)
workflow.add_node("final_response", final_response_node)

workflow.add_edge(START, "router")
workflow.add_conditional_edges(
    "router",
    route_after_intent,
    {
        "conversational": "conversational",
        "planner": "planner",
    })
workflow.add_edge("planner", "coding")
workflow.add_edge("coding", "code_tester")
workflow.add_edge("code_tester", "code_reflection")
workflow.add_conditional_edges(
    "code_reflection",
    route_after_reflection,
    {
        "human_review": "human_review",
        "re_planner": "re_planner",       
    })
workflow.add_edge("re_planner", "coding") 
workflow.add_conditional_edges(
    "human_review",
    route_after_human_review,
    {
        "approved": "final_response",
        "regenerate": "coding",
    })

workflow.add_edge("conversational", END)
workflow.add_edge("final_response", END)


_chat_app = None

async def get_chat_app():
    global _chat_app
    if _chat_app is not None:
        return _chat_app

    conn_string = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

   
    async with await psycopg.AsyncConnection.connect(
        conn_string, autocommit=True
    ) as setup_conn:
        setup_checkpointer = AsyncPostgresSaver(setup_conn)
        await setup_checkpointer.setup()

    pool = AsyncConnectionPool(conninfo=conn_string, max_size=10, open=False)
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)

    _chat_app = workflow.compile(checkpointer=checkpointer)
    return _chat_app