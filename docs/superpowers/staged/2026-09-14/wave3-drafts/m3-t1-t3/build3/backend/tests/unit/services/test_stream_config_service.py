"""Unit tests for stream configuration service (NEM-4394, NEM-4395).

Tests stream configuration service logic for reading/writing camera stream settings
via ONVIF Media service. This is part of Phase 3: Stream Settings Control.

Run with: uv run pytest backend/tests/unit/services/test_stream_config_service.py -v

TDD RED Phase: These tests will FAIL initially since StreamConfigService doesn't exist yet.
Implementation will follow in GREEN phase.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# Import will fail until GREEN phase implementation
try:
    from backend.services.stream_config_service import StreamConfigService
except ImportError:
    StreamConfigService = None  # type: ignore


@pytest.mark.skipif(StreamConfigService is None, reason="StreamConfigService not implemented yet")
class TestStreamConfigServiceGetConfig:
    """Tests for getting stream configuration from camera."""

    @pytest.mark.asyncio
    async def test_get_stream_config_returns_current_settings(self):
        """Test get_stream_config returns current encoder settings from ONVIF."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()

        # Mock ONVIF Media service response
        mock_profile = MagicMock()
        mock_profile.token = "Profile_1"
        mock_profile.name = "mainStream"
        mock_profile.video_encoder_configuration = MagicMock()
        mock_profile.video_encoder_configuration.encoding = "H264"
        mock_profile.video_encoder_configuration.resolution = MagicMock(width=1920, height=1080)
        mock_profile.video_encoder_configuration.bitrate_limit = 4096
        mock_profile.video_encoder_configuration.framerate_limit = 25
        mock_profile.video_encoder_configuration.gop_length = 50

        mock_onvif_client.get_profiles = AsyncMock(return_value=[mock_profile])
        mock_onvif_client.get_video_encoder_configuration_options = AsyncMock(
            return_value=MagicMock(
                resolutions=["1920x1080", "1280x720", "640x480"],
                codecs=["H264", "H265"],
                bitrate_range=MagicMock(min=512, max=8192),
                fps_range=MagicMock(min=1, max=30),
            )
        )

        result = await service.get_stream_config(
            camera_id="front_door",
            onvif_client=mock_onvif_client,
        )

        assert len(result["profiles"]) == 1
        assert result["profiles"][0]["token"] == "Profile_1"
        assert result["profiles"][0]["encoder"]["codec"] == "H264"
        assert result["profiles"][0]["encoder"]["resolution"]["width"] == 1920
        assert result["profiles"][0]["encoder"]["resolution"]["height"] == 1080
        assert result["profiles"][0]["encoder"]["bitrate"] == 4096
        assert result["profiles"][0]["encoder"]["fps"] == 25
        assert result["capabilities"]["available_resolutions"] == [
            "1920x1080",
            "1280x720",
            "640x480",
        ]
        assert result["capabilities"]["available_codecs"] == ["H264", "H265"]
        assert result["read_only"] is False

    @pytest.mark.asyncio
    async def test_get_stream_config_handles_multiple_profiles(self):
        """Test get_stream_config returns all profiles (main/sub streams)."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()

        # Mock main stream profile
        mock_main_profile = MagicMock()
        mock_main_profile.token = "Profile_1"
        mock_main_profile.name = "mainStream"
        mock_main_profile.video_encoder_configuration = MagicMock()
        mock_main_profile.video_encoder_configuration.encoding = "H264"
        mock_main_profile.video_encoder_configuration.resolution = MagicMock(
            width=1920, height=1080
        )
        mock_main_profile.video_encoder_configuration.bitrate_limit = 4096
        mock_main_profile.video_encoder_configuration.framerate_limit = 25

        # Mock sub stream profile
        mock_sub_profile = MagicMock()
        mock_sub_profile.token = "Profile_2"
        mock_sub_profile.name = "subStream"
        mock_sub_profile.video_encoder_configuration = MagicMock()
        mock_sub_profile.video_encoder_configuration.encoding = "H264"
        mock_sub_profile.video_encoder_configuration.resolution = MagicMock(width=640, height=480)
        mock_sub_profile.video_encoder_configuration.bitrate_limit = 512
        mock_sub_profile.video_encoder_configuration.framerate_limit = 15

        mock_onvif_client.get_profiles = AsyncMock(
            return_value=[mock_main_profile, mock_sub_profile]
        )
        mock_onvif_client.get_video_encoder_configuration_options = AsyncMock(
            return_value=MagicMock(
                resolutions=["1920x1080", "640x480"],
                codecs=["H264"],
                bitrate_range=MagicMock(min=512, max=8192),
                fps_range=MagicMock(min=1, max=30),
            )
        )

        result = await service.get_stream_config(
            camera_id="front_door",
            onvif_client=mock_onvif_client,
        )

        assert len(result["profiles"]) == 2
        assert result["profiles"][0]["name"] == "mainStream"
        assert result["profiles"][1]["name"] == "subStream"
        assert result["profiles"][0]["encoder"]["resolution"]["width"] == 1920
        assert result["profiles"][1]["encoder"]["resolution"]["width"] == 640

    @pytest.mark.asyncio
    async def test_get_stream_config_detects_read_only_cameras(self):
        """Test get_stream_config detects cameras that don't support write operations."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()

        mock_profile = MagicMock()
        mock_profile.token = "Profile_1"
        mock_profile.name = "mainStream"
        mock_profile.video_encoder_configuration = MagicMock()
        mock_profile.video_encoder_configuration.encoding = "H264"
        mock_profile.video_encoder_configuration.resolution = MagicMock(width=1920, height=1080)
        mock_profile.video_encoder_configuration.bitrate_limit = 4096
        mock_profile.video_encoder_configuration.framerate_limit = 25

        mock_onvif_client.get_profiles = AsyncMock(return_value=[mock_profile])
        mock_onvif_client.get_video_encoder_configuration_options = AsyncMock(
            return_value=MagicMock(
                resolutions=["1920x1080"],
                codecs=["H264"],
                bitrate_range=MagicMock(min=512, max=4096),
                fps_range=MagicMock(min=1, max=25),
            )
        )
        # Simulate camera that doesn't support SetVideoEncoderConfiguration
        mock_onvif_client.supports_video_encoder_configuration = False

        result = await service.get_stream_config(
            camera_id="front_door",
            onvif_client=mock_onvif_client,
        )

        assert result["read_only"] is True

    @pytest.mark.asyncio
    async def test_get_stream_config_handles_onvif_connection_failure(self):
        """Test get_stream_config raises error when ONVIF connection fails."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()

        mock_onvif_client.get_profiles = AsyncMock(
            side_effect=ConnectionError("Failed to connect to camera")
        )

        with pytest.raises(ConnectionError, match="Failed to connect to camera"):
            await service.get_stream_config(
                camera_id="front_door",
                onvif_client=mock_onvif_client,
            )

    @pytest.mark.asyncio
    async def test_get_stream_config_handles_onvif_timeout(self):
        """Test get_stream_config raises error when ONVIF request times out."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()

        mock_onvif_client.get_profiles = AsyncMock(
            side_effect=TimeoutError("ONVIF request timeout")
        )

        with pytest.raises(TimeoutError, match="ONVIF request timeout"):
            await service.get_stream_config(
                camera_id="front_door",
                onvif_client=mock_onvif_client,
            )

    @pytest.mark.asyncio
    async def test_get_stream_config_handles_missing_video_encoder(self):
        """Test get_stream_config handles profiles without video encoder config."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()

        # Mock profile without video encoder configuration
        mock_profile = MagicMock()
        mock_profile.token = "Profile_1"
        mock_profile.name = "audioOnly"
        mock_profile.video_encoder_configuration = None

        mock_onvif_client.get_profiles = AsyncMock(return_value=[mock_profile])

        with pytest.raises(ValueError, match="No video encoder configuration found"):
            await service.get_stream_config(
                camera_id="front_door",
                onvif_client=mock_onvif_client,
            )


@pytest.mark.skipif(StreamConfigService is None, reason="StreamConfigService not implemented yet")
class TestStreamConfigServiceSetConfig:
    """Tests for setting stream configuration on camera."""

    @pytest.mark.asyncio
    async def test_set_stream_config_applies_new_settings(self):
        """Test set_stream_config applies new encoder settings via ONVIF."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()
        mock_onvif_client.set_video_encoder_configuration = AsyncMock()

        await service.set_stream_config(
            camera_id="front_door",
            onvif_client=mock_onvif_client,
            profile_token="Profile_1",
            resolution={"width": 1280, "height": 720},
            bitrate=2048,
            fps=15,
        )

        mock_onvif_client.set_video_encoder_configuration.assert_called_once()
        call_kwargs = mock_onvif_client.set_video_encoder_configuration.call_args.kwargs
        assert call_kwargs["profile_token"] == "Profile_1"
        assert call_kwargs["resolution"]["width"] == 1280
        assert call_kwargs["resolution"]["height"] == 720
        assert call_kwargs["bitrate"] == 2048
        assert call_kwargs["fps"] == 15

    @pytest.mark.asyncio
    async def test_set_stream_config_partial_update_bitrate_only(self):
        """Test set_stream_config with partial update (bitrate only)."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()
        mock_onvif_client.set_video_encoder_configuration = AsyncMock()

        await service.set_stream_config(
            camera_id="front_door",
            onvif_client=mock_onvif_client,
            profile_token="Profile_1",
            bitrate=3072,
        )

        mock_onvif_client.set_video_encoder_configuration.assert_called_once()
        call_kwargs = mock_onvif_client.set_video_encoder_configuration.call_args.kwargs
        assert call_kwargs["bitrate"] == 3072
        assert "resolution" not in call_kwargs or call_kwargs["resolution"] is None

    @pytest.mark.asyncio
    async def test_set_stream_config_partial_update_resolution_only(self):
        """Test set_stream_config with partial update (resolution only)."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()
        mock_onvif_client.set_video_encoder_configuration = AsyncMock()

        await service.set_stream_config(
            camera_id="front_door",
            onvif_client=mock_onvif_client,
            profile_token="Profile_1",
            resolution={"width": 1280, "height": 720},
        )

        mock_onvif_client.set_video_encoder_configuration.assert_called_once()
        call_kwargs = mock_onvif_client.set_video_encoder_configuration.call_args.kwargs
        assert call_kwargs["resolution"]["width"] == 1280
        assert call_kwargs["resolution"]["height"] == 720

    @pytest.mark.asyncio
    async def test_set_stream_config_validates_settings_before_applying(self):
        """Test set_stream_config validates settings against camera capabilities."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()

        # Mock capabilities with limited bitrate range
        mock_capabilities = MagicMock()
        mock_capabilities.bitrate_range = MagicMock(min=512, max=4096)
        mock_onvif_client.get_video_encoder_configuration_options = AsyncMock(
            return_value=mock_capabilities
        )

        # Attempt to set bitrate exceeding camera's max
        with pytest.raises(ValueError, match="bitrate.*exceeds camera maximum"):
            await service.set_stream_config(
                camera_id="front_door",
                onvif_client=mock_onvif_client,
                profile_token="Profile_1",
                bitrate=8192,  # Exceeds max of 4096
            )

    @pytest.mark.asyncio
    async def test_set_stream_config_validates_resolution_supported(self):
        """Test set_stream_config validates resolution is supported by camera."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()

        # Mock capabilities with limited resolutions
        mock_capabilities = MagicMock()
        mock_capabilities.resolutions = ["1920x1080", "1280x720"]
        mock_onvif_client.get_video_encoder_configuration_options = AsyncMock(
            return_value=mock_capabilities
        )

        # Attempt to set unsupported resolution
        with pytest.raises(ValueError, match="resolution.*not supported"):
            await service.set_stream_config(
                camera_id="front_door",
                onvif_client=mock_onvif_client,
                profile_token="Profile_1",
                resolution={"width": 640, "height": 480},  # Not in supported list
            )

    @pytest.mark.asyncio
    async def test_set_stream_config_validates_codec_supported(self):
        """Test set_stream_config validates codec is supported by camera."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()

        # Mock capabilities with only H264 support
        mock_capabilities = MagicMock()
        mock_capabilities.codecs = ["H264"]
        mock_onvif_client.get_video_encoder_configuration_options = AsyncMock(
            return_value=mock_capabilities
        )

        # Attempt to set unsupported codec
        with pytest.raises(ValueError, match="codec.*not supported"):
            await service.set_stream_config(
                camera_id="front_door",
                onvif_client=mock_onvif_client,
                profile_token="Profile_1",
                codec="H265",  # Not supported
            )

    @pytest.mark.asyncio
    async def test_set_stream_config_validates_fps_within_range(self):
        """Test set_stream_config validates FPS is within camera's range."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()

        # Mock capabilities with limited FPS range
        mock_capabilities = MagicMock()
        mock_capabilities.fps_range = MagicMock(min=1, max=25)
        mock_onvif_client.get_video_encoder_configuration_options = AsyncMock(
            return_value=mock_capabilities
        )

        # Attempt to set FPS exceeding camera's max
        with pytest.raises(ValueError, match="fps.*exceeds camera maximum"):
            await service.set_stream_config(
                camera_id="front_door",
                onvif_client=mock_onvif_client,
                profile_token="Profile_1",
                fps=30,  # Exceeds max of 25
            )

    @pytest.mark.asyncio
    async def test_set_stream_config_rejects_read_only_cameras(self):
        """Test set_stream_config rejects cameras that don't support write operations."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()
        mock_onvif_client.supports_video_encoder_configuration = False

        with pytest.raises(
            ValueError, match="Camera does not support stream configuration updates"
        ):
            await service.set_stream_config(
                camera_id="front_door",
                onvif_client=mock_onvif_client,
                profile_token="Profile_1",
                bitrate=2048,
            )

    @pytest.mark.asyncio
    async def test_set_stream_config_handles_onvif_failure(self):
        """Test set_stream_config handles ONVIF command failure gracefully."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()
        mock_onvif_client.set_video_encoder_configuration = AsyncMock(
            side_effect=RuntimeError("ONVIF SetVideoEncoderConfiguration failed")
        )

        with pytest.raises(RuntimeError, match="ONVIF SetVideoEncoderConfiguration failed"):
            await service.set_stream_config(
                camera_id="front_door",
                onvif_client=mock_onvif_client,
                profile_token="Profile_1",
                bitrate=2048,
            )

    @pytest.mark.asyncio
    async def test_set_stream_config_handles_invalid_profile_token(self):
        """Test set_stream_config handles invalid profile token."""
        service = StreamConfigService()
        mock_onvif_client = MagicMock()
        mock_onvif_client.set_video_encoder_configuration = AsyncMock(
            side_effect=ValueError("Invalid profile token")
        )

        with pytest.raises(ValueError, match="Invalid profile token"):
            await service.set_stream_config(
                camera_id="front_door",
                onvif_client=mock_onvif_client,
                profile_token="InvalidToken",
                bitrate=2048,
            )


@pytest.mark.skipif(StreamConfigService is None, reason="StreamConfigService not implemented yet")
class TestStreamConfigServiceValidation:
    """Tests for stream configuration validation logic."""

    @pytest.mark.asyncio
    async def test_validate_settings_accepts_valid_settings(self):
        """Test validate_settings accepts settings within camera limits."""
        service = StreamConfigService()

        mock_capabilities = MagicMock()
        mock_capabilities.resolutions = ["1920x1080", "1280x720"]
        mock_capabilities.codecs = ["H264", "H265"]
        mock_capabilities.bitrate_range = MagicMock(min=512, max=8192)
        mock_capabilities.fps_range = MagicMock(min=1, max=30)

        # Should not raise
        service.validate_settings(
            capabilities=mock_capabilities,
            resolution={"width": 1920, "height": 1080},
            codec="H264",
            bitrate=4096,
            fps=25,
        )

    @pytest.mark.asyncio
    async def test_validate_settings_rejects_bitrate_below_min(self):
        """Test validate_settings rejects bitrate below camera minimum."""
        service = StreamConfigService()

        mock_capabilities = MagicMock()
        mock_capabilities.bitrate_range = MagicMock(min=512, max=8192)

        with pytest.raises(ValueError, match="bitrate.*below camera minimum"):
            service.validate_settings(
                capabilities=mock_capabilities,
                bitrate=256,  # Below min of 512
            )

    @pytest.mark.asyncio
    async def test_validate_settings_rejects_fps_below_min(self):
        """Test validate_settings rejects FPS below camera minimum."""
        service = StreamConfigService()

        mock_capabilities = MagicMock()
        mock_capabilities.fps_range = MagicMock(min=5, max=30)

        with pytest.raises(ValueError, match="fps.*below camera minimum"):
            service.validate_settings(
                capabilities=mock_capabilities,
                fps=1,  # Below min of 5
            )

    @pytest.mark.asyncio
    async def test_validate_settings_allows_none_values(self):
        """Test validate_settings allows None for optional fields."""
        service = StreamConfigService()

        mock_capabilities = MagicMock()
        mock_capabilities.resolutions = ["1920x1080"]
        mock_capabilities.codecs = ["H264"]
        mock_capabilities.bitrate_range = MagicMock(min=512, max=8192)
        mock_capabilities.fps_range = MagicMock(min=1, max=30)

        # Should not raise - None values are valid for partial updates
        service.validate_settings(
            capabilities=mock_capabilities,
            resolution=None,
            codec=None,
            bitrate=2048,
            fps=None,
        )
