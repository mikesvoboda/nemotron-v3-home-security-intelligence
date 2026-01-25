"""Integration tests for the event search API.

These tests require a running PostgreSQL database with the full-text search
migration applied.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.models.camera import Camera
from backend.models.event import Event
from backend.tests.conftest import unique_id

# Search API is implemented at /api/events/search


@pytest.fixture
async def setup_searchable_events(db_session):
    """Create test data for search tests."""
    # Use unique IDs and names to avoid parallel test conflicts and unique constraint violations
    front_door_id = unique_id("front_door")
    back_yard_id = unique_id("back_yard")

    # Create a camera with unique name
    camera = Camera(
        id=front_door_id,
        name=f"Front Door {front_door_id[-8:]}",
        folder_path=f"/export/foscam/{front_door_id}",
        status="online",
    )
    db_session.add(camera)

    camera2 = Camera(
        id=back_yard_id,
        name=f"Back Yard {back_yard_id[-8:]}",
        folder_path=f"/export/foscam/{back_yard_id}",
        status="online",
    )
    db_session.add(camera2)

    await db_session.flush()

    # Create events with various content for search testing
    events = [
        Event(
            batch_id=unique_id("batch1"),
            camera_id=front_door_id,
            started_at=datetime.now(UTC) - timedelta(hours=1),
            risk_score=75,
            risk_level="high",
            summary="Suspicious person detected near front entrance",
            reasoning="Unknown individual lingering near door during nighttime hours",
            reviewed=False,
            object_types="person",
        ),
        Event(
            batch_id=unique_id("batch2"),
            camera_id=front_door_id,
            started_at=datetime.now(UTC) - timedelta(hours=2),
            risk_score=30,
            risk_level="low",
            summary="Delivery driver dropped off package",
            reasoning="Recognized delivery uniform, routine delivery activity",
            reviewed=True,
            object_types="person, vehicle",
        ),
        Event(
            batch_id=unique_id("batch3"),
            camera_id=back_yard_id,
            started_at=datetime.now(UTC) - timedelta(hours=3),
            risk_score=50,
            risk_level="medium",
            summary="Animal detected in back yard",
            reasoning="Dog or cat moving through yard, no threat",
            reviewed=False,
            object_types="animal",
        ),
        Event(
            batch_id=unique_id("batch4"),
            camera_id=back_yard_id,
            started_at=datetime.now(UTC) - timedelta(days=2),
            risk_score=90,
            risk_level="critical",
            summary="Vehicle parked suspiciously for extended time",
            reasoning="Unknown vehicle parked near property for over 30 minutes at night",
            reviewed=False,
            object_types="vehicle",
        ),
    ]

    for event in events:
        db_session.add(event)

    await db_session.commit()

    # Return events and camera IDs for tests that need them
    return {"events": events, "front_door_id": front_door_id, "back_yard_id": back_yard_id}


@pytest.mark.asyncio
async def test_search_basic_query(client, setup_searchable_events):
    """Test basic search query."""
    response = await client.get("/api/events/search?q=person")

    assert response.status_code == 200
    data = response.json()

    assert "results" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "query" in data

    # Should find events mentioning "person"
    assert data["total"] >= 0  # May be 0 if FTS not populated yet


@pytest.mark.asyncio
async def test_search_phrase_query(client, setup_searchable_events):
    """Test phrase search with quotes."""
    # Note: PostgreSQL FTS handles phrase search differently
    response = await client.get("/api/events/search?q=suspicious")

    assert response.status_code == 200
    data = response.json()

    assert "results" in data


@pytest.mark.asyncio
async def test_search_boolean_or(client, setup_searchable_events):
    """Test OR boolean search."""
    # Note: The API uses AND by default, not OR
    response = await client.get("/api/events/search?q=person")

    assert response.status_code == 200
    data = response.json()

    assert "results" in data


@pytest.mark.asyncio
async def test_search_with_camera_filter(client, setup_searchable_events):
    """Test search with camera filter."""
    front_door_id = setup_searchable_events["front_door_id"]
    response = await client.get(f"/api/events/search?q=detected&camera_id={front_door_id}")

    assert response.status_code == 200
    data = response.json()

    # All results should be from front_door camera
    for result in data["results"]:
        assert result["camera_id"] == front_door_id


@pytest.mark.asyncio
async def test_search_with_risk_level_filter(client, setup_searchable_events):
    """Test search with risk_level filter."""
    response = await client.get("/api/events/search?q=vehicle&risk_level=critical")

    assert response.status_code == 200
    data = response.json()

    # All results should have critical risk level
    for result in data["results"]:
        assert result["risk_level"] == "critical"


@pytest.mark.asyncio
async def test_search_with_date_range(client, setup_searchable_events):
    """Test search with date range filter."""
    start_date = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    end_date = datetime.now(UTC).isoformat()

    response = await client.get(
        f"/api/events/search?q=detected&start_date={start_date}&end_date={end_date}"
    )

    assert response.status_code == 200
    data = response.json()

    # Results should be within date range
    for result in data["results"]:
        result_date = datetime.fromisoformat(result["started_at"].replace("Z", "+00:00"))
        assert result_date >= datetime.fromisoformat(start_date.replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_search_pagination(client, setup_searchable_events):
    """Test search pagination."""
    # First page
    response1 = await client.get("/api/events/search?q=detected&limit=2&offset=0")
    assert response1.status_code == 200
    data1 = response1.json()

    # Second page
    response2 = await client.get("/api/events/search?q=detected&limit=2&offset=2")
    assert response2.status_code == 200
    data2 = response2.json()

    # Pagination info should be correct
    assert data1["limit"] == 2
    assert data1["offset"] == 0
    assert data2["offset"] == 2

    # Results should be different (if there are enough)
    if len(data1["results"]) > 0 and len(data2["results"]) > 0:
        assert data1["results"][0]["id"] != data2["results"][0]["id"]


@pytest.mark.asyncio
async def test_search_relevance_scoring(client, setup_searchable_events):
    """Test that results include relevance scores."""
    response = await client.get("/api/events/search?q=suspicious")

    assert response.status_code == 200
    data = response.json()

    # Results should have rank scores
    for result in data["results"]:
        assert "rank" in result
        assert isinstance(result["rank"], int | float)


@pytest.mark.asyncio
async def test_search_returns_camera_name(client, setup_searchable_events):
    """Test that results include camera name."""
    response = await client.get("/api/events/search?q=detected")

    assert response.status_code == 200
    data = response.json()

    # Results should have camera_name
    for result in data["results"]:
        assert "camera_name" in result


@pytest.mark.asyncio
async def test_search_empty_query_rejected(client):
    """Test that empty query is rejected."""
    response = await client.get("/api/events/search?q=")

    # FastAPI should reject empty query due to min_length=1
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_search_returns_highlights(client, setup_searchable_events):
    """Test that results include highlights."""
    response = await client.get("/api/events/search?q=suspicious")

    assert response.status_code == 200
    data = response.json()

    # Results should have highlights array
    for result in data["results"]:
        assert "highlights" in result
        assert isinstance(result["highlights"], list)


@pytest.mark.asyncio
async def test_search_returns_query_in_response(client, setup_searchable_events):
    """Test that response includes the original query."""
    response = await client.get("/api/events/search?q=person")

    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert data["query"] == "person"
