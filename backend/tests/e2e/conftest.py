"""E2E test fixtures.

This module provides E2E-specific fixtures. The shared fixtures (integration_db,
mock_redis, client, etc.) are inherited from backend/tests/conftest.py.

No duplicate fixture definitions - all common fixtures are centralized in the
root conftest.py file.
"""

# E2E tests use the shared fixtures from backend/tests/conftest.py:
# - integration_db: PostgreSQL test database
# - mock_redis: Mock Redis client
# - client: httpx AsyncClient for API testing

import os
from collections.abc import AsyncGenerator

import pytest

from backend.core.config import get_settings
from backend.core.database import close_db, init_db


def _get_test_database_url() -> str:
    """Get the test database URL."""
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/security_test",
    )


@pytest.fixture
async def integration_db() -> AsyncGenerator[str]:
    """Initialize a PostgreSQL test database for E2E tests.

    This fixture:
    - Sets up a PostgreSQL test database
    - Sets the DATABASE_URL environment variable
    - Clears the settings cache
    - Initializes the database
    - Yields control to the test
    - Cleans up and restores the original state
    """
    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")

    # Clear the settings cache to force reload
    get_settings.cache_clear()

    # Use PostgreSQL test database
    test_db_url = _get_test_database_url()

    # Set test database URL
    os.environ["DATABASE_URL"] = test_db_url
    # Use Redis database 15 for test isolation. This keeps test data separate
    # from development (database 0). FLUSHDB in pre-commit hooks only affects DB 15.
    # See backend/tests/AGENTS.md for full documentation on test database isolation.
    os.environ["REDIS_URL"] = "redis://localhost:6379/15"

    # Clear cache again after setting env var
    get_settings.cache_clear()

    # Ensure database is closed before initializing
    await close_db()

    # Initialize database
    await init_db()

    try:
        yield test_db_url
    finally:
        # Cleanup
        await close_db()

    # Restore original state
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    if original_redis_url:
        os.environ["REDIS_URL"] = original_redis_url
    else:
        os.environ.pop("REDIS_URL", None)

    # Clear cache one more time to ensure clean state
    get_settings.cache_clear()
