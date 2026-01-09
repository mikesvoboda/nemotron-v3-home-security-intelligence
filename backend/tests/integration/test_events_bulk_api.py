"""Integration tests for event bulk API endpoints (NEM-1433).

Tests the bulk create, update, and delete endpoints for events
including partial success handling with HTTP 207 Multi-Status responses.
"""

import uuid
from datetime import UTC, datetime

import pytest

from backend.api.schemas.bulk import BulkOperationStatus


@pytest.fixture
async def async_client(client):
    """Alias for shared client fixture for backward compatibility."""
    yield client


@pytest.fixture
async def clean_events(integration_db):
    """Delete events and cameras before test for isolation."""
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        await conn.execute(text("DELETE FROM detections"))  # nosemgrep: avoid-sqlalchemy-text
        await conn.execute(text("DELETE FROM events"))  # nosemgrep: avoid-sqlalchemy-text
        await conn.execute(text("DELETE FROM cameras"))  # nosemgrep: avoid-sqlalchemy-text

    yield


@pytest.fixture
async def sample_camera(integration_db, clean_events):
    """Create a sample camera for bulk operations."""
    from backend.core.database import get_session
    from backend.models.camera import Camera

    camera_id = f"bulk_test_{uuid.uuid4().hex[:8]}"
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name="Bulk Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        yield camera


@pytest.fixture
async def sample_events(integration_db, sample_camera):
    """Create sample events for update and delete tests."""
    from backend.core.database import get_session
    from backend.models.event import Event

    events = []
    async with get_session() as db:
        for i in range(5):
            event = Event(
                batch_id=str(uuid.uuid4()),
                camera_id=sample_camera.id,
                started_at=datetime.now(UTC),
                risk_score=50 + i * 10,
                risk_level="medium",
                summary=f"Test event {i}",
                reviewed=False,
            )
            db.add(event)
            events.append(event)
        await db.commit()
        for event in events:
            await db.refresh(event)
        yield events


class TestBulkCreateEvents:
    """Tests for POST /api/events/bulk endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_create_events_success(self, async_client, sample_camera):
        """Test successful bulk creation of events."""
        events_data = {
            "events": [
                {
                    "camera_id": sample_camera.id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Test event 1",
                },
                {
                    "camera_id": sample_camera.id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "risk_score": 25,
                    "risk_level": "low",
                    "summary": "Test event 2",
                },
            ]
        }

        response = await async_client.post("/api/events/bulk", json=events_data)

        assert response.status_code == 207  # Multi-Status
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        assert len(data["results"]) == 2

        for result in data["results"]:
            assert result["status"] == BulkOperationStatus.SUCCESS
            assert result["id"] is not None
            assert result["error"] is None

    @pytest.mark.asyncio
    async def test_bulk_create_events_partial_failure(self, async_client, sample_camera):
        """Test bulk create with partial failure (invalid camera_id)."""
        events_data = {
            "events": [
                {
                    "camera_id": sample_camera.id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Valid event",
                },
                {
                    "camera_id": "nonexistent_camera",
                    "started_at": datetime.now(UTC).isoformat(),
                    "risk_score": 25,
                    "risk_level": "low",
                    "summary": "Invalid camera event",
                },
            ]
        }

        response = await async_client.post("/api/events/bulk", json=events_data)

        assert response.status_code == 207
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1

        # First event should succeed
        assert data["results"][0]["status"] == BulkOperationStatus.SUCCESS
        assert data["results"][0]["id"] is not None

        # Second event should fail
        assert data["results"][1]["status"] == BulkOperationStatus.FAILED
        assert "not found" in data["results"][1]["error"].lower()

    @pytest.mark.asyncio
    async def test_bulk_create_events_validation_error(self, async_client):
        """Test validation error for invalid request format."""
        # Empty events list should fail validation
        response = await async_client.post("/api/events/bulk", json={"events": []})
        assert response.status_code == 422


class TestBulkUpdateEvents:
    """Tests for PATCH /api/events/bulk endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_update_events_success(self, async_client, sample_events):
        """Test successful bulk update of events."""
        update_data = {
            "events": [
                {"id": sample_events[0].id, "reviewed": True},
                {"id": sample_events[1].id, "reviewed": True, "notes": "Test note"},
            ]
        }

        response = await async_client.patch("/api/events/bulk", json=update_data)

        assert response.status_code == 207
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0

        for result in data["results"]:
            assert result["status"] == BulkOperationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_bulk_update_events_not_found(self, async_client, sample_events):
        """Test bulk update with some events not found."""
        update_data = {
            "events": [
                {"id": sample_events[0].id, "reviewed": True},
                {"id": 999999, "reviewed": True},  # Non-existent event
            ]
        }

        response = await async_client.patch("/api/events/bulk", json=update_data)

        assert response.status_code == 207
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1

        # First event should succeed
        assert data["results"][0]["status"] == BulkOperationStatus.SUCCESS

        # Second event should fail
        assert data["results"][1]["status"] == BulkOperationStatus.FAILED
        assert "not found" in data["results"][1]["error"].lower()


class TestBulkDeleteEvents:
    """Tests for DELETE /api/events/bulk endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_delete_events_soft_delete(self, async_client, sample_events):
        """Test bulk soft delete of events."""
        delete_data = {
            "event_ids": [sample_events[0].id, sample_events[1].id],
            "soft_delete": True,
        }

        response = await async_client.request("DELETE", "/api/events/bulk", json=delete_data)

        assert response.status_code == 207
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0

    @pytest.mark.asyncio
    async def test_bulk_delete_events_hard_delete(self, async_client, sample_events):
        """Test bulk hard delete of events."""
        delete_data = {
            "event_ids": [sample_events[2].id, sample_events[3].id],
            "soft_delete": False,
        }

        response = await async_client.request("DELETE", "/api/events/bulk", json=delete_data)

        assert response.status_code == 207
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0

        # Verify events are actually deleted
        check_response = await async_client.get(f"/api/events/{sample_events[2].id}")
        assert check_response.status_code == 404

    @pytest.mark.asyncio
    async def test_bulk_delete_events_not_found(self, async_client, sample_events):
        """Test bulk delete with some events not found."""
        delete_data = {
            "event_ids": [sample_events[0].id, 999999],
            "soft_delete": False,
        }

        response = await async_client.request("DELETE", "/api/events/bulk", json=delete_data)

        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 1
        assert data["failed"] == 1

        # Check results
        success_result = next(r for r in data["results"] if r["id"] == sample_events[0].id)
        assert success_result["status"] == BulkOperationStatus.SUCCESS

        failed_result = next(r for r in data["results"] if r["id"] == 999999)
        assert failed_result["status"] == BulkOperationStatus.FAILED
