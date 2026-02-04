"""Shared fixtures for API route unit tests.

This module provides fixtures common to all route tests, particularly
for handling authentication in test clients.

## Authentication in Unit Tests

All API route unit tests require authentication. The `create_authenticated_client()`
context manager and `authenticated_client` fixture automatically include the test
API key header (X-API-Key) in all requests.

### Usage Examples

Context manager (preferred for tests that create clients in setup):
```python
async with create_authenticated_client() as client:
    response = await client.get("/api/endpoint")
    assert response.status_code == 200
```

Fixture injection (preferred for simpler tests):
```python
async def test_something(authenticated_client):
    response = await authenticated_client.get("/api/endpoint")
    assert response.status_code == 200
```

### Migration from Raw AsyncClient

If you see 401 errors in route tests, replace:
```python
async with AsyncClient(
    transport=ASGITransport(app=app), base_url="http://test"
) as client:
```

With:
```python
async with create_authenticated_client() as client:
```

### How It Works

1. backend/tests/unit/conftest.py enables API key auth via `enable_api_key_auth_for_unit_tests`
2. This fixture sets API_KEY_ENABLED=true and API_KEYS=[test-key] in environment
3. create_authenticated_client() includes the test API key in all requests
4. Auth middleware validates the key and allows the request through
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from backend.tests.unit.conftest import get_auth_headers


@asynccontextmanager
async def create_authenticated_client() -> AsyncGenerator[AsyncClient]:
    """Create an authenticated AsyncClient for testing API routes.

    This context manager creates an httpx AsyncClient with the test API key
    header pre-configured. All route tests should use this instead of creating
    raw AsyncClient instances.

    Usage:
        async with create_authenticated_client() as client:
            response = await client.get("/api/some-endpoint")

    Note: Requires API key auth to be enabled via the
    enable_api_key_auth_for_unit_tests fixture from backend.tests.unit.conftest.
    """
    # Import app lazily to avoid loading it during collection
    from backend.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=get_auth_headers(),
    ) as client:
        yield client


@pytest.fixture
async def authenticated_client() -> AsyncGenerator[AsyncClient]:
    """Provide an authenticated AsyncClient as a pytest fixture.

    This is a convenience fixture for tests that prefer fixture injection
    over context managers.

    Usage:
        async def test_something(authenticated_client):
            response = await authenticated_client.get("/api/endpoint")
    """
    # Import app lazily to avoid loading it during collection
    from backend.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=get_auth_headers(),
    ) as client:
        yield client
