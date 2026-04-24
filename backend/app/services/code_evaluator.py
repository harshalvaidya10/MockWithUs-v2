from __future__ import annotations

import json
import logging
import re
from statistics import median
from typing import Any, TypedDict

from app.services.llm_client import call_llm


logger = logging.getLogger(__name__)
_TRAILING_COMMA_PATTERN = re.compile(r",\s*([}\]])")
_THINK_BLOCK_PATTERN = re.compile(r"<think>[\s\S]*?</think>", flags=re.IGNORECASE)
_EVALUATION_SYSTEM_PROMPT = """You are an expert code reviewer. Evaluate strictly.

CRITICAL EVALUATION RULES:
- The reference solution is provided for context but MAY CONTAIN BUGS.
  Do NOT assume the reference is always correct.
- If the candidate's solution passes most test cases (>80%) but fails a few,
  consider whether the candidate's approach might still be correct and expected outputs could be wrong.
- Evaluate the candidate's algorithm and logic on its own merits.
- Distinguish "candidate logic is wrong" from "candidate output differs from expected";
  output mismatch alone is not proof the candidate is wrong.
- If pass rate is 90%+ with a clean, well-reasoned approach, keep problem-solving scoring fair.

Respond ONLY with JSON.
"""


class CodeEvaluationResult(TypedDict):
    tests_passed: int
    tests_total: int
    pass_rate: float
    correctness_score: float
    efficiency_score: float
    code_quality_score: float
    problem_solving_score: float
    overall_score: float
    feedback_text: str
    strengths: list[str]
    improvements: list[str]
    expected_solution: str
    complexity_analysis: str


def _clamp_score(value: float) -> float:
    return max(0.0, min(10.0, float(value)))


def _round_score(value: float) -> float:
    return round(_clamp_score(value), 2)


def _extract_json_object(payload: str) -> dict[str, Any]:
    text = (payload or "").strip()
    if not text:
        raise ValueError("LLM response is empty.")

    text = _THINK_BLOCK_PATTERN.sub("", text).strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1 :] if first_newline != -1 else ""
    text = text.strip()
    if text.endswith("```"):
        text = text[:-3]
    text = _TRAILING_COMMA_PATTERN.sub(r"\1", text).strip()

    candidates: list[str] = [text]
    code_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(_TRAILING_COMMA_PATTERN.sub(r"\1", block.strip()) for block in code_blocks if block.strip())

    for start_idx, char in enumerate(text):
        if char != "{":
            continue
        depth = 0
        for index in range(start_idx, len(text)):
            current = text[index]
            if current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(_TRAILING_COMMA_PATTERN.sub(r"\1", text[start_idx : index + 1]))
                    break

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("LLM response does not contain a valid JSON object.")


def _runtime_metrics(test_results: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    runtimes: list[float] = []
    for result in test_results:
        raw_runtime = result.get("runtime_ms")
        try:
            runtime = float(raw_runtime)
        except (TypeError, ValueError):
            continue
        if runtime >= 0:
            runtimes.append(runtime)
    if not runtimes:
        return None, None
    return median(runtimes), max(runtimes)


def _deterministic_efficiency_score(*, pass_rate: float, test_results: list[dict[str, Any]]) -> float:
    median_runtime, max_runtime = _runtime_metrics(test_results)
    if median_runtime is None or max_runtime is None:
        base = 6.0
    elif median_runtime <= 25 and max_runtime <= 60:
        base = 9.2
    elif median_runtime <= 60 and max_runtime <= 140:
        base = 8.2
    elif median_runtime <= 120 and max_runtime <= 250:
        base = 7.2
    else:
        base = 6.0

    scaled = base * (0.55 + (0.45 * pass_rate))
    if pass_rate >= 0.95:
        scaled += 0.4
    return _round_score(max(3.0, scaled))


def _deterministic_code_quality_score(*, source_code: str, pass_rate: float) -> float:
    cleaned = (source_code or "").strip()
    if not cleaned:
        return 2.5

    lines = [line for line in cleaned.splitlines() if line.strip()]
    line_count = len(lines)
    score = 4.0
    if 6 <= line_count <= 120:
        score += 1.2
    if re.search(r"\b(def|class|return|if|for|while|try|except|switch|case)\b", cleaned):
        score += 1.4
    if re.search(r"#|//|/\*|\*/", cleaned):
        score += 0.6
    if re.search(r"\bTODO\b|\bpass\b", cleaned):
        score -= 0.8
    score += pass_rate * 2.2
    return _round_score(max(2.5, score))


def _deterministic_problem_solving_score(
    *,
    correctness_score: float,
    efficiency_score: float,
    code_quality_score: float,
) -> float:
    weighted = (0.60 * correctness_score) + (0.25 * efficiency_score) + (0.15 * code_quality_score)
    return _round_score(weighted)


def _fallback_feedback(
    *,
    tests_passed: int,
    tests_total: int,
    pass_rate: float,
) -> tuple[str, list[str], list[str], str]:
    strengths: list[str] = []
    improvements: list[str] = []
    if pass_rate >= 0.95:
        strengths.append("Excellent correctness across the full visible test suite.")
    elif pass_rate >= 0.7:
        strengths.append("Core logic works for most tested scenarios.")
    else:
        improvements.append("Review edge cases and input-boundary handling.")

    if tests_total > 0:
        strengths.append(f"Passed {tests_passed}/{tests_total} deterministic test cases.")
    if pass_rate < 1.0:
        improvements.append("Use failing test outputs to identify branch conditions not handled yet.")
    improvements.append("Add brief comments for non-obvious logic to improve readability.")

    feedback_text = (
        "Deterministic evaluation fallback used because AI scoring was unavailable. "
        f"Current run passed {tests_passed}/{tests_total} tests."
    )
    complexity_analysis = (
        "AI complexity analysis unavailable. Deterministic fallback scored runtime behavior "
        "from observed execution times."
    )
    return feedback_text, strengths[:6], improvements[:6], complexity_analysis


def correctness_score_from_pass_rate(pass_rate: float) -> float:
    if pass_rate >= 1.0:
        return 10.0
    if pass_rate >= 0.8:
        return _round_score(8.0 + ((pass_rate - 0.8) * 10))
    if pass_rate >= 0.5:
        return _round_score(5.0 + ((pass_rate - 0.5) * 10))
    return _round_score(pass_rate * 10)


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            output.append(text)
    return output[:6]


def _coerce_float(payload: dict[str, Any], key: str) -> float:
    raw_value = payload.get(key)
    if raw_value is None:
        raise ValueError(f"Missing key: {key}")
    try:
        return _round_score(float(raw_value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric key: {key}") from exc


def _build_test_summary(test_results: list[dict[str, Any]]) -> str:
    failed_cases = [result for result in test_results if not bool(result.get("passed"))]
    failed_fragments: list[str] = []
    for idx, result in enumerate(failed_cases[:8], start=1):
        status = str(result.get("status", "unknown"))
        failed_fragments.append(f"Case {idx}: {status}")
    failed_text = "; ".join(failed_fragments) if failed_fragments else "None"
    return failed_text


def _build_failed_case_details(test_results: list[dict[str, Any]]) -> str:
    failed_cases = [result for result in test_results if not bool(result.get("passed"))]
    if not failed_cases:
        return "None"

    lines: list[str] = []
    for idx, result in enumerate(failed_cases[:8], start=1):
        input_value = result.get("input_data", result.get("input", "Unavailable"))
        expected_value = result.get("expected_output")
        actual_value = result.get("actual_output")
        lines.append(f"Test case {idx}:")
        lines.append(f"  Input: {input_value!r}")
        lines.append(f"  Expected output (from reference): {expected_value!r}")
        lines.append(f"  Candidate's output: {actual_value!r}")
        lines.append(
            "  Note: If the candidate's output appears logically correct for this input, "
            "the reference solution may have a bug on this case."
        )
    return "\n".join(lines)


def _compute_overall(
    *,
    correctness: float,
    efficiency: float,
    code_quality: float,
    problem_solving: float,
) -> float:
    weighted = (
        (0.40 * correctness)
        + (0.20 * efficiency)
        + (0.15 * code_quality)
        + (0.25 * problem_solving)
    )
    return _round_score(weighted)


async def evaluate_code_submission(
    *,
    problem_title: str,
    problem_description: str,
    source_code: str,
    language: str,
    test_results: list[dict[str, Any]],
    reference_solution: str,
) -> CodeEvaluationResult:
    """Evaluate coding submission using deterministic correctness and LLM quality analysis."""
    tests_total = len(test_results)
    tests_passed = sum(1 for result in test_results if bool(result.get("passed")))
    pass_rate = (tests_passed / tests_total) if tests_total > 0 else 0.0

    correctness_score = correctness_score_from_pass_rate(pass_rate)
    efficiency_score = _deterministic_efficiency_score(pass_rate=pass_rate, test_results=test_results)
    code_quality_score = _deterministic_code_quality_score(source_code=source_code, pass_rate=pass_rate)
    problem_solving_score = _deterministic_problem_solving_score(
        correctness_score=correctness_score,
        efficiency_score=efficiency_score,
        code_quality_score=code_quality_score,
    )
    feedback_text, strengths, improvements, complexity_analysis = _fallback_feedback(
        tests_passed=tests_passed,
        tests_total=tests_total,
        pass_rate=pass_rate,
    )

    summary_text = _build_test_summary(test_results)
    failed_case_details = _build_failed_case_details(test_results)
    pass_rate_percent = round(pass_rate * 100, 2)
    prompt = f"""Problem Title:
{problem_title}

Problem Description:
{problem_description[:1800]}

Candidate Language:
{language}

Candidate Source Code:
{source_code[:6000]}

Test Results:
Passed {tests_passed} / {tests_total}
Pass rate context: The candidate passed {tests_passed}/{tests_total} test cases ({pass_rate_percent}%).
If pass rate is above 80%, failing cases may be due to reference solution bugs rather than candidate errors.
Failed cases: {summary_text}

## Failed Test Cases (review carefully - expected output may be wrong)
{failed_case_details}

Reference Solution:
{reference_solution[:4000]}

Return strict JSON with:
efficiency_score (0-10),
code_quality_score (0-10),
problem_solving_score (0-10),
feedback_text (string),
strengths (string array),
improvements (string array),
complexity_analysis (string).
"""

    try:
        # response_format removed - Qwen 3 32B on Groq rejects it with 400,
        # causing a wasted retry on every call. The system prompt instructs
        # JSON-only output, which is sufficient.
        response_text = await call_llm(
            messages=[
                {"role": "system", "content": _EVALUATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1000,
        )
        payload = _extract_json_object(response_text)
        efficiency_score = _coerce_float(payload, "efficiency_score")
        code_quality_score = _coerce_float(payload, "code_quality_score")
        problem_solving_score = _coerce_float(payload, "problem_solving_score")

        feedback_candidate = str(payload.get("feedback_text", "")).strip()
        if feedback_candidate:
            feedback_text = feedback_candidate
        strengths = _coerce_string_list(payload.get("strengths"))
        improvements = _coerce_string_list(payload.get("improvements"))
        complexity_candidate = str(payload.get("complexity_analysis", "")).strip()
        if complexity_candidate:
            complexity_analysis = complexity_candidate
    except Exception:
        logger.exception("LLM code evaluation failed; returning deterministic fallback.")

    if pass_rate > 0.85:
        original_problem_solving = problem_solving_score
        if original_problem_solving < 5.0:
            problem_solving_score = 5.0
            logger.info(
                "Adjusted problem_solving_score floor to 5.0 for high-pass-rate submission "
                "(pass_rate=%.2f, original_score=%.1f)",
                pass_rate,
                original_problem_solving,
            )

        original_efficiency = efficiency_score
        if original_efficiency < 4.0:
            efficiency_score = 4.0
            logger.info(
                "Adjusted efficiency_score floor to 4.0 for high-pass-rate submission "
                "(pass_rate=%.2f, original_score=%.1f)",
                pass_rate,
                original_efficiency,
            )

    overall_score = _compute_overall(
        correctness=correctness_score,
        efficiency=efficiency_score,
        code_quality=code_quality_score,
        problem_solving=problem_solving_score,
    )

    return CodeEvaluationResult(
        tests_passed=tests_passed,
        tests_total=tests_total,
        pass_rate=round(pass_rate, 4),
        correctness_score=correctness_score,
        efficiency_score=efficiency_score,
        code_quality_score=code_quality_score,
        problem_solving_score=problem_solving_score,
        overall_score=overall_score,
        feedback_text=feedback_text,
        strengths=strengths,
        improvements=improvements,
        expected_solution=reference_solution,
        complexity_analysis=complexity_analysis,
    )
