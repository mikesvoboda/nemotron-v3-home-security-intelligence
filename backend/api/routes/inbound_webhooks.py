"""API routes for receiving inbound webhooks from external systems.

This module provides endpoints for webhook notifications from external
systems like IFTTT, Zapier, n8n, and custom integrations.

Endpoints:
    POST /api/webhooks/inbound/alert - Create external alert
    POST /api/webhooks/inbound/arm - Arm zones
    POST /api/webhooks/inbound/disarm - Disarm zones
    POST /api/webhooks/inbound/mode - Set system mode

Honesty contract (B1.3, D3, UR-12)
----------------------------------
**All four endpoints answer 501 Not Implemented.** None of the actions
they accept is implemented: the arming module with webhook and MQTT
adapters is ruled for after Phase 3 (UR-12), so a handler that replied
"Arm command for N zones queued" described work nothing queued (audit
finding D3 — `arm_zones` said a house was armed when it was not). Each
handler now validates the key, logs the rejected attempt for the
integrator's sake, and raises 501 with a body naming UR-12.

Authentication is unconditional and fail-closed: the shared
:func:`~backend.api.middleware.auth.require_api_key` validates the
``X-API-Key`` header against ``settings.api_keys``. Before B1.3 this module
accepted *any* key of 16 or more characters. It deliberately does not
honour ``settings.api_key_enabled`` (whose shipped default is off) — with
that branch these routes would answer unauthenticated callers again.

The request schemas below are kept byte-compatible on purpose: the Phase 4
arming feature reuses them (package B1.3, "Keep the request schemas").
That includes ``InboundModePayload.mode``, which stays a plain ``str``: the
mode-value check that used to run in the handler went with the handler, and
validating the vocabulary belongs to the feature that acts on it.

Related Issues:
    - NEM-5170: [Implement] Phase 8: Inbound Webhook API — still open: the
      handlers remain unimplemented; only their honesty changed.
    - NEM-5032: Epic 3: Ecosystem Integration
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.api.middleware.auth import require_api_key
from backend.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/webhooks/inbound", tags=["inbound-webhooks"])

#: The body every handler raises with. Naming the ruling is the point: an
#: integrator reading a 501 learns which decision governs the feature, not
#: just that it is missing.
NOT_IMPLEMENTED_DETAIL = (
    "Inbound webhooks are not implemented (UR-12): the arming module that would act on this "
    "request is designed after Phase 3. This endpoint takes no action."
)

#: Annotated explicitly: a bare module-level dict infers ``dict[int, dict[str, str]]``,
#: which mypy rejects against ``router.post(responses=…)``'s ``dict[int | str, …]``.
_UNIMPLEMENTED_RESPONSES: dict[int | str, dict[str, Any]] = {
    501: {"description": "Not implemented — UR-12; this endpoint takes no action"},
    401: {"description": "Authentication failed"},
    422: {"description": "Invalid payload"},
}


# =============================================================================
# Schemas (kept byte-compatible for the Phase 4 arming feature — B1.3)
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


# =============================================================================
# Authentication
# =============================================================================


class WebhookAuthError(Exception):
    """Raised when webhook authentication fails."""

    pass


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


def _log_rejected_attempt(endpoint: str, request: Request) -> None:
    """Record that a correctly authenticated call reached an unimplemented route.

    The old handlers logged a fake success ("... queued"); this records the
    honest fact so an integrator's reports can be traced to the endpoint that
    refuses them. No request body, key, or other secret is logged.
    """
    logger.info(
        "Inbound webhook rejected as unimplemented (UR-12)",
        extra={
            "endpoint": endpoint,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )


def _reject_unimplemented(endpoint: str, request: Request) -> None:
    """Log and raise the 501 every handler answers with (UR-12)."""
    _log_rejected_attempt(endpoint, request)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=NOT_IMPLEMENTED_DETAIL)


# =============================================================================
# Endpoints — all four answer 501 (UR-12); see the module docstring
# =============================================================================


@router.post(
    "/alert",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    responses=_UNIMPLEMENTED_RESPONSES,
)
async def create_alert(
    payload: InboundAlertPayload,  # noqa: ARG001 - schema kept for the arming feature
    request: Request,
    _api_key: str = Depends(require_api_key),
) -> None:
    """Not implemented (UR-12): external alert ingestion takes no action.

    Accepts ``InboundAlertPayload`` and answers 501. A malformed payload
    still 422s (the schema is live); auth failures 401 first.
    """
    _reject_unimplemented("alert", request)


@router.post(
    "/arm",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    responses=_UNIMPLEMENTED_RESPONSES,
)
async def arm_zones(
    payload: InboundArmPayload,  # noqa: ARG001 - schema kept for the arming feature
    request: Request,
    _api_key: str = Depends(require_api_key),
) -> None:
    """Not implemented (UR-12): arming zones takes no action.

    This is the endpoint D3 names: it used to answer "Arm command for N
    zones queued" having queued nothing, telling an integrator the house
    was armed when it was not.
    """
    _reject_unimplemented("arm", request)


@router.post(
    "/disarm",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    responses=_UNIMPLEMENTED_RESPONSES,
)
async def disarm_zones(
    payload: InboundDisarmPayload,  # noqa: ARG001 - schema kept for the arming feature
    request: Request,
    _api_key: str = Depends(require_api_key),
) -> None:
    """Not implemented (UR-12): disarming zones takes no action."""
    _reject_unimplemented("disarm", request)


@router.post(
    "/mode",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    responses=_UNIMPLEMENTED_RESPONSES,
)
async def set_system_mode(
    payload: InboundModePayload,  # noqa: ARG001 - schema kept for the arming feature
    request: Request,
    _api_key: str = Depends(require_api_key),
) -> None:
    """Not implemented (UR-12): system-mode changes take no action.

    Mode values are no longer validated here: the check lived in the handler
    that acted on them, and ``InboundModePayload`` is kept unchanged for the
    arming feature, whose ruling it is.
    """
    _reject_unimplemented("mode", request)
