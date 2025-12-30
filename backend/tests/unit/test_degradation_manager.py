"""Unit tests for graceful degradation manager.

Tests cover:
- DegradationMode enum values
- ServiceStatus tracking
- DegradationManager state transitions
- Queue-for-later behavior during AI outages
- Redis unavailability handling
- Recovery from partial outages
- Service health monitoring integration
"""

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
        redis.add_to_queue = AsyncMock(return_value=1)
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
        redis.add_to_queue = AsyncMock(return_value=1)
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
        redis.add_to_queue = AsyncMock(return_value=1)
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
        redis.add_to_queue = AsyncMock(return_value=1)
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
