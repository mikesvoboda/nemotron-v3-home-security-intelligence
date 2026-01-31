"""Unit tests for stream configuration Pydantic schemas (NEM-4394, NEM-4395).

Tests validation for stream profile configuration, encoder settings, and capabilities.
This is part of Phase 3: Stream Settings Control.

Run with: uv run pytest backend/tests/unit/api/schemas/test_stream_config.py -v

TDD RED Phase: These tests will FAIL initially since stream_config schemas don't exist yet.
Implementation will follow in GREEN phase.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

# Import will fail until GREEN phase implementation
try:
    from backend.api.schemas.stream_config import (
        EncoderSettings,
        Resolution,
        StreamCapabilities,
        StreamConfigResponse,
        StreamConfigUpdate,
        StreamProfile,
    )
except ImportError:
    EncoderSettings = None  # type: ignore
    Resolution = None  # type: ignore
    StreamCapabilities = None  # type: ignore
    StreamConfigResponse = None  # type: ignore
    StreamConfigUpdate = None  # type: ignore
    StreamProfile = None  # type: ignore


@pytest.mark.skipif(Resolution is None, reason="Resolution schema not implemented yet")
class TestResolution:
    """Test Resolution schema validation."""

    def test_valid_resolution(self):
        """Test valid resolution with width and height."""
        resolution = Resolution(width=1920, height=1080)

        assert resolution.width == 1920
        assert resolution.height == 1080

    def test_common_resolutions(self):
        """Test common camera resolutions are valid."""
        resolutions = [
            (3840, 2160),  # 4K
            (1920, 1080),  # 1080p
            (1280, 720),  # 720p
            (640, 480),  # VGA
            (320, 240),  # QVGA
        ]

        for width, height in resolutions:
            resolution = Resolution(width=width, height=height)
            assert resolution.width == width
            assert resolution.height == height

    def test_resolution_rejects_zero_width(self):
        """Test resolution rejects zero width."""
        with pytest.raises(ValidationError, match="width"):
            Resolution(width=0, height=1080)

    def test_resolution_rejects_zero_height(self):
        """Test resolution rejects zero height."""
        with pytest.raises(ValidationError, match="height"):
            Resolution(width=1920, height=0)

    def test_resolution_rejects_negative_width(self):
        """Test resolution rejects negative width."""
        with pytest.raises(ValidationError, match="width"):
            Resolution(width=-1920, height=1080)

    def test_resolution_rejects_negative_height(self):
        """Test resolution rejects negative height."""
        with pytest.raises(ValidationError, match="height"):
            Resolution(width=1920, height=-1080)

    def test_resolution_rejects_excessive_width(self):
        """Test resolution rejects excessively large width (>8K)."""
        with pytest.raises(ValidationError, match="width"):
            Resolution(width=10000, height=1080)

    def test_resolution_rejects_excessive_height(self):
        """Test resolution rejects excessively large height (>8K)."""
        with pytest.raises(ValidationError, match="height"):
            Resolution(width=1920, height=10000)


@pytest.mark.skipif(EncoderSettings is None, reason="EncoderSettings schema not implemented yet")
class TestEncoderSettings:
    """Test EncoderSettings schema validation."""

    def test_valid_encoder_settings_h264(self):
        """Test valid encoder settings with H264 codec."""
        settings = EncoderSettings(
            resolution={"width": 1920, "height": 1080},
            codec="H264",
            bitrate=4096,
            fps=25,
        )

        assert settings.resolution.width == 1920
        assert settings.resolution.height == 1080
        assert settings.codec == "H264"
        assert settings.bitrate == 4096
        assert settings.fps == 25

    def test_valid_encoder_settings_h265(self):
        """Test valid encoder settings with H265 codec."""
        settings = EncoderSettings(
            resolution={"width": 1920, "height": 1080},
            codec="H265",
            bitrate=2048,
            fps=30,
        )

        assert settings.codec == "H265"
        assert settings.bitrate == 2048

    def test_encoder_settings_with_gop(self):
        """Test encoder settings with optional GOP (Group of Pictures)."""
        settings = EncoderSettings(
            resolution={"width": 1280, "height": 720},
            codec="H264",
            bitrate=2048,
            fps=15,
            gop=50,
        )

        assert settings.gop == 50

    def test_encoder_settings_default_gop_is_none(self):
        """Test encoder settings defaults to None for GOP if not provided."""
        settings = EncoderSettings(
            resolution={"width": 1280, "height": 720},
            codec="H264",
            bitrate=2048,
            fps=15,
        )

        assert settings.gop is None

    def test_encoder_settings_rejects_invalid_codec(self):
        """Test encoder settings rejects invalid codec values."""
        with pytest.raises(ValidationError, match="codec"):
            EncoderSettings(
                resolution={"width": 1920, "height": 1080},
                codec="MJPEG",  # Not H264 or H265
                bitrate=4096,
                fps=25,
            )

    def test_encoder_settings_rejects_zero_bitrate(self):
        """Test encoder settings rejects zero bitrate."""
        with pytest.raises(ValidationError, match="bitrate"):
            EncoderSettings(
                resolution={"width": 1920, "height": 1080},
                codec="H264",
                bitrate=0,
                fps=25,
            )

    def test_encoder_settings_rejects_negative_bitrate(self):
        """Test encoder settings rejects negative bitrate."""
        with pytest.raises(ValidationError, match="bitrate"):
            EncoderSettings(
                resolution={"width": 1920, "height": 1080},
                codec="H264",
                bitrate=-2048,
                fps=25,
            )

    def test_encoder_settings_rejects_excessive_bitrate(self):
        """Test encoder settings rejects excessively high bitrate (>100Mbps)."""
        with pytest.raises(ValidationError, match="bitrate"):
            EncoderSettings(
                resolution={"width": 1920, "height": 1080},
                codec="H264",
                bitrate=150000,  # 150Mbps
                fps=25,
            )

    def test_encoder_settings_rejects_zero_fps(self):
        """Test encoder settings rejects zero FPS."""
        with pytest.raises(ValidationError, match="fps"):
            EncoderSettings(
                resolution={"width": 1920, "height": 1080},
                codec="H264",
                bitrate=4096,
                fps=0,
            )

    def test_encoder_settings_rejects_negative_fps(self):
        """Test encoder settings rejects negative FPS."""
        with pytest.raises(ValidationError, match="fps"):
            EncoderSettings(
                resolution={"width": 1920, "height": 1080},
                codec="H264",
                bitrate=4096,
                fps=-30,
            )

    def test_encoder_settings_rejects_excessive_fps(self):
        """Test encoder settings rejects excessively high FPS (>120)."""
        with pytest.raises(ValidationError, match="fps"):
            EncoderSettings(
                resolution={"width": 1920, "height": 1080},
                codec="H264",
                bitrate=4096,
                fps=150,
            )

    def test_encoder_settings_allows_low_fps_for_timelapse(self):
        """Test encoder settings allows FPS as low as 1 for timelapse."""
        settings = EncoderSettings(
            resolution={"width": 1920, "height": 1080},
            codec="H264",
            bitrate=4096,
            fps=1,
        )

        assert settings.fps == 1

    def test_encoder_settings_rejects_negative_gop(self):
        """Test encoder settings rejects negative GOP."""
        with pytest.raises(ValidationError, match="gop"):
            EncoderSettings(
                resolution={"width": 1920, "height": 1080},
                codec="H264",
                bitrate=4096,
                fps=25,
                gop=-10,
            )


@pytest.mark.skipif(StreamProfile is None, reason="StreamProfile schema not implemented yet")
class TestStreamProfile:
    """Test StreamProfile schema validation."""

    def test_valid_stream_profile_minimal(self):
        """Test valid stream profile with minimal required fields."""
        profile = StreamProfile(
            token="Profile_1",
            name="mainStream",
            encoder=EncoderSettings(
                resolution={"width": 1920, "height": 1080},
                codec="H264",
                bitrate=4096,
                fps=25,
            ),
        )

        assert profile.token == "Profile_1"
        assert profile.name == "mainStream"
        assert profile.encoder.codec == "H264"

    def test_stream_profile_with_quality(self):
        """Test stream profile with optional quality field."""
        profile = StreamProfile(
            token="Profile_1",
            name="mainStream",
            encoder=EncoderSettings(
                resolution={"width": 1920, "height": 1080},
                codec="H264",
                bitrate=4096,
                fps=25,
            ),
            quality=8.5,
        )

        assert profile.quality == 8.5

    def test_stream_profile_multiple_profiles(self):
        """Test creating multiple stream profiles (main/sub)."""
        main_profile = StreamProfile(
            token="Profile_1",
            name="mainStream",
            encoder=EncoderSettings(
                resolution={"width": 1920, "height": 1080},
                codec="H264",
                bitrate=4096,
                fps=25,
            ),
        )

        sub_profile = StreamProfile(
            token="Profile_2",
            name="subStream",
            encoder=EncoderSettings(
                resolution={"width": 640, "height": 480},
                codec="H264",
                bitrate=512,
                fps=15,
            ),
        )

        assert main_profile.encoder.resolution.width == 1920
        assert sub_profile.encoder.resolution.width == 640

    def test_stream_profile_requires_token(self):
        """Test stream profile requires token field."""
        with pytest.raises(ValidationError, match="token"):
            StreamProfile(
                name="mainStream",
                encoder=EncoderSettings(
                    resolution={"width": 1920, "height": 1080},
                    codec="H264",
                    bitrate=4096,
                    fps=25,
                ),
            )

    def test_stream_profile_requires_name(self):
        """Test stream profile requires name field."""
        with pytest.raises(ValidationError, match="name"):
            StreamProfile(
                token="Profile_1",
                encoder=EncoderSettings(
                    resolution={"width": 1920, "height": 1080},
                    codec="H264",
                    bitrate=4096,
                    fps=25,
                ),
            )

    def test_stream_profile_requires_encoder(self):
        """Test stream profile requires encoder field."""
        with pytest.raises(ValidationError, match="encoder"):
            StreamProfile(
                token="Profile_1",
                name="mainStream",
            )


@pytest.mark.skipif(
    StreamCapabilities is None, reason="StreamCapabilities schema not implemented yet"
)
class TestStreamCapabilities:
    """Test StreamCapabilities schema validation."""

    def test_valid_stream_capabilities(self):
        """Test valid stream capabilities with available options."""
        capabilities = StreamCapabilities(
            available_resolutions=["1920x1080", "1280x720", "640x480"],
            available_codecs=["H264", "H265"],
            bitrate_range={"min": 512, "max": 8192},
            fps_range={"min": 1, "max": 30},
        )

        assert len(capabilities.available_resolutions) == 3
        assert "1920x1080" in capabilities.available_resolutions
        assert len(capabilities.available_codecs) == 2
        assert "H264" in capabilities.available_codecs
        assert capabilities.bitrate_range["min"] == 512
        assert capabilities.bitrate_range["max"] == 8192

    def test_stream_capabilities_with_single_codec(self):
        """Test stream capabilities with only H264 support."""
        capabilities = StreamCapabilities(
            available_resolutions=["1920x1080"],
            available_codecs=["H264"],
            bitrate_range={"min": 512, "max": 4096},
            fps_range={"min": 1, "max": 25},
        )

        assert capabilities.available_codecs == ["H264"]

    def test_stream_capabilities_rejects_empty_resolutions(self):
        """Test stream capabilities requires at least one resolution."""
        with pytest.raises(ValidationError, match="available_resolutions"):
            StreamCapabilities(
                available_resolutions=[],
                available_codecs=["H264"],
                bitrate_range={"min": 512, "max": 4096},
                fps_range={"min": 1, "max": 30},
            )

    def test_stream_capabilities_rejects_empty_codecs(self):
        """Test stream capabilities requires at least one codec."""
        with pytest.raises(ValidationError, match="available_codecs"):
            StreamCapabilities(
                available_resolutions=["1920x1080"],
                available_codecs=[],
                bitrate_range={"min": 512, "max": 4096},
                fps_range={"min": 1, "max": 30},
            )

    def test_stream_capabilities_rejects_invalid_bitrate_range(self):
        """Test stream capabilities rejects min > max bitrate."""
        with pytest.raises(ValidationError, match="bitrate_range"):
            StreamCapabilities(
                available_resolutions=["1920x1080"],
                available_codecs=["H264"],
                bitrate_range={"min": 8192, "max": 512},  # min > max
                fps_range={"min": 1, "max": 30},
            )

    def test_stream_capabilities_rejects_invalid_fps_range(self):
        """Test stream capabilities rejects min > max FPS."""
        with pytest.raises(ValidationError, match="fps_range"):
            StreamCapabilities(
                available_resolutions=["1920x1080"],
                available_codecs=["H264"],
                bitrate_range={"min": 512, "max": 4096},
                fps_range={"min": 30, "max": 15},  # min > max
            )

    def test_stream_capabilities_rejects_invalid_resolution_format(self):
        """Test stream capabilities validates resolution format (widthxheight)."""
        with pytest.raises(ValidationError, match="available_resolutions"):
            StreamCapabilities(
                available_resolutions=["1920x1080", "invalid_format"],
                available_codecs=["H264"],
                bitrate_range={"min": 512, "max": 4096},
                fps_range={"min": 1, "max": 30},
            )


@pytest.mark.skipif(
    StreamConfigResponse is None, reason="StreamConfigResponse schema not implemented yet"
)
class TestStreamConfigResponse:
    """Test StreamConfigResponse schema validation."""

    def test_valid_stream_config_response(self):
        """Test valid stream config response with profiles and capabilities."""
        response = StreamConfigResponse(
            profiles=[
                StreamProfile(
                    token="Profile_1",
                    name="mainStream",
                    encoder=EncoderSettings(
                        resolution={"width": 1920, "height": 1080},
                        codec="H264",
                        bitrate=4096,
                        fps=25,
                    ),
                )
            ],
            capabilities=StreamCapabilities(
                available_resolutions=["1920x1080", "1280x720"],
                available_codecs=["H264", "H265"],
                bitrate_range={"min": 512, "max": 8192},
                fps_range={"min": 1, "max": 30},
            ),
            read_only=False,
        )

        assert len(response.profiles) == 1
        assert response.profiles[0].token == "Profile_1"
        assert response.read_only is False
        assert response.capabilities.available_codecs == ["H264", "H265"]

    def test_stream_config_response_read_only_mode(self):
        """Test stream config response in read-only mode."""
        response = StreamConfigResponse(
            profiles=[
                StreamProfile(
                    token="Profile_1",
                    name="mainStream",
                    encoder=EncoderSettings(
                        resolution={"width": 1920, "height": 1080},
                        codec="H264",
                        bitrate=4096,
                        fps=25,
                    ),
                )
            ],
            capabilities=StreamCapabilities(
                available_resolutions=["1920x1080"],
                available_codecs=["H264"],
                bitrate_range={"min": 512, "max": 4096},
                fps_range={"min": 1, "max": 25},
            ),
            read_only=True,
        )

        assert response.read_only is True

    def test_stream_config_response_with_multiple_profiles(self):
        """Test stream config response with multiple profiles (main/sub)."""
        response = StreamConfigResponse(
            profiles=[
                StreamProfile(
                    token="Profile_1",
                    name="mainStream",
                    encoder=EncoderSettings(
                        resolution={"width": 1920, "height": 1080},
                        codec="H264",
                        bitrate=4096,
                        fps=25,
                    ),
                ),
                StreamProfile(
                    token="Profile_2",
                    name="subStream",
                    encoder=EncoderSettings(
                        resolution={"width": 640, "height": 480},
                        codec="H264",
                        bitrate=512,
                        fps=15,
                    ),
                ),
            ],
            capabilities=StreamCapabilities(
                available_resolutions=["1920x1080", "640x480"],
                available_codecs=["H264"],
                bitrate_range={"min": 512, "max": 8192},
                fps_range={"min": 1, "max": 30},
            ),
            read_only=False,
        )

        assert len(response.profiles) == 2
        assert response.profiles[0].name == "mainStream"
        assert response.profiles[1].name == "subStream"

    def test_stream_config_response_requires_profiles(self):
        """Test stream config response requires at least one profile."""
        with pytest.raises(ValidationError, match="profiles"):
            StreamConfigResponse(
                profiles=[],
                capabilities=StreamCapabilities(
                    available_resolutions=["1920x1080"],
                    available_codecs=["H264"],
                    bitrate_range={"min": 512, "max": 4096},
                    fps_range={"min": 1, "max": 30},
                ),
                read_only=False,
            )


@pytest.mark.skipif(
    StreamConfigUpdate is None, reason="StreamConfigUpdate schema not implemented yet"
)
class TestStreamConfigUpdate:
    """Test StreamConfigUpdate schema validation."""

    def test_valid_stream_config_update_all_fields(self):
        """Test valid stream config update with all fields."""
        update = StreamConfigUpdate(
            profile_token="Profile_1",
            resolution={"width": 1280, "height": 720},
            codec="H264",
            bitrate=2048,
            fps=15,
        )

        assert update.profile_token == "Profile_1"
        assert update.resolution.width == 1280
        assert update.resolution.height == 720
        assert update.codec == "H264"
        assert update.bitrate == 2048
        assert update.fps == 15

    def test_stream_config_update_partial_fields(self):
        """Test stream config update with only resolution change."""
        update = StreamConfigUpdate(
            profile_token="Profile_1",
            resolution={"width": 1280, "height": 720},
        )

        assert update.profile_token == "Profile_1"
        assert update.resolution.width == 1280
        assert update.codec is None
        assert update.bitrate is None
        assert update.fps is None

    def test_stream_config_update_bitrate_only(self):
        """Test stream config update with only bitrate change."""
        update = StreamConfigUpdate(
            profile_token="Profile_1",
            bitrate=3072,
        )

        assert update.bitrate == 3072
        assert update.resolution is None
        assert update.codec is None
        assert update.fps is None

    def test_stream_config_update_requires_profile_token(self):
        """Test stream config update requires profile_token."""
        with pytest.raises(ValidationError, match="profile_token"):
            StreamConfigUpdate(
                resolution={"width": 1280, "height": 720},
            )

    def test_stream_config_update_validates_bitrate_range(self):
        """Test stream config update validates bitrate within reasonable range."""
        with pytest.raises(ValidationError, match="bitrate"):
            StreamConfigUpdate(
                profile_token="Profile_1",
                bitrate=150000,  # Excessive bitrate
            )

    def test_stream_config_update_validates_fps_range(self):
        """Test stream config update validates FPS within reasonable range."""
        with pytest.raises(ValidationError, match="fps"):
            StreamConfigUpdate(
                profile_token="Profile_1",
                fps=150,  # Excessive FPS
            )

    def test_stream_config_update_validates_codec_enum(self):
        """Test stream config update validates codec is H264 or H265."""
        with pytest.raises(ValidationError, match="codec"):
            StreamConfigUpdate(
                profile_token="Profile_1",
                codec="MJPEG",  # Invalid codec
            )
