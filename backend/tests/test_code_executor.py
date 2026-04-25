from __future__ import annotations

import json
import subprocess
import urllib.error

import pytest

from app.services import code_executor
from app.services.code_executor import STATUS_ACCEPTED, STATUS_RUNTIME_ERROR, execute_code_once


def test_execute_code_once_python_falls_back_to_single_payload_arg_on_signature_mismatch() -> None:
    source_code = """
def solve(nums):
    return len(nums)
"""
    result = execute_code_once(
        language="python",
        source_code=source_code,
        function_name="solve",
        input_data=[1, 2, 3, 4],
    )

    assert result["status"] == STATUS_ACCEPTED
    assert (result["actual_output"] or "").strip() == "4"


def test_execute_code_once_python_does_not_mask_internal_type_errors() -> None:
    source_code = """
def solve(nums):
    return nums + 1
"""
    result = execute_code_once(
        language="python",
        source_code=source_code,
        function_name="solve",
        input_data=[1, 2, 3],
    )

    assert result["status"] == STATUS_RUNTIME_ERROR
    assert result["error_output"] is not None


def test_execute_code_once_rejects_invalid_function_identifier() -> None:
    result = execute_code_once(
        language="python",
        source_code="def solve(x):\n    return x\n",
        function_name='solve";import os',
        input_data=[1],
    )

    assert result["status"] == STATUS_RUNTIME_ERROR
    assert result["error_output"] is not None
    assert "Invalid function name" in result["error_output"]


def test_execute_code_once_rejects_invalid_java_class_identifier_before_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _bad_class_name(_source_code: str) -> str:
        return 'Main";System.exit(1);//'

    def _should_not_run_java(**_kwargs: object) -> None:
        raise AssertionError("Java execution should not run for invalid class names.")

    monkeypatch.setattr(code_executor, "_detect_java_class_name", _bad_class_name)
    monkeypatch.setattr(code_executor, "_execute_java", _should_not_run_java)

    result = execute_code_once(
        language="java",
        source_code="public class Main {}",
        function_name="solve",
        input_data=None,
        language_signature={"params": ""},
    )

    assert result["status"] == STATUS_RUNTIME_ERROR
    assert result["error_output"] is not None
    assert "Invalid class name" in result["error_output"]


def test_run_process_uses_sanitized_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_kwargs: dict[str, object] = {}

    def _fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_kwargs.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "should-not-leak")
    monkeypatch.setattr(code_executor.subprocess, "run", _fake_run)

    result = code_executor._run_process(command=["python3", "-V"], stdin_payload="", timeout_seconds=1)
    assert result["status"] == STATUS_ACCEPTED

    env = captured_kwargs["env"]
    assert isinstance(env, dict)
    assert "PATH" in env
    assert env.get("LANG") == "C.UTF-8"
    assert env.get("LC_ALL") == "C.UTF-8"
    assert "AWS_SECRET_ACCESS_KEY" not in env


def test_run_process_returns_runtime_error_for_subprocess_setup_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_setup_error(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.SubprocessError("sandbox setup failed")

    monkeypatch.setattr(code_executor.subprocess, "run", _raise_setup_error)

    result = code_executor._run_process(command=["python3", "-V"], stdin_payload="", timeout_seconds=1)
    assert result["status"] == STATUS_RUNTIME_ERROR
    assert result["error_output"] is not None
    assert "sandbox setup failed" in result["error_output"].lower()


def test_execute_code_once_uses_remote_executor_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request: dict[str, object] = {}

    class _FakeResponse:
        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "status": STATUS_ACCEPTED,
                    "actual_output": "4",
                    "runtime_ms": 7,
                    "error_output": None,
                }
            ).encode("utf-8")

    def _fake_urlopen(request: object, timeout: int):  # type: ignore[no-untyped-def]
        captured_request["request"] = request
        captured_request["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setenv("CODE_EXECUTION_MODE", "remote")
    monkeypatch.setenv("CODE_EXECUTOR_URL", "http://executor:9000")
    monkeypatch.setenv("CODE_EXECUTOR_SHARED_SECRET", "test-secret")
    monkeypatch.setattr(code_executor.urllib.request, "urlopen", _fake_urlopen)

    result = execute_code_once(
        language="python",
        source_code="def solve(nums):\n    return len(nums)\n",
        function_name="solve",
        input_data=[1, 2, 3, 4],
    )

    assert result["status"] == STATUS_ACCEPTED
    assert result["actual_output"] == "4"
    assert captured_request["timeout"] == 13


def test_execute_code_once_remote_executor_unavailable_returns_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_url_error(*_args: object, **_kwargs: object):  # type: ignore[no-untyped-def]
        raise urllib.error.URLError("executor unavailable")

    monkeypatch.setenv("CODE_EXECUTION_MODE", "remote")
    monkeypatch.setenv("CODE_EXECUTOR_URL", "http://executor:9000")
    monkeypatch.setattr(code_executor.urllib.request, "urlopen", _raise_url_error)

    result = execute_code_once(
        language="python",
        source_code="def solve(nums):\n    return len(nums)\n",
        function_name="solve",
        input_data=[1, 2, 3],
    )

    assert result["status"] == STATUS_RUNTIME_ERROR
    assert result["error_output"] is not None
    assert "remote executor unavailable" in result["error_output"].lower()
