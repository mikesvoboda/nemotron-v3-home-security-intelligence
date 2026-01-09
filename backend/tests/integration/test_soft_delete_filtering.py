"""Integration tests for soft delete filtering across API endpoints.

These tests verify that soft-deleted records (records with a non-null deleted_at
timestamp) are properly excluded from API responses.

Soft delete models:
- Camera: Has deleted_at field
- Event: Has deleted_at field

Note: Detection model does NOT have soft delete support.

Test scenarios covered:
1. GET list endpoints exclude soft-deleted records
2. GET single endpoints return 404 for soft-deleted records
3. Soft-deleted records are excluded from search results
4. Soft-deleted records are excluded from aggregations/counts
5. Filtering by other criteria still excludes soft-deleted records

These tests use the integration test fixtures from conftest.py:
- integration_db: Clean database with schema
- client: HTTP client for API testing
- mock_redis: Mock Redis client
"""

import uuid
from datetime import UTC, datetime

import pytest

from backend.core.database import get_session
from backend.models.camera import Camera
from backend.models.event import Event

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def active_camera(client) -> Camera:
    """Create an active (non-deleted) camera.

    Note: Depends on `client` fixture to ensure this runs AFTER client cleanup.
    """
    unique_id = uuid.uuid4().hex[:8]
    async with get_session() as db:
        camera = Camera(
            id=f"active_camera_{unique_id}",
            name=f"Active Camera {unique_id}",
            folder_path=f"/export/foscam/active_camera_{unique_id}",
            status="online",
            deleted_at=None,  # Not deleted
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        return camera


@pytest.fixture
async def soft_deleted_camera(client) -> Camera:
    """Create a soft-deleted camera (has deleted_at timestamp).

    Note: Depends on `client` fixture to ensure this runs AFTER client cleanup.
    """
    unique_id = uuid.uuid4().hex[:8]
    async with get_session() as db:
        camera = Camera(
            id=f"deleted_camera_{unique_id}",
            name=f"Deleted Camera {unique_id}",
            folder_path=f"/export/foscam/deleted_camera_{unique_id}",
            status="online",
            deleted_at=datetime.now(UTC),  # Soft deleted
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        return camera


@pytest.fixture
async def active_event(client, active_camera) -> Event:
    """Create an active (non-deleted) event.

    Note: Depends on `client` fixture to ensure this runs AFTER client cleanup.
    """
    async with get_session() as db:
        event = Event(
            batch_id=str(uuid.uuid4()),
            camera_id=active_camera.id,
            started_at=datetime.now(UTC),
            risk_score=50,
            risk_level="medium",
            summary="Active event for testing",
            reviewed=False,
            deleted_at=None,  # Not deleted
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event


@pytest.fixture
async def soft_deleted_event(client, active_camera) -> Event:
    """Create a soft-deleted event (has deleted_at timestamp).

    Note: Depends on `client` fixture to ensure this runs AFTER client cleanup.
    """
    async with get_session() as db:
        event = Event(
            batch_id=str(uuid.uuid4()),
            camera_id=active_camera.id,
            started_at=datetime.now(UTC),
            risk_score=75,
            risk_level="high",
            summary="Soft deleted event for testing",
            reviewed=False,
            deleted_at=datetime.now(UTC),  # Soft deleted
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event


@pytest.fixture
async def multiple_cameras_mixed(client) -> tuple[list[Camera], list[Camera]]:
    """Create a mix of active and soft-deleted cameras.

    Note: Depends on `client` fixture to ensure this runs AFTER client cleanup.

    Returns:
        Tuple of (active_cameras, deleted_cameras)
    """
    active_cameras = []
    deleted_cameras = []

    async with get_session() as db:
        # Create 3 active cameras
        for i in range(3):
            unique_id = uuid.uuid4().hex[:8]
            camera = Camera(
                id=f"active_{i}_{unique_id}",
                name=f"Active Camera {i} {unique_id}",
                folder_path=f"/export/foscam/active_{i}_{unique_id}",
                status="online",
                deleted_at=None,
            )
            db.add(camera)
            active_cameras.append(camera)

        # Create 2 soft-deleted cameras
        for i in range(2):
            unique_id = uuid.uuid4().hex[:8]
            camera = Camera(
                id=f"deleted_{i}_{unique_id}",
                name=f"Deleted Camera {i} {unique_id}",
                folder_path=f"/export/foscam/deleted_{i}_{unique_id}",
                status="online",
                deleted_at=datetime.now(UTC),
            )
            db.add(camera)
            deleted_cameras.append(camera)

        await db.commit()

        # Refresh all
        for camera in active_cameras + deleted_cameras:
            await db.refresh(camera)

    return active_cameras, deleted_cameras


@pytest.fixture
async def multiple_events_mixed(client, active_camera) -> tuple[list[Event], list[Event]]:
    """Create a mix of active and soft-deleted events.

    Note: Depends on `client` fixture to ensure this runs AFTER client cleanup.

    Returns:
        Tuple of (active_events, deleted_events)
    """
    active_events = []
    deleted_events = []

    async with get_session() as db:
        # Create 3 active events with different risk levels
        for i, (risk_score, risk_level) in enumerate([(20, "low"), (50, "medium"), (80, "high")]):
            event = Event(
                batch_id=str(uuid.uuid4()),
                camera_id=active_camera.id,
                started_at=datetime(2025, 12, 23, 10 + i, 0, 0, tzinfo=UTC),
                risk_score=risk_score,
                risk_level=risk_level,
                summary=f"Active event {i} - {risk_level} risk",
                reviewed=(i == 0),  # First one is reviewed
                deleted_at=None,
            )
            db.add(event)
            active_events.append(event)

        # Create 2 soft-deleted events
        for i in range(2):
            event = Event(
                batch_id=str(uuid.uuid4()),
                camera_id=active_camera.id,
                started_at=datetime(2025, 12, 23, 15 + i, 0, 0, tzinfo=UTC),
                risk_score=90,
                risk_level="critical",
                summary=f"Deleted event {i}",
                reviewed=False,
                deleted_at=datetime.now(UTC),
            )
            db.add(event)
            deleted_events.append(event)

        await db.commit()

        # Refresh all
        for event in active_events + deleted_events:
            await db.refresh(event)

    return active_events, deleted_events


# =============================================================================
# Camera Soft Delete Tests
# =============================================================================


class TestCameraSoftDeleteFiltering:
    """Tests for soft delete filtering on Camera API endpoints."""

    @pytest.mark.asyncio
    async def test_list_cameras_excludes_soft_deleted(self, client, multiple_cameras_mixed):
        """GET /api/cameras should exclude soft-deleted cameras from the list."""
        active_cameras, deleted_cameras = multiple_cameras_mixed

        response = await client.get("/api/cameras")
        assert response.status_code == 200
        data = response.json()

        # Should only return active cameras
        returned_ids = {camera["id"] for camera in data["cameras"]}
        active_ids = {camera.id for camera in active_cameras}
        deleted_ids = {camera.id for camera in deleted_cameras}

        # All active cameras should be in the response
        assert active_ids.issubset(returned_ids), (
            f"Active cameras missing from response. Expected {active_ids} to be in {returned_ids}"
        )

        # No deleted cameras should be in the response
        assert deleted_ids.isdisjoint(returned_ids), (
            f"Soft-deleted cameras should not appear in response. "
            f"Found {deleted_ids.intersection(returned_ids)}"
        )

        # Count should reflect only active cameras
        assert data["count"] >= len(active_cameras)
        # Should not include deleted cameras in count
        for deleted_camera in deleted_cameras:
            assert deleted_camera.id not in returned_ids

    @pytest.mark.asyncio
    async def test_get_camera_returns_404_for_soft_deleted(self, client, soft_deleted_camera):
        """GET /api/cameras/{id} should return 404 for soft-deleted camera."""
        response = await client.get(f"/api/cameras/{soft_deleted_camera.id}")

        # Should return 404 as if the camera doesn't exist
        assert response.status_code == 404, (
            f"Expected 404 for soft-deleted camera, got {response.status_code}. "
            f"Soft-deleted records should not be accessible via direct lookup."
        )

    @pytest.mark.asyncio
    async def test_get_camera_returns_active_camera(self, client, active_camera):
        """GET /api/cameras/{id} should return active (non-deleted) camera."""
        response = await client.get(f"/api/cameras/{active_camera.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == active_camera.id

    @pytest.mark.asyncio
    async def test_list_cameras_filter_by_status_excludes_soft_deleted(
        self, client, multiple_cameras_mixed
    ):
        """GET /api/cameras?status=online should exclude soft-deleted cameras."""
        _active_cameras, deleted_cameras = multiple_cameras_mixed

        response = await client.get("/api/cameras?status=online")
        assert response.status_code == 200
        data = response.json()

        returned_ids = {camera["id"] for camera in data["cameras"]}
        deleted_ids = {camera.id for camera in deleted_cameras}

        # Soft-deleted cameras should not appear even with status filter
        assert deleted_ids.isdisjoint(returned_ids), (
            f"Soft-deleted cameras should not appear even when filtering by status. "
            f"Found {deleted_ids.intersection(returned_ids)}"
        )

    @pytest.mark.asyncio
    async def test_update_camera_returns_404_for_soft_deleted(self, client, soft_deleted_camera):
        """PATCH /api/cameras/{id} should return 404 for soft-deleted camera."""
        response = await client.patch(
            f"/api/cameras/{soft_deleted_camera.id}",
            json={"name": "New Name"},
        )

        assert response.status_code == 404, (
            f"Expected 404 when updating soft-deleted camera, got {response.status_code}. "
            f"Soft-deleted records should not be updatable."
        )

    @pytest.mark.asyncio
    async def test_delete_camera_returns_404_for_soft_deleted(self, client, soft_deleted_camera):
        """DELETE /api/cameras/{id} should return 404 for already soft-deleted camera."""
        response = await client.delete(f"/api/cameras/{soft_deleted_camera.id}")

        assert response.status_code == 404, (
            f"Expected 404 when deleting already soft-deleted camera, got {response.status_code}. "
            f"Soft-deleted records should not be deletable again."
        )


# =============================================================================
# Event Soft Delete Tests
# =============================================================================


class TestEventSoftDeleteFiltering:
    """Tests for soft delete filtering on Event API endpoints."""

    @pytest.mark.asyncio
    async def test_list_events_excludes_soft_deleted(self, client, multiple_events_mixed):
        """GET /api/events should exclude soft-deleted events from the list."""
        active_events, deleted_events = multiple_events_mixed

        response = await client.get("/api/events")
        assert response.status_code == 200
        data = response.json()

        # Should only return active events
        returned_ids = {event["id"] for event in data["events"]}
        active_ids = {event.id for event in active_events}
        deleted_ids = {event.id for event in deleted_events}

        # All active events should be in the response
        assert active_ids.issubset(returned_ids), (
            f"Active events missing from response. Expected {active_ids} to be in {returned_ids}"
        )

        # No deleted events should be in the response
        assert deleted_ids.isdisjoint(returned_ids), (
            f"Soft-deleted events should not appear in response. "
            f"Found {deleted_ids.intersection(returned_ids)}"
        )

        # Count should reflect only active events
        assert data["count"] >= len(active_events)

    @pytest.mark.asyncio
    async def test_get_event_returns_404_for_soft_deleted(self, client, soft_deleted_event):
        """GET /api/events/{id} should return 404 for soft-deleted event."""
        response = await client.get(f"/api/events/{soft_deleted_event.id}")

        assert response.status_code == 404, (
            f"Expected 404 for soft-deleted event, got {response.status_code}. "
            f"Soft-deleted records should not be accessible via direct lookup."
        )

    @pytest.mark.asyncio
    async def test_get_event_returns_active_event(self, client, active_event):
        """GET /api/events/{id} should return active (non-deleted) event."""
        response = await client.get(f"/api/events/{active_event.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == active_event.id

    @pytest.mark.asyncio
    async def test_list_events_filter_by_risk_level_excludes_soft_deleted(
        self, client, multiple_events_mixed
    ):
        """GET /api/events?risk_level=critical should exclude soft-deleted events."""
        _active_events, deleted_events = multiple_events_mixed

        # Deleted events have critical risk level
        response = await client.get("/api/events?risk_level=critical")
        assert response.status_code == 200
        data = response.json()

        returned_ids = {event["id"] for event in data["events"]}
        deleted_ids = {event.id for event in deleted_events}

        # Soft-deleted critical events should not appear
        assert deleted_ids.isdisjoint(returned_ids), (
            f"Soft-deleted events should not appear even when filtering by risk_level. "
            f"Found {deleted_ids.intersection(returned_ids)}"
        )

    @pytest.mark.asyncio
    async def test_list_events_filter_by_camera_excludes_soft_deleted(
        self, client, multiple_events_mixed, active_camera
    ):
        """GET /api/events?camera_id={id} should exclude soft-deleted events."""
        _active_events, deleted_events = multiple_events_mixed

        response = await client.get(f"/api/events?camera_id={active_camera.id}")
        assert response.status_code == 200
        data = response.json()

        returned_ids = {event["id"] for event in data["events"]}
        deleted_ids = {event.id for event in deleted_events}

        # Soft-deleted events should not appear even with camera filter
        assert deleted_ids.isdisjoint(returned_ids), (
            f"Soft-deleted events should not appear when filtering by camera. "
            f"Found {deleted_ids.intersection(returned_ids)}"
        )

    @pytest.mark.asyncio
    async def test_list_events_filter_by_reviewed_excludes_soft_deleted(
        self, client, multiple_events_mixed
    ):
        """GET /api/events?reviewed=false should exclude soft-deleted events."""
        _active_events, deleted_events = multiple_events_mixed

        response = await client.get("/api/events?reviewed=false")
        assert response.status_code == 200
        data = response.json()

        returned_ids = {event["id"] for event in data["events"]}
        deleted_ids = {event.id for event in deleted_events}

        # Soft-deleted events (which are unreviewed) should not appear
        assert deleted_ids.isdisjoint(returned_ids), (
            f"Soft-deleted events should not appear when filtering by reviewed status. "
            f"Found {deleted_ids.intersection(returned_ids)}"
        )

    @pytest.mark.asyncio
    async def test_list_events_filter_by_date_range_excludes_soft_deleted(
        self, client, multiple_events_mixed
    ):
        """GET /api/events with date range should exclude soft-deleted events."""
        _active_events, deleted_events = multiple_events_mixed

        # Use a date range that includes all events
        response = await client.get(
            "/api/events?start_date=2025-12-23T00:00:00Z&end_date=2025-12-23T23:59:59Z"
        )
        assert response.status_code == 200
        data = response.json()

        returned_ids = {event["id"] for event in data["events"]}
        deleted_ids = {event.id for event in deleted_events}

        # Soft-deleted events should not appear even within date range
        assert deleted_ids.isdisjoint(returned_ids), (
            f"Soft-deleted events should not appear when filtering by date range. "
            f"Found {deleted_ids.intersection(returned_ids)}"
        )

    @pytest.mark.asyncio
    async def test_update_event_returns_404_for_soft_deleted(self, client, soft_deleted_event):
        """PATCH /api/events/{id} should return 404 for soft-deleted event."""
        response = await client.patch(
            f"/api/events/{soft_deleted_event.id}",
            json={"reviewed": True},
        )

        assert response.status_code == 404, (
            f"Expected 404 when updating soft-deleted event, got {response.status_code}. "
            f"Soft-deleted records should not be updatable."
        )


# =============================================================================
# Event Stats Soft Delete Tests
# =============================================================================


class TestEventStatsSoftDeleteFiltering:
    """Tests for soft delete filtering on event stats/aggregation endpoints."""

    @pytest.mark.asyncio
    async def test_event_stats_excludes_soft_deleted(self, client, multiple_events_mixed):
        """GET /api/events/stats should exclude soft-deleted events from counts."""
        active_events, _deleted_events = multiple_events_mixed

        response = await client.get("/api/events/stats")
        assert response.status_code == 200
        data = response.json()

        # Total events should only count active events
        # The deleted events have risk_level="critical", so if they're counted,
        # we'd see critical > 0
        total_active = len(active_events)

        # Verify total count matches active events (not including deleted)
        assert data["total_events"] == total_active, (
            f"Total events count ({data['total_events']}) should equal active events ({total_active}). "
            f"Soft-deleted events should not be counted."
        )

        # Critical events are only in deleted_events, so should be 0
        assert data["events_by_risk_level"]["critical"] == 0, (
            f"Critical events count ({data['events_by_risk_level']['critical']}) should be 0. "
            f"Soft-deleted critical events should not be counted."
        )

    @pytest.mark.asyncio
    async def test_event_stats_with_date_filter_excludes_soft_deleted(
        self, client, multiple_events_mixed
    ):
        """GET /api/events/stats with date filter should exclude soft-deleted events."""
        active_events, _deleted_events = multiple_events_mixed

        response = await client.get(
            "/api/events/stats?start_date=2025-12-23T00:00:00Z&end_date=2025-12-23T23:59:59Z"
        )
        assert response.status_code == 200
        data = response.json()

        # Should only count active events in the date range
        total_active = len(active_events)
        assert data["total_events"] == total_active, (
            f"Total events with date filter ({data['total_events']}) should equal "
            f"active events ({total_active}). Soft-deleted events should not be counted."
        )


# =============================================================================
# Event Search Soft Delete Tests
# =============================================================================


class TestEventSearchSoftDeleteFiltering:
    """Tests for soft delete filtering on event search endpoint."""

    @pytest.mark.asyncio
    async def test_search_events_excludes_soft_deleted(self, client, multiple_events_mixed):
        """GET /api/events/search should exclude soft-deleted events from results."""
        _active_events, deleted_events = multiple_events_mixed

        # Search for "event" which should match all events' summaries
        response = await client.get("/api/events/search?q=event")
        assert response.status_code == 200
        data = response.json()

        returned_ids = {result["id"] for result in data["results"]}
        deleted_ids = {event.id for event in deleted_events}

        # Soft-deleted events should not appear in search results
        assert deleted_ids.isdisjoint(returned_ids), (
            f"Soft-deleted events should not appear in search results. "
            f"Found {deleted_ids.intersection(returned_ids)}"
        )

    @pytest.mark.asyncio
    async def test_search_events_by_summary_excludes_soft_deleted(
        self, client, multiple_events_mixed
    ):
        """Searching by text that matches deleted events should not return them."""
        _active_events, _deleted_events = multiple_events_mixed

        # Search for "Deleted event" which is in the deleted events' summaries
        response = await client.get("/api/events/search?q=Deleted%20event")
        assert response.status_code == 200
        data = response.json()

        # Should return 0 results since matching events are soft-deleted
        assert data["total_count"] == 0, (
            f"Search for text in soft-deleted events should return 0 results. "
            f"Got {data['total_count']} results instead."
        )


# =============================================================================
# Event Export Soft Delete Tests
# =============================================================================


class TestEventExportSoftDeleteFiltering:
    """Tests for soft delete filtering on event export endpoint."""

    @pytest.mark.asyncio
    async def test_export_events_excludes_soft_deleted(self, client, multiple_events_mixed):
        """GET /api/events/export should exclude soft-deleted events."""
        import csv
        import io

        _active_events, deleted_events = multiple_events_mixed

        response = await client.get("/api/events/export")
        assert response.status_code == 200

        content = response.content.decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Extract event IDs from CSV (first column after header)
        exported_ids = {int(row[0]) for row in rows[1:] if row}  # Skip header
        deleted_ids = {event.id for event in deleted_events}

        # Soft-deleted events should not be exported
        assert deleted_ids.isdisjoint(exported_ids), (
            f"Soft-deleted events should not be exported. "
            f"Found {deleted_ids.intersection(exported_ids)}"
        )


# =============================================================================
# Cross-Domain Soft Delete Tests
# =============================================================================


class TestCrossDomainSoftDeleteFiltering:
    """Tests for soft delete filtering across related entities."""

    @pytest.mark.asyncio
    async def test_events_from_soft_deleted_camera_excluded(self, client, soft_deleted_camera):
        """Events from a soft-deleted camera should be excluded from event lists.

        Even if the event itself is not soft-deleted, if its camera is soft-deleted,
        the event should not be returned (referential integrity).
        """
        # Create an active event linked to the soft-deleted camera
        async with get_session() as db:
            event = Event(
                batch_id=str(uuid.uuid4()),
                camera_id=soft_deleted_camera.id,
                started_at=datetime.now(UTC),
                risk_score=50,
                risk_level="medium",
                summary="Event on deleted camera",
                reviewed=False,
                deleted_at=None,  # Event itself is not deleted
            )
            db.add(event)
            await db.commit()
            await db.refresh(event)
            event_id = event.id

        response = await client.get("/api/events")
        assert response.status_code == 200
        data = response.json()

        returned_ids = {e["id"] for e in data["events"]}

        # This test documents expected behavior - events from deleted cameras
        # may or may not be filtered depending on implementation choice.
        # The assertion below expects them to be filtered:
        assert event_id not in returned_ids, (
            f"Events linked to soft-deleted cameras should be excluded. "
            f"Event {event_id} found in response."
        )

    @pytest.mark.asyncio
    async def test_list_cameras_count_excludes_soft_deleted(self, client, multiple_cameras_mixed):
        """Camera list count should not include soft-deleted cameras."""
        active_cameras, _deleted_cameras = multiple_cameras_mixed

        response = await client.get("/api/cameras")
        assert response.status_code == 200
        data = response.json()

        # Count should match number of active cameras only
        assert data["count"] == len(active_cameras), (
            f"Camera count ({data['count']}) should equal active cameras ({len(active_cameras)}). "
            f"Soft-deleted cameras should not be counted."
        )
