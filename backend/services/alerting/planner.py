"""Alert delivery planner (B4.2).

Decides, for an alert, which recipient channels receive it and in what state
each delivery starts. The decision core is pure — no I/O, no session — so it is
tested table-driven; the production wrapper (``default_planner``) supplies the
recipient/channel records via a loader and is injected into the alert pipeline
in place of the empty planner.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from backend.models.alert_delivery import DeliveryChannelKind, DeliveryStatus
from backend.services.alerting.quiet_hours import in_quiet_period


@dataclass(frozen=True)
class PlannedDelivery:
    """One delivery the pipeline should record, before any row is written."""

    alert_id: str | None
    recipient_id: str
    channel_id: str
    channel_kind: DeliveryChannelKind
    status: DeliveryStatus
    include_names: bool


def plan(
    alert: Any,
    recipients: Sequence[Any],
    *,
    now: datetime,
    tz: str,
    stale: bool = False,
) -> list[PlannedDelivery]:
    """Plan the deliveries for ``alert`` against the given recipients.

    Pure: reads only the passed records and ``now``/``tz``/``stale``. Channels
    are planned per recipient; non-browser channels inside the recipient's quiet
    hours are planned as ``suppressed`` (recorded, not sent) unless the alert is
    critical and the recipient allows critical to break through. A stale alert
    (recovered by the sweep) expires every channel — late sends are not useful,
    but the record still shows what the alert would have done.
    """
    is_critical = getattr(alert, "severity", None) == "critical"
    planned: list[PlannedDelivery] = []
    try:
        local_now = now.astimezone(ZoneInfo(tz))
    except ValueError, KeyError:
        local_now = now
    for recipient in recipients:
        if not getattr(recipient, "enabled", True):
            continue
        breaks_quiet = is_critical and getattr(recipient, "critical_breaks_quiet", True)
        periods = getattr(recipient, "quiet_periods", ()) or ()
        for channel in getattr(recipient, "channels", ()) or ():
            if not getattr(channel, "enabled", True):
                continue
            # A channel row's kind is stored as the enum's value; coerce both
            # the enum member and the bare string to the member the dataclass
            # carries. An unknown kind is skipped — the worker has no adapter
            # for it, so planning it would only ladder it to failed.
            kind_raw: Any = getattr(channel, "kind", None)
            kind_name = getattr(kind_raw, "value", kind_raw)
            try:
                kind = DeliveryChannelKind(kind_name)
            except ValueError, TypeError:
                continue
            status = DeliveryStatus.PENDING
            if stale:
                status = DeliveryStatus.EXPIRED
            elif kind is not DeliveryChannelKind.BROWSER:
                quiet = in_quiet_period(local_now, periods)
                if quiet and not breaks_quiet:
                    status = DeliveryStatus.SUPPRESSED
            planned.append(
                PlannedDelivery(
                    alert_id=str(getattr(alert, "id", None)),
                    recipient_id=recipient.id,
                    channel_id=channel.id,
                    channel_kind=kind,
                    status=status,
                    include_names=bool(getattr(channel, "include_names", False)),
                )
            )
    return planned


def default_planner(
    load_recipients: Callable[[], Sequence[Any]],
    *,
    tz: str = "UTC",
) -> Callable[..., list[PlannedDelivery]]:
    """Wrap the pure core in the pipeline's hook shape.

    The pipeline calls ``self._planner(alert, now=now, stale=is_stale)`` — a
    ``Callable[..., Sequence[Any]]``. The wrapper loads recipients at call time
    (the DB path has a session in scope; the loader closes over it) and applies
    the household timezone.
    """

    def _plan(alert: Any, *, now: datetime, stale: bool) -> list[PlannedDelivery]:
        return plan(
            alert,
            load_recipients(),
            now=now,
            tz=tz,
            stale=stale,
        )

    return _plan


__all__ = ["PlannedDelivery", "default_planner", "plan"]
