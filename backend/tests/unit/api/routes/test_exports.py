"""Tests for the Exports API routes (NEM-2385)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.exports import router
from backend.api.schemas.export import (
    ExportFormatEnum,
    ExportJobStatusEnum,
    ExportTypeEnum,
)
from backend.models.export_job import ExportJob, ExportJobStatus
from backend.services.job_tracker import JobTracker


@pytest.fixture
def mock_job_tracker() -> MagicMock:
    """Create a mock job tracker."""
    tracker = MagicMock(spec=JobTracker)
    return tracker


@pytest.fixture
def mock_export_service() -> MagicMock:
    """Create a mock export service."""
    service = MagicMock()
    service.export_events_with_progress = AsyncMock()
    return service


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def sample_export_job() -> ExportJob:
    """Create a sample export job for testing."""
    job = ExportJob(
        id=str(uuid4()),
        status=ExportJobStatus.PENDING,
        export_type="events",
        export_format="csv",
        total_items=None,
        processed_items=0,
        progress_percent=0,
        current_step=None,
        created_at=datetime.now(UTC),
        started_at=None,
        completed_at=None,
        estimated_completion=None,
        output_path=None,
        output_size_bytes=None,
        error_message=None,
        filter_params=None,
    )
    return job


@pytest.fixture
def app(mock_job_tracker: MagicMock, mock_export_service: MagicMock, mock_db: AsyncMock) -> FastAPI:
    """Create a test FastAPI app with mocked dependencies."""
    from backend.api.dependencies import get_export_service_dep, get_job_tracker_dep
    from backend.core.database import get_db

    test_app = FastAPI()
    test_app.include_router(router)

    test_app.dependency_overrides[get_job_tracker_dep] = lambda: mock_job_tracker
    test_app.dependency_overrides[get_export_service_dep] = lambda: mock_export_service
    test_app.dependency_overrides[get_db] = lambda: mock_db

    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


class TestStartExport:
    """Tests for POST /api/exports."""

    def test_start_export_creates_job(
        self,
        client: TestClient,
        mock_job_tracker: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Should create an export job and return 202."""
        mock_job_tracker.create_job.return_value = "test-job-id"

        response = client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
            },
        )
        assert response.status_code == 202

        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert "message" in data
        assert "GET /api/exports" in data["message"]

    def test_start_export_with_filters(
        self,
        client: TestClient,
        mock_job_tracker: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Should accept filter parameters."""
        mock_job_tracker.create_job.return_value = "test-job-id"

        response = client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "csv",
                "camera_id": "front_door",
                "risk_level": "high",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-12T23:59:59Z",
                "reviewed": True,
            },
        )
        assert response.status_code == 202

    def test_start_export_json_format(
        self,
        client: TestClient,
        mock_job_tracker: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Should accept JSON export format."""
        mock_job_tracker.create_job.return_value = "test-job-id"

        response = client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "json",
            },
        )
        assert response.status_code == 202

    def test_start_export_invalid_format(
        self,
        client: TestClient,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should reject invalid export format."""
        response = client.post(
            "/api/exports",
            json={
                "export_type": "events",
                "export_format": "invalid",
            },
        )
        assert response.status_code == 422

    def test_start_export_invalid_type(
        self,
        client: TestClient,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should reject invalid export type."""
        response = client.post(
            "/api/exports",
            json={
                "export_type": "invalid",
                "export_format": "csv",
            },
        )
        assert response.status_code == 422


class TestListExports:
    """Tests for GET /api/exports."""

    def test_list_exports_empty(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should return empty list when no jobs exist."""
        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/exports")
        assert response.status_code == 200

        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0

    def test_list_exports_with_jobs(
        self,
        client: TestClient,
        mock_db: AsyncMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should return list of export jobs."""
        # Mock result with one job
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_export_job]
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/exports")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == sample_export_job.id
        assert data["items"][0]["status"] == "pending"

    def test_list_exports_with_status_filter(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should filter by status."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/exports?status=running")
        assert response.status_code == 200

    def test_list_exports_pagination(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should support pagination."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/exports?limit=10&offset=5")
        assert response.status_code == 200

        data = response.json()
        assert data["pagination"]["limit"] == 10
        assert data["pagination"]["offset"] == 5


class TestGetExportStatus:
    """Tests for GET /api/exports/{job_id}."""

    def test_get_export_status_found(
        self,
        client: TestClient,
        mock_db: AsyncMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should return export job status when found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/exports/{sample_export_job.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == sample_export_job.id
        assert data["status"] == "pending"
        assert data["export_type"] == "events"
        assert data["export_format"] == "csv"

    def test_get_export_status_not_found(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should return 404 when job not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/exports/nonexistent-id")
        assert response.status_code == 404

        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_export_status_running_with_progress(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should return progress info for running job."""
        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.RUNNING,
            export_type="events",
            export_format="csv",
            total_items=1000,
            processed_items=500,
            progress_percent=50,
            current_step="Processing events...",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=None,
            estimated_completion=None,
            output_path=None,
            output_size_bytes=None,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/exports/{job.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "running"
        assert data["progress"]["total_items"] == 1000
        assert data["progress"]["processed_items"] == 500
        assert data["progress"]["progress_percent"] == 50
        assert data["progress"]["current_step"] == "Processing events..."

    def test_get_export_status_completed_with_result(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should return result info for completed job."""
        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="csv",
            total_items=1000,
            processed_items=1000,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path="/api/exports/test.csv",
            output_size_bytes=12345,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/exports/{job.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "completed"
        assert data["result"] is not None
        assert data["result"]["output_path"] == "/api/exports/test.csv"
        assert data["result"]["output_size_bytes"] == 12345


class TestCancelExport:
    """Tests for DELETE /api/exports/{job_id}."""

    def test_cancel_export_success(
        self,
        client: TestClient,
        mock_db: AsyncMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should cancel a pending export job."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_job_tracker.cancel_job.return_value = True

        response = client.delete(f"/api/exports/{sample_export_job.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == sample_export_job.id
        assert data["status"] == "failed"
        assert data["cancelled"] is True

    def test_cancel_export_running(
        self,
        client: TestClient,
        mock_db: AsyncMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Should cancel a running export job."""
        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.RUNNING,
            export_type="events",
            export_format="csv",
            total_items=1000,
            processed_items=500,
            progress_percent=50,
            current_step="Processing...",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=None,
            estimated_completion=None,
            output_path=None,
            output_size_bytes=None,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_job_tracker.cancel_job.return_value = True

        response = client.delete(f"/api/exports/{job.id}")
        assert response.status_code == 200

    def test_cancel_export_not_found(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should return 404 when job not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.delete("/api/exports/nonexistent-id")
        assert response.status_code == 404

    def test_cancel_export_already_completed(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should return 409 when job already completed."""
        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="csv",
            total_items=1000,
            processed_items=1000,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path="/api/exports/test.csv",
            output_size_bytes=12345,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.delete(f"/api/exports/{job.id}")
        assert response.status_code == 409

        data = response.json()
        assert "cannot be cancelled" in data["detail"].lower()

    def test_cancel_export_already_failed(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should return 409 when job already failed."""
        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.FAILED,
            export_type="events",
            export_format="csv",
            total_items=1000,
            processed_items=500,
            progress_percent=50,
            current_step="Failed",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path=None,
            output_size_bytes=None,
            error_message="Connection error",
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.delete(f"/api/exports/{job.id}")
        assert response.status_code == 409


class TestDownloadExport:
    """Tests for GET /api/exports/{job_id}/download."""

    def test_download_export_not_found(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should return 404 when job not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/exports/nonexistent-id/download")
        assert response.status_code == 404

    def test_download_export_not_complete(
        self,
        client: TestClient,
        mock_db: AsyncMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should return 400 when job not complete."""
        sample_export_job.status = ExportJobStatus.RUNNING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/exports/{sample_export_job.id}/download")
        assert response.status_code == 400

        data = response.json()
        assert "not complete" in data["detail"].lower()

    def test_download_export_no_file_path(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should return 404 when file path not set."""
        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="csv",
            total_items=1000,
            processed_items=1000,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path=None,  # No file path
            output_size_bytes=None,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/exports/{job.id}/download")
        assert response.status_code == 404

        data = response.json()
        assert "path not found" in data["detail"].lower()


class TestGetDownloadInfo:
    """Tests for GET /api/exports/{job_id}/download/info."""

    def test_get_download_info_not_ready(
        self,
        client: TestClient,
        mock_db: AsyncMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Should return not ready when job not complete."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/exports/{sample_export_job.id}/download/info")
        assert response.status_code == 200

        data = response.json()
        assert data["ready"] is False
        assert data["filename"] is None

    def test_get_download_info_ready(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Should return download info when ready."""
        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.COMPLETED,
            export_type="events",
            export_format="csv",
            total_items=1000,
            processed_items=1000,
            progress_percent=100,
            current_step="Complete",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            estimated_completion=None,
            output_path="/api/exports/events_export_20250112.csv",
            output_size_bytes=12345,
            error_message=None,
            filter_params=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock file existence check
        with patch("backend.api.routes.exports.EXPORT_DIR") as mock_export_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_export_dir.__truediv__.return_value = mock_path

            response = client.get(f"/api/exports/{job.id}/download/info")
            assert response.status_code == 200

            data = response.json()
            assert data["ready"] is True
            assert data["filename"] == "events_export_20250112.csv"
            assert data["content_type"] == "text/csv"
            assert data["size_bytes"] == 12345


class TestExportSchemas:
    """Tests for export-related Pydantic schemas."""

    def test_export_job_create_defaults(self) -> None:
        """Should have sensible defaults."""
        from backend.api.schemas.export import ExportJobCreate

        request = ExportJobCreate()

        assert request.export_type == ExportTypeEnum.EVENTS
        assert request.export_format == ExportFormatEnum.CSV
        assert request.camera_id is None
        assert request.risk_level is None
        assert request.start_date is None
        assert request.end_date is None
        assert request.reviewed is None

    def test_export_job_response_serialization(self) -> None:
        """Should serialize ExportJobResponse correctly."""
        from backend.api.schemas.export import (
            ExportJobProgress,
            ExportJobResponse,
            ExportJobStatusEnum,
        )

        progress = ExportJobProgress(
            total_items=1000,
            processed_items=500,
            progress_percent=50,
            current_step="Processing...",
        )

        response = ExportJobResponse(
            id="test-123",
            status=ExportJobStatusEnum.RUNNING,
            export_type="events",
            export_format="csv",
            progress=progress,
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
        )

        data = response.model_dump()
        assert data["id"] == "test-123"
        assert data["status"] == "running"
        assert data["progress"]["progress_percent"] == 50

    def test_export_job_progress_defaults(self) -> None:
        """Should have zero defaults for progress."""
        from backend.api.schemas.export import ExportJobProgress

        progress = ExportJobProgress()

        assert progress.total_items is None
        assert progress.processed_items == 0
        assert progress.progress_percent == 0
        assert progress.current_step is None
        assert progress.estimated_completion is None

    def test_export_format_enum_values(self) -> None:
        """Should have correct format values."""
        assert ExportFormatEnum.CSV.value == "csv"
        assert ExportFormatEnum.JSON.value == "json"
        assert ExportFormatEnum.ZIP.value == "zip"
        assert ExportFormatEnum.EXCEL.value == "excel"

    def test_export_type_enum_values(self) -> None:
        """Should have correct type values."""
        assert ExportTypeEnum.EVENTS.value == "events"
        assert ExportTypeEnum.ALERTS.value == "alerts"
        assert ExportTypeEnum.FULL_BACKUP.value == "full_backup"

    def test_export_job_status_enum_values(self) -> None:
        """Should have correct status values."""
        assert ExportJobStatusEnum.PENDING.value == "pending"
        assert ExportJobStatusEnum.RUNNING.value == "running"
        assert ExportJobStatusEnum.COMPLETED.value == "completed"
        assert ExportJobStatusEnum.FAILED.value == "failed"
