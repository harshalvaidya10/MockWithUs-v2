from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.models.answer import Answer
from app.models.interview import InterviewSession
from app.models.question import Question
from app.services import evaluator


def test_rule_based_score() -> None:
    """Rule-based scoring should produce bounded and sensible dimension values."""
    question = "How did you improve API performance and reliability?"
    answer = (
        "I led an API optimization effort where I profiled slow endpoints, reduced N+1 queries, "
        "added caching, and improved error handling. The result was lower latency and fewer incidents "
        "across production workloads."
    )

    scores = evaluator.rule_based_score(answer, question)

    assert set(scores.keys()) == {"relevance_score", "clarity_score", "depth_score", "structure_score"}
    assert all(0.0 <= score <= 10.0 for score in scores.values())
    assert scores["relevance_score"] > 0.0
    assert scores["structure_score"] >= 5.0


def test_hybrid_score() -> None:
    """Hybrid blending should apply configured weights and return overall average."""
    rule_scores = {
        "relevance_score": 4.0,
        "clarity_score": 5.0,
        "depth_score": 6.0,
        "structure_score": 7.0,
    }
    llm_scores = {
        "relevance_score": 8.0,
        "clarity_score": 9.0,
        "depth_score": 7.0,
        "structure_score": 6.0,
    }

    blended = evaluator.hybrid_score(rule_scores, llm_scores)

    assert blended["relevance_score"] == pytest.approx(6.8)
    assert blended["clarity_score"] == pytest.approx(8.2)
    assert blended["depth_score"] == pytest.approx(6.8)
    assert blended["structure_score"] == pytest.approx(6.4)
    assert blended["overall_score"] == pytest.approx(7.05)


def test_empty_answer() -> None:
    """Empty answers should be scored low by deterministic evaluator."""
    scores = evaluator.rule_based_score("", "Tell me about a production incident you handled.")
    assert all(score <= 2.0 for score in scores.values())


def test_llm_evaluate_with_mocked_llm_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM output parsing should accept strict JSON and normalize fields."""

    async def fake_call_llm(*, messages, temperature, max_tokens, response_format):  # type: ignore[no-untyped-def]
        assert messages
        assert temperature == pytest.approx(0.1)
        assert max_tokens == 1000
        assert response_format == {"type": "json_object"}
        return """
        {
          "relevance_score": 8,
          "clarity_score": 7.5,
          "depth_score": 6,
          "structure_score": 7,
          "feedback_text": "Good answer with clear ownership.",
          "strengths": ["Concrete example", "Good clarity"],
          "improvements": ["Add more measurable impact"]
        }
        """

    monkeypatch.setattr(evaluator, "call_llm", fake_call_llm)

    result = asyncio.run(
        evaluator.llm_evaluate(
            question="Describe a difficult backend bug you fixed.",
            answer="I traced it to a race condition and fixed locking in our worker pipeline.",
            job_context="Backend engineer role requiring production debugging depth.",
        )
    )

    assert result["relevance_score"] == pytest.approx(8.0)
    assert result["clarity_score"] == pytest.approx(7.5)
    assert result["depth_score"] == pytest.approx(6.0)
    assert result["structure_score"] == pytest.approx(7.0)
    assert result["feedback_text"] == "Good answer with clear ownership."
    assert result["strengths"] == ["Concrete example", "Good clarity"]
    assert result["improvements"] == ["Add more measurable impact"]


def test_extract_json_object_tolerates_trailing_commas() -> None:
    payload = """
    {
      "relevance_score": 8,
      "clarity_score": 7.5,
      "depth_score": 6,
      "structure_score": 7,
      "feedback_text": "Good answer with clear ownership.",
      "strengths": ["Concrete example",],
      "improvements": ["Add more measurable impact",],
    }
    """

    parsed = evaluator._extract_json_object(payload)

    assert parsed["relevance_score"] == 8
    assert parsed["clarity_score"] == 7.5
    assert parsed["feedback_text"] == "Good answer with clear ownership."


def test_extract_json_object_accepts_list_wrapped_dict() -> None:
    payload = """
    [
      {
        "relevance_score": 8,
        "clarity_score": 7.5,
        "depth_score": 6,
        "structure_score": 7,
        "feedback_text": "Structured answer.",
        "strengths": ["Clear context"],
        "improvements": ["Add numbers"]
      }
    ]
    """

    parsed = evaluator._extract_json_object(payload)

    assert parsed["relevance_score"] == 8
    assert parsed["feedback_text"] == "Structured answer."


def test_extract_json_object_accepts_python_style_dict_literal() -> None:
    payload = """{'relevance_score': 8, 'clarity_score': 7, 'depth_score': 6, 'structure_score': 7,
    'feedback_text': 'Good answer.', 'strengths': ['Ownership'], 'improvements': ['Add impact']}"""

    parsed = evaluator._extract_json_object(payload)

    assert parsed["clarity_score"] == 7
    assert parsed["feedback_text"] == "Good answer."


def test_structure_score_with_we_pronoun() -> None:
    """'we' should get the same first-person credit as 'I'."""
    answer = (
        "We built a caching layer for frequently accessed endpoints, then tuned invalidation rules "
        "and query plans across services. The result was a 40% improvement."
    )
    score = evaluator.rule_based_score(answer, "Describe a technical challenge")
    assert score["structure_score"] >= 6.0


def test_structure_score_with_transitions() -> None:
    """Transition words should boost structure score."""
    answer = (
        "First, I identified the bottleneck. Then I implemented indexing. "
        "Finally, the query time decreased by 30%."
    )
    score = evaluator.rule_based_score(answer, "Walk me through your optimization")
    assert score["structure_score"] >= 7.0


def test_structure_score_short_vague_answer() -> None:
    """Short vague answers should score low on structure."""
    answer = "I used good practices."
    score = evaluator.rule_based_score(answer, "Describe your approach")
    assert score["structure_score"] <= 4.0


def test_audio_answer_uses_transcript_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """When answer_text is None, evaluate_answer should use transcript_text."""
    captured: dict[str, object] = {}

    async def fake_llm_evaluate(*, question, answer, job_context, is_transcribed):  # type: ignore[no-untyped-def]
        captured["answer"] = answer
        captured["is_transcribed"] = is_transcribed
        return {
            "relevance_score": 8.0,
            "clarity_score": 7.0,
            "depth_score": 7.0,
            "structure_score": 8.0,
            "feedback_text": "Good response.",
            "strengths": ["Clear example"],
            "improvements": ["Add metrics"],
        }

    monkeypatch.setattr(evaluator, "llm_evaluate", fake_llm_evaluate)

    session = InterviewSession(user_id=uuid4(), status="ready", match_summary="Role context")
    session.id = uuid4()

    question = Question(
        session_id=session.id,
        question_text="Tell me about a time you improved performance.",
        category="technical",
        rationale="Check technical depth",
        order_index=1,
    )
    question.id = uuid4()

    answer = Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text=None,
        transcript_text="I redesigned indexing and reduced p95 latency by 30%.",
        audio_file_path="answers/file.webm",
    )
    answer.id = uuid4()

    result = asyncio.run(evaluator.evaluate_answer(answer=answer, question=question, session=session))

    assert captured["answer"] == "I redesigned indexing and reduced p95 latency by 30%."
    assert captured["is_transcribed"] is True
    assert result["answer_text"] == "I redesigned indexing and reduced p95 latency by 30%."


def test_typed_answer_uses_answer_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """When answer_text is set, evaluate_answer should prefer it over transcript_text."""
    captured: dict[str, object] = {}

    async def fake_llm_evaluate(*, question, answer, job_context, is_transcribed):  # type: ignore[no-untyped-def]
        captured["answer"] = answer
        captured["is_transcribed"] = is_transcribed
        return {
            "relevance_score": 8.0,
            "clarity_score": 7.0,
            "depth_score": 7.0,
            "structure_score": 8.0,
            "feedback_text": "Good response.",
            "strengths": ["Clear example"],
            "improvements": ["Add metrics"],
        }

    monkeypatch.setattr(evaluator, "llm_evaluate", fake_llm_evaluate)

    session = InterviewSession(user_id=uuid4(), status="ready", match_summary="Role context")
    session.id = uuid4()

    question = Question(
        session_id=session.id,
        question_text="Tell me about a time you improved performance.",
        category="technical",
        rationale="Check technical depth",
        order_index=1,
    )
    question.id = uuid4()

    answer = Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text="I optimized query plans and cut latency by 20%.",
        transcript_text="Possible transcript text that should not be used.",
        audio_file_path=None,
    )
    answer.id = uuid4()

    result = asyncio.run(evaluator.evaluate_answer(answer=answer, question=question, session=session))

    assert captured["answer"] == "I optimized query plans and cut latency by 20%."
    assert captured["is_transcribed"] is False
    assert result["answer_text"] == "I optimized query plans and cut latency by 20%."
