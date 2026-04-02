from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user, get_db
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ResumeUploadResponse
from app.services.embedding_service import generate_embedding
from app.services.resume_parser import parse_resume_file


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
