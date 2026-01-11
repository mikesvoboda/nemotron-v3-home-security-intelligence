"""Tests for the Jobs API routes (NEM-1989)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.jobs import router
from backend.services.job_tracker import JobInfo, JobStatus, JobTracker


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
def app(mock_job_tracker: MagicMock, mock_export_service: MagicMock) -> FastAPI:
    """Create a test FastAPI app with mocked dependencies."""
    from backend.api.dependencies import get_export_service_dep, get_job_tracker_dep

    test_app = FastAPI()
    test_app.include_router(router)

    test_app.dependency_overrides[get_job_tracker_dep] = lambda: mock_job_tracker
    test_app.dependency_overrides[get_export_service_dep] = lambda: mock_export_service

    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


class TestGetJobStatus:
    """Tests for GET /api/jobs/{job_id}."""

    def test_get_job_status_returns_job(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should return job status when job exists."""
        mock_job_tracker.get_job.return_value = JobInfo(
            job_id="test-job-123",
            job_type="export",
            status=JobStatus.RUNNING,
            progress=45,
            message="Processing events...",
            created_at="2024-01-15T10:30:00Z",
            started_at="2024-01-15T10:30:01Z",
            completed_at=None,
            result=None,
            error=None,
        )

        response = client.get("/jobs/test-job-123")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "test-job-123"
        assert data["job_type"] == "export"
        assert data["status"] == "running"
        assert data["progress"] == 45
        assert data["message"] == "Processing events..."

    def test_get_job_status_completed(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should return completed job with result."""
        mock_job_tracker.get_job.return_value = JobInfo(
            job_id="test-job-456",
            job_type="export",
            status=JobStatus.COMPLETED,
            progress=100,
            message="Completed successfully",
            created_at="2024-01-15T10:30:00Z",
            started_at="2024-01-15T10:30:01Z",
            completed_at="2024-01-15T10:31:00Z",
            result={
                "file_path": "/api/exports/events.csv",
                "file_size": 12345,
                "event_count": 100,
                "format": "csv",
            },
            error=None,
        )

        response = client.get("/jobs/test-job-456")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert data["result"]["file_path"] == "/api/exports/events.csv"
        assert data["result"]["event_count"] == 100

    def test_get_job_status_failed(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should return failed job with error."""
        mock_job_tracker.get_job.return_value = JobInfo(
            job_id="test-job-789",
            job_type="export",
            status=JobStatus.FAILED,
            progress=30,
            message="Failed: Database connection error",
            created_at="2024-01-15T10:30:00Z",
            started_at="2024-01-15T10:30:01Z",
            completed_at="2024-01-15T10:30:30Z",
            result=None,
            error="Database connection error",
        )

        response = client.get("/jobs/test-job-789")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Database connection error"

    def test_get_job_status_not_found(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should return 404 when job not found."""
        mock_job_tracker.get_job.return_value = None
        mock_job_tracker.get_job_from_redis = AsyncMock(return_value=None)

        response = client.get("/jobs/nonexistent-job")
        assert response.status_code == 404

        data = response.json()
        assert "No job found" in data["detail"]

    def test_get_job_status_from_redis(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should fall back to Redis when job not in memory."""
        mock_job_tracker.get_job.return_value = None
        mock_job_tracker.get_job_from_redis = AsyncMock(
            return_value=JobInfo(
                job_id="redis-job-123",
                job_type="export",
                status=JobStatus.COMPLETED,
                progress=100,
                message="Completed successfully",
                created_at="2024-01-15T10:30:00Z",
                started_at="2024-01-15T10:30:01Z",
                completed_at="2024-01-15T10:31:00Z",
                result=None,
                error=None,
            )
        )

        response = client.get("/jobs/redis-job-123")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "redis-job-123"


class TestStartExportJob:
    """Tests for POST /api/events/export."""

    def test_start_export_job_csv(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should start CSV export job."""
        mock_job_tracker.create_job.return_value = "export-job-001"

        response = client.post(
            "/events/export",
            json={"format": "csv"},
        )
        assert response.status_code == 202

        data = response.json()
        assert data["job_id"] == "export-job-001"
        assert data["status"] == "pending"
        assert "GET /api/jobs" in data["message"]

    def test_start_export_job_json(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should start JSON export job."""
        mock_job_tracker.create_job.return_value = "export-job-002"

        response = client.post(
            "/events/export",
            json={"format": "json"},
        )
        assert response.status_code == 202

        data = response.json()
        assert data["job_id"] == "export-job-002"

    def test_start_export_job_zip(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should start ZIP export job."""
        mock_job_tracker.create_job.return_value = "export-job-003"

        response = client.post(
            "/events/export",
            json={"format": "zip"},
        )
        assert response.status_code == 202

        data = response.json()
        assert data["job_id"] == "export-job-003"

    def test_start_export_job_with_filters(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should accept filter parameters."""
        mock_job_tracker.create_job.return_value = "export-job-004"

        response = client.post(
            "/events/export",
            json={
                "format": "csv",
                "camera_id": "cam-1",
                "risk_level": "high",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-15T23:59:59Z",
                "reviewed": True,
            },
        )
        assert response.status_code == 202

        data = response.json()
        assert data["job_id"] == "export-job-004"

    def test_start_export_job_invalid_format(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should reject invalid export format."""
        response = client.post(
            "/events/export",
            json={"format": "invalid"},
        )
        assert response.status_code == 422


class TestJobSchemas:
    """Tests for job-related Pydantic schemas."""

    def test_job_response_serialization(self) -> None:
        """Should serialize JobResponse correctly."""
        from backend.api.schemas.jobs import JobResponse, JobStatusEnum

        response = JobResponse(
            job_id="test-123",
            job_type="export",
            status=JobStatusEnum.RUNNING,
            progress=50,
            message="Processing...",
            created_at="2024-01-15T10:30:00Z",
        )

        data = response.model_dump()
        assert data["job_id"] == "test-123"
        assert data["status"] == "running"
        assert data["progress"] == 50

    def test_export_job_request_validation(self) -> None:
        """Should validate ExportJobRequest."""
        from backend.api.schemas.jobs import ExportFormat, ExportJobRequest

        request = ExportJobRequest(
            format=ExportFormat.CSV,
            risk_level="high",
        )

        assert request.format == ExportFormat.CSV
        assert request.risk_level == "high"
        assert request.camera_id is None
