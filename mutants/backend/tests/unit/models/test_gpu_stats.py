"""Unit tests for GPUStats model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- GPU metrics fields
- Inference performance tracking
- Property-based tests for field values
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.gpu_stats import GPUStats

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for GPU utilization (0-100%)
gpu_utilization = st.floats(min_value=0.0, max_value=100.0, allow_nan=False)

# Strategy for temperature (reasonable GPU temp range)
temperature = st.floats(min_value=0.0, max_value=150.0, allow_nan=False)

# Strategy for power usage in watts
power_usage = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False)

# Strategy for memory in bytes (up to 128GB)
memory_bytes = st.integers(min_value=0, max_value=128 * 1024 * 1024 * 1024)

# Strategy for inference FPS
inference_fps = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False)

# Strategy for GPU names
gpu_names = st.sampled_from(
    [
        "NVIDIA RTX A5500",
        "NVIDIA RTX 4090",
        "NVIDIA RTX 3080",
        "NVIDIA Tesla V100",
        "NVIDIA A100",
        "AMD Radeon RX 7900 XTX",
    ]
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_gpu_stats():
    """Create sample GPU stats for testing."""
    return GPUStats(
        id=1,
        recorded_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        gpu_name="NVIDIA RTX A5500",
        gpu_utilization=85.5,
        memory_used=12000000000,  # 12GB
        memory_total=24000000000,  # 24GB
        temperature=72.0,
        power_usage=200.0,
        inference_fps=45.0,
    )


@pytest.fixture
def minimal_gpu_stats():
    """Create GPU stats with minimal fields."""
    return GPUStats()


@pytest.fixture
def idle_gpu_stats():
    """Create GPU stats for idle state."""
    return GPUStats(
        gpu_name="NVIDIA RTX A5500",
        gpu_utilization=0.0,
        memory_used=500000000,  # 500MB baseline
        memory_total=24000000000,
        temperature=35.0,
        power_usage=25.0,
        inference_fps=0.0,
    )


@pytest.fixture
def high_load_gpu_stats():
    """Create GPU stats for high load state."""
    return GPUStats(
        gpu_name="NVIDIA RTX A5500",
        gpu_utilization=98.5,
        memory_used=23000000000,  # Almost full
        memory_total=24000000000,
        temperature=85.0,
        power_usage=350.0,
        inference_fps=120.0,
    )


# =============================================================================
# GPUStats Model Initialization Tests
# =============================================================================


class TestGPUStatsModelInitialization:
    """Tests for GPUStats model initialization."""

    def test_gpu_stats_creation_minimal(self):
        """Test creating GPU stats with minimal fields."""
        stats = GPUStats()
        # All optional fields should be None
        assert stats.gpu_name is None
        assert stats.gpu_utilization is None
        assert stats.memory_used is None
        assert stats.memory_total is None
        assert stats.temperature is None
        assert stats.power_usage is None
        assert stats.inference_fps is None

    def test_gpu_stats_with_all_fields(self, sample_gpu_stats):
        """Test GPU stats with all fields populated."""
        assert sample_gpu_stats.id == 1
        assert sample_gpu_stats.gpu_name == "NVIDIA RTX A5500"
        assert sample_gpu_stats.gpu_utilization == 85.5
        assert sample_gpu_stats.memory_used == 12000000000
        assert sample_gpu_stats.memory_total == 24000000000
        assert sample_gpu_stats.temperature == 72.0
        assert sample_gpu_stats.power_usage == 200.0
        assert sample_gpu_stats.inference_fps == 45.0

    def test_gpu_stats_all_fields_optional(self, minimal_gpu_stats):
        """Test all GPU stats fields are optional."""
        assert minimal_gpu_stats.gpu_name is None
        assert minimal_gpu_stats.gpu_utilization is None
        assert minimal_gpu_stats.memory_used is None
        assert minimal_gpu_stats.memory_total is None
        assert minimal_gpu_stats.temperature is None
        assert minimal_gpu_stats.power_usage is None
        assert minimal_gpu_stats.inference_fps is None


# =============================================================================
# GPUStats Field Tests
# =============================================================================


class TestGPUStatsGPUName:
    """Tests for GPUStats gpu_name field."""

    def test_gpu_name_nvidia(self, sample_gpu_stats):
        """Test NVIDIA GPU name."""
        assert sample_gpu_stats.gpu_name == "NVIDIA RTX A5500"

    def test_gpu_name_various(self):
        """Test various GPU names."""
        names = [
            "NVIDIA RTX 4090",
            "NVIDIA Tesla V100",
            "AMD Radeon RX 7900 XTX",
            "Intel Arc A770",
        ]
        for name in names:
            stats = GPUStats(gpu_name=name)
            assert stats.gpu_name == name

    def test_gpu_name_long(self):
        """Test GPU name with max length."""
        long_name = "A" * 255
        stats = GPUStats(gpu_name=long_name)
        assert stats.gpu_name == long_name


class TestGPUStatsUtilization:
    """Tests for GPUStats gpu_utilization field."""

    def test_utilization_normal(self, sample_gpu_stats):
        """Test normal utilization value."""
        assert sample_gpu_stats.gpu_utilization == 85.5

    def test_utilization_zero(self, idle_gpu_stats):
        """Test zero utilization."""
        assert idle_gpu_stats.gpu_utilization == 0.0

    def test_utilization_full(self):
        """Test 100% utilization."""
        stats = GPUStats(gpu_utilization=100.0)
        assert stats.gpu_utilization == 100.0

    def test_utilization_high(self, high_load_gpu_stats):
        """Test high utilization value."""
        assert high_load_gpu_stats.gpu_utilization == 98.5

    def test_utilization_fractional(self):
        """Test fractional utilization value."""
        stats = GPUStats(gpu_utilization=33.33)
        assert stats.gpu_utilization == 33.33


class TestGPUStatsMemory:
    """Tests for GPUStats memory fields."""

    def test_memory_values(self, sample_gpu_stats):
        """Test memory used and total values."""
        assert sample_gpu_stats.memory_used == 12000000000
        assert sample_gpu_stats.memory_total == 24000000000

    def test_memory_zero_used(self):
        """Test zero memory used."""
        stats = GPUStats(memory_used=0, memory_total=24000000000)
        assert stats.memory_used == 0

    def test_memory_full_utilization(self):
        """Test memory at full utilization."""
        stats = GPUStats(memory_used=24000000000, memory_total=24000000000)
        assert stats.memory_used == stats.memory_total

    def test_memory_large_values(self):
        """Test large memory values (128GB)."""
        total = 128 * 1024 * 1024 * 1024  # 128GB
        stats = GPUStats(memory_used=total // 2, memory_total=total)
        assert stats.memory_total == total


class TestGPUStatsTemperature:
    """Tests for GPUStats temperature field."""

    def test_temperature_normal(self, sample_gpu_stats):
        """Test normal temperature value."""
        assert sample_gpu_stats.temperature == 72.0

    def test_temperature_idle(self, idle_gpu_stats):
        """Test idle temperature."""
        assert idle_gpu_stats.temperature == 35.0

    def test_temperature_high_load(self, high_load_gpu_stats):
        """Test high load temperature."""
        assert high_load_gpu_stats.temperature == 85.0

    def test_temperature_zero(self):
        """Test temperature of zero (edge case)."""
        stats = GPUStats(temperature=0.0)
        assert stats.temperature == 0.0

    def test_temperature_fractional(self):
        """Test fractional temperature."""
        stats = GPUStats(temperature=65.7)
        assert stats.temperature == 65.7


class TestGPUStatsPowerUsage:
    """Tests for GPUStats power_usage field."""

    def test_power_normal(self, sample_gpu_stats):
        """Test normal power usage."""
        assert sample_gpu_stats.power_usage == 200.0

    def test_power_idle(self, idle_gpu_stats):
        """Test idle power usage."""
        assert idle_gpu_stats.power_usage == 25.0

    def test_power_high_load(self, high_load_gpu_stats):
        """Test high load power usage."""
        assert high_load_gpu_stats.power_usage == 350.0

    def test_power_zero(self):
        """Test zero power usage (GPU off)."""
        stats = GPUStats(power_usage=0.0)
        assert stats.power_usage == 0.0


class TestGPUStatsInferenceFPS:
    """Tests for GPUStats inference_fps field."""

    def test_fps_normal(self, sample_gpu_stats):
        """Test normal inference FPS."""
        assert sample_gpu_stats.inference_fps == 45.0

    def test_fps_zero(self, idle_gpu_stats):
        """Test zero FPS when idle."""
        assert idle_gpu_stats.inference_fps == 0.0

    def test_fps_high(self, high_load_gpu_stats):
        """Test high FPS value."""
        assert high_load_gpu_stats.inference_fps == 120.0

    def test_fps_fractional(self):
        """Test fractional FPS value."""
        stats = GPUStats(inference_fps=30.5)
        assert stats.inference_fps == 30.5


class TestGPUStatsRecordedAt:
    """Tests for GPUStats recorded_at field."""

    def test_recorded_at_set(self, sample_gpu_stats):
        """Test recorded_at timestamp is set."""
        assert sample_gpu_stats.recorded_at == datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)

    def test_recorded_at_has_field(self, minimal_gpu_stats):
        """Test GPU stats has recorded_at field."""
        assert hasattr(minimal_gpu_stats, "recorded_at")


# =============================================================================
# GPUStats Repr Tests
# =============================================================================


class TestGPUStatsRepr:
    """Tests for GPUStats string representation."""

    def test_gpu_stats_repr_contains_class_name(self, sample_gpu_stats):
        """Test repr contains class name."""
        repr_str = repr(sample_gpu_stats)
        assert "GPUStats" in repr_str

    def test_gpu_stats_repr_contains_id(self, sample_gpu_stats):
        """Test repr contains GPU stats id."""
        repr_str = repr(sample_gpu_stats)
        assert "id=1" in repr_str

    def test_gpu_stats_repr_contains_gpu_name(self, sample_gpu_stats):
        """Test repr contains GPU name."""
        repr_str = repr(sample_gpu_stats)
        assert "NVIDIA RTX A5500" in repr_str

    def test_gpu_stats_repr_contains_utilization(self, sample_gpu_stats):
        """Test repr contains GPU utilization."""
        repr_str = repr(sample_gpu_stats)
        assert "85.5%" in repr_str

    def test_gpu_stats_repr_contains_temperature(self, sample_gpu_stats):
        """Test repr contains temperature."""
        repr_str = repr(sample_gpu_stats)
        # Temperature is shown in repr
        assert "72.0" in repr_str

    def test_gpu_stats_repr_contains_power(self, sample_gpu_stats):
        """Test repr contains power usage."""
        repr_str = repr(sample_gpu_stats)
        assert "200.0" in repr_str

    def test_gpu_stats_repr_format(self, sample_gpu_stats):
        """Test repr has expected format."""
        repr_str = repr(sample_gpu_stats)
        assert repr_str.startswith("<GPUStats(")
        assert repr_str.endswith(")>")


# =============================================================================
# GPUStats Table Args Tests
# =============================================================================


class TestGPUStatsTableArgs:
    """Tests for GPUStats table arguments (indexes)."""

    def test_gpu_stats_has_table_args(self):
        """Test GPUStats model has __table_args__."""
        assert hasattr(GPUStats, "__table_args__")

    def test_gpu_stats_tablename(self):
        """Test GPUStats has correct table name."""
        assert GPUStats.__tablename__ == "gpu_stats"


# =============================================================================
# Property-based Tests
# =============================================================================


class TestGPUStatsProperties:
    """Property-based tests for GPUStats model."""

    @given(utilization=gpu_utilization)
    @settings(max_examples=50)
    def test_utilization_roundtrip(self, utilization: float):
        """Property: GPU utilization values roundtrip correctly."""
        stats = GPUStats(gpu_utilization=utilization)
        assert abs(stats.gpu_utilization - utilization) < 1e-10

    @given(temp=temperature)
    @settings(max_examples=50)
    def test_temperature_roundtrip(self, temp: float):
        """Property: Temperature values roundtrip correctly."""
        stats = GPUStats(temperature=temp)
        assert abs(stats.temperature - temp) < 1e-10

    @given(power=power_usage)
    @settings(max_examples=50)
    def test_power_usage_roundtrip(self, power: float):
        """Property: Power usage values roundtrip correctly."""
        stats = GPUStats(power_usage=power)
        assert abs(stats.power_usage - power) < 1e-10

    @given(memory=memory_bytes)
    @settings(max_examples=50)
    def test_memory_used_roundtrip(self, memory: int):
        """Property: Memory used values roundtrip correctly."""
        stats = GPUStats(memory_used=memory)
        assert stats.memory_used == memory

    @given(memory=memory_bytes)
    @settings(max_examples=50)
    def test_memory_total_roundtrip(self, memory: int):
        """Property: Memory total values roundtrip correctly."""
        stats = GPUStats(memory_total=memory)
        assert stats.memory_total == memory

    @given(fps=inference_fps)
    @settings(max_examples=50)
    def test_inference_fps_roundtrip(self, fps: float):
        """Property: Inference FPS values roundtrip correctly."""
        stats = GPUStats(inference_fps=fps)
        assert abs(stats.inference_fps - fps) < 1e-10

    @given(name=gpu_names)
    @settings(max_examples=10)
    def test_gpu_name_roundtrip(self, name: str):
        """Property: GPU name values roundtrip correctly."""
        stats = GPUStats(gpu_name=name)
        assert stats.gpu_name == name

    @given(
        utilization=gpu_utilization,
        temp=temperature,
        power=power_usage,
        fps=inference_fps,
    )
    @settings(max_examples=50)
    def test_all_float_fields_roundtrip(
        self, utilization: float, temp: float, power: float, fps: float
    ):
        """Property: All float fields roundtrip correctly together."""
        stats = GPUStats(
            gpu_utilization=utilization,
            temperature=temp,
            power_usage=power,
            inference_fps=fps,
        )
        assert abs(stats.gpu_utilization - utilization) < 1e-10
        assert abs(stats.temperature - temp) < 1e-10
        assert abs(stats.power_usage - power) < 1e-10
        assert abs(stats.inference_fps - fps) < 1e-10


class TestGPUStatsMetricRanges:
    """Property-based tests for GPU metric ranges."""

    @given(utilization=gpu_utilization)
    @settings(max_examples=50)
    def test_utilization_in_valid_range(self, utilization: float):
        """Property: Utilization is always in 0-100 range."""
        stats = GPUStats(gpu_utilization=utilization)
        assert 0.0 <= stats.gpu_utilization <= 100.0

    @given(memory_used=memory_bytes, memory_total=memory_bytes)
    @settings(max_examples=50)
    def test_memory_values_non_negative(self, memory_used: int, memory_total: int):
        """Property: Memory values are non-negative."""
        stats = GPUStats(memory_used=memory_used, memory_total=memory_total)
        assert stats.memory_used >= 0
        assert stats.memory_total >= 0

    @given(temp=temperature)
    @settings(max_examples=50)
    def test_temperature_non_negative(self, temp: float):
        """Property: Temperature is non-negative."""
        stats = GPUStats(temperature=temp)
        assert stats.temperature >= 0.0

    @given(power=power_usage)
    @settings(max_examples=50)
    def test_power_non_negative(self, power: float):
        """Property: Power usage is non-negative."""
        stats = GPUStats(power_usage=power)
        assert stats.power_usage >= 0.0

    @given(fps=inference_fps)
    @settings(max_examples=50)
    def test_fps_non_negative(self, fps: float):
        """Property: Inference FPS is non-negative."""
        stats = GPUStats(inference_fps=fps)
        assert stats.inference_fps >= 0.0
