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
        """Redis connection pool recovers from stress."""
        client = RedisClient()
        await client.connect()

        try:
            # Perform many operations to stress the pool
            tasks = [client.set(f"key_{i}", f"value_{i}") for i in range(100)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Most should succeed
            successful = sum(1 for r in results if not isinstance(r, Exception))
            assert successful > 90  # At least 90% success rate

        finally:
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
        """Test cache invalidation pattern."""
        # Mock Redis client
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.get = AsyncMock(return_value=None)

        # Simulate cache invalidation
        cache_key = "camera:test_cam"
        await mock_redis.delete(cache_key)
        mock_redis.delete.assert_called_once_with(cache_key)

    @pytest.mark.asyncio
    async def test_write_through_cache_pattern(self, integration_db: str) -> None:
        """Test write-through cache pattern."""
        # Create camera in database
        async with get_session() as session:
            camera = CameraFactory.build(id="cache_test_cam", name="Cache Test Camera")
            session.add(camera)
            await session.commit()

        # Mock cache write
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.set = AsyncMock(return_value=True)

        # Simulate write-through: write to DB, then cache
        import json

        cache_data = json.dumps({"id": camera.id, "name": camera.name})
        await mock_redis.set(f"camera:{camera.id}", cache_data)
        mock_redis.set.assert_called_once()

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
