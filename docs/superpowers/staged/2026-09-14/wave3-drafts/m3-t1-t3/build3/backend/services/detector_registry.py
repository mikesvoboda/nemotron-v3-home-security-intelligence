"""Detector registry service for managing multiple object detectors.

This service implements a registry pattern for managing object detectors
(YOLO26, YOLOv8, etc.) with runtime switching capability (NEM-3692).

Features:
- Register multiple detector configurations
- Set/get active detector
- Health checking for detectors
- Runtime switching with optional health validation

Usage:
    from backend.services.detector_registry import get_detector_registry

    registry = get_detector_registry()

    # List available detectors
    detectors = registry.list_detectors()

    # Switch to a different detector (validates health first)
    await registry.switch_detector("yolov8")

    # Get active detector configuration
    config = registry.get_active_config()
"""

from __future__ import annotations

__all__ = [
    "DetectorConfig",
    "DetectorInfo",
    "DetectorRegistry",
    "DetectorStatus",
    "get_detector_registry",
]

from dataclasses import dataclass, field

import httpx

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DetectorConfig:
    """Configuration for an object detector.

    Attributes:
        detector_type: Unique identifier for the detector (e.g., "yolo26", "yolov8")
        display_name: Human-readable name for UI display
        url: Base URL of the detector HTTP service
        enabled: Whether this detector is available for use
        model_version: Optional model version string (e.g., "yolo26m", "yolov8n")
        description: Description of the detector capabilities
    """

    detector_type: str
    display_name: str
    url: str
    enabled: bool = True
    model_version: str | None = None
    description: str = field(default="Object detection model")


@dataclass
class DetectorStatus:
    """Health status of a detector.

    Attributes:
        detector_type: Identifier of the detector
        healthy: Whether the detector is responding and healthy
        model_loaded: Whether the model is loaded (from health endpoint)
        latency_ms: Response time of the health check in milliseconds
        error_message: Error message if unhealthy
    """

    detector_type: str
    healthy: bool
    model_loaded: bool = False
    latency_ms: float | None = None
    error_message: str | None = None


@dataclass
class DetectorInfo:
    """Information about a registered detector for API responses.

    Attributes:
        detector_type: Unique identifier
        display_name: Human-readable name
        url: Service URL
        enabled: Whether available for use
        is_active: Whether this is the currently active detector
        model_version: Optional model version
        description: Detector description
    """

    detector_type: str
    display_name: str
    url: str
    enabled: bool
    is_active: bool
    model_version: str | None = None
    description: str = ""


class DetectorRegistry:
    """Registry for managing object detectors.

    This class implements a singleton pattern to maintain consistent
    state across the application. Use get_detector_registry() to get
    the singleton instance.

    Thread-safety note: This implementation is designed for async usage.
    The registry operations are not thread-safe but are safe for concurrent
    async operations within a single event loop.
    """

    _instance: DetectorRegistry | None = None

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._detectors: dict[str, DetectorConfig] = {}
        self._active_detector: str | None = None

    @property
    def available_detectors(self) -> list[str]:
        """Get list of registered detector type identifiers."""
        return list(self._detectors.keys())

    @property
    def active_detector(self) -> str | None:
        """Get the currently active detector type."""
        return self._active_detector

    def register(self, config: DetectorConfig) -> None:
        """Register a detector configuration.

        Args:
            config: Detector configuration to register

        Note:
            If a detector with the same type is already registered,
            it will be overwritten.
        """
        self._detectors[config.detector_type] = config
        logger.info(
            f"Registered detector: {config.detector_type}",
            extra={
                "detector_type": config.detector_type,
                "display_name": config.display_name,
                "enabled": config.enabled,
            },
        )

    def unregister(self, detector_type: str) -> None:
        """Remove a detector from the registry.

        Args:
            detector_type: Type identifier of detector to remove

        Raises:
            ValueError: If detector_type is currently active
        """
        if self._active_detector == detector_type:
            raise ValueError(f"Cannot unregister active detector: {detector_type}")

        if detector_type in self._detectors:
            del self._detectors[detector_type]
            logger.info(f"Unregistered detector: {detector_type}")

    def get_config(self, detector_type: str) -> DetectorConfig:
        """Get configuration for a specific detector.

        Args:
            detector_type: Type identifier of the detector

        Returns:
            DetectorConfig for the requested detector

        Raises:
            ValueError: If detector_type is not registered
        """
        if detector_type not in self._detectors:
            raise ValueError(f"Unknown detector type: {detector_type}")
        return self._detectors[detector_type]

    def set_active(self, detector_type: str) -> None:
        """Set the active detector.

        This is a synchronous operation that only updates the registry state.
        Use switch_detector() for production use which includes health validation.

        Args:
            detector_type: Type identifier of detector to make active

        Raises:
            ValueError: If detector_type is unknown or not enabled
        """
        if detector_type not in self._detectors:
            raise ValueError(f"Unknown detector type: {detector_type}")

        config = self._detectors[detector_type]
        if not config.enabled:
            raise ValueError(f"Detector {detector_type} is not enabled")

        self._active_detector = detector_type
        logger.info(
            f"Set active detector: {detector_type}",
            extra={"detector_type": detector_type},
        )

    def get_active_config(self) -> DetectorConfig:
        """Get the configuration of the active detector.

        Returns:
            DetectorConfig for the active detector

        Raises:
            ValueError: If no detector is currently active
        """
        if self._active_detector is None:
            raise ValueError("No active detector configured")
        return self._detectors[self._active_detector]

    def list_detectors(self) -> list[DetectorInfo]:
        """List all registered detectors with their status.

        Returns:
            List of DetectorInfo objects for all registered detectors
        """
        result = []
        for detector_type, config in self._detectors.items():
            result.append(
                DetectorInfo(
                    detector_type=config.detector_type,
                    display_name=config.display_name,
                    url=config.url,
                    enabled=config.enabled,
                    is_active=(detector_type == self._active_detector),
                    model_version=config.model_version,
                    description=config.description,
                )
            )
        return result

    async def check_health(self, detector_type: str) -> DetectorStatus:
        """Check health of a specific detector.

        Args:
            detector_type: Type identifier of the detector

        Returns:
            DetectorStatus with health information

        Raises:
            ValueError: If detector_type is not registered
        """
        if detector_type not in self._detectors:
            raise ValueError(f"Unknown detector type: {detector_type}")

        config = self._detectors[detector_type]
        health_url = f"{config.url}/health"

        import time

        start_time = time.monotonic()

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(health_url)

            latency_ms = (time.monotonic() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                return DetectorStatus(
                    detector_type=detector_type,
                    healthy=True,
                    model_loaded=data.get("model_loaded", False),
                    latency_ms=latency_ms,
                )
            else:
                return DetectorStatus(
                    detector_type=detector_type,
                    healthy=False,
                    latency_ms=latency_ms,
                    error_message=f"HTTP {response.status_code}",
                )

        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            logger.warning(
                f"Health check failed for detector {detector_type}: {e}",
                extra={"detector_type": detector_type, "error": str(e)},
            )
            return DetectorStatus(
                detector_type=detector_type,
                healthy=False,
                latency_ms=latency_ms,
                error_message=str(e),
            )

    async def check_all_health(self) -> list[DetectorStatus]:
        """Check health of all registered detectors.

        Returns:
            List of DetectorStatus for all registered detectors
        """
        import asyncio

        tasks = [self.check_health(dt) for dt in self._detectors]
        return await asyncio.gather(*tasks)

    async def switch_detector(self, detector_type: str, *, force: bool = False) -> DetectorStatus:
        """Switch to a different active detector.

        This method validates that the target detector is healthy before
        switching, unless force=True is specified.

        Args:
            detector_type: Type identifier of detector to switch to
            force: If True, skip health check validation

        Returns:
            DetectorStatus of the new active detector

        Raises:
            ValueError: If detector_type is unknown, not enabled, or not healthy
        """
        if detector_type not in self._detectors:
            raise ValueError(f"Unknown detector type: {detector_type}")

        config = self._detectors[detector_type]
        if not config.enabled:
            raise ValueError(f"Detector {detector_type} is not enabled")

        if not force:
            status = await self.check_health(detector_type)
            if not status.healthy:
                raise ValueError(f"Detector {detector_type} is not healthy: {status.error_message}")
        else:
            # Create a placeholder status when skipping health check
            status = DetectorStatus(
                detector_type=detector_type,
                healthy=True,  # Assumed healthy when force=True
                model_loaded=True,
            )

        # Update the active detector
        old_active = self._active_detector
        self._active_detector = detector_type

        logger.info(
            f"Switched detector from {old_active} to {detector_type}",
            extra={
                "old_detector": old_active,
                "new_detector": detector_type,
                "forced": force,
            },
        )

        return status


def _initialize_default_detectors(registry: DetectorRegistry) -> None:
    """Initialize the registry with default detector configurations.

    Reads configuration from settings and registers detectors accordingly.
    """
    settings = get_settings()

    # Register YOLO26 (primary detector)
    yolo26_config = DetectorConfig(
        detector_type="yolo26",
        display_name="YOLO26",
        url=settings.yolo26_url,
        enabled=True,
        model_version="yolo26m",
        description="YOLO26 TensorRT object detection model for real-time security monitoring",
    )
    registry.register(yolo26_config)

    # Register YOLOv8 (alternative detector - disabled by default until configured)
    # This can be enabled when a YOLOv8 service is deployed
    yolov8_url = getattr(settings, "yolov8_url", None)
    if yolov8_url:
        yolov8_config = DetectorConfig(
            detector_type="yolov8",
            display_name="YOLOv8",
            url=yolov8_url,
            enabled=True,
            model_version="yolov8n",
            description="YOLOv8 nano model for efficient object detection",
        )
        registry.register(yolov8_config)

    # Set YOLO26 as the default active detector
    registry.set_active("yolo26")

    logger.info(
        "Detector registry initialized",
        extra={
            "registered_detectors": registry.available_detectors,
            "active_detector": registry.active_detector,
        },
    )


def get_detector_registry() -> DetectorRegistry:
    """Get the singleton detector registry instance.

    Creates and initializes the registry on first call with default
    detector configurations from settings.

    Returns:
        The DetectorRegistry singleton instance
    """
    if DetectorRegistry._instance is None:
        DetectorRegistry._instance = DetectorRegistry()
        _initialize_default_detectors(DetectorRegistry._instance)

    return DetectorRegistry._instance


def reset_detector_registry() -> None:
    """Reset the detector registry singleton.

    This is primarily for testing purposes to ensure a fresh registry
    state between tests.
    """
    DetectorRegistry._instance = None
