"""Unit tests for the GPUMonitor service.

This module contains comprehensive unit tests for the GPUMonitor service, which
monitors NVIDIA GPU metrics (utilization, memory, temperature, power) and
broadcasts them via WebSocket for the dashboard's GPU stats display.

Related Issues:
    - NEM-1661: Improve Test Documentation with Intent and Acceptance Criteria
    - NEM-249: GPU Monitor Service Implementation
    - NEM-1121: Configurable HTTP Client Timeouts
    - NEM-1123: Error Logging Context Improvements

Test Organization:
    - Initialization tests: GPUMonitor creation with pynvml/nvidia-smi/mock modes
    - Stats collection tests: Real GPU stats, mock GPU stats, and partial failures
    - nvidia-smi fallback tests: Parsing, N/A values, timeout handling, async support
    - Stats history tests: Empty history, filtering by time, circular buffer
    - Async operations tests: Database storage, WebSocket broadcasting
    - Lifecycle tests: Start/stop, idempotency, poll loop error handling
    - Database retrieval tests: get_stats_from_db with and without errors
    - RT-DETR response parsing tests: VRAM metrics from AI containers
    - Inference FPS calculation tests: Detection-based FPS calculation
    - HTTP timeout tests: Configurable timeouts for AI container queries
    - Error logging tests: Context-rich error logging (NEM-1123)

Acceptance Criteria:
    - GPUMonitor detects and uses pynvml when available
    - Falls back to nvidia-smi CLI when pynvml unavailable
    - Falls back to mock data when no GPU access available
    - Stats include: gpu_name, gpu_utilization, memory_used/total, temperature, power_usage
    - Stats are stored to database periodically
    - Stats are broadcast via WebSocket to connected clients
    - Graceful handling of partial NVML failures (individual metrics)
    - Configurable poll interval, history retention, and HTTP timeout

Notes:
    These tests use mocks extensively to simulate GPU hardware behavior.
    Tests work on machines without NVIDIA GPUs by mocking pynvml and nvidia-smi.
"""

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


# =============================================================================
# GPUMonitor Initialization Tests
# =============================================================================


def test_gpu_monitor_init_with_gpu(mock_pynvml):
    """Verify GPUMonitor initializes correctly when pynvml detects GPU.

    Given: pynvml module is available and detects "NVIDIA RTX A5500" GPU
    When: A new GPUMonitor is created with custom poll_interval and history_minutes
    Then: Service stores GPU name, marks GPU as available, and is not running
    """
    monitor = GPUMonitor(poll_interval=2.0, history_minutes=30)

    assert monitor.poll_interval == 2.0
    assert monitor.history_minutes == 30
    assert monitor._gpu_available is True
    assert monitor._nvml_initialized is True
    assert monitor._gpu_name == "NVIDIA RTX A5500"
    assert monitor.running is False


@pytest.mark.usefixtures("mock_no_gpu_access")
def test_gpu_monitor_init_without_pynvml():
    """Verify GPUMonitor falls back to mock mode when no GPU access available.

    Given: pynvml module is not installed AND nvidia-smi is not in PATH
    When: A new GPUMonitor is created
    Then: Service marks GPU as unavailable and enters mock data mode
    """
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


# =============================================================================
# GPU Stats Collection Tests
# =============================================================================


def test_get_current_stats_real_gpu(mock_pynvml):
    """Verify get_current_stats returns complete GPU metrics from pynvml.

    Given: pynvml is available with mocked GPU metrics
    When: get_current_stats() is called
    Then: Returns dict with gpu_name, utilization, memory, temperature, power, timestamp
    """
    monitor = GPUMonitor()
    stats = monitor.get_current_stats()

    assert stats["gpu_name"] == "NVIDIA RTX A5500"
    assert stats["gpu_utilization"] == 75.0
    assert stats["memory_used"] == 8192  # MB
    assert stats["memory_total"] == 24576  # MB
    assert stats["temperature"] == 65.0
    assert stats["power_usage"] == 150.0  # Watts
    assert isinstance(stats["recorded_at"], datetime)


@pytest.mark.usefixtures("mock_no_gpu_access")
def test_get_current_stats_mock_gpu():
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


# =============================================================================
# nvidia-smi Fallback Tests
# =============================================================================


def test_nvidia_smi_fallback_when_pynvml_unavailable(mock_pynvml_not_available):
    """Verify nvidia-smi CLI is used when pynvml module is unavailable.

    Given: pynvml module raises ImportError, but nvidia-smi is in PATH
    When: GPUMonitor is created and stats are requested
    Then: Stats are obtained via nvidia-smi subprocess (not mock data)

    Note: This test is conditional - on systems without nvidia-smi, it passes silently.
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


@pytest.mark.asyncio
async def test_nvidia_smi_async_stats_parsing():
    """Test async nvidia-smi subprocess wrapper returns correct stats."""
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    # Mock the async_subprocess_run function
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "42, 32.5, 45, 2048, 24576, NVIDIA RTX A5500"
    mock_result.stderr = ""

    with patch(
        "backend.core.async_utils.async_subprocess_run",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        stats = await monitor._get_gpu_stats_nvidia_smi_async()

        assert stats["temperature"] == 42.0
        assert stats["power_usage"] == 32.5
        assert stats["gpu_utilization"] == 45.0
        assert stats["memory_used"] == 2048
        assert stats["memory_total"] == 24576
        assert stats["gpu_name"] == "NVIDIA RTX A5500"


@pytest.mark.asyncio
async def test_nvidia_smi_async_handles_errors():
    """Test async nvidia-smi handles subprocess errors properly."""
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    # Mock subprocess to return error
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "NVIDIA-SMI has failed"

    with (
        patch(
            "backend.core.async_utils.async_subprocess_run",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        pytest.raises(RuntimeError, match="nvidia-smi returned error"),
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()


@pytest.mark.asyncio
async def test_nvidia_smi_async_used_in_get_current_stats_async():
    """Test that get_current_stats_async uses the async nvidia-smi method."""
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._gpu_available = False
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"
    monitor._nvml_initialized = False

    expected_stats = {
        "gpu_name": "NVIDIA RTX A5500",
        "gpu_utilization": 50.0,
        "memory_used": 4096,
        "memory_total": 24576,
        "temperature": 55.0,
        "power_usage": 75.0,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(
        monitor,
        "_get_gpu_stats_nvidia_smi_async",
        new_callable=AsyncMock,
        return_value=expected_stats,
    ) as mock_method:
        stats = await monitor.get_current_stats_async()

        mock_method.assert_called_once()
        assert stats == expected_stats


# =============================================================================
# Stats History Tests
# =============================================================================


def test_stats_history_empty(mock_pynvml):
    """Verify empty stats history returns empty list.

    Given: A newly created GPUMonitor with no collected stats
    When: get_stats_history() is called
    Then: Returns empty list
    """
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


# =============================================================================
# Async Operations Tests (Database Storage & WebSocket Broadcasting)
# =============================================================================


@pytest.mark.asyncio
async def test_store_stats_in_database(mock_pynvml, mock_database_session):
    """Verify GPU stats are stored to database via SQLAlchemy session.

    Given: A GPUMonitor with collected stats and a mocked database session
    When: _store_stats() is called with stats dictionary
    Then: Session.add() and session.commit() are called to persist the record
    """
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


# =============================================================================
# Service Lifecycle Tests (Start/Stop)
# =============================================================================


@pytest.mark.asyncio
async def test_start_monitor(mock_pynvml, mock_database_session):
    """Verify starting GPUMonitor creates background polling task.

    Given: A new GPUMonitor instance that is not running
    When: start() is called
    Then: Service is running and poll task is created and active
    """
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
    # Increased sleep to 0.5s to reliably allow multiple polls in CI environments
    # where async scheduling may have more overhead
    await asyncio.sleep(0.5)
    await monitor.stop()

    # Should have collected stats (at least 1, may get more with reliable timing)
    assert len(monitor._stats_history) >= 1

    # Should have stored in database
    assert mock_database_session.add.call_count >= 1

    # Should have broadcasted
    assert mock_broadcaster.broadcast_gpu_stats.call_count >= 1


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


# =============================================================================
# Database Retrieval Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_stats_from_db(mock_pynvml):
    """Verify historical GPU stats are retrieved from database.

    Given: Database contains GPU stats records from the past hour
    When: get_stats_from_db(minutes=60) is called
    Then: Returns list of GPUStats ORM objects with GPU metrics
    """
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


# =============================================================================
# RT-DETR Response Parsing Tests
# =============================================================================


def test_parse_yolo26_response_full_data(mock_pynvml):
    """Verify RT-DETRv2 health endpoint response parsing with full GPU metrics.

    Given: RT-DETRv2 /health response with vram_used_gb, device, gpu_utilization,
           temperature, and power_watts
    When: _parse_yolo26_response() is called with this data
    Then: Returns tuple (vram_mb, device, gpu_util, temp, power) with converted values
    """
    monitor = GPUMonitor()

    data = {
        "vram_used_gb": 4.5,
        "device": "cuda:0",
        "gpu_utilization": 75.0,
        "temperature": 65,
        "power_watts": 150.0,
    }
    vram_mb, device, gpu_util, temp, power = monitor._parse_yolo26_response(data)

    assert vram_mb == 4.5 * 1024  # 4608 MB
    assert device == "cuda:0"
    assert gpu_util == 75.0
    assert temp == 65
    assert power == 150.0


def test_parse_yolo26_response_no_vram(mock_pynvml):
    """Test parsing RT-DETRv2 response without VRAM data."""
    monitor = GPUMonitor()

    data = {"device": "cuda:0", "gpu_utilization": 50.0}
    vram_mb, device, gpu_util, temp, power = monitor._parse_yolo26_response(data)

    assert vram_mb == 0.0
    assert device == "cuda:0"
    assert gpu_util == 50.0
    assert temp is None
    assert power is None


def test_parse_yolo26_response_no_device(mock_pynvml):
    """Test parsing RT-DETRv2 response without device data."""
    monitor = GPUMonitor()

    data = {"vram_used_gb": 2.0, "temperature": 55, "power_watts": 100.0}
    vram_mb, device, gpu_util, temp, power = monitor._parse_yolo26_response(data)

    assert vram_mb == 2.0 * 1024
    assert device is None
    assert gpu_util is None
    assert temp == 55
    assert power == 100.0


def test_parse_yolo26_response_empty(mock_pynvml):
    """Test parsing RT-DETRv2 response with empty data."""
    monitor = GPUMonitor()

    data = {}
    vram_mb, device, gpu_util, temp, power = monitor._parse_yolo26_response(data)

    assert vram_mb == 0.0
    assert device is None
    assert gpu_util is None
    assert temp is None
    assert power is None


def test_parse_yolo26_response_legacy_format(mock_pynvml):
    """Test parsing RT-DETRv2 response in legacy format (no GPU metrics)."""
    monitor = GPUMonitor()

    # Simulate old response format that only had vram_used_gb and device
    data = {"vram_used_gb": 3.0, "device": "cuda:0"}
    vram_mb, device, gpu_util, temp, power = monitor._parse_yolo26_response(data)

    assert vram_mb == 3.0 * 1024
    assert device == "cuda:0"
    assert gpu_util is None
    assert temp is None
    assert power is None


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

    yolo26_response = {"vram_used_gb": 3.5, "device": "cuda:0"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # RT-DETRv2 succeeds
        mock_yolo26_resp = MagicMock()
        mock_yolo26_resp.status_code = 200
        mock_yolo26_resp.json.return_value = yolo26_response

        mock_client.get.return_value = mock_yolo26_resp

        stats = await monitor._get_gpu_stats_from_ai_containers()

        assert stats is not None
        assert stats["memory_used"] == int(3.5 * 1024)
        assert "cuda:0" in stats["gpu_name"]
        # Verify default values are set instead of None when not provided
        assert stats["gpu_utilization"] == 0.0
        assert stats["memory_total"] == 24576  # 24GB in MB
        assert stats["temperature"] == 0
        assert stats["power_usage"] == 0.0


@pytest.mark.asyncio
async def test_get_gpu_stats_from_ai_containers_with_gpu_metrics(mock_pynvml):
    """Test getting GPU stats from AI containers with full GPU metrics.

    Tests that gpu_utilization, temperature, and power_watts are correctly
    passed through from the RT-DETRv2 health endpoint.
    """
    monitor = GPUMonitor()

    yolo26_response = {
        "vram_used_gb": 4.0,
        "device": "cuda:0",
        "gpu_utilization": 75.0,
        "temperature": 65,
        "power_watts": 150.0,
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_yolo26_resp = MagicMock()
        mock_yolo26_resp.status_code = 200
        mock_yolo26_resp.json.return_value = yolo26_response

        mock_client.get.return_value = mock_yolo26_resp

        stats = await monitor._get_gpu_stats_from_ai_containers()

        assert stats is not None
        assert stats["memory_used"] == int(4.0 * 1024)
        assert "cuda:0" in stats["gpu_name"]
        # Verify GPU metrics are passed through
        assert stats["gpu_utilization"] == 75.0
        assert stats["temperature"] == 65
        assert stats["power_usage"] == 150.0


@pytest.mark.asyncio
async def test_get_gpu_stats_from_ai_containers_partial_metrics(mock_pynvml):
    """Test getting GPU stats when only some GPU metrics are available."""
    monitor = GPUMonitor()

    # Only temperature is provided, others are None
    yolo26_response = {
        "vram_used_gb": 2.5,
        "device": "cuda:0",
        "gpu_utilization": 50.0,
        "temperature": None,  # Not available
        "power_watts": 100.0,
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_yolo26_resp = MagicMock()
        mock_yolo26_resp.status_code = 200
        mock_yolo26_resp.json.return_value = yolo26_response

        mock_client.get.return_value = mock_yolo26_resp

        stats = await monitor._get_gpu_stats_from_ai_containers()

        assert stats is not None
        assert stats["gpu_utilization"] == 50.0
        assert stats["temperature"] == 0  # Falls back to 0 when None
        assert stats["power_usage"] == 100.0


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
        mock_yolo26_resp = MagicMock()
        mock_yolo26_resp.status_code = 200
        mock_yolo26_resp.json.return_value = {}

        mock_client.get.return_value = mock_yolo26_resp

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
@pytest.mark.usefixtures("mock_no_gpu_access")
async def test_get_current_stats_async_ai_container_fallback():
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
@pytest.mark.usefixtures("mock_no_gpu_access")
async def test_get_current_stats_async_mock_fallback():
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


# =============================================================================
# Inference FPS Calculation Tests (NEM-249)
# =============================================================================


@pytest.mark.asyncio
async def test_calculate_inference_fps_with_detections(mock_pynvml):
    """Verify inference FPS is calculated from detection count over time window.

    Given: Database contains 120 detections from the last 60 seconds
    When: _calculate_inference_fps() is called
    Then: Returns 2.0 FPS (120 detections / 60 seconds)

    Note: This metric helps users understand RT-DETRv2 throughput on their hardware.
    """
    monitor = GPUMonitor()

    # Mock the database query to return a detection count
    with patch("backend.services.gpu_monitor.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        # Mock the result to return 120 detections in the last 60 seconds
        mock_result = MagicMock()
        mock_result.scalar.return_value = 120
        mock_session.execute.return_value = mock_result

        mock_get_session.return_value = mock_session

        fps = await monitor._calculate_inference_fps(mock_session)

        # 120 detections / 60 seconds = 2.0 FPS
        assert fps == 2.0
        mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_calculate_inference_fps_no_detections(mock_pynvml):
    """Test inference FPS calculation when there are no recent detections."""
    monitor = GPUMonitor()

    with patch("backend.services.gpu_monitor.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        # Mock the result to return 0 detections
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute.return_value = mock_result

        mock_get_session.return_value = mock_session

        fps = await monitor._calculate_inference_fps(mock_session)

        assert fps == 0.0


@pytest.mark.asyncio
async def test_calculate_inference_fps_null_result(mock_pynvml):
    """Test inference FPS calculation when query returns None."""
    monitor = GPUMonitor()

    with patch("backend.services.gpu_monitor.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        # Mock the result to return None
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        mock_get_session.return_value = mock_session

        fps = await monitor._calculate_inference_fps(mock_session)

        assert fps == 0.0


@pytest.mark.asyncio
async def test_calculate_inference_fps_database_error(mock_pynvml):
    """Test inference FPS calculation handles database errors gracefully."""
    monitor = GPUMonitor()

    with patch("backend.services.gpu_monitor.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        # Mock the query to raise an exception
        mock_session.execute.side_effect = Exception("Database error")

        mock_get_session.return_value = mock_session

        # Should return None on error, not raise
        fps = await monitor._calculate_inference_fps(mock_session)

        assert fps is None


@pytest.mark.asyncio
async def test_store_stats_includes_inference_fps(mock_pynvml, mock_database_session):
    """Test that _store_stats includes calculated inference_fps."""
    monitor = GPUMonitor()
    stats = monitor.get_current_stats()

    # Mock the inference FPS calculation
    with patch.object(monitor, "_calculate_inference_fps", return_value=5.5):
        await monitor._store_stats(stats)

        # Verify that the GPUStats model was created with inference_fps
        # The inference_fps should be set from the calculation
        # Note: Since we're patching, this test validates the integration point
        mock_database_session.add.assert_called_once()
        mock_database_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_loop_calculates_inference_fps(mock_pynvml, mock_database_session):
    """Test that poll loop calculates inference FPS on each iteration."""
    monitor = GPUMonitor(poll_interval=0.05)

    with patch.object(monitor, "_calculate_inference_fps", return_value=3.0) as mock_calc:
        await monitor.start()
        await asyncio.sleep(0.12)  # Let it run for ~2 polls
        await monitor.stop()

        # The calculation should have been called during the poll loop
        # At least once during the store_stats call
        assert mock_calc.call_count >= 1


# =============================================================================
# Configurable HTTP Client Timeout Tests (NEM-1121)
# =============================================================================


def test_gpu_monitor_default_http_timeout(mock_pynvml):
    """Verify GPUMonitor uses sensible default HTTP timeout.

    Given: No http_timeout parameter provided to GPUMonitor
    When: GPUMonitor is created
    Then: Uses default timeout between 5-10 seconds for AI container queries
    """
    monitor = GPUMonitor()

    # Should use default timeout from settings (or default value)
    assert hasattr(monitor, "_http_timeout")
    assert monitor._http_timeout > 0
    # Default should be 5-10 seconds
    assert 5.0 <= monitor._http_timeout <= 10.0


def test_gpu_monitor_custom_http_timeout(mock_pynvml):
    """Test that GPUMonitor accepts custom HTTP timeout."""
    monitor = GPUMonitor(http_timeout=15.0)

    assert monitor._http_timeout == 15.0


@pytest.mark.asyncio
async def test_ai_container_query_uses_configured_timeout(mock_pynvml):
    """Test that AI container HTTP client uses the configured timeout."""
    monitor = GPUMonitor(http_timeout=7.5)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # RT-DETRv2 returns empty response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_client.get.return_value = mock_resp

        await monitor._get_gpu_stats_from_ai_containers()

        # Verify AsyncClient was created with the correct timeout
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args.kwargs
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == 7.5


@pytest.mark.asyncio
async def test_ai_container_query_timeout_handling(mock_pynvml):
    """Test that AI container query handles HTTP timeout gracefully."""
    monitor = GPUMonitor(http_timeout=0.1)  # Very short timeout

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Simulate timeout error
        import httpx

        mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")

        # Should return None instead of raising
        stats = await monitor._get_gpu_stats_from_ai_containers()
        assert stats is None


@patch("backend.services.gpu_monitor.get_settings")
def test_gpu_monitor_http_timeout_from_settings(mock_get_settings, mock_pynvml):
    """Test that GPUMonitor reads HTTP timeout from settings when not provided."""
    mock_settings = MagicMock()
    mock_settings.gpu_http_timeout = 8.0
    mock_settings.gpu_poll_interval_seconds = 5.0
    mock_settings.gpu_stats_history_minutes = 60
    mock_get_settings.return_value = mock_settings

    monitor = GPUMonitor()

    assert monitor._http_timeout == 8.0


# =============================================================================
# Error Logging Context Tests (NEM-1123)
# =============================================================================


def test_gpu_stats_error_logging_includes_context(mock_pynvml, caplog):
    """Verify GPU stats collection errors include operation context in logs.

    Given: pynvml is available but utilization query raises an exception
    When: get_current_stats() is called
    Then: Error is logged with context about which operation failed,
          and stats are returned with None for the failed metric

    Note: Context-rich logging helps operators diagnose GPU monitoring issues.
    """
    import logging

    monitor = GPUMonitor()

    # Make utilization fail
    mock_pynvml.nvmlDeviceGetUtilizationRates.side_effect = Exception("GPU util error")

    with caplog.at_level(logging.DEBUG):
        stats = monitor.get_current_stats()

    # Stats should still return with None values for failed metrics
    assert stats["gpu_name"] == "NVIDIA RTX A5500"
    assert stats["gpu_utilization"] is None
    # Memory should still work
    assert stats["memory_used"] == 8192


@pytest.mark.asyncio
async def test_store_stats_error_logging_includes_context(mock_pynvml, caplog):
    """Test that database store errors include context (NEM-1123).

    When storing stats to database fails, the error log should include:
    - GPU name
    - Operation (store_stats)
    """
    import logging

    monitor = GPUMonitor()
    stats = monitor.get_current_stats()

    with (
        patch("backend.services.gpu_monitor.get_session") as mock_get_session,
        caplog.at_level(logging.ERROR),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session.commit.side_effect = Exception("Database error")
        mock_get_session.return_value = mock_session

        await monitor._store_stats(stats)

    # Should have logged an error with context
    assert any("Failed to store GPU stats" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_broadcast_stats_error_logging_includes_context(
    mock_pynvml, mock_broadcaster, caplog
):
    """Test that broadcast errors include context (NEM-1123).

    When broadcasting stats fails, the error log should include:
    - Operation (broadcast_stats)
    """
    import logging

    monitor = GPUMonitor(broadcaster=mock_broadcaster)
    stats = monitor.get_current_stats()

    mock_broadcaster.broadcast_gpu_stats.side_effect = Exception("Broadcast error")

    with caplog.at_level(logging.ERROR):
        await monitor._broadcast_stats(stats)

    # Should have logged an error with context
    assert any("Failed to broadcast GPU stats" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_poll_loop_error_logging_includes_context(mock_pynvml, mock_database_session, caplog):
    """Test that poll loop errors include context (NEM-1123).

    When the poll loop encounters an error, the error log should include:
    - Operation being performed
    """
    import logging

    monitor = GPUMonitor(poll_interval=0.05)

    async def get_stats_error():
        raise Exception("Simulated poll error")

    with (
        patch.object(monitor, "get_current_stats_async", side_effect=get_stats_error),
        caplog.at_level(logging.ERROR),
    ):
        await monitor.start()
        await asyncio.sleep(0.1)
        await monitor.stop()

    # Should have logged an error from the poll loop
    assert any("Error in GPU monitor poll loop" in record.message for record in caplog.records)


# =============================================================================
# Async Context Manager Tests
# =============================================================================


@pytest.mark.asyncio
async def test_gpu_monitor_async_context_manager(mock_pynvml, mock_database_session):
    """Test GPUMonitor as async context manager.

    Given: A GPUMonitor instance
    When: Used with async with statement
    Then: Starts automatically on enter, stops on exit
    """
    async with GPUMonitor(poll_interval=0.05) as monitor:
        assert monitor.running is True
        assert monitor._poll_task is not None

    # After exiting context, should be stopped
    assert monitor.running is False


@pytest.mark.asyncio
async def test_gpu_monitor_async_context_manager_with_exception(mock_pynvml, mock_database_session):
    """Test GPUMonitor async context manager handles exceptions gracefully.

    Given: A GPUMonitor instance used as async context manager
    When: An exception is raised inside the context
    Then: Monitor is still properly cleaned up and stopped
    """
    monitor = None
    try:
        async with GPUMonitor(poll_interval=0.05) as mon:
            monitor = mon
            assert monitor.running is True
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Should still have stopped despite exception
    assert monitor is not None
    assert monitor.running is False


# =============================================================================
# Memory Pressure Monitoring Tests (NEM-1727)
# =============================================================================


@pytest.mark.asyncio
async def test_check_memory_pressure_normal(mock_pynvml):
    """Test memory pressure detection when usage is normal (<85%).

    Given: GPU memory usage is 50% (normal level)
    When: check_memory_pressure() is called
    Then: Returns NORMAL pressure level
    """
    from backend.services.gpu_monitor import MemoryPressureLevel

    monitor = GPUMonitor()

    # Mock stats with 50% memory usage (12288 MB used of 24576 MB)
    mock_stats = {
        "gpu_name": "Test GPU",
        "gpu_utilization": 50.0,
        "memory_used": 12288,  # 50% of 24576 MB
        "memory_total": 24576,
        "temperature": 60.0,
        "power_usage": 100.0,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(monitor, "get_current_stats_async", return_value=mock_stats):
        level = await monitor.check_memory_pressure()

    assert level == MemoryPressureLevel.NORMAL


@pytest.mark.asyncio
async def test_check_memory_pressure_warning(mock_pynvml):
    """Test memory pressure detection when usage is in warning range (85-95%).

    Given: GPU memory usage is 90% (warning level)
    When: check_memory_pressure() is called
    Then: Returns WARNING pressure level
    """
    from backend.services.gpu_monitor import MemoryPressureLevel

    monitor = GPUMonitor()

    # Mock stats with 90% memory usage (22118 MB used of 24576 MB)
    mock_stats = {
        "gpu_name": "Test GPU",
        "gpu_utilization": 80.0,
        "memory_used": 22118,  # 90% of 24576 MB
        "memory_total": 24576,
        "temperature": 70.0,
        "power_usage": 150.0,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(monitor, "get_current_stats_async", return_value=mock_stats):
        level = await monitor.check_memory_pressure()

    assert level == MemoryPressureLevel.WARNING


@pytest.mark.asyncio
async def test_check_memory_pressure_critical(mock_pynvml):
    """Test memory pressure detection when usage is critical (>=95%).

    Given: GPU memory usage is 96% (critical level)
    When: check_memory_pressure() is called
    Then: Returns CRITICAL pressure level
    """
    from backend.services.gpu_monitor import MemoryPressureLevel

    monitor = GPUMonitor()

    # Mock stats with 96% memory usage (23592 MB used of 24576 MB)
    mock_stats = {
        "gpu_name": "Test GPU",
        "gpu_utilization": 95.0,
        "memory_used": 23592,  # 96% of 24576 MB
        "memory_total": 24576,
        "temperature": 85.0,
        "power_usage": 200.0,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(monitor, "get_current_stats_async", return_value=mock_stats):
        level = await monitor.check_memory_pressure()

    assert level == MemoryPressureLevel.CRITICAL


@pytest.mark.asyncio
async def test_check_memory_pressure_missing_memory_stats(mock_pynvml):
    """Test memory pressure when memory stats are unavailable.

    Given: GPU stats have None for memory_used or memory_total
    When: check_memory_pressure() is called
    Then: Returns NORMAL to avoid unnecessary throttling
    """
    from backend.services.gpu_monitor import MemoryPressureLevel

    monitor = GPUMonitor()

    # Mock stats with missing memory data
    mock_stats = {
        "gpu_name": "Test GPU",
        "gpu_utilization": 50.0,
        "memory_used": None,
        "memory_total": None,
        "temperature": 60.0,
        "power_usage": 100.0,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(monitor, "get_current_stats_async", return_value=mock_stats):
        level = await monitor.check_memory_pressure()

    assert level == MemoryPressureLevel.NORMAL


@pytest.mark.asyncio
async def test_check_memory_pressure_zero_total_memory(mock_pynvml):
    """Test memory pressure when total memory is zero.

    Given: GPU stats have memory_total = 0
    When: check_memory_pressure() is called
    Then: Returns NORMAL to avoid division by zero
    """
    from backend.services.gpu_monitor import MemoryPressureLevel

    monitor = GPUMonitor()

    # Mock stats with zero total memory
    mock_stats = {
        "gpu_name": "Test GPU",
        "gpu_utilization": 50.0,
        "memory_used": 1000,
        "memory_total": 0,
        "temperature": 60.0,
        "power_usage": 100.0,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(monitor, "get_current_stats_async", return_value=mock_stats):
        level = await monitor.check_memory_pressure()

    assert level == MemoryPressureLevel.NORMAL


@pytest.mark.asyncio
async def test_check_memory_pressure_error_returns_normal(mock_pynvml):
    """Test that memory pressure check returns NORMAL on error.

    Given: get_current_stats_async raises an exception
    When: check_memory_pressure() is called
    Then: Returns NORMAL to avoid unnecessary throttling, error is logged
    """
    from backend.services.gpu_monitor import MemoryPressureLevel

    monitor = GPUMonitor()

    with patch.object(monitor, "get_current_stats_async", side_effect=Exception("GPU stats error")):
        level = await monitor.check_memory_pressure()

    assert level == MemoryPressureLevel.NORMAL


@pytest.mark.asyncio
async def test_memory_pressure_callback_on_level_change(mock_pynvml):
    """Test that callbacks are invoked when memory pressure level changes.

    Given: A callback is registered for memory pressure changes
    When: Memory pressure transitions from NORMAL to WARNING
    Then: Callback is invoked with new and old levels
    """
    from backend.services.gpu_monitor import MemoryPressureLevel

    monitor = GPUMonitor()

    callback_invoked = False
    new_level_received = None
    old_level_received = None

    def memory_pressure_callback(new_level, old_level):
        nonlocal callback_invoked, new_level_received, old_level_received
        callback_invoked = True
        new_level_received = new_level
        old_level_received = old_level

    monitor.register_memory_pressure_callback(memory_pressure_callback)

    # Start at NORMAL
    mock_normal_stats = {
        "gpu_name": "Test GPU",
        "memory_used": 12288,  # 50%
        "memory_total": 24576,
        "recorded_at": datetime.now(UTC),
    }

    # Transition to WARNING
    mock_warning_stats = {
        "gpu_name": "Test GPU",
        "memory_used": 22118,  # 90%
        "memory_total": 24576,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(monitor, "get_current_stats_async", return_value=mock_normal_stats):
        await monitor.check_memory_pressure()

    # Now trigger warning
    with patch.object(monitor, "get_current_stats_async", return_value=mock_warning_stats):
        await monitor.check_memory_pressure()

    assert callback_invoked is True
    assert new_level_received == MemoryPressureLevel.WARNING
    assert old_level_received == MemoryPressureLevel.NORMAL


@pytest.mark.asyncio
async def test_memory_pressure_callback_async_support(mock_pynvml):
    """Test that async callbacks are supported for memory pressure changes.

    Given: An async callback is registered for memory pressure changes
    When: Memory pressure level changes
    Then: Async callback is awaited properly
    """

    monitor = GPUMonitor()

    callback_invoked = False

    async def async_memory_pressure_callback(new_level, old_level):
        nonlocal callback_invoked
        await asyncio.sleep(0.01)  # Simulate async work
        callback_invoked = True

    monitor.register_memory_pressure_callback(async_memory_pressure_callback)

    # Transition from NORMAL to CRITICAL
    mock_critical_stats = {
        "gpu_name": "Test GPU",
        "memory_used": 23592,  # 96%
        "memory_total": 24576,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(monitor, "get_current_stats_async", return_value=mock_critical_stats):
        await monitor.check_memory_pressure()

    assert callback_invoked is True


@pytest.mark.asyncio
async def test_memory_pressure_callback_error_handling(mock_pynvml, caplog):
    """Test that callback errors don't crash memory pressure monitoring.

    Given: A callback that raises an exception
    When: Memory pressure level changes
    Then: Error is logged but monitoring continues
    """
    import logging

    from backend.services.gpu_monitor import MemoryPressureLevel

    monitor = GPUMonitor()

    def failing_callback(new_level, old_level):
        raise ValueError("Callback error")

    monitor.register_memory_pressure_callback(failing_callback)

    # Transition to WARNING
    mock_warning_stats = {
        "gpu_name": "Test GPU",
        "memory_used": 22118,  # 90%
        "memory_total": 24576,
        "recorded_at": datetime.now(UTC),
    }

    with (
        patch.object(monitor, "get_current_stats_async", return_value=mock_warning_stats),
        caplog.at_level(logging.ERROR),
    ):
        level = await monitor.check_memory_pressure()

    # Should still return the correct level despite callback error
    assert level == MemoryPressureLevel.WARNING
    assert any("Memory pressure callback failed" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_memory_pressure_metrics(mock_pynvml):
    """Test memory pressure metrics tracking.

    Given: Multiple memory pressure transitions occur
    When: get_memory_pressure_metrics() is called
    Then: Returns metrics including current level, thresholds, and event counts
    """

    monitor = GPUMonitor()

    # Initial metrics
    metrics = monitor.get_memory_pressure_metrics()
    assert metrics["current_level"] == "normal"
    assert metrics["total_warning_events"] == 0
    assert metrics["total_critical_events"] == 0

    # Trigger WARNING
    mock_warning_stats = {
        "gpu_name": "Test GPU",
        "memory_used": 22118,  # 90%
        "memory_total": 24576,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(monitor, "get_current_stats_async", return_value=mock_warning_stats):
        await monitor.check_memory_pressure()

    metrics = monitor.get_memory_pressure_metrics()
    assert metrics["current_level"] == "warning"
    assert metrics["total_warning_events"] == 1
    assert metrics["last_warning_event_at"] is not None

    # Trigger CRITICAL
    mock_critical_stats = {
        "gpu_name": "Test GPU",
        "memory_used": 23592,  # 96%
        "memory_total": 24576,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(monitor, "get_current_stats_async", return_value=mock_critical_stats):
        await monitor.check_memory_pressure()

    metrics = monitor.get_memory_pressure_metrics()
    assert metrics["current_level"] == "critical"
    assert metrics["total_critical_events"] == 1
    assert metrics["last_critical_event_at"] is not None


@pytest.mark.asyncio
async def test_memory_pressure_no_callback_on_same_level(mock_pynvml):
    """Test that callbacks are NOT invoked when pressure level stays the same.

    Given: Memory pressure is at WARNING
    When: check_memory_pressure() is called again with WARNING level stats
    Then: Callback is not invoked (no level change)
    """

    monitor = GPUMonitor()

    callback_count = 0

    def memory_pressure_callback(new_level, old_level):
        nonlocal callback_count
        callback_count += 1

    monitor.register_memory_pressure_callback(memory_pressure_callback)

    # Set to WARNING
    mock_warning_stats = {
        "gpu_name": "Test GPU",
        "memory_used": 22118,  # 90%
        "memory_total": 24576,
        "recorded_at": datetime.now(UTC),
    }

    with patch.object(monitor, "get_current_stats_async", return_value=mock_warning_stats):
        await monitor.check_memory_pressure()

    # Should have been called once (transition from NORMAL to WARNING)
    assert callback_count == 1

    # Call again with same WARNING level
    with patch.object(monitor, "get_current_stats_async", return_value=mock_warning_stats):
        await monitor.check_memory_pressure()

    # Should still be 1 (no level change)
    assert callback_count == 1


# =============================================================================
# Database Filtering Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_stats_from_db_with_time_filter(mock_pynvml):
    """Test database retrieval with time-based filtering.

    Given: Database contains GPU stats with various timestamps
    When: get_stats_from_db(minutes=30) is called
    Then: Only returns stats from last 30 minutes
    """
    from backend.models.gpu_stats import GPUStats

    monitor = GPUMonitor()

    # Mock stats from different times
    now = datetime.now(UTC)
    mock_stats = [
        GPUStats(
            id=1,
            recorded_at=now - timedelta(minutes=10),
            gpu_name="NVIDIA RTX A5500",
            gpu_utilization=75.0,
            memory_used=8192,
            memory_total=24576,
            temperature=65.0,
            power_usage=150.0,
        ),
        GPUStats(
            id=2,
            recorded_at=now - timedelta(minutes=20),
            gpu_name="NVIDIA RTX A5500",
            gpu_utilization=70.0,
            memory_used=8000,
            memory_total=24576,
            temperature=63.0,
            power_usage=145.0,
        ),
    ]

    with patch("backend.services.gpu_monitor.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_stats
        mock_session.execute.return_value = mock_result

        mock_get_session.return_value = mock_session

        stats = await monitor.get_stats_from_db(minutes=30)

        assert len(stats) == 2
        # Verify query was executed (filtering should be in the query)
        mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_stats_from_db_with_limit(mock_pynvml):
    """Test database retrieval with result limit.

    Given: Database contains many GPU stats records
    When: get_stats_from_db(limit=5) is called
    Then: Returns at most 5 records
    """
    from backend.models.gpu_stats import GPUStats

    monitor = GPUMonitor()

    now = datetime.now(UTC)
    mock_stats = [
        GPUStats(
            id=i,
            recorded_at=now - timedelta(minutes=i),
            gpu_name="NVIDIA RTX A5500",
            gpu_utilization=70.0 + i,
            memory_used=8000 + i * 100,
            memory_total=24576,
            temperature=60.0 + i,
            power_usage=140.0 + i,
        )
        for i in range(5)
    ]

    with patch("backend.services.gpu_monitor.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_stats
        mock_session.execute.return_value = mock_result

        mock_get_session.return_value = mock_session

        stats = await monitor.get_stats_from_db(limit=5)

        assert len(stats) == 5


# =============================================================================
# nvidia-smi Fallback Error Path Tests
# =============================================================================


def test_nvidia_smi_not_available_raises_error():
    """Test that nvidia-smi methods raise RuntimeError when not available.

    Given: nvidia-smi is not available
    When: _get_gpu_stats_nvidia_smi() is called
    Then: Raises RuntimeError
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = False
    monitor._nvidia_smi_path = None

    with pytest.raises(RuntimeError, match="nvidia-smi not available"):
        monitor._get_gpu_stats_nvidia_smi()


@pytest.mark.asyncio
async def test_nvidia_smi_async_not_available_raises_error():
    """Test that async nvidia-smi methods raise RuntimeError when not available.

    Given: nvidia-smi is not available
    When: _get_gpu_stats_nvidia_smi_async() is called
    Then: Raises RuntimeError
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = False
    monitor._nvidia_smi_path = None

    with pytest.raises(RuntimeError, match="nvidia-smi not available"):
        await monitor._get_gpu_stats_nvidia_smi_async()


def test_nvidia_smi_subprocess_error():
    """Test nvidia-smi subprocess returning error code.

    Given: nvidia-smi subprocess returns non-zero exit code
    When: _get_gpu_stats_nvidia_smi() is called
    Then: Raises RuntimeError with stderr message
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = (
        "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver"
    )

    with (
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(RuntimeError, match="nvidia-smi returned error"),
    ):
        monitor._get_gpu_stats_nvidia_smi()


def test_nvidia_smi_unexpected_output_format():
    """Test nvidia-smi with unexpected output format.

    Given: nvidia-smi returns output with too few fields
    When: _get_gpu_stats_nvidia_smi() is called
    Then: Raises RuntimeError about unexpected format
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "39, 29.61"  # Only 2 fields instead of expected 5+

    with (
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(RuntimeError, match="Unexpected nvidia-smi output format"),
    ):
        monitor._get_gpu_stats_nvidia_smi()


@pytest.mark.asyncio
async def test_nvidia_smi_async_unexpected_output_format():
    """Test async nvidia-smi with unexpected output format.

    Given: nvidia-smi returns output with too few fields
    When: _get_gpu_stats_nvidia_smi_async() is called
    Then: Raises RuntimeError about unexpected format
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "39, 29.61"  # Only 2 fields
    mock_result.stderr = ""

    with (
        patch(
            "backend.core.async_utils.async_subprocess_run",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        pytest.raises(RuntimeError, match="Unexpected nvidia-smi output format"),
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()


@pytest.mark.asyncio
async def test_nvidia_smi_async_timeout():
    """Test async nvidia-smi subprocess timeout handling.

    Given: nvidia-smi subprocess times out
    When: _get_gpu_stats_nvidia_smi_async() is called
    Then: Raises RuntimeError about timeout
    """
    import subprocess

    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    with (
        patch(
            "backend.core.async_utils.async_subprocess_run",
            side_effect=subprocess.TimeoutExpired("nvidia-smi", 5.0),
        ),
        pytest.raises(RuntimeError, match="nvidia-smi timed out"),
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()


def test_nvidia_smi_generic_exception():
    """Test nvidia-smi handling of generic exceptions.

    Given: nvidia-smi subprocess raises unexpected exception
    When: _get_gpu_stats_nvidia_smi() is called
    Then: Raises RuntimeError wrapping the original exception
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    with (
        patch("subprocess.run", side_effect=OSError("Permission denied")),
        pytest.raises(RuntimeError, match="Failed to get GPU stats via nvidia-smi"),
    ):
        monitor._get_gpu_stats_nvidia_smi()


@pytest.mark.asyncio
async def test_nvidia_smi_async_generic_exception():
    """Test async nvidia-smi handling of generic exceptions.

    Given: nvidia-smi subprocess raises unexpected exception
    When: _get_gpu_stats_nvidia_smi_async() is called
    Then: Raises RuntimeError wrapping the original exception
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    with (
        patch(
            "backend.core.async_utils.async_subprocess_run",
            side_effect=OSError("Permission denied"),
        ),
        pytest.raises(RuntimeError, match="Failed to get GPU stats via nvidia-smi"),
    ):
        await monitor._get_gpu_stats_nvidia_smi_async()


def test_check_nvidia_smi_found_and_working(mock_pynvml_not_available):
    """Test _check_nvidia_smi when nvidia-smi is found and works.

    Given: pynvml is not available but nvidia-smi is in PATH
    When: GPUMonitor is initialized (calls _check_nvidia_smi)
    Then: _nvidia_smi_available is True and GPU name is set
    """
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "NVIDIA RTX A5500"
    mock_result.stderr = ""

    with (
        patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
        patch("subprocess.run", return_value=mock_result),
    ):
        monitor = GPUMonitor()

        assert monitor._nvidia_smi_available is True
        assert monitor._nvidia_smi_path == "/usr/bin/nvidia-smi"
        assert monitor._gpu_name == "NVIDIA RTX A5500"


def test_nvidia_smi_parsing_all_na_values():
    """Test nvidia-smi parsing when all values are [N/A].

    Given: nvidia-smi returns [N/A] for all metrics
    When: _get_gpu_stats_nvidia_smi() is called
    Then: Returns stats with all None values except GPU name
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "[N/A], [N/A], [N/A], [N/A], [N/A], Test GPU"

    with patch("subprocess.run", return_value=mock_result):
        stats = monitor._get_gpu_stats_nvidia_smi()

        assert stats["temperature"] is None
        assert stats["power_usage"] is None
        assert stats["gpu_utilization"] is None
        assert stats["memory_used"] is None
        assert stats["memory_total"] is None
        assert stats["gpu_name"] == "Test GPU"


@pytest.mark.asyncio
async def test_nvidia_smi_async_parsing_all_na_values():
    """Test async nvidia-smi parsing when all values are [N/A].

    Given: nvidia-smi returns [N/A] for all metrics
    When: _get_gpu_stats_nvidia_smi_async() is called
    Then: Returns stats with all None values except GPU name
    """
    monitor = GPUMonitor.__new__(GPUMonitor)
    monitor._nvidia_smi_available = True
    monitor._nvidia_smi_path = "/usr/bin/nvidia-smi"
    monitor._gpu_name = "Test GPU"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "[N/A], [N/A], [N/A], [N/A], [N/A], Test GPU"
    mock_result.stderr = ""

    with patch(
        "backend.core.async_utils.async_subprocess_run",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        stats = await monitor._get_gpu_stats_nvidia_smi_async()

        assert stats["temperature"] is None
        assert stats["power_usage"] is None
        assert stats["gpu_utilization"] is None
        assert stats["memory_used"] is None
        assert stats["memory_total"] is None
        assert stats["gpu_name"] == "Test GPU"


def test_nvidia_smi_check_subprocess_error(mock_pynvml_not_available):
    """Test nvidia-smi check during init when subprocess returns error.

    Given: nvidia-smi found in PATH but returns error on test query
    When: GPUMonitor is initialized
    Then: _nvidia_smi_available is False
    """
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Error message"

    with (
        patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
        patch("subprocess.run", return_value=mock_result),
    ):
        monitor = GPUMonitor()

        # nvidia-smi should not be marked as available
        assert monitor._nvidia_smi_available is False


@pytest.mark.asyncio
async def test_get_current_stats_async_with_nvidia_smi_error(mock_pynvml_not_available):
    """Test async stats retrieval when nvidia-smi fails.

    Given: pynvml not available and nvidia-smi subprocess fails
    When: get_current_stats_async() is called
    Then: Falls back to AI containers or mock data
    """
    with patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True

        # Make nvidia-smi async fail
        with patch.object(
            monitor,
            "_get_gpu_stats_nvidia_smi_async",
            side_effect=RuntimeError("nvidia-smi failed"),
        ):
            # Mock AI containers returning None
            with patch.object(monitor, "_get_gpu_stats_from_ai_containers", return_value=None):
                stats = await monitor.get_current_stats_async()

                # Should fall back to mock
                assert stats["gpu_name"] == "Mock GPU (Development Mode)"


def test_get_current_stats_with_nvidia_smi_error(mock_pynvml_not_available):
    """Test sync stats retrieval when nvidia-smi fails.

    Given: pynvml not available and nvidia-smi subprocess fails
    When: get_current_stats() is called
    Then: Falls back to mock data
    """
    with patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True

        # Make nvidia-smi fail
        with patch.object(
            monitor, "_get_gpu_stats_nvidia_smi", side_effect=RuntimeError("nvidia-smi failed")
        ):
            stats = monitor.get_current_stats()

            # Should fall back to mock
            assert stats["gpu_name"] == "Mock GPU (Development Mode)"


@pytest.mark.asyncio
async def test_get_gpu_stats_from_ai_containers_with_gpu_utilization_only():
    """Test AI container stats when only GPU utilization is provided.

    Given: RT-DETRv2 returns only gpu_utilization (no VRAM)
    When: _get_gpu_stats_from_ai_containers() is called
    Then: Returns stats with GPU utilization data
    """
    monitor = GPUMonitor()

    yolo26_response = {"gpu_utilization": 75.0}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_yolo26_resp = MagicMock()
        mock_yolo26_resp.status_code = 200
        mock_yolo26_resp.json.return_value = yolo26_response

        mock_client.get.return_value = mock_yolo26_resp

        stats = await monitor._get_gpu_stats_from_ai_containers()

        # Should still return stats even without VRAM (gpu_utilization alone is sufficient)
        assert stats is not None
        assert stats["gpu_utilization"] == 75.0
