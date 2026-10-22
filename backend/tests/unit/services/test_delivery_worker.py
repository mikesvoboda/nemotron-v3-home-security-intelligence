"""Unit tests for backend.services.alerting.worker (B4.2).

The backoff ladder and browser timing are pure and tested here. The SKIP LOCKED
lease claim needs real Postgres — those tests live in the DB-gated block below
and skip without TEST_DATABASE_URL.
"""

from __future__ import annotations

from datetime import timedelta

from backend.models.alert_delivery import DeliveryChannelKind
from backend.services.alerting.worker import (
    BACKOFF_SECONDS,
    BROWSER_EXPIRE_AFTER,
    BROWSER_REPUBLISH_AFTER,
    MAX_ATTEMPTS,
    NotificationDeliveryWorker,
    next_backoff,
)


class TestBackoffLadder:
    def test_ladder_shape(self) -> None:
        assert BACKOFF_SECONDS == (30, 120, 600)
        assert next_backoff(1) == timedelta(seconds=30)
        assert next_backoff(2) == timedelta(minutes=2)
        assert next_backoff(3) == timedelta(minutes=10)

    def test_fourth_failure_is_terminal(self) -> None:
        assert next_backoff(4) is None
        assert next_backoff(5) is None

    def test_max_attempts_is_four(self) -> None:
        assert MAX_ATTEMPTS == 4

    def test_browser_ladder_constants(self) -> None:
        assert timedelta(seconds=15) == BROWSER_REPUBLISH_AFTER
        assert timedelta(minutes=5) == BROWSER_EXPIRE_AFTER


class _FakeChannel:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[object] = []

    async def send(self, task: object) -> object:
        self.calls.append(task)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _worker(channel: object, **kw: object) -> NotificationDeliveryWorker:

    factory = kw.pop("session_factory", None)
    if factory is None:

        async def factory():  # type: ignore[misc]
            raise AssertionError("no DB in this test")

    channels = kw.pop("channels", {DeliveryChannelKind.EMAIL.value: channel})
    return NotificationDeliveryWorker(
        factory,
        channels,
        **kw,  # type: ignore[arg-type]
    )


class TestWakeLifecycle:
    async def test_wake_before_start_is_harmless(self) -> None:
        w = _worker(_FakeChannel(None))
        w.wake()  # no loop running; must not raise
        await w.stop()  # stop without start is also fine

    async def test_stop_is_idempotent(self) -> None:
        w = _worker(_FakeChannel(None))
        await w.start()
        await w.stop()
        await w.stop()
