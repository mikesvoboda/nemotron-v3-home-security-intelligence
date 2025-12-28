"""Integration test fixtures.

This module provides integration-specific fixtures. The shared fixtures
(integration_db, mock_redis, client, etc.) are inherited from backend/tests/conftest.py.

No duplicate fixture definitions - all common fixtures are centralized in the
root conftest.py file.
"""

from __future__ import annotations

# Integration tests use the shared fixtures from backend/tests/conftest.py:
# - integration_env: Environment setup only (no DB init)
# - integration_db: Isolated temporary SQLite database
# - mock_redis: Mock Redis client
# - db_session: Database session for direct DB access
# - client: httpx AsyncClient for API testing
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def integration_env() -> Generator[str]:
    """Set DATABASE_URL/REDIS_URL to a temporary per-test database.

    This fixture ONLY sets environment variables and clears cached settings.
    Use `integration_db` if the test needs the database initialized.
    """
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")
    original_runtime_env_path = os.environ.get("HSI_RUNTIME_ENV_PATH")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "integration_test.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"
        runtime_env_path = str(Path(tmpdir) / "runtime.env")

        os.environ["DATABASE_URL"] = test_db_url
        # Use Redis database 15 for test isolation. This keeps test data separate
        # from development (database 0). FLUSHDB in pre-commit hooks only affects DB 15.
        # See backend/tests/AGENTS.md for full documentation on test database isolation.
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"
        os.environ["HSI_RUNTIME_ENV_PATH"] = runtime_env_path

        get_settings.cache_clear()

        try:
            yield test_db_url
        finally:
            # Restore env
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
async def integration_db(integration_env: str) -> AsyncGenerator[str]:
    """Initialize a temporary SQLite DB for integration tests and cleanly tear it down."""
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    # Ensure clean state
    get_settings.cache_clear()
    await close_db()

    await init_db()

    try:
        yield integration_env
    finally:
        await close_db()
        get_settings.cache_clear()


@pytest.fixture
async def mock_redis() -> AsyncGenerator[AsyncMock]:
    """Mock Redis operations so integration tests don't require an actual Redis server."""
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    # Patch both the shared singleton and the initializer.
    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
    ):
        yield mock_redis_client


@pytest.fixture
async def db_session(integration_db: str):
    """Yield a live AsyncSession bound to the integration test database."""
    from backend.core.database import get_session

    async with get_session() as session:
        yield session


@pytest.fixture
async def client(integration_db: str, mock_redis: AsyncMock) -> AsyncGenerator[AsyncClient]:
    """Async HTTP client bound to the FastAPI app (no network, no server startup).

    Notes:
    - The DB is pre-initialized by `integration_db`.
    - We patch app lifespan DB init/close to avoid double initialization and reduce flakiness.
    - We patch Redis init/close in `backend.main` so lifespan does not try to connect for real.
    """
    # Import the app only after env is set up.
    from backend.main import app

    with (
        patch("backend.main.init_db", return_value=None),
        patch("backend.main.close_db", return_value=None),
        patch("backend.main.init_redis", return_value=mock_redis),
        patch("backend.main.close_redis", return_value=None),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
