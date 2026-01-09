"""Slow query detection tests for CI enforcement.

These tests verify that API operations don't produce slow queries.
Used as a CI gate to catch performance regressions that introduce slow queries.

The tests work by:
1. Setting a strict slow query threshold (50ms)
2. Running representative API operations
3. Capturing any slow query warnings
4. Failing if slow queries are detected

Usage:
    pytest tests/benchmarks/test_slow_query_detection.py -v
    pytest tests/benchmarks/test_slow_query_detection.py --slow-query-threshold=100

Environment:
    SLOW_QUERY_THRESHOLD_MS: Override the threshold (default: 50ms for tests)
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


# Slow query threshold for CI tests (stricter than production default)
CI_SLOW_QUERY_THRESHOLD_MS = 50.0


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def slow_query_test_env() -> Generator[str]:
    """Set up test environment with strict slow query threshold."""
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")
    original_runtime_env_path = os.environ.get("HSI_RUNTIME_ENV_PATH")
    original_threshold = os.environ.get("SLOW_QUERY_THRESHOLD_MS")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "slow_query_test.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"
        runtime_env_path = str(Path(tmpdir) / "runtime.env")

        os.environ["DATABASE_URL"] = test_db_url
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"
        os.environ["HSI_RUNTIME_ENV_PATH"] = runtime_env_path
        os.environ["SLOW_QUERY_THRESHOLD_MS"] = str(CI_SLOW_QUERY_THRESHOLD_MS)

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

            if original_threshold is not None:
                os.environ["SLOW_QUERY_THRESHOLD_MS"] = original_threshold
            else:
                os.environ.pop("SLOW_QUERY_THRESHOLD_MS", None)

            get_settings.cache_clear()


@pytest.fixture
async def slow_query_test_db(slow_query_test_env: str) -> AsyncGenerator[str]:
    """Initialize a temporary SQLite DB for slow query tests."""
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    get_settings.cache_clear()
    await close_db()
    await init_db()

    try:
        yield slow_query_test_env
    finally:
        await close_db()
        get_settings.cache_clear()


@pytest.fixture
def mock_redis_for_slow_query() -> Generator[AsyncMock]:
    """Mock Redis operations for slow query tests."""
    mock_redis = AsyncMock()
    mock_redis.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    with (
        patch("backend.core.redis._redis_client", mock_redis),
        patch("backend.core.redis.init_redis", return_value=mock_redis),
    ):
        yield mock_redis


class SlowQueryCapture:
    """Capture slow query log messages for assertion."""

    def __init__(self) -> None:
        self.slow_queries: list[dict] = []
        self._handler: logging.Handler | None = None

    def start(self) -> None:
        """Start capturing slow query logs."""
        self.slow_queries = []

        class CaptureHandler(logging.Handler):
            def __init__(handler_self, capture: SlowQueryCapture) -> None:
                super().__init__()
                handler_self.capture = capture

            def emit(handler_self, record: logging.LogRecord) -> None:
                if "Slow query" in record.getMessage() or "slow_query" in str(
                    getattr(record, "extra", {})
                ):
                    handler_self.capture.slow_queries.append(
                        {
                            "message": record.getMessage(),
                            "extra": getattr(record, "extra", {}),
                            "level": record.levelname,
                        }
                    )

        self._handler = CaptureHandler(self)

        # Add handler to database and query_explain loggers
        for logger_name in ["backend.core.database", "backend.core.query_explain"]:
            logger = logging.getLogger(logger_name)
            logger.addHandler(self._handler)
            logger.setLevel(logging.WARNING)

    def stop(self) -> None:
        """Stop capturing slow query logs."""
        if self._handler:
            for logger_name in ["backend.core.database", "backend.core.query_explain"]:
                logger = logging.getLogger(logger_name)
                logger.removeHandler(self._handler)
            self._handler = None


@contextmanager
def capture_slow_queries():
    """Context manager to capture slow query log messages."""
    capture = SlowQueryCapture()
    capture.start()
    try:
        yield capture
    finally:
        capture.stop()


def run_async(coro):
    """Run an async coroutine in a sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =============================================================================
# Slow Query Detection Tests
# =============================================================================


@pytest.mark.slow
class TestSlowQueryDetection:
    """Tests that verify no slow queries occur during common operations."""

    @pytest.mark.asyncio
    async def test_simple_select_no_slow_query(self, slow_query_test_db: str) -> None:
        """Test that simple SELECT queries don't trigger slow query warnings."""
        from sqlalchemy import text

        from backend.core.database import get_async_session

        with capture_slow_queries() as capture:
            for _ in range(10):
                async with get_async_session() as session:
                    result = await session.execute(text("SELECT 1"))
                    _ = result.scalar()

        assert len(capture.slow_queries) == 0, f"Slow queries detected: {capture.slow_queries}"

    @pytest.mark.asyncio
    async def test_concurrent_selects_no_slow_query(self, slow_query_test_db: str) -> None:
        """Test that concurrent SELECT queries don't trigger slow query warnings."""
        from sqlalchemy import text

        from backend.core.database import get_async_session

        async def single_query():
            async with get_async_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar()

        with capture_slow_queries() as capture:
            tasks = [single_query() for _ in range(20)]
            await asyncio.gather(*tasks)

        assert len(capture.slow_queries) == 0, f"Slow queries detected: {capture.slow_queries}"

    @pytest.mark.asyncio
    async def test_session_creation_no_slow_query(self, slow_query_test_db: str) -> None:
        """Test that session creation doesn't trigger slow query warnings."""
        from backend.core.database import get_async_session

        with capture_slow_queries() as capture:
            for _ in range(20):
                async with get_async_session() as session:
                    pass  # Just open and close session

        assert len(capture.slow_queries) == 0, f"Slow queries detected: {capture.slow_queries}"


# =============================================================================
# Slow Query Threshold Verification Tests
# =============================================================================


@pytest.mark.slow
class TestSlowQueryThresholdVerification:
    """Tests that verify slow query detection works correctly."""

    @pytest.mark.asyncio
    async def test_slow_query_is_detected(self, slow_query_test_db: str) -> None:
        """Test that deliberately slow queries are detected.

        This test verifies that the slow query detection mechanism works
        by simulating a slow query scenario.
        """
        import time

        from backend.core.database import (
            _after_cursor_execute,
            _before_cursor_execute,
        )

        # Create a mock connection with info dict
        class MockConnection:
            def __init__(self):
                self.info = {}

        mock_conn = MockConnection()

        # Simulate a query that takes longer than threshold
        _before_cursor_execute(
            mock_conn,
            None,  # cursor
            "SELECT * FROM events WHERE id = 1",
            None,
            None,
            False,
        )

        # Manually set start time to simulate slow query
        mock_conn.info["query_start_time"] = time.perf_counter() - 0.1  # 100ms ago

        # The after_cursor_execute should detect this as slow
        # We use patch to capture the logging
        with (
            patch("backend.core.database.get_settings") as mock_settings,
            patch("backend.core.database._logger") as mock_logger,
            patch("backend.core.metrics.observe_db_query_duration"),
            patch("backend.core.metrics.record_slow_query"),
        ):
            mock_settings.return_value = type(
                "Settings", (), {"slow_query_threshold_ms": CI_SLOW_QUERY_THRESHOLD_MS}
            )()

            _after_cursor_execute(
                mock_conn,
                None,  # cursor
                "SELECT * FROM events WHERE id = 1",
                None,
                None,
                False,
            )

            # Verify warning was logged
            mock_logger.warning.assert_called()


# =============================================================================
# API Operation Slow Query Tests
# =============================================================================


@pytest.mark.slow
class TestAPIOperationSlowQueries:
    """Tests that verify API operations don't produce slow queries.

    These tests use the test client to make actual API requests and
    verify that no slow queries are generated.
    """

    @pytest.mark.asyncio
    async def test_health_endpoint_no_slow_query(
        self,
        slow_query_test_db: str,
        mock_redis_for_slow_query: AsyncMock,
    ) -> None:
        """Test that health endpoint doesn't trigger slow queries."""
        from httpx import ASGITransport, AsyncClient

        from backend.main import app

        with capture_slow_queries() as capture:
            with (
                patch("backend.main.init_db", return_value=None),
                patch("backend.main.close_db", return_value=None),
                patch("backend.main.init_redis", return_value=mock_redis_for_slow_query),
                patch("backend.main.close_redis", return_value=None),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    for _ in range(5):
                        response = await client.get("/")
                        assert response.status_code == 200

        assert len(capture.slow_queries) == 0, (
            f"Slow queries detected in health endpoint: {capture.slow_queries}"
        )

    @pytest.mark.asyncio
    async def test_cameras_endpoint_no_slow_query(
        self,
        slow_query_test_db: str,
        mock_redis_for_slow_query: AsyncMock,
    ) -> None:
        """Test that cameras endpoint doesn't trigger slow queries."""
        from httpx import ASGITransport, AsyncClient

        from backend.main import app

        with capture_slow_queries() as capture:
            with (
                patch("backend.main.init_db", return_value=None),
                patch("backend.main.close_db", return_value=None),
                patch("backend.main.init_redis", return_value=mock_redis_for_slow_query),
                patch("backend.main.close_redis", return_value=None),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    for _ in range(5):
                        response = await client.get("/api/cameras")
                        # 200 or 401 (auth) are both valid
                        assert response.status_code in [200, 401]

        assert len(capture.slow_queries) == 0, (
            f"Slow queries detected in cameras endpoint: {capture.slow_queries}"
        )
