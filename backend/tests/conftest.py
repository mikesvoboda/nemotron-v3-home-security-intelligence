"""Pytest configuration and shared fixtures."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="function")
async def isolated_db():
    """Create an isolated test database for each test.

    This fixture:
    - Creates a temporary database file
    - Sets the DATABASE_URL environment variable
    - Clears the settings cache
    - Initializes the database
    - Yields control to the test
    - Cleans up and restores the original state
    """
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    # Save original state
    original_db_url = os.environ.get("DATABASE_URL")

    # Clear the settings cache to force reload
    get_settings.cache_clear()

    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"

        # Set test database URL
        os.environ["DATABASE_URL"] = test_db_url

        # Clear cache again after setting env var
        get_settings.cache_clear()

        # Ensure database is closed before initializing
        await close_db()

        # Initialize database
        await init_db()

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
    It sets up a temporary database for testing and ensures cleanup.

    Usage:
        async with test_db() as session:
            # Use session for database operations
            ...
    """
    from backend.core.config import get_settings
    from backend.core.database import close_db, get_session, init_db

    # Save original state
    original_db_url = os.environ.get("DATABASE_URL")

    # Clear the settings cache to force reload
    get_settings.cache_clear()

    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"

        # Set test database URL
        os.environ["DATABASE_URL"] = test_db_url

        # Clear cache again after setting env var
        get_settings.cache_clear()

        # Ensure database is closed before initializing
        await close_db()

        # Initialize database
        await init_db()

        # Return the get_session function as a callable
        yield get_session

        # Cleanup
        await close_db()

    # Restore original state
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    # Clear cache one more time to ensure clean state
    get_settings.cache_clear()
