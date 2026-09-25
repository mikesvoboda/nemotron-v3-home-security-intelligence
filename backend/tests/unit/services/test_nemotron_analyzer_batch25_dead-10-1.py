"""Batch-25 kill battery — chunk dead-10-1:
NemotronAnalyzer.analyze_detection_fast_path#chunk2#part1 (65 keys).

Chunk file: /tmp/wp-batch25/chunks2/dead-10-1.json. Every key is
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ
        analyze_detection_fast_path__mutmut_<n>
(shipped body: backend/services/nemotron_analyzer.py:3143-3612).

DISPOSITION (65 keys)
  61 killed_by_draft — already killed by the EXISTING green battery
      /tmp/wp-batch25/parts/test_batch25_10.py. Verified, not assumed, by an
      in-process RED-CHECK: mutant installed lazily at call time with
      __globals__ == the LIVE module dict so the spies those tests install are
      honoured (driver /tmp/wp-batch25/parts/redcheck_dead101.py, per-key
      result /tmp/wp-batch25/parts/redcheck_dead101_test_batch25_10.json):
      61/65 RED, 4 SURVIVED. Those keys are NOT re-tested here.
      (An earlier run of that driver re-exec'd the whole module per mutant,
      which re-imported SQLAlchemy and clobbered the spies, producing blanket
      false REDs; the driver was fixed and the whole chunk re-checked.)
      The two red tests in 10.py — test_event_detections_junction_sql and
      test_partial_audit_call_shape — do not matter to this tally: every key
      this chunk owns dies on a GREEN test of that file.
  4 equivalent — 194, 195, 197, 198. Proof below, witnessed empirically by
      TestFallbackKeyRenameEquivalence.

THE FOUR EQUIVALENTS
  mutant_diff_lines (built from mutmut's own span bodies) shows each of the
  four edits exactly ONE line and nothing else:
      :3350  "risk_score": 50,       -> 194 "XXrisk_scoreXX" / 195 "RISK_SCORE"
      :3351  "risk_level": "medium", -> 197 "XXrisk_levelXX" / 198 "RISK_LEVEL"
  inside the LLM-failure fallback dict literal (:3349-3355). After that
  literal is built, the shipped body touches risk_data ONLY through literal
  .get(<key>) reads (enumerated from the shipped source):
      :3365 risk_data.get("risk_score", 50)          <- default EQUALS stored 50
      :3366 risk_data["risk_score"] = 100            (unconditional write)
      :3367 risk_data["risk_level"] = "critical"     (unconditional write)
      :3368/:3370 summary reads   :3372/:3376 reasoning reads
      :3391 risk_data.get("risk_score", 50)          <- default EQUALS stored 50
      :3392 risk_data.get("risk_level", "medium")    <- default EQUALS stored value
      :3393 summary  :3394 reasoning  :3395 llm_prompt  :3399 entities
      :3400 flags    :3401 confidence_factors          :3402 recommended_action
      :3449 risk_data.get("llm_prompt")     :3510 risk_data.get("raw_response","")
  risk_data is never iterated, never serialised, never logged and never handed
  to a collaborator as a dict (the audit call, the LLMInteraction row and the
  completion log all read the EVENT). So renaming the "risk_score" key is
  value-preserving: both of its readers fall back to the very value that was
  stored (50), including the fire override at :3365 which then writes 100 over
  it; and renaming "risk_level" is value-preserving because its only reader
  (:3392) falls back to "medium". Unreachable-operand / default-absorbed
  equivalence. The two tests below run a variant carrying the exact one-line
  edit and require an IDENTICAL observable transcript (Event fields, added
  rows, SQL text, audit kwargs, metric args, every log record) to shipped over
  8 scenarios, one of which drives the fire override that reads "risk_score".

OCCURRENCE-TWIN RULE — settled from mutmut's span bodies, not text heuristics:
  156 / 189 ("duration_ms" -> "DURATION_MS"): 156 = SUCCESS site :3329,
      189 = FAILURE site :3344. Both keys are in this chunk; both
      killed_by_draft.
  234 / 326 (llm_prompt=... -> None): 234 = EVENT site :3395,
      326 = create_partial_audit site :3449. Both in this chunk.
  249 / 330 (llm_prompt kwarg removed): 249 = EVENT site, 330 = AUDIT site.
      Both in this chunk.
  (chunk-10's docstrings attribute 234/249 to the audit site; the span map
  says they are the EVENT site — test_event_construction_passes_risk_data_
  through is their actual killer. The verdicts here follow the span map.)
  This file's fire-override tests are an INDEPENDENT second witness for the
  whole fallback-dict-consuming region, all three twin pairs included.

AUTOSPEC NOTE (WP4.2 ratchet): the only unittest.mock patch CALL SITE here is
`get_audit_service` below and it carries autospec=True. The variant
installations are not mock-patch sites — they are direct __dict__ writes of the
function under test, for which autospec is unsatisfiable by construction (the
spec would be built FROM the function being replaced). Collaborators
(get_session, logger, time, metrics, _call_llm, ...) are installed on the
module dict of BOTH the shipped module and the variant's own globals snapshot,
so shipped and variant see exactly the same collaborators.

READ-ONLY: nothing under the repo or /home/lanes is written; variant sources
are built in memory from the shipped text.

GREEN CHECK
  cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
      "/tmp/wp-batch25/parts/test_batch25_dead-10-1.py" \
      -p no:cacheprovider -o addopts= -q
"""

from __future__ import annotations

import asyncio
import datetime as dt
import functools
import os
import sys
import types
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

# --- minimum env, values copied from backend/tests/unit/conftest.py ----------
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("API_KEY_ENABLED", "true")  # pragma: allowlist secret
os.environ.setdefault("API_KEYS", '["test-unit-api-key-12345"]')  # pragma: allowlist secret

REPO = str(__import__("pathlib").Path(__file__).resolve().parents[4])
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import backend.services.nemotron_analyzer as SHIP
from backend.services.nemotron_analyzer import NemotronAnalyzer

SHIP_PATH = REPO + "/backend/services/nemotron_analyzer.py"
SHIP_LINES = open(SHIP_PATH).read().split("\n")  # nosemgrep: path-traversal-open
FP_FIRST = next(
    i
    for i, ln in enumerate(SHIP_LINES)
    if ln.startswith("    async def analyze_detection_fast_path")
)
FP_LAST = next(
    j
    for j in range(FP_FIRST + 1, len(SHIP_LINES))
    if SHIP_LINES[j].startswith("    async def ") or SHIP_LINES[j].startswith("    def ")
)
SHIP_FP = NemotronAnalyzer.analyze_detection_fast_path

DET_TIME = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC)
DETECT_ID = 4242
EVENT_ID = 555
AUDIT_ID = 4242
SANITIZED = "SANITIZED-ERR"

# Shipped values measured by /tmp/wp-batch25/probes/probe_dead101.py.
FALLBACK_SUMMARY = "Analysis unavailable - LLM service error"
FALLBACK_REASONING = "Failed to analyze detection due to service error"
FIRE_SUMMARY = "FIRE DETECTED - " + FALLBACK_SUMMARY
FIRE_REASONING = (
    "Fire detected (confidence: 83%). Risk overridden from 50 to 100. " + FALLBACK_REASONING
)


# =============================================================================
# variant machinery (in memory; the repo is never written)
# =============================================================================
@functools.lru_cache(maxsize=16)
def variant(old: str, new: str, anchor: str):
    """(method, globals-snapshot-dict) for the shipped function with ONE
    textual edit applied — the same single-line edit mutmut applied.

    `anchor` locates the region (searched inside the fast-path body only), then
    the next line whose stripped text == `old` is replaced. The module copy is
    compiled with a __dict__ snapshot, so the variant's globals are an
    independent dict; run() installs its collaborators into that dict too, so
    the variant and the shipped method see identical collaborators.
    """
    lines = list(SHIP_LINES)
    idx = None
    for i in range(FP_FIRST, FP_LAST):
        if anchor in lines[i]:
            idx = i
            break
    assert idx is not None, "anchor not in fast-path body: %r" % anchor
    while SHIP_LINES[idx].strip() != old:
        idx += 1
        assert idx < FP_LAST, "target line not found: %r" % old
    assert SHIP_LINES[idx].count(old) == 1, old
    lines[idx] = SHIP_LINES[idx].replace(old, new)
    assert lines != SHIP_LINES
    ns = dict(SHIP.__dict__)
    ns.pop("__name__", None)
    exec(compile("\n".join(lines), SHIP_PATH, "exec"), ns)  # nosemgrep: dangerous-eval
    return ns["NemotronAnalyzer"].analyze_detection_fast_path, ns


# =============================================================================
# scenario machinery (every expectation probed against SHIPPED)
# =============================================================================
class FakeTime:
    """Deterministic time.time(): +1.0 per call.

    Both LLM branches read time exactly 6 times (:3197 analysis_start,
    :3296 llm_start, then :3320/:3321 or :3333/:3334, then :3567/:3568), so
    every transcript lands on llm 1000 ms / 2.0 s and total 4000 ms / 5.0 s —
    which makes two transcripts comparable by value."""

    def __init__(self):
        self.n = 0

    def time(self):
        self.n += 1
        return 1000.0 + self.n


def _freeze(obj):
    """Value-freeze so transcripts compare structurally; non-primitives
    collapse to their type name (object identity is not an observable here)."""
    if isinstance(obj, dict):
        return {k: _freeze(v) for k, v in sorted(obj.items(), key=str)}
    if isinstance(obj, (list, tuple)):
        return [_freeze(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return "<%s>" % type(obj).__name__


class Logger:
    def __init__(self):
        self.calls = []

    def _rec(self, level):
        def go(msg, *a, **kw):
            self.calls.append((level, msg, _freeze(kw)))

        return go

    def __getattr__(self, name):
        return self._rec(name)


class Spy:
    def __init__(self, value=None):
        self.value = value
        self.args = []

    def __call__(self, *a, **kw):
        self.args.append([list(a), _freeze(kw)])
        return self.value


class AsyncSpy(Spy):
    async def __call__(self, *a, **kw):
        self.args.append([list(a), _freeze(kw)])
        return self.value


class AsyncRaise(Spy):
    async def __call__(self, *a, **kw):
        self.args.append([list(a), _freeze(kw)])
        raise self.value


class Boom(Exception):
    def __init__(self, msg="llm down", raw=None):
        super().__init__(msg)
        if raw is not None:
            self.raw_completion = raw


class _Ctx:
    def __init__(self, sess):
        self.sess = sess

    async def __aenter__(self):
        return self.sess

    async def __aexit__(self, *exc):
        return False


class _Session:
    """Records add()/execute(); flush() assigns PKs the way a real flush does
    (the shipped body depends on event.id being a real int downstream)."""

    def __init__(self, results=()):
        self.results = list(results)
        self.added = []
        self.executed = []

    async def execute(self, stmt, *a, **kw):
        try:
            self.executed.append(str(stmt))
        except Exception as exc:  # pragma: no cover - shows up as a transcript diff
            self.executed.append("<unprintable:%s>" % type(exc).__name__)
        return types.SimpleNamespace(
            scalar_one_or_none=lambda: self.results.pop(0) if self.results else None
        )

    async def flush(self, *a, **kw):
        for obj in self.added:
            if getattr(obj, "id", "unset") in (None, "unset"):
                try:
                    obj.id = EVENT_ID
                except Exception:  # pragma: no cover - defensive
                    pass

    def add(self, obj):
        self.added.append(obj)


class Fire:
    has_fire = True
    highest_confidence = 0.83


class NoFire:
    has_fire = False
    highest_confidence = 0.10


FIRE_MAP = {"fire": Fire(), "nofire": NoFire()}


class EnrichResult:
    """Only to_storage_dict, the two household match lists and
    smoke_fire_detection are read off this object by the shipped body."""

    def __init__(self, storage=None, fire=None, persons=None, vehicles=None):
        self._storage = {} if storage is None else storage
        self.person_household_matches = persons
        self.vehicle_household_matches = vehicles
        self.smoke_fire_detection = FIRE_MAP[fire] if fire else None

    def to_storage_dict(self, det_id):
        return self._storage


def make_camera():
    return types.SimpleNamespace(id="cam-1", name="Front Door")


def make_detection():
    return types.SimpleNamespace(
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


def run(
    *,
    llm_exc=None,
    risk_data=None,
    fire=None,
    storage=None,
    persons=None,
    vehicles=None,
    variant_pair=None,
):
    """Drive one analyze_detection_fast_path("cam-1", DETECT_ID) and return the
    observable transcript. `variant_pair=(method, globals_dict)` runs the
    variant instead of the shipped method, with the SAME collaborators."""
    log = Logger()
    fake_time = FakeTime()
    rpe = Spy()
    san = Spy(SANITIZED)
    observe_ai = Spy()
    observe_stage = Spy()
    rec_created = Spy()
    rec_camera = Spy()
    set_idem = AsyncSpy()
    enqueue = AsyncSpy()
    snapshot = Spy({"SNAP": 1})
    sources = Spy({"SRC": 2})
    audit_service = types.SimpleNamespace(
        create_partial_audit=Spy(types.SimpleNamespace(id=AUDIT_ID))
    )

    an = NemotronAnalyzer.__new__(NemotronAnalyzer)
    an._redis = types.SimpleNamespace()
    s1 = _Session([make_camera(), make_detection()])
    s2 = _Session([])
    sessions = [s1, s2]
    cur = {"i": 0}

    def get_session():
        i = cur["i"]
        cur["i"] += 1
        return _Ctx(sessions[i] if i < len(sessions) else sessions[-1])

    er = EnrichResult(storage=storage, fire=fire, persons=persons, vehicles=vehicles)
    tracking = types.SimpleNamespace(has_data=True, data=er)

    async def call_llm(*a, **kw):
        if llm_exc is not None:
            raise llm_exc
        return dict(risk_data or {})

    an._check_idempotency = AsyncSpy(None)
    an._get_existing_event = AsyncSpy(None)
    an._format_detections = lambda dets: "FMT"
    an._get_enriched_context = AsyncSpy({"ctx": 1})
    an._get_recent_scene_changes = AsyncSpy([])
    an._get_enrichment_result_from_data = AsyncSpy(tracking)
    an._call_llm = call_llm
    an._set_idempotency = set_idem
    an._enqueue_for_evaluation = enqueue
    an._broadcast_event = AsyncSpy(None)
    an._trigger_event_created_webhook = AsyncSpy(None)
    an._get_facade = lambda: types.SimpleNamespace(
        get_cache_service=AsyncRaise(RuntimeError("no facade"))
    )
    an._build_enrichment_snapshot = snapshot
    an._build_context_sources = sources

    swapped = {
        "get_session": get_session,
        "logger": log,
        "time": fake_time,
        "record_pipeline_error": rpe,
        "sanitize_error": san,
        "observe_ai_request_duration": observe_ai,
        "observe_stage_duration": observe_stage,
        "record_event_created": rec_created,
        "record_event_by_camera": rec_camera,
    }
    targets = [SHIP.__dict__]
    if variant_pair is not None:
        targets.append(variant_pair[1])
    olds = []
    for ns in targets:
        olds.append({k: ns.get(k) for k in swapped})
        for k, v in swapped.items():
            ns[k] = v
    if variant_pair is not None:
        NemotronAnalyzer.analyze_detection_fast_path = variant_pair[0]
    audit_patch = patch(
        "backend.services.pipeline_quality_audit_service.get_audit_service",
        autospec=True,
        return_value=audit_service,
    )
    audit_patch.start()

    error = None
    event = None
    try:
        event = asyncio.run(an.analyze_detection_fast_path("cam-1", DETECT_ID))
    except Exception as exc:
        error = "%s: %s" % (type(exc).__name__, exc)
    finally:
        audit_patch.stop()
        for ns, old in zip(targets, olds):
            ns.update(old)
        NemotronAnalyzer.analyze_detection_fast_path = SHIP_FP

    event_fields = None
    if event is not None:
        event_fields = {}
        for f in (
            "batch_id",
            "camera_id",
            "risk_score",
            "risk_level",
            "summary",
            "reasoning",
            "llm_prompt",
            "reviewed",
            "is_fast_path",
            "entities",
            "flags",
            "confidence_factors",
            "recommended_action",
            "id",
        ):
            try:
                event_fields[f] = _freeze(getattr(event, f))
            except AttributeError:
                event_fields[f] = "<UNSET>"
        for f in ("started_at", "ended_at"):
            try:
                event_fields[f] = repr(getattr(event, f))
            except AttributeError:
                event_fields[f] = "<UNSET>"

    rows = [x for x in s2.added if type(x).__name__ == "LLMInteraction"]
    llm_row = None
    if rows:
        llm_row = {
            f: _freeze(getattr(rows[0], f, "<UNSET>"))
            for f in (
                "event_id",
                "raw_response",
                "enrichment_snapshot",
                "household_matches",
                "context_sources",
            )
        }

    return {
        "error": error,
        "event": event_fields,
        "added_types": [type(x).__name__ for x in s2.added],
        "llm_interaction": llm_row,
        "audit_call": audit_service.create_partial_audit.args,
        "session1_sql": s1.executed,
        "session2_sql": s2.executed,
        "logs": log.calls,
        "record_pipeline_error": rpe.args,
        "sanitize_error": san.args,
        "observe_ai_request_duration": observe_ai.args,
        "observe_stage_duration": observe_stage.args,
        "record_event_created": rec_created.args,
        "record_event_by_camera": rec_camera.args,
        "set_idempotency": set_idem.args,
        "enqueue_for_evaluation": enqueue.args,
        "snapshot_call": snapshot.args,
        "sources_call": sources.args,
    }


def logged(trans, level, msg):
    return [kw for lv, m, kw in trans["logs"] if lv == level and m == msg]


# =============================================================================
# INDEPENDENT WITNESS — the fire-override region
# =============================================================================
class TestFireOverrideRegion:
    """This chunk's keys cluster in the NEM-5566 fire-override block
    (:3360-3377) and in the Event / audit kwargs that consume the LLM-failure
    fallback dict. No existing battery pushes the fallback dict THROUGH the
    override (chunk-10 fails the LLM with enrichment absent, chunk-11 never
    fails the LLM at all), so these tests are the second witness for every key
    in that region — all three occurrence-twin pairs included."""

    def test_llm_failure_without_fire_pins_fallback_flow(self):
        """Second witness for 203, 206, 207, 208, 209, 210 (canned summary /
        reasoning literals), 211, 212, 213, 215, 219, 220, 221 (raw_response
        getattr shape), 233, 248 (reasoning kwarg -> None / removed), 234, 249
        (llm_prompt kwarg -> None / removed, EVENT occurrence), 326, 330
        (llm_prompt, AUDIT occurrence), 237, 238, 239, 240, 252, 253, 254, 255
        (advanced-risk kwargs), 257, 259, 262, 264, 266, 269, 270, 272, 274,
        277, 278, 279 (get() default literals), 170, 171, 172
        (record_pipeline_error argument), 173, 174 (sanitize_error call), 175,
        181, 182, 183 (error message literal), 176, 179, 177, 180, 192 (extra
        dict / exc_info), 190, 191 ("error" key spelling) and 189 (FAILURE-site
        "duration_ms" twin)."""
        t = run(llm_exc=Boom("t", raw="RAWCOMP"))
        assert t["error"] is None, t["error"]
        ev = t["event"]
        assert ev["batch_id"] == "fast_path_4242"
        assert ev["camera_id"] == "cam-1"
        assert ev["id"] == EVENT_ID
        assert ev["risk_score"] == 50
        assert ev["risk_level"] == "medium"
        assert ev["summary"] == FALLBACK_SUMMARY
        assert ev["reasoning"] == FALLBACK_REASONING
        assert ev["llm_prompt"] is None
        assert ev["entities"] is None
        assert ev["flags"] is None
        assert ev["confidence_factors"] is None
        assert ev["recommended_action"] is None
        assert ev["reviewed"] is False
        assert ev["is_fast_path"] is True
        assert ev["started_at"] == repr(DET_TIME)
        assert ev["ended_at"] == repr(DET_TIME)
        assert t["added_types"] == ["Event", "SimpleNamespace", "LLMInteraction"]
        assert t["llm_interaction"]["raw_response"] == "RAWCOMP"
        assert t["llm_interaction"]["event_id"] == EVENT_ID
        assert t["llm_interaction"]["household_matches"] is None
        assert t["audit_call"] == [
            [
                [],
                {
                    "event_id": EVENT_ID,
                    "llm_prompt": None,
                    "enriched_context": {"ctx": 1},
                    "enrichment_result": "<EnrichResult>",
                },
            ]
        ]
        assert t["enqueue_for_evaluation"] == [[[EVENT_ID, 50], {}]]
        assert t["set_idempotency"] == [[["fast_path_4242", EVENT_ID], {}]]
        assert t["record_pipeline_error"] == [[["nemotron_fast_path_error"], {}]]
        assert len(t["sanitize_error"]) == 1
        assert t["sanitize_error"][0][1] == {}
        (kw,) = logged(t, "error", "LLM analysis failed for fast path detection")
        assert kw == {
            "extra": {
                "camera_id": "cam-1",
                "detection_id": DETECT_ID,
                "duration_ms": 1000,
                "error": SANITIZED,
            },
            "exc_info": True,
        }
        assert logged(t, "debug", "Fast path LLM analysis completed for detection 4242") == []
        (done,) = logged(t, "info", "Batch analysis completed")
        assert done["extra"] == {
            "event_id": EVENT_ID,
            "risk_score": 50,
            "risk_level": "medium",
            "duration_ms": 4000,
            "detection_count": 1,
            "is_fast_path": True,
        }
        assert t["observe_ai_request_duration"] == [[["nemotron", 2.0], {}]]
        assert t["observe_stage_duration"] == [[["analyze", 5.0], {}]]
        assert t["record_event_by_camera"] == [[["cam-1", "Front Door"], {}]]
        assert t["record_event_created"] == [[[], {}]]
        assert any(
            sql.startswith("INSERT INTO event_detections (event_id, detection_id, created_at)")
            for sql in t["session2_sql"]
        ), t["session2_sql"]

    def test_fire_override_reads_the_fallback_dict(self):
        """Kills any key-mutation that would stop the override from READING
        the fallback dict: 203, 206, 207, 208, 209, 210 (the summary/reasoning
        literals the override interpolates), 257, 259, 262 (risk_score default
        literals at :3365/:3391), 264, 266, 269, 270 (risk_level default at
        :3392), 233, 248 (reasoning kwarg) — plus twins 234/326 and 249/330 and
        215, 221 (raw_response default). Shipped: score 50 -> 100, level ->
        critical, summary prefixed with "FIRE DETECTED - ", and the override
        sentence carries `from 50 to 100`, i.e. the 50 read out of the fallback
        dict at :3365."""
        t = run(llm_exc=Boom("t", raw="RAWCOMP"), fire="fire", storage={"plates": ["A"]})
        ev = t["event"]
        assert ev["risk_score"] == 100
        assert ev["risk_level"] == "critical"
        assert ev["summary"] == FIRE_SUMMARY
        assert ev["reasoning"] == FIRE_REASONING
        assert "from 50 to 100" in ev["reasoning"]
        assert ev["llm_prompt"] is None
        assert t["llm_interaction"]["raw_response"] == "RAWCOMP"
        assert t["audit_call"] == [
            [
                [],
                {
                    "event_id": EVENT_ID,
                    "llm_prompt": None,
                    "enriched_context": {"ctx": 1},
                    "enrichment_result": "<EnrichResult>",
                },
            ]
        ]
        assert t["enqueue_for_evaluation"] == [[[EVENT_ID, 100], {}]]
        (done,) = logged(t, "info", "Batch analysis completed")
        assert done["extra"]["risk_score"] == 100
        assert done["extra"]["risk_level"] == "critical"
        assert any(
            sql.startswith("UPDATE detections SET enrichment_data") for sql in t["session2_sql"]
        ), t["session2_sql"]

    def test_fire_override_skipped_when_has_fire_false(self):
        """Second witness for the guard operands the chunk's literals feed
        (203, 206, 257, 264): with has_fire False the fallback flows through
        unchanged, so the equality asserts in the tests above remain the
        discriminating ones, and this test pins that the override does NOT run."""
        t = run(llm_exc=Boom("t"), fire="nofire")
        ev = t["event"]
        assert ev["risk_score"] == 50
        assert ev["risk_level"] == "medium"
        assert ev["summary"] == FALLBACK_SUMMARY
        assert ev["reasoning"] == FALLBACK_REASONING
        assert t["enqueue_for_evaluation"] == [[[EVENT_ID, 50], {}]]
        assert t["llm_interaction"]["raw_response"] == ""

    def test_success_with_fire_uses_llm_score_as_original(self):
        """Second witness for 257, 259, 262 and 264, 266, 269, 270 on the
        SUCCESS side of the override: with risk_data from the LLM the override
        reports THAT score (30), not any fallback default, so a changed
        `.get(..., default)` literal at :3365/:3391 is observable."""
        t = run(
            fire="fire",
            risk_data={
                "risk_score": 30,
                "risk_level": "low",
                "summary": "smoke?",
                "reasoning": "R3",
                "llm_prompt": "LP3",
            },
        )
        ev = t["event"]
        assert ev["risk_score"] == 100
        assert ev["risk_level"] == "critical"
        assert ev["summary"] == "FIRE DETECTED - smoke?"
        assert "Risk overridden from 30 to 100. R3" in ev["reasoning"]
        assert ev["llm_prompt"] == "LP3"
        assert t["audit_call"] == [
            [
                [],
                {
                    "event_id": EVENT_ID,
                    "llm_prompt": "LP3",
                    "enriched_context": {"ctx": 1},
                    "enrichment_result": "<EnrichResult>",
                },
            ]
        ]

    def test_success_without_fire_passes_risk_data_through(self):
        """Second witness for the Event-kwarg twins 234/326 and 249/330 plus
        237, 238, 239, 240, 252, 253, 254, 255 and 156 (SUCCESS-site
        "duration_ms" twin): full risk_data must reach Event, the audit call
        and the success debug log verbatim."""
        t = run(risk_data=FULL_RISK)
        ev = t["event"]
        assert (ev["risk_score"], ev["risk_level"]) == (71, "high")
        assert (ev["summary"], ev["reasoning"]) == ("S", "R")
        assert ev["llm_prompt"] == "LP"
        assert (ev["entities"], ev["flags"]) == (["e"], ["f"])
        assert ev["confidence_factors"] == ["c"]
        assert ev["recommended_action"] == "RA"
        assert t["llm_interaction"]["raw_response"] == "RR"
        assert t["audit_call"] == [
            [
                [],
                {
                    "event_id": EVENT_ID,
                    "llm_prompt": "LP",
                    "enriched_context": {"ctx": 1},
                    "enrichment_result": "<EnrichResult>",
                },
            ]
        ]
        (dbg,) = logged(t, "debug", "Fast path LLM analysis completed for detection 4242")
        assert dbg == {
            "extra": {"camera_id": "cam-1", "detection_id": DETECT_ID, "duration_ms": 1000}
        }


# =============================================================================
# EQUIVALENCE WITNESSES — 194, 195, 197, 198
# =============================================================================
SCENARIOS = [
    ("llm_fail_no_fire", dict(llm_exc=Boom("t", raw="RAWCOMP"))),
    (
        "llm_fail_fire",
        dict(llm_exc=Boom("t", raw="RAWCOMP"), fire="fire", storage={"plates": ["A"]}),
    ),
    (
        "llm_fail_fire_household",
        dict(llm_exc=Boom("t"), fire="fire", persons=["p1"], vehicles=["v1"]),
    ),
    ("llm_fail_enrich_only", dict(llm_exc=Boom("t"), storage={}, vehicles=["v1"])),
    (
        "ok_fire_low_score",
        dict(
            fire="fire",
            risk_data={
                "risk_score": 30,
                "risk_level": "low",
                "summary": "smoke?",
                "reasoning": "R3",
                "llm_prompt": "LP3",
            },
        ),
    ),
    ("ok_full", dict(risk_data=FULL_RISK)),
    ("ok_empty_risk", dict(risk_data={})),
    (
        "ok_fire_summary_mentions_fire",
        dict(
            fire="fire",
            risk_data={
                "risk_score": 12,
                "risk_level": "low",
                "summary": "FIRE visible",
                "reasoning": "R2",
            },
        ),
    ),
]


def _transcripts(pair=None):
    return {name: run(variant_pair=pair, **scen) for name, scen in SCENARIOS}


def _first_diff(a, b, path=""):
    if type(a) is not type(b):
        return "%s: type %s vs %s" % (path, type(a).__name__, type(b).__name__)
    if isinstance(a, dict):
        if set(a) != set(b):
            return "%s: key sets %s vs %s" % (path, sorted(a), sorted(b))
        for k in a:
            d = _first_diff(a[k], b[k], "%s.%s" % (path, k))
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return "%s: len %d vs %d" % (path, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            d = _first_diff(x, y, "%s[%d]" % (path, i))
            if d:
                return d
        return None
    return None if a == b else "%s: %r != %r" % (path, a, b)


class TestFallbackKeyRenameEquivalence:
    """194/195/197/198 each rename ONE key of the LLM-failure fallback literal
    (:3350 "risk_score", :3351 "risk_level") and are ruled EQUIVALENT: the
    stored value is recovered verbatim by every reader's .get() DEFAULT — which
    equals the stored value (:3365 and :3391 default 50; :3392 default
    "medium") — and risk_data is never iterated, serialised, logged or passed
    on as a dict. Each test applies mutmut's exact one-line edit and requires
    the FULL observable transcript to be identical to shipped across 8
    scenarios, one of which drives the fire override that reads "risk_score"
    at :3365 (so the equivalence is proven at the only read that could tell
    the difference, not merely asserted)."""

    def test_risk_score_key_rename_is_transparent(self):
        """Witness for 194 ("XXrisk_scoreXX") and 195 ("RISK_SCORE") at :3350.
        EQUIVALENT: readers :3365 / :3391 both default to 50 == stored value."""
        shipped = _transcripts()
        for new_key in ("XXrisk_scoreXX", "RISK_SCORE"):
            pair = variant('"risk_score": 50,', '"%s": 50,' % new_key, "risk_data = {")
            got = _transcripts(pair)
            for name in shipped:
                d = _first_diff(shipped[name], got[name], name)
                assert d is None, "%s -> %s" % (new_key, d)
            # explicit: the default-absorbed value still drives the override
            assert got["llm_fail_fire"]["event"]["risk_score"] == 100
            assert "from 50 to 100" in got["llm_fail_fire"]["event"]["reasoning"]
            assert got["llm_fail_no_fire"]["event"]["risk_score"] == 50
            assert got["ok_fire_low_score"]["event"]["reasoning"].count("from 30 to 100") == 1

    def test_risk_level_key_rename_is_transparent(self):
        """Witness for 197 ("XXrisk_levelXX") and 198 ("RISK_LEVEL") at :3351.
        EQUIVALENT: the only reader (:3392) defaults to "medium" == stored
        value; :3367 is an unconditional write, not a read."""
        shipped = _transcripts()
        for new_key in ("XXrisk_levelXX", "RISK_LEVEL"):
            pair = variant('"risk_level": "medium",', '"%s": "medium",' % new_key, "risk_data = {")
            got = _transcripts(pair)
            for name in shipped:
                d = _first_diff(shipped[name], got[name], name)
                assert d is None, "%s -> %s" % (new_key, d)
            assert got["llm_fail_no_fire"]["event"]["risk_level"] == "medium"
            assert got["llm_fail_fire"]["event"]["risk_level"] == "critical"
            assert got["ok_full"]["event"]["risk_level"] == "high"

    def test_witness_machinery_is_sensitive_control(self):
        """NEGATIVE CONTROL against a vacuous witness: the SAME machinery and
        the SAME one-line-edit mechanism, applied to an edit that is NOT
        equivalent — :3391's `risk_data.get("risk_score", 50)` default 50 -> 51
        (mutant 262, which the red-check marks killed) — MUST produce a
        transcript diff. If this ever passes with no diff, the four equivalence
        verdicts above are worthless and must be re-derived."""
        shipped = _transcripts()
        pair = variant(
            'risk_score=risk_data.get("risk_score", 50),',
            'risk_score=risk_data.get("risk_score", 51),',
            'risk_score=risk_data.get("risk_score", 50),',
        )
        got = _transcripts(pair)
        d = _first_diff(shipped["ok_empty_risk"], got["ok_empty_risk"], "ok_empty_risk")
        assert d is not None, "control edit produced NO transcript diff"
        assert "risk_score" in d, d
        # and the four renamed-key edits still show NO diff, side by side
        for old, new in (
            ('"risk_score": 50,', '"RISK_SCORE": 50,'),
            ('"risk_level": "medium",', '"RISK_LEVEL": "medium",'),
        ):
            p2 = variant(old, new, "risk_data = {")
            g2 = _transcripts(p2)
            for name in shipped:
                assert _first_diff(shipped[name], g2[name], name) is None
