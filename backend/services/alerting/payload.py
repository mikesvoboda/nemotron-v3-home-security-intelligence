"""Alert delivery payload builder (B4.2).

Builds the outbound payload for a delivery from the alert record, applying
F13 redaction (gallery names → "a known person" unless the channel opted in).
Adapters take this dict as-is: email renders it into a message, webhook posts
it as JSON, browser/push carries the title.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.secret_box import decrypt_secret
from backend.services.alerting.channels.base import DeliveryTask
from backend.services.alerting.redact import redact_names


def build_payload(
    alert: Any,
    *,
    idempotency_key: str,
    include_names: bool,
    known_names: set[str] | None = None,
    dashboard_base_url: str = "",
) -> dict[str, Any]:
    """Build the delivery payload for one alert + channel pair.

    Shape (kept minimal on purpose — every field is read by at least one
    adapter or the golden path):
        alert_id, title, severity, camera_id, event_id, summary, link,
        idempotency_key, occurred_at.

    ``summary`` is the VLM text with gallery names redacted per the channel's
    include_names switch (F13). Images never leave on any channel — none are
    attached here. The alert has no title column: the rule name lives in
    alert_metadata (the shape notification.py:322 already reads).
    """
    metadata = getattr(alert, "alert_metadata", None) or {}
    title = metadata.get("rule_name") or "Security alert"
    summary = getattr(alert, "alert_metadata", None) or {}
    vlm_summary = summary.get("summary") or summary.get("reasoning") or ""
    if not vlm_summary:
        vlm_summary = getattr(alert, "description", "") or ""
    vlm_summary = redact_names(vlm_summary, known_names or set(), include_names)
    payload: dict[str, Any] = {
        "alert_id": str(getattr(alert, "id", "")),
        "title": title,
        "severity": getattr(alert, "severity", ""),
        "camera_id": getattr(alert, "camera_id", ""),
        "event_id": getattr(alert, "event_id", None),
        "summary": vlm_summary,
        "link": dashboard_base_url.rstrip("/") + "/alerts" if dashboard_base_url else "",
        "idempotency_key": idempotency_key,
    }
    occurred = getattr(alert, "created_at", None)
    if occurred is not None:
        payload["occurred_at"] = occurred.isoformat()
    return payload


async def _load_alert_and_channel(
    session_factory: async_sessionmaker[AsyncSession],
    alert_id: str,
    channel_id: str,
) -> tuple[Any, Any]:
    """The alert and the recipient channel row behind one claimed delivery."""
    from backend.models.alert import Alert
    from backend.models.alert_delivery import RecipientChannel

    async with session_factory() as session:
        alert = await session.get(Alert, alert_id)
        channel = await session.get(RecipientChannel, channel_id)
    return alert, channel


def build_delivery_task(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[..., Awaitable[DeliveryTask]]:
    """The production task builder for the delivery worker's seam.

    The worker calls its ``build_payload`` argument as
    ``(alert_id, channel_id, recipient_id, extras, known_names=...)`` and
    expects an awaitable ``DeliveryTask``. The default builder it ships
    instead produces an EMPTY payload and no target — fine for tests that
    inject their own builder, but production wiring must pass the builder
    this returns: it loads the alert and the channel row, applies F13
    redaction through :func:`build_payload`, and resolves the webhook
    channel's target and signing secret (decrypted at send time; the
    plaintext never persists — design 4n-alerting.md:186).

    A missing alert row (purged while a delivery was pending) yields a task
    with an empty payload; the adapter's send on an empty payload is skipped
    upstream by the worker recording a failure, so the cycle lives on.
    """
    from backend.models.alert_delivery import DeliveryChannelKind

    async def _build(
        alert_id: str,
        channel_id: str,
        recipient_id: str,
        extras: dict[str, Any],
        *,
        known_names: set[str] | None = None,
    ) -> DeliveryTask:
        alert, channel = await _load_alert_and_channel(session_factory, alert_id, channel_id)
        kind_raw = getattr(channel, "kind", None)
        kind_name = getattr(kind_raw, "value", kind_raw)
        kind = DeliveryChannelKind(kind_name) if kind_name else extras.get("kind", "email")
        include_names = bool(getattr(channel, "include_names", False))
        target = str(getattr(channel, "target", "") or "")
        signing_secret: str | None = None
        encrypted = getattr(channel, "signing_secret_encrypted", None)
        if encrypted:
            signing_secret = decrypt_secret(encrypted)

        payload: dict[str, Any] = {}
        if alert is not None:
            payload = build_payload(
                alert,
                idempotency_key=extras.get("idempotency_key", ""),
                include_names=include_names,
                known_names=known_names,
                dashboard_base_url="",
            )

        return DeliveryTask(
            delivery_id=alert_id,
            channel_id=channel_id,
            channel_kind=kind,
            recipient_id=recipient_id,
            idempotency_key=extras.get("idempotency_key", ""),
            payload=payload,
            include_names=include_names,
            known_names=known_names or set(),
            on_local_network=bool(getattr(channel, "on_local_network", False)),
            target=target,
            signing_secret=signing_secret,
            push_subscription=getattr(channel, "push_subscription", None),
        )

    return _build


__all__ = ["build_delivery_task", "build_payload"]
