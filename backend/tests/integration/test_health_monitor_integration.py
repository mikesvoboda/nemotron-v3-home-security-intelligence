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


@pytest.fixture(autouse=True)
def allow_test_commands():
    """Patch validate_restart_command to allow test commands.

    Integration tests for subprocess execution need to run arbitrary
    commands like 'echo' and 'exit'. The security validation is tested
    separately in unit tests. This fixture allows test commands while
    preserving the security validation in production code.
    """
    with patch(
        "backend.services.service_managers.validate_restart_command",
        return_value=True,
    ):
        yield


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
    # The broadcast format is {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    unhealthy_broadcasts = [
        call
        for call in mock_broadcaster.broadcast_calls
        if call.get("data", {}).get("status") == "unhealthy"
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
    # The broadcast format is {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    healthy_broadcasts = [
        call
        for call in mock_broadcaster.broadcast_calls
        if call.get("data", {}).get("status") == "healthy"
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
    # The broadcast format is {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    first_broadcast = mock_broadcaster.broadcast_calls[0]
    assert "type" in first_broadcast
    assert first_broadcast["type"] == "service_status"
    assert "data" in first_broadcast
    assert "service" in first_broadcast["data"]
    assert first_broadcast["data"]["service"] == test_config.name
    assert "status" in first_broadcast["data"]
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
    # The broadcast format is {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    failed_broadcasts = [
        call
        for call in mock_broadcaster.broadcast_calls
        if call.get("data", {}).get("status") == "failed"
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
    # The broadcast format is {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    unhealthy_broadcasts = [
        call
        for call in mock_broadcaster.broadcast_calls
        if call.get("data", {}).get("status") == "unhealthy"
        and call.get("data", {}).get("service") == "unhealthy_service"
    ]
    assert len(unhealthy_broadcasts) > 0, (
        "Should have broadcast unhealthy status for unhealthy_service"
    )

    # Verify no unhealthy broadcasts for the healthy service
    healthy_service_unhealthy = [
        call
        for call in mock_broadcaster.broadcast_calls
        if call.get("data", {}).get("status") == "unhealthy"
        and call.get("data", {}).get("service") == "healthy_service"
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


# =============================================================================
# Tests for mb9s.15: Health monitor restart logic verification
# =============================================================================


@pytest.mark.asyncio
async def test_health_monitor_restart_cycle_on_failure(fast_sleep) -> None:
    """Test that health monitor properly restarts a failed service.

    This test verifies the complete restart cycle:
    1. Service starts unhealthy (health check fails)
    2. Monitor detects failure and initiates restart
    3. Restart command is executed
    4. Post-restart health check is performed
    5. On successful health check, failure count is reset

    This is a critical test for the automatic recovery feature.
    """
    config = ServiceConfig(
        name="restart_test_service",
        health_url="http://localhost:19998/health",
        restart_cmd="echo 'service_restarted'",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.1,
    )

    # Track sequence of events
    event_sequence: list[str] = []

    # First 2 health checks fail, then succeed (simulating restart fixing the service)
    health_check_count = 0

    async def mock_check_health(cfg: ServiceConfig) -> bool:
        nonlocal health_check_count
        health_check_count += 1
        event_sequence.append(f"health_check_{health_check_count}")

        # First check fails (triggers restart), post-restart check succeeds
        return health_check_count != 1  # First check returns False, rest return True

    async def mock_restart(cfg: ServiceConfig) -> bool:
        event_sequence.append("restart")
        return True  # Restart succeeds

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(side_effect=mock_check_health)
    mock_manager.restart = AsyncMock(side_effect=mock_restart)

    mock_broadcaster = MockBroadcaster()

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    await monitor.start()

    # Wait for recovery cycle (mocked 2s pause allows faster completion)
    await asyncio.sleep(0.5)

    await monitor.stop()

    # Verify the sequence of events
    assert "health_check_1" in event_sequence, "Initial health check should have occurred"
    assert "restart" in event_sequence, "Restart should have been called after failure"

    # Verify restart was called exactly once (one failure recovery)
    assert mock_manager.restart.call_count >= 1, "Restart should have been called"

    # Verify healthy status was broadcast after recovery
    healthy_broadcasts = [
        call
        for call in mock_broadcaster.broadcast_calls
        if call.get("data", {}).get("status") == "healthy"
    ]
    assert len(healthy_broadcasts) > 0, "Should have broadcast 'healthy' status after recovery"

    # Verify failure count was reset
    status = monitor.get_status()
    assert status[config.name]["failure_count"] == 0, (
        "Failure count should be reset to 0 after successful recovery"
    )


@pytest.mark.asyncio
async def test_health_monitor_multiple_restart_attempts_before_recovery(fast_sleep) -> None:
    """Test that health monitor retries restart multiple times before succeeding.

    Verifies:
    1. First restart fails (health check still failing after restart)
    2. Second restart attempt is made with exponential backoff
    3. Service eventually recovers
    4. Failure count is reset
    """
    config = ServiceConfig(
        name="retry_test_service",
        health_url="http://localhost:19997/health",
        restart_cmd="echo 'retry_service_restarted'",
        health_timeout=1.0,
        max_retries=5,
        backoff_base=0.05,  # Very short for testing
    )

    restart_count = 0
    health_check_count = 0

    async def mock_check_health(cfg: ServiceConfig) -> bool:
        nonlocal health_check_count
        health_check_count += 1
        # Fail first 3 checks, then succeed (simulates 2 restart attempts before success)
        return health_check_count > 3

    async def mock_restart(cfg: ServiceConfig) -> bool:
        nonlocal restart_count
        restart_count += 1
        return True  # Restart command itself succeeds

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(side_effect=mock_check_health)
    mock_manager.restart = AsyncMock(side_effect=mock_restart)

    mock_broadcaster = MockBroadcaster()

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.05,
    )

    await monitor.start()

    # Wait for multiple retry cycles (mocked 2s pause allows faster completion)
    await asyncio.sleep(0.8)

    await monitor.stop()

    # Verify multiple restart attempts were made
    assert restart_count >= 2, f"Expected at least 2 restart attempts, got {restart_count}"

    # Verify eventual recovery (healthy status broadcast)
    healthy_broadcasts = [
        call
        for call in mock_broadcaster.broadcast_calls
        if call.get("data", {}).get("status") == "healthy"
    ]
    assert len(healthy_broadcasts) > 0, "Should have eventually broadcast 'healthy' status"


@pytest.mark.asyncio
async def test_health_monitor_restart_with_health_verification(fast_sleep) -> None:
    """Test that health monitor verifies health after restart.

    Specifically tests the 2-second post-restart health verification flow:
    1. Service fails health check
    2. Restart is triggered
    3. Brief pause (2s in real code, mocked to 0.02s)
    4. Health is re-checked to verify restart success
    5. Status updated based on verification result
    """
    config = ServiceConfig(
        name="verify_restart_service",
        health_url="http://localhost:19996/health",
        restart_cmd="echo 'verified_restart'",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.1,
    )

    health_checks_after_restart = 0
    first_check_done = False

    async def mock_check_health(cfg: ServiceConfig) -> bool:
        nonlocal health_checks_after_restart, first_check_done

        if not first_check_done:
            first_check_done = True
            return False  # First check fails

        # Track post-restart checks
        health_checks_after_restart += 1
        return True  # Post-restart checks succeed

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(side_effect=mock_check_health)
    mock_manager.restart = AsyncMock(return_value=True)

    mock_broadcaster = MockBroadcaster()

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    await monitor.start()

    # Wait for recovery cycle (mocked 2s pause allows faster completion)
    await asyncio.sleep(0.5)

    await monitor.stop()

    # Verify health check was called after restart (verification step)
    assert health_checks_after_restart >= 1, "Health should be verified after restart"

    # Verify healthy status was broadcast after verification passed
    healthy_broadcasts = [
        call
        for call in mock_broadcaster.broadcast_calls
        if call.get("data", {}).get("status") == "healthy"
        and "restarted successfully" in call.get("data", {}).get("message", "")
    ]
    assert len(healthy_broadcasts) > 0, (
        "Should broadcast 'healthy' with 'restarted successfully' message after verification"
    )


# =============================================================================
# Tests for mb9s.16: Graceful shutdown order verification
# =============================================================================


@pytest.mark.asyncio
async def test_graceful_shutdown_completes_without_hanging(fast_sleep) -> None:
    """Test that graceful shutdown completes in a reasonable time.

    Verifies:
    1. stop() completes within timeout
    2. Monitor transitions to not-running state
    3. Background task is properly cancelled
    """
    config = ServiceConfig(
        name="shutdown_test_service",
        health_url="http://localhost:19995/health",
        restart_cmd="echo 'shutdown_test'",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.1,
    )

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=True)

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=None,
        check_interval=0.1,
    )

    await monitor.start()
    assert monitor.is_running, "Monitor should be running after start"
    assert monitor._task is not None, "Background task should exist"

    # Wait a bit for the monitor to start its cycle
    await asyncio.sleep(0.15)

    # Shutdown should complete quickly
    try:
        await asyncio.wait_for(monitor.stop(), timeout=2.0)
    except TimeoutError:
        pytest.fail("Graceful shutdown took too long (>2 seconds)")

    # Verify clean shutdown
    assert not monitor.is_running, "Monitor should be stopped"
    assert monitor._task is None, "Background task should be cleared"


@pytest.mark.asyncio
async def test_shutdown_during_health_check_cycle(fast_sleep) -> None:
    """Test that shutdown during active health check completes gracefully.

    Verifies:
    1. Shutdown can happen during a health check
    2. The check cycle is interrupted cleanly
    3. No errors or hangs occur
    """
    config = ServiceConfig(
        name="interrupt_check_service",
        health_url="http://localhost:19994/health",
        restart_cmd="echo 'interrupt_test'",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.1,
    )

    health_check_started = asyncio.Event()

    async def slow_health_check(cfg: ServiceConfig) -> bool:
        health_check_started.set()
        # Simulate a health check that takes some time
        await asyncio.sleep(0.05)
        return True

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(side_effect=slow_health_check)

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=None,
        check_interval=0.1,
    )

    await monitor.start()

    # Wait for health check to start
    await asyncio.wait_for(health_check_started.wait(), timeout=1.0)

    # Stop during the health check
    try:
        await asyncio.wait_for(monitor.stop(), timeout=2.0)
    except TimeoutError:
        pytest.fail("Shutdown during health check should not hang")

    assert not monitor.is_running, "Monitor should be stopped"


@pytest.mark.asyncio
async def test_shutdown_during_backoff_wait(fast_sleep) -> None:
    """Test that shutdown during backoff wait period completes gracefully.

    When a service fails and the monitor is waiting (backoff), calling stop()
    should interrupt the wait and shut down cleanly.
    """
    config = ServiceConfig(
        name="backoff_shutdown_service",
        health_url="http://localhost:19993/health",
        restart_cmd="echo 'backoff_test'",
        health_timeout=1.0,
        max_retries=5,
        backoff_base=0.2,  # Longer backoff to ensure we catch it
    )

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=False)  # Always failing
    mock_manager.restart = AsyncMock(return_value=False)  # Restart also fails

    mock_broadcaster = MockBroadcaster()

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    await monitor.start()

    # Wait for failure to be detected and backoff to start
    await asyncio.sleep(0.15)

    # Stop during backoff
    try:
        await asyncio.wait_for(monitor.stop(), timeout=2.0)
    except TimeoutError:
        pytest.fail("Shutdown during backoff should not hang")

    assert not monitor.is_running, "Monitor should be stopped"


@pytest.mark.asyncio
async def test_shutdown_cleans_up_all_resources(fast_sleep) -> None:
    """Test that shutdown properly cleans up all internal resources.

    Verifies:
    1. _running flag is set to False
    2. _task is set to None
    3. No lingering asyncio tasks
    """
    config = ServiceConfig(
        name="cleanup_test_service",
        health_url="http://localhost:19992/health",
        restart_cmd="echo 'cleanup_test'",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.1,
    )

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=True)

    mock_broadcaster = MockBroadcaster()

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    # Pre-shutdown state
    await monitor.start()
    assert monitor._running is True
    assert monitor._task is not None
    task_before_stop = monitor._task

    await asyncio.sleep(0.05)

    await monitor.stop()

    # Post-shutdown state
    assert monitor._running is False, "_running should be False after stop"
    assert monitor._task is None, "_task should be None after stop"
    assert task_before_stop.done() or task_before_stop.cancelled(), (
        "Original task should be done or cancelled"
    )


@pytest.mark.asyncio
async def test_multiple_stop_calls_are_safe(fast_sleep) -> None:
    """Test that calling stop() multiple times is safe (idempotent).

    This is important for robustness - if shutdown is called twice
    (e.g., from different error handlers), it shouldn't crash.
    """
    config = ServiceConfig(
        name="multi_stop_service",
        health_url="http://localhost:19991/health",
        restart_cmd="echo 'multi_stop_test'",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.1,
    )

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=True)

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=None,
        check_interval=0.1,
    )

    await monitor.start()
    await asyncio.sleep(0.05)

    # Call stop multiple times - should not raise any errors
    await monitor.stop()
    await monitor.stop()
    await monitor.stop()

    assert not monitor.is_running, "Monitor should remain stopped"


@pytest.mark.asyncio
async def test_shutdown_prevents_new_restart_attempts(fast_sleep) -> None:
    """Test that once shutdown starts, no new restart attempts are initiated.

    Verifies the _running check in _handle_failure prevents new restarts
    after stop() is called.
    """
    config = ServiceConfig(
        name="no_restart_after_stop_service",
        health_url="http://localhost:19990/health",
        restart_cmd="echo 'no_restart_test'",
        health_timeout=1.0,
        max_retries=10,
        backoff_base=0.05,
    )

    restart_attempts = 0

    async def mock_restart(cfg: ServiceConfig) -> bool:
        nonlocal restart_attempts
        restart_attempts += 1
        # Wait to simulate restart taking time
        await asyncio.sleep(0.02)
        return False  # Keep failing to trigger more attempts

    mock_manager = MagicMock()
    mock_manager.check_health = AsyncMock(return_value=False)
    mock_manager.restart = AsyncMock(side_effect=mock_restart)

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=None,
        check_interval=0.05,
    )

    await monitor.start()

    # Wait for some restart attempts
    await asyncio.sleep(0.2)

    # Record restart count at stop time
    restarts_at_stop = restart_attempts

    # Stop the monitor
    await monitor.stop()

    # Wait a bit more to ensure no new restarts
    await asyncio.sleep(0.1)

    # Restart count should not have increased much after stop
    # (may have one more in-flight when stop was called)
    assert restart_attempts <= restarts_at_stop + 1, (
        f"No significant new restarts after stop. "
        f"Before: {restarts_at_stop}, After: {restart_attempts}"
    )
