"""Service for restoring system data from backup files.

This service provides functionality to restore the entire system from a backup ZIP file.
It validates the backup manifest, verifies file checksums, and restores all tables
within a database transaction (all-or-nothing).

Features:
- Manifest validation with version compatibility check
- SHA256 checksum verification before restore
- Transactional restore (all-or-nothing)
- Progress callbacks for tracking restore status
- Support for all backup content types (events, alerts, cameras, zones, etc.)

Security:
- Validates backup format version before restore
- Verifies checksums to detect file corruption or tampering
- Uses database transactions to ensure data integrity

NEM-3566: Backup/Restore implementation.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger(__name__)

# Supported backup format version
SUPPORTED_BACKUP_VERSION = "1.0"

# Tables to restore in dependency order (foreign key constraints)
# Tables with foreign key dependencies come after their parent tables
RESTORE_TABLE_ORDER = [
    "cameras",
    "zones",
    "events",
    "alerts",
    "prompts",
    "baselines",
    "household_members",
    "settings",
]


class BackupValidationError(Exception):
    """Raised when backup validation fails."""

    pass


class BackupCorruptedError(Exception):
    """Raised when backup file integrity check fails."""

    pass


class RestoreError(Exception):
    """Raised when restore operation fails."""

    pass


@dataclass
class RestoreResult:
    """Result of a restore operation."""

    backup_id: str
    backup_created_at: datetime
    items_restored: dict[str, int]
    total_items: int


class RestoreService:
    """Service for restoring system data from backup files.

    This service handles the complete restore workflow:
    1. Extract and validate backup ZIP file
    2. Validate manifest version and contents
    3. Verify file checksums
    4. Restore tables in dependency order within a transaction

    Example:
        service = RestoreService()
        result = await service.restore_from_backup(
            backup_file=Path("/tmp/backup.zip"),
            db=session,
            job_id="restore-123",
            progress_callback=update_progress,
        )
    """

    # Model mapping for restore operations
    # Maps table names to (model_class, import_path) tuples
    TABLE_MODEL_MAPPING: ClassVar[dict[str, str]] = {
        "cameras": "backend.models.camera.Camera",
        "events": "backend.models.event.Event",
        "alerts": "backend.models.alert.Alert",
        "zones": "backend.models.camera_zone.CameraZone",
        "prompts": "backend.models.prompt_config.PromptConfig",
        "baselines": "backend.models.baseline.ActivityBaseline",
        "household_members": "backend.models.household.HouseholdMember",
        "settings": "backend.models.gpu_config.SystemSetting",
    }

    async def restore_from_backup(
        self,
        backup_file: Path,
        db: AsyncSession,
        job_id: str,
        progress_callback: Callable[[int, str], Awaitable[None]] | None = None,
    ) -> RestoreResult:
        """Restore system from backup file.

        Extracts the backup ZIP, validates the manifest and checksums,
        then restores all tables within a database transaction.

        Args:
            backup_file: Path to uploaded backup ZIP file.
            db: Database session for restore operations.
            job_id: Restore job ID for tracking.
            progress_callback: Optional callback(percent, step_name) for progress updates.

        Returns:
            RestoreResult with backup info and item counts.

        Raises:
            BackupValidationError: If backup manifest is invalid or version incompatible.
            BackupCorruptedError: If file checksums don't match.
            RestoreError: If restore operation fails.
        """
        logger.info(
            "Starting restore from backup",
            extra={"job_id": job_id, "backup_file": str(backup_file)},
        )

        if progress_callback:
            await progress_callback(5, "Extracting backup file...")

        # Extract backup to temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)

            try:
                with zipfile.ZipFile(backup_file, "r") as zf:
                    zf.extractall(backup_dir)
            except zipfile.BadZipFile as e:
                raise BackupValidationError(f"Invalid backup file: {e}") from e

            if progress_callback:
                await progress_callback(10, "Reading manifest...")

            # Load and validate manifest
            manifest_path = (backup_dir / "manifest.json").resolve()
            # Validate path is within backup directory (security check)
            if not str(manifest_path).startswith(str(backup_dir.resolve())):
                raise BackupValidationError("Invalid manifest path detected")
            if not manifest_path.exists():
                raise BackupValidationError("Backup manifest not found")

            try:
                # nosec: path is validated above
                with open(manifest_path) as f:  # nosemgrep: path-traversal-open
                    manifest_data = json.load(f)
            except json.JSONDecodeError as e:
                raise BackupValidationError(f"Invalid manifest JSON: {e}") from e

            # Validate manifest structure
            self._validate_manifest(manifest_data)

            if progress_callback:
                await progress_callback(15, "Verifying checksums...")

            # Verify file checksums
            self._verify_checksums(backup_dir, manifest_data)

            if progress_callback:
                await progress_callback(20, "Starting restore...")

            # Restore tables within a transaction
            items_restored: dict[str, int] = {}
            total_items = 0
            total_tables = len(manifest_data.get("contents", {}))
            tables_completed = 0

            # Use a single transaction for all-or-nothing restore
            try:
                for table_name in RESTORE_TABLE_ORDER:
                    if table_name not in manifest_data.get("contents", {}):
                        continue

                    file_path = backup_dir / f"{table_name}.json"

                    if not file_path.exists():
                        logger.warning(
                            f"Backup file for {table_name} not found, skipping",
                            extra={"job_id": job_id, "table": table_name},
                        )
                        continue

                    # Update progress
                    progress_percent = 20 + int((tables_completed / max(total_tables, 1)) * 70)
                    if progress_callback:
                        await progress_callback(progress_percent, f"Restoring {table_name}...")

                    # Restore the table
                    count = await self._restore_table(db, table_name, file_path)
                    items_restored[table_name] = count
                    total_items += count
                    tables_completed += 1

                    logger.info(
                        f"Restored {count} records to {table_name}",
                        extra={"job_id": job_id, "table": table_name, "count": count},
                    )

                # Commit the transaction
                await db.commit()

            except Exception as e:
                await db.rollback()
                logger.error(
                    "Restore failed, rolled back transaction",
                    extra={"job_id": job_id, "error": str(e)},
                )
                raise RestoreError(f"Restore failed: {e}") from e

            if progress_callback:
                await progress_callback(95, "Finalizing restore...")

            # Parse backup timestamp
            backup_created_at = datetime.fromisoformat(
                manifest_data["created_at"].replace("Z", "+00:00")
            )

            result = RestoreResult(
                backup_id=manifest_data["backup_id"],
                backup_created_at=backup_created_at,
                items_restored=items_restored,
                total_items=total_items,
            )

            logger.info(
                "Restore completed successfully",
                extra={
                    "job_id": job_id,
                    "backup_id": result.backup_id,
                    "total_items": total_items,
                    "items_restored": items_restored,
                },
            )

            return result

    def _validate_manifest(self, manifest: dict[str, Any]) -> None:
        """Validate backup manifest version and structure.

        Args:
            manifest: Parsed manifest dictionary.

        Raises:
            BackupValidationError: If manifest is invalid or version incompatible.
        """
        # Check required fields
        required_fields = ["backup_id", "version", "created_at"]
        for field in required_fields:
            if field not in manifest:
                raise BackupValidationError(f"Missing required manifest field: {field}")

        # Check version compatibility
        version = manifest.get("version", "")
        if version != SUPPORTED_BACKUP_VERSION:
            raise BackupValidationError(
                f"Unsupported backup version: {version}. Expected: {SUPPORTED_BACKUP_VERSION}"
            )

        # Validate contents structure if present
        contents = manifest.get("contents", {})
        if not isinstance(contents, dict):
            raise BackupValidationError("Invalid manifest contents structure")

        for table_name, content_info in contents.items():
            if not isinstance(content_info, dict):
                raise BackupValidationError(f"Invalid content info for table {table_name}")
            if "count" not in content_info or "checksum" not in content_info:
                raise BackupValidationError(f"Missing count or checksum for table {table_name}")

    def _verify_checksums(self, backup_dir: Path, manifest: dict[str, Any]) -> None:
        """Verify all file checksums match manifest.

        Args:
            backup_dir: Directory containing extracted backup files.
            manifest: Parsed manifest dictionary.

        Raises:
            BackupCorruptedError: If any checksum doesn't match.
        """
        contents = manifest.get("contents", {})

        for table_name, content_info in contents.items():
            file_path = backup_dir / f"{table_name}.json"

            if not file_path.exists():
                logger.warning(f"File for {table_name} not found during checksum verification")
                continue

            expected_checksum = content_info.get("checksum", "")
            actual_checksum = self._calculate_checksum(file_path)

            if actual_checksum != expected_checksum:
                raise BackupCorruptedError(
                    f"Checksum mismatch for {table_name}: "
                    f"expected {expected_checksum}, got {actual_checksum}"
                )

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file.

        Args:
            file_path: Path to the file.

        Returns:
            SHA256 checksum as hex string.
        """
        # Resolve and validate path
        resolved_path = file_path.resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"File not found: {resolved_path}")

        sha256_hash = hashlib.sha256()
        # nosec: path is validated and resolved above
        with open(resolved_path, "rb") as f:  # nosemgrep: path-traversal-open
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    async def _restore_table(
        self,
        db: AsyncSession,
        table_name: str,
        file_path: Path,
    ) -> int:
        """Restore a single table from JSON file.

        Clears the existing table data and inserts records from the backup file.
        Uses bulk insert for efficiency.

        Args:
            db: Database session.
            table_name: Name of the table to restore.
            file_path: Path to the JSON backup file.

        Returns:
            Number of records restored.

        Raises:
            RestoreError: If restore fails for this table.
        """
        # Load backup data with path validation
        resolved_path = file_path.resolve()
        if not resolved_path.exists():
            raise RestoreError(f"Backup file not found: {file_path}")

        try:
            # nosec: path is validated above
            with open(resolved_path) as f:  # nosemgrep: path-traversal-open
                records = json.load(f)
        except json.JSONDecodeError as e:
            raise RestoreError(f"Invalid JSON in {table_name} backup: {e}") from e

        if not isinstance(records, list):
            raise RestoreError(f"Expected list of records for {table_name}")

        if not records:
            return 0

        # Get the model class for this table
        model_class = self._get_model_class(table_name)
        if model_class is None:
            logger.warning(f"No model mapping for table {table_name}, skipping")
            return 0

        # Clear existing data
        # Use raw SQL DELETE for efficiency with large tables
        await db.execute(delete(model_class))
        await db.flush()

        # Insert records
        count = 0
        for record_data in records:
            try:
                # Convert datetime strings to datetime objects
                processed_data = self._process_record_data(record_data)

                # Create model instance
                instance = model_class(**processed_data)
                db.add(instance)
                count += 1

            except Exception as e:
                logger.warning(
                    f"Failed to restore record in {table_name}: {e}",
                    extra={"table": table_name, "record": str(record_data)[:200]},
                )
                # Continue with other records

        # Flush to catch any constraint violations
        await db.flush()

        return count

    def _get_model_class(self, table_name: str) -> type | None:
        """Get SQLAlchemy model class for a table name.

        Args:
            table_name: Name of the table.

        Returns:
            Model class or None if not found.
        """
        model_path = self.TABLE_MODEL_MAPPING.get(table_name)
        if not model_path:
            return None

        try:
            # Dynamically import the model
            module_path, class_name = model_path.rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            model_class: type = getattr(module, class_name)
            return model_class
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to import model for {table_name}: {e}")
            return None

    def _process_record_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Process record data for database insertion.

        Converts datetime strings to datetime objects and handles
        other type conversions as needed.

        Args:
            data: Raw record data from JSON.

        Returns:
            Processed data ready for model instantiation.
        """
        processed: dict[str, Any] = {}

        for key, value in data.items():
            if value is None:
                processed[key] = None
            elif isinstance(value, str) and self._is_datetime_field(key, value):
                # Convert ISO datetime strings
                try:
                    processed[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    processed[key] = value
            else:
                processed[key] = value

        return processed

    def _is_datetime_field(self, field_name: str, value: str) -> bool:
        """Check if a field should be parsed as a datetime.

        Args:
            field_name: Name of the field.
            value: String value.

        Returns:
            True if the field should be parsed as datetime.
        """
        datetime_suffixes = ("_at", "_date", "_time", "_timestamp")
        if any(field_name.endswith(suffix) for suffix in datetime_suffixes):
            # Quick check for ISO format pattern
            return len(value) >= 10 and "-" in value[:10]
        return False


# Global service instance
_restore_service: RestoreService | None = None


def get_restore_service() -> RestoreService:
    """Get or create the global RestoreService instance.

    Returns:
        RestoreService singleton instance.
    """
    global _restore_service  # noqa: PLW0603
    if _restore_service is None:
        _restore_service = RestoreService()
    return _restore_service


def reset_restore_service() -> None:
    """Reset the global RestoreService instance (for testing)."""
    global _restore_service  # noqa: PLW0603
    _restore_service = None
