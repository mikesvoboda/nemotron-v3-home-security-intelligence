"""Security test fixtures.

This module provides fixtures specifically for security testing,
including test clients with and without authentication.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from collections.abc import Generator


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
def security_client() -> Generator[TestClient]:
    """Create a test client for security testing.

    This fixture provides a synchronous test client with all background
    services mocked, suitable for security testing that doesn't require
    database access.
    """
    mocks = _create_mock_services()

    # Ensure DATABASE_URL is set
    original_db_url = os.environ.get("DATABASE_URL")
    if not original_db_url:
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"  # pragma: allowlist secret
        )

    # Disable database logging for tests (no logs table in test DB)
    original_log_db_enabled = os.environ.get("LOG_DB_ENABLED")
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
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        yield client

    # Restore original environment
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url

    if original_log_db_enabled is not None:
        os.environ["LOG_DB_ENABLED"] = original_log_db_enabled
    else:
        os.environ.pop("LOG_DB_ENABLED", None)

    get_settings.cache_clear()
