"""Security test fixtures.

This module provides fixtures specifically for security testing,
including test clients with and without authentication.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from collections.abc import Generator


# API key used for security tests - allows tests to bypass auth and test actual security behaviors
SECURITY_TEST_API_KEY = "test-security-key-12345"  # pragma: allowlist secret


class AuthenticatedTestClient:
    """Wrapper around TestClient that automatically adds API key authentication.

    This wrapper ensures all requests include the X-API-Key header,
    allowing security tests to reach endpoints and test behaviors like
    input validation, path traversal protection, and HTTP method restrictions.
    """

    def __init__(self, client: TestClient, api_key: str):
        self._client = client
        self._api_key = api_key
        self._auth_header = {"X-API-Key": api_key}

    def _merge_headers(self, headers: dict[str, str] | None) -> dict[str, str]:
        """Merge provided headers with authentication header."""
        if headers is None:
            return self._auth_header.copy()
        merged = self._auth_header.copy()
        merged.update(headers)
        return merged

    def get(self, url: str, **kwargs: Any) -> Any:
        """Make GET request with authentication."""
        kwargs["headers"] = self._merge_headers(kwargs.get("headers"))
        return self._client.get(url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        """Make POST request with authentication."""
        kwargs["headers"] = self._merge_headers(kwargs.get("headers"))
        return self._client.post(url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> Any:
        """Make PUT request with authentication."""
        kwargs["headers"] = self._merge_headers(kwargs.get("headers"))
        return self._client.put(url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> Any:
        """Make PATCH request with authentication."""
        kwargs["headers"] = self._merge_headers(kwargs.get("headers"))
        return self._client.patch(url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Any:
        """Make DELETE request with authentication."""
        kwargs["headers"] = self._merge_headers(kwargs.get("headers"))
        return self._client.delete(url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> Any:
        """Make OPTIONS request with authentication."""
        kwargs["headers"] = self._merge_headers(kwargs.get("headers"))
        return self._client.options(url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> Any:
        """Make HEAD request with authentication."""
        kwargs["headers"] = self._merge_headers(kwargs.get("headers"))
        return self._client.head(url, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Make request with specified method and authentication."""
        kwargs["headers"] = self._merge_headers(kwargs.get("headers"))
        return self._client.request(method, url, **kwargs)


def _create_mock_services() -> dict:
    """Create mock services for testing."""
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()
    mock_system_broadcaster.is_degraded = MagicMock(return_value=False)

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()

    mock_redis_client = MagicMock()

    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.channel_name = "test_channel"

    mock_file_watcher = MagicMock()
    mock_file_watcher.start = AsyncMock()
    mock_file_watcher.stop = AsyncMock()

    mock_pipeline_manager = MagicMock()
    mock_pipeline_manager.start = AsyncMock()
    mock_pipeline_manager.stop = AsyncMock()

    mock_service_health_monitor = MagicMock()
    mock_service_health_monitor.start = AsyncMock()
    mock_service_health_monitor.stop = AsyncMock()

    return {
        "system_broadcaster": mock_system_broadcaster,
        "gpu_monitor": mock_gpu_monitor,
        "cleanup_service": mock_cleanup_service,
        "redis_client": mock_redis_client,
        "event_broadcaster": mock_event_broadcaster,
        "file_watcher": mock_file_watcher,
        "pipeline_manager": mock_pipeline_manager,
        "service_health_monitor": mock_service_health_monitor,
    }


@pytest.fixture(scope="module")
def security_client() -> Generator[AuthenticatedTestClient]:
    """Create a test client for security testing.

    This fixture provides a synchronous test client with all background
    services mocked, suitable for security testing that doesn't require
    database access.

    Authentication is enabled via API key so that tests can reach
    the endpoints to test security behaviors like path traversal,
    input validation, and HTTP method restrictions.

    Returns an AuthenticatedTestClient that automatically adds the
    X-API-Key header to all requests.
    """
    mocks = _create_mock_services()

    # Store original environment values
    original_db_url = os.environ.get("DATABASE_URL")
    original_log_db_enabled = os.environ.get("LOG_DB_ENABLED")
    original_environment = os.environ.get("ENVIRONMENT")
    original_api_key_enabled = os.environ.get("API_KEY_ENABLED")
    original_api_keys = os.environ.get("API_KEYS")
    original_cors_origins = os.environ.get("CORS_ORIGINS")

    # Use development environment to bypass password validation for security tests
    # The tests themselves mock the settings to test specific behaviors
    os.environ["ENVIRONMENT"] = "development"

    # Enable API key authentication for security tests
    # This allows tests to reach endpoints and test actual security behaviors
    os.environ["API_KEY_ENABLED"] = "true"  # pragma: allowlist secret
    os.environ["API_KEYS"] = f'["{SECURITY_TEST_API_KEY}"]'  # pragma: allowlist secret

    # Configure CORS origins for testing
    # Include the origin that the security tests use for CORS validation
    os.environ["CORS_ORIGINS"] = '["http://localhost:3000", "https://localhost:8444"]'

    # Ensure DATABASE_URL is set
    if not original_db_url:
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"  # pragma: allowlist secret
        )

    # Disable database logging for tests (no logs table in test DB)
    os.environ["LOG_DB_ENABLED"] = "false"

    # Clear settings cache before creating app
    from backend.core.config import get_settings

    get_settings.cache_clear()

    async def mock_init_db():
        pass

    async def mock_seed_cameras_if_empty():
        return 0

    async def mock_validate_camera_paths_on_startup():
        return (0, 0)

    async def mock_init_redis():
        return mocks["redis_client"]

    async def mock_get_broadcaster(_redis_client):
        return mocks["event_broadcaster"]

    async def mock_get_pipeline_manager(_redis_client):
        return mocks["pipeline_manager"]

    # Mock setup guard to always return setup complete
    # This allows security tests to reach endpoints without creating test users
    async def mock_setup_complete():
        return True

    from backend.main import app

    with (
        patch("backend.main.init_db", mock_init_db),
        patch("backend.main.seed_cameras_if_empty", mock_seed_cameras_if_empty),
        patch(
            "backend.main.validate_camera_paths_on_startup",
            mock_validate_camera_paths_on_startup,
        ),
        patch("backend.main.init_redis", mock_init_redis),
        patch("backend.main.get_broadcaster", mock_get_broadcaster),
        patch("backend.main.FileWatcher", return_value=mocks["file_watcher"]),
        patch("backend.main.get_pipeline_manager", mock_get_pipeline_manager),
        patch("backend.main.get_system_broadcaster", return_value=mocks["system_broadcaster"]),
        patch("backend.main.GPUMonitor", return_value=mocks["gpu_monitor"]),
        patch("backend.main.CleanupService", return_value=mocks["cleanup_service"]),
        patch("backend.main.ServiceHealthMonitor", return_value=mocks["service_health_monitor"]),
        patch(
            "backend.api.middleware.setup_guard.SetupGuardMiddleware._check_setup_complete",
            mock_setup_complete,
        ),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        # Wrap client with AuthenticatedTestClient to auto-add API key header
        yield AuthenticatedTestClient(client, SECURITY_TEST_API_KEY)

    # Restore original environment
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url

    if original_log_db_enabled is not None:
        os.environ["LOG_DB_ENABLED"] = original_log_db_enabled
    else:
        os.environ.pop("LOG_DB_ENABLED", None)

    if original_environment is not None:
        os.environ["ENVIRONMENT"] = original_environment
    else:
        os.environ.pop("ENVIRONMENT", None)

    if original_api_key_enabled is not None:
        os.environ["API_KEY_ENABLED"] = original_api_key_enabled
    else:
        os.environ.pop("API_KEY_ENABLED", None)

    if original_api_keys is not None:
        os.environ["API_KEYS"] = original_api_keys
    else:
        os.environ.pop("API_KEYS", None)

    if original_cors_origins is not None:
        os.environ["CORS_ORIGINS"] = original_cors_origins
    else:
        os.environ.pop("CORS_ORIGINS", None)

    get_settings.cache_clear()
