"""Integration tests for admin API endpoints (development seed data).

NOTE: These tests use serial execution because admin seed operations
manipulate global database state with fixed sample camera IDs.
Parallel execution would cause race conditions.

NOTE: Admin endpoints are always accessible (no authentication required
for local deployment - this is a single-user local deployment).
"""

import os

import pytest
from sqlalchemy import select

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.tests.integration.test_helpers import get_error_message

# Mark all tests in this module for serial execution to avoid parallel conflicts
# Admin seed tests use fixed camera IDs and DELETE operations that affect global state
# Using xdist_group ensures all tests in this module run on the same worker sequentially
# Mark as integration since these tests require real database (integration_db fixture)
pytestmark = [
    pytest.mark.serial,
    pytest.mark.xdist_group(name="admin_seed"),
    pytest.mark.integration,
]


@pytest.fixture
async def debug_client(integration_db, mock_redis):
    """Async HTTP client with DEBUG=true and ADMIN_ENABLED=true for admin tests.

    This fixture creates an HTTP client with admin access enabled, eliminating
    the need for context managers or try/finally blocks in each test.
    """
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    from backend.core.config import Settings, get_settings

    # Create settings with debug and admin enabled
    debug_settings = Settings(
        debug=True,
        admin_enabled=True,
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )

    # Import the app only after env is set up
    from backend.main import app

    with (
        patch("backend.main.init_db", return_value=None),
        patch("backend.main.close_db", return_value=None),
        patch("backend.main.init_redis", return_value=mock_redis),
        patch("backend.main.close_redis", return_value=None),
        patch("backend.core.config.get_settings", return_value=debug_settings),
        patch("backend.api.routes.admin.get_settings", return_value=debug_settings),
    ):
        get_settings.cache_clear()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        get_settings.cache_clear()


@pytest.fixture
async def clean_seed_data(integration_db):
    """Clean up ALL data before/after each test for proper isolation.

    Admin seed tests need a clean database because:
    1. API endpoints query/clear ALL cameras, not just specific IDs
    2. Tests make exact count assertions (e.g., "created == 3")

    Uses an advisory lock to coordinate with other tests that might
    be creating data in parallel, ensuring these tests see a clean slate.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    engine = get_engine()

    async def _delete_all_data():
        """Delete all test data in a separate connection/transaction."""
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM detections"))
            await conn.execute(text("DELETE FROM events"))
            await conn.execute(text("DELETE FROM cameras"))

    # Acquire exclusive advisory lock for admin seed operations
    async with engine.connect() as lock_conn:
        await lock_conn.execute(text("SELECT pg_advisory_lock(777777)"))
        try:
            # Delete all data before test
            await _delete_all_data()

            yield

            # Cleanup after test
            await _delete_all_data()
        finally:
            await lock_conn.execute(text("SELECT pg_advisory_unlock(777777)"))
            await lock_conn.commit()  # Commit to release the lock properly


# === Seed Cameras Tests (with full admin access) ===


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_cameras_success(debug_client, clean_seed_data):
    """Test successful camera seeding with full admin access."""
    response = await debug_client.post("/api/admin/seed/cameras", json={"count": 3})

    assert response.status_code == 201
    data = response.json()
    assert data["created"] == 3
    assert data["cleared"] == 0
    assert len(data["cameras"]) == 3

    # Verify camera IDs match expected sample cameras
    camera_ids = [c["id"] for c in data["cameras"]]
    assert "front-door" in camera_ids
    assert "backyard" in camera_ids
    assert "garage" in camera_ids


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_cameras_clear_existing(debug_client, clean_seed_data):
    """Test seeding cameras with clear_existing=true."""
    # First seed some cameras
    await debug_client.post("/api/admin/seed/cameras", json={"count": 2})

    # Verify they exist
    list_response = await debug_client.get("/api/cameras")
    assert list_response.json()["pagination"]["total"] == 2

    # Seed again with clear_existing=true
    response = await debug_client.post(
        "/api/admin/seed/cameras",
        json={"count": 4, "clear_existing": True},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["cleared"] == 2
    assert data["created"] == 4
    assert len(data["cameras"]) == 4


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_cameras_skips_existing(debug_client, clean_seed_data):
    """Test that seeding skips cameras that already exist."""
    # First seed 3 cameras
    response1 = await debug_client.post("/api/admin/seed/cameras", json={"count": 3})
    assert response1.json()["created"] == 3

    # Try to seed 5 cameras (should skip existing 3, create remaining 2)
    response2 = await debug_client.post("/api/admin/seed/cameras", json={"count": 5})

    assert response2.status_code == 201
    data = response2.json()
    assert data["created"] == 2  # Only 2 new cameras created
    assert data["cleared"] == 0

    # Verify total is 5
    list_response = await debug_client.get("/api/cameras")
    assert list_response.json()["pagination"]["total"] == 5


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_cameras_max_count(debug_client, clean_seed_data):
    """Test seeding the maximum number of cameras."""
    response = await debug_client.post("/api/admin/seed/cameras", json={"count": 6})

    assert response.status_code == 201
    data = response.json()
    assert data["created"] == 6
    assert len(data["cameras"]) == 6


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_cameras_count_validation(debug_client):
    """Test camera count validation."""
    # Count too low
    response = await debug_client.post("/api/admin/seed/cameras", json={"count": 0})
    assert response.status_code == 422

    # Count too high
    response = await debug_client.post("/api/admin/seed/cameras", json={"count": 7})
    assert response.status_code == 422


# === Seed Events Tests ===


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_events_success(debug_client, clean_seed_data):
    """Test successful event seeding."""
    # First seed cameras (required for events)
    await debug_client.post("/api/admin/seed/cameras", json={"count": 3})

    # Seed events
    response = await debug_client.post("/api/admin/seed/events", json={"count": 10})

    assert response.status_code == 201
    data = response.json()
    assert data["events_created"] == 10
    assert data["detections_created"] > 0  # At least 1 detection per event
    assert data["events_cleared"] == 0
    assert data["detections_cleared"] == 0


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_events_requires_cameras(debug_client, clean_seed_data):
    """Test that seeding events requires cameras to exist."""
    # Try to seed events without cameras (clean_seed_data ensures no cameras exist)
    response = await debug_client.post("/api/admin/seed/events", json={"count": 5})

    assert response.status_code == 400
    assert "No cameras found" in get_error_message(response.json())


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_events_clear_existing(debug_client, clean_seed_data):
    """Test seeding events with clear_existing=true."""
    # Seed cameras and events (clean_seed_data ensures we start fresh)
    await debug_client.post("/api/admin/seed/cameras", json={"count": 2})
    await debug_client.post("/api/admin/seed/events", json={"count": 5})

    # Seed more events with clear_existing=true
    response = await debug_client.post(
        "/api/admin/seed/events",
        json={"count": 3, "clear_existing": True},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["events_created"] == 3
    assert data["events_cleared"] == 5  # Previous events cleared
    assert data["detections_cleared"] > 0  # Previous detections cleared


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_events_creates_detections(debug_client, clean_seed_data):
    """Test that seeding events also creates associated detections."""
    from backend.core.database import get_session

    # Seed cameras and events (clean_seed_data ensures we start fresh)
    await debug_client.post("/api/admin/seed/cameras", json={"count": 2})
    response = await debug_client.post("/api/admin/seed/events", json={"count": 5})

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

        # Verify events have linked detections via junction table
        for event in events:
            await session.refresh(event, ["detections"])
            assert len(event.detection_id_list) > 0


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_events_risk_levels(debug_client, clean_seed_data):
    """Test that seeded events have varied risk levels."""
    from backend.core.database import get_session

    # Seed cameras and a decent number of events (clean_seed_data ensures fresh start)
    await debug_client.post("/api/admin/seed/cameras", json={"count": 3})
    await debug_client.post("/api/admin/seed/events", json={"count": 50})

    # Check risk level distribution
    async with get_session() as session:
        result = await session.execute(select(Event))
        events = result.scalars().all()

        risk_levels = {e.risk_level for e in events}
        # With 50 events, we should have at least 2 different risk levels
        assert len(risk_levels) >= 2


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_events_count_validation(debug_client):
    """Test event count validation."""
    # Count too low
    response = await debug_client.post("/api/admin/seed/events", json={"count": 0})
    assert response.status_code == 422

    # Count too high
    response = await debug_client.post("/api/admin/seed/events", json={"count": 101})
    assert response.status_code == 422


# === Clear Data Tests ===


@pytest.mark.asyncio
@pytest.mark.slow
async def test_clear_data_success(debug_client, clean_seed_data):
    """Test clearing all seeded data with confirmation."""
    # Seed cameras and events (clean_seed_data ensures we start fresh)
    await debug_client.post("/api/admin/seed/cameras", json={"count": 4})
    await debug_client.post("/api/admin/seed/events", json={"count": 10})

    # Clear all data with confirmation body
    response = await debug_client.request(
        "DELETE",
        "/api/admin/seed/clear",
        json={"confirm": "DELETE_ALL_DATA"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["cameras_cleared"] == 4
    assert data["events_cleared"] == 10
    assert data["detections_cleared"] > 0

    # Verify data is gone
    cameras_response = await debug_client.get("/api/cameras")
    assert cameras_response.json()["pagination"]["total"] == 0


@pytest.mark.asyncio
@pytest.mark.slow
async def test_clear_data_empty_database(debug_client, clean_seed_data):
    """Test clearing when database is already empty with confirmation."""
    # clean_seed_data ensures we start with an empty database
    response = await debug_client.request(
        "DELETE",
        "/api/admin/seed/clear",
        json={"confirm": "DELETE_ALL_DATA"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["cameras_cleared"] == 0
    assert data["events_cleared"] == 0
    assert data["detections_cleared"] == 0


@pytest.mark.asyncio
@pytest.mark.slow
async def test_clear_data_requires_confirmation(debug_client, clean_seed_data):
    """Test that clear data endpoint requires explicit confirmation."""
    # Seed some data first
    await debug_client.post("/api/admin/seed/cameras", json={"count": 2})

    # Try to clear with wrong confirmation string
    response = await debug_client.request(
        "DELETE",
        "/api/admin/seed/clear",
        json={"confirm": "wrong_string"},
    )

    assert response.status_code == 400
    assert "Confirmation required" in get_error_message(response.json())

    # Verify data is NOT deleted
    cameras_response = await debug_client.get("/api/cameras")
    assert cameras_response.json()["pagination"]["total"] == 2


@pytest.mark.asyncio
@pytest.mark.slow
async def test_clear_data_missing_confirmation(debug_client, clean_seed_data):
    """Test that clear data returns 422 when confirm field is not provided."""
    # Seed some data first
    await debug_client.post("/api/admin/seed/cameras", json={"count": 2})

    # Try to clear without providing confirm field in body
    response = await debug_client.request(
        "DELETE",
        "/api/admin/seed/clear",
        json={},
    )

    # Missing required field returns 422 Unprocessable Entity
    assert response.status_code == 422

    # Verify data is NOT deleted
    cameras_response = await debug_client.get("/api/cameras")
    assert cameras_response.json()["pagination"]["total"] == 2


# === Edge Cases ===


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_cameras_default_values(debug_client, clean_seed_data):
    """Test seeding cameras with default values."""
    # POST with empty body uses defaults (clean_seed_data ensures no existing cameras)
    response = await debug_client.post("/api/admin/seed/cameras", json={})

    assert response.status_code == 201
    data = response.json()
    assert data["created"] == 6  # Default count
    assert data["cleared"] == 0  # Default clear_existing=false


@pytest.mark.asyncio
@pytest.mark.slow
async def test_seed_events_default_values(debug_client, clean_seed_data):
    """Test seeding events with default values."""
    # First seed cameras (clean_seed_data ensures fresh start)
    await debug_client.post("/api/admin/seed/cameras", json={"count": 2})

    # POST with empty body uses defaults
    response = await debug_client.post("/api/admin/seed/events", json={})

    assert response.status_code == 201
    data = response.json()
    assert data["events_created"] == 15  # Default count
    assert data["events_cleared"] == 0  # Default clear_existing=false


@pytest.mark.asyncio
@pytest.mark.slow
async def test_full_seed_workflow(debug_client, clean_seed_data):
    """Test complete seeding workflow: cameras -> events -> clear."""
    from backend.core.database import get_session

    # Step 1: Seed cameras (clean_seed_data ensures fresh start)
    cameras_response = await debug_client.post(
        "/api/admin/seed/cameras",
        json={"count": 3},
    )
    assert cameras_response.status_code == 201
    assert cameras_response.json()["created"] == 3

    # Step 2: Seed events
    events_response = await debug_client.post(
        "/api/admin/seed/events",
        json={"count": 8},
    )
    assert events_response.status_code == 201
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
    clear_response = await debug_client.request(
        "DELETE",
        "/api/admin/seed/clear",
        json={"confirm": "DELETE_ALL_DATA"},
    )
    assert clear_response.status_code == 200

    # Step 5: Verify data is cleared
    async with get_session() as session:
        cameras = (await session.execute(select(Camera))).scalars().all()
        events = (await session.execute(select(Event))).scalars().all()
        detections = (await session.execute(select(Detection))).scalars().all()

        assert len(cameras) == 0
        assert len(events) == 0
        assert len(detections) == 0


# === Security Tests ===


@pytest.mark.asyncio
@pytest.mark.requires_debug_mode
@pytest.mark.unit  # Override integration mark - this test doesn't need database
async def test_admin_endpoints_require_debug_mode(mock_redis, mock_db_session):
    """Test that admin endpoints return 403 when DEBUG=false or ADMIN_ENABLED=false.

    SECURITY: This test verifies defense-in-depth access control.
    Admin endpoints must have BOTH debug=True AND admin_enabled=True.
    This prevents accidental exposure in production environments.

    NOTE: This test doesn't need a real database because it patches init_db
    and overrides the database dependency with a mock session.
    It only needs to verify HTTP response codes from the admin endpoints.
    """
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    from backend.core.config import Settings
    from backend.core.database import get_db
    from backend.core.dependencies import get_redis_dependency

    # Test 1: DEBUG=false, ADMIN_ENABLED=true (should fail)
    production_settings = Settings(
        debug=False,
        admin_enabled=True,
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )

    from backend.main import app

    # Override redis dependency to return mock_redis
    async def mock_redis_dependency():
        yield mock_redis

    # Override database dependency to return mock_db_session
    async def mock_db_dependency():
        yield mock_db_session

    app.dependency_overrides[get_redis_dependency] = mock_redis_dependency
    app.dependency_overrides[get_db] = mock_db_dependency

    try:
        with (
            patch("backend.main.init_db", return_value=None),
            patch("backend.main.close_db", return_value=None),
            patch("backend.main.init_redis", return_value=mock_redis),
            patch("backend.main.close_redis", return_value=None),
            patch("backend.core.config.get_settings", return_value=production_settings),
            patch("backend.api.routes.admin.get_settings", return_value=production_settings),
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # All admin endpoints should return 403
                endpoints = [
                    ("POST", "/api/admin/seed/cameras", {"count": 1}),
                    ("POST", "/api/admin/seed/events", {"count": 1}),
                    ("DELETE", "/api/admin/seed/clear", {"confirm": "DELETE_ALL_DATA"}),
                    ("POST", "/api/admin/cleanup/orphans", {"dry_run": True}),
                    ("POST", "/api/admin/seed/pipeline-latency", {"num_samples": 10}),
                    ("POST", "/api/admin/maintenance/clear-cache", None),
                    ("POST", "/api/admin/maintenance/flush-queues", None),
                ]

                for method, endpoint, body in endpoints:
                    if body:
                        response = await client.request(method, endpoint, json=body)
                    else:
                        response = await client.request(method, endpoint)

                    assert response.status_code == 403, (
                        f"{method} {endpoint} should return 403 when DEBUG=false, "
                        f"but returned {response.status_code}"
                    )
                    assert "Admin endpoints require DEBUG=true" in response.json()["detail"]
            get_settings.cache_clear()

        # Test 2: DEBUG=true, ADMIN_ENABLED=false (should fail)
        no_admin_settings = Settings(
            debug=True,
            admin_enabled=False,
            database_url=os.environ.get("DATABASE_URL", ""),
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
        )

        with (
            patch("backend.main.init_db", return_value=None),
            patch("backend.main.close_db", return_value=None),
            patch("backend.main.init_redis", return_value=mock_redis),
            patch("backend.main.close_redis", return_value=None),
            patch("backend.core.config.get_settings", return_value=no_admin_settings),
            patch("backend.api.routes.admin.get_settings", return_value=no_admin_settings),
        ):
            from backend.core.config import get_settings

            get_settings.cache_clear()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # Test one endpoint to verify admin_enabled=false also blocks
                response = await client.post("/api/admin/seed/cameras", json={"count": 1})
                assert response.status_code == 403
                assert "Admin endpoints require DEBUG=true" in response.json()["detail"]
            get_settings.cache_clear()
    finally:
        # Clean up dependency overrides
        app.dependency_overrides.pop(get_redis_dependency, None)
        app.dependency_overrides.pop(get_db, None)
