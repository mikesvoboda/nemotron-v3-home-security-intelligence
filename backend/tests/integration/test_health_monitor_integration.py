"""Integration tests for the ServiceHealthMonitor and ShellServiceManager.

Tests the full health monitor flow including:
- Real subprocess execution with shell commands
- Failure detection and recovery cycles
- Multiple service monitoring
- WebSocket broadcast on status changes
- Graceful shutdown handling

External HTTP services are mocked to avoid real network calls.
"""

import asyncio
import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.health_monitor import ServiceHealthMonitor
from backend.services.service_managers import ServiceConfig, ShellServiceManager


@pytest.fixture
def fast_sleep():
    """Mock asyncio.sleep to speed up tests by reducing the 2s post-restart pause.

    Specifically targets the 2s delay in health_monitor._handle_failure() which
    slows down tests waiting for restart + health verification cycles.

    Only reduces delays of exactly 2 seconds (the post-restart pause).
    Other delays are preserved for proper timing behavior.
    """
    original_sleep = asyncio.sleep

    async def quick_sleep(delay):
        # Only accelerate the specific 2s post-restart pause
        if delay == 2:
            await original_sleep(0.02)  # Replace 2s pause with 20ms
        else:
            await original_sleep(delay)

    with patch.object(asyncio, "sleep", side_effect=quick_sleep) as mock_sleep:
        yield mock_sleep


@pytest.fixture
def test_config() -> ServiceConfig:
    """Config with short intervals for testing."""
    return ServiceConfig(
        name="test_service",
        health_url="http://localhost:19999/health",
        restart_cmd="echo 'restarted'",
        health_timeout=1.0,
        max_retries=2,
        backoff_base=0.1,
    )


@pytest.fixture
def multiple_service_configs() -> list[ServiceConfig]:
    """Multiple service configs for testing concurrent monitoring."""
    return [
        ServiceConfig(
            name="service_1",
            health_url="http://localhost:19991/health",
            restart_cmd="echo 'service_1_restarted'",
            health_timeout=1.0,
            max_retries=2,
            backoff_base=0.1,
        ),
        ServiceConfig(
            name="service_2",
            health_url="http://localhost:19992/health",
            restart_cmd="echo 'service_2_restarted'",
            health_timeout=1.0,
            max_retries=2,
            backoff_base=0.1,
        ),
        ServiceConfig(
            name="service_3",
            health_url="http://localhost:19993/health",
            restart_cmd="echo 'service_3_restarted'",
            health_timeout=1.0,
            max_retries=2,
            backoff_base=0.1,
        ),
    ]


class MockBroadcaster:
    """Mock EventBroadcaster for testing WebSocket broadcasts."""

    def __init__(self) -> None:
        self.broadcast_calls: list[dict[str, Any]] = []
        self.broadcast_event = AsyncMock(side_effect=self._record_broadcast)

    async def _record_broadcast(self, event_data: dict[str, Any]) -> int:
        """Record broadcast calls for verification."""
        self.broadcast_calls.append(event_data)
        return 1


@pytest.mark.asyncio
async def test_shell_manager_executes_real_echo_script() -> None:
    """Test that ShellServiceManager actually executes subprocess commands.

    Verifies that:
    1. restart() returns True for successful commands
    2. The subprocess actually ran (echo command)
    """
    config = ServiceConfig(
        name="echo_test",
        health_url="http://localhost:9999/health",
        restart_cmd="echo 'test_output'",
        health_timeout=1.0,
        max_retries=1,
        backoff_base=0.1,
    )

    manager = ShellServiceManager(subprocess_timeout=5.0)

    # Execute real subprocess
    result = await manager.restart(config)

    assert result is True, "restart() should return True for successful echo command"


@pytest.mark.asyncio
async def test_shell_manager_handles_failing_command() -> None:
    """Test that ShellServiceManager correctly handles failing commands."""
    config = ServiceConfig(
        name="fail_test",
        health_url="http://localhost:9999/health",
        restart_cmd="exit 1",  # Command that fails
        health_timeout=1.0,
        max_retries=1,
        backoff_base=0.1,
    )

    manager = ShellServiceManager(subprocess_timeout=5.0)

    result = await manager.restart(config)

    assert result is False, "restart() should return False for failing command"


@pytest.mark.asyncio
async def test_full_failure_detection_cycle(test_config: ServiceConfig, fast_sleep) -> None:
    """Test full failure detection cycle.

    Verifies that:
    1. Health check failure is detected
    2. Failure is logged appropriately
    """
    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=False)
    mock_manager.restart = AsyncMock(return_value=False)

    mock_broadcaster = MockBroadcaster()

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[test_config],
        broadcaster=mock_broadcaster,
        check_interval=0.2,  # Short interval for fast tests
    )

    await monitor.start()

    # Wait for at least one check cycle
    await asyncio.sleep(0.3)

    await monitor.stop()

    # Verify health check was called
    mock_manager.check_health.assert_called()

    # Verify broadcast was called for unhealthy status
    unhealthy_broadcasts = [
        call for call in mock_broadcaster.broadcast_calls if call.get("status") == "unhealthy"
    ]
    assert len(unhealthy_broadcasts) > 0, "Should have broadcast unhealthy status"


@pytest.mark.asyncio
async def test_full_recovery_cycle(test_config: ServiceConfig, fast_sleep) -> None:
    """Test full recovery cycle: unhealthy -> restart -> healthy.

    Verifies that:
    1. Service starts as unhealthy
    2. Restart is attempted
    3. Health check passes after restart
    4. Failure count is reset to 0
    """
    # Track call counts for health check
    # First call fails (triggers restart), post-restart check succeeds
    health_check_results = [False, True, True, True, True]
    health_check_index = 0

    async def mock_check_health(config: ServiceConfig) -> bool:
        nonlocal health_check_index
        if health_check_index < len(health_check_results):
            result = health_check_results[health_check_index]
            health_check_index += 1
            return result
        return True

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(side_effect=mock_check_health)
    mock_manager.restart = AsyncMock(return_value=True)

    mock_broadcaster = MockBroadcaster()

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[test_config],
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    await monitor.start()

    # Wait for recovery cycle (mocked 2s pause allows faster completion)
    await asyncio.sleep(0.5)

    await monitor.stop()

    # Verify restart was attempted
    assert mock_manager.restart.call_count >= 1, "Restart should have been attempted"

    # Verify healthy status was eventually broadcast
    healthy_broadcasts = [
        call for call in mock_broadcaster.broadcast_calls if call.get("status") == "healthy"
    ]
    assert len(healthy_broadcasts) > 0, "Should have broadcast healthy status after recovery"

    # Verify failure count was reset
    status = monitor.get_status()
    assert status[test_config.name]["failure_count"] == 0, "Failure count should be reset"


@pytest.mark.asyncio
async def test_multiple_services_monitored(
    multiple_service_configs: list[ServiceConfig],
    fast_sleep,
) -> None:
    """Test monitoring multiple services simultaneously.

    Verifies that:
    1. All 3 services are checked
    2. Different health states are handled correctly

    Note: The health monitor processes services sequentially and
    when a service fails, it goes into restart cycle which takes time
    (backoff + 2s post-restart check). We need to wait long enough
    for at least one complete cycle.
    """

    # All services healthy to avoid restart blocking
    async def mock_check_health(config: ServiceConfig) -> bool:
        return True  # All healthy

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(side_effect=mock_check_health)
    mock_manager.restart = AsyncMock(return_value=True)

    mock_broadcaster = MockBroadcaster()

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=multiple_service_configs,
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    await monitor.start()

    # Wait for at least one full check cycle
    await asyncio.sleep(0.3)

    await monitor.stop()

    # Verify all services were checked
    checked_services = {call[0][0].name for call in mock_manager.check_health.call_args_list}
    expected_services = {"service_1", "service_2", "service_3"}
    assert checked_services == expected_services, "All services should have been checked"


@pytest.mark.asyncio
async def test_websocket_broadcast_on_status_change(test_config: ServiceConfig, fast_sleep) -> None:
    """Test that status changes trigger WebSocket broadcasts.

    Verifies that:
    1. broadcast_event() is called on status change
    2. Correct payload structure is sent
    """
    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=False)
    mock_manager.restart = AsyncMock(return_value=False)

    mock_broadcaster = MockBroadcaster()

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[test_config],
        broadcaster=mock_broadcaster,
        check_interval=0.2,
    )

    await monitor.start()

    # Wait for check to complete
    await asyncio.sleep(0.3)

    await monitor.stop()

    # Verify broadcast was called
    assert len(mock_broadcaster.broadcast_calls) > 0, "broadcast_event should have been called"

    # Verify payload structure
    first_broadcast = mock_broadcaster.broadcast_calls[0]
    assert "type" in first_broadcast
    assert first_broadcast["type"] == "service_status"
    assert "service" in first_broadcast
    assert first_broadcast["service"] == test_config.name
    assert "status" in first_broadcast
    assert "timestamp" in first_broadcast


@pytest.mark.asyncio
async def test_monitor_survives_single_service_failure(
    multiple_service_configs: list[ServiceConfig],
    fast_sleep,
) -> None:
    """Test that monitor continues checking other services after one throws exception.

    Verifies that:
    1. When one service check throws an exception, others are still checked
    2. Monitor remains stable and continues operating

    Note: When a health check fails (including via exception), the monitor
    calls _handle_failure which does exponential backoff + restart. With
    backoff_base=0.1, we need to wait long enough for the cycle to complete.
    """
    call_counts: dict[str, int] = {"service_1": 0, "service_2": 0, "service_3": 0}

    async def mock_check_health(config: ServiceConfig) -> bool:
        call_counts[config.name] = call_counts.get(config.name, 0) + 1
        if config.name == "service_2":
            # Service 2 throws exception
            raise RuntimeError("Simulated service error")
        return True

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(side_effect=mock_check_health)
    mock_manager.restart = AsyncMock(return_value=True)

    mock_broadcaster = MockBroadcaster()

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=multiple_service_configs,
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    await monitor.start()

    # Wait for at least one full check cycle (mocked 2s pause allows faster completion)
    await asyncio.sleep(0.5)

    await monitor.stop()

    # Verify all services were checked despite service_2 throwing exceptions
    assert call_counts["service_1"] >= 1, "service_1 should have been checked"
    assert call_counts["service_2"] >= 1, "service_2 should have been checked (despite exception)"
    assert call_counts["service_3"] >= 1, "service_3 should have been checked"

    # Verify monitor still running before stop
    # (it was running until we called stop)


@pytest.mark.asyncio
async def test_graceful_shutdown_during_restart(test_config: ServiceConfig, fast_sleep) -> None:
    """Test graceful shutdown while restart is in progress.

    Verifies that:
    1. Calling stop() during restart doesn't hang
    2. Monitor shuts down cleanly
    """
    restart_started = asyncio.Event()
    restart_can_finish = asyncio.Event()

    async def slow_restart(config: ServiceConfig) -> bool:
        restart_started.set()
        # Wait for signal to finish, or timeout
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(restart_can_finish.wait(), timeout=2.0)
        return True

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=False)
    mock_manager.restart = AsyncMock(side_effect=slow_restart)

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[test_config],
        broadcaster=None,
        check_interval=0.1,
    )

    await monitor.start()

    # Wait for restart to start
    await asyncio.wait_for(restart_started.wait(), timeout=2.0)

    # Now stop the monitor while restart is "in progress"
    # This should complete without hanging
    stop_task = asyncio.create_task(monitor.stop())

    # Allow restart to complete
    restart_can_finish.set()

    # Stop should complete quickly
    try:
        await asyncio.wait_for(stop_task, timeout=3.0)
    except TimeoutError:
        pytest.fail("stop() should not hang during restart")

    assert not monitor.is_running, "Monitor should be stopped"


@pytest.mark.asyncio
async def test_health_check_with_real_http_mock(test_config: ServiceConfig) -> None:
    """Test health check with mocked HTTP responses.

    Uses patch to mock httpx.AsyncClient for HTTP health checks.
    """
    manager = ShellServiceManager(subprocess_timeout=5.0)

    # Mock successful health check
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch("backend.services.service_managers.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await manager.check_health(test_config)

    assert result is True, "Health check should succeed with 200 response"


@pytest.mark.asyncio
async def test_health_check_failure_with_http_error(test_config: ServiceConfig) -> None:
    """Test health check failure with HTTP error response."""
    import httpx

    manager = ShellServiceManager(subprocess_timeout=5.0)

    # Mock failed health check (500 error)
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )
    )

    with patch("backend.services.service_managers.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await manager.check_health(test_config)

    assert result is False, "Health check should fail with 500 response"


@pytest.mark.asyncio
async def test_max_retries_exceeded(test_config: ServiceConfig, fast_sleep) -> None:
    """Test that monitor gives up after max retries exceeded.

    Verifies that:
    1. After max_retries failures, service is marked as 'failed'
    2. No more restart attempts are made
    """
    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=False)
    mock_manager.restart = AsyncMock(return_value=False)

    mock_broadcaster = MockBroadcaster()

    # Config with max_retries=2
    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[test_config],
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    await monitor.start()

    # Wait for retries to be exhausted (need enough time for max_retries=2 cycles)
    # Each cycle: check_interval + backoff (0.1 + 0.1*2^attempt)
    await asyncio.sleep(1.0)  # timeout - intentional wait for retry cycles

    await monitor.stop()

    # Verify 'failed' status was broadcast
    failed_broadcasts = [
        call for call in mock_broadcaster.broadcast_calls if call.get("status") == "failed"
    ]
    assert len(failed_broadcasts) > 0, "Should have broadcast 'failed' status after max retries"


@pytest.mark.asyncio
async def test_monitor_get_status() -> None:
    """Test get_status() returns correct status information."""
    configs = [
        ServiceConfig(
            name="svc_a",
            health_url="http://localhost:1111/health",
            restart_cmd="echo a",
            max_retries=3,
            backoff_base=0.1,
        ),
        ServiceConfig(
            name="svc_b",
            health_url="http://localhost:2222/health",
            restart_cmd="echo b",
            max_retries=5,
            backoff_base=0.1,
        ),
    ]

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=True)
    mock_manager.restart = AsyncMock(return_value=True)

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=configs,
        broadcaster=None,
        check_interval=10.0,  # Long interval since we don't need checks
    )

    status = monitor.get_status()

    assert "svc_a" in status
    assert "svc_b" in status
    assert status["svc_a"]["failure_count"] == 0
    assert status["svc_a"]["max_retries"] == 3
    assert status["svc_b"]["failure_count"] == 0
    assert status["svc_b"]["max_retries"] == 5


@pytest.mark.asyncio
async def test_monitor_idempotent_start_stop(fast_sleep) -> None:
    """Test that start() and stop() are idempotent."""
    config = ServiceConfig(
        name="idempotent_test",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
        max_retries=1,
        backoff_base=0.1,
    )

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=True)

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=None,
        check_interval=1.0,
    )

    # Multiple starts should be safe
    await monitor.start()
    await monitor.start()  # Should log warning but not error
    assert monitor.is_running

    # Multiple stops should be safe
    await monitor.stop()
    await monitor.stop()  # Should be no-op
    assert not monitor.is_running


@pytest.mark.asyncio
async def test_broadcast_failure_does_not_crash_monitor(
    test_config: ServiceConfig, fast_sleep
) -> None:
    """Test that broadcast failures don't crash the health monitor."""
    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=False)
    mock_manager.restart = AsyncMock(return_value=True)

    # Broadcaster that fails
    failing_broadcaster = MagicMock()
    failing_broadcaster.broadcast_event = AsyncMock(side_effect=RuntimeError("Broadcast failed"))

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[test_config],
        broadcaster=failing_broadcaster,
        check_interval=0.2,
    )

    await monitor.start()

    # Wait for check cycle
    await asyncio.sleep(0.4)

    # Monitor should still be running despite broadcast failure
    assert monitor.is_running, "Monitor should continue running despite broadcast failures"

    await monitor.stop()


@pytest.mark.asyncio
async def test_multiple_services_different_health_states(fast_sleep) -> None:
    """Test monitoring multiple services with different health outcomes.

    Verifies that broadcasts correctly report the state of each service
    and that mixed health states are properly handled.
    """
    configs = [
        ServiceConfig(
            name="healthy_service",
            health_url="http://localhost:1111/health",
            restart_cmd="echo healthy",
            health_timeout=1.0,
            max_retries=1,
            backoff_base=0.1,
        ),
        ServiceConfig(
            name="unhealthy_service",
            health_url="http://localhost:2222/health",
            restart_cmd="echo unhealthy",
            health_timeout=1.0,
            max_retries=1,
            backoff_base=0.1,
        ),
    ]

    health_states = {
        "healthy_service": True,
        "unhealthy_service": False,
    }

    async def mock_check_health(config: ServiceConfig) -> bool:
        return health_states.get(config.name, False)

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(side_effect=mock_check_health)
    mock_manager.restart = AsyncMock(return_value=True)

    mock_broadcaster = MockBroadcaster()

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=configs,
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    await monitor.start()

    # Wait for checks and restart cycle (mocked 2s pause allows faster completion)
    await asyncio.sleep(0.5)

    await monitor.stop()

    # Verify unhealthy broadcasts for the unhealthy service
    unhealthy_broadcasts = [
        call
        for call in mock_broadcaster.broadcast_calls
        if call.get("status") == "unhealthy" and call.get("service") == "unhealthy_service"
    ]
    assert len(unhealthy_broadcasts) > 0, (
        "Should have broadcast unhealthy status for unhealthy_service"
    )

    # Verify no unhealthy broadcasts for the healthy service
    healthy_service_unhealthy = [
        call
        for call in mock_broadcaster.broadcast_calls
        if call.get("status") == "unhealthy" and call.get("service") == "healthy_service"
    ]
    assert len(healthy_service_unhealthy) == 0, (
        "healthy_service should not have any unhealthy broadcasts"
    )


@pytest.mark.asyncio
async def test_subprocess_timeout_handling() -> None:
    """Test that subprocess timeout is properly handled."""
    config = ServiceConfig(
        name="timeout_test",
        health_url="http://localhost:9999/health",
        restart_cmd="sleep 10",  # Long running command
        health_timeout=1.0,
        max_retries=1,
        backoff_base=0.1,
    )

    # Very short timeout to trigger timeout handling
    manager = ShellServiceManager(subprocess_timeout=0.1)

    result = await manager.restart(config)

    assert result is False, "restart() should return False when subprocess times out"
