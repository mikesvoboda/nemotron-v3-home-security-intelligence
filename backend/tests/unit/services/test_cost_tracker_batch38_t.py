# TARGET-MODULE: backend.services.cost_tracker
"""Battery T - campaign #18 of the ladder (batch-38): kill-real coverage for
``backend/services/cost_tracker.py`` (277 survivors at 51.40% entering).

Harness-compatible by design (batch-30 single-process sweep): every test is a
module-level sync ``test_*()`` with no fixtures and no parametrize; coroutines
run through ``asyncio.run`` inside. The file is also collected by normal
pytest in the repo tree, so every seam swap restores in ``finally``.

Why the shipped battery leaves 277 survivors: it checks "a record came back"
and aggregate sanity, never the EXACT float arithmetic (every ``/1000.0 ->
/1001.0`` and ``* -> /`` mutant survives a tolerant sum-check), never the
metrics call SIGNATURES (the ``record_gpu_seconds(model, dur)`` family with
None/XX/UPPER/dropped args is invisible without a call-recording spy pinned to
``(name, args, kwargs)`` equality), never the Redis wire shape (persist's
8-key hash mapping and ``expire(key, 90*24*60*60)`` product, load's decoded
``get(key, default)`` family - killable only with BOTH present-field and
absent-field polarities, per the trailing-comma ARG-DELETION rule), and never
the ``datetime.now(UTC) -> now(None)`` tz discriminator (naive vs aware - the
only discriminators are ``utcoffset()`` on the record, or a swapped fake clock
whose aware and naive readings land on DIFFERENT dates so dict keys and
monthly sums split). The budget ternaries need the exact-boundary
polarities: used EXACTLY at budget (``>=`` vs ``>``), EXACTLY at threshold,
budget EXACTLY 0 (``or True``/``>= 0`` predicates turn the ratio ternary into
ZeroDivisionError), budget 0.5 (``> 1`` predicate flips the branch while the
ratio still crosses 1.0). ``get_usage_summary`` is killed by ONE strict
whole-dict ``==`` against a hand-built literal: the XX/UPPER key family only
dies when the expected dict's keys are exact.

Honesty ledger - dispositions registered EQUIVALENT (the sweep must show
GREEN on exactly these unless the sweep proves otherwise; anything else GREEN
is a test gap). Each is a BODY proof, not a diff shape:

* estimate_cost m3/m10/m22/m27 EQUIVALENT - ``if x > 0:`` -> ``if x >= 0:``
*  for the four int axes (input_tokens/output_tokens/images/operations): the
*  only newly-entered case is x == 0, whose term is ``0 / 1000.0 * price`` or
*  ``0 * price`` == 0.0, and ``cost += 0.0`` onto ``cost = 0.0`` is the float
*  identity (even the sign: ``0.0 + 0.0`` is +0.0). No input observes the
*  branch.
* estimate_cost m17 EQUIVALENT - same ``> 0 -> >= 0`` on the float axis
*  gpu_seconds: newly-entered values are +0.0 and -0.0; ``-0.0 * 0.000139``
*  is -0.0 and ``0.0 + -0.0`` is +0.0; with any earlier positive addend the
*  sum is unchanged - -0.0 is unobservable through ``+`` here and equality
*  compares -0.0 == 0.0 True everywhere downstream.
* estimate_cost m5 EQUIVALENT - the FIRST addend line ``cost += X`` -> ``cost
*  = X``: when that line runs cost is still exactly 0.0 (nothing executes
*  before it inside the function), and ``0.0 + X == X`` bit-identically for
*  the strictly-positive X the guard admits.
* get_budget_status m45/m53 EQUIVALENT - ``exceeded = ratio >= 1.0 if
*  (budget > 0) or True else False`` (m53 = monthly mirror): with budget <= 0
*  the UNMUTATED ratio ternary yields exactly 0.0, so the now-taken branch
*  evaluates ``0.0 >= 1.0`` -> False - identical to the else-branch False;
*  with budget > 0 the predicate is irrelevant.
* get_budget_status m48/m56 EQUIVALENT - ``if budget >= 0 else False`` (m56 =
*  monthly mirror): budget > 0 unchanged; budget == 0 takes the branch with
*  ratio 0.0 -> ``0.0 >= 1.0`` False (same as else-False); budget < 0 falls
*  to False. Every outcome matches orig.

All other 267 survivor keys have an explicit kill polarity in this battery;
run-1 sweep: RED=267 GREEN=10 of 277 == this ledger exactly, and run 1
banked it: 570 -> 577 keys, 12 survivors == THIS LEDGER 10 + 2 body-BIRTHS
that inherited renumbered slot numbers (_update_daily_usage m45
set_cost_per_event(total_cost * total_events) - invisible while total_events
was 1 in the only test reaching the line, now killed by the events=2 full-
shape test; load_usage m13 `not data: break` - break and continue coincide
on a single key, now killed by empty-key-first-then-good-key ordering). The
number-keyed delta missed those 2 births (slot-inheritance, renumber capture
#4); the body crosswalk found them: 0 true kill losses, old load_usage m13
sits at new m14 still killed. Ledger stays the 10 rows above - both births
are KILLABLE and killed, not equivalents.

Run 2 killed both birth keys (bank 566/577) but LOST one kill: m43
(`total_events > 0` -> `> 1` in _update_daily_usage) - its only kill was
MY pre-edit full-shape test at events 1 (mutant skips the call, spy
length differs); raising that test to events 2 for the m45 kill made both
arms fire identically. Disclosed honestly: the pre-run-2 full-577 sweep
showed m43 GREEN and I misread it as a shipped-suite kill. Fixed with a
dedicated events-EXACTLY-1 test (the two tests cover each other's blind
spot: / vs * coincide at 1, >0 vs >1 coincide at 2).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

from backend.services.cost_tracker import (
    CostTracker,
    DailyUsage,
    UsageRecord,
    get_cost_tracker,
    reset_cost_tracker,
)

_REAL_DT = datetime  # captured BEFORE any clock swap


def _globals_of(fn: Any) -> dict[str, Any]:
    """Module globals of the REAL function (mutant-tree wrappers delegate)."""
    f = fn
    while hasattr(f, "__wrapped__"):
        f = f.__wrapped__
    return f.__globals__


_G = _globals_of(CostTracker.track_llm_usage)


def _swap(key: str, value: Any) -> Any:
    old = _G[key]

    def restore() -> None:
        _G[key] = old

    _G[key] = value
    return restore


class _LogCap:
    """Records (level, msg) pairs; installed as the module logger."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def _rec(self, level: str) -> Any:
        def _f(msg: Any, *args: Any, **kwargs: Any) -> None:
            self.calls.append((level, msg))

        return _f

    def __getattr__(self, name: str) -> Any:
        return self._rec(name)

    def names(self) -> list[tuple[str, Any]]:
        return list(self.calls)


class _MetricsSpy:
    """Records EVERY metrics call as (name, args, kwargs); assert WHOLE-LIST
    equality - arg renames, None swaps and trailing-comma arg-DELETIONS all
    change the tuple."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Any:
        def _rec(*args: Any, **kwargs: Any) -> None:
            self.calls.append((name, args, kwargs))

        return _rec


class _ClockDT:
    """Fake ``datetime`` for the module: now(UTC) -> real aware now;
    now(None) -> a NAIVE reading 400 days AHEAD. now(UTC)->now(None) mutants
    (a dozen ``datetime.now(UTC)`` sites) then look up / key into the WRONG
    day, month and year."""

    @staticmethod
    def now(tz: Any = None) -> datetime:
        real = _REAL_DT.now(UTC)
        if tz is None:
            return real.replace(tzinfo=None) + timedelta(days=400)
        return real


class _Redis:
    """Records hset/expire/scan_iter/hgetall calls; scan_iter yields the
    stored keys VERBATIM (bytes or str polarity per test)."""

    def __init__(self, payloads: dict[Any, dict[Any, Any]]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def hset(self, *args: Any, **kwargs: Any) -> int:
        self.calls.append(("hset", args, kwargs))
        return 1

    async def expire(self, *args: Any, **kwargs: Any) -> bool:
        self.calls.append(("expire", args, kwargs))
        return True

    def scan_iter(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(("scan_iter", args, kwargs))
        keys = list(self.payloads)

        async def _gen() -> Any:
            for k in keys:
                yield k

        return _gen()

    async def hgetall(self, *args: Any, **kwargs: Any) -> dict[Any, Any]:
        self.calls.append(("hgetall", args, kwargs))
        k = args[0]
        alt = k.encode() if isinstance(k, str) else (k.decode() if isinstance(k, bytes) else k)
        return self.payloads.get(k) or self.payloads.get(alt) or {}


def _mk(**cfg: Any) -> tuple[CostTracker, _MetricsSpy]:
    """Fresh tracker with a metrics spy installed (the real
    get_metrics_service() is harmless at construction)."""
    svc = CostTracker(**cfg)
    spy = _MetricsSpy()
    svc._metrics = spy
    return svc, spy


def _rec(ts: datetime, **kw: Any) -> UsageRecord:
    return UsageRecord(timestamp=ts, model=kw.pop("model", "nemotron"), **kw)


def _other_month_same_year(d: date) -> date:
    """A date in the SAME year but a DIFFERENT month (Feb unless d is in
    Feb -> May), so the monthly ``or`` mutants see a same-year other-month
    row on EVERY day of the year."""
    return d.replace(month=5 if d.month == 2 else 2)


def _other_year_same_month(d: date) -> date:
    y = 2000 if (d.month, d.day) == (2, 29) else 2001
    return d.replace(year=y)


def _same_month_other_day(d: date) -> date:
    """A date in d's month with a DIFFERENT day (today is day 2 of Oct, so a
    fixed day=2 would collide with the real-today key)."""
    return d.replace(day=3 if d.day != 3 else 4)


def test_track_llm_usage_exact_shape_and_calls():
    svc, spy = _mk()
    cap = _LogCap()
    restores = [_swap("logger", cap)]
    try:
        tok = (1500 / 1000.0) * 0.003 + (500 / 1000.0) * 0.006
        exp = tok + 2.5 * 0.000139
        rec = svc.track_llm_usage(
            input_tokens=1500,
            output_tokens=500,
            model="nemotron",
            duration_seconds=2.5,
            camera_id="cam-1",
        )
        assert isinstance(rec, UsageRecord)
        assert rec.model == "nemotron"
        assert rec.input_tokens == 1500
        assert rec.output_tokens == 500
        assert rec.gpu_seconds == 2.5
        assert rec.images_processed == 0
        assert rec.operations == 0
        assert rec.camera_id == "cam-1"
        assert rec.estimated_cost_usd == exp
        # datetime.now(UTC) -> now(None) kills on tz-awareness alone
        assert rec.timestamp.tzinfo is not None
        assert rec.timestamp.utcoffset() == timedelta(0)
        assert spy.calls == [
            ("record_gpu_seconds", ("nemotron", 2.5), {}),
            ("record_estimated_cost", ("nemotron", exp), {}),
            ("record_event_analysis_cost", ("cam-1", exp), {}),
            ("set_daily_cost", (exp,), {}),
            ("set_monthly_cost", (exp,), {}),
        ]
        assert cap.names() == [
            (
                "debug",
                f"Tracked LLM usage: model=nemotron, input_tokens=1500, "
                f"output_tokens=500, duration=2.500s, cost=${exp:.6f}",
            )
        ]
    finally:
        for r in restores:
            r()


def test_track_llm_usage_no_camera_skips_event_cost():
    svc, spy = _mk()
    cap = _LogCap()
    restores = [_swap("logger", cap)]
    try:
        tok = (10 / 1000.0) * 0.003 + (20 / 1000.0) * 0.006
        exp = tok + 0.5 * 0.000139
        rec = svc.track_llm_usage(
            input_tokens=10, output_tokens=20, model="m", duration_seconds=0.5
        )
        assert rec.camera_id is None
        assert rec.estimated_cost_usd == exp
        assert spy.calls == [
            ("record_gpu_seconds", ("m", 0.5), {}),
            ("record_estimated_cost", ("m", exp), {}),
            ("set_daily_cost", (exp,), {}),
            ("set_monthly_cost", (exp,), {}),
        ]
        assert cap.names() == [
            (
                "debug",
                f"Tracked LLM usage: model=m, input_tokens=10, "
                f"output_tokens=20, duration=0.500s, cost=${exp:.6f}",
            )
        ]
    finally:
        for r in restores:
            r()


def test_track_detection_usage_exact_shape_and_calls():
    svc, spy = _mk()
    cap = _LogCap()
    restores = [_swap("logger", cap)]
    try:
        exp = 0.15 * 0.000139 + 3 * 0.00002
        rec = svc.track_detection_usage(model="yolo26", duration_seconds=0.15, images_processed=3)
        assert rec.model == "yolo26"
        assert rec.input_tokens == 0
        assert rec.output_tokens == 0
        assert rec.gpu_seconds == 0.15
        assert rec.images_processed == 3
        assert rec.operations == 0
        assert rec.camera_id is None
        assert rec.estimated_cost_usd == exp
        assert rec.timestamp.utcoffset() == timedelta(0)
        assert spy.calls == [
            ("record_gpu_seconds", ("yolo26", 0.15), {}),
            ("record_estimated_cost", ("yolo26", exp), {}),
            ("set_daily_cost", (exp,), {}),
            ("set_monthly_cost", (exp,), {}),
            ("set_cost_per_detection", (exp / 3,), {}),  # images 3 -> avg fires
        ]
        assert cap.names() == [
            (
                "debug",
                f"Tracked detection usage: model=yolo26, images=3, "
                f"duration=0.150s, cost=${exp:.6f}",
            )
        ]
    finally:
        for r in restores:
            r()


def test_track_enrichment_usage_exact_shape_and_calls():
    svc, spy = _mk()
    cap = _LogCap()
    restores = [_swap("logger", cap)]
    try:
        exp = 1.0 * 0.000139 + 4 * 0.00001
        rec = svc.track_enrichment_usage(model="clip", duration_seconds=1.0, operations=4)
        assert rec.model == "clip"
        assert rec.gpu_seconds == 1.0
        assert rec.images_processed == 0
        assert rec.operations == 4
        assert rec.estimated_cost_usd == exp
        assert rec.timestamp.utcoffset() == timedelta(0)
        assert spy.calls == [
            ("record_gpu_seconds", ("clip", 1.0), {}),
            ("record_estimated_cost", ("clip", exp), {}),
            ("set_daily_cost", (exp,), {}),
            ("set_monthly_cost", (exp,), {}),
        ]
        assert cap.names() == [
            (
                "debug",
                f"Tracked enrichment usage: model=clip, operations=4, "
                f"duration=1.000s, cost=${exp:.6f}",
            )
        ]
    finally:
        for r in restores:
            r()


def test_estimate_cost_all_axes_exact():
    svc, _ = _mk()
    exp = 0.0
    exp += (1000 / 1000.0) * 0.003
    exp += (2000 / 1000.0) * 0.006
    exp += 10.0 * 0.000139
    exp += 5 * 0.00002
    exp += 7 * 0.00001
    assert (
        svc.estimate_cost(
            input_tokens=1000, output_tokens=2000, gpu_seconds=10.0, images=5, operations=7
        )
        == exp
    )


def test_estimate_cost_zero_and_single_boundaries():
    svc, _ = _mk()
    assert svc.estimate_cost() == 0.0
    # "> 1" mutants skip value 1 / 0.5; ">=" int mutants cannot be observed
    assert svc.estimate_cost(input_tokens=1) == (1 / 1000.0) * 0.003
    assert svc.estimate_cost(output_tokens=1) == (1 / 1000.0) * 0.006
    assert svc.estimate_cost(gpu_seconds=0.5) == 0.5 * 0.000139
    assert svc.estimate_cost(images=1) == 1 * 0.00002
    assert svc.estimate_cost(operations=1) == 1 * 0.00001
    # m30: the -= mutant negates this axis
    assert svc.estimate_cost(operations=7) == 7 * 0.00001


def test_update_daily_usage_full_shape():
    svc, spy = _mk()
    d_now = date(2026, 6, 15)
    d_other_m = date(2026, 2, 15)  # same year, other month
    d_other_y = date(2020, 6, 15)  # same month, other year
    # event_count 1 on the decoy makes total_events 2 overall: the run-2 birth
    # m45 (set_cost_per_event(total_cost * total_events)) only diverges from
    # orig's / when events != 1 (10.0/2=5.0 vs 10.0*2=20.0).
    svc._daily_usage[d_other_m] = DailyUsage(
        date=d_other_m, total_estimated_cost_usd=1.0, event_count=1
    )
    svc._daily_usage[d_other_y] = DailyUsage(date=d_other_y, total_estimated_cost_usd=7.0)
    svc._daily_usage[d_now] = DailyUsage(date=d_now, event_count=1)
    rec = _rec(
        datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC),
        model="nemotron",
        input_tokens=100,
        output_tokens=40,
        gpu_seconds=2.0,
        images_processed=1,
        operations=3,
        estimated_cost_usd=2.0,
    )
    svc._update_daily_usage(rec)
    u = svc._daily_usage[d_now]
    assert u.total_input_tokens == 100
    assert u.total_output_tokens == 40
    assert u.total_gpu_seconds == 2.0
    assert u.total_images_processed == 1
    assert u.total_enrichment_operations == 3
    assert u.total_estimated_cost_usd == 2.0
    assert u.usage_by_model == {"nemotron": 2.0}
    assert u.event_count == 1
    # all-time 10.0 over detections 1 / events 2; monthly ONLY d_now
    assert spy.calls == [
        ("set_daily_cost", (2.0,), {}),
        ("set_monthly_cost", (2.0,), {}),
        ("set_cost_per_detection", (10.0 / 1,), {}),
        ("set_cost_per_event", (10.0 / 2,), {}),
    ]


def test_update_daily_usage_single_event_fires_cost_per_event():
    # EXACTLY one event overall: orig calls set_cost_per_event(cost/1); the
    # m43 (> 0 -> > 1) mutant SKIPS the call (spy length differs) - the
    # events=2 full-shape test cannot see m43 (both arms call, same value),
    # and m45 (* instead of /) coincides at events 1 - the two tests cover
    # each other's blind spot.
    svc, spy = _mk()
    d_now = date(2026, 6, 15)
    svc._daily_usage[d_now] = DailyUsage(date=d_now, event_count=1)
    rec = _rec(
        datetime(2026, 6, 15, 9, 0, 0, tzinfo=UTC),
        model="m",
        estimated_cost_usd=5.0,
    )
    svc._update_daily_usage(rec)
    assert spy.calls == [
        ("set_daily_cost", (5.0,), {}),
        ("set_monthly_cost", (5.0,), {}),
        ("set_cost_per_event", (5.0 / 1,), {}),
    ]


def test_update_daily_usage_accumulates_second_call():
    svc, spy = _mk()
    d_now = date(2026, 6, 15)
    ts = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
    svc._update_daily_usage(
        _rec(ts, model="a", input_tokens=1, operations=2, estimated_cost_usd=2.0)
    )
    svc._update_daily_usage(
        _rec(ts, model="a", input_tokens=2, operations=3, estimated_cost_usd=3.0)
    )
    u = svc._daily_usage[d_now]
    assert u.total_input_tokens == 3
    assert u.total_enrichment_operations == 5  # m14 =-mutant gives 3, m15 -= gives -1
    assert u.total_estimated_cost_usd == 5.0  # m16 (= instead of +=) gives 3.0
    assert u.usage_by_model == {"a": 5.0}  # m20 (=0.0->1.0) gives 6.0, m21 (=) gives 3.0
    assert spy.calls[-1][0] == "set_monthly_cost"


def test_update_daily_usage_two_models_two_detections():
    svc, spy = _mk()
    ts = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
    svc._update_daily_usage(_rec(ts, model="a", images_processed=2, estimated_cost_usd=4.0))
    assert spy.calls[-1] == ("set_cost_per_detection", (4.0 / 2,), {})  # m41 * gives 8.0


def test_update_daily_usage_monthly_budget_typeerror_polarity():
    # m45 passes None as monthly_cost -> None / budget TypeError
    svc, spy = _mk(monthly_budget_usd=5.0)
    ts = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
    svc._update_daily_usage(_rec(ts, estimated_cost_usd=1.0))
    assert ("set_budget_utilization", ("monthly", 0.2), {}) in spy.calls


def test_budget_thresholds_exact_exceeded_and_utilization():
    svc, spy = _mk(daily_budget_usd=2.0, monthly_budget_usd=4.0)
    cap = _LogCap()
    restores = [_swap("logger", cap)]
    try:
        # daily EXACTLY at budget -> exceeded arm; monthly below -> no monthly lines
        svc._check_budget_thresholds(daily_cost=2.0, monthly_cost=0.0)
        assert spy.calls == [
            ("set_budget_utilization", ("daily", 1.0), {}),
            ("record_budget_exceeded", ("daily",), {}),
            ("set_budget_utilization", ("monthly", 0.0), {}),
        ]
        assert cap.names() == [("warning", "Daily budget exceeded: $2.0000 / $2.00")]
    finally:
        for r in restores:
            r()


def test_budget_thresholds_monthly_exceeded_exact():
    svc, spy = _mk(daily_budget_usd=2.0, monthly_budget_usd=4.0)
    cap = _LogCap()
    restores = [_swap("logger", cap)]
    try:
        svc._check_budget_thresholds(daily_cost=0.0, monthly_cost=4.0)
        assert spy.calls == [
            ("set_budget_utilization", ("daily", 0.0), {}),
            ("set_budget_utilization", ("monthly", 1.0), {}),
            ("record_budget_exceeded", ("monthly",), {}),
        ]
        assert cap.names() == [("warning", "Monthly budget exceeded: $4.0000 / $4.00")]
    finally:
        for r in restores:
            r()


def test_budget_thresholds_warning_arm_exactly_at_threshold():
    svc, spy = _mk(daily_budget_usd=2.0, monthly_budget_usd=2.0, warning_threshold=0.8)
    cap = _LogCap()
    restores = [_swap("logger", cap)]
    try:
        # 1.6/2.0 == 0.8 EXACTLY: >= threshold fires; > mutants stay silent
        svc._check_budget_thresholds(daily_cost=1.6, monthly_cost=1.6)
        assert spy.calls == [
            ("set_budget_utilization", ("daily", 0.8), {}),
            ("set_budget_utilization", ("monthly", 0.8), {}),
        ]
        assert cap.names() == [
            ("warning", "Daily budget warning (80%): $1.6000 / $2.00"),
            ("warning", "Monthly budget warning (80%): $1.6000 / $2.00"),
        ]
    finally:
        for r in restores:
            r()


def test_budget_thresholds_monthly_zero_division_polarity():
    # m19: `if monthly_budget_usd > 1` skips a 0.5 budget entirely
    svc, spy = _mk(monthly_budget_usd=0.5)
    svc._check_budget_thresholds(daily_cost=0.0, monthly_cost=0.0)
    assert spy.calls == [("set_budget_utilization", ("monthly", 0.0), {})]
    # ratio via 0.4/0.5 == 0.8 EXACTLY (m21 * gives 0.2)
    svc2, spy2 = _mk(monthly_budget_usd=0.5, warning_threshold=0.8)
    cap = _LogCap()
    restores = [_swap("logger", cap)]
    try:
        svc2._check_budget_thresholds(daily_cost=0.0, monthly_cost=0.4)
        assert spy2.calls == [("set_budget_utilization", ("monthly", 0.8), {})]
        assert cap.names() == [("warning", "Monthly budget warning (80%): $0.4000 / $0.50")]
    finally:
        for r in restores:
            r()


def test_get_daily_usage_default_and_explicit_polarities():
    svc, _ = _mk()
    d_now = date(2026, 6, 15)
    d_far = date(2020, 1, 2)
    svc._daily_usage[d_now] = DailyUsage(date=d_now, total_estimated_cost_usd=1.0)
    svc._daily_usage[d_far] = DailyUsage(date=d_far)
    restores = [_swap("datetime", _ClockDT)]
    try:
        # default-arg path reads now(UTC).date(): with the fake clock the UTC
        # reading is real-today; the now(None) mutant lands 400 days ahead ->
        # get returns None (and the 2020 row stays invisible).
        got = svc.get_daily_usage()
        assert got is None or got.date == _REAL_DT.now(UTC).date()
        assert svc.get_daily_usage(target_date=d_far).total_estimated_cost_usd == 0.0
        # m3 polarity: NOW(UTC)-keyed row must be found via the DEFAULT path.
        d_utc = _REAL_DT.now(UTC).date()
        svc._daily_usage[d_utc] = DailyUsage(date=d_utc, total_estimated_cost_usd=9.0)
        assert svc.get_daily_usage().total_estimated_cost_usd == 9.0
    finally:
        for r in restores:
            r()


def test_get_monthly_usage_exact_membership():
    svc, _ = _mk()
    ref = _REAL_DT.now(UTC).date()
    d_same = ref.replace(day=9)
    d_other_m = _other_month_same_year(ref).replace(day=9)
    d_other_y = _other_year_same_month(ref)
    svc._daily_usage[d_same] = DailyUsage(date=d_same)
    svc._daily_usage[d_other_m] = DailyUsage(date=d_other_m)  # kills m8 or-mutant
    svc._daily_usage[d_other_y] = DailyUsage(date=d_other_y)  # kills m8 or-mutant
    out = svc.get_monthly_usage(year=ref.year, month=ref.month)
    assert [u.date for u in out] == [d_same]
    restores = [_swap("datetime", _ClockDT)]
    try:
        # default path: real now(UTC) -> the current-month row; now(None)
        # mutant (m2) queries a shifted year+month -> [].
        assert [u.date for u in svc.get_monthly_usage()] == [d_same]
    finally:
        for r in restores:
            r()


def test_get_monthly_usage_sorted_exact():
    svc, _ = _mk()
    y = 2020
    for day in (10, 1, 5):
        d = date(y, 3, day)
        svc._daily_usage[d] = DailyUsage(date=d)
    assert [u.date for u in svc.get_monthly_usage(year=y, month=3)] == [
        date(y, 3, 1),
        date(y, 3, 5),
        date(y, 3, 10),
    ]


def test_budget_status_full_shape_used_under_budget():
    svc, _ = _mk(daily_budget_usd=10.0, monthly_budget_usd=20.0, warning_threshold=0.8)
    d_now = _REAL_DT.now(UTC).date()
    d_prev_m = (d_now.replace(day=1) - timedelta(days=1)).replace(day=15)
    svc._daily_usage[d_now] = DailyUsage(date=d_now, total_estimated_cost_usd=6.0)
    svc._daily_usage[d_prev_m] = DailyUsage(date=d_prev_m, total_estimated_cost_usd=100.0)
    st = asyncio.run(svc.get_budget_status())
    assert st.daily_limit_usd == 10.0
    assert st.monthly_limit_usd == 20.0
    assert st.daily_used_usd == 6.0
    assert st.monthly_used_usd == 6.0  # m12/m13/m14 or-arms would add 100.0
    assert st.daily_remaining_usd == 4.0
    assert st.monthly_remaining_usd == 14.0
    assert st.daily_utilization_ratio == 0.6
    assert st.monthly_utilization_ratio == 0.3
    assert st.daily_exceeded is False
    assert st.monthly_exceeded is False
    assert st.warning_threshold_reached is False


def test_budget_status_used_over_budget_and_decoys():
    # BOTH budgets OVER: remaining clamps to EXACTLY 0.0 (m20/m27
    # max(1.0,..) -> 1.0, m22 None, m28 + -> sums). orig monthly sum =
    # CURRENT-month rows ONLY; the prev-month decoy is what the
    # or/d.year!=/d.month!= mutants would wrongly include.
    svc, _ = _mk(daily_budget_usd=2.0, monthly_budget_usd=50.0, warning_threshold=0.8)
    d_now = _REAL_DT.now(UTC).date()
    d_same_m = _same_month_other_day(d_now)
    d_prev_m = (d_now.replace(day=1) - timedelta(days=1)).replace(day=14)
    svc._daily_usage[d_now] = DailyUsage(date=d_now, total_estimated_cost_usd=3.0)
    svc._daily_usage[d_same_m] = DailyUsage(date=d_same_m, total_estimated_cost_usd=57.0)
    svc._daily_usage[d_prev_m] = DailyUsage(date=d_prev_m, total_estimated_cost_usd=46.0)
    st = asyncio.run(svc.get_budget_status())
    assert st.daily_used_usd == 3.0
    assert st.daily_remaining_usd == 0.0  # max(0.0, -1.0); m20 -> 1.0
    assert st.monthly_used_usd == 60.0  # m12 or -> 106.0, m13 != -> 0.0, m14 -> 46.0
    assert st.monthly_remaining_usd == 0.0  # m27 -> 1.0, m28 (+) -> 110.0, m22 None
    assert st.daily_utilization_ratio == 1.5
    assert st.monthly_utilization_ratio == 1.2  # m39 * -> 3000.0
    assert st.daily_exceeded is True  # m47 >=2 -> False
    assert st.monthly_exceeded is True  # m55 >=2 -> False
    assert st.warning_threshold_reached is True


def test_budget_status_exceeded_exactly_at_1():
    # used EXACTLY == budget: >= True, > mutants False; ratio EXACTLY 1.0
    svc, _ = _mk(daily_budget_usd=3.0, monthly_budget_usd=47.0, warning_threshold=0.8)
    d_now = _REAL_DT.now(UTC).date()
    d_prev_m = (d_now.replace(day=1) - timedelta(days=1)).replace(day=13)
    d_same_m = _same_month_other_day(d_now)  # second CURRENT-month row
    svc._daily_usage[d_now] = DailyUsage(date=d_now, total_estimated_cost_usd=3.0)
    svc._daily_usage[d_same_m] = DailyUsage(date=d_same_m, total_estimated_cost_usd=44.0)
    svc._daily_usage[d_prev_m] = DailyUsage(date=d_prev_m, total_estimated_cost_usd=100.0)
    st = asyncio.run(svc.get_budget_status())
    assert st.daily_remaining_usd == 0.0  # max(0.0, 0.0); m20 max(1.0,..) -> 1.0
    assert st.daily_utilization_ratio == 1.0
    assert st.daily_exceeded is True
    assert st.monthly_remaining_usd == 0.0  # max(0.0, 0.0); m27 -> 1.0
    # monthly = 3.0 + 44.0 = 47.0 EXACTLY (the 100.0 decoy is other-month)
    assert st.monthly_used_usd == 47.0
    assert st.monthly_utilization_ratio == 1.0
    assert st.monthly_exceeded is True
    assert st.warning_threshold_reached is True


def test_budget_status_no_budgets_zero_ratio_polarities():
    # budgets 0/0: ternary guards keep ratio 0.0, exceeded False (a
    # `(>0) or True` / `>= 0` mutant re-evaluates the ratio -> ZeroDivision).
    svc, _ = _mk(daily_budget_usd=0.0, monthly_budget_usd=0.0)
    d_now = _REAL_DT.now(UTC).date()
    svc._daily_usage[d_now] = DailyUsage(date=d_now, total_estimated_cost_usd=5.0)
    st = asyncio.run(svc.get_budget_status())
    assert st.daily_used_usd == 5.0
    assert st.monthly_used_usd == 5.0
    assert st.daily_remaining_usd == 0.0  # max(0.0, 0.0-5.0); m20 max(1.0,..) -> 1.0
    assert st.monthly_remaining_usd == 0.0  # m22 None -> AttributeError
    assert st.daily_utilization_ratio == 0.0  # m35/m42 -> 1.0, m31/m33/m37-40 raise
    assert st.monthly_utilization_ratio == 0.0
    assert st.daily_exceeded is False  # m50/m58 -> True
    assert st.monthly_exceeded is False  # m51 None -> assert fails
    assert st.warning_threshold_reached is False


def test_budget_status_negative_budgets_polarity():
    # budget -1: > 0 guards take else (ratio 0.0, False); >= 0 mutants too
    svc, _ = _mk(daily_budget_usd=-1.0, monthly_budget_usd=-1.0)
    st = asyncio.run(svc.get_budget_status())
    assert st.daily_utilization_ratio == 0.0
    assert st.daily_exceeded is False
    assert st.monthly_utilization_ratio == 0.0
    assert st.monthly_exceeded is False


def test_budget_status_used_no_row_and_threshold_or():
    # no row for today -> daily_used 0.0 (m9 else->1.0 would say 1.0);
    # daily EXACTLY at threshold, monthly 0 -> OR keeps True, and-mutant False.
    svc, _ = _mk(daily_budget_usd=5.0, monthly_budget_usd=10.0, warning_threshold=0.4)
    assert not svc._daily_usage
    st = asyncio.run(svc.get_budget_status())
    assert st.daily_used_usd == 0.0
    assert st.monthly_used_usd == 0.0
    assert st.daily_utilization_ratio == 0.0
    assert st.warning_threshold_reached is False
    d_now = _REAL_DT.now(UTC).date()
    svc._daily_usage[d_now] = DailyUsage(date=d_now, total_estimated_cost_usd=2.0)
    st2 = asyncio.run(svc.get_budget_status())
    assert st2.daily_utilization_ratio == 0.4  # EXACTLY threshold
    assert st2.warning_threshold_reached is True  # m60 and -> False; m61/m62 -> False
    # monthly-only EXACTLY at threshold (current-month row; an other-month
    # decoy is EXCLUDED by orig and only seen by the or/d.year!=/d.month!= arms)
    svc3, _ = _mk(daily_budget_usd=5.0, monthly_budget_usd=10.0, warning_threshold=0.4)
    svc3._daily_usage[d_now] = DailyUsage(date=d_now, total_estimated_cost_usd=0.0)
    d_same_m = _same_month_other_day(d_now)
    svc3._daily_usage[d_same_m] = DailyUsage(date=d_same_m, total_estimated_cost_usd=4.0)
    st3 = asyncio.run(svc3.get_budget_status())
    assert st3.daily_utilization_ratio == 0.0
    assert st3.monthly_used_usd == 4.0
    assert st3.monthly_utilization_ratio == 4.0 / 10.0  # EXACTLY 0.4
    assert st3.warning_threshold_reached is True
    # and the other-month decoy stays OUT of the orig sum:
    d_prev_m = (d_now.replace(day=1) - timedelta(days=1)).replace(day=12)
    svc3._daily_usage[d_prev_m] = DailyUsage(date=d_prev_m, total_estimated_cost_usd=99.0)
    st4 = asyncio.run(svc3.get_budget_status())
    assert st4.monthly_used_usd == 4.0  # m12 or -> 103.0; m13 != -> 0.0; m14 -> 99.0


def test_budget_status_budget_half_gt1_polarity():
    # budget 0.5: m41/m57 ("> 1") flip ratio/exceeded arms to defaults
    svc, _ = _mk(daily_budget_usd=0.5, monthly_budget_usd=0.5, warning_threshold=0.8)
    d_now = _REAL_DT.now(UTC).date()
    svc._daily_usage[d_now] = DailyUsage(date=d_now, total_estimated_cost_usd=0.5)
    st = asyncio.run(svc.get_budget_status())
    assert st.daily_remaining_usd == 0.0  # max(0.0, 0.0); m20 max(1.0,..) -> 1.0
    assert st.daily_utilization_ratio == 1.0
    assert st.daily_exceeded is True
    assert st.monthly_remaining_usd == 0.0  # max(0.0, 0.0); m27 -> 1.0
    assert st.monthly_utilization_ratio == 1.0
    assert st.monthly_exceeded is True


def test_budget_status_none_mutants_and_clock():
    svc, _ = _mk(daily_budget_usd=10.0, monthly_budget_usd=20.0, warning_threshold=0.8)
    d_now = _REAL_DT.now(UTC).date()
    svc._daily_usage[d_now] = DailyUsage(date=d_now, total_estimated_cost_usd=8.0)
    st = asyncio.run(svc.get_budget_status())
    assert st.daily_used_usd == 8.0
    # fake clock: now(UTC) still real -> lookups find today's row; the
    # now(None) mutant (m2) keys 400 days ahead -> all-default status.
    restores = [_swap("datetime", _ClockDT)]
    try:
        st2 = asyncio.run(svc.get_budget_status())
        assert st2.daily_used_usd == 8.0
        assert st2.monthly_used_usd == 8.0
    finally:
        for r in restores:
            r()


def test_persist_usage_none_redis_noop():
    svc, _ = _mk()  # redis_client default None
    assert asyncio.run(svc.persist_usage()) is None


def test_persist_usage_exact_wire_shape():
    svc, _ = _mk()
    cap = _LogCap()
    r = _Redis({})
    svc._redis = r
    d = date(2026, 6, 15)
    svc._daily_usage[d] = DailyUsage(
        date=d,
        total_input_tokens=11,
        total_output_tokens=22,
        total_gpu_seconds=3.5,
        total_images_processed=4,
        total_enrichment_operations=5,
        total_estimated_cost_usd=6.5,
        event_count=7,
    )
    restores = [_swap("logger", cap)]
    try:
        assert asyncio.run(svc.persist_usage()) is None
        key = "hsi:cost_tracking:daily:2026-06-15"
        assert r.calls == [
            (
                "hset",
                (key,),
                {
                    "mapping": {
                        "date": "2026-06-15",
                        "total_input_tokens": 11,
                        "total_output_tokens": 22,
                        "total_gpu_seconds": 3.5,
                        "total_images_processed": 4,
                        "total_enrichment_operations": 5,
                        "total_estimated_cost_usd": 6.5,
                        "event_count": 7,
                    }
                },
            ),
            ("expire", (key, 7776000), {}),  # 90*24*60*60; every m28-m34 twin differs
        ]
        assert cap.names() == [("debug", "Persisted usage data for 1 days")]
    finally:
        for rr in restores:
            rr()


def test_persist_usage_failure_logs_exact_error():
    svc, _ = _mk()
    cap = _LogCap()
    r = _Redis({})

    async def _boom(*args: Any, **kwargs: Any) -> None:
        msg = "kaboom"
        raise RuntimeError(msg)

    r.hset = _boom  # type: ignore[method-assign]
    svc._redis = r
    d = date(2026, 6, 15)
    svc._daily_usage[d] = DailyUsage(date=d)
    restores = [_swap("logger", cap)]
    try:
        assert asyncio.run(svc.persist_usage()) is None  # swallowed by except
        assert cap.names() == [("error", "Failed to persist usage data: kaboom")]
    finally:
        for rr in restores:
            rr()


def _full_payload(key: str) -> dict[str, Any]:
    return {
        "date": "2026-06-15",
        "total_input_tokens": b"11",
        "total_output_tokens": b"22",
        "total_gpu_seconds": b"3.5",
        "total_images_processed": b"4",
        "total_enrichment_operations": b"5",
        "total_estimated_cost_usd": b"6.5",
        "event_count": b"7",
    }


def test_load_usage_none_redis_noop():
    svc, _ = _mk()
    assert asyncio.run(svc.load_usage()) is None


def test_load_usage_full_bytes_payload():
    svc, _ = _mk()
    cap = _LogCap()
    key = b"hsi:cost_tracking:daily:2026-06-15"
    r = _Redis({key: _full_payload("k")})
    svc._redis = r
    restores = [_swap("logger", cap)]
    try:
        assert asyncio.run(svc.load_usage()) is None
        assert r.calls[0] == ("scan_iter", (), {"match": "hsi:cost_tracking:daily:*"})
        assert r.calls[1] == ("hgetall", ("hsi:cost_tracking:daily:2026-06-15",), {})
        u = svc._daily_usage[date(2026, 6, 15)]
        assert u.date == date(2026, 6, 15)  # m26 None -> wrong key + bad date
        assert u.total_input_tokens == 11
        assert u.total_output_tokens == 22
        assert u.total_gpu_seconds == 3.5
        assert u.total_images_processed == 4
        assert u.total_enrichment_operations == 5
        assert u.total_estimated_cost_usd == 6.5
        assert u.event_count == 7
        assert cap.names() == [("info", "Loaded usage data for 1 days from Redis")]
    finally:
        for rr in restores:
            rr()


def test_load_usage_full_str_payload():
    svc, _ = _mk()
    cap = _LogCap()
    key = "hsi:cost_tracking:daily:2026-06-15"
    payload = {
        k: (v.decode() if isinstance(v, bytes) else v) for k, v in _full_payload("k").items()
    }
    r = _Redis({key: payload})
    svc._redis = r
    restores = [_swap("logger", cap)]
    try:
        assert asyncio.run(svc.load_usage()) is None
        assert r.calls[1] == ("hgetall", ("hsi:cost_tracking:daily:2026-06-15",), {})
        u = svc._daily_usage[date(2026, 6, 15)]
        assert u.total_input_tokens == 11
        assert u.total_estimated_cost_usd == 6.5
        assert cap.names() == [("info", "Loaded usage data for 1 days from Redis")]
    finally:
        for rr in restores:
            rr()


def test_load_usage_missing_fields_default_to_zero():
    # ONLY date present: every default arm of the .get family fires. The
    # default-mutants die on the WRONG VALUE here (None -> TypeError inside
    # int()/float(), 1/1.0 -> nonzero where orig says 0); the default-DELETED
    # (trailing-comma) mutants die here too - 1-arg .get(missing) -> None ->
    # int(None) TypeError. The NAME mutants (None/XX/UPPER keys) read the
    # default 0 and are caught by the FULL-payload tests asserting 11/22/...
    svc, _ = _mk()
    key = "hsi:cost_tracking:daily:2026-06-15"
    r = _Redis({key: {"date": "2026-06-15"}})
    svc._redis = r
    cap = _LogCap()
    restores = [_swap("logger", cap)]
    try:
        assert asyncio.run(svc.load_usage()) is None
        u = svc._daily_usage[date(2026, 6, 15)]
        assert u.total_input_tokens == 0  # m44 None / m46 1-arg / m49 1 die here
        assert u.total_output_tokens == 0  # m52/m54/m57
        assert u.total_gpu_seconds == 0.0  # m60/m62/m65
        assert u.total_images_processed == 0  # m68/m70/m73
        assert u.total_enrichment_operations == 0  # m76/m78/m81
        assert u.total_estimated_cost_usd == 0.0  # m84/m86/m89
        assert u.event_count == 0  # m92/m94/m97
    finally:
        for rr in restores:
            rr()


def test_load_usage_empty_hgetall_skips_key():
    # EMPTY FIRST KEY, good key second: orig `continue` loads the good row
    # (1 day); the run-2 birth m13 `break` stops at the empty key (0 days).
    # A single-key empty case cannot distinguish break from continue.
    svc, _ = _mk()
    empty_key = "hsi:cost_tracking:daily:2026-01-01"
    good_key = "hsi:cost_tracking:daily:2026-06-15"
    r = _Redis({empty_key: {}, good_key: _full_payload("k")})
    svc._redis = r
    cap = _LogCap()
    restores = [_swap("logger", cap)]
    try:
        assert asyncio.run(svc.load_usage()) is None
        assert list(svc._daily_usage) == [date(2026, 6, 15)]
        assert svc._daily_usage[date(2026, 6, 15)].total_input_tokens == 11
        assert cap.names() == [("info", "Loaded usage data for 1 days from Redis")]
    finally:
        for rr in restores:
            rr()


def test_load_usage_bad_payload_logs_exact_error():
    svc, _ = _mk()
    key = "hsi:cost_tracking:daily:not-a-date"
    r = _Redis({key: {"date": "not-a-date"}})
    svc._redis = r
    cap = _LogCap()
    restores = [_swap("logger", cap)]
    try:
        assert asyncio.run(svc.load_usage()) is None
        assert cap.names() == [
            (
                "error",
                "Failed to load usage data: Invalid isoformat string: 'not-a-date'",
            )
        ]
    finally:
        for rr in restores:
            rr()


def test_usage_summary_full_dict_exact():
    svc, _ = _mk(daily_budget_usd=1.0, monthly_budget_usd=2.0, warning_threshold=0.7)
    d_now = _REAL_DT.now(UTC).date()
    d_other_m = _other_month_same_year(d_now)
    svc._daily_usage[d_now] = DailyUsage(
        date=d_now,
        total_input_tokens=100,
        total_output_tokens=50,
        total_gpu_seconds=9.0,
        total_estimated_cost_usd=4.0,
        event_count=1,
    )
    svc._daily_usage[d_other_m] = DailyUsage(date=d_other_m, total_estimated_cost_usd=8.0)
    got = svc.get_usage_summary()
    assert got == {
        "today": {
            "cost_usd": 4.0,
            "input_tokens": 100,
            "output_tokens": 50,
            "gpu_seconds": 9.0,
            "events": 1,
        },
        "this_month": {
            "cost_usd": 4.0,
            "total_tokens": 150,  # m11 - -> 50
            "gpu_seconds": 9.0,
            "days_tracked": 1,  # the other-month decoy EXCLUDED (m8-or -> 2)
        },
        "all_time": {
            "total_cost_usd": 12.0,
            "total_events": 1,
            "avg_cost_per_event_usd": 12.0,  # m23 (>1) -> 0.0; m18/m19 -> None/0.0
            "days_tracked": 2,
        },
        "budgets": {
            "daily_limit_usd": 1.0,
            "monthly_limit_usd": 2.0,
            "warning_threshold": 0.7,
        },
        "pricing": {
            "input_cost_per_1k_tokens": 0.003,
            "output_cost_per_1k_tokens": 0.006,
            "gpu_cost_per_second": 0.000139,
        },
    }


def test_usage_summary_empty_polarities():
    # no rows at all -> every today-else arm (m36/m41/m46/m51 -> 1/1/1.0/1)
    # and the events-else 0.0 arms (m19 and_false / m24 else 1.0).
    svc, _ = _mk()
    got = svc.get_usage_summary()
    assert got["today"] == {
        "cost_usd": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "gpu_seconds": 0.0,
        "events": 0,
    }
    assert got["this_month"] == {
        "cost_usd": 0.0,
        "total_tokens": 0,
        "gpu_seconds": 0.0,
        "days_tracked": 0,
    }
    assert got["all_time"]["avg_cost_per_event_usd"] == 0.0
    assert got["all_time"]["total_events"] == 0


def test_usage_summary_avg_diverges_from_multiply():
    # events 2 cost 4.0 -> avg 2.0; the m21 * mutant says 8.0 (with events 1
    # they coincide, which is why the full-dict test uses events EXACTLY 1
    # for the m23 (>1) polarity instead).
    svc, _ = _mk()
    d_now = _REAL_DT.now(UTC).date()
    svc._daily_usage[d_now] = DailyUsage(date=d_now, total_estimated_cost_usd=4.0, event_count=2)
    got = svc.get_usage_summary()
    assert got["all_time"]["avg_cost_per_event_usd"] == 2.0


def test_usage_summary_clock_polarity():
    # a row keyed at the REAL UTC today must be found as "today" under the
    # fake clock (now(None) mutant -> 400-days-ahead date -> today empty).
    svc, _ = _mk()
    d_utc = _REAL_DT.now(UTC).date()
    svc._daily_usage[d_utc] = DailyUsage(date=d_utc, total_estimated_cost_usd=5.0)
    restores = [_swap("datetime", _ClockDT)]
    try:
        got = svc.get_usage_summary()
        assert got["today"]["cost_usd"] == 5.0
    finally:
        for rr in restores:
            rr()


def test_increment_event_count_creates_row_and_metric():
    svc, spy = _mk()
    d_utc = _REAL_DT.now(UTC).date()
    svc._daily_usage[d_utc] = DailyUsage(date=d_utc, total_estimated_cost_usd=4.0)
    svc.increment_event_count()
    assert svc._daily_usage[d_utc].event_count == 1
    assert spy.calls == [("set_cost_per_event", (4.0 / 1,), {})]
    svc.increment_event_count(count=3)
    assert svc._daily_usage[d_utc].event_count == 4
    assert spy.calls[-1] == ("set_cost_per_event", (4.0 / 4,), {})


def test_increment_event_count_zero_skips_metric():
    # total_events stays 0 -> orig SKIPS the ratio call; m13 (>= 0) evaluates
    # total_cost / 0 -> ZeroDivisionError.
    svc, spy = _mk()
    svc.increment_event_count(count=0)
    assert spy.calls == []
    assert svc._daily_usage[_REAL_DT.now(UTC).date()].event_count == 0


def test_increment_event_count_creates_missing_row():
    svc, spy = _mk()
    restores = [_swap("datetime", _ClockDT)]
    try:
        svc.increment_event_count(count=2)
        d_utc = _REAL_DT.now(UTC).date()
        assert svc._daily_usage[d_utc].event_count == 2  # m3 mutant: 400d-off row
        assert svc._daily_usage[d_utc].date == d_utc  # m6 date=None -> bad key
        assert spy.calls[-1] == ("set_cost_per_event", (0.0 / 2,), {})
    finally:
        for rr in restores:
            rr()


def test_singleton_get_and_reset_identity():
    reset_cost_tracker()
    try:
        a = get_cost_tracker(daily_budget_usd=1.0)
        b = get_cost_tracker(daily_budget_usd=99.0)  # ignores params after first
        assert a is b
        assert a._daily_budget_usd == 1.0
        reset_cost_tracker()
        c = get_cost_tracker(monthly_budget_usd=5.0)
        assert c is not a
        assert c._monthly_budget_usd == 5.0
    finally:
        reset_cost_tracker()


def test_singleton_forwards_every_config_kwarg():
    reset_cost_tracker()
    try:
        pr = object()
        rd = object()
        t = get_cost_tracker(
            redis_client=rd,
            pricing=pr,  # type: ignore[arg-type]
            daily_budget_usd=1.5,
            monthly_budget_usd=2.5,
            warning_threshold=0.25,
        )
        assert t._redis is rd  # m3/m8 (=None/deleted) die
        assert t._pricing is pr  # m4 (=None) / m9 (deleted) fall to DEFAULT
        assert t._daily_budget_usd == 1.5  # m10
        assert t._monthly_budget_usd == 2.5  # m11
        assert t._warning_threshold == 0.25  # m7/m12
    finally:
        reset_cost_tracker()
