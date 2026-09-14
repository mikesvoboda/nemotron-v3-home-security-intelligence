"""Home Assistant MQTT Discovery Service.

This service publishes MQTT Discovery payloads for Home Assistant to auto-configure
HSI devices and entities. Supports binary sensors, sensors, and device triggers.

Features:
- Auto-configure cameras, alerts, and events in Home Assistant
- Device grouping with manufacturer/model metadata
- Selective device_class mapping for proper icons
- Retained discovery messages for persistence

Discovery Topics:
    homeassistant/{component}/hsi_{id}/config

Related Issues:
    - NEM-5146: [Implement] Phase 4: HA MQTT Discovery + Entity Types
    - NEM-5032: Epic 3: Ecosystem Integration
"""

from __future__ import annotations

__all__ = [
    "ComponentType",
    "DeviceClass",
    "HADeviceInfo",
    "HADiscoveryManager",
    "HADiscoveryPayload",
    "HADiscoverySettings",
]

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.services.mqtt_client import MQTTClient

logger = get_logger(__name__)


# =============================================================================
# Enums
# =============================================================================


class ComponentType(StrEnum):
    """Home Assistant MQTT component types."""

    BINARY_SENSOR = "binary_sensor"
    SENSOR = "sensor"
    BUTTON = "button"
    SWITCH = "switch"
    DEVICE_TRIGGER = "device_trigger"


class DeviceClass(StrEnum):
    """Home Assistant device classes for sensors."""

    # Binary sensor device classes
    MOTION = "motion"
    OCCUPANCY = "occupancy"
    DOOR = "door"
    WINDOW = "window"
    TAMPER = "tamper"
    CONNECTIVITY = "connectivity"
    PROBLEM = "problem"
    PRESENCE = "presence"
    SMOKE = "smoke"
    SAFETY = "safety"

    # Sensor device classes
    TIMESTAMP = "timestamp"


# =============================================================================
# Settings
# =============================================================================


class HADiscoverySettings(BaseSettings):
    """Home Assistant Discovery configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="HA_DISCOVERY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        description="Enable HA MQTT Discovery publishing.",
    )
    discovery_prefix: str = Field(
        default="homeassistant",
        description="Discovery topic prefix (homeassistant by default).",
    )
    publish_cameras: bool = Field(
        default=True,
        description="Publish discovery for camera entities.",
    )
    publish_alerts: bool = Field(
        default=True,
        description="Publish discovery for alert entities.",
    )
    publish_events: bool = Field(
        default=True,
        description="Publish discovery for event risk scores.",
    )
    device_name_prefix: str = Field(
        default="HSI",
        description="Prefix for device names in Home Assistant.",
    )


# =============================================================================
# Schemas
# =============================================================================


class HADeviceInfo(BaseModel):
    """Device information for Home Assistant grouping."""

    identifiers: list[str] = Field(
        description="Unique identifiers for the device.",
    )
    name: str = Field(
        description="Human-readable device name.",
    )
    manufacturer: str = Field(
        default="HSI",
        description="Device manufacturer.",
    )
    model: str = Field(
        description="Device model.",
    )
    sw_version: str | None = Field(
        default=None,
        description="Software version.",
    )
    hw_version: str | None = Field(
        default=None,
        description="Hardware version.",
    )
    via_device: str | None = Field(
        default="hsi_hub",
        description="Parent device identifier.",
    )


class HADiscoveryPayload(BaseModel):
    """Complete MQTT Discovery payload for Home Assistant."""

    component: ComponentType = Field(
        description="HA component type.",
    )
    object_id: str = Field(
        description="Unique object identifier.",
    )
    unique_id: str = Field(
        description="Globally unique entity identifier.",
    )
    name: str | None = Field(
        default=None,
        description="Human-readable entity name.",
    )
    state_topic: str = Field(
        description="MQTT topic for state updates.",
    )
    command_topic: str | None = Field(
        default=None,
        description="MQTT topic for commands.",
    )
    device_class: DeviceClass | None = Field(
        default=None,
        description="Device class for icon/behavior.",
    )
    unit_of_measurement: str | None = Field(
        default=None,
        description="Unit for sensor values.",
    )
    value_template: str | None = Field(
        default=None,
        description="Jinja2 template for value extraction.",
    )
    icon: str | None = Field(
        default=None,
        description="MDI icon (e.g., mdi:alert-circle).",
    )
    payload_on: str = Field(
        default="ON",
        description="Payload meaning 'on' for binary sensors.",
    )
    payload_off: str = Field(
        default="OFF",
        description="Payload meaning 'off' for binary sensors.",
    )
    availability_topic: str | None = Field(
        default=None,
        description="Topic for availability status.",
    )
    payload_available: str = Field(
        default="online",
        description="Payload meaning 'available'.",
    )
    payload_not_available: str = Field(
        default="offline",
        description="Payload meaning 'unavailable'.",
    )
    qos: int = Field(
        default=1,
        ge=0,
        le=2,
        description="MQTT QoS level.",
    )
    retain: bool = Field(
        default=True,
        description="Retain discovery message.",
    )
    device: HADeviceInfo = Field(
        description="Device information for grouping.",
    )

    def to_discovery_dict(self) -> dict[str, Any]:
        """Convert to dictionary for MQTT publishing.

        Returns dict with snake_case keys matching HA MQTT Discovery schema.
        """
        data: dict[str, Any] = {
            "unique_id": self.unique_id,
            "object_id": self.object_id,
            "state_topic": self.state_topic,
            "qos": self.qos,
            "device": {
                "identifiers": self.device.identifiers,
                "name": self.device.name,
                "manufacturer": self.device.manufacturer,
                "model": self.device.model,
            },
        }

        # Add optional fields
        if self.name:
            data["name"] = self.name
        if self.command_topic:
            data["command_topic"] = self.command_topic
        if self.device_class:
            data["device_class"] = self.device_class.value
        if self.unit_of_measurement:
            data["unit_of_measurement"] = self.unit_of_measurement
        if self.value_template:
            data["value_template"] = self.value_template
        if self.icon:
            data["icon"] = self.icon
        if self.availability_topic:
            data["availability_topic"] = self.availability_topic
            data["payload_available"] = self.payload_available
            data["payload_not_available"] = self.payload_not_available

        # Binary sensor specific
        if self.component == ComponentType.BINARY_SENSOR:
            data["payload_on"] = self.payload_on
            data["payload_off"] = self.payload_off

        # Device optional fields
        if self.device.sw_version:
            data["device"]["sw_version"] = self.device.sw_version
        if self.device.hw_version:
            data["device"]["hw_version"] = self.device.hw_version
        if self.device.via_device:
            data["device"]["via_device"] = self.device.via_device

        return data


# =============================================================================
# Discovery Manager
# =============================================================================


class HADiscoveryManager:
    """Manages Home Assistant MQTT Discovery for HSI entities.

    This service publishes discovery payloads to configure HSI cameras,
    alerts, and events as Home Assistant entities.

    Example:
        settings = HADiscoverySettings(enabled=True)
        manager = HADiscoveryManager(mqtt_client=client, settings=settings)
        await manager.publish_camera_discovery(camera)
    """

    def __init__(
        self,
        mqtt_client: MQTTClient,
        settings: HADiscoverySettings | None = None,
    ) -> None:
        """Initialize HA Discovery manager.

        Args:
            mqtt_client: MQTT client for publishing.
            settings: Discovery configuration.
        """
        self._client = mqtt_client
        self._settings = settings or HADiscoverySettings()
        self._published_entities: set[str] = set()

        logger.info(
            "HADiscoveryManager initialized",
            extra={
                "enabled": self._settings.enabled,
                "discovery_prefix": self._settings.discovery_prefix,
            },
        )

    async def publish_camera_discovery(
        self,
        camera_id: str,
        camera_name: str,
    ) -> None:
        """Publish discovery payloads for a camera.

        Creates:
        - Binary sensor for camera connectivity (online/offline)
        - Sensor for detection count
        - Sensor for last detection time

        Args:
            camera_id: Camera identifier.
            camera_name: Human-readable camera name.
        """
        if not self._settings.enabled or not self._settings.publish_cameras:
            return

        device = HADeviceInfo(
            identifiers=[f"hsi_{camera_id}"],
            name=f"{self._settings.device_name_prefix} {camera_name}",
            model="Security Camera",
        )

        # Connectivity binary sensor
        connectivity = HADiscoveryPayload(
            component=ComponentType.BINARY_SENSOR,
            object_id=f"hsi_{camera_id}_connectivity",
            unique_id=f"hsi_{camera_id}_connectivity",
            name=f"{camera_name} Status",
            state_topic=f"hsi/health/cameras/{camera_id}",
            device_class=DeviceClass.CONNECTIVITY,
            payload_on="online",
            payload_off="offline",
            value_template="{{ value_json.status }}",
            device=device,
        )
        await self._publish_discovery(connectivity)

        # Motion binary sensor
        motion = HADiscoveryPayload(
            component=ComponentType.BINARY_SENSOR,
            object_id=f"hsi_{camera_id}_motion",
            unique_id=f"hsi_{camera_id}_motion",
            name=f"{camera_name} Motion",
            state_topic=f"hsi/detections/{camera_id}/person",
            device_class=DeviceClass.MOTION,
            payload_on="detected",
            payload_off="clear",
            value_template="{{ value_json.status | default('clear') }}",
            device=device,
        )
        await self._publish_discovery(motion)

        # Risk score sensor
        risk_score = HADiscoveryPayload(
            component=ComponentType.SENSOR,
            object_id=f"hsi_{camera_id}_risk_score",
            unique_id=f"hsi_{camera_id}_risk_score",
            name=f"{camera_name} Risk Score",
            state_topic=f"hsi/events/{camera_id}",
            unit_of_measurement="%",
            icon="mdi:alert-circle",
            value_template="{{ value_json.risk_score | default(0) }}",
            device=device,
        )
        await self._publish_discovery(risk_score)

        logger.info(f"Published HA discovery for camera: {camera_id}")

    async def publish_alert_discovery(self, severity: str = "high") -> None:
        """Publish discovery for alert system.

        Creates a binary sensor for active alerts.

        Args:
            severity: Alert severity level.
        """
        if not self._settings.enabled or not self._settings.publish_alerts:
            return

        device = HADeviceInfo(
            identifiers=["hsi_alerts"],
            name=f"{self._settings.device_name_prefix} Alert System",
            model="Alert Engine",
        )

        # Alert active binary sensor
        alert = HADiscoveryPayload(
            component=ComponentType.BINARY_SENSOR,
            object_id=f"hsi_alert_{severity}_active",
            unique_id=f"hsi_alert_{severity}_active",
            name=f"{severity.title()} Severity Alert",
            state_topic=f"hsi/alerts/{severity}",
            device_class=DeviceClass.SAFETY,
            payload_on="active",
            payload_off="resolved",
            value_template="{{ value_json.status | default('resolved') }}",
            device=device,
        )
        await self._publish_discovery(alert)

        logger.info(f"Published HA discovery for {severity} alerts")

    async def publish_system_discovery(self) -> None:
        """Publish discovery for system health.

        Creates sensors for overall system health status.
        """
        if not self._settings.enabled:
            return

        device = HADeviceInfo(
            identifiers=["hsi_hub"],
            name=f"{self._settings.device_name_prefix} Hub",
            model="Home Security Intelligence",
        )

        # System health sensor
        health = HADiscoveryPayload(
            component=ComponentType.SENSOR,
            object_id="hsi_system_health",
            unique_id="hsi_system_health",
            name="System Health",
            state_topic="hsi/health/system",
            icon="mdi:heart-pulse",
            value_template="{{ value_json.health | default('unknown') }}",
            device=device,
        )
        await self._publish_discovery(health)

        logger.info("Published HA discovery for system health")

    async def unpublish_entity(self, component: ComponentType, object_id: str) -> None:
        """Remove entity from Home Assistant by publishing empty payload.

        Args:
            component: Component type.
            object_id: Entity object ID.
        """
        if not self._settings.enabled:
            return

        topic = f"{self._settings.discovery_prefix}/{component.value}/{object_id}/config"
        await self._client.publish(topic, {}, qos=1, retain=True)

        self._published_entities.discard(object_id)
        logger.info(f"Unpublished HA entity: {object_id}")

    async def _publish_discovery(self, payload: HADiscoveryPayload) -> None:
        """Publish discovery payload to MQTT.

        Args:
            payload: Discovery payload to publish.
        """
        topic = (
            f"{self._settings.discovery_prefix}/"
            f"{payload.component.value}/"
            f"{payload.object_id}/config"
        )

        await self._client.publish(
            topic=topic,
            payload=payload.to_discovery_dict(),
            qos=payload.qos,
            retain=payload.retain,
        )

        self._published_entities.add(payload.object_id)

        logger.debug(
            f"Published HA discovery: {payload.object_id}",
            extra={"topic": topic, "component": payload.component.value},
        )
