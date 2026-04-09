from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SkillGapOut(BaseModel):
    matched: list[str]
    missing: list[str]
    coverage: float = Field(ge=0.0, le=1.0)


class MatchOut(BaseModel):
    match_score: float = Field(ge=0.0, le=1.0)
    skill_gaps: SkillGapOut
    match_summary: str
    resume_id: UUID
    job_id: UUID


class JobCreate(BaseModel):
    """Input validation for job description creation."""

    title: str | None = None
    company: str | None = None
    content: str = Field(..., min_length=50)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 50:
            raise ValueError("String should have at least 50 characters")
        return stripped


class JobOut(BaseModel):
    """Serialized job description response for list and create endpoints (no content field)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    company: str | None
    keywords: list[str]
    required_skills: list[str]
    created_at: datetime


class JobDetailOut(JobOut):
    """Full job description response with content field, used for GET /jobs/{id}."""

    content: str
