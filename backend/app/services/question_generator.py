from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any, TypedDict

from app.services.llm_client import call_llm as call_llm_with_provider


logger = logging.getLogger(__name__)

VALID_CATEGORIES = ("technical", "behavioral", "resume_based")
REQUIRED_DISTRIBUTION: tuple[tuple[str, int], ...] = (
    ("technical", 3),
    ("behavioral", 3),
    ("resume_based", 2),
)


class GeneratedQuestion(TypedDict):
    question_text: str
    category: str
    rationale: str


FALLBACK_QUESTIONS_BY_CATEGORY: dict[str, list[GeneratedQuestion]] = {
    "technical": [
        {
            "question_text": "Walk me through a recent backend project where you designed APIs and data models.",
            "category": "technical",
            "rationale": "Assesses practical backend architecture depth for a typical engineering role.",
        },
        {
            "question_text": "How would you diagnose and improve the performance of a slow database-backed endpoint?",
            "category": "technical",
            "rationale": "Evaluates debugging approach, database fundamentals, and production mindset.",
        },
        {
            "question_text": "Describe how you would design tests for a feature that spans API, database, and business logic layers.",
            "category": "technical",
            "rationale": "Measures understanding of reliability and maintainable testing strategy.",
        },
    ],
    "behavioral": [
        {
            "question_text": "Tell me about a time you had to deliver under a tight deadline with incomplete requirements.",
            "category": "behavioral",
            "rationale": "Evaluates ambiguity handling, prioritization, and communication under pressure.",
        },
        {
            "question_text": "Describe a conflict with a teammate on technical direction and how you resolved it.",
            "category": "behavioral",
            "rationale": "Assesses collaboration, ownership, and decision-making maturity.",
        },
        {
            "question_text": "Share an example of feedback you received that changed how you work.",
            "category": "behavioral",
            "rationale": "Measures coachability and continuous improvement.",
        },
    ],
    "resume_based": [
        {
            "question_text": "From your resume, which project best demonstrates your readiness for this role, and why?",
            "category": "resume_based",
            "rationale": "Connects the candidate's experience directly to role fit.",
        },
        {
            "question_text": "Looking at your resume timeline, what was your most impactful learning step and how did it influence your results?",
            "category": "resume_based",
            "rationale": "Surfaces growth narrative and reflection on outcomes.",
        },
    ],
}


def _truncate_text(value: str, *, limit: int = 1500) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."


def _format_skills(skills: list[str]) -> str:
    cleaned = [skill.strip() for skill in skills if isinstance(skill, str) and skill.strip()]
    return ", ".join(cleaned) if cleaned else "None identified"


def build_prompt(
    *,
    resume_text: str,
    jd_text: str,
    match_summary: str,
    matched_skills: list[str],
    missing_skills: list[str],
) -> str:
    """Build a deterministic, context-rich prompt for question generation."""
    resume_chunk = _truncate_text(resume_text, limit=1500)
    jd_chunk = _truncate_text(jd_text, limit=1500)
    summary_chunk = _truncate_text(match_summary, limit=800)
    matched = _format_skills(matched_skills)
    missing = _format_skills(missing_skills)

    return f"""SYSTEM:
You are an expert technical interviewer.

You MUST return valid JSON only.
No explanation. No markdown.

USER:

## Candidate Resume
{resume_chunk}

## Job Description
{jd_chunk}

## Match Analysis
{summary_chunk}

Matched Skills:
{matched}

Missing Skills:
{missing}

## Instructions

Generate exactly 8 interview questions.

Rules:
- 3 technical
- 3 behavioral
- 2 resume_based
- Tailored to THIS candidate
- Avoid generic questions

Return JSON:

[
  {{
    "question_text": "...",
    "category": "technical",
    "rationale": "..."
  }}
]"""


async def call_llm(prompt: str) -> str:
    """Call configured LLM provider and return model text content."""
    return await call_llm_with_provider(
        messages=[
            {"role": "system", "content": "You are an expert interviewer. Return only JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=None,
    )


def _try_load_questions(payload: str) -> list[dict[str, Any]] | None:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        if isinstance(parsed.get("questions"), list):
            parsed = parsed["questions"]
        else:
            return None

    if not isinstance(parsed, list):
        return None

    question_dicts = [item for item in parsed if isinstance(item, dict)]
    return question_dicts


def parse_llm_output(response: str) -> list[dict[str, Any]]:
    """Extract question JSON from raw model output, tolerating wrappers/noise."""
    if not response or not response.strip():
        return []

    candidates: list[str] = []
    stripped = response.strip()
    candidates.append(stripped)

    code_blocks = re.findall(r"```(?:json)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(code_blocks)

    start_idx = stripped.find("[")
    end_idx = stripped.rfind("]")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidates.append(stripped[start_idx : end_idx + 1])

    for candidate in candidates:
        parsed = _try_load_questions(candidate.strip())
        if parsed is not None:
            return parsed

    return []


def _sanitize_question(candidate: dict[str, Any]) -> GeneratedQuestion | None:
    question_text_raw = candidate.get("question_text")
    rationale_raw = candidate.get("rationale")
    category_raw = candidate.get("category")

    question_text = str(question_text_raw or "").strip()
    if not question_text:
        return None

    category = str(category_raw or "").strip().lower()
    rationale = str(rationale_raw or "").strip()

    return GeneratedQuestion(
        question_text=question_text,
        category=category,
        rationale=rationale or "Generated using resume, job description, and match context.",
    )


def _fallback_question(category: str, index: int) -> GeneratedQuestion:
    options = FALLBACK_QUESTIONS_BY_CATEGORY[category]
    if index < len(options):
        return GeneratedQuestion(**options[index])

    return GeneratedQuestion(
        question_text=f"Share an example that demonstrates your strengths related to {category.replace('_', ' ')} topics.",
        category=category,
        rationale="Ensures the interview can proceed with a valid, structured backup question.",
    )


def validate_questions(questions: list[dict[str, Any]]) -> list[GeneratedQuestion]:
    """Return exactly 8 valid questions with supported categories."""
    category_buckets: dict[str, list[GeneratedQuestion]] = defaultdict(list)
    uncategorized: list[GeneratedQuestion] = []

    for candidate in questions:
        sanitized = _sanitize_question(candidate)
        if sanitized is None:
            continue

        if sanitized["category"] in VALID_CATEGORIES:
            category_buckets[sanitized["category"]].append(sanitized)
        else:
            uncategorized.append(sanitized)

    final_questions: list[GeneratedQuestion] = []
    fallback_offsets: dict[str, int] = {category: 0 for category in VALID_CATEGORIES}

    for category, count in REQUIRED_DISTRIBUTION:
        for _ in range(count):
            if category_buckets[category]:
                chosen = category_buckets[category].pop(0)
                chosen["category"] = category
            elif uncategorized:
                chosen = uncategorized.pop(0)
                chosen["category"] = category
            else:
                chosen = _fallback_question(category, fallback_offsets[category])
                fallback_offsets[category] += 1

            final_questions.append(chosen)

    return final_questions


async def generate_questions(
    *,
    resume_text: str,
    jd_text: str,
    match_summary: str,
    matched_skills: list[str],
    missing_skills: list[str],
) -> list[GeneratedQuestion]:
    """Generate structured interview questions, falling back safely on failures."""
    prompt = build_prompt(
        resume_text=resume_text,
        jd_text=jd_text,
        match_summary=match_summary,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
    )

    parsed_questions: list[dict[str, Any]]
    try:
        raw_response = await call_llm(prompt)
        parsed_questions = parse_llm_output(raw_response)
        if not parsed_questions:
            logger.warning("LLM response could not be parsed into question JSON. Using fallback questions.")
    except Exception:
        logger.exception("LLM question generation failed. Using fallback questions.")
        parsed_questions = []

    return validate_questions(parsed_questions)
