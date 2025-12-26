"""API endpoint benchmarks for regression detection.

These benchmarks measure response times for critical API endpoints
and fail if performance degrades significantly from baseline.

Usage:
    pytest tests/benchmarks/test_api_benchmarks.py --benchmark-only
    pytest tests/benchmarks/test_api_benchmarks.py --benchmark-compare
    pytest tests/benchmarks/test_api_benchmarks.py --benchmark-compare-fail=mean:20%
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


@pytest.fixture
def benchmark_env() -> Generator[str, None, None]:
    """Set DATABASE_URL/REDIS_URL to a temporary per-test database."""
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")
    original_runtime_env_path = os.environ.get("HSI_RUNTIME_ENV_PATH")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "benchmark_test.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"
        runtime_env_path = str(Path(tmpdir) / "runtime.env")

        os.environ["DATABASE_URL"] = test_db_url
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"
        os.environ["HSI_RUNTIME_ENV_PATH"] = runtime_env_path

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

            get_settings.cache_clear()


@pytest.fixture
async def benchmark_db(benchmark_env: str) -> AsyncGenerator[str, None]:
    """Initialize a temporary SQLite DB for benchmark tests."""
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    get_settings.cache_clear()
    await close_db()
    await init_db()

    try:
        yield benchmark_env
    finally:
        await close_db()
        get_settings.cache_clear()


@pytest.fixture
async def mock_redis_client() -> AsyncGenerator[AsyncMock, None]:
    """Mock Redis operations for benchmarks."""
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


@pytest.fixture
async def benchmark_client(
    benchmark_db: str,
    mock_redis_client: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for benchmark tests."""
    from backend.main import app

    with (
        patch("backend.main.init_db", return_value=None),
        patch("backend.main.close_db", return_value=None),
        patch("backend.main.init_redis", return_value=mock_redis_client),
        patch("backend.main.close_redis", return_value=None),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


def run_async(coro):
    """Run an async coroutine in a sync context for benchmarks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.mark.slow
class TestAPIBenchmarks:
    """Benchmark tests for API endpoints."""

    @pytest.mark.benchmark(group="api-health")
    def test_health_endpoint_benchmark(self, benchmark, benchmark_client: AsyncClient):
        """Benchmark GET / health check endpoint."""

        async def fetch_health():
            response = await benchmark_client.get("/")
            return response

        result = benchmark(lambda: run_async(fetch_health()))
        assert result.status_code == 200

    @pytest.mark.benchmark(group="api-health")
    def test_detailed_health_benchmark(self, benchmark, benchmark_client: AsyncClient):
        """Benchmark GET /health detailed health check endpoint."""

        async def fetch_detailed_health():
            response = await benchmark_client.get("/health")
            return response

        result = benchmark(lambda: run_async(fetch_detailed_health()))
        assert result.status_code == 200

    @pytest.mark.benchmark(group="api-cameras")
    def test_cameras_list_benchmark(self, benchmark, benchmark_client: AsyncClient):
        """Benchmark GET /api/cameras endpoint."""

        async def fetch_cameras():
            response = await benchmark_client.get("/api/cameras")
            return response

        result = benchmark(lambda: run_async(fetch_cameras()))
        # 200 (success) or 401 (auth required) are both valid
        assert result.status_code in [200, 401]

    @pytest.mark.benchmark(group="api-events")
    def test_events_list_benchmark(self, benchmark, benchmark_client: AsyncClient):
        """Benchmark GET /api/events endpoint."""

        async def fetch_events():
            response = await benchmark_client.get("/api/events?limit=50")
            return response

        result = benchmark(lambda: run_async(fetch_events()))
        assert result.status_code in [200, 401]

    @pytest.mark.benchmark(group="api-system")
    def test_system_status_benchmark(self, benchmark, benchmark_client: AsyncClient):
        """Benchmark GET /api/system/status endpoint."""

        async def fetch_status():
            response = await benchmark_client.get("/api/system/status")
            return response

        result = benchmark(lambda: run_async(fetch_status()))
        # 200 (success), 401 (auth required), or 404 (endpoint not implemented) are valid
        assert result.status_code in [200, 401, 404]

    @pytest.mark.benchmark(group="api-detections")
    def test_detections_list_benchmark(self, benchmark, benchmark_client: AsyncClient):
        """Benchmark GET /api/detections endpoint."""

        async def fetch_detections():
            response = await benchmark_client.get("/api/detections?limit=50")
            return response

        result = benchmark(lambda: run_async(fetch_detections()))
        assert result.status_code in [200, 401]


@pytest.mark.slow
class TestAPIBenchmarksAsync:
    """Async benchmark tests for more accurate async measurements."""

    @pytest.mark.benchmark(group="api-async")
    def test_concurrent_requests_benchmark(
        self,
        benchmark,
        benchmark_client: AsyncClient,
    ):
        """Benchmark multiple concurrent API requests."""

        async def fetch_concurrent():
            tasks = [
                benchmark_client.get("/"),
                benchmark_client.get("/health"),
                benchmark_client.get("/api/cameras"),
            ]
            results = await asyncio.gather(*tasks)
            return results

        results = benchmark(lambda: run_async(fetch_concurrent()))
        assert len(results) == 3
        assert all(r.status_code in [200, 401] for r in results)
