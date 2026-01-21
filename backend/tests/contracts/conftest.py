"""Pytest configuration and fixtures for contract tests.

This module provides fixtures for running contract tests against the API,
including database setup, test client configuration, and schema loading.

NOTE: Mock fixtures (mock_db_session, mock_redis_client) are imported from
the root conftest.py to avoid duplication. See backend/tests/conftest.py
for comprehensive mock fixture implementations.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


# Set test environment before importing app
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/security_test",  # pragma: allowlist secret
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    """Use asyncio as the async backend for pytest-anyio."""
    return "asyncio"


@pytest.fixture(scope="module")
async def test_app() -> AsyncGenerator:
    """Create test FastAPI app with mocked dependencies.

    This fixture creates the FastAPI app with mocked Redis and database
    dependencies, suitable for contract testing where we focus on API
    schema validation rather than full integration.
    """
    from backend.main import app

    # Mock the lifespan context to avoid actual service initialization
    original_lifespan = app.router.lifespan_context

    async def mock_lifespan(_app):
        """Mock lifespan that skips actual service initialization."""
        yield

    app.router.lifespan_context = mock_lifespan

    try:
        yield app
    finally:
        app.router.lifespan_context = original_lifespan


@pytest.fixture(scope="module")
async def async_client(test_app) -> AsyncGenerator[AsyncClient]:
    """Create async HTTP client for testing.

    This client connects directly to the ASGI app without going through
    the network, making tests faster and more reliable.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# NOTE: mock_db_session and mock_redis_client are now imported from root conftest.py
# They are automatically available to all tests via pytest's fixture discovery.
# See backend/tests/conftest.py for their implementations.


@pytest.fixture
def patch_database_dependency(mock_db_session):
    """Patch the database dependency injection.

    This fixture patches the get_db dependency to return a mock session,
    allowing contract tests to run without a real database.

    Uses the mock_db_session fixture from root conftest.py.
    """

    async def mock_get_db():
        yield mock_db_session

    with patch("backend.core.database.get_db", mock_get_db):
        yield mock_db_session


@pytest.fixture
def patch_redis_dependency(mock_redis_client):
    """Patch the Redis dependency injection.

    This fixture patches Redis-related dependencies to return mocks,
    allowing contract tests to run without a real Redis connection.

    Uses the mock_redis_client fixture from root conftest.py.
    """
    with (
        patch("backend.core.redis.get_redis", return_value=mock_redis_client),
        patch("backend.core.redis.get_redis_optional", return_value=mock_redis_client),
        patch("backend.core.redis._redis_client", mock_redis_client),
    ):
        yield mock_redis_client
