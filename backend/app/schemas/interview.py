from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
