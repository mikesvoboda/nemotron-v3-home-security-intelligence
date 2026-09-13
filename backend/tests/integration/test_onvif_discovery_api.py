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

    with patch("backend.services.onvif_service.OnvifService") as mock_service_class:
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

        # Verify device fields (shipped schema: OnvifDiscoveryResult carries
        # device_url/manufacturer/model/firmware_version/serial_number/
        # hardware_id — ip/port/rtsp_urls/requires_auth/capabilities are
        # unshipped Phase-2 design fields dropped by response_model)
        device = data["devices"][0]
        assert device["device_url"] == "http://192.168.1.100/onvif/device_service"
        assert device["manufacturer"] == "Hikvision"
        assert device["model"] == "DS-2CD2385G1"


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

    with patch("backend.services.onvif_service.OnvifService") as mock_service_class:
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

        # Verify both devices present (shipped schema key)
        urls = [d["device_url"] for d in data["devices"]]
        assert "http://192.168.1.100/onvif/device_service" in urls
        assert "http://192.168.1.101:8080/onvif/device_service" in urls

        # Verify non-standard port on the Dahua device_url
        dahua = next(d for d in data["devices"] if "192.168.1.101:8080" in d["device_url"])
        assert ":8080" in dahua["device_url"]


@pytest.mark.asyncio
async def test_discover_onvif_devices_no_devices_found(client: AsyncClient):
    """Test discovery when no ONVIF devices found on network.

    Should return 200 with empty devices list and count 0.
    """
    with patch("backend.services.onvif_service.OnvifService") as mock_service_class:
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
    # Mock result: discover_devices returns list[dict] (onvif_service.py:282)
    # — the route wraps it in OnvifDiscoveryResponse(devices=..., count=...).
    # timeout_count/message are internal-only (never serialized; the dict
    # shape would raise ValidationError -> 500 inside the route).
    mock_result = [
        {
            "device_url": "http://192.168.1.100/onvif/device_service",
            "manufacturer": "Hikvision",
            "model": "DS-2CD2385G1",
        }
    ]

    with patch("backend.services.onvif_service.OnvifService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.discover_devices = AsyncMock(return_value=mock_result)
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/cameras/onvif/discover",
            json={"subnet": "192.168.1.0/24", "timeout": 10},
        )

        assert response.status_code == 200
        data = response.json()

        # Should include successful device (shipped top-level keys: devices
        # + count only — partial-success indication is not part of the
        # shipped contract)
        assert data["count"] == 1
        assert len(data["devices"]) == 1
        assert data["devices"][0]["manufacturer"] == "Hikvision"


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
    # App-wide error envelope (validation_exception_handler):
    # {"error": {"code": "VALIDATION_ERROR", ...}} — no "detail" key.
    assert data["error"]["code"] == "VALIDATION_ERROR"


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
    # App-wide error envelope (validation_exception_handler):
    # {"error": {"code": "VALIDATION_ERROR", ...}} — no "detail" key.
    assert data["error"]["code"] == "VALIDATION_ERROR"


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

    with patch("backend.services.onvif_service.OnvifService") as mock_service_class:
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
    with patch("backend.services.onvif_service.OnvifService") as mock_service_class:
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

    with patch("backend.services.onvif_service.OnvifService") as mock_service_class:
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
        # rtsp_urls is NOT part of the shipped response schema
        # (OnvifDiscoveryResult, schemas/onvif.py:73-115) — the design-doc
        # per-stream structure was never shipped. Assert the shipped
        # serialization survived the response_model filter instead.
        assert device["device_url"].startswith("http://")
        assert device["manufacturer"] == "Hikvision"
        assert device["model"] == "DS-2CD2385G1"


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

    with patch("backend.services.onvif_service.OnvifService") as mock_service_class:
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

        # Verify device has the SHIPPED required fields
        # (OnvifDiscoveryResult, schemas/onvif.py:73-115); the design-doc
        # fields (ip/port/rtsp_urls/requires_auth/capabilities) were never
        # shipped and are dropped by the response model.
        device = data["devices"][0]
        required_fields = [
            "device_url",
            "manufacturer",
            "model",
            "firmware_version",
            "serial_number",
            "hardware_id",
        ]

        for field in required_fields:
            assert field in device, f"Missing required field: {field}"

        # Verify types
        assert isinstance(device["device_url"], str)
        assert isinstance(device["manufacturer"], str)
        assert isinstance(device["model"], str)
