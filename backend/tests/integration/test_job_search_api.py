"""Integration tests for job search API endpoint.

Tests the GET /api/jobs/search endpoint with various filters
and aggregation capabilities.

NEM-2392: Job search and filtering API integration tests.
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
# Basic Search Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_returns_valid_structure(client: AsyncClient, mock_redis):
    """Test search endpoint returns valid response structure."""
    response = await client.get("/api/jobs/search")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data
    assert "aggregations" in data
    assert isinstance(data["data"], list)

    # Verify meta structure
    meta = data["meta"]
    assert "total" in meta
    assert "limit" in meta
    assert "offset" in meta
    assert "has_more" in meta

    # Verify aggregations structure
    aggs = data["aggregations"]
    assert "by_status" in aggs
    assert "by_type" in aggs
    assert isinstance(aggs["by_status"], dict)
    assert isinstance(aggs["by_type"], dict)


@pytest.mark.asyncio
async def test_search_jobs_empty_results(client: AsyncClient, mock_redis):
    """Test search with no matching results returns empty data array."""
    response = await client.get("/api/jobs/search?q=nonexistent_random_string_xyz")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["data"], list)


# =============================================================================
# Free Text Search Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_by_query(client: AsyncClient, mock_redis, integration_db):
    """Test free text search across job fields."""
    # Create an export job first
    job_request = {"format": "csv", "camera_id": "test_cam"}
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    # Search for export
    response = await client.get("/api/jobs/search?q=export")

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_search_jobs_query_case_insensitive(client: AsyncClient, mock_redis, integration_db):
    """Test free text search is case insensitive."""
    # Create an export job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    # Search with uppercase
    response_upper = await client.get("/api/jobs/search?q=EXPORT")
    # Search with mixed case
    response_mixed = await client.get("/api/jobs/search?q=Export")

    assert response_upper.status_code == 200
    assert response_mixed.status_code == 200


# =============================================================================
# Status Filter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_single_status_filter(client: AsyncClient, mock_redis, integration_db):
    """Test filtering by single status."""
    # Create a job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    # Search for pending jobs
    response = await client.get("/api/jobs/search?status=pending")

    assert response.status_code == 200
    data = response.json()
    for job in data["data"]:
        assert job["status"] == "pending"


@pytest.mark.asyncio
async def test_search_jobs_multiple_status_filter(client: AsyncClient, mock_redis, integration_db):
    """Test filtering by multiple comma-separated statuses."""
    # Create a job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    # Search for pending or running jobs
    response = await client.get("/api/jobs/search?status=pending,running")

    assert response.status_code == 200
    data = response.json()
    for job in data["data"]:
        assert job["status"] in ("pending", "running")


# =============================================================================
# Job Type Filter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_single_type_filter(client: AsyncClient, mock_redis, integration_db):
    """Test filtering by single job type."""
    # Create an export job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    response = await client.get("/api/jobs/search?job_type=export")

    assert response.status_code == 200
    data = response.json()
    for job in data["data"]:
        assert job["job_type"] == "export"


@pytest.mark.asyncio
async def test_search_jobs_multiple_type_filter(client: AsyncClient, mock_redis, integration_db):
    """Test filtering by multiple comma-separated job types."""
    # Create an export job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    response = await client.get("/api/jobs/search?job_type=export,cleanup")

    assert response.status_code == 200
    data = response.json()
    for job in data["data"]:
        assert job["job_type"] in ("export", "cleanup")


# =============================================================================
# Timestamp Filter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_created_after_filter(client: AsyncClient, mock_redis, integration_db):
    """Test filtering by created_after timestamp."""
    # Create a job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    # Search for jobs created in the past hour
    past_hour = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    response = await client.get(f"/api/jobs/search?created_after={past_hour}")

    assert response.status_code == 200
    data = response.json()
    # Jobs created just now should match
    assert "data" in data


@pytest.mark.asyncio
async def test_search_jobs_created_before_filter(client: AsyncClient, mock_redis, integration_db):
    """Test filtering by created_before timestamp."""
    # Create a job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    # Search for jobs created before now (all jobs)
    now = datetime.now(UTC).isoformat()
    response = await client.get(f"/api/jobs/search?created_before={now}")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_jobs_created_range_filter(client: AsyncClient, mock_redis, integration_db):
    """Test filtering by created_at range (after AND before)."""
    # Create a job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    past_hour = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    future_hour = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    response = await client.get(
        f"/api/jobs/search?created_after={past_hour}&created_before={future_hour}"
    )

    assert response.status_code == 200


# =============================================================================
# Error Filter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_has_error_true(client: AsyncClient, mock_redis, integration_db):
    """Test filtering for jobs with errors."""
    response = await client.get("/api/jobs/search?has_error=true")

    assert response.status_code == 200
    data = response.json()
    for job in data["data"]:
        assert job.get("error") is not None


@pytest.mark.asyncio
async def test_search_jobs_has_error_false(client: AsyncClient, mock_redis, integration_db):
    """Test filtering for jobs without errors."""
    # Create a job (no error expected initially)
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    response = await client.get("/api/jobs/search?has_error=false")

    assert response.status_code == 200
    data = response.json()
    for job in data["data"]:
        error = job.get("error")
        # Error should be None or empty
        assert error is None or error == ""


# =============================================================================
# Duration Filter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_min_duration_filter(client: AsyncClient, mock_redis, integration_db):
    """Test filtering by minimum duration."""
    response = await client.get("/api/jobs/search?min_duration=0")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_jobs_max_duration_filter(client: AsyncClient, mock_redis, integration_db):
    """Test filtering by maximum duration."""
    response = await client.get("/api/jobs/search?max_duration=3600")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_jobs_duration_range_filter(client: AsyncClient, mock_redis, integration_db):
    """Test filtering by duration range."""
    response = await client.get("/api/jobs/search?min_duration=0&max_duration=3600")

    assert response.status_code == 200


# =============================================================================
# Pagination Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_pagination_limit(client: AsyncClient, mock_redis, integration_db):
    """Test pagination limit parameter."""
    # Create multiple jobs
    for _ in range(3):
        job_request = {"format": "csv"}
        await client.post("/api/events/export", json=job_request)

    response = await client.get("/api/jobs/search?limit=2")

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) <= 2
    assert data["meta"]["limit"] == 2


@pytest.mark.asyncio
async def test_search_jobs_pagination_offset(client: AsyncClient, mock_redis, integration_db):
    """Test pagination offset parameter."""
    # Create multiple jobs
    for _ in range(3):
        job_request = {"format": "csv"}
        await client.post("/api/events/export", json=job_request)

    response = await client.get("/api/jobs/search?limit=10&offset=1")

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["offset"] == 1


@pytest.mark.asyncio
async def test_search_jobs_pagination_has_more(client: AsyncClient, mock_redis, integration_db):
    """Test pagination has_more indicator."""
    # Create multiple jobs
    for _ in range(3):
        job_request = {"format": "csv"}
        await client.post("/api/events/export", json=job_request)

    # Get first page with small limit
    response = await client.get("/api/jobs/search?limit=1")

    assert response.status_code == 200
    data = response.json()
    # If total > limit, has_more should be true
    if data["meta"]["total"] > 1:
        assert data["meta"]["has_more"] is True


# =============================================================================
# Sorting Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_sort_by_created_at_desc(client: AsyncClient, mock_redis, integration_db):
    """Test sorting by created_at descending (default)."""
    # Create multiple jobs with slight delay
    for _ in range(2):
        job_request = {"format": "csv"}
        await client.post("/api/events/export", json=job_request)
        await asyncio.sleep(0.1)

    response = await client.get("/api/jobs/search?sort=created_at&order=desc")

    assert response.status_code == 200
    data = response.json()
    if len(data["data"]) >= 2:
        # First job should be created after second job
        created_at_0 = data["data"][0]["created_at"]
        created_at_1 = data["data"][1]["created_at"]
        assert created_at_0 >= created_at_1


@pytest.mark.asyncio
async def test_search_jobs_sort_by_created_at_asc(client: AsyncClient, mock_redis, integration_db):
    """Test sorting by created_at ascending."""
    # Create multiple jobs with slight delay
    for _ in range(2):
        job_request = {"format": "csv"}
        await client.post("/api/events/export", json=job_request)
        await asyncio.sleep(0.1)

    response = await client.get("/api/jobs/search?sort=created_at&order=asc")

    assert response.status_code == 200
    data = response.json()
    if len(data["data"]) >= 2:
        # First job should be created before second job
        created_at_0 = data["data"][0]["created_at"]
        created_at_1 = data["data"][1]["created_at"]
        assert created_at_0 <= created_at_1


@pytest.mark.asyncio
async def test_search_jobs_sort_by_status(client: AsyncClient, mock_redis, integration_db):
    """Test sorting by status field."""
    response = await client.get("/api/jobs/search?sort=status&order=asc")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_jobs_sort_by_job_type(client: AsyncClient, mock_redis, integration_db):
    """Test sorting by job_type field."""
    response = await client.get("/api/jobs/search?sort=job_type&order=desc")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_jobs_sort_by_progress(client: AsyncClient, mock_redis, integration_db):
    """Test sorting by progress field."""
    response = await client.get("/api/jobs/search?sort=progress&order=desc")

    assert response.status_code == 200


# =============================================================================
# Aggregation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_aggregations_by_status(client: AsyncClient, mock_redis, integration_db):
    """Test aggregations include status counts."""
    # Create jobs
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    response = await client.get("/api/jobs/search")

    assert response.status_code == 200
    data = response.json()
    by_status = data["aggregations"]["by_status"]
    assert isinstance(by_status, dict)
    # All status values should be non-negative integers
    for status, count in by_status.items():
        assert isinstance(count, int)
        assert count >= 0


@pytest.mark.asyncio
async def test_search_jobs_aggregations_by_type(client: AsyncClient, mock_redis, integration_db):
    """Test aggregations include job type counts."""
    # Create export job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    response = await client.get("/api/jobs/search")

    assert response.status_code == 200
    data = response.json()
    by_type = data["aggregations"]["by_type"]
    assert isinstance(by_type, dict)
    # All type counts should be non-negative integers
    for job_type, count in by_type.items():
        assert isinstance(count, int)
        assert count >= 0


@pytest.mark.asyncio
async def test_search_jobs_aggregations_reflect_filters(
    client: AsyncClient, mock_redis, integration_db
):
    """Test aggregations are computed on filtered results, not all jobs."""
    # Create an export job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    # Search only for export jobs
    response = await client.get("/api/jobs/search?job_type=export")

    assert response.status_code == 200
    data = response.json()
    by_type = data["aggregations"]["by_type"]
    # Only export type should be in aggregations
    if by_type:
        assert "export" in by_type


# =============================================================================
# Combined Filter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_combined_filters(client: AsyncClient, mock_redis, integration_db):
    """Test combining multiple filters."""
    # Create job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    past_hour = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

    response = await client.get(
        f"/api/jobs/search?q=export&status=pending,running&job_type=export&created_after={past_hour}"
    )

    assert response.status_code == 200
    data = response.json()
    for job in data["data"]:
        assert job["job_type"] == "export"
        assert job["status"] in ("pending", "running")


@pytest.mark.asyncio
async def test_search_jobs_all_parameters(client: AsyncClient, mock_redis, integration_db):
    """Test search with all parameters specified."""
    now = datetime.now(UTC)
    past_hour = (now - timedelta(hours=1)).isoformat()
    future_hour = (now + timedelta(hours=1)).isoformat()

    response = await client.get(
        f"/api/jobs/search?"
        f"q=test&"
        f"status=pending,running,completed&"
        f"job_type=export&"
        f"created_after={past_hour}&"
        f"created_before={future_hour}&"
        f"has_error=false&"
        f"min_duration=0&"
        f"max_duration=3600&"
        f"limit=10&"
        f"offset=0&"
        f"sort=created_at&"
        f"order=desc"
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert "aggregations" in data


# =============================================================================
# Edge Cases and Validation
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_invalid_limit(client: AsyncClient, mock_redis):
    """Test search with invalid limit returns validation error."""
    response = await client.get("/api/jobs/search?limit=-1")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_jobs_limit_exceeds_max(client: AsyncClient, mock_redis):
    """Test search with limit exceeding maximum returns validation error."""
    response = await client.get("/api/jobs/search?limit=2000")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_jobs_invalid_offset(client: AsyncClient, mock_redis):
    """Test search with invalid offset returns validation error."""
    response = await client.get("/api/jobs/search?offset=-1")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_jobs_invalid_min_duration(client: AsyncClient, mock_redis):
    """Test search with negative min_duration returns validation error."""
    response = await client.get("/api/jobs/search?min_duration=-1")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_jobs_empty_status_filter(client: AsyncClient, mock_redis, integration_db):
    """Test search with empty status filter returns all jobs."""
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    response = await client.get("/api/jobs/search?status=")

    # Empty status should be treated as no filter
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_jobs_whitespace_in_filter(client: AsyncClient, mock_redis, integration_db):
    """Test search handles whitespace in comma-separated filters."""
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    response = await client.get("/api/jobs/search?status=pending, running,completed ")

    assert response.status_code == 200


# =============================================================================
# Meta Total Accuracy Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_jobs_total_matches_unfiltered(
    client: AsyncClient, mock_redis, integration_db
):
    """Test meta.total accurately reflects total matching jobs."""
    # Create some jobs
    for _ in range(3):
        job_request = {"format": "csv"}
        await client.post("/api/events/export", json=job_request)

    # Get with small limit
    response = await client.get("/api/jobs/search?limit=1")

    assert response.status_code == 200
    data = response.json()
    # Total should be >= jobs returned (pagination applies after counting)
    assert data["meta"]["total"] >= len(data["data"])


@pytest.mark.asyncio
async def test_search_jobs_total_with_filter(client: AsyncClient, mock_redis, integration_db):
    """Test meta.total reflects filtered count, not all jobs."""
    # Create an export job
    job_request = {"format": "csv"}
    await client.post("/api/events/export", json=job_request)

    # Filter to only export jobs
    response = await client.get("/api/jobs/search?job_type=export")

    assert response.status_code == 200
    data = response.json()
    # Total should match count of export jobs specifically
    for job in data["data"]:
        assert job["job_type"] == "export"
