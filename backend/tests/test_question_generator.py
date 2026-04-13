from __future__ import annotations

import asyncio
import json

import pytest

from app.services import llm_client
from app.services import question_generator


def test_parse_llm_output_valid_json() -> None:
    """Raw JSON arrays should parse directly into question dictionaries."""
    payload = json.dumps(
        [
            {
                "question_text": "How did you optimize API latency in production?",
                "category": "technical",
                "rationale": "Targets backend performance ownership.",
            }
        ]
    )

    parsed = question_generator.parse_llm_output(payload)
    assert len(parsed) == 1
    assert parsed[0]["category"] == "technical"


def test_parse_llm_output_handles_markdown_wrapped_json() -> None:
    """Parser should extract the JSON array from markdown/code-fence wrappers."""
    wrapped = """
    Here are your questions:
    ```json
    [
      {
        "question_text": "Tell me about a difficult stakeholder conversation.",
        "category": "behavioral",
        "rationale": "Evaluates communication under pressure."
      }
    ]
    ```
    """

    parsed = question_generator.parse_llm_output(wrapped)
    assert len(parsed) == 1
    assert parsed[0]["category"] == "behavioral"


def test_parse_llm_output_malformed_json_returns_empty() -> None:
    """Malformed payloads should fail closed instead of raising parser exceptions."""
    malformed = '[{"question_text": "Broken", "category": "technical",}]'

    parsed = question_generator.parse_llm_output(malformed)
    assert parsed == []


def test_generate_questions_uses_fallback_for_empty_llm_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty LLM responses should trigger fallback questions with required shape/count."""

    async def fake_call_llm(_: str) -> str:
        return ""

    monkeypatch.setattr(question_generator, "call_llm", fake_call_llm)

    result = asyncio.run(
        question_generator.generate_questions(
            resume_text="Built APIs with FastAPI and PostgreSQL.",
            jd_text="Need backend engineer with API design and debugging skills.",
            match_summary="Solid match with some missing distributed systems depth.",
            matched_skills=["fastapi", "postgresql"],
            missing_skills=["distributed systems"],
        )
    )

    assert len(result) == 8
    categories = [item["category"] for item in result]
    assert categories.count("technical") == 3
    assert categories.count("behavioral") == 3
    assert categories.count("resume_based") == 2


def test_generate_questions_uses_fallback_when_llm_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM transport failures must not crash generation and should return fallbacks."""

    async def failing_call_llm(_: str) -> str:
        raise RuntimeError("upstream timeout")

    monkeypatch.setattr(question_generator, "call_llm", failing_call_llm)

    result = asyncio.run(
        question_generator.generate_questions(
            resume_text="Candidate resume",
            jd_text="Job description",
            match_summary="Match summary",
            matched_skills=["python"],
            missing_skills=["system design"],
        )
    )

    assert len(result) == 8
    assert all(item["question_text"] for item in result)
    assert all(item["rationale"] for item in result)


def test_retry_delay_uses_expected_exponential_schedule() -> None:
    """429 retry delays should follow 1s, 2s, 4s and then stay capped at 4s."""
    assert llm_client.retry_delay_for_attempt(1) == pytest.approx(1.0)
    assert llm_client.retry_delay_for_attempt(2) == pytest.approx(2.0)
    assert llm_client.retry_delay_for_attempt(3) == pytest.approx(4.0)
    assert llm_client.retry_delay_for_attempt(4) == pytest.approx(4.0)
