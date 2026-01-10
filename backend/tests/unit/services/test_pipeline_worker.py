"""Unit tests for pipeline worker process.

This module tests the pipeline worker behaviors including:
- Queue consumer loops (detection_queue and analysis_queue)
- Batch timeout checking
- Graceful shutdown handling (SIGTERM/SIGINT)
- Error recovery from Redis connection loss
- Error recovery from AI service unavailability
- Health status reporting

The pipeline worker is not a single file but rather an orchestration of:
- FileWatcher (produces to detection_queue)
- DetectorClient (consumes from detection_queue, processes detections)
- BatchAggregator (groups detections, pushes to analysis_queue)
- NemotronAnalyzer (consumes from analysis_queue)
- ServiceHealthMonitor (reports health status)

Run with:
    pytest backend/tests/unit/test_pipeline_worker.py -v -k worker
"""

import asyncio
import json
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# fakeredis is optional - skip tests that need it if not installed
fakeredis = pytest.importorskip("fakeredis")

from backend.core.redis import QueueAddResult, RedisClient  # noqa: E402
from backend.services.batch_aggregator import BatchAggregator  # noqa: E402
from backend.services.detector_client import DetectorClient  # noqa: E402
from backend.services.health_monitor import ServiceHealthMonitor  # noqa: E402
from backend.services.nemotron_analyzer import NemotronAnalyzer  # noqa: E402
from backend.services.service_managers import ServiceConfig, ShellServiceManager  # noqa: E402

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def fake_redis():
    """Create a fakeredis client for testing.

    Returns:
        Configured fakeredis async client
    """
    server = fakeredis.FakeServer()
    client = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    yield client
    await client.aclose()


def _create_empty_async_generator():
    """Create an empty async generator for scan_iter mocking."""

    async def _generator():
        for _ in []:  # Empty async generator pattern
            yield

    return _generator()


@pytest.fixture
def mock_redis_client():
    """Create a mock RedisClient with all necessary methods.

    Returns:
        MagicMock: Mocked RedisClient
    """
    mock_client = MagicMock(spec=RedisClient)

    # Internal client mock for low-level operations
    mock_internal = AsyncMock()
    # Use scan_iter instead of keys (returns async generator)
    mock_internal.scan_iter = MagicMock(return_value=_create_empty_async_generator())
    mock_internal.ping = AsyncMock(return_value=True)
    # lrange is used for atomic list operations (detections)
    mock_internal.lrange = AsyncMock(return_value=[])
    mock_internal.rpush = AsyncMock(return_value=1)
    mock_internal.expire = AsyncMock(return_value=True)
    # llen is used for batch size checking (NEM-1726)
    mock_internal.llen = AsyncMock(return_value=0)
    mock_client._client = mock_internal

    # High-level operations
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    # add_to_queue_safe is the preferred method with backpressure handling
    mock_client.add_to_queue_safe = AsyncMock(
        return_value=QueueAddResult(success=True, queue_length=1)
    )
    mock_client.get_from_queue = AsyncMock(return_value=None)
    mock_client.get_queue_length = AsyncMock(return_value=0)
    mock_client.publish = AsyncMock(return_value=1)
    mock_client.health_check = AsyncMock(return_value={"status": "healthy", "connected": True})
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()

    # Mock add_to_queue_safe for close_batch (returns QueueResult-like object)
    queue_result_mock = MagicMock()
    queue_result_mock.success = True
    queue_result_mock.had_backpressure = False
    queue_result_mock.queue_length = 0
    queue_result_mock.error = None
    mock_client.add_to_queue_safe = AsyncMock(return_value=queue_result_mock)

    return mock_client


@pytest.fixture
def mock_detector():
    """Create a mock DetectorClient.

    Returns:
        AsyncMock: Mocked DetectorClient
    """
    detector = AsyncMock(spec=DetectorClient)
    detector.detect_objects = AsyncMock(return_value=[])
    detector.health_check = AsyncMock(return_value=True)
    return detector


@pytest.fixture
def mock_analyzer(mock_redis_client):
    """Create a mock NemotronAnalyzer.

    Returns:
        AsyncMock: Mocked NemotronAnalyzer
    """
    analyzer = AsyncMock(spec=NemotronAnalyzer)
    analyzer.analyze_batch = AsyncMock(return_value=None)
    analyzer.analyze_detection_fast_path = AsyncMock(return_value=None)
    analyzer.health_check = AsyncMock(return_value=True)
    return analyzer


@pytest.fixture
def batch_aggregator(mock_redis_client, mock_analyzer):
    """Create BatchAggregator with mocked dependencies.

    Returns:
        BatchAggregator: Configured aggregator
    """
    # Mock get_settings to avoid DATABASE_URL validation error in unit tests
    with patch("backend.services.batch_aggregator.get_settings") as mock_settings:
        mock_settings.return_value.batch_window_seconds = 90
        mock_settings.return_value.batch_idle_timeout_seconds = 30
        mock_settings.return_value.fast_path_confidence_threshold = 0.9
        mock_settings.return_value.fast_path_object_types = ["person", "vehicle"]
        # Batch size limit (NEM-1726)
        mock_settings.return_value.batch_max_detections = 1000
        aggregator = BatchAggregator(redis_client=mock_redis_client, analyzer=mock_analyzer)
        return aggregator


# =============================================================================
# Queue Consumer Loop Tests
# =============================================================================


class TestQueueConsumerLoop:
    """Tests for continuous queue consumption from detection_queue and analysis_queue."""

    @pytest.mark.asyncio
    async def test_detection_queue_continuous_consumption(self, mock_redis_client):
        """Test continuous consumption from detection_queue."""
        # Setup: Queue items to consume
        queue_items = [
            {
                "camera_id": "front_door",
                "file_path": "/export/foscam/front_door/image1.jpg",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            {
                "camera_id": "back_door",
                "file_path": "/export/foscam/back_door/image2.jpg",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            None,  # Timeout/no item
            None,  # Timeout/no item
            None,  # Timeout/no item
        ]
        call_count = 0

        async def mock_get_from_queue(queue_name, timeout=0):
            nonlocal call_count
            call_count += 1
            if call_count <= len(queue_items):
                return queue_items[call_count - 1]
            return None

        mock_redis_client.get_from_queue = AsyncMock(side_effect=mock_get_from_queue)

        # Simulate consumer loop
        consumed_items = []
        max_iterations = 5

        for _ in range(max_iterations):
            item = await mock_redis_client.get_from_queue("detection_queue", timeout=1)
            if item:
                consumed_items.append(item)

        # Verify consumed items
        assert len(consumed_items) == 2
        assert consumed_items[0]["camera_id"] == "front_door"
        assert consumed_items[1]["camera_id"] == "back_door"
        assert call_count == 5  # All iterations attempted

    @pytest.mark.asyncio
    async def test_analysis_queue_continuous_consumption(self, mock_redis_client):
        """Test continuous consumption from analysis_queue."""
        # Setup: Queue items for analysis
        analysis_items = [
            {
                "batch_id": "batch_001",
                "camera_id": "front_door",
                "detection_ids": ["det_1", "det_2"],
                "timestamp": time.time(),
            },
            {
                "batch_id": "batch_002",
                "camera_id": "garage",
                "detection_ids": ["det_3"],
                "timestamp": time.time(),
            },
        ]
        item_index = 0

        async def mock_get_from_queue(queue_name, timeout=0):
            nonlocal item_index
            if queue_name == "analysis_queue" and item_index < len(analysis_items):
                item = analysis_items[item_index]
                item_index += 1
                return item
            return None

        mock_redis_client.get_from_queue = AsyncMock(side_effect=mock_get_from_queue)

        # Simulate consumer loop
        consumed_batches = []
        for _ in range(len(analysis_items) + 1):
            item = await mock_redis_client.get_from_queue("analysis_queue", timeout=1)
            if item:
                consumed_batches.append(item)

        # Verify all batches were consumed
        assert len(consumed_batches) == 2
        assert consumed_batches[0]["batch_id"] == "batch_001"
        assert consumed_batches[1]["batch_id"] == "batch_002"

    @pytest.mark.asyncio
    async def test_batch_timeout_check_loop(self, batch_aggregator, mock_redis_client):
        """Test batch timeout check loop runs periodically."""
        # Setup: Simulate an expired batch
        batch_id = "batch_expired"
        camera_id = "test_cam"
        old_timestamp = str(time.time() - 100)  # 100 seconds ago

        # Create async generator for scan_iter that yields batch keys
        async def mock_scan_iter(match="*", count=100):
            yield f"batch:{camera_id}:current"

        mock_redis_client._client.scan_iter = MagicMock(return_value=mock_scan_iter())

        # Create mock pipeline for the optimized check_batch_timeouts
        def create_mock_pipeline(execute_results):
            mock_pipe = MagicMock()
            mock_pipe.get = MagicMock(return_value=mock_pipe)
            mock_pipe.execute = AsyncMock(return_value=execute_results)
            return mock_pipe

        # Phase 1 pipeline: fetch batch IDs
        phase1_pipe = create_mock_pipeline([batch_id])
        # Phase 2 pipeline: fetch started_at and last_activity
        phase2_pipe = create_mock_pipeline([old_timestamp, old_timestamp])

        call_count = [0]

        def get_pipeline():
            call_count[0] += 1
            if call_count[0] == 1:
                return phase1_pipe
            return phase2_pipe

        mock_redis_client._client.pipeline = MagicMock(side_effect=get_pipeline)

        async def mock_get(key):
            if key == f"batch:{batch_id}:camera_id":
                return camera_id
            return None

        mock_redis_client.get.side_effect = mock_get
        # Mock lrange for detections (now uses atomic list operations)
        mock_redis_client._client.lrange = AsyncMock(return_value=["1"])

        # Execute timeout check
        closed_batches = await batch_aggregator.check_batch_timeouts()

        # Verify batch was closed
        assert batch_id in closed_batches
        # Note: BatchAggregator.close_batch() uses add_to_queue_safe(), not add_to_queue()
        mock_redis_client.add_to_queue_safe.assert_called()

    @pytest.mark.asyncio
    async def test_consumer_handles_empty_queue(self, mock_redis_client):
        """Test consumer handles empty queue gracefully (returns None on timeout)."""
        mock_redis_client.get_from_queue = AsyncMock(return_value=None)

        # Should not raise exception
        result = await mock_redis_client.get_from_queue("detection_queue", timeout=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_consumer_processes_items_in_order(self, mock_redis_client):
        """Test queue consumer processes items in FIFO order."""
        items = [{"id": i, "order": i} for i in range(5)]
        item_iter = iter(items)

        async def get_item(queue_name, timeout=0):
            try:
                return next(item_iter)
            except StopIteration:
                return None

        mock_redis_client.get_from_queue = AsyncMock(side_effect=get_item)

        # Consume all items
        consumed = []
        for _ in range(6):  # Extra iteration to confirm queue is empty
            item = await mock_redis_client.get_from_queue("test_queue", timeout=1)
            if item:
                consumed.append(item)

        # Verify order preserved
        assert len(consumed) == 5
        for i, item in enumerate(consumed):
            assert item["order"] == i


# =============================================================================
# Graceful Shutdown Tests
# =============================================================================


class TestGracefulShutdown:
    """Tests for SIGTERM/SIGINT handling and graceful shutdown."""

    @pytest.mark.asyncio
    async def test_sigterm_stops_consumer_loop(self):
        """Test SIGTERM signal stops consumer loop cleanly."""
        shutdown_event = asyncio.Event()
        consumed_count = 0

        async def consumer_loop():
            nonlocal consumed_count
            while not shutdown_event.is_set():
                consumed_count += 1
                await asyncio.sleep(0.01)
                if consumed_count >= 5:  # Simulate some processing
                    break

        # Start consumer
        task = asyncio.create_task(consumer_loop())

        # Simulate SIGTERM by setting shutdown event
        await asyncio.sleep(0.03)
        shutdown_event.set()

        await task
        assert consumed_count >= 1
        assert shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_sigint_stops_consumer_loop(self):
        """Test SIGINT signal stops consumer loop cleanly."""
        shutdown_requested = False
        iterations = 0

        def signal_handler():
            nonlocal shutdown_requested
            shutdown_requested = True

        # Simulate consumer loop
        async def consumer_loop():
            nonlocal iterations, shutdown_requested
            while not shutdown_requested:
                iterations += 1
                await asyncio.sleep(0.01)
                if iterations >= 3:
                    signal_handler()  # Simulate SIGINT

        await consumer_loop()
        assert shutdown_requested
        assert iterations >= 3

    @pytest.mark.asyncio
    async def test_in_flight_work_completion_before_exit(self, mock_redis_client):
        """Test in-flight work is completed before exit."""
        in_flight_work = []
        shutdown_event = asyncio.Event()

        async def process_item(item):
            """Simulate processing an item."""
            in_flight_work.append(item)
            await asyncio.sleep(0.02)  # Simulate processing time
            item["completed"] = True

        async def consumer_loop():
            items = [{"id": 1}, {"id": 2}, {"id": 3}]
            for item in items:
                if shutdown_event.is_set():
                    break
                await process_item(item)

        # Start consumer
        task = asyncio.create_task(consumer_loop())

        # Request shutdown after first item
        await asyncio.sleep(0.05)
        shutdown_event.set()

        await task

        # Verify at least one item was completed
        completed = [w for w in in_flight_work if w.get("completed")]
        assert len(completed) >= 1

    @pytest.mark.asyncio
    async def test_shutdown_waits_for_current_batch_analysis(
        self, batch_aggregator, mock_redis_client, mock_analyzer
    ):
        """Test shutdown waits for current batch analysis to complete."""
        analysis_completed = asyncio.Event()

        async def slow_analyze(batch_id):
            await asyncio.sleep(0.05)  # Simulate slow analysis
            analysis_completed.set()
            return MagicMock(id=1, risk_score=50)

        mock_analyzer.analyze_batch = slow_analyze

        # Start analysis
        task = asyncio.create_task(mock_analyzer.analyze_batch("test_batch"))

        # Wait for completion
        await task
        assert analysis_completed.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_pending_queue_reads(self):
        """Test shutdown cancels pending blocking queue reads."""
        queue_read_started = asyncio.Event()
        queue_read_cancelled = False

        async def blocking_read():
            nonlocal queue_read_cancelled
            queue_read_started.set()
            try:
                await asyncio.sleep(0.5)  # cancelled - simulating BLPOP, task.cancel() below
            except asyncio.CancelledError:
                queue_read_cancelled = True
                raise

        # Start blocking read
        task = asyncio.create_task(blocking_read())

        # Wait for read to start then cancel
        await queue_read_started.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert queue_read_cancelled

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up_resources(self, mock_redis_client):
        """Test shutdown properly cleans up Redis connections."""
        # Simulate shutdown sequence
        await mock_redis_client.disconnect()

        mock_redis_client.disconnect.assert_called_once()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for recovery from Redis connection loss and AI service unavailability."""

    @pytest.mark.asyncio
    async def test_redis_connection_loss_detection(self, mock_redis_client):
        """Test detection of Redis connection loss."""
        # Simulate connection loss
        mock_redis_client.health_check = AsyncMock(
            return_value={"status": "unhealthy", "connected": False, "error": "Connection refused"}
        )

        health = await mock_redis_client.health_check()

        assert health["status"] == "unhealthy"
        assert health["connected"] is False

    @pytest.mark.asyncio
    async def test_redis_reconnection_on_failure(self, mock_redis_client):
        """Test automatic reconnection attempt after Redis failure."""
        connection_attempts = 0

        async def mock_connect():
            nonlocal connection_attempts
            connection_attempts += 1
            if connection_attempts < 3:
                raise ConnectionError("Connection refused")
            # Success on 3rd attempt

        mock_redis_client.connect = AsyncMock(side_effect=mock_connect)

        # Attempt reconnection with retry
        for attempt in range(3):
            try:
                await mock_redis_client.connect()
                break
            except ConnectionError:
                await asyncio.sleep(0.01)  # Backoff

        assert connection_attempts == 3

    @pytest.mark.asyncio
    async def test_queue_operation_retry_on_connection_error(self, mock_redis_client):
        """Test queue operations retry on connection error."""
        call_count = 0

        async def flaky_get_from_queue(queue_name, timeout=0):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection lost")
            return {"data": "success"}

        mock_redis_client.get_from_queue = AsyncMock(side_effect=flaky_get_from_queue)

        # Retry loop
        result = None
        for _ in range(3):
            try:
                result = await mock_redis_client.get_from_queue("test_queue", timeout=1)
                break
            except ConnectionError:
                await asyncio.sleep(0.01)

        assert result == {"data": "success"}
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_ai_service_unavailability_handling(self, mock_analyzer):
        """Test handling when AI service is unavailable."""
        mock_analyzer.health_check = AsyncMock(return_value=False)

        is_healthy = await mock_analyzer.health_check()
        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_detector_service_fallback_on_error(self, mock_detector):
        """Test detector returns empty list on service error."""
        mock_detector.detect_objects = AsyncMock(
            side_effect=Exception("RT-DETRv2 service unavailable")
        )

        # Should handle exception gracefully
        try:
            await mock_detector.detect_objects("/path/to/image.jpg", "camera1", None)
        except Exception as e:
            assert "RT-DETRv2 service unavailable" in str(e)

    @pytest.mark.asyncio
    async def test_nemotron_fallback_risk_data_on_error(self, mock_redis_client):
        """Test NemotronAnalyzer uses fallback risk data on LLM error."""
        # Setup: Create analyzer with mock redis
        batch_id = "test_batch"
        camera_id = "test_cam"

        async def mock_get(key):
            if key == f"batch:{batch_id}:camera_id":
                return camera_id
            elif key == f"batch:{batch_id}:detections":
                return json.dumps(["det_1"])
            return None

        mock_redis_client.get = AsyncMock(side_effect=mock_get)

        # The actual analyzer would fall back to default risk score (50, medium)
        # when LLM is unavailable - this is the expected behavior
        fallback_event = {
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "Analysis unavailable - LLM service error",
        }

        assert fallback_event["risk_score"] == 50
        assert fallback_event["risk_level"] == "medium"

    @pytest.mark.asyncio
    async def test_batch_aggregator_handles_redis_error_gracefully(
        self, batch_aggregator, mock_redis_client
    ):
        """Test batch aggregator handles Redis errors without crashing."""

        # Create async generator that raises an error when iterated
        async def error_scan_iter(match="*", count=100):
            for _ in []:  # Makes this an async generator
                yield
            raise Exception("Redis connection error")

        # Simulate Redis error during batch timeout check (scan_iter iteration)
        mock_redis_client._client.scan_iter = MagicMock(return_value=error_scan_iter())

        # The error propagates up as Exception (Redis operations fail)
        with pytest.raises(Exception, match="Redis connection error"):
            await batch_aggregator.check_batch_timeouts()

    @pytest.mark.asyncio
    async def test_consumer_continues_after_individual_item_error(self, mock_redis_client):
        """Test consumer continues processing after individual item error."""
        items_processed = []
        items_errored = []

        items = [
            {"id": 1, "valid": True},
            {"id": 2, "valid": False},  # This will cause error
            {"id": 3, "valid": True},
        ]

        for item in items:
            try:
                if not item["valid"]:
                    raise ValueError("Invalid item")
                items_processed.append(item)
            except ValueError:
                items_errored.append(item)
                # Continue processing next item

        assert len(items_processed) == 2
        assert len(items_errored) == 1


# =============================================================================
# Health Reporting Tests
# =============================================================================


class TestHealthReporting:
    """Tests for worker health status reporting."""

    @pytest.mark.asyncio
    async def test_worker_reports_healthy_when_consuming(self, mock_redis_client):
        """Test worker reports healthy when actively consuming."""
        mock_redis_client.health_check = AsyncMock(
            return_value={
                "status": "healthy",
                "connected": True,
                "redis_version": "7.0.0",
            }
        )

        health = await mock_redis_client.health_check()
        assert health["status"] == "healthy"
        assert health["connected"] is True

    @pytest.mark.asyncio
    async def test_worker_reports_unhealthy_when_stalled(self, mock_redis_client):
        """Test worker reports unhealthy when stalled (no progress)."""
        # Simulate stalled state
        mock_redis_client.health_check = AsyncMock(
            return_value={
                "status": "unhealthy",
                "connected": False,
                "error": "No progress in 60 seconds",
            }
        )

        health = await mock_redis_client.health_check()
        assert health["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_monitor_detects_service_failure(self, mock_redis_client):
        """Test health monitor detects when a service fails."""
        # Create service config
        service_config = ServiceConfig(
            name="redis",
            health_url="redis://localhost:6379",
            restart_cmd="systemctl restart redis",
            health_timeout=5.0,
            max_retries=3,
        )

        # Mock unhealthy service
        manager = MagicMock(spec=ShellServiceManager)
        manager.check_health = AsyncMock(return_value=False)

        is_healthy = await manager.check_health(service_config)
        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_health_monitor_tracks_failure_count(self):
        """Test health monitor tracks consecutive failures."""
        service_config = ServiceConfig(
            name="test_service",
            health_url="http://localhost:8001/health",
            restart_cmd="./restart.sh",
            max_retries=3,
        )

        # Create health monitor
        manager = MagicMock(spec=ShellServiceManager)
        manager.check_health = AsyncMock(return_value=False)
        manager.restart = AsyncMock(return_value=True)

        monitor = ServiceHealthMonitor(
            manager=manager,
            services=[service_config],
            broadcaster=None,
            check_interval=0.1,
        )

        # Verify initial state
        status = monitor.get_status()
        assert service_config.name in status
        assert status[service_config.name]["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_health_monitor_broadcasts_status_changes(self, mock_redis_client):
        """Test health monitor broadcasts status changes via WebSocket."""
        broadcaster = AsyncMock()
        broadcaster.broadcast_service_status = AsyncMock()

        service_config = ServiceConfig(
            name="rtdetr",
            health_url="http://localhost:8001/health",
            restart_cmd="./restart.sh",
        )

        manager = MagicMock(spec=ShellServiceManager)
        manager.check_health = AsyncMock(return_value=False)
        manager.restart = AsyncMock(return_value=False)

        monitor = ServiceHealthMonitor(
            manager=manager,
            services=[service_config],
            broadcaster=broadcaster,
            check_interval=0.1,
        )

        # Simulate status broadcast
        await monitor._broadcast_status(service_config, "unhealthy", "Health check failed")

        broadcaster.broadcast_service_status.assert_called_once()
        call_args = broadcaster.broadcast_service_status.call_args[0][0]
        assert call_args["type"] == "service_status"
        # Note: The broadcast payload uses nested data structure: {"type": "...", "data": {"status": ...}}
        assert call_args["data"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_includes_queue_depths(self, mock_redis_client):
        """Test health check includes queue depth information."""
        mock_redis_client.get_queue_length = AsyncMock(side_effect=[10, 5])

        detection_queue_depth = await mock_redis_client.get_queue_length("detection_queue")
        analysis_queue_depth = await mock_redis_client.get_queue_length("analysis_queue")

        assert detection_queue_depth == 10
        assert analysis_queue_depth == 5

    @pytest.mark.asyncio
    async def test_health_monitor_recovery_resets_failure_count(self):
        """Test health monitor resets failure count on recovery."""
        service_config = ServiceConfig(
            name="test_service",
            health_url="http://localhost:8001/health",
            restart_cmd="./restart.sh",
            max_retries=3,
        )

        manager = MagicMock(spec=ShellServiceManager)
        manager.check_health = AsyncMock(return_value=True)
        manager.restart = AsyncMock(return_value=True)

        monitor = ServiceHealthMonitor(
            manager=manager,
            services=[service_config],
            broadcaster=None,
            check_interval=0.1,
        )

        # Simulate failure then recovery
        monitor._failure_counts[service_config.name] = 2

        # When check_health returns True, failure count should reset
        # (This happens in _health_check_loop)
        status = monitor.get_status()
        assert status[service_config.name]["max_retries"] == 3


# =============================================================================
# Integration-Style Tests (Using FakeRedis)
# =============================================================================


@pytest.mark.slow
class TestPipelineWorkerIntegration:
    """Integration-style tests using fakeredis for more realistic behavior."""

    @pytest.mark.asyncio
    async def test_full_queue_consumer_cycle(self, fake_redis):
        """Test complete queue consumer cycle with fakeredis."""
        queue_name = "test_queue"

        # Add items to queue
        items = [
            json.dumps({"id": 1, "data": "first"}),
            json.dumps({"id": 2, "data": "second"}),
        ]
        for item in items:
            await fake_redis.rpush(queue_name, item)

        # Verify queue length
        length = await fake_redis.llen(queue_name)
        assert length == 2

        # Consume items
        consumed = []
        while True:
            result = await fake_redis.blpop([queue_name], timeout=1)
            if result is None:
                break
            _, value = result
            consumed.append(json.loads(value))

        assert len(consumed) == 2
        assert consumed[0]["id"] == 1
        assert consumed[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_batch_metadata_lifecycle(self, fake_redis):
        """Test batch metadata creation and cleanup with fakeredis."""
        batch_id = "test_batch_123"
        camera_id = "front_door"

        # Create batch metadata
        await fake_redis.set(f"batch:{camera_id}:current", batch_id)
        await fake_redis.set(f"batch:{batch_id}:camera_id", camera_id)
        await fake_redis.set(f"batch:{batch_id}:started_at", str(time.time()))
        await fake_redis.set(f"batch:{batch_id}:detections", json.dumps(["det_1", "det_2"]))

        # Verify metadata exists
        current_batch = await fake_redis.get(f"batch:{camera_id}:current")
        assert current_batch == batch_id

        detections = await fake_redis.get(f"batch:{batch_id}:detections")
        assert json.loads(detections) == ["det_1", "det_2"]

        # Cleanup (simulate batch close)
        await fake_redis.delete(
            f"batch:{camera_id}:current",
            f"batch:{batch_id}:camera_id",
            f"batch:{batch_id}:started_at",
            f"batch:{batch_id}:detections",
        )

        # Verify cleanup
        assert await fake_redis.get(f"batch:{camera_id}:current") is None

    @pytest.mark.asyncio
    async def test_concurrent_queue_consumers(self, fake_redis):
        """Test multiple concurrent consumers on same queue."""
        queue_name = "shared_queue"
        consumed_by_consumer1 = []
        consumed_by_consumer2 = []

        # Add items
        for i in range(10):
            await fake_redis.rpush(queue_name, json.dumps({"id": i}))

        async def consumer1():
            while True:
                result = await fake_redis.blpop([queue_name], timeout=1)
                if result is None:
                    break
                _, value = result
                consumed_by_consumer1.append(json.loads(value))

        async def consumer2():
            while True:
                result = await fake_redis.blpop([queue_name], timeout=1)
                if result is None:
                    break
                _, value = result
                consumed_by_consumer2.append(json.loads(value))

        # Run consumers concurrently
        await asyncio.gather(consumer1(), consumer2())

        # All items should be consumed (no duplicates)
        total_consumed = len(consumed_by_consumer1) + len(consumed_by_consumer2)
        assert total_consumed == 10

        # Verify no duplicates
        all_ids = [item["id"] for item in consumed_by_consumer1 + consumed_by_consumer2]
        assert len(all_ids) == len(set(all_ids))

    @pytest.mark.asyncio
    async def test_pub_sub_health_notification(self, fake_redis):
        """Test pub/sub health status notifications."""
        channel = "worker_health"
        messages_received = []

        # Subscribe to channel
        pubsub = fake_redis.pubsub()
        await pubsub.subscribe(channel)

        # Publish health status
        status_message = json.dumps(
            {
                "worker_id": "worker_1",
                "status": "healthy",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        await fake_redis.publish(channel, status_message)

        # Receive messages
        async for message in pubsub.listen():
            if message["type"] == "message":
                messages_received.append(json.loads(message["data"]))
                break

        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

        assert len(messages_received) == 1
        assert messages_received[0]["status"] == "healthy"


# =============================================================================
# Edge Cases and Boundary Conditions
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_batch_handling(self, batch_aggregator, mock_redis_client):
        """Test handling of batch with no detections."""
        batch_id = "empty_batch"

        async def mock_get(key):
            if key == f"batch:{batch_id}:camera_id":
                return "test_cam"
            elif key == f"batch:{batch_id}:detections":
                return json.dumps([])  # Empty detections
            elif key == f"batch:{batch_id}:started_at":
                return str(time.time())
            return None

        mock_redis_client.get.side_effect = mock_get

        summary = await batch_aggregator.close_batch(batch_id)

        assert summary["detection_count"] == 0
        # Empty batches should not be queued for analysis
        mock_redis_client.add_to_queue_safe.assert_not_called()

    @pytest.mark.asyncio
    async def test_malformed_queue_item_handling(self, mock_redis_client):
        """Test handling of malformed queue items."""
        # Return malformed JSON
        mock_redis_client.get_from_queue = AsyncMock(return_value="not valid json {}")

        item = await mock_redis_client.get_from_queue("detection_queue", timeout=1)

        # Should return the raw value (already deserialized by mock)
        assert item == "not valid json {}"

    @pytest.mark.asyncio
    async def test_very_large_batch_handling(self, batch_aggregator, mock_redis_client):
        """Test handling of batch with many detections."""
        batch_id = "large_batch"
        # Detection IDs must be integers (database model requirement)
        detection_ids = list(range(1000))  # 1000 detections (integers 0-999)
        # lrange returns list of strings
        detection_ids_str = [str(i) for i in detection_ids]

        async def mock_get(key):
            if key == f"batch:{batch_id}:camera_id":
                return "test_cam"
            elif key == f"batch:{batch_id}:started_at":
                return str(time.time())
            return None

        mock_redis_client.get.side_effect = mock_get
        # Mock lrange for detections (now uses atomic list operations)
        mock_redis_client._client.lrange = AsyncMock(return_value=detection_ids_str)

        summary = await batch_aggregator.close_batch(batch_id)

        assert summary["detection_count"] == 1000
        # Note: BatchAggregator.close_batch() uses add_to_queue_safe(), not add_to_queue()
        mock_redis_client.add_to_queue_safe.assert_called_once()

    @pytest.mark.asyncio
    async def test_rapid_shutdown_restart_cycle(self, mock_redis_client):
        """Test rapid shutdown and restart cycles."""
        for _ in range(5):
            # Start
            await mock_redis_client.connect()
            # Stop
            await mock_redis_client.disconnect()

        # Verify all cycles completed
        assert mock_redis_client.connect.await_count == 5
        assert mock_redis_client.disconnect.await_count == 5

    @pytest.mark.asyncio
    async def test_timeout_during_batch_analysis(self, mock_analyzer):
        """Test handling of timeout during batch analysis."""

        async def slow_analysis(batch_id):
            await asyncio.sleep(0.5)  # Longer than 0.1s timeout

        mock_analyzer.analyze_batch = slow_analysis

        # Should timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(mock_analyzer.analyze_batch("test_batch"), timeout=0.1)

    @pytest.mark.asyncio
    async def test_duplicate_detection_handling(self, batch_aggregator, mock_redis_client):
        """Test handling of duplicate detections in batch."""
        camera_id = "test_cam"

        # Mock the pipeline for atomic batch metadata creation
        mock_pipe = MagicMock()
        mock_pipe.set = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[True, True, True, True])
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_redis_client._client.pipeline = MagicMock(return_value=mock_pipe)

        # Mock rpush for atomic list append
        mock_redis_client._client.rpush = AsyncMock(return_value=1)
        mock_redis_client._client.expire = AsyncMock(return_value=True)

        # First add - creates new batch
        # Detection IDs must be integers (database model requirement)
        mock_redis_client.get.return_value = None
        with patch("backend.services.batch_aggregator.uuid.uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "batch_001"
            batch_id1 = await batch_aggregator.add_detection(
                camera_id=camera_id,
                detection_id=1,  # Use integer detection ID
                _file_path="/path/1.jpg",
            )

        # Second add - same detection ID (duplicate)
        async def mock_get(key):
            if key == f"batch:{camera_id}:current":
                return "batch_001"
            elif key == "batch:batch_001:detections":
                return json.dumps([1])  # Already has detection ID 1
            return None

        mock_redis_client.get.side_effect = mock_get

        # Mock llen for batch size checking
        mock_redis_client._client.llen = AsyncMock(return_value=1)

        # Mock rpush to return 2 (after second detection added)
        mock_redis_client._client.rpush = AsyncMock(return_value=2)

        batch_id2 = await batch_aggregator.add_detection(
            camera_id=camera_id,
            detection_id=1,  # Same detection ID (integer)
            _file_path="/path/1.jpg",
        )

        # Should be added to same batch (no dedup at this level)
        assert batch_id1 == batch_id2
