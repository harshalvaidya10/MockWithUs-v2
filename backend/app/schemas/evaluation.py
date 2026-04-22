from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EvalOut(BaseModel):
    """Serialized evaluation response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    answer_id: UUID
    session_id: UUID
    question_id: UUID
    question_text: str
    answer_text: str
    relevance_score: float | None
    clarity_score: float | None
    depth_score: float | None
    structure_score: float | None
    overall_score: float | None
    feedback_text: str | None
    strengths: list[str]
    improvements: list[str]
    created_at: datetime


class FeedbackOut(BaseModel):
    """Session-level interview feedback payload."""

    session_id: UUID
    overall_score: float | None
    evaluations: list[EvalOut]
