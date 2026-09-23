import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from backend.auth.dependencies import get_current_user
from backend.users.models import User
from backend.chatbot.schemas import (
    ChatRequest,
    ChatResponse,
    HistoryResponse,
    ThreadSchema,
    ThreadResponse,
    ReviewRequest,
)
from backend.chatbot.service import ChatbotService

router = APIRouter(prefix = "/chatbot", tags = ["Chatbot"])

@router.post("/chat")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends()) -> StreamingResponse:
    async def event_generator():
        async for event in chatbot_service.chat_stream(
            user_message=chat_request.query,
            user=current_user,
            thread_id=chat_request.thread_id,
            request=request,
        ):
            # Stop yielding as soon as the client has gone
            if await request.is_disconnected():
                break
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/chat/sync", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat_sync(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends(),
) -> ChatResponse:
    """Non-streaming chat endpoint returning assistant response and execution metadata."""
    return await chatbot_service.chat(
        user_message=request.query,
        user=current_user,
        thread_id=request.thread_id,
    )

@router.get("/threads", response_model=ThreadResponse, status_code=status.HTTP_200_OK)
async def get_user_threads(
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends(),
) -> ThreadResponse:
    """Retrieve all conversation threads for the authenticated user."""
    try:
        threads = await chatbot_service.get_threads(current_user)

        thread_schemas = [
            ThreadSchema(
                thread_id=t["thread_id"],
                preview=t["preview"],
                intent=t["intent"],
                updated_at=t["updated_at"],
            )
            for t in threads
        ]
        return ThreadResponse(threads=thread_schemas)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred retrieving threads: {str(e)}",
        )

@router.get("/history/{thread_id}", response_model=HistoryResponse)
async def get_history(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends(),
) -> HistoryResponse:
    """Retrieve conversation history for a specific thread, scoped to the current user."""
    messages = await chatbot_service.get_history(thread_id=thread_id, user=current_user)
    return HistoryResponse(thread_id=thread_id, messages=messages)

@router.delete("/delete-chat/{thread_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(thread_id: str, current_user: User = Depends(get_current_user),chatbot_service: ChatbotService = Depends()):
    try:
        await chatbot_service.delete_chat(thread_id, current_user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred deleting chat: {str(e)}",
        )

@router.post("/review/{thread_id}")
async def review_code(
    thread_id: str,
    review: ReviewRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends(),
) -> StreamingResponse:
    """Resume a graph paused at human_review_node with approval/rejection + feedback."""
    async def event_generator():
        async for event in chatbot_service.resume_stream(
            thread_id=thread_id,
            user=current_user,
            approved=review.approved,
            feedback=review.feedback,
            request=request,
        ):
            if await request.is_disconnected():
                break
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/new-chat",status_code=status.HTTP_201_CREATED)
async def new_chat(current_user: User = Depends(get_current_user),chatbot_service: ChatbotService = Depends()):
    try:
        return await chatbot_service.new_chat(current_user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred creating new chat: {str(e)}",
        )