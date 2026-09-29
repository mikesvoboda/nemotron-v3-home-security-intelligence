# TARGET-MODULE: backend.services.event_broadcaster
"""Batch-31 kill battery A: module-level machinery of ``event_broadcaster``.

Covers the survivor pools of ``requires_ack`` (3), ``BroadcastRetryMetrics``
(8), ``broadcast_with_retry`` (53), ``broadcast_alert_with_retry_background``
(12), ``get_instance`` (4), ``_get_broadcaster_lock`` (3),
``get_broadcaster`` (10), ``stop_broadcaster`` (4).

Style (batch-30 doctrine): every assert is exact-whole-value against the
SHIPPED contract — retry backoffs pinned by stubbing ``random.uniform``
(factor 0.2) and patching ``asyncio.sleep`` (float arithmetic is EXACT for the
bases used here: 1.2 / 2.4 / 6.0 / 36.0 verified this session), log lines and
``extra`` dicts asserted as whole strings/dicts. A comment above each test
names the surviving mutmut key(s) it kills.

Harness: no pytest fixtures — each test is sync and drives the async contract
through ``_run`` (fresh event loop per call).

Honesty ledger (EQUIVALENT, not covered — proven by construction AND sweep):
all three ``requires_ack`` survivors are value-equivalent. ``_25`` (risk_level
default "" -> None) and ``_30`` ("" -> "XXXX"): the default is observable only
when the key is ABSENT, and every candidate (None, "XXXX") compares unequal to
"critical" exactly like "". ``_27`` (``.get("risk_level", )``): the trailing
comma is a NO-ARG default — that spells the 1-arg ``.get(key)`` returning
None on an absent key (the raising form is 2-positional-arg ``getattr``, not
``dict.get``), so it too is indistinguishable from "" on every input."""

from __future__ import annotations

import asyncio
import logging
import random
import sys
import types
from pathlib import Path
from typing import Any

# Fragment lives outside the repo tree during authoring (/home/agent/runs/b31-frags);
# the sweep always runs with the repo root (or the mutant home) as cwd. Mirror
# that so the imports below resolve in both worlds (b30 precedent).
_ROOT = str(Path.cwd())
if (Path(_ROOT) / "backend" / "services" / "event_broadcaster.py").is_file():
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.api.schemas.websocket import WebSocketAlertEventType  # noqa: E402
from backend.services import event_broadcaster as eb  # noqa: E402
from backend.services.event_broadcaster import (  # noqa: E402
    BroadcastRetryMetrics,
    EventBroadcaster,
    _get_broadcaster_lock,
    broadcast_alert_with_retry_background,
    broadcast_with_retry,
    get_broadcaster,
    requires_ack,
    reset_broadcaster_state,
    stop_broadcaster,
)

_MISSING = object()
_REAL_SLEEP = asyncio.sleep
_REAL_UNIFORM = random.uniform  # captured before any pin replaces it


def _run(coro: Any) -> Any:
    """Run a coroutine on a throwaway loop (fresh loop per call)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _ListHandler(logging.Handler):
    def __init__(self, sink: list[logging.LogRecord]) -> None:
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self.sink.append(record)


class LogCapture:
    """Capture records emitted by the target module's logger only."""

    def __enter__(self) -> LogCapture:
        self.records: list[logging.LogRecord] = []
        self._handler = _ListHandler(self.records)
        eb.logger.addHandler(self._handler)
        self._old_level = eb.logger.level
        eb.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc: object) -> None:
        eb.logger.removeHandler(self._handler)
        eb.logger.setLevel(self._old_level)

    def texts(self) -> list[str]:
        return [r.getMessage() for r in self.records]

    def one(self, level: int, needle: str) -> logging.LogRecord:
        hits = [r for r in self.records if r.levelno == level and needle in r.getMessage()]
        assert len(hits) == 1, (
            f"expected exactly one {logging.getLevelName(level)} record containing "
            f"{needle!r}, got {self.texts()}"
        )
        return hits[0]


def extras(record: logging.LogRecord, *keys: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in keys:
        v = getattr(record, k, _MISSING)
        assert v is not _MISSING, f"record lacks extra key {k!r}"
        out[k] = v
    return out


class FakeRedis:
    """Duck-typed backend.core.redis.RedisClient stand-in."""

    def __init__(self) -> None:
        self.published: list[tuple[Any, Any]] = []
        self.subscribed: list[Any] = []
        self.unsubscribed: list[Any] = []

    async def publish(self, channel: Any, data: Any) -> int:
        self.published.append((channel, data))
        return 3

    async def subscribe(self, channel: Any) -> object:
        self.subscribed.append(channel)
        return types.SimpleNamespace(kind="pubsub")

    async def unsubscribe(self, channel: Any) -> None:
        self.unsubscribed.append(channel)


def patched_sleep() -> list[float]:
    """Patch asyncio.sleep to record delays and return instantly."""
    slept: list[float] = []

    async def fake(t: float, *_args: object, **_kwargs: object) -> None:
        slept.append(t)
        await _REAL_SLEEP(0)

    asyncio.sleep = fake  # type: ignore[assignment]
    return slept


def pinned_jitter() -> list[tuple[float, float]]:
    """Pin the timing jitter (factor 0.2) AND record the bounds it is called with.

    The pin keeps the backoff arithmetic exact; recording the args is what
    makes the ``random.uniform(0.1, 0.3)`` BOUNDS-swap family visible at all
    (``_38`` -> ``(1.1, 0.3)``, ``_39`` -> ``(0.1, 1.3)``): a pin that ignores
    its arguments cannot distinguish a swapped interval from the shipped one,
    and a pin that ignores them AND leaks process-globally additionally blinds
    the pre-existing window-asserting tests (that is how _38/_39 slipped from
    killed to survived in the batch-31 run).
    """
    bounds: list[tuple[float, float]] = []

    def _pin(a: float, b: float) -> float:
        bounds.append((a, b))
        return 0.2

    random.uniform = _pin  # type: ignore[assignment]
    return bounds


def restore_sleep() -> None:
    """Undo BOTH global pins — asyncio.sleep and random.uniform."""
    asyncio.sleep = _REAL_SLEEP  # type: ignore[assignment]
    random.uniform = _REAL_UNIFORM  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# requires_ack (backend/services/event_broadcaster.py L306)
# ---------------------------------------------------------------------------
def test_requires_ack_non_event_types_never_ack() -> None:
    # Pins the outer type gate: `!=` flips, XX/CASE type-key swaps and the
    # always-True/False polarity mutants all die on these three.
    assert requires_ack({"type": "alert_created", "data": {"risk_score": 99}}) is False
    assert requires_ack({"data": {"risk_score": 99}}) is False  # absent type key
    assert requires_ack({"type": "service_status", "data": {"risk_level": "critical"}}) is False


def test_requires_ack_empty_or_missing_data_never_ack() -> None:
    # `data` falsy (absent / None / {}) -> False before the score arms; kills
    # the `if not data: return False` guard's polarity mutants.
    assert requires_ack({"type": "event"}) is False
    assert requires_ack({"type": "event", "data": None}) is False
    assert requires_ack({"type": "event", "data": {}}) is False


def test_requires_ack_score_boundaries() -> None:
    # 80 is the shipped threshold: 79 False / 80 True; a PRESENT-None score
    # must never raise and never ack by itself (P0.25 contract).
    assert requires_ack({"type": "event", "data": {"risk_score": 79}}) is False
    assert requires_ack({"type": "event", "data": {"risk_score": 80}}) is True
    assert requires_ack({"type": "event", "data": {"risk_score": 90}}) is True
    assert requires_ack({"type": "event", "data": {"risk_score": None}}) is False


def test_requires_ack_critical_level_and_absent_key() -> None:
    # risk_level == "critical" acks even with an ABSENT risk_score; the
    # absent-key paths kill requires_ack__mutmut_27 (`.get("risk_level", )`
    # is the 2-arg form mutmut emits — it RAISES KeyError on an absent key).
    assert requires_ack({"type": "event", "data": {"risk_level": "critical"}}) is True
    assert (
        requires_ack({"type": "event", "data": {"risk_score": None, "risk_level": "critical"}})
        is True
    )
    assert requires_ack({"type": "event", "data": {"risk_score": None}}) is False
    assert requires_ack({"type": "event", "data": {"risk_level": "high"}}) is False


# ---------------------------------------------------------------------------
# BroadcastRetryMetrics (L110/L125/L135)
# ---------------------------------------------------------------------------
def test_metrics_record_success_first_try_and_outlier() -> None:
    # kills record_success__mutmut_9 (`in` -> `not in`: the second first-try
    # success takes the else branch and RESETS bucket 0) and __mutmut_10
    # (`+= 1` -> `= 1`: {0: 2} below can't form).
    m = BroadcastRetryMetrics()
    m.record_success(1)
    m.record_success(1)
    m.record_success(5)  # retry_count 4 is OUTSIDE the seeded 0..3 buckets
    assert m.total_attempts == 7
    assert m.successful_broadcasts == 3
    assert m.retry_counts == {0: 2, 1: 0, 2: 0, 3: 0, 4: 1}


def test_metrics_record_failure_counts_accumulate() -> None:
    # kills record_failure__mutmut_3/_6 (`+= 1` -> `= 1`: two failures must
    # yield 2) and the total_attempts += mutants (1 + 3 = 4, not a reset).
    m = BroadcastRetryMetrics()
    m.record_failure(1)
    m.record_failure(3)
    assert m.total_attempts == 4
    assert m.failed_broadcasts == 2
    assert m.retries_exhausted == 2


def test_metrics_to_dict_exact_shape_and_success_rate() -> None:
    # kills to_dict__mutmut_9/_10 ("retry_counts" key XX/CASE renames) and the
    # guard mutants _17 (`+` -> `-`: 1 success + 1 failure takes the else arm
    # -> rate 0.0, shipped 0.5) and _19 (`> 0` -> `> 1`: lone success takes
    # the else arm -> 0.0, shipped 1.0).
    m = BroadcastRetryMetrics()
    assert m.to_dict() == {
        "total_attempts": 0,
        "successful_broadcasts": 0,
        "failed_broadcasts": 0,
        "retries_exhausted": 0,
        "retry_counts": {0: 0, 1: 0, 2: 0, 3: 0},
        "success_rate": 0.0,
    }
    m.record_success(1)
    assert m.to_dict()["success_rate"] == 1.0
    m.record_failure(4)
    d = m.to_dict()
    assert d["success_rate"] == 0.5
    assert d["total_attempts"] == 5
    assert d["retry_counts"] == {0: 1, 1: 0, 2: 0, 3: 0}


# ---------------------------------------------------------------------------
# broadcast_with_retry (L155) — timings pinned via patched sleep + uniform
# ---------------------------------------------------------------------------
def test_retry_first_try_success_records_one_attempt() -> None:
    # kills the record_success(attempt +/- n) family (bucket/total wrong on
    # the shipped {0: 1} + total_attempts 1), `return None` (identity fails),
    # the range(max_retries -/+ n) family at max_retries=3 (loop skipped ->
    # result None / metrics untouched).
    slept = patched_sleep()
    pinned_jitter()
    try:
        m = BroadcastRetryMetrics()
        marker = object()

        async def ok() -> object:
            return marker

        out = _run(broadcast_with_retry(ok, "unit", max_retries=3, metrics=m))
        assert out is marker
        assert slept == []
        assert m.total_attempts == 1
        assert m.successful_broadcasts == 1
        assert m.retry_counts == {0: 1, 1: 0, 2: 0, 3: 0}
    finally:
        restore_sleep()


def test_retry_success_on_second_attempt_pinned_backoff_and_metrics() -> None:
    # First call fails, second succeeds. Jitter pinned 0.2 -> delay for
    # attempt 0 is min(1.0 * 2**0, 30) = 1.0, total = 1.2 EXACTLY. Kills the
    # delay/jitter/min arithmetic family (2**attempt +/- n, base_delay +/- n,
    # `delay * uniform` -> `delay + uniform`) plus the success-path
    # record_success buckets (bucket 1, total 2). The uniform() BOUNDS swaps are
    # NOT killable here -- the pin returns a constant -- they die in
    # test_retry_jitter_interval_is_exactly_one_tenth_to_three_tenths.
    slept = patched_sleep()
    pinned_jitter()
    try:
        m = BroadcastRetryMetrics()
        calls = {"n": 0}

        async def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("boom")
            return "ok"

        with LogCapture() as cap:
            out = _run(
                broadcast_with_retry(flaky, "unit", max_retries=3, base_delay=1.0, metrics=m)
            )
        assert out == "ok"
        assert calls["n"] == 2
        assert slept == [1.2]
        assert m.total_attempts == 2
        assert m.successful_broadcasts == 1
        assert m.retry_counts == {0: 0, 1: 1, 2: 0, 3: 0}
        # the retry-succeeded INFO line pins the `attempt` / `attempt + 1`
        # renderings exactly (kills the success-log arg/XX/case/None family).
        rec = cap.one(logging.INFO, "Broadcast succeeded on retry attempt")
        assert rec.getMessage() == "Broadcast succeeded on retry attempt 1 for unit"
        assert extras(rec, "message_type", "attempt") == {"message_type": "unit", "attempt": 2}
    finally:
        restore_sleep()


def test_retry_jitter_interval_is_exactly_one_tenth_to_three_tenths() -> None:
    # Kills the random.uniform BOUNDS family: ``_38`` spells the call
    # uniform(1.1, 0.3) and ``_39`` uniform(0.1, 1.3) -- both keep the shipped
    # FACTOR arithmetic green (any arg-ignoring pin does), so only asserting the
    # recorded INTERVAL separates them. Two retries -> two jitter draws, both at
    # the shipped interval, and nothing else in the module calls uniform.
    slept = patched_sleep()
    bounds = pinned_jitter()
    try:
        calls = {"n": 0}

        async def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("boom")
            return "ok"

        out = _run(broadcast_with_retry(flaky, "unit", max_retries=3, base_delay=1.0, metrics=None))
        assert out == "ok"
        assert calls["n"] == 3
        assert slept == [1.2, 2.4]
        assert bounds == [(0.1, 0.3), (0.1, 0.3)], bounds
    finally:
        restore_sleep()
        assert random.uniform is _REAL_UNIFORM  # the pin must not leak


def test_retry_warning_line_and_extras_are_exact() -> None:
    # Kills the retry-WARNING family: message renderings (`attempt + 1` /
    # `max_retries + 1` / `:.2f`), extra dict key renames (message_type /
    # attempt / max_retries / retry_delay / error -> XX / CASE / None / drop)
    # and value swaps inside those extras.
    slept = patched_sleep()
    pinned_jitter()
    try:
        calls = {"n": 0}

        async def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("kaboom")
            return "ok"

        with LogCapture() as cap:
            out = _run(
                broadcast_with_retry(flaky, "msgT", max_retries=3, base_delay=2.0, metrics=None)
            )
        assert out == "ok"
        assert slept == [2.4]
        rec = cap.one(logging.WARNING, "Broadcast failed for msgT")
        assert rec.getMessage() == (
            "Broadcast failed for msgT, retrying in 2.40s (attempt 1/4): kaboom"
        )
        assert extras(rec, "message_type", "attempt", "max_retries", "retry_delay", "error") == {
            "message_type": "msgT",
            "attempt": 1,
            "max_retries": 4,
            "retry_delay": 2.4,
            "error": "kaboom",
        }
    finally:
        restore_sleep()


def test_retry_exhausted_raises_original_with_metrics_and_log() -> None:
    # max_retries=1, always fails: exactly TWO attempts, one sleep of 6.0, the
    # ORIGINAL RuntimeError propagates. Kills `last_exception = ""` (raise ""
    # is a TypeError), the tail `raise RuntimeError(...)` mutants, the
    # record_failure(attempt +/- n) family (total_attempts 1+1=2 pins it), the
    # exhaustion ERROR message/extras family, and range boundary mutants
    # (attempts pinned 2, slept exactly one 6.0).
    slept = patched_sleep()
    pinned_jitter()
    try:
        m = BroadcastRetryMetrics()

        async def always_fail() -> None:
            raise RuntimeError("nope")

        with LogCapture() as cap:
            try:
                _run(
                    broadcast_with_retry(always_fail, "t", max_retries=1, base_delay=5.0, metrics=m)
                )
                raise AssertionError("broadcast_with_retry should re-raise RuntimeError")
            except RuntimeError as re_exc:
                assert str(re_exc) == "nope"
        assert slept == [6.0]
        assert m.total_attempts == 2
        assert m.failed_broadcasts == 1
        assert m.retries_exhausted == 1
        assert m.successful_broadcasts == 0
        rec = cap.one(logging.ERROR, "Broadcast failed after 2 attempts for t")
        assert rec.getMessage() == "Broadcast failed after 2 attempts for t: nope"
        assert extras(rec, "message_type", "total_attempts", "error") == {
            "message_type": "t",
            "total_attempts": 2,
            "error": "nope",
        }
        # exc_info=True renders as the active exception triple on the record.
        assert rec.exc_info is not None and str(rec.exc_info[1]) == "nope"
    finally:
        restore_sleep()


def test_retry_max_delay_caps_the_backoff() -> None:
    # base 100 clamped by max_delay 30 -> delay 30, jitter 6.0 -> slept
    # [36.0]. Kills the `min(..., max_delay)` clamp mutants and the
    # max_delay arg-swap mutants (unclamped sleeps 120.0).
    slept = patched_sleep()
    pinned_jitter()
    try:

        async def always_fail() -> None:
            raise RuntimeError("x")

        try:
            _run(
                broadcast_with_retry(
                    always_fail, "t", max_retries=1, base_delay=100.0, max_delay=30.0
                )
            )
        except RuntimeError:
            pass
        assert slept == [36.0]
    finally:
        restore_sleep()


def test_retry_zero_retries_single_attempt_no_sleep() -> None:
    # max_retries=0: one attempt, NO sleep, original error raised, one
    # exhaustion recorded. Kills the `attempt < max_retries` polarity (a
    # mutant sleeping on the last attempt leaves slept == [1.2]) and
    # range(max_retries - 1) (zero attempts -> silent None return).
    slept = patched_sleep()
    pinned_jitter()
    try:
        m = BroadcastRetryMetrics()
        calls = {"n": 0}

        async def always_fail() -> None:
            calls["n"] += 1
            raise ValueError("only-once")

        try:
            _run(broadcast_with_retry(always_fail, "t", max_retries=0, metrics=m))
            raise AssertionError("should re-raise ValueError")
        except ValueError as ve:
            assert str(ve) == "only-once"
        assert calls["n"] == 1
        assert slept == []
        assert m.total_attempts == 1
        assert m.retries_exhausted == 1
    finally:
        restore_sleep()


def test_retry_negative_retries_reaches_unexpected_state() -> None:
    # max_retries=-1 -> range(0) never runs -> last_exception stays None ->
    # the sentinel tail raises RuntimeError("Unexpected state..."). Kills
    # x_broadcast_with_retry__mutmut_1 (`last_exception = ""`: the tail test
    # "" is not None -> raise "" -> TypeError instead of the pinned message)
    # and the tail's own message mutants.
    patched_sleep()
    pinned_jitter()
    try:

        async def never_called() -> str:
            raise AssertionError("must never be called")

        try:
            _run(broadcast_with_retry(never_called, "t", max_retries=-1))
            raise AssertionError("expected the unexpected-state RuntimeError")
        except RuntimeError as re_exc:
            assert str(re_exc) == "Unexpected state in broadcast_with_retry"
    finally:
        restore_sleep()


def test_retry_no_success_log_on_first_try() -> None:
    # The `if attempt > 0:` guard: first-try success must NOT emit the
    # "succeeded on retry" INFO line (kills `>= 0` polarity mutants).
    patched_sleep()
    pinned_jitter()
    try:

        async def ok() -> str:
            return "v"

        with LogCapture() as cap:
            out = _run(broadcast_with_retry(ok, "t", max_retries=3))
        assert out == "v"
        assert not [t for t in cap.texts() if "succeeded on retry" in t]
    finally:
        restore_sleep()


def test_retry_metrics_none_tolerated_on_both_paths() -> None:
    # metrics=None must work on BOTH the success and the exhaustion path
    # (kills the `if metrics is not None:` polarity flips — they would call a
    # method on None and crash).
    patched_sleep()
    pinned_jitter()
    try:

        async def ok() -> str:
            return "s"

        assert _run(broadcast_with_retry(ok, "t", max_retries=2, metrics=None)) == "s"

        async def bad() -> None:
            raise RuntimeError("e")

        try:
            _run(broadcast_with_retry(bad, "t", max_retries=0, metrics=None))
            raise AssertionError("should re-raise")
        except RuntimeError:
            pass
    finally:
        restore_sleep()


# ---------------------------------------------------------------------------
# broadcast_alert_with_retry_background (L257)
# ---------------------------------------------------------------------------
class RecordingBroadcaster:
    def __init__(self, fail: bool) -> None:
        self.calls: list[tuple[Any, Any]] = []
        self.fail = fail

    async def broadcast_alert(self, alert_data: dict[str, Any], event_type: Any) -> int:
        self.calls.append((alert_data, event_type))
        if self.fail:
            raise RuntimeError("dead")
        return 1


def test_alert_background_success_calls_through_once() -> None:
    # Pins the lambda's exact call args (alert_data + event_type identity);
    # single-attempt success emits NO log at all (kills the background wrapper
    # calling broadcast() without event_type, the `await` drop, metrics wiring).
    patched_sleep()
    pinned_jitter()
    try:
        alert = {"id": "a-1"}
        b = RecordingBroadcaster(fail=False)
        m = BroadcastRetryMetrics()
        et = WebSocketAlertEventType.ALERT_CREATED
        with LogCapture() as cap:
            _run(broadcast_alert_with_retry_background(b, alert, et, max_retries=2, metrics=m))
        assert b.calls == [(alert, et)]
        assert m.total_attempts == 1
        assert m.successful_broadcasts == 1
        assert cap.records == []
    finally:
        restore_sleep()


def test_alert_background_swallows_failure_and_logs_exact() -> None:
    # The background contract NEVER raises. Pins BOTH the inner retry ERROR
    # (message_type spelling "alert_alert_acknowledged" — kills the
    # f"alert_{event_type.value}" family) and the wrapper's own ERROR message
    # + extras (event_type.value / alert_data renames), plus single-attempt
    # metrics with max_retries=0.
    patched_sleep()
    pinned_jitter()
    try:
        alert = {"id": "a-2"}
        b = RecordingBroadcaster(fail=True)
        m = BroadcastRetryMetrics()
        et = WebSocketAlertEventType.ALERT_ACKNOWLEDGED
        with LogCapture() as cap:
            _run(broadcast_alert_with_retry_background(b, alert, et, max_retries=0, metrics=m))
        assert m.failed_broadcasts == 1
        assert m.retries_exhausted == 1
        inner = cap.one(logging.ERROR, "Broadcast failed after 1 attempts")
        assert inner.getMessage() == (
            "Broadcast failed after 1 attempts for alert_alert_acknowledged: dead"
        )
        rec = cap.one(logging.ERROR, "Background broadcast failed permanently")
        assert rec.getMessage() == (
            "Background broadcast failed permanently for alert alert_acknowledged: dead"
        )
        assert extras(rec, "event_type", "alert_data") == {
            "event_type": "alert_acknowledged",
            "alert_data": alert,
        }
    finally:
        restore_sleep()


# ---------------------------------------------------------------------------
# get_instance / lock / get_broadcaster / stop_broadcaster (L460, L2370-2437)
# ---------------------------------------------------------------------------
def test_get_instance_round_trip() -> None:
    sentinel = object()
    old = eb._broadcaster
    try:
        eb._broadcaster = sentinel  # type: ignore[assignment]
        assert EventBroadcaster.get_instance() is sentinel
    finally:
        eb._broadcaster = old


def test_get_instance_error_message_exact_when_uninitialized() -> None:
    # kills get_instance__mutmut_2 (RuntimeError(None)), _3 (XX wrap), _4/_5
    # (case swaps): the message is asserted as the full shipped string.
    reset_broadcaster_state()
    try:
        try:
            EventBroadcaster.get_instance()
            raise AssertionError("expected RuntimeError")
        except RuntimeError as re_exc:
            assert str(re_exc) == (
                "EventBroadcaster has not been initialized. "
                "Call get_broadcaster() during application startup."
            )
    finally:
        reset_broadcaster_state()


def test_broadcaster_lock_is_lazy_singleton() -> None:
    # kills the `_broadcaster_lock = None` assignment mutant (next call
    # crashes), the double-check guard flip (fresh lock per call), and the
    # early-return mutants.
    reset_broadcaster_state()
    try:
        first = _get_broadcaster_lock()
        assert isinstance(first, asyncio.Lock)
        second = _get_broadcaster_lock()
        assert second is first
        eb._broadcaster_lock = None
        third = _get_broadcaster_lock()
        assert isinstance(third, asyncio.Lock)
    finally:
        reset_broadcaster_state()


def test_get_broadcaster_slow_then_fast_path_then_stop() -> None:
    # Slow path builds EventBroadcaster off settings.redis_event_channel,
    # STARTS it (subscribe recorded), stores the global, logs init. Fast path
    # returns the SAME instance WITHOUT a second subscribe. stop_broadcaster
    # clears the global and unsubscribes. Kills the fast-path guard flip, the
    # `await broadcaster.start()` drop, the missing `_broadcaster = None` on
    # stop, the `if _broadcaster:` polarity on stop, and both lifecycle logs.
    from unittest.mock import patch

    reset_broadcaster_state()
    settings = types.SimpleNamespace(redis_event_channel="unit:test:events")
    redis = FakeRedis()
    logs1: list[str] = []
    logs2: list[str] = []

    async def scenario() -> tuple[Any, Any]:
        # ONE loop for the whole lifecycle: start tasks and stop() must share
        # it (cross-loop task await is forbidden).
        with LogCapture() as cap:
            b = await get_broadcaster(redis)
            logs1.extend(cap.texts())
            b2 = await get_broadcaster(redis)
        with LogCapture() as cap2:
            await stop_broadcaster()
            logs2.extend(cap2.texts())
        return b, b2

    try:
        with patch.object(eb, "get_settings", autospec=True, return_value=settings):
            b, b2 = _run(scenario())
        assert isinstance(b, EventBroadcaster)
        assert b.channel_name == "unit:test:events"
        assert redis.subscribed == ["unit:test:events"]
        assert "Global event broadcaster initialized" in logs1
        assert b2 is b
        assert redis.subscribed == ["unit:test:events"]  # no second subscribe
        assert eb._broadcaster is None
        assert redis.unsubscribed == ["unit:test:events"]
        assert "Global event broadcaster stopped" in logs2
    finally:
        eb._broadcaster = None
        reset_broadcaster_state()


def test_get_broadcaster_double_check_uses_lock() -> None:
    # Hold the init lock and launch get_broadcaster: it parks on the lock; we
    # store an instance and release; it must then take the post-lock
    # double-check and return the STORED instance (not build its own).
    # Proves `async with lock` and the `if _broadcaster is None:` recheck.
    from unittest.mock import patch

    reset_broadcaster_state()
    settings = types.SimpleNamespace(redis_event_channel="unit:lock:events")
    redis = FakeRedis()

    async def scenario() -> Any:
        lock = _get_broadcaster_lock()
        async with lock:
            pending = asyncio.ensure_future(get_broadcaster(redis))
            await asyncio.sleep(0)  # let it start and park on the lock
            stored = EventBroadcaster(redis, channel_name="unit:lock:events")
            eb._broadcaster = stored
        return await pending

    try:
        with patch.object(eb, "get_settings", autospec=True, return_value=settings):
            out = _run(scenario())
        assert isinstance(out, EventBroadcaster)
        assert out is eb._broadcaster
        assert out.channel_name == "unit:lock:events"  # not a freshly built one
        assert redis.subscribed == []  # the parked call never started redis work
    finally:
        eb._broadcaster = None
        reset_broadcaster_state()
