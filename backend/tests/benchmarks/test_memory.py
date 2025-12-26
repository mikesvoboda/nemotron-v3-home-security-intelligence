"""Memory profiling tests for API endpoints.

These tests use pytest-memray to ensure API endpoints stay within
memory usage limits during repeated requests.

Usage:
    pytest tests/benchmarks/test_memory.py --memray -v

Note: pytest-memray only works on Linux. Tests will be skipped on other platforms.
"""

from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

# Check if memray is available (Linux only)
MEMRAY_AVAILABLE = platform.system() == "Linux"

if MEMRAY_AVAILABLE:
    try:
        import memray  # noqa: F401

        pytest_plugins = ["memray"]
    except ImportError:
        MEMRAY_AVAILABLE = False


@pytest.fixture
def memory_test_env() -> Generator[str, None, None]:
    """Set DATABASE_URL/REDIS_URL to a temporary per-test database."""
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")
    original_runtime_env_path = os.environ.get("HSI_RUNTIME_ENV_PATH")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "memory_test.db"
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
async def memory_test_db(memory_test_env: str) -> AsyncGenerator[str, None]:
    """Initialize a temporary SQLite DB for memory tests."""
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    get_settings.cache_clear()
    await close_db()
    await init_db()

    try:
        yield memory_test_env
    finally:
        await close_db()
        get_settings.cache_clear()


@pytest.fixture
def mock_redis_for_memory() -> Generator[AsyncMock, None, None]:
    """Mock Redis operations for memory tests."""
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


def get_test_client(mock_redis: AsyncMock):
    """Get a synchronous test client for memory tests.

    Memory tests require synchronous HTTP client (not async) because
    pytest-memray tracks memory in synchronous code paths.
    """
    from httpx import ASGITransport, Client

    from backend.main import app

    with (
        patch("backend.main.init_db", return_value=None),
        patch("backend.main.close_db", return_value=None),
        patch("backend.main.init_redis", return_value=mock_redis),
        patch("backend.main.close_redis", return_value=None),
    ):
        transport = ASGITransport(app=app)
        return Client(transport=transport, base_url="http://test")


@pytest.mark.skipif(
    not MEMRAY_AVAILABLE,
    reason="memray only available on Linux",
)
class TestMemoryProfiling:
    """Memory profiling tests for API endpoints."""

    @pytest.mark.limit_memory("500 MB")
    def test_health_endpoint_memory(
        self,
        memory_test_db: str,
        mock_redis_for_memory: AsyncMock,
    ):
        """Ensure health endpoint stays under 500MB with repeated calls."""
        with get_test_client(mock_redis_for_memory) as client:
            for _ in range(100):
                response = client.get("/")
                assert response.status_code == 200

    @pytest.mark.limit_memory("500 MB")
    def test_cameras_endpoint_memory(
        self,
        memory_test_db: str,
        mock_redis_for_memory: AsyncMock,
    ):
        """Ensure cameras endpoint stays under 500MB with repeated calls."""
        with get_test_client(mock_redis_for_memory) as client:
            for _ in range(100):
                response = client.get("/api/cameras")
                assert response.status_code in [200, 401]

    @pytest.mark.limit_memory("500 MB")
    def test_events_endpoint_memory(
        self,
        memory_test_db: str,
        mock_redis_for_memory: AsyncMock,
    ):
        """Ensure events endpoint stays under 500MB with repeated calls."""
        with get_test_client(mock_redis_for_memory) as client:
            for _ in range(100):
                response = client.get("/api/events?limit=50")
                assert response.status_code in [200, 401]

    @pytest.mark.limit_memory("500 MB")
    def test_system_status_endpoint_memory(
        self,
        memory_test_db: str,
        mock_redis_for_memory: AsyncMock,
    ):
        """Ensure system status endpoint stays under 500MB with repeated calls."""
        with get_test_client(mock_redis_for_memory) as client:
            for _ in range(100):
                response = client.get("/api/system/status")
                assert response.status_code in [200, 401]


@pytest.mark.slow
class TestMemoryProfilingFallback:
    """Fallback tests when memray is not available.

    These tests provide basic functionality verification without memory limits.
    """

    @pytest.mark.skipif(
        MEMRAY_AVAILABLE,
        reason="memray is available, using memray tests instead",
    )
    def test_health_endpoint_without_memray(
        self,
        memory_test_db: str,
        mock_redis_for_memory: AsyncMock,
    ):
        """Basic health endpoint test without memory profiling."""
        with get_test_client(mock_redis_for_memory) as client:
            for _ in range(10):
                response = client.get("/")
                assert response.status_code == 200

    @pytest.mark.skipif(
        MEMRAY_AVAILABLE,
        reason="memray is available, using memray tests instead",
    )
    def test_cameras_endpoint_without_memray(
        self,
        memory_test_db: str,
        mock_redis_for_memory: AsyncMock,
    ):
        """Basic cameras endpoint test without memory profiling."""
        with get_test_client(mock_redis_for_memory) as client:
            for _ in range(10):
                response = client.get("/api/cameras")
                assert response.status_code in [200, 401]
