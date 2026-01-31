"""Integration tests for stream configuration API endpoints (NEM-4394, NEM-4395).

Tests the complete flow of reading and updating camera stream settings through
the REST API. This is part of Phase 3: Stream Settings Control.

Run with: uv run pytest backend/tests/integration/test_stream_config_api.py -v -n0

TDD RED Phase: These tests will FAIL initially since the API endpoints don't exist yet.
Implementation will follow in GREEN phase.

Note: These tests require ONVIF mocking infrastructure to avoid real camera dependencies.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
async def test_camera(client):
    """Create a test camera with ONVIF ingestion mode."""
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"ONVIF Camera {unique_id}",
        "folder_path": f"/export/foscam/onvif_{unique_id}",
        "status": "online",
        "ingestion_mode": "onvif",
        "rtsp_url": "rtsp://192.168.1.100:554/stream1",
        "rtsp_username": "admin",
        "rtsp_password": "password123",  # pragma: allowlist secret
        "onvif_port": 80,
    }

    response = await client.post("/api/cameras", json=camera_data)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def mock_onvif_client():
    """Mock ONVIF client with typical camera responses."""
    client = MagicMock()

    # Mock profile data
    mock_profile = MagicMock()
    mock_profile.token = "Profile_1"
    mock_profile.name = "mainStream"
    mock_profile.video_encoder_configuration = MagicMock()
    mock_profile.video_encoder_configuration.encoding = "H264"
    mock_profile.video_encoder_configuration.resolution = MagicMock(width=1920, height=1080)
    mock_profile.video_encoder_configuration.bitrate_limit = 4096
    mock_profile.video_encoder_configuration.framerate_limit = 25
    mock_profile.video_encoder_configuration.gop_length = 50

    client.get_profiles = AsyncMock(return_value=[mock_profile])

    # Mock capabilities
    mock_capabilities = MagicMock()
    mock_capabilities.resolutions = ["1920x1080", "1280x720", "640x480"]
    mock_capabilities.codecs = ["H264", "H265"]
    mock_capabilities.bitrate_range = MagicMock(min=512, max=8192)
    mock_capabilities.fps_range = MagicMock(min=1, max=30)

    client.get_video_encoder_configuration_options = AsyncMock(return_value=mock_capabilities)
    client.set_video_encoder_configuration = AsyncMock()
    client.supports_video_encoder_configuration = True

    return client


@pytest.mark.asyncio
async def test_get_stream_config_success(client, test_camera, mock_onvif_client):
    """Test GET /api/cameras/{id}/stream-config returns current settings."""
    camera_id = test_camera["id"]

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_onvif_client,
    ):
        response = await client.get(f"/api/cameras/{camera_id}/stream-config")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "profiles" in data
    assert "capabilities" in data
    assert "read_only" in data

    # Verify profile data
    assert len(data["profiles"]) == 1
    profile = data["profiles"][0]
    assert profile["token"] == "Profile_1"
    assert profile["name"] == "mainStream"
    assert profile["encoder"]["codec"] == "H264"
    assert profile["encoder"]["resolution"]["width"] == 1920
    assert profile["encoder"]["resolution"]["height"] == 1080
    assert profile["encoder"]["bitrate"] == 4096
    assert profile["encoder"]["fps"] == 25

    # Verify capabilities
    assert data["capabilities"]["available_resolutions"] == ["1920x1080", "1280x720", "640x480"]
    assert data["capabilities"]["available_codecs"] == ["H264", "H265"]
    assert data["capabilities"]["bitrate_range"]["min"] == 512
    assert data["capabilities"]["bitrate_range"]["max"] == 8192

    # Verify read-only flag
    assert data["read_only"] is False


@pytest.mark.asyncio
async def test_get_stream_config_camera_not_found(client):
    """Test GET /api/cameras/{id}/stream-config with non-existent camera."""
    response = await client.get("/api/cameras/nonexistent_camera/stream-config")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_stream_config_non_onvif_camera(client):
    """Test GET /api/cameras/{id}/stream-config with FTP camera returns 400."""
    # Create FTP camera
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"FTP Camera {unique_id}",
        "folder_path": f"/export/foscam/ftp_{unique_id}",
        "status": "online",
        "ingestion_mode": "ftp",
    }
    create_response = await client.post("/api/cameras", json=camera_data)
    camera_id = create_response.json()["id"]

    response = await client.get(f"/api/cameras/{camera_id}/stream-config")

    assert response.status_code == 400
    assert "onvif" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_stream_config_connection_failure(client, test_camera):
    """Test GET /api/cameras/{id}/stream-config handles ONVIF connection failure."""
    camera_id = test_camera["id"]

    mock_client = MagicMock()
    mock_client.get_profiles = AsyncMock(side_effect=ConnectionError("Failed to connect"))

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_client,
    ):
        response = await client.get(f"/api/cameras/{camera_id}/stream-config")

    assert response.status_code == 503  # Service Unavailable
    assert "connection" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_stream_config_read_only_camera(client, test_camera):
    """Test GET /api/cameras/{id}/stream-config with read-only camera."""
    camera_id = test_camera["id"]

    # Mock read-only camera
    mock_client = MagicMock()
    mock_profile = MagicMock()
    mock_profile.token = "Profile_1"
    mock_profile.name = "mainStream"
    mock_profile.video_encoder_configuration = MagicMock()
    mock_profile.video_encoder_configuration.encoding = "H264"
    mock_profile.video_encoder_configuration.resolution = MagicMock(width=1920, height=1080)
    mock_profile.video_encoder_configuration.bitrate_limit = 4096
    mock_profile.video_encoder_configuration.framerate_limit = 25

    mock_client.get_profiles = AsyncMock(return_value=[mock_profile])
    mock_capabilities = MagicMock()
    mock_capabilities.resolutions = ["1920x1080"]
    mock_capabilities.codecs = ["H264"]
    mock_capabilities.bitrate_range = MagicMock(min=512, max=4096)
    mock_capabilities.fps_range = MagicMock(min=1, max=25)
    mock_client.get_video_encoder_configuration_options = AsyncMock(return_value=mock_capabilities)
    mock_client.supports_video_encoder_configuration = False  # Read-only

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_client,
    ):
        response = await client.get(f"/api/cameras/{camera_id}/stream-config")

    assert response.status_code == 200
    data = response.json()
    assert data["read_only"] is True


@pytest.mark.asyncio
async def test_put_stream_config_success_full_update(client, test_camera, mock_onvif_client):
    """Test PUT /api/cameras/{id}/stream-config applies new settings."""
    camera_id = test_camera["id"]

    update_data = {
        "profile_token": "Profile_1",
        "resolution": {"width": 1280, "height": 720},
        "codec": "H264",
        "bitrate": 2048,
        "fps": 15,
    }

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_onvif_client,
    ):
        response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "applied" in data["message"].lower()

    # Verify ONVIF client was called with correct parameters
    mock_onvif_client.set_video_encoder_configuration.assert_called_once()


@pytest.mark.asyncio
async def test_put_stream_config_success_partial_update_bitrate(
    client, test_camera, mock_onvif_client
):
    """Test PUT /api/cameras/{id}/stream-config with partial update (bitrate only)."""
    camera_id = test_camera["id"]

    update_data = {
        "profile_token": "Profile_1",
        "bitrate": 3072,
    }

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_onvif_client,
    ):
        response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_put_stream_config_success_partial_update_resolution(
    client, test_camera, mock_onvif_client
):
    """Test PUT /api/cameras/{id}/stream-config with partial update (resolution only)."""
    camera_id = test_camera["id"]

    update_data = {
        "profile_token": "Profile_1",
        "resolution": {"width": 1280, "height": 720},
    }

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_onvif_client,
    ):
        response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_put_stream_config_validation_error_bitrate_exceeds_max(
    client, test_camera, mock_onvif_client
):
    """Test PUT /api/cameras/{id}/stream-config rejects bitrate exceeding camera max."""
    camera_id = test_camera["id"]

    update_data = {
        "profile_token": "Profile_1",
        "bitrate": 10000,  # Exceeds max of 8192
    }

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_onvif_client,
    ):
        response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 400
    assert "bitrate" in response.json()["detail"].lower()
    assert "exceeds" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_put_stream_config_validation_error_bitrate_below_min(
    client, test_camera, mock_onvif_client
):
    """Test PUT /api/cameras/{id}/stream-config rejects bitrate below camera min."""
    camera_id = test_camera["id"]

    update_data = {
        "profile_token": "Profile_1",
        "bitrate": 256,  # Below min of 512
    }

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_onvif_client,
    ):
        response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 400
    assert "bitrate" in response.json()["detail"].lower()
    assert "below" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_put_stream_config_validation_error_unsupported_resolution(
    client, test_camera, mock_onvif_client
):
    """Test PUT /api/cameras/{id}/stream-config rejects unsupported resolution."""
    camera_id = test_camera["id"]

    update_data = {
        "profile_token": "Profile_1",
        "resolution": {"width": 800, "height": 600},  # Not in supported list
    }

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_onvif_client,
    ):
        response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 400
    assert "resolution" in response.json()["detail"].lower()
    assert "not supported" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_put_stream_config_validation_error_unsupported_codec(
    client, test_camera, mock_onvif_client
):
    """Test PUT /api/cameras/{id}/stream-config rejects unsupported codec."""
    camera_id = test_camera["id"]

    # Modify mock to only support H264
    mock_capabilities = MagicMock()
    mock_capabilities.codecs = ["H264"]
    mock_capabilities.resolutions = ["1920x1080"]
    mock_capabilities.bitrate_range = MagicMock(min=512, max=8192)
    mock_capabilities.fps_range = MagicMock(min=1, max=30)
    mock_onvif_client.get_video_encoder_configuration_options = AsyncMock(
        return_value=mock_capabilities
    )

    update_data = {
        "profile_token": "Profile_1",
        "codec": "H265",  # Not supported
    }

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_onvif_client,
    ):
        response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 400
    assert "codec" in response.json()["detail"].lower()
    assert "not supported" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_put_stream_config_validation_error_fps_exceeds_max(
    client, test_camera, mock_onvif_client
):
    """Test PUT /api/cameras/{id}/stream-config rejects FPS exceeding camera max."""
    camera_id = test_camera["id"]

    update_data = {
        "profile_token": "Profile_1",
        "fps": 60,  # Exceeds max of 30
    }

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_onvif_client,
    ):
        response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 400
    assert "fps" in response.json()["detail"].lower()
    assert "exceeds" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_put_stream_config_conflict_read_only_camera(client, test_camera):
    """Test PUT /api/cameras/{id}/stream-config returns 409 CONFLICT for read-only cameras."""
    camera_id = test_camera["id"]

    # Mock read-only camera
    mock_client = MagicMock()
    mock_client.supports_video_encoder_configuration = False

    update_data = {
        "profile_token": "Profile_1",
        "bitrate": 2048,
    }

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_client,
    ):
        response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 409  # CONFLICT
    assert (
        "read-only" in response.json()["detail"].lower()
        or "not support" in response.json()["detail"].lower()
    )


@pytest.mark.asyncio
async def test_put_stream_config_camera_not_found(client):
    """Test PUT /api/cameras/{id}/stream-config with non-existent camera."""
    update_data = {
        "profile_token": "Profile_1",
        "bitrate": 2048,
    }

    response = await client.put("/api/cameras/nonexistent_camera/stream-config", json=update_data)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_put_stream_config_missing_profile_token(client, test_camera, mock_onvif_client):
    """Test PUT /api/cameras/{id}/stream-config requires profile_token."""
    camera_id = test_camera["id"]

    update_data = {
        "bitrate": 2048,
        # Missing profile_token
    }

    response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 422  # Validation error
    assert "profile_token" in str(response.json()).lower()


@pytest.mark.asyncio
async def test_put_stream_config_invalid_profile_token(client, test_camera, mock_onvif_client):
    """Test PUT /api/cameras/{id}/stream-config with invalid profile token."""
    camera_id = test_camera["id"]

    mock_onvif_client.set_video_encoder_configuration = AsyncMock(
        side_effect=ValueError("Invalid profile token")
    )

    update_data = {
        "profile_token": "InvalidToken",
        "bitrate": 2048,
    }

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_onvif_client,
    ):
        response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 400
    assert "profile" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_put_stream_config_onvif_failure(client, test_camera, mock_onvif_client):
    """Test PUT /api/cameras/{id}/stream-config handles ONVIF command failure."""
    camera_id = test_camera["id"]

    mock_onvif_client.set_video_encoder_configuration = AsyncMock(
        side_effect=RuntimeError("ONVIF command failed")
    )

    update_data = {
        "profile_token": "Profile_1",
        "bitrate": 2048,
    }

    with patch(
        "backend.services.onvif_service.ONVIFService.create_client",
        return_value=mock_onvif_client,
    ):
        response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 503  # Service Unavailable
    assert (
        "onvif" in response.json()["detail"].lower()
        or "failed" in response.json()["detail"].lower()
    )


@pytest.mark.asyncio
async def test_stream_config_api_validates_schema(client, test_camera, mock_onvif_client):
    """Test stream config API validates request schema with Pydantic."""
    camera_id = test_camera["id"]

    # Invalid update: negative bitrate
    update_data = {
        "profile_token": "Profile_1",
        "bitrate": -2048,  # Invalid
    }

    response = await client.put(f"/api/cameras/{camera_id}/stream-config", json=update_data)

    assert response.status_code == 422  # Validation error
    assert "bitrate" in str(response.json()).lower()
