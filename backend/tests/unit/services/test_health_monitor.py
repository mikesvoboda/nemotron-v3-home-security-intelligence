"""Unit tests for ServiceHealthMonitor (NEM-5057).

Tests cover:
- Health monitor task naming for asyncio debugging
- Start/stop lifecycle management
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.health_monitor import ServiceHealthMonitor
from backend.services.service_managers import ServiceConfig


@pytest.fixture
def mock_manager() -> MagicMock:
    """Create a mock ServiceManager."""
    manager = MagicMock()
    manager.check_health = AsyncMock(return_value=True)
    manager.restart = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def mock_broadcaster() -> MagicMock:
    """Create a mock EventBroadcaster."""
    broadcaster = MagicMock()
    broadcaster.broadcast_service_status = AsyncMock()
    return broadcaster


@pytest.fixture
def service_config() -> ServiceConfig:
    """Create a test service configuration."""
    return ServiceConfig(
        name="test_service",
        health_url="http://localhost:8000/health",
        restart_cmd="echo restart",
        max_retries=3,
        backoff_base=0.01,  # Very short for testing
    )


class TestHealthMonitorTaskNaming:
    """Tests for NEM-5057: asyncio.create_task() should have name parameter."""

    @pytest.mark.asyncio
    async def test_start_creates_named_task(
        self,
        mock_manager: MagicMock,
        mock_broadcaster: MagicMock,
        service_config: ServiceConfig,
    ) -> None:
        """Test that start() creates a task with a descriptive name for debugging."""
        monitor = ServiceHealthMonitor(
            manager=mock_manager,
            services=[service_config],
            broadcaster=mock_broadcaster,
            check_interval=0.05,
        )

        await monitor.start()
        try:
            # Verify task exists and has a name
            assert monitor._task is not None
            task_name = monitor._task.get_name()
            # Task should have a descriptive name containing "health"
            assert "health" in task_name.lower(), (
                f"Task name should contain 'health' for debugging, got: {task_name}"
            )
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_task_name_includes_monitor_identifier(
        self,
        mock_manager: MagicMock,
        mock_broadcaster: MagicMock,
        service_config: ServiceConfig,
    ) -> None:
        """Test that the task name is specific enough for debugging multiple monitors."""
        monitor = ServiceHealthMonitor(
            manager=mock_manager,
            services=[service_config],
            broadcaster=mock_broadcaster,
            check_interval=0.05,
        )

        await monitor.start()
        try:
            task_name = monitor._task.get_name()
            # Name should be descriptive - check it's not just "Task-N"
            assert not task_name.startswith("Task-"), (
                f"Task should have a custom name, not default Task-N: {task_name}"
            )
        finally:
            await monitor.stop()
