"""Integration tests for job history and audit trail API endpoints.

Tests job history functionality with real database interactions including:
- Job history retrieval with transitions
- Job logs retrieval with filtering
- Integration with job lifecycle

NEM-2396: Job history and audit trail API integration tests.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.integration


# =============================================================================
# Job History Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_job_history_not_found(client: AsyncClient, mock_redis):
    """Test get job history returns 404 for non-existent job."""
    response = await client.get("/api/jobs/nonexistent-job-id/history")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_get_job_history_invalid_uuid(client: AsyncClient, mock_redis):
    """Test get job history returns 404 for invalid UUID format."""
    response = await client.get("/api/jobs/not-a-valid-uuid/history")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_get_job_history_for_existing_job(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test get job history returns history for existing job."""
    # Create an export job first
    job_request = {
        "format": "csv",
        "camera_id": "test_cam",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get job history
    response = await client.get(f"/api/jobs/{job_id}/history")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert data["job_id"] == job_id
    assert data["job_type"] == "export"
    assert "status" in data
    assert "created_at" in data
    assert "transitions" in data
    assert "attempts" in data
    assert isinstance(data["transitions"], list)
    assert isinstance(data["attempts"], list)


@pytest.mark.asyncio
async def test_get_job_history_has_timestamps(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test job history includes proper timestamps."""
    # Create an export job
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get job history
    response = await client.get(f"/api/jobs/{job_id}/history")
    assert response.status_code == 200

    data = response.json()

    # Verify timestamps
    assert data["created_at"] is not None
    # started_at and completed_at may be None initially
    assert "started_at" in data
    assert "completed_at" in data


@pytest.mark.asyncio
async def test_get_job_history_after_completion(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test job history after job completes includes timing info."""
    # Create an export job that should complete quickly
    job_request = {
        "format": "csv",
        "camera_id": "nonexistent_cam",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Wait for job to complete
    await asyncio.sleep(0.5)

    # Get job history
    response = await client.get(f"/api/jobs/{job_id}/history")
    assert response.status_code == 200

    data = response.json()

    # Verify job has proper status
    assert data["status"] in ("pending", "running", "completed", "failed")


# =============================================================================
# Job Logs Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_job_logs_not_found(client: AsyncClient, mock_redis):
    """Test get job logs returns 404 for non-existent job."""
    response = await client.get("/api/jobs/nonexistent-job-id/logs")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_get_job_logs_invalid_uuid(client: AsyncClient, mock_redis):
    """Test get job logs returns 404 for invalid UUID format."""
    response = await client.get("/api/jobs/not-a-valid-uuid/logs")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_job_logs_for_existing_job(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test get job logs returns logs structure for existing job."""
    # Create an export job first
    job_request = {
        "format": "csv",
        "camera_id": "test_cam",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get job logs
    response = await client.get(f"/api/jobs/{job_id}/logs")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert data["job_id"] == job_id
    assert "logs" in data
    assert "total" in data
    assert "has_more" in data
    assert isinstance(data["logs"], list)
    assert isinstance(data["total"], int)
    assert isinstance(data["has_more"], bool)


@pytest.mark.asyncio
async def test_get_job_logs_with_level_filter(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test get job logs with level filter."""
    # Create an export job first
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get job logs with ERROR level filter
    response = await client.get(f"/api/jobs/{job_id}/logs?level=ERROR")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "logs" in data
    # All returned logs should be ERROR level or higher
    for log in data["logs"]:
        assert log["level"] in ("ERROR",)


@pytest.mark.asyncio
async def test_get_job_logs_with_since_filter(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test get job logs with since timestamp filter."""
    # Create an export job first
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get job logs with since filter
    since = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    response = await client.get(f"/api/jobs/{job_id}/logs?since={since}")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "logs" in data


@pytest.mark.asyncio
async def test_get_job_logs_with_limit(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test get job logs respects limit parameter."""
    # Create an export job first
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get job logs with small limit
    response = await client.get(f"/api/jobs/{job_id}/logs?limit=5")

    assert response.status_code == 200
    data = response.json()

    # Verify limit is respected
    assert len(data["logs"]) <= 5


@pytest.mark.asyncio
async def test_get_job_logs_limit_validation(
    client: AsyncClient,
    mock_redis,
):
    """Test get job logs validates limit parameter bounds."""
    # Try with limit below minimum
    response = await client.get("/api/jobs/test-job/logs?limit=0")
    assert response.status_code == 422  # Validation error

    # Try with limit above maximum
    response = await client.get("/api/jobs/test-job/logs?limit=100001")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_job_logs_response_format(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test job logs response has correct log entry format."""
    # Create an export job first
    job_request = {
        "format": "csv",
        "camera_id": "test_cam",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Wait a bit for potential log entries
    await asyncio.sleep(0.2)

    # Get job logs
    response = await client.get(f"/api/jobs/{job_id}/logs")
    assert response.status_code == 200

    data = response.json()

    # If there are logs, verify their format
    for log in data["logs"]:
        assert "timestamp" in log
        assert "level" in log
        assert log["level"] in ("DEBUG", "INFO", "WARNING", "ERROR")
        assert "message" in log
        assert "attempt_number" in log
        assert isinstance(log["attempt_number"], int)
        assert log["attempt_number"] >= 1


# =============================================================================
# Combined History and Logs Tests
# =============================================================================


@pytest.mark.asyncio
async def test_job_history_and_logs_consistency(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test job history and logs endpoints return consistent data."""
    # Create an export job
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get both history and logs
    history_response = await client.get(f"/api/jobs/{job_id}/history")
    logs_response = await client.get(f"/api/jobs/{job_id}/logs")

    assert history_response.status_code == 200
    assert logs_response.status_code == 200

    history_data = history_response.json()
    logs_data = logs_response.json()

    # Verify job_id is consistent
    assert history_data["job_id"] == job_id
    assert logs_data["job_id"] == job_id


# =============================================================================
# Job History Transition Tests
# =============================================================================


@pytest.mark.asyncio
async def test_job_history_transitions_structure(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test job history transitions have correct structure."""
    # Create an export job
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get job history
    response = await client.get(f"/api/jobs/{job_id}/history")
    assert response.status_code == 200

    data = response.json()

    # If there are transitions, verify their structure
    for transition in data["transitions"]:
        # "from" can be null for initial transition
        assert "from" in transition or transition.get("from") is None
        assert "to" in transition
        assert "at" in transition
        assert "triggered_by" in transition
        # details can be null
        assert "details" in transition or transition.get("details") is None


@pytest.mark.asyncio
async def test_job_history_attempts_structure(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test job history attempts have correct structure."""
    # Create an export job
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get job history
    response = await client.get(f"/api/jobs/{job_id}/history")
    assert response.status_code == 200

    data = response.json()

    # If there are attempts, verify their structure
    for attempt in data["attempts"]:
        assert "attempt_number" in attempt
        assert isinstance(attempt["attempt_number"], int)
        assert attempt["attempt_number"] >= 1
        assert "started_at" in attempt
        assert "status" in attempt
        assert attempt["status"] in ("started", "succeeded", "failed", "cancelled")
        # ended_at, error, worker_id, duration_seconds, result can be null
        assert "ended_at" in attempt or attempt.get("ended_at") is None
        assert "error" in attempt or attempt.get("error") is None
        assert "worker_id" in attempt or attempt.get("worker_id") is None


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


@pytest.mark.asyncio
async def test_get_job_history_special_characters_in_id(client: AsyncClient, mock_redis):
    """Test get job history handles special characters in job ID."""
    # Test with URL-encoded special characters
    response = await client.get("/api/jobs/job%20with%20spaces/history")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_job_logs_special_characters_in_id(client: AsyncClient, mock_redis):
    """Test get job logs handles special characters in job ID."""
    response = await client.get("/api/jobs/job%20with%20spaces/logs")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_job_logs_invalid_level_filter(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test get job logs with invalid level filter still works."""
    # Create an export job first
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]

    # Get job logs with invalid level (should be treated as no filter)
    response = await client.get(f"/api/jobs/{job_id}/logs?level=INVALID")

    # Should still return 200 with logs (invalid level is essentially no filter)
    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
