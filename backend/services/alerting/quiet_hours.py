"""Pure quiet-hours check for the delivery planner (B4.2).

Mirrors ``backend.services.notification_filter.NotificationFilter.is_quiet_period``
semantics (day-name match, wrap-midnight comparison) against plain records so
the planner needs no session. The existing method stays the Settings-page
implementation; if the two ever drift, the contract tests on both sides fail.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, time
from typing import Any


def in_quiet_period(local_now: datetime, periods: Sequence[Any]) -> bool:
    """Whether ``local_now`` falls inside any of ``periods``.

    ``periods`` are quiet-hours records (or SimpleNamespace fakes) with
    ``start_time``/``end_time`` ``time`` fields and a ``days`` list of lowercase
    day names. Wrap-midnight periods (start > end) match either side.
    """
    for period in periods:
        day_name = local_now.strftime("%A").lower()
        if day_name not in getattr(period, "days", ()):
            continue
        start = getattr(period, "start_time", None)
        end = getattr(period, "end_time", None)
        if not isinstance(start, time) or not isinstance(end, time):
            continue
        current = local_now.time()
        if start > end:
            if current >= start or current <= end:
                return True
        elif start <= current <= end:
            return True
    return False


__all__ = ["in_quiet_period"]
