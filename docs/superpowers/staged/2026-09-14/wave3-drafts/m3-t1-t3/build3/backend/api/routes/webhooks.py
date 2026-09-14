"""API routes for webhook receivers.

This module provides endpoints for receiving webhooks from external systems,
primarily Alertmanager for infrastructure alerts.

Webhook Endpoints:
    POST /api/webhooks/alerts - Receive Alertmanager webhook notifications
"""

from fastapi import APIRouter, BackgroundTasks, status

from backend.api.schemas.webhooks import (
    AlertmanagerStatus,
    AlertmanagerWebhookPayload,
    WebhookProcessingResponse,
)
from backend.core.logging import get_logger
from backend.services.event_broadcaster import EventBroadcaster

logger = get_logger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


async def _broadcast_infrastructure_alerts(payload: AlertmanagerWebhookPayload) -> None:
    """Broadcast infrastructure alerts to WebSocket clients.

    This allows the frontend to display real-time infrastructure alerts
    (GPU memory, pipeline health, etc.) alongside security alerts.
    """
    try:
        broadcaster = EventBroadcaster.get_instance()

        for alert in payload.alerts:
            alert_data = {
                "type": "infrastructure_alert",
                "data": {
                    "alertname": alert.labels.get("alertname", "unknown"),
                    "status": alert.status.value,
                    "severity": alert.labels.get("severity", "info"),
                    "component": alert.labels.get("component", "unknown"),
                    "summary": alert.annotations.get("summary", ""),
                    "description": alert.annotations.get("description", ""),
                    "started_at": alert.startsAt.isoformat() if alert.startsAt else None,
                    "fingerprint": alert.fingerprint,
                    "receiver": payload.receiver,
                },
            }

            try:
                await broadcaster.broadcast_infrastructure_alert(alert_data)
            except ValueError as ve:
                # Validation error - log but continue with other alerts
                logger.warning(f"Failed to broadcast infrastructure alert: {ve}")
            except Exception as e:
                logger.warning(f"Failed to broadcast infrastructure alert: {e}")

    except RuntimeError as e:
        # Broadcaster not initialized - log but don't fail
        logger.debug(f"WebSocket broadcast skipped (broadcaster not ready): {e}")
    except Exception as e:
        logger.warning(f"Failed to broadcast infrastructure alerts: {e}")


@router.post(
    "/alerts",
    response_model=WebhookProcessingResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Webhook received and processed"},
        422: {"description": "Invalid payload format"},
        500: {"description": "Internal server error"},
    },
)
async def receive_alertmanager_webhook(
    payload: AlertmanagerWebhookPayload,
    background_tasks: BackgroundTasks,
) -> WebhookProcessingResponse:
    """Receive webhook notifications from Alertmanager.

    This endpoint receives alerts from Prometheus Alertmanager and:
    1. Logs the alert for observability
    2. Broadcasts to WebSocket clients for real-time frontend updates
    3. Returns acknowledgment to Alertmanager

    The alerts are infrastructure alerts (GPU memory, pipeline health, etc.)
    which are separate from AI-generated security alerts.

    Args:
        payload: Alertmanager webhook payload containing alert details
        background_tasks: FastAPI background tasks for async processing

    Returns:
        WebhookProcessingResponse with processing status
    """
    alert_count = len(payload.alerts)

    # Log each alert with appropriate level based on status and severity
    for alert in payload.alerts:
        alertname = alert.labels.get("alertname", "unknown")
        severity = alert.labels.get("severity", "info")
        component = alert.labels.get("component", "unknown")
        description = alert.annotations.get("description", alert.annotations.get("summary", ""))

        if alert.status == AlertmanagerStatus.FIRING:
            log_msg = (
                f"[ALERT FIRING] {alertname} ({severity}) - component={component}: {description}"
            )
            if severity == "critical":
                logger.error(log_msg)
            elif severity in ("warning", "high"):
                logger.warning(log_msg)
            else:
                logger.info(log_msg)
        else:
            logger.info(
                f"[ALERT RESOLVED] {alertname} ({severity}) - "
                f"component={component}: resolved after firing since {alert.startsAt}"
            )

    # Broadcast to WebSocket clients in background
    # Note: BackgroundTasks can run coroutines
    background_tasks.add_task(_broadcast_infrastructure_alerts, payload)

    return WebhookProcessingResponse(
        status="ok",
        received=alert_count,
        processed=alert_count,
        message=f"Processed {alert_count} alert(s) from {payload.receiver}",
    )
