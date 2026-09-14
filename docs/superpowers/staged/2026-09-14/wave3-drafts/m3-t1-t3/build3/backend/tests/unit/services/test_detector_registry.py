"""Unit tests for the detector registry service.

Tests the detector registry pattern for managing multiple object detectors
(YOLO26, YOLOv8, etc.) with runtime switching capability (NEM-3692).

TDD: Write tests first, then implement the registry.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.detector_registry import (
    DetectorConfig,
    DetectorRegistry,
    DetectorStatus,
    get_detector_registry,
)


class TestDetectorConfig:
    """Tests for DetectorConfig data class."""

    def test_detector_config_defaults(self):
        """Test that DetectorConfig has sensible defaults."""
        config = DetectorConfig(
            detector_type="yolo26",
            display_name="YOLO26",
            url="http://localhost:8095",
        )

        assert config.detector_type == "yolo26"
        assert config.display_name == "YOLO26"
        assert config.url == "http://localhost:8095"
        assert config.enabled is True
        assert config.model_version is None
        assert config.description is not None

    def test_detector_config_custom_values(self):
        """Test DetectorConfig with custom values."""
        config = DetectorConfig(
            detector_type="yolov8",
            display_name="YOLOv8",
            url="http://localhost:8096",
            enabled=False,
            model_version="yolov8n",
            description="YOLOv8 nano model for fast inference",
        )

        assert config.detector_type == "yolov8"
        assert config.enabled is False
        assert config.model_version == "yolov8n"


class TestDetectorRegistry:
    """Tests for the DetectorRegistry singleton."""

    def test_register_detector(self):
        """Test registering a new detector."""
        registry = DetectorRegistry()

        config = DetectorConfig(
            detector_type="yolo26",
            display_name="YOLO26",
            url="http://localhost:8095",
        )
        registry.register(config)

        assert "yolo26" in registry.available_detectors
        assert registry.get_config("yolo26") == config

    def test_register_multiple_detectors(self):
        """Test registering multiple detectors."""
        registry = DetectorRegistry()

        yolo26_config = DetectorConfig(
            detector_type="yolo26",
            display_name="YOLO26",
            url="http://localhost:8095",
        )
        yolov8_config = DetectorConfig(
            detector_type="yolov8",
            display_name="YOLOv8",
            url="http://localhost:8096",
        )

        registry.register(yolo26_config)
        registry.register(yolov8_config)

        assert len(registry.available_detectors) == 2
        assert "yolo26" in registry.available_detectors
        assert "yolov8" in registry.available_detectors

    def test_get_config_raises_for_unknown_detector(self):
        """Test that getting config for unknown detector raises ValueError."""
        registry = DetectorRegistry()

        with pytest.raises(ValueError, match="Unknown detector type"):
            registry.get_config("unknown_detector")

    def test_set_active_detector(self):
        """Test setting the active detector."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )

        registry.set_active("yolo26")

        assert registry.active_detector == "yolo26"

    def test_set_active_detector_validates_exists(self):
        """Test that setting unknown detector as active raises error."""
        registry = DetectorRegistry()

        with pytest.raises(ValueError, match="Unknown detector type"):
            registry.set_active("nonexistent")

    def test_set_active_detector_validates_enabled(self):
        """Test that setting disabled detector as active raises error."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolov8",
                display_name="YOLOv8",
                url="http://localhost:8096",
                enabled=False,
            )
        )

        with pytest.raises(ValueError, match="not enabled"):
            registry.set_active("yolov8")

    def test_get_active_config(self):
        """Test getting the active detector configuration."""
        registry = DetectorRegistry()
        config = DetectorConfig(
            detector_type="yolo26",
            display_name="YOLO26",
            url="http://localhost:8095",
        )
        registry.register(config)
        registry.set_active("yolo26")

        active_config = registry.get_active_config()

        assert active_config == config

    def test_get_active_config_raises_when_none_active(self):
        """Test that getting active config raises when no detector is active."""
        registry = DetectorRegistry()

        with pytest.raises(ValueError, match="No active detector"):
            registry.get_active_config()

    def test_list_detectors_returns_info(self):
        """Test listing all registered detectors with their info."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )
        registry.register(
            DetectorConfig(
                detector_type="yolov8",
                display_name="YOLOv8",
                url="http://localhost:8096",
                enabled=False,
            )
        )
        registry.set_active("yolo26")

        detectors = registry.list_detectors()

        assert len(detectors) == 2

        yolo26_info = next(d for d in detectors if d.detector_type == "yolo26")
        assert yolo26_info.display_name == "YOLO26"
        assert yolo26_info.enabled is True
        assert yolo26_info.is_active is True

        yolov8_info = next(d for d in detectors if d.detector_type == "yolov8")
        assert yolov8_info.enabled is False
        assert yolov8_info.is_active is False


class TestDetectorRegistryHealth:
    """Tests for detector health checking in the registry."""

    @pytest.mark.asyncio
    async def test_check_detector_health_healthy(self):
        """Test health check returns healthy status."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy", "model_loaded": True}
            mock_client.get.return_value = mock_response

            status = await registry.check_health("yolo26")

            assert status.detector_type == "yolo26"
            assert status.healthy is True
            assert status.model_loaded is True

    @pytest.mark.asyncio
    async def test_check_detector_health_unhealthy(self):
        """Test health check returns unhealthy status on connection error."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = Exception("Connection refused")

            status = await registry.check_health("yolo26")

            assert status.detector_type == "yolo26"
            assert status.healthy is False
            assert "Connection refused" in status.error_message

    @pytest.mark.asyncio
    async def test_check_all_health(self):
        """Test checking health of all registered detectors."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )
        registry.register(
            DetectorConfig(
                detector_type="yolov8",
                display_name="YOLOv8",
                url="http://localhost:8096",
            )
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy", "model_loaded": True}
            mock_client.get.return_value = mock_response

            statuses = await registry.check_all_health()

            assert len(statuses) == 2
            assert all(s.healthy for s in statuses)


class TestDetectorRegistrySingleton:
    """Tests for the detector registry singleton pattern."""

    def test_get_detector_registry_returns_singleton(self):
        """Test that get_detector_registry returns the same instance."""
        # Clear the singleton for testing
        with patch.object(DetectorRegistry, "_instance", None):
            registry1 = get_detector_registry()
            registry2 = get_detector_registry()

            assert registry1 is registry2

    def test_registry_initialized_with_default_detectors(self):
        """Test that registry is initialized with default detector configs."""
        with patch.object(DetectorRegistry, "_instance", None):
            registry = get_detector_registry()

            # Should have at least YOLO26 registered by default
            assert "yolo26" in registry.available_detectors


class TestDetectorRegistrySwitching:
    """Tests for runtime detector switching."""

    @pytest.mark.asyncio
    async def test_switch_detector_validates_health_first(self):
        """Test that switching detectors validates health before switching."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )
        registry.register(
            DetectorConfig(
                detector_type="yolov8",
                display_name="YOLOv8",
                url="http://localhost:8096",
            )
        )
        registry.set_active("yolo26")

        with patch.object(registry, "check_health") as mock_health:
            mock_health.return_value = DetectorStatus(
                detector_type="yolov8",
                healthy=True,
                model_loaded=True,
            )

            await registry.switch_detector("yolov8")

            mock_health.assert_called_once_with("yolov8")
            assert registry.active_detector == "yolov8"

    @pytest.mark.asyncio
    async def test_switch_detector_fails_if_unhealthy(self):
        """Test that switching to unhealthy detector fails."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )
        registry.register(
            DetectorConfig(
                detector_type="yolov8",
                display_name="YOLOv8",
                url="http://localhost:8096",
            )
        )
        registry.set_active("yolo26")

        with patch.object(registry, "check_health") as mock_health:
            mock_health.return_value = DetectorStatus(
                detector_type="yolov8",
                healthy=False,
                model_loaded=False,
                error_message="Service unavailable",
            )

            with pytest.raises(ValueError, match="not healthy"):
                await registry.switch_detector("yolov8")

            # Active detector should remain unchanged
            assert registry.active_detector == "yolo26"

    @pytest.mark.asyncio
    async def test_switch_detector_with_force_skips_health(self):
        """Test that force switch bypasses health check."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )
        registry.register(
            DetectorConfig(
                detector_type="yolov8",
                display_name="YOLOv8",
                url="http://localhost:8096",
            )
        )
        registry.set_active("yolo26")

        with patch.object(registry, "check_health") as mock_health:
            await registry.switch_detector("yolov8", force=True)

            mock_health.assert_not_called()
            assert registry.active_detector == "yolov8"
