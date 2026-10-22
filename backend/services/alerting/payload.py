"""Alert delivery payload builder (B4.2).

Builds the outbound payload for a delivery from the alert record, applying
F13 redaction (gallery names → "a known person" unless the channel opted in).
Adapters take this dict as-is: email renders it into a message, webhook posts
it as JSON, browser/push carries the title.
"""

from __future__ import annotations

from typing import Any

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


__all__ = ["build_payload"]
