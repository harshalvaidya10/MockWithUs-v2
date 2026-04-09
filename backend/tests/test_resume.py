from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.security import get_current_user, get_db
from app.main import app
from app.models.resume import Resume
from app.models.user import User
from app.routers import resumes as resumes_router
from app.services.resume_parser import (
    NON_RESUME_UPLOAD_MESSAGE,
    assess_resume_document,
    assess_resume_text,
    extract_skills,
    score_resume_likeness,
)


client = TestClient(app)


class FakeSession:
    """Minimal DB-session substitute for router tests."""

    def __init__(self) -> None:
        self.added_objects: list[object] = []
        self.commit_called = False
        self._store: list[object] = []

    def add(self, obj: object) -> None:
        self.added_objects.append(obj)
        self._store.append(obj)

    def commit(self) -> None:
        self.commit_called = True

    def refresh(self, obj: object) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)

    def rollback(self) -> None:
        return

    def delete(self, obj: object) -> None:
        if obj in self._store:
            self._store.remove(obj)
        if obj in self.added_objects:
            self.added_objects.remove(obj)

    def query(self, model: type) -> _FakeQuery:
        return _FakeQuery(self._store, model)


class _FakeQuery:
    """Minimal SQLAlchemy-like query chain backed by in-memory objects."""

    def __init__(self, store: list[object], model: type) -> None:
        self._results: list[object] = [obj for obj in store if isinstance(obj, model)]

    @staticmethod
    def _matches_condition(obj: object, condition: object) -> bool:
        left = getattr(condition, "left", None)
        right = getattr(condition, "right", None)
        operator = getattr(condition, "operator", None)
        attr_name = getattr(left, "key", None)

        if attr_name is None or operator is None:
            return False

        right_value = getattr(right, "value", right)
        try:
            return bool(operator(getattr(obj, attr_name), right_value))
        except Exception:
            return False

    def filter(self, *conditions: object) -> _FakeQuery:
        for condition in conditions:
            self._results = [obj for obj in self._results if self._matches_condition(obj, condition)]
        return self

    def order_by(self, *_args: object) -> _FakeQuery:
        return self

    def first(self) -> object | None:
        return self._results[0] if self._results else None

    def all(self) -> list[object]:
        return list(self._results)


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


def test_delete_requires_auth() -> None:
    """Ensure resume delete cannot be used anonymously."""
    response = client.delete(f"/resumes/{uuid4()}")
    assert response.status_code == 401


def test_fake_query_matches_condition_fails_closed_for_unsupported_expression() -> None:
    """Unsupported SQLAlchemy-like conditions must not match rows by default."""

    class _Row:
        def __init__(self) -> None:
            self.user_id = uuid4()

    query = _FakeQuery([_Row()], _Row)

    class _UnsupportedCondition:
        pass

    assert query.filter(_UnsupportedCondition()).all() == []


def test_fake_query_matches_condition_fails_closed_when_operator_raises() -> None:
    """Condition-evaluation errors must not be silently treated as matches."""

    class _Row:
        def __init__(self) -> None:
            self.user_id = uuid4()

    class _Left:
        key = "user_id"

    class _Right:
        value = uuid4()

    class _Condition:
        left = _Left()
        right = _Right()

        @staticmethod
        def operator(_lhs: object, _rhs: object) -> bool:
            raise RuntimeError("Simulated operator failure")

    query = _FakeQuery([_Row()], _Row)
    assert query.filter(_Condition()).all() == []


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
            "parsed_text": (
                "Jane Doe\n"
                "jane.doe@example.com | +1 (415) 555-0199\n"
                "Professional Summary\n"
                "Backend engineer with strong Python and FastAPI experience.\n"
                "Work Experience\n"
                "Software Engineer, Acme Corp (2022 - 2025)\n"
                "Skills: Python, FastAPI, PostgreSQL\n"
                "Education\n"
                "B.Tech in Computer Science, 2021\n"
            ),
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
    assert set(payload.keys()) == {"id", "filename", "skills", "created_at", "is_resume_like"}
    assert payload["filename"] == "resume.pdf"
    assert payload["skills"] == ["Python", "FastAPI", "PostgreSQL"]
    assert payload["is_resume_like"] is True

    fake_db = authenticated_context["db"]
    assert isinstance(fake_db, FakeSession)
    assert fake_db.commit_called
    assert len(fake_db.added_objects) == 1

    stored_resume = fake_db.added_objects[0]
    assert stored_resume.filename == "resume.pdf"
    assert stored_resume.stored_filename.endswith(".pdf")
    assert stored_resume.stored_filename != "resume.pdf"
    assert stored_resume.parsed_text.startswith("Jane Doe")

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


def test_assess_resume_text_accepts_resume_like_content() -> None:
    """Heuristic should accept standard resume structure and signals."""
    resume_text = """
    Jane Doe
    jane.doe@example.com | +1 (415) 555-0199 | https://linkedin.com/in/janedoe

    Professional Summary
    Backend engineer with 4 years of experience building APIs.

    Work Experience
    Software Engineer, Acme Corp (2022 - 2025)
    - Built FastAPI services in Python and PostgreSQL.
    - Deployed workloads with Docker and AWS.

    Education
    B.Tech in Computer Science, 2021
    """

    is_resume_like, rejection_reason = assess_resume_text(resume_text)
    assert is_resume_like
    assert rejection_reason == ""

    check = score_resume_likeness(resume_text)
    assert check.is_likely_resume
    assert check.confidence >= 0.5
    assert check.resume_score > check.non_resume_score


def test_assess_resume_text_rejects_project_plan_content() -> None:
    """Heuristic should reject implementation plans uploaded as resumes."""
    plan_text = """
    Project Implementation Plan
    Timeline and Milestones
    Deliverables:
    - Finalize architecture roadmap
    - Sprint plan for stakeholder review
    - Risk mitigation and dependency tracking
    """

    is_resume_like, rejection_reason = assess_resume_text(plan_text)
    assert not is_resume_like
    assert rejection_reason == NON_RESUME_UPLOAD_MESSAGE

    check = score_resume_likeness(plan_text)
    assert not check.is_likely_resume
    assert check.rejection_reason == NON_RESUME_UPLOAD_MESSAGE


def test_assess_resume_document_rejects_suspicious_filename() -> None:
    """Filename heuristics should reject plan/spec files even with resume-like text."""
    resume_like_text = """
    Jane Doe
    jane.doe@example.com
    Professional Summary
    Software Engineer with Python and FastAPI experience.
    Work Experience
    Acme Corp (2022-2025)
    """

    is_resume_like, rejection_reason = assess_resume_document(
        resume_like_text,
        "MockWithUs_Implementation_Plan.docx",
    )
    assert not is_resume_like
    assert rejection_reason == NON_RESUME_UPLOAD_MESSAGE


def test_assess_resume_document_accepts_resume_hint_with_underscores() -> None:
    """Underscore-separated 'resume' hint should prevent false suspicious-filename reject."""
    resume_like_text = """
    Jane Doe
    jane.doe@example.com | +1 (415) 555-0199
    Professional Summary
    Software Engineer with Python and FastAPI experience.
    Work Experience
    Software Engineer, Acme Corp (2022 - 2025)
    Skills: Python, FastAPI, PostgreSQL
    Education
    B.Tech in Computer Science, 2021
    """

    is_resume_like, rejection_reason = assess_resume_document(
        resume_like_text,
        "john_resume_implementation_plan_2026.pdf",
    )
    assert is_resume_like
    assert rejection_reason == ""


def test_upload_rejects_non_resume_text_document(
    authenticated_context: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upload endpoint should reject valid text that looks like a job description."""

    jd_like_text = """
    About the role
    We are looking for a Software Engineer to join our platform team.
    Responsibilities
    You will be responsible for building and scaling backend systems.
    Requirements
    3+ years of Python experience and strong SQL skills.
    Qualifications
    Strong communication and collaboration skills.
    Preferred qualifications
    Experience with cloud infrastructure.
    """

    monkeypatch.setattr(
        resumes_router,
        "parse_resume_file",
        lambda _: {
            "parsed_text": jd_like_text,
            "skills": ["Python", "SQL"],
        },
    )

    response = client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", b"%PDF-1.4 mocked content", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == NON_RESUME_UPLOAD_MESSAGE


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


def test_list_resumes_returns_uploaded_resumes(
    authenticated_context: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure GET /resumes/ returns resumes uploaded by the authenticated user."""

    monkeypatch.setattr(
        resumes_router,
        "parse_resume_file",
        lambda _: {
            "parsed_text": (
                "John Doe\n"
                "john@example.com | +1 (415) 555-0177\n"
                "Professional Summary\n"
                "Backend engineer with API development experience.\n"
                "Work Experience\n"
                "Software Engineer, Example Corp (2022 - 2025)\n"
                "Skills: Python, FastAPI\n"
                "Education\n"
                "B.E. Computer Science, 2021\n"
            ),
            "skills": ["Python", "FastAPI"],
        },
    )
    monkeypatch.setattr(
        resumes_router,
        "generate_embedding",
        lambda _: [0.1, 0.2, 0.3],
    )

    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", b"%PDF-1.4 mocked content", "application/pdf")},
    )
    assert upload_response.status_code == 201
    uploaded_resume = upload_response.json()

    list_response = client.get("/resumes/")
    assert list_response.status_code == 200

    payload = list_response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == uploaded_resume["id"]
    assert payload[0]["filename"] == "resume.pdf"
    assert payload[0]["skills"] == ["Python", "FastAPI"]
    assert payload[0]["is_resume_like"] is True


def test_list_resumes_includes_legacy_non_resume_documents_with_status_flag(
    authenticated_context: dict[str, object],
) -> None:
    """GET /resumes/ should include all docs and flag non-resume-like uploads."""
    fake_db = authenticated_context["db"]
    user = authenticated_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    valid_resume = Resume(
        user_id=user.id,
        filename="resume.pdf",
        stored_filename="resume-stored.pdf",
        parsed_text=(
            "John Doe\njohn@example.com\nProfessional Summary\nWork Experience\n"
            "Software Engineer 2022\nSkills: Python, FastAPI, Docker"
        ),
        skills=["Python", "FastAPI", "Docker"],
        embedding=None,
    )
    valid_resume.id = uuid4()
    valid_resume.created_at = datetime.now(timezone.utc)
    fake_db.add(valid_resume)

    plan_doc = Resume(
        user_id=user.id,
        filename="implementation_plan.docx",
        stored_filename="plan-stored.docx",
        parsed_text=(
            "Project Implementation Plan\nTimeline\nMilestones\nDeliverables\n"
            "Stakeholder alignment and risk mitigation"
        ),
        skills=["Python"],
        embedding=None,
    )
    plan_doc.id = uuid4()
    plan_doc.created_at = datetime.now(timezone.utc)
    fake_db.add(plan_doc)

    list_response = client.get("/resumes/")
    assert list_response.status_code == 200
    payload = list_response.json()

    assert len(payload) == 2

    by_id = {item["id"]: item for item in payload}
    assert by_id[str(valid_resume.id)]["filename"] == "resume.pdf"
    assert by_id[str(valid_resume.id)]["is_resume_like"] is True
    assert by_id[str(plan_doc.id)]["filename"] == "implementation_plan.docx"
    assert by_id[str(plan_doc.id)]["is_resume_like"] is False


def test_delete_resume_success_removes_record_and_file(
    authenticated_context: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /resumes/{id} should remove owned resume and stored upload file."""
    monkeypatch.setattr(
        resumes_router,
        "parse_resume_file",
        lambda _: {
            "parsed_text": (
                "Jane Doe\n"
                "jane@example.com | +1 (415) 555-0199\n"
                "Professional Summary\n"
                "Software engineer.\n"
                "Work Experience\n"
                "Acme Corp (2022 - 2025)\n"
                "Skills: Python, FastAPI\n"
                "Education\n"
                "B.Tech, 2021\n"
            ),
            "skills": ["Python", "FastAPI"],
        },
    )
    monkeypatch.setattr(resumes_router, "generate_embedding", lambda _: [0.1, 0.2, 0.3])

    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", b"%PDF-1.4 mocked content", "application/pdf")},
    )
    assert upload_response.status_code == 201
    resume_id = upload_response.json()["id"]

    fake_db = authenticated_context["db"]
    assert isinstance(fake_db, FakeSession)
    assert len(fake_db.added_objects) == 1
    stored_resume = fake_db.added_objects[0]
    stored_file = Path(authenticated_context["tmp_path"]) / stored_resume.stored_filename
    assert stored_file.exists()

    delete_response = client.delete(f"/resumes/{resume_id}")
    assert delete_response.status_code == 204

    list_response = client.get("/resumes/")
    assert list_response.status_code == 200
    assert list_response.json() == []
    assert not stored_file.exists()


def test_delete_resume_not_found(authenticated_context: dict[str, object]) -> None:
    """Deleting a missing resume should return 404."""
    response = client.delete(f"/resumes/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Resume not found."
