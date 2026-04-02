from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResumeOut(BaseModel):
    """Serialized resume response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    filename: str
    stored_filename: str
    parsed_text: str
    skills: list[str]
    experience: str | None
    created_at: datetime


class ResumeUploadResponse(BaseModel):
    """Response payload for successful resume uploads."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    skills: list[str]
    created_at: datetime
