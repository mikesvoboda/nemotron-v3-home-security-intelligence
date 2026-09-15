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

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


# Test API key for contract tests - must match API_KEYS env var below
CONTRACT_TEST_API_KEY = "test-api-key-12345"  # pragma: allowlist secret

# Set test environment before importing app
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/security_test",  # pragma: allowlist secret
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
# Enable API key authentication for contract tests
os.environ.setdefault("API_KEY_ENABLED", "true")
os.environ.setdefault("API_KEYS", f'["{CONTRACT_TEST_API_KEY}"]')


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

    Includes X-API-Key header for API key authentication.
    """
    from backend.core.config import get_settings

    # Clear settings cache to pick up API key env vars
    get_settings.cache_clear()

    transport = ASGITransport(app=test_app)
    headers = {"X-API-Key": CONTRACT_TEST_API_KEY}
    async with AsyncClient(
        transport=transport, base_url="http://testserver", headers=headers
    ) as client:
        yield client


# NOTE: mock_db_session and mock_redis_client are now imported from root conftest.py
# They are automatically available to all tests via pytest's fixture discovery.
# See backend/tests/conftest.py for their implementations.
