from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, TypedDict
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.code_evaluation import CodeEvaluation
from app.models.code_submission import CodeSubmission
from app.models.coding_problem import CodingProblem
from app.models.interview import InterviewSession
from app.models.job import JobDescription
from app.models.resume import Resume
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.services.code_evaluator import evaluate_code_submission
from app.services.code_executor import execute_code_submission
from app.services.coding_problem_generator import generate_coding_problem_for_job


logger = logging.getLogger(__name__)


class CodingStartResult(TypedDict):
    session: InterviewSession
    problem: CodingProblem
    sample_test_cases: list[TestCase]


class CodingRunResult(TypedDict):
    submission: CodeSubmission
    results: list[TestResult]


class CodingSubmitResult(CodingRunResult):
    evaluation: CodeEvaluation


class CodingProblemPayload(TypedDict):
    problem: CodingProblem
    sample_test_cases: list[TestCase]


def _parse_json_value(raw_value: str) -> Any:
    try:
        return json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return raw_value


def _to_json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _get_resume_for_user(db: Session, *, user_id: UUID, resume_id: UUID) -> Resume | None:
    return (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user_id,
        )
        .first()
    )


def _get_job_for_user(db: Session, *, user_id: UUID, job_id: UUID) -> JobDescription | None:
    return (
        db.query(JobDescription)
        .filter(
            JobDescription.id == job_id,
            JobDescription.user_id == user_id,
        )
        .first()
    )


def _get_coding_session_for_user(db: Session, *, user_id: UUID, session_id: UUID) -> InterviewSession | None:
    return (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id,
            InterviewSession.user_id == user_id,
            InterviewSession.session_type == "coding",
        )
        .first()
    )


def _get_problem_for_session(db: Session, *, session_id: UUID) -> CodingProblem | None:
    return (
        db.query(CodingProblem)
        .filter(CodingProblem.session_id == session_id)
        .first()
    )


def _function_name_for_language(function_signature: dict[str, Any], language: str) -> str:
    signature = function_signature.get(language)
    if isinstance(signature, dict):
        name = str(signature.get("name", "")).strip()
        if name:
            return name
    return "solve"


async def start_coding_session(
    *,
    db: Session,
    user_id: UUID,
    resume_id: UUID,
    job_id: UUID,
    difficulty: str,
) -> CodingStartResult:
    """Create coding session, generate a coding problem, and persist sample + hidden test cases."""
    resume = _get_resume_for_user(db, user_id=user_id, resume_id=resume_id)
    if resume is None:
        raise NotFoundError("Resume not found.")

    job = _get_job_for_user(db, user_id=user_id, job_id=job_id)
    if job is None:
        raise NotFoundError("Job description not found.")

    generated = await generate_coding_problem_for_job(
        job_text=job.content or "",
        required_skills=job.required_skills or [],
        company_name=job.company,
        requested_difficulty=difficulty,
    )

    problem_payload = generated["problem"]
    test_case_payloads = generated["test_cases"]

    session = InterviewSession(
        user_id=user_id,
        resume_id=resume_id,
        job_id=job_id,
        status="ready",
        session_type="coding",
    )

    try:
        db.add(session)
        db.flush()

        problem = CodingProblem(
            session_id=session.id,
            title=problem_payload["title"],
            description=problem_payload["description"],
            difficulty=problem_payload["difficulty"],
            category=problem_payload["category"],
            function_signature=problem_payload["function_signature"],
            starter_code=problem_payload["starter_code"],
            reference_solution=problem_payload["reference_solution"],
            constraints=problem_payload["constraints"],
        )
        db.add(problem)
        db.flush()

        for case in test_case_payloads:
            db.add(
                TestCase(
                    problem_id=problem.id,
                    input_data=str(case["input_data"]),
                    expected_output=str(case["expected_output"]),
                    is_sample=bool(case["is_sample"]),
                    is_edge_case=bool(case["is_edge_case"]),
                    order_index=case["order_index"],
                )
            )

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to start coding session for user %s", user_id)
        raise RuntimeError("Could not start coding session.") from exc

    sample_cases = (
        db.query(TestCase)
        .filter(
            TestCase.problem_id == problem.id,
            TestCase.is_sample.is_(True),
        )
        .order_by(TestCase.order_index.asc())
        .all()
    )

    return CodingStartResult(
        session=session,
        problem=problem,
        sample_test_cases=sample_cases,
    )


def _serialize_test_results(rows: list[TestResult]) -> list[dict[str, Any]]:
    return [
        {
            "test_case_id": row.test_case_id,
            "passed": row.passed,
            "actual_output": row.actual_output,
            "expected_output": row.expected_output,
            "runtime_ms": row.runtime_ms,
            "error_output": row.error_output,
            "status": row.status,
        }
        for row in rows
    ]


async def run_coding_submission(
    *,
    db: Session,
    user_id: UUID,
    session_id: UUID,
    problem_id: UUID,
    language: str,
    source_code: str,
    submission_type: str,
) -> CodingRunResult | CodingSubmitResult:
    """Run or submit candidate code for a coding session."""
    session = _get_coding_session_for_user(db, user_id=user_id, session_id=session_id)
    if session is None:
        raise NotFoundError("Coding session not found.")

    problem = (
        db.query(CodingProblem)
        .filter(
            CodingProblem.id == problem_id,
            CodingProblem.session_id == session.id,
        )
        .first()
    )
    if problem is None:
        raise NotFoundError("Coding problem not found for this session.")

    normalized_language = language.strip().lower()
    if normalized_language not in {"python", "javascript", "java", "cpp"}:
        raise ValidationError("Unsupported programming language.")

    query = db.query(TestCase).filter(TestCase.problem_id == problem.id)
    if submission_type == "run":
        query = query.filter(TestCase.is_sample.is_(True))
    test_cases = query.order_by(TestCase.order_index.asc()).all()
    if not test_cases:
        raise ValidationError("No test cases found for this coding problem.")

    function_name = _function_name_for_language(problem.function_signature or {}, normalized_language)
    language_signature: dict[str, Any] = {}
    if isinstance(problem.function_signature, dict):
        selected_signature = problem.function_signature.get(normalized_language)
        if isinstance(selected_signature, dict):
            language_signature = selected_signature
    executable_cases = [
        {
            "id": case.id,
            "input_data": _parse_json_value(case.input_data),
            "expected_output": _parse_json_value(case.expected_output),
        }
        for case in test_cases
    ]

    execution_results = execute_code_submission(
        language=normalized_language,
        source_code=source_code,
        function_name=function_name,
        test_cases=executable_cases,
        language_signature=language_signature,
    )

    try:
        submission = CodeSubmission(
            session_id=session.id,
            problem_id=problem.id,
            language=normalized_language,
            source_code=source_code,
            submission_type=submission_type,
        )
        db.add(submission)
        db.flush()

        persisted_results: list[TestResult] = []
        for result in execution_results:
            persisted_row = TestResult(
                submission_id=submission.id,
                test_case_id=result["test_case_id"],
                passed=bool(result["passed"]),
                actual_output=result["actual_output"],
                expected_output=result["expected_output"],
                runtime_ms=result["runtime_ms"],
                error_output=result["error_output"],
                status=str(result["status"]),
            )
            db.add(persisted_row)
            persisted_results.append(persisted_row)

        if submission_type == "submit":
            evaluation_payload = await evaluate_code_submission(
                problem_title=problem.title,
                problem_description=problem.description,
                source_code=source_code,
                language=normalized_language,
                test_results=execution_results,
                reference_solution=problem.reference_solution,
            )
            evaluation = CodeEvaluation(
                submission_id=submission.id,
                session_id=session.id,
                tests_passed=evaluation_payload["tests_passed"],
                tests_total=evaluation_payload["tests_total"],
                pass_rate=evaluation_payload["pass_rate"],
                correctness_score=evaluation_payload["correctness_score"],
                efficiency_score=evaluation_payload["efficiency_score"],
                code_quality_score=evaluation_payload["code_quality_score"],
                problem_solving_score=evaluation_payload["problem_solving_score"],
                overall_score=evaluation_payload["overall_score"],
                feedback_text=evaluation_payload["feedback_text"],
                strengths=evaluation_payload["strengths"],
                improvements=evaluation_payload["improvements"],
                expected_solution=evaluation_payload["expected_solution"],
                complexity_analysis=evaluation_payload["complexity_analysis"],
            )
            db.add(evaluation)
            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Failed to persist coding %s submission for session %s and user %s",
            submission_type,
            session_id,
            user_id,
        )
        raise RuntimeError("Could not process coding submission.") from exc

    submission_results = (
        db.query(TestResult)
        .filter(TestResult.submission_id == submission.id)
        .order_by(TestResult.created_at.asc())
        .all()
    )

    if submission_type != "submit":
        return CodingRunResult(submission=submission, results=submission_results)

    evaluation_row = (
        db.query(CodeEvaluation)
        .filter(CodeEvaluation.submission_id == submission.id)
        .first()
    )
    if evaluation_row is None:
        raise RuntimeError("Coding evaluation was not created for the submitted solution.")
    return CodingSubmitResult(
        submission=submission,
        results=submission_results,
        evaluation=evaluation_row,
    )


def get_coding_problem_for_session(
    *,
    db: Session,
    user_id: UUID,
    session_id: UUID,
) -> CodingProblemPayload:
    """Return coding problem and sample test cases for a coding session."""
    session = _get_coding_session_for_user(db, user_id=user_id, session_id=session_id)
    if session is None:
        raise NotFoundError("Coding session not found.")

    problem = _get_problem_for_session(db, session_id=session.id)
    if problem is None:
        raise NotFoundError("Coding problem not found for this session.")

    sample_cases = (
        db.query(TestCase)
        .filter(
            TestCase.problem_id == problem.id,
            TestCase.is_sample.is_(True),
        )
        .order_by(TestCase.order_index.asc())
        .all()
    )
    return CodingProblemPayload(problem=problem, sample_test_cases=sample_cases)


def get_latest_coding_results_for_session(
    *,
    db: Session,
    user_id: UUID,
    session_id: UUID,
) -> CodingSubmitResult:
    """Return latest submit results + evaluation for a coding session."""
    session = _get_coding_session_for_user(db, user_id=user_id, session_id=session_id)
    if session is None:
        raise NotFoundError("Coding session not found.")

    submission = (
        db.query(CodeSubmission)
        .filter(
            CodeSubmission.session_id == session.id,
            CodeSubmission.submission_type == "submit",
        )
        .order_by(CodeSubmission.created_at.desc())
        .first()
    )
    if submission is None:
        raise NotFoundError("Coding solution has not been submitted yet.")

    results = (
        db.query(TestResult)
        .filter(TestResult.submission_id == submission.id)
        .order_by(TestResult.created_at.asc())
        .all()
    )
    evaluation = (
        db.query(CodeEvaluation)
        .filter(CodeEvaluation.submission_id == submission.id)
        .first()
    )
    if evaluation is None:
        raise NotFoundError("Coding evaluation not found for this submission.")

    return CodingSubmitResult(
        submission=submission,
        results=results,
        evaluation=evaluation,
    )


def serialize_run_response(result: CodingRunResult) -> dict[str, Any]:
    return {
        "submission_id": result["submission"].id,
        "results": _serialize_test_results(result["results"]),
    }


def serialize_submit_response(result: CodingSubmitResult) -> dict[str, Any]:
    evaluation = result["evaluation"]
    return {
        "submission_id": result["submission"].id,
        "results": _serialize_test_results(result["results"]),
        "evaluation": {
            "tests_passed": evaluation.tests_passed,
            "tests_total": evaluation.tests_total,
            "pass_rate": evaluation.pass_rate,
            "correctness_score": evaluation.correctness_score,
            "efficiency_score": evaluation.efficiency_score,
            "code_quality_score": evaluation.code_quality_score,
            "problem_solving_score": evaluation.problem_solving_score,
            "overall_score": evaluation.overall_score,
            "feedback_text": evaluation.feedback_text,
            "strengths": evaluation.strengths,
            "improvements": evaluation.improvements,
            "expected_solution": evaluation.expected_solution,
            "complexity_analysis": evaluation.complexity_analysis,
        },
    }
