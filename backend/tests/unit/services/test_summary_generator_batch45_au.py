# TARGET-MODULE: backend.services.summary_generator
"""Battery AU - campaign #45 kill battery for backend/services/summary_generator.py.

Style (proven on AT/AR): every observable an entered branch WRITES is
asserted ([[entered-branch-must-assert-every-observable-it-writes]]); log
extras are pinned BY NAME off REAL LogRecords passed through the REAL
ContextFilter ([[log-context-filter-fakes-extra-kwarg-mutants]] - ambient
keys AUDITED THIS session: the filter injects request_id/correlation_id/
trace_id/span_id/connection_id/task_id/job_id/hostname/container_id/
app_version/environment, and a bare record carries NONE of this battery's
keys, so an extra= drop makes the attribute MISSING and dies; the probe's
summary_type attr came from the probe's own extra=); dropped kwargs die at
the CALL SITE on key-presence in a raw **kwargs capture whose sentinels
are NON-ROUNDTRIPABLE objects the shipped call never refills
([[dropped-kwarg-mutants-needs-call-site-spy]]); message/extra/return
pins are FULL equality, never fragments
([[fragment-count-asserts-pass-xx-mutants]]).

Measured pins THIS session (probes, ENVIRONMENT=test):
- httpx.Timeout(connect=None, read=60.0, write=60.0, pool=None)
  CONSTRUCTS FINE and reads back None -> the timeout-attr twins die on
  ATTRIBUTE EQUALITY, not a raised error: shipped __init__ reads
  (connect=10.0, read=60.0, write=60.0, pool=10.0); timeout=7.5 override
  -> read==write==7.5; the or->and twins yield None at timeout=None.
  m5 (_timeout=None) dies at the AsyncClient call site: shipped passes
  the INSTANCE (identity), m46 passes None, m5 passes None there too.
- datetime.now(None) is NAIVE -> killed by tzinfo is UTC / isoformat
  "+00:00" on every window and generated_at pin.
- datetime.now(UTC) - timedelta(minutes=None) RAISES TypeError at the
  window computation -> pytest.raises pins keep the m14/m31 twins red.
- strftime("%i:%m %p") of 13:05 -> "'%i:05 PM'" (literal %i!), strftime
  ("%I:%M %P") -> "01:05 pm" (lowercase am/pm) -> both die on exact
  string equality of the prompt's "**From:** / **To:**" (or the context
  "timestamp") fields.
- datetime.replace(microsecond-drop trailing-comma) is 2-KWARG:
  microsecond SURVIVES -> daily window_start.microsecond == 0 kills it;
  the microsecond=1 twin dies on the same pin.
- settings ENVIRONMENT=test: ai_vlm_read_timeout=25.0 +
  ai_connect_timeout=10.0; asyncio.timeout(None) is LEGAL -> the
  explicit_timeout twins (None / minus) die on the CAPTURED ARG against
  the live-computed sum (never a literal 35.0 - no env coupling).
- build_summary_prompt is DETERMINISTIC (same call twice), embeds
  "hour"/"day" and the formatted window bounds in the user prompt, and
  the routine_count>0 suffix "\n(1 routine/low-priority detections
  occurred)" is REAL -> the routine_count=1 twin dies on full-text
  equality of the captured system+user prompts.
- re.sub WITHOUT DOTALL lets a multi-line <|im_start|>..\n..<|im_
  end|> wrapper SURVIVE -> think-strip m76 dies on content equality
  ("Visible" != "<think>\nx\n<|im_start|>y<|im_end|>Visible").
- result.get("content", ) trailing-comma becomes 1-ARG: missing key ->
  None -> .strip() AttributeError; default "XXXX" -> returns "XXXX"
  WITHOUT raising ValueError; both die on pytest.raises(ValueError) /
  equality of the direct _call_nemotron contract.
- Singleton: resetting sg._summary_generator lets the two module-level
  twins die IN-PROCESS (is-not-None inversion returns None on first
  call; assign-None never caches - two calls must return the SAME
  instance and land the global).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest import mock

import httpx
import pytest

import backend.services.summary_generator as sg
from backend.models.summary import SummaryType

# ============================================================================
# Measured constants (module-local literals are re-declared HERE on purpose:
# reading sg's constants would let a constant-twin mutant round-trip)
# ============================================================================

WS = datetime(2026, 3, 5, 12, 5, 0, tzinfo=UTC)  # window start pin
WE = datetime(2026, 3, 5, 13, 5, 0, tzinfo=UTC)  # window end pin
WSF = "12:05 PM"  # WS.strftime("%I:%M %p") measured
WEF = "01:05 PM"  # WE.strftime("%I:%M %p") measured
LLM_URL = "http://llm.test:8080"
COMPL = LLM_URL + "/completion"
CONTENT = "  Two detections reviewed.  "
STRIPPED = "Two detections reviewed."
CREATED_ID = 99

_SENT = object()  # NOT roundtrippable: a None-twin reads None != _SENT


class Env:
    """One constructed world: every global the module looks up is captured
    with raw-**kwargs recorders (deletion = MISSING key, never a refilled
    default); only the REAL ContextFilter log chain stays real."""

    def __init__(self, rows: list[Any], post_exc: Exception | None, json_payload: Any) -> None:
        self.rows = rows
        self.post_exc = post_exc
        self.json_payload = json_payload
        self.ctx_opens: int = 0
        self.repo_sessions: list[Any] = []
        self.sum_sessions: list[Any] = []
        self.gen_calls: list[dict[str, Any]] = []
        self.repo_calls: list[tuple[Any, ...]] = []
        self.eager: list[Any] = []
        self.create_calls: list[dict[str, Any]] = []
        self.client_inits: list[Any] = []
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.timeouts: list[Any] = []
        self.bsp_calls: list[dict[str, Any]] = []
        parent = self

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> Any:
                return parent.json_payload

        class Client:
            def __init__(self, timeout: Any = _SENT) -> None:
                parent.client_inits.append(timeout)

            async def __aenter__(self) -> Client:
                return self

            async def __aexit__(self, *exc: Any) -> None:
                return None

            async def post(self, url: str, **kw: Any) -> Any:
                parent.posts.append((url, kw))
                if parent.post_exc is not None:
                    raise parent.post_exc
                return Response()

        self.client_cls = Client

    def build_prompt(self, **kw: Any) -> tuple[str, str]:
        self.bsp_calls.append(kw)
        return ("SYS", "USER")

    def timeout_cm(self, arg: Any) -> Any:
        self.timeouts.append(arg)
        return self._noop_cm()

    @staticmethod
    @asynccontextmanager
    async def _noop_cm() -> Any:
        yield

    def fake_asyncio(self) -> SimpleNamespace:
        return SimpleNamespace(timeout=self.timeout_cm)

    def fake_httpx(self) -> SimpleNamespace:
        return SimpleNamespace(Timeout=httpx.Timeout, AsyncClient=self.client_cls)


_SESS = object()


@contextmanager
def env(
    rows: list[Any] | None = None,
    post_exc: Exception | None = None,
    json_payload: Any = None,
    session: Any = _SESS,
):
    e = Env(rows or [], post_exc, json_payload)
    s = session if session is not _SESS else object()
    with (
        mock.patch.object(sg, "get_session", _fake_get_session(e)),
        mock.patch.object(sg, "EventRepository", lambda sess: _Repo(e, sess)),
        mock.patch.object(sg, "SummaryRepository", lambda sess: _SumRepo(e, sess)),
        mock.patch.object(sg, "build_summary_prompt", e.build_prompt),
        mock.patch.object(sg, "httpx", e.fake_httpx()),
        mock.patch.object(sg, "asyncio", e.fake_asyncio()),
    ):
        e.session = s
        yield e


def _fake_get_session(e: Env) -> Any:
    @asynccontextmanager
    async def _cm() -> Any:
        e.ctx_opens += 1
        yield "CTX-SESSION"

    return _cm


class _Repo:
    def __init__(self, cap: Env, session: Any) -> None:
        self.cap, self.session = cap, session
        cap.repo_sessions.append(session)

    async def get_in_date_range(self, *a: Any, **kw: Any) -> list[Any]:
        self.cap.repo_calls.append(a)
        self.cap.eager.append(kw.get("eager_load_camera", _SENT))
        return self.cap.rows


class _SumRepo:
    def __init__(self, cap: Env, session: Any) -> None:
        self.cap, self.session = cap, session
        cap.sum_sessions.append(session)

    async def create_summary(self, **kw: Any) -> Any:
        self.cap.create_calls.append(kw)
        return SimpleNamespace(id=CREATED_ID)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _event(
    eid: int = 7,
    started_at: Any = None,
    camera_id: Any = "cam-1",
    camera: Any = None,
    risk_level: Any = "high",
    risk_score: Any = 8,
    summary: Any = "Person at door",
    object_types: Any = "person",
) -> Any:
    return SimpleNamespace(
        id=eid,
        started_at=started_at,
        camera_id=camera_id,
        camera=camera,
        risk_level=risk_level,
        risk_score=risk_score,
        summary=summary,
        object_types=object_types,
    )


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.recs: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.recs.append(record)

    def one(self, msg: str) -> logging.LogRecord:
        hits = [r for r in self.recs if r.getMessage() == msg]
        assert len(hits) == 1, (msg, [r.getMessage() for r in self.recs])
        return hits[0]


@contextmanager
def logcap():
    h = _Records()
    old = sg.logger.level
    sg.logger.addHandler(h)
    sg.logger.setLevel(logging.DEBUG)
    try:
        yield h
    finally:
        sg.logger.removeHandler(h)
        sg.logger.setLevel(old)


def _extras(rec: logging.LogRecord, names: list[str]) -> dict[str, Any]:
    """BY NAME, never a record-attr census; a dropped/None extra raises
    MISSING (audit: ContextFilter injects none of these keys)."""
    out: dict[str, Any] = {}
    for n in names:
        assert hasattr(rec, n), (n, "MISSING from record")
        out[n] = getattr(rec, n)
    return out


# ============================================================================
# __init__  (survivors m5 m6 m7 m8 m9 m14 m15)
# ============================================================================


def test_init_timeout_attributes_are_the_shipped_constants():
    # m6/m7/m8/m9 (connect/read/write/pool -> None) and m14/m15
    # (or -> and, which yields None when timeout is None) all die here:
    # httpx.Timeout CONSTRUCTS with None values, so this is ATTRIBUTE
    # EQUALITY (measured), never a raised error.
    gen = sg.SummaryGenerator()
    assert gen._timeout.connect == 10.0
    assert gen._timeout.read == 60.0
    assert gen._timeout.write == 60.0
    assert gen._timeout.pool == 10.0
    assert gen._api_key is None


def test_init_timeout_override_sets_read_and_write_only():
    gen = sg.SummaryGenerator(timeout=7.5)
    assert gen._timeout.read == 7.5
    assert gen._timeout.write == 7.5
    assert gen._timeout.connect == 10.0
    assert gen._timeout.pool == 10.0


def test_init_llm_url_override_and_settings_default():
    gen = sg.SummaryGenerator(llm_url=LLM_URL)
    assert gen._llm_url == LLM_URL
    default = sg.SummaryGenerator()
    assert default._llm_url == sg.get_settings().ai_vlm_url
    assert default._llm_url != LLM_URL


# ============================================================================
# generate_hourly_summary  (survivors m2..m35)
# ============================================================================


def _gs_spy():
    """Raw **kwargs capture on the internal dispatch: a DELETED kwarg is a
    MISSING KEY here (never a refilled default)."""
    calls: list[dict[str, Any]] = []

    async def _spy(self: Any, **kw: Any) -> Any:
        calls.append(kw)
        return SimpleNamespace(id=CREATED_ID)

    return calls, _spy


GS_KEYS = {"session", "summary_type", "window_start", "window_end", "period_type"}


def test_generate_hourly_summary_creates_session_when_none():
    calls, spy = _gs_spy()
    with env() as e, mock.patch.object(sg.SummaryGenerator, "_generate_summary", spy):
        out = _run(sg.SummaryGenerator(llm_url=LLM_URL).generate_hourly_summary())
    assert out.id == CREATED_ID
    assert e.ctx_opens == 1
    assert len(calls) == 1
    kw = calls[0]
    assert set(kw) == GS_KEYS
    assert kw["session"] == "CTX-SESSION"
    assert kw["summary_type"] is SummaryType.HOURLY
    assert kw["period_type"] == "hour"
    assert kw["window_start"].tzinfo is UTC
    assert kw["window_end"].tzinfo is UTC
    # the two shipped now() calls drift microseconds apart: pin 60 minutes
    # within +-5s (kills the +/- twins at a full minute, never env-coupled)
    diff = kw["window_end"] - kw["window_start"]
    assert timedelta(minutes=59, seconds=55) < diff < timedelta(minutes=60, seconds=5)


def test_generate_hourly_summary_uses_supplied_session():
    calls, spy = _gs_spy()
    sess = object()
    with env() as e, mock.patch.object(sg.SummaryGenerator, "_generate_summary", spy):
        out = _run(sg.SummaryGenerator(llm_url=LLM_URL).generate_hourly_summary(sess))
    assert out.id == CREATED_ID
    assert e.ctx_opens == 0
    assert len(calls) == 1
    kw = calls[0]
    assert set(kw) == GS_KEYS
    assert kw["session"] is sess
    assert kw["summary_type"] is SummaryType.HOURLY
    assert kw["period_type"] == "hour"
    assert kw["window_start"].tzinfo is UTC
    assert kw["window_end"].tzinfo is UTC
    # the two shipped now() calls drift microseconds apart: pin 60 minutes
    # within +-5s (kills the +/- twins at a full minute, never env-coupled)
    diff = kw["window_end"] - kw["window_start"]
    assert timedelta(minutes=59, seconds=55) < diff < timedelta(minutes=60, seconds=5)


# ============================================================================
# generate_daily_summary  (survivors m2 m11 m15 m17..m40)
# ============================================================================


def test_generate_daily_summary_creates_session_when_none():
    calls, spy = _gs_spy()
    with env() as e, mock.patch.object(sg.SummaryGenerator, "_generate_summary", spy):
        out = _run(sg.SummaryGenerator(llm_url=LLM_URL).generate_daily_summary())
    assert out.id == CREATED_ID
    assert e.ctx_opens == 1
    assert len(calls) == 1
    kw = calls[0]
    assert set(kw) == GS_KEYS
    assert kw["session"] == "CTX-SESSION"
    assert kw["summary_type"] is SummaryType.DAILY
    assert kw["period_type"] == "day"
    assert kw["window_end"].tzinfo is UTC
    assert kw["window_start"].tzinfo is UTC
    assert kw["window_start"].hour == 0
    assert kw["window_start"].minute == 0
    assert kw["window_start"].second == 0
    assert kw["window_start"].microsecond == 0
    assert kw["window_start"].date() == kw["window_end"].date()
    # m11/m15: the microsecond-drop trailing-comma twin keeps now's
    # microsecond and the microsecond=1 twin sets 1; either fails this pin
    # (equal only in the ~1e-6 instant where the real now() has microsecond 0,
    # which is ALSO the instant where window_end's own microsecond is 0 - the
    # pin is self-consistent, never environment-coupled).
    assert kw["window_start"] == kw["window_end"].replace(hour=0, minute=0, second=0, microsecond=0)


def test_generate_daily_summary_uses_supplied_session():
    calls, spy = _gs_spy()
    sess = object()
    with env() as e, mock.patch.object(sg.SummaryGenerator, "_generate_summary", spy):
        out = _run(sg.SummaryGenerator(llm_url=LLM_URL).generate_daily_summary(sess))
    assert out.id == CREATED_ID
    assert e.ctx_opens == 0
    assert len(calls) == 1
    kw = calls[0]
    assert set(kw) == GS_KEYS
    assert kw["session"] is sess
    assert kw["summary_type"] is SummaryType.DAILY
    assert kw["period_type"] == "day"
    assert kw["window_start"].microsecond == 0
    assert kw["window_start"].second == 0
    assert kw["window_start"].hour == 0
    assert kw["window_start"].minute == 0
    assert kw["window_end"].tzinfo is UTC


def test_generate_all_summaries_uses_supplied_session_for_both():
    sess = object()
    with env() as e:
        out = _run(sg.SummaryGenerator(llm_url=LLM_URL).generate_all_summaries(sess))
    assert e.ctx_opens == 0
    assert sorted(out) == ["daily", "hourly"]


def test_generate_all_summaries_creates_one_session_for_both():
    with env() as e:
        out = _run(sg.SummaryGenerator(llm_url=LLM_URL).generate_all_summaries())
    assert e.ctx_opens == 1
    assert sorted(out) == ["daily", "hourly"]


# ============================================================================
# _generate_summary  (survivors m2 m6 m12..m93) + _get_high_critical_events
# (m3 m4 m7 m8)
#
# Three driven paths, each asserting EVERY observable its branch writes:
#   ZERO   -> all-clear content, INFO x3 (generating/zero/created)
#   OK     -> content from _call_nemotron, INFO x3 (generating/created),
#             build_summary_prompt + timeout + httpx call-site pins
#   FAIL   -> exception -> WARNING (fallback) + INFO x2, fallback content
# ============================================================================

GS_MSG_GEN = "Generating hourly summary"
GS_MSG_ZERO = "Zero events for hourly summary, using deterministic all-clear message"
GS_MSG_FAIL = "Nemotron unavailable for hourly summary, using fallback"
GS_MSG_CREATED = "Created hourly summary"
NMSG = "Generated summary via Nemotron"

ALLCLEAR = "No high-priority security events detected in this period. The property has been quiet."


def _drive(
    e: Env, rows: list[Any], post_exc: Exception | None, payload: Any, url: str = LLM_URL
) -> Any:
    gen = sg.SummaryGenerator(llm_url=url)
    return _run(
        gen._generate_summary(
            session=e.session,
            summary_type=SummaryType.HOURLY,
            window_start=WS,
            window_end=WE,
            period_type="hour",
        )
    )


def test_zero_events_path_writes_every_observable():
    with env(rows=[], session="S") as e, logcap() as cap:
        out = _drive(e, [], None, None)
    assert out.id == CREATED_ID
    # repo construction carries the SESSION (m2/m64: EventRepository(None)/
    # SummaryRepository(None) die on the captured session identity)
    assert e.repo_sessions == ["S"]
    assert e.sum_sessions == ["S"]
    # the entered branch FORWARDS its window to the repo: pin the call args
    # (m6's window_end->None twin is observable ONLY here - the direct
    # _get_high_critical_events tests drive WS/WE themselves and never see
    # what _generate_summary hands it)
    assert e.repo_calls == [(WS, WE)]
    assert e.eager == [True]
    # m70/m71/m72 -> None and m77/m78/m79 (deletion -> MISSING key) die on
    # FULL key-set + value equality of the raw create_summary capture
    assert len(e.create_calls) == 1
    cc = e.create_calls[0]
    assert set(cc) == {
        "summary_type",
        "content",
        "event_count",
        "event_ids",
        "window_start",
        "window_end",
        "generated_at",
    }
    assert cc["summary_type"] is SummaryType.HOURLY
    assert cc["content"] == ALLCLEAR
    assert cc["event_count"] == 0
    assert cc["event_ids"] is None
    assert cc["window_start"] == WS
    assert cc["window_end"] == WE
    assert cc["generated_at"].tzinfo is UTC  # m26 None / m27 naive die
    assert cc["generated_at"].isoformat().endswith("+00:00")
    # m24: event_context=None would flow to _call_nemotron - never reached
    # on this path, pinned instead via the OK path's events kwarg below.
    m1 = cap.one(GS_MSG_GEN)  # m12 None message dies at the ONE-hit lookup
    assert _extras(m1, ["summary_type", "event_count", "window_start", "window_end"]) == {
        "summary_type": "hourly",
        "event_count": 0,
        "window_start": WS.isoformat(),
        "window_end": WE.isoformat(),
    }
    m2 = cap.one(GS_MSG_ZERO)
    assert _extras(m2, ["summary_type", "event_count"]) == {
        "summary_type": "hourly",
        "event_count": 0,  # m40: 1 fails
    }
    m3 = cap.one(GS_MSG_CREATED)
    assert _extras(m3, ["summary_id", "summary_type", "event_count", "content_length"]) == {
        "summary_id": CREATED_ID,
        "summary_type": "hourly",
        "event_count": 0,
        "content_length": len(ALLCLEAR),
    }


def test_llm_success_path_writes_every_observable():
    row = _event(started_at=WS)
    with env(rows=[row], json_payload={"content": CONTENT}, session="S") as e, logcap() as cap:
        out = _drive(e, [row], None, {"content": CONTENT})
    assert out.id == CREATED_ID
    assert e.repo_sessions == ["S"] and e.sum_sessions == ["S"]
    assert e.repo_calls == [(WS, WE)]  # m6 forwarding twin
    assert e.eager == [True]
    # the branch hands its OWN arguments to _call_nemotron, which forwards
    # them to build_summary_prompt: FULL equality here kills m44
    # (period_type->None: the mock never raises on it, so ONLY this capture
    # sees it) and the m45/m46/m47 deletion twins.
    assert e.bsp_calls == [
        {
            "window_start": WSF,
            "window_end": WEF,
            "period_type": "hour",
            "events": [
                {
                    "timestamp": WSF,
                    "camera_name": "cam-1",
                    "risk_level": "high",
                    "risk_score": 8,
                    "summary": "Person at door",
                    "object_types": "person",
                }
            ],
            "routine_count": 0,
        }
    ]
    cc = e.create_calls[0]
    assert cc["content"] == STRIPPED
    assert cc["event_count"] == 1
    assert cc["event_ids"] == [7]
    assert cc["window_start"] == WS and cc["window_end"] == WE
    assert cc["generated_at"].tzinfo is UTC
    m1 = cap.one(GS_MSG_GEN)
    assert _extras(m1, ["summary_type", "event_count", "window_start", "window_end"]) == {
        "summary_type": "hourly",
        "event_count": 1,
        "window_start": WS.isoformat(),
        "window_end": WE.isoformat(),
    }
    m3 = cap.one(GS_MSG_CREATED)
    assert _extras(m3, ["summary_id", "summary_type", "event_count", "content_length"]) == {
        "summary_id": CREATED_ID,
        "summary_type": "hourly",
        "event_count": 1,
        "content_length": len(STRIPPED),
    }
    assert cap.one(NMSG)  # fallback WARNING must NOT have fired
    assert not any(r.getMessage() == GS_MSG_FAIL for r in cap.recs)


def test_llm_failure_path_writes_every_observable():
    row = _event(started_at=WS)
    boom = httpx.ConnectError("no route")
    with env(rows=[row], post_exc=boom, session="S") as e, logcap() as cap:
        out = _drive(e, [row], boom, None)
    assert e.repo_calls == [(WS, WE)]  # m6 on the fallback path too
    assert e.eager == [True]
    cc = e.create_calls[0]
    assert cc["content"] == (
        "Summary temporarily unavailable. 1 high/critical events in this period."
    )
    assert cc["event_count"] == 1 and cc["event_ids"] == [7]
    assert cc["window_start"] == WS and cc["window_end"] == WE
    m1 = cap.one(GS_MSG_GEN)
    assert _extras(m1, ["summary_type", "event_count", "window_start", "window_end"]) == {
        "summary_type": "hourly",
        "event_count": 1,
        "window_start": WS.isoformat(),
        "window_end": WE.isoformat(),
    }
    mw = cap.one(GS_MSG_FAIL)  # m50 None message dies at the ONE-hit lookup
    assert _extras(mw, ["summary_type", "error", "event_count"]) == {
        "summary_type": "hourly",
        "error": str(boom),
        "event_count": 1,
    }  # m58 str(None) -> "None" != "no route"; m56/m57/m59/m60 renames MISSING
    m3 = cap.one(GS_MSG_CREATED)
    assert _extras(m3, ["summary_id", "summary_type", "event_count", "content_length"]) == {
        "summary_id": CREATED_ID,
        "summary_type": "hourly",
        "event_count": 1,
        "content_length": len(cc["content"]),
    }
    assert not any(r.getMessage() == GS_MSG_ZERO for r in cap.recs)
    assert not any(r.getMessage() == NMSG for r in cap.recs)


# ============================================================================
# _get_high_critical_events  (survivors m3 m4 m7 m8)
#   raw positional capture (m3 -> window_end None, m7 deletion -> SHORTER
#   tuple) + eager_load_camera captured with a NON-ROUNDTRIPABLE sentinel
#   (m4 explicit None / m8 False die on value; m7 deletion is MISSING -> _SENT)
# ============================================================================


def test_get_high_critical_events_filters_and_forwards_call():
    rows = [
        _event(eid=1, risk_level="high"),
        _event(eid=2, risk_level="critical"),
        _event(eid=3, risk_level="low"),
        _event(eid=4, risk_level=None),
        _event(eid=5, risk_level="medium"),
    ]
    with env(rows=rows) as e:
        out = _run(
            sg.SummaryGenerator(llm_url=LLM_URL)._get_high_critical_events(_Repo(e, "S"), WS, WE)
        )
    assert [r.id for r in out] == [1, 2]
    assert e.repo_calls == [(WS, WE)]  # m3 (None) / m7 (1-tuple) die exactly
    assert e.eager == [True]  # m4 None / m8 False / m7 MISSING die


def test_get_high_critical_events_all_filtered_out():
    with env(rows=[_event(risk_level="low")]) as e:
        out = _run(
            sg.SummaryGenerator(llm_url=LLM_URL)._get_high_critical_events(_Repo(e, "S"), WS, WE)
        )
    assert out == []
    assert e.repo_calls == [(WS, WE)] and e.eager == [True]


# ============================================================================
# _build_event_context  (survivors m2 m3 m4 m6..m11 m24 m25 m31 m32 m36
#                        m40..m42 m46..m48)
#   ONE call with TWO rows: a populated row (every field truthy) and a
#   falsy-field row (started_at None, camera None, risk_level "", risk_score
#   0, summary "", object_types "") so BOTH sides of every `or`/ternary twin
#   is exercised, and the whole returned list is compared BY FULL EQUALITY.
# ============================================================================

BEV_POP = {
    "timestamp": "12:05 PM",  # WS.strftime("%I:%M %p"), measured pin
    "camera_name": "Front Door",
    "risk_level": "critical",
    "risk_score": 9,
    "summary": "Person at door",
    "object_types": "person",
}
BEV_FALSY = {
    "timestamp": "Unknown time",
    "camera_name": "cam-9",
    "risk_level": "unknown",
    "risk_score": 0,
    "summary": "No summary available",
    "object_types": "Unknown objects",
}


def test_build_event_context_both_extremes_full_equality():
    pop = _event(
        eid=1,
        started_at=WS,
        camera_id="cam-9",
        camera=SimpleNamespace(name="Front Door"),
        risk_level="critical",
        risk_score=9,
        summary="Person at door",
        object_types="person",
    )
    fal = _event(
        eid=2,
        started_at=None,
        camera_id="cam-9",
        camera=None,
        risk_level="",
        risk_score=0,
        summary="",
        object_types="",
    )
    out = sg.SummaryGenerator(llm_url=LLM_URL)._build_event_context([pop, fal])
    assert out == [BEV_POP, BEV_FALSY]


def test_build_event_context_camera_name_falls_back_to_camera_id():
    # camera present but .name falsy -> camera_id wins (the `or` inside the
    # camera branch; m24/m25 rename twins die on the FULL-EQ row above too)
    ev = _event(
        eid=3,
        started_at=WE,
        camera_id="cam-7",
        camera=SimpleNamespace(name=""),
        risk_level="critical",
        risk_score=9,
    )
    out = sg.SummaryGenerator(llm_url=LLM_URL)._build_event_context([ev])
    assert out == [{**BEV_POP, "timestamp": "01:05 PM", "camera_name": "cam-7"}]


def test_build_event_context_camera_attribute_absent():
    # row WITHOUT a camera attribute at all -> hasattr False branch ->
    # camera_id; a del-attr-vs-None conflation twin dies on the row equality
    ev = SimpleNamespace(
        id=4,
        started_at=WS,
        camera_id="cam-absent",
        risk_level="critical",
        risk_score=9,
        summary="Person at door",
        object_types="person",
    )
    assert not hasattr(ev, "camera")
    out = sg.SummaryGenerator(llm_url=LLM_URL)._build_event_context([ev])
    assert out == [{**BEV_POP, "camera_name": "cam-absent"}]


def test_build_event_context_empty_returns_empty_list():
    assert sg.SummaryGenerator(llm_url=LLM_URL)._build_event_context([]) == []


# ============================================================================
# _call_nemotron  (survivors m1 m3..m6 m8..m14 m21..m41 m43..m46 m49 m50
#                  m52 m53 m57 m59 m62 m65 m76 m79..m92)
#
# The ChatML tokens are BUILT here, never written as literals (they are
# mangled in transit through some channels); the built values are byte-exact
# and every pin below is FULL equality, so each token twin dies.
# ============================================================================

IM_START = "<" + "|im_" + "start|" + ">"
IM_END = "<" + "|im_" + "end|" + ">"
FULL_PROMPT = (
    IM_START
    + "system\nSYS"
    + IM_END
    + "\n"
    + IM_START
    + "user\nUSER"
    + IM_END
    + "\n"
    + IM_START
    + "assistant\n"
)
PAYLOAD = {
    "prompt": FULL_PROMPT,
    "temperature": 0.3,
    "top_p": 0.9,
    "max_tokens": 256,
    "stop": [IM_END, IM_START],
}
NEMO_SETTINGS_SUM = sg.get_settings().ai_vlm_read_timeout + sg.get_settings().ai_connect_timeout
API_KEY_VAL = "sekret"  # pragma: allowlist secret


def _nemo(gen: Any, events: list[Any] | None = None) -> Any:
    return _run(
        gen._call_nemotron(
            window_start=WS,
            window_end=WE,
            period_type="hour",
            events=events if events is not None else [BEV_POP],
        )
    )


def test_call_nemotron_success_pins_every_call_site():
    with env(json_payload={"content": CONTENT}) as e, logcap() as cap:
        out = _nemo(sg.SummaryGenerator(llm_url=LLM_URL))
    assert out == STRIPPED
    # m12/m13/m14 -> None and m21 (routine_count deleted) + m22 (routine_count
    # =1) die on the FULL build_summary_prompt kwargs capture; the formatted
    # bounds also kill every strftime twin (m3 m4 m5 m8 m9 m10).
    assert e.bsp_calls == [
        {
            "window_start": WSF,
            "window_end": WEF,
            "period_type": "hour",
            "events": [BEV_POP],
            "routine_count": 0,
        }
    ]
    # m46 passes timeout=None and m5/m14/m15 make the INSTANCE attrs None:
    # both die on the captured AsyncClient init arg (shipped passes the
    # instance, so the captured object's attrs are the shipped ones).
    assert len(e.client_inits) == 1
    to = e.client_inits[0]
    assert (to.connect, to.read, to.write, to.pool) == (10.0, 60.0, 60.0, 10.0)
    assert len(e.posts) == 1
    url, kw = e.posts[0]
    assert url == COMPL
    assert set(kw) == {"json", "headers"}  # m52/m53 deletions -> MISSING key
    assert kw["json"] == PAYLOAD  # every payload key/value/stop-token twin
    assert kw["headers"] == {"Content-Type": "application/json"}  # m50 None
    # m43 (None) / m44 (minus) / m45 (None) die against the LIVE-computed
    # sum, never a literal - no env coupling.
    assert e.timeouts == [NEMO_SETTINGS_SUM]
    m = cap.one(NMSG)
    assert _extras(m, ["period_type", "content_length", "event_count"]) == {
        "period_type": "hour",
        "content_length": len(STRIPPED),
        "event_count": 1,
    }


def test_call_nemotron_auth_headers_are_sent():
    with env(json_payload={"content": CONTENT}) as e:
        _nemo(sg.SummaryGenerator(llm_url=LLM_URL, api_key=API_KEY_VAL))
    assert e.posts[0][1]["headers"] == {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY_VAL,
    }


def test_call_nemotron_empty_completion_raises():
    for payload in ({}, {"content": "   "}):
        with env(json_payload=payload) as e:
            with pytest.raises(ValueError) as exc:
                _nemo(sg.SummaryGenerator(llm_url=LLM_URL))
        assert str(exc.value) == "Empty completion from LLM"  # m65 XX-wrapped
        # m57/m59 (None default) die BEFORE the raise on AttributeError and
        # m62 ("XXXX" default) never raises at all - both covered by this
        # raises-contract; the absent-key row is payload {}.
        assert e.bsp_calls[0]["routine_count"] == 0


THINK_OPEN = "<" + "think" + ">"  # shipped regex uses <think> (od -c)
THINK_CLOSE = "<" + "/think" + ">"  # and </think>, not ChatML


def test_call_nemotron_strips_think_wrappers_multiline():
    wrapped = "V1" + THINK_OPEN + "\nhidden\n" + THINK_CLOSE + "Visible"
    with env(json_payload={"content": wrapped}) as e:
        out = _nemo(sg.SummaryGenerator(llm_url=LLM_URL))
    # measured: re.sub WITHOUT DOTALL leaves the multi-line wrapper -> the
    # m76 flag-drop twin returns the raw wrapper and dies HERE.
    assert out == "V1Visible"
    assert e.posts[0][0] == COMPL


def test_call_nemotron_replacement_is_empty_not_placeholder():
    wrapped = "A" + THINK_OPEN + "hidden" + THINK_CLOSE + "B"
    with env(json_payload={"content": wrapped}):
        out = _nemo(sg.SummaryGenerator(llm_url=LLM_URL))
    assert out == "AB"  # m79 ("XXXX" replacement) returns "AXXXXB"


# ============================================================================
# _get_fallback_content  (survivor m3)
# ============================================================================


def test_get_fallback_content_both_branches_full_equality():
    gen = sg.SummaryGenerator(llm_url=LLM_URL)
    assert gen._get_fallback_content(0) == ALLCLEAR
    assert gen._get_fallback_content(3) == (
        "Summary temporarily unavailable. 3 high/critical events in this period."
    )
    assert gen._get_fallback_content(1) == (
        "Summary temporarily unavailable. 1 high/critical events in this period."
    )


# ============================================================================
# module singleton  (survivors m1 is-None inversion, m2 assign-None)
# ============================================================================


def test_get_summary_generator_is_a_cached_singleton():
    old = sg._summary_generator
    sg._summary_generator = None
    try:
        first = sg.get_summary_generator()
        assert first is not None  # m1 inversion returns None on the first call
        second = sg.get_summary_generator()
        assert second is first  # m2 (assign None) never caches -> fails here
        assert sg._summary_generator is first
    finally:
        sg._summary_generator = old
