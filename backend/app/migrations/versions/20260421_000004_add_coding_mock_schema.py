"""add coding mock tables and interview session type"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260421_000004"
down_revision = "20260408_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create coding mock schema and session type column."""

    op.add_column(
        "interview_sessions",
        sa.Column("session_type", sa.String(length=20), nullable=False, server_default="interview"),
    )

    op.create_table(
        "coding_problems",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("function_signature", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("starter_code", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reference_solution", sa.Text(), nullable=False),
        sa.Column("constraints", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coding_problems_session_id", "coding_problems", ["session_id"], unique=False)

    op.create_table(
        "test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("problem_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_data", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_edge_case", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("order_index", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["problem_id"], ["coding_problems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_cases_problem_id", "test_cases", ["problem_id"], unique=False)

    op.create_table(
        "code_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("problem_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("submission_type", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["problem_id"], ["coding_problems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_code_submissions_problem_id", "code_submissions", ["problem_id"], unique=False)
    op.create_index("ix_code_submissions_session_id", "code_submissions", ["session_id"], unique=False)

    op.create_table(
        "test_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("actual_output", sa.Text(), nullable=True),
        sa.Column("expected_output", sa.Text(), nullable=True),
        sa.Column("runtime_ms", sa.Integer(), nullable=True),
        sa.Column("error_output", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["code_submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_results_submission_id", "test_results", ["submission_id"], unique=False)
    op.create_index("ix_test_results_test_case_id", "test_results", ["test_case_id"], unique=False)

    op.create_table(
        "code_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tests_passed", sa.Integer(), nullable=False),
        sa.Column("tests_total", sa.Integer(), nullable=False),
        sa.Column("pass_rate", sa.Float(), nullable=False),
        sa.Column("correctness_score", sa.Float(), nullable=True),
        sa.Column("efficiency_score", sa.Float(), nullable=True),
        sa.Column("code_quality_score", sa.Float(), nullable=True),
        sa.Column("problem_solving_score", sa.Float(), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("strengths", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("improvements", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("expected_solution", sa.Text(), nullable=True),
        sa.Column("complexity_analysis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["code_submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_code_evaluations_session_id", "code_evaluations", ["session_id"], unique=False)
    op.create_index("ix_code_evaluations_submission_id", "code_evaluations", ["submission_id"], unique=False)


def downgrade() -> None:
    """Drop coding mock schema changes."""

    op.drop_index("ix_code_evaluations_submission_id", table_name="code_evaluations")
    op.drop_index("ix_code_evaluations_session_id", table_name="code_evaluations")
    op.drop_table("code_evaluations")

    op.drop_index("ix_test_results_test_case_id", table_name="test_results")
    op.drop_index("ix_test_results_submission_id", table_name="test_results")
    op.drop_table("test_results")

    op.drop_index("ix_code_submissions_session_id", table_name="code_submissions")
    op.drop_index("ix_code_submissions_problem_id", table_name="code_submissions")
    op.drop_table("code_submissions")

    op.drop_index("ix_test_cases_problem_id", table_name="test_cases")
    op.drop_table("test_cases")

    op.drop_index("ix_coding_problems_session_id", table_name="coding_problems")
    op.drop_table("coding_problems")

    op.drop_column("interview_sessions", "session_type")
