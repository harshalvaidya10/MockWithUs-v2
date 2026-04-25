from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.executor_main import _validate_executor_token


def test_validate_executor_token_rejects_when_secret_missing_and_unauth_not_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODE_EXECUTOR_SHARED_SECRET", raising=False)
    monkeypatch.delenv("CODE_EXECUTOR_ALLOW_UNAUTHENTICATED", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        _validate_executor_token(None)

    assert exc_info.value.status_code == 401


def test_validate_executor_token_allows_when_secret_missing_and_unauth_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODE_EXECUTOR_SHARED_SECRET", raising=False)
    monkeypatch.setenv("CODE_EXECUTOR_ALLOW_UNAUTHENTICATED", "1")

    _validate_executor_token(None)


def test_validate_executor_token_rejects_mismatch_when_secret_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODE_EXECUTOR_SHARED_SECRET", "expected-token")
    monkeypatch.delenv("CODE_EXECUTOR_ALLOW_UNAUTHENTICATED", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        _validate_executor_token("wrong-token")

    assert exc_info.value.status_code == 401


def test_validate_executor_token_accepts_match_when_secret_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODE_EXECUTOR_SHARED_SECRET", "expected-token")
    monkeypatch.delenv("CODE_EXECUTOR_ALLOW_UNAUTHENTICATED", raising=False)

    _validate_executor_token("expected-token")
