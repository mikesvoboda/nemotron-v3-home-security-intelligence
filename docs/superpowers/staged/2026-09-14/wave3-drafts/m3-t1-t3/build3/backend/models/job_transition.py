"""Job transition model for tracking job state changes.

This module provides the JobTransition model for recording all state transitions
of background jobs, enabling audit trails and debugging of job lifecycle issues.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum, auto

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .camera import Base


class JobTransitionTrigger(StrEnum):
    """Source of the state transition trigger."""

    WORKER = auto()  # Background worker initiated the transition
    USER = auto()  # User action (cancel, retry)
    TIMEOUT = auto()  # Timeout-based transition
    RETRY = auto()  # Retry mechanism initiated the transition
    SYSTEM = auto()  # System-initiated (cleanup, recovery)


class JobTransition(Base):
    """Record of a job state transition for audit and debugging.

    Each transition records:
    - The job that transitioned
    - The old and new status values
    - When the transition occurred
    - What triggered the transition
    - Optional metadata about the transition

    This enables:
    - Full audit trail of job lifecycle
    - Debugging of job failures
    - Analysis of job processing patterns
    - Validation of state machine correctness
    """

    __tablename__ = "job_transitions"
    __table_args__ = (
        Index("idx_job_transitions_job_id", "job_id"),
        Index("idx_job_transitions_transitioned_at", "transitioned_at"),
        Index("idx_job_transitions_job_id_transitioned_at", "job_id", "transitioned_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid7,
    )
    # Use String(36) to match the Job model's id type (UUID as string)
    job_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    to_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    transitioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    triggered_by: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=str(JobTransitionTrigger.WORKER),
    )
    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<JobTransition(id={self.id!r}, job_id={self.job_id!r}, "
            f"{self.from_status!r} -> {self.to_status!r})>"
        )
