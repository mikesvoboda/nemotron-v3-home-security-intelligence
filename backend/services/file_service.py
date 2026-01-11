"""File service for scheduled file deletion with Redis sorted set queue.

This module provides the FileService class for managing scheduled file deletions.
Files are queued for deletion with a configurable delay (default 5 minutes) to
support undo operations when events are restored.

Related Linear issue: NEM-1988
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from backend.core.logging import get_logger
from backend.core.redis import RedisClient, get_redis_client_sync

logger = get_logger(__name__)

# Default delay before file deletion (5 minutes)
DEFAULT_DELETION_DELAY_SECONDS = 300

# Redis key for the file deletion queue (sorted set)
FILE_DELETION_QUEUE = "file_deletion_queue"

# Default batch size for processing deletions
DEFAULT_BATCH_SIZE = 100

# Background task polling interval in seconds
BACKGROUND_POLL_INTERVAL = 60


@dataclass
class FileDeletionJob:
    """Represents a scheduled file deletion job.

    Attributes:
        file_paths: List of file paths to delete
        event_id: ID of the event that triggered the deletion
        job_id: Unique identifier for this job
        created_at: Timestamp when the job was created
    """

    file_paths: list[str]
    event_id: int
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        """Serialize job to JSON string."""
        return json.dumps(
            {
                "file_paths": self.file_paths,
                "event_id": self.event_id,
                "job_id": self.job_id,
                "created_at": self.created_at,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> FileDeletionJob:
        """Deserialize job from JSON string."""
        data = json.loads(json_str)
        return cls(
            file_paths=data["file_paths"],
            event_id=data["event_id"],
            job_id=data["job_id"],
            created_at=data["created_at"],
        )


class FileService:
    """Service for managing scheduled file deletions.

    Files are queued in a Redis sorted set with the deletion timestamp as the score.
    A background task periodically processes the queue, deleting files whose
    scheduled deletion time has passed.

    This supports cascade file deletion when events are soft-deleted, with a
    configurable delay (default 5 minutes) to allow for undo/restore operations.
    """

    def __init__(self, redis_client: RedisClient | None = None):
        """Initialize the file service.

        Args:
            redis_client: Optional Redis client. If not provided, will be obtained
                from get_redis_client_sync() when needed.
        """
        self._redis_client = redis_client
        self._running = False
        self._task: asyncio.Task[None] | None = None

    def _get_redis(self) -> RedisClient | None:
        """Get the Redis client.

        Returns:
            RedisClient if available, None otherwise.
        """
        if self._redis_client:
            return self._redis_client
        return get_redis_client_sync()

    async def schedule_deletion(
        self,
        file_paths: list[str],
        event_id: int,
        delay_seconds: int | None = None,
    ) -> str | None:
        """Schedule files for deletion after a delay.

        Args:
            file_paths: List of file paths to delete
            event_id: ID of the event associated with these files
            delay_seconds: Delay before deletion in seconds.
                Defaults to DEFAULT_DELETION_DELAY_SECONDS (5 minutes).

        Returns:
            Job ID if successfully scheduled, None if Redis unavailable or no files.
        """
        redis = self._get_redis()
        if not redis:
            logger.warning("Redis unavailable, cannot schedule file deletion")
            return None

        # Filter out empty paths and non-existent files
        valid_paths = [p for p in file_paths if p and Path(p).exists()]
        if not valid_paths:
            logger.debug(f"No valid file paths to delete for event {event_id}")
            return None

        if delay_seconds is None:
            delay_seconds = DEFAULT_DELETION_DELAY_SECONDS

        job = FileDeletionJob(file_paths=valid_paths, event_id=event_id)
        deletion_time = time.time() + delay_seconds

        # Add to sorted set with deletion time as score
        await redis.zadd(FILE_DELETION_QUEUE, {job.to_json(): deletion_time})

        logger.info(
            f"Scheduled {len(valid_paths)} files for deletion in {delay_seconds}s "
            f"(event_id={event_id}, job_id={job.job_id})"
        )

        return job.job_id

    async def cancel_deletion(self, job_id: str) -> bool:
        """Cancel a scheduled deletion by job ID.

        Args:
            job_id: The job ID to cancel

        Returns:
            True if job was found and cancelled, False otherwise.
        """
        redis = self._get_redis()
        if not redis:
            logger.warning("Redis unavailable, cannot cancel file deletion")
            return False

        # Get all jobs and find the one with matching job_id
        all_jobs = await redis.zrange(FILE_DELETION_QUEUE, 0, -1)

        for job_json in all_jobs:
            try:
                job = FileDeletionJob.from_json(job_json)
                if job.job_id == job_id:
                    await redis.zrem(FILE_DELETION_QUEUE, job_json)
                    logger.info(f"Cancelled file deletion job {job_id}")
                    return True
            except (json.JSONDecodeError, KeyError):
                continue

        logger.debug(f"File deletion job {job_id} not found")
        return False

    async def cancel_deletion_by_event_id(self, event_id: int) -> int:
        """Cancel all scheduled deletions for a specific event.

        Args:
            event_id: The event ID whose deletions should be cancelled

        Returns:
            Number of jobs cancelled.
        """
        redis = self._get_redis()
        if not redis:
            logger.warning("Redis unavailable, cannot cancel file deletion")
            return 0

        # Get all jobs and find those matching the event_id
        all_jobs = await redis.zrange(FILE_DELETION_QUEUE, 0, -1)
        cancelled_count = 0

        for job_json in all_jobs:
            try:
                job = FileDeletionJob.from_json(job_json)
                if job.event_id == event_id:
                    await redis.zrem(FILE_DELETION_QUEUE, job_json)
                    cancelled_count += 1
                    logger.debug(f"Cancelled file deletion job {job.job_id} for event {event_id}")
            except (json.JSONDecodeError, KeyError):
                continue

        if cancelled_count > 0:
            logger.info(f"Cancelled {cancelled_count} file deletion jobs for event {event_id}")

        return cancelled_count

    async def process_deletion_queue(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> tuple[int, int]:
        """Process pending file deletions that are due.

        Args:
            batch_size: Maximum number of jobs to process in one batch.

        Returns:
            Tuple of (jobs_processed, files_deleted).
        """
        redis = self._get_redis()
        if not redis:
            return 0, 0

        current_time = time.time()

        # Get jobs that are due for deletion (score <= current_time)
        due_jobs = await redis.zrangebyscore(
            FILE_DELETION_QUEUE,
            "-inf",
            current_time,
            start=0,
            num=batch_size,
        )

        jobs_processed = 0
        files_deleted = 0

        for job_json in due_jobs:
            try:
                job = FileDeletionJob.from_json(job_json)

                # Delete each file
                for file_path in job.file_paths:
                    if await self.delete_file(file_path):
                        files_deleted += 1

                # Remove from queue after processing
                await redis.zrem(FILE_DELETION_QUEUE, job_json)
                jobs_processed += 1

                logger.debug(
                    f"Processed file deletion job {job.job_id} "
                    f"(event_id={job.event_id}, files={len(job.file_paths)})"
                )

            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to process file deletion job: {e}")
                # Remove malformed entry
                await redis.zrem(FILE_DELETION_QUEUE, job_json)

        if jobs_processed > 0:
            logger.info(
                f"Processed {jobs_processed} file deletion jobs, deleted {files_deleted} files"
            )

        return jobs_processed, files_deleted

    async def delete_file(self, file_path: str) -> bool:
        """Delete a single file.

        Args:
            file_path: Path to the file to delete

        Returns:
            True if file was deleted, False if it didn't exist or failed.
        """
        try:
            path = Path(file_path)
            if path.exists():
                Path(file_path).unlink()
                logger.debug(f"Deleted file: {file_path}")
                return True
            else:
                logger.debug(f"File not found (already deleted?): {file_path}")
                return False
        except OSError as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False

    async def delete_files_immediately(
        self,
        file_paths: list[str],
    ) -> tuple[int, int]:
        """Delete multiple files immediately without scheduling.

        This method is used for hard deletes where files should be removed
        immediately rather than being scheduled for delayed deletion.

        Args:
            file_paths: List of file paths to delete

        Returns:
            Tuple of (files_deleted, files_failed).
            - files_deleted: Number of files that were successfully deleted
            - files_failed: Number of files that failed to delete due to errors
        """
        # Filter out empty/None paths
        valid_paths = [p for p in file_paths if p]
        if not valid_paths:
            return 0, 0

        files_deleted = 0
        files_failed = 0

        for file_path in valid_paths:
            try:
                path = Path(file_path)
                if path.exists():
                    path.unlink()
                    files_deleted += 1
                    logger.debug(f"Immediately deleted file: {file_path}")
                # Non-existent files are not counted as deleted or failed
                # (they're already gone, which is the desired state)
            except OSError as e:
                logger.error(f"Failed to immediately delete file {file_path}: {e}")
                files_failed += 1

        if files_deleted > 0 or files_failed > 0:
            logger.info(f"Immediate file deletion: {files_deleted} deleted, {files_failed} failed")

        return files_deleted, files_failed

    async def get_queue_size(self) -> int:
        """Get the number of jobs in the deletion queue.

        Returns:
            Number of pending deletion jobs.
        """
        redis = self._get_redis()
        if not redis:
            return 0
        return await redis.zcard(FILE_DELETION_QUEUE)

    async def get_pending_jobs_for_event(self, event_id: int) -> list[FileDeletionJob]:
        """Get all pending deletion jobs for a specific event.

        Args:
            event_id: The event ID to look up

        Returns:
            List of pending deletion jobs for the event.
        """
        redis = self._get_redis()
        if not redis:
            return []

        all_jobs = await redis.zrange(FILE_DELETION_QUEUE, 0, -1)
        result = []

        for job_json in all_jobs:
            try:
                job = FileDeletionJob.from_json(job_json)
                if job.event_id == event_id:
                    result.append(job)
            except (json.JSONDecodeError, KeyError):
                continue

        return result

    async def start(self) -> None:
        """Start the background task for processing deletions."""
        if self._running:
            logger.warning("FileService background task already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._background_worker())
        logger.info("FileService background task started")

    async def stop(self) -> None:
        """Stop the background task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("FileService background task stopped")

    async def _background_worker(self) -> None:
        """Background worker that periodically processes the deletion queue."""
        while self._running:
            try:
                await self.process_deletion_queue()
            except Exception as e:
                logger.error(f"Error in file deletion background worker: {e}")

            # Wait for next poll interval
            try:
                await asyncio.sleep(BACKGROUND_POLL_INTERVAL)
            except asyncio.CancelledError:
                break


class _FileServiceSingleton:
    """Singleton holder for FileService instance."""

    _instance: FileService | None = None

    @classmethod
    def get_instance(cls) -> FileService:
        """Get the FileService singleton instance.

        Returns:
            The FileService instance
        """
        if cls._instance is None:
            cls._instance = FileService()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None


def get_file_service() -> FileService:
    """Get the FileService singleton instance.

    Returns:
        The FileService instance
    """
    return _FileServiceSingleton.get_instance()


def reset_file_service() -> None:
    """Reset the FileService singleton (for testing)."""
    _FileServiceSingleton.reset()
