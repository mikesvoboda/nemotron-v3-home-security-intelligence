"""Unit tests for backend.services.alerting.planner (B4.2).

The planner is the pure decision core of delivery planning: given an alert and
the recipient/channel records, it decides which deliveries to create and which
state each starts in. Table-driven here — no I/O, no session, fixed clocks.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from types import SimpleNamespace

from backend.models.alert_delivery import DeliveryChannelKind, DeliveryStatus
from backend.services.alerting.planner import (
    PlannedDelivery,
    default_planner,
    plan,
)


def _tz_hour(hour: int) -> datetime:
    """A fixed instant (2026-10-21 HH:00 UTC) — tests pass a household tz alongside."""
    return datetime(2026, 10, 21, hour, 0, 0, tzinfo=UTC)


def _channel(kind: str, **kw) -> SimpleNamespace:
    base = {
        "id": f"ch-{kind}",
        "kind": DeliveryChannelKind(kind),
        "enabled": True,
        "target": "ch@example.com",
        "include_names": False,
        "on_local_network": False,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _recipient(name: str = "Household", **kw) -> SimpleNamespace:
    base = {
        "id": f"rec-{name}",
        "name": name,
        "enabled": True,
        "critical_breaks_quiet": True,
        "quiet_periods": (),
        "channels": (),
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _alert(severity: str = "medium", **kw) -> SimpleNamespace:
    base = {
        "id": "a-1",
        "title": "Person detected",
        "severity": severity,
        "camera_id": "front_door",
        "event_id": 42,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _quiet(
    start: str,
    end: str,
    days: tuple[str, ...] = (
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ),
) -> SimpleNamespace:
    return SimpleNamespace(
        start_time=time.fromisoformat(start),
        end_time=time.fromisoformat(end),
        days=list(days),
    )


class TestEnabledRecipients:
    def test_disabled_recipient_is_skipped_entirely(self) -> None:
        rec = _recipient(enabled=False, channels=(_channel("browser"),))
        planned = plan(_alert(), (rec,), now=_tz_hour(12), tz="UTC")
        assert planned == []

    def test_disabled_channel_is_skipped(self) -> None:
        rec = _recipient(channels=(_channel("browser", enabled=False),))
        planned = plan(_alert(), (rec,), now=_tz_hour(12), tz="UTC")
        assert planned == []

    def test_browser_channel_always_planned_pending(self) -> None:
        rec = _recipient(channels=(_channel("browser"),))
        planned = plan(_alert(), (rec,), now=_tz_hour(12), tz="UTC")
        assert len(planned) == 1
        assert planned[0].status is DeliveryStatus.PENDING
        assert planned[0].channel_kind is DeliveryChannelKind.BROWSER


class TestQuietHours:
    def test_non_browser_channel_in_quiet_hours_is_suppressed(self) -> None:
        rec = _recipient(quiet_periods=(_quiet("10:00", "14:00"),), channels=(_channel("email"),))
        planned = plan(_alert(), (rec,), now=_tz_hour(12), tz="UTC")
        assert len(planned) == 1
        assert planned[0].status is DeliveryStatus.SUPPRESSED

    def test_non_browser_channel_outside_quiet_hours_is_pending(self) -> None:
        rec = _recipient(quiet_periods=(_quiet("10:00", "14:00"),), channels=(_channel("email"),))
        planned = plan(_alert(), (rec,), now=_tz_hour(20), tz="UTC")
        assert len(planned) == 1
        assert planned[0].status is DeliveryStatus.PENDING

    def test_quiet_hours_wrap_midnight(self) -> None:
        rec = _recipient(quiet_periods=(_quiet("22:00", "06:00"),), channels=(_channel("webhook"),))
        planned = plan(_alert(), (rec,), now=_tz_hour(3), tz="UTC")
        assert planned[0].status is DeliveryStatus.SUPPRESSED

    def test_browser_channel_ignores_quiet_hours(self) -> None:
        rec = _recipient(
            quiet_periods=(_quiet("10:00", "14:00"),),
            channels=(_channel("browser"), _channel("email")),
        )
        planned = plan(_alert(), (rec,), now=_tz_hour(12), tz="UTC")
        by_kind = {p.channel_kind: p.status for p in planned}
        assert by_kind[DeliveryChannelKind.BROWSER] is DeliveryStatus.PENDING
        assert by_kind[DeliveryChannelKind.EMAIL] is DeliveryStatus.SUPPRESSED

    def test_quiet_hours_respect_household_timezone(self) -> None:
        # 12:00 UTC is 22:00 in UTC+10 — inside a 22:00-06:00 window.
        rec = _recipient(quiet_periods=(_quiet("22:00", "06:00"),), channels=(_channel("email"),))
        planned = plan(_alert(), (rec,), now=_tz_hour(12), tz="Australia/Brisbane")
        assert planned[0].status is DeliveryStatus.SUPPRESSED

    def test_quiet_period_inactive_day_is_ignored(self) -> None:
        # 2026-10-21 is a Wednesday; make the window Sunday-only.
        rec = _recipient(
            quiet_periods=(_quiet("00:00", "23:59", days=("sunday",)),),
            channels=(_channel("email"),),
        )
        planned = plan(_alert(), (rec,), now=_tz_hour(12), tz="UTC")
        assert planned[0].status is DeliveryStatus.PENDING


class TestCriticalBreakthrough:
    def test_critical_breaks_quiet_hours_by_default(self) -> None:
        rec = _recipient(quiet_periods=(_quiet("10:00", "14:00"),), channels=(_channel("email"),))
        planned = plan(_alert(severity="critical"), (rec,), now=_tz_hour(12), tz="UTC")
        assert planned[0].status is DeliveryStatus.PENDING

    def test_critical_respected_opt_out(self) -> None:
        rec = _recipient(
            critical_breaks_quiet=False,
            quiet_periods=(_quiet("10:00", "14:00"),),
            channels=(_channel("email"),),
        )
        planned = plan(_alert(severity="critical"), (rec,), now=_tz_hour(12), tz="UTC")
        assert planned[0].status is DeliveryStatus.SUPPRESSED


class TestIncludeNames:
    def test_include_names_flag_is_carried_on_the_plan(self) -> None:
        on = _channel("email", include_names=True)
        off = _channel("email", id="ch-off", include_names=False)
        rec = _recipient(channels=(on, off))
        planned = plan(_alert(), (rec,), now=_tz_hour(12), tz="UTC")
        flags = {p.channel_id: p.include_names for p in planned}
        assert flags["ch-email"] is True
        assert flags["ch-off"] is False


class TestStale:
    def test_stale_alert_non_browser_channels_expire(self) -> None:
        rec = _recipient(channels=(_channel("email"), _channel("browser")))
        planned = plan(_alert(), (rec,), now=_tz_hour(12), tz="UTC", stale=True)
        by_kind = {p.channel_kind: p.status for p in planned}
        assert by_kind[DeliveryChannelKind.EMAIL] is DeliveryStatus.EXPIRED
        # Browser rows still record — the browser UI shows the alert arrived late.
        assert by_kind[DeliveryChannelKind.BROWSER] is DeliveryStatus.EXPIRED


class TestDefaults:
    def test_default_planner_accepts_pipeline_call_shape(self) -> None:
        """The pipeline hook is `self._planner(alert, now=now, stale=is_stale)`."""
        rec = _recipient(channels=(_channel("browser"),))
        planner = default_planner(lambda: (rec,))
        planned = planner(_alert(), now=_tz_hour(12), stale=False)
        assert len(planned) == 1
        assert isinstance(planned[0], PlannedDelivery)
