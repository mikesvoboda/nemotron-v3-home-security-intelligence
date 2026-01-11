"""Integration tests for jobs API endpoints.

These tests verify job tracking functionality works correctly with
real database interactions.
"""

import pytest


@pytest.mark.asyncio
async def test_list_jobs_empty(client, mock_redis):
    """Test list jobs endpoint returns empty list when no jobs exist."""
    response = await client.get("/api/jobs/")

    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert isinstance(data["jobs"], list)


@pytest.mark.asyncio
async def test_list_jobs_with_type_filter(client, mock_redis):
    """Test list jobs endpoint with job_type filter."""
    response = await client.get("/api/jobs/?job_type=export")

    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data


@pytest.mark.asyncio
async def test_list_jobs_with_status_filter(client, mock_redis):
    """Test list jobs endpoint with status filter."""
    response = await client.get("/api/jobs/?status=running")

    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data


@pytest.mark.asyncio
async def test_list_jobs_pagination(client, mock_redis):
    """Test list jobs endpoint with pagination."""
    response = await client.get("/api/jobs/?limit=10&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_job_not_found(client, mock_redis):
    """Test get job endpoint returns 404 for non-existent job."""
    response = await client.get("/api/jobs/nonexistent-job-id")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_job_not_found(client, mock_redis):
    """Test cancel job endpoint returns 404 for non-existent job."""
    response = await client.post("/api/jobs/nonexistent-job-id/cancel")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_job_stats_endpoint(client, mock_redis):
    """Test job stats endpoint returns statistics."""
    response = await client.get("/api/jobs/stats")

    assert response.status_code == 200
    data = response.json()
    assert "total_jobs" in data
    assert "by_status" in data
    assert "by_type" in data
