from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user, get_db
from app.main import app
from app.models.job import JobDescription
from app.models.resume import Resume
from app.models.user import User
from app.routers import jobs as jobs_router


client = TestClient(app)

# A realistic JD that exceeds the 50-char min_length and mentions multiple real skills.
REALISTIC_JD = (
    "We are looking for a senior software engineer to join our platform team. "
    "The ideal candidate has strong experience with Python, FastAPI, and PostgreSQL. "
    "You will design and build scalable microservices deployed on AWS using Docker and Kubernetes. "
    "Experience with React and TypeScript for internal tooling is a plus. "
    "We follow agile and TDD practices and value clean API design."
)


# ---------------------------------------------------------------------------
# Minimal fake DB session — mirrors the pattern in tests/test_resume.py
# ---------------------------------------------------------------------------

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
            object.__setattr__(obj, "id", uuid4())
        if getattr(obj, "created_at", None) is None:
            object.__setattr__(obj, "created_at", datetime.now(timezone.utc))

    def rollback(self) -> None:
        return

    def query(self, model: type) -> _FakeQuery:
        return _FakeQuery(self._store, model)


class _FakeQuery:
    """Minimal SQLAlchemy query chain backed by an in-memory list."""

    def __init__(self, store: list[object], model: type) -> None:
        self._results: list[object] = [o for o in store if isinstance(o, model)]

    @staticmethod
    def _matches_condition(obj: object, condition: object) -> bool:
        """Evaluate simple SQLAlchemy equality conditions against in-memory objects."""
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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_user() -> User:
    """Return a transient User with a stable UUID (not persisted to any DB)."""
    user = User(email=f"user_{uuid4().hex[:8]}@example.com", password_hash="hashed")
    user.id = uuid4()
    return user


def _seed_job(
    db: FakeSession,
    *,
    user_id,
    required_skills: list[str],
    embedding: list[float] | None,
    title: str = "Backend Engineer",
) -> JobDescription:
    """Insert a deterministic in-memory JobDescription for matcher endpoint tests."""
    job = JobDescription(
        user_id=user_id,
        title=title,
        company="Acme",
        content=REALISTIC_JD,
        keywords=["python", "fastapi", "docker"],
        required_skills=required_skills,
        embedding=None if embedding is None else json.dumps(embedding),
    )
    job.id = uuid4()
    job.created_at = datetime.now(timezone.utc)
    db.add(job)
    return job


def _seed_resume(
    db: FakeSession,
    *,
    user_id,
    skills: list[str],
    embedding: list[float] | None,
) -> Resume:
    """Insert a deterministic in-memory Resume for matcher endpoint tests."""
    formatted_skills = ", ".join(skills) if skills else "Python, Docker"
    resume = Resume(
        user_id=user_id,
        filename="resume.pdf",
        stored_filename="stored-resume.pdf",
        parsed_text=(
            "Jane Doe\n"
            "jane.doe@example.com | +1 (415) 555-0199\n"
            "Professional Summary\n"
            "Backend engineer with production API experience.\n"
            "Work Experience\n"
            "Software Engineer, Acme Corp (2022 - 2025)\n"
            f"Skills: {formatted_skills}\n"
            "Education\n"
            "B.Tech in Computer Science, 2021\n"
        ),
        skills=skills,
        embedding=None if embedding is None else json.dumps(embedding),
    )
    resume.id = uuid4()
    resume.created_at = datetime.now(timezone.utc)
    db.add(resume)
    return resume


@pytest.fixture()
def auth_context():
    """Override auth + DB dependencies for isolated job endpoint tests."""
    fake_db = FakeSession()
    user = _make_user()

    def override_get_db():
        yield fake_db

    def override_get_current_user() -> User:
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    yield {"db": fake_db, "user": user}

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Authentication guard tests
# ---------------------------------------------------------------------------

def test_create_job_requires_auth() -> None:
    """POST /jobs/ without a token must return 401."""
    response = client.post("/jobs/", json={"content": REALISTIC_JD})
    assert response.status_code == 401


def test_list_jobs_requires_auth() -> None:
    """GET /jobs/ without a token must return 401."""
    response = client.get("/jobs/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Input validation tests (Pydantic rejects before the handler runs → 422)
# ---------------------------------------------------------------------------

def test_create_job_empty_content_rejected(auth_context: dict) -> None:
    """Empty content string must be rejected by Pydantic min_length constraint."""
    response = client.post("/jobs/", json={"content": ""})
    assert response.status_code == 422


def test_create_job_too_short_rejected(auth_context: dict) -> None:
    """Content shorter than 50 characters must be rejected by Pydantic."""
    response = client.post("/jobs/", json={"content": "Too short."})
    assert response.status_code == 422


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
    """Condition evaluation errors must not be silently treated as matches."""

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


# ---------------------------------------------------------------------------
# Happy-path creation tests
# ---------------------------------------------------------------------------

def test_create_job_success(
    auth_context: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /jobs/ with valid input must return 201 with the expected response shape."""
    monkeypatch.setattr(jobs_router, "generate_embedding", lambda _: [0.1, 0.2, 0.3])

    response = client.post(
        "/jobs/",
        json={"title": "Backend Engineer", "company": "Acme Corp", "content": REALISTIC_JD},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Backend Engineer"
    assert payload["company"] == "Acme Corp"
    assert "id" in payload
    assert "created_at" in payload
    assert "required_skills" in payload
    assert "keywords" in payload
    # JobOut must NOT expose content — list responses stay lean
    assert "content" not in payload


def test_create_job_extracts_skills(
    auth_context: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skills mentioned in REALISTIC_JD must appear in required_skills."""
    monkeypatch.setattr(jobs_router, "generate_embedding", lambda _: [0.0] * 384)

    response = client.post("/jobs/", json={"content": REALISTIC_JD})

    assert response.status_code == 201
    skills = response.json()["required_skills"]
    for expected_skill in ("python", "fastapi", "postgresql", "docker", "kubernetes", "react", "typescript"):
        assert expected_skill in skills, f"Expected '{expected_skill}' in required_skills but got: {skills}"


def test_create_job_does_not_treat_plain_go_verb_as_go_skill(
    auth_context: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plain English verb usage of 'go' must not produce Go language skill."""
    monkeypatch.setattr(jobs_router, "generate_embedding", lambda _: [0.0] * 384)

    jd_with_go_verb = (
        "We need engineers who can go deep into systems and go fast in execution. "
        "Strong Python and Docker experience required for backend delivery."
    )
    response = client.post("/jobs/", json={"content": jd_with_go_verb})

    assert response.status_code == 201
    skills = response.json()["required_skills"]
    assert "python" in skills
    assert "docker" in skills
    assert "go" not in skills


# ---------------------------------------------------------------------------
# List endpoint tests
# ---------------------------------------------------------------------------

def test_list_jobs_returns_only_own_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each user must only see their own job descriptions — no cross-user leakage."""
    monkeypatch.setattr(jobs_router, "generate_embedding", lambda _: [0.0] * 384)

    user_a = _make_user()
    user_b = _make_user()
    shared_db = FakeSession()

    def shared_db_override():
        yield shared_db

    app.dependency_overrides[get_db] = shared_db_override
    app.dependency_overrides[get_current_user] = lambda: user_a
    create_a = client.post("/jobs/", json={"content": REALISTIC_JD})
    assert create_a.status_code == 201

    # User B creates a job in the same DB; ownership must come from user_id filtering.
    app.dependency_overrides[get_current_user] = lambda: user_b
    create_b = client.post("/jobs/", json={"content": REALISTIC_JD})
    assert create_b.status_code == 201

    # Each user's list must only contain their own job
    app.dependency_overrides[get_current_user] = lambda: user_a
    ids_a = {j["id"] for j in client.get("/jobs/").json()}

    app.dependency_overrides[get_current_user] = lambda: user_b
    ids_b = {j["id"] for j in client.get("/jobs/").json()}

    assert len(ids_a) == 1
    assert len(ids_b) == 1
    assert ids_a.isdisjoint(ids_b), "Users share job IDs — ownership isolation broken."

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Detail endpoint tests
# ---------------------------------------------------------------------------

def test_get_job_by_id_includes_content(
    auth_context: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /jobs/{id} must include the full content field absent from JobOut."""
    monkeypatch.setattr(jobs_router, "generate_embedding", lambda _: [0.0] * 384)

    create_resp = client.post("/jobs/", json={"content": REALISTIC_JD})
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    detail_resp = client.get(f"/jobs/{job_id}")
    assert detail_resp.status_code == 200
    assert "content" in detail_resp.json()
    assert detail_resp.json()["content"]  # must be non-empty


def test_get_job_not_found(auth_context: dict) -> None:
    """GET /jobs/{nonexistent_uuid} must return 404."""
    response = client.get(f"/jobs/{uuid4()}")
    assert response.status_code == 404


def test_get_job_of_other_user_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fetching another user's job must return 404, not 403 (existence must not leak)."""
    monkeypatch.setattr(jobs_router, "generate_embedding", lambda _: [0.0] * 384)

    user_a = _make_user()
    user_b = _make_user()
    shared_db = FakeSession()

    def shared_db_override():
        yield shared_db

    # User A creates a job
    app.dependency_overrides[get_db] = shared_db_override
    app.dependency_overrides[get_current_user] = lambda: user_a
    create_resp = client.post("/jobs/", json={"content": REALISTIC_JD})
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    # User B attempts to fetch user A's job ID from the same DB.
    # Access must still be denied via user_id ownership filtering.
    app.dependency_overrides[get_current_user] = lambda: user_b
    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 404, (
        "Expected 404 (not 403) — returning 403 would leak that the resource exists."
    )

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Match endpoint tests
# ---------------------------------------------------------------------------

def test_match_endpoint_returns_score_and_skill_gaps(auth_context: dict) -> None:
    """GET /jobs/{id}/match should return score + gaps for owned resume/job."""
    fake_db = auth_context["db"]
    user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    job = _seed_job(
        fake_db,
        user_id=user.id,
        required_skills=["python", "docker", "kubernetes"],
        embedding=[1.0, 0.0, 0.0],
    )
    resume = _seed_resume(
        fake_db,
        user_id=user.id,
        skills=["Python", "Docker", "FastAPI"],
        embedding=[1.0, 0.0, 0.0],
    )

    response = client.get(f"/jobs/{job.id}/match", params={"resume_id": str(resume.id)})
    assert response.status_code == 200

    payload = response.json()
    assert payload["job_id"] == str(job.id)
    assert payload["resume_id"] == str(resume.id)
    assert payload["match_score"] == pytest.approx(1.0, abs=1e-6)
    assert set(payload["skill_gaps"]["matched"]) == {"python", "docker"}
    assert payload["skill_gaps"]["missing"] == ["kubernetes"]
    assert payload["skill_gaps"]["coverage"] == pytest.approx(2 / 3, rel=1e-6)
    assert "Strong match" in payload["match_summary"]


def test_match_endpoint_falls_back_to_coverage_without_embeddings(auth_context: dict) -> None:
    """If embeddings are absent, match score should equal skill coverage."""
    fake_db = auth_context["db"]
    user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    job = _seed_job(
        fake_db,
        user_id=user.id,
        required_skills=["python", "docker", "kubernetes"],
        embedding=None,
    )
    resume = _seed_resume(
        fake_db,
        user_id=user.id,
        skills=["python"],
        embedding=None,
    )

    response = client.get(f"/jobs/{job.id}/match", params={"resume_id": str(resume.id)})
    assert response.status_code == 200
    payload = response.json()
    assert payload["match_score"] == pytest.approx(1 / 3, rel=1e-6)
    assert payload["skill_gaps"]["coverage"] == pytest.approx(1 / 3, rel=1e-6)


def test_match_endpoint_returns_404_for_unknown_job(auth_context: dict) -> None:
    """Matching with a non-existent job id must return 404."""
    fake_db = auth_context["db"]
    user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    resume = _seed_resume(
        fake_db,
        user_id=user.id,
        skills=["python"],
        embedding=[1.0, 0.0],
    )

    response = client.get(f"/jobs/{uuid4()}/match", params={"resume_id": str(resume.id)})
    assert response.status_code == 404
    assert response.json()["detail"] == "Job description not found."


def test_match_endpoint_returns_404_for_unknown_resume(auth_context: dict) -> None:
    """Matching with a non-existent resume id must return 404."""
    fake_db = auth_context["db"]
    user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    job = _seed_job(
        fake_db,
        user_id=user.id,
        required_skills=["python"],
        embedding=[1.0, 0.0],
    )

    response = client.get(f"/jobs/{job.id}/match", params={"resume_id": str(uuid4())})
    assert response.status_code == 404
    assert response.json()["detail"] == "Resume not found."


def test_match_endpoint_rejects_non_resume_document(auth_context: dict) -> None:
    """Matching should fail when selected file content is not resume-like."""
    fake_db = auth_context["db"]
    user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    job = _seed_job(
        fake_db,
        user_id=user.id,
        required_skills=["python", "docker"],
        embedding=[1.0, 0.0],
    )
    resume = _seed_resume(
        fake_db,
        user_id=user.id,
        skills=["Python"],
        embedding=[1.0, 0.0],
    )
    resume.parsed_text = """
    Project Implementation Plan
    Timeline and Milestones
    Deliverables and stakeholder updates
    Risk mitigation and dependency tracking
    """

    response = client.get(f"/jobs/{job.id}/match", params={"resume_id": str(resume.id)})
    assert response.status_code == 400
    assert "does not appear to be a resume" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Embedding resilience test
# ---------------------------------------------------------------------------

def test_embedding_failure_is_nonfatal(
    auth_context: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crash in generate_embedding must not block a successful 201 response."""
    def raise_on_embed(_: str) -> list[float]:
        raise RuntimeError("Simulated GPU out-of-memory error")

    monkeypatch.setattr(jobs_router, "generate_embedding", raise_on_embed)

    response = client.post("/jobs/", json={"content": REALISTIC_JD})
    assert response.status_code == 201
    # The job was persisted without an embedding
    assert response.json()["id"]
