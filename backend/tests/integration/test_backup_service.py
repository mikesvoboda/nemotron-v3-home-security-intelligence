"""Integration tests for BackupService.

Tests the BackupService class which creates ZIP archive backups of system data.
Tests cover database interactions, file operations, and error handling.

Related: NEM-3566 Backup/Restore Implementation
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.models.camera import Camera
from backend.services.backup_service import (
    BackupContentInfo,
    BackupManifest,
    BackupService,
    reset_backup_service,
)
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
        assert manifest_data["version"] == "1.1"
        assert manifest_data["installation_id"]
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


class TestBackupExcludesEventHistoryAndExportsConfig:
    """[B4.6] 4n-restore.md: backups export configuration tables and exclude event/alert history."""

    N_EVENTS = 3

    @pytest.fixture
    async def seeded_events(self, test_db) -> list[int]:
        """Populate cameras + events with deferred columns populated."""
        from backend.models.event import Event

        camera_ids = [unique_id("b46_cam") for _ in range(2)]
        event_ids: list[int] = []
        async with test_db() as session:
            for camera_id in camera_ids:
                session.add(
                    Camera(
                        id=camera_id,
                        name=f"B46 Camera {camera_id[-6:]}",
                        folder_path=f"/export/foscam/{camera_id}",
                    )
                )
            await session.flush()

            for i in range(self.N_EVENTS):
                event = Event(
                    batch_id=str(uuid.uuid4()),
                    camera_id=camera_ids[i % 2],
                    started_at=datetime(2026, 1, i + 1, 12, 0, 0, tzinfo=UTC),
                    risk_score=30 + i * 10,
                    risk_level="medium",
                    summary=f"B46 event {i}",
                    reasoning=f"B46-REASONING-{i}",
                    llm_prompt=f"B46-LLMPROMPT-{i}",
                )
                session.add(event)
                await session.flush()
                event_ids.append(event.id)
            await session.commit()
        return event_ids

    @pytest.mark.asyncio
    async def test_backup_excludes_events_and_alerts_and_exports_12_config_tables(
        self,
        test_db,
        backup_service: BackupService,
        seeded_events: list[int],
    ) -> None:
        """Backups contain the 12 configuration tables and omit events/alerts/prompts."""
        assert len(seeded_events) == self.N_EVENTS
        job_id = unique_id("backup_job")

        async with test_db() as session:
            result = await backup_service.create_backup(session, job_id)

        with zipfile.ZipFile(result.file_path, "r") as zf:
            names = set(zf.namelist())
            assert "events.json" not in names
            assert "alerts.json" not in names
            assert "prompts.json" not in names
            assert "households.json" in names
            assert "properties.json" in names
            assert "areas.json" in names
            assert "cameras.json" in names
            assert "camera_areas.json" in names
            assert "zones.json" in names
            assert "activity_baselines.json" in names
            assert "class_baselines.json" in names
            assert "household_members.json" in names
            assert "prompt_versions.json" in names
            assert "settings.json" in names
            assert "alert_rules.json" in names


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


class TestLegacy10ArchiveRestoreAdapter:
    """[B4.6] 4n-restore.md: a 1.0 archive with events and alerts skips both and restores the rest."""

    @pytest.mark.asyncio
    async def test_1_0_archive_skips_events_and_alerts_and_restores_cameras(
        self,
        test_db,
    ) -> None:
        """A 1.0 archive from origin/main with events and alerts restores cameras and lists both skipped."""
        from sqlalchemy import select

        from backend.services.restore_service import (
            RestoreService,
            reset_restore_service,
        )

        cam_id = unique_id("v10_cam")
        cameras_payload = json.dumps(
            [
                {
                    "id": cam_id,
                    "name": f"V10 Camera {cam_id[-6:]}",
                    "folder_path": f"/export/foscam/{cam_id}",
                    "status": "online",
                }
            ]
        )
        events_payload = json.dumps([{"id": 99999, "camera_id": cam_id, "risk_score": 50}])
        alerts_payload = json.dumps(
            [{"id": str(uuid.uuid4()), "event_id": 99999, "metadata": "MetaData()"}]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            manifest = BackupManifest(
                backup_id=unique_id("v10_backup"),
                version="1.0",
                created_at=datetime.now(UTC),
                app_version="1.0.0",
                contents={
                    "events": BackupContentInfo(
                        count=1,
                        checksum=hashlib.sha256(events_payload.encode()).hexdigest(),
                    ),
                    "alerts": BackupContentInfo(
                        count=1,
                        checksum=hashlib.sha256(alerts_payload.encode()).hexdigest(),
                    ),
                    "cameras": BackupContentInfo(
                        count=1,
                        checksum=hashlib.sha256(cameras_payload.encode()).hexdigest(),
                    ),
                },
            )
            backup_path = tmpdir_path / "v10_backup.zip"
            with zipfile.ZipFile(backup_path, "w") as zf:
                zf.writestr("manifest.json", json.dumps(manifest.to_dict()))
                zf.writestr("events.json", events_payload)
                zf.writestr("alerts.json", alerts_payload)
                zf.writestr("cameras.json", cameras_payload)

            reset_restore_service()
            async with test_db() as session:
                res = await RestoreService().restore_from_backup(
                    backup_path, session, unique_id("v10_restore")
                )
                await session.commit()

        assert res.skipped_tables == ["events", "alerts"]
        assert res.items_restored == {"cameras": 1}

        async with test_db() as session:
            restored_cam = (
                await session.execute(select(Camera).where(Camera.id == cam_id))
            ).scalar_one()
            assert restored_cam.name == f"V10 Camera {cam_id[-6:]}"
