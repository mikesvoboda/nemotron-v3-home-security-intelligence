# TARGET-MODULE: backend.services.circuit_breaker
"""Battery AG - campaign #31 backend/services/circuit_breaker.py (224 survivors).

Kill surfaces (each proven by construction against the pristine module):
  * State/counter mutations are observed through get_status(),
    get_state_info() and get_metrics().to_dict() compared WHOLE against
    static literals; every value slot is pinned DISTINCT (failure/success/
    total/rejected counters differ) so slot renames (XXkeyXX / UPPER),
    swaps and cross-copies ride through as inequalities; the monotonic
    float slots (last_failure_time/opened_at) and the
    last_state_change datetime are STAMPed - name-censused and
    tz-asserted (dt.tzinfo is not None) - so the XX/case twin of a STAMP
    key fails the whole-dict equality and datetime.now(None) arms fail
    the tzinfo assert. (.astimezone() does NOT raise on naive - it
    assumes local time - so tzinfo/utcoffset must be asserted directly.)
  * Circuit state is pinned as a RAW OBJECT (is CircuitState.X, never the
    string alone) so a _state=None arm crashes the control, not the assert.
  * Prometheus children are censused two ways: (a) stub metric objects
    record every labels() kwargs and every inc()/set() call - a
    service=self._name -> None/XX swap, a result='failure' -> XX swap and
    a set(None) all change the recorded call; (b) one real-registry test
    reads the REAL children maps (_metrics) - labels(service=None) does
    NOT raise, it silently creates a ('None',...) child while the correct
    key stays absent, which only the real-child census can see.
  * Log records are censused BY NAME (record.service/from_state/to_state/
    failure_count) plus WHOLE-message equality and LEVEL; extra=None,
    dropped extra=, key renames and msg=None/XX/case flips all bite.
  * otel_record_success/failure/rejected/state_change and get_trace_context
    are swapped as cb MODULE GLOBALS (trampoline wrappers read the module
    __dict__) and recorded as whole (args, kwargs) tuples.
  * Time-dependent arms (_should_attempt_recovery >= vs >, get_metrics
    last_failure_dt arithmetic, protect's recovery_time_remaining,
    force_open's two monotonic reads) run on a scripted cb.time shim, so
    the exact arithmetic is checked with zero wall-clock dependence.
  * CircuitBreakerError/CircuitOpenError arguments are pinned by MESSAGE
    plus attributes. call() has two structurally identical raise sites -
    the OPEN-arm and the HALF_OPEN-arm - driven to DISTINCT messages here
    ("is open" vs "is half_open"), which separates the two mutant families
    (the OPEN-arm state argument is the CONSTANT "open"; the HALF-arm one
    is not). __aenter__'s reject is likewise driven from HALF_OPEN, so all
    four of its raise-arg mutants bite on the message.

Honesty ledger (registered EQUIVALENTS - value-identical by construction):
  call m10 / m12: the OPEN-branch `raise CircuitBreakerError(self._name,
    self._state.value)` -> state arg None / omitted. That branch only
    executes while state IS OPEN, so self._state.value == "open" is a
    constant there, and CircuitBreakerError maps None -> ("open",
    CircuitState.OPEN) and omission -> the same default; message, .state,
    .service_name and .args are identical on every reachable input.
    (The HALF_OPEN-arm twins m19-m22 are KILLABLE - they render "is
    open" where pristine renders "is half_open", or lose the name.)
  CircuitBreakerRegistry.__init__ m2: `self._lock = asyncio.Lock()` ->
    None. The registry exposes only synchronous methods; no code path
    ever awaits registry._lock - a dead store, unobservable.
  CircuitBreaker.record_success m14: sync `CLOSED and failure_count > 0`
    -> `>= 0`. The only input separating the comparisons is count == 0
    (both arms fire for count > 0), and the branch body there is the
    single statement `self._failure_count = 0` - a 0->0 no-op with no log
    and no metric - so no slot of any observation changes. (The ASYNC
    _record_success twin m15 is KILLABLE - its branch body has a DEBUG
    log the >=0 twin emits at count 0; see
    test_record_success_closed_zero_count_no_reset_log.)

Sweep adjudication: authoring sweep of all 224 survivor keys = 200R/24G;
20 of the 24 GREENs were stub-coverage gaps (service=None on
labels(service=..)/set() twins only bite through the REAL prometheus
children maps; result= label twins need a post-sync-inc last_labels pin;
_rejected_calls/_half_open_calls +=1 vs =1 twins need PRE-SEEDED
counters; datetime.now(None) needs a direct tzinfo assert) - all 20
re-swept RED with named attributing tests. Final sweep of the committed
bytes: 220 RED / 4 GREEN / 0 HANG with the GREEN set == this ledger.
"""

import asyncio
import contextlib
import logging
from datetime import datetime
from types import SimpleNamespace

import backend.services.circuit_breaker as cb
from backend.core.exceptions import CircuitBreakerOpenError as CoreCircuitBreakerOpenError
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitOpenError,
    CircuitState,
)

run = asyncio.run

# Static config every expectation is pinned against (never derived from the
# module source at runtime - under the trampoline tree that text also
# contains every mutant body).
_CFG = {
    "failure_threshold": 3,
    "recovery_timeout": 30.0,
    "half_open_max_calls": 2,
    "success_threshold": 2,
    "excluded_exceptions": (),
}
_CFG_S3 = {
    "failure_threshold": 3,
    "recovery_timeout": 30.0,
    "half_open_max_calls": 2,
    "success_threshold": 2,
}
_CFG_DEFAULT = {
    "failure_threshold": 5,
    "recovery_timeout": 30.0,
    "half_open_max_calls": 3,
    "success_threshold": 2,
}

_CENSUS = {"n": 0}  # unique prometheus names per test EXECUTION (sweep reruns)


def _mk(name="svc", **kw):
    config = kw.pop("config", None)
    if config is None:
        config = CircuitBreakerConfig(**kw) if kw else CircuitBreakerConfig(**_CFG)
    return CircuitBreaker(name=name, config=config)


def _stub_time(values):
    """cb.time shim: monotonic() pops scripted values, reusing the LAST."""
    box = {"i": 0}

    def monotonic():
        v = values[min(box["i"], len(values) - 1)]
        box["i"] += 1
        return v

    return SimpleNamespace(monotonic=monotonic, time=lambda: 1_000_000.0)


class _Metric:
    """Stub prometheus metric: labels() records the kwargs and hands back a
    child whose inc()/set() land on the PARENT's tallies."""

    def __init__(self):
        self.inc_total = 0
        self.last_labels = None
        self.set_calls = []

    def labels(self, *args, **kwargs):
        self.last_labels = (args, kwargs)
        parent = self

        class _Child:
            def inc(self, *a, **k):
                parent.inc_total += 1

            def set(self, *a, **k):
                parent.set_calls.append((a, k))

        return _Child()


def _metrics6():
    return (
        _Metric(),  # CIRCUIT_BREAKER_STATE
        _Metric(),  # CIRCUIT_BREAKER_FAILURES_TOTAL
        _Metric(),  # CIRCUIT_BREAKER_STATE_CHANGES_TOTAL
        _Metric(),  # CIRCUIT_BREAKER_CALLS_TOTAL
        _Metric(),  # HSI_CIRCUIT_BREAKER_STATE
        _Metric(),  # HSI_CIRCUIT_BREAKER_TRIPS_TOTAL
    )


class _OtelRec(list):
    def __call__(self, *args, **kwargs):
        self.append((args, kwargs))


class _CtxRec:
    """get_trace_context replacement: fresh dict per call (the extra= merge
    stays live), call-counted."""

    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return {"trace_id": f"T{self.n}", "span_id": f"S{self.n}"}


class _RecHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def caplogs(fn):
    def wrapper():
        handler = _RecHandler()
        lg = cb.logger
        prev_propagate, prev_level = lg.propagate, lg.level
        lg.addHandler(handler)
        lg.propagate = False
        lg.setLevel(logging.DEBUG)
        try:
            return fn(handler.records)
        finally:
            lg.removeHandler(handler)
            lg.propagate = prev_propagate
            lg.setLevel(prev_level)

    wrapper.__name__ = fn.__name__
    wrapper.__qualname__ = fn.__qualname__
    wrapper.__doc__ = fn.__doc__
    return wrapper


_PATCH_NAMES = (
    "otel_record_success",
    "otel_record_failure",
    "otel_record_rejected",
    "otel_record_state_change",
    "get_trace_context",
    "time",
    "CIRCUIT_BREAKER_STATE",
    "CIRCUIT_BREAKER_FAILURES_TOTAL",
    "CIRCUIT_BREAKER_STATE_CHANGES_TOTAL",
    "CIRCUIT_BREAKER_CALLS_TOTAL",
    "CIRCUIT_BREAKER_REJECTED_TOTAL",
    "HSI_CIRCUIT_BREAKER_STATE",
    "HSI_CIRCUIT_BREAKER_TRIPS_TOTAL",
)
_MISSING = object()


def patched(fn):
    def wrapper():
        saved = {n: getattr(cb, n, _MISSING) for n in _PATCH_NAMES}
        try:
            return fn()
        finally:
            for n, v in saved.items():
                if v is _MISSING:
                    with contextlib.suppress(AttributeError):
                        delattr(cb, n)
                else:
                    setattr(cb, n, v)

    wrapper.__name__ = fn.__name__
    wrapper.__qualname__ = fn.__qualname__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def _install(stubs):
    for name, obj in stubs:
        setattr(cb, name, obj)


def _stub_env(trip_reads=None, **extra_stubs):
    """Install the 7 metric stubs + otel recorders + ctx + time shim.

    Returns (g_state, g_fail, g_chg, g_calls, h_state, h_trips, otel_ok,
    otel_fail, otel_rej, otel_chg, ctx)."""
    g_state, g_fail, g_chg, g_calls, h_state, h_trips = _metrics6()
    otel_ok, otel_fail, otel_rej, otel_chg = _OtelRec(), _OtelRec(), _OtelRec(), _OtelRec()
    ctx = _CtxRec()
    stubs = [
        ("otel_record_success", otel_ok),
        ("otel_record_failure", otel_fail),
        ("otel_record_rejected", otel_rej),
        ("otel_record_state_change", otel_chg),
        ("get_trace_context", ctx),
        ("CIRCUIT_BREAKER_STATE", g_state),
        ("CIRCUIT_BREAKER_FAILURES_TOTAL", g_fail),
        ("CIRCUIT_BREAKER_STATE_CHANGES_TOTAL", g_chg),
        ("CIRCUIT_BREAKER_CALLS_TOTAL", g_calls),
        ("HSI_CIRCUIT_BREAKER_STATE", h_state),
        ("HSI_CIRCUIT_BREAKER_TRIPS_TOTAL", h_trips),
    ]
    for key, obj in extra_stubs.items():
        stubs.append((key, obj))
    _install(stubs)
    if trip_reads is not None:
        cb.time = _stub_time(trip_reads)
    return (
        g_state,
        g_fail,
        g_chg,
        g_calls,
        h_state,
        h_trips,
        otel_ok,
        otel_fail,
        otel_rej,
        otel_chg,
        ctx,
    )


def _attrs(rec, names):
    return tuple(getattr(rec, n, "MISSING") for n in names)


def _msgs(records, level):
    return [r.getMessage() for r in records if r.levelno == level]


def _iso_stamp(dt):
    """STAMP polarity for a datetime.now(UTC) slot.

    .astimezone() does NOT raise on a naive datetime (it assumes local
    time), so the tz-awareness must be asserted directly - datetime.now(None)
    produces tzinfo None and fails here.
    """
    assert dt.tzinfo is not None, "stamp is naive: datetime.now(None) arm"
    assert dt.utcoffset() is not None, "stamp has no offset: datetime.now(None) arm"
    return dt.isoformat()


def _status(name, state, failure, success, total, rejected, *, lf, opened_at, cfg=_CFG_S3):
    return {
        "name": name,
        "state": state,
        "failure_count": failure,
        "success_count": success,
        "total_calls": total,
        "rejected_calls": rejected,
        "last_failure_time": lf,
        "opened_at": opened_at,
        "config": cfg,
    }


# =============================================================================
# CircuitState / error constructors / Metrics.to_dict
# =============================================================================


def test_state_enum_values():
    assert CircuitState.CLOSED == "closed"
    assert CircuitState.OPEN == "open"
    assert CircuitState.HALF_OPEN == "half_open"
    assert [s.value for s in CircuitState] == ["closed", "open", "half_open"]


def test_error_ctor_polarities():
    e = CircuitBreakerError("svc")
    assert str(e) == "Circuit breaker for 'svc' is open. Service is temporarily unavailable."
    assert e.service_name == "svc" and e.name == "svc" and e.recovery_timeout is None
    assert e.state is CircuitState.OPEN

    e2 = CircuitBreakerError("svc", CircuitState.HALF_OPEN, recovery_timeout=9.5)
    assert str(e2) == "Circuit breaker for 'svc' is half_open. Service is temporarily unavailable."
    assert e2.state is CircuitState.HALF_OPEN and e2.recovery_timeout == 9.5

    e3 = CircuitBreakerError("svc", "half_open")
    assert e3.state is CircuitState.HALF_OPEN
    assert str(e3) == "Circuit breaker for 'svc' is half_open. Service is temporarily unavailable."

    e4 = CircuitBreakerError("svc", "bogus")
    # the raw string rides into the MESSAGE unchanged; only .state defaults
    assert str(e4) == "Circuit breaker for 'svc' is bogus. Service is temporarily unavailable."
    assert e4.state is CircuitState.OPEN


def test_circuit_open_error():
    e = CircuitOpenError("svc", 42.5)
    assert str(e) == "Circuit open for svc"
    assert e.service_name == "svc" and e.recovery_time_remaining == 42.5


def test_metrics_to_dict_whole():
    base = datetime.fromisoformat("2026-10-03T09:00:00+00:00")
    m = cb.CircuitBreakerMetrics(
        name="svc",
        state=CircuitState.HALF_OPEN,
        failure_count=11,
        success_count=22,
        total_calls=33,
        rejected_calls=44,
        last_failure_time=base,
        last_state_change=base,
    )
    assert m.to_dict() == {
        "name": "svc",
        "state": "half_open",
        "failure_count": 11,
        "success_count": 22,
        "total_calls": 33,
        "rejected_calls": 44,
        "last_failure_time": "2026-10-03T09:00:00+00:00",
        "last_state_change": "2026-10-03T09:00:00+00:00",
    }
    m2 = cb.CircuitBreakerMetrics(name="svc", state=CircuitState.CLOSED)
    assert m2.to_dict() == {
        "name": "svc",
        "state": "closed",
        "failure_count": 0,
        "success_count": 0,
        "total_calls": 0,
        "rejected_calls": 0,
        "last_failure_time": None,
        "last_state_change": None,
    }


# =============================================================================
# __init__ / properties
# =============================================================================


@caplogs
def test_init_defaults_and_config_override(logs):
    d = CircuitBreaker(name="dsvc")
    assert d.state is CircuitState.CLOSED
    assert d.name == "dsvc"
    assert d.config.failure_threshold == 5
    assert d.config.recovery_timeout == 30.0
    assert d.config.half_open_max_calls == 3
    assert d.config.success_threshold == 2
    assert d.config.excluded_exceptions == ()
    assert d._failure_count == 0 and d._success_count == 0 and d._total_calls == 0
    assert d._rejected_calls == 0 and d._half_open_calls == 0
    assert d._last_failure_time is None and d._opened_at is None
    assert d._last_state_change is None
    assert isinstance(d._lock, asyncio.Lock)
    assert d.get_status() == _status(
        "dsvc", "closed", 0, 0, 0, 0, lf=None, opened_at=None, cfg=_CFG_DEFAULT
    )

    o = CircuitBreaker(
        name="osvc", failure_threshold=7, recovery_timeout=4.0, half_open_max_calls=1
    )
    assert o.config.failure_threshold == 7
    assert o.config.recovery_timeout == 4.0
    assert o.config.half_open_max_calls == 1
    assert o.config.success_threshold == 2

    provided = CircuitBreakerConfig(failure_threshold=9)
    p = CircuitBreaker(name="psvc", config=provided, failure_threshold=1, recovery_timeout=2.0)
    assert p._config is provided
    assert p.config.failure_threshold == 9

    assert _msgs(logs, logging.INFO) == [
        "CircuitBreaker 'dsvc' initialized: failure_threshold=5, "
        "recovery_timeout=30.0s, half_open_max_calls=3",
        "CircuitBreaker 'osvc' initialized: failure_threshold=7, "
        "recovery_timeout=4.0s, half_open_max_calls=1",
        "CircuitBreaker 'psvc' initialized: failure_threshold=9, "
        "recovery_timeout=30.0s, half_open_max_calls=3",
    ]


def test_properties_and_compat_aliases():
    b = _mk()
    assert b.name == "svc"
    assert b.config.failure_threshold == 3
    assert b.state is CircuitState.CLOSED
    assert b.get_state() is CircuitState.CLOSED
    assert b.is_closed is True
    assert b.is_open is False
    assert b.failure_count == 0
    assert b.success_count == 0
    assert b._failure_threshold == 3
    assert b._recovery_timeout == 30.0
    assert b._half_open_max_calls == 2
    assert str(b) == "CircuitBreaker(svc, state=CLOSED)"
    assert repr(b) == "CircuitBreaker(name='svc', state=closed, failures=0)"
    b._failure_count = 2
    b._success_count = 1
    assert b.failure_count == 2 and b.success_count == 1
    assert repr(b) == "CircuitBreaker(name='svc', state=closed, failures=2)"


# =============================================================================
# _record_failure
# =============================================================================


@patched
@caplogs
def test_record_failure_closed_below_threshold(logs):
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, _, _, otel_chg, ctx = _stub_env(
        trip_reads=[500.0]
    )
    b = _mk()
    run(b._record_failure())
    st = b.get_status()
    assert st["failure_count"] == 1
    assert st["last_failure_time"] == 500.0
    assert st["state"] == "closed"
    assert b.state is CircuitState.CLOSED
    assert g_fail.inc_total == 1 and g_fail.last_labels == ((), {"service": "svc"})
    assert g_calls.inc_total == 1
    assert g_calls.last_labels == ((), {"service": "svc", "result": "failure"})
    assert g_chg.inc_total == 0 and h_trips.inc_total == 0
    assert otel_chg == []
    # only __init__ set(0) so far - no transition
    assert g_state.set_calls == [((0,), {})]
    assert h_state.set_calls == [((0,), {})]
    assert ctx.n == 1
    assert _msgs(logs, logging.WARNING) == ["CircuitBreaker 'svc' failure recorded: 1/3"]
    rec = logs[-1]
    assert (rec.levelno, rec.getMessage()) == (
        logging.WARNING,
        "CircuitBreaker 'svc' failure recorded: 1/3",
    )
    assert _attrs(rec, ("service", "trace_id", "span_id")) == ("svc", "T1", "S1")


@patched
@caplogs
def test_record_failure_closed_trips_to_open(logs):
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, otel_fail, _, otel_chg, ctx = _stub_env(
        trip_reads=[10.0, 11.0, 12.0, 13.0]
    )
    b = _mk()
    run(b._record_failure())
    assert b.state is CircuitState.CLOSED
    assert b._last_failure_time == 10.0
    run(b._record_failure())
    assert b.state is CircuitState.CLOSED  # 2 < threshold 3
    assert b._last_failure_time == 11.0
    run(b._record_failure())  # 3rd trips
    assert b.state is CircuitState.OPEN
    st = b.get_status()
    assert st == _status("svc", "open", 3, 0, 0, 0, lf=12.0, opened_at=13.0)
    _iso_stamp(b._last_state_change)
    assert g_state.set_calls == [((0,), {}), ((1,), {})]
    assert h_state.set_calls == [((0,), {}), ((1,), {})]
    assert g_fail.inc_total == 3
    assert g_calls.inc_total == 3
    assert g_chg.inc_total == 1
    assert g_chg.last_labels == (
        (),
        {"service": "svc", "from_state": "closed", "to_state": "open"},
    )
    assert h_trips.inc_total == 1 and h_trips.last_labels == ((), {"service": "svc"})
    assert otel_fail == [(("svc",), {})] * 3
    assert otel_chg == [(("svc", "closed", "open"), {})]
    assert ctx.n == 4  # three failure logs + one transition log
    assert _msgs(logs, logging.WARNING) == [
        "CircuitBreaker 'svc' failure recorded: 1/3",
        "CircuitBreaker 'svc' failure recorded: 2/3",
        "CircuitBreaker 'svc' failure recorded: 3/3",
        "CircuitBreaker 'svc' transitioned closed -> OPEN (failures=3, threshold=3)",
    ]
    tr = logs[-1]
    assert _attrs(tr, ("service", "from_state", "to_state", "failure_count")) == (
        "svc",
        "closed",
        "open",
        3,
    )


@patched
@caplogs
def test_record_failure_half_open_reopens(logs):
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, _, _, otel_chg, ctx = _stub_env(
        trip_reads=[777.0, 778.0]
    )
    del g_calls
    b = _mk()
    b._state = CircuitState.HALF_OPEN
    b._success_count = 1
    run(b._record_failure())
    assert b.state is CircuitState.OPEN
    assert b._failure_count == 1
    assert b._last_failure_time == 777.0
    assert b._success_count == 0  # reset by transition_to_open
    assert b._half_open_calls == 0
    assert b._opened_at == 778.0
    assert b.get_status()["state"] == "open"
    assert g_chg.last_labels == (
        (),
        {"service": "svc", "from_state": "half_open", "to_state": "open"},
    )
    assert g_state.set_calls == [((0,), {}), ((1,), {})]
    assert h_state.set_calls == [((0,), {}), ((1,), {})]
    assert otel_chg == [(("svc", "half_open", "open"), {})]
    assert ctx.n == 2
    tr = next(r for r in logs if "transitioned half_open" in r.getMessage())
    assert _attrs(tr, ("service", "from_state", "to_state", "failure_count")) == (
        "svc",
        "half_open",
        "open",
        1,
    )
    assert tr.getMessage() == (
        "CircuitBreaker 'svc' transitioned half_open -> OPEN (failures=1, threshold=3)"
    )


# =============================================================================
# _record_success
# =============================================================================


@patched
@caplogs
def test_record_success_closed_reset_and_half_open_flow(logs):
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, otel_ok, _, _, otel_chg, ctx = _stub_env()
    del g_fail, h_trips
    b1 = _mk(name="rs1")
    b1._failure_count = 1
    run(b1._record_success())
    assert b1._failure_count == 0
    assert b1.state is CircuitState.CLOSED
    reset = next(r for r in logs if r.getMessage().endswith("resetting failure count on success"))
    assert reset.levelno == logging.DEBUG
    assert reset.getMessage() == "CircuitBreaker 'rs1' resetting failure count on success"

    b2 = _mk(name="rs2")
    b2._state = CircuitState.HALF_OPEN
    b2._success_count = 1  # one short of threshold 2
    run(b2._record_success())
    assert b2.state is CircuitState.CLOSED
    assert b2._failure_count == 0
    assert b2._success_count == 0  # reset by transition_to_closed
    assert b2._opened_at is None
    assert b2._half_open_calls == 0
    _iso_stamp(b2._last_state_change)
    assert g_calls.inc_total == 2
    assert g_calls.last_labels == ((), {"service": "rs2", "result": "success"})
    assert otel_ok == [(("rs1",), {}), (("rs2",), {})]
    assert g_chg.inc_total == 1
    assert g_chg.last_labels == (
        (),
        {"service": "rs2", "from_state": "half_open", "to_state": "closed"},
    )
    # gauges: init x2 + close-transition
    assert g_state.set_calls == [((0,), {}), ((0,), {}), ((0,), {})]
    assert h_state.set_calls == [((0,), {}), ((0,), {}), ((0,), {})]
    assert otel_chg == [(("rs2", "half_open", "closed"), {})]
    assert ctx.n == 1  # only the CLOSED-transition log uses trace ctx
    assert _msgs(logs, logging.DEBUG) == [
        "CircuitBreaker 'rs1' resetting failure count on success",
        "CircuitBreaker 'rs2' half-open success: 2/2",
    ]
    closed = logs[-1]
    assert (closed.levelno, closed.getMessage()) == (
        logging.INFO,
        "CircuitBreaker 'rs2' transitioned HALF_OPEN -> CLOSED (service recovered)",
    )
    assert _attrs(closed, ("service", "from_state", "to_state")) == (
        "rs2",
        "half_open",
        "closed",
    )


@patched
@caplogs
def test_record_success_half_open_below_threshold_stays(logs):
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, otel_ok, _, _, otel_chg, _ = _stub_env()
    del g_fail, h_trips
    b = _mk()
    b._state = CircuitState.HALF_OPEN
    run(b._record_success())
    assert b.state is CircuitState.HALF_OPEN
    assert b._success_count == 1  # +1, not +2 (m10 twin would hit threshold)
    assert g_chg.inc_total == 0
    assert otel_chg == []
    assert g_state.set_calls == [((0,), {})]  # init only
    assert h_state.set_calls == [((0,), {})]
    assert otel_ok == [(("svc",), {})]
    assert g_calls.last_labels == ((), {"service": "svc", "result": "success"})
    assert _msgs(logs, logging.DEBUG) == ["CircuitBreaker 'svc' half-open success: 1/2"]


@patched
@caplogs
def test_record_success_closed_zero_count_no_reset_log(logs):
    # CLOSED with failure_count == 0: pristine skips the reset branch
    # (`> 0` is False); the >=0 twin (_record_success m15) ENTERS it and
    # emits the "resetting failure count" debug line. Assert ABSENCE.
    _stub_env()
    b = _mk()
    assert b._failure_count == 0
    run(b._record_success())
    assert b._failure_count == 0
    assert _msgs(logs, logging.DEBUG) == []


# =============================================================================
# allow_call family
# =============================================================================


@patched
@caplogs
def test_allow_call_and_transitions(logs):
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, _, _, otel_chg, _ = _stub_env(
        trip_reads=[500.0, 531.0]
    )
    del g_fail, g_calls
    b = _mk()
    assert run(b.allow_call()) is True
    assert b.allow_request() is True
    assert run(b.allow_request_async()) is True

    b._state = CircuitState.OPEN
    b._opened_at = 500.0
    assert run(b.allow_call()) is False  # 500-500=0 < 30
    assert b.state is CircuitState.OPEN
    assert run(b.allow_call()) is True  # 531-500=31 >= 30 -> HALF_OPEN
    assert b.state is CircuitState.HALF_OPEN
    assert b._half_open_calls == 0  # _allow_call_unlocked never increments
    assert b._success_count == 0
    _iso_stamp(b._last_state_change)
    assert g_chg.inc_total == 1
    assert g_chg.last_labels == (
        (),
        {"service": "svc", "from_state": "open", "to_state": "half_open"},
    )
    assert g_state.set_calls == [((0,), {}), ((2,), {})]
    assert h_state.set_calls == [((0,), {}), ((2,), {})]
    assert otel_chg == [(("svc", "open", "half_open"), {})]
    ho = logs[-1]
    assert (ho.levelno, ho.getMessage()) == (
        logging.INFO,
        "CircuitBreaker 'svc' transitioned OPEN -> HALF_OPEN (testing recovery after 30.0s)",
    )
    assert _attrs(ho, ("service", "from_state", "to_state", "recovery_timeout")) == (
        "svc",
        "open",
        "half_open",
        30.0,
    )

    # HALF_OPEN capacity window through allow_call (no increments here)
    b._half_open_calls = 1
    assert run(b.allow_call()) is True
    b._half_open_calls = 2
    assert run(b.allow_call()) is False


@patched
def test_allow_request_sync_increments_half_open():
    b = _mk()
    b._state = CircuitState.HALF_OPEN
    b._half_open_calls = 0
    assert b.allow_request() is True
    assert b._half_open_calls == 1
    b._half_open_calls = 2
    assert b.allow_request() is False  # capacity exhausted
    assert b._half_open_calls == 2  # unchanged on rejection


# =============================================================================
# _should_attempt_recovery (>= vs > at the exact boundary)
# =============================================================================


@patched
def test_should_attempt_recovery_boundary():
    b = _mk()
    assert b._should_attempt_recovery() is False  # _opened_at None
    b._state = CircuitState.OPEN
    b._opened_at = 100.0
    cb.time = _stub_time([130.0])  # elapsed EXACTLY recovery_timeout
    assert b._should_attempt_recovery() is True  # kills the > twin
    cb.time = _stub_time([129.9])
    assert b._should_attempt_recovery() is False
    cb.time = _stub_time([140.0])
    assert b._should_attempt_recovery() is True


# =============================================================================
# call()
# =============================================================================


@patched
def test_call_success_records_and_returns():
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, otel_ok, _, _, _, _ = _stub_env()
    del g_state, g_fail, g_chg, h_state, h_trips

    async def op(a, *, k):
        return (a, k)

    b = _mk()
    assert run(b.call(op, 7, k=8)) == (7, 8)
    st = b.get_status()
    assert st["total_calls"] == 1
    assert st["failure_count"] == 0
    assert st["state"] == "closed"
    assert g_calls.inc_total == 1
    assert g_calls.last_labels == ((), {"service": "svc", "result": "success"})
    assert otel_ok == [(("svc",), {})]


@patched
def test_call_failure_reraises_and_trips():
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, otel_fail, _, otel_chg, _ = _stub_env(
        trip_reads=[600.0]
    )
    del g_state, h_state

    async def boom():
        raise ValueError("venom")

    b = _mk()
    for _ in range(2):
        with contextlib.suppress(ValueError):
            run(b.call(boom))
        assert b.state is CircuitState.CLOSED
    with contextlib.suppress(ValueError):
        run(b.call(boom))
    assert b.state is CircuitState.OPEN
    assert b._failure_count == 3
    assert b._last_failure_time == 600.0
    assert g_fail.inc_total == 3
    assert otel_fail == [(("svc",), {})] * 3
    assert otel_chg == [(("svc", "closed", "open"), {})]


@patched
def test_call_excluded_exception_reraises_without_record():
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, otel_fail, _, _, _ = _stub_env()
    del g_state, g_chg, h_state, h_trips

    async def boom():
        raise KeyError("skip")

    b = _mk(config=CircuitBreakerConfig(**{**_CFG, "excluded_exceptions": (KeyError,)}))
    with contextlib.suppress(KeyError):
        run(b.call(boom))
    assert b._failure_count == 0
    assert b.state is CircuitState.CLOSED
    assert otel_fail == []
    assert g_fail.inc_total == 0
    assert g_calls.inc_total == 0  # neither success nor failure recorded


@patched
def test_call_open_reject_and_half_open_reject_are_distinct():
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, _, otel_rej, _, _ = _stub_env(
        trip_reads=[100.0]
    )
    del g_state, g_fail, g_chg, g_calls, h_state, h_trips

    async def op():
        return "ok"

    b = _mk()
    b._state = CircuitState.OPEN
    b._opened_at = 100.0  # 100-100=0 < 30 -> reject
    try:
        run(b.call(op))
        raise AssertionError("should have raised")
    except CircuitBreakerError as e:
        assert str(e) == "Circuit breaker for 'svc' is open. Service is temporarily unavailable."
        assert e.service_name == "svc" and e.state is CircuitState.OPEN
    assert b._rejected_calls == 1
    assert b.get_status()["total_calls"] == 1

    # HALF_OPEN capacity reject renders "is half_open" - kills every
    # HALF-arm raise mutant that loses or Nones the state argument.
    # rejected_calls PRE-SEEDED to 1 so the HALF-arm `_rejected_calls = 1`
    # twin (vs pristine += 1) is observable (call m15).
    b2 = _mk()
    b2._state = CircuitState.HALF_OPEN
    b2._half_open_calls = 2  # >= max_calls 2
    b2._rejected_calls = 1
    try:
        run(b2.call(op))
        raise AssertionError("should have raised")
    except CircuitBreakerError as e:
        assert (
            str(e) == "Circuit breaker for 'svc' is half_open. Service is temporarily unavailable."
        )
        assert e.service_name == "svc" and e.state is CircuitState.HALF_OPEN
    assert b2._rejected_calls == 2
    assert otel_rej == [(("svc",), {}), (("svc",), {})]


@patched
def test_call_half_open_capacity_boundary():
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, otel_ok, _, otel_rej, _, _ = _stub_env()
    del g_state, g_fail, g_chg, h_state, h_trips

    async def op():
        return 1

    b = _mk()
    b._state = CircuitState.HALF_OPEN
    b._half_open_calls = 1
    assert run(b.call(op)) == 1
    assert b._half_open_calls == 2  # +1 (m23 =1 / m24 -=1 change this)
    assert b._success_count == 1  # still HALF_OPEN (threshold 2)
    assert b.state is CircuitState.HALF_OPEN
    try:
        run(b.call(op))
        raise AssertionError("should have raised")
    except CircuitBreakerError as e:
        assert "is half_open" in str(e)
    assert otel_rej == [(("svc",), {})]
    assert otel_ok == [(("svc",), {})]


# =============================================================================
# sync record_failure / record_success
# =============================================================================


@patched
@caplogs
def test_sync_record_failure_and_success(logs):
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, otel_fail, _, otel_chg, ctx = _stub_env(
        trip_reads=[400.0]
    )
    del g_state, h_state, otel_chg, ctx
    b = _mk()
    b.record_failure()
    assert b._failure_count == 1
    assert b._last_failure_time == 400.0
    assert b.state is CircuitState.CLOSED
    assert g_fail.inc_total == 1 and g_fail.last_labels == ((), {"service": "svc"})
    assert g_calls.inc_total == 1
    assert g_calls.last_labels == ((), {"service": "svc", "result": "failure"})
    assert otel_fail == []  # the SYNC path does not emit otel
    assert len(logs) == 1  # sync failure path logs nothing

    b.record_success()  # CLOSED with count 1 -> reset
    assert b._failure_count == 0
    assert len(logs) == 1  # sync success path logs nothing either
    # the sync record_success inc MUST carry service=name, result="success"
    # (kills the service=None / result=None / 'XXsuccessXX' / 'SUCCESS' label
    # twins that the stub's last_labels pin makes decisive)
    assert g_calls.inc_total == 2
    assert g_calls.last_labels == ((), {"service": "svc", "result": "success"})

    b2 = _mk(name="s2")
    b2._state = CircuitState.HALF_OPEN
    b2.record_success()
    assert b2._success_count == 1
    assert b2.state is CircuitState.HALF_OPEN

    # OPEN polarity: sync success must NOT reset the failure count
    # (kills the `and` -> `or` twin, whose reset branch would fire for
    # OPEN-with-count>0)
    b3 = _mk(name="s3")
    b3._state = CircuitState.OPEN
    b3._failure_count = 1
    b3.record_success()
    assert b3._failure_count == 1
    assert b3.state is CircuitState.OPEN


# =============================================================================
# reset / reset_async / registry
# =============================================================================


@patched
@caplogs
def test_reset_clears_state_and_logs(logs):
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, _, _, otel_chg, ctx = _stub_env(
        trip_reads=[300.0, 301.0, 302.0, 303.0]
    )
    del g_calls, ctx
    b = _mk()
    run(b._record_failure())
    run(b._record_failure())
    run(b._record_failure())  # trips OPEN
    assert b.state is CircuitState.OPEN
    assert otel_chg == [(("svc", "closed", "open"), {})]
    logs.clear()
    b.reset()
    assert b.state is CircuitState.CLOSED
    assert b._failure_count == 0 and b._success_count == 0
    assert b._half_open_calls == 0
    assert b._last_failure_time is None
    assert b._opened_at is None
    _iso_stamp(b._last_state_change)
    assert g_state.set_calls == [((0,), {}), ((1,), {}), ((0,), {})]
    assert h_state.set_calls == [((0,), {}), ((1,), {}), ((0,), {})]
    assert g_chg.inc_total == 2  # trip + reset
    assert g_chg.last_labels == (
        (),
        {"service": "svc", "from_state": "open", "to_state": "closed"},
    )
    assert otel_chg == [(("svc", "closed", "open"), {}), (("svc", "open", "closed"), {})]
    assert _msgs(logs, logging.INFO) == ["CircuitBreaker 'svc' manually reset to CLOSED"]

    logs.clear()
    b._failure_count = 4
    run(b.reset_async())  # async wrapper under the lock
    assert b._failure_count == 0
    assert _msgs(logs, logging.INFO) == ["CircuitBreaker 'svc' manually reset to CLOSED"]


@patched
@caplogs
def test_reset_from_closed_skips_state_change(logs):
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, _, _, otel_chg, _ = _stub_env(
        trip_reads=[300.0]
    )
    del g_calls, g_fail
    b = _mk()
    logs.clear()  # drop the __init__ INFO (pinned in test_init_defaults_and_config_override)
    b.reset()
    assert g_chg.inc_total == 0  # prev CLOSED -> guard skips the inc
    assert otel_chg == []
    assert g_state.set_calls == [((0,), {}), ((0,), {})]  # init + reset
    assert _msgs(logs, logging.INFO) == ["CircuitBreaker 'svc' manually reset to CLOSED"]


@patched
@caplogs
def test_registry_reset_all_and_getters(logs):
    _stub_env(trip_reads=[200.0, 201.0, 202.0, 203.0, 204.0, 205.0])
    reg = cb.CircuitBreakerRegistry()
    b1 = reg.get_or_create("alpha")
    b2 = reg.get_or_create("beta")
    assert reg.get("alpha") is b1
    assert reg.get("beta") is b2
    assert reg.get("missing") is None
    assert reg.list_names() == ["alpha", "beta"]
    allst = reg.get_all_status()
    assert sorted(allst) == ["alpha", "beta"]
    assert allst["alpha"]["name"] == "alpha" and allst["alpha"]["state"] == "closed"
    assert allst["beta"]["name"] == "beta"
    assert reg.get_or_create("alpha") is b1  # no rebuild

    b1._failure_count = 3
    b2._failure_count = 5
    logs.clear()
    reg.reset_all()
    assert b1._failure_count == 0 and b2._failure_count == 0
    assert b1.state is CircuitState.CLOSED and b2.state is CircuitState.CLOSED
    assert _msgs(logs, logging.INFO) == [
        "CircuitBreaker 'alpha' manually reset to CLOSED",
        "CircuitBreaker 'beta' manually reset to CLOSED",
        "Reset all 2 circuit breakers",
    ]

    reg.clear()
    assert reg.list_names() == []
    assert reg.get_all_status() == {}


# =============================================================================
# force_open
# =============================================================================


@patched
@caplogs
def test_force_open(logs):
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, _, _, otel_chg, _ = _stub_env(
        trip_reads=[888.0, 889.0]
    )
    del g_fail, g_calls
    b = _mk()
    logs.clear()
    b.force_open()
    assert b.state is CircuitState.OPEN
    assert b._opened_at == 888.0  # _transition_to_open read #1
    assert b._last_failure_time == 889.0  # force_open read #2
    assert b.get_status()["opened_at"] == 888.0
    _iso_stamp(b._last_state_change)
    assert h_trips.inc_total == 1
    assert g_chg.last_labels == (
        (),
        {"service": "svc", "from_state": "closed", "to_state": "open"},
    )
    assert otel_chg == [(("svc", "closed", "open"), {})]
    assert _msgs(logs, logging.WARNING) == [
        "CircuitBreaker 'svc' force opened",
        "CircuitBreaker 'svc' transitioned closed -> OPEN (failures=0, threshold=3)",
    ]


# =============================================================================
# get_metrics
# =============================================================================


@patched
def test_get_metrics_none_last_failure():
    cb.time = _stub_time([0.0])
    b = _mk()
    m = b.get_metrics()
    assert m.name == "svc"
    assert m.state is CircuitState.CLOSED
    assert m.failure_count == 0
    assert m.success_count == 0
    assert m.total_calls == 0
    assert m.rejected_calls == 0
    assert m.last_failure_time is None
    assert m.last_state_change is None
    assert m.to_dict()["last_failure_time"] is None


@patched
def test_get_metrics_last_failure_arithmetic():
    cb.time = _stub_time([900.0])  # one monotonic read: elapsed = 900 - 888 = 12
    b = _mk()
    b._last_failure_time = 888.0
    m = b.get_metrics()
    assert m.last_failure_time is not None
    _iso_stamp(m.last_failure_time)  # tz-aware (datetime.now(None) raises)
    delta = (datetime.now(tz=m.last_failure_time.tzinfo) - m.last_failure_time).total_seconds()
    assert 11.5 <= delta <= 13.5  # the -timedelta direction; +timedelta => ~ -11
    assert m.to_dict()["last_failure_time"].endswith("+00:00")


@patched
def test_get_metrics_whole_slots():
    cb.time = _stub_time([0.0])
    b = _mk()
    b._failure_count = 5
    b._success_count = 2
    b._total_calls = 9
    b._rejected_calls = 3
    b._state = CircuitState.HALF_OPEN
    m = b.get_metrics()
    assert m.state is CircuitState.HALF_OPEN
    assert m.failure_count == 5
    assert m.success_count == 2  # kills the success_count=None arm
    assert m.total_calls == 9
    assert m.rejected_calls == 3
    assert m.last_failure_time is None
    assert m.last_state_change is None  # unset passthrough (see passthrough test)


@patched
def test_get_metrics_state_change_passthrough():
    cb.time = _stub_time([0.0])
    b = _mk()
    stamp = datetime.fromisoformat("2026-10-03T09:00:00+00:00")
    b._last_state_change = stamp
    m = b.get_metrics()
    assert m.last_state_change is stamp  # identity passthrough (None arm dies)
    assert m.to_dict()["last_state_change"] == "2026-10-03T09:00:00+00:00"
    b._failure_count = 5
    b._success_count = 2
    b._total_calls = 9
    b._rejected_calls = 3
    b._state = CircuitState.HALF_OPEN
    m2 = b.get_metrics()
    assert m2.failure_count == 5
    assert m2.success_count == 2
    assert m2.total_calls == 9
    assert m2.rejected_calls == 3
    assert m2.state is CircuitState.HALF_OPEN


# =============================================================================
# get_state_info
# =============================================================================


def test_get_state_info_whole_closed():
    b = _mk()
    assert b.get_state_info() == {
        "name": "svc",
        "state": "closed",
        "failure_count": 0,
        "failure_threshold": 3,
        "recovery_timeout": 30.0,
        "half_open_max_calls": 2,
        "half_open_calls": 0,
        "opened_at": None,
        "last_state_change": None,
    }


def test_get_state_info_whole_open():
    b = _mk()
    b._state = CircuitState.OPEN
    b._failure_count = 7
    b._half_open_calls = 1
    b._opened_at = 4242.0
    b._last_state_change = datetime.fromisoformat("2026-10-03T09:00:00+00:00")
    assert b.get_state_info() == {
        "name": "svc",
        "state": "open",
        "failure_count": 7,
        "failure_threshold": 3,
        "recovery_timeout": 30.0,
        "half_open_max_calls": 2,
        "half_open_calls": 1,
        "opened_at": 4242.0,
        "last_state_change": "2026-10-03T09:00:00+00:00",
    }
    # the `and False` twin would print None for a SET stamp
    b._last_state_change = None
    assert b.get_state_info()["last_state_change"] is None


# =============================================================================
# check_and_raise
# =============================================================================


@patched
def test_check_and_raise():
    cb.time = _stub_time([100.0])  # 100-100=0 < 30 -> still rejecting
    b = _mk()
    assert b.check_and_raise() is None  # CLOSED -> allowed, silent
    b._state = CircuitState.OPEN
    b._opened_at = 100.0
    try:
        b.check_and_raise()
        raise AssertionError("should have raised")
    except CoreCircuitBreakerOpenError as e:
        assert str(e) == "Circuit breaker for 'svc' is open. Service is temporarily unavailable."
        assert e.details.get("recovery_timeout_seconds") == 30.0


# =============================================================================
# __aenter__ / __aexit__
# =============================================================================


@patched
def test_aenter_aexit_success():
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, otel_ok, _, _, _, _ = _stub_env()
    del g_state, g_fail, g_chg, h_state, h_trips

    async def use():
        async with _mk(name="ae1") as br:
            assert br.name == "ae1"
            return br.get_status()

    st = run(use())
    assert st["total_calls"] == 1
    assert st["state"] == "closed"
    assert g_calls.inc_total == 1
    assert g_calls.last_labels == ((), {"service": "ae1", "result": "success"})
    assert otel_ok == [(("ae1",), {})]


@patched
def test_aenter_reject_from_open_and_half_open():
    _stub_env(trip_reads=[100.0])

    async def reject(br):
        async with br:
            pass  # pragma: no cover - unreachable

    b = _mk()
    b._state = CircuitState.OPEN
    b._opened_at = 100.0
    try:
        run(reject(b))
        raise AssertionError("should have raised")
    except CircuitBreakerError as e:
        assert str(e) == "Circuit breaker for 'svc' is open. Service is temporarily unavailable."
        assert e.service_name == "svc"
    assert b._rejected_calls == 1
    assert b.get_status()["total_calls"] == 1

    # HALF_OPEN-driven reject: pristine raises "is half_open"; m8/m10 lose
    # the service name and m9/m11 lose the state (defaulting to "open") -
    # ALL four raise mutants change the message here.
    # rejected_calls PRE-SEEDED to 1: the =1 twin resets it to 1 (pristine
    # reaches 2) - the +=1 vs =1 polarity for __aenter__ m5.
    b2 = _mk()
    b2._state = CircuitState.HALF_OPEN
    b2._half_open_calls = 5  # >= max -> allow False
    b2._rejected_calls = 1
    try:
        run(reject(b2))
        raise AssertionError("should have raised")
    except CircuitBreakerError as e:
        assert (
            str(e) == "Circuit breaker for 'svc' is half_open. Service is temporarily unavailable."
        )
    assert b2._rejected_calls == 2


@patched
def test_aenter_half_open_increments():
    async def go():
        b = _mk()
        b._state = CircuitState.HALF_OPEN
        b._half_open_calls = 0
        async with b:
            return b._half_open_calls

    assert run(go()) == 1  # m12 (flip) skips the inc -> 0; m15 (+2) -> 2


@patched
def test_aenter_half_open_increment_is_absolute():
    async def go():
        b = _mk(half_open_max_calls=10)  # keep the seeded value ALLOWABLE
        b._state = CircuitState.HALF_OPEN
        b._half_open_calls = 3  # pre-seeded: +=1 -> 4, the =1 twin -> 1
        async with b:
            return b._half_open_calls

    assert run(go()) == 4


@patched
@caplogs
def test_aexit_records_failure_on_exception(logs):
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, otel_fail, _, _, ctx = _stub_env(
        trip_reads=[555.0]
    )
    del g_state, g_chg, h_state, h_trips

    async def go():
        b = _mk(name="ax1")
        try:
            async with b:
                raise ValueError("boom")
        except ValueError:
            return b
        raise AssertionError  # pragma: no cover

    b = run(go())
    assert b._failure_count == 1
    assert b._last_failure_time == 555.0
    assert otel_fail == [(("ax1",), {})]
    assert g_fail.inc_total == 1 and g_calls.inc_total == 1
    assert ctx.n == 1
    assert _msgs(logs, logging.WARNING) == [
        "CircuitBreaker 'ax1' failure recorded: 1/3",
    ]


@patched
def test_aexit_excluded_exception_no_record():
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, otel_fail, _, _, _ = _stub_env()
    del g_state, g_chg, h_state, h_trips

    async def go():
        b = _mk(
            name="ax2",
            config=CircuitBreakerConfig(**{**_CFG, "excluded_exceptions": (KeyError,)}),
        )
        try:
            async with b:
                raise KeyError("skip")
        except KeyError:
            return b
        raise AssertionError  # pragma: no cover

    b = run(go())
    assert b._failure_count == 0
    assert otel_fail == []
    assert g_fail.inc_total == 0
    assert g_calls.inc_total == 0


# =============================================================================
# protected_call / protect
# =============================================================================


@patched
def test_protected_call_records_and_rejects():
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, otel_ok, otel_fail, _, _, _ = _stub_env(
        trip_reads=[100.0]
    )
    del g_state, g_chg, h_state, h_trips

    async def op():
        return 5

    b1 = _mk(name="pc1")
    assert run(b1.protected_call(op)) == 5
    assert g_calls.last_labels == ((), {"service": "pc1", "result": "success"})
    assert otel_ok == [(("pc1",), {})]

    async def boom():
        raise ValueError("z")

    b2 = _mk(name="pc2")
    with contextlib.suppress(ValueError):
        run(b2.protected_call(boom, record_on=(ValueError,)))
    assert b2._failure_count == 1
    assert otel_fail == [(("pc2",), {})]

    # open circuit: check_and_raise inside protected_call
    b3 = _mk(name="pc3")
    b3._state = CircuitState.OPEN
    b3._opened_at = 100.0
    try:
        run(b3.protected_call(op))
        raise AssertionError("should have raised")
    except CoreCircuitBreakerOpenError as e:
        assert e.details.get("recovery_timeout_seconds") == 30.0

    # NOT-in-record_on: exception rides out WITHOUT a failure record
    b4 = _mk(name="pc4")
    with contextlib.suppress(ValueError):
        run(b4.protected_call(boom, record_on=(KeyError,)))
    assert b4._failure_count == 0
    assert otel_fail == [(("pc2",), {})]  # unchanged


@patched
def test_protect_records_success_and_failure():
    g_state, g_fail, g_chg, g_calls, h_state, h_trips, _, otel_fail, _, _, _ = _stub_env(
        trip_reads=[400.0]
    )
    del g_state, g_chg, h_state, h_trips

    async def good():
        async with _mk(name="pr1").protect():
            return "v"

    assert run(good()) == "v"

    async def bad():
        b = _mk(name="pr2")
        try:
            async with b.protect():
                raise ValueError("x")
        except ValueError:
            return b
        raise AssertionError  # pragma: no cover

    b2 = run(bad())
    assert b2._failure_count == 1
    assert b2._last_failure_time == 400.0
    assert g_fail.last_labels == ((), {"service": "pr2"})
    assert otel_fail == []  # protect's sync record path skips otel


@patched
def test_protect_open_raises_circuit_open_error_with_remaining():
    cb.time = _stub_time([100.0, 125.0])  # allow read, then remaining-computation read

    async def go():
        b = _mk()
        b._state = CircuitState.OPEN
        b._opened_at = 100.0
        async with b.protect():
            return "nope"  # pragma: no cover

    try:
        run(go())
        raise AssertionError("should have raised")
    except CircuitOpenError as e:
        assert str(e) == "Circuit open for svc"
        assert e.service_name == "svc"
        assert e.recovery_time_remaining == 5.0  # 30 - (125 - 100)


@patched
def test_protect_open_remaining_zero_when_no_opened_at():
    cb.time = _stub_time([100.0])

    async def go():
        b = _mk()
        b._state = CircuitState.OPEN
        b._opened_at = None  # no recovery attempt -> reject
        async with b.protect():
            return "nope"  # pragma: no cover

    try:
        run(go())
        raise AssertionError("should have raised")
    except CircuitOpenError as e:
        assert e.recovery_time_remaining == 0.0


# =============================================================================
# global registry helpers
# =============================================================================


def test_global_registry_helpers():
    # real metrics are fine here - only instance identity is asserted
    cb.reset_circuit_breaker_registry()
    assert cb._registry is None
    r1 = cb._get_registry()
    assert isinstance(r1, cb.CircuitBreakerRegistry)
    assert cb._registry is r1
    assert cb._get_registry() is r1  # cached
    b = cb.get_circuit_breaker("gsvc")
    assert b.name == "gsvc"
    assert r1.get("gsvc") is b
    assert cb.get_circuit_breaker("gsvc") is b  # same instance
    cb.reset_circuit_breaker_registry()
    assert cb._registry is None
    r2 = cb._get_registry()
    assert r2 is not r1
    cb.reset_circuit_breaker_registry()


def test_reset_circuit_breaker_registry_none_guard():
    cb._registry = None
    cb.reset_circuit_breaker_registry()  # already None: skip-clear branch
    assert cb._registry is None


# =============================================================================
# REAL prometheus child census (service-label mutants create a silent
# ('None',...) child; only the real child maps can see that)
# =============================================================================


def test_prometheus_children_census_real():
    # NO _stub_env here: this test reads the REAL metric child maps. A
    # labels(service=None)/XX-swap mutant silently creates a ('None',...)/
    # XX child and leaves the correct key ABSENT - invisible through the
    # stubbed parents, decisive here.
    _CENSUS["n"] += 1
    name = f"census-svc-{_CENSUS['n']}"
    legacy = cb.CIRCUIT_BREAKER_STATE
    hsi = cb.HSI_CIRCUIT_BREAKER_STATE
    b = _mk(name=name)
    # __init__ sets both STATE gauges to 0 on the (name,) child
    assert legacy._metrics.get((name,))._value.get() == 0
    assert hsi._metrics.get((name,))._value.get() == 0
    run(b._record_failure())
    run(b._record_failure())
    run(b._record_failure())  # trips
    assert b.state is CircuitState.OPEN
    assert legacy._metrics.get((name,))._value.get() == 1
    assert hsi._metrics.get((name,))._value.get() == 1
    assert cb.CIRCUIT_BREAKER_FAILURES_TOTAL._metrics.get((name,))._value.get() == 3
    failres = cb.CIRCUIT_BREAKER_CALLS_TOTAL._metrics.get((name, "failure"))
    assert failres is not None and failres._value.get() == 3
    key = (name, "closed", "open")
    assert cb.CIRCUIT_BREAKER_STATE_CHANGES_TOTAL._metrics.get(key)._value.get() == 1
    assert cb.HSI_CIRCUIT_BREAKER_TRIPS_TOTAL._metrics.get((name,))._value.get() == 1

    # OPEN -> HALF_OPEN transition sets both gauges to 2 on the real child
    b._opened_at = cb.time.monotonic() - 100.0  # recovery timeout elapsed
    assert run(b.allow_call()) is True
    assert b.state is CircuitState.HALF_OPEN
    assert legacy._metrics.get((name,))._value.get() == 2
    assert hsi._metrics.get((name,))._value.get() == 2

    # HALF_OPEN -> CLOSED transition (via success threshold) sets both to 0
    run(b._record_success())
    run(b._record_success())
    assert b.state is CircuitState.CLOSED
    assert legacy._metrics.get((name,))._value.get() == 0
    assert hsi._metrics.get((name,))._value.get() == 0

    # and reset() from OPEN sets them to 0 as well
    b.force_open()
    assert legacy._metrics.get((name,))._value.get() == 1
    b.reset()
    assert legacy._metrics.get((name,))._value.get() == 0
    assert hsi._metrics.get((name,))._value.get() == 0
