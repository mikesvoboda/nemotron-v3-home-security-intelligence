"""Delivery-row writer for the alert pipeline (B4.2).

The pipeline's ``delivery_writer`` hook: given the session the alert is being
written in and the planner's records, inserts one ``NotificationDelivery`` row
per record — inside the SAME transaction, so a rollback removes the alert and
its pending deliveries together.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid7

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.alert_delivery import DeliveryStatus, NotificationDelivery
from backend.services.alerting.planner import PlannedDelivery


def _idempotency_key(alert_id: str, channel_id: str, now: datetime) -> str:
    """Unique per-send key: alert+channel pair and the planning second."""
    return f"{alert_id}:{channel_id}:{now.strftime('%Y%m%dT%H%M%S')}:{uuid7().hex[:12]}"


async def write_delivery_rows(
    session: AsyncSession,
    planned_deliveries: Sequence[Any],
) -> int:
    """Insert NotificationDelivery rows for the planner's records.

    Accepts ``PlannedDelivery`` dataclasses (production planner) or dicts
    (test planners). Returns the number of rows written. Runs inside the
    caller's transaction — no commit here.
    """
    now = datetime.now(UTC)
    written = 0
    for record in planned_deliveries:
        if isinstance(record, PlannedDelivery):
            alert_id = getattr(record, "alert_id", None)
            recipient_id = record.recipient_id
            channel_id = record.channel_id
            kind = record.channel_kind.value
            status = record.status.value
            include_names = record.include_names
        else:
            alert_id = record.get("alert_id")
            recipient_id = record["recipient_id"]
            channel_id = record["channel_id"]
            kind = str(record.get("channel_kind", "email"))
            status = str(record.get("status", "pending"))
            include_names = bool(record.get("include_names", False))
        if not alert_id:
            # Planner records on the in-memory path carry alert ids; a record
            # without one cannot become a row (would violate the FK).
            continue
        session.add(
            NotificationDelivery(
                alert_id=alert_id,
                recipient_id=recipient_id,
                channel_id=channel_id,
                kind=kind,
                status=DeliveryStatus(status),
                attempts=0,
                idempotency_key=_idempotency_key(alert_id, channel_id, now),
            )
        )
        written += 1
    if written:
        await session.flush()
    return written
