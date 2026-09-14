"""File cleanup service for cascade file deletion when events are deleted.

This module provides the FileCleanupService class for cleaning up media files
associated with events when they are deleted. It handles:
- Getting all file paths associated with an event
- Deleting individual event files with result tracking
- Batch deletion for retention cleanup efficiency

File Types Handled:
- Original images: /export/foscam/{camera}/snap_{timestamp}.jpg
- Thumbnails: /export/foscam/{camera}/thumb_{event_id}.jpg
- Video clips: /export/foscam/{camera}/clip_{event_id}.mp4
- AI annotation overlays: /export/foscam/{camera}/annotated_{event_id}.jpg

Related Linear issue: NEM-2384
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models.event import Event

logger = get_logger(__name__)


@dataclass
class FileCleanupResult:
    """Result of a file cleanup operation for a single event.

    Attributes:
        event_id: The event ID that was cleaned up
        deleted: List of file paths that were successfully deleted
        missing: List of file paths that didn't exist (already deleted or never created)
        failed: List of file paths that failed to delete with error messages
        total_bytes_freed: Estimated bytes freed by deletion (0 if unknown)
    """

    event_id: int | UUID
    deleted: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (path, error_message)
    total_bytes_freed: int = 0

    @property
    def success(self) -> bool:
        """Check if cleanup was successful (no failures)."""
        return len(self.failed) == 0

    @property
    def total_files(self) -> int:
        """Get total number of files processed."""
        return len(self.deleted) + len(self.missing) + len(self.failed)

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/API responses."""
        return {
            "event_id": str(self.event_id),
            "deleted_count": len(self.deleted),
            "missing_count": len(self.missing),
            "failed_count": len(self.failed),
            "total_bytes_freed": self.total_bytes_freed,
            "success": self.success,
            "failed_files": [(path, error) for path, error in self.failed],
        }


@dataclass
class BatchCleanupResult:
    """Result of a batch file cleanup operation for multiple events.

    Attributes:
        event_ids: List of event IDs that were processed
        total_deleted: Total number of files deleted across all events
        total_missing: Total number of files that were missing
        total_failed: Total number of files that failed to delete
        total_bytes_freed: Estimated bytes freed by deletion
        per_event_results: Individual results for each event
    """

    event_ids: list[int | UUID] = field(default_factory=list)
    total_deleted: int = 0
    total_missing: int = 0
    total_failed: int = 0
    total_bytes_freed: int = 0
    per_event_results: list[FileCleanupResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if batch cleanup was successful (no failures)."""
        return self.total_failed == 0

    @property
    def events_processed(self) -> int:
        """Get total number of events processed."""
        return len(self.event_ids)

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/API responses."""
        return {
            "events_processed": self.events_processed,
            "total_deleted": self.total_deleted,
            "total_missing": self.total_missing,
            "total_failed": self.total_failed,
            "total_bytes_freed": self.total_bytes_freed,
            "success": self.success,
        }


class FileCleanupService:
    """Service for cleaning up media files associated with events.

    This service provides methods to delete files associated with events
    during event deletion or retention cleanup. It handles:
    - Individual event file cleanup
    - Batch cleanup for retention policy
    - Error tracking and reporting
    - Safe handling of missing files

    The service does NOT fail if files are missing - this is expected
    behavior when files have already been deleted or never existed.
    """

    def __init__(self, base_path: str | None = None):
        """Initialize the file cleanup service.

        Args:
            base_path: Optional base path for resolving relative file paths.
                If not provided, uses paths as-is (absolute paths expected).
        """
        self._base_path = Path(base_path) if base_path else None

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve a file path to an absolute path.

        Args:
            file_path: The file path to resolve

        Returns:
            Resolved absolute Path object
        """
        path = Path(file_path)
        if self._base_path and not path.is_absolute():
            return self._base_path / path
        return path

    def _collect_event_file_paths(self, event: Event) -> list[str]:
        """Collect all file paths associated with an event.

        This method gathers file paths from:
        - Event clip path
        - Detection file paths (original images)
        - Detection thumbnail paths

        Args:
            event: Event model with detections relationship loaded

        Returns:
            List of file paths (may include None/empty, filtered by caller)
        """
        file_paths: list[str] = []

        # Add event clip path if exists
        if event.clip_path:
            file_paths.append(event.clip_path)

        # Add detection file paths and thumbnails
        # Note: Event.detections relationship should be loaded
        for detection in event.detections:
            if detection.file_path:
                file_paths.append(detection.file_path)
            if detection.thumbnail_path:
                file_paths.append(detection.thumbnail_path)

        return file_paths

    async def get_event_files(
        self,
        event_id: int | UUID,
        db: AsyncSession,
    ) -> list[Path]:
        """Get all file paths associated with an event.

        Fetches the event from the database with detections loaded
        and returns all associated file paths.

        Args:
            event_id: ID of the event to get files for
            db: Database session

        Returns:
            List of Path objects for files associated with the event.
            Returns empty list if event not found.
        """
        from backend.models.event import Event

        # Fetch event with detections
        stmt = (
            select(Event).options(selectinload(Event.detections)).where(Event.id == int(event_id))
        )
        result = await db.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            logger.warning(f"Event not found for file lookup: {event_id}")
            return []

        # Collect file paths
        file_paths = self._collect_event_file_paths(event)

        # Filter and resolve paths
        resolved_paths: list[Path] = []
        for path_str in file_paths:
            if path_str:
                resolved_paths.append(self._resolve_path(path_str))

        return resolved_paths

    def _delete_single_file(self, file_path: Path) -> tuple[bool, str | None, int]:
        """Delete a single file and return the result.

        Args:
            file_path: Path to the file to delete

        Returns:
            Tuple of (deleted, error_message, bytes_freed)
            - deleted: True if file was deleted, False otherwise
            - error_message: Error message if deletion failed, None otherwise
            - bytes_freed: Size of deleted file in bytes, 0 if not deleted
        """
        try:
            if not file_path.exists():
                return False, None, 0  # Missing, not an error

            # Get file size before deletion
            try:
                file_size = file_path.stat().st_size
            except OSError:
                file_size = 0

            # Delete the file
            file_path.unlink()
            logger.debug(f"Deleted file: {file_path}")
            return True, None, file_size

        except PermissionError as e:
            error_msg = f"Permission denied: {e}"
            logger.warning(f"Failed to delete {file_path}: {error_msg}")
            return False, error_msg, 0

        except OSError as e:
            error_msg = f"OS error: {e}"
            logger.warning(f"Failed to delete {file_path}: {error_msg}")
            return False, error_msg, 0

    async def delete_event_files(
        self,
        event_id: int | UUID,
        db: AsyncSession,
    ) -> FileCleanupResult:
        """Delete all files associated with an event.

        This method:
        1. Fetches all file paths for the event
        2. Deletes each file, tracking success/failure
        3. Returns detailed results

        Missing files are logged but not treated as errors - they may have
        already been deleted or never existed.

        Args:
            event_id: ID of the event whose files should be deleted
            db: Database session

        Returns:
            FileCleanupResult with deletion statistics and any errors
        """
        result = FileCleanupResult(event_id=event_id)

        # Get all files for this event
        file_paths = await self.get_event_files(event_id, db)

        if not file_paths:
            logger.debug(f"No files to delete for event {event_id}")
            return result

        # Delete each file
        for file_path in file_paths:
            deleted, error, bytes_freed = self._delete_single_file(file_path)

            if deleted:
                result.deleted.append(str(file_path))
                result.total_bytes_freed += bytes_freed
            elif error:
                result.failed.append((str(file_path), error))
            else:
                # File was missing (not an error)
                result.missing.append(str(file_path))

        # Log summary
        if result.deleted or result.failed:
            logger.info(
                f"Event {event_id} file cleanup: "
                f"{len(result.deleted)} deleted, "
                f"{len(result.missing)} missing, "
                f"{len(result.failed)} failed"
            )

        return result

    async def delete_files_batch(
        self,
        event_ids: list[int | UUID],
        db: AsyncSession,
    ) -> BatchCleanupResult:
        """Batch delete files for multiple events.

        Efficiently processes multiple events for retention cleanup,
        tracking per-event results and aggregating statistics.

        Args:
            event_ids: List of event IDs whose files should be deleted
            db: Database session

        Returns:
            BatchCleanupResult with aggregated statistics and per-event details
        """
        batch_result = BatchCleanupResult(event_ids=list(event_ids))

        if not event_ids:
            return batch_result

        logger.info(f"Starting batch file cleanup for {len(event_ids)} events")

        for event_id in event_ids:
            event_result = await self.delete_event_files(event_id, db)
            batch_result.per_event_results.append(event_result)

            # Aggregate statistics
            batch_result.total_deleted += len(event_result.deleted)
            batch_result.total_missing += len(event_result.missing)
            batch_result.total_failed += len(event_result.failed)
            batch_result.total_bytes_freed += event_result.total_bytes_freed

        # Log summary
        logger.info(
            f"Batch cleanup complete: "
            f"{batch_result.events_processed} events, "
            f"{batch_result.total_deleted} files deleted, "
            f"{batch_result.total_missing} missing, "
            f"{batch_result.total_failed} failed, "
            f"{batch_result.total_bytes_freed} bytes freed"
        )

        return batch_result

    async def delete_files_by_paths(
        self,
        file_paths: list[str],
        event_id: int | UUID | None = None,
    ) -> FileCleanupResult:
        """Delete files by their paths directly (no database lookup).

        This method is useful when the file paths are already known
        and a database lookup is not needed.

        Args:
            file_paths: List of file paths to delete
            event_id: Optional event ID for logging purposes

        Returns:
            FileCleanupResult with deletion statistics
        """
        result = FileCleanupResult(event_id=event_id or 0)

        for path_str in file_paths:
            if not path_str:
                continue

            file_path = self._resolve_path(path_str)
            deleted, error, bytes_freed = self._delete_single_file(file_path)

            if deleted:
                result.deleted.append(str(file_path))
                result.total_bytes_freed += bytes_freed
            elif error:
                result.failed.append((str(file_path), error))
            else:
                result.missing.append(str(file_path))

        return result


class _FileCleanupServiceSingleton:
    """Singleton holder for FileCleanupService instance.

    This class-based approach avoids using global statements,
    which are discouraged by PLW0603 linter rule.
    """

    _instance: FileCleanupService | None = None

    @classmethod
    def get_instance(cls) -> FileCleanupService:
        """Get the FileCleanupService singleton instance.

        Returns:
            The FileCleanupService instance
        """
        if cls._instance is None:
            cls._instance = FileCleanupService()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None


def get_file_cleanup_service() -> FileCleanupService:
    """Get the FileCleanupService singleton instance.

    Returns:
        The FileCleanupService instance
    """
    return _FileCleanupServiceSingleton.get_instance()


def reset_file_cleanup_service() -> None:
    """Reset the FileCleanupService singleton (for testing)."""
    _FileCleanupServiceSingleton.reset()
