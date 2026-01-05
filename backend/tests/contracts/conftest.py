"""Contract test fixtures for Schemathesis-based API testing.

This module provides fixtures for contract tests that verify API schema
compliance using Schemathesis schema-based fuzzing.

Contract tests run against the FastAPI app using ASGI transport,
so no running server is needed.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
import schemathesis
import schemathesis.openapi
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI


@pytest.fixture(scope="function")
async def app_with_db() -> AsyncGenerator[FastAPI]:
    """Create FastAPI app with database initialized for contract testing.

    This fixture:
    1. Sets up test database URL
    2. Initializes the database with schema
    3. Yields the FastAPI app
    4. Cleans up after tests

    Uses function scope to avoid pytest-asyncio scope issues.
    """
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    # Set test database URL if not already set
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"  # pragma: allowlist secret
        )
    if not os.environ.get("REDIS_URL"):
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"

    # Clear settings cache
    get_settings.cache_clear()

    # Initialize database
    await init_db()

    # Import app after database is initialized
    from backend.main import app

    yield app

    # Cleanup
    await close_db()
    get_settings.cache_clear()


@pytest.fixture(scope="function")
async def async_client(app_with_db: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Create an async HTTP client for testing the API.

    Uses ASGI transport to test against the app directly without
    starting a server.
    """
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="function")
def openapi_schema(app_with_db: FastAPI) -> dict:
    """Get the OpenAPI schema from the FastAPI app."""
    return app_with_db.openapi()


@pytest.fixture(scope="function")
def schemathesis_schema(app_with_db: FastAPI) -> schemathesis.openapi.OpenApiSchema:
    """Create a Schemathesis schema from the FastAPI app.

    This schema can be used for property-based testing of API endpoints.
    """
    return schemathesis.openapi.from_asgi("/openapi.json", app=app_with_db)
