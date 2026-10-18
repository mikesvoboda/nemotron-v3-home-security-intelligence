"""Integration tests for job logs API endpoint (NEM-2396)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def _seed_job_row(job_id: str, status: str = "queued") -> None:
    """Persist a jobs row for an in-memory tracker job."""
    from datetime import UTC, datetime

    from backend.core.database import get_session
    from backend.models.job import Job

    async with get_session() as session:
        session.add(
            Job(
                id=job_id,
                job_type="export",
                status=status,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()


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
    job_request = {
        "format": "csv",
        "camera_id": "test_cam",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]
    await _seed_job_row(job_id)

    response = await client.get(f"/api/jobs/{job_id}/logs")

    assert response.status_code == 200
    data = response.json()

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
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]
    await _seed_job_row(job_id)

    response = await client.get(f"/api/jobs/{job_id}/logs?level=ERROR")

    assert response.status_code == 200
    data = response.json()

    assert "logs" in data
    for log in data["logs"]:
        assert log["level"] in ("ERROR",)


@pytest.mark.asyncio
async def test_get_job_logs_with_since_filter(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test get job logs with since timestamp filter."""
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]
    await _seed_job_row(job_id)

    since = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    response = await client.get(f"/api/jobs/{job_id}/logs", params={"since": since})

    assert response.status_code == 200
    data = response.json()

    assert "logs" in data


@pytest.mark.asyncio
async def test_get_job_logs_with_limit(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test get job logs respects limit parameter."""
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]
    await _seed_job_row(job_id)

    response = await client.get(f"/api/jobs/{job_id}/logs?limit=5")

    assert response.status_code == 200
    data = response.json()

    assert len(data["logs"]) <= 5


@pytest.mark.asyncio
async def test_get_job_logs_limit_validation(
    client: AsyncClient,
    mock_redis,
):
    """Test get job logs validates limit parameter bounds."""
    response = await client.get("/api/jobs/test-job/logs?limit=0")
    assert response.status_code == 422

    response = await client.get("/api/jobs/test-job/logs?limit=100001")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_job_logs_response_format(
    client: AsyncClient,
    mock_redis,
    integration_db,
):
    """Test job logs response has correct log entry format."""
    job_request = {
        "format": "csv",
        "camera_id": "test_cam",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]
    await _seed_job_row(job_id)

    await asyncio.sleep(0.2)

    response = await client.get(f"/api/jobs/{job_id}/logs")
    assert response.status_code == 200

    data = response.json()

    for log in data["logs"]:
        assert "timestamp" in log
        assert "level" in log
        assert log["level"] in ("DEBUG", "INFO", "WARNING", "ERROR")
        assert "message" in log
        assert "attempt_number" in log
        assert isinstance(log["attempt_number"], int)
        assert log["attempt_number"] >= 1


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
    job_request = {
        "format": "csv",
    }
    create_response = await client.post("/api/events/export", json=job_request)
    assert create_response.status_code == 202

    job_data = create_response.json()
    job_id = job_data["job_id"]
    await _seed_job_row(job_id)

    response = await client.get(f"/api/jobs/{job_id}/logs?level=INVALID")

    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
