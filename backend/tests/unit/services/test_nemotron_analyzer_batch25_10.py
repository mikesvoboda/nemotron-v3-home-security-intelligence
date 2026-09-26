"""Batch-25 chunk-10 kill battery: NemotronAnalyzer.analyze_detection_fast_path.

Source under test: backend/services/nemotron_analyzer.py, lines 3143-3612.

This file lives OUTSIDE the repo tree, so the repo conftest.py does NOT apply:
``pytestmark = pytest.mark.unit`` is declared below and the settings env vars
are mirrored from backend/tests/unit/conftest.py (values copied, not invented)
BEFORE the backend import. Async is driven with an explicit ``asyncio.run``
inside sync tests because pytest-asyncio's ``asyncio_mode = "auto"`` ini is not
picked up for /tmp paths.

Every expectation below was PROBED against the SHIPPED function first; where
shipped behavior differs from a naive expectation the TEST pins shipped
behavior. No source change is proposed anywhere.

MUTANT SOURCE: bodies come from /tmp/wp-batch25/instrumented-nemotron_analyzer.py
via instrumented.py.spans (mutmut's own per-mutant bodies) — not from text
heuristics. A mutant is installed for exactly one test by swapping
``SHIP.NemotronAnalyzer.analyze_detection_fast_path`` in the module __dict__.

AUTOSPEC NOTE (WP4.2 ratchet): the only unittest.mock patch CALL SITE in this
file is ``get_audit_service`` below, and it carries ``autospec=True``. The
mutant install is NOT a mock-patch site: it is a direct __dict__ swap of the
function under test, for which ``autospec=True`` is unsatisfiable by
construction (autospec would build the spec FROM the shipped function it is
about to replace, and specing to it is exactly what the swap must not do). The
collaborators (get_session, logger, metrics, _call_llm, ...) are swapped through
the module __dict__ / the instance for the same reason: the swapped mutant body
resolves them as globals of the SHIPPED module dict.

OCCURRENCE-TWIN RULE: mutant identity is occurrence order among identical
minus/plus shapes. Where a shape occurs twice in this function (156/189,
234/326, 249/330, 289/333, 290/334, 291/335, 325/359, 329/364) the instrumented
bodies confirm which site each number carries, and each number is killed by the
test that exercises THAT site (spelled out per test below).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import functools
import json
import os
import re
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

# --- minimum env, values copied from backend/tests/unit/conftest.py -----------
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("API_KEY_ENABLED", "true")  # pragma: allowlist secret
os.environ.setdefault("API_KEYS", '["test-unit-api-key-12345"]')  # pragma: allowlist secret

REPO = str(__import__("pathlib").Path(__file__).resolve().parents[4])

SHIP_SRC = REPO + "/backend/services/nemotron_analyzer.py"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import backend.services.nemotron_analyzer as SHIP
from backend.services.nemotron_analyzer import NemotronAnalyzer

FN = "xǁNemotronAnalyzerǁanalyze_detection_fast_path"
INSTRUMENTED = "/tmp/wp-batch25/instrumented-nemotron_analyzer.py"
SPANS = "/tmp/wp-batch25/instrumented.py.spans"

DET_TIME = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC)
DETECT_ID = 4242
EVENT_ID = 555  # id assigned by the fake flush(), mirroring a real flush()

FULL_RISK = {
    "risk_score": 71,
    "risk_level": "high",
    "summary": "S",
    "reasoning": "R",
    "llm_prompt": "LP",
    "entities": ["e"],
    "flags": ["f"],
    "confidence_factors": ["c"],
    "recommended_action": "RA",
    "raw_response": "RR",
}
SANITIZED = "SANITIZED-ERR"


# =============================================================================
# mutant machinery
# =============================================================================
_SH = _S = _E = _SPANS = _ILINES = None


def _load():
    """Lazy loader for the WP25_MUTT mutant machinery ONLY — the /tmp
    instrumented copy + spans are self-verification artifacts, absent in CI."""
    global _SH, _S, _E, _SPANS, _ILINES
    if _SH is not None:
        return
    _SH = open(SHIP_SRC).read().split("\n")  # nosemgrep: path-traversal-open
    _S = next(
        i for i, ln in enumerate(_SH) if ln.startswith("    async def analyze_detection_fast_path")
    )
    _E = next(
        j
        for j in range(_S + 1, len(_SH))
        if _SH[j].startswith("    async def ") or _SH[j].startswith("    def ")
    )
    _SPANS = json.load(open(SPANS))["spans"]
    _ILINES = open(INSTRUMENTED).read().split("\n")


@functools.lru_cache(maxsize=512)
def mutant_source(mnum: int) -> str:
    """mutmut's own body for mutant <mnum>, spliced into the shipped file."""
    _load()
    a, b = _SPANS["%s__mutmut_%d" % (FN, mnum)]
    body = _ILINES[a - 1 : b]
    if body[0].strip() == "":
        body = body[1:]
    body[0] = re.sub(
        r"async def " + FN + r"__mutmut_\d+",
        "async def analyze_detection_fast_path",
        body[0],
        count=1,
    )
    while len(body) < _E - _S:
        body.append("")
    body = body[: _E - _S]
    return "\n".join(_SH[:_S] + body + _SH[_E:])


@functools.lru_cache(maxsize=512)
def mutant_fn(mnum: int):
    ns = dict(SHIP.__dict__)
    ns.pop("__name__", None)
    exec(compile(mutant_source(mnum), SHIP.__file__, "exec"), ns)  # nosemgrep: dangerous-eval
    return ns["NemotronAnalyzer"].analyze_detection_fast_path


class mutant:
    """Install one mutant body for the duration of a test."""

    def __init__(self, mnum):
        self.mnum = mnum

    def __enter__(self):
        self.orig = NemotronAnalyzer.analyze_detection_fast_path
        NemotronAnalyzer.analyze_detection_fast_path = mutant_fn(self.mnum)
        return self

    def __exit__(self, *exc):
        NemotronAnalyzer.analyze_detection_fast_path = self.orig
        return False


# =============================================================================
# scenario machinery (all expectations probed against shipped)
# =============================================================================
class Logger:
    def __init__(self):
        self.calls = []

    def _rec(self, level):
        def go(msg, *a, **kw):
            self.calls.append((level, msg, kw))

        return go

    def __getattr__(self, name):
        return self._rec(name)


class Spy:
    def __init__(self, value=None):
        self.value = value
        self.args = []

    def __call__(self, *a, **kw):
        self.args.append((a, kw))
        return self.value


class AsyncSpy(Spy):
    async def __call__(self, *a, **kw):
        self.args.append((a, kw))
        return self.value


class AsyncRaise(Spy):
    async def __call__(self, *a, **kw):
        self.args.append((a, kw))
        raise self.value


class _Ctx:
    def __init__(self, sess):
        self.sess = sess

    async def __aenter__(self):
        return self.sess

    async def __aexit__(self, *exc):
        return False


class _Session:
    """Records add()/execute()/flush(). flush() assigns PKs exactly as a real
    flush does, so event.id is a real int downstream (the shipped code depends
    on that)."""

    def __init__(self, results, raise_on_flush=0):
        self.results = list(results)
        self.added = []
        self.executed = []
        self.flushes = 0
        self.raise_on_flush = raise_on_flush

    async def execute(self, stmt, *a, **kw):
        self.executed.append(stmt)
        return SimpleNamespace(
            scalar_one_or_none=lambda: self.results.pop(0) if self.results else None
        )

    async def flush(self, *a, **kw):
        self.flushes += 1
        for obj in self.added:
            if getattr(obj, "id", "unset") in (None, "unset"):
                try:
                    obj.id = EVENT_ID
                except Exception:  # pragma: no cover - defensive
                    pass
        if self.raise_on_flush and self.flushes >= self.raise_on_flush:
            raise RuntimeError("flush exploded")

    def add(self, obj):
        self.added.append(obj)


def make_camera():
    return SimpleNamespace(id="cam-1", name="Front Door")


def make_detection(det_time=None):
    return SimpleNamespace(
        id=DETECT_ID,
        camera_id="cam-1",
        object_type="person",
        confidence=0.9,
        file_path="/export/det.jpg",
        detected_at=det_time or DET_TIME,
        bbox_x=1,
        bbox_y=2,
        bbox_width=3,
        bbox_height=4,
        video_width=10,
        video_height=20,
    )


class EnrichResult:
    """The shipped function only reads to_storage_dict + the two household
    match lists + smoke_fire_detection off EnrichmentResult."""

    def __init__(self, storage=None, persons=None, vehicles=None, fire=None):
        self._storage = storage or {}
        self.person_household_matches = persons
        self.vehicle_household_matches = vehicles
        self.smoke_fire_detection = fire

    def to_storage_dict(self, det_id):
        return self._storage


MISSING = "<<unset-attribute>>"


def attr(obj, name):
    """Read as shipped would; MISSING marks an UNSET ORM attribute (which
    raises AttributeError shipped-side and is swallowed by the shipped
    try/except) so tests can distinguish 'unset' from 'None'."""
    try:
        return getattr(obj, name)
    except AttributeError:
        return MISSING


class Boom(Exception):
    def __init__(self, msg="llm down", raw=None):
        super().__init__(msg)
        if raw is not None:
            self.raw_completion = raw


class Runner:
    """Builds the analyzer + patched environment for one scenario."""

    def __init__(self, **scen):
        self.scen = scen
        self.log = Logger()
        self.rpe = Spy()
        self.san = Spy(SANITIZED)
        self.observe = Spy()
        self.set_idem = AsyncSpy()
        self.enqueue = AsyncSpy()
        self.broadcast = AsyncSpy()
        self.webhook = AsyncSpy()
        self.snapshot = Spy({"SNAP": 1})
        self.sources = Spy({"SRC": 2})
        self.audit_service = SimpleNamespace(create_partial_audit=Spy(SimpleNamespace(id=4242)))
        self.error = None

    def __enter__(self):
        scen = self.scen
        self.an = NemotronAnalyzer.__new__(NemotronAnalyzer)
        # P0.3 gate attrs (#6678 added them to __init__; __new__ skips it).
        # Values copied from the repo test_nemotron_analyzer.py mock_settings
        # fixture: constrained decoding OFF => legacy path byte-identical.
        self.an._constrained_enabled = False
        self.an._constrained_fail_closed = True
        self.an._constrained_probe_enabled = True
        self.an._constrained_required_build = None
        self.an._constrained_enforced = None
        self.an._fail_closed_active = False
        self.an._verification_engine = "llama.cpp"
        self.an._verification_model_id = "Nemotron-3-Nano-30B-A3B-Q4_K_M"
        self.an._last_call_duration_ms = None
        self.an._redis = SimpleNamespace()
        camera = scen.get("camera", make_camera())
        detection = scen.get("detection", make_detection())
        self.s1 = _Session([camera, detection])
        self.s2 = _Session([], raise_on_flush=scen.get("raise_on_flush", 0))
        sessions = [self.s1, self.s2]
        cur = {"i": 0}

        def get_session():
            i = cur["i"]
            cur["i"] += 1
            return _Ctx(sessions[i] if i < len(sessions) else sessions[-1])

        tracking = scen.get("tracking")
        if tracking is None:
            tracking = SimpleNamespace(has_data=False, data=None)
        llm_exc = scen.get("llm_exc")
        self.llm_calls = []

        async def call_llm(*a, **kw):
            self.llm_calls.append((a, kw))
            if llm_exc is not None:
                raise llm_exc
            return dict(scen.get("risk_data", {}))

        self.an._check_idempotency = AsyncSpy(scen.get("existing_event_id"))
        self.an._get_existing_event = AsyncSpy(scen.get("existing_event"))
        self.an._format_detections = lambda dets: "FMT"
        self.an._get_enriched_context = AsyncSpy({"ctx": 1})
        self.an._get_recent_scene_changes = AsyncSpy([])
        self.an._get_enrichment_result_from_data = AsyncSpy(tracking)
        self.an._call_llm = call_llm
        self.an._set_idempotency = self.set_idem
        self.an._enqueue_for_evaluation = self.enqueue
        self.an._broadcast_event = self.broadcast
        self.an._trigger_event_created_webhook = self.webhook
        self.an._get_facade = lambda: SimpleNamespace(
            get_cache_service=AsyncRaise(RuntimeError("no facade"))
        )
        self.an._build_enrichment_snapshot = self.snapshot
        self.an._build_context_sources = self.sources

        self._swapped = {
            "get_session": get_session,
            "logger": self.log,
            "record_pipeline_error": self.rpe,
            "sanitize_error": self.san,
            "observe_ai_request_duration": self.observe,
            "observe_stage_duration": Spy(),
            "record_event_created": Spy(),
            "record_event_by_camera": Spy(),
        }
        self._old = {}
        for k, v in self._swapped.items():
            self._old[k] = getattr(SHIP, k)
            setattr(SHIP, k, v)
        self._audit_patch = patch(
            "backend.services.pipeline_quality_audit_service.get_audit_service",
            autospec=True,
            return_value=self.audit_service,
        )
        self._audit_patch.start()
        return self

    def __exit__(self, *exc):
        self._audit_patch.stop()
        for k, v in self._old.items():
            setattr(SHIP, k, v)
        return False

    def run(self):
        target = self.scen.get("target", ("cam-1", DETECT_ID))
        try:
            return asyncio.run(self.an.analyze_detection_fast_path(*target))
        except Exception as exc:
            self.error = exc
            return None


def run(**scen):
    with Runner(**scen) as r:
        outcome = r.run()
    return r, outcome


def logged(log, level, msg):
    return [kw for lv, m, kw in log.calls if lv == level and m == msg]


def msgs(log):
    return [(lv, m) for lv, m, _kw in log.calls]


def types_added(session):
    return [type(x).__name__ for x in session.added]


# =============================================================================
# SUCCESS PATH (full risk_data) — Event construction, junction INSERT,
# idempotency, audit, LLMInteraction
# =============================================================================
class TestSuccessPath:
    """All assertions below are the shipped values measured by probing
    backend/services/nemotron_analyzer.py:3383-3520 unmodified."""

    def test_event_construction_passes_risk_data_through(self):
        """Kills the Event(...) kwarg->None mutants 228, 229, 233, 234, 237,
        238, 239, 240 and the kwarg-REMOVAL mutants 243, 244, 248, 249, 252,
        253, 254, 255, and the get() key-mutation mutants whose result is a
        changed Event field: 280, 282, 284, 285 (reasoning key), 289, 290, 291
        (llm_prompt key), 294, 295, 296 (entities), 297, 298, 299 (flags),
        300, 301, 302 (confidence_factors), 303, 304, 305
        (recommended_action)."""
        r, ev = run(risk_data=FULL_RISK)
        assert r.error is None, repr(r.error)
        assert ev.batch_id == "fast_path_4242"
        assert ev.camera_id == "cam-1"
        assert attr(ev, "started_at") is DET_TIME
        assert attr(ev, "ended_at") is DET_TIME
        assert ev.risk_score == 71
        assert ev.risk_level == "high"
        assert (ev.summary, ev.reasoning, ev.llm_prompt) == ("S", "R", "LP")
        assert ev.reviewed is False
        assert ev.is_fast_path is True
        assert attr(ev, "entities") == ["e"]
        assert attr(ev, "flags") == ["f"]
        assert attr(ev, "confidence_factors") == ["c"]
        assert attr(ev, "recommended_action") == "RA"

    def test_event_defaults_when_risk_data_empty(self):
        """Kills the Event(...) DEFAULT-value mutants: 257, 259, 262
        (risk_score default None/omitted/51), 264, 266, 269, 270 (risk_level
        default None/omitted/XXmediumXX/MEDIUM), 272, 274, 277, 278, 279
        (summary default), 281, 283, 286, 287, 288 (reasoning default)."""
        r, ev = run(risk_data={})
        assert r.error is None, repr(r.error)
        assert ev.risk_score == 50
        assert ev.risk_level == "medium"
        assert ev.summary == "No summary available"
        assert ev.reasoning == "No reasoning available"
        assert ev.llm_prompt is None
        assert ev.entities is None
        assert ev.flags is None
        assert ev.confidence_factors is None
        assert ev.recommended_action is None

    def test_event_added_to_session2(self):
        """Kills 306 (session.add(None) instead of the Event) — shipped adds
        exactly Event, the audit row, then the LLMInteraction."""
        r, ev = run(risk_data=FULL_RISK)
        assert types_added(r.s2) == ["Event", "SimpleNamespace", "LLMInteraction"]
        assert r.s2.added[0] is ev

    def test_event_detections_junction_sql(self):
        """Kills 307 (stmt=None), 308 (index_elements=None), 309, 310, 311,
        312 (.values() kwarg -> None / removed), 314, 315, 316, 317
        (ON CONFLICT index_elements spellings) and 318
        (session.execute(None)): the shipped statement's INSERT column list,
        ON CONFLICT target and bound params are all pinned."""
        r, ev = run(risk_data=FULL_RISK)
        assert len(r.s2.executed) == 1
        stmt = r.s2.executed[0]
        assert stmt is not None, "mutant dropped the statement (307/318 -> None)"
        sql = str(stmt)
        assert sql.startswith(
            "INSERT INTO event_detections (event_id, detection_id, created_at)"
        ), sql
        assert "ON CONFLICT (event_id, detection_id) DO NOTHING" in sql, sql
        params = stmt.compile().params
        assert params["event_id"] == EVENT_ID
        assert params["detection_id"] == DETECT_ID

    def test_set_idempotency_after_flush(self):
        """Kills 319 (batch_id -> None) and 320 (event.id -> None): shipped
        stores the (batch_id, event.id) pair produced by the flush."""
        r, ev = run(risk_data=FULL_RISK)
        assert ev.id == EVENT_ID
        assert r.set_idem.args == [(("fast_path_4242", EVENT_ID), {})]

    def test_partial_audit_call_shape(self):
        """Kills 323 (audit_service=None -> AttributeError swallowed -> no
        audit row), 324 (audit=None -> audit.id raises -> swallowed), 336
        (session.add(None)), 337 (logger.debug(None)) and the audit-site
        kwarg/key mutants 325, 326, 329, 330, 332, 333, 334, 335 (event_id /
        llm_prompt occurrence-2 twins + dropped enrichment_result)."""
        r, ev = run(risk_data=FULL_RISK)
        kwargs = self_audit_kwargs(r)
        assert kwargs == {
            "event_id": EVENT_ID,
            "llm_prompt": "LP",
            "enriched_context": {"ctx": 1},
            "enrichment_result": None,
        }
        assert types_added(r.s2) == ["Event", "SimpleNamespace", "LLMInteraction"]
        assert logged(r.log, "debug", "Created audit 4242 for event 555") == [{}]

    def test_enqueue_for_evaluation_uses_event_id_and_score(self):
        """Kills 338 (event_id -> None), 339 (priority -> None), 340 (dropped
        event_id arg), 341 (dropped priority arg), 342 (`or` -> `and`) and 343
        (50 -> 51): shipped enqueues (event.id, event.risk_score or 50)."""
        r, ev = run(risk_data=FULL_RISK)
        assert r.enqueue.args == [((EVENT_ID, 71), {})]

    def test_enqueue_priority_fallback_when_score_none(self):
        """Second witness for 342/343 (and 339): with risk_score None the
        shipped `event.risk_score or 50` yields 50 — the `and` mutant yields
        None and the 51 mutant yields 51."""
        r, ev = run(risk_data={})
        ev.risk_score = None
        assert r.enqueue.args == [((EVENT_ID, 50), {})]

    def test_llm_interaction_wiring(self):
        """Kills 344 (enrichment_snapshot=None), 345 (detection_ids=None),
        351 (context_sources=None), 356 (household_matches init ""), 359, 364
        (event_id occurrence-1 twins at the LLMInteraction site), 361, 362,
        363 (kwarg -> None), 366, 367 (kwarg removed) and the success-site
        debug log of 156 (duration_ms key) is covered by
        test_success_debug_log_extra."""
        r, ev = run(risk_data=FULL_RISK)
        li = r.s2.added[2]
        assert li.event_id == EVENT_ID
        assert li.raw_response == "RR"
        assert li.enrichment_snapshot == {"SNAP": 1}
        assert li.household_matches is None
        assert li.context_sources == {"SRC": 2}
        assert r.snapshot.args == [
            (
                (),
                {
                    "detection_ids": [DETECT_ID],
                    "enrichment_result": None,
                    "enriched_context": {"ctx": 1},
                },
            )
        ]
        assert r.sources.args == [((), {"enrichment_result": None, "enriched_context": {"ctx": 1}})]

    def test_household_matches_are_serialised_into_interaction(self):
        """Kills 362 (household_matches=None) and 367 (kwarg removed): with
        person matches present the shipped dict is passed through."""
        er = EnrichResult(persons=["p1"], vehicles=None)
        tr = SimpleNamespace(has_data=True, data=er)
        r, ev = run(risk_data=FULL_RISK, tracking=tr)
        li = r.s2.added[2]
        assert li.household_matches == {"persons": ["p1"], "vehicles": []}
        assert r.snapshot.args[0][1]["enrichment_result"] is er

    def test_success_debug_log_extra(self):
        """Kills 156 — the FIRST occurrence of the
        `"duration_ms": llm_duration_ms` shape (the success-path debug log
        extra dict), mutated to "DURATION_MS". (Its twin 189 is the
        failure-site occurrence, killed by test_error_log_extra.)"""
        r, ev = run(risk_data=FULL_RISK)
        (kw,) = logged(r.log, "debug", "Fast path LLM analysis completed for detection 4242")
        assert kw == {"extra": {"camera_id": "cam-1", "detection_id": DETECT_ID, "duration_ms": 0}}


def self_audit_kwargs(r):
    """Pins the shipped kwargs-only call shape of create_partial_audit.

    The Spy records each call as (positional_tuple, kwargs_dict) into .args,
    so `.args` is the LIST OF CALLS, not one call's positional args. Shipped
    calls create_partial_audit(**kwargs) exactly once (the success path after
    the event + audit + LLMInteraction rows). Asserting zero positional args
    on that single call is what kills 323/324/336 (no-audit / audit.id-raise
    / session.add(None) -> AttributeError-swallow -> call never happens, so
    len(spy.args) != 1) and pins kwargs keys against the 325-335 twins.
    """
    spy = r.audit_service.create_partial_audit
    assert len(spy.args) == 1, spy.args
    (positional, kwargs) = spy.args[0]
    assert positional == (), positional
    return dict(kwargs)


# =============================================================================
# LLM FAILURE PATH
# =============================================================================
class TestLlmFailurePath:
    """Shipped behavior probed at lines 3332-3355: metric, sanitize, one
    logger.error, then a canned fallback risk_data that flows into the Event
    and into LLMInteraction.raw_response."""

    def test_error_log_extra(self):
        """Kills 175 (message -> None), 176/179 (extra dict -> None /
        removed), 177/192 (exc_info True -> None/False), 180 (exc_info kwarg
        removed), 181, 182, 183 (message case mutations), 190, 191 (the
        "error" key spelling), 170, 171, 172 (record_pipeline_error argument)
        and 173, 174 (sanitize_error call mutants), plus 189 — the SECOND
        occurrence of the `"duration_ms"` shape, which lives in THIS
        failure-site extra dict."""
        boom = Boom("t")
        r, ev = run(llm_exc=boom)
        assert r.error is None, repr(r.error)
        (kw,) = logged(r.log, "error", "LLM analysis failed for fast path detection")
        assert kw["extra"] == {
            "camera_id": "cam-1",
            "detection_id": DETECT_ID,
            "duration_ms": 0,
            "error": SANITIZED,
        }
        assert kw["exc_info"] is True
        assert r.rpe.args == [(("nemotron_fast_path_error",), {})]
        assert r.san.args == [((boom,), {})]

    def test_fallback_event_fields(self):
        """Kills 203 (the canned summary literal) and 206, 207, 208, 209, 210
        (the canned reasoning key/value literals) — the fallback dict's values
        land verbatim on the Event."""
        r, ev = run(llm_exc=Boom("t"))
        assert ev.risk_score == 50
        assert ev.risk_level == "medium"
        assert ev.summary == "Analysis unavailable - LLM service error"
        assert ev.reasoning == "Failed to analyze detection due to service error"
        assert ev.llm_prompt is None
        assert ev.entities is None

    def test_raw_response_taken_from_exception(self):
        """Kills 211, 212 (the "raw_response" key spelling), 213
        (getattr(None, ...)), 219, 220 (the "raw_completion" attribute name):
        with raw_completion present the shipped LLMInteraction carries it."""
        r, ev = run(llm_exc=Boom("t", raw="RAWCOMP"))
        assert r.s2.added[2].raw_response == "RAWCOMP"

    def test_raw_response_defaults_to_empty_string(self):
        """Kills 215 (default -> None) and 221 (default -> "XXXX"): with no
        raw_completion attribute the shipped fallback is the empty string."""
        r, ev = run(llm_exc=Boom("t"))
        assert r.s2.added[2].raw_response == ""


# =============================================================================
# AUDIT-SWALLOW PATH (second witness for the audit-block call site)
# =============================================================================
class TestAuditSwallow:
    def test_audit_failure_does_not_block_event(self):
        """Kills 323, 324 and 332 as a second witness, and pins the shipped
        swallow: a create_partial_audit failure logs the warning (with the
        exception type/message) and the Event + LLMInteraction still land."""
        r, ev = _run_audit_boom()
        assert r.error is None, repr(r.error)
        assert types_added(r.s2) == ["Event", "LLMInteraction"]
        assert r.enqueue.args == []
        (kw,) = logged(r.log, "warning", "Audit log write failed")
        assert kw["extra"]["error_message"] == "audit boom"


def _run_audit_boom():
    with Runner(risk_data=FULL_RISK) as r:
        r.audit_service.create_partial_audit = Boom_audit()
        outcome = r.run()
    return r, outcome


class Boom_audit:
    def __call__(self, **kw):
        raise RuntimeError("audit boom")
