from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import get_current_user, get_db
from app.models.user import User
from app.schemas.evaluation import FeedbackOut
from app.services.evaluator import EvaluationAccessError, evaluate_session, get_session_results


router = APIRouter(prefix="", tags=["evaluations"])
logger = logging.getLogger(__name__)


@router.post("/evaluate/{session_id}", response_model=FeedbackOut)
async def evaluate_interview_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedbackOut:
    """Evaluate all answers in an interview session and persist per-answer feedback."""
    try:
        result = await evaluate_session(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EvaluationAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error while evaluating session %s for user %s",
            session_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not evaluate interview session.",
        ) from exc

    return FeedbackOut.model_validate(result)


@router.get("/results/{session_id}", response_model=FeedbackOut)
def get_interview_results(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedbackOut:
    """Return persisted session-level interview evaluation results."""
    try:
        result = get_session_results(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EvaluationAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error while loading results for session %s and user %s",
            session_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load interview results.",
        ) from exc

    return FeedbackOut.model_validate(result)
