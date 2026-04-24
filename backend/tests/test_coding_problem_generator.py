from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.services import coding_problem_generator


def test_extract_json_from_markdown_fences() -> None:
    raw = '```json\n{"title": "Two Sum", "difficulty": "medium"}\n```'
    result = coding_problem_generator._extract_json_object(raw)
    assert result["title"] == "Two Sum"


def test_extract_json_with_preamble() -> None:
    raw = 'Here is the problem:\n{"title": "Two Sum", "difficulty": "medium"}'
    result = coding_problem_generator._extract_json_object(raw)
    assert result["title"] == "Two Sum"


def test_extract_json_with_trailing_commas() -> None:
    raw = '{"title": "Two Sum", "items": ["a", "b",], "difficulty": "medium",}'
    result = coding_problem_generator._extract_json_object(raw)
    assert result["title"] == "Two Sum"


def test_extract_json_with_think_block_prefix() -> None:
    raw = (
        "<think>\nNeed to reason first.\n</think>\n"
        '{"title": "Two Sum", "difficulty": "medium"}'
    )
    result = coding_problem_generator._extract_json_object(raw)
    assert result["title"] == "Two Sum"


def test_extract_json_skips_invalid_first_brace_candidate() -> None:
    raw = (
        "Reasoning scratch {not valid json}\n"
        '{"title": "Two Sum", "difficulty": "medium"}'
    )
    result = coding_problem_generator._extract_json_object(raw)
    assert result["title"] == "Two Sum"


def test_extract_json_plain() -> None:
    raw = '{"title": "Two Sum", "difficulty": "medium"}'
    result = coding_problem_generator._extract_json_object(raw)
    assert result["title"] == "Two Sum"


def test_extract_json_invalid_raises() -> None:
    with pytest.raises(ValueError, match="not a valid JSON object"):
        coding_problem_generator._extract_json_object("This is not JSON at all")


def test_normalize_problem_payload_accepts_nested_alias_keys() -> None:
    payload = {
        "problem": {
            "title": "Two Number Sum",
            "description": "Find indices of two numbers that add up to target.",
            "difficulty": "medium",
            "solution": (
                "```python\n"
                "def two_sum(nums, target):\n"
                "    seen = {}\n"
                "    for index, value in enumerate(nums):\n"
                "        remain = target - value\n"
                "        if remain in seen:\n"
                "            return [seen[remain], index]\n"
                "        seen[value] = index\n"
                "    return []\n"
                "```"
            ),
            "samples": [
                {"input": "[[2,7,11,15],9]", "output": "[0,1]"},
                {"input": [[3, 2, 4], 6], "expected": [1, 2]},
            ],
        }
    }

    normalized = coding_problem_generator._normalize_problem_payload(payload, requested_difficulty="medium")

    assert normalized["title"] == "Two Number Sum"
    assert normalized["function_signature"]["python"]["name"] == "two_sum"
    assert normalized["sample_test_cases"][0]["input_data"] == [[2, 7, 11, 15], 9]
    assert normalized["sample_test_cases"][0]["expected_output"] == [0, 1]
    assert "```" not in normalized["reference_solution"]
    assert normalized["constraints"]


def test_normalize_problem_payload_wraps_class_solution_with_solve_entrypoint() -> None:
    payload = {
        "title": "Two Sum Class Style",
        "description": "Return the pair of indices that sums to target.",
        "reference_solution": (
            "```python\n"
            "class Solution:\n"
            "    def twoSum(self, nums, target):\n"
            "        seen = {}\n"
            "        for i, value in enumerate(nums):\n"
            "            if target - value in seen:\n"
            "                return [seen[target - value], i]\n"
            "            seen[value] = i\n"
            "        return []\n"
            "```"
        ),
        "sample_test_cases": [
            {"input_data": [[2, 7, 11, 15], 9], "expected_output": [0, 1]},
            {"input_data": [[3, 2, 4], 6], "expected_output": [1, 2]},
        ],
    }

    normalized = coding_problem_generator._normalize_problem_payload(payload, requested_difficulty="medium")

    assert normalized["function_signature"]["python"]["name"] == "solve"
    assert "def solve(*args, **kwargs):" in normalized["reference_solution"]
    assert "Solution().twoSum(*args, **kwargs)" in normalized["reference_solution"]


def _fallback_problem() -> dict[str, object]:
    return {
        "title": "Fallback Problem",
        "description": "Fallback description",
        "difficulty": "medium",
        "category": "arrays",
        "constraints": "1 <= n <= 10^5",
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
        "reference_solution": "def solve(nums):\n    return 0\n",
        "sample_test_cases": [
            {"input_data": [[1, 2, 3]], "expected_output": 0},
            {"input_data": [[5]], "expected_output": 0},
        ],
        "edge_case_hints": ["empty input"],
    }


def test_generate_problem_with_llm_uses_configured_timeout_and_fast_429_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_call_kwargs: dict[str, object] = {}

    async def fake_call_llm(**kwargs) -> str:  # type: ignore[no-untyped-def]
        captured_call_kwargs.update(kwargs)
        return json.dumps(
            {
                "title": "Contains Duplicate",
                "description": "Determine whether an array contains duplicates.",
                "difficulty": "medium",
                "reference_solution": (
                    "def solve(nums):\n"
                    "    seen = set()\n"
                    "    for value in nums:\n"
                    "        if value in seen:\n"
                    "            return True\n"
                    "        seen.add(value)\n"
                    "    return False\n"
                ),
                "sample_test_cases": [
                    {"input_data": [[1, 2, 3, 1]], "expected_output": True},
                    {"input_data": [[1, 2, 3, 4]], "expected_output": False},
                ],
            }
        )

    monkeypatch.setattr(coding_problem_generator, "call_llm", fake_call_llm)

    generated = asyncio.run(
        coding_problem_generator._generate_problem_with_llm(
            job_text="Need Python engineer comfortable with arrays and hashing.",
            required_skills=["python", "hashing"],
            company_name="Acme",
            requested_difficulty="medium",
        )
    )

    assert generated["title"] == "Contains Duplicate"
    assert captured_call_kwargs["timeout_seconds"] == coding_problem_generator.PROBLEM_GENERATION_TIMEOUT_SECONDS
    assert captured_call_kwargs["max_429_retries"] == coding_problem_generator.PROBLEM_GENERATION_MAX_429_RETRIES
    assert captured_call_kwargs["max_tokens"] == 2200


def test_no_response_format_in_call_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_call_kwargs: dict[str, object] = {}

    async def fake_call_llm(**kwargs) -> str:  # type: ignore[no-untyped-def]
        captured_call_kwargs.update(kwargs)
        return json.dumps(
            {
                "title": "Contains Duplicate",
                "description": "Determine whether an array contains duplicates.",
                "difficulty": "medium",
                "reference_solution": (
                    "def solve(nums):\n"
                    "    seen = set()\n"
                    "    for value in nums:\n"
                    "        if value in seen:\n"
                    "            return True\n"
                    "        seen.add(value)\n"
                    "    return False\n"
                ),
                "sample_test_cases": [
                    {"input_data": [[1, 2, 3, 1]], "expected_output": True},
                    {"input_data": [[1, 2, 3, 4]], "expected_output": False},
                ],
            }
        )

    monkeypatch.setattr(coding_problem_generator, "call_llm", fake_call_llm)

    asyncio.run(
        coding_problem_generator._generate_problem_with_llm(
            job_text="Need Python engineer comfortable with arrays and hashing.",
            required_skills=["python", "hashing"],
            company_name="Acme",
            requested_difficulty="medium",
        )
    )

    assert "response_format" not in captured_call_kwargs


def test_generate_coding_problem_short_circuits_to_fallback_on_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm_attempts = 0

    async def fake_generate_problem_with_llm(**_: object) -> dict[str, object]:
        nonlocal llm_attempts
        llm_attempts += 1
        request = httpx.Request("POST", "https://api.test/chat/completions")
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("429 Too Many Requests", request=request, response=response)

    async def fake_generate_validated_test_cases(**_: object) -> list[dict[str, object]]:
        return [
            {
                "input_data": "[1,2,3]",
                "expected_output": "0",
                "is_sample": True,
                "is_edge_case": False,
                "order_index": 1,
            }
        ]

    monkeypatch.setattr(coding_problem_generator, "_generate_problem_with_llm", fake_generate_problem_with_llm)
    monkeypatch.setattr(coding_problem_generator, "_fallback_problem_set", lambda: [_fallback_problem()])
    monkeypatch.setattr(coding_problem_generator, "generate_validated_test_cases", fake_generate_validated_test_cases)

    result = asyncio.run(
        coding_problem_generator.generate_coding_problem_for_job(
            job_text="Need backend engineer",
            required_skills=["python"],
            company_name="Acme",
            requested_difficulty="medium",
        )
    )

    assert llm_attempts == 1
    assert result["problem"]["title"] == "Fallback Problem"


def test_generate_coding_problem_respects_total_budget_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm_attempts = 0

    async def fake_generate_problem_with_llm(**_: object) -> dict[str, object]:
        nonlocal llm_attempts
        llm_attempts += 1
        monkeypatch.setattr(coding_problem_generator, "PROBLEM_GENERATION_TOTAL_BUDGET_SECONDS", 0.0)
        raise ValueError("invalid model payload")

    async def fake_generate_validated_test_cases(**_: object) -> list[dict[str, object]]:
        return [
            {
                "input_data": "[1]",
                "expected_output": "0",
                "is_sample": True,
                "is_edge_case": False,
                "order_index": 1,
            }
        ]

    monkeypatch.setattr(coding_problem_generator, "_generate_problem_with_llm", fake_generate_problem_with_llm)
    monkeypatch.setattr(coding_problem_generator, "_fallback_problem_set", lambda: [_fallback_problem()])
    monkeypatch.setattr(coding_problem_generator, "generate_validated_test_cases", fake_generate_validated_test_cases)

    result = asyncio.run(
        coding_problem_generator.generate_coding_problem_for_job(
            job_text="Need backend engineer",
            required_skills=["python"],
            company_name="Acme",
            requested_difficulty="medium",
        )
    )

    assert llm_attempts == 1
    assert result["problem"]["title"] == "Fallback Problem"
