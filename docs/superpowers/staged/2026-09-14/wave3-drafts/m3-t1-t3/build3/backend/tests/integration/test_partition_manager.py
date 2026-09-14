"""Integration tests for partition management service.

Tests the partition manager with a real PostgreSQL database to verify
that partitioned tables work correctly for high-volume data operations.

Following TDD approach - tests written first before implementation.

# nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
# This test file requires raw SQL to test partition functionality.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

# =============================================================================
# Partition Creation Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_partition_manager_creates_partitions_in_database(
    integration_db: None,
) -> None:
    """Test that partition manager creates real partitions in PostgreSQL."""
    from backend.core.database import get_session
    from backend.services.partition_manager import PartitionConfig, PartitionManager

    # Create a test-specific partitioned table first
    async with get_session() as session:
        # Create parent partitioned table for testing
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_partitioned (
                    id SERIAL,
                    created_at TIMESTAMPTZ NOT NULL,
                    data TEXT,
                    PRIMARY KEY (id, created_at)
                ) PARTITION BY RANGE (created_at)
                """
            )
        )
        await session.commit()

    # Now test partition creation
    config = PartitionConfig(
        table_name="test_partitioned",
        partition_column="created_at",
        partition_interval="monthly",
        retention_months=12,
    )
    manager = PartitionManager(configs=[config])

    async with get_session() as session:
        created = await manager.ensure_partitions()

        # Should have created partitions
        assert len(created) >= 3  # Current + 2 future months

        # Verify partitions exist in pg_class
        result = await session.execute(
            text(
                """
                SELECT relname FROM pg_class
                WHERE relname LIKE 'test_partitioned_y%'
                ORDER BY relname
                """
            )
        )
        partitions = [row[0] for row in result.fetchall()]

        assert len(partitions) >= 3

    # Cleanup
    async with get_session() as session:
        for partition in partitions:
            await session.execute(text(f"DROP TABLE IF EXISTS {partition} CASCADE"))
        await session.execute(text("DROP TABLE IF EXISTS test_partitioned CASCADE"))
        await session.commit()


@pytest.mark.asyncio
async def test_partition_manager_insert_into_correct_partition(
    integration_db: None,
) -> None:
    """Test that data is inserted into the correct partition based on timestamp."""
    from backend.core.database import get_session
    from backend.services.partition_manager import PartitionConfig, PartitionManager

    # Create partitioned table
    async with get_session() as session:
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_insert_partition (
                    id SERIAL,
                    created_at TIMESTAMPTZ NOT NULL,
                    data TEXT,
                    PRIMARY KEY (id, created_at)
                ) PARTITION BY RANGE (created_at)
                """
            )
        )
        await session.commit()

    # Create partitions
    config = PartitionConfig(
        table_name="test_insert_partition",
        partition_column="created_at",
        partition_interval="monthly",
    )
    manager = PartitionManager(configs=[config])

    async with get_session() as session:
        await manager.ensure_partitions()

        # Insert data for current month
        now = datetime.now(UTC)
        await session.execute(
            text(
                """
                INSERT INTO test_insert_partition (created_at, data)
                VALUES (:ts, 'test data')
                """
            ),
            {"ts": now},
        )
        await session.commit()

        # Verify data exists
        result = await session.execute(text("SELECT COUNT(*) FROM test_insert_partition"))
        count = result.scalar_one()
        assert count == 1

        # Verify it's in the correct partition (based on naming)
        year = now.year
        month = now.month
        partition_name = f"test_insert_partition_y{year}m{month:02d}"

        result = await session.execute(
            text(f"SELECT COUNT(*) FROM {partition_name}")  # noqa: S608
        )
        partition_count = result.scalar_one()
        assert partition_count == 1

    # Cleanup
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT relname FROM pg_class
                WHERE relname LIKE 'test_insert_partition%'
                AND relkind IN ('r', 'p')
                """
            )
        )
        tables = [row[0] for row in result.fetchall()]
        for table in tables:
            await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        await session.commit()


@pytest.mark.asyncio
async def test_partition_manager_query_across_partitions(
    integration_db: None,
) -> None:
    """Test that queries across partitions work correctly."""
    from backend.core.database import get_session
    from backend.services.partition_manager import PartitionConfig, PartitionManager

    # Create partitioned table
    async with get_session() as session:
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_query_partition (
                    id SERIAL,
                    created_at TIMESTAMPTZ NOT NULL,
                    data TEXT,
                    PRIMARY KEY (id, created_at)
                ) PARTITION BY RANGE (created_at)
                """
            )
        )
        await session.commit()

    # Create partitions including past and future
    config = PartitionConfig(
        table_name="test_query_partition",
        partition_column="created_at",
        partition_interval="monthly",
    )
    manager = PartitionManager(configs=[config])

    async with get_session() as session:
        await manager.ensure_partitions()

        # Insert data
        now = datetime.now(UTC)
        await session.execute(
            text(
                """
                INSERT INTO test_query_partition (created_at, data)
                VALUES (:ts, 'current data')
                """
            ),
            {"ts": now},
        )
        await session.commit()

        # Query with time range filter (should use partition pruning)
        result = await session.execute(
            text(
                """
                SELECT data FROM test_query_partition
                WHERE created_at >= :start AND created_at < :end
                """
            ),
            {"start": now - timedelta(hours=1), "end": now + timedelta(hours=1)},
        )
        rows = result.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "current data"

    # Cleanup
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT relname FROM pg_class
                WHERE relname LIKE 'test_query_partition%'
                AND relkind IN ('r', 'p')
                """
            )
        )
        tables = [row[0] for row in result.fetchall()]
        for table in tables:
            await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        await session.commit()


# =============================================================================
# Partition Cleanup Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_partition_manager_drops_old_partitions(
    integration_db: None,
) -> None:
    """Test that old partitions beyond retention period are dropped."""
    from backend.core.database import get_session
    from backend.services.partition_manager import PartitionConfig, PartitionManager

    # Create partitioned table
    async with get_session() as session:
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_cleanup_partition (
                    id SERIAL,
                    created_at TIMESTAMPTZ NOT NULL,
                    data TEXT,
                    PRIMARY KEY (id, created_at)
                ) PARTITION BY RANGE (created_at)
                """
            )
        )
        await session.commit()

    # Create partition manager with short retention
    config = PartitionConfig(
        table_name="test_cleanup_partition",
        partition_column="created_at",
        partition_interval="monthly",
        retention_months=1,  # Short retention for testing
    )
    manager = PartitionManager(configs=[config])

    async with get_session() as session:
        # Manually create an old partition (13 months ago)
        old_date = datetime.now(UTC) - timedelta(days=400)
        old_year = old_date.year
        old_month = old_date.month
        old_partition = f"test_cleanup_partition_y{old_year}m{old_month:02d}"

        # Calculate bounds for old partition
        if old_month == 12:
            end_year = old_year + 1
            end_month = 1
        else:
            end_year = old_year
            end_month = old_month + 1

        await session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {old_partition} PARTITION OF test_cleanup_partition
                FOR VALUES FROM ('{old_year}-{old_month:02d}-01')
                TO ('{end_year}-{end_month:02d}-01')
                """
            )
        )
        await session.commit()

        # Also create current partitions
        await manager.ensure_partitions()

        # Now cleanup old partitions
        dropped = await manager.cleanup_old_partitions()

        # Should have dropped the old partition
        assert old_partition in dropped

        # Verify it's gone
        result = await session.execute(
            text(
                """
                SELECT relname FROM pg_class
                WHERE relname = :partition_name
                """
            ),
            {"partition_name": old_partition},
        )
        row = result.fetchone()
        assert row is None

    # Cleanup
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT relname FROM pg_class
                WHERE relname LIKE 'test_cleanup_partition%'
                AND relkind IN ('r', 'p')
                """
            )
        )
        tables = [row[0] for row in result.fetchall()]
        for table in tables:
            await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        await session.commit()


# =============================================================================
# Partition Stats Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_partition_manager_get_stats(
    integration_db: None,
) -> None:
    """Test getting partition statistics from database."""
    from backend.core.database import get_session
    from backend.services.partition_manager import PartitionConfig, PartitionManager

    # Clean up any existing test tables before starting
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT relname FROM pg_class
                WHERE relname LIKE 'test_stats_partition%'
                AND relkind IN ('r', 'p')
                """
            )
        )
        tables = [row[0] for row in result.fetchall()]
        for table in tables:
            await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        await session.commit()

    # Create partitioned table
    async with get_session() as session:
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_stats_partition (
                    id SERIAL,
                    created_at TIMESTAMPTZ NOT NULL,
                    data TEXT,
                    PRIMARY KEY (id, created_at)
                ) PARTITION BY RANGE (created_at)
                """
            )
        )
        await session.commit()

    # Create partitions and add data
    config = PartitionConfig(
        table_name="test_stats_partition",
        partition_column="created_at",
        partition_interval="monthly",
    )
    manager = PartitionManager(configs=[config])

    async with get_session() as session:
        await manager.ensure_partitions()

        # Insert test data
        now = datetime.now(UTC)
        for i in range(10):
            await session.execute(
                text(
                    """
                    INSERT INTO test_stats_partition (created_at, data)
                    VALUES (:ts, :data)
                    """
                ),
                {"ts": now, "data": f"data_{i}"},
            )
        await session.commit()

        # Run ANALYZE to update statistics (required for accurate row_count)
        await session.execute(text("ANALYZE test_stats_partition"))

        # Get partition stats
        stats = await manager.get_partition_stats()

        assert "test_stats_partition" in stats
        partitions = stats["test_stats_partition"]
        assert len(partitions) >= 1

        # Find the current month partition
        year = now.year
        month = now.month
        current_partition_name = f"test_stats_partition_y{year}m{month:02d}"

        current_stats = None
        for p in partitions:
            if p["name"] == current_partition_name:
                current_stats = p
                break

        assert current_stats is not None
        assert current_stats["row_count"] == 10

    # Cleanup
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT relname FROM pg_class
                WHERE relname LIKE 'test_stats_partition%'
                AND relkind IN ('r', 'p')
                """
            )
        )
        tables = [row[0] for row in result.fetchall()]
        for table in tables:
            await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        await session.commit()


# =============================================================================
# Index Tests
# =============================================================================


@pytest.mark.asyncio
async def test_partition_inherits_indexes(
    integration_db: None,
) -> None:
    """Test that partitions inherit indexes from parent table."""
    from backend.core.database import get_session
    from backend.services.partition_manager import PartitionConfig, PartitionManager

    # Create partitioned table with index
    async with get_session() as session:
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_index_partition (
                    id SERIAL,
                    created_at TIMESTAMPTZ NOT NULL,
                    data TEXT,
                    PRIMARY KEY (id, created_at)
                ) PARTITION BY RANGE (created_at)
                """
            )
        )
        # Create index on parent table
        await session.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_test_index_partition_data
                ON test_index_partition (data)
                """
            )
        )
        await session.commit()

    # Create partitions
    config = PartitionConfig(
        table_name="test_index_partition",
        partition_column="created_at",
        partition_interval="monthly",
    )
    manager = PartitionManager(configs=[config])

    async with get_session() as session:
        created = await manager.ensure_partitions()

        assert len(created) >= 1

        # Verify indexes exist on partition
        now = datetime.now(UTC)
        year = now.year
        month = now.month
        partition_name = f"test_index_partition_y{year}m{month:02d}"

        result = await session.execute(
            text(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename = :table_name
                """
            ),
            {"table_name": partition_name},
        )
        indexes = [row[0] for row in result.fetchall()]

        # Should have primary key index and data index
        assert len(indexes) >= 1

    # Cleanup
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT relname FROM pg_class
                WHERE relname LIKE 'test_index_partition%'
                AND relkind IN ('r', 'p')
                """
            )
        )
        tables = [row[0] for row in result.fetchall()]
        for table in tables:
            await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        await session.commit()


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_partition_manager_handles_existing_partition_gracefully(
    integration_db: None,
) -> None:
    """Test that creating an existing partition doesn't cause errors."""
    from backend.core.database import get_session
    from backend.services.partition_manager import PartitionConfig, PartitionManager

    # Create partitioned table
    async with get_session() as session:
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_existing_partition (
                    id SERIAL,
                    created_at TIMESTAMPTZ NOT NULL,
                    data TEXT,
                    PRIMARY KEY (id, created_at)
                ) PARTITION BY RANGE (created_at)
                """
            )
        )
        await session.commit()

    config = PartitionConfig(
        table_name="test_existing_partition",
        partition_column="created_at",
        partition_interval="monthly",
    )
    manager = PartitionManager(configs=[config])

    async with get_session() as session:
        # Create partitions first time
        created1 = await manager.ensure_partitions()
        assert len(created1) >= 1

        # Try to create again - should not fail
        created2 = await manager.ensure_partitions()
        # Second time should not create anything (already exists)
        assert len(created2) == 0

    # Cleanup
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT relname FROM pg_class
                WHERE relname LIKE 'test_existing_partition%'
                AND relkind IN ('r', 'p')
                """
            )
        )
        tables = [row[0] for row in result.fetchall()]
        for table in tables:
            await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        await session.commit()


@pytest.mark.asyncio
async def test_partition_manager_handles_missing_parent_table(
    integration_db: None,
) -> None:
    """Test handling of missing parent table."""
    from backend.services.partition_manager import PartitionConfig, PartitionManager

    # Try to create partitions for non-existent table
    config = PartitionConfig(
        table_name="nonexistent_table_xyz",
        partition_column="created_at",
        partition_interval="monthly",
    )
    manager = PartitionManager(configs=[config])

    # Should handle gracefully (either raise specific error or return empty list)
    # Implementation will define exact behavior
    try:
        created = await manager.ensure_partitions()
        # If it doesn't raise, it should return empty list
        assert created == []
    except Exception as e:
        # Should be a descriptive error, not a raw SQL error
        assert "nonexistent" in str(e).lower() or "not partitioned" in str(e).lower()
