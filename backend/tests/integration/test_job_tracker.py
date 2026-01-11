"""Integration tests for job tracker service.

These tests verify the job tracker service works correctly for
tracking background jobs, exports, and async operations.
"""

import pytest

from backend.services.job_tracker import JobStatus, JobTracker, JobType


@pytest.mark.asyncio
async def test_job_tracker_create_job():
    """Test creating a new job through the tracker."""
    tracker = JobTracker()

    job = await tracker.create_job(
        job_type=JobType.EXPORT,
        description="Test export job",
        metadata={"format": "csv"},
    )

    assert job.id is not None
    assert job.job_type == JobType.EXPORT
    assert job.status == JobStatus.PENDING
    assert job.description == "Test export job"
    assert job.metadata["format"] == "csv"


@pytest.mark.asyncio
async def test_job_tracker_update_status():
    """Test updating job status."""
    tracker = JobTracker()

    job = await tracker.create_job(
        job_type=JobType.EXPORT,
        description="Test job",
    )

    updated = await tracker.update_status(job.id, JobStatus.RUNNING)
    assert updated.status == JobStatus.RUNNING
    assert updated.started_at is not None


@pytest.mark.asyncio
async def test_job_tracker_update_progress():
    """Test updating job progress."""
    tracker = JobTracker()

    job = await tracker.create_job(
        job_type=JobType.EXPORT,
        description="Test job",
    )
    await tracker.update_status(job.id, JobStatus.RUNNING)

    updated = await tracker.update_progress(job.id, 50, "Processing...")
    assert updated.progress == 50
    assert updated.message == "Processing..."


@pytest.mark.asyncio
async def test_job_tracker_complete_job():
    """Test completing a job."""
    tracker = JobTracker()

    job = await tracker.create_job(
        job_type=JobType.EXPORT,
        description="Test job",
    )
    await tracker.update_status(job.id, JobStatus.RUNNING)

    updated = await tracker.complete_job(
        job.id,
        result={"file_path": "/exports/test.csv", "rows": 100},
    )
    assert updated.status == JobStatus.COMPLETED
    assert updated.progress == 100
    assert updated.completed_at is not None
    assert updated.result["rows"] == 100


@pytest.mark.asyncio
async def test_job_tracker_fail_job():
    """Test failing a job."""
    tracker = JobTracker()

    job = await tracker.create_job(
        job_type=JobType.EXPORT,
        description="Test job",
    )
    await tracker.update_status(job.id, JobStatus.RUNNING)

    updated = await tracker.fail_job(job.id, error="Export failed: disk full")
    assert updated.status == JobStatus.FAILED
    assert updated.error == "Export failed: disk full"
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_job_tracker_get_jobs_by_type():
    """Test getting jobs filtered by type."""
    tracker = JobTracker()

    # Create jobs of different types
    await tracker.create_job(job_type=JobType.EXPORT, description="Export 1")
    await tracker.create_job(job_type=JobType.CLEANUP, description="Cleanup 1")
    await tracker.create_job(job_type=JobType.EXPORT, description="Export 2")

    export_jobs = await tracker.get_jobs(job_type=JobType.EXPORT)
    assert len(export_jobs) == 2


@pytest.mark.asyncio
async def test_job_tracker_get_jobs_by_status():
    """Test getting jobs filtered by status."""
    tracker = JobTracker()

    job1 = await tracker.create_job(job_type=JobType.EXPORT, description="Job 1")
    job2 = await tracker.create_job(job_type=JobType.EXPORT, description="Job 2")
    await tracker.update_status(job1.id, JobStatus.RUNNING)

    running_jobs = await tracker.get_jobs(status=JobStatus.RUNNING)
    assert len(running_jobs) == 1
    assert running_jobs[0].id == job1.id


@pytest.mark.asyncio
async def test_job_tracker_cancel_job():
    """Test cancelling a job."""
    tracker = JobTracker()

    job = await tracker.create_job(
        job_type=JobType.EXPORT,
        description="Test job",
    )
    await tracker.update_status(job.id, JobStatus.RUNNING)

    updated = await tracker.cancel_job(job.id)
    assert updated.status == JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_job_tracker_get_stats():
    """Test getting job statistics."""
    tracker = JobTracker()

    # Create various jobs
    job1 = await tracker.create_job(job_type=JobType.EXPORT, description="Export")
    job2 = await tracker.create_job(job_type=JobType.CLEANUP, description="Cleanup")
    await tracker.update_status(job1.id, JobStatus.RUNNING)
    await tracker.complete_job(job2.id, result={})

    stats = await tracker.get_stats()
    assert stats["total_jobs"] >= 2
    assert "by_status" in stats
    assert "by_type" in stats
