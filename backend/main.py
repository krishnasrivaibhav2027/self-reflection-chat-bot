import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.users.router import router as user_router
from backend.auth.router import router as auth_router
from backend.chatbot.router import router as chatbot_router
from backend.chatbot.sandbox_router import router as sandbox_router
from backend.middleware.logging import LoggingMiddleware
from backend.middleware.exception import ExceptionMiddleware
from backend.middleware.timing import RequestTimingMiddleware
from fastapi.middleware.cors import CORSMiddleware
from backend.core.database import engine, Base
from backend.core.config import settings
from backend.users.models import User
from backend.chatbot.models import ChatThread, ChatMessage

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)
app.add_middleware(ExceptionMiddleware)
app.add_middleware(RequestTimingMiddleware)

app.include_router(user_router)
app.include_router(auth_router)
app.include_router(chatbot_router)
app.include_router(sandbox_router)

@app.get("/")
async def root():
    return {
        "message":"Welcome to your AI Coding and Personal Assistant"
    }
    
