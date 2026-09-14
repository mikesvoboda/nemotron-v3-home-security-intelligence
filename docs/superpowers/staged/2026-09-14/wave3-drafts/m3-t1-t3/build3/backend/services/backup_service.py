"""BackupService for creating full system backups.

This service provides functionality for creating ZIP archive backups of all
system data including events, alerts, cameras, zones, prompts, baselines,
household members, and settings.

Backup Format:
    - ZIP archive containing JSON files for each table
    - manifest.json with backup metadata and checksums
    - SHA256 checksums for integrity verification

Features:
    - Progress callbacks for UI updates
    - Configurable backup directory
    - Listing and deleting existing backups

See docs/plans/interfaces/backup-restore-interfaces.md for interface contracts.
"""

from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger
from backend.core.time_utils import utc_now
from backend.models.alert import Alert
from backend.models.baseline import ActivityBaseline, ClassBaseline
from backend.models.camera import Camera
from backend.models.camera_zone import CameraZone
from backend.models.gpu_config import SystemSetting
from backend.models.household import HouseholdMember
from backend.models.prompt_config import PromptConfig

logger = get_logger(__name__)


# Default backup directory
BACKUP_DIR = Path("/tmp/backups")  # noqa: S108


@dataclass
class BackupContentInfo:
    """Information about a single backup content type."""

    count: int
    checksum: str


@dataclass
class BackupManifest:
    """Manifest file stored inside backup ZIP."""

    backup_id: str
    version: str
    created_at: datetime
    app_version: str | None
    contents: dict[str, BackupContentInfo]

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary for JSON serialization."""
        return {
            "backup_id": self.backup_id,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "app_version": self.app_version,
            "contents": {
                name: {"count": info.count, "checksum": info.checksum}
                for name, info in self.contents.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupManifest:
        """Create manifest from dictionary."""
        contents = {
            name: BackupContentInfo(count=info["count"], checksum=info["checksum"])
            for name, info in data.get("contents", {}).items()
        }
        return cls(
            backup_id=data["backup_id"],
            version=data["version"],
            created_at=datetime.fromisoformat(data["created_at"]),
            app_version=data.get("app_version"),
            contents=contents,
        )


@dataclass
class BackupResult:
    """Result of a backup operation."""

    file_path: Path
    file_size: int
    manifest: BackupManifest


@dataclass
class BackupInfo:
    """Information about an existing backup file."""

    backup_id: str
    file_path: Path
    file_size: int
    created_at: datetime


class BackupService:
    """Service for creating full system backups.

    This service exports all system data to a ZIP archive with a manifest
    file containing checksums for integrity verification.

    Attributes:
        BACKUP_FORMAT_VERSION: Current backup format version
        BACKUP_DIR: Directory where backups are stored
        BACKUP_TABLES: List of (table_name, model_class) tuples to backup

    Example:
        service = BackupService()
        result = await service.create_backup(db, job_id="123")
        print(f"Backup created: {result.file_path}")
    """

    BACKUP_FORMAT_VERSION = "1.0"
    BACKUP_DIR = BACKUP_DIR

    # Tables to back up (in order)
    # Note: Using lazy loading to avoid import issues with Event model
    BACKUP_TABLES: ClassVar[list[tuple[str, type[Any]]]] = [
        ("alerts", Alert),
        ("cameras", Camera),
        ("zones", CameraZone),
        ("prompts", PromptConfig),
        ("activity_baselines", ActivityBaseline),
        ("class_baselines", ClassBaseline),
        ("household_members", HouseholdMember),
        ("settings", SystemSetting),
    ]

    def __init__(self, backup_dir: Path | None = None) -> None:
        """Initialize the backup service.

        Args:
            backup_dir: Optional custom backup directory. Defaults to BACKUP_DIR.
        """
        self._backup_dir = backup_dir or self.BACKUP_DIR
        # Ensure backup directory exists
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def _get_backup_tables(self) -> list[tuple[str, type[Any]]]:
        """Get the list of tables to backup with lazy Event import.

        Returns:
            List of (table_name, model_class) tuples.
        """
        # Import Event lazily to avoid circular imports
        from backend.models.event import Event

        return [
            ("events", Event),
            *self.BACKUP_TABLES,
        ]

    async def create_backup(
        self,
        db: AsyncSession,
        job_id: str,
        progress_callback: Callable[[int, str], Awaitable[None]] | None = None,
    ) -> BackupResult:
        """Create a full system backup.

        Exports all tables to JSON files, creates a manifest with checksums,
        and packages everything into a ZIP archive.

        Args:
            db: Database session for querying data.
            job_id: Backup job ID for tracking.
            progress_callback: Optional callback(percent, step_name) for progress updates.

        Returns:
            BackupResult with file_path, file_size, and manifest.

        Raises:
            IOError: If backup file cannot be written.
            Exception: If database query fails.
        """
        backup_tables = self._get_backup_tables()
        total_tables = len(backup_tables)
        contents: dict[str, BackupContentInfo] = {}

        # Create temp directory for staging backup files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Export each table
            for idx, (table_name, model) in enumerate(backup_tables):
                step_name = f"Exporting {table_name}"
                progress_percent = int((idx / total_tables) * 80)  # 0-80% for export

                if progress_callback:
                    await progress_callback(progress_percent, step_name)

                logger.info(
                    f"Exporting table: {table_name}",
                    extra={"job_id": job_id, "table": table_name},
                )

                # Export table to JSON file
                output_file = temp_path / f"{table_name}.json"
                count = await self._export_table(db, model, output_file)

                # Calculate checksum
                checksum = self._calculate_checksum(output_file)

                contents[table_name] = BackupContentInfo(count=count, checksum=checksum)

                logger.info(
                    f"Exported {count} records from {table_name}",
                    extra={
                        "job_id": job_id,
                        "table": table_name,
                        "count": count,
                        "checksum": checksum,
                    },
                )

            # Create manifest
            if progress_callback:
                await progress_callback(85, "Creating manifest")

            app_version = self._get_app_version()
            manifest = BackupManifest(
                backup_id=job_id,
                version=self.BACKUP_FORMAT_VERSION,
                created_at=utc_now(),
                app_version=app_version,
                contents=contents,
            )

            # Write manifest to temp directory
            manifest_file = temp_path / "manifest.json"
            manifest_file.write_text(
                json.dumps(manifest.to_dict(), indent=2),
                encoding="utf-8",
            )

            # Create ZIP archive
            if progress_callback:
                await progress_callback(90, "Creating ZIP archive")

            timestamp = manifest.created_at.strftime("%Y%m%d_%H%M%S")
            zip_filename = f"backup_{timestamp}_{job_id[:8]}.zip"
            zip_path = self._backup_dir / zip_filename

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add manifest first
                zf.write(manifest_file, "manifest.json")

                # Add all table JSON files
                for table_name, _ in backup_tables:
                    json_file = temp_path / f"{table_name}.json"
                    zf.write(json_file, f"{table_name}.json")

            if progress_callback:
                await progress_callback(95, "Finalizing backup")

            # Get file size
            file_size = zip_path.stat().st_size

            logger.info(
                "Backup created successfully",
                extra={
                    "job_id": job_id,
                    "file_path": str(zip_path),
                    "file_size": file_size,
                    "tables": list(contents.keys()),
                },
            )

            if progress_callback:
                await progress_callback(100, "Backup complete")

            return BackupResult(
                file_path=zip_path,
                file_size=file_size,
                manifest=manifest,
            )

    async def _export_table(
        self,
        db: AsyncSession,
        model: type[Any],
        output_path: Path,
    ) -> int:
        """Export a single table to JSON file.

        Exports all rows from the specified table as a JSON array.
        Handles datetime serialization and relationship exclusion.

        Args:
            db: Database session.
            model: SQLAlchemy model class.
            output_path: Path to write JSON file.

        Returns:
            Number of records exported.
        """
        # Query all records from the table
        stmt = select(model)
        result = await db.execute(stmt)
        records = result.scalars().all()

        # Convert records to dictionaries
        rows: list[dict[str, Any]] = []
        mapper = inspect(model)
        column_names = [col.key for col in mapper.columns]

        for record in records:
            row_dict: dict[str, Any] = {}
            for col_name in column_names:
                value = getattr(record, col_name, None)
                # Handle datetime serialization
                if isinstance(value, datetime):
                    row_dict[col_name] = value.isoformat()
                # Handle bytes (e.g., embeddings) - encode as base64
                elif isinstance(value, bytes):
                    row_dict[col_name] = base64.b64encode(value).decode("utf-8")
                # Handle enum values - check for Enum type explicitly
                elif value is not None and hasattr(type(value), "__mro__"):
                    import enum

                    if isinstance(value, enum.Enum):
                        row_dict[col_name] = value.value
                    else:
                        row_dict[col_name] = value
                else:
                    row_dict[col_name] = value
            rows.append(row_dict)

        # Write to JSON file
        output_path.write_text(
            json.dumps(rows, indent=2, default=str),
            encoding="utf-8",
        )

        return len(rows)

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file.

        Args:
            file_path: Path to the file.

        Returns:
            SHA256 checksum as hexadecimal string.
        """
        # Resolve path and validate it exists
        resolved_path = file_path.resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"File not found: {resolved_path}")

        sha256_hash = hashlib.sha256()
        # nosec: path is validated and resolved above
        with open(resolved_path, "rb") as f:  # nosemgrep: path-traversal-open
            # Read in 64KB chunks for memory efficiency
            for chunk in iter(lambda: f.read(65536), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _get_app_version(self) -> str | None:
        """Get the application version from pyproject.toml.

        Returns:
            Version string or None if not available.
        """
        try:
            import tomllib

            # Use resolved path for security
            pyproject_path = (Path(__file__).parent.parent.parent / "pyproject.toml").resolve()
            if pyproject_path.exists() and pyproject_path.name == "pyproject.toml":
                # nosec: path is hardcoded and validated
                with open(pyproject_path, "rb") as f:  # nosemgrep: path-traversal-open
                    data = tomllib.load(f)
                    version: str | None = data.get("project", {}).get("version")
                    return version
        except (ImportError, OSError, ValueError):
            pass
        return None

    def list_backups(self) -> list[BackupInfo]:
        """List available backup files.

        Scans the backup directory for ZIP files and extracts metadata
        from their manifests.

        Returns:
            List of BackupInfo objects sorted by creation time (newest first).
        """
        backups: list[BackupInfo] = []

        if not self._backup_dir.exists():
            return backups

        for file_path in self._backup_dir.glob("backup_*.zip"):
            try:
                # Extract manifest from ZIP
                with zipfile.ZipFile(file_path, "r") as zf:
                    manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))

                manifest = BackupManifest.from_dict(manifest_data)
                file_size = file_path.stat().st_size

                backups.append(
                    BackupInfo(
                        backup_id=manifest.backup_id,
                        file_path=file_path,
                        file_size=file_size,
                        created_at=manifest.created_at,
                    )
                )
            except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(
                    f"Failed to read backup file: {file_path}",
                    extra={"error": str(e), "file_path": str(file_path)},
                )
                continue

        # Sort by creation time, newest first
        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups

    def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup file.

        Args:
            backup_id: ID of the backup to delete.

        Returns:
            True if backup was deleted, False if not found.
        """
        # Find the backup file by ID
        backups = self.list_backups()
        for backup in backups:
            if backup.backup_id == backup_id:
                try:
                    backup.file_path.unlink()
                    logger.info(
                        f"Deleted backup: {backup_id}",
                        extra={"backup_id": backup_id, "file_path": str(backup.file_path)},
                    )
                    return True
                except OSError as e:
                    logger.error(
                        f"Failed to delete backup: {backup_id}",
                        extra={"backup_id": backup_id, "error": str(e)},
                    )
                    return False

        logger.warning(
            f"Backup not found: {backup_id}",
            extra={"backup_id": backup_id},
        )
        return False

    def get_backup_path(self, backup_id: str) -> Path | None:
        """Get the file path for a backup by ID.

        Args:
            backup_id: ID of the backup.

        Returns:
            Path to the backup file, or None if not found.
        """
        backups = self.list_backups()
        for backup in backups:
            if backup.backup_id == backup_id:
                return backup.file_path
        return None

    def cleanup_old_backups(self, max_age_days: int = 30, max_count: int = 10) -> int:
        """Clean up old backup files.

        Removes backups that exceed the maximum age or count limit.

        Args:
            max_age_days: Maximum age in days to keep backups.
            max_count: Maximum number of backups to keep.

        Returns:
            Number of backups deleted.
        """
        from datetime import timedelta

        backups = self.list_backups()
        deleted_count = 0
        now = utc_now()
        cutoff_date = now - timedelta(days=max_age_days)

        # Delete backups older than max_age_days
        for backup in backups:
            if backup.created_at < cutoff_date:
                if self.delete_backup(backup.backup_id):
                    deleted_count += 1

        # Refresh list and delete excess backups
        backups = self.list_backups()
        if len(backups) > max_count:
            # Delete oldest backups to maintain max_count
            for backup in backups[max_count:]:
                if self.delete_backup(backup.backup_id):
                    deleted_count += 1

        if deleted_count > 0:
            logger.info(
                f"Cleaned up {deleted_count} old backups",
                extra={"deleted_count": deleted_count},
            )

        return deleted_count


# Global service instance
_backup_service: BackupService | None = None


def get_backup_service() -> BackupService:
    """Get or create the global BackupService instance.

    Returns:
        BackupService singleton instance.
    """
    global _backup_service  # noqa: PLW0603
    if _backup_service is None:
        _backup_service = BackupService()
    return _backup_service


def reset_backup_service() -> None:
    """Reset the global BackupService instance (for testing)."""
    global _backup_service  # noqa: PLW0603
    _backup_service = None
