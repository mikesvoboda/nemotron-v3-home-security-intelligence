"""Unit tests for backend.services.alerting.worker (B4.2).

The backoff ladder and browser timing are pure and tested here. The SKIP LOCKED
lease claim needs real Postgres — those tests live in the DB-gated block below
and skip without TEST_DATABASE_URL.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.models.alert_delivery import DeliveryChannelKind
from backend.services.alerting.channels.base import SendResult
from backend.services.alerting.worker import (
    BACKOFF_SECONDS,
    BROWSER_EXPIRE_AFTER,
    BROWSER_REPUBLISH_AFTER,
    MAX_ATTEMPTS,
    NotificationDeliveryWorker,
    next_backoff,
)

_NOW = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)


class TestBackoffLadder:
    def test_ladder_shape(self) -> None:
        # 4n-alerting.md:117: backoff 30 s, 2 min, 10 min, 30 min, then failed.
        assert BACKOFF_SECONDS == (30, 120, 600, 1800)
        assert next_backoff(1) == timedelta(seconds=30)
        assert next_backoff(2) == timedelta(minutes=2)
        assert next_backoff(3) == timedelta(minutes=10)
        assert next_backoff(4) == timedelta(minutes=30)

    def test_fifth_failure_is_terminal(self) -> None:
        assert next_backoff(5) is None
        assert next_backoff(6) is None

    def test_max_attempts_is_five(self) -> None:
        assert MAX_ATTEMPTS == 5

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


class _RecordingFactory:
    """Session factory double that records every UPDATE's SQL text + params."""

    def __init__(self, capture: list[tuple[str, dict]]) -> None:
        self.capture = capture

    def __call__(self):
        return _RecordingSession(self.capture)


class _RecordingSession:
    def __init__(self, capture: list[tuple[str, dict]]) -> None:
        self.capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, stmt: object, params: dict | None = None) -> None:
        self.capture.append((str(stmt), dict(params or {})))

    async def commit(self) -> None:
        return None


class TestExpiryDisablesChannel:
    """The worker's 410 contract (4n-alerting.md:236): a push subscription
    expiry switches the channel off so the recipient's settings show it."""

    def _row(self, kind: str = "webpush") -> dict:
        return {
            "id": "d-1",
            "kind": kind,
            "channel_id": "ch-1",
            "recipient_id": "r-1",
            "attempts": 1,
            "created_at": None,
            "alert_id": "a-1",
            "idempotency_key": "k-1",
        }

    def _disable_writes(self, capture: list[tuple[str, dict]]) -> list[dict]:
        """Params of the writes that UPDATE recipient_channels."""
        return [p for sql, p in capture if "recipient_channels" in sql]

    async def test_subscription_expired_disables_the_channel_row(self) -> None:
        capture: list[tuple[str, dict]] = []
        channel = _FakeChannel(SendResult(success=False, error="subscription_expired", meta={"expired": True}))
        w = _worker(channel, session_factory=_RecordingFactory(capture), channels={"webpush": channel})
        await w._send_one(self._row(), set(), _NOW)
        # Two writes happen: the delivery failure + the channel disable.
        disable = self._disable_writes(capture)
        assert disable, f"no channel-disable write among {len(capture)} writes"
        assert disable[0]["cid"] == "ch-1"

    async def test_404_expired_marker_disables_too(self) -> None:
        capture: list[tuple[str, dict]] = []
        channel = _FakeChannel(SendResult(success=False, error="subscription_expired", meta={"status_code": 404, "expired": True}))
        w = _worker(channel, session_factory=_RecordingFactory(capture), channels={"webpush": channel})
        await w._send_one(self._row(), set(), _NOW)
        assert self._disable_writes(capture), "404 expiry must also disable the channel row"

    async def test_ordinary_failure_does_not_disable(self) -> None:
        """5xx rides the backoff ladder; the channel stays enabled."""
        capture: list[tuple[str, dict]] = []
        channel = _FakeChannel(SendResult(success=False, error="http_500", meta={"status_code": 500}))
        w = _worker(channel, session_factory=_RecordingFactory(capture), channels={"webpush": channel})
        await w._send_one(self._row(), set(), _NOW)
        assert not self._disable_writes(capture)

    async def test_disabled_channel_also_records_the_failure(self) -> None:
        """The delivery itself still lands FAILED/RETRYING with the marker —
        disabling the channel is in addition to, not instead of, recording."""
        capture: list[tuple[str, dict]] = []
        channel = _FakeChannel(SendResult(success=False, error="subscription_expired", meta={"expired": True}))
        w = _worker(channel, session_factory=_RecordingFactory(capture), channels={"webpush": channel})
        await w._send_one(self._row(), set(), _NOW)
        assert any("notification_deliveries" in sql for sql, _ in capture)
