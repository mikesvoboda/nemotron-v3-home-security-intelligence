"""MQTT configuration API routes for the Configuration UI.

This module provides endpoints for:
1. MQTT configuration management (GET/PUT /api/mqtt-config)
2. Connection status monitoring (GET /api/mqtt-config/status)
3. Connection testing (POST /api/mqtt-config/test)
4. Connection control (POST /api/mqtt-config/reconnect, /api/mqtt-config/disconnect)

The configuration is persisted using the SystemSetting key-value store,
so no new database migrations are required.

Related Issues:
    - NEM-XXXX: MQTT Configuration UI Backend
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.mqtt_config import (
    MqttBrokerConfig,
    MqttConfigResponse,
    MqttConfigUpdate,
    MqttConnectionStatus,
    MqttDisconnectResponse,
    MqttIntegrationConfig,
    MqttPublisherConfig,
    MqttReconnectResponse,
    MqttTestRequest,
    MqttTestResult,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.gpu_config import SystemSetting

logger = get_logger(__name__)

# Router with /api prefix
router = APIRouter(prefix="/api/mqtt-config", tags=["mqtt-config"])

# SystemSetting key for MQTT configuration
MQTT_CONFIG_KEY = "mqtt_config"

# Default MQTT configuration
DEFAULT_MQTT_CONFIG: dict[str, Any] = {
    "broker": {
        "host": "localhost",
        "port": 1883,
        "username": None,
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
        "enabled": False,
        "publish_events": True,
        "publish_detections": False,
        "publish_system_status": True,
    },
}

# In-memory connection state (would be replaced by actual MQTT client in production)
_mqtt_connection_state: dict[str, Any] = {
    "connected": False,
    "last_connected_at": None,
    "last_error": None,
    "last_error_at": None,
    "messages_published": 0,
}


# =============================================================================
# Helper Functions
# =============================================================================


def _mask_password(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Remove password from configuration dictionary.

    Args:
        config_dict: Configuration dictionary that may contain password

    Returns:
        Configuration dictionary with password set to None
    """
    result = config_dict.copy()
    if "broker" in result and isinstance(result["broker"], dict):
        result["broker"] = result["broker"].copy()
        result["broker"]["password"] = None
    return result


def _merge_config_update(
    existing: dict[str, Any],
    update: dict[str, Any],
) -> dict[str, Any]:
    """Merge update into existing configuration.

    Only updates fields that are explicitly provided (not None).

    Args:
        existing: Current configuration
        update: Update to apply

    Returns:
        Merged configuration
    """
    result = existing.copy()

    for section_name in ["broker", "publisher", "integration"]:
        if section_name in update and update[section_name] is not None:
            section_update = update[section_name]
            if section_name not in result:
                result[section_name] = {}
            else:
                result[section_name] = result[section_name].copy()

            for key, value in section_update.items():
                if value is not None:
                    result[section_name][key] = value

    return result


async def _get_mqtt_config(db: AsyncSession) -> tuple[dict[str, Any], datetime | None]:
    """Get MQTT configuration from database.

    Args:
        db: Database session

    Returns:
        Tuple of (config_dict, updated_at)
    """
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == MQTT_CONFIG_KEY))
    setting = result.scalar_one_or_none()

    if setting is None:
        return DEFAULT_MQTT_CONFIG.copy(), None

    return setting.value, setting.updated_at


async def _save_mqtt_config(
    db: AsyncSession,
    config: dict[str, Any],
) -> datetime:
    """Save MQTT configuration to database.

    Args:
        db: Database session
        config: Configuration dictionary to save

    Returns:
        Updated timestamp
    """
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == MQTT_CONFIG_KEY))
    setting = result.scalar_one_or_none()

    if setting is None:
        setting = SystemSetting(
            key=MQTT_CONFIG_KEY,
            value=config,
        )
        db.add(setting)
    else:
        setting.value = config

    await db.commit()
    await db.refresh(setting)

    return setting.updated_at


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "",
    response_model=MqttConfigResponse,
    summary="Get MQTT configuration",
    description="Returns current MQTT configuration with password masked.",
    responses={
        500: {"description": "Failed to load configuration"},
    },
)
async def get_mqtt_config(
    db: AsyncSession = Depends(get_db),
) -> MqttConfigResponse:
    """Get the current MQTT configuration.

    Returns the broker, publisher, and integration settings.
    The password field is always returned as None for security.

    Args:
        db: Database session

    Returns:
        MqttConfigResponse with current settings (password masked)
    """
    try:
        config_dict, updated_at = await _get_mqtt_config(db)

        # Mask password before returning
        masked_config = _mask_password(config_dict)

        # Build response with proper defaults
        broker_data = {**DEFAULT_MQTT_CONFIG["broker"], **masked_config.get("broker", {})}
        publisher_data = {**DEFAULT_MQTT_CONFIG["publisher"], **masked_config.get("publisher", {})}
        integration_data = {
            **DEFAULT_MQTT_CONFIG["integration"],
            **masked_config.get("integration", {}),
        }

        return MqttConfigResponse(
            broker=MqttBrokerConfig(**broker_data),
            publisher=MqttPublisherConfig(**publisher_data),
            integration=MqttIntegrationConfig(**integration_data),
            updated_at=updated_at,
        )

    except Exception as e:
        logger.exception("Failed to load MQTT configuration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load MQTT configuration: {e}",
        ) from e


@router.put(
    "",
    response_model=MqttConfigResponse,
    summary="Update MQTT configuration",
    description="Updates MQTT configuration. Supports partial updates.",
    responses={
        400: {"description": "Invalid configuration"},
        500: {"description": "Failed to save configuration"},
    },
)
async def update_mqtt_config(
    request: MqttConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> MqttConfigResponse:
    """Update MQTT configuration.

    Supports partial updates - only provided fields are updated.
    Password is stored but never returned in responses.

    Args:
        request: Configuration update request
        db: Database session

    Returns:
        MqttConfigResponse with updated settings (password masked)
    """
    try:
        # Get current configuration
        existing_config, _ = await _get_mqtt_config(db)

        # Convert update request to dict
        update_dict: dict[str, Any] = {}
        if request.broker is not None:
            update_dict["broker"] = request.broker.model_dump(exclude_none=True)
        if request.publisher is not None:
            update_dict["publisher"] = request.publisher.model_dump(exclude_none=True)
        if request.integration is not None:
            update_dict["integration"] = request.integration.model_dump(exclude_none=True)

        # Merge updates
        merged_config = _merge_config_update(existing_config, update_dict)

        # Save configuration
        updated_at = await _save_mqtt_config(db, merged_config)

        # Mask password for response
        masked_config = _mask_password(merged_config)

        # Build response
        broker_data = {**DEFAULT_MQTT_CONFIG["broker"], **masked_config.get("broker", {})}
        publisher_data = {**DEFAULT_MQTT_CONFIG["publisher"], **masked_config.get("publisher", {})}
        integration_data = {
            **DEFAULT_MQTT_CONFIG["integration"],
            **masked_config.get("integration", {}),
        }

        logger.info(
            "MQTT configuration updated",
            extra={
                "broker_host": broker_data.get("host"),
                "integration_enabled": integration_data.get("enabled"),
            },
        )

        return MqttConfigResponse(
            broker=MqttBrokerConfig(**broker_data),
            publisher=MqttPublisherConfig(**publisher_data),
            integration=MqttIntegrationConfig(**integration_data),
            updated_at=updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to save MQTT configuration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save MQTT configuration: {e}",
        ) from e


@router.get(
    "/status",
    response_model=MqttConnectionStatus,
    summary="Get MQTT connection status",
    description="Returns current MQTT broker connection status.",
)
async def get_mqtt_status(
    db: AsyncSession = Depends(get_db),
) -> MqttConnectionStatus:
    """Get the current MQTT connection status.

    Returns connection state, last error, and message statistics.

    Args:
        db: Database session

    Returns:
        MqttConnectionStatus with current connection state
    """
    # Get current configuration for broker info
    config_dict, _ = await _get_mqtt_config(db)
    broker_config = config_dict.get("broker", {})

    return MqttConnectionStatus(
        connected=_mqtt_connection_state["connected"],
        last_connected_at=_mqtt_connection_state["last_connected_at"],
        last_error=_mqtt_connection_state["last_error"],
        last_error_at=_mqtt_connection_state["last_error_at"],
        messages_published=_mqtt_connection_state["messages_published"],
        broker_host=broker_config.get("host"),
        broker_port=broker_config.get("port"),
    )


@router.post(
    "/test",
    response_model=MqttTestResult,
    summary="Test MQTT connection",
    description="Tests connection to MQTT broker without modifying configuration.",
    responses={
        400: {"description": "Invalid test configuration"},
    },
)
async def test_mqtt_connection(
    request: MqttTestRequest,
    db: AsyncSession = Depends(get_db),
) -> MqttTestResult:
    """Test MQTT broker connection.

    Tests connectivity to the MQTT broker using either saved configuration
    or provided override settings. Does not modify saved configuration.

    Args:
        request: Test request with optional configuration override
        db: Database session

    Returns:
        MqttTestResult with test outcome
    """
    try:
        # Determine which configuration to use
        if request.use_saved_config:
            config_dict, _ = await _get_mqtt_config(db)
            broker_config = config_dict.get("broker", DEFAULT_MQTT_CONFIG["broker"])
        else:
            if request.broker_override is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="broker_override is required when use_saved_config is False",
                )
            broker_config = request.broker_override.model_dump()

        host = broker_config.get("host", "localhost")
        port = broker_config.get("port", 1883)

        # Simulate connection test (in production, use actual MQTT client)
        # For now, we'll do a simple TCP socket test
        start_time = time.time()

        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(request.timeout_seconds)
            sock.connect((host, port))
            sock.close()

            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                f"MQTT connection test successful: {host}:{port}",
                extra={"host": host, "port": port, "latency_ms": latency_ms},
            )

            return MqttTestResult(
                success=True,
                message=f"Successfully connected to {host}:{port}",
                latency_ms=round(latency_ms, 2),
                broker_version=None,  # Would require actual MQTT connection
                error_code=None,
                error_details=None,
            )

        except TimeoutError:
            return MqttTestResult(
                success=False,
                message=f"Connection timeout to {host}:{port}",
                latency_ms=None,
                broker_version=None,
                error_code="TIMEOUT",
                error_details=f"Connection timed out after {request.timeout_seconds} seconds",
            )

        except OSError as e:
            return MqttTestResult(
                success=False,
                message=f"Failed to connect to {host}:{port}",
                latency_ms=None,
                broker_version=None,
                error_code="CONNECTION_ERROR",
                error_details=str(e),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("MQTT connection test failed")
        return MqttTestResult(
            success=False,
            message="Connection test failed",
            latency_ms=None,
            broker_version=None,
            error_code="INTERNAL_ERROR",
            error_details=str(e),
        )


@router.post(
    "/reconnect",
    response_model=MqttReconnectResponse,
    summary="Reconnect to MQTT broker",
    description="Disconnects and reconnects to the MQTT broker.",
    responses={
        500: {"description": "Reconnection failed"},
    },
)
async def reconnect_mqtt(
    db: AsyncSession = Depends(get_db),
) -> MqttReconnectResponse:
    """Reconnect to the MQTT broker.

    Disconnects from the current broker (if connected) and establishes
    a new connection using the saved configuration.

    Args:
        db: Database session

    Returns:
        MqttReconnectResponse with reconnection result
    """
    previous_state = "connected" if _mqtt_connection_state["connected"] else "disconnected"

    try:
        # Get current configuration
        config_dict, _ = await _get_mqtt_config(db)
        broker_config = config_dict.get("broker", DEFAULT_MQTT_CONFIG["broker"])
        integration_config = config_dict.get("integration", DEFAULT_MQTT_CONFIG["integration"])

        # Check if MQTT is enabled
        if not integration_config.get("enabled", False):
            return MqttReconnectResponse(
                success=False,
                message="MQTT integration is disabled. Enable it in configuration first.",
                previous_state=previous_state,
                new_state="disconnected",
            )

        host = broker_config.get("host", "localhost")
        port = broker_config.get("port", 1883)

        # Simulate reconnection (in production, use actual MQTT client)
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            sock.connect((host, port))
            sock.close()

            # Update connection state
            _mqtt_connection_state["connected"] = True
            _mqtt_connection_state["last_connected_at"] = datetime.now(UTC)
            _mqtt_connection_state["last_error"] = None
            _mqtt_connection_state["last_error_at"] = None

            logger.info(
                f"MQTT reconnected: {host}:{port}",
                extra={"host": host, "port": port},
            )

            return MqttReconnectResponse(
                success=True,
                message=f"Reconnected to {host}:{port}",
                previous_state=previous_state,
                new_state="connected",
            )

        except (TimeoutError, OSError) as e:
            _mqtt_connection_state["connected"] = False
            _mqtt_connection_state["last_error"] = str(e)
            _mqtt_connection_state["last_error_at"] = datetime.now(UTC)

            return MqttReconnectResponse(
                success=False,
                message=f"Failed to reconnect to {host}:{port}: {e}",
                previous_state=previous_state,
                new_state="disconnected",
            )

    except Exception as e:
        logger.exception("MQTT reconnection failed")
        _mqtt_connection_state["connected"] = False
        _mqtt_connection_state["last_error"] = str(e)
        _mqtt_connection_state["last_error_at"] = datetime.now(UTC)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MQTT reconnection failed: {e}",
        ) from e


@router.post(
    "/disconnect",
    response_model=MqttDisconnectResponse,
    summary="Disconnect from MQTT broker",
    description="Gracefully disconnects from the MQTT broker.",
)
async def disconnect_mqtt() -> MqttDisconnectResponse:
    """Disconnect from the MQTT broker.

    Gracefully closes the connection to the MQTT broker.

    Returns:
        MqttDisconnectResponse with disconnect result
    """
    was_connected = _mqtt_connection_state["connected"]

    # Update connection state
    _mqtt_connection_state["connected"] = False

    if was_connected:
        logger.info("MQTT disconnected by user request")
        return MqttDisconnectResponse(
            success=True,
            message="Disconnected from MQTT broker",
            was_connected=True,
        )
    else:
        return MqttDisconnectResponse(
            success=True,
            message="Already disconnected from MQTT broker",
            was_connected=False,
        )


# Export router
__all__ = ["router"]
