"""Job history service for retrieving job execution history.

This service provides methods to retrieve comprehensive job history including
state transitions, retry history, execution timeline, and logs. It supports
the job history API endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger
from backend.models.job import Job
from backend.models.job_attempt import JobAttempt
from backend.models.job_log import JobLog, LogLevel
from backend.models.job_transition import JobTransition

logger = get_logger(__name__)


@dataclass
class TransitionRecord:
    """A single state transition record."""

    from_status: str | None
    to_status: str
    at: datetime
    triggered_by: str
    details: dict[str, Any] | None = None


@dataclass
class AttemptRecord:
    """A single job attempt record."""

    attempt_number: int
    started_at: datetime
    ended_at: datetime | None
    status: str
    error: str | None
    worker_id: str | None
    duration_seconds: float | None = None
    result: dict[str, Any] | None = None


@dataclass
class JobHistory:
    """Complete job history with transitions and attempts."""

    job_id: str
    job_type: str
    status: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    transitions: list[TransitionRecord] = field(default_factory=list)
    attempts: list[AttemptRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "transitions": [
                {
                    "from": t.from_status,
                    "to": t.to_status,
                    "at": t.at.isoformat(),
                    "triggered_by": t.triggered_by,
                    "details": t.details,
                }
                for t in self.transitions
            ],
            "attempts": [
                {
                    "attempt_number": a.attempt_number,
                    "started_at": a.started_at.isoformat(),
                    "ended_at": a.ended_at.isoformat() if a.ended_at else None,
                    "status": a.status,
                    "error": a.error,
                    "worker_id": a.worker_id,
                    "duration_seconds": a.duration_seconds,
                    "result": a.result,
                }
                for a in self.attempts
            ],
        }


@dataclass
class JobLogEntry:
    """A single job log entry."""

    timestamp: datetime
    level: str
    message: str
    context: dict[str, Any] | None = None
    attempt_number: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.upper(),
            "message": self.message,
            "context": self.context,
            "attempt_number": self.attempt_number,
        }


class JobHistoryService:
    """Service for retrieving job history and audit trail information.

    This service provides methods to query comprehensive job execution history
    including state transitions, retry attempts, and execution logs.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the job history service.

        Args:
            session: SQLAlchemy async session for database access.
        """
        self._session = session

    async def get_job_history(self, job_id: str | UUID) -> JobHistory | None:
        """Get complete job history with transitions and attempts.

        Retrieves the full execution history of a job including all state
        transitions and retry attempts.

        Args:
            job_id: The job ID (string or UUID).

        Returns:
            JobHistory object containing transitions and attempts,
            or None if job not found.
        """
        job_id_str = str(job_id)

        # Get the job
        job_result = await self._session.execute(select(Job).where(Job.id == job_id_str))
        job = job_result.scalar_one_or_none()

        if job is None:
            logger.debug(
                "Job not found for history lookup",
                extra={"job_id": job_id_str},
            )
            return None

        # Get all transitions for this job
        transitions = await self._get_transitions(job_id_str)

        # Get all attempts for this job
        attempts = await self._get_attempts(job_id_str)

        return JobHistory(
            job_id=job.id,
            job_type=job.job_type,
            status=job.status,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            transitions=transitions,
            attempts=attempts,
        )

    async def _get_transitions(self, job_id: str) -> list[TransitionRecord]:
        """Get all state transitions for a job.

        Args:
            job_id: The job ID string.

        Returns:
            List of TransitionRecord objects ordered by transition time.
        """
        # Try to parse as UUID for the transition table
        try:
            job_uuid = UUID(job_id)
            result = await self._session.execute(
                select(JobTransition)
                .where(JobTransition.job_id == job_uuid)
                .order_by(JobTransition.transitioned_at)
            )
            transitions = result.scalars().all()

            return [
                TransitionRecord(
                    from_status=t.from_status if t.from_status != "initial" else None,
                    to_status=t.to_status,
                    at=t.transitioned_at,
                    triggered_by=t.triggered_by,
                    details={"metadata": t.metadata_json} if t.metadata_json else None,
                )
                for t in transitions
            ]
        except (ValueError, TypeError):
            # Job ID is not a valid UUID - return empty transitions
            return []

    async def _get_attempts(self, job_id: str) -> list[AttemptRecord]:
        """Get all execution attempts for a job.

        Args:
            job_id: The job ID string.

        Returns:
            List of AttemptRecord objects ordered by attempt number.
        """
        # Try to parse as UUID for the attempts table
        try:
            job_uuid = UUID(job_id)
            result = await self._session.execute(
                select(JobAttempt)
                .where(JobAttempt.job_id == job_uuid)
                .order_by(JobAttempt.attempt_number)
            )
            attempts = result.scalars().all()

            return [
                AttemptRecord(
                    attempt_number=a.attempt_number,
                    started_at=a.started_at,
                    ended_at=a.ended_at,
                    status=a.status,
                    error=a.error_message,
                    worker_id=a.worker_id,
                    duration_seconds=a.duration_seconds,
                    result=a.result,
                )
                for a in attempts
            ]
        except (ValueError, TypeError):
            # Job ID is not a valid UUID - return empty attempts
            return []

    async def get_job_logs(
        self,
        job_id: str | UUID,
        level: str | None = None,
        since: datetime | None = None,
        limit: int = 1000,
    ) -> list[JobLogEntry]:
        """Get job logs with optional filtering.

        Retrieves log entries for a job, optionally filtered by level and/or
        time range.

        Args:
            job_id: The job ID (string or UUID).
            level: Optional log level filter (DEBUG, INFO, WARNING, ERROR).
                   Only logs at this level or higher will be returned.
            since: Optional timestamp to filter logs from this time onwards.
            limit: Maximum number of log entries to return (default 1000).

        Returns:
            List of JobLogEntry objects ordered by timestamp.
        """
        # Try to parse as UUID for the logs table
        try:
            job_uuid = UUID(str(job_id))
        except (ValueError, TypeError):
            logger.debug(
                "Invalid job ID format for logs lookup",
                extra={"job_id": str(job_id)},
            )
            return []

        # Build the query
        query = select(JobLog).where(JobLog.job_id == job_uuid)

        # Apply level filter - filter to this level and above
        if level:
            level_upper = level.upper()
            level_order = {
                "DEBUG": 0,
                "INFO": 1,
                "WARNING": 2,
                "ERROR": 3,
            }
            min_level = level_order.get(level_upper, 0)
            if min_level > 0:
                # Filter to only include logs at or above the specified level
                allowed_levels = [
                    LogLevel.DEBUG.value,
                    LogLevel.INFO.value,
                    LogLevel.WARNING.value,
                    LogLevel.ERROR.value,
                ][min_level:]
                query = query.where(JobLog.level.in_(allowed_levels))

        # Apply time filter
        if since:
            query = query.where(JobLog.timestamp >= since)

        # Order and limit
        query = query.order_by(JobLog.timestamp).limit(limit)

        result = await self._session.execute(query)
        logs = result.scalars().all()

        return [
            JobLogEntry(
                timestamp=log.timestamp,
                level=log.level,
                message=log.message,
                context=log.context,
                attempt_number=log.attempt_number,
            )
            for log in logs
        ]

    async def record_attempt_start(
        self,
        job_id: str | UUID,
        attempt_number: int,
        worker_id: str | None = None,
    ) -> JobAttempt | None:
        """Record the start of a job execution attempt.

        Creates a new JobAttempt record when a job begins execution.

        Args:
            job_id: The job ID (string or UUID).
            attempt_number: The attempt number (1-based).
            worker_id: Optional identifier of the worker processing this attempt.

        Returns:
            The created JobAttempt record, or None if creation failed.
        """
        try:
            job_uuid = UUID(str(job_id))
        except (ValueError, TypeError):
            logger.warning(
                "Invalid job ID format for attempt recording",
                extra={"job_id": str(job_id)},
            )
            return None

        attempt = JobAttempt(
            job_id=job_uuid,
            attempt_number=attempt_number,
            worker_id=worker_id,
            status="started",
        )
        self._session.add(attempt)
        await self._session.flush()

        logger.info(
            "Job attempt started",
            extra={
                "job_id": str(job_id),
                "attempt_number": attempt_number,
                "worker_id": worker_id,
            },
        )

        return attempt

    async def record_attempt_end(
        self,
        job_id: str | UUID,
        attempt_number: int,
        status: str,
        error_message: str | None = None,
        error_traceback: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> JobAttempt | None:
        """Record the end of a job execution attempt.

        Updates the JobAttempt record when a job attempt completes.

        Args:
            job_id: The job ID (string or UUID).
            attempt_number: The attempt number (1-based).
            status: Final status (succeeded, failed, cancelled).
            error_message: Optional error message if failed.
            error_traceback: Optional error traceback if failed.
            result: Optional result data if successful.

        Returns:
            The updated JobAttempt record, or None if not found.
        """
        try:
            job_uuid = UUID(str(job_id))
        except (ValueError, TypeError):
            logger.warning(
                "Invalid job ID format for attempt end recording",
                extra={"job_id": str(job_id)},
            )
            return None

        result_query = await self._session.execute(
            select(JobAttempt)
            .where(JobAttempt.job_id == job_uuid)
            .where(JobAttempt.attempt_number == attempt_number)
        )
        attempt = result_query.scalar_one_or_none()

        if attempt is None:
            logger.warning(
                "Job attempt not found for end recording",
                extra={"job_id": str(job_id), "attempt_number": attempt_number},
            )
            return None

        from datetime import UTC, datetime

        attempt.ended_at = datetime.now(UTC)
        attempt.status = status
        attempt.error_message = error_message
        attempt.error_traceback = error_traceback
        attempt.result = result

        logger.info(
            "Job attempt ended",
            extra={
                "job_id": str(job_id),
                "attempt_number": attempt_number,
                "status": status,
            },
        )

        return attempt

    async def add_job_log(
        self,
        job_id: str | UUID,
        level: str,
        message: str,
        context: dict[str, Any] | None = None,
        attempt_number: int = 1,
        *,
        emit_to_websocket: bool = True,
    ) -> JobLog | None:
        """Add a log entry for a job.

        Creates a new JobLog record for tracking job execution progress.
        Optionally emits the log to Redis pub/sub for real-time WebSocket streaming.

        Args:
            job_id: The job ID (string or UUID).
            level: Log level (DEBUG, INFO, WARNING, ERROR).
            message: The log message.
            context: Optional context data to include.
            attempt_number: Which attempt this log belongs to (default 1).
            emit_to_websocket: Whether to emit log to WebSocket via Redis pub/sub.
                Defaults to True for real-time streaming.

        Returns:
            The created JobLog record, or None if creation failed.
        """
        try:
            job_uuid = UUID(str(job_id))
        except (ValueError, TypeError):
            logger.warning(
                "Invalid job ID format for log recording",
                extra={"job_id": str(job_id)},
            )
            return None

        log_entry = JobLog(
            job_id=job_uuid,
            attempt_number=attempt_number,
            level=level.lower(),
            message=message,
            context=context,
        )
        self._session.add(log_entry)
        await self._session.flush()

        # Emit log to Redis pub/sub for real-time WebSocket streaming (NEM-2711)
        if emit_to_websocket:
            try:
                from backend.services.job_log_emitter import get_job_log_emitter

                emitter = await get_job_log_emitter()
                await emitter.emit_log(
                    job_id=job_id,
                    level=level,
                    message=message,
                    context=context,
                )
            except Exception as e:
                # Log emission failure but don't fail the database operation
                logger.warning(
                    f"Failed to emit job log to WebSocket: {e}",
                    extra={"job_id": str(job_id)},
                )

        return log_entry


# Module-level singleton
_job_history_service: JobHistoryService | None = None


def get_job_history_service(session: AsyncSession) -> JobHistoryService:
    """Get or create a JobHistoryService instance.

    Args:
        session: SQLAlchemy async session for database access.

    Returns:
        JobHistoryService instance.
    """
    return JobHistoryService(session)
