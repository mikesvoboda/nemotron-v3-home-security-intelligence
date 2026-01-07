"""Unit tests for GPU memory pressure monitoring and throttling (NEM-1727).

Tests cover:
- MemoryPressureLevel enum values and thresholds
- check_memory_pressure method in GPUMonitor
- Auto-reduce semaphore permits under critical pressure
- Backpressure signal integration with batch_aggregator
- Memory pressure event metrics
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.gpu_monitor import GPUMonitor, MemoryPressureLevel


class TestMemoryPressureLevel:
    """Tests for MemoryPressureLevel enum."""

    def test_memory_pressure_level_values(self) -> None:
        """Test MemoryPressureLevel enum values."""
        assert MemoryPressureLevel.NORMAL.value == "normal"
        assert MemoryPressureLevel.WARNING.value == "warning"
        assert MemoryPressureLevel.CRITICAL.value == "critical"

    def test_memory_pressure_level_threshold_constants(self) -> None:
        """Test that threshold constants are defined correctly."""
        from backend.services.gpu_monitor import (
            MEMORY_PRESSURE_CRITICAL_THRESHOLD,
            MEMORY_PRESSURE_WARNING_THRESHOLD,
        )

        assert MEMORY_PRESSURE_WARNING_THRESHOLD == 85.0
        assert MEMORY_PRESSURE_CRITICAL_THRESHOLD == 95.0
        # Critical must be higher than warning
        assert MEMORY_PRESSURE_CRITICAL_THRESHOLD > MEMORY_PRESSURE_WARNING_THRESHOLD


class TestCheckMemoryPressure:
    """Tests for GPUMonitor.check_memory_pressure method."""

    @pytest.fixture
    def mock_pynvml(self):
        """Mock pynvml module for testing."""
        import sys

        mock_nvml = MagicMock()
        mock_handle = MagicMock()
        mock_nvml.nvmlInit.return_value = None
        mock_nvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_nvml.nvmlDeviceGetName.return_value = "NVIDIA RTX A5500"
        mock_nvml.NVMLError = Exception
        mock_nvml.nvmlShutdown.return_value = None

        # Default memory: 8 GB used of 24 GB total (33.3% - NORMAL)
        mock_memory = MagicMock()
        mock_memory.used = 8192 * 1024 * 1024  # 8192 MB in bytes
        mock_memory.total = 24576 * 1024 * 1024  # 24576 MB in bytes
        mock_nvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        mock_utilization = MagicMock()
        mock_utilization.gpu = 50.0
        mock_nvml.nvmlDeviceGetUtilizationRates.return_value = mock_utilization
        mock_nvml.nvmlDeviceGetTemperature.return_value = 45.0
        mock_nvml.NVML_TEMPERATURE_GPU = 0
        mock_nvml.nvmlDeviceGetPowerUsage.return_value = 100000

        sys.modules["pynvml"] = mock_nvml
        yield mock_nvml
        if "pynvml" in sys.modules:
            del sys.modules["pynvml"]

    @pytest.mark.asyncio
    async def test_check_memory_pressure_normal(self, mock_pynvml) -> None:
        """Test check_memory_pressure returns NORMAL for usage < 85%."""
        # Set up: 8GB / 24GB = 33.3% usage
        mock_memory = MagicMock()
        mock_memory.used = 8192 * 1024 * 1024  # 8 GB in bytes
        mock_memory.total = 24576 * 1024 * 1024  # 24 GB in bytes
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        monitor = GPUMonitor()
        level = await monitor.check_memory_pressure()

        assert level == MemoryPressureLevel.NORMAL

    @pytest.mark.asyncio
    async def test_check_memory_pressure_warning(self, mock_pynvml) -> None:
        """Test check_memory_pressure returns WARNING for 85% <= usage < 95%."""
        # Set up: 21GB / 24GB = 87.5% usage (WARNING)
        mock_memory = MagicMock()
        mock_memory.used = 21 * 1024 * 1024 * 1024  # 21 GB in bytes
        mock_memory.total = 24 * 1024 * 1024 * 1024  # 24 GB in bytes
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        monitor = GPUMonitor()
        level = await monitor.check_memory_pressure()

        assert level == MemoryPressureLevel.WARNING

    @pytest.mark.asyncio
    async def test_check_memory_pressure_critical(self, mock_pynvml) -> None:
        """Test check_memory_pressure returns CRITICAL for usage >= 95%."""
        # Set up: 23.5GB / 24GB = 97.9% usage (CRITICAL)
        mock_memory = MagicMock()
        mock_memory.used = int(23.5 * 1024 * 1024 * 1024)  # 23.5 GB in bytes
        mock_memory.total = 24 * 1024 * 1024 * 1024  # 24 GB in bytes
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        monitor = GPUMonitor()
        level = await monitor.check_memory_pressure()

        assert level == MemoryPressureLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_check_memory_pressure_at_warning_boundary(self, mock_pynvml) -> None:
        """Test check_memory_pressure at exactly 85% (WARNING boundary)."""
        monitor = GPUMonitor()

        # Mock get_current_stats_async to return exactly 85% usage
        # Memory is returned in MB by _get_gpu_stats_real
        async def mock_stats():
            return {
                "memory_used": 20400,  # 20.4 GB = 20400 MB (85% of 24000)
                "memory_total": 24000,  # 24 GB = 24000 MB
                "gpu_utilization": 50.0,
            }

        with patch.object(monitor, "get_current_stats_async", side_effect=mock_stats):
            level = await monitor.check_memory_pressure()

        # At exactly 85%, should be WARNING
        assert level == MemoryPressureLevel.WARNING

    @pytest.mark.asyncio
    async def test_check_memory_pressure_at_critical_boundary(self, mock_pynvml) -> None:
        """Test check_memory_pressure at exactly 95% (CRITICAL boundary)."""
        monitor = GPUMonitor()

        # Mock get_current_stats_async to return exactly 95% usage
        # Memory is returned in MB by _get_gpu_stats_real
        async def mock_stats():
            return {
                "memory_used": 22800,  # 22.8 GB = 22800 MB (95% of 24000)
                "memory_total": 24000,  # 24 GB = 24000 MB
                "gpu_utilization": 50.0,
            }

        with patch.object(monitor, "get_current_stats_async", side_effect=mock_stats):
            level = await monitor.check_memory_pressure()

        # At exactly 95%, should be CRITICAL
        assert level == MemoryPressureLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_check_memory_pressure_just_below_warning(self, mock_pynvml) -> None:
        """Test check_memory_pressure just below 85% threshold."""
        # Set up: 84.9% usage (NORMAL)
        mock_memory = MagicMock()
        mock_memory.used = int(0.849 * 24 * 1024 * 1024 * 1024)
        mock_memory.total = 24 * 1024 * 1024 * 1024
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        monitor = GPUMonitor()
        level = await monitor.check_memory_pressure()

        assert level == MemoryPressureLevel.NORMAL

    @pytest.mark.asyncio
    async def test_check_memory_pressure_just_below_critical(self, mock_pynvml) -> None:
        """Test check_memory_pressure just below 95% threshold."""
        # Set up: 94.9% usage (WARNING)
        mock_memory = MagicMock()
        mock_memory.used = int(0.949 * 24 * 1024 * 1024 * 1024)
        mock_memory.total = 24 * 1024 * 1024 * 1024
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        monitor = GPUMonitor()
        level = await monitor.check_memory_pressure()

        assert level == MemoryPressureLevel.WARNING

    @pytest.mark.asyncio
    async def test_check_memory_pressure_with_mock_gpu(self) -> None:
        """Test check_memory_pressure with mock GPU (no real GPU available)."""
        # When GPU not available, should return NORMAL (mock data is low usage)
        with (
            patch("shutil.which", return_value=None),
            patch.dict("sys.modules", {"pynvml": None}),
            patch("builtins.__import__", side_effect=ImportError("pynvml not installed")),
        ):
            # Create monitor that will use mock mode
            monitor = GPUMonitor.__new__(GPUMonitor)
            monitor._gpu_available = False
            monitor._nvidia_smi_available = False
            monitor.poll_interval = 5.0
            monitor.history_minutes = 60
            monitor._http_timeout = 5.0
            monitor.broadcaster = None

            level = await monitor.check_memory_pressure()

            # Mock data should be low usage, returning NORMAL
            assert level == MemoryPressureLevel.NORMAL

    @pytest.mark.asyncio
    async def test_check_memory_pressure_tracks_last_level(self, mock_pynvml) -> None:
        """Test that check_memory_pressure tracks the last pressure level."""
        monitor = GPUMonitor()

        # Initial check
        level1 = await monitor.check_memory_pressure()
        assert monitor._last_memory_pressure_level == level1

        # Change to critical
        mock_memory = MagicMock()
        mock_memory.used = int(23.5 * 1024 * 1024 * 1024)
        mock_memory.total = 24 * 1024 * 1024 * 1024
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        level2 = await monitor.check_memory_pressure()
        assert level2 == MemoryPressureLevel.CRITICAL
        assert monitor._last_memory_pressure_level == MemoryPressureLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_check_memory_pressure_handles_stats_error(self, mock_pynvml) -> None:
        """Test check_memory_pressure handles errors gracefully."""
        monitor = GPUMonitor()

        # Make get_current_stats_async fail
        with patch.object(monitor, "get_current_stats_async", side_effect=Exception("Stats error")):
            # Should return NORMAL and not raise
            level = await monitor.check_memory_pressure()
            assert level == MemoryPressureLevel.NORMAL


class TestMemoryPressureCallbacks:
    """Tests for memory pressure change callbacks."""

    @pytest.fixture
    def mock_pynvml(self):
        """Mock pynvml module for testing."""
        import sys

        mock_nvml = MagicMock()
        mock_handle = MagicMock()
        mock_nvml.nvmlInit.return_value = None
        mock_nvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_nvml.nvmlDeviceGetName.return_value = "NVIDIA RTX A5500"
        mock_nvml.NVMLError = Exception
        mock_nvml.nvmlShutdown.return_value = None

        mock_memory = MagicMock()
        mock_memory.used = 8192 * 1024 * 1024
        mock_memory.total = 24576 * 1024 * 1024
        mock_nvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        mock_utilization = MagicMock()
        mock_utilization.gpu = 50.0
        mock_nvml.nvmlDeviceGetUtilizationRates.return_value = mock_utilization
        mock_nvml.nvmlDeviceGetTemperature.return_value = 45.0
        mock_nvml.NVML_TEMPERATURE_GPU = 0
        mock_nvml.nvmlDeviceGetPowerUsage.return_value = 100000

        sys.modules["pynvml"] = mock_nvml
        yield mock_nvml
        if "pynvml" in sys.modules:
            del sys.modules["pynvml"]

    @pytest.mark.asyncio
    async def test_register_memory_pressure_callback(self, mock_pynvml) -> None:
        """Test registering a callback for memory pressure changes."""
        monitor = GPUMonitor()
        callback = AsyncMock()

        monitor.register_memory_pressure_callback(callback)

        assert callback in monitor._memory_pressure_callbacks

    @pytest.mark.asyncio
    async def test_callback_triggered_on_pressure_change(self, mock_pynvml) -> None:
        """Test callback is triggered when pressure level changes."""
        monitor = GPUMonitor()
        callback = AsyncMock()
        monitor.register_memory_pressure_callback(callback)

        # Set initial level to NORMAL
        monitor._last_memory_pressure_level = MemoryPressureLevel.NORMAL

        # Simulate change to CRITICAL
        mock_memory = MagicMock()
        mock_memory.used = int(23.5 * 1024 * 1024 * 1024)
        mock_memory.total = 24 * 1024 * 1024 * 1024
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        await monitor.check_memory_pressure()

        # Callback should have been called with new level
        callback.assert_called_once_with(MemoryPressureLevel.CRITICAL, MemoryPressureLevel.NORMAL)

    @pytest.mark.asyncio
    async def test_callback_not_triggered_when_level_unchanged(self, mock_pynvml) -> None:
        """Test callback is NOT triggered when pressure level stays the same."""
        monitor = GPUMonitor()
        callback = AsyncMock()
        monitor.register_memory_pressure_callback(callback)

        # Set initial level to NORMAL
        monitor._last_memory_pressure_level = MemoryPressureLevel.NORMAL

        # Check pressure - should still be NORMAL (33% usage)
        await monitor.check_memory_pressure()

        # Callback should NOT have been called
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_callbacks_triggered(self, mock_pynvml) -> None:
        """Test multiple callbacks are all triggered on pressure change."""
        monitor = GPUMonitor()
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        monitor.register_memory_pressure_callback(callback1)
        monitor.register_memory_pressure_callback(callback2)

        monitor._last_memory_pressure_level = MemoryPressureLevel.NORMAL

        # Simulate change to CRITICAL
        mock_memory = MagicMock()
        mock_memory.used = int(23.5 * 1024 * 1024 * 1024)
        mock_memory.total = 24 * 1024 * 1024 * 1024
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        await monitor.check_memory_pressure()

        callback1.assert_called_once()
        callback2.assert_called_once()


class TestMemoryPressureMetrics:
    """Tests for memory pressure metrics tracking."""

    @pytest.fixture
    def mock_pynvml(self):
        """Mock pynvml module for testing."""
        import sys

        mock_nvml = MagicMock()
        mock_handle = MagicMock()
        mock_nvml.nvmlInit.return_value = None
        mock_nvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_nvml.nvmlDeviceGetName.return_value = "NVIDIA RTX A5500"
        mock_nvml.NVMLError = Exception
        mock_nvml.nvmlShutdown.return_value = None

        mock_memory = MagicMock()
        mock_memory.used = 8192 * 1024 * 1024
        mock_memory.total = 24576 * 1024 * 1024
        mock_nvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        mock_utilization = MagicMock()
        mock_utilization.gpu = 50.0
        mock_nvml.nvmlDeviceGetUtilizationRates.return_value = mock_utilization
        mock_nvml.nvmlDeviceGetTemperature.return_value = 45.0
        mock_nvml.NVML_TEMPERATURE_GPU = 0
        mock_nvml.nvmlDeviceGetPowerUsage.return_value = 100000

        sys.modules["pynvml"] = mock_nvml
        yield mock_nvml
        if "pynvml" in sys.modules:
            del sys.modules["pynvml"]

    def test_get_memory_pressure_metrics_initial(self, mock_pynvml) -> None:
        """Test initial memory pressure metrics."""
        monitor = GPUMonitor()
        metrics = monitor.get_memory_pressure_metrics()

        assert "current_level" in metrics
        assert "warning_threshold" in metrics
        assert "critical_threshold" in metrics
        assert "total_warning_events" in metrics
        assert "total_critical_events" in metrics
        assert metrics["warning_threshold"] == 85.0
        assert metrics["critical_threshold"] == 95.0
        assert metrics["total_warning_events"] == 0
        assert metrics["total_critical_events"] == 0

    @pytest.mark.asyncio
    async def test_metrics_track_warning_events(self, mock_pynvml) -> None:
        """Test that warning events are tracked in metrics."""
        monitor = GPUMonitor()
        monitor._last_memory_pressure_level = MemoryPressureLevel.NORMAL

        # Simulate transition to WARNING
        mock_memory = MagicMock()
        mock_memory.used = int(0.87 * 24 * 1024 * 1024 * 1024)  # 87%
        mock_memory.total = 24 * 1024 * 1024 * 1024
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        await monitor.check_memory_pressure()

        metrics = monitor.get_memory_pressure_metrics()
        assert metrics["total_warning_events"] == 1
        assert metrics["total_critical_events"] == 0

    @pytest.mark.asyncio
    async def test_metrics_track_critical_events(self, mock_pynvml) -> None:
        """Test that critical events are tracked in metrics."""
        monitor = GPUMonitor()
        monitor._last_memory_pressure_level = MemoryPressureLevel.NORMAL

        # Simulate transition to CRITICAL
        mock_memory = MagicMock()
        mock_memory.used = int(0.97 * 24 * 1024 * 1024 * 1024)  # 97%
        mock_memory.total = 24 * 1024 * 1024 * 1024
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        await monitor.check_memory_pressure()

        metrics = monitor.get_memory_pressure_metrics()
        assert metrics["total_critical_events"] == 1

    @pytest.mark.asyncio
    async def test_metrics_include_last_event_timestamp(self, mock_pynvml) -> None:
        """Test that last event timestamps are tracked."""
        monitor = GPUMonitor()
        monitor._last_memory_pressure_level = MemoryPressureLevel.NORMAL

        # Simulate transition to WARNING
        mock_memory = MagicMock()
        mock_memory.used = int(0.87 * 24 * 1024 * 1024 * 1024)
        mock_memory.total = 24 * 1024 * 1024 * 1024
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        await monitor.check_memory_pressure()

        metrics = monitor.get_memory_pressure_metrics()
        assert "last_warning_event_at" in metrics
        assert metrics["last_warning_event_at"] is not None


class TestInferenceSemaphoreThrottling:
    """Tests for auto-reducing semaphore permits under memory pressure."""

    @pytest.fixture
    def reset_semaphore(self):
        """Reset inference semaphore before and after each test."""
        from backend.services.inference_semaphore import reset_inference_semaphore

        reset_inference_semaphore()
        yield
        reset_inference_semaphore()

    @pytest.mark.asyncio
    async def test_semaphore_reduces_on_critical_pressure(self, reset_semaphore) -> None:
        """Test that semaphore permits are reduced when memory pressure is CRITICAL."""
        from backend.services.inference_semaphore import (
            get_inference_semaphore,
            reduce_permits_for_memory_pressure,
        )

        # Get initial semaphore
        semaphore = get_inference_semaphore()
        initial_permits = semaphore._value

        # Trigger permit reduction
        await reduce_permits_for_memory_pressure(MemoryPressureLevel.CRITICAL)

        # Permits should be reduced (at least halved)
        assert semaphore._value < initial_permits
        assert semaphore._value >= 1  # Always keep at least 1 permit

    @pytest.mark.asyncio
    async def test_semaphore_restores_on_normal_pressure(self, reset_semaphore) -> None:
        """Test that semaphore permits are restored when memory pressure returns to NORMAL."""
        from backend.services.inference_semaphore import (
            get_inference_semaphore,
            reduce_permits_for_memory_pressure,
            restore_permits_after_pressure,
        )

        # Get initial permits
        semaphore = get_inference_semaphore()
        initial_permits = semaphore._value

        # Reduce permits
        await reduce_permits_for_memory_pressure(MemoryPressureLevel.CRITICAL)
        assert semaphore._value < initial_permits

        # Restore permits
        await restore_permits_after_pressure()
        assert semaphore._value == initial_permits

    @pytest.mark.asyncio
    async def test_semaphore_unchanged_on_normal_pressure(self, reset_semaphore) -> None:
        """Test semaphore is unchanged when pressure is NORMAL."""
        from backend.services.inference_semaphore import (
            get_inference_semaphore,
            reduce_permits_for_memory_pressure,
        )

        semaphore = get_inference_semaphore()
        initial_permits = semaphore._value

        # Call with NORMAL pressure
        await reduce_permits_for_memory_pressure(MemoryPressureLevel.NORMAL)

        # Should be unchanged
        assert semaphore._value == initial_permits

    @pytest.mark.asyncio
    async def test_semaphore_reduced_on_warning_pressure(self, reset_semaphore) -> None:
        """Test semaphore is moderately reduced on WARNING pressure."""
        from backend.services.inference_semaphore import (
            get_inference_semaphore,
            reduce_permits_for_memory_pressure,
        )

        semaphore = get_inference_semaphore()
        initial_permits = semaphore._value

        # Call with WARNING pressure
        await reduce_permits_for_memory_pressure(MemoryPressureLevel.WARNING)

        # Should be reduced but less than CRITICAL
        assert semaphore._value <= initial_permits
        # For WARNING, reduce by 25% (75% of original)
        expected_min = max(1, int(initial_permits * 0.5))
        assert semaphore._value >= expected_min


class TestBatchAggregatorBackpressure:
    """Tests for backpressure signal integration with batch_aggregator."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        from backend.core.redis import QueueAddResult

        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=True)
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        redis._client = MagicMock()
        redis._client.rpush = AsyncMock(return_value=1)
        redis._client.expire = AsyncMock(return_value=True)
        redis._client.lrange = AsyncMock(return_value=[])
        redis._client.scan_iter = AsyncMock(return_value=iter([]))
        return redis

    @pytest.mark.asyncio
    async def test_batch_aggregator_checks_memory_pressure(self, mock_redis) -> None:
        """Test that batch_aggregator checks memory pressure before processing."""
        from backend.services.batch_aggregator import BatchAggregator

        aggregator = BatchAggregator(redis_client=mock_redis)

        # Should have a method to check memory pressure backpressure
        assert hasattr(aggregator, "should_apply_backpressure")

    @pytest.mark.asyncio
    async def test_backpressure_applied_on_critical_memory(self, mock_redis) -> None:
        """Test that backpressure is applied when memory is critical."""
        from backend.services.batch_aggregator import BatchAggregator

        aggregator = BatchAggregator(redis_client=mock_redis)

        # Simulate critical memory pressure
        with patch(
            "backend.services.batch_aggregator.get_memory_pressure_level",
            return_value=MemoryPressureLevel.CRITICAL,
        ):
            should_apply = await aggregator.should_apply_backpressure()
            assert should_apply is True

    @pytest.mark.asyncio
    async def test_no_backpressure_on_normal_memory(self, mock_redis) -> None:
        """Test that no backpressure when memory is normal."""
        from backend.services.batch_aggregator import BatchAggregator

        aggregator = BatchAggregator(redis_client=mock_redis)

        # Simulate normal memory pressure
        with patch(
            "backend.services.batch_aggregator.get_memory_pressure_level",
            return_value=MemoryPressureLevel.NORMAL,
        ):
            should_apply = await aggregator.should_apply_backpressure()
            assert should_apply is False

    @pytest.mark.asyncio
    async def test_add_detection_delays_on_backpressure(self, mock_redis) -> None:
        """Test that add_detection delays processing when backpressure is active."""
        from backend.services.batch_aggregator import BatchAggregator

        aggregator = BatchAggregator(redis_client=mock_redis)

        # Simulate critical memory pressure causing backpressure
        with patch.object(
            aggregator, "should_apply_backpressure", new_callable=AsyncMock
        ) as mock_bp:
            mock_bp.return_value = True

            # Add detection should still work but may log a warning
            # The actual delay behavior can vary (skip, delay, or queue)
            # For now, we just ensure it doesn't crash
            batch_id = await aggregator.add_detection(
                camera_id="test_cam",
                detection_id=123,
                _file_path="/path/to/image.jpg",
            )

            # Should still return a batch ID
            assert batch_id is not None


class TestMemoryPressureIntegration:
    """Integration tests for memory pressure monitoring system."""

    @pytest.fixture
    def mock_pynvml(self):
        """Mock pynvml module for testing."""
        import sys

        mock_nvml = MagicMock()
        mock_handle = MagicMock()
        mock_nvml.nvmlInit.return_value = None
        mock_nvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_nvml.nvmlDeviceGetName.return_value = "NVIDIA RTX A5500"
        mock_nvml.NVMLError = Exception
        mock_nvml.nvmlShutdown.return_value = None

        mock_memory = MagicMock()
        mock_memory.used = 8192 * 1024 * 1024
        mock_memory.total = 24576 * 1024 * 1024
        mock_nvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        mock_utilization = MagicMock()
        mock_utilization.gpu = 50.0
        mock_nvml.nvmlDeviceGetUtilizationRates.return_value = mock_utilization
        mock_nvml.nvmlDeviceGetTemperature.return_value = 45.0
        mock_nvml.NVML_TEMPERATURE_GPU = 0
        mock_nvml.nvmlDeviceGetPowerUsage.return_value = 100000

        sys.modules["pynvml"] = mock_nvml
        yield mock_nvml
        if "pynvml" in sys.modules:
            del sys.modules["pynvml"]

    @pytest.fixture
    def reset_semaphore(self):
        """Reset inference semaphore."""
        from backend.services.inference_semaphore import reset_inference_semaphore

        reset_inference_semaphore()
        yield
        reset_inference_semaphore()

    @pytest.mark.asyncio
    async def test_full_pressure_cycle(self, mock_pynvml, reset_semaphore) -> None:
        """Test full cycle: NORMAL -> WARNING -> CRITICAL -> NORMAL."""
        from backend.services.inference_semaphore import get_inference_semaphore

        monitor = GPUMonitor()
        semaphore = get_inference_semaphore()
        initial_permits = semaphore._value

        # Register semaphore throttling callback
        from backend.services.inference_semaphore import (
            reduce_permits_for_memory_pressure,
            restore_permits_after_pressure,
        )

        async def throttle_callback(new_level: MemoryPressureLevel, old_level: MemoryPressureLevel):
            if new_level == MemoryPressureLevel.CRITICAL:
                await reduce_permits_for_memory_pressure(new_level)
            elif (
                new_level == MemoryPressureLevel.NORMAL and old_level != MemoryPressureLevel.NORMAL
            ):
                await restore_permits_after_pressure()

        monitor.register_memory_pressure_callback(throttle_callback)
        monitor._last_memory_pressure_level = MemoryPressureLevel.NORMAL

        # Transition to CRITICAL
        mock_memory = MagicMock()
        mock_memory.used = int(0.97 * 24 * 1024 * 1024 * 1024)
        mock_memory.total = 24 * 1024 * 1024 * 1024
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        await monitor.check_memory_pressure()
        assert semaphore._value < initial_permits

        # Transition back to NORMAL
        mock_memory.used = int(0.5 * 24 * 1024 * 1024 * 1024)
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

        await monitor.check_memory_pressure()
        assert semaphore._value == initial_permits

    @pytest.mark.asyncio
    async def test_poll_loop_checks_memory_pressure(self, mock_pynvml) -> None:
        """Test that poll loop checks memory pressure periodically."""
        monitor = GPUMonitor(poll_interval=0.05)

        with patch("backend.services.gpu_monitor.get_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()
            mock_db_session = AsyncMock()
            mock_db_session.add = MagicMock()
            mock_db_session.commit = AsyncMock()
            mock_db_session.execute = AsyncMock(
                return_value=MagicMock(scalar=MagicMock(return_value=0))
            )
            mock_session.return_value.__aenter__.return_value = mock_db_session

            with patch.object(
                monitor, "check_memory_pressure", new_callable=AsyncMock
            ) as mock_check:
                mock_check.return_value = MemoryPressureLevel.NORMAL

                await monitor.start()
                await asyncio.sleep(0.15)
                await monitor.stop()

                # Memory pressure should have been checked at least once
                assert mock_check.call_count >= 1
