from __future__ import annotations

import asyncio
import ast
import json
import logging
import re
from typing import Any, TypedDict
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.interview import InterviewSession
from app.models.question import Question
from app.services.llm_client import call_llm


logger = logging.getLogger(__name__)
settings = get_settings()

_TOKEN_PATTERN = re.compile(r"[a-z0-9']+")
_TRAILING_COMMA_PATTERN = re.compile(r",\s*(?=[}\]])")
_SESSION_EVALUATION_LOCKS: dict[UUID, asyncio.Lock] = {}
_DEFAULT_EVAL_CONCURRENCY = 2


def _configured_eval_concurrency() -> int:
    configured = getattr(settings, "llm_eval_max_concurrency", _DEFAULT_EVAL_CONCURRENCY)
    try:
        return max(1, int(configured))
    except (TypeError, ValueError):
        return _DEFAULT_EVAL_CONCURRENCY


_LLM_EVALUATION_SEMAPHORE = asyncio.Semaphore(_configured_eval_concurrency())


class EvaluationAccessError(Exception):
    """Raised when a user tries to access another user's interview session."""


class ScoreSet(TypedDict):
    relevance_score: float
    clarity_score: float
    depth_score: float
    structure_score: float


class HybridScoreSet(ScoreSet):
    overall_score: float


class LlmEvaluation(TypedDict):
    relevance_score: float
    clarity_score: float
    depth_score: float
    structure_score: float
    feedback_text: str
    strengths: list[str]
    improvements: list[str]


class AnswerEvaluationResult(TypedDict):
    answer_id: UUID
    question_id: UUID
    question_text: str
    answer_text: str
    relevance_score: float
    clarity_score: float
    depth_score: float
    structure_score: float
    overall_score: float
    feedback_text: str
    strengths: list[str]
    improvements: list[str]


class SessionEvaluationResult(TypedDict):
    session_id: UUID
    overall_score: float | None
    evaluations: list[dict[str, Any]]


def _tokenize(value: str) -> list[str]:
    return _TOKEN_PATTERN.findall((value or "").lower())


def _clamp_score(value: float) -> float:
    return max(0.0, min(10.0, float(value)))


def _round_score(value: float) -> float:
    return round(_clamp_score(value), 2)


def _length_score(word_count: int) -> float:
    if word_count < 30:
        return 2.0
    if word_count <= 80:
        return 5.0
    if word_count <= 200:
        return 8.0
    if word_count <= 350:
        return 9.0
    return 6.0


def _keyword_overlap_score(question_text: str, answer_text: str) -> float:
    question_terms = {token for token in _tokenize(question_text) if len(token) > 2}
    answer_terms = {token for token in _tokenize(answer_text) if len(token) > 2}

    if not question_terms:
        return 0.0

    overlap_ratio = len(question_terms & answer_terms) / len(question_terms)
    return _round_score(overlap_ratio * 10.0)


def _structure_score(answer_text: str) -> float:
    cleaned = (answer_text or "").strip()
    if not cleaned:
        return 0.0

    # Structure score — detect organized, narrative answers.
    structure = 0.0

    # Length threshold (organized answers tend to be substantive).
    word_count = len(cleaned.split())
    if word_count > 20:
        structure += 2.0
    if word_count > 50:
        structure += 1.0

    # First-person narrative (STAR-style) — accept both "I" and "we".
    first_person = bool(re.search(r"\b(I|we)\b", cleaned, re.IGNORECASE))
    past_action = bool(re.search(
        r"\b(built|designed|implemented|created|developed|led|managed|wrote|deployed|"
        r"optimized|reduced|improved|launched|migrated|refactored|integrated|delivered|"
        r"architected|automated|configured|established|maintained|resolved|shipped|"
        r"collaborated|coordinated|mentored|presented|proposed|researched|tested)\b",
        cleaned,
        re.IGNORECASE,
    ))
    if first_person and past_action:
        structure += 3.0

    # Result/impact signals — explicit outcomes.
    result_mentioned = bool(re.search(
        r"\b(result|outcome|impact|led to|which meant|this allowed|improved by|"
        r"reduced by|increased|decreased|saved|achieved|enabled|resulting in|"
        r"as a result|the effect|consequently)\b",
        cleaned,
        re.IGNORECASE,
    ))
    if result_mentioned:
        structure += 2.5

    # Transition/organization signals — shows structured thinking.
    has_transitions = bool(re.search(
        r"\b(first|second|then|next|finally|additionally|however|because|"
        r"for example|specifically|in particular|on the other hand|"
        r"the challenge was|the approach was|the solution was)\b",
        cleaned,
        re.IGNORECASE,
    ))
    if has_transitions:
        structure += 1.5

    return _round_score(min(structure, 10.0))


def rule_based_score(answer_text: str, question_text: str) -> ScoreSet:
    """Deterministic baseline evaluation used for hybrid scoring and fallbacks."""
    cleaned_answer = (answer_text or "").strip()
    if not cleaned_answer:
        low_score = 1.0
        return ScoreSet(
            relevance_score=low_score,
            clarity_score=low_score,
            depth_score=low_score,
            structure_score=low_score,
        )

    word_count = len(_tokenize(cleaned_answer))
    length_score = _length_score(word_count)
    keyword_overlap = _keyword_overlap_score(question_text, cleaned_answer)
    structure = _structure_score(cleaned_answer)

    clarity_score = _round_score((length_score * 0.6) + (structure * 0.4))
    depth_score = _round_score((length_score * 0.5) + (keyword_overlap * 0.5))

    return ScoreSet(
        relevance_score=_round_score(keyword_overlap),
        clarity_score=clarity_score,
        depth_score=depth_score,
        structure_score=_round_score(structure),
    )


def _parse_json_object_candidate(candidate: str) -> dict[str, Any] | None:
    normalized = candidate.strip()
    if not normalized:
        return None

    payload_candidates = (
        normalized,
        _TRAILING_COMMA_PATTERN.sub("", normalized),
    )
    for payload in payload_candidates:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            return parsed[0]

        try:
            parsed_python = ast.literal_eval(payload)
        except (ValueError, SyntaxError):
            continue
        if isinstance(parsed_python, dict):
            return parsed_python
        if isinstance(parsed_python, list) and parsed_python and isinstance(parsed_python[0], dict):
            return parsed_python[0]

    return None


def _extract_balanced_json_objects(payload: str) -> list[str]:
    candidates: list[str] = []
    in_string = False
    escape_next = False
    depth = 0
    object_start: int | None = None

    for index, char in enumerate(payload):
        if in_string:
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            if depth == 0:
                object_start = index
            depth += 1
            continue

        if char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and object_start is not None:
                candidates.append(payload[object_start : index + 1])
                object_start = None

    return candidates


def _unique_candidates(candidates: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _extract_json_object(payload: str) -> dict[str, Any]:
    candidates: list[str] = []
    stripped = (payload or "").strip()
    if stripped:
        candidates.append(stripped)

    code_blocks = re.findall(r"```(?:json)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(code_blocks)

    start_idx = stripped.find("{")
    end_idx = stripped.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidates.append(stripped[start_idx : end_idx + 1])

    candidates.extend(_extract_balanced_json_objects(stripped))

    for candidate in _unique_candidates(candidates):
        parsed = _parse_json_object_candidate(candidate)
        if parsed is not None:
            return parsed

    raise ValueError("LLM evaluation response was not valid JSON object.")


def _get_session_evaluation_lock(session_id: UUID) -> asyncio.Lock:
    lock = _SESSION_EVALUATION_LOCKS.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _SESSION_EVALUATION_LOCKS[session_id] = lock
    return lock


def _normalize_score_field(payload: dict[str, Any], key: str) -> float:
    raw_value = payload.get(key)
    if raw_value is None:
        raise ValueError(f"Missing field '{key}' in LLM response.")
    try:
        return _round_score(float(raw_value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric field '{key}' in LLM response.") from exc


def _normalize_string_list(raw_value: Any) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    result: list[str] = []
    for item in raw_value:
        text = str(item).strip()
        if text:
            result.append(text)
    return result[:5]


async def llm_evaluate(
    *,
    question: str,
    answer: str,
    job_context: str,
    is_transcribed: bool = False,
) -> LlmEvaluation:
    """Run LLM-based grading and parse strict JSON output."""
    system_prompt = """
You are an interview evaluator.
Score each answer on relevance, clarity, depth, and structure from 0 to 10.

IMPORTANT: The candidate's answer may have been transcribed from spoken audio.
Transcription artifacts (misspellings, odd word breaks, phonetic errors) are NOT
the candidate's fault. Evaluate the SUBSTANCE and INTENT of what they communicated,
not surface-level spelling or grammar from transcription. For example, "increment
tilly" likely means "incrementally" — score based on the intended meaning.

Return ONLY valid JSON with these exact keys:
{
  "relevance_score": 0-10,
  "clarity_score": 0-10,
  "depth_score": 0-10,
  "structure_score": 0-10,
  "feedback_text": "string",
  "strengths": ["string"],
  "improvements": ["string"]
}
""".strip()

    prompt = f"""
Question:
{question}

Candidate Answer:
{answer}

Job Context:
{job_context}
""".strip()
    if is_transcribed:
        prompt = f"{prompt}\n\nNote: This answer was transcribed from audio. Ignore transcription artifacts."

    async with _LLM_EVALUATION_SEMAPHORE:
        response_text = await call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )

    parsed = _extract_json_object(response_text)
    feedback_text = str(parsed.get("feedback_text", "")).strip()
    if not feedback_text:
        raise ValueError("Missing non-empty feedback_text in LLM response.")

    return LlmEvaluation(
        relevance_score=_normalize_score_field(parsed, "relevance_score"),
        clarity_score=_normalize_score_field(parsed, "clarity_score"),
        depth_score=_normalize_score_field(parsed, "depth_score"),
        structure_score=_normalize_score_field(parsed, "structure_score"),
        feedback_text=feedback_text,
        strengths=_normalize_string_list(parsed.get("strengths")),
        improvements=_normalize_string_list(parsed.get("improvements")),
    )


def hybrid_score(rule_scores: ScoreSet, llm_scores: ScoreSet) -> HybridScoreSet:
    """Blend deterministic and LLM scoring dimensions into final scores."""
    relevance = _round_score((0.3 * rule_scores["relevance_score"]) + (0.7 * llm_scores["relevance_score"]))
    clarity = _round_score((0.2 * rule_scores["clarity_score"]) + (0.8 * llm_scores["clarity_score"]))
    depth = _round_score((0.2 * rule_scores["depth_score"]) + (0.8 * llm_scores["depth_score"]))
    structure = _round_score((0.4 * rule_scores["structure_score"]) + (0.6 * llm_scores["structure_score"]))
    overall = _round_score((relevance + clarity + depth + structure) / 4.0)

    return HybridScoreSet(
        relevance_score=relevance,
        clarity_score=clarity,
        depth_score=depth,
        structure_score=structure,
        overall_score=overall,
    )


def _default_feedback(answer_text: str) -> tuple[str, list[str], list[str]]:
    if not (answer_text or "").strip():
        return (
            "No meaningful spoken answer was captured for this question.",
            [],
            [
                "Record a clear spoken response that directly addresses the question.",
                "Include concrete details and outcomes to improve depth.",
            ],
        )

    return (
        "Evaluation fallback was used because AI scoring was unavailable for this answer.",
        ["Response addresses at least part of the prompt."],
        [
            "Use a clearer structure (context, action, result).",
            "Add specific metrics or outcomes to strengthen impact.",
        ],
    )


def _resolve_answer_input(answer: Answer) -> tuple[str, bool]:
    transcript_present = bool((answer.transcript_text or "").strip())
    audio_file_present = bool((answer.audio_file_path or "").strip())
    is_audio_transcribed = transcript_present or audio_file_present

    typed_answer = (answer.answer_text or "").strip()
    if typed_answer:
        return typed_answer, False

    transcript_answer = (answer.transcript_text or "").strip()
    if transcript_answer:
        return transcript_answer, True

    return "", is_audio_transcribed


async def evaluate_answer(
    *,
    answer: Answer,
    question: Question,
    session: InterviewSession,
) -> AnswerEvaluationResult:
    """Evaluate one answer with hybrid scoring and robust fallbacks."""
    answer_input, is_transcribed = _resolve_answer_input(answer)
    rule_scores = rule_based_score(answer_input, question.question_text)

    try:
        llm_result = await llm_evaluate(
            question=question.question_text,
            answer=answer_input,
            job_context=session.match_summary or "",
            is_transcribed=is_transcribed,
        )
        blended = hybrid_score(rule_scores, ScoreSet(
            relevance_score=llm_result["relevance_score"],
            clarity_score=llm_result["clarity_score"],
            depth_score=llm_result["depth_score"],
            structure_score=llm_result["structure_score"],
        ))
        feedback_text = llm_result["feedback_text"]
        strengths = llm_result["strengths"] or _default_feedback(answer_input)[1]
        improvements = llm_result["improvements"] or _default_feedback(answer_input)[2]
    except Exception:
        logger.exception(
            "LLM evaluation failed for answer %s in session %s. Falling back to rule-based scores.",
            answer.id,
            session.id,
        )
        blended = hybrid_score(rule_scores, rule_scores)
        feedback_text, strengths, improvements = _default_feedback(answer_input)

    return AnswerEvaluationResult(
        answer_id=answer.id,
        question_id=question.id,
        question_text=question.question_text,
        answer_text=answer_input,
        relevance_score=blended["relevance_score"],
        clarity_score=blended["clarity_score"],
        depth_score=blended["depth_score"],
        structure_score=blended["structure_score"],
        overall_score=blended["overall_score"],
        feedback_text=feedback_text,
        strengths=strengths,
        improvements=improvements,
    )


def _get_session(db: Session, session_id: UUID) -> InterviewSession | None:
    return db.query(InterviewSession).filter(InterviewSession.id == session_id).first()


def _validate_session_access(*, db: Session, user_id: UUID, session_id: UUID) -> InterviewSession:
    session = _get_session(db, session_id)
    if session is None:
        raise NotFoundError("Interview session not found.")
    if session.user_id != user_id:
        raise EvaluationAccessError("You do not have access to this interview session.")
    return session


def _empty_session_results(*, session_id: UUID) -> SessionEvaluationResult:
    return SessionEvaluationResult(
        session_id=session_id,
        overall_score=None,
        evaluations=[],
    )


def _session_has_answers(*, db: Session, session_id: UUID) -> bool:
    answer_row = (
        db.query(Answer)
        .filter(Answer.session_id == session_id)
        .first()
    )
    return answer_row is not None


def _build_session_results(
    *,
    db: Session,
    session: InterviewSession,
    session_id: UUID,
) -> SessionEvaluationResult:
    rows = (
        db.query(Evaluation, Answer, Question)
        .join(Answer, Answer.id == Evaluation.answer_id)
        .join(Question, Question.id == Answer.question_id)
        .filter(Evaluation.session_id == session_id)
        .order_by(Question.order_index.asc(), Evaluation.created_at.asc())
        .all()
    )

    if not rows:
        if session.status == "completed" and not _session_has_answers(db=db, session_id=session_id):
            return _empty_session_results(session_id=session_id)
        raise ValidationError("Session has not been evaluated yet.")

    evaluations_payload = []
    for evaluation, answer, question in rows:
        answer_input, _ = _resolve_answer_input(answer)
        evaluations_payload.append(
            {
                "id": evaluation.id,
                "answer_id": evaluation.answer_id,
                "session_id": evaluation.session_id,
                "question_id": question.id,
                "question_text": question.question_text,
                "answer_text": answer_input,
                "relevance_score": evaluation.relevance_score,
                "clarity_score": evaluation.clarity_score,
                "depth_score": evaluation.depth_score,
                "structure_score": evaluation.structure_score,
                "overall_score": evaluation.overall_score,
                "feedback_text": evaluation.feedback_text,
                "strengths": evaluation.strengths,
                "improvements": evaluation.improvements,
                "created_at": evaluation.created_at,
            }
        )

    overall_score = _round_score(
        sum(float(item["overall_score"] or 0.0) for item in evaluations_payload)
        / len(evaluations_payload)
    )

    return SessionEvaluationResult(
        session_id=session_id,
        overall_score=overall_score,
        evaluations=evaluations_payload,
    )


async def evaluate_session(
    *,
    db: Session,
    user_id: UUID,
    session_id: UUID,
) -> SessionEvaluationResult:
    """Evaluate pending answers for a session and persist new evaluation rows."""
    session = _validate_session_access(db=db, user_id=user_id, session_id=session_id)

    async with _get_session_evaluation_lock(session_id):
        answers = (
            db.query(Answer)
            .filter(Answer.session_id == session_id)
            .order_by(Answer.created_at.asc())
            .all()
        )
        if not answers:
            if session.status == "completed":
                return _empty_session_results(session_id=session_id)
            raise ValidationError("No answers found for this session.")

        questions = (
            db.query(Question)
            .filter(Question.session_id == session_id)
            .all()
        )
        questions_by_id = {question.id: question for question in questions}

        if not questions_by_id:
            raise ValidationError("No interview questions found for this session.")

        for answer in answers:
            if answer.question_id not in questions_by_id:
                raise ValidationError("Question for one or more answers is missing in this session.")

        answer_ids = {answer.id for answer in answers}

        try:
            existing_rows = (
                db.query(Evaluation)
                .filter(Evaluation.session_id == session_id)
                .order_by(Evaluation.created_at.asc())
                .all()
            )

            existing_by_answer: dict[UUID, Evaluation] = {}
            duplicate_rows: list[Evaluation] = []
            for row in existing_rows:
                previous = existing_by_answer.get(row.answer_id)
                if previous is not None:
                    duplicate_rows.append(previous)
                existing_by_answer[row.answer_id] = row

            did_mutate = False

            for row in duplicate_rows:
                db.delete(row)
                did_mutate = True

            stale_answer_ids = [answer_id for answer_id in existing_by_answer if answer_id not in answer_ids]
            for stale_answer_id in stale_answer_ids:
                stale_row = existing_by_answer.pop(stale_answer_id, None)
                if stale_row is not None:
                    db.delete(stale_row)
                    did_mutate = True

            for answer in answers:
                if answer.id in existing_by_answer:
                    continue

                question = questions_by_id.get(answer.question_id)
                if question is None:
                    raise ValidationError("Question for one or more answers is missing in this session.")

                evaluated = await evaluate_answer(
                    answer=answer,
                    question=question,
                    session=session,
                )
                db.add(
                    Evaluation(
                        answer_id=evaluated["answer_id"],
                        session_id=session_id,
                        relevance_score=evaluated["relevance_score"],
                        clarity_score=evaluated["clarity_score"],
                        depth_score=evaluated["depth_score"],
                        structure_score=evaluated["structure_score"],
                        overall_score=evaluated["overall_score"],
                        feedback_text=evaluated["feedback_text"],
                        strengths=evaluated["strengths"],
                        improvements=evaluated["improvements"],
                    )
                )
                did_mutate = True

            if did_mutate:
                db.commit()
        except ValidationError:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to evaluate session %s for user %s", session_id, user_id)
            raise RuntimeError("Could not evaluate interview session.") from exc

        return _build_session_results(
            db=db,
            session=session,
            session_id=session_id,
        )


def get_session_results(
    *,
    db: Session,
    user_id: UUID,
    session_id: UUID,
) -> SessionEvaluationResult:
    """Return persisted evaluation results for a session."""
    session = _validate_session_access(db=db, user_id=user_id, session_id=session_id)
    return _build_session_results(
        db=db,
        session=session,
        session_id=session_id,
    )
