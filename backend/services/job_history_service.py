"""Job log service for retrieving and recording database-backed job logs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger
from backend.models.job import Job
from backend.models.job_log import JobLog, LogLevel

logger = get_logger(__name__)


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
    """Service for retrieving and storing job execution logs."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the job history service.

        Args:
            session: SQLAlchemy async session for database access.
        """
        self._session = session

    async def job_exists(self, job_id: str | UUID) -> bool:
        """Check whether a job exists in the database.

        Args:
            job_id: The job ID (string or UUID).

        Returns:
            True if the job exists, False otherwise.
        """
        job_id_str = str(job_id)
        job_result = await self._session.execute(select(Job).where(Job.id == job_id_str))
        job = job_result.scalar_one_or_none()
        if job is None:
            logger.debug(
                "Job not found for logs lookup",
                extra={"job_id": job_id_str},
            )
            return False
        return True

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
        try:
            job_uuid = UUID(str(job_id))
        except ValueError, TypeError:
            logger.debug(
                "Invalid job ID format for logs lookup",
                extra={"job_id": str(job_id)},
            )
            return []

        query = select(JobLog).where(JobLog.job_id == job_uuid)

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
                allowed_levels = [
                    LogLevel.DEBUG.value,
                    LogLevel.INFO.value,
                    LogLevel.WARNING.value,
                    LogLevel.ERROR.value,
                ][min_level:]
                query = query.where(JobLog.level.in_(allowed_levels))

        if since:
            query = query.where(JobLog.timestamp >= since)

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

    async def add_job_log(
        self,
        job_id: str | UUID,
        level: str,
        message: str,
        context: dict[str, Any] | None = None,
        attempt_number: int = 1,
    ) -> JobLog | None:
        """Add a log entry for a job.

        Creates a new JobLog record for tracking job execution progress.

        Args:
            job_id: The job ID (string or UUID).
            level: Log level (DEBUG, INFO, WARNING, ERROR).
            message: The log message.
            context: Optional context data to include.
            attempt_number: Which attempt this log belongs to (default 1).

        Returns:
            The created JobLog record, or None if creation failed.
        """
        try:
            job_uuid = UUID(str(job_id))
        except ValueError, TypeError:
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

        return log_entry


_job_history_service: JobHistoryService | None = None


def get_job_history_service(session: AsyncSession) -> JobHistoryService:
    """Get or create a JobHistoryService instance.

    Args:
        session: SQLAlchemy async session for database access.

    Returns:
        JobHistoryService instance.
    """
    return JobHistoryService(session)
