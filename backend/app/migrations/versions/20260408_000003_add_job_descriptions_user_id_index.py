"""add user_id index to job_descriptions"""

from __future__ import annotations

from alembic import op


revision = "20260408_000003"
down_revision = "20260401_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create index for faster per-user job lookups."""

    op.create_index(
        "ix_job_descriptions_user_id",
        "job_descriptions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop index created for per-user job lookups."""

    op.drop_index("ix_job_descriptions_user_id", table_name="job_descriptions")
