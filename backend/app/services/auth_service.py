from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings
from app.core.exceptions import AuthenticationError


settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a secure hash for a plaintext password."""

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its hash."""

    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Create a signed JWT access token for the provided subject."""

    payload: dict[str, Any] = {"sub": subject}
    if extra_claims is not None:
        payload.update(extra_claims)

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.access_token_expire_days)
    payload["exp"] = expires_at

    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_jwt_token(token: str) -> dict[str, Any]:
    """Decode a JWT and return its payload."""

    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token.") from exc
