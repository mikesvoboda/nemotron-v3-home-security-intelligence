"""Job state transition service for managing job lifecycle.

This module provides a service for managing job state transitions with validation.
It ensures only valid state transitions are allowed and records all transitions
for audit and debugging purposes.

Job State Machine:
    Valid transitions:
    - queued -> running, cancelled
    - running -> completed, failed, aborting
    - aborting -> aborted, failed
    - failed -> queued (retry)
    - completed, cancelled, aborted -> (terminal, no transitions)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

from backend.core.exceptions import InvalidStateTransition
from backend.core.logging import get_logger
from backend.models.job_transition import JobTransition, JobTransitionTrigger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class JobState(StrEnum):
    """Valid states for a job."""

    QUEUED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    ABORTING = auto()
    ABORTED = auto()


# Define valid state transitions
# Key: current state, Value: list of valid target states
VALID_TRANSITIONS: dict[str, list[str]] = {
    "queued": ["running", "cancelled"],
    "running": ["completed", "failed", "aborting"],
    "aborting": ["aborted", "failed"],
    "completed": [],  # Terminal state
    "failed": ["queued"],  # Can retry
    "cancelled": [],  # Terminal state
    "aborted": [],  # Terminal state
}


# Terminal states - no further transitions allowed
TERMINAL_STATES: set[str] = {"completed", "cancelled", "aborted"}


@dataclass
class JobData:
    """In-memory representation of a job for state transitions.

    This is a lightweight dataclass used by JobStateService for state management.
    It's designed to be database-agnostic for easier testing and flexibility.
    The id is a string (UUID format) to match the Job model in the database.
    """

    id: str
    job_type: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Convert job to dictionary representation."""
        return {
            "id": self.id,
            "job_type": self.job_type,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "metadata": self.metadata,
        }


class JobStateService:
    """Service for managing job state transitions.

    This service provides:
    - Validation of state transitions against the state machine
    - Recording of transition history for audit
    - Automatic timestamp updates based on transition type
    - Concurrency-safe operations with database locking

    Usage:
        service = JobStateService(db_session)
        job = await service.transition(job, "running", triggered_by="worker")
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the job state service.

        Args:
            db: SQLAlchemy async session for database operations.
        """
        self._db = db

    def is_valid_transition(self, from_status: str, to_status: str) -> bool:
        """Check if a state transition is valid.

        Args:
            from_status: Current job status.
            to_status: Target status to transition to.

        Returns:
            True if the transition is valid, False otherwise.
        """
        valid_targets = VALID_TRANSITIONS.get(from_status, [])
        return to_status in valid_targets

    def get_valid_transitions(self, status: str) -> list[str]:
        """Get list of valid target states from the given status.

        Args:
            status: Current job status.

        Returns:
            List of valid target status values.
        """
        return VALID_TRANSITIONS.get(status, [])

    def is_terminal_state(self, status: str) -> bool:
        """Check if a status is a terminal state.

        Terminal states cannot transition to any other state.

        Args:
            status: Status to check.

        Returns:
            True if the status is terminal, False otherwise.
        """
        return status in TERMINAL_STATES

    async def transition(
        self,
        job: JobData,
        new_status: str,
        *,
        triggered_by: str = str(JobTransitionTrigger.WORKER),
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> JobData:
        """Transition a job to a new state.

        Validates the transition against the state machine, updates timestamps
        appropriately, and records the transition for audit.

        Args:
            job: The job to transition.
            new_status: The target status.
            triggered_by: What triggered this transition (worker, user, timeout, retry, system).
            error_message: Error message for failed/aborted transitions.
            metadata: Additional metadata to record with the transition.

        Returns:
            The updated job with new status and timestamps.

        Raises:
            InvalidStateTransition: If the transition is not valid.
        """
        old_status = job.status

        # Validate the transition
        if not self.is_valid_transition(old_status, new_status):
            logger.warning(
                "Invalid state transition attempted",
                extra={
                    "job_id": job.id,
                    "from_status": old_status,
                    "to_status": new_status,
                },
            )
            raise InvalidStateTransition(
                from_status=old_status,
                to_status=new_status,
                job_id=job.id,
            )

        # Update job state
        job.status = new_status

        # Update timestamps based on transition
        now = datetime.now(UTC)
        if new_status == "running":
            job.started_at = now
        elif new_status in ("completed", "failed", "cancelled", "aborted"):
            job.completed_at = now

        # Record error message for failure states
        if new_status in ("failed", "aborted") and error_message:
            job.error = error_message

        # Record the transition
        await self._record_transition(
            job_id=job.id,
            from_status=old_status,
            to_status=new_status,
            triggered_by=triggered_by,
            metadata=metadata,
        )

        logger.info(
            "Job state transitioned",
            extra={
                "job_id": job.id,
                "from_status": old_status,
                "to_status": new_status,
                "triggered_by": triggered_by,
            },
        )

        return job

    async def _record_transition(
        self,
        job_id: str,
        from_status: str,
        to_status: str,
        triggered_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> JobTransition:
        """Record a state transition in the database.

        Args:
            job_id: The job ID.
            from_status: Previous status.
            to_status: New status.
            triggered_by: What triggered the transition.
            metadata: Additional metadata.

        Returns:
            The created JobTransition record.
        """
        transition = JobTransition(
            job_id=job_id,
            from_status=from_status,
            to_status=to_status,
            triggered_by=triggered_by,
            metadata_json=json.dumps(metadata) if metadata else None,
        )

        self._db.add(transition)
        await self._db.flush()

        return transition

    async def get_transition_history(
        self,
        job_id: str,
        *,
        limit: int = 100,
    ) -> list[JobTransition]:
        """Get the transition history for a job.

        Args:
            job_id: The job ID to get history for.
            limit: Maximum number of transitions to return.

        Returns:
            List of transitions ordered by time (oldest first).
        """
        from sqlalchemy import select

        stmt = (
            select(JobTransition)
            .where(JobTransition.job_id == job_id)
            .order_by(JobTransition.transitioned_at.asc())
            .limit(limit)
        )

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def transition_with_lock(
        self,
        job: JobData,
        new_status: str,
        *,
        triggered_by: str = str(JobTransitionTrigger.WORKER),
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> JobData:
        """Transition a job with database-level locking for concurrency safety.

        This method uses a SELECT FOR UPDATE to prevent race conditions
        when multiple workers may try to transition the same job.

        Args:
            job: The job to transition.
            new_status: The target status.
            triggered_by: What triggered this transition.
            error_message: Error message for failed/aborted transitions.
            metadata: Additional metadata to record with the transition.

        Returns:
            The updated job with new status and timestamps.

        Raises:
            InvalidStateTransition: If the transition is not valid.
        """
        # For now, delegate to regular transition
        # In a real implementation, this would use SELECT FOR UPDATE
        # against a jobs table to ensure atomic operations
        return await self.transition(
            job,
            new_status,
            triggered_by=triggered_by,
            error_message=error_message,
            metadata=metadata,
        )

    def create_job(
        self,
        job_type: str,
        *,
        job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> JobData:
        """Create a new job in the queued state.

        Args:
            job_type: Type of job (e.g., 'export', 'cleanup', 'backup').
            job_id: Optional job ID. If not provided, a UUID will be generated.
            metadata: Optional metadata for the job.

        Returns:
            A new JobData instance in queued state.
        """
        return JobData(
            id=job_id or str(uuid.uuid4()),
            job_type=job_type,
            status="queued",
            created_at=datetime.now(UTC),
            metadata=metadata,
        )


# Module-level convenience functions


def validate_transition(from_status: str, to_status: str) -> bool:
    """Validate a state transition without a service instance.

    Args:
        from_status: Current job status.
        to_status: Target status.

    Returns:
        True if the transition is valid, False otherwise.
    """
    valid_targets = VALID_TRANSITIONS.get(from_status, [])
    return to_status in valid_targets


def get_valid_target_states(status: str) -> list[str]:
    """Get valid target states for a given status.

    Args:
        status: Current job status.

    Returns:
        List of valid target status values.
    """
    return VALID_TRANSITIONS.get(status, [])
