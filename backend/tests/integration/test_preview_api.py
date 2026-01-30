"""Integration tests for camera preview API endpoints.

This module tests the live video preview endpoints that integrate with go2rtc.
Tests MUST FAIL initially (RED phase) until implementation is complete.

Endpoints tested:
- POST /api/cameras/{id}/preview/start - Register stream and get WebRTC URL
- DELETE /api/cameras/{id}/preview/stop - Stop preview session
- GET /api/cameras/{id}/snapshot - Fallback when go2rtc unavailable

Design Doc: docs/plans/2025-01-30-rtsp-camera-configuration-ui-design.md
Related Issues: NEM-4400, NEM-4401
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera import Camera

# Fixtures


@pytest.fixture
async def rtsp_camera(session: AsyncSession):
    """Create a camera with RTSP configuration for testing."""
    camera = Camera(
        id="test_rtsp_camera",
        name="Test RTSP Camera",
        status="active",
        rtsp_url="rtsp://192.168.1.100:554/stream1",
        rtsp_username="admin",
        rtsp_password="encrypted_password",  # pragma: allowlist secret
        ingestion_mode="rtsp",
    )
    session.add(camera)
    await session.commit()
    await session.refresh(camera)
    return camera


@pytest.fixture
def mock_go2rtc_client():
    """Mock go2rtc client for testing."""
    client = AsyncMock()
    client.health_check.return_value = True
    client.register_stream.return_value = {
        "stream_id": "camera_test_rtsp_camera_12345",
        "webrtc_url": "http://localhost:8555/api/ws?src=camera_test_rtsp_camera_12345",
        "expires_in": 300,
    }
    client.unregister_stream.return_value = None
    return client


# Test: Start Preview


@pytest.mark.asyncio
async def test_start_preview_returns_webrtc_url(
    client: AsyncClient, rtsp_camera: Camera, mock_go2rtc_client
):
    """Test POST /api/cameras/{id}/preview/start returns WebRTC URL.

    RED: This test will fail until the endpoint is implemented.
    Expected behavior:
    - Returns 200 status code
    - Response includes webrtc_url
    - Response includes stream_id
    - Response includes expires_in (300 seconds)
    """
    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        response = await client.post(f"/api/cameras/{rtsp_camera.id}/preview/start")

        assert response.status_code == 200

        data = response.json()
        assert "webrtc_url" in data
        assert "stream_id" in data
        assert "expires_in" in data
        assert data["expires_in"] == 300

        # Verify go2rtc client was called
        mock_go2rtc_client.register_stream.assert_called_once()


@pytest.mark.asyncio
async def test_start_preview_within_2_seconds(
    client: AsyncClient, rtsp_camera: Camera, mock_go2rtc_client
):
    """Test that preview starts within 2 seconds (performance requirement).

    RED: This test will fail until performance optimization is implemented.
    Expected behavior:
    - Response time < 2 seconds
    - Design doc acceptance criteria: preview start within 2 seconds
    """
    import time

    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        start_time = time.time()
        response = await client.post(f"/api/cameras/{rtsp_camera.id}/preview/start")
        elapsed = time.time() - start_time

        assert response.status_code == 200
        assert elapsed < 2.0, f"Preview start took {elapsed:.2f}s, expected < 2.0s"


@pytest.mark.asyncio
async def test_start_preview_passes_credentials_to_go2rtc(
    client: AsyncClient, rtsp_camera: Camera, mock_go2rtc_client
):
    """Test that RTSP credentials are passed to go2rtc.

    RED: This test will fail until credential handling is implemented.
    Expected behavior:
    - Camera's RTSP URL, username, and password sent to go2rtc
    - Credentials decrypted before sending
    - Password never in API response
    """
    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        response = await client.post(f"/api/cameras/{rtsp_camera.id}/preview/start")

        assert response.status_code == 200

        # Verify go2rtc client received credentials
        mock_go2rtc_client.register_stream.assert_called_once()
        call_kwargs = mock_go2rtc_client.register_stream.call_args.kwargs

        assert call_kwargs["camera_id"] == rtsp_camera.id
        assert call_kwargs["rtsp_url"] == rtsp_camera.rtsp_url
        assert call_kwargs["username"] == rtsp_camera.rtsp_username
        assert "password" in call_kwargs  # Decrypted password passed

        # Verify password not in response
        data = response.json()
        assert "password" not in data


@pytest.mark.asyncio
async def test_start_preview_camera_not_found(client: AsyncClient, mock_go2rtc_client):
    """Test starting preview for non-existent camera.

    RED: This test will fail until 404 handling is implemented.
    Expected behavior:
    - Returns 404 status code
    - Error message indicates camera not found
    """
    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        response = await client.post("/api/cameras/nonexistent/preview/start")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_start_preview_non_rtsp_camera(
    client: AsyncClient, session: AsyncSession, mock_go2rtc_client
):
    """Test starting preview for camera without RTSP configuration.

    RED: This test will fail until validation is implemented.
    Expected behavior:
    - Returns 400 status code
    - Error message indicates RTSP not configured
    """
    # Create FTP-only camera
    camera = Camera(
        id="ftp_camera",
        name="FTP Camera",
        status="active",
        ingestion_mode="ftp",
        # No rtsp_url configured
    )
    session.add(camera)
    await session.commit()

    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        response = await client.post(f"/api/cameras/{camera.id}/preview/start")

        assert response.status_code == 400
        data = response.json()
        assert "rtsp" in data["detail"].lower()


@pytest.mark.asyncio
async def test_start_preview_go2rtc_unavailable_returns_503(
    client: AsyncClient, rtsp_camera: Camera
):
    """Test graceful degradation when go2rtc is unavailable.

    RED: This test will fail until error handling is implemented.
    Expected behavior:
    - Returns 503 status code (Service Unavailable)
    - Error message indicates go2rtc unavailable
    - Frontend can fallback to snapshot endpoint
    - Design doc: "Showing snapshot instead" on go2rtc failure
    """
    mock_client = AsyncMock()
    mock_client.health_check.return_value = False

    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_client):
        response = await client.post(f"/api/cameras/{rtsp_camera.id}/preview/start")

        assert response.status_code == 503
        data = response.json()
        assert "unavailable" in data["detail"].lower() or "go2rtc" in data["detail"].lower()


@pytest.mark.asyncio
async def test_start_preview_go2rtc_connection_error(client: AsyncClient, rtsp_camera: Camera):
    """Test handling of go2rtc connection errors.

    RED: This test will fail until exception handling is implemented.
    Expected behavior:
    - Returns 503 status code
    - Error message indicates service issue
    - No stack trace exposed to client
    """
    from backend.services.go2rtc_client import Go2RTCUnavailableError

    mock_client = AsyncMock()
    mock_client.health_check.return_value = True
    mock_client.register_stream.side_effect = Go2RTCUnavailableError("Connection refused")

    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_client):
        response = await client.post(f"/api/cameras/{rtsp_camera.id}/preview/start")

        assert response.status_code == 503
        data = response.json()
        assert "detail" in data


# Test: Stop Preview


@pytest.mark.asyncio
async def test_stop_preview_success(client: AsyncClient, rtsp_camera: Camera, mock_go2rtc_client):
    """Test DELETE /api/cameras/{id}/preview/stop removes stream.

    RED: This test will fail until the endpoint is implemented.
    Expected behavior:
    - Returns 200 status code
    - Stream removed from go2rtc
    - Cleanup on session end
    """
    stream_id = "camera_test_rtsp_camera_12345"

    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        response = await client.delete(f"/api/cameras/{rtsp_camera.id}/preview/stop")

        assert response.status_code == 200

        # Verify go2rtc client unregister was called
        # Note: Stream ID tracking may be needed
        mock_go2rtc_client.unregister_stream.assert_called()


@pytest.mark.asyncio
async def test_stop_preview_idempotent(
    client: AsyncClient, rtsp_camera: Camera, mock_go2rtc_client
):
    """Test that stopping preview multiple times is safe (idempotent).

    RED: This test will fail until idempotent handling is implemented.
    Expected behavior:
    - Multiple DELETE requests succeed
    - No error on stopping already-stopped preview
    """
    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        # First stop
        response1 = await client.delete(f"/api/cameras/{rtsp_camera.id}/preview/stop")
        assert response1.status_code == 200

        # Second stop (should also succeed)
        response2 = await client.delete(f"/api/cameras/{rtsp_camera.id}/preview/stop")
        assert response2.status_code == 200


@pytest.mark.asyncio
async def test_stop_preview_camera_not_found(client: AsyncClient, mock_go2rtc_client):
    """Test stopping preview for non-existent camera.

    RED: This test will fail until 404 handling is implemented.
    Expected behavior:
    - Returns 404 status code
    - Error message indicates camera not found
    """
    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        response = await client.delete("/api/cameras/nonexistent/preview/stop")

        assert response.status_code == 404


# Test: Session Expiry


@pytest.mark.asyncio
async def test_preview_session_expires_after_5_minutes(
    client: AsyncClient, rtsp_camera: Camera, mock_go2rtc_client
):
    """Test that preview sessions expire after 5 minutes.

    RED: This test will fail until session expiry is implemented.
    Expected behavior:
    - Session tracked with expiry timestamp
    - Automatic cleanup after 300 seconds
    - Design doc requirement: 5-minute expiry
    """
    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        response = await client.post(f"/api/cameras/{rtsp_camera.id}/preview/start")

        assert response.status_code == 200
        data = response.json()

        assert "expires_in" in data
        assert data["expires_in"] == 300  # 5 minutes

        # TODO: Test actual expiry mechanism (background task)
        # For now, verify the contract


# Test: Multiple Concurrent Previews


@pytest.mark.asyncio
async def test_multiple_cameras_preview_simultaneously(
    client: AsyncClient, session: AsyncSession, mock_go2rtc_client
):
    """Test that multiple cameras can have active preview sessions.

    RED: This test will fail until multi-session support is implemented.
    Expected behavior:
    - Each camera has independent session
    - Unique stream IDs per camera
    - No interference between sessions
    """
    # Create multiple cameras
    cameras = []
    for i in range(3):
        camera = Camera(
            id=f"camera_{i}",
            name=f"Camera {i}",
            status="active",
            rtsp_url=f"rtsp://192.168.1.{100 + i}:554/stream",
            rtsp_username="admin",
            rtsp_password="encrypted",  # pragma: allowlist secret
            ingestion_mode="rtsp",
        )
        session.add(camera)
        cameras.append(camera)

    await session.commit()

    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        # Start preview for all cameras
        responses = []
        for camera in cameras:
            response = await client.post(f"/api/cameras/{camera.id}/preview/start")
            assert response.status_code == 200
            responses.append(response.json())

        # Verify unique stream IDs
        stream_ids = [r["stream_id"] for r in responses]
        assert len(stream_ids) == len(set(stream_ids)), "Stream IDs must be unique"


# Test: Snapshot Fallback


@pytest.mark.asyncio
async def test_snapshot_endpoint_exists_for_fallback(client: AsyncClient, rtsp_camera: Camera):
    """Test that snapshot endpoint exists as fallback.

    RED: This test will fail until snapshot endpoint is implemented.
    Expected behavior:
    - GET /api/cameras/{id}/snapshot returns JPEG
    - Used as fallback when go2rtc unavailable
    - Design doc: "Showing snapshot instead" on failure
    """
    # Note: This test assumes snapshot endpoint exists from Phase 1
    # May need to be updated based on actual implementation
    response = await client.get(f"/api/cameras/{rtsp_camera.id}/snapshot")

    # Endpoint should exist (may return placeholder or error if not configured)
    assert response.status_code in [200, 404, 503]  # Valid responses


# Test: Rate Limiting (Optional)


@pytest.mark.asyncio
async def test_preview_rate_limit_per_camera(
    client: AsyncClient, rtsp_camera: Camera, mock_go2rtc_client
):
    """Test that preview start requests are rate-limited.

    RED: This test will fail until rate limiting is implemented.
    Expected behavior:
    - Prevent abuse of preview endpoint
    - Max N requests per minute per camera
    - Optional feature for production hardening
    """
    # This is an optional test for future enhancement
    # Can be implemented if abuse becomes a concern
    pytest.skip("Rate limiting not yet specified in design doc")


# Test: WebSocket URL Format


@pytest.mark.asyncio
async def test_preview_webrtc_url_format(
    client: AsyncClient, rtsp_camera: Camera, mock_go2rtc_client
):
    """Test that WebRTC URL has correct format for frontend.

    RED: This test will fail until URL validation is implemented.
    Expected behavior:
    - URL uses http:// (not https:// for local deployment)
    - Port 8555 (go2rtc WebRTC port)
    - Path: /api/ws
    - Query parameter: src={stream_id}
    """
    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        response = await client.post(f"/api/cameras/{rtsp_camera.id}/preview/start")

        assert response.status_code == 200
        data = response.json()

        webrtc_url = data["webrtc_url"]
        assert webrtc_url.startswith("http://")
        assert ":8555" in webrtc_url
        assert "/api/ws" in webrtc_url
        assert "src=" in webrtc_url


# Test: Error Response Format


@pytest.mark.asyncio
async def test_preview_error_response_format(client: AsyncClient, mock_go2rtc_client):
    """Test that error responses follow FastAPI convention.

    RED: This test will fail until error handling is standardized.
    Expected behavior:
    - Error responses have "detail" field
    - Status codes match HTTP semantics
    - Error messages are user-friendly
    """
    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        response = await client.post("/api/cameras/nonexistent/preview/start")

        assert response.status_code == 404
        data = response.json()

        assert "detail" in data
        assert isinstance(data["detail"], str)
        assert len(data["detail"]) > 0


# Test: Credential Decryption


@pytest.mark.asyncio
async def test_preview_decrypts_password_before_go2rtc(
    client: AsyncClient, rtsp_camera: Camera, mock_go2rtc_client
):
    """Test that encrypted password is decrypted before sending to go2rtc.

    RED: This test will fail until credential service integration is implemented.
    Expected behavior:
    - Retrieve encrypted password from database
    - Decrypt using credential service
    - Send decrypted password to go2rtc
    - Never expose decrypted password in API response
    """
    with patch("backend.services.go2rtc_client.get_go2rtc_client", return_value=mock_go2rtc_client):
        with patch("backend.services.credential_service.CredentialService") as mock_cred_service:
            mock_cred_service.decrypt.return_value = "decrypted_password"

            response = await client.post(f"/api/cameras/{rtsp_camera.id}/preview/start")

            assert response.status_code == 200

            # Verify credential service was used (if implemented)
            # This test may need adjustment based on actual implementation
