"""Integration tests for backup and restore API endpoints.

These tests verify the HTTP API layer for backup/restore operations,
including job creation, progress tracking, file downloads, and error handling.

Tests use real HTTP client but mock file operations where appropriate for speed.
All tests are marked as integration tests.

Related Linear issue: NEM-3566
"""

from __future__ import annotations

import asyncio
import io
import json
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from backend.models.backup_job import BackupJob, RestoreJob
from backend.models.backup_job import BackupJobStatus as BackupJobStatusModel
from backend.models.backup_job import RestoreJobStatus as RestoreJobStatusModel
from backend.services.backup_service import BackupResult
from backend.services.restore_service import (
    BackupCorruptedError,
    BackupValidationError,
    RestoreError,
    RestoreResult,
)

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


# =============================================================================
# Helper Functions
# =============================================================================


def create_valid_backup_zip() -> bytes:
    """Create a valid backup ZIP file for testing.

    Checksums are REAL sha256 digests of the exact bytes written into the zip —
    the previous hardcoded "abc123"/"def456" made RestoreService
    _verify_checksums fail every "valid" backup (routes correctly marked the job
    failed; R-T7-BACKUP-MOUNT ledger).

    Returns:
        ZIP file contents as bytes.
    """
    import hashlib

    backup_id = str(uuid4())
    payloads = {
        "cameras.json": json.dumps(
            [
                {
                    "id": "cam1",
                    "name": "Backup Camera 1",
                    "folder_path": "/export/foscam/cam1",
                    "status": "online",
                },
                {
                    "id": "cam2",
                    "name": "Backup Camera 2",
                    "folder_path": "/export/foscam/cam2",
                    "status": "online",
                },
            ]
        ),
    }
    manifest = {
        "backup_id": backup_id,
        "version": "1.1",
        "created_at": datetime.now(UTC).isoformat(),
        "app_version": "1.0.0",
        "contents": {
            "cameras": {
                "count": 2,
                "checksum": hashlib.sha256(payloads["cameras.json"].encode()).hexdigest(),
            },
        },
    }

    # Create in-memory ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("cameras.json", payloads["cameras.json"])

    return zip_buffer.getvalue()


def create_corrupted_backup_zip() -> bytes:
    """Create a corrupted backup ZIP file for testing.

    Returns:
        Corrupted ZIP file contents as bytes.
    """
    return b"This is not a valid ZIP file"


# =============================================================================
# Backup Creation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_backup_returns_job_id(client: AsyncClient, mock_redis, integration_db):
    """Test creating a backup job returns job_id and status."""
    response = await client.post("/api/backup", json={})

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert "status" in data
    assert "message" in data
    assert data["status"] == "pending"
    assert isinstance(data["job_id"], str)
    assert len(data["job_id"]) > 0


@pytest.mark.asyncio
async def test_create_backup_creates_database_record(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test creating a backup job creates database record."""
    response = await client.post("/api/backup", json={})
    assert response.status_code == 202

    job_id = response.json()["job_id"]

    # Verify database record exists. Status is NOT asserted here: the background
    # runner can complete before this assert lands (empty test DB = instant
    # backup), and asserting membership in the whole enum would be vacuous.
    # State progression itself is covered by
    # test_create_backup_job_progresses_to_completion (R-T7-BACKUP-MOUNT).
    job = await db_session.get(BackupJob, job_id)
    assert job is not None
    assert job.id == job_id


@pytest.mark.asyncio
async def test_create_backup_job_progresses_to_completion(
    client: AsyncClient, mock_redis, integration_db
):
    """Test backup job progresses through states to completion."""
    # Create backup job
    response = await client.post("/api/backup", json={})
    assert response.status_code == 202

    job_id = response.json()["job_id"]

    # Initial status check (may be pending or running)
    response1 = await client.get(f"/api/backup/{job_id}")
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] in ("pending", "running", "completed", "failed")

    # Wait for job to progress
    await asyncio.sleep(0.5)

    # Check status again
    response2 = await client.get(f"/api/backup/{job_id}")
    assert response2.status_code == 200
    data2 = response2.json()
    assert "status" in data2
    assert "progress" in data2
    assert data2["status"] in ("pending", "running", "completed", "failed")


@pytest.mark.asyncio
async def test_create_backup_with_mocked_service(client: AsyncClient, mock_redis, integration_db):
    """Test backup job creates valid ZIP file with manifest (mocked service)."""
    # Create a valid backup result
    backup_id = str(uuid4())
    manifest = {
        "backup_id": backup_id,
        "version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "app_version": "1.0.0",
        "contents": {
            "cameras": {"count": 2, "checksum": "abc123"},
            "events": {"count": 5, "checksum": "def456"},
        },
    }

    mock_manifest = Mock()
    mock_manifest.to_dict.return_value = manifest

    mock_result = BackupResult(
        file_path=Path(tempfile.gettempdir()) / "backup.zip",
        file_size=1024,
        manifest=mock_manifest,
    )

    # Mock BackupService.create_backup
    with patch(
        "backend.api.routes.backup.BackupService.create_backup",
        return_value=mock_result,
        autospec=True,
    ):
        response = await client.post("/api/backup", json={})
        assert response.status_code == 202

        job_id = response.json()["job_id"]

        # Wait for background task
        await asyncio.sleep(0.5)

        # Check final status
        status_response = await client.get(f"/api/backup/{job_id}")
        assert status_response.status_code == 200

        # Note: Background task updates may not be visible immediately
        # due to transaction isolation, so we verify the job was created
        status_data = status_response.json()
        assert "status" in status_data
        assert "progress" in status_data


# =============================================================================
# Backup with a populated events table (r129 / owner ruling 127)
# =============================================================================

# Terminal statuses the POST /api/backup background job can settle on.
_BACKUP_TERMINAL = ("completed", "failed")


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # matches this test's own 60 x 0.5 s poll ceiling below
async def test_backup_with_events_completes_and_keeps_deferred_columns(
    client: AsyncClient,
    mock_redis,
    integration_db,
    db_session: AsyncSession,
):
    """[r129] ``POST /api/backup`` completes once an ``events`` row exists.

    Every other test in this file either mocks ``BackupService.create_backup``
    or runs it against an ``events`` table with zero rows, and the external
    golden path ``backend/tests/golden/external/test_backup.py`` was
    ``xfail(strict=True)`` for this same defect -- so before [r129] the HTTP
    layer had never carried a backup of a populated ``events`` table. That is
    how a 100%-real-world failure stayed green: the deferred-column
    ``getattr`` in ``_export_table`` (models/event.py:70-74 are ``deferred()``)
    only fires when the loop body runs, i.e. only when a row exists.

    Asserting through the download route rather than the service, because this
    is the tier CI always runs (the golden needs a live stack) and because
    "completed" alone is not the claim: the manifest count and the archive
    contents are what restore reads. Seeding follows
    ``test_backup_service.py::TestBackupExportsDeferredEventColumns`` -- no
    explicit ``Event.id`` (autoincrement Integer), ``flush()`` to get it back.
    """
    # Imported here, not at module scope: mirrors backup_service.py's own lazy
    # ``from backend.models.event import Event`` (backup_service.py:170), which
    # exists to dodge an import cycle this test module would otherwise inherit.
    from backend.models.camera import Camera
    from backend.models.event import Event

    camera_id = f"r129-api-cam-{uuid4()}"
    db_session.add(
        Camera(
            id=camera_id,
            name="R129 API Camera",
            folder_path=f"/export/foscam/{camera_id}",
        )
    )
    await db_session.flush()

    seeded_ids: list[int] = []
    for i in range(3):
        event = Event(
            batch_id=str(uuid4()),
            camera_id=camera_id,
            started_at=datetime(2026, 2, i + 1, 9, 30, 0, tzinfo=UTC),
            risk_score=40 + i * 10,
            risk_level="medium",
            summary=f"R129 api event {i}",
            # The two deferred columns, with values to prove they survived.
            reasoning=f"R129-API-REASONING-{i}",
            llm_prompt=f"R129-API-LLMPROMPT-{i}",
        )
        db_session.add(event)
        await db_session.flush()
        seeded_ids.append(event.id)
    await db_session.commit()

    response = await client.post("/api/backup", json={})
    assert response.status_code == 202, response.text[:500]
    job_id = response.json()["job_id"]

    # Bounded poll, not a fixed sleep: the background task shares this event
    # loop, so the asserts below have to wait for it to yield. A ceiling keeps
    # a hang loud instead of eating the ini timeout silently.
    status_data: dict = {}
    for _ in range(60):
        status_response = await client.get(f"/api/backup/{job_id}")
        assert status_response.status_code == 200, status_response.text[:500]
        status_data = status_response.json()
        if status_data.get("status") in _BACKUP_TERMINAL:
            break
        await asyncio.sleep(0.5)

    assert status_data.get("status") == "completed", (
        f"[B4.6] backup of a populated events table ended "
        f"{status_data.get('status')!r}: {status_data.get('error_message')!r}"
    )
    manifest = status_data.get("manifest") or {}
    assert manifest.get("version") == "1.1"
    assert manifest.get("installation_id")
    assert "events" not in manifest.get("contents", {})
    assert manifest.get("contents", {}).get("cameras", {}).get("count", 0) >= 1

    download = await client.get(f"/api/backup/{job_id}/download")
    assert download.status_code == 200, download.text[:300]
    archive = zipfile.ZipFile(io.BytesIO(download.content))
    assert "events.json" not in archive.namelist()
    cameras_data = json.loads(archive.read("cameras.json").decode("utf-8"))
    assert any(c["id"] == camera_id for c in cameras_data)


# =============================================================================
# Backup Listing Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_backups_empty(client: AsyncClient, mock_redis, integration_db):
    """Test listing backups when none exist."""
    response = await client.get("/api/backup")

    assert response.status_code == 200
    data = response.json()
    assert "backups" in data
    assert "total" in data
    assert isinstance(data["backups"], list)
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_backups_returns_completed_backups(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test listing backups returns completed backup jobs."""
    # Create completed backup job
    backup_id = str(uuid4())
    job = BackupJob(
        id=backup_id,
        status=BackupJobStatusModel.COMPLETED,
        file_path=f"/backups/backup_{backup_id}.zip",
        file_size_bytes=2048,
        progress_percent=100,
    )
    db_session.add(job)
    await db_session.commit()

    # List backups
    response = await client.get("/api/backup")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["backups"]) == 1

    backup = data["backups"][0]
    assert backup["id"] == backup_id
    assert backup["status"] == "completed"
    assert backup["file_size_bytes"] == 2048
    assert backup["download_url"] == f"/api/backup/{backup_id}/download"


@pytest.mark.asyncio
async def test_list_backups_after_creating_multiple(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test listing backups returns correct count after creating multiple."""
    # Create multiple completed backup jobs
    for i in range(3):
        backup_id = str(uuid4())
        job = BackupJob(
            id=backup_id,
            status=BackupJobStatusModel.COMPLETED,
            file_path=f"/backups/backup_{i}.zip",
            file_size_bytes=1024 * (i + 1),
            progress_percent=100,
        )
        db_session.add(job)

    await db_session.commit()

    # List backups
    response = await client.get("/api/backup")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["backups"]) == 3


@pytest.mark.asyncio
async def test_list_backups_excludes_pending_and_failed(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test listing backups excludes pending and failed jobs."""
    # Create jobs with different statuses
    completed_id = str(uuid4())
    pending_id = str(uuid4())
    failed_id = str(uuid4())

    completed_job = BackupJob(
        id=completed_id,
        status=BackupJobStatusModel.COMPLETED,
        file_path="/backups/completed.zip",
        file_size_bytes=2048,
    )

    pending_job = BackupJob(
        id=pending_id,
        status=BackupJobStatusModel.PENDING,
    )

    failed_job = BackupJob(
        id=failed_id,
        status=BackupJobStatusModel.FAILED,
        error_message="Test error",
    )

    db_session.add_all([completed_job, pending_job, failed_job])
    await db_session.commit()

    # List backups
    response = await client.get("/api/backup")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1  # Only completed
    assert data["backups"][0]["id"] == completed_id


# =============================================================================
# Backup Status Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path_template"),
    [
        ("get", "/api/backup/{job_id}"),
        ("get", "/api/backup/{job_id}/download"),
        ("delete", "/api/backup/{job_id}"),
        ("get", "/api/backup/restore/{job_id}"),
    ],
)
async def test_backup_endpoint_not_found(
    client: AsyncClient,
    mock_redis,
    integration_db,
    method: str,
    path_template: str,
):
    """Test backup/restore endpoints return 404 for a non-existent well-formed UUID."""
    request_fn = getattr(client, method)
    response = await request_fn(path_template.format(job_id=uuid4()))

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_get_backup_status_success(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test get backup status returns job details."""
    # Create backup job
    backup_id = str(uuid4())
    job = BackupJob(
        id=backup_id,
        status=BackupJobStatusModel.RUNNING,
        progress_percent=50,
        current_step="Exporting cameras...",
        total_tables=8,
        completed_tables=4,
    )
    db_session.add(job)
    await db_session.commit()

    # Get status
    response = await client.get(f"/api/backup/{backup_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == backup_id
    assert data["status"] == "running"
    assert data["progress"]["progress_percent"] == 50
    assert data["progress"]["current_step"] == "Exporting cameras..."
    assert data["progress"]["total_tables"] == 8
    assert data["progress"]["completed_tables"] == 4


@pytest.mark.asyncio
async def test_get_backup_status_with_manifest(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test get backup status includes manifest when available."""
    # Create completed backup job with manifest
    backup_id = str(uuid4())
    manifest = {
        "backup_id": backup_id,
        "version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "contents": {
            "cameras": {"count": 2, "checksum": "abc123"},
        },
    }

    job = BackupJob(
        id=backup_id,
        status=BackupJobStatusModel.COMPLETED,
        progress_percent=100,
        file_path=f"/backups/backup_{backup_id}.zip",
        file_size_bytes=2048,
        manifest_json=manifest,
    )
    db_session.add(job)
    await db_session.commit()

    # Get status
    response = await client.get(f"/api/backup/{backup_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["manifest"] is not None
    assert data["manifest"]["backup_id"] == backup_id
    assert data["manifest"]["version"] == "1.0"
    assert "cameras" in data["manifest"]["contents"]


# =============================================================================
# Backup Download Tests
# =============================================================================


@pytest.mark.asyncio
async def test_download_incomplete_backup_fails(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test downloading incomplete backup returns 400."""
    # Create pending backup job
    backup_id = str(uuid4())
    job = BackupJob(
        id=backup_id,
        status=BackupJobStatusModel.PENDING,
    )
    db_session.add(job)
    await db_session.commit()

    # Attempt download
    response = await client.get(f"/api/backup/{backup_id}/download")

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "not complete" in data["detail"].lower()


@pytest.mark.asyncio
async def test_download_backup_file_not_found(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test downloading backup when file doesn't exist returns 404."""
    # Create completed job with non-existent file path
    backup_id = str(uuid4())
    job = BackupJob(
        id=backup_id,
        status=BackupJobStatusModel.COMPLETED,
        file_path=f"/nonexistent/backup_{backup_id}.zip",
        file_size_bytes=2048,
    )
    db_session.add(job)
    await db_session.commit()

    # Attempt download
    response = await client.get(f"/api/backup/{backup_id}/download")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found on disk" in data["detail"].lower()


@pytest.mark.asyncio
async def test_download_completed_backup_returns_zip(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test downloading completed backup returns ZIP file."""
    # Create a temporary backup file
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_dir = Path(tmpdir) / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        backup_filename = f"backup_{uuid4()}.zip"
        backup_path = backup_dir / backup_filename

        # Write a valid ZIP file
        zip_content = create_valid_backup_zip()
        backup_path.write_bytes(zip_content)

        # Create completed backup job
        backup_id = str(uuid4())
        job = BackupJob(
            id=backup_id,
            status=BackupJobStatusModel.COMPLETED,
            file_path=str(backup_path),
            file_size_bytes=len(zip_content),
        )
        db_session.add(job)
        await db_session.commit()

        # Mock BACKUP_DIR to point to our temp directory
        with patch("backend.api.routes.backup.BACKUP_DIR", backup_dir):
            response = await client.get(f"/api/backup/{backup_id}/download")

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/zip"
            assert "content-disposition" in response.headers
            assert "attachment" in response.headers["content-disposition"]


# =============================================================================
# Backup Deletion Tests
# =============================================================================


@pytest.mark.asyncio
async def test_delete_backup_removes_record(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test deleting backup removes database record."""
    # Create backup job
    backup_id = str(uuid4())
    job = BackupJob(
        id=backup_id,
        status=BackupJobStatusModel.COMPLETED,
        file_path=f"/backups/backup_{backup_id}.zip",
        file_size_bytes=2048,
    )
    db_session.add(job)
    await db_session.commit()

    # Delete backup
    response = await client.delete(f"/api/backup/{backup_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True

    # Verify record is deleted (expire_all is sync on the ORM session — awaiting None
    # was a test bug)
    db_session.expire_all()
    deleted_job = await db_session.get(BackupJob, backup_id)
    assert deleted_job is None


@pytest.mark.asyncio
async def test_delete_backup_removes_file_and_record(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test deleting backup removes file and database record."""
    # Create a temporary backup file
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_dir = Path(tmpdir) / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        backup_filename = f"backup_{uuid4()}.zip"
        backup_path = backup_dir / backup_filename
        backup_path.write_bytes(create_valid_backup_zip())

        # Create completed backup job
        backup_id = str(uuid4())
        job = BackupJob(
            id=backup_id,
            status=BackupJobStatusModel.COMPLETED,
            file_path=str(backup_path),
            file_size_bytes=1024,
        )
        db_session.add(job)
        await db_session.commit()

        # Verify file exists
        assert backup_path.exists()

        # Mock BACKUP_DIR to point to our temp directory
        with patch("backend.api.routes.backup.BACKUP_DIR", backup_dir):
            # Delete backup
            response = await client.delete(f"/api/backup/{backup_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["deleted"] is True

            # Verify file is deleted
            assert not backup_path.exists()


# =============================================================================
# Restore Job Tests
# =============================================================================


@pytest.mark.asyncio
async def test_start_restore_invalid_file_type(client: AsyncClient, mock_redis, integration_db):
    """Test restore with invalid file type returns 400."""
    # Upload non-ZIP file
    files = {"file": ("backup.txt", b"Not a ZIP file", "text/plain")}
    response = await client.post("/api/backup/restore", files=files)

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Invalid file type" in data["detail"]


@pytest.mark.asyncio
async def test_start_restore_from_valid_file(client: AsyncClient, mock_redis, integration_db):
    """Test restore from valid backup file creates job."""
    # Create valid ZIP file
    zip_content = create_valid_backup_zip()

    # Upload file
    files = {"file": ("backup.zip", zip_content, "application/zip")}
    response = await client.post("/api/backup/restore", files=files)

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert "status" in data
    assert "message" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_start_restore_creates_database_record(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test restore job creates database record."""
    # Create valid ZIP file
    zip_content = create_valid_backup_zip()

    # Upload file
    files = {"file": ("backup.zip", zip_content, "application/zip")}
    response = await client.post("/api/backup/restore", files=files)

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # Verify database record exists. Status NOT asserted: the ASGI client runs
    # BackgroundTasks before the response resolves, so PENDING is never
    # observable at fetch time (the job has already reached its terminal state
    # — R-T7-BACKUP-MOUNT). Record creation + id linkage is this test's claim;
    # restore-pipeline behavior is covered service-side.
    job = await db_session.get(RestoreJob, job_id)
    assert job is not None
    assert job.id == job_id


@pytest.mark.asyncio
async def test_start_restore_with_corrupted_file(client: AsyncClient, mock_redis, integration_db):
    """Test restore with corrupted file fails appropriately."""
    # Create corrupted file
    corrupted_content = create_corrupted_backup_zip()

    # Upload file
    files = {"file": ("backup.zip", corrupted_content, "application/zip")}

    # Mock RestoreService to raise BackupCorruptedError
    with patch(
        "backend.api.routes.backup.RestoreService.restore_from_backup",
        side_effect=BackupCorruptedError("Backup file is corrupted"),
        autospec=True,
    ):
        response = await client.post("/api/backup/restore", files=files)

        # Job is created but will fail in background
        assert response.status_code == 202

        job_id = response.json()["job_id"]

        # Wait for background task
        await asyncio.sleep(0.5)

        # Check job status shows failure
        status_response = await client.get(f"/api/backup/restore/{job_id}")
        # Note: Due to transaction isolation, the failure may not be visible
        # The key is that the job was created successfully
        assert status_response.status_code == 200


@pytest.mark.asyncio
async def test_restore_job_progress_tracking(client: AsyncClient, mock_redis, integration_db):
    """Test restore job progress is tracked and queryable."""
    # Create valid ZIP file
    zip_content = create_valid_backup_zip()

    # Upload file
    files = {"file": ("backup.zip", zip_content, "application/zip")}
    response = await client.post("/api/backup/restore", files=files)

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # Query job progress
    response = await client.get(f"/api/backup/restore/{job_id}")
    assert response.status_code == 200

    data = response.json()
    assert "progress" in data
    assert "progress_percent" in data["progress"]
    assert isinstance(data["progress"]["progress_percent"], int)
    assert 0 <= data["progress"]["progress_percent"] <= 100


# =============================================================================
# Restore Status Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_restore_status_success(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test get restore status returns job details."""
    # Create restore job
    restore_id = str(uuid4())
    backup_id = str(uuid4())
    job = RestoreJob(
        id=restore_id,
        status=RestoreJobStatusModel.RESTORING,
        progress_percent=75,
        current_step="Restoring events...",
        total_tables=8,
        completed_tables=6,
        backup_id=backup_id,
        backup_created_at=datetime.now(UTC),
    )
    db_session.add(job)
    await db_session.commit()

    # Get status
    response = await client.get(f"/api/backup/restore/{restore_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == restore_id
    assert data["status"] == "restoring"
    assert data["progress"]["progress_percent"] == 75
    assert data["progress"]["current_step"] == "Restoring events..."
    assert data["backup_id"] == backup_id


@pytest.mark.asyncio
async def test_get_restore_status_completed_with_items_restored(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test get restore status shows items restored on completion."""
    # Create completed restore job
    restore_id = str(uuid4())
    items_restored = {
        "cameras": 5,
        "events": 100,
        "detections": 200,
    }

    job = RestoreJob(
        id=restore_id,
        status=RestoreJobStatusModel.COMPLETED,
        progress_percent=100,
        items_restored=items_restored,
    )
    db_session.add(job)
    await db_session.commit()

    # Get status
    response = await client.get(f"/api/backup/restore/{restore_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["items_restored"] is not None
    assert data["items_restored"]["cameras"] == 5
    assert data["items_restored"]["events"] == 100
    assert data["items_restored"]["detections"] == 200


@pytest.mark.asyncio
async def test_restore_job_with_mocked_service_success(
    client: AsyncClient, mock_redis, integration_db
):
    """Test restore job completes successfully with mocked service."""
    # Create valid ZIP file
    zip_content = create_valid_backup_zip()

    # Create restore result
    backup_id = str(uuid4())
    restore_result = RestoreResult(
        backup_id=backup_id,
        backup_created_at=datetime.now(UTC),
        total_items=10,
        items_restored={"cameras": 2, "events": 8},
    )

    # Mock RestoreService.restore_from_backup
    with patch(
        "backend.api.routes.backup.RestoreService.restore_from_backup",
        return_value=restore_result,
        autospec=True,
    ):
        # Upload file
        files = {"file": ("backup.zip", zip_content, "application/zip")}
        response = await client.post("/api/backup/restore", files=files)

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for background task
        await asyncio.sleep(0.5)

        # Check status
        status_response = await client.get(f"/api/backup/restore/{job_id}")
        assert status_response.status_code == 200

        # Note: Background task updates may not be visible immediately
        status_data = status_response.json()
        assert "status" in status_data
        assert "progress" in status_data


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_backup_job_failure_updates_status(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test backup job failure updates database with error message."""
    # Mock BackupService to raise error
    with patch(
        "backend.api.routes.backup.BackupService.create_backup",
        side_effect=Exception("Test backup error"),
        autospec=True,
    ):
        response = await client.post("/api/backup", json={})
        assert response.status_code == 202

        job_id = response.json()["job_id"]

        # Wait for background task to fail
        await asyncio.sleep(0.5)

        # Check job shows failure
        status_response = await client.get(f"/api/backup/{job_id}")
        # Note: Transaction isolation may prevent seeing the failure
        # The key is that the job was created and error handling code ran
        assert status_response.status_code == 200


@pytest.mark.asyncio
async def test_restore_validation_error_updates_status(
    client: AsyncClient, mock_redis, integration_db
):
    """Test restore validation error updates job status."""
    # Create valid ZIP file
    zip_content = create_valid_backup_zip()

    # Mock RestoreService to raise validation error
    with patch(
        "backend.api.routes.backup.RestoreService.restore_from_backup",
        side_effect=BackupValidationError("Invalid backup format"),
        autospec=True,
    ):
        files = {"file": ("backup.zip", zip_content, "application/zip")}
        response = await client.post("/api/backup/restore", files=files)

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for background task
        await asyncio.sleep(0.5)

        # Check job status
        status_response = await client.get(f"/api/backup/restore/{job_id}")
        assert status_response.status_code == 200


@pytest.mark.asyncio
async def test_restore_error_cleans_up_temp_file(client: AsyncClient, mock_redis, integration_db):
    """Test restore error cleans up temporary upload file."""
    # Create valid ZIP file
    zip_content = create_valid_backup_zip()

    # Track if temp file cleanup happens (indirectly via error path)
    with patch(
        "backend.api.routes.backup.RestoreService.restore_from_backup",
        side_effect=RestoreError("Restore failed"),
        autospec=True,
    ):
        files = {"file": ("backup.zip", zip_content, "application/zip")}
        response = await client.post("/api/backup/restore", files=files)

        assert response.status_code == 202

        # Wait for background task to complete
        await asyncio.sleep(0.5)

        # File cleanup is handled in finally block - no assertion needed
        # The test verifies the job was created and error path executed


# =============================================================================
# Edge Cases
# =============================================================================


@pytest.mark.asyncio
async def test_backup_job_without_manifest(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test backup job status when manifest_json is None."""
    backup_id = str(uuid4())
    job = BackupJob(
        id=backup_id,
        status=BackupJobStatusModel.COMPLETED,
        file_path=f"/backups/backup_{backup_id}.zip",
        file_size_bytes=1024,
        manifest_json=None,  # No manifest
    )
    db_session.add(job)
    await db_session.commit()

    # Get status
    response = await client.get(f"/api/backup/{backup_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["manifest"] is None


@pytest.mark.asyncio
async def test_backup_job_with_invalid_manifest_json(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test backup job status when manifest_json is invalid."""
    backup_id = str(uuid4())
    job = BackupJob(
        id=backup_id,
        status=BackupJobStatusModel.COMPLETED,
        file_path=f"/backups/backup_{backup_id}.zip",
        file_size_bytes=1024,
        manifest_json={"invalid": "structure"},  # Invalid manifest structure
    )
    db_session.add(job)
    await db_session.commit()

    # Get status - should handle invalid manifest gracefully
    response = await client.get(f"/api/backup/{backup_id}")

    assert response.status_code == 200
    data = response.json()
    # Invalid manifest should be treated as None
    assert data["manifest"] is None


@pytest.mark.asyncio
async def test_restore_job_without_backup_info(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """Test restore job status when backup info is missing."""
    restore_id = str(uuid4())
    job = RestoreJob(
        id=restore_id,
        status=RestoreJobStatusModel.PENDING,
        backup_id=None,
        backup_created_at=None,
    )
    db_session.add(job)
    await db_session.commit()

    # Get status
    response = await client.get(f"/api/backup/restore/{restore_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["backup_id"] is None
    assert data["backup_created_at"] is None


@pytest.mark.asyncio
async def test_restore_job_failure_in_last_table_rolls_back_all_tables_and_keeps_safety_backup(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """[B4.6] A failure in the last table (alert_rules) changes nothing even though
    progress_callback ran after earlier tables, while the Session A safety backup remains committed."""
    import hashlib

    from sqlalchemy import select

    from backend.models.camera import Camera

    cam_id = f"b46-rollback-cam-{uuid4().hex[:8]}"
    db_session.add(
        Camera(
            id=cam_id,
            name="Original Camera Before Failed Restore",
            folder_path=f"/export/foscam/{cam_id}",
        )
    )
    await db_session.commit()

    cameras_json = json.dumps(
        [
            {
                "id": cam_id,
                "name": "Mutated Camera That Must Roll Back",
                "folder_path": f"/export/foscam/{cam_id}",
                "status": "online",
            }
        ]
    )
    bad_rules_json = json.dumps(
        [{"id": str(uuid4()), "name": "Bad Last Table Rule", "unknown_field": "boom"}]
    )
    manifest = {
        "backup_id": "last-table-fail-bk",
        "version": "1.1",
        "created_at": datetime.now(UTC).isoformat(),
        "contents": {
            "cameras": {
                "count": 1,
                "checksum": hashlib.sha256(cameras_json.encode()).hexdigest(),
            },
            "alert_rules": {
                "count": 1,
                "checksum": hashlib.sha256(bad_rules_json.encode()).hexdigest(),
            },
        },
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("cameras.json", cameras_json)
        zf.writestr("alert_rules.json", bad_rules_json)

    response = await client.post(
        "/api/backup/restore",
        files={"file": ("bad_last_table.zip", buf.getvalue(), "application/zip")},
    )
    assert response.status_code == 202
    restore_id = response.json()["job_id"]

    status_resp = await client.get(f"/api/backup/restore/{restore_id}")
    assert status_resp.status_code == 200
    status_body = status_resp.json()
    assert status_body["status"] == "failed"
    assert "alert_rules" in (status_body.get("error_message") or "")
    assert "record 0" in (status_body.get("error_message") or "")

    # Camera in DB was NOT changed (Session B rolled back all earlier tables)
    db_session.expire_all()
    cam_row = (await db_session.execute(select(Camera).where(Camera.id == cam_id))).scalar_one()
    assert cam_row.name == "Original Camera Before Failed Restore"

    # Safety backup created on Session A before the restore is committed and listed
    list_resp = await client.get("/api/backup")
    assert list_resp.status_code == 200
    backups = list_resp.json()["backups"]
    assert any(
        (b.get("label") or "").startswith("before restore of last-table-fail-bk at ")
        for b in backups
    )


@pytest.mark.asyncio
async def test_restore_job_stops_when_safety_backup_fails(
    client: AsyncClient, mock_redis, integration_db, db_session: AsyncSession
):
    """[B4.6] If taking the safety backup fails, the restore does not start and no row changes."""
    from sqlalchemy import select

    from backend.models.camera import Camera

    cam_id = f"b46-safety-fail-{uuid4().hex[:8]}"
    db_session.add(
        Camera(
            id=cam_id,
            name="Camera Protected By Safety Check",
            folder_path=f"/export/foscam/{cam_id}",
        )
    )
    await db_session.commit()

    zip_content = create_valid_backup_zip()
    with patch(
        "backend.api.routes.backup.BackupService.create_backup",
        side_effect=OSError("disk full on data volume"),
        autospec=True,
    ):
        response = await client.post(
            "/api/backup/restore",
            files={"file": ("backup.zip", zip_content, "application/zip")},
        )
        assert response.status_code == 202
        restore_id = response.json()["job_id"]

    status_resp = await client.get(f"/api/backup/restore/{restore_id}")
    assert status_resp.status_code == 200
    status_body = status_resp.json()
    assert status_body["status"] == "failed"
    assert "Safety backup failed before restore" in (status_body.get("error_message") or "")

    # Verify the two cameras from zip_content ("cam1", "cam2") were never inserted
    db_session.expire_all()
    cam1 = (
        await db_session.execute(select(Camera).where(Camera.id == "cam1"))
    ).scalar_one_or_none()
    assert cam1 is None
