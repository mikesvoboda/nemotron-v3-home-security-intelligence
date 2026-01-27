"""WebhookService for outbound webhook management and delivery.

This module provides the WebhookService class for managing outbound webhooks
that send notifications to external systems when events occur in the application.

Features:
- CRUD operations for webhook configurations
- HTTP delivery with httpx async client
- Exponential backoff retry logic
- HMAC-SHA256 payload signing
- Custom payload templates via Jinja2
- Delivery tracking and statistics

Usage:
    from backend.services.webhook_service import WebhookService

    service = WebhookService()

    # Create webhook
    webhook = await service.create_webhook(db, WebhookCreate(...))

    # Trigger webhooks for an event
    deliveries = await service.trigger_webhooks_for_event(
        db,
        event_type=WebhookEventType.ALERT_FIRED,
        event_data={"alert_id": "...", "severity": "high"},
    )

    # Get delivery statistics
    health = await service.get_health_summary(db)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
from jinja2 import BaseLoader, Environment, TemplateSyntaxError, UndefinedError
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

# WebhookEventType is needed at runtime for trigger_webhook_background
from backend.api.schemas.outbound_webhook import WebhookEventType
from backend.core.logging import get_logger
from backend.core.time_utils import utc_now

if TYPE_CHECKING:
    from backend.api.schemas.outbound_webhook import (
        WebhookCreate,
        WebhookHealthSummary,
        WebhookTestResponse,
        WebhookUpdate,
    )
    from backend.models.outbound_webhook import (
        OutboundWebhook,
        WebhookDelivery,
    )

logger = get_logger(__name__)

# HTTP client timeout configuration
DEFAULT_TIMEOUT = 30.0  # seconds
MAX_RESPONSE_BODY_LENGTH = 2000  # characters to store

# Retry configuration
DEFAULT_MAX_RETRIES = 4
DEFAULT_RETRY_DELAY = 10  # seconds
BACKOFF_MULTIPLIER = 2
MAX_BACKOFF_SECONDS = 3600  # 1 hour maximum delay

# Jinja2 environment for payload templates
# Note: autoescape=False is intentional here because we're generating JSON payloads,
# not HTML. The output is serialized to JSON which handles escaping appropriately.
_jinja_env = Environment(loader=BaseLoader(), autoescape=False)  # noqa: S701  # nosemgrep


class WebhookService:
    """Service for outbound webhook management and delivery.

    This service handles all webhook operations including:
    - Creating, updating, and deleting webhook configurations
    - Delivering webhooks to external systems with retry logic
    - Tracking delivery statistics and health metrics
    - Testing webhook configurations

    Attributes:
        _http_client: Shared httpx async client for webhook delivery.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialize the webhook service.

        Args:
            http_client: Optional httpx async client. If not provided, a new
                client will be created for each request.
        """
        self._http_client = http_client

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def create_webhook(
        self,
        db: AsyncSession,
        data: WebhookCreate,
    ) -> OutboundWebhook:
        """Create a new webhook configuration.

        Generates a signing secret for HMAC-SHA256 payload signatures and
        stores the webhook configuration in the database.

        Args:
            db: Async database session.
            data: Webhook creation data.

        Returns:
            Created OutboundWebhook instance.

        Raises:
            SQLAlchemy exceptions on database errors.
        """
        # Import model here to avoid circular imports
        from backend.models.outbound_webhook import OutboundWebhook

        # Generate signing secret for HMAC signatures
        signing_secret = secrets.token_hex(32)

        webhook = OutboundWebhook(
            name=data.name,
            url=str(data.url),
            event_types=[et.value if hasattr(et, "value") else str(et) for et in data.event_types],
            integration_type=data.integration_type,
            enabled=data.enabled,
            auth_config=data.auth.model_dump() if data.auth else None,
            custom_headers=data.custom_headers or {},
            payload_template=data.payload_template,
            max_retries=data.max_retries,
            retry_delay_seconds=data.retry_delay_seconds,
            signing_secret=signing_secret,
        )

        db.add(webhook)
        await db.flush()
        await db.refresh(webhook)

        logger.info(
            f"Created webhook '{webhook.name}' (id={webhook.id})",
            extra={
                "webhook_id": webhook.id,
                "webhook_name": webhook.name,
                "event_types": webhook.event_types,
            },
        )

        return webhook

    async def get_webhook(
        self,
        db: AsyncSession,
        webhook_id: str,
    ) -> OutboundWebhook | None:
        """Get a webhook by ID.

        Args:
            db: Async database session.
            webhook_id: Webhook UUID.

        Returns:
            OutboundWebhook instance if found, None otherwise.
        """
        from backend.models.outbound_webhook import OutboundWebhook

        result = await db.execute(select(OutboundWebhook).where(OutboundWebhook.id == webhook_id))
        return result.scalar_one_or_none()

    async def list_webhooks(
        self,
        db: AsyncSession,
        enabled_only: bool = False,
    ) -> list[OutboundWebhook]:
        """List all webhooks.

        Args:
            db: Async database session.
            enabled_only: If True, only return enabled webhooks.

        Returns:
            List of OutboundWebhook instances.
        """
        from backend.models.outbound_webhook import OutboundWebhook

        query = select(OutboundWebhook)
        if enabled_only:
            query = query.where(OutboundWebhook.enabled.is_(True))

        query = query.order_by(OutboundWebhook.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_webhook(
        self,
        db: AsyncSession,
        webhook_id: str,
        data: WebhookUpdate,
    ) -> OutboundWebhook | None:
        """Update a webhook configuration.

        Only updates fields that are explicitly provided (not None).

        Args:
            db: Async database session.
            webhook_id: Webhook UUID to update.
            data: Update data with optional fields.

        Returns:
            Updated OutboundWebhook instance if found, None otherwise.

        Raises:
            SQLAlchemy exceptions on database errors.
        """
        webhook = await self.get_webhook(db, webhook_id)
        if webhook is None:
            return None

        updated_fields: list[str] = []

        if data.name is not None:
            webhook.name = data.name
            updated_fields.append("name")

        if data.url is not None:
            webhook.url = str(data.url)
            updated_fields.append("url")

        if data.event_types is not None:
            webhook.event_types = [
                et.value if hasattr(et, "value") else str(et) for et in data.event_types
            ]
            updated_fields.append("event_types")

        if data.integration_type is not None:
            webhook.integration_type = data.integration_type  # type: ignore[assignment]
            updated_fields.append("integration_type")

        if data.enabled is not None:
            webhook.enabled = data.enabled
            updated_fields.append("enabled")

        if data.auth is not None:
            webhook.auth_config = data.auth.model_dump()
            updated_fields.append("auth_config")

        if data.custom_headers is not None:
            webhook.custom_headers = data.custom_headers
            updated_fields.append("custom_headers")

        if data.payload_template is not None:
            webhook.payload_template = data.payload_template
            updated_fields.append("payload_template")

        if data.max_retries is not None:
            webhook.max_retries = data.max_retries
            updated_fields.append("max_retries")

        if data.retry_delay_seconds is not None:
            webhook.retry_delay_seconds = data.retry_delay_seconds
            updated_fields.append("retry_delay_seconds")

        if updated_fields:
            await db.flush()
            await db.refresh(webhook)

            logger.debug(
                f"Updated webhook {webhook_id}",
                extra={
                    "webhook_id": webhook_id,
                    "updated_fields": updated_fields,
                },
            )

        return webhook

    async def delete_webhook(
        self,
        db: AsyncSession,
        webhook_id: str,
    ) -> bool:
        """Delete a webhook.

        Cascades to delete all associated delivery records.

        Args:
            db: Async database session.
            webhook_id: Webhook UUID to delete.

        Returns:
            True if webhook was deleted, False if not found.

        Raises:
            SQLAlchemy exceptions on database errors.
        """
        webhook = await self.get_webhook(db, webhook_id)
        if webhook is None:
            return False

        await db.delete(webhook)
        await db.flush()

        logger.info(
            f"Deleted webhook {webhook_id}",
            extra={"webhook_id": webhook_id},
        )

        return True

    # =========================================================================
    # Delivery Operations
    # =========================================================================

    async def deliver_webhook(
        self,
        db: AsyncSession,
        webhook: OutboundWebhook,
        event_type: WebhookEventType,
        event_data: dict[str, Any],
        event_id: str | None = None,
    ) -> WebhookDelivery:
        """Deliver a webhook notification.

        Creates a delivery record and sends the HTTP request. On failure,
        schedules a retry if retries are configured.

        Args:
            db: Async database session.
            webhook: Webhook configuration.
            event_type: Type of event triggering the webhook.
            event_data: Event data to include in payload.
            event_id: Optional related event ID for tracking.

        Returns:
            WebhookDelivery record with delivery status.

        Raises:
            SQLAlchemy exceptions on database errors.
        """
        from backend.models.outbound_webhook import WebhookDelivery, WebhookDeliveryStatus

        # Build payload
        payload = self._build_payload(webhook, event_type, event_data)

        # Create delivery record
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event_type=event_type.value if hasattr(event_type, "value") else str(event_type),
            event_id=event_id,
            status=WebhookDeliveryStatus.PENDING,
            request_payload=payload,
            attempt_count=1,
        )

        db.add(delivery)
        await db.flush()

        # Send request
        try:
            status_code, response_body, response_time_ms = await self._send_request(
                webhook, payload
            )

            if 200 <= status_code < 300:
                # Success
                delivery.status = WebhookDeliveryStatus.SUCCESS
                delivery.status_code = status_code
                delivery.response_body = response_body[:MAX_RESPONSE_BODY_LENGTH]
                delivery.response_time_ms = response_time_ms
                delivery.delivered_at = utc_now()

                # Update webhook stats
                webhook.total_deliveries += 1
                webhook.successful_deliveries += 1
                webhook.last_delivery_at = utc_now()
                webhook.last_delivery_status = WebhookDeliveryStatus.SUCCESS.value

                logger.debug(
                    f"Webhook delivered successfully: {webhook.id} -> {webhook.url}",
                    extra={
                        "webhook_id": webhook.id,
                        "delivery_id": delivery.id,
                        "status_code": status_code,
                        "response_time_ms": response_time_ms,
                    },
                )
            else:
                # HTTP error - schedule retry
                delivery.status_code = status_code
                delivery.response_body = response_body[:MAX_RESPONSE_BODY_LENGTH]
                delivery.response_time_ms = response_time_ms
                delivery.error_message = f"HTTP {status_code}"

                await self._handle_delivery_failure(db, webhook, delivery)

        except httpx.RequestError as e:
            # Network error - schedule retry
            delivery.error_message = str(e)[:500]
            await self._handle_delivery_failure(db, webhook, delivery)

        except Exception as e:
            # Unexpected error
            delivery.status = WebhookDeliveryStatus.FAILED
            delivery.error_message = str(e)[:500]
            webhook.total_deliveries += 1
            webhook.last_delivery_at = utc_now()
            webhook.last_delivery_status = WebhookDeliveryStatus.FAILED.value

            logger.error(
                f"Webhook delivery failed unexpectedly: {e}",
                extra={
                    "webhook_id": webhook.id,
                    "delivery_id": delivery.id,
                },
                exc_info=True,
            )

        await db.flush()
        await db.refresh(delivery)

        return delivery

    async def _handle_delivery_failure(
        self,
        db: AsyncSession,  # noqa: ARG002 - kept for API consistency
        webhook: OutboundWebhook,
        delivery: WebhookDelivery,
    ) -> None:
        """Handle delivery failure, scheduling retry if applicable.

        Args:
            db: Async database session (unused but kept for consistency).
            webhook: Webhook configuration.
            delivery: Delivery record that failed.
        """
        from backend.models.outbound_webhook import WebhookDeliveryStatus

        if delivery.attempt_count < webhook.max_retries:
            # Schedule retry
            delivery.status = WebhookDeliveryStatus.RETRYING
            delivery.next_retry_at = self._calculate_next_retry(
                delivery.attempt_count,
                webhook.retry_delay_seconds,
            )

            logger.warning(
                f"Webhook delivery failed, scheduling retry {delivery.attempt_count + 1}/{webhook.max_retries}",
                extra={
                    "webhook_id": webhook.id,
                    "delivery_id": delivery.id,
                    "next_retry_at": delivery.next_retry_at.isoformat(),
                    "error": delivery.error_message,
                },
            )
        else:
            # Max retries exhausted
            delivery.status = WebhookDeliveryStatus.FAILED

            logger.error(
                f"Webhook delivery failed after {delivery.attempt_count} attempts",
                extra={
                    "webhook_id": webhook.id,
                    "delivery_id": delivery.id,
                    "error": delivery.error_message,
                },
            )

        # Update webhook stats
        webhook.total_deliveries += 1
        webhook.last_delivery_at = utc_now()
        webhook.last_delivery_status = delivery.status.value

    async def trigger_webhooks_for_event(
        self,
        db: AsyncSession,
        event_type: WebhookEventType,
        event_data: dict[str, Any],
        event_id: str | None = None,
    ) -> list[WebhookDelivery]:
        """Trigger all webhooks subscribed to an event type.

        Finds all enabled webhooks that subscribe to the given event type
        and delivers the event to each one.

        Args:
            db: Async database session.
            event_type: Type of event that occurred.
            event_data: Event data to include in payload.
            event_id: Optional related event ID for tracking.

        Returns:
            List of WebhookDelivery records.
        """
        from backend.models.outbound_webhook import OutboundWebhook

        # Find enabled webhooks subscribed to this event type
        event_type_value = event_type.value if hasattr(event_type, "value") else str(event_type)

        result = await db.execute(
            select(OutboundWebhook).where(
                and_(
                    OutboundWebhook.enabled.is_(True),
                    OutboundWebhook.event_types.any(event_type_value),  # type: ignore[arg-type]
                )
            )
        )
        webhooks = list(result.scalars().all())

        if not webhooks:
            logger.debug(
                f"No webhooks subscribed to event type: {event_type_value}",
                extra={"event_type": event_type_value},
            )
            return []

        logger.info(
            f"Triggering {len(webhooks)} webhooks for event type: {event_type_value}",
            extra={
                "event_type": event_type_value,
                "webhook_count": len(webhooks),
            },
        )

        # Deliver to each webhook
        deliveries: list[WebhookDelivery] = []
        for webhook in webhooks:
            delivery = await self.deliver_webhook(
                db,
                webhook,
                event_type,
                event_data,
                event_id,
            )
            deliveries.append(delivery)

        return deliveries

    async def test_webhook(
        self,
        db: AsyncSession,
        webhook_id: str,
        event_type: WebhookEventType,
    ) -> WebhookTestResponse:
        """Test a webhook with sample data.

        Sends a test payload to the webhook URL without creating a delivery
        record in the database.

        Args:
            db: Async database session.
            webhook_id: Webhook UUID to test.
            event_type: Event type for the test payload.

        Returns:
            WebhookTestResponse with test results.
        """
        from backend.api.schemas.outbound_webhook import WebhookTestResponse

        webhook = await self.get_webhook(db, webhook_id)
        if webhook is None:
            return WebhookTestResponse(
                success=False,
                error_message="Webhook not found",
            )

        # Build test payload
        test_data = self._build_test_event_data(event_type)
        payload = self._build_payload(webhook, event_type, test_data)

        # Send request
        try:
            status_code, response_body, response_time_ms = await self._send_request(
                webhook, payload
            )

            success = 200 <= status_code < 300

            return WebhookTestResponse(
                success=success,
                status_code=status_code,
                response_time_ms=response_time_ms,
                response_body=response_body[:MAX_RESPONSE_BODY_LENGTH] if response_body else None,
                error_message=None if success else f"HTTP {status_code}",
            )

        except httpx.RequestError as e:
            return WebhookTestResponse(
                success=False,
                error_message=str(e)[:500],
            )

        except Exception as e:
            return WebhookTestResponse(
                success=False,
                error_message=f"Unexpected error: {e!s}"[:500],
            )

    async def retry_delivery(
        self,
        db: AsyncSession,
        delivery_id: str,
    ) -> WebhookDelivery | None:
        """Manually retry a failed delivery.

        Resets the delivery status and immediately attempts redelivery.

        Args:
            db: Async database session.
            delivery_id: Delivery UUID to retry.

        Returns:
            Updated WebhookDelivery instance if found, None otherwise.
        """
        from backend.models.outbound_webhook import (
            WebhookDelivery,
            WebhookDeliveryStatus,
        )

        result = await db.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id))
        delivery = result.scalar_one_or_none()

        if delivery is None:
            return None

        # Get webhook
        webhook = await self.get_webhook(db, delivery.webhook_id)
        if webhook is None:
            return None

        # Reset delivery for retry
        delivery.attempt_count += 1
        delivery.status = WebhookDeliveryStatus.PENDING
        delivery.error_message = None
        delivery.next_retry_at = None

        # Rebuild payload from stored data
        payload = delivery.request_payload or {}

        # Send request
        try:
            status_code, response_body, response_time_ms = await self._send_request(
                webhook, payload
            )

            if 200 <= status_code < 300:
                delivery.status = WebhookDeliveryStatus.SUCCESS
                delivery.status_code = status_code
                delivery.response_body = response_body[:MAX_RESPONSE_BODY_LENGTH]
                delivery.response_time_ms = response_time_ms
                delivery.delivered_at = utc_now()

                webhook.successful_deliveries += 1
                webhook.last_delivery_status = WebhookDeliveryStatus.SUCCESS.value
            else:
                delivery.status = WebhookDeliveryStatus.FAILED
                delivery.status_code = status_code
                delivery.response_body = response_body[:MAX_RESPONSE_BODY_LENGTH]
                delivery.response_time_ms = response_time_ms
                delivery.error_message = f"HTTP {status_code}"

                webhook.last_delivery_status = WebhookDeliveryStatus.FAILED.value

        except httpx.RequestError as e:
            delivery.status = WebhookDeliveryStatus.FAILED
            delivery.error_message = str(e)[:500]
            webhook.last_delivery_status = WebhookDeliveryStatus.FAILED.value

        webhook.total_deliveries += 1
        webhook.last_delivery_at = utc_now()

        await db.flush()
        await db.refresh(delivery)

        return delivery

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_health_summary(
        self,
        db: AsyncSession,
    ) -> WebhookHealthSummary:
        """Get webhook health summary for dashboard.

        Calculates aggregate statistics across all webhooks including
        total counts, success rates, and average response times.

        Args:
            db: Async database session.

        Returns:
            WebhookHealthSummary with aggregate statistics.
        """
        from backend.api.schemas.outbound_webhook import WebhookHealthSummary
        from backend.models.outbound_webhook import (
            OutboundWebhook,
            WebhookDelivery,
            WebhookDeliveryStatus,
        )

        # Get webhook counts
        total_result = await db.execute(select(func.count()).select_from(OutboundWebhook))
        total_webhooks = total_result.scalar() or 0

        enabled_result = await db.execute(
            select(func.count())
            .select_from(OutboundWebhook)
            .where(OutboundWebhook.enabled.is_(True))
        )
        enabled_webhooks = enabled_result.scalar() or 0

        # Get delivery stats from the last 24 hours
        cutoff = utc_now() - timedelta(hours=24)

        deliveries_24h_result = await db.execute(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(WebhookDelivery.created_at >= cutoff)
        )
        total_deliveries_24h = deliveries_24h_result.scalar() or 0

        successful_24h_result = await db.execute(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(
                and_(
                    WebhookDelivery.created_at >= cutoff,
                    WebhookDelivery.status == WebhookDeliveryStatus.SUCCESS,
                )
            )
        )
        successful_deliveries_24h = successful_24h_result.scalar() or 0

        failed_24h_result = await db.execute(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(
                and_(
                    WebhookDelivery.created_at >= cutoff,
                    WebhookDelivery.status == WebhookDeliveryStatus.FAILED,
                )
            )
        )
        failed_deliveries_24h = failed_24h_result.scalar() or 0

        # Calculate average response time
        avg_response_result = await db.execute(
            select(func.avg(WebhookDelivery.response_time_ms)).where(
                and_(
                    WebhookDelivery.created_at >= cutoff,
                    WebhookDelivery.response_time_ms.is_not(None),
                )
            )
        )
        avg_response_time = avg_response_result.scalar()

        # Calculate healthy/unhealthy webhook counts
        # Healthy: >90% success rate, Unhealthy: <50% success rate
        webhooks = await self.list_webhooks(db)
        healthy_count = 0
        unhealthy_count = 0

        for webhook in webhooks:
            if webhook.total_deliveries > 0:
                success_rate = webhook.successful_deliveries / webhook.total_deliveries
                if success_rate >= 0.9:
                    healthy_count += 1
                elif success_rate < 0.5:
                    unhealthy_count += 1

        return WebhookHealthSummary(
            total_webhooks=total_webhooks,
            enabled_webhooks=enabled_webhooks,
            healthy_webhooks=healthy_count,
            unhealthy_webhooks=unhealthy_count,
            total_deliveries_24h=total_deliveries_24h,
            successful_deliveries_24h=successful_deliveries_24h,
            failed_deliveries_24h=failed_deliveries_24h,
            average_response_time_ms=float(avg_response_time) if avg_response_time else None,
        )

    async def get_deliveries(
        self,
        db: AsyncSession,
        webhook_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WebhookDelivery], int]:
        """Get delivery history for a webhook.

        Args:
            db: Async database session.
            webhook_id: Webhook UUID.
            limit: Maximum number of deliveries to return.
            offset: Number of deliveries to skip.

        Returns:
            Tuple of (list of deliveries, total count).
        """
        from backend.models.outbound_webhook import WebhookDelivery

        # Get total count
        count_result = await db.execute(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == webhook_id)
        )
        total = count_result.scalar() or 0

        # Get deliveries
        result = await db.execute(
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == webhook_id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        deliveries = list(result.scalars().all())

        return deliveries, total

    async def get_delivery(
        self,
        db: AsyncSession,
        delivery_id: str,
    ) -> WebhookDelivery | None:
        """Get a delivery by ID.

        Args:
            db: Async database session.
            delivery_id: Delivery UUID.

        Returns:
            WebhookDelivery instance if found, None otherwise.
        """
        from backend.models.outbound_webhook import WebhookDelivery

        result = await db.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id))
        return result.scalar_one_or_none()

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _build_payload(
        self,
        webhook: OutboundWebhook,
        event_type: WebhookEventType,
        event_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Build webhook payload, applying template if configured.

        If a custom payload template is set, renders it with Jinja2.
        Otherwise, builds a standard payload with event metadata.

        Args:
            webhook: Webhook configuration.
            event_type: Type of event.
            event_data: Event-specific data.

        Returns:
            Payload dictionary to send.
        """
        event_type_value = event_type.value if hasattr(event_type, "value") else str(event_type)

        # Standard payload structure
        standard_payload = {
            "event_type": event_type_value,
            "timestamp": utc_now().isoformat(),
            "webhook_id": webhook.id,
            "data": event_data,
        }

        if not webhook.payload_template:
            return self._format_for_integration(webhook, standard_payload)

        # Render custom template
        try:
            template = _jinja_env.from_string(webhook.payload_template)
            rendered = template.render(
                event_type=event_type_value,
                timestamp=standard_payload["timestamp"],
                webhook_id=webhook.id,
                data=event_data,
                **event_data,  # Allow direct access to event_data fields
            )
            # Parse rendered JSON
            result: dict[str, Any] = json.loads(rendered)
            return result

        except (TemplateSyntaxError, UndefinedError, json.JSONDecodeError) as e:
            logger.warning(
                f"Failed to render payload template, using standard payload: {e}",
                extra={"webhook_id": webhook.id},
            )
            return self._format_for_integration(webhook, standard_payload)

    def _format_for_integration(
        self,
        webhook: OutboundWebhook,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Format payload for specific integration types.

        Applies integration-specific formatting for Slack, Discord, etc.

        Args:
            webhook: Webhook configuration with integration type.
            payload: Standard payload to format.

        Returns:
            Formatted payload for the integration.
        """
        integration = (
            webhook.integration_type.value
            if hasattr(webhook.integration_type, "value")
            else str(webhook.integration_type)
        )

        if integration == "slack":
            return self._format_slack_payload(payload)
        elif integration == "discord":
            return self._format_discord_payload(payload)
        elif integration == "teams":
            return self._format_teams_payload(payload)

        # Generic - return as-is
        return payload

    def _format_slack_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Format payload for Slack webhook API.

        Args:
            payload: Standard payload.

        Returns:
            Slack-formatted payload with blocks.
        """
        event_type = payload.get("event_type", "event")
        data = payload.get("data", {})

        # Build text summary
        text = f"*{event_type}*\n"
        for key, value in data.items():
            if isinstance(value, str | int | float | bool):
                text += f"- {key}: {value}\n"

        return {
            "text": text,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text,
                    },
                },
            ],
        }

    def _format_discord_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Format payload for Discord webhook API.

        Args:
            payload: Standard payload.

        Returns:
            Discord-formatted payload with embeds.
        """
        event_type = payload.get("event_type", "event")
        data = payload.get("data", {})
        timestamp = payload.get("timestamp", utc_now().isoformat())

        # Build fields from data
        fields = []
        for key, value in data.items():
            if isinstance(value, str | int | float | bool):
                fields.append(
                    {
                        "name": key.replace("_", " ").title(),
                        "value": str(value),
                        "inline": True,
                    }
                )

        return {
            "embeds": [
                {
                    "title": event_type.replace("_", " ").title(),
                    "timestamp": timestamp,
                    "fields": fields[:25],  # Discord limit
                },
            ],
        }

    def _format_teams_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Format payload for Microsoft Teams webhook API.

        Args:
            payload: Standard payload.

        Returns:
            Teams-formatted adaptive card payload.
        """
        event_type = payload.get("event_type", "event")
        data = payload.get("data", {})

        # Build facts from data
        facts = []
        for key, value in data.items():
            if isinstance(value, str | int | float | bool):
                facts.append(
                    {
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                    }
                )

        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": event_type,
            "themeColor": "0076D7",
            "title": event_type.replace("_", " ").title(),
            "sections": [
                {
                    "facts": facts[:10],  # Reasonable limit
                },
            ],
        }

    def _sign_payload(self, payload: dict[str, Any], secret: str) -> str:
        """Generate HMAC-SHA256 signature for payload.

        Creates a signature that can be used by webhook consumers to verify
        the authenticity and integrity of the payload.

        Args:
            payload: Payload dictionary to sign.
            secret: Signing secret (hex string).

        Returns:
            Hex-encoded HMAC-SHA256 signature.
        """
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        secret_bytes = bytes.fromhex(secret)

        signature = hmac.new(
            secret_bytes,
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return signature

    async def _send_request(
        self,
        webhook: OutboundWebhook,
        payload: dict[str, Any],
    ) -> tuple[int, str, int]:
        """Send HTTP request to webhook URL.

        Applies authentication, custom headers, and signing before sending.

        Args:
            webhook: Webhook configuration.
            payload: Payload to send.

        Returns:
            Tuple of (status_code, response_body, response_time_ms).

        Raises:
            httpx.RequestError: On network errors.
        """
        # Build headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "NemotronWebhook/1.0",
        }

        # Add custom headers
        if webhook.custom_headers:
            headers.update(webhook.custom_headers)

        # Add authentication
        if webhook.auth_config:
            auth_type = webhook.auth_config.get("type", "none")

            if auth_type == "bearer":
                token = webhook.auth_config.get("token", "")
                headers["Authorization"] = f"Bearer {token}"
            elif auth_type == "basic":
                username = webhook.auth_config.get("username", "")
                password = webhook.auth_config.get("password", "")
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {credentials}"
            elif auth_type == "header":
                header_name = webhook.auth_config.get("header_name", "")
                header_value = webhook.auth_config.get("header_value", "")
                if header_name:
                    headers[header_name] = header_value

        # Add signature
        if webhook.signing_secret:
            signature = self._sign_payload(payload, webhook.signing_secret)
            headers["X-Webhook-Signature"] = f"sha256={signature}"
            headers["X-Webhook-Signature-256"] = signature

        # Send request
        start_time = datetime.now(UTC)

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                webhook.url,
                json=payload,
                headers=headers,
            )

        end_time = datetime.now(UTC)
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)

        return response.status_code, response.text, response_time_ms

    def _calculate_next_retry(self, attempt: int, base_delay: int) -> datetime:
        """Calculate next retry time with exponential backoff.

        Uses exponential backoff with a cap to prevent excessively long delays.

        Args:
            attempt: Current attempt number (1-based).
            base_delay: Base delay in seconds.

        Returns:
            Datetime for next retry attempt.
        """
        # Exponential backoff: base_delay * 2^(attempt-1)
        delay_seconds = base_delay * (BACKOFF_MULTIPLIER ** (attempt - 1))

        # Cap at maximum
        delay_seconds = min(delay_seconds, MAX_BACKOFF_SECONDS)

        return utc_now() + timedelta(seconds=delay_seconds)

    def _build_test_event_data(self, event_type: WebhookEventType) -> dict[str, Any]:
        """Build sample event data for testing.

        Creates realistic test data based on the event type.

        Args:
            event_type: Event type to generate data for.

        Returns:
            Sample event data dictionary.
        """
        event_type_value = event_type.value if hasattr(event_type, "value") else str(event_type)

        base_data: dict[str, Any] = {
            "test": True,
            "timestamp": utc_now().isoformat(),
        }

        # Event-specific test data lookup
        event_specific_data: dict[str, dict[str, Any]] = {
            "alert_fired": {
                "alert_id": "test-alert-001",
                "severity": "high",
                "camera_id": "front_door",
                "description": "Test alert triggered",
            },
            "alert_dismissed": {
                "alert_id": "test-alert-001",
            },
            "alert_acknowledged": {
                "alert_id": "test-alert-001",
            },
            "event_created": {
                "event_id": "test-event-001",
                "camera_id": "front_door",
                "event_type": "motion_detected",
            },
            "event_enriched": {
                "event_id": "test-event-001",
                "enrichment_type": "person_detection",
                "confidence": 0.95,
            },
            "entity_discovered": {
                "entity_id": "test-entity-001",
                "entity_type": "person",
                "label": "Unknown Person",
            },
            "anomaly_detected": {
                "anomaly_id": "test-anomaly-001",
                "zone_id": "driveway",
                "anomaly_type": "unusual_activity",
                "score": 0.87,
            },
            "system_health_changed": {
                "component": "ai-yolo26",
                "status": "degraded",
                "message": "High latency detected",
            },
        }

        specific_data = event_specific_data.get(event_type_value, {})
        return {**base_data, **specific_data}


# =============================================================================
# Singleton Instance
# =============================================================================


class _WebhookServiceHolder:
    """Holder class for singleton WebhookService instance."""

    instance: WebhookService | None = None


def get_webhook_service() -> WebhookService:
    """Get the singleton WebhookService instance.

    Returns:
        WebhookService instance.
    """
    if _WebhookServiceHolder.instance is None:
        _WebhookServiceHolder.instance = WebhookService()
    return _WebhookServiceHolder.instance


async def trigger_webhook_background(
    db: AsyncSession,
    event_type: WebhookEventType,
    event_data: dict[str, Any],
    event_id: str | None = None,
) -> None:
    """Trigger webhooks for an event type in background task context.

    This function is designed to be called from FastAPI background tasks
    to ensure webhook delivery doesn't block the main request.

    Failures are logged but do not raise exceptions to prevent
    background task crashes.

    Args:
        db: Async database session.
        event_type: Type of event that occurred.
        event_data: Event data to include in payload.
        event_id: Optional related event ID for tracking.
    """
    try:
        webhook_service = get_webhook_service()
        await webhook_service.trigger_webhooks_for_event(
            db,
            event_type,
            event_data,
            event_id=event_id,
        )
    except Exception as e:
        # Log but don't raise - background tasks should fail gracefully
        logger.warning(
            f"Background webhook trigger failed for {event_type.value}: {e}",
            extra={"event_type": event_type.value, "event_id": event_id},
        )
