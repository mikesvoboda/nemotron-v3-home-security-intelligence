"""Unit tests for OnvifService.

Tests the ONVIF service's device discovery, PTZ control, and capability retrieval
using mocked onvif-zeep library.

Run with: uv run pytest backend/tests/unit/services/test_onvif_service.py -v

TDD Phase 4: These tests will FAIL initially since OnvifService doesn't exist yet.
Implementation will be done in Phase 5.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import will fail until Phase 5 implementation
try:
    from backend.services.onvif_service import OnvifService
except ImportError:
    OnvifService = None  # type: ignore


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_onvif_camera():
    """Create a mock ONVIF camera device."""
    camera = MagicMock()
    camera.xaddrs = "http://192.168.1.100/onvif/device_service"
    camera.hostname = "192.168.1.100"

    # Mock device capabilities
    camera.devicemgmt = MagicMock()
    camera.media = MagicMock()
    camera.ptz = MagicMock()

    # Mock device info
    device_info = MagicMock()
    device_info.Manufacturer = "Test Manufacturer"
    device_info.Model = "Test Model"
    device_info.FirmwareVersion = "1.0.0"
    device_info.SerialNumber = "TEST123456"
    device_info.HardwareId = "HW-001"
    camera.devicemgmt.GetDeviceInformation.return_value = device_info

    return camera


@pytest.fixture
def mock_wsdiscovery():
    """Create a mock WSDiscovery client for device discovery."""
    with patch("backend.services.onvif_service.WSDiscovery") as mock:
        discovery = MagicMock()
        mock.return_value = discovery
        yield discovery


@pytest.fixture
def mock_onvif_camera_class():
    """Create a mock ONVIFCamera class from onvif library."""
    with patch("backend.services.onvif_service.ONVIFCamera") as mock:
        yield mock


@pytest.mark.skipif(OnvifService is None, reason="OnvifService not implemented yet")
class TestOnvifServiceInit:
    """Test OnvifService initialization."""

    def test_init_accepts_session_and_redis(self, mock_session, mock_redis):
        """Test that OnvifService accepts session and redis parameters."""
        service = OnvifService(mock_session, mock_redis)

        assert service.session == mock_session
        assert service.redis == mock_redis


@pytest.mark.skipif(OnvifService is None, reason="OnvifService not implemented yet")
class TestDiscoverDevices:
    """Test ONVIF device discovery functionality."""

    @pytest.mark.asyncio
    async def test_discover_devices_returns_list(
        self, mock_session, mock_redis, mock_wsdiscovery, mock_onvif_camera
    ):
        """Test discover_devices returns list of discovered devices."""
        # Mock WS-Discovery to return devices
        mock_wsdiscovery.searchServices.return_value = [mock_onvif_camera]

        service = OnvifService(mock_session, mock_redis)
        devices = await service.discover_devices(subnet="192.168.1.0/24", timeout=5)

        assert isinstance(devices, list)
        assert len(devices) == 1
        assert "device_url" in devices[0]
        assert "manufacturer" in devices[0]
        assert "model" in devices[0]

    @pytest.mark.asyncio
    async def test_discover_devices_with_timeout(self, mock_session, mock_redis, mock_wsdiscovery):
        """Test discover_devices respects timeout parameter."""
        mock_wsdiscovery.searchServices.return_value = []

        service = OnvifService(mock_session, mock_redis)
        devices = await service.discover_devices(subnet="192.168.1.0/24", timeout=3)

        assert isinstance(devices, list)
        assert len(devices) == 0
        # Verify timeout was used
        mock_wsdiscovery.searchServices.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_devices_filters_non_onvif(
        self, mock_session, mock_redis, mock_wsdiscovery
    ):
        """Test discover_devices filters out non-ONVIF devices."""
        # Create a mix of ONVIF and non-ONVIF devices
        onvif_device = MagicMock()
        onvif_device.xaddrs = "http://192.168.1.100/onvif/device_service"

        non_onvif_device = MagicMock()
        non_onvif_device.xaddrs = "http://192.168.1.101/other/service"

        mock_wsdiscovery.searchServices.return_value = [onvif_device, non_onvif_device]

        service = OnvifService(mock_session, mock_redis)
        devices = await service.discover_devices(subnet="192.168.1.0/24", timeout=5)

        # Only ONVIF devices should be returned
        assert len(devices) == 1
        assert "192.168.1.100" in devices[0]["device_url"]

    @pytest.mark.asyncio
    async def test_discover_devices_handles_discovery_failure(
        self, mock_session, mock_redis, mock_wsdiscovery
    ):
        """Test discover_devices handles discovery failures gracefully."""
        mock_wsdiscovery.searchServices.side_effect = Exception("Discovery failed")

        service = OnvifService(mock_session, mock_redis)

        with pytest.raises(Exception, match="Discovery failed"):
            await service.discover_devices(subnet="192.168.1.0/24", timeout=5)


@pytest.mark.skipif(OnvifService is None, reason="OnvifService not implemented yet")
class TestGetCapabilities:
    """Test ONVIF device capability retrieval."""

    @pytest.mark.asyncio
    async def test_get_capabilities_returns_device_info(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test get_capabilities returns device information dictionary."""
        # Mock camera lookup
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_camera_model.name = "Front Door"

        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        # Mock ONVIF camera
        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance

        # Mock device info
        device_info = MagicMock()
        device_info.Manufacturer = "Test Manufacturer"
        device_info.Model = "Test Model"
        device_info.FirmwareVersion = "1.0.0"
        mock_onvif_instance.devicemgmt.GetDeviceInformation.return_value = device_info

        # Mock capabilities
        capabilities = MagicMock()
        capabilities.PTZ = MagicMock()
        capabilities.Media = MagicMock()
        mock_onvif_instance.devicemgmt.GetCapabilities.return_value = capabilities

        service = OnvifService(mock_session, mock_redis)
        result = await service.get_capabilities(camera_id="front_door")

        assert isinstance(result, dict)
        assert result["manufacturer"] == "Test Manufacturer"
        assert result["model"] == "Test Model"
        assert result["firmware_version"] == "1.0.0"
        assert "ptz_supported" in result
        assert "media_supported" in result

    @pytest.mark.asyncio
    async def test_get_capabilities_camera_not_found(self, mock_session, mock_redis):
        """Test get_capabilities raises error when camera not found."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        service = OnvifService(mock_session, mock_redis)

        with pytest.raises(ValueError, match="Camera .* not found"):
            await service.get_capabilities(camera_id="nonexistent")

    @pytest.mark.asyncio
    async def test_get_capabilities_connection_failure(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test get_capabilities handles connection failures."""
        # Mock camera lookup
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        # Mock connection failure
        mock_onvif_camera_class.side_effect = Exception("Connection refused")

        service = OnvifService(mock_session, mock_redis)

        with pytest.raises(Exception, match="Connection refused"):
            await service.get_capabilities(camera_id="front_door")


@pytest.mark.skipif(OnvifService is None, reason="OnvifService not implemented yet")
class TestExecutePtzCommand:
    """Test PTZ command execution."""

    @pytest.mark.asyncio
    async def test_execute_ptz_pan_command(self, mock_session, mock_redis, mock_onvif_camera_class):
        """Test executing pan PTZ command."""
        # Mock camera lookup
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        # Mock ONVIF camera with PTZ
        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance
        mock_onvif_instance.ptz = MagicMock()

        service = OnvifService(mock_session, mock_redis)
        result = await service.execute_ptz_command(
            camera_id="front_door", command="pan", value=0.5, speed=1.0
        )

        assert result is True
        mock_onvif_instance.ptz.ContinuousMove.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_ptz_tilt_command(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test executing tilt PTZ command."""
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance
        mock_onvif_instance.ptz = MagicMock()

        service = OnvifService(mock_session, mock_redis)
        result = await service.execute_ptz_command(
            camera_id="front_door", command="tilt", value=-0.3, speed=0.8
        )

        assert result is True
        mock_onvif_instance.ptz.ContinuousMove.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_ptz_zoom_command(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test executing zoom PTZ command."""
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance
        mock_onvif_instance.ptz = MagicMock()

        service = OnvifService(mock_session, mock_redis)
        result = await service.execute_ptz_command(
            camera_id="front_door", command="zoom", value=0.2, speed=1.0
        )

        assert result is True
        mock_onvif_instance.ptz.ContinuousMove.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_ptz_stop_command(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test executing stop PTZ command."""
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance
        mock_onvif_instance.ptz = MagicMock()

        service = OnvifService(mock_session, mock_redis)
        result = await service.execute_ptz_command(
            camera_id="front_door", command="stop", value=0.0, speed=0.0
        )

        assert result is True
        mock_onvif_instance.ptz.Stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_ptz_invalid_command(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test executing invalid PTZ command raises error."""
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        service = OnvifService(mock_session, mock_redis)

        with pytest.raises(ValueError, match="Invalid PTZ command"):
            await service.execute_ptz_command(
                camera_id="front_door", command="invalid", value=0.0, speed=1.0
            )

    @pytest.mark.asyncio
    async def test_execute_ptz_value_out_of_range(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test PTZ command with out-of-range value."""
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        service = OnvifService(mock_session, mock_redis)

        with pytest.raises(ValueError, match="PTZ value must be between -1.0 and 1.0"):
            await service.execute_ptz_command(
                camera_id="front_door",
                command="pan",
                value=2.0,  # Out of range
                speed=1.0,
            )

    @pytest.mark.asyncio
    async def test_execute_ptz_camera_not_found(self, mock_session, mock_redis):
        """Test PTZ command fails when camera not found."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        service = OnvifService(mock_session, mock_redis)

        with pytest.raises(ValueError, match="Camera .* not found"):
            await service.execute_ptz_command(
                camera_id="nonexistent", command="pan", value=0.5, speed=1.0
            )


@pytest.mark.skipif(OnvifService is None, reason="OnvifService not implemented yet")
class TestGetRtspUrlFromDevice:
    """Test RTSP URL extraction from ONVIF device."""

    @pytest.mark.asyncio
    async def test_get_rtsp_url_from_device_success(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test successful RTSP URL extraction."""
        # Mock ONVIF camera
        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance

        # Mock media profiles
        profile = MagicMock()
        profile.token = "profile_token_1"
        mock_onvif_instance.media.GetProfiles.return_value = [profile]

        # Mock stream URI
        stream_uri = MagicMock()
        stream_uri.Uri = "rtsp://192.168.1.100:554/stream1"
        mock_onvif_instance.media.GetStreamUri.return_value = stream_uri

        service = OnvifService(mock_session, mock_redis)
        rtsp_url = await service.get_rtsp_url_from_device(
            device_url="http://192.168.1.100/onvif/device_service",
            username="admin",
            password="password123",  # pragma: allowlist secret
        )

        assert rtsp_url == "rtsp://192.168.1.100:554/stream1"
        mock_onvif_instance.media.GetProfiles.assert_called_once()
        mock_onvif_instance.media.GetStreamUri.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_rtsp_url_no_profiles(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test RTSP URL extraction when no profiles available."""
        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance
        mock_onvif_instance.media.GetProfiles.return_value = []

        service = OnvifService(mock_session, mock_redis)

        with pytest.raises(ValueError, match="No media profiles found"):
            await service.get_rtsp_url_from_device(
                device_url="http://192.168.1.100/onvif/device_service",
                username="admin",
                password="password123",  # pragma: allowlist secret
            )

    @pytest.mark.asyncio
    async def test_get_rtsp_url_connection_failure(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test RTSP URL extraction handles connection failures."""
        mock_onvif_camera_class.side_effect = Exception("Connection refused")

        service = OnvifService(mock_session, mock_redis)

        with pytest.raises(Exception, match="Connection refused"):
            await service.get_rtsp_url_from_device(
                device_url="http://192.168.1.100/onvif/device_service",
                username="admin",
                password="password123",  # pragma: allowlist secret
            )


@pytest.mark.skipif(OnvifService is None, reason="OnvifService not implemented yet")
class TestGetPresets:
    """Test PTZ preset retrieval."""

    @pytest.mark.asyncio
    async def test_get_presets_returns_list(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test get_presets returns list of available presets."""
        # Mock camera lookup
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        # Mock ONVIF camera
        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance

        # Mock presets
        preset1 = MagicMock()
        preset1.token = "preset_1"
        preset1.Name = "Front Door View"

        preset2 = MagicMock()
        preset2.token = "preset_2"
        preset2.Name = "Driveway View"

        mock_onvif_instance.ptz.GetPresets.return_value = [preset1, preset2]

        service = OnvifService(mock_session, mock_redis)
        presets = await service.get_presets(camera_id="front_door")

        assert isinstance(presets, list)
        assert len(presets) == 2
        assert presets[0]["token"] == "preset_1"
        assert presets[0]["name"] == "Front Door View"
        assert presets[1]["token"] == "preset_2"
        assert presets[1]["name"] == "Driveway View"

    @pytest.mark.asyncio
    async def test_get_presets_empty_list(self, mock_session, mock_redis, mock_onvif_camera_class):
        """Test get_presets returns empty list when no presets configured."""
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance
        mock_onvif_instance.ptz.GetPresets.return_value = []

        service = OnvifService(mock_session, mock_redis)
        presets = await service.get_presets(camera_id="front_door")

        assert isinstance(presets, list)
        assert len(presets) == 0

    @pytest.mark.asyncio
    async def test_get_presets_camera_not_found(self, mock_session, mock_redis):
        """Test get_presets fails when camera not found."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        service = OnvifService(mock_session, mock_redis)

        with pytest.raises(ValueError, match="Camera .* not found"):
            await service.get_presets(camera_id="nonexistent")


@pytest.mark.skipif(OnvifService is None, reason="OnvifService not implemented yet")
class TestGotoPreset:
    """Test PTZ preset navigation."""

    @pytest.mark.asyncio
    async def test_goto_preset_success(self, mock_session, mock_redis, mock_onvif_camera_class):
        """Test successful navigation to preset."""
        # Mock camera lookup
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        # Mock ONVIF camera
        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance
        mock_onvif_instance.ptz = MagicMock()

        service = OnvifService(mock_session, mock_redis)
        result = await service.goto_preset(camera_id="front_door", preset_token="preset_1")

        assert result is True
        mock_onvif_instance.ptz.GotoPreset.assert_called_once()

    @pytest.mark.asyncio
    async def test_goto_preset_invalid_token(
        self, mock_session, mock_redis, mock_onvif_camera_class
    ):
        """Test goto_preset with invalid preset token."""
        mock_camera_model = MagicMock()
        mock_camera_model.folder_path = "http://192.168.1.100/onvif/device_service"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_camera_model

        mock_onvif_instance = MagicMock()
        mock_onvif_camera_class.return_value = mock_onvif_instance
        mock_onvif_instance.ptz.GotoPreset.side_effect = Exception("Invalid preset token")

        service = OnvifService(mock_session, mock_redis)

        with pytest.raises(Exception, match="Invalid preset token"):
            await service.goto_preset(camera_id="front_door", preset_token="invalid_preset")

    @pytest.mark.asyncio
    async def test_goto_preset_camera_not_found(self, mock_session, mock_redis):
        """Test goto_preset fails when camera not found."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        service = OnvifService(mock_session, mock_redis)

        with pytest.raises(ValueError, match="Camera .* not found"):
            await service.goto_preset(camera_id="nonexistent", preset_token="preset_1")
