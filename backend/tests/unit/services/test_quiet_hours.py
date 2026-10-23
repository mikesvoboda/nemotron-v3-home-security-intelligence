"""Unit tests for backend.services.alerting.quiet_hours (B4.2).

The planner decides suppressed/expired against these pure semantics, so the
wrap-midnight shape and the day-name gate are pinned here the same way the
Settings-page filter pins its own (the module docstring's drift contract).
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from types import SimpleNamespace

from backend.services.alerting.quiet_hours import in_quiet_period


def _period(start: str, end: str, days: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        start_time=time.fromisoformat(start),
        end_time=time.fromisoformat(end),
        days=days or ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
    )


# 2026-10-22 is a Thursday; 03:00 local is inside a 22:00-06:00 wrap.
_THU_0300 = datetime(2026, 10, 22, 3, 0, tzinfo=UTC)
_THU_1200 = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


class TestInQuietPeriod:
    def test_inside_normal_period(self) -> None:
        assert in_quiet_period(_THU_1200, [_period("10:00", "14:00")]) is True

    def test_outside_normal_period(self) -> None:
        assert in_quiet_period(_THU_1200, [_period("13:00", "14:00")]) is False

    def test_wrap_midnight_matches_both_sides(self) -> None:
        assert in_quiet_period(_THU_0300, [_period("22:00", "06:00")]) is True
        assert in_quiet_period(_THU_1200, [_period("22:00", "06:00")]) is False

    def test_day_name_gates_the_period(self) -> None:
        # Friday 03:00 — the wrap period covers 22:00-06:00, but days excludes friday.
        friday = datetime(2026, 10, 23, 3, 0, tzinfo=UTC)
        assert in_quiet_period(friday, [_period("22:00", "06:00", days=["monday"])]) is False

    def test_empty_periods_is_never_quiet(self) -> None:
        assert in_quiet_period(_THU_1200, []) is False

    def test_non_time_fields_are_skipped(self) -> None:
        # A period whose start/end are not ``time`` objects cannot match —
        # the planner feeds records straight from the DB, so a malformed row
        # degrades to "not quiet" rather than raising mid-plan.
        broken = SimpleNamespace(start_time="22:00", end_time="06:00", days=["thursday"])
        assert in_quiet_period(_THU_0300, [broken]) is False
