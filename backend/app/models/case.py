"""Case and Draft ORM models."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)

    # Input fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(200), nullable=True)
    petitioner_name: Mapped[str] = mapped_column(String(300), nullable=True)
    respondent_name: Mapped[str] = mapped_column(String(300), nullable=True)
    incident_date: Mapped[str] = mapped_column(String(50), nullable=True)
    case_description: Mapped[str] = mapped_column(Text, nullable=False)
    sections_alleged: Mapped[str] = mapped_column(String(500), nullable=True)
    relief_sought: Mapped[str] = mapped_column(Text, nullable=True)

    # NLP outputs
    case_type: Mapped[str] = mapped_column(String(100), nullable=True)
    case_type_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    extracted_entities: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Processing state
    status: Mapped[str] = mapped_column(String(50), default="pending")
    # Statuses: pending | processing | completed | failed

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="cases")  # noqa
    draft: Mapped["Draft"] = relationship(
        "Draft",
        back_populates="case",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Draft sections stored as JSON
    sections: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {
    #   "title_block": "...",
    #   "cause_of_action": "...",
    #   "facts": "...",
    #   "grounds": "...",
    #   "prayer": "...",
    #   "verification": "..."
    # }

    full_text: Mapped[str] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(default=1)
    model_used: Mapped[str] = mapped_column(String(100), nullable=True)
    generation_time_seconds: Mapped[float] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case: Mapped["Case"] = relationship("Case", back_populates="draft")
