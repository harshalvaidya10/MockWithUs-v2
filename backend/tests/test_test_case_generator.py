from __future__ import annotations

import asyncio
import json

import pytest

from app.services import coding_problem_generator
from app.services import test_case_generator


def test_generate_validated_test_cases_applies_import_fallback_for_reference_solution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_seen: list[str] = []
    expected_prefix = "from typing import *"

    def fake_execute_code_once(*, language: str, source_code: str, function_name: str, input_data: object):  # type: ignore[no-untyped-def]
        source_seen.append(source_code)
        if expected_prefix in source_code:
            payload = input_data[0] if isinstance(input_data, list) and input_data else input_data
            return {
                "status": test_case_generator.STATUS_ACCEPTED,
                "actual_output": json.dumps(payload),
                "runtime_ms": 1,
                "error_output": None,
            }
        return {
            "status": "runtime_error",
            "actual_output": None,
            "runtime_ms": 1,
            "error_output": "NameError: name 'List' is not defined",
        }

    monkeypatch.setattr(test_case_generator, "execute_code_once", fake_execute_code_once)

    cases = asyncio.run(
        test_case_generator.generate_validated_test_cases(
            description="Return the first item.",
            reference_solution="def solve(nums: List[int]):\n    return nums[0]\n",
            function_signature={"python": {"name": "solve", "params": "nums: list[int]", "return_type": "int"}},
            constraints="1 <= n <= 10^5",
            sample_test_cases=[
                {"input_data": [[3, 4, 5]], "expected_output": 3},
                {"input_data": [[9, 10]], "expected_output": 9},
            ],
            edge_case_hints=["small input"],
            use_llm_for_hidden_inputs=False,
        )
    )

    assert len(cases) == test_case_generator.REQUIRED_TOTAL_TEST_CASES
    assert any(expected_prefix in source for source in source_seen)


def test_reference_solution_retry_on_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm_problem_calls = 0
    solution_retry_calls = 0
    validation_calls = 0
    bad_solution = "def solve(nums):\n    raise RuntimeError('bad solution')\n"
    good_solution = "def solve(nums):\n    return sum(nums)\n"

    async def fake_generate_problem_with_llm(**_: object) -> dict[str, object]:
        nonlocal llm_problem_calls
        llm_problem_calls += 1
        return {
            "title": "Retryable Problem",
            "description": "Given nums, return sum(nums).",
            "difficulty": "medium",
            "category": "arrays",
            "constraints": "1 <= len(nums) <= 10^5",
            "function_signature": {
                "python": {"name": "solve", "params": "nums: list[int]", "return_type": "int"},
                "javascript": {"name": "solve", "params": "nums", "return_type": "number"},
                "java": {"name": "solve", "params": "int[] nums", "return_type": "int"},
                "cpp": {"name": "solve", "params": "vector<int>& nums", "return_type": "int"},
            },
            "starter_code": {
                "python": "def solve(nums):\n    return 0\n",
                "javascript": "function solve(nums) {\n  return 0;\n}\n",
                "java": "public class Main { public static int solve(int[] nums) { return 0; } }\n",
                "cpp": "#include <bits/stdc++.h>\nusing namespace std;\nint solve(vector<int>& nums){return 0;}\n",
            },
            "reference_solution": bad_solution,
            "sample_test_cases": [
                {"input_data": [[1, 2, 3]], "expected_output": 6},
                {"input_data": [[5]], "expected_output": 5},
            ],
            "edge_case_hints": ["single element"],
        }

    async def fake_retry_reference_solution(**kwargs: object) -> str:
        nonlocal solution_retry_calls
        solution_retry_calls += 1
        assert kwargs["failed_solution"] == bad_solution
        return good_solution

    async def fake_generate_validated_test_cases(**kwargs: object) -> list[dict[str, object]]:
        nonlocal validation_calls
        validation_calls += 1
        if kwargs["reference_solution"] == bad_solution:
            raise test_case_generator.ReferenceSolutionValidationError(
                "Reference solution failed sample test validation."
            )
        return [
            {
                "input_data": "[1,2,3]",
                "expected_output": "6",
                "is_sample": True,
                "is_edge_case": False,
                "order_index": 1,
            }
        ]

    monkeypatch.setattr(coding_problem_generator, "_generate_problem_with_llm", fake_generate_problem_with_llm)
    monkeypatch.setattr(coding_problem_generator, "_retry_reference_solution", fake_retry_reference_solution)
    monkeypatch.setattr(coding_problem_generator, "generate_validated_test_cases", fake_generate_validated_test_cases)
    monkeypatch.setattr(
        coding_problem_generator,
        "_fallback_problem_set",
        lambda: pytest.fail("Fallback should not be used when targeted retry succeeds."),
    )

    result = asyncio.run(
        coding_problem_generator.generate_coding_problem_for_job(
            job_text="Need backend engineer",
            required_skills=["python"],
            company_name="Acme",
            requested_difficulty="medium",
        )
    )

    assert llm_problem_calls == 1
    assert solution_retry_calls == 1
    assert validation_calls == 2
    assert result["problem"]["reference_solution"] == good_solution


def test_generate_validated_test_cases_derives_diverse_fallback_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute_code_once(*, language: str, source_code: str, function_name: str, input_data: object):  # type: ignore[no-untyped-def]
        return {
            "status": test_case_generator.STATUS_ACCEPTED,
            "actual_output": json.dumps(input_data),
            "runtime_ms": 10,
            "error_output": None,
        }

    monkeypatch.setattr(test_case_generator, "execute_code_once", fake_execute_code_once)

    cases = asyncio.run(
        test_case_generator.generate_validated_test_cases(
            description="Return input as-is.",
            reference_solution="def solve(nums):\n    return nums\n",
            function_signature={"python": {"name": "solve", "params": "nums: list[int]", "return_type": "list[int]"}},
            constraints="1 <= n <= 10^5",
            sample_test_cases=[
                {"input_data": [[1]], "expected_output": [[1]]},
                {"input_data": [[2]], "expected_output": [[2]]},
                {"input_data": [[3]], "expected_output": [[3]]},
            ],
            edge_case_hints=["small input"],
            use_llm_for_hidden_inputs=False,
        )
    )

    hidden_cases = [case for case in cases if not case["is_sample"]]
    assert len(cases) == test_case_generator.REQUIRED_TOTAL_TEST_CASES
    assert len(hidden_cases) == (test_case_generator.REQUIRED_TOTAL_TEST_CASES - test_case_generator.REQUIRED_SAMPLE_TEST_CASES)

    unique_hidden_inputs = {case["input_data"] for case in hidden_cases}
    assert len(unique_hidden_inputs) >= 6


def test_generate_validated_test_cases_backfill_skips_duplicate_sample_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute_code_once(*, language: str, source_code: str, function_name: str, input_data: object):  # type: ignore[no-untyped-def]
        payload = input_data[0] if isinstance(input_data, list) and input_data else input_data
        return {
            "status": test_case_generator.STATUS_ACCEPTED,
            "actual_output": json.dumps(payload),
            "runtime_ms": 5,
            "error_output": None,
        }

    monkeypatch.setattr(test_case_generator, "execute_code_once", fake_execute_code_once)
    monkeypatch.setattr(test_case_generator, "_build_fallback_input_variants", lambda **_: [])

    with pytest.raises(test_case_generator.TestCaseGenerationError, match="enough validated"):
        asyncio.run(
            test_case_generator.generate_validated_test_cases(
                description="Return input value.",
                reference_solution="def solve(nums):\n    return nums[0]\n",
                function_signature={"python": {"name": "solve", "params": "nums: list[int]", "return_type": "int"}},
                constraints="1 <= n <= 10^5",
                sample_test_cases=[
                    {"input_data": [[1]], "expected_output": 1},
                    {"input_data": [[2]], "expected_output": 2},
                    {"input_data": [[3]], "expected_output": 3},
                ],
                edge_case_hints=["small input"],
                use_llm_for_hidden_inputs=False,
            )
        )


def test_cross_validation_excludes_disagreements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute_code_once(*, language: str, source_code: str, function_name: str, input_data: object):  # type: ignore[no-untyped-def]
        if input_data == "case-bad":
            return {
                "status": test_case_generator.STATUS_ACCEPTED,
                "actual_output": "3",
                "runtime_ms": 5,
                "error_output": None,
            }
        return {
            "status": test_case_generator.STATUS_ACCEPTED,
            "actual_output": "5",
            "runtime_ms": 5,
            "error_output": None,
        }

    monkeypatch.setattr(test_case_generator, "execute_code_once", fake_execute_code_once)

    validated = asyncio.run(
        test_case_generator._cross_validate_outputs(
            verification_solution="def solve(x):\n    return 0\n",
            function_name="solve",
            test_inputs=["case-good", "case-bad"],
            primary_outputs=["5", "5"],
        )
    )

    assert validated == [("case-good", "5")]


def test_cross_validation_keeps_agreements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute_code_once(*, language: str, source_code: str, function_name: str, input_data: object):  # type: ignore[no-untyped-def]
        return {
            "status": test_case_generator.STATUS_ACCEPTED,
            "actual_output": "5",
            "runtime_ms": 5,
            "error_output": None,
        }

    monkeypatch.setattr(test_case_generator, "execute_code_once", fake_execute_code_once)

    validated = asyncio.run(
        test_case_generator._cross_validate_outputs(
            verification_solution="def solve(x):\n    return 0\n",
            function_name="solve",
            test_inputs=["case-1", "case-2"],
            primary_outputs=["5", "5"],
        )
    )

    assert validated == [("case-1", "5"), ("case-2", "5")]


def test_verification_failure_falls_back_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute_code_once(*, language: str, source_code: str, function_name: str, input_data: object):  # type: ignore[no-untyped-def]
        payload = input_data[0] if isinstance(input_data, list) and input_data else input_data
        return {
            "status": test_case_generator.STATUS_ACCEPTED,
            "actual_output": json.dumps(payload),
            "runtime_ms": 5,
            "error_output": None,
        }

    async def fake_request_additional_inputs(**_: object) -> list[object]:
        return [[10], [11], [12], [13], [14], [15], [16], [17], [18], [19], [20], [21]]

    async def fake_generate_verification_solution(**_: object) -> str | None:
        return None

    monkeypatch.setattr(test_case_generator, "execute_code_once", fake_execute_code_once)
    monkeypatch.setattr(test_case_generator, "_request_additional_inputs", fake_request_additional_inputs)
    monkeypatch.setattr(
        test_case_generator,
        "_generate_verification_solution",
        fake_generate_verification_solution,
    )

    cases = asyncio.run(
        test_case_generator.generate_validated_test_cases(
            description="Return input value.",
            reference_solution="def solve(nums):\n    return nums[0]\n",
            function_signature={"python": {"name": "solve", "params": "nums: list[int]", "return_type": "int"}},
            constraints="1 <= n <= 10^5",
            sample_test_cases=[
                {"input_data": [[1]], "expected_output": 1},
                {"input_data": [[2]], "expected_output": 2},
                {"input_data": [[3]], "expected_output": 3},
            ],
            edge_case_hints=["small input"],
            use_llm_for_hidden_inputs=True,
        )
    )

    assert len(cases) == test_case_generator.REQUIRED_TOTAL_TEST_CASES


def test_minimum_test_case_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute_code_once(*, language: str, source_code: str, function_name: str, input_data: object):  # type: ignore[no-untyped-def]
        payload = input_data[0] if isinstance(input_data, list) and input_data else input_data
        return {
            "status": test_case_generator.STATUS_ACCEPTED,
            "actual_output": json.dumps(payload),
            "runtime_ms": 5,
            "error_output": None,
        }

    async def fake_request_additional_inputs(**_: object) -> list[object]:
        return [[10], [11], [12], [13], [14], [15], [16], [17], [18], [19], [20], [21]]

    async def fake_generate_verification_solution(**_: object) -> str | None:
        return "def solve(nums):\n    return nums[0]\n"

    async def fake_cross_validate_outputs(**_: object) -> list[tuple[object, str]]:
        return [([10], "10"), ([11], "11"), ([12], "12"), ([13], "13"), ([14], "14"), ([15], "15")]

    monkeypatch.setattr(test_case_generator, "execute_code_once", fake_execute_code_once)
    monkeypatch.setattr(test_case_generator, "_request_additional_inputs", fake_request_additional_inputs)
    monkeypatch.setattr(
        test_case_generator,
        "_generate_verification_solution",
        fake_generate_verification_solution,
    )
    monkeypatch.setattr(test_case_generator, "_cross_validate_outputs", fake_cross_validate_outputs)

    with pytest.raises(test_case_generator.TestCaseGenerationError, match="excluded"):
        asyncio.run(
            test_case_generator.generate_validated_test_cases(
                description="Return input value.",
                reference_solution="def solve(nums):\n    return nums[0]\n",
                function_signature={"python": {"name": "solve", "params": "nums: list[int]", "return_type": "int"}},
                constraints="1 <= n <= 10^5",
                sample_test_cases=[
                    {"input_data": [[1]], "expected_output": 1},
                    {"input_data": [[2]], "expected_output": 2},
                    {"input_data": [[3]], "expected_output": 3},
                ],
                edge_case_hints=["small input"],
                use_llm_for_hidden_inputs=True,
            )
        )
