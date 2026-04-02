"""add stored filename to resumes"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260401_000002"
down_revision = "20260327_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add persisted saved filename for uploaded resumes."""

    op.add_column(
        "resumes",
        sa.Column("stored_filename", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE resumes
        SET stored_filename = (
            gen_random_uuid()::text ||
            COALESCE(SUBSTRING(filename FROM '\\.[^.]+$'), '')
        )
        WHERE stored_filename IS NULL OR BTRIM(stored_filename) = '';
        """
    )
    op.alter_column("resumes", "stored_filename", nullable=False)


def downgrade() -> None:
    """Revert stored filename column on resumes."""

    op.drop_column("resumes", "stored_filename")
