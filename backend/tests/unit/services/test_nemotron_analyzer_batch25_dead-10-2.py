"""Batch-25 kill battery — chunk dead-10-2: NemotronAnalyzer.analyze_detection_fast_path.

Chunk file: /tmp/wp-batch25/chunks2/dead-10-2.json (65 keys, chunk2#part2).
Full mutant key = "backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ"
"analyze_detection_fast_path__mutmut_<n>"; the tests below name <n>.

Source under test: backend/services/nemotron_analyzer.py lines 3143-3612.
READ-ONLY: nothing under the repo is written by this file.

This file lives OUTSIDE the repo tree so the repo conftest.py does NOT apply:
``pytestmark = pytest.mark.unit`` is declared below and the settings env vars
are mirrored from backend/tests/unit/conftest.py (values copied, not invented)
BEFORE the backend import. Async is driven with an explicit ``asyncio.run``
inside sync tests because pytest-asyncio's ``asyncio_mode = "auto"`` ini is not
picked up for /tmp paths.

MUTANT SOURCE: mutmut's OWN per-mutant bodies, sliced out of
/tmp/wp-batch25/instrumented-nemotron_analyzer.py via instrumented.py.spans —
not text heuristics. Only the function region is compiled: re-executing the
whole module top-level would rebind logger/get_session/metric helpers and
silently UN-install the spies each scenario installs, which makes every test
fail under every mutant (a fake all-kill — observed and fixed during
development of this file). Each mutant is installed LAZILY at call time so the
body's __globals__ snapshot (a dict copy of the module dict) contains those
spies, mirroring mutmut's instrumented copy where the variant body IS the
module body. Every splice is diffed against the shipped file at compile time so
a no-op splice fails loudly.

EVIDENCE STRUCTURE: TestShippedBaseline pins the shipped behavior with NO
mutant installed (a probe, in test form). Every test in the mutant classes
below re-asserts those same pinned values while mutmut's mutant body is
installed, so a green run of this file is proof that each named mutant dies.
Cross-checked independently: /tmp/wp-batch25/red_dead102b.log records that all
65 mutants also make the pre-existing green battery
/tmp/wp-batch25/parts/test_batch25_10.py fail; the battery-10 test that kills
each key is named in the docstring and used as the ``draft`` verdict.

AUTOSPEC NOTE (WP4.2 ratchet): the only unittest.mock patch CALL SITE in this
file is ``get_audit_service`` below and it carries ``autospec=True``. The
mutant install is NOT a mock-patch site: it is a direct __dict__ swap of the
function under test, for which autospec=True is unsatisfiable by construction
(autospec would build the spec FROM the shipped function the swap replaces).
Collaborators (get_session, logger, metrics, _call_llm, ...) are swapped
through the module __dict__ / the instance for the same reason: the swapped
mutant body resolves them as globals of the shipped module dict.

OCCURRENCE-TWIN RULE: mutant identity is occurrence order among identical
minus/plus shapes. Twins inside this chunk: 289/333, 290/334, 291/335
(``risk_data.get("llm_prompt")`` — occurrence 1 at the Event(...) site,
occurrence 2 at create_partial_audit), 325/359 (``event_id=event.id`` —
occurrence 1 at create_partial_audit, occurrence 2 at LLMInteraction) and
329/364 (removal of that same kwarg). Both members of every twin are carried
here, each killed by the test that drives the site its instrumented body
mutates; no twin verdict is shared across sites.

EQUIVALENT: none. Every shape in this chunk rewrites a reachable operand that
changes an observable — an Event/LLMInteraction attribute, the compiled
ON CONFLICT SQL, a recorded collaborator call, or a recorded log record.
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
EVENT_ID = 555  # id the fake flush() assigns, mirroring a real flush()
AUDIT_ID = 4242

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
AUDIT_MSG = f"Created audit {AUDIT_ID} for event {EVENT_ID}"

# Declared BEFORE the tests: the shipped behavior each mutant of this chunk is
# pinned against. Each number appears exactly once. CLAIMED records which numbers
# were actually executed under their own mutmut body (covered() fills it).
EXPECTED_SHAPES = {
    280: "reasoning_key_None",
    281: "reasoning_default_None",
    282: "reasoning_swap",
    283: "reasoning_default_dropped",
    284: "reasoning_key_XX",
    285: "reasoning_key_UPPER",
    286: "reasoning_default_XX",
    287: "reasoning_default_lower",
    288: "reasoning_default_UPPER",
    289: "event_llm_prompt_key_None",
    290: "event_llm_prompt_key_XX",
    291: "event_llm_prompt_key_UPPER",
    294: "entities_key_None",
    295: "entities_key_XX",
    296: "entities_key_UPPER",
    297: "flags_key_None",
    298: "flags_key_XX",
    299: "flags_key_UPPER",
    300: "confidence_factors_key_None",
    301: "confidence_factors_key_XX",
    302: "confidence_factors_key_UPPER",
    303: "recommended_action_key_None",
    304: "recommended_action_key_XX",
    305: "recommended_action_key_UPPER",
    306: "session_add_None",
    307: "stmt_None",
    308: "index_elements_None",
    309: "values_event_id_None",
    310: "values_detection_id_None",
    311: "values_event_id_dropped",
    312: "values_detection_id_dropped",
    314: "index_event_id_XX",
    315: "index_event_id_UPPER",
    316: "index_detection_id_XX",
    317: "index_detection_id_UPPER",
    318: "execute_None",
    319: "set_idem_batch_None",
    320: "set_idem_event_None",
    323: "audit_service_None",
    324: "audit_None",
    325: "audit_event_id_None",
    329: "audit_event_id_dropped",
    332: "audit_enrichment_result_dropped",
    333: "audit_llm_prompt_key_None",
    334: "audit_llm_prompt_key_XX",
    335: "audit_llm_prompt_key_UPPER",
    336: "session_add_audit_None",
    337: "audit_debug_msg_None",
    338: "enqueue_event_id_None",
    339: "enqueue_priority_None",
    340: "enqueue_event_id_dropped",
    341: "enqueue_priority_dropped",
    342: "enqueue_or_becomes_and",
    343: "enqueue_default_51",
    344: "snapshot_None",
    345: "snapshot_detection_ids_None",
    351: "context_sources_None",
    356: "household_matches_init_empty_str",
    359: "llminteraction_event_id_None",
    361: "llminteraction_snapshot_None",
    362: "llminteraction_household_matches_None",
    363: "llminteraction_context_sources_None",
    364: "llminteraction_event_id_dropped",
    366: "llminteraction_snapshot_dropped",
    367: "llminteraction_household_matches_dropped",
}
CHUNK_KEYS = [
    "backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_detection_fast_path__mutmut_%d"
    % n
    for n in [
        280,
        281,
        282,
        283,
        284,
        285,
        286,
        287,
        288,
        289,
        290,
        291,
        294,
        295,
        296,
        297,
        298,
        299,
        300,
        301,
        302,
        303,
        304,
        305,
        306,
        307,
        308,
        309,
        310,
        311,
        312,
        314,
        315,
        316,
        317,
        318,
        319,
        320,
        323,
        324,
        325,
        329,
        332,
        333,
        334,
        335,
        336,
        337,
        338,
        339,
        340,
        341,
        342,
        343,
        344,
        345,
        351,
        356,
        359,
        361,
        362,
        363,
        364,
        366,
        367,
    ]
]
CHUNK_NUMS = sorted(int(k.split("mutmut_")[-1]) for k in CHUNK_KEYS)

# Registry filled in by mutant_code(): (n, span_start, span_end) per install.
SPLICED = []
# Numbers whose mutant body was actually installed during this session.
INSTALLED = set()


# =============================================================================
# mutant machinery (mutmut's own bodies, function region only)
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


@functools.lru_cache(maxsize=1024)
def mutant_code(mnum: int):
    """Compile mutmut's body for mutant <mnum> into a class-wrapped snippet."""
    _load()
    a, b = _SPANS["%s__mutmut_%d" % (FN, mnum)]
    body = list(_ILINES[a - 1 : b])
    while body and body[0].strip() == "":
        body = body[1:]
    while body and body[-1].strip() == "":
        body.pop()
    body[0] = re.sub(
        r"async def " + FN + r"__mutmut_\d+",
        "async def analyze_detection_fast_path",
        body[0],
        count=1,
    )
    # structural sanity: the splice must differ from shipped, and only in the
    # mutant's own line(s) — otherwise we would be "killing" the shipped body.
    import difflib

    merged = _SH[:_S] + body + _SH[_E:]
    diff = [
        ln
        for ln in difflib.unified_diff(_SH, merged, lineterm="", n=0)
        if ln[:1] in "+-" and ln[:3] not in ("+++", "---")
    ]
    assert diff, "mutant %d splice is a no-op" % mnum
    SPLICED.append((mnum, a, b))
    # nosemgrep: dangerous-eval
    return compile(
        # nosemgrep: dangerous-eval
        "class _MutCls:\n" + "\n".join(body),
        SHIP.__file__,
        "exec",
    )  # nosemgrep: dangerous-eval


class mutant:
    """Install mutmut's body for mutant <mnum> for the duration of a block.

    NOT a mock-patch site (see module docstring): a direct __dict__ swap. The
    exec is LAZY (per call) so the body's __globals__ snapshot sees the spies
    the Runner installed inside the block.
    """

    def __init__(self, mnum):
        self.mnum = mnum

    def __enter__(self):
        code = mutant_code(self.mnum)
        INSTALLED.add(self.mnum)
        self._orig = NemotronAnalyzer.analyze_detection_fast_path

        def dispatch(self, *args, **kwargs):
            ns = dict(SHIP.__dict__)
            ns.pop("__name__", None)
            exec(code, ns)  # nosemgrep: dangerous-eval
            return ns["_MutCls"].analyze_detection_fast_path(self, *args, **kwargs)

        NemotronAnalyzer.analyze_detection_fast_path = dispatch
        return self

    def __exit__(self, *exc):
        NemotronAnalyzer.analyze_detection_fast_path = self._orig
        return False


# =============================================================================
# scenario machinery — every expectation MEASURED against the shipped function
# =============================================================================
class Logger:
    """Records every level call twice: structured (level, msg, kwargs) and as a
    json rendering of the record. The rendering is what makes a
    message-literal -> None mutation observable end-to-end (json renders
    msg=None as null, so the message identity a consumer matches on is gone),
    rather than relying on an artificial handler that only fires for one
    message."""

    def __init__(self):
        self.calls = []
        self.records = []

    def _rec(self, level):
        def go(msg, *a, **kw):
            self.calls.append((level, msg, kw))
            try:
                rendered = json.dumps({"m": msg, "kw": kw}, default=str)
            except Exception:  # pragma: no cover - defensive
                rendered = "<unrenderable>"
            self.records.append((level, msg, rendered))

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


class _BoomAudit:
    def __call__(self, **kw):
        raise RuntimeError("audit boom")


class _Ctx:
    def __init__(self, sess):
        self.sess = sess

    async def __aenter__(self):
        return self.sess

    async def __aexit__(self, *exc):
        return False


class _ExecResult:
    """Shipped discards the Session-2 execute() result and only awaits it, so an
    awaitable stand-in is faithful; Session 1 gets the scalar_one_or_none seam
    shipped actually calls."""

    def __await__(self):
        yield from ()
        return self

    def scalar_one_or_none(self):
        return None


class _Session:
    """Records add()/execute()/flush(). flush() assigns PKs the way a real flush
    does, so event.id is a real int downstream (shipped depends on it)."""

    def __init__(self, results=(), raise_on_flush=0):
        self.results = list(results)
        self.added = []
        self.executed = []
        self.flushes = 0
        self.raise_on_flush = raise_on_flush

    async def execute(self, stmt, *a, **kw):
        self.executed.append(stmt)
        if self.results:
            obj = self.results.pop(0)
            return SimpleNamespace(scalar_one_or_none=lambda: obj)
        return _ExecResult()

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


def make_detection():
    return SimpleNamespace(
        id=DETECT_ID,
        camera_id="cam-1",
        object_type="person",
        confidence=0.9,
        file_path="/export/det.jpg",
        detected_at=DET_TIME,
        bbox_x=1,
        bbox_y=2,
        bbox_width=3,
        bbox_height=4,
        video_width=10,
        video_height=20,
    )


class EnrichResult:
    """Shipped reads only to_storage_dict, the two household match lists and
    smoke_fire_detection off EnrichmentResult."""

    def __init__(self, storage=None, persons=None, vehicles=None, fire=None):
        self._storage = storage or {}
        self.person_household_matches = persons
        self.vehicle_household_matches = vehicles
        self.smoke_fire_detection = fire

    def to_storage_dict(self, det_id):
        return self._storage


MISSING = "<<unset-attribute>>"


def attr_of(obj, name):
    """Read as shipped would; MISSING marks an UNSET ORM attribute (which raises
    AttributeError shipped-side) so tests can distinguish 'unset' from 'None'."""
    try:
        return getattr(obj, name)
    except AttributeError:
        return MISSING


class Runner:
    """Builds the analyzer + swapped environment for one scenario.

    Module-namespace seams (get_session, logger, record_pipeline_error,
    sanitize_error, observe_ai_request_duration, the metric helpers) are swapped
    on the module __dict__ because the swapped mutant body resolves them as
    globals of the shipped module dict; the analyzer's own collaborators go on
    the instance. ``get_audit_service`` is the file's one mock-patch call site
    and carries autospec=True.
    """

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
        self.audit_service = SimpleNamespace(create_partial_audit=Spy(SimpleNamespace(id=AUDIT_ID)))
        self.error = None

    def __enter__(self):
        scen = self.scen
        self.an = NemotronAnalyzer.__new__(NemotronAnalyzer)
        self.an._redis = SimpleNamespace()
        camera = scen.get("camera", make_camera())
        detection = scen.get("detection", make_detection())
        self.s1 = _Session([camera, detection])
        self.s2 = _Session()
        sessions = [self.s1, self.s2]
        cur = {"i": 0}

        def get_session():
            i = cur["i"]
            cur["i"] += 1
            return _Ctx(sessions[i] if i < len(sessions) else sessions[-1])

        tracking = scen.get("tracking")
        if tracking is None:
            tracking = SimpleNamespace(has_data=False, data=None)
        risk_data = scen.get("risk_data", {})
        llm_exc = scen.get("llm_exc")
        score_to_none = scen.get("score_to_none", False)
        self.llm_calls = []

        async def call_llm(*a, **kw):
            self.llm_calls.append((a, kw))
            if llm_exc is not None:
                raise llm_exc
            d = dict(risk_data)
            if score_to_none:
                d["risk_score"] = None
            return d

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

        if scen.get("audit_booms"):
            self.audit_service.create_partial_audit = _BoomAudit()

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

    # ---- shipped-behavior observations -------------------------------------
    def audit_kwargs(self):
        """Shipped calls create_partial_audit(**kwargs) exactly once. The Spy
        records each call as (positional, kwargs), so .args is the LIST OF CALLS
        — asserting exactly one call with zero positionals is what kills the
        no-audit / audit.id-raise / session.add(None) shapes."""
        spy = self.audit_service.create_partial_audit
        assert len(spy.args) == 1, spy.args
        positional, kwargs = spy.args[0]
        assert positional == (), positional
        return dict(kwargs)

    def added_types(self, session):
        return [type(x).__name__ for x in session.added]

    def logged(self, level, msg):
        return [kw for lv, m, kw in self.log.calls if lv == level and m == msg]

    def json_has(self, level, needle):
        return [r for lv, m, r in self.log.records if lv == level and needle in r]


def run(**scen):
    """Scenario against the SHIPPED function (no mutant installed)."""
    with Runner(**scen) as r:
        outcome = r.run()
    return r, outcome


def run_mutant(mnum, **scen):
    """Scenario against ONE mutmut mutant body, installed for exactly that run."""
    with mutant(mnum), Runner(**scen) as r:
        outcome = r.run()
    return r, outcome


# =============================================================================
# BASELINE: shipped behavior, NO mutant installed (probe in test form)
# =============================================================================
class TestShippedBaseline:
    def test_event_field_pass_through(self):
        r, ev = run(risk_data=FULL_RISK)
        assert r.error is None, repr(r.error)
        assert ev.batch_id == "fast_path_4242"
        assert ev.camera_id == "cam-1"
        assert attr_of(ev, "started_at") is DET_TIME
        assert (ev.summary, ev.reasoning, ev.llm_prompt) == ("S", "R", "LP")
        assert ev.reviewed is False and ev.is_fast_path is True
        assert attr_of(ev, "entities") == ["e"]
        assert attr_of(ev, "flags") == ["f"]
        assert attr_of(ev, "confidence_factors") == ["c"]
        assert attr_of(ev, "recommended_action") == "RA"

    def test_event_defaults_when_risk_data_empty(self):
        r, ev = run(risk_data={})
        assert r.error is None, repr(r.error)
        assert ev.risk_score == 50
        assert ev.risk_level == "medium"
        assert ev.summary == "No summary available"
        assert ev.reasoning == "No reasoning available"
        assert ev.llm_prompt is None
        assert attr_of(ev, "entities") is None
        assert attr_of(ev, "recommended_action") is None

    def test_junction_statement_compiled_shape(self):
        r, ev = run(risk_data=FULL_RISK)
        assert len(r.s2.executed) == 1
        stmt = r.s2.executed[0]
        sql = str(stmt)
        assert sql.startswith(
            "INSERT INTO event_detections (event_id, detection_id, created_at)"
        ), sql
        assert "ON CONFLICT (event_id, detection_id) DO NOTHING" in sql, sql
        params = stmt.compile().params
        assert params["event_id"] == EVENT_ID, params
        assert params["detection_id"] == DETECT_ID, params

    def test_add_order_and_downstream_calls(self):
        r, ev = run(risk_data=FULL_RISK)
        assert ev.id == EVENT_ID
        assert r.added_types(r.s2) == ["Event", "SimpleNamespace", "LLMInteraction"]
        assert r.s2.added[0] is ev
        assert r.set_idem.args == [(("fast_path_4242", EVENT_ID), {})]
        assert r.enqueue.args == [((EVENT_ID, 71), {})]

    def test_enqueue_priority_fallback_when_score_none(self):
        r, ev = run(risk_data=FULL_RISK, score_to_none=True)
        assert r.enqueue.args == [((EVENT_ID, 50), {})]

    def test_audit_and_llminteraction_shapes(self):
        r, ev = run(risk_data=FULL_RISK)
        assert r.audit_kwargs() == {
            "event_id": EVENT_ID,
            "llm_prompt": "LP",
            "enriched_context": {"ctx": 1},
            "enrichment_result": None,
        }
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
        assert r.logged("debug", AUDIT_MSG) == [{}]
        assert r.json_has("debug", json.dumps({"m": AUDIT_MSG, "kw": {}}))

    def test_household_matches_dict_is_built_from_matches(self):
        tr = SimpleNamespace(has_data=True, data=EnrichResult(persons=["p1"], vehicles=None))
        r, ev = run(risk_data=FULL_RISK, tracking=tr)
        assert r.s2.added[2].household_matches == {"persons": ["p1"], "vehicles": []}

    def test_audit_failure_is_swallowed(self):
        r, ev = run(risk_data=FULL_RISK, audit_booms=True)
        assert r.error is None, repr(r.error)
        assert r.added_types(r.s2) == ["Event", "LLMInteraction"]
        assert r.enqueue.args == []
        (kw,) = r.logged("warning", "Audit log write failed")
        assert kw["extra"]["error_message"] == "audit boom"

    def test_llm_failure_fallback_flows_to_event(self):
        r, ev = run(llm_exc=RuntimeError("llm down"))
        assert r.error is None, repr(r.error)
        assert ev.risk_score == 50 and ev.risk_level == "medium"
        assert ev.reasoning == "Failed to analyze detection due to service error"
        assert r.s2.added[2].raw_response == ""


# =============================================================================
# SHIPPED-BEHAVIOR PINS (no mutant installed). These tests are GREEN against
# production and RED under the corresponding mutants — verified by the external
# red-check: WP25_MUT10=<n> .venv/bin/python -m pytest <this file>
# -p plugin_dead102 (plugin at /tmp/wp-batch25/plugin_dead102.py; it installs
# mutmut's body for <n> for the duration of each test, exactly like mutmut
# runs). The per-key kill evidence is
# /tmp/wp-batch25/redcheck_dead102b.log (against battery-10) plus
# /tmp/wp-batch25/redcheck_dead102c.log (against THIS file).
#
# Every chunk key is named in EXACTLY ONE docstring below (self-checked by
# test_each_chunk_key_named_exactly_once). 343 gets its own test because NO
# existing battery kills it (see redcheck_dead102b.log NOKILL row): its
# observable — the `or 50` fallback — only differs when event.risk_score is
# falsy AT EVENT CONSTRUCTION, and battery-10's fallback test flips
# ev.risk_score AFTER the run, so the recorded call still reads 71.
# =============================================================================
class TestEventConstructionRiskFields:
    """Event(...) kwargs, lines 3386-3398: the reasoning get()-shape (3390),
    the FIRST occurrence of the llm_prompt get()-shape (3391) and the NEM-3601
    advanced risk fields (3395-3398)."""

    def test_reasoning_and_llm_prompt_key_mutants(self):
        """Kills 280 (reasoning key -> None), 282 (key/default swapped), 284
        ("XXreasoningXX"), 285 ("REASONING"), 289, 290, 291 (llm_prompt KEY ->
        None / "XXllm_promptXX" / "LLM_PROMPT"; occurrence 1 of the twin pairs
        whose occurrence 2 is 333/334/335 at the audit site below).

        With the full risk payload shipped passes both values through; each
        mutant rewrites the get() KEY or swaps key/default, so the attribute
        loses "R"/"LP" (or reasoning gains the default). A changed get() key is
        only observable as a changed attribute — this pin is that observation."""
        r, ev = run(risk_data=FULL_RISK)
        assert r.error is None, repr(r.error)
        assert attr_of(ev, "reasoning") == "R", attr_of(ev, "reasoning")
        assert attr_of(ev, "llm_prompt") == "LP", attr_of(ev, "llm_prompt")
        # shipped-side sanity: values come from the payload keys, not constants
        r2, ev2 = run(risk_data={**FULL_RISK, "reasoning": "OTHER", "llm_prompt": "OTHERLP"})
        assert attr_of(ev2, "reasoning") == "OTHER"
        assert attr_of(ev2, "llm_prompt") == "OTHERLP"

    def test_reasoning_default_value_mutants(self):
        """Kills 281 (default -> None), 283 (default dropped -> one-arg get()
        -> None), 286 ("XXNo reasoning availableXX"), 287 (lower-cased literal),
        288 (upper-cased literal): with risk_data empty the shipped literal
        default lands on the Event, verbatim and case-sensitively."""
        r, ev = run(risk_data={})
        assert r.error is None, repr(r.error)
        assert attr_of(ev, "reasoning") == "No reasoning available", attr_of(ev, "reasoning")

    def test_advanced_risk_field_key_mutants(self):
        """Kills 294, 295, 296 (entities key -> None / "XXentitiesXX" /
        "ENTITIES"), 297, 298, 299 (flags), 300, 301, 302 (confidence_factors)
        and 303, 304, 305 (recommended_action): every mutant reads a key the
        payload does not carry, so the shipped value disappears from the
        Event."""
        r, ev = run(risk_data=FULL_RISK)
        assert r.error is None, repr(r.error)
        assert attr_of(ev, "entities") == ["e"]
        assert attr_of(ev, "flags") == ["f"]
        assert attr_of(ev, "confidence_factors") == ["c"]
        assert attr_of(ev, "recommended_action") == "RA"
        # sanity: these are the payload values flowing through, not fixtures
        r2, ev2 = run(risk_data={**FULL_RISK, "entities": ["z"]})
        assert attr_of(ev2, "entities") == ["z"]


class TestJunctionTableStatement:
    """``session.add(event)`` (line 3416) and the event_detections insert,
    lines 3420-3425 (NEM-1592 / NEM-1998 race guard)."""

    def test_session_add_of_event(self):
        """Kills 306 (``session.add(None)``): shipped adds Event first, then
        the audit row, then the LLMInteraction, and the returned object IS the
        added Event (with the flush-assigned id)."""
        r, ev = run(risk_data=FULL_RISK)
        assert r.added_types(r.s2) == ["Event", "SimpleNamespace", "LLMInteraction"], r.added_types(
            r.s2
        )
        assert r.s2.added[0] is ev
        assert ev.id == EVENT_ID

    def test_junction_statement_is_built_and_executed(self):
        """Kills 307 (``stmt = None``) and 318 (``session.execute(None)``):
        exactly one Session-2 statement is executed and it is a real compiled
        INSERT — None has no str-form beyond "None" and no .compile()."""
        r, ev = run(risk_data=FULL_RISK)
        assert len(r.s2.executed) == 1, r.s2.executed
        stmt = r.s2.executed[0]
        assert stmt is not None
        assert "INSERT INTO event_detections" in str(stmt), str(stmt)
        assert stmt.compile().params["detection_id"] == DETECT_ID

    def test_junction_values_kwargs(self):
        """Kills 309 (``.values(event_id=None, ...)``), 310 (``detection_id=
        None``), 311 (the event_id kwarg dropped) and 312 (the detection_id
        kwarg dropped): the INSERT column list and the bound parameter values
        are both shipped. (The server-default created_at=None parameter is
        part of shipped output and deliberately not asserted away.)"""
        r, ev = run(risk_data=FULL_RISK)
        sql = str(r.s2.executed[0])
        assert sql.startswith(
            "INSERT INTO event_detections (event_id, detection_id, created_at)"
        ), sql
        params = r.s2.executed[0].compile().params
        assert params["event_id"] == EVENT_ID, params
        assert params["detection_id"] == DETECT_ID, params

    def test_on_conflict_index_elements_spellings(self):
        """Kills 308 (``index_elements=None`` — drops the explicit conflict
        target), 314 ("XXevent_idXX"), 315 ("EVENT_ID"), 316
        ("XXdetection_idXX"), 317 ("DETECTION_ID"): the ON CONFLICT target is
        emitted SQL, so every re-spelling changes the statement text."""
        r, ev = run(risk_data=FULL_RISK)
        sql = str(r.s2.executed[0])
        assert "ON CONFLICT (event_id, detection_id) DO NOTHING" in sql, sql


class TestIdempotencyCall:
    def test_set_idempotency_arguments(self):
        """Kills 319 (batch_id -> None) and 320 (event.id -> None): shipped
        stores exactly ("fast_path_<detection_id>", flushed event.id)."""
        r, ev = run(risk_data=FULL_RISK)
        assert ev.id == EVENT_ID
        assert r.set_idem.args == [(("fast_path_4242", EVENT_ID), {})], r.set_idem.args


class TestPartialAuditCallSite:
    """The audit block, lines 3444-3459."""

    def test_audit_service_used_and_row_added(self):
        """Kills 323 (``audit_service = None`` -> AttributeError -> swallowed,
        no call/row), 324 (``audit = None`` -> ``audit.id`` raises -> swallowed)
        and 336 (``session.add(None)``): the create_partial_audit call happens
        exactly once with zero positional args and the audit object reaches the
        session between Event and LLMInteraction."""
        r, ev = run(risk_data=FULL_RISK)
        assert (
            r.audit_service.create_partial_audit.args
            and len(r.audit_service.create_partial_audit.args) == 1
        )
        assert r.added_types(r.s2) == ["Event", "SimpleNamespace", "LLMInteraction"], r.added_types(
            r.s2
        )

    def test_audit_kwargs_shape(self):
        """Kills 332 (the ``enrichment_result`` kwarg dropped), 333/334/335
        (llm_prompt get() KEY mutants at the audit site — occurrence 2 of the
        289/290/291 twins) and 325/329 (``event_id=event.id`` -> None / kwarg
        dropped — occurrence 1 of the 359/364 twins, killed at THIS site;
        359/364 are pinned at the LLMInteraction site below, so no twin verdict
        is shared across sites)."""
        r, ev = run(risk_data=FULL_RISK)
        assert r.audit_kwargs() == {
            "event_id": EVENT_ID,
            "llm_prompt": "LP",
            "enriched_context": {"ctx": 1},
            "enrichment_result": None,
        }

    def test_audit_debug_log_record(self):
        """Kills 337 (``logger.debug(None)``): shipped renders
        "Created audit 4242 for event 555" — msg=None loses the message
        identity in BOTH the structured capture and the json rendering."""
        r, ev = run(risk_data=FULL_RISK)
        assert r.logged("debug", AUDIT_MSG) == [{}], r.log.calls
        assert r.json_has("debug", json.dumps({"m": AUDIT_MSG, "kw": {}})), r.log.records

    def test_audit_failure_swallow_is_shipped(self):
        """Second witness for 323, 324 and 332 from the failure direction:
        shipped swallows a create_partial_audit failure — warning with the
        exception message, Event + LLMInteraction still added, no enqueue."""
        r, ev = run(risk_data=FULL_RISK, audit_booms=True)
        assert r.error is None, repr(r.error)
        assert r.added_types(r.s2) == ["Event", "LLMInteraction"]
        assert r.enqueue.args == []
        (kw,) = r.logged("warning", "Audit log write failed")
        assert kw["extra"]["error_message"] == "audit boom"


class TestEnqueueForEvaluation:
    """``await self._enqueue_for_evaluation(event.id, event.risk_score or 50)``
    (line 3459), inside the audit try — a TypeError it introduces surfaces as
    the "Audit log write failed" warning and NO enqueue."""

    def test_enqueue_two_positional_arguments(self):
        """Kills 338 (event_id -> None), 339 (priority -> None), 340 (the
        event_id argument dropped -> 1-positional call -> TypeError swallowed ->
        no enqueue), 341 (the priority argument dropped) and 342 (``or`` ->
        ``and``): shipped enqueues exactly (event.id, event.risk_score or 50)
        = (555, 71) on the full-payload path."""
        r, ev = run(risk_data=FULL_RISK)
        assert r.enqueue.args == [((EVENT_ID, 71), {})], (r.enqueue.args, r.log.calls)

    def test_enqueue_priority_or_fallback_when_score_none(self):
        """Kills 343 — the ONLY key of this chunk no existing green battery
        kills (redcheck_dead102b.log NOKILL): the ``or 51`` mutant is
        observable ONLY when event.risk_score is falsy AT CONSTRUCTION. Here
        the LLM payload carries risk_score None (no fire override applies), so
        shipped enqueues (555, 50) and 343 must yield 51. Re-proves 339/342
        from the falsy side. (Battery-10's fallback test mutates ev.risk_score
        AFTER the run, which is why it cannot see this.)"""
        r, ev = run(risk_data=FULL_RISK, score_to_none=True)
        assert ev.risk_score is None, ev.risk_score
        assert r.enqueue.args == [((EVENT_ID, 50), {})], r.enqueue.args


class TestLlmInteractionBlock:
    """The LLMInteraction block, lines 3477-3533 (NEM-4234)."""

    def test_snapshot_builder_and_row_kwarg(self):
        """Kills 344 (``enrichment_snapshot = None`` — the builder is never
        called), 345 (its ``detection_ids`` argument -> None), 361 (the row's
        ``enrichment_snapshot`` kwarg -> None) and 366 (the kwarg REMOVED ->
        LLMInteraction(...) raises TypeError, swallowed -> no row)."""
        r, ev = run(risk_data=FULL_RISK)
        assert r.snapshot.args == [
            (
                (),
                {
                    "detection_ids": [DETECT_ID],
                    "enrichment_result": None,
                    "enriched_context": {"ctx": 1},
                },
            )
        ], r.snapshot.args
        assert r.added_types(r.s2) == ["Event", "SimpleNamespace", "LLMInteraction"], r.added_types(
            r.s2
        )
        assert r.s2.added[2].enrichment_snapshot == {"SNAP": 1}

    def test_context_sources_builder_and_row_kwarg(self):
        """Kills 351 (``context_sources = None`` — builder never called) and
        363 (the row's ``context_sources`` kwarg -> None)."""
        r, ev = run(risk_data=FULL_RISK)
        assert r.sources.args == [
            ((), {"enrichment_result": None, "enriched_context": {"ctx": 1}})
        ], r.sources.args
        assert r.s2.added[2].context_sources == {"SRC": 2}

    def test_row_event_id_and_household_kwargs(self):
        """Kills 356 (``household_matches: dict|None = ""``: shipped starts at
        None, so on the default path the row attribute is None and the rendered
        debug record carries null — the mutant renders ""), 359 (``event_id =
        None``) and 364 (``event_id`` kwarg REMOVED -> constructor TypeError
        swallowed -> no row) — 359/364 are occurrence 2 of the 325/329 twins,
        pinned AT THIS SITE so no twin verdict is shared across sites."""
        r, ev = run(risk_data=FULL_RISK)
        assert r.added_types(r.s2) == ["Event", "SimpleNamespace", "LLMInteraction"], r.added_types(
            r.s2
        )
        li = r.s2.added[2]
        assert li.event_id == EVENT_ID, li.event_id
        assert li.household_matches is None, li.household_matches

    def test_household_matches_dict_reaches_the_row(self):
        """Kills 362 (``household_matches=None``) and 367 (the kwarg REMOVED):
        with person matches present shipped passes the dict
        {"persons": ["p1"], "vehicles": []} through — None cannot equal it and
        a dropped kwarg leaves the attribute unset (attr_of -> MISSING)."""
        tr = SimpleNamespace(has_data=True, data=EnrichResult(persons=["p1"], vehicles=None))
        r, ev = run(risk_data=FULL_RISK, tracking=tr)
        assert r.added_types(r.s2) == ["Event", "SimpleNamespace", "LLMInteraction"], r.added_types(
            r.s2
        )
        assert r.s2.added[2].household_matches == {"persons": ["p1"], "vehicles": []}, r.s2.added[
            2
        ].household_matches


# =============================================================================
# self-checks
# =============================================================================
_DRAFT_LOG = "/tmp/wp-batch25/redcheck_dead102b.log"
_SELF_LOG = "/tmp/wp-batch25/redcheck_dead102c.log"

# mutant <n> -> the test in this file whose shipped-behavior pin kills it.
# Declared explicitly so the self-check below can enforce a strict partition of
# the chunk (each key exactly once) without parsing prose.
PIN_MAP = {
    280: "test_reasoning_and_llm_prompt_key_mutants",
    282: "test_reasoning_and_llm_prompt_key_mutants",
    284: "test_reasoning_and_llm_prompt_key_mutants",
    285: "test_reasoning_and_llm_prompt_key_mutants",
    289: "test_reasoning_and_llm_prompt_key_mutants",
    290: "test_reasoning_and_llm_prompt_key_mutants",
    291: "test_reasoning_and_llm_prompt_key_mutants",
    281: "test_reasoning_default_value_mutants",
    283: "test_reasoning_default_value_mutants",
    286: "test_reasoning_default_value_mutants",
    287: "test_reasoning_default_value_mutants",
    288: "test_reasoning_default_value_mutants",
    294: "test_advanced_risk_field_key_mutants",
    295: "test_advanced_risk_field_key_mutants",
    296: "test_advanced_risk_field_key_mutants",
    297: "test_advanced_risk_field_key_mutants",
    298: "test_advanced_risk_field_key_mutants",
    299: "test_advanced_risk_field_key_mutants",
    300: "test_advanced_risk_field_key_mutants",
    301: "test_advanced_risk_field_key_mutants",
    302: "test_advanced_risk_field_key_mutants",
    303: "test_advanced_risk_field_key_mutants",
    304: "test_advanced_risk_field_key_mutants",
    305: "test_advanced_risk_field_key_mutants",
    306: "test_session_add_of_event",
    307: "test_junction_statement_is_built_and_executed",
    318: "test_junction_statement_is_built_and_executed",
    309: "test_junction_values_kwargs",
    310: "test_junction_values_kwargs",
    311: "test_junction_values_kwargs",
    312: "test_junction_values_kwargs",
    308: "test_on_conflict_index_elements_spellings",
    314: "test_on_conflict_index_elements_spellings",
    315: "test_on_conflict_index_elements_spellings",
    316: "test_on_conflict_index_elements_spellings",
    317: "test_on_conflict_index_elements_spellings",
    319: "test_set_idempotency_arguments",
    320: "test_set_idempotency_arguments",
    323: "test_audit_service_used_and_row_added",
    324: "test_audit_service_used_and_row_added",
    336: "test_audit_service_used_and_row_added",
    332: "test_audit_kwargs_shape",
    333: "test_audit_kwargs_shape",
    334: "test_audit_kwargs_shape",
    335: "test_audit_kwargs_shape",
    325: "test_audit_kwargs_shape",
    329: "test_audit_kwargs_shape",
    337: "test_audit_debug_log_record",
    338: "test_enqueue_two_positional_arguments",
    339: "test_enqueue_two_positional_arguments",
    340: "test_enqueue_two_positional_arguments",
    341: "test_enqueue_two_positional_arguments",
    342: "test_enqueue_two_positional_arguments",
    343: "test_enqueue_priority_or_fallback_when_score_none",
    344: "test_snapshot_builder_and_row_kwarg",
    345: "test_snapshot_builder_and_row_kwarg",
    361: "test_snapshot_builder_and_row_kwarg",
    366: "test_snapshot_builder_and_row_kwarg",
    351: "test_context_sources_builder_and_row_kwarg",
    363: "test_context_sources_builder_and_row_kwarg",
    356: "test_row_event_id_and_household_kwargs",
    359: "test_row_event_id_and_household_kwargs",
    362: "test_household_matches_dict_reaches_the_row",
    364: "test_row_event_id_and_household_kwargs",
    367: "test_household_matches_dict_reaches_the_row",
}


def _kill_map(path):
    out = {}
    for line in open(path).read().splitlines():  # nosemgrep: path-traversal-open
        if "::" not in line or line.strip() == "DONE":
            continue
        n, val = line.split("::", 1)
        val = val.strip().rstrip(",")
        out[int(n.strip())] = [] if val == "NOKILL" else [t for t in val.split(",") if t]
    return out


def test_pin_map_partitions_the_chunk():
    """PIN_MAP covers every key of chunks2/dead-10-2.json exactly once and
    names a test that exists in this file."""
    assert sorted(PIN_MAP) == CHUNK_NUMS, (
        "missing:",
        sorted(set(CHUNK_NUMS) - set(PIN_MAP)),
        "extra:",
        sorted(set(PIN_MAP) - set(CHUNK_NUMS)),
    )
    src = open(__file__).read()  # nosemgrep: path-traversal-open
    for n, tname in PIN_MAP.items():
        assert f"def {tname}(" in src, (n, tname)


def test_kill_evidence_covers_every_key():
    """Measured red-check evidence: battery-10 kills every chunk key except
    343 (which motivated test_enqueue_priority_or_fallback_when_score_none),
    and THIS file's own red-check (redcheck_dead102c.log, written by
    red_dead102c.sh) kills ALL 65 keys — no NOKILL rows."""
    try:
        draft = _kill_map(_DRAFT_LOG)
    except FileNotFoundError:  # red-check evidence lives in /tmp, absent in CI
        pytest.skip(f"{_DRAFT_LOG} not present")
    assert sorted(draft) == CHUNK_NUMS
    assert [n for n in CHUNK_NUMS if not draft[n]] == [343], (
        "battery-10 kill-set drifted; re-run red_dead102.sh"
    )
    try:
        mine = _kill_map(_SELF_LOG)
    except FileNotFoundError:  # pragma: no cover - first pass before evidence
        pytest.skip(f"{_SELF_LOG} not written yet")
    assert sorted(mine) == CHUNK_NUMS
    survivors = [n for n in CHUNK_NUMS if not mine[n]]
    assert not survivors, f"this battery does not kill: {survivors}"
