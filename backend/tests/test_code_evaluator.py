from __future__ import annotations

import asyncio
import json

import pytest

from app.services import code_evaluator


def _sample_test_results() -> list[dict[str, object]]:
    return [
        {"passed": True, "status": "accepted", "runtime_ms": 55},
        {"passed": True, "status": "accepted", "runtime_ms": 61},
        {"passed": True, "status": "accepted", "runtime_ms": 58},
    ]


def test_evaluate_code_submission_uses_non_zero_deterministic_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_call_llm(**_: object) -> str:
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(code_evaluator, "call_llm", failing_call_llm)

    result = asyncio.run(
        code_evaluator.evaluate_code_submission(
            problem_title="Two Sum",
            problem_description="Return indices summing to target.",
            source_code="def solve(nums, target):\n    return [0, 1]\n",
            language="python",
            test_results=_sample_test_results(),
            reference_solution="def solve(nums, target):\n    return [0, 1]\n",
        )
    )

    assert result["tests_passed"] == 3
    assert result["tests_total"] == 3
    assert result["correctness_score"] == 10.0
    assert result["efficiency_score"] > 0.0
    assert result["code_quality_score"] > 0.0
    assert result["problem_solving_score"] > 0.0
    assert "Deterministic evaluation fallback used" in result["feedback_text"]


def test_evaluate_code_submission_omits_response_format_in_llm_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_call_kwargs: dict[str, object] = {}

    async def fake_call_llm(**kwargs: object) -> str:
        captured_call_kwargs.update(kwargs)
        return json.dumps(
            {
                "efficiency_score": 8.1,
                "code_quality_score": 7.9,
                "problem_solving_score": 8.0,
                "feedback_text": "Good approach.",
                "strengths": ["Correct output", "Clean logic"],
                "improvements": ["Add edge-case comments"],
                "complexity_analysis": "Time O(n), space O(n).",
            }
        )

    monkeypatch.setattr(code_evaluator, "call_llm", fake_call_llm)

    result = asyncio.run(
        code_evaluator.evaluate_code_submission(
            problem_title="Two Sum",
            problem_description="Return indices summing to target.",
            source_code="def solve(nums, target):\n    return [0, 1]\n",
            language="python",
            test_results=_sample_test_results(),
            reference_solution="def solve(nums, target):\n    return [0, 1]\n",
        )
    )

    assert "response_format" not in captured_call_kwargs
    assert result["efficiency_score"] == 8.1


def _mixed_test_results(*, passed: int, total: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(total):
        is_passed = index < passed
        rows.append(
            {
                "passed": is_passed,
                "status": "accepted" if is_passed else "wrong_answer",
                "runtime_ms": 60 + index,
                "expected_output": str(index),
                "actual_output": str(index if is_passed else index + 1),
                "input_data": {"value": index},
            }
        )
    return rows


def test_high_pass_rate_problem_solving_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_llm(**_: object) -> str:
        return json.dumps(
            {
                "efficiency_score": 7.2,
                "code_quality_score": 7.1,
                "problem_solving_score": 3.0,
                "feedback_text": "Mostly good.",
                "strengths": ["Solid structure"],
                "improvements": ["Handle one edge case"],
                "complexity_analysis": "O(n)",
            }
        )

    monkeypatch.setattr(code_evaluator, "call_llm", fake_call_llm)

    result = asyncio.run(
        code_evaluator.evaluate_code_submission(
            problem_title="Sample",
            problem_description="Desc",
            source_code="def solve(x):\n    return x\n",
            language="python",
            test_results=_mixed_test_results(passed=14, total=15),
            reference_solution="def solve(x):\n    return x\n",
        )
    )

    assert result["problem_solving_score"] >= 5.0


def test_high_pass_rate_efficiency_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_llm(**_: object) -> str:
        return json.dumps(
            {
                "efficiency_score": 2.0,
                "code_quality_score": 7.0,
                "problem_solving_score": 7.0,
                "feedback_text": "Good approach.",
                "strengths": ["Clear logic"],
                "improvements": ["Optimize constants"],
                "complexity_analysis": "O(n)",
            }
        )

    monkeypatch.setattr(code_evaluator, "call_llm", fake_call_llm)

    result = asyncio.run(
        code_evaluator.evaluate_code_submission(
            problem_title="Sample",
            problem_description="Desc",
            source_code="def solve(x):\n    return x\n",
            language="python",
            test_results=_mixed_test_results(passed=14, total=15),
            reference_solution="def solve(x):\n    return x\n",
        )
    )

    assert result["efficiency_score"] >= 4.0


def test_low_pass_rate_no_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_llm(**_: object) -> str:
        return json.dumps(
            {
                "efficiency_score": 2.0,
                "code_quality_score": 7.0,
                "problem_solving_score": 3.0,
                "feedback_text": "Needs work.",
                "strengths": ["Readable"],
                "improvements": ["Fix correctness"],
                "complexity_analysis": "O(n^2)",
            }
        )

    monkeypatch.setattr(code_evaluator, "call_llm", fake_call_llm)

    result = asyncio.run(
        code_evaluator.evaluate_code_submission(
            problem_title="Sample",
            problem_description="Desc",
            source_code="def solve(x):\n    return x\n",
            language="python",
            test_results=_mixed_test_results(passed=6, total=10),
            reference_solution="def solve(x):\n    return x\n",
        )
    )

    assert result["problem_solving_score"] == 3.0
    assert result["efficiency_score"] == 2.0


def test_evaluation_prompt_contains_reference_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_messages: list[dict[str, str]] = []

    async def fake_call_llm(**kwargs: object) -> str:
        nonlocal captured_messages
        captured_messages = kwargs["messages"]  # type: ignore[assignment]
        return json.dumps(
            {
                "efficiency_score": 7.5,
                "code_quality_score": 7.5,
                "problem_solving_score": 7.5,
                "feedback_text": "Good.",
                "strengths": ["Clean"],
                "improvements": ["More tests"],
                "complexity_analysis": "O(n)",
            }
        )

    monkeypatch.setattr(code_evaluator, "call_llm", fake_call_llm)

    asyncio.run(
        code_evaluator.evaluate_code_submission(
            problem_title="Sample",
            problem_description="Desc",
            source_code="def solve(x):\n    return x\n",
            language="python",
            test_results=_mixed_test_results(passed=14, total=15),
            reference_solution="def solve(x):\n    return x\n",
        )
    )

    system_prompt = captured_messages[0]["content"]
    user_prompt = captured_messages[1]["content"]
    assert "MAY CONTAIN BUGS" in system_prompt
    assert "expected output may be wrong" in user_prompt
