from __future__ import annotations

import asyncio
import logging
from typing import TypedDict
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.answer import Answer
from app.models.interview import InterviewSession
from app.models.job import JobDescription
from app.models.question import Question
from app.models.resume import Resume
from app.schemas.interview import SessionCreate
from app.services.matcher import parse_embedding_vector, run_match
from app.services.question_generator import generate_questions, validate_questions


logger = logging.getLogger(__name__)
QUESTION_GENERATION_TIMEOUT_SECONDS = 60


class InterviewStartResult(TypedDict):
    session: InterviewSession
    questions: list[Question]


class InterviewHistoryItem(TypedDict):
    session: InterviewSession
    question_count: int
    answered_count: int


class InterviewHistoryResult(TypedDict):
    sessions: list[InterviewHistoryItem]


def _get_resume_for_user(db: Session, *, resume_id: UUID, user_id: UUID) -> Resume | None:
    return (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user_id,
        )
        .first()
    )


def _get_job_for_user(db: Session, *, job_id: UUID, user_id: UUID) -> JobDescription | None:
    return (
        db.query(JobDescription)
        .filter(
            JobDescription.id == job_id,
            JobDescription.user_id == user_id,
        )
        .first()
    )


def get_interview_session_for_user(
    *,
    db: Session,
    user_id: UUID,
    session_id: UUID,
) -> InterviewStartResult:
    """Load an interview session and its questions for the authenticated user."""
    session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id,
            InterviewSession.user_id == user_id,
        )
        .first()
    )
    if session is None:
        raise NotFoundError("Interview session not found.")

    questions = (
        db.query(Question)
        .filter(Question.session_id == session.id)
        .all()
    )
    ordered_questions = sorted(questions, key=lambda question: question.order_index)

    return InterviewStartResult(session=session, questions=ordered_questions)


def list_interview_sessions_for_user(
    *,
    db: Session,
    user_id: UUID,
) -> InterviewHistoryResult:
    """Return all interview sessions for the authenticated user (newest first)."""
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == user_id)
        .order_by(InterviewSession.created_at.desc())
        .all()
    )

    history_items: list[InterviewHistoryItem] = []
    for session in sessions:
        questions = (
            db.query(Question)
            .filter(Question.session_id == session.id)
            .all()
        )
        answers = (
            db.query(Answer)
            .filter(Answer.session_id == session.id)
            .all()
        )

        question_count = len(questions)
        answered_count = len({answer.question_id for answer in answers})

        history_items.append(
            InterviewHistoryItem(
                session=session,
                question_count=question_count,
                answered_count=answered_count,
            )
        )

    return InterviewHistoryResult(sessions=history_items)


async def start_interview_session(
    *,
    db: Session,
    user_id: UUID,
    payload: SessionCreate,
) -> InterviewStartResult:
    """Create an interview session and persist generated interview questions."""
    resume = _get_resume_for_user(db, resume_id=payload.resume_id, user_id=user_id)
    if resume is None:
        raise NotFoundError("Resume not found.")

    job = _get_job_for_user(db, job_id=payload.job_id, user_id=user_id)
    if job is None:
        raise NotFoundError("Job description not found.")

    match_result = await asyncio.to_thread(
        run_match,
        parse_embedding_vector(resume.embedding),
        parse_embedding_vector(job.embedding),
        resume.skills,
        job.required_skills,
        job.title,
    )

    session = InterviewSession(
        user_id=user_id,
        resume_id=resume.id,
        job_id=job.id,
        match_score=match_result["match_score"],
        match_summary=match_result["match_summary"],
        status="draft",
    )

    try:
        db.add(session)
        db.flush()
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to create interview session for user %s", user_id)
        raise RuntimeError("Could not create interview session.") from exc

    try:
        generated = await asyncio.wait_for(
            generate_questions(
                resume_text=resume.parsed_text or "",
                jd_text=job.content or "",
                match_summary=match_result["match_summary"],
                matched_skills=match_result["skill_gaps"]["matched"],
                missing_skills=match_result["skill_gaps"]["missing"],
            ),
            timeout=QUESTION_GENERATION_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.exception(
            "Question generation timed out after %ss for session %s. Using fallback questions.",
            QUESTION_GENERATION_TIMEOUT_SECONDS,
            session.id,
        )
        generated = validate_questions([])

    questions: list[Question] = []
    for index, generated_question in enumerate(generated, start=1):
        question = Question(
            session_id=session.id,
            question_text=generated_question["question_text"],
            category=generated_question["category"],
            rationale=generated_question["rationale"],
            order_index=index,
        )
        db.add(question)
        questions.append(question)

    session.status = "ready"

    try:
        db.commit()
        db.refresh(session)
        for question in questions:
            db.refresh(question)
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Failed to persist interview questions for session %s",
            session.id,
        )
        raise RuntimeError("Could not save generated interview questions.") from exc

    return InterviewStartResult(session=session, questions=questions)
