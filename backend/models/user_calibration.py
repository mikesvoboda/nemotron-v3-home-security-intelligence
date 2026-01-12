"""UserCalibration model for personalized risk threshold calibration."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .camera import Base


class UserCalibration(Base):
    """UserCalibration model for storing personalized risk thresholds.

    Tracks user-specific risk thresholds that are adjusted based on
    feedback (correct, false positives, missed threats, and severity errors).

    Default thresholds:
    - low_threshold: 30 (0-29 = low risk)
    - medium_threshold: 60 (30-59 = medium risk)
    - high_threshold: 85 (60-84 = high risk, 85-100 = critical)

    Decay factor controls how quickly thresholds adjust based on feedback.
    Lower values = slower adjustment, higher values = faster adjustment.

    Feedback tracking for all 4 types:
    - correct_count: Alerts that were accurate
    - false_positive_count: Alerts that were wrong (no real threat)
    - missed_threat_count: Threats that were not detected
    - severity_wrong_count: Alerts with incorrect severity

    Database constraints:
    - UNIQUE(user_id): One calibration record per user
    - CHECK: Thresholds in range [0, 100]
    - CHECK: Thresholds ordered (low < medium < high)
    - CHECK: decay_factor in range [0.0, 1.0]
    - CHECK: Feedback counts >= 0
    """

    __tablename__ = "user_calibration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    # Risk thresholds (0-100)
    low_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    medium_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    high_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=85)

    # Decay factor for threshold adjustment (0.0-1.0)
    # Controls learning rate - how quickly thresholds adapt to feedback
    decay_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)

    # Feedback tracking for all 4 types
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    false_positive_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missed_threat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    severity_wrong_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        # Index for user lookup
        Index("idx_user_calibration_user_id", "user_id"),
        # CHECK constraints for threshold ranges
        CheckConstraint(
            "low_threshold >= 0 AND low_threshold <= 100",
            name="ck_user_calibration_low_range",
        ),
        CheckConstraint(
            "medium_threshold >= 0 AND medium_threshold <= 100",
            name="ck_user_calibration_medium_range",
        ),
        CheckConstraint(
            "high_threshold >= 0 AND high_threshold <= 100",
            name="ck_user_calibration_high_range",
        ),
        # CHECK constraint for threshold ordering
        CheckConstraint(
            "low_threshold < medium_threshold AND medium_threshold < high_threshold",
            name="ck_user_calibration_threshold_order",
        ),
        # CHECK constraint for decay factor range
        CheckConstraint(
            "decay_factor >= 0.0 AND decay_factor <= 1.0",
            name="ck_user_calibration_decay_range",
        ),
        # CHECK constraints for feedback counts (all 4 types)
        CheckConstraint(
            "correct_count >= 0",
            name="ck_user_calibration_correct_count",
        ),
        CheckConstraint(
            "false_positive_count >= 0",
            name="ck_user_calibration_fp_count",
        ),
        CheckConstraint(
            "missed_threat_count >= 0",
            name="ck_user_calibration_mt_count",
        ),
        CheckConstraint(
            "severity_wrong_count >= 0",
            name="ck_user_calibration_sw_count",
        ),
    )

    @property
    def total_feedback_count(self) -> int:
        """Get the total number of feedback responses across all types.

        Returns:
            Total count of all feedback provided by this user
        """
        return (
            self.correct_count
            + self.false_positive_count
            + self.missed_threat_count
            + self.severity_wrong_count
        )

    @property
    def accuracy_rate(self) -> float | None:
        """Calculate the accuracy rate based on feedback.

        Returns the ratio of correct predictions to total feedback.
        Returns None if no feedback has been provided.

        Returns:
            Accuracy rate as a float between 0.0 and 1.0, or None if no feedback
        """
        total = self.total_feedback_count
        if total == 0:
            return None
        return self.correct_count / total

    def __repr__(self) -> str:
        """Return string representation of UserCalibration."""
        return (
            f"<UserCalibration(id={self.id}, user_id={self.user_id!r}, "
            f"low={self.low_threshold}, medium={self.medium_threshold}, "
            f"high={self.high_threshold})>"
        )
