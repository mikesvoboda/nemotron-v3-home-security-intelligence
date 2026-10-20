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


class TestBackupExportsDeferredEventColumns:
    """[r129] ruling 127: a populated `events` table must survive a backup.

    ``Event.reasoning`` and ``Event.llm_prompt`` are ``deferred()``
    (backend/models/event.py:70-74), so ``select(Event)`` does not load them.
    ``_export_table`` then walks EVERY mapper column with ``getattr``
    (backend/services/backup_service.py:353-354), and touching an unloaded
    deferred column makes SQLAlchemy issue a lazy load -- which raises
    ``MissingGreenlet`` inside an ``AsyncSession``. Pre-fix every backup failed
    as soon as one event existed, and every backup looked healthy on an empty
    table. No test ran THIS service's ``create_backup`` over a populated
    ``events`` table: the unit tier drives it with a ``FakeDB`` whose ``events``
    count it asserts is 0, and the one integration file that does seed events
    (``test_backup_restore.py:381``) exercises ``create_pg_backup``
    (``:123`` -- a pg_dump shell-out), a different implementation. That is why
    a 100 % real-world failure passed CI.

    Asserting the VALUES, not just completion, is deliberate: the tempting
    fix is to skip deferred columns, which would make this backup "complete
    with every row present" while silently dropping two columns from every
    backup forever -- a loud failure traded for permanent data loss.
    """

    # Number of event rows seeded per test.
    N_EVENTS = 5

    @pytest.fixture
    async def seeded_events(self, test_db) -> list[int]:
        """Populate cameras + events, with the deferred columns non-NULL.

        Seeding follows ``test_ai_audit_api.py::_events_for_batch``: no explicit
        ``id`` (``Event.id`` is an autoincrement Integer, event.py:49), then
        ``flush()`` so ``event.id`` is populated for the assertions.
        """
        from backend.models.event import Event

        camera_ids = [unique_id("r129_cam") for _ in range(2)]
        event_ids: list[int] = []
        async with test_db() as session:
            for camera_id in camera_ids:
                session.add(
                    Camera(
                        id=camera_id,
                        name=f"R129 Camera {camera_id[-6:]}",
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
                    summary=f"R129 event {i}",
                    # The two deferred columns, with sentinel payloads.
                    reasoning=f"R129-REASONING-{i}",
                    llm_prompt=f"R129-LLMPROMPT-{i}",
                )
                session.add(event)
                await session.flush()
                event_ids.append(event.id)
            await session.commit()
        return event_ids

    @pytest.mark.asyncio
    async def test_backup_of_populated_events_table_completes_with_every_row(
        self,
        test_db,
        backup_service: BackupService,
        seeded_events: list[int],
    ) -> None:
        """Done-when (2): the backup completes and every event row is present."""
        job_id = unique_id("backup_job")

        async with test_db() as session:
            result = await backup_service.create_backup(session, job_id)

        with zipfile.ZipFile(result.file_path, "r") as zf:
            assert "events.json" in zf.namelist()
            events_data = json.loads(zf.read("events.json").decode("utf-8"))

        assert len(events_data) == len(seeded_events), (
            f"[r129] backup exported {len(events_data)} of {len(seeded_events)} "
            f"event rows; manifest count was "
            f"{result.manifest.contents['events'].count}"
        )
        assert sorted(e["id"] for e in events_data) == sorted(seeded_events)

    @pytest.mark.asyncio
    async def test_backup_preserves_the_deferred_column_values(
        self,
        test_db,
        backup_service: BackupService,
        seeded_events: list[int],
    ) -> None:
        """The deferred columns must be IN the archive, not skipped to get there.

        This is the half that separates "undefer the load" from "drop the
        columns". A backup that completes while writing ``reasoning: null``
        for every row passes Done-when (2) and is still data loss.
        """
        job_id = unique_id("backup_job")

        async with test_db() as session:
            result = await backup_service.create_backup(session, job_id)

        with zipfile.ZipFile(result.file_path, "r") as zf:
            events_data = json.loads(zf.read("events.json").decode("utf-8"))

        by_id = {e["id"]: e for e in events_data}
        assert len(by_id) == len(seeded_events)
        for i, event_id in enumerate(seeded_events):
            row = by_id[event_id]
            assert row.get("reasoning") == f"R129-REASONING-{i}", (
                f"[r129] event {event_id} lost its deferred `reasoning` in the "
                f"backup: {row.get('reasoning')!r}"
            )
            assert row.get("llm_prompt") == f"R129-LLMPROMPT-{i}", (
                f"[r129] event {event_id} lost its deferred `llm_prompt` in the "
                f"backup: {row.get('llm_prompt')!r}"
            )

    @pytest.mark.asyncio
    async def test_an_empty_events_table_was_never_evidence_of_a_working_backup(
        self,
        test_db,
        backup_service: BackupService,
    ) -> None:
        """Negative control: the green path everyone relied on is the vacuous one.

        With no event rows the deferred getattr never fires, so the export
        succeeds -- proving the OLD suite's confidence was an artifact of an
        empty table. Kept as a pin so the empty case stays working, and as
        the documented reason the defect survived.
        """
        job_id = unique_id("backup_job")

        async with test_db() as session:
            result = await backup_service.create_backup(session, job_id)

        with zipfile.ZipFile(result.file_path, "r") as zf:
            events_data = json.loads(zf.read("events.json").decode("utf-8"))

        assert events_data == []
        assert result.manifest.contents["events"].count == 0


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


class TestAlertMetadataSurvivesBackupAndRestore:
    """[r271b] Q-040: the alert payload survives backup then restore.

    ``Alert`` names its payload attribute ``alert_metadata`` but maps it to the
    table's ``metadata`` column (models/alert.py:120-121), so the mapper's
    column key ``metadata`` has no class-bound attribute behind it. The export
    walk reads ``getattr(record, "metadata")`` -- SQLAlchemy's reserved
    ``MetaData`` object -- stringifies it into the JSON as
    ``"metadata": "MetaData()"``, and the real payload is never written; the
    restore side drops the unknown key, so the payload is lost both ways.
    Measured at the PR base (d5c470715): exported
    ``"metadata": "MetaData()"``, no ``alert_metadata`` key, and the restored
    alert's ``alert_metadata`` came back ``None``.

    Asserting the VALUE, not just the row count, is deliberate (r129's
    precedent in this file): a backup that completes while silently nulling
    every alert payload passes a count-only assertion and is still data loss.

    ``Alert`` is the only walked model with this collision (census at the PR
    base over all 8 BACKUP_TABLES models plus the lazily appended Event);
    the tests are scoped to it.
    """

    # Sentinel payload the round trip must preserve.
    PAYLOAD = {"reason": "R271B-SENTINEL", "channels_tried": ["email", "webhook"]}

    @pytest.fixture
    async def seeded_alert(self, test_db) -> dict:
        """Seed camera -> event -> alert, returning the alert's exported keys."""
        from backend.models.alert import Alert
        from backend.models.event import Event

        camera_id = unique_id("r271b_cam")
        async with test_db() as session:
            session.add(
                Camera(
                    id=camera_id,
                    name=f"R271B Camera {camera_id[-6:]}",
                    folder_path=f"/export/foscam/{camera_id}",
                )
            )
            await session.flush()
            event = Event(
                batch_id=unique_id("r271b_batch"),
                camera_id=camera_id,
                started_at=datetime.now(UTC),
                risk_score=40,
                summary=f"R271B event {camera_id[-6:]}",
            )
            session.add(event)
            await session.flush()
            alert = Alert(
                event_id=event.id,
                dedup_key=unique_id("r271b_dedup"),
                alert_metadata=self.PAYLOAD,
            )
            session.add(alert)
            await session.commit()
            # Alert.id is a UUID column with a uuid7 default; read the
            # generated value back instead of assigning a string.
            alert_id = alert.id
        return {"alert_id": alert_id, "camera_id": camera_id, "event_id": event.id}

    @pytest.mark.asyncio
    async def test_backup_writes_alert_metadata_payload(
        self,
        test_db,
        backup_service: BackupService,
        seeded_alert: dict,
    ) -> None:
        """Export leg: the payload is IN the archive, under ``alert_metadata``."""
        job_id = unique_id("r271b_backup")

        async with test_db() as session:
            await backup_service.create_backup(session, job_id)

        with zipfile.ZipFile(backup_service.get_backup_path(job_id), "r") as zf:
            alerts = json.loads(zf.read("alerts.json").decode("utf-8"))

        (row,) = [a for a in alerts if a["id"] == seeded_alert["alert_id"]]
        assert row.get("alert_metadata") == self.PAYLOAD, (
            f"[r271b] alert {seeded_alert['alert_id']} lost its payload in the "
            f"backup: alert_metadata={row.get('alert_metadata')!r}, "
            f"metadata={row.get('metadata')!r}"
        )
        # The reserved key must not carry the stringified MetaData object.
        assert "metadata" not in row

    @pytest.mark.asyncio
    async def test_round_trip_restores_alert_metadata_payload(
        self,
        test_db,
        backup_service: BackupService,
        seeded_alert: dict,
    ) -> None:
        """Full round trip: seed -> backup -> restore -> payload intact."""
        from sqlalchemy import select

        from backend.models.alert import Alert
        from backend.services.restore_service import (
            RestoreService,
            reset_restore_service,
        )

        job_id = unique_id("r271b_roundtrip")

        async with test_db() as session:
            result = await backup_service.create_backup(session, job_id)

        reset_restore_service()
        async with test_db() as session:
            await RestoreService().restore_from_backup(
                result.file_path, session, unique_id("r271b_restore")
            )

        async with test_db() as session:
            restored = (
                await session.execute(
                    select(Alert).where(Alert.id == seeded_alert["alert_id"])
                )
            ).scalar_one()
            assert restored.alert_metadata == self.PAYLOAD, (
                f"[r271b] restored alert {seeded_alert['alert_id']} came back "
                f"with alert_metadata={restored.alert_metadata!r}; the payload "
                f"did not survive the round trip"
            )

    @pytest.mark.asyncio
    async def test_null_payload_stays_null_through_round_trip(
        self,
        test_db,
        backup_service: BackupService,
    ) -> None:
        """A seeded NULL payload must not become ``{}`` or ``"MetaData()"``."""
        from sqlalchemy import select

        from backend.models.alert import Alert
        from backend.models.event import Event
        from backend.services.restore_service import (
            RestoreService,
            reset_restore_service,
        )

        camera_id = unique_id("r271b_null_cam")
        async with test_db() as session:
            session.add(
                Camera(
                    id=camera_id,
                    name=f"R271B Null Camera {camera_id[-6:]}",
                    folder_path=f"/export/foscam/{camera_id}",
                )
            )
            await session.flush()
            event = Event(
                batch_id=unique_id("r271b_null_batch"),
                camera_id=camera_id,
                started_at=datetime.now(UTC),
                risk_score=10,
            )
            session.add(event)
            await session.flush()
            alert = Alert(
                event_id=event.id,
                dedup_key=unique_id("r271b_null_dedup"),
                # alert_metadata stays NULL: the constructor default.
            )
            session.add(alert)
            await session.commit()
            alert_id = alert.id

        job_id = unique_id("r271b_null_backup")
        async with test_db() as session:
            result = await backup_service.create_backup(session, job_id)

        reset_restore_service()
        async with test_db() as session:
            await RestoreService().restore_from_backup(
                result.file_path, session, unique_id("r271b_null_restore")
            )

        async with test_db() as session:
            restored = (
                await session.execute(select(Alert).where(Alert.id == alert_id))
            ).scalar_one()
            assert restored.alert_metadata is None

    @pytest.mark.asyncio
    async def test_prefix_backup_restores_with_null_metadata_and_no_error(
        self,
        test_db,
    ) -> None:
        """A backup made BEFORE the fix restores with ``alert_metadata`` null.

        The old export wrote ``"metadata": "MetaData()"`` and no
        ``alert_metadata`` key; there is nothing to recover, so the restore
        must accept the row without an error and leave the payload NULL --
        not crash and not silently invent a payload.

        The manifest contents name only ``alerts``, so the restore clears and
        refills only that table; the camera and event seeded for the FK chain
        survive it.
        """
        from sqlalchemy import select

        from backend.models.alert import Alert
        from backend.models.event import Event
        from backend.services.restore_service import (
            RestoreService,
            reset_restore_service,
        )

        camera_id = unique_id("r271b_prefix_cam")
        async with test_db() as session:
            session.add(
                Camera(
                    id=camera_id,
                    name=f"R271B Prefix Camera {camera_id[-6:]}",
                    folder_path=f"/export/foscam/{camera_id}",
                )
            )
            await session.flush()
            event = Event(
                batch_id=unique_id("r271b_prefix_batch"),
                camera_id=camera_id,
                started_at=datetime.now(UTC),
                risk_score=10,
            )
            session.add(event)
            await session.flush()
            event_id = event.id
            await session.commit()

        prefix_row = {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "severity": "medium",
            "status": "pending",
            "dedup_key": unique_id("r271b_prefix_dedup"),
            # Exactly what the pre-fix export wrote.
            "metadata": "MetaData()",
            "version_id": 1,
            "is_high_priority": False,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            alerts_path = tmpdir_path / "alerts.json"
            alerts_path.write_text(json.dumps([prefix_row]), encoding="utf-8")
            manifest = BackupManifest(
                backup_id=unique_id("r271b_prefix_backup"),
                version=BackupService.BACKUP_FORMAT_VERSION,
                created_at=datetime.now(UTC),
                app_version=None,
                contents={
                    "alerts": BackupContentInfo(
                        count=1,
                        checksum=hashlib.sha256(alerts_path.read_bytes()).hexdigest(),
                    )
                },
            )
            backup_path = tmpdir_path / "prefix_backup.zip"
            with zipfile.ZipFile(backup_path, "w") as zf:
                zf.writestr("manifest.json", json.dumps(manifest.to_dict()))
                zf.writestr("alerts.json", json.dumps([prefix_row]))

            reset_restore_service()
            async with test_db() as session:
                await RestoreService().restore_from_backup(
                    backup_path, session, unique_id("r271b_prefix_restore")
                )

        async with test_db() as session:
            restored = (
                await session.execute(
                    select(Alert).where(Alert.dedup_key == prefix_row["dedup_key"])
                )
            ).scalar_one()
            assert restored.alert_metadata is None

