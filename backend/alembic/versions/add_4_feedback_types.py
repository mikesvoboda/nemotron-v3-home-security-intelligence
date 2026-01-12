"""Add 4 feedback types to event_feedback and user_calibration

Revision ID: add_4_feedback_types
Revises: add_snooze_until_column
Create Date: 2026-01-12 12:00:00.000000

This migration updates the feedback system to support 4 feedback types:
1. correct - The alert was accurate
2. false_positive - The alert was wrong (no real threat)
3. missed_threat - A real threat was not detected
4. severity_wrong - Threat detected but severity was incorrect

Changes to event_feedback table:
- Updates CHECK constraint to allow 4 feedback types
- Adds expected_severity column for severity_wrong feedback
- Adds CHECK constraint for expected_severity values

Changes to user_calibration table:
- Adds correct_count column
- Adds missed_threat_count column
- Adds severity_wrong_count column
- Removes missed_detection_count (replaced by missed_threat_count)
- Adds CHECK constraints for new columns

Related Linear issues: NEM-2348, NEM-2352
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_4_feedback_types"
down_revision: str | Sequence[str] | None = "add_snooze_until_column"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add support for 4 feedback types."""
    # ==========================================================================
    # Update event_feedback table
    # ==========================================================================

    # 1. Drop the old CHECK constraint for feedback_type
    op.drop_constraint("ck_event_feedback_type", "event_feedback", type_="check")

    # 2. Create new CHECK constraint with 4 feedback types
    op.create_check_constraint(
        "ck_event_feedback_type",
        "event_feedback",
        sa.text(
            "feedback_type IN ('correct', 'false_positive', 'missed_threat', 'severity_wrong')"
        ),
    )

    # 3. Add expected_severity column
    op.add_column(
        "event_feedback",
        sa.Column("expected_severity", sa.String(), nullable=True),
    )

    # 4. Add CHECK constraint for expected_severity
    op.create_check_constraint(
        "ck_event_feedback_expected_severity",
        "event_feedback",
        sa.text(
            "expected_severity IS NULL OR expected_severity IN ('low', 'medium', 'high', 'critical')"
        ),
    )

    # ==========================================================================
    # Update user_calibration table
    # ==========================================================================

    # 1. Add new columns for feedback counts
    op.add_column(
        "user_calibration",
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column(
        "user_calibration",
        sa.Column("missed_threat_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column(
        "user_calibration",
        sa.Column("severity_wrong_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # 2. Add CHECK constraints for new columns
    op.create_check_constraint(
        "ck_user_calibration_correct_count",
        "user_calibration",
        sa.text("correct_count >= 0"),
    )

    op.create_check_constraint(
        "ck_user_calibration_mt_count",
        "user_calibration",
        sa.text("missed_threat_count >= 0"),
    )

    op.create_check_constraint(
        "ck_user_calibration_sw_count",
        "user_calibration",
        sa.text("severity_wrong_count >= 0"),
    )

    # 3. Migrate data: copy missed_detection_count to missed_threat_count
    op.execute("UPDATE user_calibration SET missed_threat_count = missed_detection_count")

    # 4. Drop the old missed_detection_count column constraint and column
    op.drop_constraint("ck_user_calibration_md_count", "user_calibration", type_="check")
    op.drop_column("user_calibration", "missed_detection_count")

    # 5. Migrate existing feedback types in event_feedback
    # Convert 'missed_detection' to 'missed_threat' for consistency
    op.execute(
        "UPDATE event_feedback SET feedback_type = 'missed_threat' "
        "WHERE feedback_type = 'missed_detection'"
    )


def downgrade() -> None:
    """Revert to 2 feedback types."""
    # ==========================================================================
    # Revert user_calibration table
    # ==========================================================================

    # 1. Add back missed_detection_count column
    op.add_column(
        "user_calibration",
        sa.Column("missed_detection_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # 2. Add back the constraint
    op.create_check_constraint(
        "ck_user_calibration_md_count",
        "user_calibration",
        sa.text("missed_detection_count >= 0"),
    )

    # 3. Migrate data back
    op.execute("UPDATE user_calibration SET missed_detection_count = missed_threat_count")

    # 4. Drop new columns and constraints
    op.drop_constraint("ck_user_calibration_sw_count", "user_calibration", type_="check")
    op.drop_constraint("ck_user_calibration_mt_count", "user_calibration", type_="check")
    op.drop_constraint("ck_user_calibration_correct_count", "user_calibration", type_="check")
    op.drop_column("user_calibration", "severity_wrong_count")
    op.drop_column("user_calibration", "missed_threat_count")
    op.drop_column("user_calibration", "correct_count")

    # ==========================================================================
    # Revert event_feedback table
    # ==========================================================================

    # 1. Convert 'missed_threat' back to 'missed_detection'
    op.execute(
        "UPDATE event_feedback SET feedback_type = 'missed_detection' "
        "WHERE feedback_type = 'missed_threat'"
    )

    # 2. Delete any 'correct' or 'severity_wrong' feedback (can't downgrade)
    op.execute("DELETE FROM event_feedback WHERE feedback_type IN ('correct', 'severity_wrong')")

    # 3. Drop expected_severity constraint and column
    op.drop_constraint("ck_event_feedback_expected_severity", "event_feedback", type_="check")
    op.drop_column("event_feedback", "expected_severity")

    # 4. Drop and recreate CHECK constraint with original 2 types
    op.drop_constraint("ck_event_feedback_type", "event_feedback", type_="check")
    op.create_check_constraint(
        "ck_event_feedback_type",
        "event_feedback",
        sa.text("feedback_type IN ('false_positive', 'missed_detection')"),
    )
