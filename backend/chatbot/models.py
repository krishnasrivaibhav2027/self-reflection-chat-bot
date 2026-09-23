from sqlalchemy import Integer, String, Text, ForeignKey, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.core.database import Base

class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key = True)
    thread_id: Mapped[str] = mapped_column(String(50), unique = True, nullable = False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable = False)
    preview: Mapped[str] = mapped_column(String(255), default="New Conversation", server_default="New Conversation")
    intent: Mapped[str] = mapped_column(String(50), default = "Conversational")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default = func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default = func.now(), onupdate = func.now())
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="thread", cascade="all, delete-orphan"
    )

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("chat_threads.thread_id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    thread: Mapped[ChatThread] = relationship("ChatThread", back_populates="messages")
