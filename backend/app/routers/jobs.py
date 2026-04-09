from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user, get_db
from app.models.job import JobDescription
from app.models.resume import Resume
from app.models.user import User
from app.schemas.job import JobCreate, JobDetailOut, JobOut, MatchOut, SkillGapOut
from app.services.embedding_service import generate_embedding
from app.services.jd_parser import parse_jd
from app.services.matcher import parse_embedding_vector, run_match
from app.services.resume_parser import assess_resume_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_job_for_user(db: Session, job_id: UUID, user_id: UUID) -> JobDescription | None:
    return (
        db.query(JobDescription)
        .filter(JobDescription.id == job_id, JobDescription.user_id == user_id)
        .first()
    )


def _get_resume_for_user(db: Session, resume_id: UUID, user_id: UUID) -> Resume | None:
    return (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == user_id)
        .first()
    )


def _serialize_embedding(raw: object) -> str | None:
    if isinstance(raw, list):
        return "[" + ",".join(str(v) for v in raw) + "]"
    if isinstance(raw, str):
        return raw
    return None


@router.post("/", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobOut:
    """Parse and persist a job description for the authenticated user."""

    try:
        parsed = await asyncio.to_thread(parse_jd, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    embedding: str | None = None
    try:
        raw = await asyncio.to_thread(generate_embedding, str(parsed["cleaned_content"]))
        embedding = _serialize_embedding(raw)
        if raw is not None and embedding is None:
            logger.warning("Embedding output type is unsupported. Skipping persisted embedding.")
    except NotImplementedError:
        logger.info("Embedding service not configured; persisting job without embedding.")
    except Exception:
        logger.warning(
            "Embedding generation failed for job description; continuing without embedding.",
            exc_info=True,
        )

    job = JobDescription(
        user_id=current_user.id,
        title=payload.title,
        company=payload.company,
        content=parsed["cleaned_content"],
        keywords=parsed["keywords"],
        required_skills=parsed["required_skills"],
        embedding=embedding,
    )

    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to persist job description for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save the job description.",
        ) from exc

    logger.info(
        "Job description created",
        extra={"job_id": str(job.id), "user_id": str(current_user.id)},
    )
    return JobOut.model_validate(job)


@router.get("/", response_model=list[JobOut])
async def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JobOut]:
    """Return all job descriptions for the authenticated user, newest first."""

    jobs = (
        db.query(JobDescription)
        .filter(JobDescription.user_id == current_user.id)
        .order_by(JobDescription.created_at.desc())
        .all()
    )
    return [JobOut.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobDetailOut)
async def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDetailOut:
    """Return a single job description with its full content.

    Filters on both id AND user_id and returns 404 (not 403) when the job
    belongs to another user — returning 403 would leak the existence of the resource.
    """
    job = _get_job_for_user(db, job_id=job_id, user_id=current_user.id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found.",
        )

    return JobDetailOut.model_validate(job)


@router.get("/{job_id}/match", response_model=MatchOut)
async def match_resume_to_job(
    job_id: UUID,
    resume_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchOut:
    """Run the resume-to-JD matcher and return score, skill gaps, and summary.

    Both resources must belong to the authenticated user; 404 is returned in
    either case to avoid leaking existence of other users' data.
    """
    job = _get_job_for_user(db, job_id=job_id, user_id=current_user.id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job description not found.")

    resume = _get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")

    is_resume_like, rejection_reason = await asyncio.to_thread(
        assess_resume_document,
        resume.parsed_text or "",
        resume.filename,
    )
    if not is_resume_like:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=rejection_reason)

    result = await asyncio.to_thread(
        run_match,
        parse_embedding_vector(resume.embedding),
        parse_embedding_vector(job.embedding),
        resume.skills,
        job.required_skills,
        job.title,
    )

    return MatchOut(
        match_score=result["match_score"],
        skill_gaps=SkillGapOut(**result["skill_gaps"]),
        match_summary=result["match_summary"],
        resume_id=resume_id,
        job_id=job_id,
    )
