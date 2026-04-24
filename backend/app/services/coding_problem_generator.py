from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, TypedDict

import httpx

from app.services.llm_client import call_llm
from app.services.test_case_generator import (
    GeneratedTestCase,
    ReferenceSolutionValidationError,
    TestCaseGenerationError,
    generate_validated_test_cases,
)


logger = logging.getLogger(__name__)

_REQUIRED_LANGUAGES = ("python", "javascript", "java", "cpp")
_CORE_REQUIRED_FIELDS = ("title", "description", "reference_solution")
_SAMPLE_TEST_CASE_KEYS = ("sample_test_cases", "sample_cases", "samples", "examples", "test_cases")
_EDGE_CASE_HINT_KEYS = ("edge_case_hints", "edge_case_notes", "hints", "edge_cases")
_REFERENCE_SOLUTION_KEYS = ("reference_solution", "solution", "python_solution", "referenceSolution")
_CONSTRAINT_KEYS = ("constraints", "constraint", "limits")
_CATEGORY_KEYS = ("category", "topic", "domain")
_TRAILING_COMMA_PATTERN = re.compile(r",\s*([}\]])")
_THINK_BLOCK_PATTERN = re.compile(r"<think>[\s\S]*?</think>", flags=re.IGNORECASE)

_SYSTEM_PROMPT = (
    "You are an expert competitive programming problem setter who creates problems "
    "for platforms like LeetCode and HackerRank.\n\n"
    "Generate a single DSA coding problem tailored to the candidate's job description.\n\n"
    "PROBLEM QUALITY RULES:\n"
    "- Write the problem as a clear, self-contained story with a concrete scenario.\n"
    "- State EXACTLY what the input represents, what the output should be, and the "
    "return type - leave ZERO ambiguity.\n"
    "- The problem description must be understandable WITHOUT looking at the examples. "
    "The examples CONFIRM understanding, they don't REPLACE the description.\n"
    "- Use simple, direct language. A strong candidate should fully understand the "
    "problem in under 2 minutes of reading.\n"
    "- Constraints must be precise numerical ranges (e.g., '1 <= nums.length <= 10^4'), "
    "NOT vague descriptions.\n"
    "- Each example must include a step-by-step explanation showing HOW the output "
    "is derived from the input.\n"
    "- The function signature must match the actual input/output types. If the problem "
    "takes two arrays, the signature takes two arrays - not 'nums' and 'target'.\n"
    "- Difficulty should match the requested level: medium = requires one key insight "
    "or data structure, hard = requires combining multiple techniques or optimizations.\n"
    "- IMPORTANT: The function signature parameters must EXACTLY match the input structure. "
    "If the problem takes an array of events and a list of operations, the function "
    "signature must reflect that - not generic 'nums' and 'target' placeholders.\n\n"
    "BAD EXAMPLE (vague, unclear):\n"
    "  Title: 'Data Processor'\n"
    "  Description: 'Process operations on data and return results for queries.'\n"
    "  This is bad because it doesn't explain WHAT the operations do or HOW to process them.\n\n"
    "GOOD EXAMPLE (clear, specific, LeetCode-quality):\n"
    "  Title: 'Minimum Platforms Required'\n"
    "  Description: 'Given two arrays arrival[] and departure[] representing train times "
    "at a station, find the minimum number of platforms required so that no train waits. "
    "A platform is occupied from arrival[i] to departure[i] inclusive. Two trains can "
    "share a platform only if one departs strictly before the other arrives.'\n"
    "  This is good because you know EXACTLY what to compute and the precise rule for overlap.\n\n"
    "IMPORTANT: The function signature parameters must EXACTLY match the input structure. "
    "If the problem takes an array of events and a list of operations, the function "
    "signature must reflect that - not generic 'nums' and 'target' placeholders.\n\n"
    "Do NOT output chain-of-thought, reasoning traces, or <think> tags.\n"
    "Respond ONLY with valid JSON. No prose, no markdown."
)
# Keep low to minimize 429 risk on Groq free tier.
MAX_PRIMARY_PROBLEM_ATTEMPTS = 2
PROBLEM_GENERATION_TIMEOUT_SECONDS = 20.0
PROBLEM_GENERATION_MIN_TIMEOUT_SECONDS = 8.0
PROBLEM_GENERATION_TOTAL_BUDGET_SECONDS = 30.0
PROBLEM_GENERATION_MAX_429_RETRIES = 0


class GeneratedCodingProblem(TypedDict):
    title: str
    description: str
    difficulty: str
    category: str
    constraints: str
    function_signature: dict[str, dict[str, str]]
    starter_code: dict[str, str]
    reference_solution: str
    sample_test_cases: list[dict[str, Any]]
    edge_case_hints: list[str]


class CodingProblemGenerationResult(TypedDict):
    problem: GeneratedCodingProblem
    test_cases: list[GeneratedTestCase]


def _truncate_text(value: str, *, limit: int) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."


def _parsed_json_to_problem_payload(parsed: Any) -> dict[str, Any] | None:
    if isinstance(parsed, dict):
        for nested_key in ("problem", "response", "output"):
            nested_payload = parsed.get(nested_key)
            if isinstance(nested_payload, dict):
                return nested_payload
            if isinstance(nested_payload, str):
                nested_candidate = _TRAILING_COMMA_PATTERN.sub(r"\1", nested_payload.strip())
                try:
                    nested_parsed = json.loads(nested_candidate)
                except json.JSONDecodeError:
                    continue
                if isinstance(nested_parsed, dict):
                    return nested_parsed
        return parsed

    if isinstance(parsed, list):
        first_object = next((item for item in parsed if isinstance(item, dict)), None)
        if first_object is not None:
            return first_object

    return None


def _extract_json_object(payload: str) -> dict[str, Any]:
    raw_text = (payload or "").strip()
    if not raw_text:
        raise ValueError("LLM returned empty payload.")

    text = raw_text
    text = _THINK_BLOCK_PATTERN.sub("", text).strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1 :] if first_newline != -1 else ""
    text = text.strip()
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    text = _TRAILING_COMMA_PATTERN.sub(r"\1", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    payload_object = _parsed_json_to_problem_payload(parsed)
    if payload_object is not None:
        return payload_object

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
                    candidate = _TRAILING_COMMA_PATTERN.sub(r"\1", text[start_idx : index + 1])
                    try:
                        candidate_parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        continue
                    payload_object = _parsed_json_to_problem_payload(candidate_parsed)
                    if payload_object is not None:
                        return payload_object
                    continue

    raise ValueError(
        "LLM payload is not a valid JSON object. "
        f"Raw text starts with: {text[:200]!r}"
    )


def _first_present_value(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload and payload.get(key) is not None:
            return payload.get(key)
    return None


def _coerce_json_if_possible(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _extract_code_block(value: str, *, language: str | None = None) -> str:
    stripped = (value or "").strip()
    if not stripped:
        return ""

    pattern = r"```(?:[a-zA-Z0-9_+-]+)?\s*(.*?)```"
    if language:
        preferred_pattern = rf"```{re.escape(language)}\s*(.*?)```"
        preferred_blocks = re.findall(preferred_pattern, stripped, flags=re.IGNORECASE | re.DOTALL)
        if preferred_blocks:
            return preferred_blocks[0].strip()

    blocks = re.findall(pattern, stripped, flags=re.IGNORECASE | re.DOTALL)
    if blocks:
        return blocks[0].strip()
    return stripped


def _extract_python_function_names(source_code: str) -> list[str]:
    found_names = re.findall(r"(?m)^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source_code or "")
    seen: set[str] = set()
    ordered: list[str] = []
    for name in found_names:
        if name.startswith("__"):
            continue
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def _has_top_level_python_function(*, source_code: str, function_name: str) -> bool:
    escaped_name = re.escape(function_name)
    return re.search(rf"(?m)^def\s+{escaped_name}\s*\(", source_code or "") is not None


def _append_solution_wrapper_if_needed(reference_solution: str, *, function_name: str) -> str:
    if not reference_solution.strip():
        return reference_solution
    if _has_top_level_python_function(source_code=reference_solution, function_name=function_name):
        return reference_solution

    method_match = re.search(
        r"class\s+Solution\b[\s\S]*?^\s+def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(self(?:\s*,|\s*\))",
        reference_solution,
        flags=re.MULTILINE,
    )
    if method_match is None:
        return reference_solution

    method_name = method_match.group(1)
    wrapper = (
        "\n\n"
        f"def {function_name}(*args, **kwargs):\n"
        f"    return Solution().{method_name}(*args, **kwargs)\n"
    )
    return f"{reference_solution.rstrip()}{wrapper}"


def _resolve_reference_solution(payload: dict[str, Any]) -> str:
    raw_reference_solution = _first_present_value(payload, _REFERENCE_SOLUTION_KEYS)
    if isinstance(raw_reference_solution, dict):
        python_value = raw_reference_solution.get("python")
        if isinstance(python_value, str) and python_value.strip():
            raw_reference_solution = python_value
        else:
            raw_reference_solution = ""

    if isinstance(raw_reference_solution, list):
        if all(isinstance(item, str) for item in raw_reference_solution):
            raw_reference_solution = "\n".join(item.strip() for item in raw_reference_solution if item.strip())
        else:
            raw_reference_solution = ""

    if not isinstance(raw_reference_solution, str):
        return ""
    return _extract_code_block(raw_reference_solution, language="python")


def _resolve_sample_cases(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sample_cases_raw = _first_present_value(payload, _SAMPLE_TEST_CASE_KEYS)
    if not isinstance(sample_cases_raw, list):
        return []

    sample_cases: list[dict[str, Any]] = []
    for item in sample_cases_raw:
        if not isinstance(item, dict):
            continue

        input_data = item.get("input_data", item.get("input"))
        if input_data is None:
            input_data = item.get("inputs", item.get("args"))

        expected_output = item.get("expected_output", item.get("output"))
        if expected_output is None:
            expected_output = item.get("expected", item.get("answer"))

        if input_data is None or expected_output is None:
            continue

        sample_case: dict[str, Any] = {
            "input_data": _coerce_json_if_possible(input_data),
            "expected_output": _coerce_json_if_possible(expected_output),
            "explanation": str(item.get("explanation", "")).strip() or None,
        }
        sample_cases.append(sample_case)

    return sample_cases


def _resolve_edge_case_hints(payload: dict[str, Any]) -> list[str]:
    edge_case_hints_raw = _first_present_value(payload, _EDGE_CASE_HINT_KEYS)
    edge_case_hints: list[str] = []
    if isinstance(edge_case_hints_raw, list):
        for hint in edge_case_hints_raw:
            hint_text = str(hint).strip()
            if hint_text:
                edge_case_hints.append(hint_text)

    if not edge_case_hints:
        edge_case_hints = [
            "empty input edge case when valid",
            "single element edge case",
            "minimum and maximum constraint boundaries",
            "duplicate-heavy input",
        ]
    return edge_case_hints


def _default_function_signature() -> dict[str, dict[str, str]]:
    return {
        "python": {"name": "solve", "params": "nums: list[int], target: int", "return_type": "list[int]"},
        "javascript": {"name": "solve", "params": "nums, target", "return_type": "number[]"},
        "java": {"name": "solve", "params": "int[] nums, int target", "return_type": "int[]"},
        "cpp": {"name": "solve", "params": "vector<int>& nums, int target", "return_type": "vector<int>"},
    }


def _default_starter_code() -> dict[str, str]:
    return {
        "python": "def solve(nums, target):\n    # Write your solution here\n    return []\n",
        "javascript": "function solve(nums, target) {\n  // Write your solution here\n  return [];\n}\n",
        "java": (
            "import java.util.*;\n\n"
            "public class Main {\n"
            "    public static int[] solve(int[] nums, int target) {\n"
            "        // Write your solution here\n"
            "        return new int[]{};\n"
            "    }\n"
            "}\n"
        ),
        "cpp": (
            "#include <bits/stdc++.h>\n"
            "using namespace std;\n\n"
            "vector<int> solve(vector<int>& nums, int target) {\n"
            "    // Write your solution here\n"
            "    return {};\n"
            "}\n"
        ),
    }


def _java_default_return(return_type: str) -> str:
    lowered = return_type.lower()
    if "bool" in lowered:
        return "false"
    if "int" in lowered or "long" in lowered or "short" in lowered or "byte" in lowered:
        return "0"
    if "double" in lowered or "float" in lowered:
        return "0.0"
    if "char" in lowered:
        return "'\\0'"
    if "string" in lowered:
        return "\"\""
    if "[]" in lowered:
        base = return_type.replace("[]", "").strip() or "int"
        return f"new {base}[0]"
    return "null"


def _cpp_default_return(return_type: str) -> str:
    lowered = return_type.lower()
    if "bool" in lowered:
        return "false"
    if "int" in lowered or "long" in lowered or "short" in lowered:
        return "0"
    if "double" in lowered or "float" in lowered:
        return "0.0"
    if "string" in lowered:
        return "\"\""
    if "vector" in lowered:
        return "{}"
    return "{}"


def _build_starter_stub(
    *,
    language: str,
    function_name: str,
    params: str,
    return_type: str,
) -> str:
    if language == "python":
        signature = f"def {function_name}({params}):" if params else f"def {function_name}():"
        return f"{signature}\n    # Write your solution here\n    return None\n"

    if language == "javascript":
        signature = f"function {function_name}({params})" if params else f"function {function_name}()"
        return f"{signature} {{\n  // Write your solution here\n  return null;\n}}\n"

    if language == "java":
        method_params = params or ""
        method_return = return_type or "Object"
        default_return = _java_default_return(method_return)
        return (
            "import java.util.*;\n\n"
            "public class Main {\n"
            f"    public static {method_return} {function_name}({method_params}) {{\n"
            "        // Write your solution here\n"
            f"        return {default_return};\n"
            "    }\n"
            "}\n"
        )

    method_params = params or ""
    method_return = return_type or "auto"
    default_return = _cpp_default_return(method_return)
    return (
        "#include <bits/stdc++.h>\n"
        "using namespace std;\n\n"
        f"{method_return} {function_name}({method_params}) {{\n"
        "    // Write your solution here\n"
        f"    return {default_return};\n"
        "}\n"
    )


def _has_required_entrypoint(*, language: str, source_code: str, function_name: str) -> bool:
    escaped_name = re.escape(function_name)
    if language == "python":
        return re.search(rf"\bdef\s+{escaped_name}\s*\(", source_code) is not None
    if language == "javascript":
        return (
            re.search(rf"\bfunction\s+{escaped_name}\s*\(", source_code) is not None
            or re.search(rf"\bconst\s+{escaped_name}\s*=\s*\(", source_code) is not None
            or re.search(rf"\blet\s+{escaped_name}\s*=\s*\(", source_code) is not None
            or re.search(rf"\bvar\s+{escaped_name}\s*=\s*\(", source_code) is not None
        )
    return re.search(rf"\b{escaped_name}\s*\(", source_code) is not None


def _sanitize_starter_code(
    *,
    starter_code: dict[str, str],
    function_signature: dict[str, dict[str, str]],
) -> dict[str, str]:
    sanitized = starter_code.copy()
    for language in _REQUIRED_LANGUAGES:
        signature = function_signature.get(language, {})
        function_name = str(signature.get("name", "solve")).strip() or "solve"
        params = str(signature.get("params", "")).strip()
        return_type = str(signature.get("return_type", "")).strip()
        code = str(sanitized.get(language, "") or "")

        if not code.strip() or not _has_required_entrypoint(
            language=language,
            source_code=code,
            function_name=function_name,
        ):
            sanitized[language] = _build_starter_stub(
                language=language,
                function_name=function_name,
                params=params,
                return_type=return_type,
            )
    return sanitized


def _normalize_problem_payload(payload: dict[str, Any], *, requested_difficulty: str) -> GeneratedCodingProblem:
    if isinstance(payload.get("problem"), dict):
        merged_payload = payload.copy()
        merged_payload.update(payload["problem"])
        payload = merged_payload

    title = str(payload.get("title", payload.get("problem_title", ""))).strip()
    description = str(payload.get("description", payload.get("problem_statement", ""))).strip()
    reference_solution = _resolve_reference_solution(payload)

    required_values = {
        "title": title,
        "description": description,
        "reference_solution": reference_solution,
    }
    missing = [field for field in _CORE_REQUIRED_FIELDS if not required_values[field]]
    if missing:
        raise ValueError(f"Missing required fields in generated problem payload: {', '.join(missing)}")

    difficulty = str(payload.get("difficulty", requested_difficulty)).strip().lower()
    if difficulty not in {"medium", "hard"}:
        difficulty = requested_difficulty

    function_signature_raw = payload.get("function_signature")
    starter_code_raw = payload.get("starter_code")

    function_signature = _default_function_signature()
    if isinstance(function_signature_raw, dict):
        for language in _REQUIRED_LANGUAGES:
            language_signature = function_signature_raw.get(language)
            if isinstance(language_signature, dict):
                merged = function_signature[language].copy()
                for key in ("name", "params", "return_type"):
                    value = language_signature.get(key)
                    if isinstance(value, str) and value.strip():
                        merged[key] = value.strip()
                function_signature[language] = merged

    python_signature = function_signature["python"].copy()
    configured_python_name = str(python_signature.get("name", "solve")).strip() or "solve"
    python_function_names = _extract_python_function_names(reference_solution)
    if python_function_names and configured_python_name not in python_function_names:
        replacement_name = "solve" if "solve" in python_function_names else python_function_names[0]
        python_signature["name"] = replacement_name
        function_signature["python"] = python_signature

    python_function_name = str(function_signature["python"].get("name", "solve")).strip() or "solve"
    reference_solution = _append_solution_wrapper_if_needed(
        reference_solution,
        function_name=python_function_name,
    )

    starter_code = _default_starter_code()
    if isinstance(starter_code_raw, dict):
        for language in _REQUIRED_LANGUAGES:
            language_starter = starter_code_raw.get(language)
            if isinstance(language_starter, str) and language_starter.strip():
                starter_code[language] = language_starter
    starter_code = _sanitize_starter_code(
        starter_code=starter_code,
        function_signature=function_signature,
    )

    sample_cases = _resolve_sample_cases(payload)
    if len(sample_cases) < 2:
        raise ValueError("Generated problem must include at least 2 sample test cases.")

    edge_case_hints = _resolve_edge_case_hints(payload)
    category = str(_first_present_value(payload, _CATEGORY_KEYS) or "").strip()
    constraints = str(_first_present_value(payload, _CONSTRAINT_KEYS) or "").strip()
    if not constraints:
        constraints = "Design a solution that handles both typical and edge-case inputs efficiently."

    return GeneratedCodingProblem(
        title=title,
        description=description,
        difficulty=difficulty,
        category=category or "arrays",
        constraints=constraints,
        function_signature=function_signature,
        starter_code=starter_code,
        reference_solution=reference_solution,
        sample_test_cases=sample_cases[:3],
        edge_case_hints=edge_case_hints[:8],
    )


def _fallback_problem_set() -> list[GeneratedCodingProblem]:
    two_sum_solution = (
        "def solve(nums, target):\n"
        "    seen = {}\n"
        "    for idx, value in enumerate(nums):\n"
        "        complement = target - value\n"
        "        if complement in seen:\n"
        "            return [seen[complement], idx]\n"
        "        seen[value] = idx\n"
        "    return []\n"
    )
    valid_parentheses_solution = (
        "def solve(s):\n"
        "    pairs = {')': '(', ']': '[', '}': '{'}\n"
        "    stack = []\n"
        "    for char in s:\n"
        "        if char in pairs.values():\n"
        "            stack.append(char)\n"
        "        elif char in pairs:\n"
        "            if not stack or stack.pop() != pairs[char]:\n"
        "                return False\n"
        "    return len(stack) == 0\n"
    )

    return [
        GeneratedCodingProblem(
            title="Two Sum",
            description=(
                "Given an integer array nums and an integer target, return indices of the two numbers "
                "such that they add up to target. You may assume each input has exactly one solution "
                "and you may not use the same element twice."
            ),
            difficulty="medium",
            category="arrays + hashing",
            constraints="2 <= nums.length <= 10^5, -10^9 <= nums[i], target <= 10^9",
            function_signature={
                "python": {"name": "solve", "params": "nums: list[int], target: int", "return_type": "list[int]"},
                "javascript": {"name": "solve", "params": "nums, target", "return_type": "number[]"},
                "java": {"name": "solve", "params": "int[] nums, int target", "return_type": "int[]"},
                "cpp": {"name": "solve", "params": "vector<int>& nums, int target", "return_type": "vector<int>"},
            },
            starter_code=_default_starter_code(),
            reference_solution=two_sum_solution,
            sample_test_cases=[
                {"input_data": [[2, 7, 11, 15], 9], "expected_output": [0, 1], "explanation": "2 + 7 = 9"},
                {"input_data": [[3, 2, 4], 6], "expected_output": [1, 2], "explanation": "2 + 4 = 6"},
                {"input_data": [[3, 3], 6], "expected_output": [0, 1], "explanation": "3 + 3 = 6"},
            ],
            edge_case_hints=[
                "array with duplicate values",
                "negative values",
                "solution using first and last elements",
                "smallest valid array length",
            ],
        ),
        GeneratedCodingProblem(
            title="Valid Parentheses",
            description=(
                "Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', "
                "determine if the input string is valid. An input string is valid if open brackets are "
                "closed by the same type of brackets in the correct order."
            ),
            difficulty="hard",
            category="stack",
            constraints="1 <= s.length <= 10^5, s consists only of bracket characters.",
            function_signature={
                "python": {"name": "solve", "params": "s: str", "return_type": "bool"},
                "javascript": {"name": "solve", "params": "s", "return_type": "boolean"},
                "java": {"name": "solve", "params": "String s", "return_type": "boolean"},
                "cpp": {"name": "solve", "params": "string s", "return_type": "bool"},
            },
            starter_code={
                "python": "def solve(s):\n    # Write your solution here\n    return False\n",
                "javascript": "function solve(s) {\n  // Write your solution here\n  return false;\n}\n",
                "java": (
                    "import java.util.*;\n\n"
                    "public class Main {\n"
                    "    public static boolean solve(String s) {\n"
                    "        // Write your solution here\n"
                    "        return false;\n"
                    "    }\n"
                    "}\n"
                ),
                "cpp": (
                    "#include <bits/stdc++.h>\n"
                    "using namespace std;\n\n"
                    "bool solve(string s) {\n"
                    "    // Write your solution here\n"
                    "    return false;\n"
                    "}\n"
                ),
            },
            reference_solution=valid_parentheses_solution,
            sample_test_cases=[
                {"input_data": ["()"], "expected_output": True, "explanation": "single valid pair"},
                {"input_data": ["()[]{}"], "expected_output": True, "explanation": "all pairs closed properly"},
                {"input_data": ["(]"], "expected_output": False, "explanation": "mismatched closing bracket"},
            ],
            edge_case_hints=[
                "empty stack close attempt",
                "nested valid sequence",
                "long alternating valid sequence",
                "string ending with unmatched opening bracket",
            ],
        ),
    ]


async def _generate_problem_with_llm(
    *,
    job_text: str,
    required_skills: list[str],
    company_name: str | None,
    requested_difficulty: str,
    strict_retry: bool = False,
    timeout_seconds: float | None = None,
) -> GeneratedCodingProblem:
    jd_chunk = _truncate_text(job_text, limit=1500)
    skills_chunk = ", ".join(skill for skill in required_skills if skill.strip()) or "N/A"
    retry_note = (
        "Previous generation was invalid. Ensure reference_solution is executable Python code and sample test cases are consistent."
        if strict_retry
        else ""
    )

    user_prompt = f"""Job Description:
{jd_chunk}

Required Skills:
{skills_chunk}

Company:
{company_name or "N/A"}

Requested difficulty: {requested_difficulty}

Return strict JSON with all required fields:
title, description, difficulty, category, constraints,
function_signature (python/javascript/java/cpp),
starter_code (python/javascript/java/cpp),
reference_solution (python),
sample_test_cases (2-3 cases: input_data + expected_output + explanation),
edge_case_hints (list of strings).
Keep descriptions concise.

{retry_note}
"""

    # response_format removed - Qwen 3 32B on Groq rejects it with 400,
    # causing a wasted retry on every call. The system prompt instructs
    # JSON-only output, which is sufficient.
    response_text = await call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=2200,
        timeout_seconds=timeout_seconds or PROBLEM_GENERATION_TIMEOUT_SECONDS,
        max_429_retries=PROBLEM_GENERATION_MAX_429_RETRIES,
    )
    payload = _extract_json_object(response_text)
    return _normalize_problem_payload(payload, requested_difficulty=requested_difficulty)


async def _generate_test_cases_for_problem(problem: GeneratedCodingProblem) -> list[GeneratedTestCase]:
    return await generate_validated_test_cases(
        description=problem["description"],
        reference_solution=problem["reference_solution"],
        function_signature=problem["function_signature"],
        constraints=problem["constraints"],
        sample_test_cases=problem["sample_test_cases"],
        edge_case_hints=problem["edge_case_hints"],
        use_llm_for_hidden_inputs=False,
    )


def _python_signature_text(function_signature: dict[str, dict[str, str]]) -> str:
    python_signature = function_signature.get("python", {})
    function_name = str(python_signature.get("name", "solve")).strip() or "solve"
    params = str(python_signature.get("params", "")).strip()
    return_type = str(python_signature.get("return_type", "")).strip()
    signature = f"{function_name}({params})" if params else f"{function_name}()"
    if return_type:
        signature = f"{signature} -> {return_type}"
    return signature


async def _retry_reference_solution(
    *,
    problem: GeneratedCodingProblem,
    failed_solution: str,
    timeout_seconds: float | None = None,
) -> str:
    signature = _python_signature_text(problem["function_signature"])
    prompt = f"""The following Python solution for the problem "{problem["title"]}" is incorrect.
It failed validation against the sample test cases.

Problem:
{_truncate_text(problem["description"], limit=1800)}

Constraints:
{problem["constraints"]}

Function signature:
{signature}

Failed solution:
```python
{failed_solution}
```

Write a CORRECT Python solution.
Return ONLY the Python code, no explanation, no markdown fences.
"""
    # response_format removed - Qwen 3 32B on Groq rejects it with 400,
    # causing a wasted retry on every call. The system prompt instructs
    # JSON-only output, which is sufficient.
    response_text = await call_llm(
        messages=[
            {
                "role": "system",
                "content": "You fix Python reference solutions for coding interview problems. Return only Python code.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=1000,
        timeout_seconds=timeout_seconds or PROBLEM_GENERATION_TIMEOUT_SECONDS,
        max_429_retries=PROBLEM_GENERATION_MAX_429_RETRIES,
    )
    repaired_solution = _extract_code_block(response_text, language="python").strip()
    if not repaired_solution:
        raise ValueError("Targeted reference solution retry returned empty code.")
    return repaired_solution


async def generate_coding_problem_for_job(
    *,
    job_text: str,
    required_skills: list[str],
    company_name: str | None,
    requested_difficulty: str,
) -> CodingProblemGenerationResult:
    """Generate a coding problem with bounded latency and fallback safety."""
    normalized_difficulty = requested_difficulty.strip().lower()
    if normalized_difficulty not in {"medium", "hard"}:
        normalized_difficulty = "medium"

    generation_started_at = time.monotonic()
    for attempt in range(MAX_PRIMARY_PROBLEM_ATTEMPTS):
        elapsed = time.monotonic() - generation_started_at
        remaining_budget = PROBLEM_GENERATION_TOTAL_BUDGET_SECONDS - elapsed
        if remaining_budget <= 0:
            logger.warning(
                "Coding problem generation exceeded budget (%.1fs). Switching to fallback problem.",
                PROBLEM_GENERATION_TOTAL_BUDGET_SECONDS,
            )
            break

        attempt_timeout_seconds = min(PROBLEM_GENERATION_TIMEOUT_SECONDS, remaining_budget)
        if attempt_timeout_seconds < PROBLEM_GENERATION_MIN_TIMEOUT_SECONDS:
            logger.warning(
                "Insufficient remaining budget (%.1fs) before attempt %s. Switching to fallback problem.",
                remaining_budget,
                attempt + 1,
            )
            break

        problem: GeneratedCodingProblem | None = None
        try:
            problem = await _generate_problem_with_llm(
                job_text=job_text,
                required_skills=required_skills,
                company_name=company_name,
                requested_difficulty=normalized_difficulty,
                strict_retry=attempt > 0,
                timeout_seconds=attempt_timeout_seconds,
            )
            test_cases = await _generate_test_cases_for_problem(problem)
            return CodingProblemGenerationResult(problem=problem, test_cases=test_cases)
        except ReferenceSolutionValidationError:
            logger.warning(
                "Reference solution failed validation on attempt %s. Attempting targeted retry.",
                attempt + 1,
                exc_info=True,
            )
            if problem is None:
                logger.warning(
                    "Reference solution retry skipped because no problem payload was produced on attempt %s.",
                    attempt + 1,
                )
                continue
            try:
                repaired_solution = await _retry_reference_solution(
                    problem=problem,
                    failed_solution=problem["reference_solution"],
                    timeout_seconds=attempt_timeout_seconds,
                )
                problem["reference_solution"] = repaired_solution
                test_cases = await _generate_test_cases_for_problem(problem)
                logger.warning("Targeted reference solution retry succeeded on attempt %s.", attempt + 1)
                return CodingProblemGenerationResult(problem=problem, test_cases=test_cases)
            except ReferenceSolutionValidationError:
                logger.warning(
                    "Targeted reference solution retry failed sample validation on attempt %s.",
                    attempt + 1,
                    exc_info=True,
                )
                continue
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response is not None else "unknown"
                logger.warning(
                    "Targeted reference solution retry failed with HTTP %s on attempt %s.",
                    status_code,
                    attempt + 1,
                    exc_info=True,
                )
                if status_code == 429:
                    logger.warning(
                        "Received 429 during targeted reference solution retry. "
                        "Switching to fallback problem immediately."
                    )
                    break
                continue
            except Exception:
                logger.warning("Targeted reference solution retry failed on attempt %s.", attempt + 1, exc_info=True)
                continue
        except (TestCaseGenerationError, ValueError):
            logger.warning("Generated coding problem attempt %s failed validation.", attempt + 1, exc_info=True)
            continue
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            logger.warning(
                "LLM coding problem generation attempt %s failed with HTTP %s.",
                attempt + 1,
                status_code,
                exc_info=True,
            )
            if status_code == 429:
                logger.warning("Received 429 during coding generation. Switching to fallback problem immediately.")
                break
            continue
        except Exception:
            logger.exception("LLM coding problem generation attempt %s failed unexpectedly.", attempt + 1)
            continue

    for fallback_problem in _fallback_problem_set():
        if normalized_difficulty != fallback_problem["difficulty"]:
            continue
        try:
            fallback_cases = await generate_validated_test_cases(
                description=fallback_problem["description"],
                reference_solution=fallback_problem["reference_solution"],
                function_signature=fallback_problem["function_signature"],
                constraints=fallback_problem["constraints"],
                sample_test_cases=fallback_problem["sample_test_cases"],
                edge_case_hints=fallback_problem["edge_case_hints"],
                use_llm_for_hidden_inputs=False,
            )
            return CodingProblemGenerationResult(problem=fallback_problem, test_cases=fallback_cases)
        except Exception:
            logger.exception("Fallback problem generation failed for %s.", fallback_problem["title"])

    raise RuntimeError("Could not generate a valid coding problem at this time.")
