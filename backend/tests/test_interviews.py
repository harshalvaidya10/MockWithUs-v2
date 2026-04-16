from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user, get_db
from app.main import app
from app.models.interview import InterviewSession
from app.models.job import JobDescription
from app.models.question import Question
from app.models.resume import Resume
from app.models.user import User
from app.models.answer import Answer


client = TestClient(app)


class FakeSession:
    """Minimal DB-session substitute for interview router integration tests."""

    def __init__(self) -> None:
        self._store: list[object] = []
        self.commit_called = False
        self.commit_count = 0

    def add(self, obj: object) -> None:
        self._store.append(obj)

    def commit(self) -> None:
        self.commit_called = True
        self.commit_count += 1

    def flush(self) -> None:
        for obj in self._store:
            if getattr(obj, "id", None) is None:
                object.__setattr__(obj, "id", uuid4())
            if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
                object.__setattr__(obj, "created_at", datetime.now(timezone.utc))

    def refresh(self, obj: object) -> None:
        if getattr(obj, "id", None) is None:
            object.__setattr__(obj, "id", uuid4())
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            object.__setattr__(obj, "created_at", datetime.now(timezone.utc))

    def rollback(self) -> None:
        return

    def query(self, model: type) -> _FakeQuery:
        return _FakeQuery(self._store, model)


class _FakeQuery:
    """Minimal SQLAlchemy-like query chain backed by an in-memory list."""

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

    def order_by(self, *columns: object) -> _FakeQuery:
        if not columns:
            return self

        first_column = columns[0]
        attr_name = getattr(first_column, "name", None)
        if attr_name is None:
            attr_name = getattr(getattr(first_column, "element", None), "name", None)

        if attr_name is not None:
            reverse = bool(getattr(first_column, "modifier", None))
            self._results.sort(key=lambda obj: getattr(obj, attr_name, None), reverse=reverse)
        return self

    def first(self) -> object | None:
        return self._results[0] if self._results else None

    def all(self) -> list[object]:
        return list(self._results)


def _make_user() -> User:
    user = User(email=f"user_{uuid4().hex[:8]}@example.com", password_hash="hashed")
    user.id = uuid4()
    return user


def _seed_resume(db: FakeSession, *, user_id: UUID) -> Resume:
    resume = Resume(
        user_id=user_id,
        filename="resume.pdf",
        stored_filename="stored-resume.pdf",
        parsed_text=(
            "Senior backend engineer with FastAPI, PostgreSQL, and Docker experience. "
            "Led API reliability improvements and performance optimizations."
        ),
        skills=["python", "fastapi", "postgresql", "docker"],
        embedding=json.dumps([1.0, 0.0, 0.0]),
    )
    resume.id = uuid4()
    resume.created_at = datetime.now(timezone.utc)
    db.add(resume)
    return resume


def _seed_job(db: FakeSession, *, user_id: UUID) -> JobDescription:
    job = JobDescription(
        user_id=user_id,
        title="Backend Engineer",
        company="Acme",
        content=(
            "Looking for a backend engineer with strong Python, FastAPI, PostgreSQL, "
            "and API performance tuning experience."
        ),
        keywords=["python", "fastapi", "postgresql"],
        required_skills=["python", "fastapi", "postgresql", "system design"],
        embedding=json.dumps([1.0, 0.0, 0.0]),
    )
    job.id = uuid4()
    job.created_at = datetime.now(timezone.utc)
    db.add(job)
    return job


def _seed_session_with_questions(
    db: FakeSession,
    *,
    user_id: UUID,
    resume_id: UUID,
    job_id: UUID,
) -> tuple[InterviewSession, list[Question]]:
    session = InterviewSession(
        user_id=user_id,
        resume_id=resume_id,
        job_id=job_id,
        match_score=0.75,
        match_summary="Strong FastAPI alignment with minor system-design gap.",
        status="ready",
    )
    session.id = uuid4()
    session.created_at = datetime.now(timezone.utc)
    db.add(session)

    categories = [
        "technical",
        "technical",
        "technical",
        "behavioral",
        "behavioral",
        "behavioral",
        "resume_based",
        "resume_based",
    ]
    questions: list[Question] = []
    for index, category in enumerate(categories, start=1):
        question = Question(
            session_id=session.id,
            question_text=f"Question {index}",
            category=category,
            rationale=f"Rationale {index}",
            order_index=index,
        )
        question.id = uuid4()
        question.created_at = datetime.now(timezone.utc)
        db.add(question)
        questions.append(question)

    return session, questions


def _seed_answers(
    db: FakeSession,
    *,
    session_id: UUID,
    question_ids: list[UUID],
) -> list[Answer]:
    answers: list[Answer] = []
    for question_id in question_ids:
        answer = Answer(
            session_id=session_id,
            question_id=question_id,
            answer_text="sample answer",
            transcript_text="sample answer",
            audio_file_path=None,
        )
        answer.id = uuid4()
        answer.created_at = datetime.now(timezone.utc)
        db.add(answer)
        answers.append(answer)
    return answers


@pytest.fixture()
def auth_context():
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


def test_start_interview_generates_and_persists_questions(auth_context: dict) -> None:
    """POST /interviews/start should create a session and persist generated questions."""
    fake_db = auth_context["db"]
    user = auth_context["user"]

    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    resume = _seed_resume(fake_db, user_id=user.id)
    job = _seed_job(fake_db, user_id=user.id)

    llm_output = json.dumps(
        [
            {
                "question_text": "How would you optimize an N+1 query issue in an API?",
                "category": "technical",
                "rationale": "Targets backend performance and data-access depth.",
            },
            {
                "question_text": "Explain your approach to database migration safety in production.",
                "category": "technical",
                "rationale": "Checks production readiness and risk management.",
            },
            {
                "question_text": "How do you instrument and monitor critical API endpoints?",
                "category": "technical",
                "rationale": "Evaluates observability practices.",
            },
            {
                "question_text": "Tell me about a time you handled conflicting priorities.",
                "category": "behavioral",
                "rationale": "Assesses prioritization under pressure.",
            },
            {
                "question_text": "Describe a difficult technical disagreement and how it ended.",
                "category": "behavioral",
                "rationale": "Assesses collaboration and conflict resolution.",
            },
            {
                "question_text": "Give an example of when you improved team execution quality.",
                "category": "behavioral",
                "rationale": "Assesses leadership and process impact.",
            },
            {
                "question_text": "From your resume, which project best demonstrates FastAPI expertise?",
                "category": "resume_based",
                "rationale": "Maps resume evidence to role requirements.",
            },
            {
                "question_text": "Which achievement on your resume best reflects production ownership?",
                "category": "resume_based",
                "rationale": "Connects past impact to expected responsibilities.",
            },
        ]
    )

    with patch("app.services.question_generator.call_llm") as mock_call_llm:
        mock_call_llm.return_value = llm_output
        response = client.post(
            "/interviews/start",
            json={"resume_id": str(resume.id), "job_id": str(job.id)},
        )

    assert response.status_code == 201
    payload = response.json()

    assert "session_id" in payload
    assert payload["match_score"] == pytest.approx(1.0, abs=1e-6)
    assert isinstance(payload["match_summary"], str) and payload["match_summary"]
    assert len(payload["questions"]) == 8

    question_categories = [question["category"] for question in payload["questions"]]
    assert question_categories.count("technical") == 3
    assert question_categories.count("behavioral") == 3
    assert question_categories.count("resume_based") == 2

    session_id = UUID(payload["session_id"])
    persisted_sessions = fake_db.query(InterviewSession).filter(InterviewSession.id == session_id).all()
    persisted_questions = fake_db.query(Question).filter(Question.session_id == session_id).all()

    assert len(persisted_sessions) == 1
    assert len(persisted_questions) == 8
    assert sorted(question.order_index for question in persisted_questions) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert fake_db.commit_count == 1


def test_get_interview_session_returns_saved_questions(auth_context: dict) -> None:
    """GET /interviews/{session_id} should return saved interview metadata and questions."""
    fake_db = auth_context["db"]
    user = auth_context["user"]

    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    resume = _seed_resume(fake_db, user_id=user.id)
    job = _seed_job(fake_db, user_id=user.id)
    session, questions = _seed_session_with_questions(
        fake_db,
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
    )

    response = client.get(f"/interviews/{session.id}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["session_id"] == str(session.id)
    assert payload["match_score"] == pytest.approx(0.75, abs=1e-6)
    assert payload["match_summary"] == "Strong FastAPI alignment with minor system-design gap."

    returned_questions = payload["questions"]
    assert len(returned_questions) == 8
    assert [item["order_index"] for item in returned_questions] == list(range(1, 9))
    assert [item["question_text"] for item in returned_questions] == [item.question_text for item in questions]


def test_get_interview_session_returns_404_for_missing_session(auth_context: dict) -> None:
    """GET /interviews/{session_id} should return 404 when session is missing."""
    _ = auth_context
    missing_session_id = uuid4()

    response = client.get(f"/interviews/{missing_session_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Interview session not found."


def test_list_interview_sessions_returns_history_with_progress(auth_context: dict) -> None:
    """GET /interviews should return previous sessions with answered/question counts."""
    fake_db = auth_context["db"]
    user = auth_context["user"]

    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    resume = _seed_resume(fake_db, user_id=user.id)
    job = _seed_job(fake_db, user_id=user.id)

    first_session, first_questions = _seed_session_with_questions(
        fake_db,
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
    )
    first_session.status = "completed"
    first_session.completed_at = datetime.now(timezone.utc)
    _seed_answers(
        fake_db,
        session_id=first_session.id,
        question_ids=[question.id for question in first_questions],
    )

    second_session, second_questions = _seed_session_with_questions(
        fake_db,
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
    )
    second_session.status = "ready"
    _seed_answers(
        fake_db,
        session_id=second_session.id,
        question_ids=[question.id for question in second_questions[:3]],
    )

    response = client.get("/interviews")
    assert response.status_code == 200

    payload = response.json()
    sessions = payload["sessions"]
    assert len(sessions) == 2

    session_by_id = {item["session_id"]: item for item in sessions}

    completed_item = session_by_id[str(first_session.id)]
    assert completed_item["status"] == "completed"
    assert completed_item["question_count"] == 8
    assert completed_item["answered_count"] == 8
    assert completed_item["is_complete"] is True

    in_progress_item = session_by_id[str(second_session.id)]
    assert in_progress_item["status"] == "ready"
    assert in_progress_item["question_count"] == 8
    assert in_progress_item["answered_count"] == 3
    assert in_progress_item["is_complete"] is False
