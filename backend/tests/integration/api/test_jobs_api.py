"""Integration tests for Jobs API endpoints (NEM-2389).

Tests for the background job management API including:
1. Listing jobs with filtering and pagination
2. Job statistics endpoint
3. Job detail endpoint
4. Cancel/delete/bulk-cancel operations

Ruling (2026-09-13, owner): these tests previously seeded the Postgres `jobs`
table, but GET /api/jobs, /api/jobs/stats, /api/jobs/{id}, cancel and delete all
read the in-memory JobTracker singleton (+ Redis fallback) — the DB-backed
job_history_service only serves the detail/history/logs routes. The seed was
invisible to the routes by construction. Tests now seed the tracker singleton
itself, the same way production does. See ledger
docs/plans/2026-09-12-context-map-doc-updates.md (R-T7-JOBSAPI).

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database via testcontainers
- client: httpx AsyncClient with test app
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from backend.services.job_tracker import JobInfo, get_job_tracker, reset_job_tracker


@pytest.fixture
def clean_tracker():
    """Reset the JobTracker singleton before and after the test.

    The routes read the singleton via get_job_tracker_dep; reset_job_tracker()
    guarantees this test's view contains exactly what it seeds — nothing from a
    prior test on the same xdist worker.
    """
    reset_job_tracker()
    yield
    reset_job_tracker()


@pytest.fixture
def test_jobs(clean_tracker) -> list[JobInfo]:
    """Seed the JobTracker singleton with jobs in various states.

    Production-shaped seeding: create_job() then the status-transition methods
    where they apply. created_at/started_at/completed_at are overwritten after
    creation so ordering and duration stats are deterministic.

    JobStatus is StrEnum with auto() values: PENDING/RUNNING/COMPLETED/FAILED
    only — there is no QUEUED/CANCELLED state; queued maps to PENDING and the
    formerly-CANCELLED job maps to FAILED (terminal, non-cancellable).
    """
    base_time = datetime(2025, 12, 1, 12, 0, 0, tzinfo=UTC)
    tracker = get_job_tracker()

    job_configs = [
        # Completed export jobs
        ("export", "completed", 0, 100),
        ("export", "completed", 1, 100),
        ("export", "completed", 2, 100),
        # Running export job
        ("export", "running", 3, 50),
        # Queued (pending) export job
        ("export", "pending", 4, 0),
        # Completed cleanup jobs
        ("cleanup", "completed", 5, 100),
        ("cleanup", "completed", 6, 100),
        # Failed cleanup job
        ("cleanup", "failed", 7, 25),
        # Queued (pending) backup jobs
        ("backup", "pending", 8, 0),
        ("backup", "pending", 9, 0),
        # Cancelled-then-failed import job (FAILED is the terminal non-cancellable state)
        ("import", "failed", 10, 75),
    ]

    jobs: list[JobInfo] = []
    for job_type, status, hour_offset, progress in job_configs:
        created_at = base_time + timedelta(hours=hour_offset)
        job_id = tracker.create_job(job_type)
        job = tracker._jobs[job_id]  # seeding the tracker's own store, on purpose

        if status == "running":
            tracker.start_job(job_id)
        elif status in ("completed", "failed"):
            tracker.start_job(job_id)
            if status == "completed":
                tracker.complete_job(job_id, result=None)
            else:
                tracker.fail_job(job_id, error="Test error message")

        # Deterministic timestamps for ordering + stats duration math
        job["created_at"] = created_at.isoformat()
        if status in ("running", "completed", "failed"):
            job["started_at"] = (created_at + timedelta(seconds=5)).isoformat()
        if status in ("completed", "failed"):
            job["completed_at"] = (created_at + timedelta(minutes=2)).isoformat()
        job["progress"] = progress
        jobs.append(job)

    return jobs


class TestListJobsEndpoint:
    """Integration tests for GET /api/jobs endpoint."""

    @pytest.mark.asyncio
    async def test_list_jobs_returns_paginated_response(
        self, client: AsyncClient, test_jobs: list[JobInfo]
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
        self, client: AsyncClient, test_jobs: list[JobInfo]
    ) -> None:
        """Test filtering jobs by status."""
        response = await client.get("/api/jobs?status=completed")

        assert response.status_code == 200
        data = response.json()

        # All returned jobs should be completed
        assert len(data["items"]) == 5  # 3 export + 2 cleanup
        for job in data["items"]:
            assert job["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_job_type(
        self, client: AsyncClient, test_jobs: list[JobInfo]
    ) -> None:
        """Test filtering jobs by job type."""
        response = await client.get("/api/jobs?job_type=export")

        assert response.status_code == 200
        data = response.json()

        # All returned jobs should be export type
        assert len(data["items"]) == 5
        for job in data["items"]:
            assert job["job_type"] == "export"

    @pytest.mark.asyncio
    async def test_list_jobs_pagination_offset(
        self, client: AsyncClient, test_jobs: list[JobInfo]
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
    async def test_list_jobs_empty_when_no_jobs(self, client: AsyncClient, clean_tracker) -> None:
        """Test empty response when no jobs exist."""
        response = await client.get("/api/jobs")

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 0
        assert data["pagination"]["total"] == 0


class TestJobTypesEndpoint:
    """Integration tests for GET /api/jobs/types endpoint."""

    @pytest.mark.asyncio
    async def test_list_job_types(self, client: AsyncClient, clean_tracker) -> None:
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
        self, client: AsyncClient, test_jobs: list[JobInfo]
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
        self, client: AsyncClient, test_jobs: list[JobInfo]
    ) -> None:
        """Test that job stats counts are correct."""
        response = await client.get("/api/jobs/stats")

        assert response.status_code == 200
        data = response.json()

        # Shipped JobStatsResponse shape: by_status/by_type are LISTS of
        # {status|job_type, count} (JobStatusCount/JobTypeCount), not dicts.
        # by_status omits zero-count statuses; by_type is sorted by name.
        assert data["total_jobs"] == len(test_jobs)
        status_counts = {e["status"]: e["count"] for e in data["by_status"]}
        assert status_counts == {"completed": 5, "pending": 3, "running": 1, "failed": 2}
        type_counts = {e["job_type"]: e["count"] for e in data["by_type"]}
        assert type_counts == {"export": 5, "cleanup": 3, "backup": 2, "import": 1}

    @pytest.mark.asyncio
    async def test_job_stats_empty_when_no_jobs(self, client: AsyncClient, clean_tracker) -> None:
        """Test job stats with no jobs."""
        response = await client.get("/api/jobs/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["total_jobs"] == 0


class TestGetJobStatusEndpoint:
    """Integration tests for GET /api/jobs/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_job_status_returns_job(
        self, client: AsyncClient, test_jobs: list[JobInfo]
    ) -> None:
        """Test getting a specific job's status."""
        job = test_jobs[0]
        response = await client.get(f"/api/jobs/{job['job_id']}")

        assert response.status_code == 200
        data = response.json()

        assert data["job_id"] == job["job_id"]
        assert data["job_type"] == job["job_type"]
        assert data["status"] == job["status"]

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, client: AsyncClient, clean_tracker) -> None:
        """Test getting a non-existent job returns 404."""
        response = await client.get("/api/jobs/nonexistent-job-id")

        assert response.status_code == 404
        data = response.json()
        # Route detail is f"No job found with ID: {job_id}"
        assert "no job found" in data["detail"].lower()


class TestCancelJobEndpoint:
    """Integration tests for POST /api/jobs/{job_id}/cancel endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_pending_job(self, client: AsyncClient, test_jobs: list[JobInfo]) -> None:
        """Test cancelling a pending (queued) job."""
        # Find a pending job
        pending_job = next(job for job in test_jobs if job["status"] == "pending")

        response = await client.post(f"/api/jobs/{pending_job['job_id']}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == pending_job["job_id"]

    @pytest.mark.asyncio
    async def test_cancel_completed_job_fails(
        self, client: AsyncClient, test_jobs: list[JobInfo]
    ) -> None:
        """Test that cancelling a completed job returns 409."""
        # Find a completed job
        completed_job = next(job for job in test_jobs if job["status"] == "completed")

        response = await client.post(f"/api/jobs/{completed_job['job_id']}/cancel")

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, client: AsyncClient, clean_tracker) -> None:
        """Test cancelling a non-existent job returns 404."""
        response = await client.post("/api/jobs/nonexistent-job-id/cancel")

        assert response.status_code == 404


class TestBulkCancelEndpoint:
    """Integration tests for POST /api/jobs/bulk-cancel endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_cancel_jobs(self, client: AsyncClient, test_jobs: list[JobInfo]) -> None:
        """Test bulk cancelling multiple jobs."""
        # Get IDs of pending jobs
        pending_jobs = [job for job in test_jobs if job["status"] == "pending"]
        job_ids = [job["job_id"] for job in pending_jobs]

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
        assert data["cancelled"] == len(job_ids)

    @pytest.mark.asyncio
    async def test_bulk_cancel_empty_list(self, client: AsyncClient, clean_tracker) -> None:
        """Test bulk cancel with empty list is rejected.

        Shipped contract: BulkCancelRequest.job_ids has min_length=1
        ("1-100 jobs"), so an empty list is a 422 validation failure before
        the route body runs — not a 200 with zero counts.
        """
        response = await client.post(
            "/api/jobs/bulk-cancel",
            json={"job_ids": []},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_bulk_cancel_mixed_results(
        self, client: AsyncClient, test_jobs: list[JobInfo]
    ) -> None:
        """Test bulk cancel with mix of cancellable and non-cancellable jobs."""
        # Mix of pending (cancellable) and completed (not cancellable) jobs
        pending_job = next(job for job in test_jobs if job["status"] == "pending")
        completed_job = next(job for job in test_jobs if job["status"] == "completed")

        response = await client.post(
            "/api/jobs/bulk-cancel",
            json={"job_ids": [pending_job["job_id"], completed_job["job_id"]]},
        )

        assert response.status_code == 200
        data = response.json()

        # Exactly one cancelled (pending), one failed (completed)
        assert data["cancelled"] == 1
        assert data["failed"] == 1


class TestDeleteJobEndpoint:
    """Integration tests for DELETE /api/jobs/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_queued_job(self, client: AsyncClient, test_jobs: list[JobInfo]) -> None:
        """Test deleting (cancelling) a pending job."""
        pending_job = next(job for job in test_jobs if job["status"] == "pending")

        response = await client.delete(f"/api/jobs/{pending_job['job_id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == pending_job["job_id"]

    @pytest.mark.asyncio
    async def test_delete_completed_job_fails(
        self, client: AsyncClient, test_jobs: list[JobInfo]
    ) -> None:
        """Test that deleting a completed job returns 400."""
        completed_job = next(job for job in test_jobs if job["status"] == "completed")

        response = await client.delete(f"/api/jobs/{completed_job['job_id']}")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_nonexistent_job(self, client: AsyncClient, clean_tracker) -> None:
        """Test deleting a non-existent job returns 404."""
        response = await client.delete("/api/jobs/nonexistent-job-id")

        assert response.status_code == 404
