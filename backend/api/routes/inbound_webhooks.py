"""API routes for receiving inbound webhooks from external systems (B4.7 / 4n-arming.md).

Endpoints:
    POST /api/webhooks/inbound/alert  - Create an external event on a named camera and run AlertPipeline
    POST /api/webhooks/inbound/arm    - Switch household arming mode (default 'away')
    POST /api/webhooks/inbound/disarm - Switch household arming mode to 'disarmed'
    POST /api/webhooks/inbound/mode   - Switch household arming mode ('home', 'away', 'night', 'disarmed')

Authentication is unconditional and fail-closed via `require_api_key` (`X-API-Key`).
The source recorded in `arming_state` / `arming_changes` and namespaced into `/alert`'s
`batch_id` is the key's SHA-256 fingerprint, never the raw key.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.middleware.auth import require_api_key as _require_settings_api_key
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.alert import Alert, AlertEvent
from backend.models.api_key import APIKey
from backend.models.arming import VALID_ARMING_MODES
from backend.models.camera import Camera
from backend.models.event import Event
from backend.services.alerting.pipeline import AlertPipeline
from backend.services.alerting.verdict import external_severity_top_score
from backend.services.arming import (
    ensure_external_alerts_rule,
    key_fingerprint,
    set_mode,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/webhooks/inbound", tags=["inbound-webhooks"])

VALID_EXTERNAL_SEVERITIES: tuple[str, ...] = ("low", "medium", "high", "critical")
_MODES_HELP = "valid modes are home, away, night, disarmed"

_WEBHOOK_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {"description": "Webhook processed"},
    401: {"description": "Authentication failed"},
    422: {"description": "Invalid payload"},
}


# =============================================================================
# Schemas
# =============================================================================


class InboundAlertPayload(BaseModel):
    """Payload for creating an external alert event on a camera (B4.7 / 4n-arming.md)."""

    camera_id: str | None = Field(
        default=None,
        description="Camera ID associated with the external sensor/alert (required by /alert).",
    )
    source: str = Field(
        min_length=1,
        max_length=100,
        description="Source system identifier (e.g., 'ifttt', 'home_assistant').",
    )
    message: str = Field(
        min_length=1,
        max_length=1000,
        description="Alert message stored as the external event summary.",
    )
    severity: str = Field(
        default="medium",
        description="Alert severity: low, medium, high, critical.",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=255,
        description="Optional caller idempotency key (namespaced per API key fingerprint).",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata.",
    )


class InboundArmPayload(BaseModel):
    """Payload for arming the household via inbound webhook."""

    zone_ids: list[str] | None = Field(
        default=None,
        description="Zone IDs (unsupported; supplying zone_ids returns 422 naming the four modes).",
    )
    mode: str | None = Field(
        default=None,
        description="Optional target mode (home, away, night, disarmed; default away).",
    )


class InboundDisarmPayload(BaseModel):
    """Payload for disarming the household via inbound webhook."""

    zone_ids: list[str] | None = Field(
        default=None,
        description="Zone IDs (unsupported; supplying zone_ids returns 422 naming the four modes).",
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional reason for disarming.",
    )


class InboundModePayload(BaseModel):
    """Payload for setting the household arming mode."""

    mode: str = Field(
        description="System mode: home, away, night, disarmed.",
    )


class InboundModeWebhookResponse(BaseModel):
    """Response returned by /mode, /arm, and /disarm."""

    status: str = "ok"
    mode: str
    source_kind: str = "webhook"
    source_name: str


class InboundAlertWebhookResponse(BaseModel):
    """Response returned by /alert."""

    status: str = "ok"
    event_id: int
    batch_id: str
    camera_id: str
    severity: str
    notify: bool
    alert_ids: list[str] = Field(default_factory=list)


# =============================================================================
# Authentication helpers
# =============================================================================


def verify_hmac_signature(
    request_body: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify HMAC-SHA256 signature."""
    if not signature.startswith("sha256="):
        return False

    expected_sig = signature[7:]
    computed_sig = hmac.new(
        secret.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_sig, computed_sig)


async def require_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: AsyncSession = Depends(get_db),
) -> str:
    """Validate `X-API-Key` against `settings.api_keys` or active `api_keys` DB rows (fail-closed)."""
    try:
        return _require_settings_api_key(request, x_api_key)
    except HTTPException as exc:
        if not x_api_key or exc.status_code != status.HTTP_401_UNAUTHORIZED:
            raise
        with contextlib.suppress(Exception):
            candidate_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
            now = datetime.now(UTC)
            rows = (
                (await db.execute(select(APIKey).where(APIKey.is_active.is_(True)))).scalars().all()
            )
            matched = False
            for row in rows:
                if not isinstance(getattr(row, "key_hash", None), str):
                    continue
                exp = getattr(row, "expires_at", None)
                if isinstance(exp, datetime):
                    exp_utc = exp.replace(tzinfo=UTC) if exp.tzinfo is None else exp.astimezone(UTC)
                    if exp_utc <= now:
                        continue
                if hmac.compare_digest(row.key_hash, candidate_hash):
                    matched = True
            if matched:
                return x_api_key
        raise exc


def _validate_webhook_mode(raw_mode: str | None, *, default: str | None = None) -> str:
    candidate = (raw_mode if raw_mode is not None else default) or ""
    normalized = candidate.strip().lower()
    if normalized not in VALID_ARMING_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid mode {raw_mode!r}; {_MODES_HELP}",
        )
    return normalized


def _refuse_zone_ids(zone_ids: list[str] | None) -> None:
    if zone_ids is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Zones are not supported yet; {_MODES_HELP}",
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/alert",
    response_model=InboundAlertWebhookResponse,
    status_code=status.HTTP_200_OK,
    responses=_WEBHOOK_RESPONSES,
)
async def create_alert(
    payload: InboundAlertPayload,
    request: Request,  # noqa: ARG001
    api_key: str = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> InboundAlertWebhookResponse:
    """Create an external event on `payload.camera_id` and run `AlertPipeline.process` (A4, A5)."""
    camera_id = (payload.camera_id or "").strip()
    if not camera_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="camera_id is required for external alerts",
        )

    sev_lower = (payload.severity or "").strip().lower()
    if sev_lower not in VALID_EXTERNAL_SEVERITIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid severity {payload.severity!r}; must be one of "
                f"{', '.join(VALID_EXTERNAL_SEVERITIES)}"
            ),
        )

    camera = await db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown camera_id: {camera_id}",
        )

    fp = key_fingerprint(api_key)
    if payload.idempotency_key:
        idem_sha = hashlib.sha256(payload.idempotency_key.encode("utf-8")).hexdigest()
        batch_id = f"external:{fp}:{idem_sha}"
    else:
        batch_id = f"external:{uuid.uuid4()}"

    now = datetime.now(UTC)
    score = external_severity_top_score(sev_lower)
    await ensure_external_alerts_rule(db)

    await db.execute(
        pg_insert(Event)
        .values(
            batch_id=batch_id,
            camera_id=camera_id,
            started_at=now,
            ended_at=now,
            risk_score=score,
            risk_level=sev_lower,
            summary=payload.message,
            source="external",
            external_source=payload.source,
            reviewed=False,
            flagged=False,
            is_fast_path=False,
        )
        .on_conflict_do_nothing(index_elements=["batch_id"])
    )

    event = (await db.execute(select(Event).where(Event.batch_id == batch_id))).scalars().first()
    if event is None:
        raise HTTPException(status_code=500, detail="Failed to persist external event")

    await db.commit()

    # Every request, first or repeated, calls AlertPipeline.process after the commit (A5)
    pipeline = AlertPipeline()
    result = await pipeline.process(event.id, session=db, now=now)
    await db.commit()

    alert_ids = [a.id for a in (*result.created_alerts, *result.updated_alerts)]
    if not alert_ids and result.notify:
        rows = (
            (
                await db.execute(
                    select(Alert.id)
                    .outerjoin(AlertEvent, AlertEvent.alert_id == Alert.id)
                    .where(or_(Alert.event_id == event.id, AlertEvent.event_id == event.id))
                    .order_by(Alert.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        alert_ids = list(dict.fromkeys(rows))
    return InboundAlertWebhookResponse(
        status="ok",
        event_id=event.id,
        batch_id=event.batch_id,
        camera_id=event.camera_id,
        severity=sev_lower,
        notify=result.notify,
        alert_ids=alert_ids,
    )


@router.post(
    "/arm",
    response_model=InboundModeWebhookResponse,
    status_code=status.HTTP_200_OK,
    responses=_WEBHOOK_RESPONSES,
)
async def arm_zones(
    payload: InboundArmPayload,
    request: Request,  # noqa: ARG001
    api_key: str = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> InboundModeWebhookResponse:
    """Arm the household in `payload.mode` (default `away`)."""
    _refuse_zone_ids(payload.zone_ids)
    target_mode = _validate_webhook_mode(payload.mode, default="away")
    fp = key_fingerprint(api_key)
    await set_mode(db, target_mode, source_kind="webhook", source_name=fp)
    await db.commit()
    return InboundModeWebhookResponse(
        status="ok",
        mode=target_mode,
        source_kind="webhook",
        source_name=fp,
    )


@router.post(
    "/disarm",
    response_model=InboundModeWebhookResponse,
    status_code=status.HTTP_200_OK,
    responses=_WEBHOOK_RESPONSES,
)
async def disarm_zones(
    payload: InboundDisarmPayload,
    request: Request,  # noqa: ARG001
    api_key: str = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> InboundModeWebhookResponse:
    """Disarm the household (`mode = 'disarmed'`)."""
    _refuse_zone_ids(payload.zone_ids)
    fp = key_fingerprint(api_key)
    await set_mode(db, "disarmed", source_kind="webhook", source_name=fp)
    await db.commit()
    return InboundModeWebhookResponse(
        status="ok",
        mode="disarmed",
        source_kind="webhook",
        source_name=fp,
    )


@router.post(
    "/mode",
    response_model=InboundModeWebhookResponse,
    status_code=status.HTTP_200_OK,
    responses=_WEBHOOK_RESPONSES,
)
async def set_system_mode(
    payload: InboundModePayload,
    request: Request,  # noqa: ARG001
    api_key: str = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> InboundModeWebhookResponse:
    """Set the household arming mode (`home`, `away`, `night`, `disarmed`)."""
    target_mode = _validate_webhook_mode(payload.mode)
    fp = key_fingerprint(api_key)
    await set_mode(db, target_mode, source_kind="webhook", source_name=fp)
    await db.commit()
    return InboundModeWebhookResponse(
        status="ok",
        mode=target_mode,
        source_kind="webhook",
        source_name=fp,
    )
