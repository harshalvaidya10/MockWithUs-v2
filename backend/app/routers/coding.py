from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import get_current_user, get_db
from app.models.user import User
from app.schemas.coding import (
    CodeRunRequest,
    CodeRunResponse,
    CodeSubmitResponse,
    CodingProblemOut,
    CodingSessionStartRequest,
    CodingSessionStartResponse,
    TestCaseOut,
)
from app.services.coding_service import (
    get_coding_problem_for_session,
    get_latest_coding_results_for_session,
    run_coding_submission,
    serialize_run_response,
    serialize_submit_response,
    start_coding_session,
)


router = APIRouter(prefix="/coding", tags=["coding"])
logger = logging.getLogger(__name__)


@router.post("/start", response_model=CodingSessionStartResponse, status_code=status.HTTP_201_CREATED)
async def start_coding_session_route(
    payload: CodingSessionStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CodingSessionStartResponse:
    """Start a coding mock session and return generated problem with sample tests."""
    try:
        result = await start_coding_session(
            db=db,
            user_id=current_user.id,
            resume_id=payload.resume_id,
            job_id=payload.job_id,
            difficulty=payload.difficulty,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error while starting coding session for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not start coding session.",
        ) from exc

    return CodingSessionStartResponse(
        session_id=result["session"].id,
        problem=CodingProblemOut.model_validate(result["problem"]),
        sample_test_cases=[TestCaseOut.model_validate(case) for case in result["sample_test_cases"]],
    )


@router.post("/run", response_model=CodeRunResponse)
async def run_coding_submission_route(
    payload: CodeRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CodeRunResponse:
    """Run code against sample test cases only."""
    try:
        result = await run_coding_submission(
            db=db,
            user_id=current_user.id,
            session_id=payload.session_id,
            problem_id=payload.problem_id,
            language=payload.language,
            source_code=payload.source_code,
            submission_type="run",
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error while running coding submission for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not run coding submission.",
        ) from exc

    return CodeRunResponse.model_validate(serialize_run_response(result))


@router.post("/submit", response_model=CodeSubmitResponse)
async def submit_coding_solution_route(
    payload: CodeRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CodeSubmitResponse:
    """Submit code against all test cases and return evaluation feedback."""
    try:
        result = await run_coding_submission(
            db=db,
            user_id=current_user.id,
            session_id=payload.session_id,
            problem_id=payload.problem_id,
            language=payload.language,
            source_code=payload.source_code,
            submission_type="submit",
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error while submitting coding solution for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not submit coding solution.",
        ) from exc

    return CodeSubmitResponse.model_validate(serialize_submit_response(result))


@router.get("/{session_id}/problem", response_model=CodingSessionStartResponse)
def get_coding_problem_route(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CodingSessionStartResponse:
    """Return coding problem details and visible sample test cases for a session."""
    try:
        payload = get_coding_problem_for_session(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error while loading coding problem for session %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load coding problem.",
        ) from exc

    return CodingSessionStartResponse(
        session_id=session_id,
        problem=CodingProblemOut.model_validate(payload["problem"]),
        sample_test_cases=[TestCaseOut.model_validate(case) for case in payload["sample_test_cases"]],
    )


@router.get("/{session_id}/results", response_model=CodeSubmitResponse)
def get_coding_results_route(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CodeSubmitResponse:
    """Return latest submitted coding results + evaluation for a session."""
    try:
        result = get_latest_coding_results_for_session(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error while loading coding results for session %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load coding results.",
        ) from exc

    return CodeSubmitResponse.model_validate(serialize_submit_response(result))
