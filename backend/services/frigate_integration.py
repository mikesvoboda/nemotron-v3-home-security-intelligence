"""Frigate NVR Integration Service.

This service integrates with Frigate NVR via MQTT, receiving detection events
and mapping them to HSI's detection and event models.

Features:
- Subscribe to Frigate MQTT events (0.13+ format)
- Map Frigate detections to HSI Detection model
- Unified timeline with Frigate events
- Camera mapping (Frigate camera ID -> HSI camera ID)

MQTT Topics (Frigate 0.13+):
    frigate/{camera}/events - Event lifecycle (new, update, end)
    frigate/{camera}/detections - Object detections

Related Issues:
    - NEM-5159: [Implement] Phase 9: Frigate Integration
    - NEM-5032: Epic 3: Ecosystem Integration
"""

from __future__ import annotations

__all__ = [
    "FrigateDetection",
    "FrigateEvent",
    "FrigateIntegrationService",
    "FrigateSettings",
]

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.services.mqtt_client import MQTTClient

logger = get_logger(__name__)


# =============================================================================
# Settings
# =============================================================================


class FrigateSettings(BaseSettings):
    """Frigate integration configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="FRIGATE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        description="Enable Frigate integration.",
    )
    mqtt_topic_prefix: str = Field(
        default="frigate",
        description="Frigate MQTT topic prefix.",
    )
    camera_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="Map Frigate camera IDs to HSI camera IDs.",
    )
    api_url: str | None = Field(
        default=None,
        description="Frigate API URL for snapshots (e.g., http://frigate:5000).",
    )
    import_snapshots: bool = Field(
        default=True,
        description="Import snapshot images from Frigate.",
    )
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for importing detections.",
    )


# =============================================================================
# Schemas
# =============================================================================


class FrigateDetection(BaseModel):
    """Frigate detection payload (0.13+ format)."""

    id: str = Field(description="Detection ID")
    camera: str = Field(description="Frigate camera name")
    frame_time: float = Field(description="Unix timestamp of frame")
    label: str = Field(description="Object label (person, car, etc.)")
    score: float = Field(description="Detection confidence 0-1")
    box: list[float] = Field(description="Bounding box [y1, x1, y2, x2] normalized")
    area: float = Field(description="Detection area in pixels")
    region: list[float] = Field(description="Region box")
    current_zones: list[str] = Field(default_factory=list, description="Zones containing object")
    entered_zones: list[str] = Field(default_factory=list, description="Zones object has entered")
    has_clip: bool = Field(default=False, description="Clip available")
    has_snapshot: bool = Field(default=False, description="Snapshot available")
    stationary: bool = Field(default=False, description="Object is stationary")
    motionless_count: int = Field(default=0, description="Frames object has been motionless")
    position_changes: int = Field(default=0, description="Number of position changes")


class FrigateEvent(BaseModel):
    """Frigate event payload (0.13+ format)."""

    type: str = Field(description="Event type: new, update, end")
    before: FrigateDetection | None = Field(default=None, description="Previous state")
    after: FrigateDetection = Field(description="Current state")


# =============================================================================
# Integration Service
# =============================================================================


class FrigateIntegrationService:
    """Integrates Frigate NVR events with HSI.

    This service subscribes to Frigate MQTT topics and creates
    HSI Detection records from Frigate events.

    Example:
        settings = FrigateSettings(enabled=True)
        frigate = FrigateIntegrationService(mqtt_client=client, settings=settings)
        await frigate.start()
    """

    def __init__(
        self,
        mqtt_client: MQTTClient,
        settings: FrigateSettings | None = None,
    ) -> None:
        """Initialize Frigate integration.

        Args:
            mqtt_client: MQTT client for subscriptions.
            settings: Integration configuration.
        """
        self._client = mqtt_client
        self._settings = settings or FrigateSettings()
        self._running = False
        self._processed_events: set[str] = set()

        logger.info(
            "FrigateIntegrationService initialized",
            extra={
                "enabled": self._settings.enabled,
                "camera_mapping": self._settings.camera_mapping,
            },
        )

    async def start(self) -> None:
        """Start Frigate integration and subscribe to topics."""
        if not self._settings.enabled:
            logger.info("Frigate integration disabled")
            return

        if self._running:
            logger.warning("Frigate integration already running")
            return

        prefix = self._settings.mqtt_topic_prefix

        # Subscribe to Frigate event topics
        await self._client.subscribe(f"{prefix}/+/events", self._on_event)

        self._running = True
        logger.info("Frigate integration started")

    async def stop(self) -> None:
        """Stop Frigate integration."""
        if not self._running:
            return

        prefix = self._settings.mqtt_topic_prefix
        await self._client.unsubscribe(f"{prefix}/+/events")

        self._running = False
        logger.info("Frigate integration stopped")

    def _map_camera_id(self, frigate_camera: str) -> str:
        """Map Frigate camera ID to HSI camera ID.

        Args:
            frigate_camera: Frigate camera identifier.

        Returns:
            HSI camera ID (uses Frigate ID if no mapping exists).
        """
        return self._settings.camera_mapping.get(frigate_camera, frigate_camera)

    def _map_object_type(self, frigate_label: str) -> str:
        """Map Frigate label to HSI object type.

        Args:
            frigate_label: Frigate object label.

        Returns:
            HSI object type.
        """
        # Frigate labels map directly for most common types
        label_map = {
            "person": "person",
            "car": "vehicle",
            "truck": "vehicle",
            "motorcycle": "vehicle",
            "bicycle": "bicycle",
            "dog": "animal",
            "cat": "animal",
            "bird": "animal",
        }
        return label_map.get(frigate_label, frigate_label)

    def _convert_bbox(
        self,
        box: list[float],
        image_width: int = 1920,
        image_height: int = 1080,
    ) -> dict[str, int]:
        """Convert Frigate normalized bbox to pixel coordinates.

        Frigate uses [y1, x1, y2, x2] normalized (0-1).
        HSI uses x, y, width, height in pixels.

        Args:
            box: Frigate bbox [y1, x1, y2, x2].
            image_width: Frame width in pixels.
            image_height: Frame height in pixels.

        Returns:
            Dict with x, y, width, height in pixels.
        """
        y1, x1, y2, x2 = box
        return {
            "bbox_x": int(x1 * image_width),
            "bbox_y": int(y1 * image_height),
            "bbox_width": int((x2 - x1) * image_width),
            "bbox_height": int((y2 - y1) * image_height),
        }

    async def _on_event(self, _topic: str, payload: dict[str, Any]) -> None:
        """Handle Frigate event message.

        Args:
            _topic: MQTT topic (frigate/{camera}/events).
            payload: Event payload.
        """
        try:
            event = FrigateEvent.model_validate(payload)

            # Only process new and end events
            if event.type not in ("new", "end"):
                return

            detection = event.after

            # Check confidence threshold
            if detection.score < self._settings.min_confidence:
                logger.debug(
                    f"Frigate detection below threshold: {detection.score}",
                    extra={"threshold": self._settings.min_confidence},
                )
                return

            # Skip duplicates
            event_key = f"{detection.id}_{event.type}"
            if event_key in self._processed_events:
                return
            self._processed_events.add(event_key)

            # Map to HSI
            hsi_camera_id = self._map_camera_id(detection.camera)
            hsi_object_type = self._map_object_type(detection.label)
            bbox = self._convert_bbox(detection.box)

            # Log the detection
            logger.info(
                "Frigate detection received",
                extra={
                    "frigate_id": detection.id,
                    "frigate_camera": detection.camera,
                    "hsi_camera_id": hsi_camera_id,
                    "label": detection.label,
                    "object_type": hsi_object_type,
                    "confidence": detection.score,
                    "zones": detection.current_zones,
                    "event_type": event.type,
                    "bbox": bbox,
                },
            )

            # TODO: NEM-5159 - Create Detection record in database

            # Evict old processed events
            if len(self._processed_events) > 10000:
                self._processed_events = set(list(self._processed_events)[5000:])

        except Exception as e:
            logger.error(f"Failed to process Frigate event: {e}", exc_info=True)

    async def get_snapshot_url(self, event_id: str) -> str | None:
        """Get snapshot URL for a Frigate event.

        Args:
            event_id: Frigate event ID.

        Returns:
            Snapshot URL or None if unavailable.
        """
        if not self._settings.api_url:
            return None

        return f"{self._settings.api_url}/api/events/{event_id}/snapshot.jpg"

    async def get_clip_url(self, event_id: str) -> str | None:
        """Get clip URL for a Frigate event.

        Args:
            event_id: Frigate event ID.

        Returns:
            Clip URL or None if unavailable.
        """
        if not self._settings.api_url:
            return None

        return f"{self._settings.api_url}/api/events/{event_id}/clip.mp4"
