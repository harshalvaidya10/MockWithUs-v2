from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.security import get_current_user, get_db
from app.main import app
from app.models.user import User
from app.routers import resumes as resumes_router
from app.services.resume_parser import extract_skills


client = TestClient(app)


class FakeSession:
    """Minimal DB-session substitute for router tests."""

    def __init__(self) -> None:
        self.added_objects: list[object] = []
        self.commit_called = False

    def add(self, obj: object) -> None:
        self.added_objects.append(obj)

    def commit(self) -> None:
        self.commit_called = True

    def refresh(self, obj: object) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)

    def rollback(self) -> None:
        return


@pytest.fixture()
def authenticated_context(tmp_path: Path):
    """Override auth + DB dependencies for isolated upload tests."""

    settings = get_settings()
    original_upload_dir = settings.upload_dir
    original_max_upload_size_mb = settings.max_upload_size_mb

    settings.upload_dir = str(tmp_path)
    settings.max_upload_size_mb = 5

    fake_db = FakeSession()
    user = User(email="candidate@example.com", password_hash="hashed-password")
    user.id = uuid4()

    def override_get_db():
        yield fake_db

    def override_get_current_user() -> User:
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    yield {"db": fake_db, "user": user, "tmp_path": tmp_path}

    app.dependency_overrides.clear()
    settings.upload_dir = original_upload_dir
    settings.max_upload_size_mb = original_max_upload_size_mb


def test_upload_requires_auth() -> None:
    """Ensure resume upload cannot be used anonymously."""

    response = client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 401


def test_upload_rejects_unsupported_file_type(authenticated_context: dict[str, object]) -> None:
    """Ensure unsupported extensions are rejected with a clear 400 error."""

    response = client.post(
        "/resumes/upload",
        files={"file": ("resume.txt", b"plain text content", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type. Only PDF and DOCX are allowed."


def test_successful_upload_stores_resume_and_returns_expected_shape(
    authenticated_context: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure upload persists metadata and returns the upload response schema."""

    monkeypatch.setattr(
        resumes_router,
        "parse_resume_file",
        lambda _: {
            "parsed_text": "Experienced Python and FastAPI engineer with PostgreSQL background.",
            "skills": ["Python", "FastAPI", "PostgreSQL"],
        },
    )
    monkeypatch.setattr(
        resumes_router,
        "generate_embedding",
        lambda _: [0.1, 0.2, 0.3],
    )

    response = client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", b"%PDF-1.4 mocked content", "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert set(payload.keys()) == {"id", "filename", "skills", "created_at"}
    assert payload["filename"] == "resume.pdf"
    assert payload["skills"] == ["Python", "FastAPI", "PostgreSQL"]

    fake_db = authenticated_context["db"]
    assert isinstance(fake_db, FakeSession)
    assert fake_db.commit_called
    assert len(fake_db.added_objects) == 1

    stored_resume = fake_db.added_objects[0]
    assert stored_resume.filename == "resume.pdf"
    assert stored_resume.stored_filename.endswith(".pdf")
    assert stored_resume.stored_filename != "resume.pdf"
    assert stored_resume.parsed_text.startswith("Experienced Python")

    saved_file = Path(authenticated_context["tmp_path"]) / stored_resume.stored_filename
    assert saved_file.exists()


def test_extract_skills_detects_basic_resume_keywords() -> None:
    """Ensure skill extraction catches common engineering keywords."""

    text = """
    Built production APIs with FASTAPI and Python. Deployed services on AWS with Docker.
    Implemented CI/CD pipelines and worked with PostgreSQL plus TypeScript dashboards.
    """

    assert extract_skills(text) == [
        "Python",
        "TypeScript",
        "FastAPI",
        "PostgreSQL",
        "Docker",
        "AWS",
        "CI/CD",
    ]


def test_upload_returns_user_friendly_error_when_text_extraction_fails(
    authenticated_context: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure parser failures return a clear message to the client."""

    def raise_empty_extraction(_: str) -> dict[str, object]:
        raise ValueError("Could not extract text from the uploaded file.")

    monkeypatch.setattr(resumes_router, "parse_resume_file", raise_empty_extraction)

    response = client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", b"%PDF-1.4 mocked content", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Could not extract text from the uploaded file."

    upload_dir = Path(authenticated_context["tmp_path"])
    assert list(upload_dir.iterdir()) == []
