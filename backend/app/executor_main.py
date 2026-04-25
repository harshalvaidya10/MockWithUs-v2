from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.services.code_executor import (
    DEFAULT_TIMEOUT_SECONDS,
    STATUS_RUNTIME_ERROR,
    SUPPORTED_LANGUAGES,
    _execute_code_once_local,
    _invalid_identifier_result,
    _is_valid_identifier,
)

app = FastAPI(title="MockWithUs Code Executor", version="1.0.0")


class ExecuteOnceRequest(BaseModel):
    language: str
    source_code: str
    function_name: str
    input_data: Any = None
    language_signature: dict[str, Any] | None = None
    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=1, le=60)


def _validate_executor_token(header_token: str | None) -> None:
    expected = os.getenv("CODE_EXECUTOR_SHARED_SECRET", "").strip()
    allow_unauthenticated = os.getenv("CODE_EXECUTOR_ALLOW_UNAUTHENTICATED", "").strip() == "1"

    if not expected and not allow_unauthenticated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized executor request.")

    if not expected:
        return

    provided_token = (header_token or "").strip()
    if not hmac.compare_digest(provided_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized executor request.")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/execute-once")
def execute_once(
    payload: ExecuteOnceRequest,
    x_executor_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _validate_executor_token(x_executor_token)
    normalized_language = (payload.language or "").strip().lower()
    if normalized_language not in SUPPORTED_LANGUAGES:
        return {
            "actual_output": None,
            "runtime_ms": None,
            "error_output": f"Unsupported language '{payload.language}'.",
            "status": STATUS_RUNTIME_ERROR,
        }
    if not _is_valid_identifier(payload.function_name):
        return dict(_invalid_identifier_result(label="function name", value=payload.function_name))
    result = _execute_code_once_local(
        normalized_language=normalized_language,
        source_code=payload.source_code,
        function_name=payload.function_name,
        input_data=payload.input_data,
        language_signature=payload.language_signature,
        timeout_seconds=payload.timeout_seconds,
    )
    return dict(result)
