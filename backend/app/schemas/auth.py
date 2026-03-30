from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    """Request payload for user registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """Request payload for user login."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """JWT token response payload."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"


class SignupResponse(BaseModel):
    """Response payload returned after successful signup."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None
    created_at: datetime


class CurrentUserResponse(BaseModel):
    """Response payload for the authenticated user profile."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None
    created_at: datetime


# Backward-compatible aliases for existing imports.
Token = TokenResponse
UserOut = CurrentUserResponse
