from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    """Request payload to start an interview session."""

    resume_id: UUID
    job_id: UUID


class QuestionOut(BaseModel):
    """Serialized question response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    question_text: str
    category: str | None
    rationale: str | None
    order_index: int
    created_at: datetime


class SessionOut(BaseModel):
    """Serialized interview session response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    resume_id: UUID | None
    job_id: UUID | None
    match_score: float | None
    match_summary: str | None
    status: str
    created_at: datetime
    completed_at: datetime | None


class SessionStartQuestionOut(BaseModel):
    """Question shape returned during interview start."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question_text: str
    category: str
    rationale: str
    order_index: int


class SessionStartOut(BaseModel):
    """Response contract for POST /interviews/start."""

    session_id: UUID
    match_score: float = Field(ge=0.0, le=1.0)
    match_summary: str
    questions: list[SessionStartQuestionOut]
