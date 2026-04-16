from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import get_current_user, get_db
from app.models.user import User
from app.schemas.answer import AudioAnswerOut, SessionAnswerItemOut, SessionAnswerListOut
from app.services.answer_service import (
    AnswerAccessError,
    AnswerValidationError,
    list_answers_for_session,
    submit_audio_answer,
)

router = APIRouter(prefix="/answers", tags=["answers"])
logger = logging.getLogger(__name__)


@router.post("/audio", response_model=AudioAnswerOut, status_code=status.HTTP_201_CREATED)
async def submit_audio_answer_route(
    session_id: UUID = Form(...),
    question_id: UUID = Form(...),
    audio: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AudioAnswerOut:
    """Submit a spoken answer audio file, transcribe it, and persist the answer record."""
    try:
        result = await submit_audio_answer(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            question_id=question_id,
            audio=audio,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AnswerAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AnswerValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected failure during audio answer submission (session_id=%s, question_id=%s, user_id=%s)",
            session_id,
            question_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not submit audio answer.",
        ) from exc

    answer = result["answer"]
    return AudioAnswerOut(
        answer_id=answer.id,
        session_id=answer.session_id,
        question_id=answer.question_id,
        transcript_text=answer.transcript_text or "",
        created_at=answer.created_at,
    )


@router.get("/session/{session_id}", response_model=SessionAnswerListOut)
def list_session_answers_route(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionAnswerListOut:
    """Return saved answers for a session so clients can resume interview progress."""
    try:
        result = list_answers_for_session(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AnswerAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected failure while listing answers for session %s (user_id=%s)",
            session_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load session answers.",
        ) from exc

    return SessionAnswerListOut(
        session_id=session_id,
        answers=[
            SessionAnswerItemOut(
                answer_id=answer.id,
                session_id=answer.session_id,
                question_id=answer.question_id,
                transcript_text=answer.transcript_text,
                created_at=answer.created_at,
            )
            for answer in result["answers"]
        ],
    )
