"""Session tracking ORM model for login/logout history."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class SessionStatus(PyEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    LOGOUT = "logout"
    REVOKED = "revoked"


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_token_jti: Mapped[str] = mapped_column(String, unique=True, index=True)
    refresh_token_jti: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=True)
    
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.ACTIVE)
    
    # Timestamps
    login_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    logout_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Client info
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)  # IPv6 max 45 chars
    device_info: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")  # noqa: F821


# Add to User model:
# sessions: Mapped[list["UserSession"]] = relationship("UserSession", back_populates="user", lazy="select")