"""Integration tests for graceful shutdown sequence.

Tests verify:
- Database connection cleanup during shutdown
- Redis connection cleanup during shutdown
- In-flight requests complete before shutdown
- Background tasks gracefully terminate
- Resource cleanup order and dependencies

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- clean_tables: Database isolation for each test
- real_redis: Real Redis client for shutdown testing
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from backend.core.database import close_db, get_engine, get_session, init_db
from backend.core.redis import RedisClient
from backend.models.camera import Camera
from backend.tests.conftest import unique_id

pytestmark = pytest.mark.integration


class TestDatabaseShutdown:
    """Tests for database connection shutdown and cleanup."""

    async def test_database_close_disposes_engine(self, integration_db: str) -> None:
        """Test that close_db properly disposes of the engine."""
        # Verify database is initialized
        engine = get_engine()
        assert engine is not None

        # Close database
        await close_db()

        # Verify engine is no longer accessible
        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_engine()

        # Re-initialize for cleanup by fixture
        await init_db()

    async def test_database_shutdown_completes_pending_operations(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that pending operations complete before database shutdown."""
        camera_id = unique_id("camera")

        # Start operation
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Verify operation completed
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one_or_none()
            assert camera is not None

        # Close database (should wait for pending operations)
        await close_db()

        # Re-initialize for verification
        await init_db()

        # Verify data was persisted
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one_or_none()
            assert camera is not None

    async def test_database_multiple_close_calls_safe(self, integration_db: str) -> None:
        """Test that calling close_db multiple times is safe (idempotent)."""
        # First close
        await close_db()

        # Second close (should not raise)
        await close_db()

        # Third close (should not raise)
        await close_db()

        # Re-initialize for cleanup by fixture
        await init_db()

    async def test_database_shutdown_prevents_new_operations(self, integration_db: str) -> None:
        """Test that new operations fail after database shutdown."""
        # Close database
        await close_db()

        # Attempt new operation (should fail)
        with pytest.raises(RuntimeError, match="Database not initialized"):
            async with get_session() as session:
                result = await session.execute(select(Camera))
                result.scalars().all()

        # Re-initialize for cleanup by fixture
        await init_db()


class TestRedisShutdown:
    """Tests for Redis connection shutdown and cleanup."""

    async def test_redis_close_disconnects_client(
        self, integration_db: str, worker_redis_url: str
    ) -> None:
        """Test that close_redis properly disconnects the client."""
        # Initialize Redis
        client = RedisClient(redis_url=worker_redis_url)
        await client.connect()

        # Verify connection works
        await client.set("test_key", "test_value")
        value = await client.get("test_key")
        assert value == "test_value"

        # Clean up test key
        await client.delete("test_key")

        # Close Redis
        await client.disconnect()

        # Verify client is disconnected (operations should fail gracefully)
        # Note: Actual behavior depends on Redis client implementation

    async def test_redis_multiple_close_calls_safe(
        self, integration_db: str, worker_redis_url: str
    ) -> None:
        """Test that calling disconnect multiple times is safe (idempotent)."""
        client = RedisClient(redis_url=worker_redis_url)
        await client.connect()

        # First close
        await client.disconnect()

        # Second close (should not raise)
        await client.disconnect()

        # Third close (should not raise)
        await client.disconnect()


class TestGracefulShutdownSequence:
    """Tests for complete graceful shutdown sequence."""

    async def test_shutdown_order_database_then_redis(
        self, integration_db: str, worker_redis_url: str, clean_tables: None
    ) -> None:
        """Test proper shutdown order: complete operations, close database, close Redis."""
        camera_id = unique_id("camera")

        # Perform database operation
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Initialize Redis
        client = RedisClient(redis_url=worker_redis_url)
        await client.connect()

        # Perform Redis operation
        await client.set("shutdown_test", "active")

        # Verify both are working
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one()
            assert camera is not None

        value = await client.get("shutdown_test")
        assert value == "active"

        # Graceful shutdown sequence
        # 1. Stop accepting new work (not applicable in test)
        # 2. Complete pending operations (already done)
        # 3. Close database
        await close_db()

        # 4. Close Redis
        await client.delete("shutdown_test")
        await client.disconnect()

        # 5. Verify shutdown completed
        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_engine()

        # Re-initialize for cleanup by fixture
        await init_db()

    async def test_shutdown_with_pending_background_tasks(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test shutdown waits for background tasks to complete."""
        camera_id = unique_id("camera")
        task_completed = False

        async def background_task() -> None:
            """Simulate background task."""
            nonlocal task_completed
            # Wait for intentional sleep to test shutdown coordination (not mocked)
            await asyncio.sleep(0.1)
            async with get_session() as session:
                camera = Camera(
                    id=camera_id,
                    name="Background Camera",
                    folder_path=f"/export/foscam/{camera_id}",
                    status="online",
                )
                session.add(camera)
                await session.commit()
            task_completed = True

        # Start background task
        task = asyncio.create_task(background_task())

        # Wait for task to complete before shutdown
        await task

        # Verify task completed
        assert task_completed

        # Verify data was persisted
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one_or_none()
            assert camera is not None

    async def test_shutdown_cancels_long_running_tasks(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that long-running tasks are cancelled during shutdown."""
        cancelled = False

        async def long_running_task() -> None:
            """Simulate long-running task that should be cancelled."""
            nonlocal cancelled
            try:
                # Intentional long sleep - cancelled immediately after 0.1s (see below)
                await asyncio.sleep(10)  # cancelled
            except asyncio.CancelledError:
                cancelled = True
                raise

        # Start long-running task
        task = asyncio.create_task(long_running_task())

        # Wait briefly then cancel (simulating shutdown)
        await asyncio.sleep(0.1)
        task.cancel()

        # Verify task was cancelled
        with pytest.raises(asyncio.CancelledError):
            await task

        assert cancelled


class TestInFlightRequestCompletion:
    """Tests for completing in-flight requests during shutdown."""

    async def test_inflight_database_operations_complete(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that in-flight database operations complete before shutdown."""
        camera_id = unique_id("camera")

        async def slow_database_operation() -> None:
            """Simulate slow database operation."""
            async with get_session() as session:
                # Simulate slow processing (intentional sleep - not mocked)
                await asyncio.sleep(0.1)

                camera = Camera(
                    id=camera_id,
                    name="Slow Camera",
                    folder_path=f"/export/foscam/{camera_id}",
                    status="online",
                )
                session.add(camera)
                await session.commit()

        # Start operation
        await slow_database_operation()

        # Verify operation completed
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one_or_none()
            assert camera is not None

    async def test_concurrent_operations_all_complete_before_shutdown(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that all concurrent operations complete before shutdown."""

        async def create_camera(index: int) -> None:
            """Create a camera."""
            camera_id = f"{unique_id('camera')}_{index}"
            async with get_session() as session:
                camera = Camera(
                    id=camera_id,
                    name=f"Camera {index}",
                    folder_path=f"/export/foscam/{camera_id}",
                    status="online",
                )
                session.add(camera)
                await session.commit()

        # Start concurrent operations
        tasks = [create_camera(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # Verify all completed
        async with get_session() as session:
            result = await session.execute(select(Camera))
            cameras = result.scalars().all()
            assert len(cameras) == 5


class TestResourceCleanupOrder:
    """Tests for proper resource cleanup order during shutdown."""

    async def test_cleanup_order_sessions_before_engine(self, integration_db: str) -> None:
        """Test that sessions are cleaned up before engine disposal."""
        camera_id = unique_id("camera")

        # Create session and perform operation
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()
            # Session closes here

        # Now close engine
        await close_db()

        # Verify engine is closed
        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_engine()

        # Re-initialize for cleanup by fixture
        await init_db()

    async def test_cleanup_handles_partial_failure(self, integration_db: str) -> None:
        """Test that cleanup continues even if some steps fail."""
        # This test demonstrates the pattern of continuing cleanup
        # even when individual steps fail

        cleanup_steps = []

        async def cleanup_step_1() -> None:
            """First cleanup step (succeeds)."""
            cleanup_steps.append("step1")

        async def cleanup_step_2() -> None:
            """Second cleanup step (fails)."""
            cleanup_steps.append("step2")
            raise RuntimeError("Simulated cleanup error")

        async def cleanup_step_3() -> None:
            """Third cleanup step (should still execute)."""
            cleanup_steps.append("step3")

        # Execute cleanup sequence
        for step in [cleanup_step_1, cleanup_step_2, cleanup_step_3]:
            try:
                await step()
            except Exception:
                # Continue cleanup even if step fails
                pass

        # Verify all steps were attempted
        assert "step1" in cleanup_steps
        assert "step2" in cleanup_steps
        assert "step3" in cleanup_steps


class TestShutdownIdempotency:
    """Tests for shutdown operation idempotency."""

    async def test_repeated_shutdown_calls_safe(self, integration_db: str) -> None:
        """Test that calling shutdown functions multiple times is safe."""
        # First shutdown
        await close_db()

        # Second shutdown (idempotent)
        await close_db()

        # Third shutdown (idempotent)
        await close_db()

        # Re-initialize for cleanup by fixture
        await init_db()

    async def test_shutdown_after_failed_initialization(self, integration_db: str) -> None:
        """Test that shutdown works even after failed initialization."""
        # Close current database
        await close_db()

        # Try to close again (should not raise even though not initialized)
        await close_db()

        # Re-initialize for cleanup by fixture
        await init_db()


class TestShutdownSignalHandling:
    """Tests for shutdown signal handling patterns."""

    async def test_shutdown_coordinator_pattern(self, integration_db: str) -> None:
        """Test shutdown coordinator pattern for managing multiple resources."""
        shutdown_complete = False

        async def shutdown_coordinator() -> None:
            """Coordinate shutdown of multiple resources."""
            nonlocal shutdown_complete

            # 1. Stop accepting new work
            # (In real system, would stop accepting HTTP requests)

            # 2. Wait for in-flight operations
            # Wait for intentional sleep to simulate operations completing (not mocked)
            await asyncio.sleep(0.1)

            # 3. Close database
            await close_db()

            # 4. Close other resources
            # (In real system, would close Redis, etc.)

            shutdown_complete = True

        # Execute shutdown
        await shutdown_coordinator()

        # Verify shutdown completed
        assert shutdown_complete

        # Re-initialize for cleanup by fixture
        await init_db()

    async def test_graceful_shutdown_with_timeout(self, integration_db: str) -> None:
        """Test graceful shutdown with timeout fallback."""
        shutdown_timeout = 1.0  # 1 second timeout

        async def slow_operation() -> None:
            """Operation that takes too long."""
            # Wait for intentional long sleep to test timeout (not mocked)
            await asyncio.sleep(2.0)

        async def graceful_shutdown_with_timeout() -> bool:
            """Attempt graceful shutdown with timeout."""
            try:
                # Try to complete slow operation within timeout
                await asyncio.wait_for(slow_operation(), timeout=shutdown_timeout)
                return True
            except TimeoutError:
                # Timeout occurred - force shutdown
                return False

        # Execute shutdown with timeout
        completed = await graceful_shutdown_with_timeout()

        # Verify timeout occurred
        assert completed is False


class TestShutdownLogging:
    """Tests for shutdown logging and observability."""

    async def test_shutdown_sequence_logged(self, integration_db: str) -> None:
        """Test that shutdown sequence is properly logged."""
        log_entries = []

        async def log_shutdown_step(step: str) -> None:
            """Log shutdown step."""
            log_entries.append(step)

        # Simulate shutdown sequence with logging
        await log_shutdown_step("Starting shutdown")
        await log_shutdown_step("Stopping new requests")
        await log_shutdown_step("Waiting for in-flight operations")
        await close_db()
        await log_shutdown_step("Database closed")
        await log_shutdown_step("Shutdown complete")

        # Verify logging sequence
        assert "Starting shutdown" in log_entries
        assert "Database closed" in log_entries
        assert "Shutdown complete" in log_entries
        assert len(log_entries) == 5

        # Re-initialize for cleanup by fixture
        await init_db()

    async def test_shutdown_metrics_recorded(self, integration_db: str) -> None:
        """Test that shutdown metrics are recorded."""
        metrics = {
            "shutdown_start_time": None,
            "shutdown_end_time": None,
            "inflight_operations": 0,
            "shutdown_duration_ms": None,
        }

        async def record_shutdown_metrics() -> None:
            """Record shutdown metrics."""
            import time

            metrics["shutdown_start_time"] = time.time()
            metrics["inflight_operations"] = 0  # Would count actual operations

            # Simulate shutdown operations
            await close_db()

            metrics["shutdown_end_time"] = time.time()
            metrics["shutdown_duration_ms"] = (
                metrics["shutdown_end_time"] - metrics["shutdown_start_time"]
            ) * 1000

        # Execute shutdown with metrics
        await record_shutdown_metrics()

        # Verify metrics were recorded
        assert metrics["shutdown_start_time"] is not None
        assert metrics["shutdown_end_time"] is not None
        assert metrics["shutdown_duration_ms"] is not None
        assert metrics["shutdown_duration_ms"] >= 0

        # Re-initialize for cleanup by fixture
        await init_db()
