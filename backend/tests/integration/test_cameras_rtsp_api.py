"""Integration tests for RTSP camera configuration API.

NEM-4382: Test-Driven Development for RTSP configuration endpoints.
These tests define the expected behavior for the /api/cameras/rtsp/test endpoint.

Tests cover:
- POST /api/cameras/rtsp/test endpoint with valid credentials
- Connection test success responses
- Connection test error responses (401, timeout, invalid URL)
- Password security (never in responses)
- Mock camera integration
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.services.rtsp_test_service import RTSPCapabilities, RTSPTestResult


@pytest.mark.asyncio
async def test_rtsp_test_endpoint_success(client: AsyncClient) -> None:
    """Test successful RTSP connection test via API.

    Expected response:
    {
        "success": true,
        "latency_ms": 145,
        "capabilities": {
            "video": true,
            "audio": true,
            "ptz": false,
            "resolution": "1920x1080",
            "codec": "H.264",
            "fps": 25
        }
    }
    """
    # Mock successful connection test
    mock_result = RTSPTestResult(
        success=True,
        latency_ms=145,
        capabilities=RTSPCapabilities(
            video=True,
            audio=True,
            ptz=False,
            resolution="1920x1080",
            codec="H.264",
            fps=25,
        ),
        error_message=None,
    )

    with patch(
        "backend.services.rtsp_test_service.RTSPTestService.test_connection",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await client.post(
            "/api/cameras/rtsp/test",
            json={
                "rtsp_url": "rtsp://192.168.1.100:554/stream1",
                "username": "admin",
                "password": "secret123",  # pragma: allowlist secret
            },
        )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["latency_ms"] == 145
    assert data["capabilities"]["video"] is True
    assert data["capabilities"]["audio"] is True
    assert data["capabilities"]["ptz"] is False
    assert data["capabilities"]["resolution"] == "1920x1080"
    assert data["capabilities"]["codec"] == "H.264"
    assert data["capabilities"]["fps"] == 25


@pytest.mark.asyncio
async def test_rtsp_test_endpoint_timeout(client: AsyncClient) -> None:
    """Test RTSP connection timeout via API.

    Expected response:
    {
        "success": false,
        "error_message": "Connection timeout after 5 seconds",
        "latency_ms": null,
        "capabilities": null
    }
    """
    mock_result = RTSPTestResult(
        success=False,
        error_message="Connection timeout after 5 seconds",
        latency_ms=None,
        capabilities=None,
    )

    with patch(
        "backend.services.rtsp_test_service.RTSPTestService.test_connection",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await client.post(
            "/api/cameras/rtsp/test",
            json={"rtsp_url": "rtsp://192.168.1.100:554/stream1"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is False
    assert "timeout" in data["error_message"].lower()
    assert data["latency_ms"] is None
    assert data["capabilities"] is None


@pytest.mark.asyncio
async def test_rtsp_test_endpoint_authentication_failure(client: AsyncClient) -> None:
    """Test RTSP authentication failure via API.

    Expected response:
    {
        "success": false,
        "error_message": "Authentication failed. Check username/password.",
        "latency_ms": null,
        "capabilities": null
    }
    """
    mock_result = RTSPTestResult(
        success=False,
        error_message="Authentication failed. Check username/password.",
        latency_ms=None,
        capabilities=None,
    )

    with patch(
        "backend.services.rtsp_test_service.RTSPTestService.test_connection",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await client.post(
            "/api/cameras/rtsp/test",
            json={
                "rtsp_url": "rtsp://192.168.1.100:554/stream1",
                "username": "wrong",
                "password": "wrong",  # pragma: allowlist secret
            },
        )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is False
    assert (
        "authentication" in data["error_message"].lower()
        or "credentials" in data["error_message"].lower()
    )


@pytest.mark.asyncio
async def test_rtsp_test_endpoint_invalid_url(client: AsyncClient) -> None:
    """Test RTSP connection with invalid URL format via API.

    Expected response: 422 validation error or 200 with error
    """
    response = await client.post(
        "/api/cameras/rtsp/test",
        json={
            "rtsp_url": "http://192.168.1.100:80/stream",  # Wrong protocol
        },
    )

    # Could be 422 (validation error) or 200 (runtime error)
    assert response.status_code in [200, 422]

    if response.status_code == 200:
        data = response.json()
        assert data["success"] is False
        assert data["error_message"] is not None


@pytest.mark.asyncio
async def test_rtsp_test_endpoint_missing_url(client: AsyncClient) -> None:
    """Test RTSP connection test with missing URL.

    Expected response: 422 validation error
    """
    response = await client.post("/api/cameras/rtsp/test", json={})

    assert response.status_code == 422
    data = response.json()
    assert "rtsp_url" in str(data).lower() or "required" in str(data).lower()


@pytest.mark.asyncio
async def test_rtsp_test_endpoint_optional_credentials(client: AsyncClient) -> None:
    """Test RTSP connection test with URL only (no credentials).

    Some cameras don't require authentication.
    """
    mock_result = RTSPTestResult(
        success=True,
        latency_ms=120,
        capabilities=RTSPCapabilities(video=True, resolution="1280x720", codec="H.264", fps=15),
        error_message=None,
    )

    with patch(
        "backend.services.rtsp_test_service.RTSPTestService.test_connection",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await client.post(
            "/api/cameras/rtsp/test",
            json={"rtsp_url": "rtsp://192.168.1.100:554/stream1"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_rtsp_test_response_never_includes_password(client: AsyncClient) -> None:
    """Test that passwords are never included in API responses.

    Critical security requirement: passwords must never be echoed back.
    """
    mock_result = RTSPTestResult(
        success=True,
        latency_ms=150,
        capabilities=RTSPCapabilities(video=True, resolution="1920x1080"),
        error_message=None,
    )

    with patch(
        "backend.services.rtsp_test_service.RTSPTestService.test_connection",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await client.post(
            "/api/cameras/rtsp/test",
            json={
                "rtsp_url": "rtsp://192.168.1.100:554/stream1",
                "username": "admin",
                "password": "my_secret_password_12345",  # pragma: allowlist secret
            },
        )

    assert response.status_code == 200
    response_text = response.text.lower()

    # Password should NOT appear in response
    assert "my_secret_password" not in response_text
    assert "secret" not in response_text or "***" in response_text


@pytest.mark.asyncio
async def test_rtsp_test_endpoint_network_error(client: AsyncClient) -> None:
    """Test RTSP connection with network unreachable error."""
    mock_result = RTSPTestResult(
        success=False,
        error_message="Network unreachable: camera not found on network",
        latency_ms=None,
        capabilities=None,
    )

    with patch(
        "backend.services.rtsp_test_service.RTSPTestService.test_connection",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await client.post(
            "/api/cameras/rtsp/test",
            json={"rtsp_url": "rtsp://192.168.99.99:554/stream1"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is False
    assert (
        "unreachable" in data["error_message"].lower()
        or "not found" in data["error_message"].lower()
    )


@pytest.mark.asyncio
async def test_rtsp_test_endpoint_rtsps_secure(client: AsyncClient) -> None:
    """Test RTSP connection with secure rtsps:// protocol."""
    mock_result = RTSPTestResult(
        success=True,
        latency_ms=200,
        capabilities=RTSPCapabilities(video=True, resolution="1920x1080"),
        error_message=None,
    )

    with patch(
        "backend.services.rtsp_test_service.RTSPTestService.test_connection",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await client.post(
            "/api/cameras/rtsp/test",
            json={"rtsp_url": "rtsps://192.168.1.100:322/stream1"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_rtsp_test_endpoint_concurrent_requests(client: AsyncClient) -> None:
    """Test that multiple concurrent RTSP test requests are handled properly."""
    mock_result = RTSPTestResult(
        success=True,
        latency_ms=150,
        capabilities=RTSPCapabilities(video=True, resolution="1920x1080"),
        error_message=None,
    )

    with patch(
        "backend.services.rtsp_test_service.RTSPTestService.test_connection",
        new=AsyncMock(return_value=mock_result),
    ):
        # Send 5 concurrent requests
        import asyncio

        tasks = [
            client.post(
                "/api/cameras/rtsp/test",
                json={"rtsp_url": f"rtsp://192.168.1.{i}:554/stream1"},
            )
            for i in range(100, 105)
        ]

        responses = await asyncio.gather(*tasks)

    # All should succeed
    for response in responses:
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_rtsp_test_endpoint_long_url(client: AsyncClient) -> None:
    """Test RTSP connection with very long URL path."""
    long_path = "/".join([f"segment{i}" for i in range(50)])
    url = f"rtsp://192.168.1.100:554/{long_path}"

    mock_result = RTSPTestResult(
        success=True,
        latency_ms=180,
        capabilities=RTSPCapabilities(video=True, resolution="1920x1080"),
        error_message=None,
    )

    with patch(
        "backend.services.rtsp_test_service.RTSPTestService.test_connection",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await client.post("/api/cameras/rtsp/test", json={"rtsp_url": url})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_rtsp_test_endpoint_special_characters_in_password(client: AsyncClient) -> None:
    """Test RTSP connection with special characters in password."""
    mock_result = RTSPTestResult(
        success=True,
        latency_ms=150,
        capabilities=RTSPCapabilities(video=True, resolution="1920x1080"),
        error_message=None,
    )

    with patch(
        "backend.services.rtsp_test_service.RTSPTestService.test_connection",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await client.post(
            "/api/cameras/rtsp/test",
            json={
                "rtsp_url": "rtsp://192.168.1.100:554/stream1",
                "username": "admin",
                "password": "p@$$w0rd!#&*()[]{}",  # pragma: allowlist secret
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
