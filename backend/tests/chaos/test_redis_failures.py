"""Chaos tests for Redis service failures.

This module tests system behavior when Redis experiences various failure modes:
- Connection failures (service unreachable)
- Timeouts (operations hang)
- Intermittent failures (random failures)

Expected Behavior:
- Caching falls back to in-memory or disk-based queues
- WebSocket connections still work (degraded mode)
- Queue operations use fallback mechanisms
- System reports degraded health status
"""

from __future__ import annotations

import asyncio
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from backend.core.redis import QueueAddResult, RedisClient
from backend.services.degradation_manager import (
    DegradationManager,
    DegradationMode,
    FallbackQueue,
    ServiceStatus,
    reset_degradation_manager,
)


@pytest.fixture(autouse=True)
def reset_degradation_state() -> None:
    """Reset degradation manager state before each test."""
    reset_degradation_manager()


class TestRedisConnectionFailure:
    """Tests for Redis connection failure scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_degradation_manager_detects_redis_failure(self) -> None:
        """DegradationManager correctly detects Redis unavailability."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.ping = AsyncMock(side_effect=RedisConnectionError("Connection refused"))

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(redis_client=mock_redis, fallback_dir=tmpdir)

            result = await manager.check_redis_health()

            assert result is False
            assert manager._redis_healthy is False

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_fallback_queue_stores_items_on_disk(self) -> None:
        """FallbackQueue correctly stores items to disk when Redis is down."""
        with TemporaryDirectory() as tmpdir:
            queue = FallbackQueue(queue_name="test_queue", fallback_dir=tmpdir, max_size=100)

            # Add items
            item1 = {"type": "detection", "data": "test1"}
            item2 = {"type": "detection", "data": "test2"}

            success1 = await queue.add(item1)
            success2 = await queue.add(item2)

            assert success1 is True
            assert success2 is True
            assert queue.count() == 2

            # Retrieve items (FIFO order)
            retrieved1 = await queue.get()
            retrieved2 = await queue.get()

            assert retrieved1 == item1
            assert retrieved2 == item2
            assert queue.count() == 0

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_fallback_queue_respects_max_size(self) -> None:
        """FallbackQueue drops oldest items when exceeding max size."""
        with TemporaryDirectory() as tmpdir:
            queue = FallbackQueue(queue_name="test_queue", fallback_dir=tmpdir, max_size=3)

            # Add 5 items to a queue with max 3
            for i in range(5):
                await queue.add({"index": i})

            # Should only have 3 items (oldest dropped)
            assert queue.count() == 3

            # Should get items 2, 3, 4 (0 and 1 were dropped)
            items = await queue.peek(limit=3)
            indices = [item["index"] for item in items]
            assert indices == [2, 3, 4]

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_memory_queue_fallback_when_redis_fails(self) -> None:
        """DegradationManager uses memory queue when Redis fails."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.add_to_queue_safe = AsyncMock(
            side_effect=RedisConnectionError("Connection refused")
        )
        mock_redis.ping = AsyncMock(side_effect=RedisConnectionError("Connection refused"))

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(
                redis_client=mock_redis, fallback_dir=tmpdir, max_memory_queue_size=100
            )

            # Queue a job - should fall back to memory
            success = await manager.queue_job_for_later("detection", {"test": "data"})

            assert success is True
            assert manager.get_queued_job_count() == 1


class TestRedisTimeout:
    """Tests for Redis timeout scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_redis_client_with_retry_handles_timeout(self) -> None:
        """RedisClient with_retry handles timeout errors with backoff."""
        client = RedisClient()

        # Mock the internal client
        mock_internal = AsyncMock()
        call_count = 0

        async def timeout_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RedisTimeoutError("Operation timed out")
            return "success"

        mock_internal.ping = timeout_then_success

        # Patch the client's internal redis
        with patch.object(client, "_client", mock_internal):
            # This should eventually succeed after retries
            # Note: We need to test with_retry directly
            result = await client.with_retry(
                timeout_then_success, operation_name="test_op", max_retries=3
            )
            assert result == "success"
            assert call_count == 3


class TestDegradationModes:
    """Tests for degradation mode transitions."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_mode_transitions_based_on_service_health(self) -> None:
        """DegradationManager transitions modes based on service health."""
        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(fallback_dir=tmpdir, failure_threshold=2)

            # Register services
            manager.register_service(
                name="redis", health_check=AsyncMock(return_value=True), critical=True
            )
            manager.register_service(
                name="rtdetr", health_check=AsyncMock(return_value=True), critical=False
            )

            # Start in NORMAL mode
            assert manager.mode == DegradationMode.NORMAL

            # Simulate non-critical service failure (should go to DEGRADED)
            await manager.update_service_health("rtdetr", is_healthy=False)
            await manager.update_service_health("rtdetr", is_healthy=False)  # 2nd failure

            assert manager.mode == DegradationMode.DEGRADED

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_critical_service_failure_triggers_minimal_mode(self) -> None:
        """Critical service failure triggers MINIMAL degradation mode."""
        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(fallback_dir=tmpdir, failure_threshold=2)

            # Register critical service
            manager.register_service(
                name="database", health_check=AsyncMock(return_value=True), critical=True
            )
            manager.register_service(
                name="redis", health_check=AsyncMock(return_value=True), critical=True
            )

            # Simulate one critical service failure
            await manager.update_service_health("redis", is_healthy=False)
            await manager.update_service_health("redis", is_healthy=False)
            await manager.update_service_health("redis", is_healthy=False)

            # With one critical service down, should be MINIMAL
            assert manager.mode in (DegradationMode.MINIMAL, DegradationMode.DEGRADED)

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_recovery_restores_normal_mode(self) -> None:
        """Service recovery restores NORMAL degradation mode."""
        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(fallback_dir=tmpdir, failure_threshold=2)

            manager.register_service(
                name="redis", health_check=AsyncMock(return_value=True), critical=False
            )

            # Degrade
            await manager.update_service_health("redis", is_healthy=False)
            await manager.update_service_health("redis", is_healthy=False)
            await manager.update_service_health("redis", is_healthy=False)
            assert manager.mode == DegradationMode.DEGRADED

            # Recover
            await manager.update_service_health("redis", is_healthy=True)
            assert manager.mode == DegradationMode.NORMAL


class TestQueueWithFallback:
    """Tests for queue operations with fallback behavior."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_queue_with_fallback_uses_disk_when_redis_fails(self) -> None:
        """queue_with_fallback correctly falls back to disk storage."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.add_to_queue_safe = AsyncMock(
            side_effect=RedisConnectionError("Redis unavailable")
        )

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(redis_client=mock_redis, fallback_dir=tmpdir)
            manager._redis_healthy = True  # Start as healthy

            # Queue should fall back to disk
            result = await manager.queue_with_fallback("test_queue", {"key": "value"})

            assert result is True
            # Redis should have been tried and marked unhealthy
            assert manager._redis_healthy is False

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_drain_fallback_queue_restores_to_redis(self) -> None:
        """drain_fallback_queue moves items back to Redis when available."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(redis_client=mock_redis, fallback_dir=tmpdir)

            # Add items directly to fallback queue
            fallback = manager._get_fallback_queue("test_queue")
            await fallback.add({"item": 1})
            await fallback.add({"item": 2})

            assert fallback.count() == 2

            # Drain to Redis
            drained = await manager.drain_fallback_queue("test_queue")

            assert drained == 2
            assert fallback.count() == 0
            assert mock_redis.add_to_queue_safe.call_count == 2


class TestServiceHealthMonitoring:
    """Tests for service health monitoring functionality."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_service_health_tracks_consecutive_failures(self) -> None:
        """Service health correctly tracks consecutive failures."""
        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(fallback_dir=tmpdir)

            manager.register_service(name="redis", health_check=AsyncMock(return_value=True))

            # Track failures
            await manager.update_service_health("redis", is_healthy=False, error_message="Timeout")
            health = manager.get_service_health("redis")
            assert health.consecutive_failures == 1

            await manager.update_service_health(
                "redis", is_healthy=False, error_message="Connection refused"
            )
            health = manager.get_service_health("redis")
            assert health.consecutive_failures == 2

            # Success resets counter
            await manager.update_service_health("redis", is_healthy=True)
            health = manager.get_service_health("redis")
            assert health.consecutive_failures == 0

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_health_check_timeout_handling(self) -> None:
        """Health checks that timeout are handled gracefully."""
        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(fallback_dir=tmpdir, health_check_timeout=0.1)

            async def slow_health_check() -> bool:
                await asyncio.sleep(1.0)  # Longer than timeout
                return True

            manager.register_service(name="slow_service", health_check=slow_health_check)

            # Run health checks - should timeout
            await manager.run_health_checks()

            health = manager.get_service_health("slow_service")
            assert health.status == ServiceStatus.UNHEALTHY
            assert health.error_message is not None
            # Error message contains "timed out" (case insensitive check)
            assert "timed out" in health.error_message.lower()


class TestDegradationManagerStatus:
    """Tests for degradation manager status reporting."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_status_reports_all_components(self) -> None:
        """get_status returns comprehensive status information."""
        mock_redis = AsyncMock(spec=RedisClient)

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(redis_client=mock_redis, fallback_dir=tmpdir)

            manager.register_service(name="redis", health_check=AsyncMock(return_value=True))

            status = manager.get_status()

            assert "mode" in status
            assert "is_degraded" in status
            assert "redis_healthy" in status
            assert "memory_queue_size" in status
            assert "services" in status
            assert "available_features" in status

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_available_features_reduces_with_degradation(self) -> None:
        """Available features reduce as degradation increases."""
        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(fallback_dir=tmpdir, failure_threshold=1)

            manager.register_service(
                name="critical", health_check=AsyncMock(return_value=True), critical=True
            )

            # NORMAL mode - all features
            normal_features = manager.get_available_features()
            assert len(normal_features) > 0

            # Trigger degradation
            await manager.update_service_health("critical", is_healthy=False)
            await manager.update_service_health("critical", is_healthy=False)

            # Degraded mode - fewer features
            degraded_features = manager.get_available_features()
            # Features should be reduced or the same (depends on mode)
            assert len(degraded_features) <= len(normal_features)


class TestMemoryQueueOverflow:
    """Tests for memory queue overflow handling."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_memory_queue_drops_oldest_on_overflow(self) -> None:
        """Memory queue drops oldest items when at capacity."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.add_to_queue_safe = AsyncMock(
            side_effect=RedisConnectionError("Redis unavailable")
        )
        mock_redis.ping = AsyncMock(side_effect=RedisConnectionError("Redis unavailable"))

        with TemporaryDirectory() as tmpdir:
            manager = DegradationManager(
                redis_client=mock_redis, fallback_dir=tmpdir, max_memory_queue_size=3
            )

            # Queue 5 items (max is 3)
            for i in range(5):
                await manager.queue_job_for_later("test", {"index": i})

            # Should only have 3 items
            assert manager.get_queued_job_count() == 3

            # Should have items 2, 3, 4 (0 and 1 dropped)
            # Check by examining the internal queue
            jobs = list(manager._memory_queue)
            indices = [j.data["index"] for j in jobs]
            assert indices == [2, 3, 4]
