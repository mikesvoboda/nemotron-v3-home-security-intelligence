"""Alert service for CRUD operations with WebSocket event emissions.

This module provides a service layer for managing alerts (create, read, update, delete)
with integrated WebSocket event broadcasting for real-time frontend updates and
outbound webhook triggering for external system notifications.

WebSocket Events:
    - alert.created: Emitted when a new alert is created
    - alert.updated: Emitted when an alert is updated (including acknowledgment)
    - alert.deleted: Emitted when an alert is deleted

Webhook Events (NEM-3624):
    - ALERT_FIRED: Triggered when a new alert is created
    - ALERT_ACKNOWLEDGED: Triggered when an alert is acknowledged
    - ALERT_DISMISSED: Triggered when an alert is dismissed

Example Usage:
    from backend.services.alert_service import AlertService, get_alert_service

    service = await get_alert_service(session, emitter)

    # Create alert
    alert = await service.create_alert(
        event_id=123,
        rule_id="rule-uuid",
        severity=AlertSeverity.HIGH,
        dedup_key="front_door:rule-uuid",
    )

    # Acknowledge alert
    alert = await service.acknowledge_alert(alert_id="alert-uuid")

    # Delete alert
    await service.delete_alert(alert_id="alert-uuid")
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.outbound_webhook import WebhookEventType
from backend.core.logging import get_logger
from backend.core.websocket.event_types import WebSocketEventType
from backend.models import Alert, AlertSeverity, AlertStatus
from backend.services.webhook_service import get_webhook_service

if TYPE_CHECKING:
    from backend.services.websocket_emitter import WebSocketEmitterService

logger = get_logger(__name__)


class AlertService:
    """Service for alert CRUD operations with WebSocket event emissions.

    This service encapsulates all alert database operations and automatically
    emits WebSocket events for real-time frontend updates. Events are emitted
    after successful database operations.

    Attributes:
        _session: SQLAlchemy async session for database operations
        _emitter: WebSocket emitter service for broadcasting events
    """

    def __init__(
        self,
        session: AsyncSession,
        emitter: WebSocketEmitterService | None = None,
    ) -> None:
        """Initialize the alert service.

        Args:
            session: SQLAlchemy async session for database operations.
            emitter: Optional WebSocket emitter for broadcasting events.
                    If not provided, events will not be emitted.
        """
        self._session = session
        self._emitter = emitter

    def set_emitter(self, emitter: WebSocketEmitterService) -> None:
        """Set the WebSocket emitter after initialization.

        Args:
            emitter: WebSocket emitter service instance.
        """
        self._emitter = emitter

    # =========================================================================
    # Alert CRUD Operations
    # =========================================================================

    async def create_alert(
        self,
        event_id: int,
        severity: AlertSeverity,
        dedup_key: str,
        rule_id: str | None = None,
        status: AlertStatus = AlertStatus.PENDING,
        channels: list[str] | None = None,
        alert_metadata: dict[str, Any] | None = None,
        *,
        correlation_id: str | None = None,
    ) -> Alert:
        """Create a new alert and emit alert.created event.

        Args:
            event_id: Associated security event ID.
            severity: Alert severity level.
            dedup_key: Deduplication key for alert grouping.
            rule_id: Optional alert rule UUID that triggered this alert.
            status: Initial alert status (default: PENDING).
            channels: Optional list of notification channels.
            alert_metadata: Optional metadata dictionary.
            correlation_id: Optional correlation ID for request tracing.

        Returns:
            Created Alert instance.

        Raises:
            SQLAlchemy exceptions on database errors.
        """
        alert = Alert(
            event_id=event_id,
            rule_id=rule_id,
            severity=severity,
            status=status,
            dedup_key=dedup_key,
            channels=channels or [],
            alert_metadata=alert_metadata,
        )

        self._session.add(alert)
        await self._session.flush()
        await self._session.refresh(alert)

        # Emit WebSocket event
        await self._emit_alert_created(alert, correlation_id=correlation_id)

        # Trigger outbound webhooks for ALERT_FIRED event (NEM-3624)
        await self._trigger_webhook(
            WebhookEventType.ALERT_FIRED,
            self._build_alert_webhook_data(alert),
            alert.id,
        )

        logger.debug(
            f"Created alert {alert.id} for event {event_id}",
            extra={
                "alert_id": alert.id,
                "event_id": event_id,
                "severity": severity.value,
            },
        )

        return alert

    async def get_alert(self, alert_id: str) -> Alert | None:
        """Get an alert by ID.

        Args:
            alert_id: Alert UUID.

        Returns:
            Alert instance if found, None otherwise.
        """
        result = await self._session.execute(select(Alert).where(Alert.id == alert_id))
        return result.scalar_one_or_none()

    async def update_alert(
        self,
        alert_id: str,
        *,
        status: AlertStatus | None = None,
        severity: AlertSeverity | None = None,
        channels: list[str] | None = None,
        alert_metadata: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> Alert | None:
        """Update an alert and emit alert.updated event.

        Args:
            alert_id: Alert UUID to update.
            status: New status (optional).
            severity: New severity (optional).
            channels: New channels list (optional).
            alert_metadata: New metadata dict (optional).
            correlation_id: Optional correlation ID for request tracing.

        Returns:
            Updated Alert instance if found, None otherwise.

        Raises:
            SQLAlchemy exceptions on database errors.
        """
        alert = await self.get_alert(alert_id)
        if alert is None:
            return None

        updated_fields: list[str] = []

        if status is not None and status != alert.status:
            alert.status = status
            updated_fields.append("status")

        if severity is not None and severity != alert.severity:
            alert.severity = severity
            updated_fields.append("severity")

        if channels is not None:
            alert.channels = channels
            updated_fields.append("channels")

        if alert_metadata is not None:
            alert.alert_metadata = alert_metadata
            updated_fields.append("alert_metadata")

        if updated_fields:
            await self._session.flush()
            await self._session.refresh(alert)

            # Emit WebSocket event
            await self._emit_alert_updated(
                alert,
                updated_fields=updated_fields,
                correlation_id=correlation_id,
            )

            logger.debug(
                f"Updated alert {alert_id}",
                extra={
                    "alert_id": alert_id,
                    "updated_fields": updated_fields,
                },
            )

        return alert

    async def delete_alert(
        self,
        alert_id: str,
        *,
        reason: str | None = None,
        correlation_id: str | None = None,
    ) -> bool:
        """Delete an alert and emit alert.deleted event.

        Args:
            alert_id: Alert UUID to delete.
            reason: Optional reason for deletion.
            correlation_id: Optional correlation ID for request tracing.

        Returns:
            True if alert was deleted, False if not found.

        Raises:
            SQLAlchemy exceptions on database errors.
        """
        alert = await self.get_alert(alert_id)
        if alert is None:
            return False

        # Capture alert ID before deletion
        deleted_id = alert.id

        await self._session.delete(alert)
        await self._session.flush()

        # Emit WebSocket event
        await self._emit_alert_deleted(
            deleted_id,
            reason=reason,
            correlation_id=correlation_id,
        )

        logger.debug(
            f"Deleted alert {deleted_id}",
            extra={
                "alert_id": deleted_id,
                "reason": reason,
            },
        )

        return True

    async def acknowledge_alert(
        self,
        alert_id: str,
        *,
        correlation_id: str | None = None,
    ) -> Alert | None:
        """Acknowledge an alert and emit alert.updated event.

        Sets the alert status to ACKNOWLEDGED and records the acknowledgment time
        in metadata.

        Args:
            alert_id: Alert UUID to acknowledge.
            correlation_id: Optional correlation ID for request tracing.

        Returns:
            Updated Alert instance if found, None otherwise.

        Raises:
            SQLAlchemy exceptions on database errors.
        """
        alert = await self.get_alert(alert_id)
        if alert is None:
            return None

        # Update status
        alert.status = AlertStatus.ACKNOWLEDGED

        # Update metadata with acknowledgment time
        if alert.alert_metadata is None:
            alert.alert_metadata = {}
        alert.alert_metadata["acknowledged_at"] = datetime.now(UTC).isoformat()

        await self._session.flush()
        await self._session.refresh(alert)

        # Emit WebSocket event with acknowledged=True flag
        await self._emit_alert_updated(
            alert,
            updated_fields=["status"],
            acknowledged=True,
            correlation_id=correlation_id,
        )

        # Trigger outbound webhooks for ALERT_ACKNOWLEDGED event (NEM-3624)
        await self._trigger_webhook(
            WebhookEventType.ALERT_ACKNOWLEDGED,
            self._build_alert_webhook_data(alert),
            alert.id,
        )

        logger.debug(
            f"Acknowledged alert {alert_id}",
            extra={"alert_id": alert_id},
        )

        return alert

    async def dismiss_alert(
        self,
        alert_id: str,
        *,
        reason: str | None = None,
        correlation_id: str | None = None,
    ) -> Alert | None:
        """Dismiss an alert and emit alert.updated event.

        Sets the alert status to DISMISSED and optionally records the reason.

        Args:
            alert_id: Alert UUID to dismiss.
            reason: Optional dismissal reason.
            correlation_id: Optional correlation ID for request tracing.

        Returns:
            Updated Alert instance if found, None otherwise.

        Raises:
            SQLAlchemy exceptions on database errors.
        """
        alert = await self.get_alert(alert_id)
        if alert is None:
            return None

        # Update status
        alert.status = AlertStatus.DISMISSED

        # Update metadata
        if alert.alert_metadata is None:
            alert.alert_metadata = {}
        alert.alert_metadata["dismissed_at"] = datetime.now(UTC).isoformat()
        if reason:
            alert.alert_metadata["dismissed_reason"] = reason

        await self._session.flush()
        await self._session.refresh(alert)

        # Emit WebSocket event
        await self._emit_alert_updated(
            alert,
            updated_fields=["status"],
            correlation_id=correlation_id,
        )

        # Trigger outbound webhooks for ALERT_DISMISSED event (NEM-3624)
        webhook_data = self._build_alert_webhook_data(alert)
        if reason:
            webhook_data["dismissed_reason"] = reason
        await self._trigger_webhook(
            WebhookEventType.ALERT_DISMISSED,
            webhook_data,
            alert.id,
        )

        logger.debug(
            f"Dismissed alert {alert_id}",
            extra={"alert_id": alert_id, "reason": reason},
        )

        return alert

    # =========================================================================
    # WebSocket Event Emission Helpers
    # =========================================================================

    async def _emit_alert_created(
        self,
        alert: Alert,
        *,
        correlation_id: str | None = None,
    ) -> None:
        """Emit alert.created WebSocket event.

        Args:
            alert: Created alert instance.
            correlation_id: Optional correlation ID for request tracing.
        """
        if self._emitter is None:
            logger.debug("No emitter configured, skipping alert.created emission")
            return

        payload = self._build_alert_created_payload(alert)

        try:
            await self._emitter.broadcast(
                WebSocketEventType.ALERT_CREATED,
                payload,
                correlation_id=correlation_id,
            )
        except Exception as e:
            # Log but don't fail the operation if emission fails
            logger.warning(
                f"Failed to emit alert.created event: {e}",
                extra={"alert_id": alert.id},
            )

    async def _emit_alert_updated(
        self,
        alert: Alert,
        *,
        updated_fields: list[str] | None = None,
        acknowledged: bool = False,
        correlation_id: str | None = None,
    ) -> None:
        """Emit alert.updated WebSocket event.

        Args:
            alert: Updated alert instance.
            updated_fields: List of fields that were updated.
            acknowledged: Whether this update is an acknowledgment.
            correlation_id: Optional correlation ID for request tracing.
        """
        if self._emitter is None:
            logger.debug("No emitter configured, skipping alert.updated emission")
            return

        payload = self._build_alert_updated_payload(
            alert,
            updated_fields=updated_fields,
            acknowledged=acknowledged,
        )

        try:
            await self._emitter.broadcast(
                WebSocketEventType.ALERT_UPDATED,
                payload,
                correlation_id=correlation_id,
            )
        except Exception as e:
            # Log but don't fail the operation if emission fails
            logger.warning(
                f"Failed to emit alert.updated event: {e}",
                extra={"alert_id": alert.id},
            )

    async def _emit_alert_deleted(
        self,
        alert_id: str,
        *,
        reason: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Emit alert.deleted WebSocket event.

        Args:
            alert_id: Deleted alert UUID.
            reason: Optional deletion reason.
            correlation_id: Optional correlation ID for request tracing.
        """
        if self._emitter is None:
            logger.debug("No emitter configured, skipping alert.deleted emission")
            return

        payload = {
            "id": alert_id,
            "reason": reason,
        }

        try:
            await self._emitter.broadcast(
                WebSocketEventType.ALERT_DELETED,
                payload,
                correlation_id=correlation_id,
            )
        except Exception as e:
            # Log but don't fail the operation if emission fails
            logger.warning(
                f"Failed to emit alert.deleted event: {e}",
                extra={"alert_id": alert_id},
            )

    # =========================================================================
    # Payload Builders
    # =========================================================================

    def _build_alert_created_payload(self, alert: Alert) -> dict[str, Any]:
        """Build payload for alert.created event.

        Args:
            alert: Alert instance.

        Returns:
            Payload dictionary matching AlertCreatedPayload schema.
        """
        return {
            "id": alert.id,
            "event_id": alert.event_id,
            "rule_id": alert.rule_id,
            "severity": alert.severity.value
            if hasattr(alert.severity, "value")
            else alert.severity,
            "status": alert.status.value if hasattr(alert.status, "value") else alert.status,
            "dedup_key": alert.dedup_key,
            "created_at": alert.created_at.isoformat()
            if alert.created_at
            else datetime.now(UTC).isoformat(),
            "updated_at": alert.updated_at.isoformat()
            if alert.updated_at
            else datetime.now(UTC).isoformat(),
        }

    def _build_alert_updated_payload(
        self,
        alert: Alert,
        *,
        updated_fields: list[str] | None = None,
        acknowledged: bool = False,
    ) -> dict[str, Any]:
        """Build payload for alert.updated event.

        Args:
            alert: Alert instance.
            updated_fields: List of fields that were updated.
            acknowledged: Whether this update is an acknowledgment.

        Returns:
            Payload dictionary matching AlertUpdatedPayload schema.
        """
        payload: dict[str, Any] = {
            "id": alert.id,
            "event_id": alert.event_id,
            "rule_id": alert.rule_id,
            "updated_at": alert.updated_at.isoformat()
            if alert.updated_at
            else datetime.now(UTC).isoformat(),
            "updated_fields": updated_fields,
        }

        # Include current values for updated fields
        if updated_fields:
            if "status" in updated_fields:
                payload["status"] = (
                    alert.status.value if hasattr(alert.status, "value") else alert.status
                )
            if "severity" in updated_fields:
                payload["severity"] = (
                    alert.severity.value if hasattr(alert.severity, "value") else alert.severity
                )

        # Add acknowledged flag if this is an acknowledgment
        if acknowledged:
            payload["acknowledged"] = True

        return payload

    # =========================================================================
    # Outbound Webhook Helpers (NEM-3624)
    # =========================================================================

    def _build_alert_webhook_data(self, alert: Alert) -> dict[str, Any]:
        """Build webhook payload data for an alert.

        Args:
            alert: Alert instance.

        Returns:
            Dictionary with alert data for webhook payload.
        """
        return {
            "alert_id": alert.id,
            "event_id": alert.event_id,
            "rule_id": alert.rule_id,
            "severity": alert.severity.value
            if hasattr(alert.severity, "value")
            else alert.severity,
            "status": alert.status.value if hasattr(alert.status, "value") else alert.status,
            "dedup_key": alert.dedup_key,
            "channels": alert.channels or [],
            "created_at": alert.created_at.isoformat()
            if alert.created_at
            else datetime.now(UTC).isoformat(),
        }

    async def _trigger_webhook(
        self,
        event_type: WebhookEventType,
        event_data: dict[str, Any],
        alert_id: str,
    ) -> None:
        """Trigger outbound webhooks for an event type.

        Webhook failures are logged but do not fail the main operation.

        Args:
            event_type: Type of webhook event to trigger.
            event_data: Data to include in webhook payload.
            alert_id: Alert ID for logging context.
        """
        try:
            webhook_service = get_webhook_service()
            await webhook_service.trigger_webhooks_for_event(
                self._session,
                event_type,
                event_data,
                event_id=alert_id,
            )
        except Exception as e:
            # Log but don't fail the main operation if webhook triggering fails
            logger.warning(
                f"Failed to trigger {event_type.value} webhooks: {e}",
                extra={"alert_id": alert_id, "event_type": event_type.value},
            )


# =============================================================================
# Factory Functions
# =============================================================================


async def get_alert_service(
    session: AsyncSession,
    emitter: WebSocketEmitterService | None = None,
) -> AlertService:
    """Get an AlertService instance.

    Args:
        session: Database session.
        emitter: Optional WebSocket emitter service.

    Returns:
        AlertService instance.
    """
    return AlertService(session, emitter)
