from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CodingSessionStartRequest(BaseModel):
    """Request payload to start a coding interview session."""

    resume_id: UUID
    job_id: UUID
    difficulty: Literal["medium", "hard"]


class CodingProblemOut(BaseModel):
    """Serialized coding problem shown to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    difficulty: str
    category: str | None
    function_signature: dict[str, Any]
    starter_code: dict[str, Any]
    constraints: str | None


class TestCaseOut(BaseModel):
    """Serialized test case payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    input_data: str
    expected_output: str
    order_index: int | None


class CodingSessionStartResponse(BaseModel):
    """Response payload for coding session start."""

    session_id: UUID
    problem: CodingProblemOut
    sample_test_cases: list[TestCaseOut]


class CodeRunRequest(BaseModel):
    """Request payload to run code against sample tests."""

    session_id: UUID
    problem_id: UUID
    language: Literal["python", "javascript", "java", "cpp"]
    source_code: str


class TestResultOut(BaseModel):
    """Single test case execution result."""

    test_case_id: UUID
    passed: bool
    actual_output: str | None
    expected_output: str | None
    runtime_ms: int | None
    error_output: str | None
    status: str


class CodeRunResponse(BaseModel):
    """Response payload for sample test run."""

    submission_id: UUID
    results: list[TestResultOut]


class CodeEvaluationOut(BaseModel):
    """Structured coding submission evaluation."""

    tests_passed: int
    tests_total: int
    pass_rate: float = Field(ge=0.0, le=1.0)
    correctness_score: float
    efficiency_score: float
    code_quality_score: float
    problem_solving_score: float
    overall_score: float
    feedback_text: str
    strengths: list[str]
    improvements: list[str]
    expected_solution: str
    complexity_analysis: str


class CodeSubmitResponse(BaseModel):
    """Response payload for full submission and evaluation."""

    submission_id: UUID
    results: list[TestResultOut]
    evaluation: CodeEvaluationOut
