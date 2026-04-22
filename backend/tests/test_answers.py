from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import app.services.answer_service as answer_service_module
from app.core.security import get_current_user, get_db
from app.main import app
from app.models.answer import Answer
from app.models.interview import InterviewSession
from app.models.question import Question
from app.models.user import User


client = TestClient(app)


class FakeSession:
    """In-memory DB-session substitute used by router tests."""

    def __init__(self) -> None:
        self._store: list[object] = []

    def add(self, obj: object) -> None:
        self._store.append(obj)

    def commit(self) -> None:
        return

    def rollback(self) -> None:
        return

    def refresh(self, obj: object) -> None:
        if getattr(obj, "id", None) is None:
            object.__setattr__(obj, "id", uuid4())
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            object.__setattr__(obj, "created_at", datetime.now(timezone.utc))

    def query(self, model: type) -> _FakeQuery:
        return _FakeQuery(self._store, model)


class _FakeQuery:
    """Minimal SQLAlchemy-like query object for filters used by answer routes."""

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
            self._results.sort(key=lambda obj: getattr(obj, attr_name, None))
        return self

    def first(self) -> object | None:
        return self._results[0] if self._results else None

    def all(self) -> list[object]:
        return list(self._results)


def _make_user(*, email_prefix: str = "user") -> User:
    user = User(email=f"{email_prefix}_{uuid4().hex[:8]}@example.com", password_hash="hashed")
    user.id = uuid4()
    return user


def _seed_session(db: FakeSession, *, user_id: UUID, status: str = "ready") -> InterviewSession:
    session = InterviewSession(
        user_id=user_id,
        resume_id=uuid4(),
        job_id=uuid4(),
        match_score=0.8,
        match_summary="Strong match for backend role.",
        status=status,
    )
    session.id = uuid4()
    session.created_at = datetime.now(timezone.utc)
    db.add(session)
    return session


def _seed_question(db: FakeSession, *, session_id: UUID, order_index: int) -> Question:
    question = Question(
        session_id=session_id,
        question_text=f"Question {order_index}",
        category="technical",
        rationale=f"Rationale {order_index}",
        order_index=order_index,
    )
    question.id = uuid4()
    question.created_at = datetime.now(timezone.utc)
    db.add(question)
    return question


@pytest.fixture()
def auth_context(tmp_path: Path):
    fake_db = FakeSession()
    user = _make_user()

    def override_get_db():
        yield fake_db

    def override_get_current_user() -> User:
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    original_settings = answer_service_module.settings
    original_schedule_background_evaluation = answer_service_module._schedule_background_evaluation
    answer_service_module.settings = SimpleNamespace(
        upload_dir=str(tmp_path / "uploads"),
        max_answer_audio_size_mb=10,
    )
    answer_service_module._schedule_background_evaluation = lambda **_: None

    yield {"db": fake_db, "user": user, "tmp_path": tmp_path}

    answer_service_module.settings = original_settings
    answer_service_module._schedule_background_evaluation = original_schedule_background_evaluation
    app.dependency_overrides.clear()


def test_submit_audio_answer_success_persists_transcript_and_audio_path(
    auth_context: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_db = auth_context["db"]
    user = auth_context["user"]
    tmp_path = auth_context["tmp_path"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    session = _seed_session(fake_db, user_id=user.id)
    question = _seed_question(fake_db, session_id=session.id, order_index=1)

    called_paths: list[str] = []

    def fake_transcribe(path: str) -> str:
        called_paths.append(path)
        return "This is my spoken answer."

    monkeypatch.setattr(answer_service_module, "transcribe_audio_file", fake_transcribe)

    response = client.post(
        "/answers/audio",
        data={"session_id": str(session.id), "question_id": str(question.id)},
        files={"audio": ("answer.webm", b"FAKEAUDIOBYTES", "audio/webm")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["session_id"] == str(session.id)
    assert payload["question_id"] == str(question.id)
    assert payload["transcript_text"] == "This is my spoken answer."

    saved_answers = fake_db.query(Answer).filter(Answer.session_id == session.id).all()
    assert len(saved_answers) == 1
    saved_answer = saved_answers[0]
    assert saved_answer.answer_text is None
    assert saved_answer.transcript_text == "This is my spoken answer."
    assert isinstance(saved_answer.audio_file_path, str)
    assert saved_answer.audio_file_path.startswith(f"answers/{session.id}/")

    assert len(called_paths) == 1
    expected_saved_path = Path(tmp_path / "uploads" / saved_answer.audio_file_path)
    assert called_paths[0] == str(expected_saved_path)
    assert expected_saved_path.exists()


def test_submit_audio_answer_rejects_foreign_session(auth_context: dict) -> None:
    fake_db = auth_context["db"]
    current_user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(current_user, User)

    other_user = _make_user(email_prefix="other")
    foreign_session = _seed_session(fake_db, user_id=other_user.id)
    foreign_question = _seed_question(fake_db, session_id=foreign_session.id, order_index=1)

    response = client.post(
        "/answers/audio",
        data={"session_id": str(foreign_session.id), "question_id": str(foreign_question.id)},
        files={"audio": ("answer.webm", b"FAKEAUDIOBYTES", "audio/webm")},
    )

    assert response.status_code == 403
    assert "access" in response.json()["detail"].lower()


def test_submit_audio_answer_rejects_question_session_mismatch(auth_context: dict) -> None:
    fake_db = auth_context["db"]
    user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    first_session = _seed_session(fake_db, user_id=user.id)
    second_session = _seed_session(fake_db, user_id=user.id)
    mismatched_question = _seed_question(fake_db, session_id=second_session.id, order_index=1)

    response = client.post(
        "/answers/audio",
        data={"session_id": str(first_session.id), "question_id": str(mismatched_question.id)},
        files={"audio": ("answer.webm", b"FAKEAUDIOBYTES", "audio/webm")},
    )

    assert response.status_code == 400
    assert "does not belong" in response.json()["detail"].lower()


def test_submit_audio_answer_requires_audio_file(auth_context: dict) -> None:
    fake_db = auth_context["db"]
    user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    session = _seed_session(fake_db, user_id=user.id)
    question = _seed_question(fake_db, session_id=session.id, order_index=1)

    response = client.post(
        "/answers/audio",
        data={"session_id": str(session.id), "question_id": str(question.id)},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Audio file is required."


def test_list_session_answers_supports_resume_progress(auth_context: dict) -> None:
    fake_db = auth_context["db"]
    user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    session = _seed_session(fake_db, user_id=user.id)
    q1 = _seed_question(fake_db, session_id=session.id, order_index=1)
    q2 = _seed_question(fake_db, session_id=session.id, order_index=2)
    q3 = _seed_question(fake_db, session_id=session.id, order_index=3)

    a1 = Answer(
        session_id=session.id,
        question_id=q1.id,
        answer_text="First answer",
        transcript_text="First answer",
        audio_file_path=f"answers/{session.id}/a1.webm",
    )
    a1.id = uuid4()
    a1.created_at = datetime.now(timezone.utc)
    fake_db.add(a1)

    a3 = Answer(
        session_id=session.id,
        question_id=q3.id,
        answer_text="Third answer",
        transcript_text="Third answer",
        audio_file_path=f"answers/{session.id}/a3.webm",
    )
    a3.id = uuid4()
    a3.created_at = datetime.now(timezone.utc)
    fake_db.add(a3)

    response = client.get(f"/answers/session/{session.id}")
    assert response.status_code == 200
    payload = response.json()

    answered_question_ids = {item["question_id"] for item in payload["answers"]}
    assert answered_question_ids == {str(q1.id), str(q3.id)}

    ordered_questions = [q1, q2, q3]
    first_unanswered = next((question for question in ordered_questions if str(question.id) not in answered_question_ids), None)
    assert first_unanswered is not None
    assert first_unanswered.id == q2.id


def test_submit_audio_answer_marks_session_completed_on_final_question(
    auth_context: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_db = auth_context["db"]
    user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    session = _seed_session(fake_db, user_id=user.id, status="ready")
    question = _seed_question(fake_db, session_id=session.id, order_index=1)

    monkeypatch.setattr(answer_service_module, "transcribe_audio_file", lambda _path: "final answer")
    scheduled_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        answer_service_module,
        "_schedule_background_evaluation",
        lambda **kwargs: scheduled_calls.append(kwargs),
    )

    response = client.post(
        "/answers/audio",
        data={"session_id": str(session.id), "question_id": str(question.id)},
        files={"audio": ("answer.webm", b"FAKEAUDIOBYTES", "audio/webm")},
    )

    assert response.status_code == 201
    assert session.status == "completed"
    assert session.completed_at is not None
    assert scheduled_calls == [{"user_id": user.id, "session_id": session.id}]


def test_submit_audio_answer_does_not_reschedule_when_already_completed(
    auth_context: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_db = auth_context["db"]
    user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    session = _seed_session(fake_db, user_id=user.id, status="completed")
    session.completed_at = datetime.now(timezone.utc)
    question = _seed_question(fake_db, session_id=session.id, order_index=1)

    monkeypatch.setattr(answer_service_module, "transcribe_audio_file", lambda _path: "final answer")
    scheduled_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        answer_service_module,
        "_schedule_background_evaluation",
        lambda **kwargs: scheduled_calls.append(kwargs),
    )

    response = client.post(
        "/answers/audio",
        data={"session_id": str(session.id), "question_id": str(question.id)},
        files={"audio": ("answer.webm", b"FAKEAUDIOBYTES", "audio/webm")},
    )

    assert response.status_code == 201
    assert scheduled_calls == []


def test_submit_audio_answer_scheduler_failure_does_not_fail_response(
    auth_context: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_db = auth_context["db"]
    user = auth_context["user"]
    assert isinstance(fake_db, FakeSession)
    assert isinstance(user, User)

    session = _seed_session(fake_db, user_id=user.id, status="ready")
    question = _seed_question(fake_db, session_id=session.id, order_index=1)

    monkeypatch.setattr(answer_service_module, "transcribe_audio_file", lambda _path: "final answer")

    def _raise_scheduler_error(**_: object) -> None:
        raise RuntimeError("scheduler failed")

    monkeypatch.setattr(answer_service_module, "_schedule_background_evaluation", _raise_scheduler_error)

    response = client.post(
        "/answers/audio",
        data={"session_id": str(session.id), "question_id": str(question.id)},
        files={"audio": ("answer.webm", b"FAKEAUDIOBYTES", "audio/webm")},
    )

    assert response.status_code == 201
    assert session.status == "completed"
    assert session.completed_at is not None

    saved_answers = fake_db.query(Answer).filter(Answer.session_id == session.id).all()
    assert len(saved_answers) == 1
