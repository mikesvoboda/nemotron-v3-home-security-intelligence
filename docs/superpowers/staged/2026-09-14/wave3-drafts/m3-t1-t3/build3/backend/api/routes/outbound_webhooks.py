"""API routes for outbound webhook management (NEM-3624).

This module provides endpoints for managing outbound webhooks that send
notifications to external systems when events occur in the security system.

Note: The existing `backend/api/routes/webhooks.py` handles INCOMING webhooks
from Alertmanager. This module handles OUTBOUND webhook management for sending
notifications to external systems (Slack, Discord, Teams, etc.).

Webhook CRUD Endpoints:
    POST   /api/outbound-webhooks              - Create webhook
    GET    /api/outbound-webhooks              - List webhooks
    GET    /api/outbound-webhooks/{id}         - Get webhook by ID
    PATCH  /api/outbound-webhooks/{id}         - Update webhook
    DELETE /api/outbound-webhooks/{id}         - Delete webhook

Webhook Operations:
    POST   /api/outbound-webhooks/{id}/test    - Test webhook with sample payload
    POST   /api/outbound-webhooks/{id}/enable  - Enable webhook
    POST   /api/outbound-webhooks/{id}/disable - Disable webhook

Delivery Logs:
    GET    /api/outbound-webhooks/{id}/deliveries           - List deliveries for webhook
    GET    /api/outbound-webhooks/deliveries/{delivery_id}  - Get delivery details

Health:
    GET    /api/outbound-webhooks/health       - Get webhook health summary

Retry:
    POST   /api/outbound-webhooks/deliveries/{delivery_id}/retry - Retry failed delivery
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.outbound_webhook import (
    IntegrationType,
    WebhookCreate,
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookDeliveryStatus,
    WebhookEventType,
    WebhookHealthSummary,
    WebhookListResponse,
    WebhookResponse,
    WebhookTestRequest,
    WebhookTestResponse,
    WebhookUpdate,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.services.webhook_service import WebhookService

if TYPE_CHECKING:
    from backend.models.outbound_webhook import OutboundWebhook, WebhookDelivery

logger = get_logger(__name__)

router = APIRouter(prefix="/api/outbound-webhooks", tags=["outbound-webhooks"])


# =============================================================================
# Dependency Injection
# =============================================================================


def get_webhook_service() -> WebhookService:
    """Get WebhookService instance for dependency injection.

    Returns:
        WebhookService instance
    """
    return WebhookService()


# =============================================================================
# Helper Functions
# =============================================================================


def _webhook_to_response(webhook: OutboundWebhook) -> WebhookResponse:
    """Convert an OutboundWebhook model to WebhookResponse schema.

    Args:
        webhook: OutboundWebhook database model instance.

    Returns:
        WebhookResponse schema instance.
    """
    # Convert string event types to enum values
    event_types = [WebhookEventType(et) for et in webhook.event_types]

    # Convert integration type
    integration_type = (
        IntegrationType(webhook.integration_type.value)
        if hasattr(webhook.integration_type, "value")
        else IntegrationType(webhook.integration_type)
    )

    # Convert last delivery status if present
    last_delivery_status = None
    if webhook.last_delivery_status:
        last_delivery_status = WebhookDeliveryStatus(webhook.last_delivery_status)

    return WebhookResponse(
        id=webhook.id,
        name=webhook.name,
        url=webhook.url,
        event_types=event_types,
        integration_type=integration_type,
        enabled=webhook.enabled,
        custom_headers=webhook.custom_headers or {},
        payload_template=webhook.payload_template,
        max_retries=webhook.max_retries,
        retry_delay_seconds=webhook.retry_delay_seconds,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
        total_deliveries=webhook.total_deliveries,
        successful_deliveries=webhook.successful_deliveries,
        last_delivery_at=webhook.last_delivery_at,
        last_delivery_status=last_delivery_status,
    )


def _delivery_to_response(delivery: WebhookDelivery) -> WebhookDeliveryResponse:
    """Convert a WebhookDelivery model to WebhookDeliveryResponse schema.

    Args:
        delivery: WebhookDelivery database model instance.

    Returns:
        WebhookDeliveryResponse schema instance.
    """
    # Convert event type
    event_type = WebhookEventType(delivery.event_type)

    # Convert status
    status_val = (
        WebhookDeliveryStatus(delivery.status.value)
        if hasattr(delivery.status, "value")
        else WebhookDeliveryStatus(delivery.status)
    )

    return WebhookDeliveryResponse(
        id=delivery.id,
        webhook_id=delivery.webhook_id,
        event_type=event_type,
        event_id=delivery.event_id,
        status=status_val,
        status_code=delivery.status_code,
        response_time_ms=delivery.response_time_ms,
        error_message=delivery.error_message,
        attempt_count=delivery.attempt_count,
        next_retry_at=delivery.next_retry_at,
        created_at=delivery.created_at,
        delivered_at=delivery.delivered_at,
    )


async def _get_webhook_or_404(
    webhook_id: str,
    db: AsyncSession,
    webhook_service: WebhookService,
) -> OutboundWebhook:
    """Get a webhook by ID or raise 404 if not found.

    Args:
        webhook_id: The webhook UUID to look up.
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        OutboundWebhook model if found.

    Raises:
        HTTPException: 404 if webhook not found.
    """
    webhook = await webhook_service.get_webhook(db, webhook_id)

    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with id {webhook_id} not found",
        )

    return webhook


# =============================================================================
# Health Endpoint (defined first to avoid path conflicts)
# =============================================================================


@router.get(
    "/health",
    response_model=WebhookHealthSummary,
    summary="Get webhook health summary",
    description=(
        "Get aggregated health metrics for all outbound webhooks, including "
        "success rates and delivery statistics over the last 24 hours."
    ),
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_webhook_health(
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookHealthSummary:
    """Get health summary for all outbound webhooks.

    Returns aggregated metrics including:
    - Total and enabled webhook counts
    - Healthy/unhealthy webhook counts (based on success rates)
    - Delivery statistics for the last 24 hours
    - Average response time

    Args:
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        WebhookHealthSummary with aggregated metrics.
    """
    return await webhook_service.get_health_summary(db)


# =============================================================================
# Delivery Endpoints (defined before /{id} to avoid path conflicts)
# =============================================================================


@router.get(
    "/deliveries/{delivery_id}",
    response_model=WebhookDeliveryResponse,
    summary="Get delivery details",
    description="Get detailed information about a specific webhook delivery attempt.",
    responses={
        404: {"description": "Delivery not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_delivery(
    delivery_id: str,
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookDeliveryResponse:
    """Get details of a specific webhook delivery.

    Args:
        delivery_id: Delivery UUID.
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        WebhookDeliveryResponse with delivery details.

    Raises:
        HTTPException: 404 if delivery not found.
    """
    delivery = await webhook_service.get_delivery(db, delivery_id)

    if delivery is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delivery with id {delivery_id} not found",
        )

    return _delivery_to_response(delivery)


@router.post(
    "/deliveries/{delivery_id}/retry",
    response_model=WebhookDeliveryResponse,
    summary="Retry failed delivery",
    description=(
        "Manually retry a failed webhook delivery. Creates a new delivery attempt "
        "for the same event and webhook configuration."
    ),
    responses={
        404: {"description": "Delivery not found"},
        409: {"description": "Delivery cannot be retried (not in failed state)"},
        500: {"description": "Internal server error"},
    },
)
async def retry_delivery(
    delivery_id: str,
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookDeliveryResponse:
    """Retry a failed webhook delivery.

    Only deliveries with status 'failed' can be retried. This creates a new
    delivery attempt that will be processed immediately.

    Args:
        delivery_id: Delivery UUID.
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        WebhookDeliveryResponse with the new delivery attempt details.

    Raises:
        HTTPException: 404 if delivery not found.
        HTTPException: 409 if delivery is not in a retriable state.
    """
    delivery = await webhook_service.retry_delivery(db, delivery_id)

    if delivery is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delivery with id {delivery_id} not found",
        )

    return _delivery_to_response(delivery)


# =============================================================================
# Webhook CRUD Endpoints
# =============================================================================


@router.post(
    "",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    description=(
        "Create a new outbound webhook configuration. The webhook will be "
        "triggered when subscribed events occur in the system."
    ),
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def create_webhook(
    webhook_data: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookResponse:
    """Create a new outbound webhook.

    Creates a webhook that will send HTTP POST requests to the specified URL
    when any of the subscribed event types occur. The webhook can be configured
    with custom authentication, headers, and payload templates.

    Args:
        webhook_data: Webhook creation data.
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        Created webhook configuration.
    """
    webhook = await webhook_service.create_webhook(db, webhook_data)

    logger.info(
        "Outbound webhook created",
        extra={
            "webhook_id": webhook.id,
            "webhook_name": webhook.name,
            "event_types": webhook.event_types,
            "integration_type": webhook.integration_type.value
            if hasattr(webhook.integration_type, "value")
            else str(webhook.integration_type),
        },
    )

    return _webhook_to_response(webhook)


@router.get(
    "",
    response_model=WebhookListResponse,
    summary="List webhooks",
    description="List all outbound webhook configurations with optional filtering.",
    responses={
        500: {"description": "Internal server error"},
    },
)
async def list_webhooks(
    enabled_only: bool = Query(
        False,
        description="Filter to only return enabled webhooks",
    ),
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookListResponse:
    """List all outbound webhooks.

    Returns a list of all webhook configurations with their current status
    and delivery statistics.

    Args:
        enabled_only: If True, only return enabled webhooks.
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        WebhookListResponse with list of webhooks and total count.
    """
    webhooks = await webhook_service.list_webhooks(db, enabled_only=enabled_only)

    return WebhookListResponse(
        webhooks=[_webhook_to_response(w) for w in webhooks],
        total=len(webhooks),
    )


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook",
    description="Get a specific outbound webhook configuration by ID.",
    responses={
        404: {"description": "Webhook not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookResponse:
    """Get a webhook by ID.

    Args:
        webhook_id: Webhook UUID.
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        WebhookResponse with webhook configuration.

    Raises:
        HTTPException: 404 if webhook not found.
    """
    webhook = await _get_webhook_or_404(webhook_id, db, webhook_service)
    return _webhook_to_response(webhook)


@router.patch(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update webhook",
    description="Update an existing outbound webhook configuration.",
    responses={
        404: {"description": "Webhook not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def update_webhook(
    webhook_id: str,
    webhook_data: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookResponse:
    """Update a webhook configuration.

    Only provided fields will be updated. Null/missing fields are not modified.

    Args:
        webhook_id: Webhook UUID.
        webhook_data: Webhook update data.
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        Updated webhook configuration.

    Raises:
        HTTPException: 404 if webhook not found.
    """
    webhook = await webhook_service.update_webhook(db, webhook_id, webhook_data)

    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with id {webhook_id} not found",
        )

    logger.info(
        "Outbound webhook updated",
        extra={
            "webhook_id": webhook_id,
            "updated_fields": list(webhook_data.model_dump(exclude_unset=True).keys()),
        },
    )

    return _webhook_to_response(webhook)


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete webhook",
    description=(
        "Delete an outbound webhook configuration. This will also delete "
        "all associated delivery history."
    ),
    responses={
        404: {"description": "Webhook not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> None:
    """Delete a webhook.

    Permanently removes the webhook configuration and all associated delivery
    records. This action cannot be undone.

    Args:
        webhook_id: Webhook UUID.
        db: Database session.
        webhook_service: WebhookService instance.

    Raises:
        HTTPException: 404 if webhook not found.
    """
    deleted = await webhook_service.delete_webhook(db, webhook_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with id {webhook_id} not found",
        )

    logger.info(
        "Outbound webhook deleted",
        extra={"webhook_id": webhook_id},
    )


# =============================================================================
# Webhook Operations
# =============================================================================


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestResponse,
    summary="Test webhook",
    description=(
        "Test a webhook by sending a sample payload. This does not create a "
        "delivery record and is useful for validating webhook configuration."
    ),
    responses={
        404: {"description": "Webhook not found"},
        500: {"description": "Internal server error"},
    },
)
async def test_webhook(
    webhook_id: str,
    test_request: WebhookTestRequest,
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookTestResponse:
    """Test a webhook with a sample payload.

    Sends a test request to the webhook URL with sample data for the specified
    event type. The response includes the HTTP status code, response time, and
    any error messages.

    This is useful for validating:
    - URL accessibility
    - Authentication configuration
    - Payload format compatibility

    Args:
        webhook_id: Webhook UUID.
        test_request: Test request with event type.
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        WebhookTestResponse with test results.

    Raises:
        HTTPException: 404 if webhook not found.
    """
    # First verify webhook exists
    await _get_webhook_or_404(webhook_id, db, webhook_service)

    result = await webhook_service.test_webhook(db, webhook_id, test_request.event_type)

    logger.info(
        "Outbound webhook test executed",
        extra={
            "webhook_id": webhook_id,
            "event_type": test_request.event_type.value,
            "success": result.success,
            "status_code": result.status_code,
            "response_time_ms": result.response_time_ms,
        },
    )

    return result


@router.post(
    "/{webhook_id}/enable",
    response_model=WebhookResponse,
    summary="Enable webhook",
    description="Enable a disabled webhook so it will receive events.",
    responses={
        404: {"description": "Webhook not found"},
        500: {"description": "Internal server error"},
    },
)
async def enable_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookResponse:
    """Enable a webhook.

    Enables a previously disabled webhook. The webhook will start receiving
    events immediately for all subscribed event types.

    Args:
        webhook_id: Webhook UUID.
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        Updated webhook configuration.

    Raises:
        HTTPException: 404 if webhook not found.
    """
    webhook = await webhook_service.update_webhook(
        db,
        webhook_id,
        WebhookUpdate(enabled=True),
    )

    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with id {webhook_id} not found",
        )

    logger.info(
        "Outbound webhook enabled",
        extra={"webhook_id": webhook_id},
    )

    return _webhook_to_response(webhook)


@router.post(
    "/{webhook_id}/disable",
    response_model=WebhookResponse,
    summary="Disable webhook",
    description="Disable a webhook so it will stop receiving events.",
    responses={
        404: {"description": "Webhook not found"},
        500: {"description": "Internal server error"},
    },
)
async def disable_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookResponse:
    """Disable a webhook.

    Disables a webhook so it will no longer receive events. The webhook
    configuration is preserved and can be re-enabled later.

    Args:
        webhook_id: Webhook UUID.
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        Updated webhook configuration.

    Raises:
        HTTPException: 404 if webhook not found.
    """
    webhook = await webhook_service.update_webhook(
        db,
        webhook_id,
        WebhookUpdate(enabled=False),
    )

    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with id {webhook_id} not found",
        )

    logger.info(
        "Outbound webhook disabled",
        extra={"webhook_id": webhook_id},
    )

    return _webhook_to_response(webhook)


# =============================================================================
# Delivery Log Endpoints
# =============================================================================


@router.get(
    "/{webhook_id}/deliveries",
    response_model=WebhookDeliveryListResponse,
    summary="List deliveries",
    description="List delivery history for a specific webhook with pagination.",
    responses={
        404: {"description": "Webhook not found"},
        500: {"description": "Internal server error"},
    },
)
async def list_deliveries(
    webhook_id: str,
    limit: int = Query(
        50,
        ge=1,
        le=1000,
        description="Maximum number of deliveries to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of deliveries to skip (for pagination)",
    ),
    db: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookDeliveryListResponse:
    """List deliveries for a webhook.

    Returns the delivery history for a specific webhook, ordered by creation
    time (most recent first). Includes both successful and failed deliveries.

    Args:
        webhook_id: Webhook UUID.
        limit: Maximum number of deliveries to return.
        offset: Number of deliveries to skip for pagination.
        db: Database session.
        webhook_service: WebhookService instance.

    Returns:
        WebhookDeliveryListResponse with deliveries and pagination info.

    Raises:
        HTTPException: 404 if webhook not found.
    """
    # First verify webhook exists
    await _get_webhook_or_404(webhook_id, db, webhook_service)

    deliveries, total = await webhook_service.get_deliveries(
        db,
        webhook_id,
        limit=limit,
        offset=offset,
    )

    return WebhookDeliveryListResponse(
        deliveries=[_delivery_to_response(d) for d in deliveries],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(deliveries)) < total,
    )
