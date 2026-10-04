# TARGET-MODULE: backend.services.pipeline_quality_audit_service
"""Battery AL - campaign #36 kill battery for pipeline_quality_audit_service.py.

Covers the 214 keys the bank leaves surviving; the shipped-only per-key sweep
proved the pool FRESH (/home/agent/runs/c36-shipped-sweep.txt: "1 red / 213
green / 0 other"). The lone RED (_call_llm__mutmut_21, url -> None) is already
killed by the shipped endpoint test - a stale-era verdict; it stays in the pool
and attributes at close via the shipped-probe route, so it is NOT re-authored.

Killing machinery, by family:
  * httpx.AsyncClient swapped for a class spy: the CTOR kwargs are pinned by
    IDENTITY (timeout must BE service._timeout - timeout=None/dropped/another
    object fail), every post() (url, json=, headers=) literal is pinned
    EXACTLY (the RAW dict pre-normalization: "content-type" != "Content-Type"
    here), and a content-ABSENT response pins the default "" vs None vs "XXXX".
  * the service's own Timeout read back field-by-field
    (connect/read/write/pool == 10.0/120.0/10.0/10.0) - every 10->11 / ->None.
  * the four _run_* mode spies plus an _call_llm spy recording (args, kwargs)
    EXACTLY: the delegated event must be the SAME object (None-swaps RED) and
    the formatted prompt is asserted VERBATIM against the module template
    .format()-ed with the event fields (None-swap format args RED).
  * a plain logging.Handler on pqas.logger AND on
    backend.core.json_utils._logger: exact record.msg plus the exact extra=
    key SET and value - the XX/UPPER/lower message mutants, the exc_info
    True -> None/False family, the extra=None/dropped family, and the
    safe_json_loads context f-string (context=None logs "unspecified").
  * a statement-signature session fake: every execute() is pinned by compiled
    Postgres text (literal_binds); UNPINNED sql RAISES, so execute(None),
    select(None), where(None), >= <-> > and the dropped WHERE clauses all RED.
    The pin list holds ONLY shipped text, so a mutant statement never matches.
  * get_stats delegation spied on the INSTANCE: the exact (args, kwargs) tuple
    pins session identity and the days value (get_stats(days) / (session, None)
    / (None, days) all RED); a trailing-comma drop is a syntax no-op -> ledger.
  * round() divergence rows: round(-0.6882472, None) == -1 and round(.., ) ==
    -1 vs shipped -0.6882, so one pinned correlation kills both round keys.
    Likewise np.std([0.0, 0.0, 2.0, 2.0]) IS exactly 1.0 -> the `std == 1`
    guard key is killable (shipped returns 0.0 for florence, mutant all-None).
  * the TZ lever (TZ=Etc/GMT+11 + time.tzset(), restored on exit):
    datetime.now(None) returns a NAIVE local time, so comparing it against
    datetime.now(UTC) raises TypeError - both audited_at keys RED in
    create_partial_audit and run_evaluation_llm_calls.
  * sorted() ordering: `sorted(items, key=None)` degrades to TUPLE order
    (suggestion name asc), `+x[1]` to frequency asc, and `-cast(..)` asc for
    the global sort - all killed by an EXACT ordered recommendation list,
    including the exact "priority" literal on a count == len(audits) * 0.3
    boundary row (shipped `>` -> medium, `>=` -> high).

HONESTY LEDGER (registered equivalents - each PROVEN by construction probe in
/home/agent/runs/c36-probe/, NOT inferred from diff shape): 30 keys.
  * qc fromkeys(MODEL_NAMES, None) -> dropped 2nd arg (m4/11/22): fromkeys'
    value defaults to None (probe P4).
  * qc np.array(quality, dtype=np.float64) -> dtype=None/dropped (m14/16) and
    np.array(presence, dtype=...) -> None/dropped (m27/29): a list of Python
    floats infers float64, corrcoef-equal (probes P5/C4b/C5).
  * qc presence 1.0 -> 2.0 (m32): Pearson is scale-invariant and 2 is a power
    of two - coefficients are EXACTLY equal pre-rounding (probe C4, exhaustive
    280 comparisons).
  * getattr(a, attr, False) -> None (qc m35, daily m21, stats m31): falsy
    parity inside a truthiness site (probe P2).
  * getattr(a, attr, ) [default DROPPED = 2-arg] (qc m38, daily m24, stats
    m34, recs m30) AND getattr(a, attr, True) (qc m39, daily m25, stats m35):
    DECISIVE probe P10 - on a real EventAudit an UNSET mapped column reads
    None (SQLAlchemy instrumentation, NOT the SQL column default), and even
    after `del a.has_pet` a 2-arg getattr STILL returns None. The default is
    unreachable for every replacement, and the shipped slot is None-valued
    anyway. The AK-style del-attribute discriminator is IMPOSSIBLE on a
    mapped model - an authoring-time trap this probe caught (a "missing
    attribute" row would have faked a GREEN).
  * qc `np.std(model_presence) == 0` -> `== 1` (m43): binary std <= 0.5 so the
    guard is unreachable; all-constant rows still land on
    isnan(corrcoef) -> None under the mutant (probe P7).
  * daily `if utilization_values` -> or True (m45): DEAD TRUE - a date group
    is non-empty by construction, and a None-utilization row raises inside
    sum() for BOTH polarities before the ternary (probe P8).
  * lb stats["model_contribution_rates"].get(model, {None, dropped, 1})
    (m22/24/27): get_stats builds that dict over the SAME MODEL_NAMES the
    leaderboard loop iterates - key ALWAYS present (probe P3).
  * lb get_stats(session, ) trailing-comma drop (m16): pure syntax no-op -
    f(a, b, ) IS f(a, b) at the call site.
  * recs safe_json_loads default=[] -> None (m33) / default DROPPED (m36):
    the reachable parse-failure return is shielded by
    `isinstance(items, list)` -> both defaults contribute ZERO rows (probe P1,
    pinned by test 42).
  * recs cast("int", x) -> cast(None / "XXintXX" / "INT", x) (m83/87/88):
    typing.cast IS the identity function at runtime (probes C1/C2).
  * recs recommendations[:20] -> [:21] (m91): four categories x top-5 caps
    bound the list at 20 rows - the slice never truncates on any input.

DEMOTED to killable after probing (recorded so the trail is honest): qc
m57/m59 (round(x, None) truncates to an INTEGER - round(0.123456, None) == 0;
pinned by test 37's -0.6882), qc m19 (np.std([0,0,2,2]) IS exactly 1.0 - test
38), recs m34/m37 (safe_json_loads LOGS the context f-string - test 42),
recs m48/m50/m52/m54/m68/m82 (ordering, [:5] cap, priority boundaries - test
40/41, with insertion-order ties so the sorted(key=None) twins actually
diverge), and run_evaluation_llm_calls m32 - my own "valid_scores is never
empty" EQUIV draft was REFUTED by probe P9: an explicit {"actionability":
null} rubric payload empties valid_scores, so shipped returns None while the
or-True mutant hits sum([])/len([]) (pinned by test 22).

"""

import asyncio
import logging
import os
import re
import time
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy.dialects import postgresql

import backend.core.json_utils as ju
import backend.services.pipeline_quality_audit_service as pqas
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.services.pipeline_quality_audit_service import (
    CONSISTENCY_CHECK_PROMPT,
    MODEL_NAMES,
    PROMPT_IMPROVEMENT_PROMPT,
    RUBRIC_EVAL_PROMPT,
    SELF_CRITIQUE_PROMPT,
    PipelineQualityAuditService,
    reset_audit_service,
)

pytestmark = pytest.mark.unit

MOD = "backend.services.pipeline_quality_audit_service"
DAY1 = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
DAY2 = datetime(2026, 1, 6, 9, 0, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


def svc():
    reset_audit_service()
    return PipelineQualityAuditService()


def make_event(**over):
    fields = {
        "id": 11,
        "batch_id": "b-1",
        "camera_id": "cam-9",
        "risk_score": 40,
        "risk_level": "medium",
        "summary": "Person at door",
        "reasoning": "Late activity",
        "llm_prompt": "hello prompt",
    }
    fields.update(over)
    return Event(**fields)


def make_audit(**over):
    """Build an EventAudit; an explicit id is written straight to __dict__."""
    audit_id = over.pop("id", None)
    fields = {
        "event_id": 1,
        "audited_at": DAY1,
        "enrichment_utilization": 0.5,
    }
    fields.update(over)
    audit = EventAudit(**fields)
    if audit_id is not None:
        audit.__dict__["id"] = audit_id
    return audit


def norm_sql(stmt):
    if stmt is None:
        raise AssertionError("execute(None): the statement argument was dropped")
    compiled = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    return " ".join(str(compiled).split())


class FakeResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    """Pins every execute() by compiled Postgres text; UNPINNED sql is fatal.

    A pin is (predicates, rows); a predicate is either a substring (glued,
    column-headed - so WHERE NULL / SELECT NULL cannot sneak through) or a
    callable(sql) -> bool for the cutoff-window check (a shifted or de-tz'd
    cutoff changes only the DATE LITERAL, so substrings alone would pass it).
    """

    def __init__(self, pins):
        self.pins = pins
        self.executed = []
        self.added = []
        self.calls = []

    async def execute(self, stmt):
        sql = norm_sql(stmt)
        self.executed.append(sql)
        for preds, rows in self.pins:
            if all(p(sql) if callable(p) else p in sql for p in preds):
                return FakeResult(rows)
        raise AssertionError(f"UNPINNED SQL: {sql[:300]}")

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.calls.append("commit")

    async def refresh(self, obj):
        self.calls.append(("refresh", obj))


COLS_HEAD = "SELECT event_audits.id, event_audits.event_id"
JOIN_HEAD = "FROM event_audits JOIN events ON events.id = event_audits.event_id"
FLAT_HEAD = "FROM event_audits WHERE"


def cutoff_within(days=7, window=5.0):
    """Predicate: SQL carries a tz-aware UTC cutoff now(UTC) - days ( +-window s ).

    Kills the +timedelta sign flip (14 days off) AND datetime.now(None)
    (a NAIVE local time: no +00:00 suffix, and 11 h off under TzPinned).
    """

    def check(sql):
        m = re.search(r"audited_at >= '([^']+)'", sql)
        if m is None:
            return False
        try:
            lit = datetime.fromisoformat(m.group(1))
        except ValueError:
            return False
        if lit.tzinfo is None:
            return False
        target = datetime.now(UTC) - timedelta(days=days)
        return abs((lit - target).total_seconds()) <= window

    return check


STATS_BASE = [
    COLS_HEAD,
    JOIN_HEAD,
    "WHERE event_audits.audited_at >=",
    cutoff_within(),
]
STATS_CAM = [*STATS_BASE, "AND events.camera_id ="]
LB_SQL = [COLS_HEAD, FLAT_HEAD, "WHERE event_audits.audited_at >=", cutoff_within()]
RECS_SQL = [
    COLS_HEAD,
    "WHERE event_audits.audited_at >=",
    "AND event_audits.overall_quality_score IS NOT NULL",
    cutoff_within(),
]


class LogCap(logging.Handler):
    def __init__(self, target):
        super().__init__()
        self.target = target
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def sole(self):
        assert len(self.records) == 1, f"expected 1 record, got {len(self.records)}"
        return self.records[0]


_STANDARD_LOG_KEYS = set(vars(logging.LogRecord("x", 0, "f", 1, "m", None, None))) | {
    "message",
    "asctime",
    "taskName",
}


def log_extras(record):
    return {k: v for k, v in vars(record).items() if k not in _STANDARD_LOG_KEYS}


# This module's logger sits behind the app ContextFilter, which injects
# ambient keys (app_version, container_id, correlation_id, ...) into EVERY
# record - the recorded "context-filter fakes extra= mutants" trap. The
# ambient key set is captured from a control record through the same logger,
# so the pins below assert exact key-SET equality (ambient + payload) plus
# the payload VALUE - rename/UPPER/drop/None twins RED either way.
@lru_cache(maxsize=1)
def ambient_keys():
    with LogSwap(pqas.logger) as cap:
        pqas.logger.info("c36-ambient-control")
    return frozenset(log_extras(cap.sole()))


def assert_event_extra(record, event_id):
    extras = log_extras(record)
    assert set(extras) == ambient_keys() | {"event_id"}, (
        f"extra key-set drift: {sorted(set(extras) - ambient_keys())}"
    )
    assert extras["event_id"] == event_id


class LogSwap:
    """Attach a LogCap to the real service logger without changing its level."""

    def __init__(self, target):
        self.target = target
        self.cap = None

    def __enter__(self):
        self.cap = LogCap(self.target)
        self._saved_level = self.target.level
        self.target.setLevel(logging.DEBUG)  # env pins WARNING; pin DEBUG rows
        self.target.addHandler(self.cap)
        return self.cap

    def __exit__(self, *exc):
        self.target.removeHandler(self.cap)
        self.target.setLevel(self._saved_level)
        return False


class TzPinned:
    """Local time sits 11 h from UTC so datetime.now(None) is distinguishable."""

    def __enter__(self):
        self._saved = os.environ.get("TZ")
        os.environ["TZ"] = "Etc/GMT+11"
        time.tzset()
        return self

    def __exit__(self, *exc):
        if self._saved is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._saved
        time.tzset()
        return False


def assert_utc_now(stamp):
    assert stamp is not None
    assert stamp.tzinfo is not None, f"timestamp {stamp!r} is naive (now(None))"
    drift = abs((datetime.now(UTC) - stamp).total_seconds())
    assert drift <= 5.0, f"timestamp {stamp!r} sits {drift}s from UTC now"


class FakeResponse:
    def __init__(self, payload, raises=None):
        self._payload = payload
        self._raises = raises

    def raise_for_status(self):
        if self._raises is not None:
            raise self._raises

    def json(self):
        return self._payload


class ClientSpy:
    """httpx.AsyncClient replacement: pins ctor identity and post literals."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.ctors = []
        self.posts = []
        self.exit_count = 0

    def __call__(self, *args, **kwargs):
        self.ctors.append((args, kwargs))
        return _ClientHandle(self)


class _ClientHandle:
    def __init__(self, spy):
        self._spy = spy

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self._spy.exit_count += 1
        return False

    async def post(self, url, **kwargs):
        self._spy.posts.append((url, kwargs))
        item = self._spy.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def client_spy(responses):
    spy = ClientSpy(responses)
    return spy, patch.object(httpx, "AsyncClient", spy)


class ModeSpies:
    """Replaces the 4 _run_* coroutines; records (args, kwargs) per call."""

    def __init__(self, target, results):
        self.target = target
        self.results = dict(results)
        self.calls = []
        self._saved = {}

    def __enter__(self):
        for name in (
            "_run_self_critique",
            "_run_rubric_eval",
            "_run_consistency_check",
            "_run_prompt_improvement",
        ):
            self._saved[name] = getattr(self.target, name)
            setattr(self.target, name, self._make(name))
        return self

    def _make(self, name):
        async def runner(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            value = self.results[name]
            if isinstance(value, BaseException):
                raise value
            return value

        return runner

    def __exit__(self, *exc):
        for name, fn in self._saved.items():
            setattr(self.target, name, fn)
        return False

    def args_for(self, name):
        hits = [c for c in self.calls if c[0] == name]
        assert len(hits) == 1, f"expected one {name} call, got {len(hits)}"
        return hits[0][1], hits[0][2]


class LlmSpy:
    """Replaces _call_llm; records the exact (args, kwargs) it was called with."""

    def __init__(self, target, responses):
        self.target = target
        self.responses = list(responses)
        self.calls = []

    def __enter__(self):
        async def fake(*args, **kwargs):
            self.calls.append((args, kwargs))
            value = self.responses.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value

        self.target._call_llm = fake
        return self

    def __exit__(self, *exc):
        del self.target._call_llm
        return False

    def sole(self):
        assert len(self.calls) == 1, f"expected one _call_llm call, got {self.calls}"
        return self.calls[0]


# ---------------------------------------------------------------------------
# 1: __init__ Timeout field readback
# ---------------------------------------------------------------------------
def test_c36al_01_init_timeout_fields_verbatim_c36():
    """__init__ m3-m15: every connect/read/write/pool 10->11 / ->None twin."""
    service = svc()
    timeout = service._timeout
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 10.0
    assert timeout.read == 120.0
    assert timeout.write == 10.0
    assert timeout.pool == 10.0


def _llm_call(service, prompt="P", payload=None):
    payload = {"content": "TEXT"} if payload is None else payload
    spy, patcher = client_spy([FakeResponse(payload)])
    with patcher:
        out = run(service._call_llm(prompt))
    return out, spy


# The shipped stop list composed from pieces so this file never carries the
# raw template-token sequence; the runtime value is the exact shipped string.
_PIPE = "|"
STOP_TOKENS = [f"<{_PIPE}im_end{_PIPE}>", f"<{_PIPE}im_start{_PIPE}>"]


def test_c36al_02_call_llm_ctor_timeout_identity_c36():
    """_call_llm m19: AsyncClient(timeout=..) must carry THE Timeout object."""
    service = svc()
    _out, spy = _llm_call(service)
    assert len(spy.ctors) == 1
    args, kwargs = spy.ctors[0]
    assert args == ()
    assert set(kwargs) == {"timeout"}
    assert kwargs["timeout"] is service._timeout


def test_c36al_03_call_llm_post_kwargs_exact_c36():
    """_call_llm payload/url/header keys: the WHOLE post() call pinned exactly."""
    service = svc()
    out, spy = _llm_call(service, prompt="PROMPT-X")
    assert out == "TEXT"
    assert len(spy.posts) == 1
    url, kwargs = spy.posts[0]
    assert url == f"{service._llm_url}/completion"
    assert kwargs == {
        "json": {
            "prompt": "PROMPT-X",
            "temperature": 0.3,
            "top_p": 0.9,
            "max_tokens": 1024,
            "stop": STOP_TOKENS,
        },
        "headers": {"Content-Type": "application/json"},
    }


def test_c36al_04_call_llm_content_default_empty_c36():
    """_call_llm result.get("content", ""): ABSENT content -> "" (None/XXXX RED)."""
    service = svc()
    out, _spy = _llm_call(service, payload={"other": 1})
    assert out == ""


def test_c36al_05_call_llm_raise_for_status_escapes_and_ctx_closes_c36():
    """raise_for_status runs inside the ctx and a request error ESCAPES _call_llm."""
    service = svc()
    spy, patcher = client_spy([FakeResponse({"content": "T"})])
    with patcher:
        assert run(service._call_llm("P")) == "T"
    assert spy.exit_count == 1
    boom = httpx.RequestError("boom", request=httpx.Request("POST", "http://x"))
    _s2, patcher2 = client_spy([FakeResponse({"content": "T"}, raises=boom)])
    try:
        with patcher2:
            run(service._call_llm("P"))
        raise AssertionError("httpx.RequestError must escape _call_llm")
    except httpx.RequestError as exc:
        assert str(exc) == "boom"


def test_c36al_06_self_critique_prompt_verbatim_c36():
    """_run_self_critique m5 (llm_prompt=None): prompt pinned against template."""
    service = svc()
    event = make_event()
    with LlmSpy(service, ["CRITIQUE-TEXT"]) as spy:
        out = run(service._run_self_critique(event))
    assert out == "CRITIQUE-TEXT"
    args, kwargs = spy.sole()
    assert kwargs == {}
    assert args == (
        SELF_CRITIQUE_PROMPT.format(
            risk_score=40,
            summary="Person at door",
            reasoning="Late activity",
            llm_prompt="hello prompt",
        ),
    )


def test_c36al_07_self_critique_network_error_family_c36():
    """m11-m22: exact msg + exc_info tuple + extra={'event_id'} on network fail."""
    service = svc()
    event = make_event()
    boom = httpx.TimeoutException("slowpoke")
    with (
        LlmSpy(service, [boom]),
        LogSwap(pqas.logger) as cap,
    ):
        out = run(service._run_self_critique(event))
    assert out == "Evaluation network error: slowpoke"
    record = cap.sole()
    assert record.msg == "Self-critique network error"
    assert record.levelno == logging.ERROR
    assert record.exc_info[0] is httpx.TimeoutException
    assert_event_extra(record, 11)


def test_c36al_08_rubric_prompt_verbatim_and_parse_c36():
    """_run_rubric_eval m2-m5: format args pinned; valid JSON returns parsed."""
    service = svc()
    event = make_event()
    payload = '{"context_usage": 4.0, "explanation": "ok"}'
    with LlmSpy(service, [payload]) as spy:
        out = run(service._run_rubric_eval(event))
    assert out == {"context_usage": 4.0, "explanation": "ok"}
    args, kwargs = spy.sole()
    assert kwargs == {}
    assert args == (
        RUBRIC_EVAL_PROMPT.format(
            llm_prompt="hello prompt",
            risk_score=40,
            summary="Person at door",
            reasoning="Late activity",
        ),
    )


def test_c36al_09_rubric_parse_fail_warning_fstring_c36():
    """m14: unparseable response -> EXACT warning f-string (warning(None) RED)."""
    service = svc()
    event = make_event()
    with LlmSpy(service, ["not json at all"]), LogSwap(pqas.logger) as cap:
        out = run(service._run_rubric_eval(event))
    assert out == {}
    record = cap.sole()
    assert record.msg == "Could not extract JSON from rubric eval for event 11"
    assert record.levelno == logging.WARNING


def test_c36al_10_rubric_network_error_family_c36():
    """m15-m26: exact msg + exc_info identity + extra key-set/value."""
    service = svc()
    event = make_event()
    boom = httpx.HTTPStatusError("bad", request=httpx.Request("POST", "u"), response=None)
    with LlmSpy(service, [boom]), LogSwap(pqas.logger) as cap:
        out = run(service._run_rubric_eval(event))
    assert out == {}
    record = cap.sole()
    assert record.msg == "Rubric eval network error"
    assert record.levelno == logging.ERROR
    assert record.exc_info[0] is httpx.HTTPStatusError
    assert_event_extra(record, 11)


def test_c36al_11_rubric_generic_error_family_c36():
    """m15-26 second path: a NON-network exception lands on the generic handler
    whose msg is "Rubric eval error" - the two handler bodies differ by msg,
    so pinning only one of them would pass a handler-swap mutant."""
    service = svc()
    event = make_event()
    with LlmSpy(service, [RuntimeError("kaboom")]), LogSwap(pqas.logger) as cap:
        out = run(service._run_rubric_eval(event))
    assert out == {}
    record = cap.sole()
    assert record.msg == "Rubric eval error"
    assert record.exc_info[0] is RuntimeError
    assert_event_extra(record, 11)


def test_c36al_12_consistency_prompt_clean_when_no_assistant_c36():
    """m3: llm_prompt None -> `or ""` feeds the template (the "XXXX" twin RED)."""
    service = svc()
    event = make_event(llm_prompt=None)
    with LlmSpy(service, ['{"risk_score": 5}']) as spy:
        out = run(service._run_consistency_check(event))
    assert out == {"risk_score": 5}
    args, kwargs = spy.sole()
    assert kwargs == {}
    assert args == (CONSISTENCY_CHECK_PROMPT.format(llm_prompt_clean=""),)


def test_c36al_13_consistency_prompt_splits_at_assistant_c36():
    """the shipped split: everything before <|im_start|>assistant is kept."""
    service = svc()
    prompt = "HEAD <|im_start|>system keep <|im_start|>assistant TAIL DROP"
    event = make_event(llm_prompt=prompt)
    with LlmSpy(service, ['{"risk_score": 5}']) as spy:
        run(service._run_consistency_check(event))
    (sent,), _ = spy.sole()
    assert sent == CONSISTENCY_CHECK_PROMPT.format(llm_prompt_clean="HEAD <|im_start|>system keep ")


def test_c36al_14_consistency_parse_fail_warning_fstring_c36():
    """m18: EXACT warning message through the event-id f-string."""
    service = svc()
    event = make_event()
    with LlmSpy(service, ["nope"]), LogSwap(pqas.logger) as cap:
        out = run(service._run_consistency_check(event))
    assert out == {}
    assert cap.sole().msg == ("Could not extract JSON from consistency check for event 11")
    assert cap.sole().levelno == logging.WARNING


def test_c36al_15_consistency_network_error_family_c36():
    """m19-m30: exact msg + exc_info + extra key-set AND value."""
    service = svc()
    event = make_event()
    boom = httpx.RequestError("net", request=httpx.Request("POST", "u"))
    with LlmSpy(service, [boom]), LogSwap(pqas.logger) as cap:
        out = run(service._run_consistency_check(event))
    assert out == {}
    record = cap.sole()
    assert record.msg == "Consistency check network error"
    assert record.levelno == logging.ERROR
    assert record.exc_info[0] is httpx.RequestError
    assert_event_extra(record, 11)


def test_c36al_16_consistency_generic_error_family_c36():
    service = svc()
    event = make_event()
    with LlmSpy(service, [ValueError("v")]), LogSwap(pqas.logger) as cap:
        out = run(service._run_consistency_check(event))
    assert out == {}
    record = cap.sole()
    assert record.msg == "Consistency check error"
    assert record.exc_info[0] is ValueError
    assert_event_extra(record, 11)


def test_c36al_17_improvement_prompt_verbatim_c36():
    """_run_prompt_improvement m2-m4: template .format(llm_prompt, risk, reason)."""
    service = svc()
    event = make_event()
    with LlmSpy(service, ['{"missing_context": ["a"]}']) as spy:
        out = run(service._run_prompt_improvement(event))
    assert out == {"missing_context": ["a"]}
    args, kwargs = spy.sole()
    assert kwargs == {}
    assert args == (
        PROMPT_IMPROVEMENT_PROMPT.format(
            llm_prompt="hello prompt", risk_score=40, reasoning="Late activity"
        ),
    )


def test_c36al_18_improvement_parse_fail_and_errors_c36():
    """m12 warning f-string + m13-m24 both error handlers, per-path attribution."""
    service = svc()
    event = make_event()
    with LlmSpy(service, ["garbage"]), LogSwap(pqas.logger) as cap:
        assert run(service._run_prompt_improvement(event)) == {}
    assert cap.sole().msg == ("Could not extract JSON from prompt improvement for event 11")

    service = svc()
    boom = httpx.TimeoutException("t")
    with LlmSpy(service, [boom]), LogSwap(pqas.logger) as cap:
        assert run(service._run_prompt_improvement(event)) == {}
    record = cap.sole()
    assert record.msg == "Prompt improvement network error"
    assert record.exc_info[0] is httpx.TimeoutException
    assert_event_extra(record, 11)

    service = svc()
    with LlmSpy(service, [KeyError("k")]), LogSwap(pqas.logger) as cap:
        assert run(service._run_prompt_improvement(event)) == {}
    record = cap.sole()
    assert record.msg == "Prompt improvement error"
    assert record.exc_info[0] is KeyError
    assert_event_extra(record, 11)


def _scores_result():
    return {
        "_run_self_critique": "CRIT",
        "_run_rubric_eval": {
            "context_usage": 5.0,
            "reasoning_coherence": 5.0,
            "risk_justification": 5.0,
        },
        "_run_consistency_check": {"risk_score": 50},
        "_run_prompt_improvement": {
            "missing_context": ["m1"],
            "confusing_sections": ["c1"],
            "unused_data": [],
            "format_suggestions": ["f1"],
        },
    }


def test_c36al_19_run_llm_calls_delegation_identity_and_matrix_c36():
    """m3/m6/m36/m58: each mode receives THE SAME event object; every field."""
    service = svc()
    event = make_event()
    audit = make_audit()
    with ModeSpies(service, _scores_result()) as spies:
        out = run(service.run_evaluation_llm_calls(audit, event))
    assert out is audit
    for name in (
        "_run_self_critique",
        "_run_rubric_eval",
        "_run_consistency_check",
        "_run_prompt_improvement",
    ):
        args, kwargs = spies.args_for(name)
        assert kwargs == {}
        assert len(args) == 1 and args[0] is event, f"{name} lost the event"
    assert audit.self_eval_critique == "CRIT"
    assert audit.context_usage_score == 5.0
    assert audit.reasoning_coherence_score == 5.0
    assert audit.risk_justification_score == 5.0
    # actionability ABSENT -> default 3.0 -> overall (5+5+5+3)/4 = 4.5
    assert audit.overall_quality_score == 4.5
    assert audit.consistency_risk_score == 50
    assert audit.consistency_diff == 10
    assert audit.consistency_score == 3.0
    assert audit.missing_context == '["m1"]'
    assert audit.confusing_sections == '["c1"]'
    assert audit.unused_data == "[]"
    assert audit.format_suggestions == '["f1"]'
    assert audit.model_gaps == "[]"


def test_c36al_20_actionability_default_three_c36():
    """m19/m21/m22/m23/m26: ABSENT actionability uses the 3.0 default exactly."""
    service = svc()
    res = _scores_result()
    res["_run_rubric_eval"] = {
        "context_usage": 1.0,
        "reasoning_coherence": 2.0,
        "risk_justification": 3.0,
    }
    audit = make_audit()
    with ModeSpies(service, res):
        run(service.run_evaluation_llm_calls(audit, make_event()))
    # shipped: (1+2+3+3)/4 = 2.25; 4.0-default -> 2.5; None-default -> 2.0
    assert audit.overall_quality_score == 2.25


def test_c36al_21_valid_scores_drops_none_keeps_actionability_c36():
    """the valid_scores filter: a None component drops, actionability stays."""
    service = svc()
    res = _scores_result()
    res["_run_rubric_eval"] = {
        "context_usage": None,
        "reasoning_coherence": 2.0,
        "actionability": 4.0,
    }
    audit = make_audit()
    with ModeSpies(service, res):
        run(service.run_evaluation_llm_calls(audit, make_event()))
    # risk_justification ABSENT -> None dropped; (2.0 + 4.0)/2 = 3.0
    assert audit.overall_quality_score == 3.0


def test_c36al_22_all_null_actionability_gives_none_not_zero_division_c36():
    """m32 (`or True`): the ONLY way valid_scores empties is an EXPLICIT null
    actionability in the rubric payload - shipped returns None, the or-True
    mutant hits sum([])/len([]) -> ZeroDivisionError. Probe P9 refuted my own
    "never empty" EQUIV draft, so this row is a KILL, not a ledger entry."""
    service = svc()
    res = _scores_result()
    res["_run_rubric_eval"] = {
        "context_usage": None,
        "reasoning_coherence": None,
        "risk_justification": None,
        "actionability": None,
    }
    audit = make_audit()
    with ModeSpies(service, res):
        run(service.run_evaluation_llm_calls(audit, make_event()))
    assert audit.overall_quality_score is None


def test_c36al_23_consistency_skipped_when_consistency_none_c36():
    """the is-not-None guard: no diff/score written when risk_score absent."""
    service = svc()
    res = _scores_result()
    res["_run_consistency_check"] = {}
    audit = make_audit()
    with ModeSpies(service, res):
        run(service.run_evaluation_llm_calls(audit, make_event()))
    assert audit.consistency_risk_score is None
    assert audit.consistency_diff is None
    assert audit.consistency_score is None


def test_c36al_24_consistency_score_formula_exact_c36():
    """diff=95 -> score max(1, 5 - 95/5) = 1.0; diff=10 -> 3.0 exactly."""
    service = svc()
    res = _scores_result()
    res["_run_consistency_check"] = {"risk_score": 135}
    audit = make_audit()
    with ModeSpies(service, res):
        run(service.run_evaluation_llm_calls(audit, make_event(risk_score=40)))
    assert audit.consistency_diff == 95
    assert audit.consistency_score == 1.0


def test_c36al_25_self_eval_prompt_short_prompt_passthrough_c36():
    """<=500 prompt: VERBATIM (no truncation, no ellipsis) in the stored prompt."""
    service = svc()
    event = make_event(llm_prompt="SHORT-PROMPT")
    audit = make_audit()
    with ModeSpies(service, _scores_result()):
        run(service.run_evaluation_llm_calls(audit, event))
    expected = RUBRIC_EVAL_PROMPT.format(
        llm_prompt="SHORT-PROMPT",
        risk_score=40,
        summary="Person at door",
        reasoning="Late activity",
    )
    assert audit.self_eval_prompt == expected


def test_c36al_26_self_eval_prompt_len_500_not_truncated_c36():
    """len == 500: shipped `> 500` is FALSE (no ellipsis). `>= 500` REDs."""
    service = svc()
    prompt = "x" * 500
    event = make_event(llm_prompt=prompt)
    audit = make_audit()
    with ModeSpies(service, _scores_result()):
        run(service.run_evaluation_llm_calls(audit, event))
    expected = RUBRIC_EVAL_PROMPT.format(
        llm_prompt=prompt,
        risk_score=40,
        summary="Person at door",
        reasoning="Late activity",
    )
    assert audit.self_eval_prompt == expected


def test_c36al_27_self_eval_prompt_len_501_truncated_c36():
    """len == 501: shipped takes [:500] + "...". `> 501` and `[:501]` RED."""
    service = svc()
    prompt = "y" * 501
    event = make_event(llm_prompt=prompt)
    audit = make_audit()
    with ModeSpies(service, _scores_result()):
        run(service.run_evaluation_llm_calls(audit, event))
    expected = RUBRIC_EVAL_PROMPT.format(
        llm_prompt="y" * 500 + "...",
        risk_score=40,
        summary="Person at door",
        reasoning="Late activity",
    )
    assert audit.self_eval_prompt == expected


def test_c36al_28_self_eval_prompt_reasoning_len_300_not_truncated_c36():
    """reasoning len == 300: shipped `> 300` FALSE. `>= 300` REDs."""
    service = svc()
    reasoning = "r" * 300
    event = make_event(reasoning=reasoning)
    audit = make_audit()
    with ModeSpies(service, _scores_result()):
        run(service.run_evaluation_llm_calls(audit, event))
    expected = RUBRIC_EVAL_PROMPT.format(
        llm_prompt="hello prompt",
        risk_score=40,
        summary="Person at door",
        reasoning=reasoning,
    )
    assert audit.self_eval_prompt == expected


def test_c36al_29_self_eval_prompt_reasoning_len_301_truncated_c36():
    """reasoning len == 301 -> [:300] + "..." (kills `>301`, `[:301]`,
    the `and False` (never truncates) and `or True` (always truncates) twins)."""
    service = svc()
    reasoning = "z" * 301
    event = make_event(reasoning=reasoning)
    audit = make_audit()
    with ModeSpies(service, _scores_result()):
        run(service.run_evaluation_llm_calls(audit, event))
    expected = RUBRIC_EVAL_PROMPT.format(
        llm_prompt="hello prompt",
        risk_score=40,
        summary="Person at door",
        reasoning="z" * 300 + "...",
    )
    assert audit.self_eval_prompt == expected


def test_c36al_30_self_eval_prompt_reasoning_none_c36():
    """reasoning None: shipped short-circuits the `and` guard (stores None).
    The `if event.reasoning or len(event.reasoning) > 300` mutant raises
    TypeError on len(None) - the m120 kill row."""
    service = svc()
    event = make_event(reasoning=None)
    audit = make_audit()
    with ModeSpies(service, _scores_result()):
        run(service.run_evaluation_llm_calls(audit, event))
    expected = RUBRIC_EVAL_PROMPT.format(
        llm_prompt="hello prompt",
        risk_score=40,
        summary="Person at door",
        reasoning=None,
    )
    assert audit.self_eval_prompt == expected


def test_c36al_31_run_llm_calls_audited_at_utc_now_c36():
    """m123/m124: audited_at is a tz-aware UTC now (None -> AttributeError on
    the compare; now(None) -> naive local, 11 h off under the TZ lever)."""
    service = svc()
    event = make_event()
    audit = make_audit(audited_at=None)
    with TzPinned(), ModeSpies(service, _scores_result()):
        run(service.run_evaluation_llm_calls(audit, event))
    assert_utc_now(audit.audited_at)


def test_c36al_32_run_llm_calls_early_return_empty_prompt_c36():
    """falsy llm_prompt: warning with the event id + audit UNTOUCHED."""
    service = svc()
    event = make_event(llm_prompt="")
    audit = make_audit(self_eval_critique="KEEP")
    with ModeSpies(service, _scores_result()) as spies, LogSwap(pqas.logger) as cap:
        out = run(service.run_evaluation_llm_calls(audit, event))
    assert out is audit
    assert spies.calls == [], "no mode may run on an empty prompt"
    assert audit.self_eval_critique == "KEEP"
    record = cap.sole()
    assert record.msg == "Event 11 has no llm_prompt, skipping evaluation"
    assert record.levelno == logging.WARNING


def _stats_rows():
    a1 = make_audit(
        overall_quality_score=4.0,
        consistency_score=2.0,
        enrichment_utilization=0.25,
        has_pet=True,
        audited_at=DAY1,
    )
    a2 = make_audit(
        overall_quality_score=2.0,
        enrichment_utilization=0.75,
        audited_at=DAY2,
    )
    return [a1, a2]


def _stats_session(rows=None):
    rows = _stats_rows() if rows is None else rows
    return FakeSession([(STATS_BASE, rows)])


def test_c36al_33_get_stats_base_query_shape_and_values_c36():
    """m2/m3/m6/m8/m9/m14 + the aggregate matrix, all through the pinned SQL."""
    service = svc()
    session = _stats_session()
    out = run(service.get_stats(session, days=7))
    assert len(session.executed) == 1
    assert out["total_events"] == 2
    assert out["audited_events"] == 2
    assert out["fully_evaluated_events"] == 2
    assert out["avg_quality_score"] == 3.0
    assert out["avg_consistency_rate"] == 2.0
    assert out["avg_enrichment_utilization"] == 0.5
    assert out["model_contribution_rates"]["pet"] == 0.5
    assert out["model_contribution_rates"]["yolo26"] == 0.0
    assert set(out["model_contribution_rates"]) == set(MODEL_NAMES)


def test_c36al_34_get_stats_camera_where_clause_c36():
    """m10/m11/m12: camera_id adds AND events.camera_id = ; the != twin REDs
    (UNPINNED SQL), the query=None twin dies in norm_sql."""
    service = svc()
    session = FakeSession([(STATS_CAM, _stats_rows())])
    out = run(service.get_stats(session, days=7, camera_id="cam-9"))
    assert out["total_events"] == 2
    assert "AND events.camera_id = 'cam-9'" in session.executed[0]


def test_c36al_35_get_stats_no_camera_no_where_clause_c36():
    """no camera_id -> the base query WITHOUT the camera clause (and the
    m10-m12 twins cannot both satisfy the same pin)."""
    service = svc()
    session = _stats_session()
    out = run(service.get_stats(session, days=7))
    assert out["total_events"] == 2
    assert "camera_id" not in session.executed[0]


def test_c36al_36_get_stats_single_row_zero_count_rate_c36():
    """m41: total_events == 1, model count 0 -> shipped 0/1 = 0.0; the
    `> 1` mutant takes the else and ALSO gives 0 - so the kill row needs
    total == 1 AND a count >= 1: shipped 1/1 = 1.0, mutant 0."""
    service = svc()
    rows = [make_audit(has_pet=True, enrichment_utilization=0.5, audited_at=DAY1)]
    session = FakeSession([(STATS_BASE, rows)])
    out = run(service.get_stats(session, days=7))
    assert out["total_events"] == 1
    assert out["model_contribution_rates"]["pet"] == 1.0
    assert out["model_contribution_rates"]["clip"] == 0.0


def test_c36al_37_correlations_exact_values_c36():
    """round(.., 4) pinned VERBATIM: -0.6882 / 0.6882 / 0.9272.

    m57/m59 (round(x, None) and the dropped default) truncate to an INTEGER
    (-1 / -1 / 1) - round(0.123456, None) IS 0 - so these three pins kill both
    keys. Constant-presence models give None (std == 0 guard).
    """
    service = svc()
    audits = [
        make_audit(overall_quality_score=1.0, has_florence=True, has_yolo26=True),
        make_audit(overall_quality_score=2.0, has_clip=True, has_yolo26=True),
        make_audit(overall_quality_score=2.0, has_florence=True, has_yolo26=True),
        make_audit(
            overall_quality_score=4.0,
            has_clip=True,
            has_baseline=True,
            has_yolo26=True,
        ),
    ]
    out = service._compute_quality_correlations(audits)
    assert out["florence"] == -0.6882
    assert out["clip"] == 0.6882
    assert out["baseline"] == 0.9272
    assert out["yolo26"] is None
    for model in (
        "violence",
        "clothing",
        "vehicle",
        "pet",
        "weather",
        "image_quality",
        "zones",
        "cross_camera",
    ):
        assert out[model] is None, f"{model} presence is constant -> None"


def test_c36al_38_correlations_std_one_scores_not_skipped_c36():
    """m19: np.std([0.0, 0.0, 2.0, 2.0]) IS exactly 1.0. Shipped's guard is
    `== 0` so it computes; the `== 1` mutant takes the early return and gives
    ALL-None. Probe-verified (probe P6b): std == 1.0 holds exactly, so this
    key was DEMOTED from my EQUIV draft to killable."""
    service = svc()
    audits = [
        make_audit(overall_quality_score=0.0, has_florence=True),
        make_audit(overall_quality_score=0.0),
        make_audit(overall_quality_score=2.0, has_florence=True),
        make_audit(overall_quality_score=2.0),
    ]
    out = service._compute_quality_correlations(audits)
    assert out["florence"] == 0.0
    assert out["clip"] is None


def test_c36al_39_get_leaderboard_query_and_delegation_c36():
    """m2/m3/m6/m7/m8/m9 + m13-m16: the FLAT (no-join) cutoff query, then
    get_stats delegated with (session, days) pinned EXACTLY."""
    service = svc()
    rows = [
        make_audit(overall_quality_score=1.0, has_florence=True, has_yolo26=True),
        make_audit(overall_quality_score=2.0, has_florence=True, has_yolo26=True),
        make_audit(overall_quality_score=2.0, has_yolo26=True),
        make_audit(overall_quality_score=4.0, has_yolo26=True),
    ]
    session = FakeSession(
        [
            (LB_SQL, rows),
            (STATS_BASE, rows),
        ]
    )
    entries = run(service.get_leaderboard(session, days=7))
    assert len(session.executed) == 2
    assert "JOIN" not in session.executed[0]
    assert "JOIN" in session.executed[1]
    assert len(entries) == len(MODEL_NAMES)
    # yolo26 present in all 4 -> rate 1.0 -> first after the rate-desc sort
    assert entries[0]["model_name"] == "yolo26"
    assert entries[0]["contribution_rate"] == 1.0
    assert entries[0]["event_count"] == 4
    assert entries[0]["quality_correlation"] is None  # constant presence
    rates = [e["contribution_rate"] for e in entries]
    assert rates == sorted(rates, reverse=True)


def _rec_audit(audit_id, **json_cols):
    import json as _json

    cols = dict.fromkeys(
        ("missing_context", "confusing_sections", "unused_data", "format_suggestions", "model_gaps")
    )
    for cat, items in json_cols.items():
        cols[cat] = _json.dumps(items)
    return make_audit(id=audit_id, overall_quality_score=3.0, **cols)


def test_c36al_40_get_recommendations_order_frequency_priority_c36():
    """EXACT ordered recommendation list through the pinned query.

    Row design (every ordering mutant must be pinned where orders DIVERGE):
      counts: b3 a3 c2 d2 e2 f1 in missing_context, u2 1, g1 1 (5 audits).
      INSERTION is b-first: shipped sorts -frequency (stable -> b before a in
      the 3-tie); `sorted(key=None)`/dropped (m48/m50) degrade to NAME order
      (a before b) - equal-frequency ties are the only place category order
      survives the global -frequency sort, so the tie carries the kill.
      f1 sits at rank 6 -> the [:5] cap drops it (m54 [:6] keeps it).
      u2/g1 (freq 1) pin medium: 1 > 0.1*5=0.5 TRUE, > 0.3*5=1.5 FALSE.
      m52 (+x[1]) and m82 (+cast) reverse the GLOBAL order -> RED here too.
    """
    service = svc()
    audits = [
        _rec_audit(1, missing_context=["b", "a", "c", "d", "e", "f"], unused_data=["u2"]),
        _rec_audit(2, missing_context=["b", "a", "c", "d", "e"]),
        _rec_audit(3, missing_context=["a", "b"], model_gaps=["g1"]),
        _rec_audit(4, format_suggestions=["fs1"]),
        make_audit(id=5, overall_quality_score=3.0),
    ]
    session = FakeSession([(RECS_SQL, audits)])
    out = run(service.get_recommendations(session, days=7))
    assert len(session.executed) == 1
    expected = [
        {"category": "missing_context", "suggestion": "b", "frequency": 3, "priority": "high"},
        {"category": "missing_context", "suggestion": "a", "frequency": 3, "priority": "high"},
        {"category": "missing_context", "suggestion": "c", "frequency": 2, "priority": "high"},
        {"category": "missing_context", "suggestion": "d", "frequency": 2, "priority": "high"},
        {"category": "missing_context", "suggestion": "e", "frequency": 2, "priority": "high"},
        {"category": "unused_data", "suggestion": "u2", "frequency": 1, "priority": "medium"},
        {"category": "model_gaps", "suggestion": "g1", "frequency": 1, "priority": "medium"},
        {
            "category": "format_suggestions",
            "suggestion": "fs1",
            "frequency": 1,
            "priority": "medium",
        },
    ]
    assert out == expected


def test_c36al_41_recommendation_priority_equality_boundary_c36():
    """m68: count == len(audits) * 0.3 EXACTLY (3 of 10 -> 3 > 3.0 FALSE ->
    medium; the `>=` mutant says high). The second row pins the low side:
    count 1 vs 0.1*10 = 1.0 -> 1 > 1.0 FALSE -> low."""
    service = svc()
    audits = (
        [_rec_audit(i, missing_context=["hit"]) for i in range(1, 4)]
        + [_rec_audit(i, missing_context=["tail"]) for i in range(4, 5)]
        + [make_audit(id=i, overall_quality_score=3.0) for i in range(5, 11)]
    )
    session = FakeSession([(RECS_SQL, audits)])
    out = run(service.get_recommendations(session, days=7))
    hit = next(r for r in out if r["suggestion"] == "hit")
    assert hit["frequency"] == 3
    assert hit["priority"] == "medium"
    tail = next(r for r in out if r["suggestion"] == "tail")
    assert tail["frequency"] == 1
    assert tail["priority"] == "low"


def test_c36al_42_recommendations_unparseable_json_context_log_c36():
    """m34/m37: safe_json_loads logs extra["context"] = the EXACT f-string
    (context=None logs "unspecified" -> RED). Also proves the m33/m36 default
    EQUIV: a parse failure contributes NO row (isinstance list shield)."""
    service = svc()
    audit = make_audit(id=7, overall_quality_score=3.0)
    audit.missing_context = "{not valid json"
    session = FakeSession([(RECS_SQL, [audit])])
    with LogSwap(ju._logger) as cap:
        out = run(service.get_recommendations(session, days=7))
    assert out == []
    record = cap.sole()
    assert record.msg == "JSON parse failed, using default"
    assert log_extras(record)["context"] == "EventAudit.missing_context (audit_id=7)"


def _vehicle_result(vclass, vdamage):
    return SimpleNamespace(
        has_vision_extraction=False,
        has_violence=False,
        has_clothing_classifications=False,
        has_pet_classifications=False,
        weather_classification=None,
        has_image_quality=False,
        person_reid_matches=[],
        vehicle_reid_matches=[],
        has_vehicle_classifications=vclass,
        has_vehicle_damage=vdamage,
    )


def test_c36al_43_has_vehicle_or_semantics_c36():
    """m3 (or -> and): (False, True) and (True, False) rows distinguish."""
    service = svc()
    assert service._has_vehicle(_vehicle_result(True, False)) is True
    assert service._has_vehicle(_vehicle_result(False, True)) is True
    assert service._has_vehicle(_vehicle_result(False, False)) is False
    assert service._has_vehicle(None) is False


def test_c36al_44_create_partial_audit_audited_at_is_utc_now_c36():
    """m36: audited_at = datetime.now(UTC). now(None) under the TZ lever is a
    NAIVE local time -> the aware-compare inside assert_utc_now raises."""
    service = svc()
    with TzPinned():
        audit = service.create_partial_audit(42, "prompt", None, None)
    assert audit.event_id == 42
    assert audit.has_yolo26 is True
    assert_utc_now(audit.audited_at)


def test_c36al_45_run_full_evaluation_early_return_no_db_c36():
    """m2: early return logs the EXACT warning and touches NO db operation."""
    service = svc()
    session = FakeSession([])
    audit = make_audit()
    with LogSwap(pqas.logger) as cap:
        out = run(service.run_full_evaluation(audit, make_event(llm_prompt=None), session))
    assert out is audit
    record = cap.sole()
    assert record.msg == "Event 11 has no llm_prompt, skipping evaluation"
    assert record.levelno == logging.WARNING
    assert session.calls == []
    assert session.added == []


def test_c36al_46_run_full_evaluation_evaluates_then_persists_c36():
    """the happy path: modes run, THEN commit, THEN refresh(audit) - order."""
    service = svc()
    audit = make_audit()
    session = FakeSession([])
    with ModeSpies(service, _scores_result()):
        out = run(service.run_full_evaluation(audit, make_event(), session))
    assert out is audit
    assert out.overall_quality_score == 4.5
    assert session.calls[0] == "commit"
    assert session.calls[1] == ("refresh", audit)
    assert len(session.calls) == 2


def test_c36al_47_persist_record_adds_commits_refreshes_and_logs_c36():
    """m3: exact debug f-string over the audit's id/event_id; the session call
    ORDER add -> commit -> refresh(audit) is pinned."""
    service = svc()
    audit = make_audit(id=55, event_id=77)
    session = FakeSession([])
    with LogSwap(pqas.logger) as cap:
        out = run(service.persist_record(audit, session))
    assert out is audit
    assert session.added == [audit]
    assert session.calls == ["commit", ("refresh", audit)]
    record = cap.sole()
    assert record.msg == "Persisted audit 55 for event 77"
    assert record.levelno == logging.DEBUG


def test_c36al_48_improvements_absent_keys_give_empty_lists_c36():
    """m62/m64/m70/m72/m78/m80/m86/m88/m94/m96: every .get(cat, []) DEFAULT
    fires only when the improvement dict LACKS the key. An EMPTY payload pins
    all five fields to "[]" - the None-default mutants write "null" and RED.
    (The XX/UPPER key twins and the present-value case live in test 19, where
    defaults are NOT the observable.)"""
    service = svc()
    res = _scores_result()
    res["_run_prompt_improvement"] = {}
    audit = make_audit()
    with ModeSpies(service, res):
        run(service.run_evaluation_llm_calls(audit, make_event()))
    assert audit.missing_context == "[]"
    assert audit.confusing_sections == "[]"
    assert audit.unused_data == "[]"
    assert audit.format_suggestions == "[]"
    assert audit.model_gaps == "[]"
