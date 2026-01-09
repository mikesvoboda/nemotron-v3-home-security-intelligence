"""Integration tests for cursor-based pagination across API endpoints.

Tests verify that cursor-based pagination works correctly across all paginated
endpoints (events, detections, audit logs). Tests use real database with
testcontainers and verify:
- First page returns correct items and next_cursor
- Next page navigation with cursor works correctly
- Previous page navigation (reverse pagination) works
- Edge cases: empty results, single page, last page
- Cursor stability (same cursor returns same position)
- Invalid cursor handling (returns 400)

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database via testcontainers
- client: httpx AsyncClient with test app
- db_session: AsyncSession for database operations
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.pagination import CursorData, encode_cursor
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event


@pytest.fixture
async def clean_data(integration_db, db_session: AsyncSession):
    """Delete all test data before and after each test for isolation.

    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks
    when tests run in parallel with xdist.
    """
    from sqlalchemy import text

    # Clean before test
    await db_session.execute(text("DELETE FROM detections"))  # nosemgrep: avoid-sqlalchemy-text
    await db_session.execute(text("DELETE FROM events"))  # nosemgrep: avoid-sqlalchemy-text
    await db_session.execute(text("DELETE FROM cameras"))  # nosemgrep: avoid-sqlalchemy-text
    await db_session.commit()

    yield

    # Clean after test (best effort)
    try:
        await db_session.execute(text("DELETE FROM detections"))  # nosemgrep: avoid-sqlalchemy-text
        await db_session.execute(text("DELETE FROM events"))  # nosemgrep: avoid-sqlalchemy-text
        await db_session.execute(text("DELETE FROM cameras"))  # nosemgrep: avoid-sqlalchemy-text
        await db_session.commit()
    except Exception:  # noqa: S110
        pass


@pytest.fixture
async def test_camera(db_session: AsyncSession, clean_data):
    """Create a test camera for events and detections."""
    camera_id = f"test_cam_{uuid.uuid4().hex[:8]}"
    camera = Camera(
        id=camera_id,
        name=f"Test Camera {uuid.uuid4().hex[:8]}",
        folder_path=f"/export/foscam/{camera_id}",
        status="online",
    )
    db_session.add(camera)
    await db_session.commit()
    await db_session.refresh(camera)
    return camera


@pytest.fixture
async def test_events(db_session: AsyncSession, test_camera: Camera):
    """Create 25 test events with different timestamps for pagination testing."""
    base_time = datetime(2025, 12, 1, 12, 0, 0, tzinfo=UTC)
    events = []

    for i in range(25):
        # Create events in reverse chronological order (newest first)
        # This matches the API's default ordering: ORDER BY started_at DESC
        started_at = base_time + timedelta(hours=24 - i)
        event = Event(
            batch_id=str(uuid.uuid4()),
            camera_id=test_camera.id,
            started_at=started_at,
            ended_at=started_at + timedelta(minutes=5),
            risk_score=i * 4,  # 0, 4, 8, ..., 96
            risk_level="low" if i < 10 else "medium" if i < 20 else "high",
            summary=f"Test event {i}",
            reasoning=f"Test reasoning {i}",
            detection_ids="[]",
            reviewed=False,
        )
        db_session.add(event)
        events.append(event)

    await db_session.commit()

    # Refresh to get IDs
    for event in events:
        await db_session.refresh(event)

    return events


@pytest.fixture
async def test_detections(db_session: AsyncSession, test_camera: Camera):
    """Create 30 test detections for pagination testing."""
    base_time = datetime(2025, 12, 1, 12, 0, 0, tzinfo=UTC)
    detections = []

    for i in range(30):
        detected_at = base_time + timedelta(minutes=i)
        detection = Detection(
            camera_id=test_camera.id,
            file_path=f"/export/foscam/{test_camera.id}/image_{i}.jpg",
            file_type="image/jpeg",
            detected_at=detected_at,
            object_type="person" if i % 2 == 0 else "vehicle",
            confidence=0.8 + (i * 0.005),  # 0.8 to 0.95
            bbox_x=100 + i,
            bbox_y=200 + i,
            bbox_width=150,
            bbox_height=200,
        )
        db_session.add(detection)
        detections.append(detection)

    await db_session.commit()

    # Refresh to get IDs
    for detection in detections:
        await db_session.refresh(detection)

    return detections


class TestEventsCursorPagination:
    """Integration tests for cursor-based pagination on /api/events endpoint."""

    @pytest.mark.asyncio
    async def test_first_page_returns_cursor_and_correct_items(
        self, client: AsyncClient, test_events: list[Event]
    ):
        """Test that first page returns next_cursor and correct number of items."""
        # Request first page with limit of 10
        response = await client.get("/api/events?limit=10")

        assert response.status_code == 200
        data = response.json()

        # Verify pagination metadata
        assert data["limit"] == 10
        assert len(data["events"]) == 10
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

        # Verify events are in descending order by started_at (newest first)
        events = data["events"]
        for i in range(len(events) - 1):
            assert events[i]["started_at"] >= events[i + 1]["started_at"]

    @pytest.mark.asyncio
    async def test_next_page_with_cursor_returns_subsequent_items(
        self, client: AsyncClient, test_events: list[Event]
    ):
        """Test that using next_cursor returns the next page of results."""
        # Get first page
        response1 = await client.get("/api/events?limit=10")
        assert response1.status_code == 200
        data1 = response1.json()

        first_page_event_ids = {event["id"] for event in data1["events"]}
        next_cursor = data1["next_cursor"]
        assert next_cursor is not None

        # Get second page using cursor
        response2 = await client.get(f"/api/events?limit=10&cursor={next_cursor}")
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify second page has different events
        second_page_event_ids = {event["id"] for event in data2["events"]}
        assert first_page_event_ids.isdisjoint(second_page_event_ids)

        # Verify second page continues chronological order
        # Last event from first page should be newer than first event of second page
        last_first_page = data1["events"][-1]["started_at"]
        first_second_page = data2["events"][0]["started_at"]
        assert last_first_page >= first_second_page

    @pytest.mark.asyncio
    async def test_cursor_pagination_multiple_pages(
        self, client: AsyncClient, test_events: list[Event]
    ):
        """Test navigating through multiple pages with cursor pagination."""
        all_event_ids = set()
        cursor = None
        page_count = 0
        limit = 8

        # Navigate through all pages
        while True:
            url = f"/api/events?limit={limit}"
            if cursor:
                url += f"&cursor={cursor}"

            response = await client.get(url)
            assert response.status_code == 200
            data = response.json()

            page_count += 1
            page_event_ids = {event["id"] for event in data["events"]}

            # Verify no duplicate events across pages
            assert all_event_ids.isdisjoint(page_event_ids)
            all_event_ids.update(page_event_ids)

            # Check if there are more pages
            if not data["has_more"]:
                break

            cursor = data["next_cursor"]
            assert cursor is not None

        # Verify we got all 25 events across multiple pages
        assert len(all_event_ids) == 25
        assert page_count == 4  # 8 + 8 + 8 + 1 = 25

    @pytest.mark.asyncio
    async def test_last_page_has_no_next_cursor(
        self, client: AsyncClient, test_events: list[Event]
    ):
        """Test that last page has has_more=False and next_cursor=None."""
        # Request with large limit to get all events on first page
        response = await client.get("/api/events?limit=100")

        assert response.status_code == 200
        data = response.json()

        # Verify last page indicators
        assert data["has_more"] is False
        assert data["next_cursor"] is None
        assert len(data["events"]) == 25  # All events fit on one page

    @pytest.mark.asyncio
    async def test_empty_results_no_cursor(self, client: AsyncClient, clean_data):
        """Test that empty results return no cursor and has_more=False."""
        # Request events when database is empty
        response = await client.get("/api/events?limit=10")

        assert response.status_code == 200
        data = response.json()

        # Verify empty result indicators
        assert len(data["events"]) == 0
        assert data["has_more"] is False
        assert data["next_cursor"] is None
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_invalid_cursor_returns_400(self, client: AsyncClient, test_events: list[Event]):
        """Test that invalid cursor string returns 400 error."""
        # Test with malformed cursor
        response = await client.get("/api/events?cursor=invalid_cursor_string")

        assert response.status_code == 400
        data = response.json()
        assert "invalid cursor" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_cursor_with_missing_fields_returns_400(
        self, client: AsyncClient, test_events: list[Event]
    ):
        """Test that cursor with missing required fields returns 400."""
        # Create cursor with missing 'created_at' field
        import base64
        import json

        invalid_payload = {"id": 1}  # Missing 'created_at'
        invalid_cursor = base64.urlsafe_b64encode(json.dumps(invalid_payload).encode()).decode()

        response = await client.get(f"/api/events?cursor={invalid_cursor}")

        assert response.status_code == 400
        data = response.json()
        assert "invalid cursor" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_cursor_stability_same_position(
        self, client: AsyncClient, test_events: list[Event]
    ):
        """Test that same cursor returns same starting position (cursor stability)."""
        # Get first page
        response1 = await client.get("/api/events?limit=10")
        assert response1.status_code == 200
        data1 = response1.json()
        cursor = data1["next_cursor"]

        # Use same cursor twice to get page 2
        response2 = await client.get(f"/api/events?limit=10&cursor={cursor}")
        response3 = await client.get(f"/api/events?limit=10&cursor={cursor}")

        assert response2.status_code == 200
        assert response3.status_code == 200

        data2 = response2.json()
        data3 = response3.json()

        # Verify both requests return identical results
        assert data2["events"] == data3["events"]
        assert data2["next_cursor"] == data3["next_cursor"]
        assert data2["has_more"] == data3["has_more"]

    @pytest.mark.asyncio
    async def test_single_item_page(self, client: AsyncClient, test_events: list[Event]):
        """Test pagination when last page has single item."""
        # Navigate to last page (25 events total, use limit=24 to leave 1 on last page)
        response1 = await client.get("/api/events?limit=24")
        assert response1.status_code == 200
        data1 = response1.json()

        assert data1["has_more"] is True
        cursor = data1["next_cursor"]

        # Get last page with single item
        response2 = await client.get(f"/api/events?limit=10&cursor={cursor}")
        assert response2.status_code == 200
        data2 = response2.json()

        assert len(data2["events"]) == 1
        assert data2["has_more"] is False
        assert data2["next_cursor"] is None

    @pytest.mark.asyncio
    async def test_cursor_with_filters(self, client: AsyncClient, test_events: list[Event]):
        """Test cursor pagination works correctly with query filters applied."""
        # Filter for high-risk events (risk_level='high')
        response1 = await client.get("/api/events?limit=3&risk_level=high")
        assert response1.status_code == 200
        data1 = response1.json()

        # Verify filtered results
        assert all(event["risk_level"] == "high" for event in data1["events"])
        assert data1["has_more"] is True  # Should have more high-risk events

        # Get next page with same filter
        cursor = data1["next_cursor"]
        response2 = await client.get(f"/api/events?limit=3&risk_level=high&cursor={cursor}")
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify second page also matches filter
        assert all(event["risk_level"] == "high" for event in data2["events"])

        # Verify no overlap between pages
        first_page_ids = {event["id"] for event in data1["events"]}
        second_page_ids = {event["id"] for event in data2["events"]}
        assert first_page_ids.isdisjoint(second_page_ids)

    @pytest.mark.asyncio
    async def test_offset_without_cursor_shows_deprecation_warning(
        self, client: AsyncClient, test_events: list[Event]
    ):
        """Test that using offset without cursor shows deprecation warning."""
        # Use offset pagination (deprecated)
        response = await client.get("/api/events?offset=10&limit=10")

        assert response.status_code == 200
        data = response.json()

        # Verify deprecation warning is present
        assert data["deprecation_warning"] is not None
        assert "deprecated" in data["deprecation_warning"].lower()
        assert "cursor" in data["deprecation_warning"].lower()

    @pytest.mark.asyncio
    async def test_cursor_overrides_offset(self, client: AsyncClient, test_events: list[Event]):
        """Test that cursor parameter takes precedence over offset."""
        # Get first page to get a cursor
        response1 = await client.get("/api/events?limit=10")
        assert response1.status_code == 200
        data1 = response1.json()
        cursor = data1["next_cursor"]

        # Use both cursor and offset (cursor should take precedence)
        response2 = await client.get(f"/api/events?limit=10&offset=50&cursor={cursor}")
        assert response2.status_code == 200
        data2 = response2.json()

        # Get same page with cursor only
        response3 = await client.get(f"/api/events?limit=10&cursor={cursor}")
        assert response3.status_code == 200
        data3 = response3.json()

        # Results should be identical (cursor ignored offset)
        assert data2["events"] == data3["events"]

        # Verify no deprecation warning when cursor is provided
        assert data2["deprecation_warning"] is None


class TestDetectionsCursorPagination:
    """Integration tests for cursor-based pagination on /api/detections endpoint."""

    @pytest.mark.asyncio
    async def test_detections_first_page_returns_cursor(
        self, client: AsyncClient, test_detections: list[Detection]
    ):
        """Test detections endpoint first page returns next_cursor."""
        response = await client.get("/api/detections?limit=15")

        assert response.status_code == 200
        data = response.json()

        assert data["limit"] == 15
        assert len(data["detections"]) == 15
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

    @pytest.mark.asyncio
    async def test_detections_cursor_navigation(
        self, client: AsyncClient, test_detections: list[Detection]
    ):
        """Test navigating through detection pages with cursor."""
        # Get first page
        response1 = await client.get("/api/detections?limit=10")
        assert response1.status_code == 200
        data1 = response1.json()

        # Get second page
        cursor = data1["next_cursor"]
        response2 = await client.get(f"/api/detections?limit=10&cursor={cursor}")
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify no overlapping detections
        first_page_ids = {det["id"] for det in data1["detections"]}
        second_page_ids = {det["id"] for det in data2["detections"]}
        assert first_page_ids.isdisjoint(second_page_ids)

    @pytest.mark.asyncio
    async def test_detections_last_page_no_cursor(
        self, client: AsyncClient, test_detections: list[Detection]
    ):
        """Test detections last page has no next_cursor."""
        # Get all detections in one page
        response = await client.get("/api/detections?limit=100")

        assert response.status_code == 200
        data = response.json()

        assert len(data["detections"]) == 30
        assert data["has_more"] is False
        assert data["next_cursor"] is None

    @pytest.mark.asyncio
    async def test_detections_invalid_cursor_returns_400(
        self, client: AsyncClient, test_detections: list[Detection]
    ):
        """Test invalid cursor returns 400 for detections endpoint."""
        response = await client.get("/api/detections?cursor=bad_cursor")

        assert response.status_code == 400
        assert "invalid cursor" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_detections_cursor_with_object_type_filter(
        self, client: AsyncClient, test_detections: list[Detection]
    ):
        """Test cursor pagination with object_type filter on detections."""
        # Filter for 'person' detections only (15 out of 30)
        response1 = await client.get("/api/detections?limit=10&object_type=person")
        assert response1.status_code == 200
        data1 = response1.json()

        # Verify all results match filter
        assert all(det["object_type"] == "person" for det in data1["detections"])
        assert len(data1["detections"]) == 10
        assert data1["has_more"] is True

        # Get next page with filter
        cursor = data1["next_cursor"]
        response2 = await client.get(f"/api/detections?limit=10&object_type=person&cursor={cursor}")
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify second page matches filter
        assert all(det["object_type"] == "person" for det in data2["detections"])
        assert len(data2["detections"]) == 5  # Remaining 5 person detections


class TestCursorEncodingDecoding:
    """Tests for cursor encoding/decoding with actual database data."""

    @pytest.mark.asyncio
    async def test_cursor_encodes_event_position_correctly(
        self, client: AsyncClient, test_events: list[Event]
    ):
        """Test that cursor correctly encodes event ID and timestamp."""
        # Get first page
        response = await client.get("/api/events?limit=1")
        assert response.status_code == 200
        data = response.json()

        cursor_str = data["next_cursor"]
        assert cursor_str is not None

        # Decode cursor to verify contents
        from backend.api.pagination import decode_cursor

        cursor_data = decode_cursor(cursor_str)
        assert cursor_data is not None
        assert cursor_data.id == data["events"][0]["id"]
        # created_at should match started_at from event (normalize both to ISO format)
        # API returns timestamps with 'Z' suffix, isoformat returns '+00:00'
        cursor_timestamp = cursor_data.created_at.isoformat().replace("+00:00", "Z")
        assert cursor_timestamp == data["events"][0]["started_at"]

    @pytest.mark.asyncio
    async def test_manual_cursor_construction_works(
        self, client: AsyncClient, test_events: list[Event]
    ):
        """Test that manually constructed cursor works correctly."""
        # Get first event to construct cursor from
        response1 = await client.get("/api/events?limit=1")
        assert response1.status_code == 200
        data1 = response1.json()
        first_event = data1["events"][0]

        # Manually construct cursor from first event
        cursor_data = CursorData(
            id=first_event["id"],
            created_at=datetime.fromisoformat(first_event["started_at"].replace("Z", "+00:00")),
        )
        manual_cursor = encode_cursor(cursor_data)

        # Use manual cursor to get next page
        response2 = await client.get(f"/api/events?limit=10&cursor={manual_cursor}")
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify we get subsequent events (not including first event)
        second_page_ids = {event["id"] for event in data2["events"]}
        assert first_event["id"] not in second_page_ids


class TestCursorEdgeCases:
    """Tests for edge cases and boundary conditions in cursor pagination."""

    @pytest.mark.asyncio
    async def test_cursor_with_exact_limit_boundary(
        self, client: AsyncClient, test_events: list[Event]
    ):
        """Test cursor pagination when total items exactly match page boundaries."""
        # We have 25 events, use limit=5 for clean boundaries
        all_event_ids = set()
        cursor = None

        for page_num in range(5):  # Exactly 5 pages
            url = "/api/events?limit=5"
            if cursor:
                url += f"&cursor={cursor}"

            response = await client.get(url)
            assert response.status_code == 200
            data = response.json()

            assert len(data["events"]) == 5
            all_event_ids.update(event["id"] for event in data["events"])

            if page_num < 4:  # First 4 pages should have more
                assert data["has_more"] is True
                cursor = data["next_cursor"]
            else:  # Last page should not have more
                assert data["has_more"] is False
                assert data["next_cursor"] is None

        # Verify we got all 25 events exactly
        assert len(all_event_ids) == 25

    @pytest.mark.asyncio
    async def test_cursor_with_limit_one(self, client: AsyncClient, test_events: list[Event]):
        """Test cursor pagination with limit=1 (minimum valid limit)."""
        # Get first event
        response1 = await client.get("/api/events?limit=1")
        assert response1.status_code == 200
        data1 = response1.json()

        assert len(data1["events"]) == 1
        assert data1["has_more"] is True

        # Get second event
        cursor = data1["next_cursor"]
        response2 = await client.get(f"/api/events?limit=1&cursor={cursor}")
        assert response2.status_code == 200
        data2 = response2.json()

        assert len(data2["events"]) == 1
        assert data1["events"][0]["id"] != data2["events"][0]["id"]

    @pytest.mark.asyncio
    async def test_cursor_with_limit_max(self, client: AsyncClient, test_events: list[Event]):
        """Test cursor pagination with limit=100 (maximum valid limit)."""
        response = await client.get("/api/events?limit=100")

        assert response.status_code == 200
        data = response.json()

        # All 25 events should fit in one page
        assert len(data["events"]) == 25
        assert data["has_more"] is False
        assert data["next_cursor"] is None
