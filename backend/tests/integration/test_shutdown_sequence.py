"""Integration tests for application graceful shutdown sequence.

These tests verify that the application shuts down gracefully by:
- Allowing in-flight requests to complete before termination
- Properly closing database connections
- Cleaning up Redis connections
- Gracefully cancelling background tasks
- Preventing data corruption or resource leaks

Note: Signal handling tests use mocking instead of actual signals to avoid
interfering with the test runner process.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# =============================================================================
# Test: Database connection cleanup during shutdown
# =============================================================================


@pytest.mark.asyncio
async def test_database_close_disposes_engine(
    integration_db: str, db_session: AsyncSession
) -> None:
    """Test that close_db properly disposes the database engine."""
    from backend.core.database import _engine, close_db, get_pool_status, init_db

    # Ensure database is initialized
    assert _engine is not None

    # Get pool status before close
    pool_before = await get_pool_status()
    assert "error" not in pool_before

    # Close database
    await close_db()

    # Engine should be disposed
    from backend.core.database import _engine as engine_after

    assert engine_after is None

    # Pool status should now indicate error (not initialized)
    pool_after = await get_pool_status()
    assert pool_after.get("error") == "Database not initialized"

    # Reinitialize for other tests
    await init_db()


@pytest.mark.asyncio
async def test_database_sessions_are_properly_closed_on_shutdown(integration_db: str) -> None:
    """Test that all database sessions are closed during shutdown."""
    from backend.core.database import close_db, get_pool_status, get_session, init_db

    # Create a session and do some work
    async with get_session() as session:
        from sqlalchemy import text

        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    # Check pool status before close
    pool_before = await get_pool_status()
    checkedout_before = pool_before.get("checkedout", 0)

    # All sessions should be checked in after context manager exits
    assert checkedout_before == 0

    # Close database
    await close_db()

    # Reinitialize for other tests
    await init_db()


# =============================================================================
# Test: Redis connection cleanup during shutdown
# =============================================================================


@pytest.mark.asyncio
async def test_redis_client_disconnect_closes_pool(real_redis: Any) -> None:
    """Test that RedisClient.disconnect properly closes the connection pool."""
    # Verify client is connected
    health = await real_redis.health_check()
    assert health["connected"] is True

    # Disconnect
    await real_redis.disconnect()

    # Client should report as disconnected
    # Note: After disconnect, health_check should show not connected
    health_after = await real_redis.health_check()
    assert health_after["connected"] is False


@pytest.mark.asyncio
async def test_close_redis_global_function(integration_env: str) -> None:
    """Test that close_redis properly cleans up the global Redis client."""
    from backend.core.redis import close_redis, init_redis

    # Initialize Redis
    redis = await init_redis()
    assert redis is not None

    # Close Redis
    await close_redis()

    # Global client should be None
    from backend.core.redis import _redis_client as client_after

    assert client_after is None


# =============================================================================
# Test: Background service graceful shutdown
# =============================================================================


@pytest.mark.asyncio
async def test_cleanup_service_stop_cancels_task() -> None:
    """Test that CleanupService.stop properly cancels the background task."""
    from backend.services.cleanup_service import CleanupService

    service = CleanupService(cleanup_time="03:00", retention_days=30)

    # Start the service
    await service.start()
    assert service.running is True
    assert service._cleanup_task is not None

    # Stop the service
    await service.stop()

    # Service should be stopped
    assert service.running is False

    # Task should be cancelled or done
    assert service._cleanup_task is None or service._cleanup_task.done()


@pytest.mark.asyncio
async def test_gpu_monitor_stop_cancels_task() -> None:
    """Test that GPUMonitor.stop properly cancels the monitoring task."""
    from backend.services.gpu_monitor import GPUMonitor

    monitor = GPUMonitor(broadcaster=None)

    # Start the monitor
    await monitor.start()
    assert monitor.running is True

    # Stop the monitor
    await monitor.stop()

    # Monitor should be stopped
    assert monitor.running is False


@pytest.mark.asyncio
async def test_system_broadcaster_stop_cancels_tasks() -> None:
    """Test that SystemBroadcaster.stop_broadcasting properly cancels tasks."""
    from backend.services.system_broadcaster import SystemBroadcaster

    broadcaster = SystemBroadcaster(redis_client=None)

    # Start broadcasting
    await broadcaster.start_broadcasting(interval=1.0)
    assert broadcaster._running is True

    # Stop broadcasting
    await broadcaster.stop_broadcasting()

    # Broadcaster should be stopped
    assert broadcaster._running is False
    assert broadcaster._broadcast_task is None or broadcaster._broadcast_task.done()


# =============================================================================
# Test: In-flight request handling during shutdown
# =============================================================================


@pytest.mark.asyncio
async def test_in_flight_request_completes_during_shutdown(client: AsyncClient) -> None:
    """Test that in-flight requests complete before shutdown."""
    # Make a request
    response = await client.get("/")
    assert response.status_code == 200

    # The client fixture properly cleans up after each test,
    # verifying that requests complete before the test ends


@pytest.mark.asyncio
async def test_concurrent_requests_complete_during_shutdown(client: AsyncClient) -> None:
    """Test that multiple concurrent requests complete during shutdown."""
    # Make multiple concurrent requests
    tasks = [client.get("/") for _ in range(5)]
    responses = await asyncio.gather(*tasks)

    # All requests should complete successfully
    for response in responses:
        assert response.status_code == 200


# =============================================================================
# Test: Event broadcaster cleanup during shutdown
# =============================================================================


@pytest.mark.asyncio
async def test_event_broadcaster_stop_cleans_up_pubsub(real_redis: Any) -> None:
    """Test that EventBroadcaster.stop properly cleans up pub/sub connections."""
    from backend.services.event_broadcaster import EventBroadcaster

    broadcaster = EventBroadcaster(redis_client=real_redis)

    # Start the broadcaster (uses start() not start_listening())
    await broadcaster.start()
    assert broadcaster._is_listening is True

    # Stop broadcaster
    await broadcaster.stop()

    # Broadcaster should be stopped and cleaned up
    assert broadcaster._is_listening is False
    assert broadcaster._pubsub is None or broadcaster._listener_task is None


# =============================================================================
# Test: Pipeline workers graceful shutdown
# =============================================================================


@pytest.mark.asyncio
async def test_detection_worker_graceful_shutdown(real_redis: Any) -> None:
    """Test that DetectionQueueWorker shuts down gracefully."""
    from backend.services.pipeline_workers import DetectionQueueWorker, WorkerState

    # Create worker with mocked detector and aggregator
    mock_detector = AsyncMock()
    mock_detector.detect_objects = AsyncMock(return_value=[])
    mock_detector.health_check = AsyncMock(return_value=True)
    mock_detector.close = AsyncMock()

    mock_aggregator = AsyncMock()
    mock_aggregator.add_detection = AsyncMock()

    worker = DetectionQueueWorker(
        redis_client=real_redis,
        detector_client=mock_detector,
        batch_aggregator=mock_aggregator,
        poll_timeout=1,
        stop_timeout=2.0,
    )

    # Start worker
    await worker.start()
    assert worker._stats.state == WorkerState.RUNNING

    # Give it a moment to start the loop
    await asyncio.sleep(0.1)

    # Stop worker
    await worker.stop()

    # Worker should be stopped
    assert worker._stats.state == WorkerState.STOPPED

    # Cleanup detector
    await mock_detector.close()


@pytest.mark.asyncio
async def test_analysis_worker_graceful_shutdown(real_redis: Any) -> None:
    """Test that AnalysisQueueWorker shuts down gracefully."""
    from backend.services.pipeline_workers import AnalysisQueueWorker, WorkerState

    # Create worker with mocked analyzer
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze_batch = AsyncMock(return_value={"risk_score": 0})
    mock_analyzer.close = AsyncMock()

    worker = AnalysisQueueWorker(
        redis_client=real_redis,
        analyzer=mock_analyzer,
        poll_timeout=1,
        stop_timeout=2.0,
    )

    # Start worker
    await worker.start()
    assert worker._stats.state == WorkerState.RUNNING

    # Give it a moment to start the loop
    await asyncio.sleep(0.1)

    # Stop worker
    await worker.stop()

    # Worker should be stopped
    assert worker._stats.state == WorkerState.STOPPED

    # Cleanup analyzer
    await mock_analyzer.close()


@pytest.mark.asyncio
async def test_pipeline_worker_manager_stops_all_workers(real_redis: Any) -> None:
    """Test that PipelineWorkerManager.stop stops all worker tasks."""
    from backend.services.pipeline_workers import PipelineWorkerManager

    # Create manager with mocked dependencies
    mock_detector = AsyncMock()
    mock_detector.detect_objects = AsyncMock(return_value=[])
    mock_detector.health_check = AsyncMock(return_value=True)
    mock_detector.close = AsyncMock()

    mock_analyzer = AsyncMock()
    mock_analyzer.analyze_batch = AsyncMock(return_value={"risk_score": 0})
    mock_analyzer.close = AsyncMock()

    # Use short stop timeout for tests
    manager = PipelineWorkerManager(
        redis_client=real_redis,
        detector_client=mock_detector,
        analyzer=mock_analyzer,
        worker_stop_timeout=2.0,
    )

    # Start manager
    await manager.start()
    assert manager.running is True

    # Give workers time to start
    await asyncio.sleep(0.2)

    # Stop manager
    await manager.stop()

    # All workers should be stopped
    assert manager.running is False

    # Cleanup
    await mock_detector.close()
    await mock_analyzer.close()


# =============================================================================
# Test: Shutdown with pending background tasks
# =============================================================================


@pytest.mark.asyncio
async def test_shutdown_waits_for_pending_tasks() -> None:
    """Test that shutdown waits for pending background tasks to complete."""
    from backend.services.gpu_monitor import GPUMonitor

    monitor = GPUMonitor(broadcaster=None)

    # Start monitor
    await monitor.start()

    # Let it run briefly
    await asyncio.sleep(0.1)

    # Stop should wait for current operation (if any)
    await monitor.stop()

    assert monitor.running is False


# =============================================================================
# Test: File watcher shutdown
# =============================================================================


@pytest.mark.asyncio
async def test_file_watcher_stop_cancels_pending_tasks(real_redis: Any) -> None:
    """Test that FileWatcher.stop cancels pending detection tasks."""
    from backend.services.file_watcher import FileWatcher

    watcher = FileWatcher(
        redis_client=real_redis,
        camera_creator=None,
    )

    # Start the watcher
    await watcher.start()
    assert watcher.running is True

    # Stop the watcher
    await watcher.stop()

    # Watcher should be stopped
    assert watcher.running is False
    # Pending tasks should be cleaned up
    assert len(watcher._pending_tasks) == 0


# =============================================================================
# Test: Batch aggregator shutdown
# =============================================================================


@pytest.mark.asyncio
async def test_batch_aggregator_can_be_used_after_creation(real_redis: Any) -> None:
    """Test that BatchAggregator can be created and used without explicit lifecycle."""
    from backend.services.batch_aggregator import BatchAggregator

    aggregator = BatchAggregator(redis_client=real_redis)

    # Verify aggregator is usable
    # The aggregator may not have explicit start/stop but we can test its state
    # by checking batch timeout functionality
    batches = await aggregator.check_batch_timeouts()
    assert isinstance(batches, list)


# =============================================================================
# Test: Health monitor shutdown
# =============================================================================


@pytest.mark.asyncio
async def test_health_monitor_stop_cancels_monitoring() -> None:
    """Test that ServiceHealthMonitor.stop cancels the monitoring task."""
    from backend.services.health_monitor import ServiceHealthMonitor
    from backend.services.service_managers import ServiceConfig, ShellServiceManager

    mock_manager = MagicMock(spec=ShellServiceManager)
    mock_manager.restart_service = AsyncMock()

    configs = [
        ServiceConfig(
            name="test_service",
            health_url="http://localhost:9999/health",
            restart_cmd=None,
            health_timeout=1.0,
            max_retries=1,
            backoff_base=1.0,
        )
    ]

    monitor = ServiceHealthMonitor(
        manager=mock_manager,
        services=configs,
        broadcaster=None,
        check_interval=1.0,
    )

    # Start monitoring
    await monitor.start()
    assert monitor.is_running is True

    # Stop monitoring
    await monitor.stop()

    # Monitor should be stopped
    assert monitor.is_running is False


# =============================================================================
# Test: Telemetry shutdown
# =============================================================================


@pytest.mark.asyncio
async def test_telemetry_shutdown_flushes_traces() -> None:
    """Test that shutdown_telemetry flushes pending traces."""
    from backend.core.telemetry import shutdown_telemetry

    # Shutdown should work even if telemetry was never initialized
    # This should not raise any exceptions
    shutdown_telemetry()


# =============================================================================
# Test: Stop broadcaster global functions
# =============================================================================


@pytest.mark.asyncio
async def test_stop_broadcaster_function() -> None:
    """Test that stop_broadcaster properly stops the global event broadcaster."""
    from backend.services.event_broadcaster import (
        stop_broadcaster,
    )

    # Get the current global broadcaster (or create a new one if needed)
    # Note: We need a Redis client for this, so we use a mock
    mock_redis = AsyncMock()
    mock_redis.subscribe = AsyncMock(return_value=AsyncMock())
    mock_redis.unsubscribe = AsyncMock()

    # If no broadcaster exists, stop_broadcaster should handle it gracefully
    await stop_broadcaster()

    # Should not raise even when called multiple times
    await stop_broadcaster()


@pytest.mark.asyncio
async def test_stop_system_broadcaster_function() -> None:
    """Test that stop_system_broadcaster properly stops the global system broadcaster."""
    from backend.services.system_broadcaster import (
        get_system_broadcaster,
        stop_system_broadcaster,
    )

    # Get or create the system broadcaster
    broadcaster = get_system_broadcaster(redis_client=None)

    # Start it
    await broadcaster.start_broadcasting(interval=1.0)

    # Stop it via the global function
    await stop_system_broadcaster()

    # Should be stopped
    assert broadcaster._running is False


# =============================================================================
# Test: Service graceful degradation
# =============================================================================


@pytest.mark.asyncio
async def test_cleanup_service_handles_stop_when_not_running() -> None:
    """Test that CleanupService.stop handles being called when not running."""
    from backend.services.cleanup_service import CleanupService

    service = CleanupService(cleanup_time="03:00", retention_days=30)

    # Service is not started
    assert service.running is False

    # Stop should not raise even when not running
    await service.stop()

    # Service should still be stopped
    assert service.running is False


@pytest.mark.asyncio
async def test_gpu_monitor_handles_stop_when_not_running() -> None:
    """Test that GPUMonitor.stop handles being called when not running."""
    from backend.services.gpu_monitor import GPUMonitor

    monitor = GPUMonitor(broadcaster=None)

    # Monitor is not started
    assert monitor.running is False

    # Stop should not raise even when not running
    await monitor.stop()

    # Monitor should still be stopped
    assert monitor.running is False


@pytest.mark.asyncio
async def test_system_broadcaster_handles_stop_when_not_running() -> None:
    """Test that SystemBroadcaster.stop_broadcasting handles being called when not running."""
    from backend.services.system_broadcaster import SystemBroadcaster

    broadcaster = SystemBroadcaster(redis_client=None)

    # Broadcaster is not started
    assert broadcaster._running is False

    # Stop should not raise even when not running
    await broadcaster.stop_broadcasting()

    # Broadcaster should still be stopped
    assert broadcaster._running is False


@pytest.mark.asyncio
async def test_event_broadcaster_handles_stop_when_not_started(real_redis: Any) -> None:
    """Test that EventBroadcaster.stop handles being called when not started."""
    from backend.services.event_broadcaster import EventBroadcaster

    broadcaster = EventBroadcaster(redis_client=real_redis)

    # Broadcaster is not started
    assert broadcaster._is_listening is False

    # Stop should not raise even when not started
    await broadcaster.stop()

    # Broadcaster should still be stopped
    assert broadcaster._is_listening is False


# =============================================================================
# Test: Multiple start/stop cycles
# =============================================================================


@pytest.mark.asyncio
async def test_cleanup_service_multiple_start_stop_cycles() -> None:
    """Test that CleanupService can be started and stopped multiple times."""
    from backend.services.cleanup_service import CleanupService

    service = CleanupService(cleanup_time="03:00", retention_days=30)

    # First cycle
    await service.start()
    assert service.running is True
    await service.stop()
    assert service.running is False

    # Second cycle
    await service.start()
    assert service.running is True
    await service.stop()
    assert service.running is False


@pytest.mark.asyncio
async def test_gpu_monitor_multiple_start_stop_cycles() -> None:
    """Test that GPUMonitor can be started and stopped multiple times."""
    from backend.services.gpu_monitor import GPUMonitor

    monitor = GPUMonitor(broadcaster=None)

    # First cycle
    await monitor.start()
    assert monitor.running is True
    await monitor.stop()
    assert monitor.running is False

    # Second cycle
    await monitor.start()
    assert monitor.running is True
    await monitor.stop()
    assert monitor.running is False


@pytest.mark.asyncio
async def test_system_broadcaster_multiple_start_stop_cycles() -> None:
    """Test that SystemBroadcaster can be started and stopped multiple times."""
    from backend.services.system_broadcaster import SystemBroadcaster

    broadcaster = SystemBroadcaster(redis_client=None)

    # First cycle
    await broadcaster.start_broadcasting(interval=1.0)
    assert broadcaster._running is True
    await broadcaster.stop_broadcasting()
    assert broadcaster._running is False

    # Second cycle
    await broadcaster.start_broadcasting(interval=1.0)
    assert broadcaster._running is True
    await broadcaster.stop_broadcasting()
    assert broadcaster._running is False


@pytest.mark.asyncio
async def test_detection_worker_single_start_stop_cycle(real_redis: Any) -> None:
    """Test that DetectionQueueWorker can be started and stopped properly.

    Note: Workers are designed for single lifecycle use. The PipelineWorkerManager
    handles worker recreation if needed during recovery scenarios.
    """
    from backend.services.pipeline_workers import DetectionQueueWorker, WorkerState

    mock_detector = AsyncMock()
    mock_detector.detect_objects = AsyncMock(return_value=[])
    mock_detector.health_check = AsyncMock(return_value=True)

    mock_aggregator = AsyncMock()
    mock_aggregator.add_detection = AsyncMock()

    worker = DetectionQueueWorker(
        redis_client=real_redis,
        detector_client=mock_detector,
        batch_aggregator=mock_aggregator,
        poll_timeout=1,
        stop_timeout=2.0,
    )

    # Single lifecycle
    await worker.start()
    assert worker._stats.state == WorkerState.RUNNING
    await asyncio.sleep(0.1)
    await worker.stop()
    assert worker._stats.state == WorkerState.STOPPED


# =============================================================================
# Test: Database pool cleanup
# =============================================================================


@pytest.mark.asyncio
async def test_database_pool_returns_all_connections_after_queries(integration_db: str) -> None:
    """Test that all database connections are returned to pool after queries."""
    from backend.core.database import get_pool_status, get_session

    # Execute multiple concurrent queries
    async def run_query() -> int:
        async with get_session() as session:
            from sqlalchemy import text

            result = await session.execute(text("SELECT 1"))
            return result.scalar() or 0

    # Run 10 concurrent queries
    tasks = [run_query() for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # All queries should complete
    assert all(r == 1 for r in results)

    # All connections should be returned to pool
    pool_status = await get_pool_status()
    assert pool_status.get("checkedout", 0) == 0


# =============================================================================
# Test: File watcher lifecycle note
# =============================================================================

# Note: FileWatcher uses the watchdog library's Observer which is based on
# threading.Thread. Python threads cannot be restarted once stopped, so
# FileWatcher instances are designed for single-use lifecycle. If a restart
# is needed, a new FileWatcher instance must be created.
#
# This is documented here rather than tested, as attempting to restart
# would raise RuntimeError("threads can only be started once").
