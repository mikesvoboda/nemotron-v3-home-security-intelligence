"""API routes for receiving inbound webhooks from external systems.

This module provides endpoints for receiving webhook notifications from
external systems like IFTTT, Zapier, n8n, and custom integrations.

Endpoints:
    POST /api/webhooks/inbound/alert - Create external alert
    POST /api/webhooks/inbound/arm - Arm zones
    POST /api/webhooks/inbound/disarm - Disarm zones
    POST /api/webhooks/inbound/mode - Set system mode

Related Issues:
    - NEM-5170: [Implement] Phase 8: Inbound Webhook API
    - NEM-5032: Epic 3: Ecosystem Integration
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.services.mqtt_command_handler import SystemMode

logger = get_logger(__name__)

router = APIRouter(prefix="/api/webhooks/inbound", tags=["inbound-webhooks"])


# =============================================================================
# Schemas
# =============================================================================


class InboundAlertPayload(BaseModel):
    """Payload for creating an external alert."""

    source: str = Field(
        min_length=1,
        max_length=100,
        description="Source system identifier (e.g., 'ifttt', 'zapier').",
    )
    message: str = Field(
        min_length=1,
        max_length=1000,
        description="Alert message.",
    )
    severity: str = Field(
        default="medium",
        description="Alert severity: low, medium, high, critical.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata.",
    )


class InboundArmPayload(BaseModel):
    """Payload for arming zones."""

    zone_ids: list[str] | None = Field(
        default=None,
        description="Zone IDs to arm. If None, arms all zones.",
    )
    mode: str | None = Field(
        default=None,
        description="Optional arm mode (full, perimeter, instant).",
    )


class InboundDisarmPayload(BaseModel):
    """Payload for disarming zones."""

    zone_ids: list[str] | None = Field(
        default=None,
        description="Zone IDs to disarm. If None, disarms all zones.",
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional reason for disarming.",
    )


class InboundModePayload(BaseModel):
    """Payload for setting system mode."""

    mode: str = Field(
        description="System mode: home, away, night, disarmed.",
    )


class InboundWebhookResponse(BaseModel):
    """Standard response for inbound webhooks."""

    status: str = Field(description="Request status.")
    message: str = Field(description="Status message.")
    request_id: str | None = Field(default=None, description="Request tracking ID.")
    timestamp: str = Field(description="Processing timestamp.")


# =============================================================================
# Authentication
# =============================================================================


class WebhookAuthError(Exception):
    """Raised when webhook authentication fails."""

    pass


def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str:
    """Verify API key from header.

    Args:
        x_api_key: API key from X-API-Key header.

    Returns:
        Validated API key.

    Raises:
        HTTPException: If API key is missing or invalid.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    # TODO: Validate against stored API keys in database
    # For now, accept any non-empty key for development
    if len(x_api_key) < 16:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return x_api_key


def verify_hmac_signature(
    request_body: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify HMAC-SHA256 signature.

    Args:
        request_body: Raw request body bytes.
        signature: Signature from X-Signature header (format: sha256=...).
        secret: HMAC secret key.

    Returns:
        True if signature is valid.
    """
    if not signature.startswith("sha256="):
        return False

    expected_sig = signature[7:]  # Remove "sha256=" prefix
    computed_sig = hmac.new(
        secret.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_sig, computed_sig)


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/alert",
    response_model=InboundWebhookResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Alert created successfully"},
        401: {"description": "Authentication failed"},
        422: {"description": "Invalid payload"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def create_alert(
    payload: InboundAlertPayload,
    request: Request,
    _background_tasks: BackgroundTasks,
    _db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
) -> InboundWebhookResponse:
    """Create an alert from an external webhook.

    This endpoint allows external systems to create alerts in HSI.

    Args:
        payload: Alert payload with source, message, and severity.
        request: FastAPI request object.
        background_tasks: For async processing.
        db: Database session.
        api_key: Validated API key.

    Returns:
        InboundWebhookResponse with status.
    """
    request_id = secrets.token_hex(8)

    logger.info(
        "Inbound alert webhook received",
        extra={
            "request_id": request_id,
            "source": payload.source,
            "severity": payload.severity,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )

    # TODO: NEM-5170 - Integrate with AlertService

    return InboundWebhookResponse(
        status="received",
        message=f"Alert from {payload.source} queued for processing",
        request_id=request_id,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.post(
    "/arm",
    response_model=InboundWebhookResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Zones armed successfully"},
        401: {"description": "Authentication failed"},
        422: {"description": "Invalid payload"},
    },
)
async def arm_zones(
    payload: InboundArmPayload,
    request: Request,
    _db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
) -> InboundWebhookResponse:
    """Arm zones via webhook.

    Args:
        payload: Arm payload with optional zone IDs.
        request: FastAPI request object.
        db: Database session.
        api_key: Validated API key.

    Returns:
        InboundWebhookResponse with status.
    """
    request_id = secrets.token_hex(8)
    zone_count = len(payload.zone_ids) if payload.zone_ids else "all"

    logger.info(
        "Inbound arm webhook received",
        extra={
            "request_id": request_id,
            "zone_ids": payload.zone_ids,
            "mode": payload.mode,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )

    # TODO: NEM-5170 - Integrate with ZoneService

    return InboundWebhookResponse(
        status="received",
        message=f"Arm command for {zone_count} zones queued",
        request_id=request_id,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.post(
    "/disarm",
    response_model=InboundWebhookResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Zones disarmed successfully"},
        401: {"description": "Authentication failed"},
        422: {"description": "Invalid payload"},
    },
)
async def disarm_zones(
    payload: InboundDisarmPayload,
    request: Request,
    _db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
) -> InboundWebhookResponse:
    """Disarm zones via webhook.

    Args:
        payload: Disarm payload with optional zone IDs.
        request: FastAPI request object.
        db: Database session.
        api_key: Validated API key.

    Returns:
        InboundWebhookResponse with status.
    """
    request_id = secrets.token_hex(8)
    zone_count = len(payload.zone_ids) if payload.zone_ids else "all"

    logger.info(
        "Inbound disarm webhook received",
        extra={
            "request_id": request_id,
            "zone_ids": payload.zone_ids,
            "reason": payload.reason,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )

    # TODO: NEM-5170 - Integrate with ZoneService

    return InboundWebhookResponse(
        status="received",
        message=f"Disarm command for {zone_count} zones queued",
        request_id=request_id,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.post(
    "/mode",
    response_model=InboundWebhookResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "System mode changed successfully"},
        401: {"description": "Authentication failed"},
        422: {"description": "Invalid payload or mode"},
    },
)
async def set_system_mode(
    payload: InboundModePayload,
    request: Request,
    _db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
) -> InboundWebhookResponse:
    """Set system mode via webhook.

    Valid modes:
    - home: Family at home, known faces suppressed
    - away: Nobody home, all alerts enabled
    - night: Sleeping, perimeter zones only
    - disarmed: No alerts, logging only

    Args:
        payload: Mode payload.
        request: FastAPI request object.
        db: Database session.
        api_key: Validated API key.

    Returns:
        InboundWebhookResponse with status.
    """
    request_id = secrets.token_hex(8)

    # Validate mode
    valid_modes = {m.value for m in SystemMode}
    if payload.mode not in valid_modes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid mode: {payload.mode}. Must be one of: {valid_modes}",
        )

    logger.info(
        "Inbound mode webhook received",
        extra={
            "request_id": request_id,
            "mode": payload.mode,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )

    # TODO: NEM-5170 - Integrate with CommandHandler

    return InboundWebhookResponse(
        status="received",
        message=f"System mode change to '{payload.mode}' queued",
        request_id=request_id,
        timestamp=datetime.now(UTC).isoformat(),
    )
