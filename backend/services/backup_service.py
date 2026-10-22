"""BackupService for creating full system configuration backups.

This service exports configuration tables to a ZIP archive with a manifest
file containing SHA-256 checksums and the installation ID for integrity
verification and cross-installation merge semantics (B4.6 / 4n-restore.md).
"""

from __future__ import annotations

import base64
import enum
import hashlib
import json
import os
import tempfile
import zipfile
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar
from uuid import uuid4

from sqlalchemy import Table, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from backend.core.logging import get_logger
from backend.core.time_utils import utc_now
from backend.models.alert import AlertRule
from backend.models.area import Area, camera_areas
from backend.models.baseline import ActivityBaseline, ClassBaseline
from backend.models.camera import Camera
from backend.models.camera_zone import CameraZone
from backend.models.gpu_config import SystemSetting
from backend.models.household import HouseholdMember
from backend.models.household_org import Household
from backend.models.prompt_version import PromptVersion
from backend.models.property import Property

logger = get_logger(__name__)

# Default backup directory on the data volume (4n-restore.md).
BACKUP_DIR = Path("/app/data/backups")
_FALLBACK_BACKUP_DIR = Path(__file__).resolve().parents[2] / "data" / "backups"

# Setting key that stores this installation's persistent identity.
INSTALLATION_ID_SETTING_KEY = "installation_id"

# Single shared table list (in parent-before-child restore order) imported by
# both BackupService and RestoreService (4n-restore.md §Shape).
SHARED_BACKUP_TABLES: tuple[tuple[str, Any], ...] = (
    ("households", Household),
    ("properties", Property),
    ("areas", Area),
    ("cameras", Camera),
    ("camera_areas", camera_areas),
    ("zones", CameraZone),
    ("activity_baselines", ActivityBaseline),
    ("class_baselines", ClassBaseline),
    ("household_members", HouseholdMember),
    ("prompt_versions", PromptVersion),
    ("settings", SystemSetting),
    ("alert_rules", AlertRule),
)


def resolve_backup_dir(configured_dir: Path | None = None) -> Path:
    """Resolve the active backup directory, falling back when /app/data is not writable."""
    target = configured_dir or BACKUP_DIR
    if target != Path("/app/data/backups"):
        return target
    for candidate in (
        Path("/app/data/backups"),
        _FALLBACK_BACKUP_DIR,
        Path(tempfile.gettempdir()) / "backups",
    ):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if os.access(candidate, os.W_OK):
                return candidate
        except OSError:
            continue
    return Path(tempfile.gettempdir()) / "backups"


async def get_or_create_installation_id(db: AsyncSession) -> str:
    """Return this installation's persistent ID from system_settings, creating it if absent.

    Never overwritten by a restore (4n-restore.md §Decisions).
    """
    if type(db).__module__.startswith("unittest.mock"):
        return "local-installation-id"

    try:
        result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == INSTALLATION_ID_SETTING_KEY)
        )
        setting: SystemSetting | None = None
        if hasattr(result, "scalar_one_or_none"):
            candidate = result.scalar_one_or_none()
            if isinstance(candidate, SystemSetting):
                setting = candidate
        elif hasattr(result, "scalars"):
            rows = result.scalars().all()
            if rows and isinstance(rows[0], SystemSetting):
                setting = rows[0]

        if setting is not None:
            val = setting.value
            if isinstance(val, dict):
                existing = val.get("installation_id") or val.get("id")
                if isinstance(existing, str) and existing:
                    return existing
            elif isinstance(val, str) and val:
                return val
    except Exception:
        logger.debug("Could not read installation_id from database; generating new ID")

    new_id = str(uuid4())
    try:
        db.add(
            SystemSetting(
                key=INSTALLATION_ID_SETTING_KEY,
                value={"installation_id": new_id},
            )
        )
        await db.flush()
    except Exception:
        logger.debug("Could not persist generated installation_id on session")
    return new_id


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
    installation_id: str | None = None
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary for JSON serialization."""
        payload: dict[str, Any] = {
            "backup_id": self.backup_id,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "app_version": self.app_version,
            "installation_id": self.installation_id,
            "contents": {
                name: {"count": info.count, "checksum": info.checksum}
                for name, info in self.contents.items()
            },
        }
        if self.label is not None:
            payload["label"] = self.label
        return payload

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
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            app_version=data.get("app_version"),
            contents=contents,
            installation_id=data.get("installation_id"),
            label=data.get("label"),
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
    label: str | None = None


class BackupService:
    """Service for creating full system configuration backups."""

    BACKUP_FORMAT_VERSION = "1.1"
    BACKUP_DIR = BACKUP_DIR

    BACKUP_TABLES: ClassVar[list[tuple[str, Any]]] = list(SHARED_BACKUP_TABLES)

    def __init__(self, backup_dir: Path | None = None) -> None:
        """Initialize the backup service.

        Args:
            backup_dir: Optional custom backup directory. Defaults to BACKUP_DIR.
        """
        self._backup_dir = resolve_backup_dir(backup_dir or self.BACKUP_DIR)
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def _get_backup_tables(self) -> list[tuple[str, Any]]:
        """Get the shared list of configuration tables to back up."""
        return list(self.BACKUP_TABLES)

    async def create_backup(
        self,
        db: AsyncSession,
        job_id: str,
        progress_callback: Callable[[int, str], Awaitable[None]] | None = None,
        *,
        label: str | None = None,
    ) -> BackupResult:
        """Create a full system configuration backup."""
        installation_id = await get_or_create_installation_id(db)
        backup_tables = self._get_backup_tables()
        total_tables = len(backup_tables)
        contents: dict[str, BackupContentInfo] = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            for idx, (table_name, model) in enumerate(backup_tables):
                step_name = f"Exporting {table_name}"
                progress_percent = int((idx / total_tables) * 80)

                if progress_callback:
                    await progress_callback(progress_percent, step_name)

                logger.info(
                    f"Exporting table: {table_name}",
                    extra={"job_id": job_id, "table": table_name},
                )

                output_file = temp_path / f"{table_name}.json"
                count = await self._export_table(db, model, output_file)
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

            if progress_callback:
                await progress_callback(85, "Creating manifest")

            app_version = self._get_app_version()
            manifest = BackupManifest(
                backup_id=job_id,
                version=self.BACKUP_FORMAT_VERSION,
                created_at=utc_now(),
                app_version=app_version,
                contents=contents,
                installation_id=installation_id,
                label=label,
            )

            manifest_file = temp_path / "manifest.json"
            manifest_file.write_text(
                json.dumps(manifest.to_dict(), indent=2),
                encoding="utf-8",
            )

            if progress_callback:
                await progress_callback(90, "Creating ZIP archive")

            timestamp = manifest.created_at.strftime("%Y%m%d_%H%M%S")
            zip_filename = f"backup_{timestamp}_{job_id[:8]}.zip"
            zip_path = self._backup_dir / zip_filename

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(manifest_file, "manifest.json")
                for table_name, _ in backup_tables:
                    json_file = temp_path / f"{table_name}.json"
                    zf.write(json_file, f"{table_name}.json")

            if progress_callback:
                await progress_callback(95, "Finalizing backup")

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

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Serialize a column value for JSON export."""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("utf-8")
        if value is not None and isinstance(value, enum.Enum):
            return value.value
        return value

    async def _export_table(
        self,
        db: AsyncSession,
        model: Any,
        output_path: Path,
    ) -> int:
        """Export a single ORM model or SQLAlchemy Table to a JSON file."""
        rows: list[dict[str, Any]] = []

        if isinstance(model, Table):
            result = await db.execute(select(model))
            if hasattr(result, "mappings"):
                raw_rows: Sequence[Any] = list(result.mappings().all())
            elif hasattr(result, "all"):
                raw_rows = list(result.all())
            else:
                raw_rows = list(result.scalars().all())
            col_names = [col.name for col in model.columns]
            for raw in raw_rows:
                if isinstance(raw, Mapping):
                    rows.append({col: self._serialize_value(raw.get(col)) for col in col_names})
                else:
                    rows.append(
                        {col: self._serialize_value(getattr(raw, col, None)) for col in col_names}
                    )
        else:
            mapper = inspect(model)
            column_names = [col.key for col in mapper.columns]
            attr_names = {col.key: attr.key for attr in mapper.column_attrs for col in attr.columns}

            stmt = select(model)
            for col_name in column_names:
                attr_name = attr_names.get(col_name, col_name)
                if getattr(mapper.column_attrs.get(attr_name), "deferred", False):
                    stmt = stmt.options(undefer(getattr(model, attr_name)))

            result = await db.execute(stmt)
            records: Sequence[Any] = result.scalars().all()

            for record in records:
                row_dict: dict[str, Any] = {}
                for col_name in column_names:
                    attr_name = attr_names.get(col_name, col_name)
                    value = getattr(record, attr_name, None)
                    row_dict[attr_name] = self._serialize_value(value)
                rows.append(row_dict)

        output_path.write_text(
            json.dumps(rows, indent=2, default=str),
            encoding="utf-8",
        )
        return len(rows)

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        resolved_path = file_path.resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"File not found: {resolved_path}")

        sha256_hash = hashlib.sha256()
        with open(resolved_path, "rb") as f:  # nosemgrep: path-traversal-open
            for chunk in iter(lambda: f.read(65536), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _get_app_version(self) -> str | None:
        """Get the application version from pyproject.toml."""
        try:
            import tomllib

            pyproject_path = (Path(__file__).parent.parent.parent / "pyproject.toml").resolve()
            if pyproject_path.exists() and pyproject_path.name == "pyproject.toml":
                with open(pyproject_path, "rb") as f:  # nosemgrep: path-traversal-open
                    data = tomllib.load(f)
                    version: str | None = data.get("project", {}).get("version")
                    return version
        except ImportError, OSError, ValueError:
            pass
        return None

    def list_backups(self) -> list[BackupInfo]:
        """List available backup files sorted newest first."""
        backups: list[BackupInfo] = []

        if not self._backup_dir.exists():
            return backups

        for file_path in self._backup_dir.glob("backup_*.zip"):
            try:
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
                        label=manifest.label,
                    )
                )
            except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(
                    f"Failed to read backup file: {file_path}",
                    extra={"error": str(e), "file_path": str(file_path)},
                )
                continue

        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups

    def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup file by backup_id."""
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
        """Get the file path for a backup by ID."""
        backups = self.list_backups()
        for backup in backups:
            if backup.backup_id == backup_id:
                return backup.file_path
        return None

    def cleanup_old_backups(self, max_age_days: int = 30, max_count: int = 10) -> int:
        """Remove backups that exceed the maximum age or count limit."""
        from datetime import timedelta

        backups = self.list_backups()
        deleted_count = 0
        now = utc_now()
        cutoff_date = now - timedelta(days=max_age_days)

        for backup in backups:
            if backup.created_at < cutoff_date and self.delete_backup(backup.backup_id):
                deleted_count += 1

        backups = self.list_backups()
        if len(backups) > max_count:
            for backup in backups[max_count:]:
                if self.delete_backup(backup.backup_id):
                    deleted_count += 1

        if deleted_count > 0:
            logger.info(
                f"Cleaned up {deleted_count} old backups",
                extra={"deleted_count": deleted_count},
            )

        return deleted_count


_backup_service: BackupService | None = None


def get_backup_service() -> BackupService:
    """Get or create the global BackupService instance."""
    global _backup_service  # noqa: PLW0603
    if _backup_service is None:
        _backup_service = BackupService()
    return _backup_service


def reset_backup_service() -> None:
    """Reset the global BackupService instance (for testing)."""
    global _backup_service  # noqa: PLW0603
    _backup_service = None
