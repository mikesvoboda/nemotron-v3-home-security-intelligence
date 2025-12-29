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
    """Mock pynvml module not being available (ImportError)."""
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
    with patch("backend.services.gpu_monitor.get_session") as mock_get_session:
        mock_session = AsyncMock()
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


def test_gpu_monitor_init_without_pynvml(mock_pynvml_not_available):
    """Test GPUMonitor initialization when pynvml is not installed."""
    monitor = GPUMonitor(poll_interval=5.0)

    assert monitor._gpu_available is False
    assert monitor._nvml_initialized is False
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


def test_get_current_stats_mock_gpu(mock_pynvml_not_available):
    """Test getting current GPU stats when GPU is not available."""
    monitor = GPUMonitor()
    stats = monitor.get_current_stats()

    assert stats["gpu_name"] == "Mock GPU (No NVIDIA GPU Available)"
    assert stats["gpu_utilization"] is None
    assert stats["memory_used"] is None
    assert stats["memory_total"] is None
    assert stats["temperature"] is None
    assert stats["power_usage"] is None
    assert isinstance(stats["recorded_at"], datetime)


def test_get_current_stats_handles_pynvml_errors(mock_pynvml):
    """Test that get_current_stats handles pynvml errors gracefully."""
    monitor = GPUMonitor()

    # Simulate pynvml error
    with patch.object(monitor, "_get_gpu_stats_real", side_effect=Exception("GPU error")):
        stats = monitor.get_current_stats()

        # Should fall back to mock data
        assert stats["gpu_name"] == "Mock GPU (No NVIDIA GPU Available)"
        assert stats["gpu_utilization"] is None


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
            recorded_at=datetime.utcnow(),
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
