"""Chat history ORM model for tracking legal assistant conversations."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import String, DateTime, Enum, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class ChatSource(PyEnum):
    LEGAL_ASSISTANT = "legal_assistant"
    AI_CHAT = "ai_chat"
    CASE_CHAT = "case_chat"


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.id", ondelete="SET NULL"), index=True, nullable=True)
    
    source: Mapped[ChatSource] = mapped_column(Enum(ChatSource), default=ChatSource.LEGAL_ASSISTANT)
    
    # Conversation data
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Metadata
    category: Mapped[str] = mapped_column(String(100), nullable=True)  # legal category
    language: Mapped[str] = mapped_column(String(10), default="english")
    model_used: Mapped[str] = mapped_column(String(100), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(default=False)
    
    # Structured response data
    key_points: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    next_steps: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    applicable_laws: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    disclaimer: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="chat_history")  # noqa: F821
    case: Mapped[Optional["Case"]] = relationship("Case", back_populates="chat_history")  # noqa: F821


# Add to User model:
# chat_history: Mapped[list["ChatHistory"]] = relationship("ChatHistory", back_populates="user", lazy="select")

# Add to Case model:
# chat_history: Mapped[list["ChatHistory"]] = relationship("ChatHistory", back_populates="case", lazy="select")