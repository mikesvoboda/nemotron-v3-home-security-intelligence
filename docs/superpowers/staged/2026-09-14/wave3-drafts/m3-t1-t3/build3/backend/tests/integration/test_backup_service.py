"""Integration tests for BackupService.

Tests the BackupService class which creates ZIP archive backups of system data.
Tests cover database interactions, file operations, and error handling.

Related: NEM-3566 Backup/Restore Implementation
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from backend.models.camera import Camera
from backend.services.backup_service import BackupService, reset_backup_service
from backend.tests.conftest import unique_id

# Mark all tests as integration
pytestmark = [pytest.mark.integration]


@pytest.fixture
def backup_service(tmp_path: Path) -> BackupService:
    """Create a BackupService instance with a temporary backup directory."""
    reset_backup_service()
    return BackupService(backup_dir=tmp_path)


@pytest.fixture
async def test_camera(test_db) -> str:
    """Create a test camera and return its ID."""
    camera_id = unique_id("backup_test_cam")
    async with test_db() as session:
        camera = Camera(
            id=camera_id,
            name=f"Backup Test Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.commit()
    return camera_id


class TestBackupServiceCreateBackup:
    """Tests for BackupService.create_backup()."""

    @pytest.mark.asyncio
    async def test_creates_backup_file(
        self,
        test_db,
        backup_service: BackupService,
        test_camera: str,
    ) -> None:
        """Test that create_backup creates a valid ZIP file."""
        job_id = unique_id("backup_job")

        async with test_db() as session:
            result = await backup_service.create_backup(session, job_id)

        # Verify backup file exists
        assert result.file_path.exists()
        assert result.file_path.suffix == ".zip"
        assert result.file_size > 0

    @pytest.mark.asyncio
    async def test_backup_contains_manifest(
        self,
        test_db,
        backup_service: BackupService,
    ) -> None:
        """Test that backup contains a valid manifest.json."""
        job_id = unique_id("backup_job")

        async with test_db() as session:
            result = await backup_service.create_backup(session, job_id)

        # Verify manifest in ZIP
        with zipfile.ZipFile(result.file_path, "r") as zf:
            assert "manifest.json" in zf.namelist()
            manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))

        assert manifest_data["backup_id"] == job_id
        assert manifest_data["version"] == "1.0"
        assert "created_at" in manifest_data
        assert "contents" in manifest_data

    @pytest.mark.asyncio
    async def test_backup_includes_camera_data(
        self,
        test_db,
        backup_service: BackupService,
        test_camera: str,
    ) -> None:
        """Test that backup includes camera records."""
        job_id = unique_id("backup_job")

        async with test_db() as session:
            result = await backup_service.create_backup(session, job_id)

        # Verify cameras.json in ZIP
        with zipfile.ZipFile(result.file_path, "r") as zf:
            assert "cameras.json" in zf.namelist()
            cameras_data = json.loads(zf.read("cameras.json").decode("utf-8"))

        # Should include at least our test camera
        camera_ids = [c["id"] for c in cameras_data]
        assert test_camera in camera_ids

    @pytest.mark.asyncio
    async def test_progress_callback_called(
        self,
        test_db,
        backup_service: BackupService,
    ) -> None:
        """Test that progress callback is invoked during backup."""
        job_id = unique_id("backup_job")
        progress_updates: list[tuple[int, str]] = []

        async def progress_callback(percent: int, step: str) -> None:
            progress_updates.append((percent, step))

        async with test_db() as session:
            await backup_service.create_backup(session, job_id, progress_callback)

        # Verify progress updates were received
        assert len(progress_updates) > 0
        # Should end at 100%
        assert any(pct == 100 for pct, _ in progress_updates)


class TestBackupServiceListBackups:
    """Tests for BackupService.list_backups()."""

    @pytest.mark.asyncio
    async def test_lists_created_backups(
        self,
        test_db,
        backup_service: BackupService,
    ) -> None:
        """Test that list_backups returns created backups."""
        # Create two backups
        async with test_db() as session:
            await backup_service.create_backup(session, unique_id("backup1"))
            await backup_service.create_backup(session, unique_id("backup2"))

        backups = backup_service.list_backups()
        assert len(backups) >= 2

    @pytest.mark.asyncio
    async def test_backups_sorted_by_date(
        self,
        test_db,
        backup_service: BackupService,
    ) -> None:
        """Test that list_backups returns backups sorted newest first."""
        async with test_db() as session:
            await backup_service.create_backup(session, unique_id("older"))
            await backup_service.create_backup(session, unique_id("newer"))

        backups = backup_service.list_backups()

        # Verify sorted by date descending
        for i in range(len(backups) - 1):
            assert backups[i].created_at >= backups[i + 1].created_at

    def test_empty_directory_returns_empty_list(
        self,
        backup_service: BackupService,
    ) -> None:
        """Test that list_backups returns empty list for empty directory."""
        backups = backup_service.list_backups()
        assert backups == []


class TestBackupServiceDeleteBackup:
    """Tests for BackupService.delete_backup()."""

    @pytest.mark.asyncio
    async def test_deletes_backup(
        self,
        test_db,
        backup_service: BackupService,
    ) -> None:
        """Test that delete_backup removes the backup file."""
        job_id = unique_id("backup_to_delete")

        async with test_db() as session:
            result = await backup_service.create_backup(session, job_id)

        # Verify file exists
        assert result.file_path.exists()

        # Delete backup
        deleted = backup_service.delete_backup(job_id)
        assert deleted is True

        # Verify file is gone
        assert not result.file_path.exists()

    def test_delete_nonexistent_returns_false(
        self,
        backup_service: BackupService,
    ) -> None:
        """Test that delete_backup returns False for nonexistent backup."""
        deleted = backup_service.delete_backup("nonexistent-id")
        assert deleted is False


class TestBackupServiceCleanup:
    """Tests for BackupService.cleanup_old_backups()."""

    @pytest.mark.asyncio
    async def test_cleanup_respects_max_count(
        self,
        test_db,
        backup_service: BackupService,
    ) -> None:
        """Test that cleanup removes backups exceeding max count."""
        # Create more backups than max_count
        for i in range(5):
            async with test_db() as session:
                await backup_service.create_backup(session, unique_id(f"cleanup{i}"))

        # Clean up keeping only 2
        deleted_count = backup_service.cleanup_old_backups(max_age_days=365, max_count=2)

        # Should delete 3 backups
        assert deleted_count == 3
        assert len(backup_service.list_backups()) == 2


class TestBackupServiceGetPath:
    """Tests for BackupService.get_backup_path()."""

    @pytest.mark.asyncio
    async def test_returns_path_for_existing_backup(
        self,
        test_db,
        backup_service: BackupService,
    ) -> None:
        """Test that get_backup_path returns path for existing backup."""
        job_id = unique_id("backup_path_test")

        async with test_db() as session:
            result = await backup_service.create_backup(session, job_id)

        path = backup_service.get_backup_path(job_id)
        assert path == result.file_path

    def test_returns_none_for_nonexistent(
        self,
        backup_service: BackupService,
    ) -> None:
        """Test that get_backup_path returns None for nonexistent backup."""
        path = backup_service.get_backup_path("nonexistent-id")
        assert path is None
