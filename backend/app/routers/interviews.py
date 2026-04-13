from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import get_current_user, get_db
from app.models.user import User
from app.schemas.interview import SessionCreate, SessionStartOut, SessionStartQuestionOut
from app.services.interview_service import get_interview_session_for_user, start_interview_session

router = APIRouter(prefix="/interviews", tags=["interviews"])
logger = logging.getLogger(__name__)


@router.post("/start", response_model=SessionStartOut, status_code=status.HTTP_201_CREATED)
async def start_interview(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionStartOut:
    """Create an interview session and generate tailored questions."""
    try:
        result = await start_interview_session(
            db=db,
            user_id=current_user.id,
            payload=payload,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error while starting interview for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not start interview session.",
        ) from exc

    return SessionStartOut(
        session_id=result["session"].id,
        match_score=result["session"].match_score or 0.0,
        match_summary=result["session"].match_summary or "",
        questions=[SessionStartQuestionOut.model_validate(question) for question in result["questions"]],
    )


@router.get("/{session_id}", response_model=SessionStartOut)
def get_interview_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionStartOut:
    """Fetch a started interview session and its generated questions."""
    try:
        result = get_interview_session_for_user(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error while loading interview session %s for user %s",
            session_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load interview session.",
        ) from exc

    return SessionStartOut(
        session_id=result["session"].id,
        match_score=result["session"].match_score or 0.0,
        match_summary=result["session"].match_summary or "",
        questions=[SessionStartQuestionOut.model_validate(question) for question in result["questions"]],
    )
