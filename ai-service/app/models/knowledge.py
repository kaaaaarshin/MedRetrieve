import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, JSON, Integer, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.core.ai_database import AIBase
from app.core.config import settings

DIMS = settings.EMBEDDING_DIMENSIONS


class VerifiedReport(AIBase):
    """
    Every verified+delivered report stored as a few-shot example.
    When a new case arrives, top-k similar reports are retrieved and
    injected into GPT-4o prompt so it learns from this centre's patterns.
    """
    __tablename__ = "ai_verified_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    radiologist_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    modality: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    body_part: Mapped[str] = mapped_column(String(100), nullable=False)
    clinical_indication: Mapped[str | None] = mapped_column(Text, nullable=True)

    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    impression: Mapped[str | None] = mapped_column(Text, nullable=True)
    icd_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    urgency_flag: Mapped[str] = mapped_column(String(10), default="ROUTINE")

    # How much the radiologist changed from AI suggestion
    ai_impression_accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ai_impression_modified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fields_accepted: Mapped[list | None] = mapped_column(JSON, nullable=True)
    fields_modified: Mapped[list | None] = mapped_column(JSON, nullable=True)
    fields_rejected: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Embedding of findings+impression for semantic similarity search
    embedding: Mapped[list | None] = mapped_column(Vector(DIMS), nullable=True)


class SuggestionFeedback(AIBase):
    """
    Granular feedback on every suggestion shown to the radiologist.
    Raw signal for the learning loop — what was accepted, modified, rejected.
    """
    __tablename__ = "ai_suggestion_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    radiologist_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    modality: Mapped[str] = mapped_column(String(10), nullable=False)
    body_part: Mapped[str] = mapped_column(String(100), nullable=False)
    session_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)

    impression_shown: Mapped[str | None] = mapped_column(Text, nullable=True)
    impression_action: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ACCEPTED/MODIFIED/REJECTED
    impression_final: Mapped[str | None] = mapped_column(Text, nullable=True)

    icd_shown: Mapped[list | None] = mapped_column(JSON, nullable=True)
    icd_accepted: Mapped[list | None] = mapped_column(JSON, nullable=True)
    icd_rejected: Mapped[list | None] = mapped_column(JSON, nullable=True)
    icd_added_by_doctor: Mapped[list | None] = mapped_column(JSON, nullable=True)

    recommendations_shown: Mapped[list | None] = mapped_column(JSON, nullable=True)
    recommendations_accepted: Mapped[list | None] = mapped_column(JSON, nullable=True)
    recommendations_rejected: Mapped[list | None] = mapped_column(JSON, nullable=True)

    urgency_shown: Mapped[str | None] = mapped_column(String(10), nullable=True)
    urgency_accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    urgency_final: Mapped[str | None] = mapped_column(String(10), nullable=True)

    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
