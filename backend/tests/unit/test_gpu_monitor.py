"""Unit tests for GPU monitor service."""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.gpu_monitor import GPUMonitor

# Test Fixtures


@pytest.fixture
def mock_pynvml():
    """Mock pynvml module for testing."""
    # Create a mock pynvml module
    mock_nvml = MagicMock()

    # Configure mock GPU handle
    mock_handle = MagicMock()

    # Configure nvmlInit to succeed
    mock_nvml.nvmlInit.return_value = None

    # Configure device access
    mock_nvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
    mock_nvml.nvmlDeviceGetName.return_value = "NVIDIA RTX A5500"

    # Configure utilization rates
    mock_utilization = MagicMock()
    mock_utilization.gpu = 75.0
    mock_nvml.nvmlDeviceGetUtilizationRates.return_value = mock_utilization

    # Configure memory info
    mock_memory = MagicMock()
    mock_memory.used = 8192 * 1024 * 1024  # 8192 MB in bytes
    mock_memory.total = 24576 * 1024 * 1024  # 24576 MB in bytes
    mock_nvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory

    # Configure temperature
    mock_nvml.nvmlDeviceGetTemperature.return_value = 65.0
    mock_nvml.NVML_TEMPERATURE_GPU = 0

    # Configure power usage
    mock_nvml.nvmlDeviceGetPowerUsage.return_value = 150000  # 150W in milliwatts

    # Configure shutdown
    mock_nvml.nvmlShutdown.return_value = None

    # Configure NVMLError
    mock_nvml.NVMLError = Exception

    # Inject into sys.modules before importing
    sys.modules["pynvml"] = mock_nvml

    yield mock_nvml

    # Cleanup
    if "pynvml" in sys.modules:
        del sys.modules["pynvml"]


@pytest.fixture
def mock_pynvml_not_available():
    """Mock pynvml module not being available (ImportError).

    Note: This fixture only mocks pynvml. On systems with nvidia-smi available,
    the GPUMonitor will fall back to using nvidia-smi.
    Use mock_no_gpu_access for tests that need to force mock data mode.
    """
    # Save original if it exists
    original_pynvml = sys.modules.get("pynvml")

    # Create a mock that raises ImportError
    mock_module = MagicMock()
    mock_module.__name__ = "pynvml"

    # Make the import itself fail by replacing with None
    # This will cause ImportError when trying to import
    import builtins

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "pynvml":
            raise ImportError("pynvml not installed")
        return original_import(name, *args, **kwargs)

    builtins.__import__ = mock_import

    # Remove from sys.modules if present
    if "pynvml" in sys.modules:
        del sys.modules["pynvml"]

    yield

    # Restore
    builtins.__import__ = original_import
    if original_pynvml is not None:
        sys.modules["pynvml"] = original_pynvml
    elif "pynvml" in sys.modules:
        del sys.modules["pynvml"]


@pytest.fixture
def mock_no_gpu_access():
    """Mock both pynvml not available AND nvidia-smi not in PATH.

    This fixture ensures the GPUMonitor falls back to mock data mode.
    Use this for tests that expect mock GPU data.
    """
    # Save original if it exists
    original_pynvml = sys.modules.get("pynvml")

    # Make the import itself fail by replacing with None
    import builtins

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "pynvml":
            raise ImportError("pynvml not installed")
        return original_import(name, *args, **kwargs)

    builtins.__import__ = mock_import

    # Remove from sys.modules if present
    if "pynvml" in sys.modules:
        del sys.modules["pynvml"]

    # Also mock shutil.which to return None for nvidia-smi
    with patch("shutil.which", return_value=None):
        yield

    # Restore
    builtins.__import__ = original_import
    if original_pynvml is not None:
        sys.modules["pynvml"] = original_pynvml
    elif "pynvml" in sys.modules:
        del sys.modules["pynvml"]


@pytest.fixture
def mock_pynvml_no_gpu():
    """Mock pynvml with no GPU devices available."""
    mock_nvml = MagicMock()

    # nvmlInit succeeds
    mock_nvml.nvmlInit.return_value = None

    # But no GPU device found
    mock_nvml.NVMLError = Exception
    mock_nvml.nvmlDeviceGetHandleByIndex.side_effect = Exception("No GPU device found")

    # Inject into sys.modules
    sys.modules["pynvml"] = mock_nvml

    yield mock_nvml

    # Cleanup
    if "pynvml" in sys.modules:
        del sys.modules["pynvml"]


@pytest.fixture
def mock_database_session():
    """Mock database session."""
    from sqlalchemy.ext.asyncio import AsyncSession

    with patch("backend.services.gpu_monitor.get_session") as mock_get_session:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.execute = AsyncMock()

        mock_get_session.return_value = mock_session
        yield mock_session


@pytest.fixture
def mock_broadcaster():
    """Mock WebSocket broadcaster."""
    broadcaster = AsyncMock()
    broadcaster.broadcast_gpu_stats = AsyncMock()
    return broadcaster


# Test GPU Monitor Initialization


def test_gpu_monitor_init_with_gpu(mock_pynvml):
    """Test GPUMonitor initialization with GPU available."""
    monitor = GPUMonitor(poll_interval=2.0, history_minutes=30)

    assert monitor.poll_interval == 2.0
    assert monitor.history_minutes == 30
    assert monitor._gpu_available is True
    assert monitor._nvml_initialized is True
    assert monitor._gpu_name == "NVIDIA RTX A5500"
    assert monitor.running is False


def test_gpu_monitor_init_without_pynvml(mock_no_gpu_access):
    """Test GPUMonitor initialization when pynvml is not installed and nvidia-smi unavailable."""
    monitor = GPUMonitor(poll_interval=5.0)

    assert monitor._gpu_available is False
    assert monitor._nvml_initialized is False
    assert monitor._nvidia_smi_available is False
    assert monitor._gpu_name is None
    assert monitor.running is False


def test_gpu_monitor_init_no_gpu_device(mock_pynvml_no_gpu):
    """Test GPUMonitor initialization when no GPU device is found."""
    monitor = GPUMonitor(poll_interval=5.0)

    assert monitor._gpu_available is False
    assert monitor._nvml_initialized is True
    assert monitor.running is False


def test_gpu_monitor_init_with_broadcaster(mock_pynvml, mock_broadcaster):
    """Test GPUMonitor initialization with broadcaster."""
    monitor = GPUMonitor(broadcaster=mock_broadcaster)

    assert monitor.broadcaster is mock_broadcaster
    assert monitor._gpu_available is True


# Test GPU Stats Collection


def test_get_current_stats_real_gpu(mock_pynvml):
    """Test getting current GPU stats with real GPU available."""
    monitor = GPUMonitor()
    stats = monitor.get_current_stats()

    assert stats["gpu_name"] == "NVIDIA RTX A5500"
    assert stats["gpu_utilization"] == 75.0
    assert stats["memory_used"] == 8192  # MB
    assert stats["memory_total"] == 24576  # MB
    assert stats["temperature"] == 65.0
    assert stats["power_usage"] == 150.0  # Watts
    assert isinstance(stats["recorded_at"], datetime)


def test_get_current_stats_mock_gpu(mock_no_gpu_access):
    """Test getting current GPU stats when GPU is not available.

    The mock mode now provides simulated values (varying slightly over time)
    instead of all nulls, to enable meaningful display in development environments.
    This test requires both pynvml and nvidia-smi to be unavailable to reach mock mode.
    """
    monitor = GPUMonitor()
    stats = monitor.get_current_stats()

    assert stats["gpu_name"] == "Mock GPU (Development Mode)"
    # Mock provides simulated values in reasonable ranges
    assert isinstance(stats["gpu_utilization"], float)
    assert 15.0 <= stats["gpu_utilization"] <= 35.0  # base_util +/- variance
    assert isinstance(stats["memory_used"], int)
    assert 2560 <= stats["memory_used"] <= 3584  # base_memory +/- variance
    assert stats["memory_total"] == 24576  # 24 GB in MB
    assert isinstance(stats["temperature"], float)
    assert 34.0 <= stats["temperature"] <= 50.0  # base_temp +/- variance
    assert isinstance(stats["power_usage"], float)
    assert 30.0 <= stats["power_usage"] <= 70.0  # base_power +/- variance
    assert isinstance(stats["recorded_at"], datetime)


def test_get_current_stats_handles_pynvml_errors(mock_pynvml):
    """Test that get_current_stats handles pynvml errors gracefully."""
    monitor = GPUMonitor()

    # Simulate pynvml error
    with patch.object(monitor, "_get_gpu_stats_real", side_effect=Exception("GPU error")):
        stats = monitor.get_current_stats()

        # Should fall back to mock data with simulated values
        assert stats["gpu_name"] == "Mock GPU (Development Mode)"
        assert isinstance(stats["gpu_utilization"], float)


# Test nvidia-smi Fallback


def test_nvidia_smi_fallback_when_pynvml_unavailable(mock_pynvml_not_available):
    """Test that nvidia-smi is used as fallback when pynvml is not available.

    This test runs on systems with nvidia-smi available, verifying the fallback works.
    """
    monitor = GPUMonitor()

    # When pynvml is not available but nvidia-smi is, we should use nvidia-smi
    if monitor._nvidia_smi_available:
        stats = monitor.get_current_stats()

        # Should get real data from nvidia-smi, not mock data
        assert stats["gpu_name"] != "Mock GPU (Development Mode)"
        # Temperature should be reasonable (not 0 like AI container fallback)
        assert stats["temperature"] is None or stats["temperature"] > 0
        # Power should be non-zero when GPU is powered on
        assert stats["power_usage"] is None or stats["power_usage"] > 0
    else:
        # On systems without nvidia-smi, this test is a no-op
        pass


def test_nvidia_smi_stats_parsing():
    """Test parsing of nvidia-smi output format."""
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    # Mock subprocess.run to return known values
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "39, 29.61, 35, 175, 24576, NVIDIA RTX A5500"

    with patch("subprocess.run", return_value=mock_result):
        stats = monitor._get_gpu_stats_nvidia_smi()

        assert stats["temperature"] == 39.0
        assert stats["power_usage"] == 29.61
        assert stats["gpu_utilization"] == 35.0
        assert stats["memory_used"] == 175
        assert stats["memory_total"] == 24576
        assert stats["gpu_name"] == "NVIDIA RTX A5500"


def test_nvidia_smi_handles_na_values():
    """Test that nvidia-smi parsing handles [N/A] values gracefully."""
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    # Mock subprocess.run with N/A values
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "[N/A], [N/A], 35, 175, 24576, NVIDIA RTX A5500"

    with patch("subprocess.run", return_value=mock_result):
        stats = monitor._get_gpu_stats_nvidia_smi()

        assert stats["temperature"] is None
        assert stats["power_usage"] is None
        assert stats["gpu_utilization"] == 35.0
        assert stats["memory_used"] == 175


def test_nvidia_smi_timeout_handling():
    """Test that nvidia-smi timeout is handled properly."""
    import subprocess

    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    with (
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 5)),
        pytest.raises(RuntimeError, match="nvidia-smi timed out"),
    ):
        monitor._get_gpu_stats_nvidia_smi()


# Test Stats History


def test_stats_history_empty(mock_pynvml):
    """Test getting stats history when empty."""
    monitor = GPUMonitor()
    history = monitor.get_stats_history()

    assert history == []


def test_stats_history_all(mock_pynvml):
    """Test getting all stats history."""
    monitor = GPUMonitor()

    # Add some stats to history
    for i in range(5):
        stats = monitor.get_current_stats()
        monitor._stats_history.append(stats)

    history = monitor.get_stats_history()
    assert len(history) == 5


def test_stats_history_filtered_by_time(mock_pynvml):
    """Test getting stats history filtered by time."""
    monitor = GPUMonitor()

    # Add stats with different timestamps (must be timezone-aware to match implementation)
    now = datetime.now(UTC)
    for i in range(5):
        stats = monitor.get_current_stats()
        stats["recorded_at"] = now - timedelta(minutes=i * 10)
        monitor._stats_history.append(stats)

    # Get last 25 minutes (should return 3 records: 0, 10, 20 minutes ago)
    history = monitor.get_stats_history(minutes=25)
    assert len(history) == 3


def test_stats_history_circular_buffer(mock_pynvml):
    """Test that stats history uses circular buffer (maxlen=1000)."""
    monitor = GPUMonitor()

    # Add more than maxlen items
    for i in range(1100):
        stats = monitor.get_current_stats()
        monitor._stats_history.append(stats)

    # Should only keep last 1000
    assert len(monitor._stats_history) == 1000


# Test Async Operations


@pytest.mark.asyncio
async def test_store_stats_in_database(mock_pynvml, mock_database_session):
    """Test storing GPU stats in database."""
    monitor = GPUMonitor()
    stats = monitor.get_current_stats()

    await monitor._store_stats(stats)

    # Verify session operations
    mock_database_session.add.assert_called_once()
    mock_database_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_stats_handles_database_error(mock_pynvml, mock_database_session):
    """Test that store_stats handles database errors gracefully."""
    monitor = GPUMonitor()
    stats = monitor.get_current_stats()

    # Simulate database error
    mock_database_session.commit.side_effect = Exception("Database error")

    # Should not raise exception
    await monitor._store_stats(stats)


@pytest.mark.asyncio
async def test_broadcast_stats(mock_pynvml, mock_broadcaster):
    """Test broadcasting GPU stats via WebSocket."""
    monitor = GPUMonitor(broadcaster=mock_broadcaster)
    stats = monitor.get_current_stats()

    await monitor._broadcast_stats(stats)

    mock_broadcaster.broadcast_gpu_stats.assert_awaited_once()


@pytest.mark.asyncio
async def test_broadcast_stats_no_broadcaster(mock_pynvml):
    """Test broadcasting when no broadcaster is configured."""
    monitor = GPUMonitor(broadcaster=None)
    stats = monitor.get_current_stats()

    # Should not raise exception
    await monitor._broadcast_stats(stats)


@pytest.mark.asyncio
async def test_broadcast_stats_handles_error(mock_pynvml, mock_broadcaster):
    """Test that broadcast_stats handles errors gracefully."""
    monitor = GPUMonitor(broadcaster=mock_broadcaster)
    stats = monitor.get_current_stats()

    # Simulate broadcast error
    mock_broadcaster.broadcast_gpu_stats.side_effect = Exception("Broadcast error")

    # Should not raise exception
    await monitor._broadcast_stats(stats)


# Test Start/Stop Lifecycle


@pytest.mark.asyncio
async def test_start_monitor(mock_pynvml, mock_database_session):
    """Test starting GPU monitor."""
    monitor = GPUMonitor(poll_interval=0.1)

    await monitor.start()

    assert monitor.running is True
    assert monitor._poll_task is not None
    assert not monitor._poll_task.done()

    await monitor.stop()


@pytest.mark.asyncio
async def test_start_monitor_idempotent(mock_pynvml, mock_database_session):
    """Test that starting monitor multiple times is safe."""
    monitor = GPUMonitor(poll_interval=0.1)

    await monitor.start()
    first_task = monitor._poll_task

    await monitor.start()  # Start again
    second_task = monitor._poll_task

    # Should be the same task
    assert first_task is second_task

    await monitor.stop()


@pytest.mark.asyncio
async def test_stop_monitor(mock_pynvml, mock_database_session):
    """Test stopping GPU monitor."""
    monitor = GPUMonitor(poll_interval=0.1)

    await monitor.start()
    await asyncio.sleep(0.05)  # Let it run briefly

    await monitor.stop()

    assert monitor.running is False
    assert monitor._poll_task is None or monitor._poll_task.done()


@pytest.mark.asyncio
async def test_stop_monitor_not_running(mock_pynvml):
    """Test stopping monitor that is not running."""
    monitor = GPUMonitor()

    # Should not raise exception
    await monitor.stop()


@pytest.mark.asyncio
async def test_poll_loop_collects_stats(mock_pynvml, mock_database_session, mock_broadcaster):
    """Test that poll loop collects and stores stats."""
    monitor = GPUMonitor(poll_interval=0.1, broadcaster=mock_broadcaster)

    await monitor.start()
    await asyncio.sleep(0.25)  # Let it run for ~2 polls
    await monitor.stop()

    # Should have collected stats
    assert len(monitor._stats_history) >= 2

    # Should have stored in database
    assert mock_database_session.add.call_count >= 2

    # Should have broadcasted
    assert mock_broadcaster.broadcast_gpu_stats.call_count >= 2


@pytest.mark.asyncio
async def test_poll_loop_continues_on_error(mock_pynvml, mock_database_session):
    """Test that poll loop continues even if one iteration fails."""
    monitor = GPUMonitor(poll_interval=0.1)

    # Make first iteration fail
    original_get_stats = monitor.get_current_stats
    call_count = 0

    def get_stats_with_error():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Simulated error")
        return original_get_stats()

    monitor.get_current_stats = get_stats_with_error

    await monitor.start()
    await asyncio.sleep(0.25)  # Let it run for multiple polls
    await monitor.stop()

    # Should have recovered and collected more stats
    assert len(monitor._stats_history) >= 1


# Test Database Retrieval


@pytest.mark.asyncio
async def test_get_stats_from_db(mock_pynvml):
    """Test retrieving GPU stats from database."""
    from backend.models.gpu_stats import GPUStats

    monitor = GPUMonitor()

    # Mock database query result
    mock_stats = [
        GPUStats(
            id=1,
            recorded_at=datetime.now(UTC),
            gpu_name="NVIDIA RTX A5500",
            gpu_utilization=75.0,
            memory_used=8192,
            memory_total=24576,
            temperature=65.0,
            power_usage=150.0,
        )
    ]

    with patch("backend.services.gpu_monitor.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_stats
        mock_session.execute.return_value = mock_result

        mock_get_session.return_value = mock_session

        stats = await monitor.get_stats_from_db(minutes=60, limit=100)

        assert len(stats) == 1
        assert stats[0].gpu_name == "NVIDIA RTX A5500"


@pytest.mark.asyncio
async def test_get_stats_from_db_handles_error(mock_pynvml):
    """Test that get_stats_from_db handles database errors gracefully."""
    monitor = GPUMonitor()

    with patch("backend.services.gpu_monitor.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.__aenter__.side_effect = Exception("Database error")
        mock_get_session.return_value = mock_session

        stats = await monitor.get_stats_from_db()

        # Should return empty list instead of raising
        assert stats == []


# Test Partial NVML Failures


def test_get_stats_with_partial_nvml_failure(mock_pynvml):
    """Test getting stats when some NVML calls fail."""
    monitor = GPUMonitor()

    # Make some NVML calls fail
    mock_pynvml.nvmlDeviceGetUtilizationRates.side_effect = Exception("GPU util error")
    mock_pynvml.nvmlDeviceGetTemperature.side_effect = Exception("Temp error")

    stats = monitor.get_current_stats()

    # Should still return stats with None for failed metrics
    assert stats["gpu_name"] == "NVIDIA RTX A5500"
    assert stats["gpu_utilization"] is None
    assert stats["memory_used"] == 8192  # This one still works
    assert stats["temperature"] is None
    assert stats["power_usage"] == 150.0  # This one still works


# Test NVML Shutdown


@pytest.mark.asyncio
async def test_nvml_shutdown_on_stop(mock_pynvml, mock_database_session):
    """Test that NVML is properly shutdown when monitor stops."""
    monitor = GPUMonitor(poll_interval=0.1)

    await monitor.start()
    await asyncio.sleep(0.05)
    await monitor.stop()

    # Verify NVML shutdown was called
    mock_pynvml.nvmlShutdown.assert_called_once()


@pytest.mark.asyncio
async def test_nvml_shutdown_handles_error(mock_pynvml, mock_database_session):
    """Test that stop() handles NVML shutdown errors gracefully."""
    monitor = GPUMonitor(poll_interval=0.1)

    await monitor.start()
    await asyncio.sleep(0.05)

    # Make shutdown fail
    mock_pynvml.nvmlShutdown.side_effect = Exception("Shutdown error")

    # Should not raise exception
    await monitor.stop()


# Test NVML initialization with generic exception (not ImportError)


def test_gpu_monitor_init_generic_exception():
    """Test GPUMonitor initialization when nvmlInit raises a generic exception."""
    # Save original if it exists
    original_pynvml = sys.modules.get("pynvml")

    # Create a mock pynvml that raises generic exception on nvmlInit
    mock_nvml = MagicMock()
    mock_nvml.nvmlInit.side_effect = Exception("Generic NVML error")

    sys.modules["pynvml"] = mock_nvml

    try:
        monitor = GPUMonitor(poll_interval=5.0)

        # Should fall back to mock mode
        assert monitor._gpu_available is False
        assert monitor._nvml_initialized is False
        assert monitor.running is False
    finally:
        # Cleanup
        if original_pynvml is not None:
            sys.modules["pynvml"] = original_pynvml
        elif "pynvml" in sys.modules:
            del sys.modules["pynvml"]


# Test _get_gpu_stats_real when GPU not available


def test_get_gpu_stats_real_raises_when_gpu_unavailable(mock_pynvml_not_available):
    """Test that _get_gpu_stats_real raises RuntimeError when GPU not available."""
    monitor = GPUMonitor()

    # GPU should not be available
    assert monitor._gpu_available is False

    # Trying to get real stats should raise RuntimeError
    with pytest.raises(RuntimeError, match="GPU not available"):
        monitor._get_gpu_stats_real()


# Test partial NVML failures for memory and power


def test_get_stats_with_memory_nvml_failure(mock_pynvml):
    """Test getting stats when memory NVML calls fail."""
    monitor = GPUMonitor()

    # Make memory call fail
    mock_pynvml.nvmlDeviceGetMemoryInfo.side_effect = Exception("Memory info error")

    stats = monitor.get_current_stats()

    # Memory should be None, others should still work
    assert stats["gpu_name"] == "NVIDIA RTX A5500"
    assert stats["gpu_utilization"] == 75.0
    assert stats["memory_used"] is None
    assert stats["memory_total"] is None
    assert stats["temperature"] == 65.0
    assert stats["power_usage"] == 150.0


def test_get_stats_with_power_nvml_failure(mock_pynvml):
    """Test getting stats when power NVML call fails."""
    monitor = GPUMonitor()

    # Make power call fail
    mock_pynvml.nvmlDeviceGetPowerUsage.side_effect = Exception("Power info error")

    stats = monitor.get_current_stats()

    # Power should be None, others should still work
    assert stats["gpu_name"] == "NVIDIA RTX A5500"
    assert stats["gpu_utilization"] == 75.0
    assert stats["memory_used"] == 8192
    assert stats["temperature"] == 65.0
    assert stats["power_usage"] is None


def test_get_stats_real_generic_exception(mock_pynvml):
    """Test that generic exceptions in _get_gpu_stats_real are re-raised."""
    monitor = GPUMonitor()

    # Make a generic error occur
    with patch.object(monitor, "_gpu_handle", None):
        monitor._gpu_available = True  # Force it to try real stats

        # Should fall back to mock data with simulated values in get_current_stats
        stats = monitor.get_current_stats()
        assert stats["gpu_name"] == "Mock GPU (Development Mode)"


# Test _parse_rtdetr_response


def test_parse_rtdetr_response_full_data(mock_pynvml):
    """Test parsing RT-DETRv2 response with all data."""
    monitor = GPUMonitor()

    data = {"vram_used_gb": 4.5, "device": "cuda:0"}
    vram_mb, device = monitor._parse_rtdetr_response(data)

    assert vram_mb == 4.5 * 1024  # 4608 MB
    assert device == "cuda:0"


def test_parse_rtdetr_response_no_vram(mock_pynvml):
    """Test parsing RT-DETRv2 response without VRAM data."""
    monitor = GPUMonitor()

    data = {"device": "cuda:0"}
    vram_mb, device = monitor._parse_rtdetr_response(data)

    assert vram_mb == 0.0
    assert device == "cuda:0"


def test_parse_rtdetr_response_no_device(mock_pynvml):
    """Test parsing RT-DETRv2 response without device data."""
    monitor = GPUMonitor()

    data = {"vram_used_gb": 2.0}
    vram_mb, device = monitor._parse_rtdetr_response(data)

    assert vram_mb == 2.0 * 1024
    assert device is None


def test_parse_rtdetr_response_empty(mock_pynvml):
    """Test parsing RT-DETRv2 response with empty data."""
    monitor = GPUMonitor()

    data = {}
    vram_mb, device = monitor._parse_rtdetr_response(data)

    assert vram_mb == 0.0
    assert device is None


# Test _parse_vram_metric_line


def test_parse_vram_metric_line_bytes(mock_pynvml):
    """Test parsing VRAM metric line with bytes unit."""
    monitor = GPUMonitor()

    line = "vram_used_bytes 8589934592"  # 8 GB in bytes
    result = monitor._parse_vram_metric_line(line)

    # 8589934592 bytes = 8192 MB
    assert result == 8589934592 / (1024 * 1024)


def test_parse_vram_metric_line_gb(mock_pynvml):
    """Test parsing VRAM metric line with GB unit."""
    monitor = GPUMonitor()

    line = "vram_used_gb 4.0"
    result = monitor._parse_vram_metric_line(line)

    assert result == 4.0 * 1024  # 4096 MB


def test_parse_vram_metric_line_default_mb(mock_pynvml):
    """Test parsing VRAM metric line with default MB assumption."""
    monitor = GPUMonitor()

    line = "vram_used 2048"  # Assumed MB
    result = monitor._parse_vram_metric_line(line)

    assert result == 2048.0


def test_parse_vram_metric_line_too_few_parts(mock_pynvml):
    """Test parsing VRAM metric line with insufficient parts."""
    monitor = GPUMonitor()

    line = "vram_used"
    result = monitor._parse_vram_metric_line(line)

    assert result == 0.0


def test_parse_vram_metric_line_invalid_value(mock_pynvml):
    """Test parsing VRAM metric line with invalid value."""
    monitor = GPUMonitor()

    line = "vram_used invalid_number"
    result = monitor._parse_vram_metric_line(line)

    assert result == 0.0


# Test _get_gpu_stats_from_ai_containers


@pytest.mark.asyncio
async def test_get_gpu_stats_from_ai_containers_rtdetr_only(mock_pynvml):
    """Test getting GPU stats from AI containers (RT-DETRv2 only).

    Note: Nemotron (llama.cpp server) does not expose GPU metrics,
    so GPU stats are obtained exclusively from RT-DETRv2.
    """
    monitor = GPUMonitor()

    rtdetr_response = {"vram_used_gb": 3.5, "device": "cuda:0"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # RT-DETRv2 succeeds
        mock_rtdetr_resp = MagicMock()
        mock_rtdetr_resp.status_code = 200
        mock_rtdetr_resp.json.return_value = rtdetr_response

        mock_client.get.return_value = mock_rtdetr_resp

        stats = await monitor._get_gpu_stats_from_ai_containers()

        assert stats is not None
        assert stats["memory_used"] == int(3.5 * 1024)
        assert "cuda:0" in stats["gpu_name"]
        # Verify default values are set instead of None
        assert stats["gpu_utilization"] == 0.0
        assert stats["memory_total"] == 24576  # 24GB in MB
        assert stats["temperature"] == 0
        assert stats["power_usage"] == 0.0


@pytest.mark.asyncio
async def test_get_gpu_stats_from_ai_containers_all_fail(mock_pynvml):
    """Test getting GPU stats when all AI containers fail."""
    monitor = GPUMonitor()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Both requests fail
        mock_client.get.side_effect = Exception("Connection error")

        stats = await monitor._get_gpu_stats_from_ai_containers()

        assert stats is None


@pytest.mark.asyncio
async def test_get_gpu_stats_from_ai_containers_no_vram(mock_pynvml):
    """Test getting GPU stats when AI containers return no VRAM data.

    Note: Only RT-DETRv2 is queried for GPU metrics (Nemotron doesn't expose them).
    """
    monitor = GPUMonitor()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # RT-DETRv2 returns empty (no vram_used_gb field)
        mock_rtdetr_resp = MagicMock()
        mock_rtdetr_resp.status_code = 200
        mock_rtdetr_resp.json.return_value = {}

        mock_client.get.return_value = mock_rtdetr_resp

        stats = await monitor._get_gpu_stats_from_ai_containers()

        # Should return None when no VRAM data found
        assert stats is None


@pytest.mark.asyncio
async def test_get_gpu_stats_from_ai_containers_exception(mock_pynvml):
    """Test getting GPU stats when AI container query raises exception."""
    monitor = GPUMonitor()

    with patch("httpx.AsyncClient") as mock_client_class:
        # Make the entire client context manager fail
        mock_client_class.return_value.__aenter__.side_effect = Exception("Client error")

        stats = await monitor._get_gpu_stats_from_ai_containers()

        assert stats is None


# Test get_current_stats_async


@pytest.mark.asyncio
async def test_get_current_stats_async_with_gpu(mock_pynvml):
    """Test async stats retrieval with GPU available."""
    monitor = GPUMonitor()

    stats = await monitor.get_current_stats_async()

    assert stats["gpu_name"] == "NVIDIA RTX A5500"
    assert stats["gpu_utilization"] == 75.0


@pytest.mark.asyncio
async def test_get_current_stats_async_ai_container_fallback(mock_no_gpu_access):
    """Test async stats retrieval falls back to AI containers.

    Requires both pynvml and nvidia-smi to be unavailable so AI containers are tried.
    """
    monitor = GPUMonitor()

    # Mock AI container response
    ai_stats = {
        "gpu_name": "NVIDIA GPU (via AI Containers)",
        "memory_used": 4096,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(monitor, "_get_gpu_stats_from_ai_containers", return_value=ai_stats):
        stats = await monitor.get_current_stats_async()

        assert stats["gpu_name"] == "NVIDIA GPU (via AI Containers)"
        assert stats["memory_used"] == 4096


@pytest.mark.asyncio
async def test_get_current_stats_async_mock_fallback(mock_no_gpu_access):
    """Test async stats retrieval falls back to mock when AI containers fail.

    Requires both pynvml and nvidia-smi to be unavailable to reach mock mode.
    """
    monitor = GPUMonitor()

    # Mock AI containers returning None
    with patch.object(monitor, "_get_gpu_stats_from_ai_containers", return_value=None):
        stats = await monitor.get_current_stats_async()

        # Mock provides simulated values now
        assert stats["gpu_name"] == "Mock GPU (Development Mode)"
        assert isinstance(stats["gpu_utilization"], float)


@pytest.mark.asyncio
async def test_get_current_stats_async_exception_fallback(mock_pynvml):
    """Test async stats retrieval falls back to mock on exception."""
    monitor = GPUMonitor()

    # Make _get_gpu_stats_real raise exception
    with patch.object(monitor, "_get_gpu_stats_real", side_effect=Exception("GPU error")):
        stats = await monitor.get_current_stats_async()

        # Mock provides simulated values now
        assert stats["gpu_name"] == "Mock GPU (Development Mode)"


# Test poll loop exception handling


@pytest.mark.asyncio
async def test_poll_loop_handles_exception_in_iteration(mock_pynvml, mock_database_session):
    """Test that poll loop handles exceptions in a single iteration and continues."""
    monitor = GPUMonitor(poll_interval=0.05)

    call_count = 0

    async def get_stats_with_error():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Simulated poll error")
        return monitor._get_gpu_stats_mock()

    with patch.object(monitor, "get_current_stats_async", side_effect=get_stats_with_error):
        await monitor.start()
        await asyncio.sleep(0.15)  # Let it run for a few iterations
        await monitor.stop()

    # Should have recovered from the error and continued
    assert call_count >= 2


# Test _get_gpu_stats_real exception path that re-raises


def test_get_gpu_stats_real_reraises_exception(mock_pynvml):
    """Test that _get_gpu_stats_real re-raises exceptions after logging."""
    monitor = GPUMonitor()

    # Make the import of pynvml inside _get_gpu_stats_real fail
    # This simulates an unexpected error inside the function
    with (
        patch("builtins.__import__", side_effect=RuntimeError("Unexpected import error")),
        pytest.raises(RuntimeError, match="Unexpected import error"),
    ):
        monitor._get_gpu_stats_real()
