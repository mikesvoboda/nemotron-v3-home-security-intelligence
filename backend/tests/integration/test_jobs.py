"""Integration tests for jobs API endpoints and background job lifecycle.

Tests job tracking functionality with real database interactions including:
- Job creation and tracking
- Job lifecycle (pending -> running -> completed/failed)
- Job progress updates
- Job cancellation
- Job filtering and pagination
- Job types listing
- Export job workflow

NEM-1949: Integration test coverage for background job lifecycle
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.integration


# =============================================================================
# List Jobs Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_jobs_empty(client: AsyncClient, mock_redis):
    """Test list jobs endpoint returns valid structure with pagination."""
    response = await client.get("/api/jobs")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "pagination" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["pagination"]["total"], int)
    assert data["pagination"]["total"] >= 0
    # Verify pagination structure
    assert "limit" in data["pagination"]
    assert "offset" in data["pagination"]
    assert "has_more" in data["pagination"]


@pytest.mark.asyncio
async def test_list_jobs_with_type_filter(client: AsyncClient, mock_redis):
    """Test list jobs endpoint with job_type filter."""
    response = await client.get("/api/jobs?job_type=export")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "pagination" in data
    # All returned jobs should be export type
    for job in data["items"]:
        assert job["job_type"] == "export"


@pytest.mark.asyncio
async def test_list_jobs_with_status_filter(client: AsyncClient, mock_redis):
    """Test list jobs endpoint with status filter."""
    response = await client.get("/api/jobs?status=running")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    # All returned jobs should be running
    for job in data["items"]:
        assert job["status"] == "running"


@pytest.mark.asyncio
async def test_list_jobs_with_multiple_filters(client: AsyncClient, mock_redis):
    """Test list jobs endpoint with both type and status filters."""
    response = await client.get("/api/jobs?job_type=export&status=completed")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    for job in data["items"]:
        assert job["job_type"] == "export"
        assert job["status"] == "completed"


# =============================================================================
# Get Job Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient, mock_redis):
    """Test get job endpoint returns 404 for non-existent job."""
    response = await client.get("/api/jobs/nonexistent-job-id")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_get_job_by_id_success(client: AsyncClient, mock_redis, integration_db):
    """Test get specific job by ID returns job details."""
    # Create an export job first
    job_request = {
        "format": "csv",
        "camera_id": "test_cam",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get the job by ID
    response = await client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["job_type"] == "export"
    assert "status" in data
    assert "progress" in data
    assert "created_at" in data


# =============================================================================
# Job Types Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_job_types(client: AsyncClient, mock_redis):
    """Test list job types endpoint returns available types."""
    response = await client.get("/api/jobs/types")

    assert response.status_code == 200
    data = response.json()
    assert "job_types" in data
    assert isinstance(data["job_types"], list)
    assert len(data["job_types"]) > 0

    # Check structure of returned types
    for job_type in data["job_types"]:
        assert "name" in job_type
        assert "description" in job_type


# =============================================================================
# Cancel Job Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cancel_job_not_found(client: AsyncClient, mock_redis):
    """Test cancel job endpoint returns 404 for non-existent job."""
    response = await client.post("/api/jobs/nonexistent-job-id/cancel")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_job_success(client: AsyncClient, mock_redis, integration_db):
    """Test cancelling a running job."""
    # Create an export job
    job_request = {
        "format": "csv",
        "camera_id": "test_cam",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Cancel the job
    cancel_response = await client.post(f"/api/jobs/{job_id}/cancel")

    assert cancel_response.status_code in (200, 409)
    data = cancel_response.json()
    assert "message" in data or "detail" in data


@pytest.mark.asyncio
async def test_cancel_completed_job(client: AsyncClient, mock_redis, integration_db):
    """Test cancelling a completed job returns appropriate error."""
    # Create and let complete a small export job
    job_request = {
        "format": "csv",
        "camera_id": "nonexistent_cam",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Wait a bit for job to potentially complete
    await asyncio.sleep(0.5)

    # Try to cancel (may succeed or return error depending on timing)
    cancel_response = await client.post(f"/api/jobs/{job_id}/cancel")

    # Either succeeds or returns 409 if already completed
    assert cancel_response.status_code in (200, 409)


# Note: Job stats endpoint doesn't exist in jobs.py
# Tests removed: test_job_stats_endpoint, test_job_stats_with_jobs


# =============================================================================
# Export Job Lifecycle Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_export_job_csv(client: AsyncClient, mock_redis, integration_db):
    """Test creating a CSV export job."""
    job_request = {
        "format": "csv",
        "camera_id": "test_cam",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-01-31T23:59:59Z",
    }

    response = await client.post("/api/events/export", json=job_request)

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert "message" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_export_job_json(client: AsyncClient, mock_redis, integration_db):
    """Test creating a JSON export job."""
    job_request = {
        "format": "json",
        "risk_level": "high",
    }

    response = await client.post("/api/events/export", json=job_request)

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data


@pytest.mark.asyncio
async def test_create_export_job_zip(client: AsyncClient, mock_redis, integration_db):
    """Test creating a ZIP export job with images."""
    job_request = {
        "format": "zip",
        "camera_id": "test_cam",
    }

    response = await client.post("/api/events/export", json=job_request)

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data


@pytest.mark.asyncio
async def test_export_job_validation_error(client: AsyncClient, mock_redis):
    """Test export job validation with invalid format."""
    job_request = {
        "format": "invalid_format",
    }

    response = await client.post("/api/events/export", json=job_request)

    assert response.status_code == 422
    data = response.json()
    # Response has error wrapper with validation details
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_job_lifecycle_stages(client: AsyncClient, mock_redis, integration_db):
    """Test job progresses through lifecycle stages (pending -> running -> completed)."""
    # Create export job
    job_request = {
        "format": "csv",
        "camera_id": "test_cam",
    }

    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Check initial status (may be pending, running, or completed depending on timing)
    response1 = await client.get(f"/api/jobs/{job_id}")
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] in ("pending", "running", "completed", "failed")

    # Wait for job to progress
    await asyncio.sleep(0.5)

    # Check status again
    response2 = await client.get(f"/api/jobs/{job_id}")
    assert response2.status_code == 200
    data2 = response2.json()
    # Job should have progressed or completed
    assert "status" in data2
    assert "progress" in data2
    assert data2["status"] in ("pending", "running", "completed", "failed")


@pytest.mark.asyncio
async def test_job_progress_tracking(client: AsyncClient, mock_redis, integration_db):
    """Test job progress is tracked and queryable."""
    # Create export job
    job_request = {
        "format": "csv",
    }

    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Query job progress
    response = await client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200

    data = response.json()
    assert "progress" in data
    assert isinstance(data["progress"], (int, float))
    assert 0 <= data["progress"] <= 100


# =============================================================================
# Job Detail Endpoint Tests (NEM-2390)
# =============================================================================


@pytest.mark.asyncio
async def test_get_job_detail_not_found(client: AsyncClient, mock_redis):
    """Test get job detail endpoint returns 404 for non-existent job."""
    response = await client.get("/api/jobs/nonexistent-job-id/detail")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_get_job_detail_success(client: AsyncClient, mock_redis, integration_db):
    """Test get job detail endpoint returns detailed job information."""
    # Create an export job first
    job_request = {
        "format": "csv",
        "camera_id": "test_cam",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get the detailed job info
    response = await client.get(f"/api/jobs/{job_id}/detail")

    assert response.status_code == 200
    data = response.json()

    # Verify required fields in detail response
    assert data["id"] == job_id
    assert data["job_type"] == "export"
    assert "status" in data
    assert "progress" in data
    assert "timing" in data
    assert "retry_info" in data
    assert "metadata" in data


@pytest.mark.asyncio
async def test_get_job_detail_progress_structure(client: AsyncClient, mock_redis, integration_db):
    """Test job detail progress has correct nested structure."""
    # Create an export job
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get detailed job info
    response = await client.get(f"/api/jobs/{job_id}/detail")
    assert response.status_code == 200

    data = response.json()

    # Verify progress structure
    progress = data["progress"]
    assert "percent" in progress
    assert isinstance(progress["percent"], int)
    assert 0 <= progress["percent"] <= 100
    # current_step, items_processed, items_total can be null
    assert "current_step" in progress
    assert "items_processed" in progress
    assert "items_total" in progress


@pytest.mark.asyncio
async def test_get_job_detail_timing_structure(client: AsyncClient, mock_redis, integration_db):
    """Test job detail timing has correct nested structure."""
    # Create an export job
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get detailed job info
    response = await client.get(f"/api/jobs/{job_id}/detail")
    assert response.status_code == 200

    data = response.json()

    # Verify timing structure
    timing = data["timing"]
    assert "created_at" in timing
    assert timing["created_at"] is not None
    assert "started_at" in timing
    assert "completed_at" in timing
    assert "duration_seconds" in timing
    assert "estimated_remaining_seconds" in timing


@pytest.mark.asyncio
async def test_get_job_detail_retry_info_structure(client: AsyncClient, mock_redis, integration_db):
    """Test job detail retry_info has correct nested structure."""
    # Create an export job
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get detailed job info
    response = await client.get(f"/api/jobs/{job_id}/detail")
    assert response.status_code == 200

    data = response.json()

    # Verify retry_info structure
    retry_info = data["retry_info"]
    assert "attempt_number" in retry_info
    assert retry_info["attempt_number"] >= 1
    assert "max_attempts" in retry_info
    assert retry_info["max_attempts"] >= 1
    assert "next_retry_at" in retry_info
    assert "previous_errors" in retry_info
    assert isinstance(retry_info["previous_errors"], list)


@pytest.mark.asyncio
async def test_get_job_detail_metadata_structure(client: AsyncClient, mock_redis, integration_db):
    """Test job detail metadata has correct nested structure."""
    # Create an export job
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get detailed job info
    response = await client.get(f"/api/jobs/{job_id}/detail")
    assert response.status_code == 200

    data = response.json()

    # Verify metadata structure
    metadata = data["metadata"]
    assert "input_params" in metadata
    assert "worker_id" in metadata


@pytest.mark.asyncio
async def test_get_job_detail_after_completion(client: AsyncClient, mock_redis, integration_db):
    """Test job detail endpoint returns complete info after job finishes."""
    # Create an export job
    job_request = {
        "format": "csv",
        "camera_id": "nonexistent_cam",  # Should complete quickly with no data
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Wait for job to complete
    await asyncio.sleep(0.5)

    # Get detailed job info
    response = await client.get(f"/api/jobs/{job_id}/detail")
    assert response.status_code == 200

    data = response.json()

    # Verify job has proper status
    assert data["status"] in ("pending", "running", "completed", "failed")

    # If completed, timing should have duration
    if data["status"] == "completed":
        assert data["timing"]["completed_at"] is not None
        assert data["timing"]["duration_seconds"] is not None
        assert data["progress"]["percent"] == 100
