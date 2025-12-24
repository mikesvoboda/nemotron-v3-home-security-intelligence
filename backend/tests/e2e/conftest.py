"""Shared fixtures for E2E pipeline integration tests.

These fixtures provide the necessary setup for end-to-end testing of the
complete AI pipeline, including database, Redis, and external services.
"""

import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from backend.core.config import get_settings
from backend.core.database import close_db, init_db


@pytest.fixture
async def integration_db() -> AsyncGenerator[str, None]:
    """Initialize a temporary SQLite DB for E2E tests.

    This fixture:
    - Creates a temporary database file
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

    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "e2e_test.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"

        # Set test database URL
        os.environ["DATABASE_URL"] = test_db_url
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
