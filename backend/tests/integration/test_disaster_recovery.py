"""Disaster recovery and data integrity tests.

This module tests critical disaster recovery scenarios:
- Database failover and reconnection
- Redis failover handling
- Data corruption detection
- Cache/DB consistency

Expected Behavior:
- System recovers gracefully from database failures
- Redis failover is handled transparently
- Data integrity issues are detected and reported
- Cache invalidation maintains consistency

Related: NEM-2096 (Epic: Disaster Recovery Testing)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from backend.core.database import close_db, get_engine, get_session, init_db
from backend.core.redis import RedisClient
from backend.tests.factories import CameraFactory


class TestDatabaseFailover:
    """Tests for database failover and reconnection."""

    @pytest.mark.asyncio
    async def test_application_handles_database_unavailable(self) -> None:
        """Application handles database becoming unavailable gracefully."""

        async def failing_operation() -> None:
            raise OperationalError(
                "statement",
                {},
                Exception("FATAL: terminating connection due to administrator command"),
            )

        # Verify exception is raised and can be caught
        with pytest.raises(OperationalError) as exc_info:
            await failing_operation()

        assert "terminating connection" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connection_pool_recovers_after_reconnect(self, integration_db: str) -> None:
        """Connection pool recovers after database reconnection."""
        # Perform initial query
        async with get_session() as session:
            result = await session.execute(text("SELECT 1 as test"))
            assert result.scalar_one() == 1

        # Close and reinitialize database
        await close_db()
        await init_db()

        # Verify connection works after reconnect
        async with get_session() as session:
            result = await session.execute(text("SELECT 2 as test"))
            assert result.scalar_one() == 2

    @pytest.mark.asyncio
    async def test_engine_disposal_clears_connection_pool(self, integration_db: str) -> None:
        """Engine disposal properly clears connection pool."""
        engine = get_engine()

        # Check initial pool status
        pool_status_before = engine.pool.status()
        assert pool_status_before is not None

        # Dispose engine
        await engine.dispose()

        # Verify disposal succeeded
        pool_status_after = engine.pool.status()
        assert pool_status_after is not None

    @pytest.mark.asyncio
    async def test_concurrent_connections_during_failover(self, integration_db: str) -> None:
        """Concurrent connections are handled correctly."""

        async def db_operation(session_id: int) -> int:
            async with get_session() as session:
                result = await session.execute(
                    text("SELECT :session_id as id").bindparams(session_id=session_id)
                )
                return result.scalar_one()

        # Run 10 concurrent operations
        tasks = [db_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        assert all(not isinstance(r, Exception) for r in results)
        assert results == list(range(10))


class TestRedisFailover:
    """Tests for Redis failover and reconnection."""

    @pytest.mark.asyncio
    async def test_redis_client_reconnects_after_disconnect(self) -> None:
        """Redis client reconnects after connection loss."""
        client = RedisClient()
        await client.connect()

        try:
            # Perform initial operation
            await client.set("test_key", "test_value")
            value = await client.get("test_key")
            assert value == "test_value"

            # Disconnect
            await client.disconnect()

            # Reconnect
            await client.connect()

            # Verify reconnection works
            await client.set("test_key2", "test_value2")
            value2 = await client.get("test_key2")
            assert value2 == "test_value2"

        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_redis_pubsub_reconnects_on_failure(self) -> None:
        """Redis pub/sub reconnects on connection failure."""
        client = RedisClient()
        await client.connect()

        try:
            # Subscribe to a channel
            pubsub = await client.subscribe("test_channel")
            assert pubsub is not None

            # Simulate reconnection
            await client.disconnect()
            await client.connect()

            # Verify can subscribe again
            pubsub2 = await client.subscribe("test_channel_2")
            assert pubsub2 is not None

        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_redis_connection_pool_exhaustion_recovery(self) -> None:
        """Pool survives sustained load and still serves requests after exhaustion.

        The shipped RedisClient (NEM-3368) uses redis-py's non-blocking pool:
        past `redis_pool_size` (default 50) checked-out connections it raises
        MaxConnectionsError immediately rather than queueing. So the fail-fast
        is the contract, and the disaster-recovery property that matters is
        that the pool is still healthy afterwards. The old assertion (100
        unbounded concurrent sets, >90% success) measured the pool cap and
        failed 50/100 deterministically.
        """
        client = RedisClient()
        await client.connect()

        keys = [f"dr_test:key_{i}" for i in range(100)]
        try:
            # Sustained load inside the pool capacity all succeeds
            capacity: int = client._pool.max_connections  # type: ignore[union-attr]
            window = asyncio.Semaphore(capacity)

            async def put(index: int) -> bool:
                async with window:
                    return await client.set(keys[index], f"value_{index}")

            results = await asyncio.gather(*(put(i) for i in range(100)))
            assert all(results), "writes within pool capacity must all succeed"

            # Exhausting the pool fails fast and LOUD — never silently queues
            beyond = await asyncio.gather(
                *(client.set(f"dr_test:beyond_{i}", "v") for i in range(capacity * 2)),
                return_exceptions=True,
            )
            errors = [r for r in beyond if isinstance(r, Exception)]
            assert errors, "pool exhaustion must raise, not block forever"
            assert all("MaxConnections" in type(e).__name__ for e in errors), errors[:3]

            # Recovery: the pool still serves ordinary requests afterwards
            assert await client.set("dr_test:after_recovery", "ok") is True
            assert await client.get("dr_test:after_recovery") == "ok"
        finally:
            await client.delete(*keys, "dr_test:after_recovery")
            await client.disconnect()


class TestDataCorruptionDetection:
    """Tests for detecting data integrity issues."""

    @pytest.mark.asyncio
    async def test_verify_foreign_key_constraints(self, integration_db: str) -> None:
        """Verify all foreign key constraints are properly defined."""
        async with get_session() as session:
            # Query pg_constraint to find all foreign keys
            result = await session.execute(
                text(
                    """
                    SELECT
                        tc.table_name,
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_schema = 'public'
                    ORDER BY tc.table_name, kcu.column_name
                """
                )
            )
            foreign_keys = result.fetchall()

            # Verify we have expected foreign keys
            assert len(foreign_keys) > 0

            # Check critical foreign keys exist
            fk_dict = {(row[0], row[1]): (row[2], row[3]) for row in foreign_keys}

            # detections.camera_id -> cameras.id
            assert ("detections", "camera_id") in fk_dict
            assert fk_dict[("detections", "camera_id")] == ("cameras", "id")

            # events.camera_id -> cameras.id
            assert ("events", "camera_id") in fk_dict
            assert fk_dict[("events", "camera_id")] == ("cameras", "id")

    @pytest.mark.asyncio
    async def test_detect_orphaned_records_query(self, integration_db: str) -> None:
        """Test query for detecting orphaned records."""
        # This tests the query pattern for finding orphaned records
        # In production, FK constraints prevent orphans, but this validates the detection query

        async with get_session() as session:
            # Query for orphaned detections (should be empty due to FK constraints)
            result = await session.execute(
                text(
                    """
                    SELECT d.id, d.camera_id
                    FROM detections d
                    LEFT JOIN cameras c ON d.camera_id = c.id
                    WHERE c.id IS NULL
                """
                )
            )
            orphaned_detections = result.fetchall()

            # Should be empty (FK constraints prevent orphans)
            assert len(orphaned_detections) == 0

            # Query for orphaned events (should be empty due to FK constraints)
            result = await session.execute(
                text(
                    """
                    SELECT e.id, e.camera_id
                    FROM events e
                    LEFT JOIN cameras c ON e.camera_id = c.id
                    WHERE c.id IS NULL
                """
                )
            )
            orphaned_events = result.fetchall()

            # Should be empty (FK constraints prevent orphans)
            assert len(orphaned_events) == 0


class TestCacheDatabaseConsistency:
    """Tests for cache and database consistency."""

    @pytest.mark.asyncio
    async def test_cache_invalidation_pattern(self) -> None:
        """CacheService.invalidate deletes the PREFIXED key (M3 T7).

        The old body awaited ``mock_redis.delete(cache_key)`` and asserted
        the mock saw its own argument — circular (audit 3.x). The shipped
        contract worth testing is that CacheService namespaces keys under
        ``CACHE_PREFIX`` and maps the Redis delete count to a bool, so the
        real service now runs with only the Redis I/O boundary mocked.
        """
        from backend.services.cache_service import CACHE_PREFIX, CacheService

        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.delete = AsyncMock(return_value=1)
        cache = CacheService(mock_redis)

        assert await cache.invalidate("camera:test_cam") is True

        mock_redis.delete.assert_awaited_once_with(f"{CACHE_PREFIX}camera:test_cam")

    @pytest.mark.asyncio
    async def test_cache_invalidation_reports_miss(self) -> None:
        """invalidate() returns False when Redis deleted nothing (T7 addition).

        The old test class asserted only the happy self-call; the shipped
        method's False path (deleted == 0) is the other half of its contract.
        """
        from backend.services.cache_service import CacheService

        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.delete = AsyncMock(return_value=0)

        assert await CacheService(mock_redis).invalidate("camera:absent") is False

    @pytest.mark.asyncio
    async def test_write_through_cache_pattern(self, integration_db: str) -> None:
        """Write-through: DB row lands AND cache.set writes the prefixed key.

        M3 T7: previously the cache half asserted a self-called AsyncMock.
        Now the real CacheService.set runs (JSON payload, default TTL), so
        the DB write and the cache write are both genuinely verified.
        """
        from backend.services.cache_service import CACHE_PREFIX, DEFAULT_TTL, CacheService

        # Create camera in database
        async with get_session() as session:
            camera = CameraFactory.build(id="cache_test_cam", name="Cache Test Camera")
            session.add(camera)
            await session.commit()

        # Write-through via the SHIPPED cache service
        mock_redis = AsyncMock(spec=RedisClient)
        cache = CacheService(mock_redis)
        cache_data = json.dumps({"id": camera.id, "name": camera.name})

        assert await cache.set(f"camera:{camera.id}", cache_data) is True

        mock_redis.set.assert_awaited_once()
        stored_key, stored_value = mock_redis.set.await_args.args
        assert stored_key == f"{CACHE_PREFIX}camera:{camera.id}"
        assert json.loads(stored_value) == {"id": camera.id, "name": camera.name}
        assert mock_redis.set.await_args.kwargs.get("expire") == DEFAULT_TTL

        # Verify database has the data
        async with get_session() as session:
            result = await session.execute(
                text("SELECT name FROM cameras WHERE id = :camera_id").bindparams(
                    camera_id=camera.id
                )
            )
            db_name = result.scalar_one()
            assert db_name == camera.name


class TestMigrationRollback:
    """Tests for migration rollback safety."""

    @pytest.mark.asyncio
    async def test_migration_rollback_preserves_data(self, integration_db: str) -> None:
        """Test that simulated migration rollback preserves existing data."""
        # Create test data
        async with get_session() as session:
            camera = CameraFactory.build(id="rollback_test_cam", name="Rollback Test Camera")
            session.add(camera)
            await session.commit()
            camera_id = camera.id

        # Simulate a migration that adds a column
        async with get_session() as session:
            await session.execute(
                text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS test_column VARCHAR(255)")
            )
            await session.commit()

        # Update the test column
        async with get_session() as session:
            await session.execute(
                text(
                    "UPDATE cameras SET test_column = 'test_value' WHERE id = :camera_id"
                ).bindparams(camera_id=camera_id)
            )
            await session.commit()

        # Simulate rollback by dropping the column
        async with get_session() as session:
            await session.execute(text("ALTER TABLE cameras DROP COLUMN IF EXISTS test_column"))
            await session.commit()

        # Verify original data is preserved
        async with get_session() as session:
            result = await session.execute(
                text("SELECT id, name FROM cameras WHERE id = :camera_id").bindparams(
                    camera_id=camera_id
                )
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == camera_id
            assert row[1] == "Rollback Test Camera"
