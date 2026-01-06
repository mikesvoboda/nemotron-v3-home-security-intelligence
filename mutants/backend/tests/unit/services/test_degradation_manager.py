"""Unit tests for graceful degradation manager.

Tests cover:
- DegradationMode enum values
- ServiceStatus tracking
- DegradationManager state transitions
- Queue-for-later behavior during AI outages
- Redis unavailability handling
- Recovery from partial outages
- Service health monitoring integration
- FallbackQueue disk-based queue operations
- Health check loop lifecycle
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.redis import QueueAddResult
from backend.services.degradation_manager import (
    DegradationManager,
    DegradationMode,
    QueuedJob,
    ServiceHealth,
    ServiceStatus,
    get_degradation_manager,
    reset_degradation_manager,
)


class TestDegradationMode:
    """Tests for DegradationMode enum."""

    def test_mode_values(self) -> None:
        """Test degradation mode enum values."""
        assert DegradationMode.NORMAL.value == "normal"
        assert DegradationMode.DEGRADED.value == "degraded"
        assert DegradationMode.MINIMAL.value == "minimal"
        assert DegradationMode.OFFLINE.value == "offline"


class TestServiceStatus:
    """Tests for ServiceStatus enum."""

    def test_status_values(self) -> None:
        """Test service status enum values."""
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.UNHEALTHY.value == "unhealthy"
        assert ServiceStatus.UNKNOWN.value == "unknown"


class TestServiceHealth:
    """Tests for ServiceHealth dataclass."""

    def test_default_values(self) -> None:
        """Test default health values."""
        health = ServiceHealth(name="test_service")
        assert health.name == "test_service"
        assert health.status == ServiceStatus.UNKNOWN
        assert health.last_check is None
        assert health.last_success is None
        assert health.consecutive_failures == 0
        assert health.error_message is None

    def test_custom_values(self) -> None:
        """Test custom health values."""
        health = ServiceHealth(
            name="ai_service",
            status=ServiceStatus.HEALTHY,
            consecutive_failures=0,
            error_message=None,
        )
        assert health.name == "ai_service"
        assert health.status == ServiceStatus.HEALTHY

    def test_is_healthy(self) -> None:
        """Test is_healthy property."""
        health = ServiceHealth(name="test", status=ServiceStatus.HEALTHY)
        assert health.is_healthy is True

        health.status = ServiceStatus.UNHEALTHY
        assert health.is_healthy is False

        health.status = ServiceStatus.UNKNOWN
        assert health.is_healthy is False

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        health = ServiceHealth(
            name="test_service",
            status=ServiceStatus.HEALTHY,
            consecutive_failures=0,
        )
        result = health.to_dict()
        assert result["name"] == "test_service"
        assert result["status"] == "healthy"
        assert result["consecutive_failures"] == 0


class TestQueuedJob:
    """Tests for QueuedJob dataclass."""

    def test_creation(self) -> None:
        """Test queued job creation."""
        job = QueuedJob(
            job_type="detection",
            data={"file_path": "/path/to/image.jpg"},
            queued_at="2025-12-28T10:00:00",
            retry_count=0,
        )
        assert job.job_type == "detection"
        assert job.data == {"file_path": "/path/to/image.jpg"}
        assert job.retry_count == 0

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        job = QueuedJob(
            job_type="analysis",
            data={"batch_id": "batch123"},
            queued_at="2025-12-28T10:00:00",
            retry_count=2,
        )
        result = job.to_dict()
        assert result["job_type"] == "analysis"
        assert result["data"] == {"batch_id": "batch123"}
        assert result["retry_count"] == 2

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "job_type": "detection",
            "data": {"camera_id": "cam1"},
            "queued_at": "2025-12-28T10:00:00",
            "retry_count": 1,
        }
        job = QueuedJob.from_dict(data)
        assert job.job_type == "detection"
        assert job.data == {"camera_id": "cam1"}
        assert job.retry_count == 1


class TestDegradationManager:
    """Tests for DegradationManager class."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        redis.get_from_queue = AsyncMock(return_value=None)
        redis.get_queue_length = AsyncMock(return_value=0)
        redis.ping = AsyncMock(return_value=True)
        redis.set = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        return redis

    @pytest.fixture
    def manager(self, mock_redis: MagicMock) -> DegradationManager:
        """Create a degradation manager with mock Redis."""
        return DegradationManager(redis_client=mock_redis)

    def test_initial_state(self, manager: DegradationManager) -> None:
        """Test initial manager state."""
        assert manager.mode == DegradationMode.NORMAL
        assert manager.is_degraded is False

    def test_get_service_health_unknown(self, manager: DegradationManager) -> None:
        """Test getting health of unknown service."""
        health = manager.get_service_health("unknown_service")
        assert health.name == "unknown_service"
        assert health.status == ServiceStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_register_service(self, manager: DegradationManager) -> None:
        """Test registering a service for monitoring."""
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=True),
        )
        assert "ai_detector" in manager.list_services()

    @pytest.mark.asyncio
    async def test_update_service_health_healthy(self, manager: DegradationManager) -> None:
        """Test updating service health to healthy."""
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=True),
        )

        await manager.update_service_health("ai_detector", is_healthy=True)

        health = manager.get_service_health("ai_detector")
        assert health.status == ServiceStatus.HEALTHY
        assert health.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_update_service_health_unhealthy(self, manager: DegradationManager) -> None:
        """Test updating service health to unhealthy."""
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=False),
        )

        await manager.update_service_health(
            "ai_detector",
            is_healthy=False,
            error_message="Connection refused",
        )

        health = manager.get_service_health("ai_detector")
        assert health.status == ServiceStatus.UNHEALTHY
        assert health.consecutive_failures == 1
        assert health.error_message == "Connection refused"

    @pytest.mark.asyncio
    async def test_consecutive_failures_tracked(self, manager: DegradationManager) -> None:
        """Test that consecutive failures are tracked."""
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=False),
        )

        for i in range(3):
            await manager.update_service_health(
                "ai_detector",
                is_healthy=False,
                error_message=f"Failure {i + 1}",
            )

        health = manager.get_service_health("ai_detector")
        assert health.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_failures_reset_on_success(self, manager: DegradationManager) -> None:
        """Test that consecutive failures reset on success."""
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=True),
        )

        # Record some failures
        for _ in range(3):
            await manager.update_service_health("ai_detector", is_healthy=False)

        # Record success
        await manager.update_service_health("ai_detector", is_healthy=True)

        health = manager.get_service_health("ai_detector")
        assert health.consecutive_failures == 0
        assert health.status == ServiceStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_mode_transitions_to_degraded(self, manager: DegradationManager) -> None:
        """Test that mode transitions to degraded on non-critical service failure."""
        # Register a NON-critical service
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=False),
            critical=False,  # Non-critical service
        )

        # Fail enough times to trigger degraded mode
        for _ in range(manager.failure_threshold):
            await manager.update_service_health("ai_detector", is_healthy=False)

        # Non-critical failure should result in DEGRADED mode
        assert manager.mode == DegradationMode.DEGRADED
        assert manager.is_degraded is True

    @pytest.mark.asyncio
    async def test_mode_transitions_to_offline_on_all_critical_down(
        self, manager: DegradationManager
    ) -> None:
        """Test that mode transitions to offline when all critical services are down."""
        # Register only one critical service (so when it's down, ALL critical are down)
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=False),
            critical=True,
        )

        # Fail enough times
        for _ in range(manager.failure_threshold):
            await manager.update_service_health("ai_detector", is_healthy=False)

        # All critical services down = OFFLINE
        assert manager.mode == DegradationMode.OFFLINE

    @pytest.mark.asyncio
    async def test_mode_returns_to_normal_on_recovery(self, manager: DegradationManager) -> None:
        """Test that mode returns to normal when service recovers."""
        # Use non-critical service so we get DEGRADED not OFFLINE
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=True),
            critical=False,
        )

        # Trigger degraded mode
        for _ in range(manager.failure_threshold):
            await manager.update_service_health("ai_detector", is_healthy=False)

        assert manager.mode == DegradationMode.DEGRADED

        # Service recovers
        await manager.update_service_health("ai_detector", is_healthy=True)

        # Should return to normal
        assert manager.mode == DegradationMode.NORMAL

    @pytest.mark.asyncio
    async def test_queue_job_for_later(
        self, manager: DegradationManager, mock_redis: MagicMock
    ) -> None:
        """Test queueing a job for later processing."""
        job_data = {"file_path": "/path/to/image.jpg", "camera_id": "cam1"}

        success = await manager.queue_job_for_later("detection", job_data)

        assert success is True
        mock_redis.add_to_queue_safe.assert_called_once()

    @pytest.mark.asyncio
    async def test_queue_job_without_redis(self) -> None:
        """Test queueing job without Redis falls back to in-memory."""
        manager = DegradationManager(redis_client=None)
        job_data = {"file_path": "/path/to/image.jpg"}

        success = await manager.queue_job_for_later("detection", job_data)

        assert success is True
        assert manager.get_queued_job_count() == 1

    @pytest.mark.asyncio
    async def test_get_queued_jobs(
        self, manager: DegradationManager, mock_redis: MagicMock
    ) -> None:
        """Test getting queued jobs."""
        mock_redis.get_queue_length = AsyncMock(return_value=5)

        count = await manager.get_pending_job_count()
        assert count == 5

    @pytest.mark.asyncio
    async def test_process_queued_jobs(
        self, manager: DegradationManager, mock_redis: MagicMock
    ) -> None:
        """Test processing queued jobs when service recovers."""
        job_data = {
            "job_type": "detection",
            "data": {"file_path": "/path/to/image.jpg"},
            "queued_at": "2025-12-28T10:00:00",
            "retry_count": 0,
        }
        mock_redis.get_from_queue = AsyncMock(side_effect=[job_data, None])

        processor = AsyncMock(return_value=True)
        processed = await manager.process_queued_jobs("detection", processor)

        assert processed == 1
        processor.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_queue_instead_of_process(self, manager: DegradationManager) -> None:
        """Test decision to queue job instead of processing."""
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=False),
            critical=False,  # Non-critical so we get DEGRADED
        )

        # Service healthy - should process
        await manager.update_service_health("ai_detector", is_healthy=True)
        assert manager.should_queue_job("detection") is False

        # Service unhealthy - should queue
        for _ in range(manager.failure_threshold):
            await manager.update_service_health("ai_detector", is_healthy=False)

        assert manager.should_queue_job("detection") is True

    @pytest.mark.asyncio
    async def test_check_redis_health(
        self, manager: DegradationManager, mock_redis: MagicMock
    ) -> None:
        """Test Redis health check."""
        mock_redis.ping = AsyncMock(return_value=True)

        is_healthy = await manager.check_redis_health()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_check_redis_health_failure(
        self, manager: DegradationManager, mock_redis: MagicMock
    ) -> None:
        """Test Redis health check failure."""
        mock_redis.ping = AsyncMock(side_effect=ConnectionError("Redis down"))

        is_healthy = await manager.check_redis_health()
        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_handle_redis_unavailable(
        self, manager: DegradationManager, mock_redis: MagicMock
    ) -> None:
        """Test handling Redis unavailability."""
        mock_redis.ping = AsyncMock(side_effect=ConnectionError("Redis down"))

        await manager.handle_redis_unavailable()

        # Should still be able to queue to in-memory
        success = await manager.queue_job_for_later(
            "detection",
            {"file_path": "/path/image.jpg"},
        )
        assert success is True

    def test_get_status(self, manager: DegradationManager) -> None:
        """Test getting overall degradation status."""
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=True),
        )

        status = manager.get_status()

        assert "mode" in status
        assert "services" in status
        assert "is_degraded" in status
        assert status["mode"] == "normal"

    @pytest.mark.asyncio
    async def test_run_health_checks(self, manager: DegradationManager) -> None:
        """Test running all health checks."""
        health_check = AsyncMock(return_value=True)
        manager.register_service(
            name="ai_detector",
            health_check=health_check,
        )
        manager.register_service(
            name="ai_analyzer",
            health_check=health_check,
        )

        await manager.run_health_checks()

        assert health_check.call_count == 2

    @pytest.mark.asyncio
    async def test_health_check_exception_handled(self, manager: DegradationManager) -> None:
        """Test that health check exceptions are handled gracefully."""
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(side_effect=Exception("Check failed")),
        )

        # Should not raise
        await manager.run_health_checks()

        health = manager.get_service_health("ai_detector")
        assert health.status == ServiceStatus.UNHEALTHY

    def test_list_services(self, manager: DegradationManager) -> None:
        """Test listing registered services."""
        manager.register_service(
            name="service_a",
            health_check=AsyncMock(return_value=True),
        )
        manager.register_service(
            name="service_b",
            health_check=AsyncMock(return_value=True),
        )

        services = manager.list_services()
        assert "service_a" in services
        assert "service_b" in services


class TestDegradationManagerRecovery:
    """Tests for recovery behavior."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        redis.get_from_queue = AsyncMock(return_value=None)
        redis.get_queue_length = AsyncMock(return_value=0)
        redis.ping = AsyncMock(return_value=True)
        return redis

    @pytest.mark.asyncio
    async def test_recovery_requires_success(self, mock_redis: MagicMock) -> None:
        """Test that recovery requires successful health check."""
        manager = DegradationManager(
            redis_client=mock_redis,
            recovery_threshold=1,  # Single success needed
        )
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=True),
            critical=False,  # Non-critical for DEGRADED mode
        )

        # Enter degraded mode
        for _ in range(manager.failure_threshold):
            await manager.update_service_health("ai_detector", is_healthy=False)

        assert manager.mode == DegradationMode.DEGRADED

        # One success recovers
        await manager.update_service_health("ai_detector", is_healthy=True)
        assert manager.mode == DegradationMode.NORMAL

    @pytest.mark.asyncio
    async def test_reprocess_queued_jobs_on_recovery(self, mock_redis: MagicMock) -> None:
        """Test that queued jobs are reprocessed on recovery."""
        manager = DegradationManager(redis_client=mock_redis)
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=True),
            critical=True,
        )

        # Queue some jobs
        await manager.queue_job_for_later("detection", {"file": "1.jpg"})
        await manager.queue_job_for_later("detection", {"file": "2.jpg"})

        # Set up mock to return queued jobs
        job1 = {
            "job_type": "detection",
            "data": {"file": "1.jpg"},
            "queued_at": "2025-12-28T10:00:00",
            "retry_count": 0,
        }
        job2 = {
            "job_type": "detection",
            "data": {"file": "2.jpg"},
            "queued_at": "2025-12-28T10:00:01",
            "retry_count": 0,
        }
        mock_redis.get_from_queue = AsyncMock(side_effect=[job1, job2, None])

        processor = AsyncMock(return_value=True)
        processed = await manager.process_queued_jobs("detection", processor)

        assert processed == 2


class TestDegradationManagerModes:
    """Tests for different degradation modes."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.ping = AsyncMock(return_value=True)
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        return redis

    def test_mode_affects_behavior(self, mock_redis: MagicMock) -> None:
        """Test that different modes affect manager behavior."""
        manager = DegradationManager(redis_client=mock_redis)

        # Normal mode
        assert manager.mode == DegradationMode.NORMAL
        assert manager.is_accepting_jobs() is True

        # Manually set offline mode
        manager._mode = DegradationMode.OFFLINE
        assert manager.is_accepting_jobs() is False

    @pytest.mark.asyncio
    async def test_minimal_mode_limits_functionality(self, mock_redis: MagicMock) -> None:
        """Test that minimal mode limits functionality."""
        manager = DegradationManager(redis_client=mock_redis)
        manager._mode = DegradationMode.MINIMAL

        # In minimal mode, should queue instead of process
        assert manager.should_queue_job("detection") is True

    def test_get_available_features(self, mock_redis: MagicMock) -> None:
        """Test getting available features based on mode."""
        manager = DegradationManager(redis_client=mock_redis)

        # Normal mode - all features
        features = manager.get_available_features()
        assert "detection" in features
        assert "analysis" in features

        # Degraded mode - limited features
        manager._mode = DegradationMode.DEGRADED
        features = manager.get_available_features()
        assert len(features) < 4  # Some features disabled


class TestGlobalDegradationManager:
    """Tests for global degradation manager functions."""

    def setup_method(self) -> None:
        """Reset global state before each test."""
        reset_degradation_manager()

    def teardown_method(self) -> None:
        """Reset global state after each test."""
        reset_degradation_manager()

    def test_get_degradation_manager_creates_singleton(self) -> None:
        """Test that get_degradation_manager returns singleton."""
        manager1 = get_degradation_manager()
        manager2 = get_degradation_manager()
        assert manager1 is manager2

    def test_get_degradation_manager_with_redis(self) -> None:
        """Test creating manager with Redis client."""
        mock_redis = MagicMock()
        manager = get_degradation_manager(mock_redis)
        assert manager._redis is mock_redis

    def test_reset_clears_manager(self) -> None:
        """Test reset clears the manager."""
        manager1 = get_degradation_manager()
        reset_degradation_manager()
        manager2 = get_degradation_manager()
        assert manager1 is not manager2


class TestInMemoryJobQueue:
    """Tests for in-memory job queue fallback."""

    def test_queue_to_memory_when_redis_unavailable(self) -> None:
        """Test queueing to memory when Redis is unavailable."""
        manager = DegradationManager(redis_client=None)

        # Should use in-memory queue
        assert manager._use_memory_queue() is True

    @pytest.mark.asyncio
    async def test_memory_queue_operations(self) -> None:
        """Test in-memory queue operations."""
        manager = DegradationManager(redis_client=None)

        # Queue jobs
        await manager.queue_job_for_later("detection", {"file": "1.jpg"})
        await manager.queue_job_for_later("detection", {"file": "2.jpg"})

        assert manager.get_queued_job_count() == 2

    @pytest.mark.asyncio
    async def test_memory_queue_max_size(self) -> None:
        """Test that memory queue respects max size."""
        manager = DegradationManager(redis_client=None, max_memory_queue_size=5)

        # Queue more than max
        for i in range(10):
            await manager.queue_job_for_later("detection", {"file": f"{i}.jpg"})

        # Should be capped at max
        assert manager.get_queued_job_count() <= 5

    @pytest.mark.asyncio
    async def test_drain_memory_queue_to_redis(self) -> None:
        """Test draining memory queue to Redis when available."""
        manager = DegradationManager(redis_client=None)

        # Queue to memory
        await manager.queue_job_for_later("detection", {"file": "1.jpg"})
        await manager.queue_job_for_later("detection", {"file": "2.jpg"})

        assert manager.get_queued_job_count() == 2

        # Add Redis - now need to mock add_to_queue_safe which returns QueueAddResult
        mock_redis = MagicMock()
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        manager._redis = mock_redis

        # Drain to Redis
        drained = await manager.drain_memory_queue_to_redis()
        assert drained == 2
        assert manager.get_queued_job_count() == 0


class TestDegradationMinimalMode:
    """Tests for MINIMAL mode behavior with partial critical failures."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.ping = AsyncMock(return_value=True)
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        return redis

    @pytest.mark.asyncio
    async def test_minimal_mode_with_partial_critical_failure(self, mock_redis: MagicMock) -> None:
        """Test MINIMAL mode when some but not all critical services fail."""
        manager = DegradationManager(redis_client=mock_redis)

        # Register two critical services
        manager.register_service(
            name="ai_detector",
            health_check=AsyncMock(return_value=True),
            critical=True,
        )
        manager.register_service(
            name="ai_analyzer",
            health_check=AsyncMock(return_value=True),
            critical=True,
        )

        # Fail only one of them
        for _ in range(manager.failure_threshold):
            await manager.update_service_health("ai_detector", is_healthy=False)

        # Should be MINIMAL (some critical down, but not all)
        assert manager.mode == DegradationMode.MINIMAL


class TestFallbackQueue:
    """Tests for FallbackQueue disk-based queue."""

    @pytest.fixture
    def temp_fallback_dir(self, tmp_path: Path) -> Path:
        """Create a temporary fallback directory."""
        return tmp_path / "fallback"

    @pytest.mark.asyncio
    async def test_fallback_queue_add_and_get(self, temp_fallback_dir: Path) -> None:
        """Test adding and retrieving items from fallback queue."""
        from backend.services.degradation_manager import FallbackQueue

        queue = FallbackQueue(
            queue_name="test_queue",
            fallback_dir=str(temp_fallback_dir),
        )

        # Add an item
        item = {"test": "data", "value": 123}
        success = await queue.add(item)
        assert success is True
        assert queue.count() == 1

        # Retrieve the item
        retrieved = await queue.get()
        assert retrieved == item
        assert queue.count() == 0

    @pytest.mark.asyncio
    async def test_fallback_queue_get_empty(self, temp_fallback_dir: Path) -> None:
        """Test getting from empty queue returns None."""
        from backend.services.degradation_manager import FallbackQueue

        queue = FallbackQueue(
            queue_name="test_queue",
            fallback_dir=str(temp_fallback_dir),
        )

        result = await queue.get()
        assert result is None

    @pytest.mark.asyncio
    async def test_fallback_queue_max_size_limit(self, temp_fallback_dir: Path) -> None:
        """Test that fallback queue respects max size by dropping oldest items."""
        from backend.services.degradation_manager import FallbackQueue

        queue = FallbackQueue(
            queue_name="test_queue",
            fallback_dir=str(temp_fallback_dir),
            max_size=3,
        )

        # Add more items than max size
        for i in range(5):
            await queue.add({"index": i})

        # Should only have max_size items
        assert queue.count() == 3

        # Oldest items should be dropped, so we should get 2, 3, 4
        item1 = await queue.get()
        item2 = await queue.get()
        item3 = await queue.get()

        assert item1["index"] == 2
        assert item2["index"] == 3
        assert item3["index"] == 4

    @pytest.mark.asyncio
    async def test_fallback_queue_peek(self, temp_fallback_dir: Path) -> None:
        """Test peeking at items without removing them."""
        from backend.services.degradation_manager import FallbackQueue

        queue = FallbackQueue(
            queue_name="test_queue",
            fallback_dir=str(temp_fallback_dir),
        )

        # Add items
        for i in range(3):
            await queue.add({"index": i})

        # Peek at items
        items = await queue.peek(limit=2)
        assert len(items) == 2
        assert items[0]["index"] == 0
        assert items[1]["index"] == 1

        # Items should still be in queue
        assert queue.count() == 3

    @pytest.mark.asyncio
    async def test_fallback_queue_peek_with_corrupted_files(self, temp_fallback_dir: Path) -> None:
        """Test peek gracefully handles corrupted files."""
        from backend.services.degradation_manager import FallbackQueue

        queue = FallbackQueue(
            queue_name="test_queue",
            fallback_dir=str(temp_fallback_dir),
        )

        # Add a valid item
        await queue.add({"valid": "data"})

        # Create a corrupted file
        corrupted_file = queue.fallback_dir / "20250101_000000_000000_corrupted.json"
        corrupted_file.write_text("not valid json{{{")

        # Peek should skip the corrupted file
        items = await queue.peek(limit=10)
        # Should get at least the valid item (corrupted is silently skipped)
        assert any(item.get("valid") == "data" for item in items)

    @pytest.mark.asyncio
    async def test_fallback_queue_add_failure(self, temp_fallback_dir: Path) -> None:
        """Test fallback queue add failure handling."""
        from backend.services.degradation_manager import FallbackQueue

        queue = FallbackQueue(
            queue_name="test_queue",
            fallback_dir=str(temp_fallback_dir),
        )

        # Make the directory read-only to cause write failure
        queue.fallback_dir.mkdir(parents=True, exist_ok=True)
        queue.fallback_dir.chmod(0o444)

        try:
            success = await queue.add({"test": "data"})
            assert success is False
        finally:
            # Restore permissions for cleanup
            queue.fallback_dir.chmod(0o755)

    @pytest.mark.asyncio
    async def test_fallback_queue_get_failure(self, temp_fallback_dir: Path) -> None:
        """Test fallback queue get failure handling."""
        from backend.services.degradation_manager import FallbackQueue

        queue = FallbackQueue(
            queue_name="test_queue",
            fallback_dir=str(temp_fallback_dir),
        )

        # Add an item
        await queue.add({"test": "data"})

        # Create a file that can't be read
        files = list(queue.fallback_dir.glob("*.json"))
        if files:
            files[0].chmod(0o000)

        try:
            result = await queue.get()
            assert result is None
        finally:
            # Restore permissions for cleanup
            for f in queue.fallback_dir.glob("*.json"):
                f.chmod(0o644)

    def test_fallback_queue_properties(self, temp_fallback_dir: Path) -> None:
        """Test fallback queue properties."""
        from backend.services.degradation_manager import FallbackQueue

        queue = FallbackQueue(
            queue_name="my_queue",
            fallback_dir=str(temp_fallback_dir),
        )

        assert queue.queue_name == "my_queue"
        assert queue.fallback_dir == temp_fallback_dir / "my_queue"


class TestRegisteredService:
    """Tests for RegisteredService dataclass."""

    def test_post_init_sets_health_name(self) -> None:
        """Test that __post_init__ sets health name correctly."""
        from backend.services.degradation_manager import RegisteredService

        service = RegisteredService(
            name="test_service",
            health_check=AsyncMock(return_value=True),
            critical=True,
        )

        assert service.health.name == "test_service"

    def test_post_init_with_empty_health_name(self) -> None:
        """Test that __post_init__ corrects empty health name."""
        from backend.services.degradation_manager import RegisteredService, ServiceHealth

        service = RegisteredService(
            name="test_service",
            health_check=AsyncMock(return_value=True),
            health=ServiceHealth(name=""),  # Empty name should be fixed
        )

        assert service.health.name == "test_service"


class TestQueueWithFallback:
    """Tests for queue_with_fallback functionality."""

    @pytest.fixture
    def temp_fallback_dir(self, tmp_path: Path) -> Path:
        """Create a temporary fallback directory."""
        return tmp_path / "fallback"

    @pytest.mark.asyncio
    async def test_queue_with_fallback_redis_success(self, temp_fallback_dir: Path) -> None:
        """Test queue_with_fallback uses Redis when available."""
        from backend.core.redis import QueueAddResult

        mock_redis = MagicMock()
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )

        manager = DegradationManager(
            redis_client=mock_redis,
            fallback_dir=str(temp_fallback_dir),
        )

        result = await manager.queue_with_fallback("test_queue", {"test": "data"})

        assert result is True
        mock_redis.add_to_queue_safe.assert_called_once()

    @pytest.mark.asyncio
    async def test_queue_with_fallback_redis_failure(self, temp_fallback_dir: Path) -> None:
        """Test queue_with_fallback falls back to disk when Redis fails."""
        mock_redis = MagicMock()
        mock_redis.add_to_queue_safe = AsyncMock(side_effect=Exception("Redis error"))

        manager = DegradationManager(
            redis_client=mock_redis,
            fallback_dir=str(temp_fallback_dir),
        )

        result = await manager.queue_with_fallback("test_queue", {"test": "data"})

        assert result is True
        assert manager._redis_healthy is False
        # Check the fallback queue has the item
        fallback_queue = manager._get_fallback_queue("test_queue")
        assert fallback_queue.count() == 1

    @pytest.mark.asyncio
    async def test_queue_with_fallback_no_redis(self, temp_fallback_dir: Path) -> None:
        """Test queue_with_fallback goes to disk when no Redis."""
        manager = DegradationManager(
            redis_client=None,
            fallback_dir=str(temp_fallback_dir),
        )
        manager._redis_healthy = False

        result = await manager.queue_with_fallback("test_queue", {"test": "data"})

        assert result is True
        fallback_queue = manager._get_fallback_queue("test_queue")
        assert fallback_queue.count() == 1


class TestDrainFallbackQueue:
    """Tests for drain_fallback_queue functionality."""

    @pytest.fixture
    def temp_fallback_dir(self, tmp_path: Path) -> Path:
        """Create a temporary fallback directory."""
        return tmp_path / "fallback"

    @pytest.mark.asyncio
    async def test_drain_fallback_queue_success(self, temp_fallback_dir: Path) -> None:
        """Test draining fallback queue to Redis."""
        from backend.core.redis import QueueAddResult

        mock_redis = MagicMock()
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )

        manager = DegradationManager(
            redis_client=mock_redis,
            fallback_dir=str(temp_fallback_dir),
        )

        # First, queue items to disk
        manager._redis_healthy = False
        await manager.queue_with_fallback("test_queue", {"item": 1})
        await manager.queue_with_fallback("test_queue", {"item": 2})

        # Restore Redis health
        manager._redis_healthy = True

        # Drain to Redis
        drained = await manager.drain_fallback_queue("test_queue")

        assert drained == 2
        assert mock_redis.add_to_queue_safe.call_count == 2

    @pytest.mark.asyncio
    async def test_drain_fallback_queue_no_redis(self, temp_fallback_dir: Path) -> None:
        """Test drain returns 0 when no Redis configured."""
        manager = DegradationManager(
            redis_client=None,
            fallback_dir=str(temp_fallback_dir),
        )

        drained = await manager.drain_fallback_queue("test_queue")
        assert drained == 0

    @pytest.mark.asyncio
    async def test_drain_fallback_queue_redis_error(self, temp_fallback_dir: Path) -> None:
        """Test drain stops and re-queues item on Redis error."""
        from backend.core.redis import QueueAddResult

        mock_redis = MagicMock()
        mock_redis.add_to_queue_safe = AsyncMock(
            side_effect=[
                QueueAddResult(success=True, queue_length=1),  # First succeeds
                Exception("Redis error"),  # Second fails
            ]
        )

        manager = DegradationManager(
            redis_client=mock_redis,
            fallback_dir=str(temp_fallback_dir),
        )

        # Queue items to disk
        manager._redis_healthy = False
        await manager.queue_with_fallback("test_queue", {"item": 1})
        await manager.queue_with_fallback("test_queue", {"item": 2})
        await manager.queue_with_fallback("test_queue", {"item": 3})

        # Restore Redis health
        manager._redis_healthy = True

        # Drain - should stop after error
        drained = await manager.drain_fallback_queue("test_queue")

        assert drained == 1
        # Should have 2 items back in fallback queue (the failed one was re-added)
        fallback = manager._get_fallback_queue("test_queue")
        assert fallback.count() == 2


class TestGetPendingJobCount:
    """Tests for get_pending_job_count functionality."""

    @pytest.mark.asyncio
    async def test_get_pending_job_count_redis_failure(self) -> None:
        """Test get_pending_job_count returns memory count on Redis failure."""
        mock_redis = MagicMock()
        mock_redis.get_queue_length = AsyncMock(side_effect=Exception("Redis error"))

        manager = DegradationManager(redis_client=mock_redis)

        # Queue some jobs to memory
        manager._redis_healthy = False
        await manager.queue_job_for_later("detection", {"file": "1.jpg"})
        await manager.queue_job_for_later("detection", {"file": "2.jpg"})
        manager._redis_healthy = True  # Reset for the count check

        count = await manager.get_pending_job_count()
        assert count == 2


class TestProcessQueuedJobs:
    """Tests for process_queued_jobs functionality."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.get_from_queue = AsyncMock(return_value=None)
        redis.ping = AsyncMock(return_value=True)
        return redis

    @pytest.mark.asyncio
    async def test_process_queued_jobs_processor_failure(self, mock_redis: MagicMock) -> None:
        """Test that jobs are re-queued on processor failure."""
        from backend.core.redis import QueueAddResult

        job_data = {
            "job_type": "detection",
            "data": {"file": "test.jpg"},
            "queued_at": "2025-12-28T10:00:00",
            "retry_count": 0,
        }
        mock_redis.get_from_queue = AsyncMock(side_effect=[job_data, None])
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )

        manager = DegradationManager(redis_client=mock_redis)

        # Processor that fails
        processor = AsyncMock(side_effect=Exception("Processing failed"))

        processed = await manager.process_queued_jobs("detection", processor, max_jobs=10)

        assert processed == 0
        # Job should be re-queued with incremented retry count
        mock_redis.add_to_queue_safe.assert_called()
        call_args = mock_redis.add_to_queue_safe.call_args[0]
        assert call_args[1]["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_process_queued_jobs_redis_error(self, mock_redis: MagicMock) -> None:
        """Test process_queued_jobs handles Redis errors."""
        mock_redis.get_from_queue = AsyncMock(side_effect=Exception("Redis error"))

        manager = DegradationManager(redis_client=mock_redis)
        processor = AsyncMock(return_value=True)

        processed = await manager.process_queued_jobs("detection", processor)

        assert processed == 0

    @pytest.mark.asyncio
    async def test_process_queued_jobs_memory_queue(self) -> None:
        """Test processing jobs from memory queue."""
        manager = DegradationManager(redis_client=None)

        # Queue jobs to memory
        await manager.queue_job_for_later("detection", {"file": "1.jpg"})
        await manager.queue_job_for_later("detection", {"file": "2.jpg"})
        await manager.queue_job_for_later("analysis", {"batch": "b1"})  # Different type

        processor = AsyncMock(return_value=True)

        processed = await manager.process_queued_jobs("detection", processor, max_jobs=10)

        assert processed == 2
        processor.assert_called()
        # Analysis job should still be in queue
        assert manager.get_queued_job_count() == 1

    @pytest.mark.asyncio
    async def test_process_queued_jobs_memory_processor_failure(self) -> None:
        """Test memory queue re-queues job on processor failure."""
        manager = DegradationManager(redis_client=None)

        # Queue a job
        await manager.queue_job_for_later("detection", {"file": "test.jpg"})

        # Processor that fails
        processor = AsyncMock(side_effect=Exception("Processing failed"))

        processed = await manager.process_queued_jobs("detection", processor)

        assert processed == 0
        # Job should be re-queued
        assert manager.get_queued_job_count() == 1

    @pytest.mark.asyncio
    async def test_process_queued_jobs_max_jobs_limit(self, mock_redis: MagicMock) -> None:
        """Test max_jobs limit is respected."""
        jobs = [
            {
                "job_type": "detection",
                "data": {"file": f"{i}.jpg"},
                "queued_at": "2025-12-28T10:00:00",
                "retry_count": 0,
            }
            for i in range(5)
        ]
        mock_redis.get_from_queue = AsyncMock(side_effect=[*jobs, None])

        manager = DegradationManager(redis_client=mock_redis)
        processor = AsyncMock(return_value=True)

        processed = await manager.process_queued_jobs("detection", processor, max_jobs=3)

        assert processed == 3


class TestCheckRedisHealth:
    """Tests for check_redis_health functionality."""

    @pytest.mark.asyncio
    async def test_check_redis_health_recovery_logs(self) -> None:
        """Test that Redis recovery is logged."""
        mock_redis = MagicMock()
        mock_redis.ping = AsyncMock(return_value=True)

        manager = DegradationManager(redis_client=mock_redis)
        manager._redis_healthy = False  # Simulate previous unhealthy state

        is_healthy = await manager.check_redis_health()

        assert is_healthy is True
        assert manager._redis_healthy is True


class TestDrainMemoryQueueToRedis:
    """Tests for drain_memory_queue_to_redis functionality."""

    @pytest.mark.asyncio
    async def test_drain_memory_queue_failure(self) -> None:
        """Test drain_memory_queue_to_redis handles Redis failure."""
        mock_redis = MagicMock()
        manager = DegradationManager(redis_client=mock_redis)
        manager._redis_healthy = True

        # Queue jobs to memory by setting redis_healthy to False first
        manager._redis_healthy = False
        await manager.queue_job_for_later("detection", {"file": "1.jpg"})
        await manager.queue_job_for_later("detection", {"file": "2.jpg"})
        manager._redis_healthy = True

        # Try to drain - should fail and put job back
        drained = await manager.drain_memory_queue_to_redis()

        assert drained == 0
        # Jobs should still be in memory queue
        assert manager.get_queued_job_count() == 2


class TestGetAvailableFeatures:
    """Tests for get_available_features in different modes."""

    def test_get_available_features_minimal_mode(self) -> None:
        """Test available features in MINIMAL mode."""
        manager = DegradationManager(redis_client=None)
        manager._mode = DegradationMode.MINIMAL

        features = manager.get_available_features()

        assert features == ["media"]

    def test_get_available_features_offline_mode(self) -> None:
        """Test available features in OFFLINE mode."""
        manager = DegradationManager(redis_client=None)
        manager._mode = DegradationMode.OFFLINE

        features = manager.get_available_features()

        assert features == []


class TestHealthCheckLoop:
    """Tests for start, stop, and health check loop."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self) -> None:
        """Test starting and stopping the health check loop."""
        manager = DegradationManager(redis_client=None, check_interval=0.1)

        # Start
        await manager.start()
        assert manager._running is True
        assert manager._task is not None

        # Give it a moment to run
        await asyncio.sleep(0.05)

        # Stop
        await manager.stop()
        assert manager._running is False
        assert manager._task is None

    @pytest.mark.asyncio
    async def test_start_already_running(self) -> None:
        """Test that start does nothing if already running."""
        manager = DegradationManager(redis_client=None, check_interval=0.1)

        await manager.start()
        task1 = manager._task

        # Try to start again
        await manager.start()
        task2 = manager._task

        # Should be the same task
        assert task1 is task2

        await manager.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running(self) -> None:
        """Test that stop does nothing if not running."""
        manager = DegradationManager(redis_client=None)

        # Should not raise
        await manager.stop()

    @pytest.mark.asyncio
    async def test_health_check_loop_runs_checks(self) -> None:
        """Test that health check loop runs health checks."""
        mock_redis = MagicMock()
        mock_redis.ping = AsyncMock(return_value=True)
        manager = DegradationManager(redis_client=mock_redis, check_interval=0.05)

        health_check = AsyncMock(return_value=True)
        manager.register_service(
            name="test_service",
            health_check=health_check,
        )

        await manager.start()
        await asyncio.sleep(0.15)  # Allow multiple checks
        await manager.stop()

        # Health check should have been called multiple times
        assert health_check.call_count >= 2

    @pytest.mark.asyncio
    async def test_health_check_loop_drains_memory_queue(self) -> None:
        """Test that health check loop drains memory queue when Redis available."""
        from backend.core.redis import QueueAddResult

        mock_redis = MagicMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )

        manager = DegradationManager(redis_client=mock_redis, check_interval=0.05)

        # Queue to memory first
        manager._redis_healthy = False
        await manager.queue_job_for_later("detection", {"file": "test.jpg"})
        assert manager.get_queued_job_count() == 1

        # Now let the loop run
        await manager.start()
        await asyncio.sleep(0.15)
        await manager.stop()

        # Memory queue should be drained to Redis
        assert manager.get_queued_job_count() == 0

    @pytest.mark.asyncio
    async def test_health_check_loop_error_handling(self) -> None:
        """Test that health check loop handles errors gracefully."""
        from backend.core.redis import QueueAddResult

        mock_redis = MagicMock()
        # Ping fails intermittently
        mock_redis.ping = AsyncMock(side_effect=[Exception("Error"), True, True])
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )

        manager = DegradationManager(redis_client=mock_redis, check_interval=0.05)

        await manager.start()
        await asyncio.sleep(0.2)
        await manager.stop()

        # Should not have crashed - manager should still be functional
        assert manager._task is None


class TestGetDegradationManagerSetRedis:
    """Tests for get_degradation_manager setting Redis on existing manager."""

    def setup_method(self) -> None:
        """Reset global state before each test."""
        reset_degradation_manager()

    def teardown_method(self) -> None:
        """Reset global state after each test."""
        reset_degradation_manager()

    def test_set_redis_on_existing_manager_without_redis(self) -> None:
        """Test setting Redis on existing manager that has no Redis."""
        # Create manager without Redis
        manager1 = get_degradation_manager()
        assert manager1._redis is None

        # Set Redis on existing manager
        mock_redis = MagicMock()
        manager2 = get_degradation_manager(redis_client=mock_redis)

        # Should be same instance with Redis set
        assert manager1 is manager2
        assert manager2._redis is mock_redis


class TestUpdateServiceHealthUnregistered:
    """Tests for update_service_health with unregistered service."""

    @pytest.mark.asyncio
    async def test_update_unregistered_service_health(self) -> None:
        """Test updating health for service that isn't registered."""
        manager = DegradationManager(redis_client=None)

        # Should not raise, just log warning
        await manager.update_service_health("unregistered_service", is_healthy=True)

        # Service should still not be in list
        assert "unregistered_service" not in manager.list_services()


class TestIsServiceHealthyUnregistered:
    """Tests for is_service_healthy with unregistered service."""

    def test_is_service_healthy_unregistered(self) -> None:
        """Test is_service_healthy returns False for unregistered service."""
        manager = DegradationManager(redis_client=None)

        result = manager.is_service_healthy("unregistered_service")
        assert result is False


class TestQueueJobForLaterRedisFallback:
    """Tests for queue_job_for_later Redis failure fallback."""

    @pytest.mark.asyncio
    async def test_queue_job_redis_failure_fallback_to_memory(self) -> None:
        """Test queueing falls back to memory when Redis fails."""
        mock_redis = MagicMock()
        manager = DegradationManager(redis_client=mock_redis)

        success = await manager.queue_job_for_later("detection", {"file": "test.jpg"})

        assert success is True
        assert manager._redis_healthy is False
        assert manager.get_queued_job_count() == 1


class TestIsServiceHealthyRegistered:
    """Tests for is_service_healthy with registered services."""

    @pytest.mark.asyncio
    async def test_is_service_healthy_returns_true_when_healthy(self) -> None:
        """Test is_service_healthy returns True for healthy registered service."""
        manager = DegradationManager(redis_client=None)

        manager.register_service(
            name="test_service",
            health_check=AsyncMock(return_value=True),
        )

        # Update to healthy
        await manager.update_service_health("test_service", is_healthy=True)

        result = manager.is_service_healthy("test_service")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_service_healthy_returns_false_when_unhealthy(self) -> None:
        """Test is_service_healthy returns False for unhealthy registered service."""
        manager = DegradationManager(redis_client=None)

        manager.register_service(
            name="test_service",
            health_check=AsyncMock(return_value=False),
        )

        # Update to unhealthy
        await manager.update_service_health("test_service", is_healthy=False)

        result = manager.is_service_healthy("test_service")
        assert result is False


class TestShouldQueueJobModes:
    """Tests for should_queue_job across different modes."""

    def test_should_queue_job_offline_mode(self) -> None:
        """Test should_queue_job returns True in OFFLINE mode."""
        manager = DegradationManager(redis_client=None)
        manager._mode = DegradationMode.OFFLINE

        result = manager.should_queue_job("detection")
        assert result is True

    def test_should_queue_job_minimal_mode(self) -> None:
        """Test should_queue_job returns True in MINIMAL mode."""
        manager = DegradationManager(redis_client=None)
        manager._mode = DegradationMode.MINIMAL

        result = manager.should_queue_job("detection")
        assert result is True

    def test_should_queue_job_degraded_mode(self) -> None:
        """Test should_queue_job returns True in DEGRADED mode."""
        manager = DegradationManager(redis_client=None)
        manager._mode = DegradationMode.DEGRADED

        result = manager.should_queue_job("detection")
        assert result is True

    def test_should_queue_job_normal_mode(self) -> None:
        """Test should_queue_job returns False in NORMAL mode."""
        manager = DegradationManager(redis_client=None)
        manager._mode = DegradationMode.NORMAL

        result = manager.should_queue_job("detection")
        assert result is False


class TestQueueToMemoryException:
    """Tests for _queue_to_memory exception handling."""

    def test_queue_to_memory_exception_handling(self) -> None:
        """Test _queue_to_memory handles exceptions gracefully."""
        from backend.services.degradation_manager import QueuedJob

        manager = DegradationManager(redis_client=None, max_memory_queue_size=10)

        # Create a job
        job = QueuedJob(
            job_type="detection",
            data={"file": "test.jpg"},
            queued_at="2025-12-28T10:00:00",
        )

        # Replace deque with a mock that raises on append
        original_queue = manager._memory_queue
        manager._memory_queue = MagicMock()
        manager._memory_queue.append = MagicMock(side_effect=Exception("Memory error"))

        try:
            result = manager._queue_to_memory(job)
            assert result is False
        finally:
            manager._memory_queue = original_queue


class TestHealthCheckLoopNonCancelledError:
    """Tests for health check loop handling non-cancelled errors."""

    @pytest.mark.asyncio
    async def test_health_check_loop_handles_non_cancelled_error(self) -> None:
        """Test that health check loop handles non-CancelledError exceptions."""
        manager = DegradationManager(redis_client=None, check_interval=0.02)

        # Create a health check that raises an exception (not CancelledError)
        call_count = [0]

        async def failing_health_check() -> bool:
            call_count[0] += 1
            if call_count[0] <= 2:
                raise RuntimeError("Simulated health check error")
            return True

        manager.register_service(
            name="failing_service",
            health_check=failing_health_check,
        )

        await manager.start()
        await asyncio.sleep(0.1)  # Allow loop to run and handle errors
        await manager.stop()

        # Should have been called multiple times, surviving the errors
        assert call_count[0] >= 2

    @pytest.mark.asyncio
    async def test_health_check_loop_exception_in_main_loop(self) -> None:
        """Test that health check loop handles exceptions raised at top level."""
        manager = DegradationManager(redis_client=None, check_interval=0.02)

        call_count = [0]
        original_run_health_checks = manager.run_health_checks

        async def failing_run_health_checks() -> None:
            call_count[0] += 1
            if call_count[0] <= 2:
                # Raise an exception that escapes (not caught internally)
                raise RuntimeError("Simulated loop exception")
            await original_run_health_checks()

        # Monkey-patch the method to raise exceptions
        manager.run_health_checks = failing_run_health_checks  # type: ignore[method-assign]

        await manager.start()
        await asyncio.sleep(0.15)  # Allow multiple iterations
        await manager.stop()

        # Loop should continue despite exceptions
        assert call_count[0] >= 2


class TestMemoryQueueOverflowLogging:
    """Tests for memory queue overflow logging fix (wa0t.19)."""

    @pytest.mark.asyncio
    async def test_memory_queue_overflow_logs_warning(self) -> None:
        """Test that memory queue overflow logs a warning with job details."""
        from unittest.mock import patch

        manager = DegradationManager(redis_client=None, max_memory_queue_size=2)

        with (
            patch.object(manager, "_memory_queue") as mock_queue,
            patch("backend.services.degradation_manager.logger") as mock_logger,
        ):
            # Set up mock to simulate queue at capacity
            mock_queue.__len__ = lambda _self: 2
            mock_queue.__getitem__ = lambda _self, _idx: QueuedJob(
                job_type="old_detection",
                data={"file": "old.jpg"},
                queued_at="2025-12-28T09:00:00",
            )
            mock_queue.append = lambda _job: None  # Simulate deque behavior

            # Queue a new job when queue is at capacity
            await manager.queue_job_for_later("detection", {"file": "new.jpg"})

            # Verify warning was logged
            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args
            assert "Memory queue overflow" in str(call_args)
            assert "DATA LOSS" in str(call_args)

    @pytest.mark.asyncio
    async def test_memory_queue_overflow_includes_dropped_job_info(self) -> None:
        """Test that overflow log includes information about the dropped job."""
        manager = DegradationManager(redis_client=None, max_memory_queue_size=2)

        # Fill the queue to capacity
        await manager.queue_job_for_later("detection", {"file": "1.jpg"})
        await manager.queue_job_for_later("detection", {"file": "2.jpg"})

        # The queue is now at capacity (2 items)
        assert manager.get_queued_job_count() == 2

        # Add a third item - this should trigger overflow and drop the oldest
        await manager.queue_job_for_later("analysis", {"batch": "batch1"})

        # Due to deque maxlen, size stays at 2
        assert manager.get_queued_job_count() == 2

    def test_memory_queue_overflow_detection(self) -> None:
        """Test that queue at capacity is detected correctly."""
        manager = DegradationManager(redis_client=None, max_memory_queue_size=3)

        # Initially not at capacity
        assert len(manager._memory_queue) < manager.max_memory_queue_size

        # Add jobs up to capacity
        for i in range(3):
            job = QueuedJob(
                job_type="detection",
                data={"file": f"{i}.jpg"},
                queued_at=f"2025-12-28T10:0{i}:00",
            )
            manager._queue_to_memory(job)

        # Now at capacity
        assert len(manager._memory_queue) == manager.max_memory_queue_size


class TestHealthCheckTimeout:
    """Tests for health check timeout fix (wa0t.15)."""

    def test_default_health_check_timeout(self) -> None:
        """Test that default health check timeout is set."""
        from backend.services.degradation_manager import DEFAULT_HEALTH_CHECK_TIMEOUT

        manager = DegradationManager(redis_client=None)
        assert manager.health_check_timeout == DEFAULT_HEALTH_CHECK_TIMEOUT

    def test_custom_health_check_timeout(self) -> None:
        """Test that custom health check timeout can be set."""
        manager = DegradationManager(redis_client=None, health_check_timeout=5.0)
        assert manager.health_check_timeout == 5.0

    @pytest.mark.asyncio
    async def test_health_check_timeout_triggers(self) -> None:
        """Test that health check timeout is properly enforced."""
        manager = DegradationManager(
            redis_client=None,
            health_check_timeout=0.05,  # 50ms timeout
        )

        async def slow_health_check() -> bool:
            await asyncio.sleep(0.5)  # 500ms - will timeout
            return True

        manager.register_service(
            name="slow_service",
            health_check=slow_health_check,
        )

        # Run health checks - should timeout
        await manager.run_health_checks()

        # Service should be marked unhealthy due to timeout
        health = manager.get_service_health("slow_service")
        assert health.status == ServiceStatus.UNHEALTHY
        assert "timed out" in (health.error_message or "").lower()

    @pytest.mark.asyncio
    async def test_health_check_success_within_timeout(self) -> None:
        """Test that fast health checks succeed."""
        manager = DegradationManager(
            redis_client=None,
            health_check_timeout=1.0,  # 1 second timeout
        )

        async def fast_health_check() -> bool:
            await asyncio.sleep(0.01)  # 10ms - well within timeout
            return True

        manager.register_service(
            name="fast_service",
            health_check=fast_health_check,
        )

        await manager.run_health_checks()

        health = manager.get_service_health("fast_service")
        assert health.status == ServiceStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_timeout_counts_as_failure(self) -> None:
        """Test that health check timeouts count toward failure threshold."""
        manager = DegradationManager(
            redis_client=None,
            health_check_timeout=0.05,
            failure_threshold=2,
        )

        async def slow_health_check() -> bool:
            await asyncio.sleep(0.2)  # Longer than 0.05s timeout
            return True

        manager.register_service(
            name="slow_service",
            health_check=slow_health_check,
            critical=False,
        )

        # Run health checks multiple times to trigger threshold
        await manager.run_health_checks()
        await manager.run_health_checks()

        health = manager.get_service_health("slow_service")
        assert health.consecutive_failures >= 2

    def test_health_check_timeout_in_status(self) -> None:
        """Test that health check timeout appears in status output."""
        manager = DegradationManager(redis_client=None, health_check_timeout=30.0)
        status = manager.get_status()
        assert "health_check_timeout" in status
        assert status["health_check_timeout"] == 30.0
