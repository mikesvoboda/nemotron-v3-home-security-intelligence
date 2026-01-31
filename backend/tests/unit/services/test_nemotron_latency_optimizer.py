"""Unit tests for Nemotron latency optimizer (NEM-4522).

Tests cover:
- Circuit breaker functionality based on latency thresholds
- Semaphore acquire timeout and load shedding
- Adaptive timeout calculation based on queue depth
- Rolling latency statistics
- Request prioritization and shedding
"""

from __future__ import annotations

import asyncio

import pytest

from backend.services.nemotron_latency_optimizer import (
    LatencyOptimizerConfig,
    LatencyStats,
    NemotronLatencyOptimizer,
    SemaphoreAcquireTimeout,
    get_nemotron_optimizer,
    reset_nemotron_optimizer,
)


@pytest.fixture
def optimizer_config() -> LatencyOptimizerConfig:
    """Create a test configuration with shorter timeouts for faster tests."""
    return LatencyOptimizerConfig(
        target_latency_seconds=5.0,
        max_acceptable_latency_seconds=15.0,
        rolling_window_size=10,
        semaphore_acquire_timeout=1.0,  # Short timeout for tests
        max_queue_depth=5,
        circuit_failure_threshold=3,
        circuit_recovery_timeout=2.0,  # Short recovery for tests
        min_adaptive_timeout=5.0,
        adaptive_timeout_queue_factor=2.0,
    )


@pytest.fixture
def optimizer(optimizer_config: LatencyOptimizerConfig) -> NemotronLatencyOptimizer:
    """Create a test optimizer instance."""
    return NemotronLatencyOptimizer(config=optimizer_config)


@pytest.fixture(autouse=True)
def reset_global_optimizer():
    """Reset global optimizer before and after each test."""
    reset_nemotron_optimizer()
    yield
    reset_nemotron_optimizer()


class TestLatencyStats:
    """Tests for LatencyStats dataclass."""

    def test_empty_stats(self):
        """Test default empty statistics."""
        stats = LatencyStats()

        assert stats.rolling_average == 0.0
        assert stats.p95_latency == 0.0
        assert stats.sample_count == 0
        assert stats.total_requests == 0
        assert stats.shed_requests == 0
        assert stats.circuit_trips == 0

    def test_rolling_average(self):
        """Test rolling average calculation."""
        stats = LatencyStats()
        stats.samples.extend([10.0, 20.0, 30.0])

        assert stats.rolling_average == 20.0
        assert stats.sample_count == 3

    def test_p95_latency(self):
        """Test p95 latency calculation."""
        stats = LatencyStats()
        # Add 20 samples from 1 to 20
        for i in range(1, 21):
            stats.samples.append(float(i))

        # p95 should be around 19 (95th percentile of 1-20)
        assert 18.0 <= stats.p95_latency <= 20.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        stats = LatencyStats()
        stats.samples.extend([5.0, 10.0, 15.0])
        stats.total_requests = 100
        stats.shed_requests = 5
        stats.circuit_trips = 2
        stats.last_latency = 15.0

        result = stats.to_dict()

        assert result["rolling_average_seconds"] == 10.0
        assert result["last_latency_seconds"] == 15.0
        assert result["sample_count"] == 3
        assert result["total_requests"] == 100
        assert result["shed_requests"] == 5
        assert result["circuit_trips"] == 2


class TestNemotronLatencyOptimizer:
    """Tests for NemotronLatencyOptimizer class."""

    def test_initialization(self, optimizer: NemotronLatencyOptimizer):
        """Test optimizer initializes with correct configuration."""
        assert optimizer.config.target_latency_seconds == 5.0
        assert optimizer.config.max_acceptable_latency_seconds == 15.0
        assert optimizer.config.max_queue_depth == 5
        assert optimizer.pending_count == 0

    def test_should_process_request_normal(self, optimizer: NemotronLatencyOptimizer):
        """Test that requests are allowed under normal conditions."""
        assert optimizer.should_process_request() is True

    def test_should_process_request_queue_full(self, optimizer: NemotronLatencyOptimizer):
        """Test that requests are rejected when queue is full."""
        # Artificially set pending count above max
        optimizer._pending_count = 10

        assert optimizer.should_process_request() is False
        assert optimizer.stats.shed_requests == 1

    def test_record_latency_normal(self, optimizer: NemotronLatencyOptimizer):
        """Test recording normal latency."""
        optimizer.record_latency(5.0)

        assert optimizer.stats.sample_count == 1
        assert optimizer.stats.total_requests == 1
        assert optimizer.stats.last_latency == 5.0
        assert optimizer._consecutive_high_latency == 0

    def test_record_latency_high(self, optimizer: NemotronLatencyOptimizer):
        """Test recording high latency increments consecutive counter."""
        # Record high latency (above max_acceptable_latency_seconds=15.0)
        optimizer.record_latency(20.0)

        assert optimizer._consecutive_high_latency == 1
        assert optimizer.stats.total_requests == 1

    def test_circuit_trips_after_threshold(self, optimizer: NemotronLatencyOptimizer):
        """Test circuit breaker trips after consecutive high-latency requests."""
        # Record enough high-latency requests to trip circuit (threshold=3)
        for _ in range(3):
            optimizer.record_latency(20.0)

        assert optimizer._consecutive_high_latency >= 3
        assert optimizer.stats.circuit_trips == 1

    def test_circuit_resets_on_good_latency(self, optimizer: NemotronLatencyOptimizer):
        """Test consecutive counter resets on good latency."""
        # Record some high latency
        optimizer.record_latency(20.0)
        optimizer.record_latency(20.0)
        assert optimizer._consecutive_high_latency == 2

        # Record good latency
        optimizer.record_latency(5.0)
        assert optimizer._consecutive_high_latency == 0

    def test_get_adaptive_timeout_no_queue(self, optimizer: NemotronLatencyOptimizer):
        """Test adaptive timeout with no queue backlog."""
        timeout = optimizer.get_adaptive_timeout(base_timeout=60.0)

        # Should return base timeout when queue is empty
        assert timeout == 60.0

    def test_get_adaptive_timeout_with_queue(self, optimizer: NemotronLatencyOptimizer):
        """Test adaptive timeout reduces with queue depth."""
        # Set pending count
        optimizer._pending_count = 3

        timeout = optimizer.get_adaptive_timeout(base_timeout=60.0)

        # Should reduce: 60 - (3 * 2.0) = 54
        assert timeout == 54.0

    def test_get_adaptive_timeout_minimum(self, optimizer: NemotronLatencyOptimizer):
        """Test adaptive timeout respects minimum."""
        # Set very high pending count
        optimizer._pending_count = 100

        timeout = optimizer.get_adaptive_timeout(base_timeout=60.0)

        # Should not go below minimum (5.0)
        assert timeout == optimizer.config.min_adaptive_timeout

    def test_get_adaptive_timeout_high_latency(self, optimizer: NemotronLatencyOptimizer):
        """Test adaptive timeout further reduces when latency is high."""
        # Record some latency to affect the average
        for _ in range(5):
            optimizer.record_latency(10.0)  # 2x target of 5.0

        timeout = optimizer.get_adaptive_timeout(base_timeout=60.0)

        # Should be reduced due to high average latency
        assert timeout < 60.0

    def test_reset_circuit(self, optimizer: NemotronLatencyOptimizer):
        """Test manual circuit reset."""
        # Trip the circuit
        for _ in range(5):
            optimizer.record_latency(20.0)

        # Reset
        optimizer.reset_circuit()

        assert optimizer._consecutive_high_latency == 0
        # Circuit should allow requests again
        assert optimizer.should_process_request() is True

    def test_get_status(self, optimizer: NemotronLatencyOptimizer):
        """Test status dictionary generation."""
        optimizer.record_latency(8.0)
        optimizer._pending_count = 2

        status = optimizer.get_status()

        assert "circuit_state" in status
        assert status["pending_requests"] == 2
        assert "latency_stats" in status
        assert "config" in status
        assert status["latency_stats"]["total_requests"] == 1


class TestAsyncSemaphoreContextManager:
    """Tests for semaphore context manager with timeout."""

    @pytest.mark.asyncio
    async def test_acquire_success(self, optimizer: NemotronLatencyOptimizer):
        """Test successful semaphore acquisition."""
        semaphore = asyncio.Semaphore(1)

        async with await optimizer.acquire_with_timeout(semaphore, timeout=5.0):
            assert optimizer.pending_count == 1

        assert optimizer.pending_count == 0

    @pytest.mark.asyncio
    async def test_acquire_timeout(self, optimizer: NemotronLatencyOptimizer):
        """Test semaphore acquisition timeout."""
        semaphore = asyncio.Semaphore(1)

        # Hold the semaphore
        await semaphore.acquire()

        with pytest.raises(SemaphoreAcquireTimeout) as exc_info:
            async with await optimizer.acquire_with_timeout(semaphore, timeout=0.1):
                pass

        assert exc_info.value.timeout == 0.1
        assert optimizer.stats.shed_requests == 1

    @pytest.mark.asyncio
    async def test_acquire_releases_on_exception(self, optimizer: NemotronLatencyOptimizer):
        """Test that semaphore is released even on exception."""
        semaphore = asyncio.Semaphore(1)

        with pytest.raises(ValueError):
            async with await optimizer.acquire_with_timeout(semaphore, timeout=5.0):
                raise ValueError("Test error")

        # Pending count should be decremented
        assert optimizer.pending_count == 0

        # Semaphore should be released (can acquire again)
        assert await asyncio.wait_for(semaphore.acquire(), timeout=0.1)


class TestGlobalOptimizer:
    """Tests for global optimizer singleton."""

    def test_get_optimizer_creates_instance(self):
        """Test that get_nemotron_optimizer creates an instance."""
        optimizer = get_nemotron_optimizer()

        assert optimizer is not None
        assert isinstance(optimizer, NemotronLatencyOptimizer)

    def test_get_optimizer_returns_same_instance(self):
        """Test that get_nemotron_optimizer returns the same instance."""
        optimizer1 = get_nemotron_optimizer()
        optimizer2 = get_nemotron_optimizer()

        assert optimizer1 is optimizer2

    def test_reset_optimizer(self):
        """Test that reset_nemotron_optimizer clears the instance."""
        optimizer1 = get_nemotron_optimizer()
        reset_nemotron_optimizer()
        optimizer2 = get_nemotron_optimizer()

        assert optimizer1 is not optimizer2


class TestSemaphoreAcquireTimeout:
    """Tests for SemaphoreAcquireTimeout exception."""

    def test_exception_message(self):
        """Test exception message formatting."""
        exc = SemaphoreAcquireTimeout(timeout=30.0, queue_depth=10)

        assert "30.0s" in str(exc)
        assert "queue depth: 10" in str(exc)
        assert exc.timeout == 30.0
        assert exc.queue_depth == 10


class TestOptimizerIntegration:
    """Integration tests for optimizer with realistic scenarios."""

    @pytest.mark.asyncio
    async def test_load_shedding_under_pressure(self, optimizer: NemotronLatencyOptimizer):
        """Test that load shedding works when system is under pressure."""
        semaphore = asyncio.Semaphore(1)

        # Start a long-running task that holds the semaphore
        async def long_task():
            async with await optimizer.acquire_with_timeout(semaphore, timeout=10.0):
                await asyncio.sleep(5.0)  # cancelled - task.cancel() called below

        # Start the long task
        task = asyncio.create_task(long_task())
        await asyncio.sleep(0.1)  # Let it acquire

        # Try to acquire with short timeout - should fail
        shed_count = 0
        for _ in range(3):
            try:
                async with await optimizer.acquire_with_timeout(semaphore, timeout=0.05):
                    pass
            except SemaphoreAcquireTimeout:
                shed_count += 1

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert shed_count == 3
        assert optimizer.stats.shed_requests == 3

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, optimizer: NemotronLatencyOptimizer):
        """Test concurrent requests with semaphore limiting."""
        semaphore = asyncio.Semaphore(2)  # Allow 2 concurrent
        completed = []

        async def quick_task(task_id: int):
            async with await optimizer.acquire_with_timeout(semaphore, timeout=5.0):
                await asyncio.sleep(0.01)
                completed.append(task_id)

        # Start 5 tasks with semaphore limited to 2
        tasks = [asyncio.create_task(quick_task(i)) for i in range(5)]
        await asyncio.gather(*tasks)

        assert len(completed) == 5
        assert optimizer.stats.shed_requests == 0

    def test_latency_recording_affects_adaptive_timeout(self, optimizer: NemotronLatencyOptimizer):
        """Test that recorded latency affects adaptive timeout."""
        base_timeout = 60.0

        # Get initial timeout
        initial_timeout = optimizer.get_adaptive_timeout(base_timeout)

        # Record high latency
        for _ in range(10):
            optimizer.record_latency(15.0)  # 3x target

        # Get new timeout
        new_timeout = optimizer.get_adaptive_timeout(base_timeout)

        # Should be reduced
        assert new_timeout < initial_timeout
