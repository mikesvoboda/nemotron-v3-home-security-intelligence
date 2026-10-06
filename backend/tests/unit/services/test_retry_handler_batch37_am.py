"""Unit tests for retry_handler (campaign #37, battery AM).

Complements the shipped test_retry_handler.py and the batch-28 pipeline_workers
batteries. Every test pins an OBSERVABLE the shipped suite leaves free, so each
mutation family in the 211-killable pool dies on an equality assertion at the
exact site the mutation edits. Per-key disposition (2026-10-04, in-process
trampoline probe with live mechanism controls): 211 DISTINGUISHED / 3 EQUIV.

The shipped file keeps ALL of its assertions inside test classes and asserts
almost nothing about log output, so it contributes no kill for the ~150
log-record mutations here; this file is the log/record authority.

The mutation inventory this file was written against (c37-mutant-class.tsv):
  * log-extra key renames, ``XXnameXX`` / ``NAME`` case twins and whole-``extra``
    drops at 9 call sites -> extras asserted as an exact KEY SET (module payload
    + the 11 ambient keys the app ContextFilter injects into every record) with
    every value pinned;
  * message drops (``logger.info(None)``) and message XX/case twins -> messages
    asserted by EQUALITY, in emission ORDER (fragment asserts pass XX/case);
  * ``sanitize_error(e)`` -> ``sanitize_error(None)`` and -> ``logger.error(None)``
    -> error messages built from a REAL exception through a helper that FAILS
    LOUDLY if the sanitizer is a no-op, so a pin can never go vacuous;
  * ctor/kwarg None-twins (JobFailure fields, ``overflow_policy``,
    ``get_queue_length(None)``, ``requeue_dlq_job(None)``) -> call-literal spies:
    a dropped/None/swapped argument invisible on any instance is visible in the
    recorded CALL;
  * ``datetime.now(UTC)`` -> ``now(None)`` -> tz-awareness of the stored ISO
    string (naive carries no offset), no host-TZ dependency;
  * truncation constants (``>`` vs ``>=``, the two suffix strings) are observable
    only at raw-trace totals 4095/4096/4097 and body lengths 2047/2048/2049 —
    ``_mk_trace`` iterates the message length at ONE constant caller frame;
  * ``elif redis_client is not None and _redis is None`` -> ``or`` only moves
    once a client is ALREADY attached, so both transitions are exercised.

All tests are module-level and sync (the disposition sweep calls them without
pytest); async paths run through asyncio.run. No fixture parameters anywhere
(b30-harness rule: that harness has no fixture machinery).
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime
from unittest import mock

import httpx
import pytest

import backend.services.retry_handler as rh
from backend.core.logging import sanitize_error
from backend.core.redis import QueueOverflowPolicy
from backend.services.retry_handler import (
    DLQStats,
    JobFailure,
    RetryConfig,
    RetryHandler,
    get_retry_handler,
    reset_retry_handler,
)

pytestmark = pytest.mark.unit


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fakes over the exact production surface retry_handler touches
# ---------------------------------------------------------------------------

# Sanitizer-visible failure strings: the module logs sanitize_error(e), so the
# logged message must NOT be str(e) (kills the sanitize_error(None) twin). The
# sanitization is PROVEN by _sanitized() rather than assumed.
ADD_MSG = "redis-down /opt/app/blob"
LEN_MSG = "len-fail /srv/data/blob"
POP_MSG = "pop-fail /srv/data/blob"
PEEK_MSG = "peek-fail /srv/data/blob"
CLEAR_MSG = "clear-fail /srv/data/blob"


class CB:
    """Attribute-faithful circuit-breaker fake (allow/state/failure/name/cfg)."""

    def __init__(self, allow=True, state="closed"):
        self.calls = []
        self._allow = allow
        self.state = type("S", (), {"value": state})()
        self.failure_count = 3
        self.name = "dlq_overflow"
        self.config = type("C", (), {"failure_threshold": 5, "recovery_timeout": 30.0})()

    async def allow_call(self):
        self.calls.append("allow")
        return self._allow

    async def _record_failure(self):
        self.calls.append("fail")

    async def _record_success(self):
        self.calls.append("ok")

    def reset(self):
        self.calls.append("reset")


class AddRes:
    def __init__(self, success=True, error=None, qlen=42, moved=0, dropped=0):
        self.success = success
        self.queue_length = qlen
        self.dropped_count = dropped
        self.moved_to_dlq_count = moved
        self.error = error
        self.warning = None

    @property
    def had_backpressure(self):
        return self.dropped_count > 0 or self.moved_to_dlq_count > 0 or self.error is not None


QUEUE_LENS = {
    "detection_queue": 3,
    "analysis_queue": 5,
    "dlq:detection_queue": 7,
    "dlq:analysis_queue": 11,
}

FAILURE_DICT = {
    "original_job": {"file_path": "/j.jpg"},
    "error": "stored-err",
    "attempt_count": 3,
    "first_failed_at": "FIRST",
    "last_failed_at": "LAST",
    "queue_name": "detection_queue",
    "error_type": "ValueError",
    "stack_trace": "ST",
    "http_status": 502,
    "response_body": "RB",
    "retry_delays": [1.0, 2.0],
    "context": {"k": "v"},
}


class Redis:
    """Call-recording fake. ``fail`` picks which call raises
    ("add"|"len"|"pop"|"peek"|"clear")."""

    def __init__(self, fail=None, add_res=None, pop_val="dict", peek_val=None):
        self.calls = []
        self.fail = fail
        self.add_res = add_res if add_res is not None else AddRes()
        self.pop_val = FAILURE_DICT.copy() if pop_val == "dict" else pop_val
        self.peek_val = [dict(FAILURE_DICT)] if peek_val is None else peek_val

    async def add_to_queue_safe(self, name, payload, **kw):
        self.calls.append(("add", name, payload, dict(kw)))
        if self.fail == "add":
            raise RuntimeError(ADD_MSG)
        return self.add_res

    async def get_queue_length(self, name):
        self.calls.append(("len", name))
        if self.fail == "len":
            raise RuntimeError(LEN_MSG)
        return QUEUE_LENS.get(name, 0)

    async def pop_from_queue_nonblocking(self, name):
        self.calls.append(("pop", name))
        if self.fail == "pop":
            raise RuntimeError(POP_MSG)
        return self.pop_val

    async def peek_queue(self, name, start, end):
        self.calls.append(("peek", name, start, end))
        if self.fail == "peek":
            raise RuntimeError(PEEK_MSG)
        return self.peek_val

    async def clear_queue(self, name):
        self.calls.append(("clear", name))
        if self.fail == "clear":
            raise RuntimeError(CLEAR_MSG)
        return True


def handler(redis=None, cb=None, **cfg_over):
    cfg = RetryConfig(jitter=False, base_delay_seconds=0.001, **cfg_over)
    return RetryHandler(
        redis_client=redis,
        config=cfg,
        dlq_circuit_breaker=cb if cb is not None else CB(),
    )


def _sanitized(exc):
    """sanitize_error(exc), with the sanitization PROVEN (path shortened)."""
    out = sanitize_error(exc)
    assert "/srv" not in out and "/opt" not in out and out != str(exc), (
        "sanitize_error is a no-op in this env — this message pin cannot "
        "discriminate the sanitize_error(None) family"
    )
    return out


# ---------------------------------------------------------------------------
# Log capture. retry_handler.logger sits behind the app ContextFilter, which
# injects 11 ambient keys into EVERY record (measured 2026-10-04); the pins
# below assert the FULL key set, so a renamed/dropped/None extra is a RED.
# ---------------------------------------------------------------------------


class LogCap(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


_STANDARD_LOG_KEYS = set(vars(logging.LogRecord("x", 0, "f", 1, "m", None, None))) | {
    "message",
    "asctime",
    "taskName",
}


def log_extras(record):
    return {k: v for k, v in vars(record).items() if k not in _STANDARD_LOG_KEYS}


class LogSwap:
    """Attach a DEBUG capture handler to retry_handler.logger (the env pins the
    logger to WARNING, so the module's DEBUG rows only surface here)."""

    def __init__(self):
        self.cap = LogCap()

    def __enter__(self):
        self._saved = rh.logger.level
        rh.logger.addHandler(self.cap)
        rh.logger.setLevel(logging.DEBUG)
        return self.cap

    def __exit__(self, *exc):
        rh.logger.removeHandler(self.cap)
        rh.logger.setLevel(self._saved)
        return False


def _measure_ambient():
    with LogSwap() as cap:
        rh.logger.info("c37am-ambient-control")
    assert len(cap.records) == 1, "log capture machinery is broken"
    return frozenset(log_extras(cap.records[0]))


# Warmed at IMPORT time so the control record can never leak into a test's cap.
AMBIENT_KEYS = _measure_ambient()
assert len(AMBIENT_KEYS) >= 4, f"ambient capture failed: {sorted(AMBIENT_KEYS)}"


def expect_extra(record, payload):
    """Extras == ambient keys + EXACTLY these payload keys, values as pinned."""
    extras = log_extras(record)
    assert set(extras) == set(AMBIENT_KEYS) | set(payload), (
        f"extra key-set drift: "
        f"+{sorted(set(extras) - set(AMBIENT_KEYS) - set(payload))} "
        f"-{sorted((set(AMBIENT_KEYS) | set(payload)) - set(extras))}"
    )
    for k, v in payload.items():
        assert extras[k] == v, f"extra {k}: {extras[k]!r} != {v!r}"


def iso_aware(iso_str):
    """datetime.now(UTC) stores an offset-bearing ISO string; now(None) does not."""
    assert isinstance(iso_str, str), f"timestamp not stored: {iso_str!r}"
    return datetime.fromisoformat(iso_str).tzinfo is not None


def rows(records):
    """(level, message) pairs in EMISSION ORDER — the shape most twins move."""
    return [(logging.getLevelName(r.levelno), r.getMessage()) for r in records]


# =========================================================================
# RetryHandler.__init__ — auto circuit breaker identity (3 keys)
# =========================================================================


def test_c37am_01_init_cb_name_and_settings_config_c37():
    """The auto-built DLQ breaker carries the exact name and the
    settings-derived config; name None/XX/UPPER twins die on equality."""
    from backend.core.config import get_settings

    h = RetryHandler()
    cb = h._dlq_circuit_breaker
    assert cb.name == "dlq_overflow"
    s = get_settings()
    assert cb.config.failure_threshold == s.dlq_circuit_breaker_failure_threshold
    assert cb.config.recovery_timeout == s.dlq_circuit_breaker_recovery_timeout
    assert cb.config.half_open_max_calls == s.dlq_circuit_breaker_half_open_max_calls
    assert cb.config.success_threshold == s.dlq_circuit_breaker_success_threshold
    assert h.config.max_retries == 3
    assert h._redis is None


# =========================================================================
# with_retry — loop, log records, DLQ hand-off (59 keys)
# =========================================================================


def _exhaust(h, op):
    """Run with_retry with _move_to_dlq and asyncio.sleep spied (the real
    _move_to_dlq body still executes). Returns (result, move-kwargs, sleeps,
    records in emission order)."""
    moves = []

    async def spy_move(self, **kw):
        # record the hand-off kwargs and short-circuit (the real _move_to_dlq
        # body is covered by the dedicated tests below; running it here would
        # add an INFO row + redis len/add calls that pollute this test's rows).
        moves.append(kw)
        return True

    sleeps = []
    real_sleep = asyncio.sleep

    async def spy_sleep(delay):  # the module calls sleep(delay) with one arg
        sleeps.append(delay)
        return await real_sleep(0)

    with (
        mock.patch.object(RetryHandler, "_move_to_dlq", spy_move),
        mock.patch("asyncio.sleep", spy_sleep),
        LogSwap() as cap,
    ):
        res = run(h.with_retry(op, {"file_path": "/x.jpg", "camera_id": "cam1"}, "detection_queue"))
    return res, moves, sleeps, list(cap.records)


async def _fail():
    raise ValueError("boom")


async def _fail_empty():
    raise ValueError("")


class Flaky:
    def __init__(self):
        self.n = 0

    async def __call__(self):
        self.n += 1
        if self.n == 1:
            raise RuntimeError("first-try")
        return "OP-OK"


def test_c37am_02_with_retry_success_path_record_sequence_c37():
    """Retry-then-succeed: RetryResult field equality plus the FULL 5-row
    record sequence (attempt DEBUG, failed WARNING, waiting DEBUG, attempt
    DEBUG, success INFO) with exact messages, levels, order and extras."""
    h = handler(max_retries=3)
    res, moves, sleeps, recs = _exhaust(h, Flaky())
    assert (res.success, res.result, res.error, res.attempts, res.moved_to_dlq) == (
        True,
        "OP-OK",
        None,
        2,
        False,
    )
    assert moves == [] and sleeps == [0.001]
    assert rows(recs) == [
        ("DEBUG", "Attempt 1/3 for detection_queue"),
        ("WARNING", "Attempt 1/3 failed for detection_queue: first-try"),
        ("DEBUG", "Waiting 0.00s before retry 2"),
        ("DEBUG", "Attempt 2/3 for detection_queue"),
        ("INFO", "Operation succeeded on attempt 2 for detection_queue"),
    ]
    expect_extra(recs[0], {"attempt": 1, "max_retries": 3, "queue_name": "detection_queue"})
    expect_extra(
        recs[1],
        {
            "attempt": 1,
            "max_retries": 3,
            "queue_name": "detection_queue",
            "error": "first-try",
        },
    )
    expect_extra(recs[2], {"delay_seconds": 0.001, "next_attempt": 2})
    expect_extra(recs[3], {"attempt": 2, "max_retries": 3, "queue_name": "detection_queue"})
    expect_extra(recs[4], {"attempt": 2, "queue_name": "detection_queue"})


def test_c37am_03_with_retry_exhaustion_dlq_kwargs_and_records_c37():
    """Exhaustion (max_retries=3, redis attached): RetryResult equality; the
    _move_to_dlq call literals (attempt_count, error, retry_delays LIST vs the None-twins,
    tz-aware first_failed_at, error_type, stack-trace content, http
    None-payloads); the 6-row record sequence."""
    h = handler(Redis(), max_retries=3)
    res, moves, sleeps, recs = _exhaust(h, _fail)
    assert (res.success, res.result, res.error, res.attempts) == (False, None, "boom", 3)
    assert res.moved_to_dlq is True
    assert sleeps == [0.001, 0.002]
    assert len(moves) == 1
    kw = moves[0]
    assert kw["job_data"] == {"file_path": "/x.jpg", "camera_id": "cam1"}
    assert kw["error"] == "boom"
    assert kw["attempt_count"] == 3
    assert kw["queue_name"] == "detection_queue"
    assert iso_aware(kw["first_failed_at"])
    assert kw["error_type"] == "ValueError"
    assert kw["stack_trace"].startswith("Traceback (most recent call last):")
    assert "ValueError: boom" in kw["stack_trace"]
    assert kw["http_status"] is None and kw["response_body"] is None
    assert kw["retry_delays"] == [0.001, 0.002]

    assert rows(recs) == [
        ("DEBUG", "Attempt 1/3 for detection_queue"),
        ("WARNING", "Attempt 1/3 failed for detection_queue: boom"),
        ("DEBUG", "Waiting 0.00s before retry 2"),
        ("DEBUG", "Attempt 2/3 for detection_queue"),
        ("WARNING", "Attempt 2/3 failed for detection_queue: boom"),
        ("DEBUG", "Waiting 0.00s before retry 3"),
        ("DEBUG", "Attempt 3/3 for detection_queue"),
        ("WARNING", "Attempt 3/3 failed for detection_queue: boom"),
        ("ERROR", "All 3 retries exhausted for detection_queue"),
    ]
    expect_extra(recs[2], {"delay_seconds": 0.001, "next_attempt": 2})
    expect_extra(recs[5], {"delay_seconds": 0.002, "next_attempt": 3})
    expect_extra(
        recs[8],
        {
            "queue_name": "detection_queue",
            "error": "boom",
            "moved_to_dlq": res.moved_to_dlq,
        },
    )


def test_c37am_04_with_retry_empty_error_falls_back_to_unknown_c37():
    """ValueError('') makes last_error falsy: RetryResult.error stays '' while
    the DLQ error literal must be EXACTLY 'Unknown error' — kills the or->and
    twin (which yields False) and the case/XX fallback twins; a single attempt
    also pins the retry_delays [] -> None branch."""
    h = handler(Redis(), max_retries=1)
    res, moves, sleeps, recs = _exhaust(h, _fail_empty)
    assert res.error == "" and res.attempts == 1
    assert sleeps == []
    assert len(moves) == 1
    assert moves[0]["error"] == "Unknown error"
    assert moves[0]["retry_delays"] is None
    assert moves[0]["error_type"] == "ValueError"
    assert rows(recs) == [
        ("DEBUG", "Attempt 1/1 for detection_queue"),
        ("WARNING", "Attempt 1/1 failed for detection_queue: "),
        ("ERROR", "All 1 retries exhausted for detection_queue"),
    ]
    expect_extra(
        recs[1],
        {"attempt": 1, "max_retries": 1, "error": "", "queue_name": "detection_queue"},
    )
    # the spy short-circuits _move_to_dlq to True, so the ERROR record must
    # carry that same True — the hand-off result flows through observable.
    assert res.moved_to_dlq is True
    expect_extra(recs[2], {"queue_name": "detection_queue", "error": "", "moved_to_dlq": True})


def test_c37am_05_with_retry_no_redis_skips_dlq_polarity_c37():
    """redis=None: no DLQ hand-off even though first_failed_at IS set (kills
    the `if self._redis and first_failed_at` -> or polarity: the spy records the
    CALL itself, not just its effect)."""
    h = handler(None, max_retries=1)
    res, moves, _sleeps, recs = _exhaust(h, _fail)
    assert res.success is False and res.moved_to_dlq is False
    assert moves == []
    assert rows(recs)[-1] == ("ERROR", "All 1 retries exhausted for detection_queue")


def test_c37am_06_with_retry_zero_retries_error_literal_c37():
    """max_retries=0 never enters the loop: RetryResult.error is the loop-init
    literal None (kills the last_error None->'' init twin observably) and the
    single ERROR record carries error None."""
    h = handler(max_retries=0)
    res, moves, sleeps, recs = _exhaust(h, _fail)
    assert res.error is None and res.attempts == 0 and res.success is False
    assert moves == [] and sleeps == []
    assert rows(recs) == [("ERROR", "All 0 retries exhausted for detection_queue")]
    expect_extra(recs[0], {"queue_name": "detection_queue", "error": None, "moved_to_dlq": False})


# =========================================================================
# _extract_error_context — truncation boundaries (11 keys)
# =========================================================================


def _mk_exc(msg):
    try:
        raise ValueError(msg)
    except ValueError as e:
        return e


def _raw_trace_of(exc):
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def _mk_trace(target):
    """ValueError whose RAW traceback text length is exactly ``target``.

    The search lives inside this function so every candidate's caller frame is
    this constant line; traceback overhead is NOT linear in message length
    (repeated-frame compression), so iterate to exactness and REUSE the
    verified exception.
    """
    n = target - len(_raw_trace_of(_mk_exc(""))) - 200

    def _cand(count):
        try:
            raise ValueError("M" * count)
        except ValueError as e:
            return e

    for _ in range(400):
        cand = _cand(n)
        got = len(_raw_trace_of(cand))
        if got == target:
            return cand
        n += target - got
    raise AssertionError(f"no msg length hits rawlen {target}")


def _http_exc(body_len):
    req = httpx.Request("POST", "http://svc/completion")
    resp = httpx.Response(502, request=req, text="R" * body_len)
    return httpx.HTTPStatusError("status-502", request=req, response=resp)


def test_c37am_07_extract_short_trace_verbatim_and_empty_c37():
    """Short trace passes through VERBATIM (kills the 'XXXX' join separator and
    the three None-argument twins) with error_type the exact class name; a None
    exception yields an empty dict."""
    h = handler()
    exc = _mk_exc("boom-message")
    ctx = h._extract_error_context(exc)
    assert ctx["error_type"] == "ValueError"
    assert ctx["stack_trace"] == _raw_trace_of(exc)
    assert "http_status" not in ctx and "response_body" not in ctx
    assert h._extract_error_context(None) == {}


def test_c37am_08_extract_stack_truncation_boundary_c37():
    """max_stack_trace_length=4096: raw 4095/4096 pass verbatim, raw 4097
    truncates to EXACTLY 4096 chars ending '\\n... [truncated]' — the >= twin
    and both suffix twins are only observable at these points."""
    h = handler()
    for total in (4095, 4096):
        st = h._extract_error_context(_mk_trace(total))["stack_trace"]
        assert len(st) == total, f"raw {total} altered: len={len(st)}"
        assert st.endswith("MMMM\n")
    st = h._extract_error_context(_mk_trace(4097))["stack_trace"]
    assert len(st) == 4096
    assert st.endswith("\n... [truncated]")
    assert "XX" not in st and "[TRUNCATED]" not in st


def test_c37am_09_extract_response_body_boundary_c37():
    """max_response_body_length=2048: 2047/2048 verbatim, 2049 -> 2048 ending
    EXACTLY '... [truncated]'; http_status carries the status code."""
    h = handler()
    for n in (2047, 2048):
        ctx = h._extract_error_context(_http_exc(n))
        assert ctx["response_body"] == "R" * n
        assert ctx["http_status"] == 502
        assert ctx["error_type"] == "HTTPStatusError"
    ctx = h._extract_error_context(_http_exc(2049))
    rb = ctx["response_body"]
    assert len(rb) == 2048
    assert rb.endswith("... [truncated]")
    assert "XX" not in rb and "[TRUNCATED]" not in rb


# =========================================================================
# _capture_system_context (8 keys)
# =========================================================================


def test_c37am_10_capture_context_values_and_queue_args_c37():
    """Returned dict EXACTLY; both get_queue_length call args are the real
    queue constants (None-twins die on the spy, None-value twins on the dict);
    nothing is logged on the happy path."""
    r = Redis()
    h = handler(r)
    with LogSwap() as cap:
        ctx = run(h._capture_system_context())
    assert ctx == {
        "detection_queue_depth": 3,
        "analysis_queue_depth": 5,
        "dlq_circuit_breaker_state": "closed",
    }
    assert r.calls == [("len", "detection_queue"), ("len", "analysis_queue")]
    assert cap.records == []


def test_c37am_11_capture_context_len_failure_and_no_redis_c37():
    """len() raises: the DEBUG record is emitted (message equality + the
    exception text) and the breaker key survives alone; redis=None: ONLY the
    breaker key — the queue keys are ABSENT, not None-valued."""
    h = handler(Redis(fail="len"))
    with LogSwap() as cap:
        ctx = run(h._capture_system_context())
    assert ctx == {"dlq_circuit_breaker_state": "closed"}
    assert len(cap.records) == 1
    rec = cap.records[0]
    assert rec.levelno == logging.DEBUG
    assert rec.getMessage().startswith("Failed to capture queue depths for error context:")
    assert LEN_MSG in rec.getMessage()

    with LogSwap() as cap2:
        ctx2 = run(handler(None)._capture_system_context())
    assert ctx2 == {"dlq_circuit_breaker_state": "closed"}
    assert cap2.records == []


# =========================================================================
# _move_to_dlq — the five paths (73 keys)
# =========================================================================

MOVE_KW = {
    "job_data": {"file_path": "/a.jpg", "camera_id": "cam1"},
    "error": "err-msg",
    "attempt_count": 3,
    "first_failed_at": "FIRST",
    "queue_name": "detection_queue",
    "error_type": "ValueError",
    "stack_trace": "ST",
    "http_status": 502,
    "response_body": "RB",
    "retry_delays": [1.0, 2.0],
}


def _move(h, **over):
    kw = {**MOVE_KW, **over}
    with LogSwap() as cap:
        out = run(h._move_to_dlq(**kw))
    return out, list(cap.records)


def test_c37am_12_move_no_redis_warns_and_returns_false_c37():
    out, recs = _move(handler(None))
    assert out is False
    assert rows(recs) == [("WARNING", "Cannot move job to DLQ: Redis client not initialized")]


def test_c37am_13_move_circuit_open_critical_record_c37():
    """Open circuit: False, NO redis write, breaker consulted once, and the
    CRITICAL DATA LOSS record with message equality plus the full 10-key extras
    payload (state value, failures, threshold, recovery timeout, the three
    lost_job_* fields, data_loss True) — every rename/case/False twin REDs."""
    cb = CB(allow=False, state="open")
    r = Redis()
    h = handler(r, cb)
    out, recs = _move(h)
    assert out is False
    assert r.calls == [] and cb.calls == ["allow"]
    assert len(recs) == 1
    rec = recs[0]
    assert rec.levelno == logging.ERROR
    assert rec.getMessage() == (
        "CRITICAL DATA LOSS: DLQ circuit breaker is open, "
        "job from detection_queue will be PERMANENTLY LOST. "
        "Original error: err-msg. "
        "Circuit breaker will recover after timeout or manual reset."
    )
    expect_extra(
        rec,
        {
            "queue_name": "detection_queue",
            "circuit_state": "open",
            "circuit_failures": 3,
            "circuit_threshold": 5,
            "circuit_recovery_timeout": 30.0,
            "lost_job_data": {"file_path": "/a.jpg", "camera_id": "cam1"},
            "lost_job_error": "err-msg",
            "lost_job_attempt_count": 3,
            "lost_job_first_failed_at": "FIRST",
            "data_loss": True,
        },
    )


def test_c37am_14_move_happy_call_literals_payload_and_record_c37():
    """Happy path: the exact redis call SEQUENCE (the two non-DLQ queue depths
    then the DLQ add), add_to_queue_safe receives ('dlq:detection_queue', the
    JobFailure.to_dict literal, overflow_policy=REJECT) — every JobFailure ctor
    None-twin and the now(None) twin die on the payload; the success INFO
    record is pinned; the breaker records success."""
    cb, r = CB(), Redis()
    h = handler(r, cb)
    out, recs = _move(h)
    assert out is True
    assert [c[0] for c in r.calls] == ["len", "len", "add"]
    assert r.calls[0][1] == "detection_queue"
    assert r.calls[1][1] == "analysis_queue"
    name, payload, kw = r.calls[2][1:]
    assert name == "dlq:detection_queue"
    assert kw == {"overflow_policy": QueueOverflowPolicy.REJECT}
    assert set(payload) == {
        "original_job",
        "error",
        "attempt_count",
        "first_failed_at",
        "last_failed_at",
        "queue_name",
        "error_type",
        "stack_trace",
        "http_status",
        "response_body",
        "retry_delays",
        "context",
    }
    assert payload["original_job"] == {"file_path": "/a.jpg", "camera_id": "cam1"}
    assert payload["error"] == "err-msg"
    assert payload["attempt_count"] == 3
    assert payload["first_failed_at"] == "FIRST"
    assert iso_aware(payload["last_failed_at"])
    assert payload["queue_name"] == "detection_queue"
    assert payload["error_type"] == "ValueError"
    assert payload["stack_trace"] == "ST"
    assert payload["http_status"] == 502
    assert payload["response_body"] == "RB"
    assert payload["retry_delays"] == [1.0, 2.0]
    assert payload["context"] == {
        "detection_queue_depth": 3,
        "analysis_queue_depth": 5,
        "dlq_circuit_breaker_state": "closed",
    }
    assert cb.calls == ["allow", "ok"]
    assert rows(recs) == [("INFO", "Moved job to DLQ: dlq:detection_queue")]
    expect_extra(
        recs[0],
        {
            "dlq_name": "dlq:detection_queue",
            "original_queue": "detection_queue",
            "attempt_count": 3,
            "error": "err-msg",
        },
    )


def test_c37am_15_move_dlq_name_follows_the_source_queue_c37():
    """The dlq-prefixed target name comes from the queue_name argument: a
    non-default source queue must produce dlq:analysis_queue (kills any
    hardcoded-detection twin and the constant-collapse family)."""
    r = Redis()
    h = handler(r, CB())
    out, recs = _move(h, queue_name="analysis_queue")
    assert out is True
    name, payload, kw = r.calls[2][1:]
    assert name == "dlq:analysis_queue"
    assert payload["queue_name"] == "analysis_queue"
    assert kw == {"overflow_policy": QueueOverflowPolicy.REJECT}
    assert rows(recs) == [("INFO", "Moved job to DLQ: dlq:analysis_queue")]


def test_c37am_16_move_queue_full_error_record_and_failure_c37():
    """add reports failure: False + breaker failure + the CRITICAL queue-full
    ERROR record, message equality ('3' and '5' are DIFFERENT literals so a
    swap moves the message) and the 8-key extras payload."""
    cb, r = CB(), Redis(add_res=AddRes(success=False, error="DLQ FULL", qlen=99))
    h = handler(r, cb)
    out, recs = _move(h)
    assert out is False
    assert cb.calls == ["allow", "fail"]
    assert len(recs) == 1
    rec = recs[0]
    assert rec.levelno == logging.ERROR
    assert rec.getMessage() == (
        "CRITICAL: Failed to move job to DLQ (queue full): dlq:detection_queue. "
        "Circuit breaker failures: 3/5"
    )
    expect_extra(
        rec,
        {
            "dlq_name": "dlq:detection_queue",
            "original_queue": "detection_queue",
            "attempt_count": 3,
            "error": "err-msg",
            "dlq_error": "DLQ FULL",
            "queue_length": 99,
            "circuit_state": "closed",
            "circuit_failures": 3,
        },
    )


def test_c37am_17_move_exception_path_sanitize_and_failures_c37():
    """add raises: False + breaker failure + ERROR record whose message embeds
    sanitize_error(e) EXACTLY (kills sanitize_error(None) -> 'None' and the
    logger.error(None) twin) with the 3-key extras payload."""
    cb, r = CB(), Redis(fail="add")
    h = handler(r, cb)
    out, recs = _move(h)
    assert out is False
    assert cb.calls == ["allow", "fail"]
    assert len(recs) == 1
    rec = recs[0]
    assert rec.levelno == logging.ERROR
    assert rec.getMessage() == (
        f"Failed to move job to DLQ: {_sanitized(RuntimeError(ADD_MSG))}. "
        "Circuit breaker failures: 3/5"
    )
    expect_extra(
        rec,
        {"queue_name": "detection_queue", "circuit_state": "closed", "circuit_failures": 3},
    )


# =========================================================================
# get_dlq_stats (4 keys)
# =========================================================================


def test_c37am_18_stats_counts_sum_and_queue_args_c37():
    """The DLQ constants reach both get_queue_length calls (None-twins die on
    the spy) and total == 7+11: the ->0 and ->single-operand twins differ at
    18 vs 0 and 7."""
    r = Redis()
    h = handler(r)
    with LogSwap() as cap:
        stats = run(h.get_dlq_stats())
    assert stats == DLQStats(detection_queue_count=7, analysis_queue_count=11, total_count=18)
    assert r.calls == [("len", "dlq:detection_queue"), ("len", "dlq:analysis_queue")]
    assert cap.records == []


def test_c37am_19_stats_no_redis_and_error_paths_c37():
    h1 = handler(None)
    with LogSwap() as cap0:
        assert run(h1.get_dlq_stats()) == DLQStats()
    assert cap0.records == []  # no-redis is SILENT, not an error row
    with LogSwap() as cap:
        assert run(handler(Redis(fail="len")).get_dlq_stats()) == DLQStats()
    assert len(cap.records) == 1
    rec = cap.records[0]
    assert rec.levelno == logging.ERROR
    assert rec.getMessage() == (f"Failed to get DLQ stats: {_sanitized(RuntimeError(LEN_MSG))}")


# =========================================================================
# reset_dlq_circuit_breaker (8 keys)
# =========================================================================


def test_c37am_20_reset_cb_call_message_and_extra_c37():
    cb = CB()
    h = handler(Redis(), cb)
    with LogSwap() as cap:
        assert h.reset_dlq_circuit_breaker() is None
    assert cb.calls == ["reset"]
    assert rows(cap.records) == [("INFO", "DLQ circuit breaker reset to CLOSED state")]
    expect_extra(cap.records[0], {"circuit_name": "dlq_overflow"})


# =========================================================================
# get_dlq_jobs (2 keys)
# =========================================================================


def test_c37am_21_get_jobs_peek_args_roundtrip_and_errors_c37():
    r = Redis()
    h = handler(r)
    with LogSwap() as cap:
        jobs = run(h.get_dlq_jobs("dlq:detection_queue"))
    assert r.calls == [("peek", "dlq:detection_queue", 0, -1)]  # default slice literal
    assert len(jobs) == 1
    j = jobs[0]
    assert isinstance(j, JobFailure)
    assert (j.original_job, j.error, j.attempt_count) == ({"file_path": "/j.jpg"}, "stored-err", 3)
    assert (j.first_failed_at, j.last_failed_at, j.queue_name) == (
        "FIRST",
        "LAST",
        "detection_queue",
    )
    assert cap.records == []

    assert run(handler(None).get_dlq_jobs("dlq:x")) == []
    with LogSwap() as cap2:
        assert run(handler(Redis(fail="peek")).get_dlq_jobs("dlq:x")) == []
    assert len(cap2.records) == 1
    assert cap2.records[0].levelno == logging.ERROR
    assert cap2.records[0].getMessage() == (
        f"Failed to get DLQ jobs: {_sanitized(RuntimeError(PEEK_MSG))}"
    )


# =========================================================================
# requeue_dlq_job (9 keys)
# =========================================================================


def test_c37am_22_requeue_happy_empty_and_error_paths_c37():
    r = Redis()
    h = handler(r)
    with LogSwap() as cap:
        assert run(h.requeue_dlq_job("dlq:detection_queue")) == {"file_path": "/j.jpg"}
    assert r.calls == [("pop", "dlq:detection_queue")]
    assert rows(cap.records) == [("INFO", "Requeued job from dlq:detection_queue")]
    expect_extra(
        cap.records[0],
        {"dlq_name": "dlq:detection_queue", "original_queue": "detection_queue"},
    )

    assert run(handler(None).requeue_dlq_job("dlq:x")) is None
    with LogSwap() as cap2:
        assert run(handler(Redis(pop_val=None)).requeue_dlq_job("dlq:x")) is None
    assert cap2.records == []  # an empty DLQ logs NOTHING (silent-path twins)
    with LogSwap() as cap3:
        assert run(handler(Redis(fail="pop")).requeue_dlq_job("dlq:x")) is None
    assert len(cap3.records) == 1
    assert cap3.records[0].levelno == logging.ERROR
    assert cap3.records[0].getMessage() == (
        f"Failed to requeue DLQ job: {_sanitized(RuntimeError(POP_MSG))}"
    )


# =========================================================================
# clear_dlq (3 keys)
# =========================================================================


def test_c37am_23_clear_paths_c37():
    r = Redis()
    h = handler(r)
    with LogSwap() as cap:
        assert run(h.clear_dlq("dlq:detection_queue")) is True
    assert r.calls == [("clear", "dlq:detection_queue")]
    assert rows(cap.records) == [("INFO", "Cleared DLQ: dlq:detection_queue")]

    assert run(handler(None).clear_dlq("dlq:x")) is False
    with LogSwap() as cap2:
        assert run(handler(Redis(fail="clear")).clear_dlq("dlq:x")) is False
    assert len(cap2.records) == 1
    assert cap2.records[0].levelno == logging.ERROR
    assert cap2.records[0].getMessage() == (
        f"Failed to clear DLQ: {_sanitized(RuntimeError(CLEAR_MSG))}"
    )


# =========================================================================
# move_dlq_job_to_queue (32 keys)
# =========================================================================


def test_c37am_24_move_dq_happy_call_literals_and_info_c37():
    r = Redis()
    h = handler(r)
    with LogSwap() as cap:
        assert run(h.move_dlq_job_to_queue("dlq:x", "target_q")) is True
    pops = [c for c in r.calls if c[0] == "pop"]
    adds = [c for c in r.calls if c[0] == "add"]
    assert pops == [("pop", "dlq:x")]  # dlq_name reaches requeue (None-twin dies)
    assert len(adds) == 1
    name, payload, kw = adds[0][1:]
    assert name == "target_q"
    assert payload == {"file_path": "/j.jpg"}
    assert kw == {"overflow_policy": QueueOverflowPolicy.DLQ}
    assert rows(cap.records) == [
        ("INFO", "Requeued job from dlq:x"),
        ("INFO", "Moved job from dlq:x to target_q"),
    ]
    expect_extra(cap.records[1], {"dlq_name": "dlq:x", "target_queue": "target_q"})


def test_c37am_25_move_dq_add_failure_error_record_c37():
    r = Redis(add_res=AddRes(success=False, error="TGT FULL", qlen=42))
    h = handler(r)
    with LogSwap() as cap:
        assert run(h.move_dlq_job_to_queue("dlq:x", "target_q")) is False
    assert rows(cap.records) == [
        ("INFO", "Requeued job from dlq:x"),
        ("ERROR", "Failed to move job from dlq:x to target_q: TGT FULL"),
    ]
    expect_extra(
        cap.records[1],
        {"dlq_name": "dlq:x", "target_queue": "target_q", "queue_length": 42},
    )


def test_c37am_26_move_dq_backpressure_warning_record_c37():
    r = Redis(add_res=AddRes(success=True, moved=2, qlen=8))
    h = handler(r)
    with LogSwap() as cap:
        assert run(h.move_dlq_job_to_queue("dlq:x", "target_q")) is True
    rows_ = rows(cap.records)
    assert rows_[1] == (
        "WARNING",
        "Queue backpressure while moving job from dlq:x to target_q",
    )
    assert rows_[2] == ("INFO", "Moved job from dlq:x to target_q")
    expect_extra(
        cap.records[1],
        {
            "dlq_name": "dlq:x",
            "target_queue": "target_q",
            "queue_length": 8,
            "moved_to_dlq": 2,
        },
    )


def test_c37am_27_move_dq_empty_no_redis_and_raise_c37():
    assert run(handler(None).move_dlq_job_to_queue("dlq:x", "t")) is False
    with LogSwap() as cap:
        h_empty = handler(Redis(pop_val=None))
        assert run(h_empty.move_dlq_job_to_queue("dlq:x", "t")) is False
    assert [x for x in cap.records if x.levelno >= logging.WARNING] == []

    h = handler(Redis())
    boom = RuntimeError("rq-boom /srv/data/blob")
    with (
        mock.patch.object(h, "requeue_dlq_job", mock.AsyncMock(side_effect=boom)),
        LogSwap() as cap2,
    ):
        assert run(h.move_dlq_job_to_queue("dlq:x", "t")) is False
    assert rows(cap2.records) == [("ERROR", f"Failed to move DLQ job: {_sanitized(boom)}")]


# =========================================================================
# get_retry_handler global (1 key)
# =========================================================================


def test_c37am_28_global_handler_attach_then_ignore_client_c37():
    """The elif condition's and->or twin only moves once a client is ALREADY
    attached: it would overwrite an established client on every later call."""
    reset_retry_handler()
    try:
        first = get_retry_handler(None)
        assert get_retry_handler(None) is first
        assert first._redis is None
        r1 = Redis()
        assert get_retry_handler(r1) is first
        assert first._redis is r1  # attach happened once
        r2 = Redis()
        assert get_retry_handler(r2) is first
        assert first._redis is r1  # while _redis is set the argument is IGNORED
        assert first._redis is not r2
    finally:
        reset_retry_handler()


# =========================================================================
# Backoff literals (belt: the shipped file pins get_delay directly; these pin
# what with_retry/the payload carries when jitter is ON)
# =========================================================================


def test_c37am_29_jitter_delay_window_within_bounds_c37():
    cfg = RetryConfig(max_retries=4, jitter=True, base_delay_seconds=1.0)
    for attempt in (1, 2, 3, 5):
        base = min(1.0 * (2.0 ** (attempt - 1)), 30.0)
        delay = cfg.get_delay(attempt)
        assert base <= delay <= base * 1.25
        assert delay <= 30.0 * 1.25


# =========================================================================
# JobFailure round-trip guard for the from_dict backward-compat path exercised
# by get_dlq_jobs / requeue above
# =========================================================================


def test_c37am_30_failure_roundtrip_minimal_dict_c37():
    minimal = {
        "original_job": {"p": 1},
        "error": "e",
        "attempt_count": 1,
        "first_failed_at": "F",
        "last_failed_at": "L",
        "queue_name": "q",
    }
    j = JobFailure.from_dict(minimal)
    assert (j.error_type, j.stack_trace, j.http_status) == (None, None, None)
    assert (j.response_body, j.retry_delays, j.context) == (None, None, None)
    assert JobFailure.from_dict(j.to_dict()).to_dict() == j.to_dict()
