"""CameraCalibration model for per-camera risk calibration.

This model enables learning from user feedback to adjust risk scores per camera.
If a camera consistently over-alerts (high false positive rate), the risk_offset
is decreased to reduce scores. Conversely, if a camera under-alerts (low FP rate),
the offset is increased.

Key concepts:
- risk_offset: A score adjustment (-30 to +30) applied to raw model scores
  - Negative = camera over-alerts, reduce risk scores
  - Positive = camera under-alerts, increase risk scores
- model_weights: Per-camera adjustments to individual model confidence
- suppress_patterns: Time-based behavior suppression for known patterns

Implements NEM-3022: Implement camera calibration model and feedback-driven risk adjustment.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .camera import Base, Camera


class CameraCalibration(Base):
    """Per-camera risk calibration learned from feedback.

    Tracks aggregate feedback metrics and computed adjustments that
    modify how risk scores are calculated for specific cameras.

    The calibration system works as follows:
    1. User provides feedback on events (false positive, correct, etc.)
    2. FeedbackProcessor aggregates feedback per camera
    3. When enough feedback is collected (>= 20 samples):
       - If false_positive_rate > 0.5: decrease risk_offset (reduce scores)
       - If false_positive_rate < 0.1: increase risk_offset (increase scores)
    4. Risk scores are adjusted: final_score = model_score + risk_offset

    Attributes:
        id: Primary key
        camera_id: Foreign key to cameras table (unique per camera)
        total_feedback_count: Total number of feedback submissions
        false_positive_count: Count of false positive feedback
        false_positive_rate: Computed FP rate (false_positive_count / total)
        risk_offset: Score adjustment to apply (-30 to +30)
        model_weights: Per-model confidence weights (e.g., {"pose_model": 0.5})
        suppress_patterns: Time-based pattern suppression rules
        avg_model_score: Running average of model-predicted scores
        avg_user_suggested_score: Running average of user-suggested scores
        updated_at: Last update timestamp
        camera: Relationship to parent Camera

    Database constraints:
        - UNIQUE(camera_id): One calibration record per camera
        - CHECK: risk_offset between -30 and +30
        - CHECK: false_positive_rate between 0.0 and 1.0
        - CHECK: total_feedback_count >= 0
    """

    __tablename__ = "camera_calibrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Aggregate metrics
    total_feedback_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    false_positive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    false_positive_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Score adjustment (-30 to +30)
    # Negative = camera over-alerts, reduce scores
    # Positive = camera under-alerts, increase scores
    risk_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Model-specific adjustments as JSONB dict mapping model names to weight multipliers.
    # Weight values below 1.0 reduce that model's influence for this camera.
    model_weights: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Pattern-specific suppression rules as JSONB array of dicts.
    # Each dict contains pattern, time_range, and reduction fields.
    suppress_patterns: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)

    # Computed stats for calibration quality assessment
    avg_model_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_user_suggested_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamp for when calibration was last updated
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    camera: Mapped[Camera] = relationship("Camera")

    __table_args__ = (
        # Index for querying by camera_id (unique constraint also creates an index)
        Index("idx_camera_calibrations_camera_id", "camera_id"),
        # CHECK constraint for risk_offset range (-30 to +30)
        CheckConstraint(
            "risk_offset >= -30 AND risk_offset <= 30",
            name="ck_camera_calibrations_risk_offset_range",
        ),
        # CHECK constraint for false_positive_rate range (0.0 to 1.0)
        CheckConstraint(
            "false_positive_rate >= 0.0 AND false_positive_rate <= 1.0",
            name="ck_camera_calibrations_fp_rate_range",
        ),
        # CHECK constraint for non-negative feedback counts
        CheckConstraint(
            "total_feedback_count >= 0 AND false_positive_count >= 0",
            name="ck_camera_calibrations_feedback_count",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation of CameraCalibration."""
        return (
            f"<CameraCalibration(id={self.id}, camera_id={self.camera_id!r}, "
            f"risk_offset={self.risk_offset}, fp_rate={self.false_positive_rate})>"
        )
