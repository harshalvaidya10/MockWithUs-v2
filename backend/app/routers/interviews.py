from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import get_current_user, get_db
from app.models.user import User
from app.schemas.interview import (
    SessionCreate,
    SessionHistoryItemOut,
    SessionHistoryListOut,
    SessionStartOut,
    SessionStartQuestionOut,
)
from app.services.interview_service import (
    complete_interview_session_for_user,
    delete_interview_session_for_user,
    get_interview_session_for_user,
    list_interview_sessions_for_user,
    start_interview_session,
)

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


@router.get("", response_model=SessionHistoryListOut)
def list_interview_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionHistoryListOut:
    """List interview sessions for the authenticated user."""
    try:
        result = list_interview_sessions_for_user(
            db=db,
            user_id=current_user.id,
        )
    except Exception as exc:
        logger.exception("Unexpected error while listing interviews for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load interview history.",
        ) from exc

    return SessionHistoryListOut(
        sessions=[
            SessionHistoryItemOut(
                session_id=item["session"].id,
                resume_id=item["session"].resume_id,
                job_id=item["session"].job_id,
                status=item["session"].status,
                session_type=item["session"].session_type,
                match_score=item["session"].match_score,
                match_summary=item["session"].match_summary,
                question_count=item["question_count"],
                answered_count=item["answered_count"],
                is_complete=(
                    item["session"].status == "completed"
                    or (item["question_count"] > 0 and item["answered_count"] >= item["question_count"])
                ),
                created_at=item["session"].created_at,
                completed_at=item["session"].completed_at,
            )
            for item in result["sessions"]
        ]
    )


@router.post("/{session_id}/complete", status_code=status.HTTP_200_OK)
def complete_interview_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Mark an interview session as completed so users can stop early and view results."""
    try:
        complete_interview_session_for_user(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error while completing interview session %s for user %s",
            session_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not complete interview session.",
        ) from exc

    return {"status": "completed"}


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


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a saved interview/coding session and its dependent data."""
    try:
        delete_interview_session_for_user(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error while deleting interview session %s for user %s",
            session_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete interview session.",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
