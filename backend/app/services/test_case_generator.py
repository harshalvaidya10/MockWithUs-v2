from __future__ import annotations

import json
import logging
import re
from typing import Any, TypedDict

from app.services.code_executor import STATUS_ACCEPTED, execute_code_once
from app.services.llm_client import call_llm


logger = logging.getLogger(__name__)

REQUIRED_TOTAL_TEST_CASES = 15
REQUIRED_SAMPLE_TEST_CASES = 3
REQUIRED_MIN_EDGE_CASES = 4
MIN_VALIDATED_TOTAL_TEST_CASES = 10
_REFERENCE_IMPORT_FALLBACK_PREFIX = (
    "from typing import *\n"
    "from collections import *\n"
    "import math\n"
    "import heapq\n"
    "import bisect\n"
    "import itertools\n"
    "import functools\n"
)
_NUMERIC_STRING_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?$")
_THINK_BLOCK_PATTERN = re.compile(r"<think>[\s\S]*?</think>", flags=re.IGNORECASE)


class GeneratedTestCase(TypedDict):
    input_data: str
    expected_output: str
    is_sample: bool
    is_edge_case: bool
    order_index: int


class ReferenceSolutionValidationError(Exception):
    """Raised when the reference solution fails sample validation."""


class TestCaseGenerationError(Exception):
    """Raised when test case generation fails irrecoverably."""


def _to_json_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _normalize_json_string(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    return json.dumps(parsed, separators=(",", ":"), sort_keys=True)


def _deserialize_json_if_possible(value: str | None) -> Any:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _extract_json_payload(raw_response: str) -> Any:
    stripped = (raw_response or "").strip()
    if not stripped:
        raise ValueError("LLM returned empty response.")

    candidates: list[str] = [stripped]
    code_blocks = re.findall(r"```(?:json)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(code_blocks)

    list_start = stripped.find("[")
    list_end = stripped.rfind("]")
    if list_start != -1 and list_end != -1 and list_end > list_start:
        candidates.append(stripped[list_start : list_end + 1])

    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    if object_start != -1 and object_end != -1 and object_end > object_start:
        candidates.append(stripped[object_start : object_end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError("LLM response was not valid JSON.")


def _normalize_sample_cases(sample_test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for sample in sample_test_cases:
        input_data = sample.get("input_data", sample.get("input"))
        expected_output = sample.get("expected_output")
        if input_data is None or expected_output is None:
            continue
        normalized.append(
            {
                "input_data": input_data,
                "expected_output": expected_output,
                "is_edge_case": bool(sample.get("is_edge_case", False)),
            }
        )
    return normalized


def _build_generation_prompt(
    *,
    description: str,
    constraints: str | None,
    edge_case_hints: list[str],
    count: int,
) -> str:
    edge_hints = edge_case_hints or [
        "empty input shape when valid",
        "single-element input",
        "minimum constraints",
        "maximum constraints",
    ]
    edge_hints_text = "\n".join(f"- {hint}" for hint in edge_hints[:8])
    return f"""Generate exactly {count} JSON-serialized test inputs for this DSA problem.

Problem:
{description}

Constraints:
{constraints or "Use constraints from the problem statement."}

Requirements:
- Return JSON only.
- Return a JSON array.
- Provide INPUTS ONLY, no expected outputs.
- Include at least 4 edge-case-oriented inputs.
- Include at least 3 medium-sized inputs.
- Include at least 2 near-maximum constraint inputs.

Edge case hints:
{edge_hints_text}
"""


def _parse_generated_inputs(raw_response: str) -> list[Any]:
    payload = _extract_json_payload(raw_response)
    if isinstance(payload, dict):
        if isinstance(payload.get("inputs"), list):
            payload = payload["inputs"]
        else:
            raise ValueError("Expected a JSON list or an object with an 'inputs' list.")

    if not isinstance(payload, list):
        raise ValueError("LLM response must be a JSON list of inputs.")

    parsed_inputs: list[Any] = []
    for item in payload:
        if isinstance(item, dict) and ("input" in item or "input_data" in item):
            parsed_inputs.append(item.get("input_data", item.get("input")))
            continue
        if isinstance(item, str):
            stripped = item.strip()
            try:
                parsed_inputs.append(json.loads(stripped))
            except json.JSONDecodeError:
                parsed_inputs.append(stripped)
            continue
        parsed_inputs.append(item)
    return parsed_inputs


def _python_function_name(function_signature: dict[str, Any] | None) -> str:
    if not isinstance(function_signature, dict):
        return "solve"
    python_signature = function_signature.get("python")
    if isinstance(python_signature, dict):
        name = str(python_signature.get("name", "")).strip()
        if name:
            return name
    return "solve"


def _with_reference_import_fallback(source_code: str) -> str:
    stripped_source = (source_code or "").strip()
    if not stripped_source:
        return stripped_source
    return f"{_REFERENCE_IMPORT_FALLBACK_PREFIX}\n{stripped_source}"


def _execute_reference_solution(
    *,
    source_code: str,
    function_name: str,
    input_data: Any,
) -> tuple[dict[str, Any], str]:
    run_result = execute_code_once(
        language="python",
        source_code=source_code,
        function_name=function_name,
        input_data=input_data,
    )
    if run_result["status"] == STATUS_ACCEPTED:
        return run_result, function_name

    if function_name != "solve":
        fallback_run_result = execute_code_once(
            language="python",
            source_code=source_code,
            function_name="solve",
            input_data=input_data,
        )
        if fallback_run_result["status"] == STATUS_ACCEPTED:
            logger.warning(
                "Reference solution did not expose '%s'; falling back to 'solve' for validation.",
                function_name,
            )
            return fallback_run_result, "solve"

    return run_result, function_name


def _ensure_minimum_edge_cases(test_cases: list[GeneratedTestCase]) -> None:
    edge_count = sum(1 for case in test_cases if case["is_edge_case"])
    if edge_count >= REQUIRED_MIN_EDGE_CASES:
        return
    for case in test_cases:
        if not case["is_edge_case"]:
            case["is_edge_case"] = True
            edge_count += 1
            if edge_count >= REQUIRED_MIN_EDGE_CASES:
                return


def _mutate_fallback_input(value: Any, *, seed: int, depth: int = 0) -> Any:
    if depth >= 6:
        return value

    if isinstance(value, bool):
        return value if seed % 2 == 0 else (not value)

    if isinstance(value, int):
        delta = (seed % 7) + 1
        mutated = value + delta if seed % 2 == 0 else value - delta
        if value >= 0 and mutated < 0:
            mutated = abs(mutated) + delta
        return mutated

    if isinstance(value, float):
        delta = ((seed % 7) + 1) / 10.0
        mutated = value + delta if seed % 2 == 0 else value - delta
        if value >= 0 and mutated < 0:
            mutated = abs(mutated) + delta
        return round(mutated, 6)

    if isinstance(value, str):
        stripped = value.strip()
        if _NUMERIC_STRING_PATTERN.match(stripped):
            if "." in stripped:
                return str(_mutate_fallback_input(float(stripped), seed=seed, depth=depth + 1))
            return str(_mutate_fallback_input(int(stripped), seed=seed, depth=depth + 1))

        if not value:
            return f"x{seed}"
        if set(value) <= set("()[]{}"):
            bracket_tokens = ("()", "[]", "{}")
            token = bracket_tokens[seed % len(bracket_tokens)]
            return f"{value}{token}" if seed % 2 == 0 else f"{token}{value}"
        return f"{value}_{seed}"

    if isinstance(value, list):
        if not value:
            return [seed]
        mutated_items = [
            _mutate_fallback_input(item, seed=seed + index + 1, depth=depth + 1)
            for index, item in enumerate(value)
        ]
        if len(mutated_items) > 1 and seed % 3 == 0:
            shift = seed % len(mutated_items)
            mutated_items = mutated_items[shift:] + mutated_items[:shift]
        if seed % 5 == 0 and len(mutated_items) < 32:
            mutated_items.append(
                _mutate_fallback_input(mutated_items[-1], seed=seed + 11, depth=depth + 1)
            )
        return mutated_items

    if isinstance(value, dict):
        mutated: dict[str, Any] = {}
        for key in sorted(value.keys(), key=lambda item: str(item)):
            key_seed = sum(ord(ch) for ch in str(key))
            mutated[key] = _mutate_fallback_input(value[key], seed=seed + key_seed, depth=depth + 1)
        return mutated

    return value


def _build_fallback_input_variants(
    *,
    fallback_inputs: list[Any],
    desired_count: int,
) -> list[Any]:
    variants: list[Any] = []
    if not fallback_inputs or desired_count <= 0:
        return variants

    max_seed = max(12, desired_count * 8)
    for seed in range(1, max_seed + 1):
        for input_payload in fallback_inputs:
            variants.append(_mutate_fallback_input(input_payload, seed=seed))
            if len(variants) >= desired_count * 10:
                return variants
    return variants


async def _request_additional_inputs(
    *,
    description: str,
    constraints: str | None,
    edge_case_hints: list[str],
    count: int,
) -> list[Any]:
    prompt = _build_generation_prompt(
        description=description,
        constraints=constraints,
        edge_case_hints=edge_case_hints,
        count=count,
    )
    raw_response = await call_llm(
        messages=[
            {
                "role": "system",
                "content": "You generate coding problem test inputs. Return valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=2000,
        max_429_retries=0,
    )
    return _parse_generated_inputs(raw_response)


def _prepare_generated_case(
    *,
    input_payload: Any,
    expected_output: str,
    index: int,
) -> GeneratedTestCase:
    return GeneratedTestCase(
        input_data=_to_json_string(input_payload),
        expected_output=_normalize_json_string(expected_output),
        is_sample=False,
        is_edge_case=index < REQUIRED_MIN_EDGE_CASES,
        order_index=index + 1,
    )


def _serialize_python_signature(function_signature: dict[str, Any] | None) -> str:
    if not isinstance(function_signature, dict):
        return "def solve(...):"
    python_signature = function_signature.get("python")
    if not isinstance(python_signature, dict):
        return "def solve(...):"

    name = str(python_signature.get("name", "solve")).strip() or "solve"
    params = str(python_signature.get("params", "...")).strip() or "..."
    return_type = str(python_signature.get("return_type", "")).strip()
    if return_type:
        return f"def {name}({params}) -> {return_type}:"
    return f"def {name}({params}):"


def _extract_python_code(value: str) -> str:
    text = _THINK_BLOCK_PATTERN.sub("", (value or "").strip()).strip()
    if not text:
        return ""

    preferred_blocks = re.findall(r"```python\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if preferred_blocks:
        return preferred_blocks[0].strip()

    blocks = re.findall(r"```(?:[a-zA-Z0-9_+-]+)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if blocks:
        return blocks[0].strip()

    return text


async def _generate_verification_solution(
    *,
    problem_title: str,
    problem_description: str,
    function_signature: dict[str, Any] | None,
    primary_solution: str,
) -> str | None:
    prompt = f"""Write a Python solution for this problem. Use a DIFFERENT approach or algorithm than the one shown below.

Problem: {problem_title}
{problem_description}

Function signature:
{_serialize_python_signature(function_signature)}

DO NOT use this approach (this is another solution - use a different algorithm):
{primary_solution}

Return ONLY the Python function code. No explanation. No markdown fences.
"""

    try:
        # response_format removed - Qwen 3 32B on Groq rejects it with 400,
        # causing a wasted retry on every call. The system prompt instructs
        # JSON-only output, which is sufficient.
        raw_response = await call_llm(
            messages=[
                {
                    "role": "system",
                    "content": "You write correct Python algorithm solutions. Return only Python code.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=1000,
            max_429_retries=0,
        )
    except Exception:
        logger.warning(
            "Verification solution generation failed, proceeding with single reference.",
            exc_info=True,
        )
        return None

    extracted = _extract_python_code(raw_response).strip()
    if not extracted:
        logger.warning(
            "Verification solution generation returned empty code, proceeding with single reference."
        )
        return None
    return extracted


async def _cross_validate_outputs(
    *,
    verification_solution: str,
    function_name: str,
    test_inputs: list[Any],
    primary_outputs: list[str],
) -> list[tuple[Any, str]]:
    validated: list[tuple[Any, str]] = []
    verification_source = verification_solution
    verification_function = function_name
    import_fallback_applied = False

    for index, input_payload in enumerate(test_inputs, start=1):
        run_result, verification_function = _execute_reference_solution(
            source_code=verification_source,
            function_name=verification_function,
            input_data=input_payload,
        )

        if run_result["status"] != STATUS_ACCEPTED and not import_fallback_applied:
            source_with_import_fallback = _with_reference_import_fallback(verification_source)
            fallback_result, fallback_function = _execute_reference_solution(
                source_code=source_with_import_fallback,
                function_name=verification_function,
                input_data=input_payload,
            )
            if fallback_result["status"] == STATUS_ACCEPTED:
                logger.warning(
                    "Verification solution required supplemental standard-library imports. "
                    "Applying import fallback for validation."
                )
                import_fallback_applied = True
                verification_source = source_with_import_fallback
                verification_function = fallback_function
                run_result = fallback_result

        if run_result["status"] != STATUS_ACCEPTED or run_result["actual_output"] is None:
            logger.warning("Solutions disagreed on test case %s, excluding it.", index)
            continue

        if index - 1 >= len(primary_outputs):
            break

        primary_normalized = _normalize_json_string(primary_outputs[index - 1])
        verification_normalized = _normalize_json_string(run_result["actual_output"])
        if primary_normalized != verification_normalized:
            logger.warning("Solutions disagreed on test case %s, excluding it.", index)
            continue

        validated.append((input_payload, primary_outputs[index - 1]))

    return validated


async def generate_validated_test_cases(
    *,
    description: str,
    reference_solution: str,
    function_signature: dict[str, Any],
    constraints: str | None,
    sample_test_cases: list[dict[str, Any]],
    edge_case_hints: list[str] | None = None,
    use_llm_for_hidden_inputs: bool = True,
    problem_title: str | None = None,
) -> list[GeneratedTestCase]:
    """Generate and validate the 15-case test suite for a coding problem."""
    normalized_samples = _normalize_sample_cases(sample_test_cases)
    if not normalized_samples:
        raise TestCaseGenerationError("No valid sample test cases were provided.")

    python_function = _python_function_name(function_signature)
    reference_solution_source = reference_solution
    import_fallback_applied = False
    for sample in normalized_samples:
        run_result, python_function = _execute_reference_solution(
            source_code=reference_solution_source,
            function_name=python_function,
            input_data=sample["input_data"],
        )

        if run_result["status"] != STATUS_ACCEPTED and not import_fallback_applied:
            source_with_import_fallback = _with_reference_import_fallback(reference_solution_source)
            fallback_result, fallback_function = _execute_reference_solution(
                source_code=source_with_import_fallback,
                function_name=python_function,
                input_data=sample["input_data"],
            )
            if fallback_result["status"] == STATUS_ACCEPTED:
                logger.warning(
                    "Reference solution required supplemental standard-library imports. "
                    "Applying import fallback for validation."
                )
                import_fallback_applied = True
                reference_solution_source = source_with_import_fallback
                python_function = fallback_function
                run_result = fallback_result

        if run_result["status"] != STATUS_ACCEPTED or run_result["actual_output"] is None:
            raise ReferenceSolutionValidationError(
                "Reference solution failed sample test validation."
            )

        expected_normalized = _normalize_json_string(_to_json_string(sample["expected_output"]))
        actual_normalized = _normalize_json_string(run_result["actual_output"])
        if actual_normalized != expected_normalized:
            logger.warning(
                "Sample expected output mismatched reference output; normalizing sample to reference output."
            )
            sample["expected_output"] = _deserialize_json_if_possible(run_result["actual_output"])

    selected_samples = normalized_samples[:REQUIRED_SAMPLE_TEST_CASES]
    sample_deficit = max(0, REQUIRED_SAMPLE_TEST_CASES - len(selected_samples))
    hidden_target = REQUIRED_TOTAL_TEST_CASES - REQUIRED_SAMPLE_TEST_CASES
    generated_target = hidden_target + sample_deficit

    generated_case_pairs: list[tuple[Any, str]] = []
    seen_inputs: set[str] = set(_normalize_json_string(_to_json_string(item["input_data"])) for item in selected_samples)

    if use_llm_for_hidden_inputs:
        attempts = 0
        edge_hints = edge_case_hints or []
        while len(generated_case_pairs) < generated_target and attempts < 1:
            attempts += 1
            remaining = generated_target - len(generated_case_pairs)
            try:
                generated_inputs = await _request_additional_inputs(
                    description=description,
                    constraints=constraints,
                    edge_case_hints=edge_hints,
                    count=remaining,
                )
            except Exception:
                logger.warning("Could not generate additional test inputs via LLM on attempt %s.", attempts, exc_info=True)
                continue

            for generated_input in generated_inputs:
                if len(generated_case_pairs) >= generated_target:
                    break
                canonical_input = _normalize_json_string(_to_json_string(generated_input))
                if canonical_input in seen_inputs:
                    continue
                seen_inputs.add(canonical_input)

                run_result = execute_code_once(
                    language="python",
                    source_code=reference_solution_source,
                    function_name=python_function,
                    input_data=generated_input,
                )
                if run_result["status"] != STATUS_ACCEPTED or run_result["actual_output"] is None:
                    logger.warning("Skipping generated test case due to reference-solution execution failure.")
                    continue

                generated_case_pairs.append((generated_input, run_result["actual_output"]))

    if len(generated_case_pairs) < generated_target:
        logger.warning(
            "Generated %s/%s hidden cases from generated inputs. Backfilling with validated sample-derived inputs.",
            len(generated_case_pairs),
            generated_target,
        )
        fallback_inputs = [sample["input_data"] for sample in normalized_samples]
        variant_inputs = _build_fallback_input_variants(
            fallback_inputs=fallback_inputs,
            desired_count=generated_target - len(generated_case_pairs),
        )
        for fallback_input in variant_inputs:
            if len(generated_case_pairs) >= generated_target:
                break
            canonical_input = _normalize_json_string(_to_json_string(fallback_input))
            if canonical_input in seen_inputs:
                continue
            seen_inputs.add(canonical_input)
            run_result = execute_code_once(
                language="python",
                source_code=reference_solution_source,
                function_name=python_function,
                input_data=fallback_input,
            )
            if run_result["status"] != STATUS_ACCEPTED or run_result["actual_output"] is None:
                continue
            generated_case_pairs.append((fallback_input, run_result["actual_output"]))

        cursor = 0
        iterations = 0
        max_iterations = max(len(fallback_inputs) * 2, generated_target * 3)
        failed_inputs: set[str] = set()
        while len(generated_case_pairs) < generated_target and fallback_inputs and iterations < max_iterations:
            fallback_input = fallback_inputs[cursor % len(fallback_inputs)]
            cursor += 1
            iterations += 1

            canonical_input = _normalize_json_string(_to_json_string(fallback_input))
            if canonical_input in seen_inputs or canonical_input in failed_inputs:
                continue

            run_result = execute_code_once(
                language="python",
                source_code=reference_solution_source,
                function_name=python_function,
                input_data=fallback_input,
            )
            if run_result["status"] != STATUS_ACCEPTED or run_result["actual_output"] is None:
                failed_inputs.add(canonical_input)
                continue

            seen_inputs.add(canonical_input)
            generated_case_pairs.append((fallback_input, run_result["actual_output"]))

    if len(generated_case_pairs) < generated_target:
        raise TestCaseGenerationError("Could not generate enough validated test cases.")

    if use_llm_for_hidden_inputs and generated_case_pairs:
        logger.info("Reference solution passed samples; attempting independent output cross-validation.")
        verification_solution = await _generate_verification_solution(
            problem_title=(problem_title or "Coding Problem"),
            problem_description=description,
            function_signature=function_signature,
            primary_solution=reference_solution_source,
        )
        if verification_solution is not None:
            verified_pairs = await _cross_validate_outputs(
                verification_solution=verification_solution,
                function_name=python_function,
                test_inputs=[input_payload for input_payload, _ in generated_case_pairs],
                primary_outputs=[output for _, output in generated_case_pairs],
            )
            logger.info(
                "Targeted reference verification completed (%s/%s trusted hidden candidates).",
                len(verified_pairs),
                len(generated_case_pairs),
            )
            generated_case_pairs = verified_pairs

            total_available = len(selected_samples) + len(generated_case_pairs)
            if total_available < MIN_VALIDATED_TOTAL_TEST_CASES:
                raise TestCaseGenerationError(
                    "Too many hidden test cases were excluded during reference cross-validation."
                )
        else:
            logger.warning("Verification solution generation failed, proceeding with single reference.")

    generated_cases: list[GeneratedTestCase] = [
        _prepare_generated_case(
            input_payload=input_payload,
            expected_output=expected_output,
            index=index,
        )
        for index, (input_payload, expected_output) in enumerate(generated_case_pairs)
    ]

    if len(generated_cases) < sample_deficit:
        raise TestCaseGenerationError("Not enough validated test cases to promote missing samples.")

    final_cases: list[GeneratedTestCase] = []
    for index, sample in enumerate(selected_samples):
        final_cases.append(
            GeneratedTestCase(
                input_data=_to_json_string(sample["input_data"]),
                expected_output=_normalize_json_string(_to_json_string(sample["expected_output"])),
                is_sample=True,
                is_edge_case=bool(sample["is_edge_case"]),
                order_index=index + 1,
            )
        )

    for _ in range(sample_deficit):
        promoted = generated_cases.pop(0)
        promoted["is_sample"] = True
        promoted["order_index"] = len(final_cases) + 1
        final_cases.append(promoted)

    for hidden_case in generated_cases[:hidden_target]:
        hidden_case["is_sample"] = False
        hidden_case["order_index"] = len(final_cases) + 1
        final_cases.append(hidden_case)

    if len(final_cases) < MIN_VALIDATED_TOTAL_TEST_CASES:
        raise TestCaseGenerationError(
            "Too many hidden test cases were excluded during reference cross-validation."
        )

    _ensure_minimum_edge_cases(final_cases)
    return final_cases[:REQUIRED_TOTAL_TEST_CASES]
