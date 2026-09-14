"""Unit tests for inference semaphore concurrency control.

Tests cover:
- get_inference_semaphore() singleton behavior and initialization
- reset_inference_semaphore() cleanup for testing
- Semaphore acquisition and release
- Context manager behavior
- Concurrency control and max concurrent enforcement
- Queue ordering (FIFO)
- Resource management (exception handling, cleanup)
- Memory pressure throttling (reduce_permits_for_memory_pressure)
- Memory pressure recovery (restore_permits_after_pressure)
- Metrics tracking (queue depth, wait time, acquisition count)
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from backend.services.inference_semaphore import (
    get_inference_semaphore,
    reduce_permits_for_memory_pressure,
    reset_inference_semaphore,
    restore_permits_after_pressure,
)

# =============================================================================
# Test Configuration and Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_semaphore():
    """Reset the global semaphore before and after each test."""
    reset_inference_semaphore()
    yield
    reset_inference_semaphore()


@pytest.fixture
def mock_settings():
    """Mock settings with default concurrent inference limit."""
    with patch("backend.services.inference_semaphore.get_settings") as mock:
        settings = MagicMock()
        settings.ai_max_concurrent_inferences = 4
        mock.return_value = settings
        yield mock


# =============================================================================
# Singleton and Initialization Tests
# =============================================================================


class TestInferenceSemaphoreInit:
    """Tests for semaphore singleton initialization."""

    def test_get_semaphore_creates_singleton(self, mock_settings) -> None:
        """Test that get_inference_semaphore creates a singleton instance."""
        semaphore1 = get_inference_semaphore()
        semaphore2 = get_inference_semaphore()

        assert semaphore1 is semaphore2
        assert isinstance(semaphore1, asyncio.Semaphore)

    def test_semaphore_initialized_with_config_value(self, mock_settings) -> None:
        """Test that semaphore is initialized with configured max concurrent value."""
        mock_settings.return_value.ai_max_concurrent_inferences = 8

        semaphore = get_inference_semaphore()

        # Check internal value (available permits)
        assert semaphore._value == 8

    def test_reset_clears_singleton(self, mock_settings) -> None:
        """Test that reset_inference_semaphore clears the singleton."""
        semaphore1 = get_inference_semaphore()

        reset_inference_semaphore()

        semaphore2 = get_inference_semaphore()

        # Should be different instances after reset
        assert semaphore1 is not semaphore2


# =============================================================================
# Semaphore Acquisition and Release Tests
# =============================================================================


class TestSemaphoreAcquisition:
    """Tests for semaphore acquisition and release behavior."""

    @pytest.mark.asyncio
    async def test_acquire_semaphore_successfully(self, mock_settings) -> None:
        """Test that semaphore can be acquired successfully."""
        mock_settings.return_value.ai_max_concurrent_inferences = 2
        semaphore = get_inference_semaphore()

        # Acquire semaphore
        await semaphore.acquire()

        # Should have reduced available permits
        assert semaphore._value == 1

    @pytest.mark.asyncio
    async def test_release_semaphore_correctly(self, mock_settings) -> None:
        """Test that semaphore is released correctly."""
        mock_settings.return_value.ai_max_concurrent_inferences = 2
        semaphore = get_inference_semaphore()

        await semaphore.acquire()
        initial_value = semaphore._value

        semaphore.release()

        # Should have restored permits
        assert semaphore._value == initial_value + 1

    @pytest.mark.asyncio
    async def test_context_manager_acquires_and_releases(self, mock_settings) -> None:
        """Test that context manager properly acquires and releases semaphore."""
        mock_settings.return_value.ai_max_concurrent_inferences = 2
        semaphore = get_inference_semaphore()

        initial_value = semaphore._value

        async with semaphore:
            # Should be acquired inside context
            assert semaphore._value == initial_value - 1

        # Should be released after context
        assert semaphore._value == initial_value

    @pytest.mark.asyncio
    async def test_semaphore_released_on_exception(self, mock_settings) -> None:
        """Test that semaphore is released even when exception occurs."""
        mock_settings.return_value.ai_max_concurrent_inferences = 2
        semaphore = get_inference_semaphore()

        initial_value = semaphore._value

        with pytest.raises(ValueError):
            async with semaphore:
                raise ValueError("Test exception")

        # Should still be released after exception
        assert semaphore._value == initial_value


# =============================================================================
# Concurrency Control Tests
# =============================================================================


class TestConcurrencyControl:
    """Tests for concurrency enforcement and queue behavior."""

    @pytest.mark.asyncio
    async def test_max_concurrent_requests_enforced(self, mock_settings) -> None:
        """Test that max concurrent requests limit is enforced."""
        mock_settings.return_value.ai_max_concurrent_inferences = 2
        semaphore = get_inference_semaphore()

        # Track concurrent operations
        concurrent_count = 0
        max_concurrent = 0

        async def worker(delay: float) -> None:
            nonlocal concurrent_count, max_concurrent
            async with semaphore:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(delay)
                concurrent_count -= 1

        # Launch 5 workers, but only 2 should run concurrently
        await asyncio.gather(*[worker(0.05) for _ in range(5)])

        assert max_concurrent == 2

    @pytest.mark.asyncio
    async def test_blocks_when_semaphore_exhausted(self, mock_settings) -> None:
        """Test that acquisition blocks when semaphore is exhausted."""
        mock_settings.return_value.ai_max_concurrent_inferences = 1
        semaphore = get_inference_semaphore()

        # Acquire the only permit
        await semaphore.acquire()

        # Try to acquire again with timeout - should timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(semaphore.acquire(), timeout=0.1)

        # Release and verify it can be acquired again
        semaphore.release()
        await asyncio.wait_for(semaphore.acquire(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_queue_ordering_fifo(self, mock_settings) -> None:
        """Test that queued requests are processed in FIFO order."""
        mock_settings.return_value.ai_max_concurrent_inferences = 1
        semaphore = get_inference_semaphore()

        order: list[int] = []

        async def worker(worker_id: int, delay: float) -> None:
            async with semaphore:
                order.append(worker_id)
                await asyncio.sleep(delay)

        # Start first worker (holds semaphore)
        task1 = asyncio.create_task(worker(1, 0.1))

        # Wait for first worker to acquire
        await asyncio.sleep(0.01)

        # Queue remaining workers
        tasks = [
            asyncio.create_task(worker(2, 0.01)),
            asyncio.create_task(worker(3, 0.01)),
            asyncio.create_task(worker(4, 0.01)),
        ]

        await asyncio.gather(task1, *tasks)

        # Should be processed in order
        assert order == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_graceful_degradation_under_load(self, mock_settings) -> None:
        """Test that system degrades gracefully under high load."""
        mock_settings.return_value.ai_max_concurrent_inferences = 2
        semaphore = get_inference_semaphore()

        completed = 0

        async def worker() -> None:
            nonlocal completed
            async with semaphore:
                await asyncio.sleep(0.01)
                completed += 1

        # Launch many workers
        await asyncio.gather(*[worker() for _ in range(20)])

        # All should complete successfully
        assert completed == 20


# =============================================================================
# Resource Management Tests
# =============================================================================


class TestResourceManagement:
    """Tests for resource cleanup and error handling."""

    @pytest.mark.asyncio
    async def test_no_deadlock_on_error(self, mock_settings) -> None:
        """Test that exceptions don't cause deadlocks."""
        mock_settings.return_value.ai_max_concurrent_inferences = 1
        semaphore = get_inference_semaphore()

        # First operation raises exception
        with pytest.raises(RuntimeError):
            async with semaphore:
                raise RuntimeError("Test error")

        # Second operation should acquire successfully (no deadlock)
        acquired = False
        async with semaphore:
            acquired = True
            await asyncio.sleep(0.01)

        assert acquired is True

    @pytest.mark.asyncio
    async def test_cleanup_on_service_shutdown(self, mock_settings) -> None:
        """Test that resources are cleaned up on service shutdown."""
        mock_settings.return_value.ai_max_concurrent_inferences = 2
        semaphore = get_inference_semaphore()

        # Acquire some permits
        await semaphore.acquire()
        await semaphore.acquire()

        # Simulate shutdown by resetting
        reset_inference_semaphore()

        # New semaphore should start fresh
        new_semaphore = get_inference_semaphore()
        assert new_semaphore._value == 2


# =============================================================================
# Memory Pressure Throttling Tests
# =============================================================================


class TestMemoryPressureThrottling:
    """Tests for memory pressure-based permit reduction."""

    @pytest.mark.asyncio
    async def test_reduce_permits_for_warning_pressure(self, mock_settings) -> None:
        """Test that permits are reduced to 75% for WARNING pressure."""
        from backend.services.gpu_monitor import MemoryPressureLevel

        mock_settings.return_value.ai_max_concurrent_inferences = 4
        semaphore = get_inference_semaphore()

        await reduce_permits_for_memory_pressure(MemoryPressureLevel.WARNING)

        # Should reduce to 75% = 3 permits (4 * 0.75 = 3)
        # 1 permit acquired internally, so 3 available
        assert semaphore._value == 3

    @pytest.mark.asyncio
    async def test_reduce_permits_for_critical_pressure(self, mock_settings) -> None:
        """Test that permits are reduced to 50% for CRITICAL pressure."""
        from backend.services.gpu_monitor import MemoryPressureLevel

        mock_settings.return_value.ai_max_concurrent_inferences = 4
        semaphore = get_inference_semaphore()

        await reduce_permits_for_memory_pressure(MemoryPressureLevel.CRITICAL)

        # Should reduce to 50% = 2 permits (4 // 2 = 2)
        # 2 permits acquired internally, so 2 available
        assert semaphore._value == 2

    @pytest.mark.asyncio
    async def test_no_change_for_normal_pressure(self, mock_settings) -> None:
        """Test that NORMAL pressure doesn't change permits."""
        from backend.services.gpu_monitor import MemoryPressureLevel

        mock_settings.return_value.ai_max_concurrent_inferences = 4
        semaphore = get_inference_semaphore()

        initial_value = semaphore._value

        await reduce_permits_for_memory_pressure(MemoryPressureLevel.NORMAL)

        # Should remain unchanged
        assert semaphore._value == initial_value

    @pytest.mark.asyncio
    async def test_restore_permits_after_pressure(self, mock_settings) -> None:
        """Test that permits are restored after pressure relief."""
        from backend.services.gpu_monitor import MemoryPressureLevel

        mock_settings.return_value.ai_max_concurrent_inferences = 4
        semaphore = get_inference_semaphore()

        # Reduce permits
        await reduce_permits_for_memory_pressure(MemoryPressureLevel.CRITICAL)
        reduced_value = semaphore._value

        # Restore permits
        await restore_permits_after_pressure()

        # Should be back to original
        assert semaphore._value == 4
        assert semaphore._value > reduced_value

    @pytest.mark.asyncio
    async def test_minimum_one_permit_enforced(self, mock_settings) -> None:
        """Test that at least 1 permit is always available."""
        from backend.services.gpu_monitor import MemoryPressureLevel

        mock_settings.return_value.ai_max_concurrent_inferences = 1
        semaphore = get_inference_semaphore()

        await reduce_permits_for_memory_pressure(MemoryPressureLevel.CRITICAL)

        # Should still have 1 permit (minimum)
        assert semaphore._value >= 1

    @pytest.mark.asyncio
    async def test_restore_permits_when_not_throttled(self, mock_settings) -> None:
        """Test that restore does nothing when not throttled."""
        mock_settings.return_value.ai_max_concurrent_inferences = 4
        semaphore = get_inference_semaphore()

        initial_value = semaphore._value

        # Restore without previous reduction
        await restore_permits_after_pressure()

        # Should remain unchanged
        assert semaphore._value == initial_value

    @pytest.mark.asyncio
    async def test_reduce_permits_handles_exhausted_semaphore(self, mock_settings) -> None:
        """Test reduction handles case where semaphore is fully utilized."""
        from backend.services.gpu_monitor import MemoryPressureLevel

        mock_settings.return_value.ai_max_concurrent_inferences = 2
        semaphore = get_inference_semaphore()

        # Acquire all permits
        await semaphore.acquire()
        await semaphore.acquire()

        # Try to reduce (should handle gracefully)
        await reduce_permits_for_memory_pressure(MemoryPressureLevel.CRITICAL)

        # Should not raise exception and semaphore should be valid
        assert semaphore._value == 0  # All permits acquired


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and complex scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_pressure_changes(self, mock_settings) -> None:
        """Test that concurrent pressure changes are handled safely."""
        from backend.services.gpu_monitor import MemoryPressureLevel

        mock_settings.return_value.ai_max_concurrent_inferences = 8
        get_inference_semaphore()

        # Apply multiple pressure changes concurrently
        await asyncio.gather(
            reduce_permits_for_memory_pressure(MemoryPressureLevel.WARNING),
            reduce_permits_for_memory_pressure(MemoryPressureLevel.WARNING),
        )

        # Should not raise exceptions (test passes if no exception)

    @pytest.mark.asyncio
    async def test_pressure_reduction_during_active_inference(self, mock_settings) -> None:
        """Test that pressure reduction works during active inference operations."""
        from backend.services.gpu_monitor import MemoryPressureLevel

        mock_settings.return_value.ai_max_concurrent_inferences = 4
        semaphore = get_inference_semaphore()

        inference_started = asyncio.Event()

        async def long_inference() -> None:
            async with semaphore:
                inference_started.set()
                await asyncio.sleep(0.2)

        # Start inference
        task = asyncio.create_task(long_inference())

        # Wait for inference to start
        await inference_started.wait()

        # Reduce permits during inference
        await reduce_permits_for_memory_pressure(MemoryPressureLevel.WARNING)

        # Should complete without errors
        await task

    @pytest.mark.asyncio
    async def test_reduce_permits_without_initialization(self) -> None:
        """Test that reduce_permits handles uninitialized semaphore gracefully."""
        from backend.services.gpu_monitor import MemoryPressureLevel

        # Don't call get_inference_semaphore(), so semaphore is not initialized
        # This should be handled gracefully by calling get_inference_semaphore inside
        await reduce_permits_for_memory_pressure(MemoryPressureLevel.WARNING)

        # Should not raise exception (test passes if no exception)

    @pytest.mark.asyncio
    async def test_restore_permits_without_initialization(self) -> None:
        """Test that restore_permits handles uninitialized state gracefully."""
        # Don't call get_inference_semaphore(), so semaphore is not initialized
        # This should be handled gracefully
        await restore_permits_after_pressure()

        # Should not raise exception (test passes if no exception)

    @pytest.mark.asyncio
    async def test_restore_with_no_permits_to_restore(self, mock_settings) -> None:
        """Test that restore handles case where no permits need restoring."""
        from backend.services.gpu_monitor import MemoryPressureLevel

        mock_settings.return_value.ai_max_concurrent_inferences = 4
        semaphore = get_inference_semaphore()

        # Reduce permits
        await reduce_permits_for_memory_pressure(MemoryPressureLevel.WARNING)

        # Restore once
        await restore_permits_after_pressure()

        initial_value = semaphore._value

        # Try to restore again (should be no-op)
        await restore_permits_after_pressure()

        # Should remain unchanged
        assert semaphore._value == initial_value
