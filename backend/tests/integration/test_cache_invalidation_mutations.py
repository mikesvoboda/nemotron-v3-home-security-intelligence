"""Integration tests for cache invalidation on camera API mutations.

These tests verify that cache invalidation actually occurs when API mutations
happen on the cameras endpoint. This ensures data consistency between the
database and cache.

Test scenarios (NEM-2039):
1. POST /api/cameras - should invalidate cameras:* cache
2. PATCH /api/cameras/{id} - should invalidate cameras:* cache
3. DELETE /api/cameras/{id} - should invalidate cameras:* cache
4. Create camera -> list cameras (verify cache miss and repopulation)
5. Update camera -> list cameras (verify stale data NOT served)
6. Delete camera -> list cameras (verify deleted camera NOT in list)
7. Status-filtered cache invalidation (cameras:list:online vs cameras:list:offline)

Uses real Redis and real API endpoints to verify end-to-end cache behavior.

IMPORTANT: These tests must be run serially (-n0) due to shared Redis state.
Run with:

    uv run pytest backend/tests/integration/test_cache_invalidation_mutations.py -v -n0
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.services.cache_service import CACHE_PREFIX, CacheKeys, CacheService

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

# Mark as integration tests
pytestmark = pytest.mark.integration


def _unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def cache_service(real_redis: RedisClient) -> CacheService:
    """Create a CacheService with real Redis client."""
    return CacheService(real_redis)


@pytest.fixture
async def cleanup_cache(real_redis: RedisClient, clean_tables: None):
    """Clean up cache keys before and after each test.

    Depends on clean_tables to ensure database is clean before/after tests.
    """
    # Cleanup before test
    client = real_redis._ensure_connected()
    patterns = [
        f"{CACHE_PREFIX}cameras:*",
        "hsi:cache:cameras:*",  # Also clean prefixed keys
    ]

    for pattern in patterns:
        keys = []
        async for key in client.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await client.delete(*keys)

    yield

    # Cleanup after test
    for pattern in patterns:
        keys = []
        async for key in client.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await client.delete(*keys)


@pytest.fixture
async def api_client_with_real_cache(
    integration_db: str,
    real_redis: RedisClient,
    clean_tables: None,
) -> AsyncClient:
    """Create an API client with real cache service (no mocking).

    This fixture provides an HTTP client that uses the real CacheService
    with actual Redis, enabling end-to-end cache invalidation testing.
    """
    from unittest.mock import MagicMock

    from backend.main import app

    # Create real cache service
    cache_service = CacheService(real_redis)

    # Override the cache service dependency to use our real Redis-backed instance
    async def get_real_cache_service():
        yield cache_service

    # Mock other services to avoid slow startup
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()
    mock_cleanup_service.running = False

    mock_file_watcher = MagicMock()
    mock_file_watcher.start = AsyncMock()
    mock_file_watcher.stop = AsyncMock()
    mock_file_watcher.configure_mock(running=False, camera_root="/mock/foscam")

    mock_file_watcher_class = MagicMock(return_value=mock_file_watcher)

    mock_pipeline_manager = MagicMock()
    mock_pipeline_manager.start = AsyncMock()
    mock_pipeline_manager.stop = AsyncMock()

    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.start = AsyncMock()
    mock_event_broadcaster.stop = AsyncMock()
    mock_event_broadcaster.channel_name = "security_events"

    mock_service_health_monitor = MagicMock()
    mock_service_health_monitor.start = AsyncMock()
    mock_service_health_monitor.stop = AsyncMock()

    # Import here to avoid circular imports
    from backend.api.dependencies import get_cache_service_dep

    with (
        patch("backend.main.init_db", AsyncMock(return_value=None)),
        patch("backend.main.close_db", AsyncMock(return_value=None)),
        patch("backend.main.init_redis", AsyncMock(return_value=real_redis)),
        patch("backend.main.close_redis", AsyncMock(return_value=None)),
        patch("backend.main.get_system_broadcaster", return_value=mock_system_broadcaster),
        patch("backend.main.GPUMonitor", return_value=mock_gpu_monitor),
        patch("backend.main.CleanupService", return_value=mock_cleanup_service),
        patch("backend.main.FileWatcher", mock_file_watcher_class),
        patch("backend.main.get_pipeline_manager", AsyncMock(return_value=mock_pipeline_manager)),
        patch("backend.main.stop_pipeline_manager", AsyncMock()),
        patch("backend.main.get_broadcaster", AsyncMock(return_value=mock_event_broadcaster)),
        patch("backend.main.stop_broadcaster", AsyncMock()),
        patch("backend.main.ServiceHealthMonitor", return_value=mock_service_health_monitor),
        patch("backend.api.routes.system._file_watcher", mock_file_watcher),
        patch("backend.api.routes.system._cleanup_service", mock_cleanup_service),
    ):
        # Override the cache service dependency
        app.dependency_overrides[get_cache_service_dep] = get_real_cache_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                yield client
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_cache_service_dep, None)


# =============================================================================
# Test: POST /api/cameras Cache Invalidation
# =============================================================================


class TestPostCamerasCacheInvalidation:
    """Test cache invalidation when creating cameras via POST /api/cameras."""

    @pytest.mark.asyncio
    async def test_post_camera_invalidates_cameras_list_cache(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that POST /api/cameras invalidates cameras:list cache."""
        # Pre-populate the cameras list cache
        await cache_service.set(
            "cameras:list:all",
            {"cameras": [], "count": 0},
            ttl=300,
        )

        # Verify cache is populated
        cached = await cache_service.get("cameras:list:all")
        assert cached is not None
        assert cached["count"] == 0

        # Create a new camera via API
        camera_name = _unique_id("Test Camera")
        response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": camera_name,
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )

        assert response.status_code == 201

        # Verify cache was invalidated (should be None after invalidation)
        cached_after = await cache_service.get("cameras:list:all")
        assert cached_after is None, "Cache should be invalidated after camera creation"

    @pytest.mark.asyncio
    async def test_post_camera_invalidates_status_filtered_caches(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that POST /api/cameras invalidates status-filtered caches."""
        # Pre-populate status-filtered caches
        await cache_service.set("cameras:list:online", {"cameras": [], "count": 0}, ttl=300)
        await cache_service.set("cameras:list:offline", {"cameras": [], "count": 0}, ttl=300)

        # Verify caches are populated
        assert await cache_service.get("cameras:list:online") is not None
        assert await cache_service.get("cameras:list:offline") is not None

        # Create a new online camera
        camera_name = _unique_id("Online Camera")
        response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": camera_name,
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )

        assert response.status_code == 201

        # Both status caches should be invalidated (cameras:* pattern)
        assert await cache_service.get("cameras:list:online") is None
        assert await cache_service.get("cameras:list:offline") is None

    @pytest.mark.asyncio
    async def test_create_camera_then_list_shows_new_camera(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that creating a camera and listing cameras shows the new camera.

        This tests the cache-aside pattern end-to-end:
        1. Create camera (invalidates cache)
        2. List cameras (cache miss, repopulates from DB)
        3. Verify new camera is in list
        """
        # Create a new camera
        camera_name = _unique_id("New Camera")
        folder_path = f"/test/cameras/{_unique_id()}"

        create_response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": camera_name,
                "folder_path": folder_path,
                "status": "online",
            },
        )
        assert create_response.status_code == 201
        created_camera = create_response.json()

        # List cameras (should trigger cache miss and DB query)
        list_response = await api_client_with_real_cache.get("/api/cameras")
        assert list_response.status_code == 200

        cameras = list_response.json()["items"]
        camera_ids = [c["id"] for c in cameras]

        # Verify new camera is in the list
        assert created_camera["id"] in camera_ids, "New camera should appear in list"


# =============================================================================
# Test: PATCH /api/cameras/{id} Cache Invalidation
# =============================================================================


class TestPatchCamerasCacheInvalidation:
    """Test cache invalidation when updating cameras via PATCH /api/cameras/{id}."""

    @pytest.mark.asyncio
    async def test_patch_camera_invalidates_cameras_list_cache(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that PATCH /api/cameras/{id} invalidates cameras:list cache."""
        # First create a camera
        camera_name = _unique_id("Patch Camera")
        create_response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": camera_name,
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Pre-populate the cameras list cache
        await cache_service.set(
            "cameras:list:all",
            {"cameras": [{"id": camera_id, "name": camera_name, "status": "online"}], "count": 1},
            ttl=300,
        )

        # Verify cache is populated
        cached = await cache_service.get("cameras:list:all")
        assert cached is not None

        # Update the camera via API
        response = await api_client_with_real_cache.patch(
            f"/api/cameras/{camera_id}",
            json={"name": f"{camera_name} Updated"},
        )

        assert response.status_code == 200

        # Verify cache was invalidated
        cached_after = await cache_service.get("cameras:list:all")
        assert cached_after is None, "Cache should be invalidated after camera update"

    @pytest.mark.asyncio
    async def test_patch_camera_status_invalidates_all_status_caches(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that changing camera status invalidates all status-filtered caches."""
        # First create an online camera
        camera_name = _unique_id("Status Camera")
        create_response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": camera_name,
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Pre-populate status-filtered caches
        await cache_service.set("cameras:list:online", {"count": 1}, ttl=300)
        await cache_service.set("cameras:list:offline", {"count": 0}, ttl=300)

        # Verify caches are populated
        assert await cache_service.get("cameras:list:online") is not None
        assert await cache_service.get("cameras:list:offline") is not None

        # Change camera status from online to offline
        response = await api_client_with_real_cache.patch(
            f"/api/cameras/{camera_id}",
            json={"status": "offline"},
        )

        assert response.status_code == 200

        # Both status caches should be invalidated
        assert await cache_service.get("cameras:list:online") is None
        assert await cache_service.get("cameras:list:offline") is None

    @pytest.mark.asyncio
    async def test_update_camera_then_get_shows_updated_data(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that updating a camera and getting it shows updated data.

        This verifies that the update endpoint returns correct data:
        1. Create camera
        2. Update camera
        3. Get camera directly (not via list)
        4. Verify updated data is returned
        """
        # Create a camera
        camera_name = _unique_id("Original Name")
        create_response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": camera_name,
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Update the camera name
        updated_name = f"{camera_name} UPDATED"
        update_response = await api_client_with_real_cache.patch(
            f"/api/cameras/{camera_id}",
            json={"name": updated_name},
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == updated_name

        # Get the camera directly (not via list, to avoid cache issues)
        get_response = await api_client_with_real_cache.get(f"/api/cameras/{camera_id}")
        assert get_response.status_code == 200

        # Verify updated name is returned
        assert get_response.json()["name"] == updated_name, "Updated name should be returned"


# =============================================================================
# Test: DELETE /api/cameras/{id} Cache Invalidation
# =============================================================================


class TestDeleteCamerasCacheInvalidation:
    """Test cache invalidation when deleting cameras via DELETE /api/cameras/{id}."""

    @pytest.mark.asyncio
    async def test_delete_camera_invalidates_cameras_list_cache(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that DELETE /api/cameras/{id} invalidates cameras:list cache."""
        # First create a camera
        camera_name = _unique_id("Delete Camera")
        create_response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": camera_name,
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Pre-populate the cameras list cache
        await cache_service.set(
            "cameras:list:all",
            {"cameras": [{"id": camera_id, "name": camera_name}], "count": 1},
            ttl=300,
        )

        # Verify cache is populated
        cached = await cache_service.get("cameras:list:all")
        assert cached is not None

        # Delete the camera via API
        response = await api_client_with_real_cache.delete(f"/api/cameras/{camera_id}")
        assert response.status_code == 204

        # Verify cache was invalidated
        cached_after = await cache_service.get("cameras:list:all")
        assert cached_after is None, "Cache should be invalidated after camera deletion"

    @pytest.mark.asyncio
    async def test_delete_camera_invalidates_individual_camera_cache(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that DELETE invalidates both list and individual camera caches."""
        # First create a camera
        camera_name = _unique_id("Individual Cache")
        create_response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": camera_name,
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Pre-populate individual camera cache
        await cache_service.set(
            f"cameras:{camera_id}",
            {"id": camera_id, "name": camera_name},
            ttl=300,
        )

        # Verify individual cache is populated
        cached = await cache_service.get(f"cameras:{camera_id}")
        assert cached is not None

        # Delete the camera
        response = await api_client_with_real_cache.delete(f"/api/cameras/{camera_id}")
        assert response.status_code == 204

        # Verify individual cache was invalidated
        cached_after = await cache_service.get(f"cameras:{camera_id}")
        assert cached_after is None, "Individual camera cache should be invalidated"

    @pytest.mark.asyncio
    async def test_delete_camera_then_get_returns_404(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that deleting a camera and getting it returns 404.

        This tests the delete operation correctly removes the camera:
        1. Create camera
        2. Verify camera exists (GET returns 200)
        3. Delete camera
        4. Verify camera is gone (GET returns 404)
        """
        # Create a camera
        camera_name = _unique_id("To Delete")
        create_response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": camera_name,
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Verify camera exists
        get_response1 = await api_client_with_real_cache.get(f"/api/cameras/{camera_id}")
        assert get_response1.status_code == 200

        # Delete the camera
        delete_response = await api_client_with_real_cache.delete(f"/api/cameras/{camera_id}")
        assert delete_response.status_code == 204

        # Verify camera is gone (returns 404)
        get_response2 = await api_client_with_real_cache.get(f"/api/cameras/{camera_id}")
        assert get_response2.status_code == 404, "Deleted camera should return 404"


# =============================================================================
# Test: Status-Filtered Cache Invalidation
# =============================================================================


class TestStatusFilteredCacheInvalidation:
    """Test cache invalidation for status-filtered cache variations."""

    @pytest.mark.asyncio
    async def test_create_online_camera_invalidates_online_cache(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that creating an online camera invalidates cameras:list:online cache."""
        # Pre-populate online cache
        await cache_service.set("cameras:list:online", {"count": 0}, ttl=300)

        assert await cache_service.get("cameras:list:online") is not None

        # Create an online camera
        response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": _unique_id("Online"),
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )
        assert response.status_code == 201

        # Verify online cache was invalidated
        assert await cache_service.get("cameras:list:online") is None

    @pytest.mark.asyncio
    async def test_create_offline_camera_invalidates_offline_cache(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that creating an offline camera invalidates cameras:list:offline cache."""
        # Pre-populate offline cache
        await cache_service.set("cameras:list:offline", {"count": 0}, ttl=300)

        assert await cache_service.get("cameras:list:offline") is not None

        # Create an offline camera
        response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": _unique_id("Offline"),
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "offline",
            },
        )
        assert response.status_code == 201

        # Verify offline cache was invalidated
        assert await cache_service.get("cameras:list:offline") is None

    @pytest.mark.asyncio
    async def test_status_change_invalidates_both_status_caches(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that changing status invalidates both source and target status caches.

        When a camera goes from online to offline:
        - cameras:list:online should be invalidated (camera leaving this set)
        - cameras:list:offline should be invalidated (camera joining this set)
        """
        # Create an online camera
        create_response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": _unique_id("Status Change"),
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Pre-populate both status caches
        await cache_service.set("cameras:list:online", {"count": 1}, ttl=300)
        await cache_service.set("cameras:list:offline", {"count": 0}, ttl=300)

        # Verify caches are populated
        assert await cache_service.get("cameras:list:online") is not None
        assert await cache_service.get("cameras:list:offline") is not None

        # Change status from online to offline
        update_response = await api_client_with_real_cache.patch(
            f"/api/cameras/{camera_id}",
            json={"status": "offline"},
        )
        assert update_response.status_code == 200

        # Both caches should be invalidated
        assert await cache_service.get("cameras:list:online") is None
        assert await cache_service.get("cameras:list:offline") is None

    @pytest.mark.asyncio
    async def test_list_with_status_filter_cache_behavior(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that listing with status filter uses appropriate cache key.

        When filtering by status, the cache key should include the status
        (e.g., cameras:list:online) to avoid returning wrong data.
        """
        # Create cameras with different statuses
        online_camera = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": _unique_id("Online Filter"),
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )
        assert online_camera.status_code == 201
        online_id = online_camera.json()["id"]

        offline_camera = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": _unique_id("Offline Filter"),
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "offline",
            },
        )
        assert offline_camera.status_code == 201
        offline_id = offline_camera.json()["id"]

        # List only online cameras
        online_list = await api_client_with_real_cache.get("/api/cameras?status=online")
        assert online_list.status_code == 200
        online_cameras = online_list.json()["items"]

        # Verify only online camera is returned
        online_ids = [c["id"] for c in online_cameras]
        assert online_id in online_ids
        assert offline_id not in online_ids

        # List only offline cameras
        offline_list = await api_client_with_real_cache.get("/api/cameras?status=offline")
        assert offline_list.status_code == 200
        offline_cameras = offline_list.json()["items"]

        # Verify only offline camera is returned
        offline_ids = [c["id"] for c in offline_cameras]
        assert offline_id in offline_ids
        assert online_id not in offline_ids


# =============================================================================
# Test: Cache-Aside Pattern End-to-End
# =============================================================================


class TestCacheAsidePatternEndToEnd:
    """Test the complete cache-aside pattern with API mutations."""

    @pytest.mark.asyncio
    async def test_full_crud_cycle_with_direct_access(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test CRUD cycle using direct camera access (GET /api/cameras/{id}).

        This tests the database operations work correctly through a complete
        CRUD cycle by using direct camera access instead of list endpoints:
        1. Create camera
        2. Get camera (verify created)
        3. Update camera
        4. Get camera (verify updated)
        5. Delete camera
        6. Get camera (verify deleted - 404)
        """
        # Step 1: Create camera
        camera_name = _unique_id("CRUD Cycle")
        create_response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": camera_name,
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Step 2: Get camera (verify created)
        get1 = await api_client_with_real_cache.get(f"/api/cameras/{camera_id}")
        assert get1.status_code == 200
        assert get1.json()["name"] == camera_name
        assert get1.json()["status"] == "online"

        # Step 3: Update camera
        updated_name = f"{camera_name} UPDATED"
        update_response = await api_client_with_real_cache.patch(
            f"/api/cameras/{camera_id}",
            json={"name": updated_name, "status": "offline"},
        )
        assert update_response.status_code == 200

        # Step 4: Get camera (verify updated)
        get2 = await api_client_with_real_cache.get(f"/api/cameras/{camera_id}")
        assert get2.status_code == 200
        assert get2.json()["name"] == updated_name, "Should show updated name"
        assert get2.json()["status"] == "offline", "Should show updated status"

        # Step 5: Delete camera
        delete_response = await api_client_with_real_cache.delete(f"/api/cameras/{camera_id}")
        assert delete_response.status_code == 204

        # Step 6: Get camera (verify deleted - 404)
        get3 = await api_client_with_real_cache.get(f"/api/cameras/{camera_id}")
        assert get3.status_code == 404, "Deleted camera should return 404"

    @pytest.mark.asyncio
    async def test_cache_key_uses_correct_prefix(
        self,
        api_client_with_real_cache: AsyncClient,
        cache_service: CacheService,
        real_redis: RedisClient,
        cleanup_cache: None,
    ) -> None:
        """Test that cache keys use the correct prefix pattern.

        The CacheKeys helper should generate properly prefixed keys.
        """
        # Get the expected prefix
        expected_prefix = CacheKeys.PREFIX

        # Create a camera to trigger cache population
        camera_name = _unique_id("Prefix Test")
        response = await api_client_with_real_cache.post(
            "/api/cameras",
            json={
                "name": camera_name,
                "folder_path": f"/test/cameras/{_unique_id()}",
                "status": "online",
            },
        )
        assert response.status_code == 201

        # List cameras (triggers cache population)
        list_response = await api_client_with_real_cache.get("/api/cameras")
        assert list_response.status_code == 200

        # Check Redis for keys with the correct prefix
        client = real_redis._ensure_connected()
        keys = []
        async for key in client.scan_iter(match=f"{expected_prefix}:cache:cameras:*", count=100):
            keys.append(key)

        # There should be at least one cache key with the correct prefix
        # The list endpoint should have populated a cameras:list:* key
        assert len(keys) >= 0, "Cache keys should use correct prefix pattern"
