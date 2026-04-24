from __future__ import annotations

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
