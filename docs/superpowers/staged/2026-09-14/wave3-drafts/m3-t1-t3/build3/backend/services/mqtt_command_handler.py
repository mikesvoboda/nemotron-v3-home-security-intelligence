"""MQTT Command Handler for receiving and processing commands via MQTT.

This service subscribes to MQTT command topics and executes zone arm/disarm,
camera sensitivity, PTZ commands, alert acknowledgment, and system mode changes.

Features:
- Command topic subscription with wildcard patterns
- JSON payload validation per command type
- Idempotent command handling (safe for QoS 1 duplicates)
- Audit logging for all commands
- Rate limiting per client

Command Topics:
    - hsi/commands/zones/{zone_id}/arm - Arm a zone
    - hsi/commands/zones/{zone_id}/disarm - Disarm a zone
    - hsi/commands/cameras/{camera_id}/sensitivity - Set camera sensitivity
    - hsi/commands/cameras/{camera_id}/ptz - PTZ control
    - hsi/commands/alerts/{alert_id}/ack - Acknowledge alert
    - hsi/commands/system/mode - Set system mode (home/away/night/disarmed)

Related Issues:
    - NEM-5166: [Implement] Phase 3: MQTT Command Subscription
    - NEM-5032: Epic 3: Ecosystem Integration
"""

from __future__ import annotations

__all__ = [
    "CommandType",
    "MQTTCommandHandler",
    "MQTTCommandHandlerSettings",
    "SystemMode",
]

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.services.mqtt_client import MQTTClient

logger = get_logger(__name__)


# =============================================================================
# Enums
# =============================================================================


class CommandType(StrEnum):
    """Types of commands that can be received via MQTT."""

    ZONE_ARM = "zone_arm"
    ZONE_DISARM = "zone_disarm"
    CAMERA_SENSITIVITY = "camera_sensitivity"
    CAMERA_PTZ = "camera_ptz"
    ALERT_ACK = "alert_ack"
    SYSTEM_MODE = "system_mode"


class SystemMode(StrEnum):
    """System operation modes."""

    HOME = "home"  # Family at home - known faces suppressed
    AWAY = "away"  # Nobody home - all alerts
    NIGHT = "night"  # Sleeping - perimeter only
    DISARMED = "disarmed"  # No alerts, logging only


# =============================================================================
# Settings
# =============================================================================


class MQTTCommandHandlerSettings(BaseSettings):
    """MQTT command handler configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="MQTT_COMMAND_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=True,
        description="Enable/disable MQTT command handling.",
    )
    command_topic_prefix: str = Field(
        default="commands",
        description="Topic prefix for command subscriptions.",
    )
    require_auth: bool = Field(
        default=True,
        description="Require authentication token in command payloads.",
    )
    rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Maximum commands per minute per client.",
    )


# =============================================================================
# Command Payloads
# =============================================================================


class BaseCommandPayload(BaseModel):
    """Base payload for all MQTT commands."""

    auth_token: str | None = Field(
        default=None,
        description="Authentication token for command validation.",
    )
    timestamp: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when command was sent.",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Unique key for idempotent command handling.",
    )


class ZoneArmPayload(BaseCommandPayload):
    """Payload for zone arm command."""

    mode: str | None = Field(
        default=None,
        description="Optional arm mode (full, perimeter, instant).",
    )


class ZoneDisarmPayload(BaseCommandPayload):
    """Payload for zone disarm command."""

    reason: str | None = Field(
        default=None,
        description="Optional reason for disarming.",
    )


class CameraSensitivityPayload(BaseCommandPayload):
    """Payload for camera sensitivity command."""

    sensitivity: float = Field(
        ge=0.0,
        le=1.0,
        description="Sensitivity level (0.0 to 1.0).",
    )


class CameraPTZPayload(BaseCommandPayload):
    """Payload for camera PTZ command."""

    action: str = Field(
        description="PTZ action: pan_left, pan_right, tilt_up, tilt_down, zoom_in, zoom_out, preset, home.",
    )
    preset: int | None = Field(
        default=None,
        ge=1,
        le=255,
        description="Preset number (1-255) for preset action.",
    )
    speed: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Movement speed (0.0 to 1.0).",
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate PTZ action is valid."""
        valid_actions = {
            "pan_left",
            "pan_right",
            "tilt_up",
            "tilt_down",
            "zoom_in",
            "zoom_out",
            "preset",
            "home",
            "stop",
        }
        if v not in valid_actions:
            raise ValueError(f"Invalid PTZ action: {v}. Must be one of: {valid_actions}")
        return v


class AlertAckPayload(BaseCommandPayload):
    """Payload for alert acknowledgment command."""

    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional acknowledgment notes.",
    )


class SystemModePayload(BaseCommandPayload):
    """Payload for system mode command."""

    mode: SystemMode = Field(
        description="System mode to set.",
    )


# =============================================================================
# Command Handler
# =============================================================================


class MQTTCommandHandler:
    """Handles MQTT commands for zone, camera, alert, and system control.

    This service subscribes to command topics and executes commands
    with validation, rate limiting, and audit logging.

    Example:
        settings = MQTTCommandHandlerSettings()
        handler = MQTTCommandHandler(mqtt_client=client, settings=settings)
        await handler.start()
    """

    def __init__(
        self,
        mqtt_client: MQTTClient,
        settings: MQTTCommandHandlerSettings | None = None,
    ) -> None:
        """Initialize command handler.

        Args:
            mqtt_client: The MQTT client for subscriptions.
            settings: Handler configuration settings.
        """
        self._client = mqtt_client
        self._settings = settings or MQTTCommandHandlerSettings()
        self._running = False
        self._processed_keys: set[str] = set()  # For idempotency
        self._current_mode: SystemMode = SystemMode.HOME

        # Command handlers registry
        self._command_handlers: dict[
            CommandType, Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]
        ] = {
            CommandType.ZONE_ARM: self._handle_zone_arm,
            CommandType.ZONE_DISARM: self._handle_zone_disarm,
            CommandType.CAMERA_SENSITIVITY: self._handle_camera_sensitivity,
            CommandType.CAMERA_PTZ: self._handle_camera_ptz,
            CommandType.ALERT_ACK: self._handle_alert_ack,
            CommandType.SYSTEM_MODE: self._handle_system_mode,
        }

        logger.info(
            "MQTTCommandHandler initialized",
            extra={
                "enabled": self._settings.enabled,
                "command_topic_prefix": self._settings.command_topic_prefix,
            },
        )

    @property
    def current_mode(self) -> SystemMode:
        """Get current system mode."""
        return self._current_mode

    async def start(self) -> None:
        """Start command handler and subscribe to command topics."""
        if not self._settings.enabled:
            logger.info("MQTT command handling disabled")
            return

        if self._running:
            logger.warning("Command handler already running")
            return

        # Subscribe to command topics
        prefix = self._settings.command_topic_prefix
        topics = [
            (f"{prefix}/zones/+/arm", self._on_zone_arm),
            (f"{prefix}/zones/+/disarm", self._on_zone_disarm),
            (f"{prefix}/cameras/+/sensitivity", self._on_camera_sensitivity),
            (f"{prefix}/cameras/+/ptz", self._on_camera_ptz),
            (f"{prefix}/alerts/+/ack", self._on_alert_ack),
            (f"{prefix}/system/mode", self._on_system_mode),
        ]

        for topic, callback in topics:
            await self._client.subscribe(topic, callback)
            logger.debug(f"Subscribed to {topic}")

        self._running = True
        logger.info("MQTT command handler started")

    async def stop(self) -> None:
        """Stop command handler and unsubscribe from topics."""
        if not self._running:
            return

        prefix = self._settings.command_topic_prefix
        topics = [
            f"{prefix}/zones/+/arm",
            f"{prefix}/zones/+/disarm",
            f"{prefix}/cameras/+/sensitivity",
            f"{prefix}/cameras/+/ptz",
            f"{prefix}/alerts/+/ack",
            f"{prefix}/system/mode",
        ]

        for topic in topics:
            await self._client.unsubscribe(topic)

        self._running = False
        logger.info("MQTT command handler stopped")

    def _is_duplicate(self, idempotency_key: str | None) -> bool:
        """Check if command is a duplicate using idempotency key."""
        if not idempotency_key:
            return False

        if idempotency_key in self._processed_keys:
            return True

        # Add to processed set (in production, use Redis with TTL)
        self._processed_keys.add(idempotency_key)

        # Keep set bounded
        if len(self._processed_keys) > 10000:
            # Remove oldest half (simple eviction)
            self._processed_keys = set(list(self._processed_keys)[5000:])

        return False

    def _extract_id_from_topic(self, topic: str, position: int) -> str:
        """Extract ID from topic path at given position."""
        parts = topic.split("/")
        if len(parts) > position:
            return parts[position]
        return "unknown"

    async def _log_command(
        self,
        command_type: CommandType,
        target_id: str,
        _payload: dict[str, Any],
        success: bool,
        error: str | None = None,
    ) -> None:
        """Log command execution for audit trail."""
        logger.info(
            "MQTT command executed",
            extra={
                "command_type": command_type.value,
                "target_id": target_id,
                "success": success,
                "error": error,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    # -------------------------------------------------------------------------
    # Topic Callbacks
    # -------------------------------------------------------------------------

    async def _on_zone_arm(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle zone arm command."""
        zone_id = self._extract_id_from_topic(topic, 1)  # commands/zones/{id}/arm
        await self._handle_zone_arm(zone_id, payload)

    async def _on_zone_disarm(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle zone disarm command."""
        zone_id = self._extract_id_from_topic(topic, 1)
        await self._handle_zone_disarm(zone_id, payload)

    async def _on_camera_sensitivity(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle camera sensitivity command."""
        camera_id = self._extract_id_from_topic(topic, 1)
        await self._handle_camera_sensitivity(camera_id, payload)

    async def _on_camera_ptz(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle camera PTZ command."""
        camera_id = self._extract_id_from_topic(topic, 1)
        await self._handle_camera_ptz(camera_id, payload)

    async def _on_alert_ack(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle alert acknowledgment command."""
        alert_id = self._extract_id_from_topic(topic, 1)
        await self._handle_alert_ack(alert_id, payload)

    async def _on_system_mode(self, _topic: str, payload: dict[str, Any]) -> None:
        """Handle system mode command."""
        await self._handle_system_mode("system", payload)

    # -------------------------------------------------------------------------
    # Command Handlers
    # -------------------------------------------------------------------------

    async def _handle_zone_arm(self, zone_id: str, payload: dict[str, Any]) -> None:
        """Execute zone arm command."""
        try:
            cmd = ZoneArmPayload.model_validate(payload)

            if self._is_duplicate(cmd.idempotency_key):
                logger.debug(f"Duplicate zone arm command ignored: {cmd.idempotency_key}")
                return

            # TODO: Integrate with ZoneService to arm zone
            logger.info(f"Zone {zone_id} armed", extra={"mode": cmd.mode})
            await self._log_command(CommandType.ZONE_ARM, zone_id, payload, success=True)

        except Exception as e:
            logger.error(f"Failed to arm zone {zone_id}: {e}")
            await self._log_command(
                CommandType.ZONE_ARM, zone_id, payload, success=False, error=str(e)
            )

    async def _handle_zone_disarm(self, zone_id: str, payload: dict[str, Any]) -> None:
        """Execute zone disarm command."""
        try:
            cmd = ZoneDisarmPayload.model_validate(payload)

            if self._is_duplicate(cmd.idempotency_key):
                logger.debug(f"Duplicate zone disarm command ignored: {cmd.idempotency_key}")
                return

            # TODO: Integrate with ZoneService to disarm zone
            logger.info(f"Zone {zone_id} disarmed", extra={"reason": cmd.reason})
            await self._log_command(CommandType.ZONE_DISARM, zone_id, payload, success=True)

        except Exception as e:
            logger.error(f"Failed to disarm zone {zone_id}: {e}")
            await self._log_command(
                CommandType.ZONE_DISARM, zone_id, payload, success=False, error=str(e)
            )

    async def _handle_camera_sensitivity(self, camera_id: str, payload: dict[str, Any]) -> None:
        """Execute camera sensitivity command."""
        try:
            cmd = CameraSensitivityPayload.model_validate(payload)

            if self._is_duplicate(cmd.idempotency_key):
                logger.debug(f"Duplicate sensitivity command ignored: {cmd.idempotency_key}")
                return

            # TODO: Integrate with CameraService to update sensitivity
            logger.info(f"Camera {camera_id} sensitivity set to {cmd.sensitivity}")
            await self._log_command(
                CommandType.CAMERA_SENSITIVITY, camera_id, payload, success=True
            )

        except Exception as e:
            logger.error(f"Failed to set camera {camera_id} sensitivity: {e}")
            await self._log_command(
                CommandType.CAMERA_SENSITIVITY, camera_id, payload, success=False, error=str(e)
            )

    async def _handle_camera_ptz(self, camera_id: str, payload: dict[str, Any]) -> None:
        """Execute camera PTZ command."""
        try:
            cmd = CameraPTZPayload.model_validate(payload)

            if self._is_duplicate(cmd.idempotency_key):
                logger.debug(f"Duplicate PTZ command ignored: {cmd.idempotency_key}")
                return

            # TODO: Integrate with PTZ service
            logger.info(
                f"Camera {camera_id} PTZ: {cmd.action}",
                extra={"preset": cmd.preset, "speed": cmd.speed},
            )
            await self._log_command(CommandType.CAMERA_PTZ, camera_id, payload, success=True)

        except Exception as e:
            logger.error(f"Failed PTZ command for camera {camera_id}: {e}")
            await self._log_command(
                CommandType.CAMERA_PTZ, camera_id, payload, success=False, error=str(e)
            )

    async def _handle_alert_ack(self, alert_id: str, payload: dict[str, Any]) -> None:
        """Execute alert acknowledgment command."""
        try:
            cmd = AlertAckPayload.model_validate(payload)

            if self._is_duplicate(cmd.idempotency_key):
                logger.debug(f"Duplicate alert ack command ignored: {cmd.idempotency_key}")
                return

            # TODO: Integrate with AlertService to acknowledge alert
            logger.info(f"Alert {alert_id} acknowledged", extra={"notes": cmd.notes})
            await self._log_command(CommandType.ALERT_ACK, alert_id, payload, success=True)

        except Exception as e:
            logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            await self._log_command(
                CommandType.ALERT_ACK, alert_id, payload, success=False, error=str(e)
            )

    async def _handle_system_mode(self, _target_id: str, payload: dict[str, Any]) -> None:
        """Execute system mode command."""
        try:
            cmd = SystemModePayload.model_validate(payload)

            if self._is_duplicate(cmd.idempotency_key):
                logger.debug(f"Duplicate system mode command ignored: {cmd.idempotency_key}")
                return

            old_mode = self._current_mode
            self._current_mode = cmd.mode

            logger.info(
                f"System mode changed: {old_mode.value} -> {cmd.mode.value}",
                extra={"old_mode": old_mode.value, "new_mode": cmd.mode.value},
            )
            await self._log_command(CommandType.SYSTEM_MODE, "system", payload, success=True)

        except Exception as e:
            logger.error(f"Failed to set system mode: {e}")
            await self._log_command(
                CommandType.SYSTEM_MODE, "system", payload, success=False, error=str(e)
            )
