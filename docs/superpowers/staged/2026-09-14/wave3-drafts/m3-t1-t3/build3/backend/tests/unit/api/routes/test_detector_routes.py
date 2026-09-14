"""Unit tests for detector switching API routes.

Tests the API endpoints for managing object detectors at runtime (NEM-3692).

TDD: Write tests first, then implement the routes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.routes.detector import router
from backend.services.detector_registry import (
    DetectorConfig,
    DetectorRegistry,
    DetectorStatus,
    reset_detector_registry,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_registry():
    """Create a mock detector registry with test detectors."""
    reset_detector_registry()
    registry = DetectorRegistry()

    # Register test detectors
    registry.register(
        DetectorConfig(
            detector_type="yolo26",
            display_name="YOLO26",
            url="http://localhost:8095",
            enabled=True,
            model_version="yolo26m",
            description="YOLO26 TensorRT object detection",
        )
    )
    registry.register(
        DetectorConfig(
            detector_type="yolov8",
            display_name="YOLOv8",
            url="http://localhost:8096",
            enabled=True,
            model_version="yolov8n",
            description="YOLOv8 nano model",
        )
    )
    registry.register(
        DetectorConfig(
            detector_type="disabled_detector",
            display_name="Disabled Detector",
            url="http://localhost:8097",
            enabled=False,
            description="A disabled detector for testing",
        )
    )
    registry.set_active("yolo26")

    return registry


@pytest.fixture
def test_app(mock_registry) -> FastAPI:
    """Create test FastAPI app with detector router."""
    app = FastAPI()
    app.include_router(router)

    # Override the registry to use our mock
    with patch(
        "backend.api.routes.detector.get_detector_registry",
        return_value=mock_registry,
    ):
        yield app


@pytest.fixture
async def async_client(test_app: FastAPI, mock_registry) -> AsyncClient:
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=test_app)
    with patch(
        "backend.api.routes.detector.get_detector_registry",
        return_value=mock_registry,
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


# =============================================================================
# Test Classes
# =============================================================================


class TestGetDetectors:
    """Tests for GET /api/system/detectors endpoint."""

    @pytest.mark.asyncio
    async def test_list_detectors_returns_all_registered(
        self, async_client: AsyncClient, mock_registry
    ):
        """Test listing all registered detectors."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.get("/system/detectors")

        assert response.status_code == 200
        data = response.json()

        assert "detectors" in data
        assert "active_detector" in data
        assert isinstance(data["detectors"], list)
        assert len(data["detectors"]) == 3  # yolo26, yolov8, disabled_detector

    @pytest.mark.asyncio
    async def test_list_detectors_includes_correct_fields(
        self, async_client: AsyncClient, mock_registry
    ):
        """Test that detector list includes all required fields."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.get("/system/detectors")

        assert response.status_code == 200
        data = response.json()

        for detector in data["detectors"]:
            assert "detector_type" in detector
            assert "display_name" in detector
            assert "enabled" in detector
            assert "is_active" in detector
            assert "url" in detector

    @pytest.mark.asyncio
    async def test_list_detectors_shows_active_detector(
        self, async_client: AsyncClient, mock_registry
    ):
        """Test that the active detector is correctly identified."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.get("/system/detectors")

        assert response.status_code == 200
        data = response.json()

        # Check that exactly one detector is marked as active
        active_detectors = [d for d in data["detectors"] if d["is_active"]]
        assert len(active_detectors) == 1
        assert data["active_detector"] == active_detectors[0]["detector_type"]
        assert data["active_detector"] == "yolo26"


class TestGetActiveDetector:
    """Tests for GET /api/system/detectors/active endpoint."""

    @pytest.mark.asyncio
    async def test_get_active_detector(self, async_client: AsyncClient, mock_registry):
        """Test getting the currently active detector."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.get("/system/detectors/active")

        assert response.status_code == 200
        data = response.json()

        assert data["detector_type"] == "yolo26"
        assert data["display_name"] == "YOLO26"
        assert "url" in data
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_get_active_detector_includes_config(
        self, async_client: AsyncClient, mock_registry
    ):
        """Test that active detector response includes full configuration."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.get("/system/detectors/active")

        assert response.status_code == 200
        data = response.json()

        # Should include detector configuration
        assert data["detector_type"] == "yolo26"
        assert data["enabled"] is True  # Active detector must be enabled
        assert data["model_version"] == "yolo26m"


class TestSwitchDetector:
    """Tests for PUT /api/system/detectors/active endpoint."""

    @pytest.mark.asyncio
    async def test_switch_detector_success(self, async_client: AsyncClient, mock_registry):
        """Test successfully switching to a different detector."""
        # Mock the health check to return healthy
        mock_registry.check_health = AsyncMock(
            return_value=DetectorStatus(
                detector_type="yolov8",
                healthy=True,
                model_loaded=True,
            )
        )

        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.put(
                "/system/detectors/active",
                json={"detector_type": "yolov8"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["detector_type"] == "yolov8"
        assert "message" in data

    @pytest.mark.asyncio
    async def test_switch_detector_invalid_type(self, async_client: AsyncClient, mock_registry):
        """Test switching to an invalid detector type returns 400."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.put(
                "/system/detectors/active",
                json={"detector_type": "nonexistent_detector"},
            )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "unknown" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_switch_detector_disabled_returns_400(
        self, async_client: AsyncClient, mock_registry
    ):
        """Test switching to a disabled detector returns 400."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.put(
                "/system/detectors/active",
                json={"detector_type": "disabled_detector"},
            )

        assert response.status_code == 400
        assert "not enabled" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_switch_detector_with_force(self, async_client: AsyncClient, mock_registry):
        """Test force switching bypasses health check."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.put(
                "/system/detectors/active",
                json={"detector_type": "yolov8", "force": True},
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_switch_detector_validates_body(self, async_client: AsyncClient, mock_registry):
        """Test that switch endpoint validates request body."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            # Missing detector_type
            response = await async_client.put(
                "/system/detectors/active",
                json={},
            )

        assert response.status_code == 422  # Validation error


class TestGetDetectorConfig:
    """Tests for GET /api/system/detectors/{detector_type} endpoint."""

    @pytest.mark.asyncio
    async def test_get_detector_config(self, async_client: AsyncClient, mock_registry):
        """Test getting configuration for a specific detector."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.get("/system/detectors/yolo26")

        assert response.status_code == 200
        data = response.json()

        assert data["detector_type"] == "yolo26"
        assert "display_name" in data
        assert "url" in data
        assert "enabled" in data

    @pytest.mark.asyncio
    async def test_get_detector_config_not_found(self, async_client: AsyncClient, mock_registry):
        """Test getting config for unknown detector returns 404."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.get("/system/detectors/unknown_type")

        assert response.status_code == 404


class TestDetectorHealth:
    """Tests for GET /api/system/detectors/{detector_type}/health endpoint."""

    @pytest.mark.asyncio
    async def test_get_detector_health(self, async_client: AsyncClient, mock_registry):
        """Test getting health status for a specific detector."""
        # Mock the health check
        mock_registry.check_health = AsyncMock(
            return_value=DetectorStatus(
                detector_type="yolo26",
                healthy=True,
                model_loaded=True,
                latency_ms=15.5,
            )
        )

        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.get("/system/detectors/yolo26/health")

        assert response.status_code == 200
        data = response.json()

        assert data["detector_type"] == "yolo26"
        assert data["healthy"] is True
        assert data["model_loaded"] is True

    @pytest.mark.asyncio
    async def test_get_detector_health_unknown_type(self, async_client: AsyncClient, mock_registry):
        """Test health check for unknown detector returns 404."""
        with patch(
            "backend.api.routes.detector.get_detector_registry",
            return_value=mock_registry,
        ):
            response = await async_client.get("/system/detectors/unknown/health")

        assert response.status_code == 404
