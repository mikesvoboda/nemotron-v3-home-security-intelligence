"""
Smoke Test Configuration and Fixtures

Provides fixtures and utilities for deployment verification tests.
These tests run against a deployed environment (staging or production).

Test Scope:
- Health endpoints verification
- API endpoint accessibility
- Service-to-service connectivity
- WebSocket connections
- Data flow through critical paths
"""

import os
from collections.abc import Generator

import httpx
import pytest


@pytest.fixture(scope="session")
def backend_url() -> str:
    """Get backend URL from environment or use default."""
    return os.environ.get("BACKEND_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def frontend_url() -> str:
    """Get frontend URL from environment or use default."""
    return os.environ.get("FRONTEND_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def ws_url(backend_url: str) -> str:
    """Convert backend HTTP URL to WebSocket URL."""
    ws_url = backend_url.replace("http://", "ws://").replace("https://", "wss://")
    return ws_url


@pytest.fixture(scope="session")
def http_client() -> Generator[httpx.Client]:
    """
    Create a shared HTTP client for all smoke tests.

    Reuses connections and is more efficient than creating
    a new client for each test.
    """
    with httpx.Client(timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def async_http_client() -> Generator[httpx.AsyncClient]:
    """Create a shared async HTTP client for smoke tests."""
    # Note: This would require pytest-asyncio, but sync version is sufficient
    # for smoke tests. Included for reference if needed in the future.
    pass


@pytest.fixture
def deployment_config() -> dict:
    """
    Get deployment configuration from environment.

    Returns a dict of deployment settings useful for test context.
    """
    return {
        "environment": os.environ.get("ENVIRONMENT", "unknown"),
        "backend_url": os.environ.get("BACKEND_URL", "http://localhost:8000"),
        "frontend_url": os.environ.get("FRONTEND_URL", "http://localhost:3000"),
        "timeout": int(os.environ.get("SMOKE_TEST_TIMEOUT", "120")),
        "debug": os.environ.get("DEBUG", "false").lower() == "true",
    }


@pytest.fixture
def request_headers() -> dict:
    """Get common request headers for API calls."""
    return {
        "User-Agent": "Smoke-Test/1.0",
        "Accept": "application/json",
    }


# Markers for test categorization
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "critical: Critical path smoke test (health, API basics)",
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration test (service-to-service)",
    )
    config.addinivalue_line(
        "markers",
        "websocket: WebSocket connectivity test",
    )
    config.addinivalue_line(
        "markers",
        "monitoring: Monitoring stack validation",
    )
    config.addinivalue_line(
        "markers",
        "slow: Slow test (takes >5 seconds)",
    )
