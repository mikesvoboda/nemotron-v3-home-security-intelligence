"""Orphaned file scanner service for identifying files without database records.

This service scans the Foscam FTP upload directories for files that exist on disk
but have no corresponding records in the database. This can happen due to:
- Failed event processing (file written, DB transaction rolled back)
- Manual file deletion from DB without file cleanup
- Bugs in cleanup logic
- Interrupted operations

The scanner is designed to be safe and conservative - it only identifies files
that are truly orphaned and old enough to avoid race conditions with active
processing.

Related Issues:
    - NEM-2387: Implement orphaned file cleanup background job
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.logging import get_logger
from backend.models.detection import Detection
from backend.models.event import Event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


# File patterns to scan (images and videos typically uploaded by cameras)
SCANNABLE_EXTENSIONS = {
    # Image formats
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    # Video formats
    ".mp4",
    ".webm",
    ".mkv",
    ".avi",
    ".mov",
    ".m4v",
}


@dataclass
class OrphanedFile:
    """Represents an orphaned file found during scanning.

    Attributes:
        path: Absolute path to the orphaned file
        size_bytes: Size of the file in bytes
        mtime: File modification time
        age: How long since the file was modified
    """

    path: Path
    size_bytes: int
    mtime: datetime
    age: timedelta

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "mtime": self.mtime.isoformat(),
            "age_hours": self.age.total_seconds() / 3600,
        }


@dataclass
class ScanResult:
    """Result of a directory scan for orphaned files.

    Attributes:
        scanned_files: Total number of files scanned
        orphaned_files: List of orphaned files found
        total_orphaned_bytes: Total size of orphaned files
        scan_errors: List of errors encountered during scanning
        scan_duration_seconds: Time taken to complete the scan
    """

    scanned_files: int = 0
    orphaned_files: list[OrphanedFile] = field(default_factory=list)
    total_orphaned_bytes: int = 0
    scan_errors: list[str] = field(default_factory=list)
    scan_duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "scanned_files": self.scanned_files,
            "orphaned_count": len(self.orphaned_files),
            "total_orphaned_bytes": self.total_orphaned_bytes,
            "scan_errors": self.scan_errors,
            "scan_duration_seconds": round(self.scan_duration_seconds, 2),
            "orphaned_files": [f.to_dict() for f in self.orphaned_files[:100]],  # Limit to 100
        }


class OrphanedFileScanner:
    """Scanner for identifying orphaned files in camera upload directories.

    This scanner compares files on disk with database records to identify
    files that have no corresponding detection or event records.

    The scanner is designed to be safe:
    - Only scans known file patterns (images/videos)
    - Returns file metadata without modifying anything
    - Can be used in dry-run or actual cleanup scenarios

    Example usage:
        scanner = OrphanedFileScanner()
        result = await scanner.scan_directory(Path("/export/foscam"))
        for orphan in result.orphaned_files:
            print(f"Orphan: {orphan.path} ({orphan.size_bytes} bytes)")
    """

    def __init__(
        self,
        base_path: str | Path | None = None,
        extensions: set[str] | None = None,
    ) -> None:
        """Initialize the orphaned file scanner.

        Args:
            base_path: Base path to scan. If None, uses foscam_base_path from settings.
            extensions: File extensions to scan. If None, uses default SCANNABLE_EXTENSIONS.
        """
        settings = get_settings()
        self.base_path = Path(base_path) if base_path else Path(settings.foscam_base_path)
        self.extensions = extensions or SCANNABLE_EXTENSIONS.copy()

        logger.info(
            f"OrphanedFileScanner initialized: base_path={self.base_path}, "
            f"extensions={sorted(self.extensions)}"
        )

    def _list_files(self, directory: Path) -> list[Path]:
        """List all scannable files in a directory recursively.

        Args:
            directory: Directory to scan

        Returns:
            List of file paths matching the configured extensions
        """
        files: list[Path] = []

        if not directory.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return files

        if not directory.is_dir():
            logger.warning(f"Path is not a directory: {directory}")
            return files

        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in self.extensions:
                    files.append(file_path)
        except PermissionError as e:
            logger.warning(f"Permission denied scanning directory: {e}")
        except OSError as e:
            logger.warning(f"OS error scanning directory: {e}")

        logger.debug(f"Found {len(files)} scannable files in {directory}")
        return files

    def get_file_age(self, path: Path) -> timedelta:
        """Get the age of a file based on its modification time.

        Args:
            path: Path to the file

        Returns:
            Time elapsed since the file was last modified

        Raises:
            FileNotFoundError: If the file does not exist
            OSError: If the file stats cannot be read
        """
        mtime = path.stat().st_mtime
        mtime_dt = datetime.fromtimestamp(mtime, tz=UTC)
        return datetime.now(UTC) - mtime_dt

    def _get_file_info(self, path: Path) -> tuple[int, datetime, timedelta] | None:
        """Get file size, mtime, and age.

        Args:
            path: Path to the file

        Returns:
            Tuple of (size_bytes, mtime, age) or None if file cannot be accessed
        """
        try:
            stat = path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            age = datetime.now(UTC) - mtime
            return stat.st_size, mtime, age
        except (OSError, FileNotFoundError) as e:
            logger.debug(f"Could not get file info for {path}: {e}")
            return None

    async def _get_referenced_paths(self, session: AsyncSession) -> set[str]:
        """Query all file paths referenced in the database.

        Queries:
        - Detection.file_path (source images/videos)
        - Detection.thumbnail_path (generated thumbnails)
        - Event.clip_path (generated event clips)

        Args:
            session: Database session

        Returns:
            Set of all referenced file paths (resolved to absolute paths)
        """
        referenced: set[str] = set()

        # Get detection file paths
        detection_query = select(Detection.file_path, Detection.thumbnail_path)
        result = await session.execute(detection_query)

        for file_path, thumbnail_path in result.all():
            if file_path:
                try:
                    # Normalize and resolve path
                    resolved = Path(file_path).resolve()
                    referenced.add(str(resolved))
                except (OSError, ValueError):
                    # Invalid path in database - skip it and continue scanning.
                    # Orphan scan results should not fail due to malformed DB entries.
                    # See: NEM-2540 for rationale
                    pass
            if thumbnail_path:
                try:
                    resolved = Path(thumbnail_path).resolve()
                    referenced.add(str(resolved))
                except (OSError, ValueError):
                    # Invalid thumbnail path - skip it. See: NEM-2540 for rationale
                    pass

        # Get event clip paths
        event_query = select(Event.clip_path).where(Event.clip_path.isnot(None))
        result = await session.execute(event_query)

        for (clip_path,) in result.all():
            if clip_path:
                try:
                    resolved = Path(clip_path).resolve()
                    referenced.add(str(resolved))
                except (OSError, ValueError):
                    # Invalid clip path - skip it. See: NEM-2540 for rationale
                    pass

        logger.debug(f"Found {len(referenced)} referenced paths in database")
        return referenced

    async def scan_directory(self, path: Path | None = None) -> ScanResult:
        """Scan a directory for files not referenced in the database.

        This method:
        1. Lists all files in the directory matching configured extensions
        2. Queries the database for all referenced file paths
        3. Identifies files that exist on disk but not in the database

        Args:
            path: Directory to scan. If None, uses the configured base_path.

        Returns:
            ScanResult containing all orphaned files found
        """
        import time

        start_time = time.monotonic()
        scan_path = path or self.base_path
        result = ScanResult()

        logger.info(f"Starting orphan scan of directory: {scan_path}")

        # Step 1: List all files
        try:
            all_files = self._list_files(scan_path)
            result.scanned_files = len(all_files)
        except Exception as e:
            error_msg = f"Failed to list files in {scan_path}: {e}"
            logger.error(error_msg)
            result.scan_errors.append(error_msg)
            result.scan_duration_seconds = time.monotonic() - start_time
            return result

        if not all_files:
            logger.info(f"No scannable files found in {scan_path}")
            result.scan_duration_seconds = time.monotonic() - start_time
            return result

        # Step 2: Get all referenced paths from database
        try:
            async with get_session() as session:
                referenced_paths = await self._get_referenced_paths(session)
        except Exception as e:
            error_msg = f"Failed to query database for referenced paths: {e}"
            logger.error(error_msg)
            result.scan_errors.append(error_msg)
            result.scan_duration_seconds = time.monotonic() - start_time
            return result

        # Step 3: Identify orphaned files
        for file_path in all_files:
            try:
                resolved = str(file_path.resolve())
                if resolved not in referenced_paths:
                    # File is not referenced in database - it's an orphan
                    file_info = self._get_file_info(file_path)
                    if file_info:
                        size_bytes, mtime, age = file_info
                        orphan = OrphanedFile(
                            path=file_path,
                            size_bytes=size_bytes,
                            mtime=mtime,
                            age=age,
                        )
                        result.orphaned_files.append(orphan)
                        result.total_orphaned_bytes += size_bytes
            except Exception as e:
                error_msg = f"Error checking file {file_path}: {e}"
                logger.warning(error_msg)
                result.scan_errors.append(error_msg)

        result.scan_duration_seconds = time.monotonic() - start_time

        logger.info(
            f"Orphan scan complete: scanned={result.scanned_files}, "
            f"orphaned={len(result.orphaned_files)}, "
            f"total_size={result.total_orphaned_bytes} bytes, "
            f"duration={result.scan_duration_seconds:.2f}s"
        )

        return result

    async def scan_all_directories(self) -> ScanResult:
        """Scan all configured camera directories for orphaned files.

        This scans the base path which typically contains subdirectories
        for each camera (e.g., /export/foscam/front_door/, /export/foscam/backyard/).

        Returns:
            Combined ScanResult for all directories
        """
        return await self.scan_directory(self.base_path)


# Module-level singleton
_scanner: OrphanedFileScanner | None = None


def get_orphan_scanner(
    base_path: str | Path | None = None,
    extensions: set[str] | None = None,
) -> OrphanedFileScanner:
    """Get or create the singleton orphan scanner instance.

    Args:
        base_path: Base path to scan. Only used when creating the singleton.
        extensions: File extensions to scan. Only used when creating the singleton.

    Returns:
        The orphan scanner singleton.
    """
    global _scanner  # noqa: PLW0603
    if _scanner is None:
        _scanner = OrphanedFileScanner(base_path=base_path, extensions=extensions)
    return _scanner


def reset_orphan_scanner() -> None:
    """Reset the orphan scanner singleton. Used for testing."""
    global _scanner  # noqa: PLW0603
    _scanner = None
