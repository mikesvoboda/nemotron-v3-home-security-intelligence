"""Pydantic schemas for MQTT Configuration UI API endpoints.

This module provides request/response schemas for the MQTT configuration
API, enabling configuration of MQTT broker connections, publisher settings,
and integration options through a web UI.

The MQTT configuration is persisted using the SystemSetting key-value store,
so no new database migrations are required.
"""

from datetime import datetime
from enum import IntEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MqttQoS(IntEnum):
    """MQTT Quality of Service levels.

    QoS levels determine delivery guarantees:
    - AT_MOST_ONCE (0): Fire and forget, no acknowledgment
    - AT_LEAST_ONCE (1): Acknowledged delivery, may have duplicates
    - EXACTLY_ONCE (2): Guaranteed single delivery
    """

    AT_MOST_ONCE = 0
    AT_LEAST_ONCE = 1
    EXACTLY_ONCE = 2


class MqttBrokerConfig(BaseModel):
    """MQTT broker connection settings.

    Configures how to connect to the MQTT broker including
    authentication and TLS settings.
    """

    host: str = Field(
        default="localhost",
        description="MQTT broker hostname or IP address",
        min_length=1,
        max_length=255,
    )
    port: int = Field(
        default=1883,
        description="MQTT broker port (typically 1883 for TCP, 8883 for TLS)",
        ge=1,
        le=65535,
    )
    username: str | None = Field(
        default=None,
        description="Username for broker authentication (optional)",
        max_length=128,
    )
    password: str | None = Field(
        default=None,
        description="Password for broker authentication (optional, never returned in responses)",
        max_length=256,
    )
    use_tls: bool = Field(
        default=False,
        description="Enable TLS/SSL for broker connection",
    )
    client_id: str = Field(
        default="home-security-backend",
        description="MQTT client identifier (must be unique per connection)",
        min_length=1,
        max_length=128,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "host": "mqtt.example.com",
                "port": 1883,
                "username": "user",
                "password": None,
                "use_tls": False,
                "client_id": "home-security-backend",
            }
        }
    )


class MqttBrokerConfigUpdate(BaseModel):
    """MQTT broker connection settings update (all fields optional).

    Used for partial updates to broker configuration.
    """

    host: str | None = Field(
        default=None,
        description="MQTT broker hostname or IP address",
        min_length=1,
        max_length=255,
    )
    port: int | None = Field(
        default=None,
        description="MQTT broker port",
        ge=1,
        le=65535,
    )
    username: str | None = Field(
        default=None,
        description="Username for broker authentication",
        max_length=128,
    )
    password: str | None = Field(
        default=None,
        description="Password for broker authentication",
        max_length=256,
    )
    use_tls: bool | None = Field(
        default=None,
        description="Enable TLS/SSL for broker connection",
    )
    client_id: str | None = Field(
        default=None,
        description="MQTT client identifier",
        min_length=1,
        max_length=128,
    )


class MqttPublisherConfig(BaseModel):
    """MQTT publisher settings.

    Configures how messages are published to the broker including
    topic prefix, QoS level, and retention settings.
    """

    topic_prefix: str = Field(
        default="home-security",
        description="Prefix for all MQTT topics (e.g., 'home-security/events')",
        min_length=1,
        max_length=128,
    )
    qos: int = Field(
        default=MqttQoS.AT_LEAST_ONCE,
        description="Quality of Service level (0=at most once, 1=at least once, 2=exactly once)",
        ge=0,
        le=2,
    )
    retain: bool = Field(
        default=False,
        description="Retain last message on each topic for new subscribers",
    )

    @field_validator("qos")
    @classmethod
    def validate_qos(cls, v: int) -> int:
        """Validate QoS is a valid MQTT level."""
        if v not in (0, 1, 2):
            raise ValueError("QoS must be 0, 1, or 2")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic_prefix": "home-security",
                "qos": 1,
                "retain": False,
            }
        }
    )


class MqttPublisherConfigUpdate(BaseModel):
    """MQTT publisher settings update (all fields optional).

    Used for partial updates to publisher configuration.
    """

    topic_prefix: str | None = Field(
        default=None,
        description="Prefix for all MQTT topics",
        min_length=1,
        max_length=128,
    )
    qos: int | None = Field(
        default=None,
        description="Quality of Service level",
        ge=0,
        le=2,
    )
    retain: bool | None = Field(
        default=None,
        description="Retain last message on each topic",
    )

    @field_validator("qos")
    @classmethod
    def validate_qos(cls, v: int | None) -> int | None:
        """Validate QoS is a valid MQTT level."""
        if v is not None and v not in (0, 1, 2):
            raise ValueError("QoS must be 0, 1, or 2")
        return v


class MqttIntegrationConfig(BaseModel):
    """MQTT integration settings.

    Configures which events and data are published to MQTT.
    """

    enabled: bool = Field(
        default=False,
        description="Enable MQTT integration",
    )
    publish_events: bool = Field(
        default=True,
        description="Publish security events to MQTT",
    )
    publish_detections: bool = Field(
        default=False,
        description="Publish detection events (high volume)",
    )
    publish_system_status: bool = Field(
        default=True,
        description="Publish system status updates",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enabled": True,
                "publish_events": True,
                "publish_detections": False,
                "publish_system_status": True,
            }
        }
    )


class MqttIntegrationConfigUpdate(BaseModel):
    """MQTT integration settings update (all fields optional).

    Used for partial updates to integration configuration.
    """

    enabled: bool | None = Field(
        default=None,
        description="Enable MQTT integration",
    )
    publish_events: bool | None = Field(
        default=None,
        description="Publish security events to MQTT",
    )
    publish_detections: bool | None = Field(
        default=None,
        description="Publish detection events",
    )
    publish_system_status: bool | None = Field(
        default=None,
        description="Publish system status updates",
    )


class MqttConfig(BaseModel):
    """Complete MQTT configuration.

    Combines broker, publisher, and integration settings.
    """

    broker: MqttBrokerConfig = Field(
        default_factory=MqttBrokerConfig,
        description="MQTT broker connection settings",
    )
    publisher: MqttPublisherConfig = Field(
        default_factory=MqttPublisherConfig,
        description="MQTT publisher settings",
    )
    integration: MqttIntegrationConfig = Field(
        default_factory=MqttIntegrationConfig,
        description="MQTT integration settings",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "broker": {
                    "host": "mqtt.example.com",
                    "port": 1883,
                    "username": "user",
                    "password": None,
                    "use_tls": False,
                    "client_id": "home-security-backend",
                },
                "publisher": {
                    "topic_prefix": "home-security",
                    "qos": 1,
                    "retain": False,
                },
                "integration": {
                    "enabled": True,
                    "publish_events": True,
                    "publish_detections": False,
                    "publish_system_status": True,
                },
            }
        }
    )


class MqttConfigResponse(BaseModel):
    """Response schema for MQTT configuration.

    Same as MqttConfig but with password always masked/excluded.
    """

    broker: MqttBrokerConfig = Field(
        ...,
        description="MQTT broker connection settings (password excluded)",
    )
    publisher: MqttPublisherConfig = Field(
        ...,
        description="MQTT publisher settings",
    )
    integration: MqttIntegrationConfig = Field(
        ...,
        description="MQTT integration settings",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp of last configuration update",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "broker": {
                    "host": "mqtt.example.com",
                    "port": 1883,
                    "username": "user",
                    "password": None,
                    "use_tls": False,
                    "client_id": "home-security-backend",
                },
                "publisher": {
                    "topic_prefix": "home-security",
                    "qos": 1,
                    "retain": False,
                },
                "integration": {
                    "enabled": True,
                    "publish_events": True,
                    "publish_detections": False,
                    "publish_system_status": True,
                },
                "updated_at": "2026-01-15T10:30:00Z",
            }
        },
    )


class MqttConfigUpdate(BaseModel):
    """Request schema for updating MQTT configuration.

    All fields are optional for partial updates.
    """

    broker: MqttBrokerConfigUpdate | None = Field(
        default=None,
        description="MQTT broker connection settings to update",
    )
    publisher: MqttPublisherConfigUpdate | None = Field(
        default=None,
        description="MQTT publisher settings to update",
    )
    integration: MqttIntegrationConfigUpdate | None = Field(
        default=None,
        description="MQTT integration settings to update",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "broker": {
                    "host": "new-mqtt.example.com",
                    "port": 8883,
                    "use_tls": True,
                },
                "integration": {
                    "enabled": True,
                },
            }
        }
    )


class MqttConnectionStatus(BaseModel):
    """MQTT connection status information.

    Reports the current state of the MQTT broker connection.
    """

    connected: bool = Field(
        ...,
        description="Whether currently connected to the broker",
    )
    last_connected_at: datetime | None = Field(
        default=None,
        description="Timestamp of last successful connection",
    )
    last_error: str | None = Field(
        default=None,
        description="Last connection error message (if any)",
    )
    last_error_at: datetime | None = Field(
        default=None,
        description="Timestamp of last connection error",
    )
    messages_published: int = Field(
        default=0,
        description="Total messages published since last connect",
        ge=0,
    )
    broker_host: str | None = Field(
        default=None,
        description="Currently configured broker host",
    )
    broker_port: int | None = Field(
        default=None,
        description="Currently configured broker port",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "connected": True,
                "last_connected_at": "2026-01-15T10:30:00Z",
                "last_error": None,
                "last_error_at": None,
                "messages_published": 1234,
                "broker_host": "mqtt.example.com",
                "broker_port": 1883,
            }
        },
    )


class MqttTestRequest(BaseModel):
    """Request schema for testing MQTT connection.

    Optionally override configuration for testing without saving.
    """

    use_saved_config: bool = Field(
        default=True,
        description="Use saved configuration (if False, broker_override is required)",
    )
    broker_override: MqttBrokerConfig | None = Field(
        default=None,
        description="Override broker config for testing (not saved)",
    )
    timeout_seconds: float = Field(
        default=10.0,
        description="Connection timeout in seconds",
        ge=1.0,
        le=60.0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "use_saved_config": False,
                "broker_override": {
                    "host": "test-mqtt.example.com",
                    "port": 1883,
                    "username": "testuser",
                    "password": None,  # Never include example passwords
                    "use_tls": False,
                    "client_id": "test-client",
                },
                "timeout_seconds": 10.0,
            }
        }
    )


class MqttTestResult(BaseModel):
    """Result schema for MQTT connection test.

    Reports whether the test connection was successful and any errors.
    """

    success: bool = Field(
        ...,
        description="Whether the connection test was successful",
    )
    message: str = Field(
        ...,
        description="Human-readable result message",
    )
    latency_ms: float | None = Field(
        default=None,
        description="Connection latency in milliseconds (if successful)",
        ge=0,
    )
    broker_version: str | None = Field(
        default=None,
        description="Broker version string (if available)",
    )
    error_code: str | None = Field(
        default=None,
        description="Error code (if failed)",
    )
    error_details: str | None = Field(
        default=None,
        description="Detailed error message (if failed)",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Successfully connected to mqtt.example.com:1883",
                "latency_ms": 45.2,
                "broker_version": "Mosquitto 2.0.15",
                "error_code": None,
                "error_details": None,
            }
        },
    )


class MqttReconnectResponse(BaseModel):
    """Response schema for MQTT reconnect request.

    Reports the result of a reconnection attempt.
    """

    success: bool = Field(
        ...,
        description="Whether the reconnection was initiated successfully",
    )
    message: str = Field(
        ...,
        description="Human-readable result message",
    )
    previous_state: str = Field(
        ...,
        description="Connection state before reconnect (connected/disconnected)",
    )
    new_state: str = Field(
        ...,
        description="Connection state after reconnect attempt",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Reconnected to mqtt.example.com:1883",
                "previous_state": "disconnected",
                "new_state": "connected",
            }
        },
    )


class MqttDisconnectResponse(BaseModel):
    """Response schema for MQTT disconnect request.

    Reports the result of a disconnect request.
    """

    success: bool = Field(
        ...,
        description="Whether the disconnect was successful",
    )
    message: str = Field(
        ...,
        description="Human-readable result message",
    )
    was_connected: bool = Field(
        ...,
        description="Whether the client was connected before disconnect",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Disconnected from MQTT broker",
                "was_connected": True,
            }
        },
    )


# Export all schemas
__all__ = [
    "MqttBrokerConfig",
    "MqttBrokerConfigUpdate",
    "MqttConfig",
    "MqttConfigResponse",
    "MqttConfigUpdate",
    "MqttConnectionStatus",
    "MqttDisconnectResponse",
    "MqttIntegrationConfig",
    "MqttIntegrationConfigUpdate",
    "MqttPublisherConfig",
    "MqttPublisherConfigUpdate",
    "MqttQoS",
    "MqttReconnectResponse",
    "MqttTestRequest",
    "MqttTestResult",
]
