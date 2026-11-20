"""Token blacklist model for JWT revocation."""

from datetime import datetime
from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base


class TokenBlacklist(Base):
    """Blacklisted JWT tokens (by JTI) for immediate revocation."""

    __tablename__ = "token_blacklist"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(datetime.now().astimezone().tzinfo)
    )

    __table_args__ = (
        Index("ix_token_blacklist_expires_at", "expires_at"),
    )