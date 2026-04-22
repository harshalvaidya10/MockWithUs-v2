from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from concurrent.futures import (
    CancelledError as ConcurrentCancelledError,
    Future as ConcurrentFuture,
    TimeoutError as ConcurrentTimeoutError,
)
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.database import SessionLocal
from app.models.answer import Answer
from app.models.interview import InterviewSession
from app.models.question import Question
from app.services.evaluator import evaluate_session
from app.services.transcription_service import TranscriptionError, TranscriptionInputError, transcribe_audio_file


logger = logging.getLogger(__name__)
settings = get_settings()
_BG_EVAL_TASKS: set[asyncio.Task[None]] = set()
_BG_EVAL_THREADSAFE_FUTURES: set[ConcurrentFuture[None]] = set()
_BG_EVAL_TRACKING_LOCK = threading.Lock()
_BG_EVAL_LOOP: asyncio.AbstractEventLoop | None = None
_BG_EVAL_LOOP_LOCK = threading.Lock()

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".webm"}
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "audio/webm",
    "application/octet-stream",  # Some browsers/clients use this fallback.
}
CONTENT_TYPE_EXTENSION_MAP = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
}


class AnswerAccessError(Exception):
    """Raised when a user tries to access another user's interview session."""


class AnswerValidationError(Exception):
    """Raised when the submitted answer payload is invalid."""


class AudioAnswerResult(TypedDict):
    answer: Answer


class SessionAnswerListResult(TypedDict):
    answers: list[Answer]


def _resolve_audio_extension(upload: UploadFile) -> str:
    filename = (upload.filename or "").strip()
    extension = Path(filename).suffix.lower() if filename else ""
    if extension in ALLOWED_AUDIO_EXTENSIONS:
        return extension

    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    mapped_extension = CONTENT_TYPE_EXTENSION_MAP.get(content_type)
    if mapped_extension:
        return mapped_extension

    raise AnswerValidationError(
        "Unsupported audio format. Allowed types: wav, mp3, m4a, ogg, webm."
    )


def _validate_audio_content_type(upload: UploadFile) -> None:
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise AnswerValidationError(
            "Unsupported audio content type. Please upload a wav, mp3, m4a, ogg, or webm file."
        )


def _answers_upload_dir() -> Path:
    return Path(settings.upload_dir) / "answers"


def _get_session(db: Session, session_id: UUID) -> InterviewSession | None:
    return db.query(InterviewSession).filter(InterviewSession.id == session_id).first()


def _get_question(db: Session, question_id: UUID) -> Question | None:
    return db.query(Question).filter(Question.id == question_id).first()


def configure_background_evaluation_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store the application's primary event loop for cross-thread scheduling."""
    global _BG_EVAL_LOOP
    with _BG_EVAL_LOOP_LOCK:
        _BG_EVAL_LOOP = loop


async def _run_background_evaluation(*, user_id: UUID, session_id: UUID) -> None:
    db = SessionLocal()
    try:
        await evaluate_session(
            db=db,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        logger.exception("Background evaluation failed for session %s", session_id)
    finally:
        db.close()


def _track_background_task(task: asyncio.Task[None], *, session_id: UUID) -> None:
    with _BG_EVAL_TRACKING_LOCK:
        _BG_EVAL_TASKS.add(task)

    def _cleanup(done_task: asyncio.Task[None]) -> None:
        with _BG_EVAL_TRACKING_LOCK:
            _BG_EVAL_TASKS.discard(done_task)
        try:
            done_task.result()
        except asyncio.CancelledError:
            logger.info("Background evaluation task canceled for session %s", session_id)
        except Exception:
            logger.exception("Background evaluation job crashed for session %s", session_id)

    task.add_done_callback(_cleanup)


def _track_background_threadsafe_future(future: ConcurrentFuture[None], *, session_id: UUID) -> None:
    with _BG_EVAL_TRACKING_LOCK:
        _BG_EVAL_THREADSAFE_FUTURES.add(future)

    def _cleanup(done_future: ConcurrentFuture[None]) -> None:
        with _BG_EVAL_TRACKING_LOCK:
            _BG_EVAL_THREADSAFE_FUTURES.discard(done_future)
        try:
            done_future.result()
        except ConcurrentCancelledError:
            logger.info("Background evaluation future canceled for session %s", session_id)
        except Exception:
            logger.exception("Background evaluation future crashed for session %s", session_id)

    future.add_done_callback(_cleanup)


def _schedule_background_evaluation(*, user_id: UUID, session_id: UUID) -> None:
    logger.info("Background evaluation started for session %s", session_id)
    with _BG_EVAL_LOOP_LOCK:
        target_loop = _BG_EVAL_LOOP

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if current_loop is not None and target_loop is None:
        task = current_loop.create_task(
            _run_background_evaluation(user_id=user_id, session_id=session_id)
        )
        _track_background_task(task, session_id=session_id)
        return

    if current_loop is not None and current_loop is target_loop:
        task = current_loop.create_task(
            _run_background_evaluation(user_id=user_id, session_id=session_id)
        )
        _track_background_task(task, session_id=session_id)
        return

    if target_loop is None or target_loop.is_closed():
        logger.error(
            "Background evaluation loop is unavailable; skipping schedule "
            "(session_id=%s, user_id=%s)",
            session_id,
            user_id,
        )
        return

    future = asyncio.run_coroutine_threadsafe(
        _run_background_evaluation(user_id=user_id, session_id=session_id),
        target_loop,
    )
    _track_background_threadsafe_future(future, session_id=session_id)


def _wait_for_threadsafe_futures(futures: list[ConcurrentFuture[None]], timeout_seconds: float) -> None:
    for future in futures:
        try:
            future.result(timeout=timeout_seconds)
        except ConcurrentCancelledError:
            continue
        except ConcurrentTimeoutError:
            logger.warning("Timed out waiting for background evaluation future during shutdown.")
        except Exception:
            logger.exception("Background evaluation future failed while shutting down.")


async def shutdown_background_evaluation_scheduler(*, timeout_seconds: float = 5.0) -> None:
    """Cancel/await tracked background jobs and detach from app loop."""
    global _BG_EVAL_LOOP
    with _BG_EVAL_TRACKING_LOCK:
        tasks = list(_BG_EVAL_TASKS)
        futures = list(_BG_EVAL_THREADSAFE_FUTURES)

    for future in futures:
        future.cancel()
    for task in tasks:
        task.cancel()

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    if futures:
        await asyncio.to_thread(_wait_for_threadsafe_futures, futures, timeout_seconds)

    with _BG_EVAL_TRACKING_LOCK:
        _BG_EVAL_TASKS.clear()
        _BG_EVAL_THREADSAFE_FUTURES.clear()

    with _BG_EVAL_LOOP_LOCK:
        _BG_EVAL_LOOP = None


def list_answers_for_session(
    *,
    db: Session,
    user_id: UUID,
    session_id: UUID,
) -> SessionAnswerListResult:
    """Return saved answers for an interview session after ownership validation."""
    session = _get_session(db, session_id)
    if session is None:
        raise NotFoundError("Interview session not found.")
    if session.user_id != user_id:
        raise AnswerAccessError("You do not have access to this interview session.")

    answers = (
        db.query(Answer)
        .filter(Answer.session_id == session_id)
        .order_by(Answer.created_at.asc())
        .all()
    )
    return SessionAnswerListResult(answers=answers)


async def submit_audio_answer(
    *,
    db: Session,
    user_id: UUID,
    session_id: UUID,
    question_id: UUID,
    audio: UploadFile | None,
) -> AudioAnswerResult:
    """Validate, transcribe, and persist an audio answer for a session question."""
    if audio is None:
        raise AnswerValidationError("Audio file is required.")

    session = _get_session(db, session_id)
    if session is None:
        raise NotFoundError("Interview session not found.")
    if session.user_id != user_id:
        raise AnswerAccessError("You do not have access to this interview session.")

    question = _get_question(db, question_id)
    if question is None:
        raise NotFoundError("Question not found.")
    if question.session_id != session_id:
        raise AnswerValidationError("Question does not belong to the provided session.")

    _validate_audio_content_type(audio)
    extension = _resolve_audio_extension(audio)

    max_size_bytes = settings.max_answer_audio_size_mb * 1024 * 1024
    answers_dir = _answers_upload_dir() / str(session_id)
    answers_dir.mkdir(parents=True, exist_ok=True)

    generated_name = f"{uuid.uuid4()}{extension}"
    absolute_audio_path = answers_dir / generated_name
    relative_audio_path = str(Path("answers") / str(session_id) / generated_name)

    bytes_written = 0
    chunk_size = 1024 * 1024
    try:
        with absolute_audio_path.open("wb") as destination:
            while True:
                chunk = await audio.read(chunk_size)
                if not chunk:
                    break

                bytes_written += len(chunk)
                if bytes_written > max_size_bytes:
                    raise AnswerValidationError(
                        f"Audio file exceeds {settings.max_answer_audio_size_mb} MB limit."
                    )

                destination.write(chunk)
    except AnswerValidationError:
        absolute_audio_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        absolute_audio_path.unlink(missing_ok=True)
        raise RuntimeError("Could not process uploaded audio file.") from exc
    finally:
        await audio.close()

    if bytes_written == 0:
        absolute_audio_path.unlink(missing_ok=True)
        raise AnswerValidationError("Audio file is empty.")

    try:
        transcript_text = await asyncio.to_thread(transcribe_audio_file, str(absolute_audio_path))
    except TranscriptionInputError as exc:
        absolute_audio_path.unlink(missing_ok=True)
        raise AnswerValidationError(str(exc)) from exc
    except TranscriptionError as exc:
        absolute_audio_path.unlink(missing_ok=True)
        raise RuntimeError("Audio transcription service is unavailable.") from exc
    except Exception as exc:
        absolute_audio_path.unlink(missing_ok=True)
        raise RuntimeError("Could not transcribe audio answer.") from exc

    answer = Answer(
        session_id=session_id,
        question_id=question_id,
        answer_text=None,
        transcript_text=transcript_text,
        audio_file_path=relative_audio_path,
    )

    session_questions = (
        db.query(Question)
        .filter(Question.session_id == session_id)
        .all()
    )
    session_answers = (
        db.query(Answer)
        .filter(Answer.session_id == session_id)
        .all()
    )
    answered_question_ids = {saved_answer.question_id for saved_answer in session_answers}
    answered_question_ids.add(question_id)

    should_start_background_evaluation = False
    is_now_complete = bool(session_questions) and len(answered_question_ids) >= len(session_questions)
    if is_now_complete:
        should_start_background_evaluation = session.status != "completed"
        session.status = "completed"
        if session.completed_at is None:
            should_start_background_evaluation = True
            session.completed_at = datetime.now(timezone.utc)

    committed = False
    try:
        db.add(answer)
        db.commit()
        committed = True
        db.refresh(answer)
    except Exception as exc:
        db.rollback()
        if not committed:
            absolute_audio_path.unlink(missing_ok=True)
        logger.exception(
            "Failed to persist audio answer (session_id=%s, question_id=%s, user_id=%s)",
            session_id,
            question_id,
            user_id,
        )
        raise RuntimeError("Could not save the transcribed answer.") from exc

    if should_start_background_evaluation:
        try:
            _schedule_background_evaluation(
                user_id=user_id,
                session_id=session_id,
            )
        except Exception:
            logger.exception(
                "Failed to schedule background evaluation after saving answer "
                "(session_id=%s, question_id=%s, user_id=%s)",
                session_id,
                question_id,
                user_id,
            )

    return AudioAnswerResult(answer=answer)
