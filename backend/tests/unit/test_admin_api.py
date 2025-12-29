"""Integration tests for admin API endpoints (development seed data).

NOTE: These tests use serial execution because admin seed operations
manipulate global database state with fixed sample camera IDs.
Parallel execution would cause race conditions.
"""

import os

import pytest
from sqlalchemy import delete, select

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event

# Mark all tests in this module for serial execution to avoid parallel conflicts
# Admin seed tests use fixed camera IDs and DELETE operations that affect global state
# Using xdist_group ensures all tests in this module run on the same worker sequentially
pytestmark = [pytest.mark.serial, pytest.mark.xdist_group(name="admin_seed")]


@pytest.fixture
async def clean_seed_data(integration_db):
    """Clean up seed data before each test for proper isolation.

    This fixture ensures tests start with a clean slate by deleting
    all cameras, events, and detections. Required because seed tests
    use fixed camera IDs that can conflict in parallel execution.

    Uses DELETE instead of TRUNCATE for better compatibility with
    the async session/connection model used by the API.
    """
    from backend.core.database import get_session

    async with get_session() as session:
        # Delete in order respecting FK constraints
        await session.execute(delete(Detection))
        await session.execute(delete(Event))
        await session.execute(delete(Camera))
        await session.commit()

    yield

    # Cleanup after test too
    async with get_session() as session:
        await session.execute(delete(Detection))
        await session.execute(delete(Event))
        await session.execute(delete(Camera))
        await session.commit()


# === DEBUG Mode Tests ===


@pytest.mark.asyncio
async def test_seed_cameras_requires_debug_mode(client):
    """Test that seed cameras endpoint requires DEBUG=true."""
    # Default is DEBUG=False
    response = await client.post("/api/admin/seed/cameras", json={"count": 2})

    assert response.status_code == 403
    assert "DEBUG=true" in response.json()["detail"]


@pytest.mark.asyncio
async def test_seed_events_requires_debug_mode(client):
    """Test that seed events endpoint requires DEBUG=true."""
    response = await client.post("/api/admin/seed/events", json={"count": 5})

    assert response.status_code == 403
    assert "DEBUG=true" in response.json()["detail"]


@pytest.mark.asyncio
async def test_clear_data_requires_debug_mode(client):
    """Test that clear data endpoint requires DEBUG=true."""
    response = await client.delete("/api/admin/seed/clear")

    assert response.status_code == 403
    assert "DEBUG=true" in response.json()["detail"]


# === Seed Cameras Tests (with DEBUG=true) ===


@pytest.mark.asyncio
async def test_seed_cameras_success(client, clean_seed_data):
    """Test successful camera seeding with DEBUG=true."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        response = await client.post("/api/admin/seed/cameras", json={"count": 3})

        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 3
        assert data["cleared"] == 0
        assert len(data["cameras"]) == 3

        # Verify camera IDs match expected sample cameras
        camera_ids = [c["id"] for c in data["cameras"]]
        assert "front-door" in camera_ids
        assert "backyard" in camera_ids
        assert "garage" in camera_ids
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_seed_cameras_clear_existing(client, clean_seed_data):
    """Test seeding cameras with clear_existing=true."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # First seed some cameras
        await client.post("/api/admin/seed/cameras", json={"count": 2})

        # Verify they exist
        list_response = await client.get("/api/cameras")
        assert list_response.json()["count"] == 2

        # Seed again with clear_existing=true
        response = await client.post(
            "/api/admin/seed/cameras",
            json={"count": 4, "clear_existing": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cleared"] == 2
        assert data["created"] == 4
        assert len(data["cameras"]) == 4
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_seed_cameras_skips_existing(client, clean_seed_data):
    """Test that seeding skips cameras that already exist."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # First seed 3 cameras
        response1 = await client.post("/api/admin/seed/cameras", json={"count": 3})
        assert response1.json()["created"] == 3

        # Try to seed 5 cameras (should skip existing 3, create remaining 2)
        response2 = await client.post("/api/admin/seed/cameras", json={"count": 5})

        assert response2.status_code == 200
        data = response2.json()
        assert data["created"] == 2  # Only 2 new cameras created
        assert data["cleared"] == 0

        # Verify total is 5
        list_response = await client.get("/api/cameras")
        assert list_response.json()["count"] == 5
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_seed_cameras_max_count(client, clean_seed_data):
    """Test seeding the maximum number of cameras."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        response = await client.post("/api/admin/seed/cameras", json={"count": 6})

        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 6
        assert len(data["cameras"]) == 6
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_seed_cameras_count_validation(client):
    """Test camera count validation."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # Count too low
        response = await client.post("/api/admin/seed/cameras", json={"count": 0})
        assert response.status_code == 422

        # Count too high
        response = await client.post("/api/admin/seed/cameras", json={"count": 7})
        assert response.status_code == 422
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


# === Seed Events Tests ===


@pytest.mark.asyncio
async def test_seed_events_success(client, clean_seed_data):
    """Test successful event seeding."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # First seed cameras (required for events)
        await client.post("/api/admin/seed/cameras", json={"count": 3})

        # Seed events
        response = await client.post("/api/admin/seed/events", json={"count": 10})

        assert response.status_code == 200
        data = response.json()
        assert data["events_created"] == 10
        assert data["detections_created"] > 0  # At least 1 detection per event
        assert data["events_cleared"] == 0
        assert data["detections_cleared"] == 0
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_seed_events_requires_cameras(client, clean_seed_data):
    """Test that seeding events requires cameras to exist."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # Try to seed events without cameras (clean_seed_data ensures no cameras exist)
        response = await client.post("/api/admin/seed/events", json={"count": 5})

        assert response.status_code == 400
        assert "No cameras found" in response.json()["detail"]
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_seed_events_clear_existing(client, clean_seed_data):
    """Test seeding events with clear_existing=true."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # Seed cameras and events (clean_seed_data ensures we start fresh)
        await client.post("/api/admin/seed/cameras", json={"count": 2})
        await client.post("/api/admin/seed/events", json={"count": 5})

        # Seed more events with clear_existing=true
        response = await client.post(
            "/api/admin/seed/events",
            json={"count": 3, "clear_existing": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["events_created"] == 3
        assert data["events_cleared"] == 5  # Previous events cleared
        assert data["detections_cleared"] > 0  # Previous detections cleared
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_seed_events_creates_detections(client, clean_seed_data):
    """Test that seeding events also creates associated detections."""
    from backend.core.config import get_settings
    from backend.core.database import get_session

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # Seed cameras and events (clean_seed_data ensures we start fresh)
        await client.post("/api/admin/seed/cameras", json={"count": 2})
        response = await client.post("/api/admin/seed/events", json={"count": 5})

        data = response.json()
        events_created = data["events_created"]
        detections_created = data["detections_created"]

        # Each event should have 1-5 detections
        assert detections_created >= events_created
        assert detections_created <= events_created * 5

        # Verify in database - count should match what we just created
        async with get_session() as session:
            events_result = await session.execute(select(Event))
            events = events_result.scalars().all()
            assert len(events) == 5

            detections_result = await session.execute(select(Detection))
            detections = detections_result.scalars().all()
            assert len(detections) == detections_created

            # Verify events have detection_ids
            for event in events:
                assert event.detection_ids is not None
                assert len(event.detection_ids) > 0
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_seed_events_risk_levels(client, clean_seed_data):
    """Test that seeded events have varied risk levels."""
    from backend.core.config import get_settings
    from backend.core.database import get_session

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # Seed cameras and a decent number of events (clean_seed_data ensures fresh start)
        await client.post("/api/admin/seed/cameras", json={"count": 3})
        await client.post("/api/admin/seed/events", json={"count": 50})

        # Check risk level distribution
        async with get_session() as session:
            result = await session.execute(select(Event))
            events = result.scalars().all()

            risk_levels = {e.risk_level for e in events}
            # With 50 events, we should have at least 2 different risk levels
            assert len(risk_levels) >= 2
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_seed_events_count_validation(client):
    """Test event count validation."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # Count too low
        response = await client.post("/api/admin/seed/events", json={"count": 0})
        assert response.status_code == 422

        # Count too high
        response = await client.post("/api/admin/seed/events", json={"count": 101})
        assert response.status_code == 422
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


# === Clear Data Tests ===


@pytest.mark.asyncio
async def test_clear_data_success(client, clean_seed_data):
    """Test clearing all seeded data."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # Seed cameras and events (clean_seed_data ensures we start fresh)
        await client.post("/api/admin/seed/cameras", json={"count": 4})
        await client.post("/api/admin/seed/events", json={"count": 10})

        # Clear all data
        response = await client.delete("/api/admin/seed/clear")

        assert response.status_code == 200
        data = response.json()
        assert data["cameras_cleared"] == 4
        assert data["events_cleared"] == 10
        assert data["detections_cleared"] > 0

        # Verify data is gone
        cameras_response = await client.get("/api/cameras")
        assert cameras_response.json()["count"] == 0
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_clear_data_empty_database(client, clean_seed_data):
    """Test clearing when database is already empty."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # clean_seed_data ensures we start with an empty database
        response = await client.delete("/api/admin/seed/clear")

        assert response.status_code == 200
        data = response.json()
        assert data["cameras_cleared"] == 0
        assert data["events_cleared"] == 0
        assert data["detections_cleared"] == 0
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


# === Edge Cases ===


@pytest.mark.asyncio
async def test_seed_cameras_default_values(client, clean_seed_data):
    """Test seeding cameras with default values."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # POST with empty body uses defaults (clean_seed_data ensures no existing cameras)
        response = await client.post("/api/admin/seed/cameras", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 6  # Default count
        assert data["cleared"] == 0  # Default clear_existing=false
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_seed_events_default_values(client, clean_seed_data):
    """Test seeding events with default values."""
    from backend.core.config import get_settings

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # First seed cameras (clean_seed_data ensures fresh start)
        await client.post("/api/admin/seed/cameras", json={"count": 2})

        # POST with empty body uses defaults
        response = await client.post("/api/admin/seed/events", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["events_created"] == 15  # Default count
        assert data["events_cleared"] == 0  # Default clear_existing=false
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_full_seed_workflow(client, clean_seed_data):
    """Test complete seeding workflow: cameras -> events -> clear."""
    from backend.core.config import get_settings
    from backend.core.database import get_session

    os.environ["DEBUG"] = "true"
    get_settings.cache_clear()

    try:
        # Step 1: Seed cameras (clean_seed_data ensures fresh start)
        cameras_response = await client.post(
            "/api/admin/seed/cameras",
            json={"count": 3},
        )
        assert cameras_response.status_code == 200
        assert cameras_response.json()["created"] == 3

        # Step 2: Seed events
        events_response = await client.post(
            "/api/admin/seed/events",
            json={"count": 8},
        )
        assert events_response.status_code == 200
        assert events_response.json()["events_created"] == 8

        # Step 3: Verify data exists
        async with get_session() as session:
            cameras = (await session.execute(select(Camera))).scalars().all()
            events = (await session.execute(select(Event))).scalars().all()
            detections = (await session.execute(select(Detection))).scalars().all()

            assert len(cameras) == 3
            assert len(events) == 8
            assert len(detections) > 0

        # Step 4: Clear all data
        clear_response = await client.delete("/api/admin/seed/clear")
        assert clear_response.status_code == 200

        # Step 5: Verify data is cleared
        async with get_session() as session:
            cameras = (await session.execute(select(Camera))).scalars().all()
            events = (await session.execute(select(Event))).scalars().all()
            detections = (await session.execute(select(Detection))).scalars().all()

            assert len(cameras) == 0
            assert len(events) == 0
            assert len(detections) == 0
    finally:
        os.environ.pop("DEBUG", None)
        get_settings.cache_clear()
