"""Integration tests for ONVIF Discovery API endpoint.

Tests the POST /api/cameras/onvif/discover endpoint for Phase 2 ONVIF Discovery.

Phase 2 Requirements (NEM-4388):
- Discover ONVIF devices on network via WS-Discovery
- Return device list with manufacturer, model, IP, port
- Include RTSP URLs array with profiles
- Handle partial success (some devices timeout)
- Handle no devices found scenario
- Validate subnet parameter

Run with: uv run pytest backend/tests/integration/test_onvif_discovery_api.py -v

TDD Red Phase: These tests will FAIL initially since the enhanced discovery
endpoint doesn't exist yet. Implementation will follow in Phase 2.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_discover_onvif_devices_success(client: AsyncClient):
    """Test successful ONVIF device discovery.

    Verifies that POST /api/cameras/onvif/discover returns a list of
    discovered devices with all required fields.
    """
    # Mock OnvifService.discover_devices
    mock_devices = [
        {
            "ip": "192.168.1.100",
            "port": 80,
            "device_url": "http://192.168.1.100/onvif/device_service",
            "manufacturer": "Hikvision",
            "model": "DS-2CD2385G1",
            "rtsp_urls": [
                {
                    "profile": "mainStream",
                    "url": "rtsp://192.168.1.100:554/Streaming/Channels/101",
                },
                {
                    "profile": "subStream",
                    "url": "rtsp://192.168.1.100:554/Streaming/Channels/102",
                },
            ],
            "requires_auth": True,
            "capabilities": ["video", "ptz", "events"],
        }
    ]

    with patch("backend.api.routes.onvif.OnvifService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.discover_devices = AsyncMock(return_value=mock_devices)
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/cameras/onvif/discover",
            json={"subnet": "192.168.1.0/24", "timeout": 10},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "devices" in data
        assert "count" in data
        assert data["count"] == 1

        # Verify device fields
        device = data["devices"][0]
        assert device["ip"] == "192.168.1.100"
        assert device["port"] == 80
        assert device["manufacturer"] == "Hikvision"
        assert device["model"] == "DS-2CD2385G1"
        assert device["requires_auth"] is True

        # Verify RTSP URLs
        assert "rtsp_urls" in device
        assert len(device["rtsp_urls"]) == 2
        assert device["rtsp_urls"][0]["profile"] == "mainStream"
        assert "rtsp://" in device["rtsp_urls"][0]["url"]

        # Verify capabilities
        assert "capabilities" in device
        assert "video" in device["capabilities"]
        assert "ptz" in device["capabilities"]


@pytest.mark.asyncio
async def test_discover_onvif_devices_multiple_devices(client: AsyncClient):
    """Test discovery with multiple ONVIF devices on network."""
    mock_devices = [
        {
            "ip": "192.168.1.100",
            "port": 80,
            "device_url": "http://192.168.1.100/onvif/device_service",
            "manufacturer": "Hikvision",
            "model": "DS-2CD2385G1",
            "rtsp_urls": [{"profile": "main", "url": "rtsp://192.168.1.100:554/stream1"}],
            "requires_auth": True,
            "capabilities": ["video", "ptz"],
        },
        {
            "ip": "192.168.1.101",
            "port": 8080,
            "device_url": "http://192.168.1.101:8080/onvif/device_service",
            "manufacturer": "Dahua",
            "model": "IPC-HDW5442T",
            "rtsp_urls": [{"profile": "main", "url": "rtsp://192.168.1.101:554/cam/realmonitor"}],
            "requires_auth": True,
            "capabilities": ["video"],
        },
    ]

    with patch("backend.api.routes.onvif.OnvifService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.discover_devices = AsyncMock(return_value=mock_devices)
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/cameras/onvif/discover",
            json={"subnet": "192.168.1.0/24", "timeout": 10},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 2
        assert len(data["devices"]) == 2

        # Verify both devices present
        ips = [d["ip"] for d in data["devices"]]
        assert "192.168.1.100" in ips
        assert "192.168.1.101" in ips

        # Verify non-standard port
        dahua = next(d for d in data["devices"] if d["ip"] == "192.168.1.101")
        assert dahua["port"] == 8080


@pytest.mark.asyncio
async def test_discover_onvif_devices_no_devices_found(client: AsyncClient):
    """Test discovery when no ONVIF devices found on network.

    Should return 200 with empty devices list and count 0.
    """
    with patch("backend.api.routes.onvif.OnvifService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.discover_devices = AsyncMock(return_value=[])
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/cameras/onvif/discover",
            json={"subnet": "192.168.1.0/24", "timeout": 5},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 0
        assert data["devices"] == []


@pytest.mark.asyncio
async def test_discover_onvif_devices_partial_success(client: AsyncClient):
    """Test discovery with partial success (some devices timeout).

    Should return successfully discovered devices and indicate timeout count.
    """
    # Mock result with partial success
    mock_result = {
        "devices": [
            {
                "ip": "192.168.1.100",
                "port": 80,
                "device_url": "http://192.168.1.100/onvif/device_service",
                "manufacturer": "Hikvision",
                "model": "DS-2CD2385G1",
                "rtsp_urls": [{"profile": "main", "url": "rtsp://192.168.1.100:554/stream1"}],
                "requires_auth": True,
                "capabilities": ["video"],
            }
        ],
        "count": 1,
        "timeout_count": 2,
        "message": "Found 1 camera, 2 devices timed out",
    }

    with patch("backend.api.routes.onvif.OnvifService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.discover_devices = AsyncMock(return_value=mock_result)
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/cameras/onvif/discover",
            json={"subnet": "192.168.1.0/24", "timeout": 10},
        )

        assert response.status_code == 200
        data = response.json()

        # Should include successful device
        assert data["count"] == 1
        assert len(data["devices"]) == 1

        # Should indicate partial success
        assert "timeout_count" in data
        assert data["timeout_count"] == 2
        assert "message" in data


@pytest.mark.asyncio
async def test_discover_onvif_devices_invalid_subnet(client: AsyncClient):
    """Test discovery with invalid subnet format.

    Should return 422 validation error.
    """
    response = await client.post(
        "/api/cameras/onvif/discover",
        json={"subnet": "invalid-subnet", "timeout": 10},
    )

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_discover_onvif_devices_missing_subnet(client: AsyncClient):
    """Test discovery without required subnet parameter.

    Should return 422 validation error.
    """
    response = await client.post(
        "/api/cameras/onvif/discover",
        json={"timeout": 10},
    )

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_discover_onvif_devices_invalid_timeout(client: AsyncClient):
    """Test discovery with invalid timeout values."""
    # Test negative timeout
    response = await client.post(
        "/api/cameras/onvif/discover",
        json={"subnet": "192.168.1.0/24", "timeout": -5},
    )
    assert response.status_code == 422

    # Test timeout too large
    response = await client.post(
        "/api/cameras/onvif/discover",
        json={"subnet": "192.168.1.0/24", "timeout": 400},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_discover_onvif_devices_default_timeout(client: AsyncClient):
    """Test discovery uses default timeout when not specified."""
    mock_devices = []

    with patch("backend.api.routes.onvif.OnvifService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.discover_devices = AsyncMock(return_value=mock_devices)
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/cameras/onvif/discover",
            json={"subnet": "192.168.1.0/24"},
        )

        assert response.status_code == 200

        # Verify service was called with default timeout (10 seconds)
        mock_service.discover_devices.assert_called_once()
        call_args = mock_service.discover_devices.call_args
        assert call_args.kwargs.get("timeout", 10) == 10


@pytest.mark.asyncio
async def test_discover_onvif_devices_service_failure(client: AsyncClient):
    """Test discovery when service raises exception.

    Should return 500 internal server error.
    """
    with patch("backend.api.routes.onvif.OnvifService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.discover_devices = AsyncMock(side_effect=Exception("WS-Discovery failed"))
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/cameras/onvif/discover",
            json={"subnet": "192.168.1.0/24", "timeout": 10},
        )

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Discovery failed" in data["detail"]


@pytest.mark.asyncio
async def test_discover_onvif_devices_rtsp_urls_structure(client: AsyncClient):
    """Test that RTSP URLs array has correct structure.

    Each RTSP URL entry should have profile name and URL.
    """
    mock_devices = [
        {
            "ip": "192.168.1.100",
            "port": 80,
            "device_url": "http://192.168.1.100/onvif/device_service",
            "manufacturer": "Hikvision",
            "model": "DS-2CD2385G1",
            "rtsp_urls": [
                {
                    "profile": "mainStream",
                    "url": "rtsp://192.168.1.100:554/Streaming/Channels/101",
                    "resolution": "1920x1080",
                    "codec": "H264",
                },
                {
                    "profile": "subStream",
                    "url": "rtsp://192.168.1.100:554/Streaming/Channels/102",
                    "resolution": "640x480",
                    "codec": "H264",
                },
            ],
            "requires_auth": True,
            "capabilities": ["video"],
        }
    ]

    with patch("backend.api.routes.onvif.OnvifService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.discover_devices = AsyncMock(return_value=mock_devices)
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/cameras/onvif/discover",
            json={"subnet": "192.168.1.0/24", "timeout": 10},
        )

        assert response.status_code == 200
        data = response.json()

        device = data["devices"][0]
        rtsp_urls = device["rtsp_urls"]

        # Verify structure
        for stream in rtsp_urls:
            assert "profile" in stream
            assert "url" in stream
            assert stream["url"].startswith("rtsp://")

        # Verify optional fields if present
        if "resolution" in rtsp_urls[0]:
            assert "x" in rtsp_urls[0]["resolution"]
        if "codec" in rtsp_urls[0]:
            assert rtsp_urls[0]["codec"] in ["H264", "H265", "MJPEG"]


@pytest.mark.asyncio
async def test_discover_onvif_devices_response_includes_all_required_fields(
    client: AsyncClient,
):
    """Test that discovery response includes all required fields per design doc."""
    mock_devices = [
        {
            "ip": "192.168.1.100",
            "port": 80,
            "device_url": "http://192.168.1.100/onvif/device_service",
            "manufacturer": "Hikvision",
            "model": "DS-2CD2385G1",
            "rtsp_urls": [{"profile": "main", "url": "rtsp://192.168.1.100:554/stream1"}],
            "requires_auth": True,
            "capabilities": ["video", "ptz", "events"],
        }
    ]

    with patch("backend.api.routes.onvif.OnvifService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.discover_devices = AsyncMock(return_value=mock_devices)
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/cameras/onvif/discover",
            json={"subnet": "192.168.1.0/24"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify top-level structure
        assert "devices" in data
        assert "count" in data

        # Verify device has all required fields from design doc
        device = data["devices"][0]
        required_fields = [
            "ip",
            "port",
            "manufacturer",
            "model",
            "rtsp_urls",
            "requires_auth",
            "capabilities",
        ]

        for field in required_fields:
            assert field in device, f"Missing required field: {field}"

        # Verify types
        assert isinstance(device["ip"], str)
        assert isinstance(device["port"], int)
        assert isinstance(device["manufacturer"], str)
        assert isinstance(device["model"], str)
        assert isinstance(device["rtsp_urls"], list)
        assert isinstance(device["requires_auth"], bool)
        assert isinstance(device["capabilities"], list)
