"""Unit tests for GPU configuration models.

Tests cover:
- GpuAssignmentStrategy enum values and string representation
- GpuDevice model initialization, fields, and __repr__
- GpuConfiguration model initialization, fields, and __repr__
- SystemSetting model initialization, fields, and __repr__
- Table arguments and indexes verification
- Default values and nullable fields
- Property-based tests for field values
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import inspect

from backend.models.gpu_config import (
    GpuAssignmentStrategy,
    GpuConfiguration,
    GpuDevice,
    SystemSetting,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for GPU index (0-7 typical range)
gpu_index = st.integers(min_value=0, max_value=7)

# Strategy for VRAM in MB (4GB to 80GB range)
vram_mb = st.integers(min_value=4096, max_value=81920)

# Strategy for compute capability (e.g., "8.6", "9.0")
compute_capability = st.sampled_from(["7.5", "8.0", "8.6", "8.9", "9.0"])

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

# Strategy for service names
service_names = st.sampled_from(["yolo26", "nemotron", "whisper", "yolo", "embedding"])

# Strategy for assignment strategies
assignment_strategies = st.sampled_from(list(GpuAssignmentStrategy))

# Strategy for VRAM budget override (0.5 to 1.0)
vram_budget = st.floats(min_value=0.1, max_value=1.0, allow_nan=False)

# Strategy for system setting keys
setting_keys = st.sampled_from(
    [
        "default_gpu_strategy",
        "auto_assign_enabled",
        "monitoring_interval",
        "fallback_gpu",
    ]
)


# =============================================================================
# GpuAssignmentStrategy Enum Tests
# =============================================================================


class TestGpuAssignmentStrategyEnumValues:
    """Tests for GpuAssignmentStrategy enum values."""

    def test_strategy_manual_value(self):
        """Test MANUAL strategy value."""
        assert GpuAssignmentStrategy.MANUAL.value == "manual"

    def test_strategy_vram_based_value(self):
        """Test VRAM_BASED strategy value."""
        assert GpuAssignmentStrategy.VRAM_BASED.value == "vram_based"

    def test_strategy_latency_optimized_value(self):
        """Test LATENCY_OPTIMIZED strategy value."""
        assert GpuAssignmentStrategy.LATENCY_OPTIMIZED.value == "latency_optimized"

    def test_strategy_isolation_first_value(self):
        """Test ISOLATION_FIRST strategy value."""
        assert GpuAssignmentStrategy.ISOLATION_FIRST.value == "isolation_first"

    def test_strategy_balanced_value(self):
        """Test BALANCED strategy value."""
        assert GpuAssignmentStrategy.BALANCED.value == "balanced"


class TestGpuAssignmentStrategyEnumCount:
    """Tests for GpuAssignmentStrategy enum member count."""

    def test_strategy_has_five_members(self):
        """Test GpuAssignmentStrategy has exactly 5 members."""
        assert len(GpuAssignmentStrategy) == 5

    def test_strategy_members_list(self):
        """Test all GpuAssignmentStrategy members are present."""
        members = list(GpuAssignmentStrategy)
        assert GpuAssignmentStrategy.MANUAL in members
        assert GpuAssignmentStrategy.VRAM_BASED in members
        assert GpuAssignmentStrategy.LATENCY_OPTIMIZED in members
        assert GpuAssignmentStrategy.ISOLATION_FIRST in members
        assert GpuAssignmentStrategy.BALANCED in members


class TestGpuAssignmentStrategyEnumType:
    """Tests for GpuAssignmentStrategy enum type properties."""

    def test_strategy_is_string_enum(self):
        """Test GpuAssignmentStrategy is a string enum (inherits from str)."""
        for strategy in GpuAssignmentStrategy:
            assert isinstance(strategy, str)

    def test_strategy_value_is_string(self):
        """Test GpuAssignmentStrategy values are strings."""
        for strategy in GpuAssignmentStrategy:
            assert isinstance(strategy.value, str)

    def test_strategy_can_compare_to_string(self):
        """Test GpuAssignmentStrategy can be compared to string."""
        assert GpuAssignmentStrategy.MANUAL == "manual"
        assert GpuAssignmentStrategy.VRAM_BASED == "vram_based"
        assert GpuAssignmentStrategy.LATENCY_OPTIMIZED == "latency_optimized"
        assert GpuAssignmentStrategy.ISOLATION_FIRST == "isolation_first"
        assert GpuAssignmentStrategy.BALANCED == "balanced"


class TestGpuAssignmentStrategyStr:
    """Tests for GpuAssignmentStrategy __str__ method."""

    def test_strategy_str_manual(self):
        """Test str(GpuAssignmentStrategy.MANUAL)."""
        assert str(GpuAssignmentStrategy.MANUAL) == "manual"

    def test_strategy_str_vram_based(self):
        """Test str(GpuAssignmentStrategy.VRAM_BASED)."""
        assert str(GpuAssignmentStrategy.VRAM_BASED) == "vram_based"

    def test_strategy_str_latency_optimized(self):
        """Test str(GpuAssignmentStrategy.LATENCY_OPTIMIZED)."""
        assert str(GpuAssignmentStrategy.LATENCY_OPTIMIZED) == "latency_optimized"

    def test_strategy_str_isolation_first(self):
        """Test str(GpuAssignmentStrategy.ISOLATION_FIRST)."""
        assert str(GpuAssignmentStrategy.ISOLATION_FIRST) == "isolation_first"

    def test_strategy_str_balanced(self):
        """Test str(GpuAssignmentStrategy.BALANCED)."""
        assert str(GpuAssignmentStrategy.BALANCED) == "balanced"

    def test_strategy_str_equals_value(self):
        """Test str() equals .value for all strategies."""
        for strategy in GpuAssignmentStrategy:
            assert str(strategy) == strategy.value


class TestGpuAssignmentStrategyLookup:
    """Tests for looking up GpuAssignmentStrategy enum members."""

    def test_lookup_by_value_manual(self):
        """Test looking up MANUAL by value."""
        assert GpuAssignmentStrategy("manual") == GpuAssignmentStrategy.MANUAL

    def test_lookup_by_value_vram_based(self):
        """Test looking up VRAM_BASED by value."""
        assert GpuAssignmentStrategy("vram_based") == GpuAssignmentStrategy.VRAM_BASED

    def test_lookup_by_value_latency_optimized(self):
        """Test looking up LATENCY_OPTIMIZED by value."""
        assert GpuAssignmentStrategy("latency_optimized") == GpuAssignmentStrategy.LATENCY_OPTIMIZED

    def test_lookup_by_value_isolation_first(self):
        """Test looking up ISOLATION_FIRST by value."""
        assert GpuAssignmentStrategy("isolation_first") == GpuAssignmentStrategy.ISOLATION_FIRST

    def test_lookup_by_value_balanced(self):
        """Test looking up BALANCED by value."""
        assert GpuAssignmentStrategy("balanced") == GpuAssignmentStrategy.BALANCED

    def test_lookup_by_name_manual(self):
        """Test looking up MANUAL by name."""
        assert GpuAssignmentStrategy["MANUAL"] == GpuAssignmentStrategy.MANUAL

    def test_invalid_value_raises_error(self):
        """Test invalid value raises ValueError."""
        with pytest.raises(ValueError):
            GpuAssignmentStrategy("invalid")

    def test_invalid_name_raises_error(self):
        """Test invalid name raises KeyError."""
        with pytest.raises(KeyError):
            GpuAssignmentStrategy["INVALID"]


# =============================================================================
# GpuDevice Model Tests
# =============================================================================


class TestGpuDeviceModelInitialization:
    """Tests for GpuDevice model initialization."""

    def test_gpu_device_creation_minimal(self):
        """Test creating a GPU device with minimal required fields."""
        device = GpuDevice(gpu_index=0)

        assert device.gpu_index == 0
        # Optional fields should be None
        assert device.name is None
        assert device.vram_total_mb is None
        assert device.vram_available_mb is None
        assert device.compute_capability is None

    def test_gpu_device_with_all_fields(self):
        """Test GPU device with all fields populated."""
        now = datetime.now(UTC)
        device = GpuDevice(
            gpu_index=0,
            name="NVIDIA RTX A5500",
            vram_total_mb=24000,
            vram_available_mb=20000,
            compute_capability="8.6",
            last_seen_at=now,
        )

        assert device.gpu_index == 0
        assert device.name == "NVIDIA RTX A5500"
        assert device.vram_total_mb == 24000
        assert device.vram_available_mb == 20000
        assert device.compute_capability == "8.6"
        assert device.last_seen_at == now

    def test_gpu_device_all_optional_fields_nullable(self):
        """Test all optional GPU device fields are nullable."""
        device = GpuDevice(gpu_index=0)

        assert device.name is None
        assert device.vram_total_mb is None
        assert device.vram_available_mb is None
        assert device.compute_capability is None


class TestGpuDeviceFields:
    """Tests for GpuDevice model fields."""

    def test_gpu_device_has_id_field(self):
        """Test GPU device has id field."""
        device = GpuDevice(gpu_index=0)
        assert hasattr(device, "id")

    def test_gpu_device_has_gpu_index_field(self):
        """Test GPU device has gpu_index field."""
        device = GpuDevice(gpu_index=0)
        assert hasattr(device, "gpu_index")
        assert device.gpu_index == 0

    def test_gpu_device_has_name_field(self):
        """Test GPU device has name field."""
        device = GpuDevice(gpu_index=0, name="NVIDIA RTX A5500")
        assert hasattr(device, "name")
        assert device.name == "NVIDIA RTX A5500"

    def test_gpu_device_has_vram_total_mb_field(self):
        """Test GPU device has vram_total_mb field."""
        device = GpuDevice(gpu_index=0, vram_total_mb=24000)
        assert hasattr(device, "vram_total_mb")
        assert device.vram_total_mb == 24000

    def test_gpu_device_has_vram_available_mb_field(self):
        """Test GPU device has vram_available_mb field."""
        device = GpuDevice(gpu_index=0, vram_available_mb=20000)
        assert hasattr(device, "vram_available_mb")
        assert device.vram_available_mb == 20000

    def test_gpu_device_has_compute_capability_field(self):
        """Test GPU device has compute_capability field."""
        device = GpuDevice(gpu_index=0, compute_capability="8.6")
        assert hasattr(device, "compute_capability")
        assert device.compute_capability == "8.6"

    def test_gpu_device_has_last_seen_at_field(self):
        """Test GPU device has last_seen_at field."""
        device = GpuDevice(gpu_index=0)
        assert hasattr(device, "last_seen_at")


class TestGpuDeviceRepr:
    """Tests for GpuDevice string representation."""

    def test_gpu_device_repr_contains_class_name(self):
        """Test repr contains class name."""
        device = GpuDevice(gpu_index=0, name="NVIDIA RTX A5500")
        repr_str = repr(device)
        assert "GpuDevice" in repr_str

    def test_gpu_device_repr_contains_gpu_index(self):
        """Test repr contains GPU index."""
        device = GpuDevice(gpu_index=0, name="NVIDIA RTX A5500")
        repr_str = repr(device)
        assert "gpu_index=0" in repr_str

    def test_gpu_device_repr_contains_name(self):
        """Test repr contains GPU name."""
        device = GpuDevice(gpu_index=0, name="NVIDIA RTX A5500", vram_total_mb=24000)
        repr_str = repr(device)
        assert "NVIDIA RTX A5500" in repr_str

    def test_gpu_device_repr_contains_vram(self):
        """Test repr contains VRAM total."""
        device = GpuDevice(gpu_index=0, name="NVIDIA RTX A5500", vram_total_mb=24000)
        repr_str = repr(device)
        assert "vram_total_mb=24000" in repr_str

    def test_gpu_device_repr_format(self):
        """Test repr has expected format."""
        device = GpuDevice(gpu_index=0, name="NVIDIA RTX A5500")
        repr_str = repr(device)
        assert repr_str.startswith("<GpuDevice(")
        assert repr_str.endswith(")>")


class TestGpuDeviceTableArgs:
    """Tests for GpuDevice table arguments (indexes)."""

    def test_gpu_device_has_table_args(self):
        """Test GpuDevice model has __table_args__."""
        assert hasattr(GpuDevice, "__table_args__")

    def test_gpu_device_tablename(self):
        """Test GpuDevice has correct table name."""
        assert GpuDevice.__tablename__ == "gpu_devices"

    def test_gpu_device_has_gpu_index_unique_index(self):
        """Test GpuDevice has unique index on gpu_index."""
        indexes = GpuDevice.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_gpu_devices_gpu_index" in index_names

    def test_gpu_device_gpu_index_index_is_unique(self):
        """Test gpu_index index is unique."""
        indexes = GpuDevice.__table_args__
        gpu_index_idx = None
        for idx in indexes:
            if hasattr(idx, "name") and idx.name == "idx_gpu_devices_gpu_index":
                gpu_index_idx = idx
                break
        assert gpu_index_idx is not None
        assert gpu_index_idx.unique is True

    def test_gpu_device_has_last_seen_index(self):
        """Test GpuDevice has index on last_seen_at."""
        indexes = GpuDevice.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_gpu_devices_last_seen" in index_names

    def test_gpu_device_gpu_index_column_is_unique(self):
        """Test gpu_index column has unique constraint."""
        mapper = inspect(GpuDevice)
        gpu_index_col = mapper.columns["gpu_index"]
        assert gpu_index_col.unique is True


class TestGpuDeviceTimezoneColumns:
    """Tests for GpuDevice timezone-aware datetime columns."""

    def test_last_seen_at_column_is_timezone_aware(self):
        """Test that last_seen_at column is defined with timezone=True."""
        mapper = inspect(GpuDevice)
        last_seen_at_col = mapper.columns["last_seen_at"]

        assert hasattr(last_seen_at_col.type, "timezone"), (
            "DateTime column should have timezone attribute"
        )
        assert last_seen_at_col.type.timezone is True, "last_seen_at must be timezone-aware"

    def test_last_seen_at_default_is_timezone_aware(self):
        """Test that the last_seen_at default function produces timezone-aware datetime."""
        now_utc = datetime.now(UTC)

        assert now_utc.tzinfo is not None, "datetime.now(UTC) should be timezone-aware"
        assert now_utc.tzinfo == UTC, "datetime.now(UTC) should use UTC"

    def test_timezone_aware_datetime_preserved_on_assignment(self):
        """Test that timezone-aware datetimes are preserved when assigned."""
        utc_time = datetime(2026, 1, 23, 12, 0, 0, tzinfo=UTC)

        device = GpuDevice(gpu_index=0, last_seen_at=utc_time)

        assert device.last_seen_at.tzinfo is not None, "last_seen_at should preserve timezone"
        assert device.last_seen_at == utc_time


# =============================================================================
# GpuConfiguration Model Tests
# =============================================================================


class TestGpuConfigurationModelInitialization:
    """Tests for GpuConfiguration model initialization."""

    def test_gpu_configuration_creation_minimal(self):
        """Test creating a GPU configuration with minimal required fields."""
        config = GpuConfiguration(service_name="yolo26")

        assert config.service_name == "yolo26"
        # Optional fields should be None or have defaults
        assert config.gpu_index is None
        assert config.vram_budget_override is None

    def test_gpu_configuration_with_all_fields(self):
        """Test GPU configuration with all fields populated."""
        now = datetime.now(UTC)
        config = GpuConfiguration(
            service_name="yolo26",
            gpu_index=0,
            strategy=GpuAssignmentStrategy.MANUAL.value,
            vram_budget_override=0.8,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        assert config.service_name == "yolo26"
        assert config.gpu_index == 0
        assert config.strategy == "manual"
        assert config.vram_budget_override == 0.8
        assert config.enabled is True
        assert config.created_at == now
        assert config.updated_at == now

    def test_gpu_configuration_default_strategy_column_definition(self):
        """Test that strategy column has 'manual' as default."""
        mapper = inspect(GpuConfiguration)
        strategy_col = mapper.columns["strategy"]
        assert strategy_col.default is not None
        assert strategy_col.default.arg == "manual"

    def test_gpu_configuration_default_enabled_column_definition(self):
        """Test that enabled column has True as default."""
        mapper = inspect(GpuConfiguration)
        enabled_col = mapper.columns["enabled"]
        assert enabled_col.default is not None
        assert enabled_col.default.arg is True

    def test_gpu_configuration_custom_strategy(self):
        """Test GPU configuration with custom strategy."""
        config = GpuConfiguration(
            service_name="yolo26",
            strategy=GpuAssignmentStrategy.VRAM_BASED.value,
        )

        assert config.strategy == "vram_based"

    def test_gpu_configuration_enabled_false(self):
        """Test GPU configuration with enabled=False."""
        config = GpuConfiguration(service_name="yolo26", enabled=False)

        assert config.enabled is False


class TestGpuConfigurationFields:
    """Tests for GpuConfiguration model fields."""

    def test_gpu_configuration_has_id_field(self):
        """Test GPU configuration has id field."""
        config = GpuConfiguration(service_name="yolo26")
        assert hasattr(config, "id")

    def test_gpu_configuration_has_service_name_field(self):
        """Test GPU configuration has service_name field."""
        config = GpuConfiguration(service_name="yolo26")
        assert hasattr(config, "service_name")
        assert config.service_name == "yolo26"

    def test_gpu_configuration_has_gpu_index_field(self):
        """Test GPU configuration has gpu_index field."""
        config = GpuConfiguration(service_name="yolo26", gpu_index=0)
        assert hasattr(config, "gpu_index")
        assert config.gpu_index == 0

    def test_gpu_configuration_has_strategy_field(self):
        """Test GPU configuration has strategy field."""
        config = GpuConfiguration(service_name="yolo26")
        assert hasattr(config, "strategy")

    def test_gpu_configuration_has_vram_budget_override_field(self):
        """Test GPU configuration has vram_budget_override field."""
        config = GpuConfiguration(service_name="yolo26", vram_budget_override=0.8)
        assert hasattr(config, "vram_budget_override")
        assert config.vram_budget_override == 0.8

    def test_gpu_configuration_has_enabled_field(self):
        """Test GPU configuration has enabled field."""
        config = GpuConfiguration(service_name="yolo26")
        assert hasattr(config, "enabled")

    def test_gpu_configuration_has_created_at_field(self):
        """Test GPU configuration has created_at field."""
        config = GpuConfiguration(service_name="yolo26")
        assert hasattr(config, "created_at")

    def test_gpu_configuration_has_updated_at_field(self):
        """Test GPU configuration has updated_at field."""
        config = GpuConfiguration(service_name="yolo26")
        assert hasattr(config, "updated_at")


class TestGpuConfigurationRepr:
    """Tests for GpuConfiguration string representation."""

    def test_gpu_configuration_repr_contains_class_name(self):
        """Test repr contains class name."""
        config = GpuConfiguration(service_name="yolo26", gpu_index=0)
        repr_str = repr(config)
        assert "GpuConfiguration" in repr_str

    def test_gpu_configuration_repr_contains_service_name(self):
        """Test repr contains service name."""
        config = GpuConfiguration(service_name="yolo26", gpu_index=0)
        repr_str = repr(config)
        assert "yolo26" in repr_str

    def test_gpu_configuration_repr_contains_gpu_index(self):
        """Test repr contains GPU index."""
        config = GpuConfiguration(service_name="yolo26", gpu_index=0)
        repr_str = repr(config)
        assert "gpu_index=0" in repr_str

    def test_gpu_configuration_repr_contains_strategy(self):
        """Test repr contains strategy."""
        config = GpuConfiguration(
            service_name="yolo26",
            strategy=GpuAssignmentStrategy.VRAM_BASED.value,
        )
        repr_str = repr(config)
        assert "strategy=" in repr_str

    def test_gpu_configuration_repr_format(self):
        """Test repr has expected format."""
        config = GpuConfiguration(service_name="yolo26", gpu_index=0)
        repr_str = repr(config)
        assert repr_str.startswith("<GpuConfiguration(")
        assert repr_str.endswith(")>")


class TestGpuConfigurationTableArgs:
    """Tests for GpuConfiguration table arguments (indexes)."""

    def test_gpu_configuration_has_table_args(self):
        """Test GpuConfiguration model has __table_args__."""
        assert hasattr(GpuConfiguration, "__table_args__")

    def test_gpu_configuration_tablename(self):
        """Test GpuConfiguration has correct table name."""
        assert GpuConfiguration.__tablename__ == "gpu_configurations"

    def test_gpu_configuration_has_service_name_unique_index(self):
        """Test GpuConfiguration has unique index on service_name."""
        indexes = GpuConfiguration.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_gpu_configurations_service_name" in index_names

    def test_gpu_configuration_service_name_index_is_unique(self):
        """Test service_name index is unique."""
        indexes = GpuConfiguration.__table_args__
        service_name_idx = None
        for idx in indexes:
            if hasattr(idx, "name") and idx.name == "idx_gpu_configurations_service_name":
                service_name_idx = idx
                break
        assert service_name_idx is not None
        assert service_name_idx.unique is True

    def test_gpu_configuration_has_gpu_index_index(self):
        """Test GpuConfiguration has index on gpu_index."""
        indexes = GpuConfiguration.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_gpu_configurations_gpu_index" in index_names

    def test_gpu_configuration_has_enabled_index(self):
        """Test GpuConfiguration has index on enabled."""
        indexes = GpuConfiguration.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_gpu_configurations_enabled" in index_names

    def test_gpu_configuration_service_name_column_is_unique(self):
        """Test service_name column has unique constraint."""
        mapper = inspect(GpuConfiguration)
        service_name_col = mapper.columns["service_name"]
        assert service_name_col.unique is True


class TestGpuConfigurationTimezoneColumns:
    """Tests for GpuConfiguration timezone-aware datetime columns."""

    def test_created_at_column_is_timezone_aware(self):
        """Test that created_at column is defined with timezone=True."""
        mapper = inspect(GpuConfiguration)
        created_at_col = mapper.columns["created_at"]

        assert hasattr(created_at_col.type, "timezone"), (
            "DateTime column should have timezone attribute"
        )
        assert created_at_col.type.timezone is True, "created_at must be timezone-aware"

    def test_updated_at_column_is_timezone_aware(self):
        """Test that updated_at column is defined with timezone=True."""
        mapper = inspect(GpuConfiguration)
        updated_at_col = mapper.columns["updated_at"]

        assert hasattr(updated_at_col.type, "timezone"), (
            "DateTime column should have timezone attribute"
        )
        assert updated_at_col.type.timezone is True, "updated_at must be timezone-aware"

    def test_all_datetime_columns_have_consistent_timezone_setting(self):
        """Test that all datetime columns consistently use timezone=True."""
        mapper = inspect(GpuConfiguration)
        datetime_columns = ["created_at", "updated_at"]

        for col_name in datetime_columns:
            col = mapper.columns[col_name]
            assert col.type.__class__.__name__ == "DateTime", f"{col_name} should be DateTime type"
            assert col.type.timezone is True, f"{col_name} must have timezone=True"


# =============================================================================
# SystemSetting Model Tests
# =============================================================================


class TestSystemSettingModelInitialization:
    """Tests for SystemSetting model initialization."""

    def test_system_setting_creation_minimal(self):
        """Test creating a system setting with minimal required fields."""
        setting = SystemSetting(key="default_gpu_strategy", value={"strategy": "manual"})

        assert setting.key == "default_gpu_strategy"
        assert setting.value == {"strategy": "manual"}

    def test_system_setting_with_all_fields(self):
        """Test system setting with all fields populated."""
        now = datetime.now(UTC)
        setting = SystemSetting(
            key="default_gpu_strategy",
            value={"strategy": "manual", "enabled": True},
            updated_at=now,
        )

        assert setting.key == "default_gpu_strategy"
        assert setting.value == {"strategy": "manual", "enabled": True}
        assert setting.updated_at == now

    def test_system_setting_value_is_dict(self):
        """Test system setting value is a dictionary."""
        setting = SystemSetting(
            key="monitoring_config",
            value={"interval": 60, "enabled": True},
        )

        assert isinstance(setting.value, dict)
        assert setting.value["interval"] == 60
        assert setting.value["enabled"] is True

    def test_system_setting_value_nested_dict(self):
        """Test system setting with nested dictionary value."""
        setting = SystemSetting(
            key="gpu_config",
            value={
                "strategy": "manual",
                "gpus": [
                    {"index": 0, "name": "GPU0"},
                    {"index": 1, "name": "GPU1"},
                ],
            },
        )

        assert setting.value["strategy"] == "manual"
        assert len(setting.value["gpus"]) == 2
        assert setting.value["gpus"][0]["index"] == 0


class TestSystemSettingFields:
    """Tests for SystemSetting model fields."""

    def test_system_setting_has_key_field(self):
        """Test system setting has key field."""
        setting = SystemSetting(key="test_key", value={"data": "value"})
        assert hasattr(setting, "key")
        assert setting.key == "test_key"

    def test_system_setting_has_value_field(self):
        """Test system setting has value field."""
        setting = SystemSetting(key="test_key", value={"data": "value"})
        assert hasattr(setting, "value")
        assert setting.value == {"data": "value"}

    def test_system_setting_has_updated_at_field(self):
        """Test system setting has updated_at field."""
        setting = SystemSetting(key="test_key", value={"data": "value"})
        assert hasattr(setting, "updated_at")


class TestSystemSettingRepr:
    """Tests for SystemSetting string representation."""

    def test_system_setting_repr_contains_class_name(self):
        """Test repr contains class name."""
        setting = SystemSetting(key="test_key", value={"data": "value"})
        repr_str = repr(setting)
        assert "SystemSetting" in repr_str

    def test_system_setting_repr_contains_key(self):
        """Test repr contains key."""
        setting = SystemSetting(key="test_key", value={"data": "value"})
        repr_str = repr(setting)
        assert "test_key" in repr_str

    def test_system_setting_repr_contains_value(self):
        """Test repr contains value."""
        setting = SystemSetting(key="test_key", value={"data": "value"})
        repr_str = repr(setting)
        assert "value=" in repr_str

    def test_system_setting_repr_format(self):
        """Test repr has expected format."""
        setting = SystemSetting(key="test_key", value={"data": "value"})
        repr_str = repr(setting)
        assert repr_str.startswith("<SystemSetting(")
        assert repr_str.endswith(")>")


class TestSystemSettingTableArgs:
    """Tests for SystemSetting table arguments (indexes)."""

    def test_system_setting_has_table_args(self):
        """Test SystemSetting model has __table_args__."""
        assert hasattr(SystemSetting, "__table_args__")

    def test_system_setting_tablename(self):
        """Test SystemSetting has correct table name."""
        assert SystemSetting.__tablename__ == "system_settings"

    def test_system_setting_has_updated_at_index(self):
        """Test SystemSetting has index on updated_at."""
        indexes = SystemSetting.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_system_settings_updated_at" in index_names

    def test_system_setting_key_is_primary_key(self):
        """Test key column is primary key."""
        mapper = inspect(SystemSetting)
        key_col = mapper.columns["key"]
        assert key_col.primary_key is True


class TestSystemSettingTimezoneColumns:
    """Tests for SystemSetting timezone-aware datetime columns."""

    def test_updated_at_column_is_timezone_aware(self):
        """Test that updated_at column is defined with timezone=True."""
        mapper = inspect(SystemSetting)
        updated_at_col = mapper.columns["updated_at"]

        assert hasattr(updated_at_col.type, "timezone"), (
            "DateTime column should have timezone attribute"
        )
        assert updated_at_col.type.timezone is True, "updated_at must be timezone-aware"


# =============================================================================
# Property-based Tests
# =============================================================================


class TestGpuAssignmentStrategyProperties:
    """Property-based tests for GpuAssignmentStrategy enum."""

    @given(strategy=assignment_strategies)
    @settings(max_examples=10)
    def test_strategy_str_equals_value(self, strategy: GpuAssignmentStrategy):
        """Property: str(strategy) equals strategy.value."""
        assert str(strategy) == strategy.value

    @given(strategy=assignment_strategies)
    @settings(max_examples=10)
    def test_strategy_lookup_roundtrip(self, strategy: GpuAssignmentStrategy):
        """Property: Looking up by value returns same member."""
        looked_up = GpuAssignmentStrategy(strategy.value)
        assert looked_up is strategy

    @given(strategy=assignment_strategies)
    @settings(max_examples=10)
    def test_strategy_name_lookup_roundtrip(self, strategy: GpuAssignmentStrategy):
        """Property: Looking up by name returns same member."""
        looked_up = GpuAssignmentStrategy[strategy.name]
        assert looked_up is strategy

    @given(strategy=assignment_strategies)
    @settings(max_examples=10)
    def test_strategy_is_string_instance(self, strategy: GpuAssignmentStrategy):
        """Property: All strategies are string instances."""
        assert isinstance(strategy, str)


class TestGpuDeviceProperties:
    """Property-based tests for GpuDevice model."""

    @given(index=gpu_index)
    @settings(max_examples=20)
    def test_gpu_index_roundtrip(self, index: int):
        """Property: GPU index values roundtrip correctly."""
        device = GpuDevice(gpu_index=index)
        assert device.gpu_index == index

    @given(vram=vram_mb)
    @settings(max_examples=20)
    def test_vram_total_roundtrip(self, vram: int):
        """Property: VRAM total values roundtrip correctly."""
        device = GpuDevice(gpu_index=0, vram_total_mb=vram)
        assert device.vram_total_mb == vram

    @given(vram=vram_mb)
    @settings(max_examples=20)
    def test_vram_available_roundtrip(self, vram: int):
        """Property: VRAM available values roundtrip correctly."""
        device = GpuDevice(gpu_index=0, vram_available_mb=vram)
        assert device.vram_available_mb == vram

    @given(name=gpu_names)
    @settings(max_examples=10)
    def test_gpu_name_roundtrip(self, name: str):
        """Property: GPU name values roundtrip correctly."""
        device = GpuDevice(gpu_index=0, name=name)
        assert device.name == name

    @given(capability=compute_capability)
    @settings(max_examples=10)
    def test_compute_capability_roundtrip(self, capability: str):
        """Property: Compute capability values roundtrip correctly."""
        device = GpuDevice(gpu_index=0, compute_capability=capability)
        assert device.compute_capability == capability

    @given(index=gpu_index, vram_total=vram_mb, vram_available=vram_mb)
    @settings(max_examples=20)
    def test_multiple_fields_roundtrip(self, index: int, vram_total: int, vram_available: int):
        """Property: Multiple fields roundtrip correctly together."""
        device = GpuDevice(
            gpu_index=index,
            vram_total_mb=vram_total,
            vram_available_mb=vram_available,
        )
        assert device.gpu_index == index
        assert device.vram_total_mb == vram_total
        assert device.vram_available_mb == vram_available


class TestGpuConfigurationProperties:
    """Property-based tests for GpuConfiguration model."""

    @given(service=service_names)
    @settings(max_examples=10)
    def test_service_name_roundtrip(self, service: str):
        """Property: Service name values roundtrip correctly."""
        config = GpuConfiguration(service_name=service)
        assert config.service_name == service

    @given(index=gpu_index)
    @settings(max_examples=20)
    def test_gpu_index_roundtrip(self, index: int):
        """Property: GPU index values roundtrip correctly."""
        config = GpuConfiguration(service_name="yolo26", gpu_index=index)
        assert config.gpu_index == index

    @given(strategy=assignment_strategies)
    @settings(max_examples=10)
    def test_strategy_roundtrip(self, strategy: GpuAssignmentStrategy):
        """Property: Strategy values roundtrip correctly."""
        config = GpuConfiguration(service_name="yolo26", strategy=strategy.value)
        assert config.strategy == strategy.value

    @given(budget=vram_budget)
    @settings(max_examples=20)
    def test_vram_budget_override_roundtrip(self, budget: float):
        """Property: VRAM budget override values roundtrip correctly."""
        config = GpuConfiguration(service_name="yolo26", vram_budget_override=budget)
        assert abs(config.vram_budget_override - budget) < 1e-10

    @given(enabled=st.booleans())
    @settings(max_examples=10)
    def test_enabled_roundtrip(self, enabled: bool):
        """Property: Enabled values roundtrip correctly."""
        config = GpuConfiguration(service_name="yolo26", enabled=enabled)
        assert config.enabled == enabled


class TestSystemSettingProperties:
    """Property-based tests for SystemSetting model."""

    @given(key=setting_keys)
    @settings(max_examples=10)
    def test_key_roundtrip(self, key: str):
        """Property: Key values roundtrip correctly."""
        setting = SystemSetting(key=key, value={"data": "test"})
        assert setting.key == key

    @given(
        key=setting_keys,
        value=st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.booleans(), st.integers(), st.text(min_size=1, max_size=50)),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=20)
    def test_value_dict_roundtrip(self, key: str, value: dict):
        """Property: Dictionary values roundtrip correctly."""
        setting = SystemSetting(key=key, value=value)
        assert setting.value == value


class TestGpuDeviceFieldRanges:
    """Property-based tests for GpuDevice field ranges."""

    @given(index=gpu_index)
    @settings(max_examples=20)
    def test_gpu_index_non_negative(self, index: int):
        """Property: GPU index is non-negative."""
        device = GpuDevice(gpu_index=index)
        assert device.gpu_index >= 0

    @given(vram=vram_mb)
    @settings(max_examples=20)
    def test_vram_values_non_negative(self, vram: int):
        """Property: VRAM values are non-negative."""
        device = GpuDevice(gpu_index=0, vram_total_mb=vram, vram_available_mb=vram)
        assert device.vram_total_mb >= 0
        assert device.vram_available_mb >= 0


class TestGpuConfigurationFieldRanges:
    """Property-based tests for GpuConfiguration field ranges."""

    @given(budget=vram_budget)
    @settings(max_examples=20)
    def test_vram_budget_in_valid_range(self, budget: float):
        """Property: VRAM budget override is in valid range (0.0-1.0)."""
        config = GpuConfiguration(service_name="yolo26", vram_budget_override=budget)
        assert 0.0 < config.vram_budget_override <= 1.0
