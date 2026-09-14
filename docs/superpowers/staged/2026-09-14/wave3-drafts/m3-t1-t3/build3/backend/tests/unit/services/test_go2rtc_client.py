"""Unit tests for go2rtc client service.

This module tests the go2rtc integration for live video preview via WebRTC.
Tests MUST FAIL initially (RED phase) until implementation is complete.

go2rtc provides:
- RTSP to WebRTC conversion for low-latency video streaming
- Session management with 5-minute expiry
- Health monitoring for graceful degradation

Design Doc: docs/plans/2025-01-30-rtsp-camera-configuration-ui-design.md
Related Issues: NEM-4400, NEM-4401
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.services.go2rtc_client import (
    Go2RTCClient,
    Go2RTCUnavailableError,
    StreamRegistrationError,
)

# Fixtures


@pytest.fixture
def go2rtc_client():
    """Create go2rtc client instance with test configuration."""
    return Go2RTCClient(
        api_url="http://localhost:1984",
        webrtc_url="http://localhost:8555",
        timeout=2.0,
    )


@pytest.fixture
def sample_camera_config():
    """Sample RTSP camera configuration for testing."""
    return {
        "camera_id": "front_door",
        "rtsp_url": "rtsp://192.168.1.100:554/stream1",
        "username": "admin",
        "password": "test_password",  # pragma: allowlist secret
    }


@pytest.fixture
def sample_go2rtc_response():
    """Sample response from go2rtc stream API."""
    return {
        "stream_id": "camera_front_door_12345",
        "url": "http://localhost:8555/api/ws?src=camera_front_door_12345",
        "producers": 1,
        "consumers": 0,
    }


# Test: Health Check


@pytest.mark.asyncio
async def test_health_check_success(go2rtc_client):
    """Test health check when go2rtc is available.

    RED: This test will fail until Go2RTCClient.health_check() is implemented.
    Expected behavior:
    - GET request to /api/ endpoint
    - 200 status code returns True
    - Validates go2rtc service is reachable
    """
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": "1.8.3"}
        mock_get.return_value = mock_response

        result = await go2rtc_client.health_check()

        assert result is True
        mock_get.assert_called_once()
        # Verify timeout is applied
        assert mock_get.call_args.kwargs.get("timeout") == 2.0


@pytest.mark.asyncio
async def test_health_check_connection_error(go2rtc_client):
    """Test health check when go2rtc is not reachable.

    RED: This test will fail until error handling is implemented.
    Expected behavior:
    - Connection refused or timeout returns False
    - No exception propagated to caller
    - Allows graceful degradation to snapshot fallback
    """
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
        result = await go2rtc_client.health_check()

        assert result is False


@pytest.mark.asyncio
async def test_health_check_timeout(go2rtc_client):
    """Test health check timeout handling.

    RED: This test will fail until timeout handling is implemented.
    Expected behavior:
    - Timeout error returns False
    - No blocking wait beyond configured timeout
    """
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Request timeout")):
        result = await go2rtc_client.health_check()

        assert result is False


@pytest.mark.asyncio
async def test_health_check_http_error(go2rtc_client):
    """Test health check with HTTP error response.

    RED: This test will fail until error code handling is implemented.
    Expected behavior:
    - 500 or 503 status code returns False
    - Service degradation detected properly
    """
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service unavailable", request=MagicMock(), response=mock_response
        )
        mock_get.return_value = mock_response

        result = await go2rtc_client.health_check()

        assert result is False


# Test: Register Stream


@pytest.mark.asyncio
async def test_register_stream_success(go2rtc_client, sample_camera_config, sample_go2rtc_response):
    """Test successful stream registration with go2rtc.

    RED: This test will fail until register_stream() is implemented.
    Expected behavior:
    - POST request to /api/streams endpoint
    - RTSP URL with embedded credentials sent to go2rtc
    - WebRTC URL returned for frontend connection
    - Stream ID generated and tracked
    """
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_go2rtc_response
        mock_post.return_value = mock_response

        result = await go2rtc_client.register_stream(
            camera_id=sample_camera_config["camera_id"],
            rtsp_url=sample_camera_config["rtsp_url"],
            username=sample_camera_config["username"],
            password=sample_camera_config["password"],
        )

        assert result["stream_id"] == sample_go2rtc_response["stream_id"]
        assert result["webrtc_url"] == sample_go2rtc_response["url"]
        assert "expires_in" in result
        assert result["expires_in"] == 300  # 5 minutes

        # Verify POST request
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert "json" in call_kwargs

        # Verify RTSP URL includes credentials
        stream_config = call_kwargs["json"]
        assert sample_camera_config["username"] in stream_config["source"]
        assert sample_camera_config["password"] in stream_config["source"]


@pytest.mark.asyncio
async def test_register_stream_returns_webrtc_url(go2rtc_client, sample_camera_config):
    """Test that register_stream returns correct WebRTC URL format.

    RED: This test will fail until URL construction is implemented.
    Expected behavior:
    - WebRTC URL uses port 8555
    - URL includes stream ID as query parameter
    - URL format: http://localhost:8555/api/ws?src={stream_id}
    """
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stream_id": "camera_test_abc",
            "url": "http://localhost:8555/api/ws?src=camera_test_abc",
        }
        mock_post.return_value = mock_response

        result = await go2rtc_client.register_stream(
            camera_id=sample_camera_config["camera_id"],
            rtsp_url=sample_camera_config["rtsp_url"],
        )

        assert result["webrtc_url"].startswith("http://localhost:8555")
        assert "api/ws" in result["webrtc_url"]
        assert "src=" in result["webrtc_url"]


@pytest.mark.asyncio
async def test_register_stream_credential_handling(go2rtc_client, sample_camera_config):
    """Test that credentials are properly embedded in RTSP URL.

    RED: This test will fail until credential embedding is implemented.
    Expected behavior:
    - Credentials embedded in RTSP URL format: rtsp://user:pass@host:port/path  # pragma: allowlist secret
    - Password encrypted in API response (never returned to frontend)
    - RTSP URL with credentials sent only to go2rtc backend
    """
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stream_id": "test",
            "url": "http://localhost:8555/api/ws?src=test",
        }
        mock_post.return_value = mock_response

        await go2rtc_client.register_stream(
            camera_id=sample_camera_config["camera_id"],
            rtsp_url=sample_camera_config["rtsp_url"],
            username=sample_camera_config["username"],
            password=sample_camera_config["password"],
        )

        # Verify credentials are in the RTSP URL sent to go2rtc
        call_kwargs = mock_post.call_args.kwargs
        stream_source = call_kwargs["json"]["source"]
        assert (
            f"{sample_camera_config['username']}:{sample_camera_config['password']}"
            in stream_source
        )


@pytest.mark.asyncio
async def test_register_stream_no_credentials(go2rtc_client, sample_camera_config):
    """Test stream registration without credentials (public camera).

    RED: This test will fail until optional credential handling is implemented.
    Expected behavior:
    - RTSP URL sent without credentials if not provided
    - Stream registration succeeds for public cameras
    """
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stream_id": "test",
            "url": "http://localhost:8555/api/ws?src=test",
        }
        mock_post.return_value = mock_response

        result = await go2rtc_client.register_stream(
            camera_id=sample_camera_config["camera_id"],
            rtsp_url=sample_camera_config["rtsp_url"],
            # No username/password provided
        )

        assert "webrtc_url" in result

        # Verify no credentials in RTSP URL
        call_kwargs = mock_post.call_args.kwargs
        stream_source = call_kwargs["json"]["source"]
        assert "@" not in stream_source  # No credentials prefix


@pytest.mark.asyncio
async def test_register_stream_go2rtc_unavailable(go2rtc_client, sample_camera_config):
    """Test stream registration when go2rtc is unavailable.

    RED: This test will fail until exception handling is implemented.
    Expected behavior:
    - Raises Go2RTCUnavailableError
    - Error message indicates service unavailability
    - Allows API to return 503 with fallback to snapshot
    """
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(Go2RTCUnavailableError) as exc_info:
            await go2rtc_client.register_stream(
                camera_id=sample_camera_config["camera_id"],
                rtsp_url=sample_camera_config["rtsp_url"],
            )

        assert "unavailable" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_register_stream_timeout(go2rtc_client, sample_camera_config):
    """Test stream registration timeout handling.

    RED: This test will fail until timeout exception handling is implemented.
    Expected behavior:
    - Raises Go2RTCUnavailableError on timeout
    - Timeout respects configured client timeout (2s)
    """
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Request timeout")):
        with pytest.raises(Go2RTCUnavailableError) as exc_info:
            await go2rtc_client.register_stream(
                camera_id=sample_camera_config["camera_id"],
                rtsp_url=sample_camera_config["rtsp_url"],
            )

        assert "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_register_stream_invalid_rtsp_url(go2rtc_client, sample_camera_config):
    """Test stream registration with invalid RTSP URL.

    RED: This test will fail until validation is implemented.
    Expected behavior:
    - Raises StreamRegistrationError for invalid URLs
    - Validates RTSP URL format before sending to go2rtc
    """
    with pytest.raises(StreamRegistrationError) as exc_info:
        await go2rtc_client.register_stream(
            camera_id=sample_camera_config["camera_id"],
            rtsp_url="http://invalid-protocol.com/stream",  # Not RTSP
        )

    assert "invalid" in str(exc_info.value).lower()
    assert "rtsp" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_register_stream_generates_unique_stream_id(go2rtc_client, sample_camera_config):
    """Test that each stream registration generates a unique stream ID.

    RED: This test will fail until stream ID generation is implemented.
    Expected behavior:
    - Stream ID includes camera_id for identification
    - Stream ID includes timestamp or random suffix for uniqueness
    - Format: camera_{camera_id}_{unique_suffix}
    """
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stream_id": "camera_front_door_abc123",
            "url": "http://localhost:8555/api/ws?src=camera_front_door_abc123",
        }
        mock_post.return_value = mock_response

        result = await go2rtc_client.register_stream(
            camera_id=sample_camera_config["camera_id"],
            rtsp_url=sample_camera_config["rtsp_url"],
        )

        stream_id = result["stream_id"]
        assert "camera_" in stream_id
        assert sample_camera_config["camera_id"] in stream_id


# Test: Unregister Stream


@pytest.mark.asyncio
async def test_unregister_stream_success(go2rtc_client):
    """Test successful stream removal from go2rtc.

    RED: This test will fail until unregister_stream() is implemented.
    Expected behavior:
    - DELETE request to /api/streams/{stream_id}
    - Stream removed from go2rtc
    - Cleanup on preview session end
    """
    stream_id = "camera_test_12345"

    with patch("httpx.AsyncClient.delete") as mock_delete:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_delete.return_value = mock_response

        await go2rtc_client.unregister_stream(stream_id)

        mock_delete.assert_called_once()
        # Verify correct endpoint
        call_args = mock_delete.call_args
        assert stream_id in str(call_args)


@pytest.mark.asyncio
async def test_unregister_stream_not_found(go2rtc_client):
    """Test unregistering a non-existent stream.

    RED: This test will fail until 404 handling is implemented.
    Expected behavior:
    - 404 response does not raise exception
    - Idempotent operation (safe to call multiple times)
    """
    stream_id = "nonexistent_stream"

    with patch("httpx.AsyncClient.delete") as mock_delete:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_delete.return_value = mock_response

        # Should not raise exception
        await go2rtc_client.unregister_stream(stream_id)

        mock_delete.assert_called_once()


@pytest.mark.asyncio
async def test_unregister_stream_go2rtc_unavailable(go2rtc_client):
    """Test unregister when go2rtc is unavailable.

    RED: This test will fail until error handling is implemented.
    Expected behavior:
    - Connection error does not raise exception
    - Logs warning but continues (best-effort cleanup)
    """
    stream_id = "camera_test_12345"

    with patch("httpx.AsyncClient.delete", side_effect=httpx.ConnectError("Connection refused")):
        # Should not raise exception (best-effort cleanup)
        await go2rtc_client.unregister_stream(stream_id)


# Test: Session Expiry


@pytest.mark.asyncio
async def test_register_stream_includes_expiry_time(go2rtc_client, sample_camera_config):
    """Test that stream registration includes 5-minute expiry.

    RED: This test will fail until expiry tracking is implemented.
    Expected behavior:
    - Response includes expires_in field (300 seconds)
    - Frontend can display countdown timer
    - Design doc specifies 5-minute session expiry
    """
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stream_id": "test",
            "url": "http://localhost:8555/api/ws?src=test",
        }
        mock_post.return_value = mock_response

        result = await go2rtc_client.register_stream(
            camera_id=sample_camera_config["camera_id"],
            rtsp_url=sample_camera_config["rtsp_url"],
        )

        assert "expires_in" in result
        assert result["expires_in"] == 300  # 5 minutes in seconds


# Test: Password Security


@pytest.mark.asyncio
async def test_register_stream_password_not_logged(go2rtc_client, sample_camera_config, caplog):
    """Test that passwords are never logged or exposed.

    RED: This test will fail until logging sanitization is implemented.
    Expected behavior:
    - Passwords replaced with *** in logs
    - No password in API response
    - Security requirement from design doc
    """
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "stream_id": "test",
            "url": "http://localhost:8555/api/ws?src=test",
        }
        mock_post.return_value = mock_response

        with caplog.at_level("DEBUG"):
            result = await go2rtc_client.register_stream(
                camera_id=sample_camera_config["camera_id"],
                rtsp_url=sample_camera_config["rtsp_url"],
                username=sample_camera_config["username"],
                password=sample_camera_config["password"],
            )

        # Verify password not in logs
        log_text = " ".join(caplog.messages)
        assert sample_camera_config["password"] not in log_text

        # Verify password not in API response
        assert "password" not in result
        assert sample_camera_config["password"] not in json.dumps(result)


# Test: Error Messages


@pytest.mark.asyncio
async def test_register_stream_error_message_format(go2rtc_client, sample_camera_config):
    """Test that error messages are user-friendly.

    RED: This test will fail until error message formatting is implemented.
    Expected behavior:
    - Error messages indicate what went wrong
    - Include camera_id for context
    - Actionable guidance for common issues
    """
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Invalid stream configuration"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad request", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(StreamRegistrationError) as exc_info:
            await go2rtc_client.register_stream(
                camera_id=sample_camera_config["camera_id"],
                rtsp_url=sample_camera_config["rtsp_url"],
            )

        error_msg = str(exc_info.value)
        assert sample_camera_config["camera_id"] in error_msg
        assert "stream" in error_msg.lower()
