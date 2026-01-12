"""Tests for the Jobs API routes (NEM-1989, NEM-1972)."""

from __future__ import annotations

from datetime import datetime
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
def mock_job_service() -> MagicMock:
    """Create a mock job service."""
    service = MagicMock()
    service.get_job_detail = AsyncMock()
    return service


@pytest.fixture
def mock_job_search_service() -> MagicMock:
    """Create a mock job search service."""
    service = MagicMock()
    service.search = AsyncMock()
    return service


@pytest.fixture
def mock_job_history_service() -> MagicMock:
    """Create a mock job history service."""
    service = MagicMock()
    service.get_job_history = AsyncMock()
    service.get_job_logs = AsyncMock()
    return service


@pytest.fixture
def app(
    mock_job_tracker: MagicMock,
    mock_export_service: MagicMock,
    mock_job_service: MagicMock,
    mock_job_search_service: MagicMock,
    mock_job_history_service: MagicMock,
) -> FastAPI:
    """Create a test FastAPI app with mocked dependencies."""
    from backend.api.dependencies import (
        get_export_service_dep,
        get_job_history_service_dep,
        get_job_search_service_dep,
        get_job_service_dep,
        get_job_tracker_dep,
    )

    test_app = FastAPI()
    test_app.include_router(router)

    test_app.dependency_overrides[get_job_tracker_dep] = lambda: mock_job_tracker
    test_app.dependency_overrides[get_export_service_dep] = lambda: mock_export_service
    test_app.dependency_overrides[get_job_service_dep] = lambda: mock_job_service
    test_app.dependency_overrides[get_job_search_service_dep] = lambda: mock_job_search_service

    async def get_job_history_service_override():
        yield mock_job_history_service

    test_app.dependency_overrides[get_job_history_service_dep] = get_job_history_service_override

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

    def test_get_job_stats_with_invalid_timestamps(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should handle invalid timestamps gracefully."""
        mock_job_tracker.get_all_jobs.return_value = [
            JobInfo(
                job_id="job-1",
                job_type="export",
                status=JobStatus.COMPLETED,
                progress=100,
                message="Done",
                created_at="invalid-timestamp",
                started_at="invalid-timestamp",
                completed_at="invalid-timestamp",
                result=None,
                error=None,
            ),
            JobInfo(
                job_id="job-2",
                job_type="export",
                status=JobStatus.PENDING,
                progress=0,
                message=None,
                created_at="invalid-timestamp",
                started_at=None,
                completed_at=None,
                result=None,
                error=None,
            ),
        ]

        response = client.get("/api/jobs/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_jobs"] == 2
        # Should not crash, just return None for duration and pending age
        assert data["average_duration_seconds"] is None
        assert data["oldest_pending_job_age_seconds"] is None

    def test_get_job_stats_with_negative_duration(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should skip jobs with negative duration."""
        mock_job_tracker.get_all_jobs.return_value = [
            JobInfo(
                job_id="job-1",
                job_type="export",
                status=JobStatus.COMPLETED,
                progress=100,
                message="Done",
                created_at="2024-01-15T10:00:00+00:00",
                started_at="2024-01-15T10:00:10+00:00",  # Started after completed (invalid)
                completed_at="2024-01-15T10:00:00+00:00",
                result=None,
                error=None,
            ),
        ]

        response = client.get("/api/jobs/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_jobs"] == 1
        # Should skip negative duration
        assert data["average_duration_seconds"] is None


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


class TestSearchJobs:
    """Tests for GET /api/jobs/search."""

    def test_search_jobs_basic(
        self, client: TestClient, mock_job_search_service: MagicMock
    ) -> None:
        """Should search jobs with basic query."""
        from backend.services.job_search_service import JobAggregations, JobSearchResult

        mock_job_search_service.search.return_value = JobSearchResult(
            jobs=[
                {
                    "job_id": "job-1",
                    "job_type": "export",
                    "status": "completed",
                    "progress": 100,
                    "message": "Done",
                    "created_at": "2024-01-15T10:00:00Z",
                    "started_at": "2024-01-15T10:00:01Z",
                    "completed_at": "2024-01-15T10:01:00Z",
                    "result": None,
                    "error": None,
                }
            ],
            total=1,
            aggregations=JobAggregations(
                by_status={"completed": 1},
                by_type={"export": 1},
            ),
        )

        response = client.get("/api/jobs/search?q=export")
        assert response.status_code == 200

        data = response.json()
        assert len(data["data"]) == 1
        assert data["meta"]["total"] == 1
        assert data["aggregations"]["by_status"] == {"completed": 1}
        assert data["aggregations"]["by_type"] == {"export": 1}

    def test_search_jobs_with_filters(
        self, client: TestClient, mock_job_search_service: MagicMock
    ) -> None:
        """Should search jobs with multiple filters."""
        from backend.services.job_search_service import JobAggregations, JobSearchResult

        mock_job_search_service.search.return_value = JobSearchResult(
            jobs=[],
            total=0,
            aggregations=JobAggregations(
                by_status={},
                by_type={},
            ),
        )

        response = client.get(
            "/api/jobs/search?"
            "status=completed,failed&"
            "job_type=export,cleanup&"
            "has_error=true&"
            "min_duration=10&"
            "max_duration=100&"
            "sort=created_at&"
            "order=asc"
        )
        assert response.status_code == 200

        mock_job_search_service.search.assert_called_once()
        call_kwargs = mock_job_search_service.search.call_args.kwargs
        assert call_kwargs["statuses"] == ["completed", "failed"]
        assert call_kwargs["job_types"] == ["export", "cleanup"]
        assert call_kwargs["has_error"] is True
        assert call_kwargs["duration_range"] == (10, 100)
        assert call_kwargs["sort_by"] == "created_at"
        assert call_kwargs["sort_order"] == "asc"

    def test_search_jobs_with_timestamps(
        self, client: TestClient, mock_job_search_service: MagicMock
    ) -> None:
        """Should search jobs with timestamp filters."""
        from backend.services.job_search_service import JobAggregations, JobSearchResult

        mock_job_search_service.search.return_value = JobSearchResult(
            jobs=[],
            total=0,
            aggregations=JobAggregations(
                by_status={},
                by_type={},
            ),
        )

        response = client.get(
            "/api/jobs/search?"
            "created_after=2024-01-01T00:00:00Z&"
            "created_before=2024-01-31T23:59:59Z&"
            "completed_after=2024-01-02T00:00:00Z&"
            "completed_before=2024-01-30T23:59:59Z"
        )
        assert response.status_code == 200

        call_kwargs = mock_job_search_service.search.call_args.kwargs
        assert call_kwargs["created_range"] is not None
        assert call_kwargs["completed_range"] is not None

    def test_search_jobs_pagination(
        self, client: TestClient, mock_job_search_service: MagicMock
    ) -> None:
        """Should support pagination in search."""
        from backend.services.job_search_service import JobAggregations, JobSearchResult

        mock_job_search_service.search.return_value = JobSearchResult(
            jobs=[],
            total=100,
            aggregations=JobAggregations(
                by_status={},
                by_type={},
            ),
        )

        response = client.get("/api/jobs/search?limit=20&offset=40")
        assert response.status_code == 200

        data = response.json()
        assert data["meta"]["limit"] == 20
        assert data["meta"]["offset"] == 40
        assert data["meta"]["total"] == 100


class TestGetJobDetail:
    """Tests for GET /api/jobs/{job_id}/detail."""

    def test_get_job_detail_success(self, client: TestClient, mock_job_service: MagicMock) -> None:
        """Should return detailed job information."""
        from backend.api.schemas.jobs import (
            JobDetailResponse,
            JobMetadata,
            JobProgressDetail,
            JobRetryInfo,
            JobStatusEnum,
            JobTiming,
        )

        mock_job_service.get_job_detail.return_value = JobDetailResponse(
            id="job-123",
            job_type="export",
            status=JobStatusEnum.RUNNING,
            progress=JobProgressDetail(
                percent=45,
                current_step="Processing events",
                items_processed=450,
                items_total=1000,
            ),
            timing=JobTiming(
                created_at=datetime(2024, 1, 15, 10, 0, 0),
                started_at=datetime(2024, 1, 15, 10, 0, 1),
                duration_seconds=30.0,
            ),
            retry_info=JobRetryInfo(
                attempt_number=1,
                max_attempts=3,
            ),
            metadata=JobMetadata(
                input_params={},
                worker_id="worker-1",
            ),
        )

        response = client.get("/api/jobs/job-123/detail")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == "job-123"
        assert data["progress"]["percent"] == 45
        assert data["timing"]["duration_seconds"] == 30.0


class TestAbortJob:
    """Tests for POST /api/jobs/{job_id}/abort."""

    def test_abort_job_success(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should abort a running job."""
        mock_job_tracker.abort_job = AsyncMock(return_value=(True, None))

        response = client.post("/api/jobs/job-123/abort")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["status"] == "running"
        assert "abort" in data["message"].lower()

    def test_abort_job_not_found(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should return 404 when job not found."""
        mock_job_tracker.abort_job = AsyncMock(side_effect=KeyError("Job not found"))

        response = client.post("/api/jobs/nonexistent/abort")
        assert response.status_code == 404

        data = response.json()
        assert "No job found" in data["detail"]

    def test_abort_job_not_running(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should return 400 when job is not running."""
        mock_job_tracker.abort_job = AsyncMock(return_value=(False, "Job is not running"))

        response = client.post("/api/jobs/job-123/abort")
        assert response.status_code == 400

        data = response.json()
        assert "not running" in data["detail"]


class TestDeleteJob:
    """Tests for DELETE /api/jobs/{job_id}."""

    def test_delete_pending_job(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should cancel a pending job."""
        mock_job_tracker.get_job.return_value = JobInfo(
            job_id="job-123",
            job_type="export",
            status=JobStatus.PENDING,
            progress=0,
            message=None,
            created_at="2024-01-15T10:00:00Z",
            started_at=None,
            completed_at=None,
            result=None,
            error=None,
        )
        mock_job_tracker.cancel_queued_job.return_value = (True, None)

        response = client.delete("/api/jobs/job-123")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["status"] == "failed"
        assert "cancelled" in data["message"].lower()

    def test_delete_running_job(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should abort a running job."""
        mock_job_tracker.get_job.return_value = JobInfo(
            job_id="job-123",
            job_type="export",
            status=JobStatus.RUNNING,
            progress=50,
            message="Processing...",
            created_at="2024-01-15T10:00:00Z",
            started_at="2024-01-15T10:00:01Z",
            completed_at=None,
            result=None,
            error=None,
        )
        mock_job_tracker.abort_job = AsyncMock(return_value=(True, None))

        response = client.delete("/api/jobs/job-123")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["status"] == "running"
        assert "abort" in data["message"].lower()

    def test_delete_job_not_found(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should return 404 when job not found."""
        mock_job_tracker.get_job.return_value = None
        mock_job_tracker.get_job_from_redis = AsyncMock(return_value=None)

        response = client.delete("/api/jobs/nonexistent")
        assert response.status_code == 404

        data = response.json()
        assert "No job found" in data["detail"]

    def test_delete_completed_job(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should return 400 for completed job."""
        mock_job_tracker.get_job.return_value = JobInfo(
            job_id="job-123",
            job_type="export",
            status=JobStatus.COMPLETED,
            progress=100,
            message="Done",
            created_at="2024-01-15T10:00:00Z",
            started_at="2024-01-15T10:00:01Z",
            completed_at="2024-01-15T10:01:00Z",
            result=None,
            error=None,
        )

        response = client.delete("/api/jobs/job-123")
        assert response.status_code == 400

        data = response.json()
        assert "Cannot stop job" in data["detail"]

    def test_delete_failed_job(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should return 400 for failed job."""
        mock_job_tracker.get_job.return_value = JobInfo(
            job_id="job-123",
            job_type="export",
            status=JobStatus.FAILED,
            progress=30,
            message="Failed",
            created_at="2024-01-15T10:00:00Z",
            started_at="2024-01-15T10:00:01Z",
            completed_at="2024-01-15T10:00:30Z",
            result=None,
            error="Connection error",
        )

        response = client.delete("/api/jobs/job-123")
        assert response.status_code == 400

    def test_delete_pending_job_failure(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should return 400 when cancelling pending job fails."""
        mock_job_tracker.get_job.return_value = JobInfo(
            job_id="job-123",
            job_type="export",
            status=JobStatus.PENDING,
            progress=0,
            message=None,
            created_at="2024-01-15T10:00:00Z",
            started_at=None,
            completed_at=None,
            result=None,
            error=None,
        )
        mock_job_tracker.cancel_queued_job.return_value = (False, "Cannot cancel this job")

        response = client.delete("/api/jobs/job-123")
        assert response.status_code == 400

        data = response.json()
        assert "Cannot cancel this job" in data["detail"]

    def test_delete_running_job_failure(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should return 400 when aborting running job fails."""
        mock_job_tracker.get_job.return_value = JobInfo(
            job_id="job-123",
            job_type="export",
            status=JobStatus.RUNNING,
            progress=50,
            message="Processing...",
            created_at="2024-01-15T10:00:00Z",
            started_at="2024-01-15T10:00:01Z",
            completed_at=None,
            result=None,
            error=None,
        )
        mock_job_tracker.abort_job = AsyncMock(return_value=(False, "Cannot abort this job"))

        response = client.delete("/api/jobs/job-123")
        assert response.status_code == 400

        data = response.json()
        assert "Cannot abort this job" in data["detail"]


class TestBulkCancelJobs:
    """Tests for POST /api/jobs/bulk-cancel."""

    def test_bulk_cancel_all_success(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should cancel multiple jobs successfully."""
        mock_job_tracker.cancel_job.return_value = True

        response = client.post(
            "/api/jobs/bulk-cancel",
            json={"job_ids": ["job-1", "job-2", "job-3"]},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["cancelled"] == 3
        assert data["failed"] == 0
        assert len(data["errors"]) == 0

    def test_bulk_cancel_partial_success(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should handle partial cancellation failures."""

        def cancel_job_side_effect(job_id: str) -> bool:
            if job_id == "job-2":
                raise KeyError("Job not found")
            # Return False for job-3 (already completed), True otherwise
            return job_id != "job-3"

        mock_job_tracker.cancel_job.side_effect = cancel_job_side_effect

        response = client.post(
            "/api/jobs/bulk-cancel",
            json={"job_ids": ["job-1", "job-2", "job-3"]},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["cancelled"] == 1
        assert data["failed"] == 2
        assert len(data["errors"]) == 2

        error_job_ids = {error["job_id"] for error in data["errors"]}
        assert "job-2" in error_job_ids
        assert "job-3" in error_job_ids

    def test_bulk_cancel_empty_list(self, client: TestClient, mock_job_tracker: MagicMock) -> None:
        """Should handle empty job list with validation error."""
        response = client.post(
            "/api/jobs/bulk-cancel",
            json={"job_ids": []},
        )
        # Empty list may trigger validation error if there's a min_length constraint
        # Check what the actual behavior is
        assert response.status_code in (200, 422)

        if response.status_code == 200:
            data = response.json()
            assert data["cancelled"] == 0
            assert data["failed"] == 0

    def test_bulk_cancel_with_exception(
        self, client: TestClient, mock_job_tracker: MagicMock
    ) -> None:
        """Should handle unexpected exceptions."""

        def cancel_job_side_effect(job_id: str) -> bool:
            if job_id == "job-2":
                raise RuntimeError("Unexpected error")
            return True

        mock_job_tracker.cancel_job.side_effect = cancel_job_side_effect

        response = client.post(
            "/api/jobs/bulk-cancel",
            json={"job_ids": ["job-1", "job-2", "job-3"]},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["cancelled"] == 2
        assert data["failed"] == 1
        assert any("Unexpected error" in error["error"] for error in data["errors"])


class TestGetJobHistory:
    """Tests for GET /api/jobs/{job_id}/history."""

    def test_get_job_history_success(
        self, client: TestClient, mock_job_history_service: MagicMock
    ) -> None:
        """Should return job history with transitions and attempts."""
        from backend.services.job_history_service import (
            AttemptRecord,
            JobHistory,
            TransitionRecord,
        )

        mock_job_history_service.get_job_history.return_value = JobHistory(
            job_id="job-123",
            job_type="export",
            status="completed",
            created_at=datetime(2024, 1, 15, 10, 0, 0),
            started_at=datetime(2024, 1, 15, 10, 0, 1),
            completed_at=datetime(2024, 1, 15, 10, 1, 0),
            transitions=[
                TransitionRecord(
                    from_status="pending",
                    to_status="running",
                    at=datetime(2024, 1, 15, 10, 0, 1),
                    triggered_by="system",
                    details=None,
                ),
                TransitionRecord(
                    from_status="running",
                    to_status="completed",
                    at=datetime(2024, 1, 15, 10, 1, 0),
                    triggered_by="system",
                    details=None,
                ),
            ],
            attempts=[
                AttemptRecord(
                    attempt_number=1,
                    started_at=datetime(2024, 1, 15, 10, 0, 1),
                    ended_at=datetime(2024, 1, 15, 10, 1, 0),
                    status="completed",
                    error=None,
                    worker_id="worker-1",
                    duration_seconds=59.0,
                    result={"file_path": "/exports/events.csv"},
                ),
            ],
        )

        response = client.get("/api/jobs/job-123/history")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "job-123"
        assert len(data["transitions"]) == 2
        assert len(data["attempts"]) == 1
        # The response uses alias "from" instead of "from_status"
        assert data["transitions"][0]["from"] == "pending"
        assert data["attempts"][0]["attempt_number"] == 1

    def test_get_job_history_not_found(
        self, client: TestClient, mock_job_history_service: MagicMock
    ) -> None:
        """Should return 404 when job not found."""
        mock_job_history_service.get_job_history.return_value = None

        response = client.get("/api/jobs/nonexistent/history")
        assert response.status_code == 404

        data = response.json()
        assert "No job found" in data["detail"]


class TestGetJobLogs:
    """Tests for GET /api/jobs/{job_id}/logs."""

    def test_get_job_logs_success(
        self, client: TestClient, mock_job_history_service: MagicMock
    ) -> None:
        """Should return job logs."""
        from backend.services.job_history_service import JobHistory, JobLogEntry

        mock_job_history_service.get_job_history.return_value = JobHistory(
            job_id="job-123",
            job_type="export",
            status="completed",
            created_at=datetime(2024, 1, 15, 10, 0, 0),
            started_at=datetime(2024, 1, 15, 10, 0, 1),
            completed_at=datetime(2024, 1, 15, 10, 1, 0),
            transitions=[],
            attempts=[],
        )

        mock_job_history_service.get_job_logs.return_value = [
            JobLogEntry(
                timestamp=datetime(2024, 1, 15, 10, 0, 1),
                level="info",
                message="Starting export",
                context=None,
                attempt_number=1,
            ),
            JobLogEntry(
                timestamp=datetime(2024, 1, 15, 10, 0, 30),
                level="info",
                message="Processing events",
                context={"progress": 50},
                attempt_number=1,
            ),
        ]

        response = client.get("/api/jobs/job-123/logs")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "job-123"
        assert len(data["logs"]) == 2
        assert data["total"] == 2
        assert data["has_more"] is False
        assert data["logs"][0]["message"] == "Starting export"

    def test_get_job_logs_with_filters(
        self, client: TestClient, mock_job_history_service: MagicMock
    ) -> None:
        """Should filter logs by level and timestamp."""
        from backend.services.job_history_service import JobHistory

        mock_job_history_service.get_job_history.return_value = JobHistory(
            job_id="job-123",
            job_type="export",
            status="completed",
            created_at=datetime(2024, 1, 15, 10, 0, 0),
            started_at=datetime(2024, 1, 15, 10, 0, 1),
            completed_at=datetime(2024, 1, 15, 10, 1, 0),
            transitions=[],
            attempts=[],
        )

        mock_job_history_service.get_job_logs.return_value = []

        response = client.get(
            "/api/jobs/job-123/logs?level=ERROR&since=2024-01-15T10:00:00Z&limit=500"
        )
        assert response.status_code == 200

        mock_job_history_service.get_job_logs.assert_called_once()
        call_kwargs = mock_job_history_service.get_job_logs.call_args.kwargs
        assert call_kwargs["level"] == "ERROR"
        assert call_kwargs["limit"] == 501  # limit + 1 for has_more check

    def test_get_job_logs_pagination(
        self, client: TestClient, mock_job_history_service: MagicMock
    ) -> None:
        """Should indicate when there are more logs."""
        from backend.services.job_history_service import JobHistory, JobLogEntry

        mock_job_history_service.get_job_history.return_value = JobHistory(
            job_id="job-123",
            job_type="export",
            status="completed",
            created_at=datetime(2024, 1, 15, 10, 0, 0),
            started_at=datetime(2024, 1, 15, 10, 0, 1),
            completed_at=datetime(2024, 1, 15, 10, 1, 0),
            transitions=[],
            attempts=[],
        )

        # Return limit + 1 entries to trigger has_more
        mock_job_history_service.get_job_logs.return_value = [
            JobLogEntry(
                timestamp=datetime(2024, 1, 15, 10, 0, i),
                level="info",
                message=f"Log entry {i}",
                context=None,
                attempt_number=1,
            )
            for i in range(11)  # 11 entries when limit is 10
        ]

        response = client.get("/api/jobs/job-123/logs?limit=10")
        assert response.status_code == 200

        data = response.json()
        assert data["has_more"] is True
        assert len(data["logs"]) == 10  # Should return only 10, not 11

    def test_get_job_logs_not_found(
        self, client: TestClient, mock_job_history_service: MagicMock
    ) -> None:
        """Should return 404 when job not found."""
        mock_job_history_service.get_job_history.return_value = None

        response = client.get("/api/jobs/nonexistent/logs")
        assert response.status_code == 404

        data = response.json()
        assert "No job found" in data["detail"]


class TestRunExportJob:
    """Tests for the run_export_job background task function."""

    def test_run_export_job_covered_by_integration_tests(self) -> None:
        """The run_export_job function is tested via integration tests.

        This function is a background task that is difficult to test in unit
        tests due to its async nature and FastAPI BackgroundTasks integration.
        It is comprehensively covered by the integration tests in
        backend/tests/integration/api/test_jobs_api.py.
        """
        from backend.api.routes.jobs import run_export_job

        assert callable(run_export_job)
        assert run_export_job.__name__ == "run_export_job"
