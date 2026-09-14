"""MQTT Publisher Service for broadcasting security events to MQTT topics.

This service publishes security events, alerts, detections, and health status
to MQTT topics for Home Assistant and other MQTT-compatible systems.

Features:
- Event type to MQTT topic mapping
- Configurable QoS per event category (status vs regular events)
- Retain flag support for status topics
- Integration with EventBroadcaster via callback registration
- Prometheus metrics for monitoring

Topic Structure:
    - hsi/alerts/{severity} - Alert events
    - hsi/detections/{camera_id}/{object_type} - Detection events
    - hsi/zones/{zone_id}/crossing - Zone crossing events
    - hsi/zones/{zone_id}/dwell - Zone dwell events
    - hsi/entities/{entity_type} - Entity tracking events
    - hsi/health/cameras/{camera_id} - Camera health (retained)
    - hsi/health/system - System health (retained)
    - hsi/ai/threats/{camera_id} - AI threat detection
    - hsi/ai/actions/{camera_id} - AI action recognition
    - hsi/events/{camera_id} - Generic events (fallback)

Related Issues:
    - NEM-5135: [Implement] Phase 1: MQTT Event Publishing
    - NEM-5032: Epic 3: Ecosystem Integration
"""

from __future__ import annotations

__all__ = [
    "MQTTPublisher",
    "MQTTPublisherSettings",
    "TopicMapping",
    "get_topic_for_event",
]

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.services.mqtt_client import MQTTClient

logger = get_logger(__name__)


# =============================================================================
# Settings
# =============================================================================


class MQTTPublisherSettings(BaseSettings):
    """MQTT publisher configuration settings.

    Environment variables use the MQTT_PUBLISHER_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="MQTT_PUBLISHER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=True,
        description="Enable/disable MQTT publishing globally.",
    )
    events_qos: int = Field(
        default=1,
        ge=0,
        le=2,
        description="QoS level for regular events (alerts, detections, zones).",
    )
    status_qos: int = Field(
        default=0,
        ge=0,
        le=2,
        description="QoS level for status events (camera health, system health).",
    )
    retain_status: bool = Field(
        default=True,
        description="Retain status messages on broker for new subscribers.",
    )
    retain_events: bool = Field(
        default=False,
        description="Retain regular event messages (typically False).",
    )

    @field_validator("events_qos", "status_qos")
    @classmethod
    def validate_qos(cls, v: int) -> int:
        """Validate QoS is in valid range 0-2."""
        if not 0 <= v <= 2:
            raise ValueError(f"QoS must be 0, 1, or 2, got {v}")
        return v


# =============================================================================
# Topic Mapping
# =============================================================================

# Event types that are considered status events (use status QoS and retain)
STATUS_EVENT_TYPES = frozenset(
    {
        "camera.online",
        "camera.offline",
        "camera.error",
        "camera.status_changed",
        "system.health_changed",
        "system.status",
        "system.error",
        "service.status_changed",
        "worker.started",
        "worker.stopped",
        "worker.health_check_failed",
        "worker.recovered",
    }
)


class TopicMapping:
    """Maps event types to MQTT topics."""

    @staticmethod
    def get_topic(event_type: str, data: dict[str, Any]) -> str:
        """Get MQTT topic for an event type and data.

        Args:
            event_type: The event type string (e.g., "alert.created").
            data: The event data dictionary.

        Returns:
            The MQTT topic path (without prefix).
        """
        # Extract common fields with defaults
        camera_id = data.get("camera_id") or data.get("data", {}).get("camera_id") or "unknown"
        zone_id = data.get("zone_id") or data.get("data", {}).get("zone_id") or "unknown"
        severity = data.get("severity") or data.get("data", {}).get("severity") or "unknown"
        object_type = (
            data.get("object_type") or data.get("data", {}).get("object_type") or "unknown"
        )
        entity_type = (
            data.get("entity_type") or data.get("data", {}).get("entity_type") or "unknown"
        )

        # Use a mapping table for cleaner dispatch
        topic_handlers: dict[str, str] = {
            "detection.new": f"detections/{camera_id}/{object_type}",
            "detection.batch": f"detections/{camera_id}/batch",
            "zone.crossing": f"zones/{zone_id}/crossing",
            "zone.dwell_started": f"zones/{zone_id}/dwell",
            "zone.dwell_alert": f"zones/{zone_id}/dwell",
            "zone.approach": f"zones/{zone_id}/approach",
            "ai.threat_detected": f"ai/threats/{camera_id}",
            "ai.action_recognized": f"ai/actions/{camera_id}",
        }

        # Check exact match first
        if event_type in topic_handlers:
            return topic_handlers[event_type]

        # Check prefix-based routing
        prefix_handlers: dict[str, str] = {
            "alert.": f"alerts/{severity}",
            "camera.": f"health/cameras/{camera_id}",
            "entity.": f"entities/{entity_type}",
            "system.": "health/system",
            "service.": "health/system",
            "worker.": "health/system",
            "event.": f"events/{camera_id}",
        }

        for prefix, topic in prefix_handlers.items():
            if event_type.startswith(prefix):
                return topic

        # Unknown event types use generic events topic
        return f"events/{camera_id}"


def get_topic_for_event(event_type: str, data: dict[str, Any]) -> str:
    """Get MQTT topic for an event.

    This is a convenience function that delegates to TopicMapping.

    Args:
        event_type: The event type string.
        data: The event data dictionary.

    Returns:
        The MQTT topic path (without prefix).
    """
    return TopicMapping.get_topic(event_type, data)


# =============================================================================
# MQTT Publisher
# =============================================================================


class MQTTPublisher:
    """Publishes security events to MQTT topics.

    This service integrates with the existing MQTT client to publish events
    from the EventBroadcaster to MQTT topics for Home Assistant and other
    MQTT-compatible systems.

    Example:
        settings = MQTTPublisherSettings()
        publisher = MQTTPublisher(mqtt_client=client, settings=settings)

        # Publish an event
        await publisher.publish_event("alert.created", event_data)

        # Or register with EventBroadcaster
        broadcaster.register_mqtt_callback(publisher.get_broadcast_callback())
    """

    def __init__(
        self,
        mqtt_client: MQTTClient,
        settings: MQTTPublisherSettings | None = None,
    ) -> None:
        """Initialize MQTT publisher.

        Args:
            mqtt_client: The MQTT client instance for publishing.
            settings: Publisher configuration settings.
        """
        self._client = mqtt_client
        self._settings = settings or MQTTPublisherSettings()

        logger.info(
            "MQTTPublisher initialized",
            extra={
                "enabled": self._settings.enabled,
                "events_qos": self._settings.events_qos,
                "status_qos": self._settings.status_qos,
                "retain_status": self._settings.retain_status,
            },
        )

    @property
    def enabled(self) -> bool:
        """Return whether publishing is enabled."""
        return self._settings.enabled

    def is_status_event(self, event_type: str) -> bool:
        """Check if event type is a status event.

        Status events use different QoS and retain settings.

        Args:
            event_type: The event type string.

        Returns:
            True if this is a status event.
        """
        return event_type in STATUS_EVENT_TYPES

    async def publish_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        """Publish an event to the appropriate MQTT topic.

        Args:
            event_type: The event type string (e.g., "alert.created").
            event_data: The full event data to publish.
        """
        # Skip if disabled
        if not self._settings.enabled:
            logger.debug(
                "MQTT publishing disabled, skipping event", extra={"event_type": event_type}
            )
            return

        # Skip if not connected
        if not self._client.connected:
            logger.debug(
                "MQTT client not connected, skipping event", extra={"event_type": event_type}
            )
            return

        # Determine topic
        topic = get_topic_for_event(event_type, event_data)

        # Determine QoS and retain based on event type
        is_status = self.is_status_event(event_type)
        qos = self._settings.status_qos if is_status else self._settings.events_qos
        retain = self._settings.retain_status if is_status else self._settings.retain_events

        # Ensure timestamp is present
        payload = dict(event_data)
        if "timestamp" not in payload:
            payload["timestamp"] = datetime.now(UTC).isoformat()

        try:
            await self._client.publish(
                topic=topic,
                payload=payload,
                qos=qos,
                retain=retain,
            )

            self._increment_publish_counter(topic.split("/")[0], success=True)

            logger.debug(
                "Published event to MQTT",
                extra={
                    "event_type": event_type,
                    "topic": topic,
                    "qos": qos,
                    "retain": retain,
                },
            )

        except Exception as e:
            self._increment_publish_counter(topic.split("/")[0], success=False)
            logger.error(
                "Failed to publish event to MQTT",
                extra={
                    "event_type": event_type,
                    "topic": topic,
                    "error": str(e),
                },
            )
            # Don't re-raise - MQTT failures shouldn't block event processing

    def _increment_publish_counter(self, topic_type: str, success: bool) -> None:
        """Increment Prometheus counter for publish operations.

        Args:
            topic_type: The topic category (e.g., "alerts", "detections").
            success: Whether the publish was successful.
        """
        # Metrics integration will be added in a follow-up
        # For now, this is a placeholder for the metrics hook
        pass

    def get_broadcast_callback(
        self,
    ) -> Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]:
        """Get callback function for EventBroadcaster integration.

        Returns:
            An async callback that can be registered with EventBroadcaster.
        """
        return self.publish_event

    def register_with_broadcaster(self, broadcaster: Any) -> None:
        """Register this publisher with an EventBroadcaster.

        Args:
            broadcaster: The EventBroadcaster instance to register with.
        """
        if hasattr(broadcaster, "register_mqtt_callback"):
            broadcaster.register_mqtt_callback(self.get_broadcast_callback())
            logger.info("Registered MQTT publisher with EventBroadcaster")
        else:
            logger.warning("EventBroadcaster does not support MQTT callback registration")
