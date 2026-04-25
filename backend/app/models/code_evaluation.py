from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CodeEvaluation(Base):
    """Persisted code submission evaluation and feedback."""

    __tablename__ = "code_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tests_passed: Mapped[int] = mapped_column(Integer, nullable=False)
    tests_total: Mapped[int] = mapped_column(Integer, nullable=False)
    pass_rate: Mapped[float] = mapped_column(Float, nullable=False)
    correctness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    efficiency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    code_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    problem_solving_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    improvements: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    expected_solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    complexity_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
