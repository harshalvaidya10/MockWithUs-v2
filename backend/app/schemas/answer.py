from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AudioAnswerOut(BaseModel):
    """Response payload for persisted audio answers."""

    model_config = ConfigDict(from_attributes=True)

    answer_id: UUID
    session_id: UUID
    question_id: UUID
    transcript_text: str
    created_at: datetime


class SessionAnswerItemOut(BaseModel):
    """Stored answer metadata used by frontend for interview resume state."""

    model_config = ConfigDict(from_attributes=True)

    answer_id: UUID
    session_id: UUID
    question_id: UUID
    transcript_text: str | None
    created_at: datetime


class SessionAnswerListOut(BaseModel):
    """List answers for a session."""

    session_id: UUID
    answers: list[SessionAnswerItemOut]
