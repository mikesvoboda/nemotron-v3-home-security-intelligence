"""Production wiring for the B4.2 delivery planner and row writer.

The pipeline's planner hook is ``Callable[..., Sequence[Any]]`` called as
``self._planner(alert, now=now, stale=is_stale)`` — a sync callable. The
production decision needs recipients (with channels and quiet periods) and
the household timezone, which are async loads, so they are preloaded ONCE
per pipeline run (inside the same transaction as the alert) and the hook is
a sync closure over the preloaded records:

    planner = await build_default_planner(session)   # inside the pipeline tx
    pipeline = AlertPipeline(..., planner=planner, delivery_writer=write_delivery_rows)

The pure decision core stays in planner.py; this module is the thin loader
the build plan calls for.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.alert_delivery import Recipient
from backend.models.property import Property
from backend.services.alerting.planner import default_planner

_FALLBACK_TZ = "UTC"


async def household_timezone(session: AsyncSession) -> str:
    """The household timezone from the Property row; UTC when unset."""
    prop = (
        (await session.execute(select(Property).order_by(Property.id.asc()).limit(1)))
        .scalars()
        .first()
    )
    tz = getattr(prop, "timezone", None) if prop is not None else None
    return tz or _FALLBACK_TZ


async def load_recipients_with_channels(session: AsyncSession) -> Sequence[Any]:
    """Enabled recipients with channels and quiet periods, preloaded.

    The planner's quiet-hours decision needs each recipient's
    ``quiet_periods``; one grouped query attaches them so the pure core sees
    complete records and issues no I/O of its own.
    """
    from backend.models.notification_preferences import QuietHoursPeriod

    recipients = (
        (await session.execute(select(Recipient).where(Recipient.enabled.is_(True))))
        .scalars()
        .all()
    )
    periods = (await session.execute(select(QuietHoursPeriod))).scalars().all()
    by_recipient: dict[str, list[Any]] = {}
    for period in periods:
        if period.recipient_id:
            by_recipient.setdefault(str(period.recipient_id), []).append(period)
    for recipient in recipients:
        recipient.quiet_periods = by_recipient.get(str(recipient.id), [])
    return recipients


async def build_default_planner(session: AsyncSession) -> Callable[..., list[Any]]:
    """Preload recipients + tz inside the pipeline's transaction, return the hook.

    The returned callable is the sync hook shape the pipeline calls:
    ``hook(alert, now=..., stale=...)``. Loading here (per pipeline run)
    keeps the transaction-consistent read: the planner decides on the same
    snapshot the alert is written in.
    """
    recipients = await load_recipients_with_channels(session)
    tz = await household_timezone(session)
    return default_planner(lambda: recipients, tz=tz)
