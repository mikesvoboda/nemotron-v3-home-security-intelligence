"""Pytest configuration and shared fixtures.

This module provides shared test fixtures for all backend tests:
- isolated_db: Function-scoped isolated database for unit tests (PostgreSQL)
- test_db: Callable session factory for unit tests
- integration_env: Environment setup for integration tests
- integration_db: Initialized database for integration tests
- mock_redis: Mock Redis client for integration tests
- db_session: Database session for integration tests
- client: httpx AsyncClient for API integration tests

Tests use PostgreSQL. Configure TEST_DATABASE_URL environment variable or
use the default test database URL.

See backend/tests/AGENTS.md for full documentation on test conventions.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


def _get_test_database_url() -> str:
    """Get a unique test database URL for isolation.

    Uses TEST_DATABASE_URL env var or defaults to a test database.
    Appends a unique suffix to ensure test isolation.
    """
    base_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/security_test",
    )
    return base_url


@pytest.fixture(scope="function")
async def isolated_db():
    """Create an isolated test database for each test.

    This fixture:
    - Sets up a PostgreSQL test database
    - Sets the DATABASE_URL environment variable
    - Clears the settings cache
    - Initializes the database
    - Truncates all tables for clean state
    - Yields control to the test
    - Cleans up and restores the original state
    """
    from sqlalchemy import text

    from backend.core.config import get_settings
    from backend.core.database import close_db, get_engine, init_db

    # Save original state
    original_db_url = os.environ.get("DATABASE_URL")

    # Clear the settings cache to force reload
    get_settings.cache_clear()

    # Use PostgreSQL test database
    test_db_url = _get_test_database_url()

    # Set test database URL
    os.environ["DATABASE_URL"] = test_db_url

    # Clear cache again after setting env var
    get_settings.cache_clear()

    # Ensure database is closed before initializing
    await close_db()

    # Initialize database
    await init_db()

    # Clean up any existing data before the test (for test isolation)
    # Use a raw connection to ensure immediate visibility and avoid session caching
    async with get_engine().begin() as conn:
        # Single TRUNCATE with RESTART IDENTITY ensures clean state
        await conn.execute(
            text(
                "TRUNCATE TABLE logs, gpu_stats, api_keys, detections, events, cameras "
                "RESTART IDENTITY CASCADE"
            )
        )

    yield

    # Cleanup
    await close_db()

    # Restore original state
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    # Clear cache one more time to ensure clean state
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Automatically reset settings cache before each test.

    This ensures no global state leaks between tests.
    Note: We don't auto-close database here since some tests
    explicitly test the behavior when database is not initialized.
    """
    from backend.core.config import get_settings

    # Clear settings cache before test
    get_settings.cache_clear()

    yield

    # Clear settings cache after test
    get_settings.cache_clear()


@pytest.fixture
async def test_db():
    """Create test database session factory for unit tests.

    This fixture provides a callable that returns a context manager for database sessions.
    It sets up a PostgreSQL test database and ensures cleanup after the test.

    Usage:
        async with test_db() as session:
            # Use session for database operations
            ...
    """
    from sqlalchemy import text

    from backend.core.config import get_settings
    from backend.core.database import close_db, get_session, init_db

    # Save original state
    original_db_url = os.environ.get("DATABASE_URL")

    # Clear the settings cache to force reload
    get_settings.cache_clear()

    # Use PostgreSQL test database
    test_db_url = _get_test_database_url()

    # Set test database URL
    os.environ["DATABASE_URL"] = test_db_url

    # Clear cache again after setting env var
    get_settings.cache_clear()

    # Ensure database is closed before initializing
    await close_db()

    # Initialize database
    await init_db()

    # Clean up any existing data before the test (for parallel test isolation)
    async with get_session() as session:
        # Truncate all tables in correct order to respect FK constraints
        await session.execute(text("TRUNCATE TABLE logs, gpu_stats, api_keys CASCADE"))
        await session.execute(text("TRUNCATE TABLE detections, events CASCADE"))
        await session.execute(text("TRUNCATE TABLE cameras CASCADE"))
        await session.commit()

    # Return the get_session function as a callable
    yield get_session

    # Cleanup data after the test (best effort - ignore errors during cleanup)
    try:
        async with get_session() as session:
            await session.execute(text("TRUNCATE TABLE logs, gpu_stats, api_keys CASCADE"))
            await session.execute(text("TRUNCATE TABLE detections, events CASCADE"))
            await session.execute(text("TRUNCATE TABLE cameras CASCADE"))
            await session.commit()
    except Exception:  # noqa: S110 - intentionally ignoring cleanup errors
        pass

    # Cleanup
    await close_db()

    # Restore original state
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    # Clear cache one more time to ensure clean state
    get_settings.cache_clear()


# =============================================================================
# Integration Test Fixtures
# =============================================================================
# These fixtures are shared across all integration and E2E tests.
# They provide consistent database setup, Redis mocking, and HTTP client access.


@pytest.fixture
def integration_env() -> Generator[str]:
    """Set DATABASE_URL/REDIS_URL to a test PostgreSQL database.

    This fixture ONLY sets environment variables and clears cached settings.
    Use `integration_db` if the test needs the database initialized.

    All integration tests should use this fixture (directly or via integration_db)
    to ensure proper isolation and cleanup.
    """
    import tempfile

    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")
    original_runtime_env_path = os.environ.get("HSI_RUNTIME_ENV_PATH")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_url = _get_test_database_url()
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
    """Initialize a PostgreSQL test database for integration/E2E tests.

    This fixture:
    - Depends on integration_env for environment setup
    - Closes any existing database connections
    - Initializes a fresh database with all tables
    - Truncates all tables for clean state
    - Yields the database URL
    - Cleans up after the test

    Use this fixture for any test that needs database access.
    """
    from sqlalchemy import text

    from backend.core.config import get_settings
    from backend.core.database import close_db, get_engine, init_db

    # Ensure clean state
    get_settings.cache_clear()
    await close_db()

    await init_db()

    # Clean up any existing data before the test (for test isolation)
    # Use a raw connection to ensure immediate visibility and avoid session caching
    async with get_engine().begin() as conn:
        # Single TRUNCATE with RESTART IDENTITY ensures clean state
        await conn.execute(
            text(
                "TRUNCATE TABLE logs, gpu_stats, api_keys, detections, events, cameras "
                "RESTART IDENTITY CASCADE"
            )
        )

    try:
        yield integration_env
    finally:
        # Clean up after test too for good measure
        try:
            async with get_engine().begin() as conn:
                await conn.execute(
                    text(
                        "TRUNCATE TABLE logs, gpu_stats, api_keys, detections, events, cameras "
                        "RESTART IDENTITY CASCADE"
                    )
                )
        except Exception:  # noqa: S110 - ignore cleanup errors
            pass
        await close_db()
        get_settings.cache_clear()


@pytest.fixture
async def mock_redis() -> AsyncGenerator[AsyncMock]:
    """Mock Redis operations so integration tests don't require an actual Redis server.

    This fixture provides a mock Redis client with common operations pre-configured:
    - health_check: Returns healthy status

    The mock is patched into backend.core.redis module.
    """
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    # Patch the shared singleton, initializer, and closer.
    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
        patch("backend.core.redis.close_redis", return_value=None),
    ):
        yield mock_redis_client


@pytest.fixture
async def db_session(integration_db: str):
    """Yield a live AsyncSession bound to the integration test database.

    Use this fixture when you need direct database session access in tests.
    The session is automatically committed and closed after the test.
    """
    from backend.core.database import get_session

    async with get_session() as session:
        yield session


@pytest.fixture
async def client(integration_db: str, mock_redis: AsyncMock) -> AsyncGenerator:
    """Async HTTP client bound to the FastAPI app (no network, no server startup).

    Notes:
    - The DB is pre-initialized by `integration_db`.
    - We patch app lifespan DB init/close to avoid double initialization.
    - We patch Redis init/close in `backend.main` so lifespan does not connect.
    - We truncate all tables at the start of each test for isolation.

    Use this fixture for testing API endpoints.
    """
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text

    from backend.core.database import get_engine

    # Import the app only after env is set up.
    from backend.main import app

    # Truncate all tables at the start of each test for proper isolation
    # This ensures no data persists from previous tests
    async with get_engine().begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE logs, gpu_stats, api_keys, detections, events, cameras "
                "RESTART IDENTITY CASCADE"
            )
        )

    with (
        patch("backend.main.init_db", return_value=None),
        patch("backend.main.close_db", return_value=None),
        patch("backend.main.init_redis", return_value=mock_redis),
        patch("backend.main.close_redis", return_value=None),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
