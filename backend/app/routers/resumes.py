from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user, get_db
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ResumeUploadResponse
from app.services.embedding_service import generate_embedding
from app.services.resume_parser import assess_resume_document, parse_resume_file


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resumes", tags=["resumes"])
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeUploadResponse:
    """Upload, parse, and persist a resume for the authenticated user."""

    original_filename = (file.filename or "").strip()
    if not original_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file is required.",
        )

    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only PDF and DOCX are allowed.",
        )

    file_bytes = await file.read()
    await file.close()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    max_upload_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds the maximum limit of {settings.max_upload_size_mb} MB.",
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid.uuid4()}{extension}"
    stored_file_path = upload_dir / stored_filename
    await asyncio.to_thread(stored_file_path.write_bytes, file_bytes)

    try:
        parser_result = await asyncio.to_thread(parse_resume_file, str(stored_file_path))
        parsed_text = str(parser_result.get("parsed_text", "")).strip()
        skills = [str(skill) for skill in parser_result.get("skills", [])]

        if not parsed_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract text from the uploaded file.",
            )

        is_resume_like, rejection_reason = await asyncio.to_thread(
            assess_resume_document,
            parsed_text,
            original_filename,
        )
        if not is_resume_like:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=rejection_reason)
    except HTTPException:
        if stored_file_path.exists():
            stored_file_path.unlink()
        raise
    except ValueError as exc:
        if stored_file_path.exists():
            stored_file_path.unlink()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        if stored_file_path.exists():
            stored_file_path.unlink()
        logger.exception("Resume parsing failed for file %s", original_filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract text from the uploaded file.",
        ) from exc

    embedding: str | None = None
    try:
        generated_embedding = await asyncio.to_thread(generate_embedding, parsed_text)
        if isinstance(generated_embedding, list):
            embedding = "[" + ",".join(str(value) for value in generated_embedding) + "]"
        elif isinstance(generated_embedding, str):
            embedding = generated_embedding
        else:
            logger.warning("Embedding output type is unsupported. Skipping persisted embedding.")
    except NotImplementedError:
        logger.info("Embedding generation is not configured. Continuing without embedding.")
    except Exception:
        logger.exception("Embedding generation failed. Continuing without embedding.")

    resume = Resume(
        user_id=current_user.id,
        filename=original_filename,
        stored_filename=stored_filename,
        parsed_text=parsed_text,
        skills=skills,
        embedding=embedding,
    )

    try:
        db.add(resume)
        db.commit()
        db.refresh(resume)
    except Exception as exc:
        db.rollback()
        if stored_file_path.exists():
            stored_file_path.unlink()
        logger.exception("Failed to store uploaded resume metadata for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save the uploaded resume.",
        ) from exc

    return ResumeUploadResponse(
        id=resume.id,
        filename=resume.filename,
        skills=resume.skills,
        created_at=resume.created_at,
    )


@router.get("/", response_model=list[ResumeUploadResponse])
async def list_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ResumeUploadResponse]:
    """Return resume-like uploads for the authenticated user, newest first.

    Legacy non-resume documents uploaded before validation was added are
    excluded from this list so users only see selectable resumes.
    """
    resumes = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
        .all()
    )

    valid_resumes: list[Resume] = []
    for resume in resumes:
        is_resume_like, _ = assess_resume_document(resume.parsed_text or "", resume.filename)
        if is_resume_like:
            valid_resumes.append(resume)
        else:
            logger.info(
                "Excluding non-resume document from resume list",
                extra={"resume_id": str(resume.id), "user_id": str(current_user.id)},
            )

    return [
        ResumeUploadResponse(
            id=r.id,
            filename=r.filename,
            skills=r.skills,
            created_at=r.created_at,
        )
        for r in valid_resumes
    ]


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_resume(
    resume_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a resume owned by the authenticated user."""
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")

    stored_file_path = Path(settings.upload_dir) / resume.stored_filename

    try:
        db.delete(resume)
        db.commit()
        logger.info(
            "Deleted resume successfully.",
            extra={"resume_id": str(resume_id), "user_id": str(current_user.id)},
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to delete resume %s for user %s", resume_id, current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete the resume.",
        ) from exc

    try:
        stored_file_path.unlink(missing_ok=True)
    except Exception:
        logger.warning(
            "Resume file could not be removed from disk after DB deletion.",
            extra={"resume_id": str(resume_id), "path": str(stored_file_path)},
            exc_info=True,
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
