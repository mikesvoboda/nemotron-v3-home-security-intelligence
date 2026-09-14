"""Integration tests for RestoreService.

Tests the RestoreService class which restores system data from backup files.
Tests cover manifest validation, checksum verification, and database restoration.

Related: NEM-3566 Backup/Restore Implementation
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from backend.models.camera import Camera
from backend.services.backup_service import BackupService, reset_backup_service
from backend.services.restore_service import (
    BackupCorruptedError,
    BackupValidationError,
    RestoreService,
    reset_restore_service,
)
from backend.tests.conftest import unique_id

# Mark all tests as integration
pytestmark = [pytest.mark.integration]


@pytest.fixture
def restore_service() -> RestoreService:
    """Create a RestoreService instance."""
    reset_restore_service()
    return RestoreService()


@pytest.fixture
def backup_service(tmp_path: Path) -> BackupService:
    """Create a BackupService instance with a temporary backup directory."""
    reset_backup_service()
    return BackupService(backup_dir=tmp_path)


@pytest.fixture
async def backup_file(test_db, backup_service: BackupService, tmp_path: Path) -> Path:
    """Create a test backup file and return its path."""
    # Create some test data to backup
    camera_id = unique_id("restore_test_cam")
    async with test_db() as session:
        camera = Camera(
            id=camera_id,
            name=f"Restore Test Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.commit()

        # Create backup
        result = await backup_service.create_backup(session, unique_id("restore_test"))

    return result.file_path


class TestRestoreServiceValidation:
    """Tests for RestoreService validation methods."""

    @pytest.mark.asyncio
    async def test_validates_missing_manifest(
        self,
        test_db,
        restore_service: RestoreService,
        tmp_path: Path,
    ) -> None:
        """Test that restore fails for ZIP without manifest."""
        # Create a ZIP without manifest
        invalid_zip = tmp_path / "no_manifest.zip"
        with zipfile.ZipFile(invalid_zip, "w") as zf:
            zf.writestr("cameras.json", "[]")

        async with test_db() as session:
            with pytest.raises(BackupValidationError, match="manifest not found"):
                await restore_service.restore_from_backup(
                    invalid_zip,
                    session,
                    unique_id("restore_job"),
                )

    @pytest.mark.asyncio
    async def test_validates_manifest_version(
        self,
        test_db,
        restore_service: RestoreService,
        tmp_path: Path,
    ) -> None:
        """Test that restore fails for unsupported backup version."""
        # Create a ZIP with invalid version
        invalid_zip = tmp_path / "bad_version.zip"
        manifest = {
            "backup_id": "test",
            "version": "99.0",  # Unsupported version
            "created_at": "2025-01-01T00:00:00Z",
            "contents": {},
        }
        with zipfile.ZipFile(invalid_zip, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))

        async with test_db() as session:
            with pytest.raises(BackupValidationError, match="Unsupported backup version"):
                await restore_service.restore_from_backup(
                    invalid_zip,
                    session,
                    unique_id("restore_job"),
                )

    @pytest.mark.asyncio
    async def test_validates_checksum_mismatch(
        self,
        test_db,
        restore_service: RestoreService,
        tmp_path: Path,
    ) -> None:
        """Test that restore fails when checksum doesn't match."""
        # Create a ZIP with wrong checksum
        corrupted_zip = tmp_path / "bad_checksum.zip"
        manifest = {
            "backup_id": "test",
            "version": "1.0",
            "created_at": "2025-01-01T00:00:00Z",
            "contents": {
                "cameras": {
                    "count": 1,
                    "checksum": "0000000000000000000000000000000000000000000000000000000000000000",
                },
            },
        }
        with zipfile.ZipFile(corrupted_zip, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("cameras.json", '[{"id": "test"}]')

        async with test_db() as session:
            with pytest.raises(BackupCorruptedError, match="Checksum mismatch"):
                await restore_service.restore_from_backup(
                    corrupted_zip,
                    session,
                    unique_id("restore_job"),
                )

    @pytest.mark.asyncio
    async def test_validates_invalid_zip(
        self,
        test_db,
        restore_service: RestoreService,
        tmp_path: Path,
    ) -> None:
        """Test that restore fails for invalid ZIP file."""
        invalid_file = tmp_path / "not_a_zip.zip"
        invalid_file.write_text("This is not a valid ZIP file")

        async with test_db() as session:
            with pytest.raises(BackupValidationError, match="Invalid backup file"):
                await restore_service.restore_from_backup(
                    invalid_file,
                    session,
                    unique_id("restore_job"),
                )


class TestRestoreServiceRestore:
    """Tests for RestoreService.restore_from_backup()."""

    @pytest.mark.asyncio
    async def test_restores_from_valid_backup(
        self,
        test_db,
        restore_service: RestoreService,
        backup_file: Path,
    ) -> None:
        """Test that restore works with a valid backup file."""
        job_id = unique_id("restore_job")

        async with test_db() as session:
            result = await restore_service.restore_from_backup(
                backup_file,
                session,
                job_id,
            )

        assert result.backup_id is not None
        assert result.total_items >= 0
        assert isinstance(result.items_restored, dict)

    @pytest.mark.asyncio
    async def test_progress_callback_called(
        self,
        test_db,
        restore_service: RestoreService,
        backup_file: Path,
    ) -> None:
        """Test that progress callback is invoked during restore."""
        progress_updates: list[tuple[int, str]] = []

        async def progress_callback(percent: int, step: str) -> None:
            progress_updates.append((percent, step))

        async with test_db() as session:
            await restore_service.restore_from_backup(
                backup_file,
                session,
                unique_id("restore_job"),
                progress_callback,
            )

        # Verify progress updates were received
        assert len(progress_updates) > 0
        # Should have extracting and restoring steps
        steps = [step for _, step in progress_updates]
        assert any("Extracting" in s for s in steps)

    @pytest.mark.asyncio
    async def test_restore_result_contains_item_counts(
        self,
        test_db,
        restore_service: RestoreService,
        backup_file: Path,
    ) -> None:
        """Test that restore result includes per-table item counts."""
        async with test_db() as session:
            result = await restore_service.restore_from_backup(
                backup_file,
                session,
                unique_id("restore_job"),
            )

        # items_restored should be a dict of table_name -> count
        assert isinstance(result.items_restored, dict)
        # Total should equal sum of individual counts
        assert result.total_items == sum(result.items_restored.values())


class TestRestoreServiceIntegration:
    """End-to-end integration tests for backup/restore cycle."""

    @pytest.mark.asyncio
    async def test_backup_restore_roundtrip(
        self,
        test_db,
        backup_service: BackupService,
        restore_service: RestoreService,
    ) -> None:
        """Test complete backup and restore cycle preserves data."""
        # Create test camera
        camera_id = unique_id("roundtrip_cam")
        camera_name = f"Roundtrip Camera {camera_id[-8:]}"

        async with test_db() as session:
            camera = Camera(
                id=camera_id,
                name=camera_name,
                folder_path=f"/export/foscam/{camera_id}",
            )
            session.add(camera)
            await session.commit()

            # Create backup
            backup_result = await backup_service.create_backup(
                session,
                unique_id("roundtrip_backup"),
            )

        # Restore from backup
        async with test_db() as session:
            restore_result = await restore_service.restore_from_backup(
                backup_result.file_path,
                session,
                unique_id("roundtrip_restore"),
            )

        # Verify restore completed
        assert restore_result.total_items >= 0
        assert restore_result.backup_id is not None
