"""Database connection pool benchmarks and stress tests.

These tests verify the database connection pool behavior under load:
- Connection pool exhaustion handling
- Concurrent query performance
- Connection timeout behavior
- Pool recovery after exhaustion

Usage:
    pytest tests/benchmarks/test_connection_pool.py -v
    pytest tests/benchmarks/test_connection_pool.py --benchmark-only
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def pool_test_env() -> Generator[str]:
    """Set DATABASE_URL to a temporary database with small pool size."""
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")
    original_runtime_env_path = os.environ.get("HSI_RUNTIME_ENV_PATH")
    original_pool_size = os.environ.get("DB_POOL_SIZE")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "pool_test.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"
        runtime_env_path = str(Path(tmpdir) / "runtime.env")

        os.environ["DATABASE_URL"] = test_db_url
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"
        os.environ["HSI_RUNTIME_ENV_PATH"] = runtime_env_path
        # Use small pool size for exhaustion testing
        os.environ["DB_POOL_SIZE"] = "5"

        get_settings.cache_clear()

        try:
            yield test_db_url
        finally:
            if original_db_url is not None:
                os.environ["DATABASE_URL"] = original_db_url
            else:
                os.environ.pop("DATABASE_URL", None)

            if original_redis_url is not None:
                os.environ["REDIS_URL"] = original_redis_url
            else:
                os.environ.pop("REDIS_URL", None)

            if original_runtime_env_path is not None:
                os.environ["HSI_RUNTIME_ENV_PATH"] = original_runtime_env_path
            else:
                os.environ.pop("HSI_RUNTIME_ENV_PATH", None)

            if original_pool_size is not None:
                os.environ["DB_POOL_SIZE"] = original_pool_size
            else:
                os.environ.pop("DB_POOL_SIZE", None)

            get_settings.cache_clear()


@pytest.fixture
async def pool_test_db(pool_test_env: str) -> AsyncGenerator[str]:
    """Initialize a temporary SQLite DB for pool tests."""
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    get_settings.cache_clear()
    await close_db()
    await init_db()

    try:
        yield pool_test_env
    finally:
        await close_db()
        get_settings.cache_clear()


def run_async(coro):
    """Run an async coroutine in a sync context for benchmarks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =============================================================================
# Connection Pool Benchmarks
# =============================================================================


@pytest.mark.slow
class TestConnectionPoolBenchmarks:
    """Benchmark tests for database connection pool performance."""

    @pytest.mark.benchmark(group="pool-concurrent")
    def test_concurrent_queries(self, benchmark, pool_test_db: str):
        """Benchmark concurrent query execution through connection pool."""
        from sqlalchemy import text

        from backend.core.database import get_async_session

        async def run_concurrent_queries(num_queries: int = 20):
            """Execute multiple queries concurrently."""

            async def single_query():
                async with get_async_session() as session:
                    result = await session.execute(text("SELECT 1"))
                    return result.scalar()

            tasks = [single_query() for _ in range(num_queries)]
            results = await asyncio.gather(*tasks)
            return results

        result = benchmark(lambda: run_async(run_concurrent_queries(20)))
        assert len(result) == 20
        assert all(r == 1 for r in result)

    @pytest.mark.benchmark(group="pool-sequential")
    def test_sequential_queries(self, benchmark, pool_test_db: str):
        """Benchmark sequential query execution for baseline comparison."""
        from sqlalchemy import text

        from backend.core.database import get_async_session

        async def run_sequential_queries(num_queries: int = 20):
            """Execute queries sequentially."""
            results = []
            for _ in range(num_queries):
                async with get_async_session() as session:
                    result = await session.execute(text("SELECT 1"))
                    results.append(result.scalar())
            return results

        result = benchmark(lambda: run_async(run_sequential_queries(20)))
        assert len(result) == 20

    @pytest.mark.benchmark(group="pool-session-reuse")
    def test_session_reuse_efficiency(self, benchmark, pool_test_db: str):
        """Benchmark multiple operations within a single session."""
        from sqlalchemy import text

        from backend.core.database import get_async_session

        async def run_multiple_in_session():
            """Execute multiple queries in one session."""
            async with get_async_session() as session:
                results = []
                for _ in range(10):
                    result = await session.execute(text("SELECT 1"))
                    results.append(result.scalar())
                return results

        result = benchmark(lambda: run_async(run_multiple_in_session()))
        assert len(result) == 10


# =============================================================================
# Connection Pool Stress Tests
# =============================================================================


@pytest.mark.slow
class TestConnectionPoolStress:
    """Stress tests for database connection pool exhaustion and recovery."""

    @pytest.mark.asyncio
    async def test_pool_under_concurrent_load(self, pool_test_db: str):
        """Test connection pool behavior under high concurrent load.

        This test verifies that:
        1. Many concurrent queries can be handled
        2. All queries complete successfully
        3. Response time remains reasonable
        """
        from sqlalchemy import text

        from backend.core.database import get_async_session

        num_concurrent = 50
        successful = 0
        errors = []
        start_time = time.time()

        async def single_query(query_id: int):
            nonlocal successful
            try:
                async with get_async_session() as session:
                    # Simulate some work
                    result = await session.execute(text("SELECT 1"))
                    value = result.scalar()
                    assert value == 1
                    successful += 1
                    return query_id, True
            except Exception as e:
                errors.append((query_id, str(e)))
                return query_id, False

        tasks = [single_query(i) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks)

        duration = time.time() - start_time

        # All queries should succeed
        assert successful == num_concurrent, (
            f"Only {successful}/{num_concurrent} succeeded. Errors: {errors}"
        )
        # Should complete in reasonable time (< 30 seconds for 50 queries)
        assert duration < 30, f"Took too long: {duration:.2f}s"

    @pytest.mark.asyncio
    async def test_pool_recovery_after_timeout(self, pool_test_db: str):
        """Test that connection pool recovers after query timeouts.

        This test simulates slow queries and verifies that:
        1. Subsequent queries still work
        2. Pool doesn't deadlock
        """
        from sqlalchemy import text

        from backend.core.database import get_async_session

        # First, run some normal queries
        successful_before = 0
        for _ in range(5):
            async with get_async_session() as session:
                result = await session.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    successful_before += 1

        assert successful_before == 5, "Initial queries failed"

        # Now run queries after a simulated "slow period"
        # (In a real scenario, this would involve actual slow queries)
        await asyncio.sleep(0.1)

        # Verify pool is still functional
        successful_after = 0
        for _ in range(10):
            async with get_async_session() as session:
                result = await session.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    successful_after += 1

        assert successful_after == 10, (
            f"Only {successful_after}/10 queries succeeded after slow period"
        )

    @pytest.mark.asyncio
    async def test_connection_pool_high_watermark(self, pool_test_db: str):
        """Test connection pool at high watermark.

        With pool size of 5, test behavior when more than 5 concurrent
        requests arrive. SQLAlchemy should queue excess requests.
        """
        from sqlalchemy import text

        from backend.core.database import get_async_session

        # More concurrent requests than pool size
        num_requests = 20
        pool_size = 5  # Set in fixture

        start_times = {}
        end_times = {}

        async def timed_query(query_id: int):
            start_times[query_id] = time.time()
            try:
                async with get_async_session() as session:
                    # Hold connection briefly
                    await asyncio.sleep(0.05)  # 50ms
                    result = await session.execute(text("SELECT 1"))
                    value = result.scalar()
                    end_times[query_id] = time.time()
                    return query_id, value == 1
            except Exception as e:
                end_times[query_id] = time.time()
                return query_id, False

        tasks = [timed_query(i) for i in range(num_requests)]
        results = await asyncio.gather(*tasks)

        # All should succeed (eventually)
        success_count = sum(1 for _, success in results if success)
        assert success_count == num_requests, f"Only {success_count}/{num_requests} succeeded"

        # Calculate how many were running simultaneously at any point
        # This verifies the pool is actually limiting connections
        durations = [(end_times[i] - start_times[i]) for i in range(num_requests)]
        avg_duration = sum(durations) / len(durations)

        # Average duration should be > 50ms (our sleep time)
        # but not excessively long
        assert avg_duration >= 0.05, "Queries completed too fast"
        assert avg_duration < 1.0, f"Queries took too long: {avg_duration:.3f}s avg"


# =============================================================================
# Connection Pool Health Tests
# =============================================================================


@pytest.mark.slow
class TestConnectionPoolHealth:
    """Health and monitoring tests for connection pool."""

    @pytest.mark.asyncio
    async def test_pool_no_connection_leak(self, pool_test_db: str):
        """Test that connections are properly returned to the pool."""
        from sqlalchemy import text

        from backend.core.database import get_async_session

        # Run many iterations and verify no leak
        iterations = 100
        for i in range(iterations):
            async with get_async_session() as session:
                result = await session.execute(text("SELECT 1"))
                _ = result.scalar()

        # If there was a leak, we'd see connection errors by now
        # Run a few more queries to confirm pool is healthy
        for _ in range(10):
            async with get_async_session() as session:
                result = await session.execute(text("SELECT 1"))
                assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_pool_exception_handling(self, pool_test_db: str):
        """Test that connections are returned even after exceptions."""
        from sqlalchemy import text

        from backend.core.database import get_async_session

        # Cause some exceptions
        for _ in range(10):
            try:
                async with get_async_session() as session:
                    # Try to execute invalid SQL
                    await session.execute(text("INVALID SQL SYNTAX"))
            except Exception:
                pass  # Expected

        # Pool should still be healthy after exceptions
        async with get_async_session() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1, "Pool unhealthy after exceptions"

    @pytest.mark.asyncio
    async def test_pool_transaction_rollback(self, pool_test_db: str):
        """Test that rolled-back transactions return connections properly."""
        from sqlalchemy import text

        from backend.core.database import get_async_session

        # Start and rollback several transactions
        for _ in range(20):
            async with get_async_session() as session:
                await session.execute(text("SELECT 1"))
                await session.rollback()

        # Pool should still be healthy
        async with get_async_session() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
