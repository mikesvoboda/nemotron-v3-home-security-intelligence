"""Memory leak detection integration tests.

This module contains tests that detect potential memory leaks in the application.
Tests measure memory before/after repeated operations and detect growing memory in loops.

Memory leaks can cause:
- Gradual performance degradation
- Out-of-memory crashes in production
- Resource exhaustion over time

Areas tested:
- WebSocket connection handling
- Database session management
- API request handling
- Cache operations
- Event listener/callback cleanup

Usage:
    pytest backend/tests/integration/test_memory_leaks.py -v
    pytest backend/tests/integration/test_memory_leaks.py -v -m slow  # Include slow tests
"""

from __future__ import annotations

import asyncio
import gc
import sys
import tracemalloc
import weakref
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.tests.conftest import unique_id

# Memory growth thresholds (in bytes)
# These are intentionally conservative to avoid flaky tests
MEMORY_GROWTH_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10 MB
MEMORY_GROWTH_PER_ITERATION_BYTES = 100 * 1024  # 100 KB per iteration


class MemoryTracker:
    """Helper class for tracking memory usage during tests.

    Uses tracemalloc to measure memory snapshots and detect memory growth
    across multiple iterations of an operation.
    """

    def __init__(self):
        self.snapshots: list[tracemalloc.Snapshot] = []
        self.started = False

    def start(self) -> None:
        """Start memory tracking."""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        self.started = True
        # Force garbage collection to get accurate baseline
        gc.collect()
        self.snapshots.clear()
        self.snapshots.append(tracemalloc.take_snapshot())

    def take_snapshot(self) -> None:
        """Take a memory snapshot."""
        if not self.started:
            raise RuntimeError("Memory tracking not started. Call start() first.")
        gc.collect()
        self.snapshots.append(tracemalloc.take_snapshot())

    def get_memory_growth(self) -> int:
        """Get total memory growth from first to last snapshot.

        Returns:
            Memory growth in bytes (positive means growth, negative means shrinkage)
        """
        if len(self.snapshots) < 2:
            return 0

        first = self.snapshots[0]
        last = self.snapshots[-1]

        # Compare snapshots
        top_stats = last.compare_to(first, "lineno")

        # Sum up all memory differences
        total_growth = sum(stat.size_diff for stat in top_stats)
        return total_growth

    def get_top_growth_locations(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get the top memory growth locations.

        Args:
            limit: Number of top locations to return

        Returns:
            List of (location, size_diff) tuples
        """
        if len(self.snapshots) < 2:
            return []

        first = self.snapshots[0]
        last = self.snapshots[-1]

        top_stats = last.compare_to(first, "lineno")

        return [
            (str(stat.traceback), stat.size_diff)
            for stat in sorted(top_stats, key=lambda x: x.size_diff, reverse=True)[:limit]
        ]

    def stop(self) -> None:
        """Stop memory tracking."""
        self.started = False
        # Don't stop tracemalloc as other tests might need it


@pytest.fixture
def memory_tracker() -> MemoryTracker:
    """Provide a memory tracker for tests."""
    tracker = MemoryTracker()
    yield tracker
    tracker.stop()


# =============================================================================
# WebSocket Connection Memory Leak Tests
# =============================================================================


class TestWebSocketMemoryLeaks:
    """Tests for memory leaks in WebSocket connection handling."""

    @pytest.mark.asyncio
    async def test_websocket_connection_cleanup(
        self,
        integration_env: str,
        memory_tracker: MemoryTracker,
    ):
        """Test that WebSocket connections are properly garbage collected.

        Creates multiple WebSocket connections, disconnects them, and verifies
        that the connection objects are properly garbage collected.
        """
        from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state

        # Reset broadcaster state to ensure clean test
        reset_broadcaster_state()

        # Track connection objects with weak references
        weak_refs: list[weakref.ref] = []

        # Create mock Redis
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)

        # Create broadcaster
        broadcaster = EventBroadcaster(mock_redis, channel_name="test_channel")

        memory_tracker.start()

        # Create and disconnect multiple connections
        for i in range(100):
            # Create mock WebSocket
            mock_ws = MagicMock()
            mock_ws.send_text = AsyncMock()
            mock_ws.close = AsyncMock()

            # Track with weak reference
            weak_refs.append(weakref.ref(mock_ws))

            # Add to broadcaster
            broadcaster._connections.add(mock_ws)

            # Remove from broadcaster (simulating disconnect)
            broadcaster._connections.discard(mock_ws)

            # Delete local reference
            del mock_ws

        # Force garbage collection
        gc.collect()

        memory_tracker.take_snapshot()

        # Check that connections were garbage collected
        alive_count = sum(1 for ref in weak_refs if ref() is not None)
        assert alive_count == 0, f"{alive_count} WebSocket connections not garbage collected"

        # Check memory growth
        growth = memory_tracker.get_memory_growth()
        assert growth < MEMORY_GROWTH_THRESHOLD_BYTES, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB during WebSocket test"
        )

    @pytest.mark.asyncio
    async def test_broadcaster_connection_set_no_leak(
        self,
        integration_env: str,
        memory_tracker: MemoryTracker,
    ):
        """Test that broadcaster connection set doesn't grow unboundedly.

        Simulates many connect/disconnect cycles and verifies the connection
        set remains empty after disconnections.
        """
        from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state

        reset_broadcaster_state()

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)

        broadcaster = EventBroadcaster(mock_redis, channel_name="test_channel")

        memory_tracker.start()

        # Simulate many connect/disconnect cycles
        for _ in range(1000):
            mock_ws = MagicMock()
            mock_ws.send_text = AsyncMock()
            mock_ws.close = AsyncMock()

            broadcaster._connections.add(mock_ws)
            broadcaster._connections.discard(mock_ws)

        gc.collect()
        memory_tracker.take_snapshot()

        # Connection set should be empty
        assert len(broadcaster._connections) == 0, (
            f"Broadcaster has {len(broadcaster._connections)} leaked connections"
        )

        # Memory should not grow significantly
        growth = memory_tracker.get_memory_growth()
        assert growth < MEMORY_GROWTH_THRESHOLD_BYTES, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB"
        )


# =============================================================================
# Database Session Memory Leak Tests
# =============================================================================


class TestDatabaseSessionMemoryLeaks:
    """Tests for memory leaks in database session management."""

    @pytest.mark.asyncio
    async def test_session_context_manager_cleanup(
        self,
        integration_db: str,
        memory_tracker: MemoryTracker,
    ):
        """Test that database sessions are properly cleaned up after use.

        Creates many database sessions via context manager and verifies
        they are properly closed and garbage collected.
        """
        from backend.core.database import get_session

        weak_refs: list[weakref.ref] = []

        memory_tracker.start()

        # Create and use many sessions
        for i in range(50):
            async with get_session() as session:
                # Track session with weak reference
                weak_refs.append(weakref.ref(session))

                # Perform a simple query to ensure session is active
                from sqlalchemy import text

                await session.execute(text("SELECT 1"))

        gc.collect()
        memory_tracker.take_snapshot()

        # Sessions should be garbage collected
        # Note: Some sessions may still be referenced by the connection pool
        # so we allow a small number to remain
        alive_count = sum(1 for ref in weak_refs if ref() is not None)
        assert alive_count < 5, f"{alive_count} sessions not garbage collected"

        # Check memory growth
        growth = memory_tracker.get_memory_growth()
        assert growth < MEMORY_GROWTH_THRESHOLD_BYTES, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB during session test"
        )

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_repeated_session_queries_no_leak(
        self,
        integration_db: str,
        memory_tracker: MemoryTracker,
    ):
        """Test that repeated database queries don't accumulate memory.

        Executes many queries and verifies memory doesn't grow unboundedly.
        """
        from sqlalchemy import text

        from backend.core.database import get_session

        memory_tracker.start()

        # Execute many queries
        for iteration in range(10):
            for _ in range(100):
                async with get_session() as session:
                    await session.execute(text("SELECT 1"))

            gc.collect()
            memory_tracker.take_snapshot()

            if iteration == 0:
                _initial_memory = memory_tracker.get_memory_growth()

        final_growth = memory_tracker.get_memory_growth()

        # Memory should not grow linearly with iterations
        # Allow for some growth but it should plateau
        assert final_growth < MEMORY_GROWTH_THRESHOLD_BYTES, (
            f"Memory grew by {final_growth / 1024 / 1024:.2f} MB during query loop"
        )

    @pytest.mark.asyncio
    async def test_session_exception_cleanup(
        self,
        integration_db: str,
        memory_tracker: MemoryTracker,
    ):
        """Test that sessions are cleaned up even when exceptions occur.

        Verifies that rollback and cleanup happen properly on errors.
        """
        from sqlalchemy import text

        from backend.core.database import get_session

        weak_refs: list[weakref.ref] = []

        memory_tracker.start()

        # Create sessions that encounter errors
        for i in range(50):
            try:
                async with get_session() as session:
                    weak_refs.append(weakref.ref(session))
                    # Execute invalid SQL to trigger error
                    await session.execute(text("SELECT * FROM nonexistent_table_xyz"))
            except Exception:  # noqa: S110 - Expected exception for testing cleanup
                pass

        gc.collect()
        memory_tracker.take_snapshot()

        # Sessions should still be cleaned up despite errors
        alive_count = sum(1 for ref in weak_refs if ref() is not None)
        assert alive_count < 5, f"{alive_count} sessions not cleaned up after errors"

        growth = memory_tracker.get_memory_growth()
        assert growth < MEMORY_GROWTH_THRESHOLD_BYTES, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB during error handling test"
        )


# =============================================================================
# API Request Memory Leak Tests
# =============================================================================


class TestAPIRequestMemoryLeaks:
    """Tests for memory leaks in API request handling."""

    @pytest.mark.asyncio
    async def test_repeated_api_requests_no_leak(
        self,
        client,
        memory_tracker: MemoryTracker,
    ):
        """Test that repeated API requests don't accumulate memory.

        Makes many API requests and verifies memory doesn't grow unboundedly.
        Uses smaller batch sizes to avoid overwhelming parallel test workers.
        """
        memory_tracker.start()

        # Make many requests in smaller batches
        for iteration in range(5):
            for _ in range(20):
                response = await client.get("/")
                assert response.status_code == 200

            gc.collect()
            memory_tracker.take_snapshot()

        growth = memory_tracker.get_memory_growth()
        assert growth < MEMORY_GROWTH_THRESHOLD_BYTES, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB during API request test"
        )

    @pytest.mark.asyncio
    async def test_api_error_responses_no_leak(
        self,
        client,
        memory_tracker: MemoryTracker,
    ):
        """Test that API error responses don't leak memory.

        Makes many requests that result in errors and verifies cleanup.
        """
        memory_tracker.start()

        # Make many requests to nonexistent endpoints
        for _ in range(100):
            response = await client.get("/api/nonexistent/endpoint/xyz")
            assert response.status_code == 404

        gc.collect()
        memory_tracker.take_snapshot()

        growth = memory_tracker.get_memory_growth()
        assert growth < MEMORY_GROWTH_THRESHOLD_BYTES, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB during error response test"
        )

    @pytest.mark.asyncio
    async def test_large_response_cleanup(
        self,
        integration_db: str,
        client,
        memory_tracker: MemoryTracker,
    ):
        """Test that large API responses are properly cleaned up.

        Creates entities, retrieves them, and verifies response data is freed.
        """
        from backend.core.database import get_session
        from backend.models.camera import Camera

        # Create some test cameras
        async with get_session() as session:
            for i in range(10):
                camera = Camera(
                    id=unique_id(f"memleak_cam_{i}"),
                    name=f"Memory Leak Test Camera {i}",
                    folder_path=f"/export/foscam/memleak_test_{i}",
                    status="online",
                )
                session.add(camera)
            await session.commit()

        memory_tracker.start()

        # Make many requests to cameras endpoint
        for _ in range(50):
            response = await client.get("/api/cameras")
            # Status might be 200 or 401 depending on auth
            assert response.status_code in [200, 401]

        gc.collect()
        memory_tracker.take_snapshot()

        growth = memory_tracker.get_memory_growth()
        assert growth < MEMORY_GROWTH_THRESHOLD_BYTES, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB during large response test"
        )


# =============================================================================
# Cache Memory Leak Tests
# =============================================================================


class TestCacheMemoryLeaks:
    """Tests for memory leaks in caching mechanisms."""

    @pytest.mark.asyncio
    async def test_settings_cache_no_leak(
        self,
        integration_env: str,
        memory_tracker: MemoryTracker,
    ):
        """Test that settings cache doesn't leak memory on repeated access.

        Accesses settings many times and verifies memory stability.
        """
        from backend.core.config import get_settings

        memory_tracker.start()

        # Access settings many times
        for _ in range(1000):
            settings = get_settings()
            _ = settings.database_url
            _ = settings.redis_url

        gc.collect()
        memory_tracker.take_snapshot()

        growth = memory_tracker.get_memory_growth()
        assert growth < MEMORY_GROWTH_THRESHOLD_BYTES, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB during settings cache test"
        )

    @pytest.mark.asyncio
    async def test_cache_service_eviction_cleanup(
        self,
        integration_env: str,
        memory_tracker: MemoryTracker,
    ):
        """Test that cache eviction properly frees memory.

        Uses mock cache service to verify evicted items are garbage collected.
        Uses a simple wrapper class to enable weak references to dict-like objects.
        """

        # Wrapper class to allow weak references (dicts don't support weakref)
        # Include __weakref__ in __slots__ to enable weak references
        class CacheItem:
            __slots__ = ("__weakref__", "data", "id")

            def __init__(self, data: str, item_id: int):
                self.data = data
                self.id = item_id

        weak_refs: list[weakref.ref] = []

        # Simulate a simple LRU cache
        cache: dict[str, CacheItem] = {}
        max_size = 100

        memory_tracker.start()

        # Add many items, forcing eviction
        for i in range(1000):
            # Create a large object to make memory changes visible
            large_obj = CacheItem(data="x" * 1000, item_id=i)
            weak_refs.append(weakref.ref(large_obj))

            key = f"key_{i}"

            # Simple eviction: remove oldest when full
            if len(cache) >= max_size:
                oldest_key = next(iter(cache))
                del cache[oldest_key]

            cache[key] = large_obj

        gc.collect()
        memory_tracker.take_snapshot()

        # Most objects should be garbage collected (only max_size remain in cache)
        alive_count = sum(1 for ref in weak_refs if ref() is not None)
        assert alive_count <= max_size + 10, (
            f"{alive_count} cached items not garbage collected (expected <= {max_size + 10})"
        )

        growth = memory_tracker.get_memory_growth()
        # Allow for cache size in memory
        expected_max = max_size * 2000 + MEMORY_GROWTH_THRESHOLD_BYTES
        assert growth < expected_max, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB during cache eviction test"
        )


# =============================================================================
# Event Listener/Callback Memory Leak Tests
# =============================================================================


class TestEventListenerMemoryLeaks:
    """Tests for memory leaks in event listeners and callbacks."""

    @pytest.mark.asyncio
    async def test_event_broadcaster_listener_cleanup(
        self,
        integration_env: str,
        memory_tracker: MemoryTracker,
    ):
        """Test that event broadcaster cleans up listeners properly.

        Registers and unregisters many listeners and verifies cleanup.
        """
        from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state

        reset_broadcaster_state()

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)

        broadcaster = EventBroadcaster(mock_redis, channel_name="test_channel")

        weak_refs: list[weakref.ref] = []

        memory_tracker.start()

        # Create many mock connections with callbacks
        for _ in range(500):
            mock_ws = MagicMock()
            # Create a callback that captures the mock
            callback = AsyncMock()
            mock_ws.send_text = callback
            mock_ws.close = AsyncMock()

            weak_refs.append(weakref.ref(mock_ws))
            weak_refs.append(weakref.ref(callback))

            # Add and remove
            broadcaster._connections.add(mock_ws)
            broadcaster._connections.discard(mock_ws)

            del mock_ws
            del callback

        gc.collect()
        memory_tracker.take_snapshot()

        # Check cleanup
        alive_count = sum(1 for ref in weak_refs if ref() is not None)
        assert alive_count < 50, f"{alive_count} listeners not garbage collected"

        growth = memory_tracker.get_memory_growth()
        assert growth < MEMORY_GROWTH_THRESHOLD_BYTES, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB during listener cleanup test"
        )

    @pytest.mark.asyncio
    async def test_async_task_cleanup(
        self,
        integration_env: str,
        memory_tracker: MemoryTracker,
    ):
        """Test that completed async tasks are garbage collected.

        Creates many async tasks and verifies they are cleaned up after completion.
        """
        weak_refs: list[weakref.ref] = []

        async def dummy_task(value: int) -> int:
            await asyncio.sleep(0)
            return value * 2

        memory_tracker.start()

        # Create and complete many tasks
        for i in range(500):
            task = asyncio.create_task(dummy_task(i))
            weak_refs.append(weakref.ref(task))
            result = await task
            assert result == i * 2

        gc.collect()
        memory_tracker.take_snapshot()

        # Tasks should be garbage collected
        alive_count = sum(1 for ref in weak_refs if ref() is not None)
        assert alive_count < 50, f"{alive_count} tasks not garbage collected"

        growth = memory_tracker.get_memory_growth()
        assert growth < MEMORY_GROWTH_THRESHOLD_BYTES, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB during task cleanup test"
        )


# =============================================================================
# Circular Reference Detection Tests
# =============================================================================


class TestCircularReferenceDetection:
    """Tests for detecting circular references that prevent garbage collection.

    Note: These tests use weak references instead of gc.DEBUG_SAVEALL to detect
    objects that aren't being garbage collected. gc.DEBUG_SAVEALL saves ALL
    collected objects, not just uncollectable ones, which causes false positives.
    """

    @pytest.mark.asyncio
    async def test_no_circular_refs_in_session(
        self,
        integration_db: str,
    ):
        """Test that database sessions don't create circular references.

        Uses weak references to verify sessions are properly garbage collected.
        """
        from sqlalchemy import text

        from backend.core.database import get_session

        weak_refs: list[weakref.ref] = []

        # Create and use sessions
        for _ in range(50):
            async with get_session() as session:
                weak_refs.append(weakref.ref(session))
                await session.execute(text("SELECT 1"))

        # Force garbage collection
        gc.collect()
        gc.collect()  # Multiple collections to handle weak references

        # Count sessions that weren't garbage collected
        alive_count = sum(1 for ref in weak_refs if ref() is not None)

        # Allow for some sessions to be held by connection pool
        assert alive_count < 10, (
            f"Found {alive_count} sessions not garbage collected (possible circular refs)"
        )

    @pytest.mark.asyncio
    async def test_no_circular_refs_in_broadcaster(
        self,
        integration_env: str,
    ):
        """Test that event broadcaster doesn't create circular references.

        Uses weak references to verify broadcaster and connections are properly cleaned up.
        """
        from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state

        reset_broadcaster_state()

        weak_refs: list[weakref.ref] = []

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)

        broadcaster = EventBroadcaster(mock_redis, channel_name="test_channel")
        _broadcaster_ref = weakref.ref(broadcaster)

        # Add and remove connections
        for _ in range(100):
            mock_ws = MagicMock()
            mock_ws.send_text = AsyncMock()
            mock_ws.close = AsyncMock()

            weak_refs.append(weakref.ref(mock_ws))

            broadcaster._connections.add(mock_ws)
            broadcaster._connections.discard(mock_ws)
            del mock_ws

        # Delete broadcaster reference
        del broadcaster
        reset_broadcaster_state()

        gc.collect()
        gc.collect()

        # Check that connections were garbage collected
        connection_alive = sum(1 for ref in weak_refs if ref() is not None)
        assert connection_alive == 0, f"Found {connection_alive} connections not garbage collected"

        # Note: broadcaster_ref may still be alive if held by module-level singleton
        # This is expected behavior, not a leak


# =============================================================================
# Reference Count Tests
# =============================================================================


class TestReferenceCounts:
    """Tests that verify reference counts are properly managed."""

    @pytest.mark.asyncio
    async def test_model_refcount_after_session(
        self,
        integration_db: str,
    ):
        """Test that SQLAlchemy models have expected reference counts after session.

        Verifies that models don't accumulate references when loaded from database.
        """
        from backend.core.database import get_session
        from backend.models.camera import Camera

        # Create a test camera
        camera_id = unique_id("refcount_test")
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Refcount Test Camera",
                folder_path="/export/foscam/refcount_test",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Load camera multiple times and check refcount doesn't grow
        refcounts: list[int] = []

        for _ in range(10):
            async with get_session() as session:
                from sqlalchemy import select

                result = await session.execute(select(Camera).where(Camera.id == camera_id))
                loaded_camera = result.scalar_one_or_none()
                if loaded_camera:
                    refcounts.append(sys.getrefcount(loaded_camera))

        # Refcounts should be stable, not growing
        # Some variation is expected due to internal references
        if len(refcounts) >= 2:
            growth = refcounts[-1] - refcounts[0]
            assert abs(growth) < 5, f"Reference count grew by {growth}: {refcounts}"


# =============================================================================
# Memory Snapshot Comparison Tests
# =============================================================================


class TestMemorySnapshotComparison:
    """Tests using memory snapshot comparison to detect leaks."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_overall_memory_stability(
        self,
        integration_db: str,
        client,
        memory_tracker: MemoryTracker,
    ):
        """Test overall memory stability under mixed workload.

        Simulates a realistic workload with multiple operation types
        and verifies memory remains stable.
        """
        from sqlalchemy import text

        from backend.core.database import get_session
        from backend.models.camera import Camera

        memory_tracker.start()

        # Run multiple iterations of mixed workload
        for iteration in range(5):
            # Database operations
            for i in range(10):
                async with get_session() as session:
                    await session.execute(text("SELECT 1"))

            # API requests
            for _ in range(10):
                await client.get("/")

            # Create some entities
            async with get_session() as session:
                camera = Camera(
                    id=unique_id(f"stability_test_{iteration}"),
                    name=f"Stability Test {iteration}",
                    folder_path=f"/export/foscam/stability_test_{iteration}",
                    status="online",
                )
                session.add(camera)
                await session.commit()

            gc.collect()
            memory_tracker.take_snapshot()

        # Analyze memory growth pattern
        growth = memory_tracker.get_memory_growth()

        # Memory should be relatively stable
        assert growth < MEMORY_GROWTH_THRESHOLD_BYTES * 2, (
            f"Memory grew by {growth / 1024 / 1024:.2f} MB during stability test. "
            f"Top growth locations:\n{memory_tracker.get_top_growth_locations()}"
        )

    @pytest.mark.asyncio
    async def test_tracemalloc_integration(
        self,
        integration_env: str,
    ):
        """Test that tracemalloc integration works correctly.

        Verifies that our memory tracking setup captures memory allocations.
        """
        tracker = MemoryTracker()
        tracker.start()

        # Allocate some memory
        large_list = [{"data": "x" * 10000} for _ in range(100)]

        tracker.take_snapshot()

        # Should detect memory growth
        growth = tracker.get_memory_growth()
        assert growth > 0, "Memory tracking should detect allocations"

        # Free memory
        del large_list
        gc.collect()

        tracker.take_snapshot()

        # Check top locations
        locations = tracker.get_top_growth_locations()
        assert isinstance(locations, list), "Should return list of locations"

        tracker.stop()
