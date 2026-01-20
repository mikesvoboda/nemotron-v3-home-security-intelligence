"""API route for Alertmanager webhook receiver.

This module provides an endpoint for receiving alerts from Prometheus Alertmanager,
storing them in the database for history tracking, and broadcasting them via WebSocket
for real-time frontend updates.

NEM-3122: Phase 3.1 - Alertmanager webhook receiver for Prometheus alerts.

Endpoint:
    POST /api/v1/alertmanager/webhook - Receive alerts from Alertmanager
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.alertmanager import (
    AlertmanagerWebhook,
    AlertmanagerWebhookResponse,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.core.redis import RedisClient, get_redis_optional
from backend.core.websocket.event_types import WebSocketEventType, create_event
from backend.models.prometheus_alert import PrometheusAlert, PrometheusAlertStatus
from backend.services.event_broadcaster import EventBroadcaster

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/alertmanager", tags=["alertmanager"])


async def _broadcast_prometheus_alert(
    alert: PrometheusAlert,
    redis_client: RedisClient | None,
) -> bool:
    """Broadcast a Prometheus alert via WebSocket.

    Args:
        alert: The PrometheusAlert model instance to broadcast.
        redis_client: Redis client for broadcaster (optional).

    Returns:
        True if broadcast succeeded, False otherwise.
    """
    if redis_client is None:
        logger.debug("Redis not available, skipping WebSocket broadcast")
        return False

    try:
        broadcaster = EventBroadcaster.get_instance()

        # Create payload matching PrometheusAlertPayload schema
        payload = {
            "fingerprint": alert.fingerprint,
            "status": alert.status.value,
            "alertname": alert.alertname,
            "severity": alert.severity,
            "labels": alert.labels,
            "annotations": alert.annotations,
            "starts_at": alert.starts_at.isoformat(),
            "ends_at": alert.ends_at.isoformat() if alert.ends_at else None,
            "received_at": alert.received_at.isoformat(),
        }

        # Create WebSocket event
        event = create_event(
            WebSocketEventType.PROMETHEUS_ALERT,
            payload,
        )

        # Publish to Redis channel for all connected clients
        await broadcaster._redis.publish(broadcaster.channel_name, event)
        logger.debug(f"Broadcast Prometheus alert: {alert.alertname} ({alert.status.value})")
        return True

    except RuntimeError as e:
        # Broadcaster not initialized
        logger.debug(f"WebSocket broadcast skipped (broadcaster not ready): {e}")
        return False
    except Exception as e:
        logger.warning(f"Failed to broadcast Prometheus alert: {e}")
        return False


@router.post(
    "/webhook",
    response_model=AlertmanagerWebhookResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Webhook received and processed"},
        422: {"description": "Invalid payload format"},
        500: {"description": "Internal server error"},
    },
)
async def receive_alertmanager_webhook(
    payload: AlertmanagerWebhook,
    db: AsyncSession = Depends(get_db),
    redis_client: RedisClient | None = Depends(get_redis_optional),
) -> AlertmanagerWebhookResponse:
    """Receive webhook notifications from Alertmanager.

    This endpoint receives alerts from Prometheus Alertmanager and:
    1. Stores each alert in the database for history tracking
    2. Broadcasts each alert via WebSocket for real-time frontend updates
    3. Returns acknowledgment to Alertmanager

    The alerts are infrastructure alerts (GPU memory, pipeline health, etc.)
    which are stored for history and displayed alongside security alerts.

    Args:
        payload: Alertmanager webhook payload containing alert details
        db: Database session (injected)
        redis_client: Redis client for WebSocket broadcasting (optional)

    Returns:
        AlertmanagerWebhookResponse with processing status
    """
    received_count = len(payload.alerts)
    stored_count = 0
    broadcast_count = 0

    # Get current time for received_at timestamp
    received_at = datetime.now(UTC)

    for alert in payload.alerts:
        # Log the alert with appropriate level based on status and severity
        alertname = alert.labels.get("alertname", "unknown")
        severity = alert.labels.get("severity", "info")
        description = alert.annotations.get("description", alert.annotations.get("summary", ""))

        if alert.status.value == "firing":
            log_msg = f"[PROMETHEUS ALERT FIRING] {alertname} ({severity}): {description}"
            if severity == "critical":
                logger.error(log_msg)
            elif severity in ("warning", "high"):
                logger.warning(log_msg)
            else:
                logger.info(log_msg)
        else:
            logger.info(
                f"[PROMETHEUS ALERT RESOLVED] {alertname} ({severity}): "
                f"resolved after firing since {alert.startsAt}"
            )

        # Convert status to model enum
        status_enum = PrometheusAlertStatus(alert.status.value)

        # Create database record
        db_alert = PrometheusAlert(
            fingerprint=alert.fingerprint,
            status=status_enum,
            labels=alert.labels,
            annotations=alert.annotations,
            starts_at=alert.startsAt,
            ends_at=alert.endsAt if alert.endsAt and alert.endsAt.year > 1 else None,
            received_at=received_at,
        )
        db.add(db_alert)

        try:
            # Flush to get the ID for the alert
            await db.flush()
            stored_count += 1

            # Broadcast via WebSocket
            if await _broadcast_prometheus_alert(db_alert, redis_client):
                broadcast_count += 1

        except Exception as e:
            logger.error(f"Failed to store/broadcast alert {alertname}: {e}")
            # Continue processing other alerts

    # Commit all stored alerts
    try:
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to commit alerts: {e}")
        await db.rollback()
        # Return partial success info
        return AlertmanagerWebhookResponse(
            status="partial",
            received=received_count,
            stored=0,
            broadcast=broadcast_count,
            message=f"Received {received_count} alert(s), commit failed: {e}",
        )

    return AlertmanagerWebhookResponse(
        status="ok",
        received=received_count,
        stored=stored_count,
        broadcast=broadcast_count,
        message=f"Processed {received_count} alert(s) from {payload.receiver}",
    )
