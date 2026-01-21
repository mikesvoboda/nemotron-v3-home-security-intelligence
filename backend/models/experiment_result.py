"""ExperimentResult model for tracking prompt A/B test comparisons (NEM-3023).

This model stores the results of shadow mode and A/B test prompt comparisons,
allowing analysis of prompt performance differences over time.

Data collected includes:
- Risk scores from both V1 (control) and V2 (treatment) prompts
- Latency measurements for both prompts
- Camera and experiment context for filtering

This data enables:
- Validating V2 prompt performance before full rollout
- Detecting regressions in risk scoring accuracy
- Monitoring latency impact of new prompts
- Statistical analysis of A/B test results
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .camera import Base


class ExperimentResult(Base):
    """Model for storing prompt experiment comparison results.

    This table stores the side-by-side comparison results from shadow mode
    and A/B test executions. Each row represents a single analysis where
    both V1 and V2 prompts were evaluated (or would have been in A/B mode).

    Attributes:
        id: Auto-incrementing primary key
        experiment_name: Name of the experiment (e.g., "nemotron_prompt_v2")
        experiment_version: Version/phase identifier (e.g., "shadow", "ab_test_30pct")
        camera_id: Camera that was analyzed
        created_at: When this result was recorded
        v1_risk_score: Risk score from V1 (control) prompt
        v2_risk_score: Risk score from V2 (treatment) prompt
        v1_latency_ms: V1 prompt latency in milliseconds
        v2_latency_ms: V2 prompt latency in milliseconds
        score_diff: Absolute difference between V1 and V2 scores (optional, for denormalization)
        v1_risk_level: Risk level string from V1 (low/medium/high/critical)
        v2_risk_level: Risk level string from V2 (low/medium/high/critical)
        event_id: Optional reference to the Event created from this analysis
        batch_id: Batch identifier for correlation
    """

    __tablename__ = "experiment_results"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Experiment identification
    experiment_name: Mapped[str] = mapped_column(String(100), nullable=False)
    experiment_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Context
    camera_id: Mapped[str] = mapped_column(String(50), nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # V1 (control) results
    v1_risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    v1_risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    v1_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)

    # V2 (treatment) results
    v2_risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    v2_risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    v2_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)

    # Pre-calculated diff for query convenience (denormalized)
    score_diff: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Indexes for common query patterns
    __table_args__ = (
        # Index for filtering by experiment name and time
        Index(
            "ix_experiment_results_experiment_created",
            "experiment_name",
            "created_at",
        ),
        # Index for filtering by camera
        Index(
            "ix_experiment_results_camera_created",
            "camera_id",
            "created_at",
        ),
        # Index for time-based queries
        Index(
            "ix_experiment_results_created_at",
            "created_at",
        ),
    )

    @property
    def calculated_score_diff(self) -> int:
        """Calculate absolute difference between V1 and V2 scores.

        Returns:
            Absolute difference in risk scores
        """
        return abs(self.v1_risk_score - self.v2_risk_score)

    @property
    def latency_diff_ms(self) -> float:
        """Calculate latency difference (V2 - V1).

        Positive values mean V2 is slower.

        Returns:
            Latency difference in milliseconds
        """
        return self.v2_latency_ms - self.v1_latency_ms

    @property
    def latency_increase_pct(self) -> float:
        """Calculate percentage latency increase of V2 vs V1.

        Returns:
            Percentage increase (0 if V1 latency is 0)
        """
        if self.v1_latency_ms == 0:
            return 0.0 if self.v2_latency_ms == 0 else 100.0
        return ((self.v2_latency_ms - self.v1_latency_ms) / self.v1_latency_ms) * 100

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary.

        Returns:
            Dictionary representation of the experiment result
        """
        return {
            "id": self.id,
            "experiment_name": self.experiment_name,
            "experiment_version": self.experiment_version,
            "camera_id": self.camera_id,
            "batch_id": self.batch_id,
            "event_id": self.event_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "v1_risk_score": self.v1_risk_score,
            "v1_risk_level": self.v1_risk_level,
            "v1_latency_ms": self.v1_latency_ms,
            "v2_risk_score": self.v2_risk_score,
            "v2_risk_level": self.v2_risk_level,
            "v2_latency_ms": self.v2_latency_ms,
            "score_diff": self.score_diff,
            "calculated_score_diff": self.calculated_score_diff,
            "latency_diff_ms": self.latency_diff_ms,
            "latency_increase_pct": self.latency_increase_pct,
        }
