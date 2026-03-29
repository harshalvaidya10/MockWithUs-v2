from __future__ import annotations

from app.services.auth_service import create_access_token, decode_jwt_token, hash_password, verify_password


def test_hash_and_verify_password() -> None:
    """Ensure password hashing and verification work."""

    password = "example-password"
    hashed_password = hash_password(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password)


def test_create_and_decode_access_token() -> None:
    """Ensure access tokens can be round-tripped."""

    token = create_access_token("test-user-id")
    payload = decode_jwt_token(token)

    assert payload["sub"] == "test-user-id"
