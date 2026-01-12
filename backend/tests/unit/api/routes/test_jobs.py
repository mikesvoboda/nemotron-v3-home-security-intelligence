"""Tests for the Jobs API routes (NEM-1989, NEM-1972)."""

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


class TestListJobs:
    """Tests for GET /api/jobs."""

    def test_list_jobs_empty(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should return empty list when no jobs exist."""
        mock_job_tracker.get_all_jobs.return_value = []

        response = client.get("/api/jobs")
        assert response.status_code == 200

        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0
        assert data["pagination"]["limit"] == 50
        assert data["pagination"]["offset"] == 0
        assert data["pagination"]["has_more"] is False

    def test_list_jobs_returns_jobs(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should return list of jobs."""
        mock_job_tracker.get_all_jobs.return_value = [
            JobInfo(
                job_id="job-1",
                job_type="export",
                status=JobStatus.RUNNING,
                progress=50,
                message="Processing...",
                created_at="2024-01-15T10:30:00Z",
                started_at="2024-01-15T10:30:01Z",
                completed_at=None,
                result=None,
                error=None,
            ),
            JobInfo(
                job_id="job-2",
                job_type="cleanup",
                status=JobStatus.COMPLETED,
                progress=100,
                message="Completed",
                created_at="2024-01-15T10:00:00Z",
                started_at="2024-01-15T10:00:01Z",
                completed_at="2024-01-15T10:05:00Z",
                result=None,
                error=None,
            ),
        ]

        response = client.get("/api/jobs")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 2
        assert data["pagination"]["total"] == 2
        assert data["items"][0]["job_id"] == "job-1"
        assert data["items"][1]["job_id"] == "job-2"

    def test_list_jobs_filter_by_type(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should filter jobs by type."""
        mock_job_tracker.get_all_jobs.return_value = [
            JobInfo(
                job_id="export-job",
                job_type="export",
                status=JobStatus.RUNNING,
                progress=50,
                message="Processing...",
                created_at="2024-01-15T10:30:00Z",
                started_at=None,
                completed_at=None,
                result=None,
                error=None,
            ),
        ]

        response = client.get("/api/jobs?job_type=export")
        assert response.status_code == 200

        mock_job_tracker.get_all_jobs.assert_called_once_with(job_type="export", status_filter=None)

    def test_list_jobs_filter_by_status(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should filter jobs by status."""
        mock_job_tracker.get_all_jobs.return_value = []

        response = client.get("/api/jobs?status=running")
        assert response.status_code == 200

        mock_job_tracker.get_all_jobs.assert_called_once_with(
            job_type=None, status_filter=JobStatus.RUNNING
        )

    def test_list_jobs_filter_by_type_and_status(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should filter jobs by both type and status."""
        mock_job_tracker.get_all_jobs.return_value = []

        response = client.get("/api/jobs?job_type=export&status=pending")
        assert response.status_code == 200

        mock_job_tracker.get_all_jobs.assert_called_once_with(
            job_type="export", status_filter=JobStatus.PENDING
        )

    def test_list_jobs_with_pagination(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should support pagination with limit and offset."""
        # Create 5 jobs
        jobs = [
            JobInfo(
                job_id=f"job-{i}",
                job_type="export",
                status=JobStatus.COMPLETED,
                progress=100,
                message="Done",
                created_at=f"2024-01-15T10:{i:02d}:00Z",
                started_at=f"2024-01-15T10:{i:02d}:01Z",
                completed_at=f"2024-01-15T10:{i:02d}:30Z",
                result=None,
                error=None,
            )
            for i in range(5)
        ]
        mock_job_tracker.get_all_jobs.return_value = jobs

        # Request with limit=2, offset=1
        response = client.get("/api/jobs?limit=2&offset=1")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["offset"] == 1
        assert data["pagination"]["has_more"] is True

    def test_list_jobs_pagination_last_page(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should indicate no more items on last page."""
        # Create 3 jobs
        jobs = [
            JobInfo(
                job_id=f"job-{i}",
                job_type="export",
                status=JobStatus.COMPLETED,
                progress=100,
                message="Done",
                created_at=f"2024-01-15T10:{i:02d}:00Z",
                started_at=None,
                completed_at=None,
                result=None,
                error=None,
            )
            for i in range(3)
        ]
        mock_job_tracker.get_all_jobs.return_value = jobs

        # Request page that spans to end
        response = client.get("/api/jobs?limit=50&offset=0")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 3
        assert data["pagination"]["has_more"] is False


class TestGetJobStats:
    """Tests for GET /api/jobs/stats."""

    def test_get_job_stats_empty(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should return zero stats when no jobs exist."""
        mock_job_tracker.get_all_jobs.return_value = []

        response = client.get("/api/jobs/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_jobs"] == 0
        assert data["by_status"] == []
        assert data["by_type"] == []
        assert data["average_duration_seconds"] is None
        assert data["oldest_pending_job_age_seconds"] is None

    def test_get_job_stats_with_jobs(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should return correct stats for multiple jobs."""
        mock_job_tracker.get_all_jobs.return_value = [
            JobInfo(
                job_id="job-1",
                job_type="export",
                status=JobStatus.COMPLETED,
                progress=100,
                message="Done",
                created_at="2024-01-15T10:00:00+00:00",
                started_at="2024-01-15T10:00:01+00:00",
                completed_at="2024-01-15T10:00:31+00:00",  # 30 second duration
                result=None,
                error=None,
            ),
            JobInfo(
                job_id="job-2",
                job_type="export",
                status=JobStatus.COMPLETED,
                progress=100,
                message="Done",
                created_at="2024-01-15T10:01:00+00:00",
                started_at="2024-01-15T10:01:01+00:00",
                completed_at="2024-01-15T10:02:01+00:00",  # 60 second duration
                result=None,
                error=None,
            ),
            JobInfo(
                job_id="job-3",
                job_type="cleanup",
                status=JobStatus.RUNNING,
                progress=50,
                message="Processing...",
                created_at="2024-01-15T10:02:00+00:00",
                started_at="2024-01-15T10:02:01+00:00",
                completed_at=None,
                result=None,
                error=None,
            ),
            JobInfo(
                job_id="job-4",
                job_type="backup",
                status=JobStatus.FAILED,
                progress=20,
                message="Failed",
                created_at="2024-01-15T10:03:00+00:00",
                started_at="2024-01-15T10:03:01+00:00",
                completed_at="2024-01-15T10:03:05+00:00",
                result=None,
                error="Connection error",
            ),
        ]

        response = client.get("/api/jobs/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_jobs"] == 4

        # Check status counts
        status_map = {s["status"]: s["count"] for s in data["by_status"]}
        assert status_map.get("completed", 0) == 2
        assert status_map.get("running", 0) == 1
        assert status_map.get("failed", 0) == 1

        # Check type counts
        type_map = {t["job_type"]: t["count"] for t in data["by_type"]}
        assert type_map["export"] == 2
        assert type_map["cleanup"] == 1
        assert type_map["backup"] == 1

        # Average duration should be (30 + 60) / 2 = 45 seconds
        assert data["average_duration_seconds"] == 45.0

    def test_get_job_stats_with_pending_job(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should calculate oldest pending job age."""
        mock_job_tracker.get_all_jobs.return_value = [
            JobInfo(
                job_id="job-pending",
                job_type="export",
                status=JobStatus.PENDING,
                progress=0,
                message=None,
                created_at="2024-01-15T10:00:00+00:00",
                started_at=None,
                completed_at=None,
                result=None,
                error=None,
            ),
        ]

        response = client.get("/api/jobs/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_jobs"] == 1
        # oldest_pending_job_age_seconds should be a positive number
        assert data["oldest_pending_job_age_seconds"] is not None
        assert data["oldest_pending_job_age_seconds"] > 0


class TestListJobTypes:
    """Tests for GET /api/jobs/types."""

    def test_list_job_types(self, client: TestClient) -> None:
        """Should return list of available job types."""
        response = client.get("/api/jobs/types")
        assert response.status_code == 200

        data = response.json()
        assert "job_types" in data
        assert len(data["job_types"]) > 0

        # Verify export type is included
        type_names = [jt["name"] for jt in data["job_types"]]
        assert "export" in type_names

        # Verify structure
        for job_type in data["job_types"]:
            assert "name" in job_type
            assert "description" in job_type


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

        response = client.get("/api/jobs/test-job-123")
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

        response = client.get("/api/jobs/test-job-456")
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

        response = client.get("/api/jobs/test-job-789")
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

        response = client.get("/api/jobs/nonexistent-job")
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

        response = client.get("/api/jobs/redis-job-123")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "redis-job-123"


class TestCancelJob:
    """Tests for POST /api/jobs/{job_id}/cancel."""

    def test_cancel_job_success(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should cancel a running job."""
        mock_job_tracker.cancel_job.return_value = True

        response = client.post("/api/jobs/job-123/cancel")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["status"] == "failed"
        assert "cancellation" in data["message"].lower()

        mock_job_tracker.cancel_job.assert_called_once_with("job-123")

    def test_cancel_job_not_found(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should return 404 when job not found."""
        mock_job_tracker.cancel_job.side_effect = KeyError("Job not found")

        response = client.post("/api/jobs/nonexistent/cancel")
        assert response.status_code == 404

        data = response.json()
        assert "No job found" in data["detail"]

    def test_cancel_job_already_completed(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should return 409 when job already completed."""
        mock_job_tracker.cancel_job.return_value = False

        response = client.post("/api/jobs/completed-job/cancel")
        assert response.status_code == 409

        data = response.json()
        assert "cannot be cancelled" in data["detail"]


class TestStartExportJob:
    """Tests for POST /api/events/export."""

    def test_start_export_job_csv(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should start CSV export job."""
        mock_job_tracker.create_job.return_value = "export-job-001"

        response = client.post(
            "/api/events/export",
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
            "/api/events/export",
            json={"format": "json"},
        )
        assert response.status_code == 202

        data = response.json()
        assert data["job_id"] == "export-job-002"

    def test_start_export_job_zip(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should start ZIP export job."""
        mock_job_tracker.create_job.return_value = "export-job-003"

        response = client.post(
            "/api/events/export",
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
            "/api/events/export",
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
            "/api/events/export",
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

    def test_job_list_response(self) -> None:
        """Should serialize JobListResponse correctly."""
        from backend.api.schemas.jobs import JobListResponse, JobResponse, JobStatusEnum
        from backend.api.schemas.pagination import create_pagination_meta

        job = JobResponse(
            job_id="test-123",
            job_type="export",
            status=JobStatusEnum.RUNNING,
            progress=50,
            message="Processing...",
            created_at="2024-01-15T10:30:00Z",
        )

        pagination = create_pagination_meta(total=1, limit=50, offset=0, items_count=1)
        response = JobListResponse(items=[job], pagination=pagination)

        data = response.model_dump()
        assert data["pagination"]["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["job_id"] == "test-123"

    def test_job_types_response(self) -> None:
        """Should serialize JobTypesResponse correctly."""
        from backend.api.schemas.jobs import JobTypeInfo, JobTypesResponse

        job_type = JobTypeInfo(name="export", description="Export events")
        response = JobTypesResponse(job_types=[job_type])

        data = response.model_dump()
        assert len(data["job_types"]) == 1
        assert data["job_types"][0]["name"] == "export"

    def test_job_cancel_response(self) -> None:
        """Should serialize JobCancelResponse correctly."""
        from backend.api.schemas.jobs import JobCancelResponse, JobStatusEnum

        response = JobCancelResponse(
            job_id="test-123",
            status=JobStatusEnum.FAILED,
            message="Job cancelled",
        )

        data = response.model_dump()
        assert data["job_id"] == "test-123"
        assert data["status"] == "failed"
        assert data["message"] == "Job cancelled"
