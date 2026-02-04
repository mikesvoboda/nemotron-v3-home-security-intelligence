"""Unit tests for ONVIF API routes.

Tests the ONVIF camera management endpoints:
- POST /api/cameras/onvif/discover - Discover ONVIF devices
- GET /api/cameras/{camera_id}/onvif/capabilities - Get device capabilities
- POST /api/cameras/{camera_id}/onvif/ptz - Execute PTZ command
- GET /api/cameras/{camera_id}/onvif/presets - Get PTZ presets
- POST /api/cameras/{camera_id}/onvif/presets/{preset_token} - Go to preset

Run with: uv run pytest backend/tests/unit/api/routes/test_onvif_routes.py -v

TDD Phase 4: These tests will FAIL initially since ONVIF routes don't exist yet.
Implementation will be done in Phase 5.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

# Import will fail until Phase 5 implementation
try:
    from backend.api.routes.onvif import (
        discover_onvif_devices,
        execute_ptz_command,
        get_device_capabilities,
        get_ptz_presets,
        goto_ptz_preset,
    )
except ImportError:
    discover_onvif_devices = None  # type: ignore
    get_device_capabilities = None  # type: ignore
    execute_ptz_command = None  # type: ignore
    get_ptz_presets = None  # type: ignore
    goto_ptz_preset = None  # type: ignore


@pytest.fixture
def mock_onvif_service():
    """Create a mock OnvifService."""
    service = MagicMock()
    service.discover_devices = AsyncMock()
    service.get_capabilities = AsyncMock()
    service.execute_ptz_command = AsyncMock()
    service.get_presets = AsyncMock()
    service.goto_preset = AsyncMock()
    return service


@pytest.fixture
def mock_camera_service():
    """Create a mock CameraService."""
    service = MagicMock()
    service.get_camera = AsyncMock()
    return service


@pytest.mark.skipif(discover_onvif_devices is None, reason="ONVIF routes not implemented yet")
class TestDiscoverOnvifDevices:
    """Test POST /api/cameras/onvif/discover endpoint."""

    @pytest.mark.asyncio
    async def test_discover_devices_success(self, mock_onvif_service):
        """Test successful device discovery returns list of devices."""
        # Mock discovery response
        mock_devices = [
            {
                "device_url": "http://192.168.1.100/onvif/device_service",
                "manufacturer": "Manufacturer A",
                "model": "Model A",
                "firmware_version": "1.0.0",
                "serial_number": "SN001",
                "hardware_id": "HW001",
            },
            {
                "device_url": "http://192.168.1.101/onvif/device_service",
                "manufacturer": "Manufacturer B",
                "model": "Model B",
                "firmware_version": "2.0.0",
                "serial_number": "SN002",
                "hardware_id": "HW002",
            },
        ]
        mock_onvif_service.discover_devices.return_value = mock_devices

        result = await discover_onvif_devices(
            subnet="192.168.1.0/24", timeout=5, onvif_service=mock_onvif_service
        )

        assert hasattr(result, "devices")
        assert hasattr(result, "count")
        assert len(result.devices) == 2
        assert result.devices[0].manufacturer == "Manufacturer A"
        mock_onvif_service.discover_devices.assert_called_once_with(
            subnet="192.168.1.0/24", timeout=5
        )

    @pytest.mark.asyncio
    async def test_discover_devices_empty_result(self, mock_onvif_service):
        """Test device discovery with no devices found."""
        mock_onvif_service.discover_devices.return_value = []

        result = await discover_onvif_devices(
            subnet="192.168.1.0/24", timeout=5, onvif_service=mock_onvif_service
        )

        assert result.devices == []
        assert result.count == 0

    @pytest.mark.asyncio
    async def test_discover_devices_default_timeout(self, mock_onvif_service):
        """Test device discovery uses default timeout."""
        mock_onvif_service.discover_devices.return_value = []

        await discover_onvif_devices(subnet="192.168.1.0/24", onvif_service=mock_onvif_service)

        mock_onvif_service.discover_devices.assert_called_once_with(
            subnet="192.168.1.0/24",
            timeout=10,  # Default timeout
        )

    @pytest.mark.asyncio
    async def test_discover_devices_service_error(self, mock_onvif_service):
        """Test device discovery handles service errors."""
        mock_onvif_service.discover_devices.side_effect = Exception("Discovery failed")

        with pytest.raises(HTTPException) as exc_info:
            await discover_onvif_devices(
                subnet="192.168.1.0/24", timeout=5, onvif_service=mock_onvif_service
            )

        assert exc_info.value.status_code == 500
        assert "Discovery failed" in str(exc_info.value.detail)


@pytest.mark.skipif(get_device_capabilities is None, reason="ONVIF routes not implemented yet")
class TestGetDeviceCapabilities:
    """Test GET /api/cameras/{camera_id}/onvif/capabilities endpoint."""

    @pytest.mark.asyncio
    async def test_get_capabilities_success(self, mock_onvif_service, mock_camera_service):
        """Test successful capability retrieval."""
        # Mock camera exists
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        # Mock capabilities response
        capabilities = {
            "manufacturer": "Test Manufacturer",
            "model": "Test Model",
            "firmware_version": "1.0.0",
            "serial_number": "TEST123456",
            "ptz_supported": True,
            "media_supported": True,
            "analytics_supported": False,
        }
        mock_onvif_service.get_capabilities.return_value = capabilities

        result = await get_device_capabilities(
            camera_id="front_door",
            onvif_service=mock_onvif_service,
            camera_service=mock_camera_service,
        )

        assert result.manufacturer == "Test Manufacturer"
        assert result.model == "Test Model"
        assert result.ptz_supported is True
        mock_onvif_service.get_capabilities.assert_called_once_with(camera_id="front_door")

    @pytest.mark.asyncio
    async def test_get_capabilities_camera_not_found(self, mock_onvif_service, mock_camera_service):
        """Test capability retrieval when camera doesn't exist."""
        mock_camera_service.get_camera.side_effect = ValueError("Camera not found")

        with pytest.raises(HTTPException) as exc_info:
            await get_device_capabilities(
                camera_id="nonexistent",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_capabilities_not_onvif_camera(self, mock_onvif_service, mock_camera_service):
        """Test capability retrieval for non-ONVIF camera returns 409."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.get_capabilities.side_effect = ValueError("Not an ONVIF camera")

        with pytest.raises(HTTPException) as exc_info:
            await get_device_capabilities(
                camera_id="front_door",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 409
        assert "ONVIF" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_capabilities_device_unreachable(
        self, mock_onvif_service, mock_camera_service
    ):
        """Test capability retrieval when device is unreachable."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.get_capabilities.side_effect = Exception("Connection refused")

        with pytest.raises(HTTPException) as exc_info:
            await get_device_capabilities(
                camera_id="front_door",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 503
        assert "unreachable" in str(exc_info.value.detail).lower()


@pytest.mark.skipif(execute_ptz_command is None, reason="ONVIF routes not implemented yet")
class TestExecutePTZCommand:
    """Test POST /api/cameras/{camera_id}/onvif/ptz endpoint."""

    @pytest.mark.asyncio
    async def test_execute_ptz_pan_command(self, mock_onvif_service, mock_camera_service):
        """Test executing pan PTZ command."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.execute_ptz_command.return_value = True

        result = await execute_ptz_command(
            camera_id="front_door",
            command="pan",
            value=0.5,
            speed=1.0,
            onvif_service=mock_onvif_service,
            camera_service=mock_camera_service,
        )

        assert result.success is True
        assert result.command == "pan"
        mock_onvif_service.execute_ptz_command.assert_called_once_with(
            camera_id="front_door", command="pan", value=0.5, speed=1.0
        )

    @pytest.mark.asyncio
    async def test_execute_ptz_tilt_command(self, mock_onvif_service, mock_camera_service):
        """Test executing tilt PTZ command."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.execute_ptz_command.return_value = True

        result = await execute_ptz_command(
            camera_id="front_door",
            command="tilt",
            value=-0.3,
            speed=0.8,
            onvif_service=mock_onvif_service,
            camera_service=mock_camera_service,
        )

        assert result.success is True
        assert result.command == "tilt"

    @pytest.mark.asyncio
    async def test_execute_ptz_zoom_command(self, mock_onvif_service, mock_camera_service):
        """Test executing zoom PTZ command."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.execute_ptz_command.return_value = True

        result = await execute_ptz_command(
            camera_id="front_door",
            command="zoom",
            value=0.2,
            speed=1.0,
            onvif_service=mock_onvif_service,
            camera_service=mock_camera_service,
        )

        assert result.success is True
        assert result.command == "zoom"

    @pytest.mark.asyncio
    async def test_execute_ptz_stop_command(self, mock_onvif_service, mock_camera_service):
        """Test executing stop PTZ command."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.execute_ptz_command.return_value = True

        result = await execute_ptz_command(
            camera_id="front_door",
            command="stop",
            value=0.0,
            speed=0.0,
            onvif_service=mock_onvif_service,
            camera_service=mock_camera_service,
        )

        assert result.success is True
        assert result.command == "stop"

    @pytest.mark.asyncio
    async def test_execute_ptz_camera_not_found(self, mock_onvif_service, mock_camera_service):
        """Test PTZ command when camera doesn't exist."""
        mock_camera_service.get_camera.side_effect = ValueError("Camera not found")

        with pytest.raises(HTTPException) as exc_info:
            await execute_ptz_command(
                camera_id="nonexistent",
                command="pan",
                value=0.5,
                speed=1.0,
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_ptz_not_onvif_camera(self, mock_onvif_service, mock_camera_service):
        """Test PTZ command for non-ONVIF camera returns 409."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.execute_ptz_command.side_effect = ValueError("Not an ONVIF camera")

        with pytest.raises(HTTPException) as exc_info:
            await execute_ptz_command(
                camera_id="front_door",
                command="pan",
                value=0.5,
                speed=1.0,
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_execute_ptz_device_unreachable(self, mock_onvif_service, mock_camera_service):
        """Test PTZ command when device is unreachable."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.execute_ptz_command.side_effect = Exception("Connection refused")

        with pytest.raises(HTTPException) as exc_info:
            await execute_ptz_command(
                camera_id="front_door",
                command="pan",
                value=0.5,
                speed=1.0,
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_execute_ptz_invalid_command(self, mock_onvif_service, mock_camera_service):
        """Test PTZ command with invalid command type."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.execute_ptz_command.side_effect = ValueError("Invalid PTZ command")

        with pytest.raises(HTTPException) as exc_info:
            await execute_ptz_command(
                camera_id="front_door",
                command="invalid",
                value=0.5,
                speed=1.0,
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 400
        assert "Invalid" in str(exc_info.value.detail)


@pytest.mark.skipif(get_ptz_presets is None, reason="ONVIF routes not implemented yet")
class TestGetPTZPresets:
    """Test GET /api/cameras/{camera_id}/onvif/presets endpoint."""

    @pytest.mark.asyncio
    async def test_get_presets_success(self, mock_onvif_service, mock_camera_service):
        """Test successful preset retrieval."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_presets = [
            {"token": "preset_1", "name": "Front Door View"},
            {"token": "preset_2", "name": "Driveway View"},
        ]
        mock_onvif_service.get_presets.return_value = mock_presets

        result = await get_ptz_presets(
            camera_id="front_door",
            onvif_service=mock_onvif_service,
            camera_service=mock_camera_service,
        )

        assert hasattr(result, "presets")
        assert hasattr(result, "count")
        assert len(result.presets) == 2
        assert result.presets[0].name == "Front Door View"
        mock_onvif_service.get_presets.assert_called_once_with(camera_id="front_door")

    @pytest.mark.asyncio
    async def test_get_presets_empty_list(self, mock_onvif_service, mock_camera_service):
        """Test preset retrieval with no presets configured."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.get_presets.return_value = []

        result = await get_ptz_presets(
            camera_id="front_door",
            onvif_service=mock_onvif_service,
            camera_service=mock_camera_service,
        )

        assert result.presets == []
        assert result.count == 0

    @pytest.mark.asyncio
    async def test_get_presets_camera_not_found(self, mock_onvif_service, mock_camera_service):
        """Test preset retrieval when camera doesn't exist."""
        mock_camera_service.get_camera.side_effect = ValueError("Camera not found")

        with pytest.raises(HTTPException) as exc_info:
            await get_ptz_presets(
                camera_id="nonexistent",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_presets_not_onvif_camera(self, mock_onvif_service, mock_camera_service):
        """Test preset retrieval for non-ONVIF camera returns 409."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.get_presets.side_effect = ValueError("Not an ONVIF camera")

        with pytest.raises(HTTPException) as exc_info:
            await get_ptz_presets(
                camera_id="front_door",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 409


@pytest.mark.skipif(goto_ptz_preset is None, reason="ONVIF routes not implemented yet")
class TestGotoPTZPreset:
    """Test POST /api/cameras/{camera_id}/onvif/presets/{preset_token} endpoint."""

    @pytest.mark.asyncio
    async def test_goto_preset_success(self, mock_onvif_service, mock_camera_service):
        """Test successful navigation to preset."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.goto_preset.return_value = True

        result = await goto_ptz_preset(
            camera_id="front_door",
            preset_token="preset_1",
            onvif_service=mock_onvif_service,
            camera_service=mock_camera_service,
        )

        assert result.success is True
        assert result.preset_token == "preset_1"
        mock_onvif_service.goto_preset.assert_called_once_with(
            camera_id="front_door", preset_token="preset_1"
        )

    @pytest.mark.asyncio
    async def test_goto_preset_camera_not_found(self, mock_onvif_service, mock_camera_service):
        """Test preset navigation when camera doesn't exist."""
        mock_camera_service.get_camera.side_effect = ValueError("Camera not found")

        with pytest.raises(HTTPException) as exc_info:
            await goto_ptz_preset(
                camera_id="nonexistent",
                preset_token="preset_1",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_goto_preset_invalid_token(self, mock_onvif_service, mock_camera_service):
        """Test preset navigation with invalid preset token."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.goto_preset.side_effect = ValueError("Invalid preset token")

        with pytest.raises(HTTPException) as exc_info:
            await goto_ptz_preset(
                camera_id="front_door",
                preset_token="invalid_preset",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 400
        assert "Invalid" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_goto_preset_not_onvif_camera(self, mock_onvif_service, mock_camera_service):
        """Test preset navigation for non-ONVIF camera returns 409."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.goto_preset.side_effect = ValueError("Not an ONVIF camera")

        with pytest.raises(HTTPException) as exc_info:
            await goto_ptz_preset(
                camera_id="front_door",
                preset_token="preset_1",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_goto_preset_device_unreachable(self, mock_onvif_service, mock_camera_service):
        """Test preset navigation when device is unreachable."""
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_service.get_camera.return_value = mock_camera

        mock_onvif_service.goto_preset.side_effect = Exception("Connection refused")

        with pytest.raises(HTTPException) as exc_info:
            await goto_ptz_preset(
                camera_id="front_door",
                preset_token="preset_1",
                onvif_service=mock_onvif_service,
                camera_service=mock_camera_service,
            )

        assert exc_info.value.status_code == 503
