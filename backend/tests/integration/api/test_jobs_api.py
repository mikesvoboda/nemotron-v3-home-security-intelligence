"""Integration tests for Jobs API endpoints (NEM-2389).

Tests for the background job management API including:
1. Listing jobs with filtering and pagination
2. Job statistics endpoint
3. Job detail endpoint
4. Database-backed job operations

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database via testcontainers
- client: httpx AsyncClient with test app
- db_session: AsyncSession for database operations
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.job import Job, JobStatus


@pytest.fixture
async def clean_job_data(integration_db, db_session: AsyncSession):
    """Delete all job data before and after each test for isolation.

    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks
    when tests run in parallel with xdist.
    """
    # Clean before test - also clean related tables
    await db_session.execute(text("DELETE FROM job_logs"))  # nosemgrep: avoid-sqlalchemy-text
    await db_session.execute(
        text("DELETE FROM job_transitions")
    )  # nosemgrep: avoid-sqlalchemy-text
    await db_session.execute(text("DELETE FROM job_attempts"))  # nosemgrep: avoid-sqlalchemy-text
    await db_session.execute(text("DELETE FROM jobs"))  # nosemgrep: avoid-sqlalchemy-text
    await db_session.commit()

    yield

    # Clean after test (best effort)
    try:
        await db_session.execute(text("DELETE FROM job_logs"))  # nosemgrep: avoid-sqlalchemy-text
        await db_session.execute(
            text("DELETE FROM job_transitions")
        )  # nosemgrep: avoid-sqlalchemy-text
        await db_session.execute(
            text("DELETE FROM job_attempts")
        )  # nosemgrep: avoid-sqlalchemy-text
        await db_session.execute(text("DELETE FROM jobs"))  # nosemgrep: avoid-sqlalchemy-text
        await db_session.commit()
    except Exception:
        pass


@pytest.fixture
async def test_jobs(db_session: AsyncSession, clean_job_data) -> list[Job]:
    """Create test jobs with various states for API testing."""
    base_time = datetime(2025, 12, 1, 12, 0, 0, tzinfo=UTC)
    jobs = []

    # Create jobs with different statuses and types
    job_configs = [
        # Completed export jobs
        ("export", JobStatus.COMPLETED.value, 0, 100),
        ("export", JobStatus.COMPLETED.value, 1, 100),
        ("export", JobStatus.COMPLETED.value, 2, 100),
        # Running export job
        ("export", JobStatus.RUNNING.value, 3, 50),
        # Queued export job
        ("export", JobStatus.QUEUED.value, 4, 0),
        # Completed cleanup jobs
        ("cleanup", JobStatus.COMPLETED.value, 5, 100),
        ("cleanup", JobStatus.COMPLETED.value, 6, 100),
        # Failed cleanup job
        ("cleanup", JobStatus.FAILED.value, 7, 25),
        # Queued backup jobs
        ("backup", JobStatus.QUEUED.value, 8, 0),
        ("backup", JobStatus.QUEUED.value, 9, 0),
        # Cancelled import job
        ("import", JobStatus.CANCELLED.value, 10, 75),
    ]

    for job_type, status, hour_offset, progress in job_configs:
        created_at = base_time + timedelta(hours=hour_offset)
        job = Job(
            id=str(uuid.uuid4()),
            job_type=job_type,
            status=status,
            priority=2,
            created_at=created_at,
            progress_percent=progress,
            max_attempts=3,
            attempt_number=1,
        )

        # Set timestamps based on status
        if status in (JobStatus.RUNNING.value, JobStatus.COMPLETED.value, JobStatus.FAILED.value):
            job.started_at = created_at + timedelta(seconds=5)

        if status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value):
            job.completed_at = created_at + timedelta(minutes=2)

        if status == JobStatus.FAILED.value:
            job.error_message = "Test error message"
            job.error_traceback = "Traceback: ..."

        db_session.add(job)
        jobs.append(job)

    await db_session.commit()

    # Refresh to get any DB-generated values
    for job in jobs:
        await db_session.refresh(job)

    return jobs


class TestListJobsEndpoint:
    """Integration tests for GET /api/jobs endpoint."""

    @pytest.mark.asyncio
    async def test_list_jobs_returns_paginated_response(
        self, client: AsyncClient, test_jobs: list[Job]
    ) -> None:
        """Test that listing jobs returns proper paginated response."""
        response = await client.get("/api/jobs?limit=5")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) == 5
        assert data["pagination"]["limit"] == 5

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status(
        self, client: AsyncClient, test_jobs: list[Job]
    ) -> None:
        """Test filtering jobs by status."""
        response = await client.get("/api/jobs?status=completed")

        assert response.status_code == 200
        data = response.json()

        # All returned jobs should be completed
        for job in data["items"]:
            assert job["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_job_type(
        self, client: AsyncClient, test_jobs: list[Job]
    ) -> None:
        """Test filtering jobs by job type."""
        response = await client.get("/api/jobs?job_type=export")

        assert response.status_code == 200
        data = response.json()

        # All returned jobs should be export type
        for job in data["items"]:
            assert job["job_type"] == "export"

    @pytest.mark.asyncio
    async def test_list_jobs_pagination_offset(
        self, client: AsyncClient, test_jobs: list[Job]
    ) -> None:
        """Test pagination with offset."""
        # Get first page
        response1 = await client.get("/api/jobs?limit=5&offset=0")
        assert response1.status_code == 200
        data1 = response1.json()

        # Get second page
        response2 = await client.get("/api/jobs?limit=5&offset=5")
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify no overlapping job IDs
        first_page_ids = {job["job_id"] for job in data1["items"]}
        second_page_ids = {job["job_id"] for job in data2["items"]}
        assert first_page_ids.isdisjoint(second_page_ids)

    @pytest.mark.asyncio
    async def test_list_jobs_empty_when_no_jobs(self, client: AsyncClient, clean_job_data) -> None:
        """Test empty response when no jobs exist."""
        response = await client.get("/api/jobs")

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 0
        assert data["pagination"]["total"] == 0


class TestJobTypesEndpoint:
    """Integration tests for GET /api/jobs/types endpoint."""

    @pytest.mark.asyncio
    async def test_list_job_types(self, client: AsyncClient, clean_job_data) -> None:
        """Test listing available job types."""
        response = await client.get("/api/jobs/types")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "job_types" in data
        job_types = data["job_types"]

        # Should have at least some job types defined
        assert len(job_types) > 0

        # Each job type should have name and description
        for job_type in job_types:
            assert "name" in job_type
            assert "description" in job_type


class TestJobStatsEndpoint:
    """Integration tests for GET /api/jobs/stats endpoint."""

    @pytest.mark.asyncio
    async def test_job_stats_returns_correct_structure(
        self, client: AsyncClient, test_jobs: list[Job]
    ) -> None:
        """Test that job stats returns the expected structure."""
        response = await client.get("/api/jobs/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "total_jobs" in data
        assert "by_status" in data
        assert "by_type" in data

    @pytest.mark.asyncio
    async def test_job_stats_counts_correct(
        self, client: AsyncClient, test_jobs: list[Job]
    ) -> None:
        """Test that job stats counts are correct."""
        response = await client.get("/api/jobs/stats")

        assert response.status_code == 200
        data = response.json()

        # Total should match number of test jobs
        assert data["total_jobs"] == len(test_jobs)

    @pytest.mark.asyncio
    async def test_job_stats_empty_when_no_jobs(self, client: AsyncClient, clean_job_data) -> None:
        """Test job stats with no jobs."""
        response = await client.get("/api/jobs/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["total_jobs"] == 0


class TestGetJobStatusEndpoint:
    """Integration tests for GET /api/jobs/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_job_status_returns_job(
        self, client: AsyncClient, test_jobs: list[Job]
    ) -> None:
        """Test getting a specific job's status."""
        job = test_jobs[0]
        response = await client.get(f"/api/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["job_id"] == job.id
        assert data["job_type"] == job.job_type
        assert data["status"] == job.status

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, client: AsyncClient, clean_job_data) -> None:
        """Test getting a non-existent job returns 404."""
        response = await client.get("/api/jobs/nonexistent-job-id")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestCancelJobEndpoint:
    """Integration tests for POST /api/jobs/{job_id}/cancel endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_pending_job(self, client: AsyncClient, test_jobs: list[Job]) -> None:
        """Test cancelling a pending/queued job."""
        # Find a queued job
        queued_job = next(job for job in test_jobs if job.status == JobStatus.QUEUED.value)

        response = await client.post(f"/api/jobs/{queued_job.id}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == queued_job.id

    @pytest.mark.asyncio
    async def test_cancel_completed_job_fails(
        self, client: AsyncClient, test_jobs: list[Job]
    ) -> None:
        """Test that cancelling a completed job returns 409."""
        # Find a completed job
        completed_job = next(job for job in test_jobs if job.status == JobStatus.COMPLETED.value)

        response = await client.post(f"/api/jobs/{completed_job.id}/cancel")

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, client: AsyncClient, clean_job_data) -> None:
        """Test cancelling a non-existent job returns 404."""
        response = await client.post("/api/jobs/nonexistent-job-id/cancel")

        assert response.status_code == 404


class TestBulkCancelEndpoint:
    """Integration tests for POST /api/jobs/bulk-cancel endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_cancel_jobs(self, client: AsyncClient, test_jobs: list[Job]) -> None:
        """Test bulk cancelling multiple jobs."""
        # Get IDs of queued jobs
        queued_jobs = [job for job in test_jobs if job.status == JobStatus.QUEUED.value]
        job_ids = [job.id for job in queued_jobs]

        response = await client.post(
            "/api/jobs/bulk-cancel",
            json={"job_ids": job_ids},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify counts
        assert "cancelled" in data
        assert "failed" in data
        assert data["cancelled"] + data["failed"] == len(job_ids)

    @pytest.mark.asyncio
    async def test_bulk_cancel_empty_list(self, client: AsyncClient, clean_job_data) -> None:
        """Test bulk cancel with empty list."""
        response = await client.post(
            "/api/jobs/bulk-cancel",
            json={"job_ids": []},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["cancelled"] == 0
        assert data["failed"] == 0

    @pytest.mark.asyncio
    async def test_bulk_cancel_mixed_results(
        self, client: AsyncClient, test_jobs: list[Job]
    ) -> None:
        """Test bulk cancel with mix of cancellable and non-cancellable jobs."""
        # Mix of queued (cancellable) and completed (not cancellable) jobs
        queued_job = next(job for job in test_jobs if job.status == JobStatus.QUEUED.value)
        completed_job = next(job for job in test_jobs if job.status == JobStatus.COMPLETED.value)

        response = await client.post(
            "/api/jobs/bulk-cancel",
            json={"job_ids": [queued_job.id, completed_job.id]},
        )

        assert response.status_code == 200
        data = response.json()

        # Should have at least one of each
        assert data["cancelled"] >= 0
        assert data["failed"] >= 0
        assert data["cancelled"] + data["failed"] == 2


class TestDeleteJobEndpoint:
    """Integration tests for DELETE /api/jobs/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_queued_job(self, client: AsyncClient, test_jobs: list[Job]) -> None:
        """Test deleting (cancelling) a queued job."""
        queued_job = next(job for job in test_jobs if job.status == JobStatus.QUEUED.value)

        response = await client.delete(f"/api/jobs/{queued_job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == queued_job.id

    @pytest.mark.asyncio
    async def test_delete_completed_job_fails(
        self, client: AsyncClient, test_jobs: list[Job]
    ) -> None:
        """Test that deleting a completed job returns 400."""
        completed_job = next(job for job in test_jobs if job.status == JobStatus.COMPLETED.value)

        response = await client.delete(f"/api/jobs/{completed_job.id}")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_nonexistent_job(self, client: AsyncClient, clean_job_data) -> None:
        """Test deleting a non-existent job returns 404."""
        response = await client.delete("/api/jobs/nonexistent-job-id")

        assert response.status_code == 404
