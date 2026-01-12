"""Add job_transitions table.

Revision ID: add_job_transitions
Revises: None (standalone migration)
Create Date: 2026-01-12

This migration creates the job_transitions table for tracking job state
transition history. This enables audit trails and debugging of job lifecycle.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_job_transitions"
down_revision = "add_snooze_until_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create job_transitions table with indexes."""
    # Create the job_transitions table
    op.create_table(
        "job_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("from_status", sa.String(50), nullable=False),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column(
            "transitioned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "triggered_by",
            sa.String(50),
            nullable=False,
            server_default="worker",
        ),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient querying
    op.create_index(
        "idx_job_transitions_job_id",
        "job_transitions",
        ["job_id"],
    )
    op.create_index(
        "idx_job_transitions_transitioned_at",
        "job_transitions",
        ["transitioned_at"],
    )
    op.create_index(
        "idx_job_transitions_job_id_transitioned_at",
        "job_transitions",
        ["job_id", "transitioned_at"],
    )


def downgrade() -> None:
    """Drop job_transitions table and indexes."""
    op.drop_index(
        "idx_job_transitions_job_id_transitioned_at",
        table_name="job_transitions",
    )
    op.drop_index(
        "idx_job_transitions_transitioned_at",
        table_name="job_transitions",
    )
    op.drop_index(
        "idx_job_transitions_job_id",
        table_name="job_transitions",
    )
    op.drop_table("job_transitions")
