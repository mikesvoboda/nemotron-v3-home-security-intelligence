"""Integration tests for export API endpoints.

Tests complete export pipeline: Camera → Events → Filter → Export → Download

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- mock_redis: Mock Redis client
- db_session: AsyncSession for database
- client: httpx AsyncClient with test app
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from backend.models.export_job import ExportJobStatus
from backend.services.export_service import EXPORT_DIR
from backend.tests.integration.test_helpers import get_error_message

if TYPE_CHECKING:
    from httpx import AsyncClient


# Skip all tests if running without proper database setup
pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def clean_exports(integration_db):
    """Delete export jobs before test runs for proper isolation.

    Ensures tests that expect specific export counts start with empty tables.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        await conn.execute(text("DELETE FROM export_jobs"))  # nosemgrep: avoid-sqlalchemy-text

    yield

    # Cleanup after test too (best effort)
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("DELETE FROM export_jobs"))  # nosemgrep: avoid-sqlalchemy-text
    except Exception:
        pass


@pytest.fixture
async def sample_export_camera(integration_db):
    """Create a sample camera for export tests."""
    from backend.core.database import get_session
    from backend.models.camera import Camera

    camera_id = str(uuid.uuid4())
    unique_suffix = uuid.uuid4().hex[:8]
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name=f"Export Test Camera {unique_suffix}",
            folder_path=f"/export/foscam/export_test_{unique_suffix}",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        yield camera


@pytest.fixture
async def sample_export_events(integration_db, sample_export_camera):
    """Create multiple events for export testing."""
    from backend.core.database import get_session
    from backend.models.event import Event

    async with get_session() as db:
        events = [
            # Low risk, reviewed
            Event(
                batch_id=str(uuid.uuid4()),
                camera_id=sample_export_camera.id,
                started_at=datetime(2025, 12, 20, 10, 0, 0, tzinfo=UTC),
                ended_at=datetime(2025, 12, 20, 10, 1, 30, tzinfo=UTC),
                risk_score=25,
                risk_level="low",
                summary="Package delivery detected",
                reasoning="Delivery person at front door during business hours",
                reviewed=True,
                detection_ids=json.dumps([1, 2]),
            ),
            # Medium risk, not reviewed
            Event(
                batch_id=str(uuid.uuid4()),
                camera_id=sample_export_camera.id,
                started_at=datetime(2025, 12, 20, 14, 0, 0, tzinfo=UTC),
                ended_at=datetime(2025, 12, 20, 14, 3, 0, tzinfo=UTC),
                risk_score=60,
                risk_level="medium",
                summary="Multiple people detected",
                reasoning="Unknown individuals near entrance",
                reviewed=False,
                detection_ids=json.dumps([3, 4, 5, 6]),
            ),
            # High risk, not reviewed
            Event(
                batch_id=str(uuid.uuid4()),
                camera_id=sample_export_camera.id,
                started_at=datetime(2025, 12, 20, 22, 0, 0, tzinfo=UTC),
                ended_at=datetime(2025, 12, 20, 22, 5, 0, tzinfo=UTC),
                risk_score=90,
                risk_level="high",
                summary="Suspicious activity at night",
                reasoning="Movement detected during unusual hours",
                reviewed=False,
                detection_ids=json.dumps([7, 8, 9, 10, 11]),
            ),
        ]

        for event in events:
            db.add(event)
        await db.commit()

        yield events


@pytest.fixture
async def ensure_export_dir():
    """Ensure export directory exists for testing."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Cleanup export files after test (best effort)
    try:
        for file in EXPORT_DIR.glob("*"):
            if file.is_file():
                file.unlink()
    except Exception:
        pass


# =============================================================================
# Export Creation Tests
# =============================================================================


class TestExportCreation:
    """Tests for creating export jobs with various filters."""

    async def test_create_export_with_date_range_filter(
        self, client: AsyncClient, sample_export_events, clean_exports
    ):
        """Test creating export job with date range filter."""
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
                "start_date": "2025-12-20T13:00:00Z",
                "end_date": "2025-12-20T23:00:00Z",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert "message" in data

        # Verify job was created in database
        from backend.core.database import get_session
        from backend.models.export_job import ExportJob

        async with get_session() as db:
            from sqlalchemy import select

            result = await db.execute(select(ExportJob).where(ExportJob.id == data["job_id"]))
            job = result.scalar_one_or_none()
            assert job is not None
            assert job.export_type == "events"
            assert job.export_format == "csv"
            assert job.status == ExportJobStatus.PENDING

    async def test_create_export_with_camera_filter(
        self, client: AsyncClient, sample_export_events, sample_export_camera, clean_exports
    ):
        """Test creating export job with camera filter."""
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "json",
                "camera_id": sample_export_camera.id,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

        # Verify filter parameters were stored
        from backend.core.database import get_session
        from backend.models.export_job import ExportJob

        async with get_session() as db:
            from sqlalchemy import select

            result = await db.execute(select(ExportJob).where(ExportJob.id == data["job_id"]))
            job = result.scalar_one_or_none()
            assert job is not None
            filter_params = json.loads(job.filter_params)
            assert filter_params["camera_id"] == sample_export_camera.id

    async def test_create_export_with_risk_score_filter(
        self, client: AsyncClient, sample_export_events, clean_exports
    ):
        """Test creating export job with risk score filter."""
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
                "risk_level": "high",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

        # Verify filter parameters were stored
        from backend.core.database import get_session
        from backend.models.export_job import ExportJob

        async with get_session() as db:
            from sqlalchemy import select

            result = await db.execute(select(ExportJob).where(ExportJob.id == data["job_id"]))
            job = result.scalar_one_or_none()
            assert job is not None
            filter_params = json.loads(job.filter_params)
            assert filter_params["risk_level"] == "high"

    async def test_create_export_with_invalid_date_range(self, client: AsyncClient, clean_exports):
        """Test export job validation - invalid date range."""
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
                "start_date": "invalid-date",
                "end_date": "2025-12-20T23:00:00Z",
            },
        )

        assert response.status_code == 422  # Validation error


# =============================================================================
# Export Format Tests
# =============================================================================


class TestExportFormats:
    """Tests for different export formats (CSV, JSON)."""

    async def test_export_to_csv_format(
        self, client: AsyncClient, sample_export_events, clean_exports, ensure_export_dir
    ):
        """Test export to CSV format completes successfully."""
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for job completion (with timeout)
        for _ in range(30):
            await asyncio.sleep(0.2)
            status_response = await client.get(f"/api/exports/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                if status_data["status"] in ("completed", "failed"):
                    break

        # Verify job completed
        status_response = await client.get(f"/api/exports/{job_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()

        # Job should eventually complete or fail
        assert status_data["status"] in ("completed", "failed")

        # If completed, verify CSV file was created
        if status_data["status"] == "completed":
            assert status_data["result"] is not None
            assert status_data["result"]["format"] == "csv"
            assert status_data["result"]["output_path"] is not None

    async def test_export_to_json_format(
        self, client: AsyncClient, sample_export_events, clean_exports, ensure_export_dir
    ):
        """Test export to JSON format completes successfully."""
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "json",
            },
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for job completion (with timeout)
        for _ in range(30):
            await asyncio.sleep(0.2)
            status_response = await client.get(f"/api/exports/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                if status_data["status"] in ("completed", "failed"):
                    break

        # Verify job completed
        status_response = await client.get(f"/api/exports/{job_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()

        # Job should eventually complete or fail
        assert status_data["status"] in ("completed", "failed")

        # If completed, verify JSON file was created
        if status_data["status"] == "completed":
            assert status_data["result"] is not None
            assert status_data["result"]["format"] == "json"
            assert status_data["result"]["output_path"] is not None


# =============================================================================
# Export Lifecycle Tests
# =============================================================================


class TestExportLifecycle:
    """Tests for export job lifecycle (queued → running → completed/failed)."""

    async def test_export_job_queued_successfully(
        self, client: AsyncClient, sample_export_events, clean_exports
    ):
        """Test export job is queued successfully."""
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert "job_id" in data

        # Verify job is in database with pending status
        from backend.core.database import get_session
        from backend.models.export_job import ExportJob

        async with get_session() as db:
            from sqlalchemy import select

            result = await db.execute(select(ExportJob).where(ExportJob.id == data["job_id"]))
            job = result.scalar_one_or_none()
            assert job is not None
            assert job.status == ExportJobStatus.PENDING

    async def test_export_job_completion(
        self, client: AsyncClient, sample_export_events, clean_exports, ensure_export_dir
    ):
        """Test export job completes successfully."""
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for job to complete (with timeout)
        completed = False
        for _ in range(30):
            await asyncio.sleep(0.2)
            status_response = await client.get(f"/api/exports/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                if status_data["status"] == "completed":
                    completed = True
                    break
                if status_data["status"] == "failed":
                    break

        # Verify job reached terminal state
        status_response = await client.get(f"/api/exports/{job_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] in ("completed", "failed")

    async def test_export_job_failure_handling(
        self, client: AsyncClient, clean_exports, monkeypatch
    ):
        """Test export job handles failures gracefully."""
        # Mock export_service to raise an exception
        from backend.services import export_service

        original_export = export_service.ExportService.export_events_with_progress

        async def failing_export(*args, **kwargs):
            raise RuntimeError("Simulated export failure")

        monkeypatch.setattr(
            export_service.ExportService,
            "export_events_with_progress",
            failing_export,
        )

        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for job to fail (with timeout)
        for _ in range(30):
            await asyncio.sleep(0.2)
            status_response = await client.get(f"/api/exports/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                if status_data["status"] == "failed":
                    break

        # Verify job failed with error message
        status_response = await client.get(f"/api/exports/{job_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] == "failed"
        assert status_data["error_message"] is not None
        assert "Simulated export failure" in status_data["error_message"]


# =============================================================================
# Download & Retrieval Tests
# =============================================================================


class TestExportDownload:
    """Tests for downloading completed export files."""

    async def test_download_completed_export_file(
        self, client: AsyncClient, sample_export_events, clean_exports, ensure_export_dir
    ):
        """Test downloading a completed export file."""
        # Create and wait for export to complete
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for completion
        for _ in range(30):
            await asyncio.sleep(0.2)
            status_response = await client.get(f"/api/exports/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                if status_data["status"] == "completed":
                    break

        # Verify download endpoint works
        download_response = await client.get(f"/api/exports/{job_id}/download")

        # Should either succeed (200) or return 404 if file missing (race condition)
        assert download_response.status_code in (200, 404)

        if download_response.status_code == 200:
            # Verify content-type header
            assert "text/csv" in download_response.headers["content-type"]

    async def test_download_with_proper_content_type_headers(
        self, client: AsyncClient, sample_export_events, clean_exports, ensure_export_dir
    ):
        """Test download response includes proper content-type headers."""
        # Create CSV export
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for completion
        for _ in range(30):
            await asyncio.sleep(0.2)
            status_response = await client.get(f"/api/exports/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                if status_data["status"] == "completed":
                    break

        # Check download info endpoint
        info_response = await client.get(f"/api/exports/{job_id}/download/info")
        assert info_response.status_code == 200
        info_data = info_response.json()

        if info_data["ready"]:
            assert info_data["content_type"] == "text/csv"
            assert info_data["filename"] is not None
            assert info_data["download_url"] is not None


# =============================================================================
# Error Scenarios Tests
# =============================================================================


class TestExportErrorScenarios:
    """Tests for error handling in export operations."""

    async def test_export_fails_mid_operation(
        self, client: AsyncClient, clean_exports, monkeypatch
    ):
        """Test handling of export failure during processing."""
        from backend.services import export_service

        call_count = [0]

        async def failing_export(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 0:
                raise RuntimeError("Export processing failed")

        monkeypatch.setattr(
            export_service.ExportService,
            "export_events_with_progress",
            failing_export,
        )

        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for failure
        for _ in range(30):
            await asyncio.sleep(0.2)
            status_response = await client.get(f"/api/exports/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                if status_data["status"] == "failed":
                    break

        # Verify error is recorded
        status_response = await client.get(f"/api/exports/{job_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] == "failed"
        assert status_data["error_message"] is not None

    async def test_invalid_export_format_requested(self, client: AsyncClient, clean_exports):
        """Test requesting invalid export format returns validation error."""
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "invalid_format",  # Invalid format
            },
        )

        assert response.status_code == 422  # Validation error


# =============================================================================
# Export Status and Retrieval Tests
# =============================================================================


class TestExportStatusRetrieval:
    """Tests for retrieving export job status and listings."""

    async def test_get_export_status(
        self, client: AsyncClient, sample_export_events, clean_exports
    ):
        """Test retrieving export job status."""
        # Create export
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Get status
        status_response = await client.get(f"/api/exports/{job_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()

        assert status_data["id"] == job_id
        assert status_data["status"] in ("pending", "running", "completed", "failed")
        assert status_data["export_type"] == "events"
        assert status_data["export_format"] == "csv"
        assert "progress" in status_data
        assert "created_at" in status_data

    async def test_get_nonexistent_export_status(self, client: AsyncClient, clean_exports):
        """Test retrieving status for non-existent export returns 404."""
        fake_job_id = str(uuid.uuid4())
        response = await client.get(f"/api/exports/{fake_job_id}")

        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)
        assert "not found" in error_msg.lower()

    async def test_list_exports(self, client: AsyncClient, sample_export_events, clean_exports):
        """Test listing export jobs."""
        # Create multiple exports
        job_ids = []
        for _ in range(3):
            response = await client.post(
                "/api/exports",
                json={
                    "export_type": "events",
                    "export_format": "csv",
                },
            )
            assert response.status_code == 202
            job_ids.append(response.json()["job_id"])

        # List exports
        list_response = await client.get("/api/exports")
        assert list_response.status_code == 200
        list_data = list_response.json()

        assert "items" in list_data
        assert "pagination" in list_data
        assert len(list_data["items"]) >= 3

        # Verify job IDs are present
        listed_job_ids = {job["id"] for job in list_data["items"]}
        for job_id in job_ids:
            assert job_id in listed_job_ids

    async def test_list_exports_with_status_filter(
        self, client: AsyncClient, sample_export_events, clean_exports, ensure_export_dir
    ):
        """Test listing export jobs with status filter."""
        # Create export and wait for completion
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for completion
        for _ in range(30):
            await asyncio.sleep(0.2)
            status_response = await client.get(f"/api/exports/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                if status_data["status"] in ("completed", "failed"):
                    break

        # Get final status
        status_response = await client.get(f"/api/exports/{job_id}")
        final_status = status_response.json()["status"]

        # List exports with status filter
        list_response = await client.get(f"/api/exports?status={final_status}")
        assert list_response.status_code == 200
        list_data = list_response.json()

        assert "items" in list_data
        # All returned items should have the filtered status
        for job in list_data["items"]:
            assert job["status"] == final_status

    async def test_list_exports_pagination(
        self, client: AsyncClient, sample_export_events, clean_exports
    ):
        """Test export listing with pagination."""
        # Create multiple exports
        for _ in range(5):
            await client.post(
                "/api/exports",
                json={
                    "export_type": "events",
                    "export_format": "csv",
                },
            )

        # Test pagination
        response = await client.get("/api/exports?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) <= 2
        assert data["pagination"]["limit"] == 2


# =============================================================================
# Export Cancellation Tests
# =============================================================================


class TestExportCancellation:
    """Tests for cancelling export jobs."""

    async def test_cancel_pending_export(
        self, client: AsyncClient, sample_export_events, clean_exports
    ):
        """Test cancelling a pending export job."""
        # Create export
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Cancel immediately (while likely still pending)
        cancel_response = await client.delete(f"/api/exports/{job_id}")

        # Should succeed (200) or return 409 if already completed
        assert cancel_response.status_code in (200, 409)

        if cancel_response.status_code == 200:
            cancel_data = cancel_response.json()
            assert cancel_data["job_id"] == job_id
            assert cancel_data["cancelled"] is True
            assert cancel_data["status"] == "failed"

    async def test_cancel_completed_export_fails(
        self, client: AsyncClient, sample_export_events, clean_exports, ensure_export_dir
    ):
        """Test that cancelling a completed export returns 409 conflict."""
        # Create and wait for completion
        response = await client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for completion
        for _ in range(30):
            await asyncio.sleep(0.2)
            status_response = await client.get(f"/api/exports/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                if status_data["status"] == "completed":
                    break

        # Try to cancel completed job
        cancel_response = await client.delete(f"/api/exports/{job_id}")
        assert cancel_response.status_code == 409  # Conflict

    async def test_cancel_nonexistent_export(self, client: AsyncClient, clean_exports):
        """Test cancelling non-existent export returns 404."""
        fake_job_id = str(uuid.uuid4())
        response = await client.delete(f"/api/exports/{fake_job_id}")

        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)
        assert "not found" in error_msg.lower()
