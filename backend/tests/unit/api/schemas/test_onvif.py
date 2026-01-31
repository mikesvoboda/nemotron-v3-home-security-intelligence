"""Unit tests for ONVIF Pydantic schemas.

Tests validation for ONVIF discovery, device configuration, and PTZ command schemas.

Run with: uv run pytest backend/tests/unit/api/schemas/test_onvif.py -v

TDD Phase 4: These tests will FAIL initially since ONVIF schemas don't exist yet.
Implementation will be done in Phase 5.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

# Import will fail until Phase 5 implementation
try:
    from backend.api.schemas.onvif import (
        OnvifDeviceConfig,
        OnvifDiscoveryRequest,
        OnvifDiscoveryResult,
        PTZCommand,
        PTZPreset,
    )
except ImportError:
    OnvifDiscoveryRequest = None  # type: ignore
    OnvifDiscoveryResult = None  # type: ignore
    OnvifDeviceConfig = None  # type: ignore
    PTZCommand = None  # type: ignore
    PTZPreset = None  # type: ignore


@pytest.mark.skipif(
    OnvifDiscoveryRequest is None, reason="OnvifDiscoveryRequest not implemented yet"
)
class TestOnvifDiscoveryRequest:
    """Test OnvifDiscoveryRequest schema validation."""

    def test_valid_discovery_request(self):
        """Test valid discovery request with subnet and timeout."""
        request = OnvifDiscoveryRequest(subnet="192.168.1.0/24", timeout=5)

        assert request.subnet == "192.168.1.0/24"
        assert request.timeout == 5

    def test_discovery_request_default_timeout(self):
        """Test discovery request uses default timeout if not provided."""
        request = OnvifDiscoveryRequest(subnet="192.168.1.0/24")

        assert request.subnet == "192.168.1.0/24"
        assert request.timeout == 10  # Default timeout

    def test_discovery_request_invalid_subnet(self):
        """Test discovery request rejects invalid subnet format."""
        with pytest.raises(ValidationError, match="subnet"):
            OnvifDiscoveryRequest(subnet="invalid-subnet")

    def test_discovery_request_negative_timeout(self):
        """Test discovery request rejects negative timeout."""
        with pytest.raises(ValidationError, match="timeout"):
            OnvifDiscoveryRequest(subnet="192.168.1.0/24", timeout=-5)

    def test_discovery_request_zero_timeout(self):
        """Test discovery request rejects zero timeout."""
        with pytest.raises(ValidationError, match="timeout"):
            OnvifDiscoveryRequest(subnet="192.168.1.0/24", timeout=0)

    def test_discovery_request_excessive_timeout(self):
        """Test discovery request rejects excessively long timeout."""
        with pytest.raises(ValidationError, match="timeout"):
            OnvifDiscoveryRequest(
                subnet="192.168.1.0/24",
                timeout=301,  # Over 5 minutes
            )


@pytest.mark.skipif(OnvifDiscoveryResult is None, reason="OnvifDiscoveryResult not implemented yet")
class TestOnvifDiscoveryResult:
    """Test OnvifDiscoveryResult schema validation."""

    def test_valid_discovery_result(self):
        """Test valid discovery result with device information."""
        result = OnvifDiscoveryResult(
            device_url="http://192.168.1.100/onvif/device_service",
            manufacturer="Test Manufacturer",
            model="Test Model",
            firmware_version="1.0.0",
            serial_number="TEST123456",
            hardware_id="HW-001",
        )

        assert result.device_url == "http://192.168.1.100/onvif/device_service"
        assert result.manufacturer == "Test Manufacturer"
        assert result.model == "Test Model"
        assert result.firmware_version == "1.0.0"
        assert result.serial_number == "TEST123456"
        assert result.hardware_id == "HW-001"

    def test_discovery_result_minimal_fields(self):
        """Test discovery result with only required fields."""
        result = OnvifDiscoveryResult(
            device_url="http://192.168.1.100/onvif/device_service",
            manufacturer="Test Manufacturer",
            model="Test Model",
        )

        assert result.device_url == "http://192.168.1.100/onvif/device_service"
        assert result.manufacturer == "Test Manufacturer"
        assert result.model == "Test Model"
        assert result.firmware_version is None
        assert result.serial_number is None
        assert result.hardware_id is None

    def test_discovery_result_invalid_url(self):
        """Test discovery result rejects invalid device URL."""
        with pytest.raises(ValidationError, match="device_url"):
            OnvifDiscoveryResult(device_url="not-a-url", manufacturer="Test", model="Test")

    def test_discovery_result_missing_required_fields(self):
        """Test discovery result requires device_url, manufacturer, and model."""
        with pytest.raises(ValidationError):
            OnvifDiscoveryResult(device_url="http://192.168.1.100/onvif/device_service")


@pytest.mark.skipif(OnvifDeviceConfig is None, reason="OnvifDeviceConfig not implemented yet")
class TestOnvifDeviceConfig:
    """Test OnvifDeviceConfig schema validation."""

    def test_valid_device_config(self):
        """Test valid device configuration with all fields."""
        config = OnvifDeviceConfig(
            device_url="http://192.168.1.100/onvif/device_service",
            username="admin",
            password="password123",  # pragma: allowlist secret
            rtsp_url="rtsp://192.168.1.100:554/stream1",
        )

        assert config.device_url == "http://192.168.1.100/onvif/device_service"
        assert config.username == "admin"
        assert config.password == "password123"  # pragma: allowlist secret
        assert config.rtsp_url == "rtsp://192.168.1.100:554/stream1"

    def test_device_config_optional_rtsp_url(self):
        """Test device config with optional RTSP URL."""
        config = OnvifDeviceConfig(
            device_url="http://192.168.1.100/onvif/device_service",
            username="admin",
            password="password123",  # pragma: allowlist secret
        )

        assert config.rtsp_url is None

    def test_device_config_empty_username(self):
        """Test device config rejects empty username."""
        with pytest.raises(ValidationError, match="username"):
            OnvifDeviceConfig(
                device_url="http://192.168.1.100/onvif/device_service",
                username="",
                password="password123",  # pragma: allowlist secret
            )

    def test_device_config_empty_password(self):
        """Test device config rejects empty password."""
        with pytest.raises(ValidationError, match="password"):
            OnvifDeviceConfig(
                device_url="http://192.168.1.100/onvif/device_service",
                username="admin",
                password="",
            )

    def test_device_config_invalid_device_url(self):
        """Test device config rejects invalid device URL."""
        with pytest.raises(ValidationError, match="device_url"):
            OnvifDeviceConfig(
                device_url="not-a-url",
                username="admin",
                password="password123",  # pragma: allowlist secret
            )

    def test_device_config_invalid_rtsp_url(self):
        """Test device config rejects invalid RTSP URL."""
        with pytest.raises(ValidationError, match="rtsp_url"):
            OnvifDeviceConfig(
                device_url="http://192.168.1.100/onvif/device_service",
                username="admin",
                password="password123",  # pragma: allowlist secret
                rtsp_url="not-rtsp-url",
            )


@pytest.mark.skipif(PTZCommand is None, reason="PTZCommand not implemented yet")
class TestPTZCommand:
    """Test PTZCommand schema validation."""

    def test_valid_ptz_pan_command(self):
        """Test valid PTZ pan command."""
        command = PTZCommand(command="pan", value=0.5, speed=1.0)

        assert command.command == "pan"
        assert command.value == 0.5
        assert command.speed == 1.0

    def test_valid_ptz_tilt_command(self):
        """Test valid PTZ tilt command."""
        command = PTZCommand(command="tilt", value=-0.3, speed=0.8)

        assert command.command == "tilt"
        assert command.value == -0.3
        assert command.speed == 0.8

    def test_valid_ptz_zoom_command(self):
        """Test valid PTZ zoom command."""
        command = PTZCommand(command="zoom", value=0.2, speed=1.0)

        assert command.command == "zoom"
        assert command.value == 0.2
        assert command.speed == 1.0

    def test_valid_ptz_stop_command(self):
        """Test valid PTZ stop command."""
        command = PTZCommand(command="stop", value=0.0, speed=0.0)

        assert command.command == "stop"
        assert command.value == 0.0
        assert command.speed == 0.0

    def test_ptz_command_default_speed(self):
        """Test PTZ command uses default speed if not provided."""
        command = PTZCommand(command="pan", value=0.5)

        assert command.speed == 1.0  # Default speed

    def test_ptz_command_invalid_type(self):
        """Test PTZ command rejects invalid command type."""
        with pytest.raises(ValidationError, match="command"):
            PTZCommand(command="invalid", value=0.5, speed=1.0)

    def test_ptz_command_value_below_range(self):
        """Test PTZ command rejects value below -1.0."""
        with pytest.raises(ValidationError, match="value"):
            PTZCommand(command="pan", value=-1.5, speed=1.0)

    def test_ptz_command_value_above_range(self):
        """Test PTZ command rejects value above 1.0."""
        with pytest.raises(ValidationError, match="value"):
            PTZCommand(command="pan", value=2.0, speed=1.0)

    def test_ptz_command_speed_below_range(self):
        """Test PTZ command rejects speed below 0.0."""
        with pytest.raises(ValidationError, match="speed"):
            PTZCommand(command="pan", value=0.5, speed=-0.5)

    def test_ptz_command_speed_above_range(self):
        """Test PTZ command rejects speed above 1.0."""
        with pytest.raises(ValidationError, match="speed"):
            PTZCommand(command="pan", value=0.5, speed=1.5)

    def test_ptz_command_edge_values(self):
        """Test PTZ command accepts edge values (-1.0, 1.0)."""
        command_min = PTZCommand(command="pan", value=-1.0, speed=0.0)
        assert command_min.value == -1.0
        assert command_min.speed == 0.0

        command_max = PTZCommand(command="tilt", value=1.0, speed=1.0)
        assert command_max.value == 1.0
        assert command_max.speed == 1.0


@pytest.mark.skipif(PTZPreset is None, reason="PTZPreset not implemented yet")
class TestPTZPreset:
    """Test PTZPreset schema validation."""

    def test_valid_ptz_preset(self):
        """Test valid PTZ preset."""
        preset = PTZPreset(token="preset_1", name="Front Door View")

        assert preset.token == "preset_1"
        assert preset.name == "Front Door View"

    def test_ptz_preset_empty_token(self):
        """Test PTZ preset rejects empty token."""
        with pytest.raises(ValidationError, match="token"):
            PTZPreset(token="", name="Front Door View")

    def test_ptz_preset_empty_name(self):
        """Test PTZ preset rejects empty name."""
        with pytest.raises(ValidationError, match="name"):
            PTZPreset(token="preset_1", name="")

    def test_ptz_preset_missing_fields(self):
        """Test PTZ preset requires both token and name."""
        with pytest.raises(ValidationError):
            PTZPreset(token="preset_1")

        with pytest.raises(ValidationError):
            PTZPreset(name="Front Door View")

    def test_ptz_preset_whitespace_stripping(self):
        """Test PTZ preset strips leading/trailing whitespace."""
        preset = PTZPreset(token="  preset_1  ", name="  Front Door View  ")

        assert preset.token == "preset_1"
        assert preset.name == "Front Door View"
