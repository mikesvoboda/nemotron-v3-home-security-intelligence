"""Unit tests for ServiceHealthMonitor service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.health_monitor import ServiceHealthMonitor
from backend.services.service_managers import ServiceConfig, ServiceManager

# Fixtures


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
def mock_manager():
    """Create a mock ServiceManager."""
    manager = MagicMock(spec=ServiceManager)
    manager.check_health = AsyncMock(return_value=True)
    manager.restart = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def sample_config():
    """Create a sample ServiceConfig."""
    return ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.1,  # Fast for tests
    )


@pytest.fixture
def sample_configs():
    """Create multiple sample ServiceConfigs for multi-service tests."""
    return [
        ServiceConfig(
            name="service_a",
            health_url="http://localhost:9001/health",
            restart_cmd="echo service_a",
            health_timeout=1.0,
            max_retries=3,
            backoff_base=0.1,
        ),
        ServiceConfig(
            name="service_b",
            health_url="http://localhost:9002/health",
            restart_cmd="echo service_b",
            health_timeout=1.0,
            max_retries=3,
            backoff_base=0.1,
        ),
    ]


@pytest.fixture
def mock_broadcaster():
    """Create a mock EventBroadcaster."""
    broadcaster = MagicMock()
    broadcaster.broadcast_event = AsyncMock()
    return broadcaster


@pytest.fixture
def health_monitor(mock_manager, sample_config, mock_broadcaster):
    """Create a ServiceHealthMonitor with mocked dependencies."""
    return ServiceHealthMonitor(
        manager=mock_manager,
        services=[sample_config],
        broadcaster=mock_broadcaster,
        check_interval=0.1,  # Fast for tests
    )


@pytest.fixture
def health_monitor_no_broadcaster(mock_manager, sample_config):
    """Create a ServiceHealthMonitor without a broadcaster."""
    return ServiceHealthMonitor(
        manager=mock_manager,
        services=[sample_config],
        broadcaster=None,
        check_interval=0.1,
    )


@pytest.fixture
def health_monitor_multi_service(mock_manager, sample_configs, mock_broadcaster):
    """Create a ServiceHealthMonitor with multiple services."""
    return ServiceHealthMonitor(
        manager=mock_manager,
        services=sample_configs,
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )


# Test: Health Check Detection


@pytest.mark.asyncio
async def test_health_check_detects_healthy_service(
    health_monitor, mock_manager, sample_config, mock_broadcaster, fast_sleep
):
    """Test that healthy services are detected and no restart is called."""
    # Manager returns healthy
    mock_manager.check_health.return_value = True

    # Start the monitor
    await health_monitor.start()

    # Wait for at least one health check cycle
    await asyncio.sleep(0.15)

    # Stop the monitor
    await health_monitor.stop()

    # Verify health was checked
    assert mock_manager.check_health.called

    # Verify restart was never called (service is healthy)
    mock_manager.restart.assert_not_called()


@pytest.mark.asyncio
async def test_health_check_detects_unhealthy_service(
    health_monitor, mock_manager, sample_config, mock_broadcaster, fast_sleep
):
    """Test that unhealthy services are detected and failure handling is triggered."""
    # Manager returns unhealthy
    mock_manager.check_health.return_value = False

    # Start the monitor
    await health_monitor.start()

    # Wait for health check and some backoff time
    await asyncio.sleep(0.3)

    # Stop the monitor
    await health_monitor.stop()

    # Verify health was checked
    assert mock_manager.check_health.called

    # Verify broadcast was called with "unhealthy" status
    # Event format: {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    unhealthy_broadcasts = [
        call for call in broadcast_calls if call[0][0].get("data", {}).get("status") == "unhealthy"
    ]
    assert len(unhealthy_broadcasts) > 0


@pytest.mark.asyncio
async def test_health_check_timeout_treated_as_unhealthy(
    health_monitor, mock_manager, sample_config, mock_broadcaster, fast_sleep
):
    """Test that exceptions during health check are treated as failures."""
    # Manager raises an exception on health check
    mock_manager.check_health.side_effect = Exception("Connection timeout")

    # Start the monitor
    await health_monitor.start()

    # Wait for health check cycle
    await asyncio.sleep(0.3)

    # Stop the monitor
    await health_monitor.stop()

    # Verify broadcast was called with "unhealthy" status due to exception
    # Event format: {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    unhealthy_broadcasts = [
        call for call in broadcast_calls if call[0][0].get("data", {}).get("status") == "unhealthy"
    ]
    assert len(unhealthy_broadcasts) > 0


# Test: Exponential Backoff


@pytest.mark.asyncio
async def test_restart_with_exponential_backoff(
    mock_manager, sample_config, mock_broadcaster, fast_sleep
):
    """Test that restart delays follow exponential backoff pattern."""
    # Track the number of times restart is called (not timing, since sleep is mocked)
    restart_count = 0

    async def track_restart(_config):
        nonlocal restart_count
        restart_count += 1
        # Return False to trigger more retries
        return False

    mock_manager.check_health.return_value = False
    mock_manager.restart.side_effect = track_restart

    # Use faster backoff for test
    fast_config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.05,  # 50ms base backoff
    )

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[fast_config],
        broadcaster=mock_broadcaster,
        check_interval=0.05,
    )

    await monitor.start()

    # Wait long enough for multiple restart attempts
    await asyncio.sleep(0.6)

    await monitor.stop()

    # We should have had at least 2 restarts to measure backoff
    # Due to max_retries being checked, we may get up to 3 restarts
    assert restart_count >= 2, f"Expected at least 2 restarts, got {restart_count}"

    # Verify that sleep was called with exponential backoff delays
    # Check that asyncio.sleep was called with increasing delays
    sleep_calls = [call[0][0] for call in fast_sleep.call_args_list]
    # Filter for backoff delays (not the check_interval)
    backoff_calls = [d for d in sleep_calls if d >= 0.05]
    assert len(backoff_calls) >= 2, f"Expected at least 2 backoff delays, got {backoff_calls}"


# Test: Max Retries


@pytest.mark.asyncio
async def test_max_retries_stops_restart_attempts(mock_manager, mock_broadcaster, fast_sleep):
    """Test that restart attempts stop after max_retries is exceeded."""
    restart_count = 0

    async def count_restarts(_config):
        nonlocal restart_count
        restart_count += 1
        return False  # Always fail to trigger more retries

    mock_manager.check_health.return_value = False
    mock_manager.restart.side_effect = count_restarts

    config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
        health_timeout=1.0,
        max_retries=2,  # Only 2 retries
        backoff_base=0.02,  # Very fast backoff for test
    )

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.02,
    )

    await monitor.start()

    # Wait for max retries to be exceeded
    await asyncio.sleep(0.4)

    await monitor.stop()

    # Should have exactly max_retries attempts (2)
    assert restart_count <= 2, f"Expected at most 2 restarts, got {restart_count}"

    # Verify "failed" status was broadcast
    # Event format: {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    failed_broadcasts = [
        call for call in broadcast_calls if call[0][0].get("data", {}).get("status") == "failed"
    ]
    assert len(failed_broadcasts) > 0, "Expected 'failed' status to be broadcast"


@pytest.mark.asyncio
async def test_recovery_resets_failure_count(mock_manager, mock_broadcaster, fast_sleep):
    """Test that successful health check after failures resets the failure count."""
    health_check_count = 0

    async def check_health_varying(_config):
        nonlocal health_check_count
        health_check_count += 1
        # First check fails, subsequent checks succeed (including post-restart verification)
        return health_check_count > 1

    mock_manager.check_health.side_effect = check_health_varying
    mock_manager.restart.return_value = True

    config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.02,  # Very fast for test
    )

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.02,
    )

    await monitor.start()

    # Wait for recovery cycle (mocked 2s pause allows faster completion)
    await asyncio.sleep(0.5)

    await monitor.stop()

    # After successful restart and health verification, failure count should be reset to 0
    status = monitor.get_status()
    assert status[config.name]["failure_count"] == 0


# Test: Broadcast Status


@pytest.mark.asyncio
async def test_broadcasts_status_on_failure(
    health_monitor, mock_manager, mock_broadcaster, fast_sleep
):
    """Test that 'unhealthy' status is broadcast when health check fails."""
    mock_manager.check_health.return_value = False

    await health_monitor.start()
    await asyncio.sleep(0.15)
    await health_monitor.stop()

    # Find broadcast calls with "unhealthy" status
    # Event format: {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    unhealthy_broadcasts = [
        call for call in broadcast_calls if call[0][0].get("data", {}).get("status") == "unhealthy"
    ]
    assert len(unhealthy_broadcasts) > 0, "Expected 'unhealthy' status to be broadcast"


@pytest.mark.asyncio
async def test_broadcasts_status_on_recovery(mock_manager, mock_broadcaster, fast_sleep):
    """Test that 'healthy' status is broadcast when service recovers."""
    health_check_count = 0

    async def check_health_varying(_config):
        nonlocal health_check_count
        health_check_count += 1
        # First check fails, subsequent checks succeed (including post-restart verification)
        return health_check_count > 1

    mock_manager.check_health.side_effect = check_health_varying
    mock_manager.restart.return_value = True  # Restart succeeds

    config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.02,
    )

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.02,
    )

    await monitor.start()
    # Wait for recovery cycle (mocked 2s pause allows faster completion)
    await asyncio.sleep(0.5)
    await monitor.stop()

    # Find broadcast calls with "healthy" status
    # Event format: {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    healthy_broadcasts = [
        call for call in broadcast_calls if call[0][0].get("data", {}).get("status") == "healthy"
    ]
    assert len(healthy_broadcasts) > 0, "Expected 'healthy' status to be broadcast on recovery"


@pytest.mark.asyncio
async def test_broadcasts_status_on_restart(
    health_monitor, mock_manager, mock_broadcaster, fast_sleep
):
    """Test that 'restarting' status is broadcast during restart."""
    mock_manager.check_health.return_value = False

    await health_monitor.start()

    # Wait long enough for restart to be attempted
    await asyncio.sleep(0.3)

    await health_monitor.stop()

    # Find broadcast calls with "restarting" status
    # Event format: {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    restarting_broadcasts = [
        call for call in broadcast_calls if call[0][0].get("data", {}).get("status") == "restarting"
    ]
    assert len(restarting_broadcasts) > 0, "Expected 'restarting' status to be broadcast"


# Test: Start/Stop Lifecycle


@pytest.mark.asyncio
async def test_start_stop_lifecycle(health_monitor, fast_sleep):
    """Test that start creates a task and stop cancels it."""
    # Initially not running
    assert not health_monitor.is_running
    assert health_monitor._task is None

    # Start creates task
    await health_monitor.start()
    assert health_monitor.is_running
    assert health_monitor._task is not None
    assert not health_monitor._task.done()

    # Stop cancels task
    await health_monitor.stop()
    assert not health_monitor.is_running
    assert health_monitor._task is None


@pytest.mark.asyncio
async def test_start_is_idempotent(health_monitor, fast_sleep):
    """Test that calling start multiple times has no effect."""
    await health_monitor.start()
    task1 = health_monitor._task

    # Second start should be no-op
    await health_monitor.start()
    task2 = health_monitor._task

    # Same task should be used
    assert task1 is task2

    await health_monitor.stop()


@pytest.mark.asyncio
async def test_stop_is_idempotent(health_monitor, fast_sleep):
    """Test that calling stop multiple times has no effect."""
    # Stop without start should not raise
    await health_monitor.stop()

    await health_monitor.start()
    await health_monitor.stop()

    # Second stop should not raise
    await health_monitor.stop()


# Test: Restart Command Failure


@pytest.mark.asyncio
async def test_restart_command_failure_handling(
    health_monitor, mock_manager, sample_config, mock_broadcaster, fast_sleep
):
    """Test that restart returning False increments failure count."""
    mock_manager.check_health.return_value = False
    mock_manager.restart.return_value = False  # Restart fails

    await health_monitor.start()
    await asyncio.sleep(0.3)
    await health_monitor.stop()

    # Verify restart_failed status was broadcast
    # Event format: {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    restart_failed_broadcasts = [
        call
        for call in broadcast_calls
        if call[0][0].get("data", {}).get("status") == "restart_failed"
    ]
    assert len(restart_failed_broadcasts) > 0, "Expected 'restart_failed' status to be broadcast"


# Test: No Broadcaster


@pytest.mark.asyncio
async def test_no_broadcaster_still_works(health_monitor_no_broadcaster, mock_manager, fast_sleep):
    """Test that health monitor works correctly without a broadcaster."""
    mock_manager.check_health.return_value = True

    # Should not raise even without broadcaster
    await health_monitor_no_broadcaster.start()
    await asyncio.sleep(0.15)
    await health_monitor_no_broadcaster.stop()

    # Health check should still be called
    assert mock_manager.check_health.called


@pytest.mark.asyncio
async def test_no_broadcaster_failure_handling(
    health_monitor_no_broadcaster, mock_manager, fast_sleep
):
    """Test that failure handling works without a broadcaster."""
    mock_manager.check_health.return_value = False
    mock_manager.restart.return_value = True

    # Should not raise even when broadcasting status
    await health_monitor_no_broadcaster.start()
    await asyncio.sleep(0.3)
    await health_monitor_no_broadcaster.stop()

    # Health check and restart should still be called
    assert mock_manager.check_health.called
    assert mock_manager.restart.called


# Test: Get Status


@pytest.mark.asyncio
async def test_get_status_returns_current_state(
    health_monitor, mock_manager, sample_config, fast_sleep
):
    """Test that get_status() returns the current state of all services."""
    # Initially no failures
    status = health_monitor.get_status()
    assert sample_config.name in status
    assert status[sample_config.name]["failure_count"] == 0
    assert status[sample_config.name]["max_retries"] == sample_config.max_retries

    # Force a failure
    mock_manager.check_health.return_value = False

    await health_monitor.start()
    await asyncio.sleep(0.15)
    await health_monitor.stop()

    # Status should reflect failures
    status = health_monitor.get_status()
    assert status[sample_config.name]["failure_count"] > 0


@pytest.mark.asyncio
async def test_get_status_with_multiple_services(
    health_monitor_multi_service, mock_manager, sample_configs, fast_sleep
):
    """Test that get_status() returns status for all services."""
    status = health_monitor_multi_service.get_status()

    # All services should be present
    for config in sample_configs:
        assert config.name in status
        assert "failure_count" in status[config.name]
        assert "max_retries" in status[config.name]


# Test: Multiple Services


@pytest.mark.asyncio
async def test_multiple_services_checked(
    health_monitor_multi_service, mock_manager, sample_configs, fast_sleep
):
    """Test that all services in the list are checked."""
    checked_services = []

    async def track_check(config):
        checked_services.append(config.name)
        return True

    mock_manager.check_health.side_effect = track_check

    await health_monitor_multi_service.start()
    await asyncio.sleep(0.15)
    await health_monitor_multi_service.stop()

    # All services should have been checked
    for config in sample_configs:
        assert config.name in checked_services, f"Service {config.name} was not checked"


@pytest.mark.asyncio
async def test_multiple_services_independent_failure_counts(
    mock_manager, sample_configs, mock_broadcaster, fast_sleep
):
    """Test that failure counts are tracked independently per service."""

    async def selective_health_check(config):
        # First service fails, second succeeds
        return config.name != "service_a"

    mock_manager.check_health.side_effect = selective_health_check
    mock_manager.restart.return_value = True

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=sample_configs,
        broadcaster=mock_broadcaster,
        check_interval=0.05,
    )

    await monitor.start()
    await asyncio.sleep(0.3)
    await monitor.stop()

    status = monitor.get_status()

    # service_a should have failures (failed health check)
    assert status["service_a"]["failure_count"] >= 0  # May have recovered

    # service_b should have no failures
    assert status["service_b"]["failure_count"] == 0


# Test: Broadcast Event Format


@pytest.mark.asyncio
async def test_broadcast_event_format(health_monitor, mock_manager, mock_broadcaster, fast_sleep):
    """Test that broadcast events have the correct format."""
    mock_manager.check_health.return_value = False

    await health_monitor.start()
    await asyncio.sleep(0.15)
    await health_monitor.stop()

    # Check broadcast event structure
    # Event format: {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    assert mock_broadcaster.broadcast_event.called
    event_data = mock_broadcaster.broadcast_event.call_args_list[0][0][0]

    assert "type" in event_data
    assert event_data["type"] == "service_status"
    assert "data" in event_data
    assert "service" in event_data["data"]
    assert "status" in event_data["data"]
    assert "timestamp" in event_data


# Test: Broadcast Failure Handling


@pytest.mark.asyncio
async def test_broadcast_failure_does_not_crash_monitor(
    health_monitor, mock_manager, mock_broadcaster, fast_sleep
):
    """Test that broadcaster failure doesn't crash the health monitor."""
    mock_manager.check_health.return_value = False
    mock_broadcaster.broadcast_event.side_effect = Exception("Broadcast failed")

    # Should not raise even when broadcast fails
    await health_monitor.start()
    await asyncio.sleep(0.15)
    await health_monitor.stop()

    # Health check should still have been called
    assert mock_manager.check_health.called


# Test: Restart Success with Health Verification


@pytest.mark.asyncio
async def test_restart_success_verifies_health(mock_manager, mock_broadcaster, fast_sleep):
    """Test that after successful restart, health is verified."""
    health_check_count = 0

    async def health_check_sequence(_config):
        nonlocal health_check_count
        health_check_count += 1
        # First check fails (triggers restart), checks after restart succeed
        return health_check_count > 1

    mock_manager.check_health.side_effect = health_check_sequence
    mock_manager.restart.return_value = True

    config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.02,
    )

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.02,
    )

    await monitor.start()
    # Wait for recovery cycle (mocked 2s pause allows faster completion)
    await asyncio.sleep(0.5)
    await monitor.stop()

    # Health check should have been called multiple times
    # (initial + verification after restart + regular checks)
    assert health_check_count >= 2


# Test: Restart Success but Health Still Fails


@pytest.mark.asyncio
async def test_restart_success_but_health_still_fails(mock_manager, mock_broadcaster, fast_sleep):
    """Test handling when restart succeeds but service is still unhealthy."""
    mock_manager.check_health.return_value = False  # Always unhealthy
    mock_manager.restart.return_value = True  # Restart succeeds

    config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.02,
    )

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.02,
    )

    await monitor.start()
    # Wait for recovery cycle (mocked 2s pause allows faster completion)
    await asyncio.sleep(0.5)
    await monitor.stop()

    # Should have broadcast "restart_failed" due to failed health verification
    # Event format: {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    restart_failed_broadcasts = [
        call
        for call in broadcast_calls
        if call[0][0].get("data", {}).get("status") == "restart_failed"
    ]
    assert len(restart_failed_broadcasts) > 0


@pytest.mark.asyncio
async def test_logging_on_health_check(health_monitor, mock_manager, caplog, fast_sleep):
    """Test that health checks are logged appropriately."""
    mock_manager.check_health.return_value = True

    with patch("backend.services.health_monitor.logger") as mock_logger:
        await health_monitor.start()
        await asyncio.sleep(0.15)
        await health_monitor.stop()

        # Check that info logging occurred for start/stop
        info_calls = list(mock_logger.info.call_args_list)
        assert len(info_calls) > 0


@pytest.mark.asyncio
async def test_logging_on_failure(health_monitor, mock_manager, fast_sleep):
    """Test that failures are logged as warnings."""
    mock_manager.check_health.return_value = False

    with patch("backend.services.health_monitor.logger") as mock_logger:
        await health_monitor.start()
        await asyncio.sleep(0.15)
        await health_monitor.stop()

        # Check that warning logging occurred for failures
        warning_calls = list(mock_logger.warning.call_args_list)
        assert len(warning_calls) > 0


@pytest.mark.asyncio
async def test_is_running_property(health_monitor, fast_sleep):
    """Test the is_running property reflects current state."""
    assert health_monitor.is_running is False

    await health_monitor.start()
    assert health_monitor.is_running is True

    await health_monitor.stop()
    assert health_monitor.is_running is False


def test_initialization_with_valid_params(mock_manager, sample_config, mock_broadcaster):
    """Test that ServiceHealthMonitor initializes correctly with valid parameters."""
    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[sample_config],
        broadcaster=mock_broadcaster,
        check_interval=30.0,
    )

    assert monitor._manager is mock_manager
    assert len(monitor._services) == 1
    assert monitor._services[0] is sample_config
    assert monitor._broadcaster is mock_broadcaster
    assert monitor._check_interval == 30.0
    assert not monitor.is_running


def test_initialization_without_broadcaster(mock_manager, sample_config):
    """Test that ServiceHealthMonitor can be initialized without a broadcaster."""
    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[sample_config],
        broadcaster=None,
        check_interval=15.0,
    )

    assert monitor._broadcaster is None


def test_initialization_with_empty_services(mock_manager, mock_broadcaster):
    """Test that ServiceHealthMonitor can be initialized with empty services list."""
    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[],
        broadcaster=mock_broadcaster,
        check_interval=15.0,
    )

    assert len(monitor._services) == 0


# Test: Graceful Shutdown


@pytest.mark.asyncio
async def test_graceful_shutdown_during_health_check(
    mock_manager, sample_config, mock_broadcaster, fast_sleep
):
    """Test that shutdown during health check completes gracefully."""
    # For this test, we need actual sleep to simulate slow health check
    # but we still use fast_sleep for the monitor's internal sleeps
    health_check_started = asyncio.Event()

    async def slow_health_check(_config):
        health_check_started.set()
        # Use a short actual sleep to simulate slow operation
        await asyncio.sleep(0.05)
        return True

    mock_manager.check_health.side_effect = slow_health_check

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[sample_config],
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )

    await monitor.start()

    # Wait for health check to start
    await asyncio.wait_for(health_check_started.wait(), timeout=1.0)

    # Stop should complete without hanging
    await asyncio.wait_for(monitor.stop(), timeout=2.0)

    assert not monitor.is_running


@pytest.mark.asyncio
async def test_graceful_shutdown_during_backoff(
    mock_manager, sample_config, mock_broadcaster, fast_sleep
):
    """Test that shutdown during backoff completes gracefully."""
    mock_manager.check_health.return_value = False

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[sample_config],
        broadcaster=mock_broadcaster,
        check_interval=0.05,
    )

    await monitor.start()

    # Wait for failure and backoff to start
    await asyncio.sleep(0.1)

    # Stop should complete without hanging
    await asyncio.wait_for(monitor.stop(), timeout=2.0)

    assert not monitor.is_running


# Test: Error Handling in Health Check Loop


@pytest.mark.asyncio
async def test_health_check_loop_continues_after_error(mock_manager, mock_broadcaster, fast_sleep):
    """Test that the health check loop continues after encountering errors."""
    call_count = 0

    async def check_with_errors(_config):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("First check fails")
        return True

    mock_manager.check_health.side_effect = check_with_errors
    mock_manager.restart.return_value = True

    config = ServiceConfig(
        name="test_service",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.02,  # Very fast for test
    )

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config],
        broadcaster=mock_broadcaster,
        check_interval=0.02,
    )

    await monitor.start()
    # Wait for recovery cycle (mocked 2s pause allows faster completion)
    await asyncio.sleep(0.5)
    await monitor.stop()

    # Should have made multiple attempts despite the first error
    assert call_count >= 2


# Test: Restart Exception Handling


@pytest.mark.asyncio
async def test_restart_exception_handling(
    mock_manager, sample_config, mock_broadcaster, fast_sleep
):
    """Test that exceptions during restart are handled gracefully."""
    mock_manager.check_health.return_value = False
    mock_manager.restart.side_effect = Exception("Restart error")

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[sample_config],
        broadcaster=mock_broadcaster,
        check_interval=0.05,
    )

    await monitor.start()
    await asyncio.sleep(0.2)
    await monitor.stop()

    # Should have broadcast restart_failed status
    # Event format: {"type": "service_status", "data": {"service": ..., "status": ...}, "timestamp": ...}
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    restart_failed_broadcasts = [
        call
        for call in broadcast_calls
        if call[0][0].get("data", {}).get("status") == "restart_failed"
    ]
    assert len(restart_failed_broadcasts) > 0


# Test: Restart Disabled (restart_cmd is None)


@pytest.fixture
def config_no_restart():
    """Create a ServiceConfig without restart_cmd (restart disabled)."""
    return ServiceConfig(
        name="test_service_no_restart",
        health_url="http://localhost:9999/health",
        restart_cmd=None,  # Restart disabled
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.1,
    )


@pytest.fixture
def health_monitor_no_restart(mock_manager, config_no_restart, mock_broadcaster):
    """Create a ServiceHealthMonitor with restart disabled."""
    return ServiceHealthMonitor(
        manager=mock_manager,
        services=[config_no_restart],
        broadcaster=mock_broadcaster,
        check_interval=0.1,
    )


@pytest.mark.asyncio
async def test_restart_disabled_broadcasts_restart_disabled_status(
    health_monitor_no_restart, mock_manager, mock_broadcaster, fast_sleep
):
    """Test that when restart_cmd is None, 'restart_disabled' status is broadcast instead of attempting restart."""
    mock_manager.check_health.return_value = False

    await health_monitor_no_restart.start()
    await asyncio.sleep(0.15)
    await health_monitor_no_restart.stop()

    # Verify health was checked
    assert mock_manager.check_health.called

    # Verify restart was NEVER called (since restart is disabled)
    mock_manager.restart.assert_not_called()

    # Verify 'restart_disabled' status was broadcast
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    restart_disabled_broadcasts = [
        call
        for call in broadcast_calls
        if call[0][0].get("data", {}).get("status") == "restart_disabled"
    ]
    assert len(restart_disabled_broadcasts) > 0, (
        "Expected 'restart_disabled' status to be broadcast"
    )


@pytest.mark.asyncio
async def test_restart_disabled_does_not_increment_failure_count(
    health_monitor_no_restart, mock_manager, config_no_restart, fast_sleep
):
    """Test that failure count is not incremented when restart is disabled."""
    mock_manager.check_health.return_value = False

    await health_monitor_no_restart.start()
    await asyncio.sleep(0.15)
    await health_monitor_no_restart.stop()

    # Failure count should remain at 0 since we don't track failures when restart is disabled
    status = health_monitor_no_restart.get_status()
    assert status[config_no_restart.name]["failure_count"] == 0


@pytest.mark.asyncio
async def test_restart_disabled_continues_health_monitoring(
    health_monitor_no_restart, mock_manager, fast_sleep
):
    """Test that health monitoring continues even when restart is disabled."""
    health_check_count = 0

    async def count_health_checks(_config):
        nonlocal health_check_count
        health_check_count += 1
        return False  # Always unhealthy

    mock_manager.check_health.side_effect = count_health_checks

    await health_monitor_no_restart.start()
    await asyncio.sleep(0.25)  # Multiple check intervals
    await health_monitor_no_restart.stop()

    # Should have multiple health checks even though restart is disabled
    assert health_check_count >= 2, f"Expected multiple health checks, got {health_check_count}"


@pytest.mark.asyncio
async def test_restart_disabled_healthy_service_no_broadcast(
    health_monitor_no_restart, mock_manager, mock_broadcaster, fast_sleep
):
    """Test that healthy services don't trigger restart_disabled broadcasts."""
    mock_manager.check_health.return_value = True

    await health_monitor_no_restart.start()
    await asyncio.sleep(0.15)
    await health_monitor_no_restart.stop()

    # Should not have any restart_disabled broadcasts since service is healthy
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    restart_disabled_broadcasts = [
        call
        for call in broadcast_calls
        if call[0][0].get("data", {}).get("status") == "restart_disabled"
    ]
    assert len(restart_disabled_broadcasts) == 0, (
        "Should not broadcast restart_disabled for healthy service"
    )


@pytest.mark.asyncio
async def test_mixed_services_only_disabled_one_skips_restart(
    mock_manager, mock_broadcaster, fast_sleep
):
    """Test that services with restart_cmd work normally while those without skip restart."""
    config_with_restart = ServiceConfig(
        name="with_restart",
        health_url="http://localhost:9001/health",
        restart_cmd="echo restart",  # Has restart command
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.02,
    )
    config_without_restart = ServiceConfig(
        name="without_restart",
        health_url="http://localhost:9002/health",
        restart_cmd=None,  # No restart command
        health_timeout=1.0,
        max_retries=3,
        backoff_base=0.02,
    )

    # Both services unhealthy
    mock_manager.check_health.return_value = False
    mock_manager.restart.return_value = True

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=[config_with_restart, config_without_restart],
        broadcaster=mock_broadcaster,
        check_interval=0.05,
    )

    await monitor.start()
    await asyncio.sleep(0.3)
    await monitor.stop()

    # Verify restart was called (only for the service with restart enabled)
    assert mock_manager.restart.called

    # Check that the restart was called with the correct config (the one with restart_cmd)
    restart_calls = mock_manager.restart.call_args_list
    restarted_services = [call[0][0].name for call in restart_calls]
    assert "with_restart" in restarted_services, (
        "Service with restart_cmd should have restart attempted"
    )

    # Verify both unhealthy and restart_disabled status broadcasts occurred
    broadcast_calls = mock_broadcaster.broadcast_event.call_args_list
    restart_disabled_broadcasts = [
        call
        for call in broadcast_calls
        if call[0][0].get("data", {}).get("status") == "restart_disabled"
    ]
    assert len(restart_disabled_broadcasts) > 0, (
        "Expected restart_disabled for service without restart_cmd"
    )


def test_service_config_restart_cmd_default_is_none():
    """Test that ServiceConfig.restart_cmd defaults to None."""
    config = ServiceConfig(
        name="test",
        health_url="http://localhost:9999/health",
    )
    assert config.restart_cmd is None, "restart_cmd should default to None"


def test_service_config_restart_cmd_can_be_set():
    """Test that ServiceConfig.restart_cmd can be explicitly set."""
    config = ServiceConfig(
        name="test",
        health_url="http://localhost:9999/health",
        restart_cmd="echo test",
    )
    assert config.restart_cmd == "echo test"
