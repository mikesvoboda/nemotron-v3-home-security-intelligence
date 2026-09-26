"""Chunk-19 kill battery: enrichment_pipeline mutation survivors (120 keys).

Targets (shipped source, PRISTINE workspace copy / HEAD):
  - EnrichmentPipeline._safe_clip_scene_classify   (shipped lines 3543-3588)
  - EnrichmentPipeline._safe_clip_threat_match     (shipped lines 3590-3640)
  - EnrichmentPipeline._safe_detect_smoke_fire     (shipped lines 3266-3333)
  - EnrichmentPipeline._detect_threats_via_service (shipped lines 5167-5281)

Every assertion below was PROBE-derived from shipped behaviour
(/tmp/wp-ep/probes/c19/probe1.py, probe2.py, probe3.py — outputs quoted in
verdicts_19.json), including the shipped oddities those probes measured:

  * the two CLIP helpers call ``record_enrichment_model_call`` BEFORE the
    try-block and their catch-all handler emits a WARNING whose ``extra`` is
    exactly {service, error_type, duration_ms} with ``duration_ms`` =
    ``int(duration * 1000)``;
  * ``_safe_detect_smoke_fire`` resets the per-camera smoke counter in THREE
    distinct places and the no-smoke/no-fire branch (shipped line 3327/3328)
    both resets it AND returns ``result if result.has_detections else None``
    (so a non-smoke/non-fire detection object is returned while an empty
    result object returns None — both pinned here, as shipped);
  * ``_detect_threats_via_service`` routes ValueError/KeyError/TypeError into a
    logger.error("Threat detection parse error", ..., exc_info=True) whose
    ``extra`` is {service, error_type} only — no duration_ms (unlike the CLIP
    handlers) — and the catch-all handler instead logs
    ``f"Threat detection unexpected error: {sanitize_error(e)}"``;
  * the smoke/fire loader call is pinned as the shipped positional+keyword
    shape ``detect_smoke_fire(model, image, confidence_threshold=0.5)`` with the
    model name string "smoke-fire-yolov8n" and camera key fallback "_default".

Calls go through the LIVE class attribute (``M.EnrichmentPipeline._fn``) and
module-level collaborators are patched through that function's own ``__globals__``
— MEASURED harness fact (chunk 11): the ep_plugin swap exec's the variant body
in a COPY of the module dict, so ``patch.object(M, name, ...)`` is invisible to a
swapped mutant while ``patch.dict(fn.__globals__, ...)`` is observed by both
shipped and mutant code.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from unittest.mock import AsyncMock, MagicMock, call, patch

from PIL import Image

import backend.services.enrichment_pipeline as M
import backend.services.clip_client as CLIP_MODULE
from backend.services.enrichment_pipeline import EnrichmentPipeline
from backend.services.smoke_fire_loader import SmokeFireDetection, SmokeFireDetectionResult

MODLOG = "backend.services.enrichment_pipeline"

SCENE = "_safe_clip_scene_classify"
THREAT = "_safe_clip_threat_match"
SMOKE = "_safe_detect_smoke_fire"
THREATS = "_detect_threats_via_service"

IMAGE = Image.new("RGB", (8, 8), "grey")
MODEL = "MODEL-SENTINEL"

# scripted clock values -> deterministic duration == 2.0s, duration_ms == 2000
T0, T1 = 1000.0, 1002.0


# --------------------------------------------------------------------- stubs #
class FakeTime:
    """``time`` stand-in with scripted perf_counter()/monotonic() readings.

    Repeats the last scripted value when called more often than scripted, so a
    mutation that reorders/extra-calls the clock never hangs or flakes.
    """

    def __init__(self, perf=(), mono=()) -> None:
        self._perf = list(perf)
        self._mono = list(mono)
        self._lp = 0.0
        self._lm = 0.0

    def perf_counter(self) -> float:
        if self._perf:
            self._lp = self._perf.pop(0)
        return self._lp

    def monotonic(self) -> float:
        if self._mono:
            self._lm = self._mono.pop(0)
        return self._lm

    def time(self) -> float:
        return 0.0

    def sleep(self, _seconds: float) -> None:
        return None


class _LoadCM:
    """Stand-in for ``async with model_manager.load(name) as model``."""

    def __init__(self, result=MODEL, exc: BaseException | None = None) -> None:
        self.result = result
        self.exc = exc

    async def __aenter__(self):
        if self.exc is not None:
            raise self.exc
        return self.result

    async def __aexit__(self, *exc_info) -> bool:
        return False


class ClipStub:
    """CLIPClient stand-in: both endpoints are AsyncMocks with measured returns."""

    def __init__(self, exc: BaseException | None = None) -> None:
        self.scores = {"normal activity": 0.7, "trespassing": 0.2}
        self.top = "normal activity"
        self.sims = {
            "a person checking door handles": 0.9,
            "a person walking a dog": 0.4,
            "a person crouching behind a car": 0.1,
            "extra": 0.5,
        }
        if exc is not None:
            self.classify = AsyncMock(side_effect=exc)
            self.batch_similarity = AsyncMock(side_effect=exc)
        else:
            self.classify = AsyncMock(return_value=(self.scores, self.top))
            self.batch_similarity = AsyncMock(return_value=self.sims)


def pipeline(load_exc: BaseException | None = None) -> EnrichmentPipeline:
    mm = MagicMock()
    mm.load = MagicMock(return_value=_LoadCM(result=MODEL, exc=load_exc))
    return EnrichmentPipeline(model_manager=mm)


def fn_globals(method: str) -> dict:
    """The name-resolution dict of the LIVE function object (mutant-aware).

    Pristine: ``M.__dict__``. Ep_plugin swap: the exec'd variant's snapshot
    dict (freshly compiled — no ``__wrapped__``). Mutants-tree re-bank:
    MEASURED 2026-09-26 — mutmut 3.8 trampoline-wraps every function and the
    wrapper's ``__globals__`` is mutmut's OWN module dict, invisible to the
    shipped code; ``__wrapped__`` unwraps to the implementation whose globals
    ARE ``M.__dict__`` — so unwrap only when that identity holds.
    """
    f = getattr(M.EnrichmentPipeline, method)
    if f.__globals__ is not M.__dict__:
        w = getattr(f, "__wrapped__", None)
        if w is not None and w.__globals__ is M.__dict__:
            return M.__dict__
    return f.__globals__


def live(method: str):
    """The LIVE (possibly mutant-swapped) bound-able function object."""
    return getattr(M.EnrichmentPipeline, method)


def mod_records(caplog) -> list:
    return [r for r in caplog.records if r.name == MODLOG]


def extra_values(records: list, key: str) -> list:
    """MEASURED-safe extra read: getattr over ALL matching records."""
    return [getattr(r, key, None) for r in records]


@contextlib.contextmanager
def metrics(method: str, *, mono: bool = False):
    """Patch the module-level clock + prometheus helpers a target calls."""
    subs = {
        "record_enrichment_model_call": MagicMock(),
        "observe_enrichment_model_duration": MagicMock(),
        "record_enrichment_model_error": MagicMock(),
        "time": FakeTime(mono=[T0, T1]) if mono else FakeTime(perf=[T0, T1]),
    }
    with patch.dict(fn_globals(method), subs):
        yield subs


# ==================================================================== SCENE ==
def _run_scene(caplog, clip_exc: BaseException | None = None):
    p = pipeline()
    clip = ClipStub(exc=clip_exc)
    getter = MagicMock(return_value=clip)
    with (
        caplog.at_level(logging.DEBUG, logger=MODLOG),
        metrics(SCENE) as m,
        patch.object(CLIP_MODULE, "get_clip_client", getter),
    ):
        out = asyncio.run(live(SCENE)(p, IMAGE))
    return out, m, clip


def test_c19_scene_success_returns_scores_and_pins_metrics(caplog):
    """Shipped success path (lines 3558-3575) - guard pin for the CLIP pair."""
    out, m, clip = _run_scene(caplog)
    assert out == ({"normal activity": 0.7, "trespassing": 0.2}, "normal activity")
    assert m["record_enrichment_model_call"].call_args_list == [call("clip-scene-classify")]
    assert m["observe_enrichment_model_duration"].call_args_list == [
        call("clip-scene-classify", 2.0)
    ]
    assert m["record_enrichment_model_error"].call_args_list == []
    args = clip.classify.await_args.args
    assert len(args) == 2, f"shipped call shape is (image, labels); got {args!r}"
    assert args[0] is IMAGE
    assert args[1] is M.CLIP_SCENE_LABELS
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert recs[0].levelno == logging.DEBUG
    assert recs[0].getMessage() == "CLIP scene classification: top='normal activity' (0.70)"


def test_c19_scene_error_handler_metrics(caplog):
    """scene mutmut_16/17/18 (observe site 3578) + 19/20/21 (error site 3579)."""
    out, m, _clip = _run_scene(caplog, RuntimeError("clip-down"))
    assert out is None, "shipped: the catch-all handler returns None"
    assert m["record_enrichment_model_call"].call_args_list == [call("clip-scene-classify")]
    assert m["observe_enrichment_model_duration"].call_args_list == [
        call("clip-scene-classify", 2.0)
    ]
    assert m["record_enrichment_model_error"].call_args_list == [call("clip-scene-classify")]


def test_c19_scene_error_handler_message_and_service(caplog):
    """scene mutmut_22/24 (msg site 3581), 23/25 (extra site 3582), 26-29 (key/value 3583)."""
    out, _m, _clip = _run_scene(caplog, RuntimeError("clip-down"))
    assert out is None
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert recs[0].levelno == logging.WARNING
    assert recs[0].getMessage() == "CLIP scene classification failed: clip-down"
    assert extra_values(recs, "service") == ["clip-scene-classify"]


def test_c19_scene_error_handler_error_type_and_duration_ms(caplog):
    """scene mutmut_30/31/32 (3584) + 33/34/35/36/37 (3585)."""
    out, _m, _clip = _run_scene(caplog, RuntimeError("clip-down"))
    assert out is None
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert extra_values(recs, "error_type") == ["RuntimeError"]
    assert extra_values(recs, "duration_ms") == [2000]


# ============================================================== THREAT MATCH ==
def _run_threat(caplog, clip_exc: BaseException | None = None):
    p = pipeline()
    clip = ClipStub(exc=clip_exc)
    getter = MagicMock(return_value=clip)
    with (
        caplog.at_level(logging.DEBUG, logger=MODLOG),
        metrics(THREAT) as m,
        patch.object(CLIP_MODULE, "get_clip_client", getter),
    ):
        out = asyncio.run(live(THREAT)(p, IMAGE))
    return out, m, clip


def test_c19_threat_success_pins_client_call_and_result(caplog):
    """threat mutmut_1/2/3 (3606), 4 (3607), 5 (3611), 6-10 (3612)."""
    out, m, clip = _run_threat(caplog)
    assert out == clip.sims, "shipped: the similarity dict is returned unchanged"
    assert m["record_enrichment_model_call"].call_args_list == [call("clip-threat-match")]
    assert m["observe_enrichment_model_duration"].call_args_list == [call("clip-threat-match", 2.0)]
    assert m["record_enrichment_model_error"].call_args_list == []
    args = clip.batch_similarity.await_args.args
    assert len(args) == 2, f"shipped call shape is (image, texts); got {args!r}"
    assert args[0] is IMAGE
    assert args[1] is M.CLIP_THREAT_DESCRIPTIONS
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert recs[0].getMessage().startswith("CLIP threat matches (top 3): ")
    assert extra_values(recs, "match_count") == [4]


def test_c19_threat_error_handler_metrics(caplog):
    """threat mutmut_11/12 (3629) + 13-18 (3630) + 19/20/21 (3631)."""
    out, m, _clip = _run_threat(caplog, RuntimeError("clip-down"))
    assert out is None, "shipped: the catch-all handler returns None"
    assert m["record_enrichment_model_call"].call_args_list == [call("clip-threat-match")]
    assert m["observe_enrichment_model_duration"].call_args_list == [call("clip-threat-match", 2.0)]
    assert m["record_enrichment_model_error"].call_args_list == [call("clip-threat-match")]


def test_c19_threat_error_handler_message_and_service(caplog):
    """threat mutmut_22/24 (3633), 23/25 (3634), 26-29 (3635)."""
    out, _m, _clip = _run_threat(caplog, RuntimeError("clip-down"))
    assert out is None
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert recs[0].levelno == logging.WARNING
    assert recs[0].getMessage() == "CLIP threat matching failed: clip-down"
    assert extra_values(recs, "service") == ["clip-threat-match"]


def test_c19_threat_error_handler_error_type_and_duration_ms(caplog):
    """threat mutmut_30/31/32 (3636) + 33-37 (3637)."""
    out, _m, _clip = _run_threat(caplog, RuntimeError("clip-down"))
    assert out is None
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert extra_values(recs, "error_type") == ["RuntimeError"]
    assert extra_values(recs, "duration_ms") == [2000]


# =============================================================== SMOKE / FIRE ==
def _smoke_result(*kinds: tuple[str, float]) -> SmokeFireDetectionResult:
    return SmokeFireDetectionResult(
        detections=[
            SmokeFireDetection(detection_type=k, confidence=c, bbox=(1.0, 2.0, 3.0, 4.0))
            for k, c in kinds
        ]
    )


def _run_smoke(caplog, result, *, camera_id="cam-1", counts=None, load_exc=None):
    p = pipeline(load_exc=load_exc)
    if counts is not None:
        p._smoke_consecutive_counts = dict(counts)
    detect = AsyncMock(return_value=result)
    with caplog.at_level(logging.DEBUG, logger=MODLOG), metrics(SMOKE, mono=True) as m:
        with patch.dict(fn_globals(SMOKE), {"detect_smoke_fire": detect}):
            out = asyncio.run(live(SMOKE)(p, IMAGE, camera_id))
    return out, m, detect, p


def test_c19_smoke_fire_branch_pins_model_and_loader_args(caplog):
    """smoke mutmut_1/2/3/4 (3285-3286), 5-12 (3287), 13/14 (3288), 15-20 (3289),
    21/22/23 (3290), 24 (3292)."""
    fire = _smoke_result(("fire", 0.83))
    out, m, detect, p = _run_smoke(caplog, fire)
    assert out is fire, "shipped: fire returns the detection result immediately"
    assert p.model_manager.load.call_args_list == [call("smoke-fire-yolov8n")]
    assert detect.await_args.args == (MODEL, IMAGE)
    assert detect.await_args.kwargs == {"confidence_threshold": 0.5}
    assert m["observe_enrichment_model_duration"].call_args_list == [
        call("smoke_fire_detection", 2.0)
    ]
    assert m["record_enrichment_model_call"].call_args_list == [call("smoke_fire_detection")]
    assert m["record_enrichment_model_error"].call_args_list == []
    assert p._smoke_consecutive_counts == {"cam-1": 0}, "shipped: fire resets the smoke counter"
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert recs[0].levelno == logging.WARNING
    assert recs[0].getMessage() == "FIRE DETECTED (confidence=0.83)"
    assert extra_values(recs, "camera_id") == ["cam-1"]


def test_c19_smoke_first_frame_defers_until_second_hit(caplog):
    """shipped smoke counter (3302-3319) + camera key fallback (3292):
    kills smoke mutmut_25/26/27 (and 24 again)."""
    smoke = _smoke_result(("smoke", 0.61))
    out, _m, _d, p = _run_smoke(caplog, smoke, camera_id=None)
    assert out is None, "shipped: 1/2 frames is not yet confirmed -> None"
    assert p._smoke_consecutive_counts == {"_default": 1}
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert recs[0].levelno == logging.DEBUG
    assert recs[0].getMessage() == "Smoke detected (1/2 consecutive frames needed)"
    assert extra_values(recs, "camera_id") == [None]


def test_c19_smoke_second_consecutive_frame_confirms(caplog):
    """shipped confirmation gate (3309-3316): count >= 2 returns the result."""
    smoke = _smoke_result(("smoke", 0.61))
    out, _m, _d, p = _run_smoke(caplog, smoke, camera_id="cam-9", counts={"cam-9": 1})
    assert out is smoke
    assert p._smoke_consecutive_counts == {"cam-9": 2}
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert recs[0].levelno == logging.WARNING
    assert recs[0].getMessage() == "SMOKE CONFIRMED (2 consecutive frames, confidence=0.61)"


def test_c19_smoke_other_detection_returns_result_and_resets_counter(caplog):
    """smoke mutmut_28/29 (reset value 3327) + 30 (return gate 3328)."""
    other = _smoke_result(("steam", 0.40))
    out, _m, _d, p = _run_smoke(caplog, other, counts={"cam-1": 5})
    assert out is other, "shipped: has_detections True -> the result object is returned"
    assert p._smoke_consecutive_counts == {"cam-1": 0}
    assert mod_records(caplog) == [], "shipped: the no-smoke/no-fire branch logs nothing"


def test_c19_smoke_empty_result_returns_none_and_resets_counter(caplog):
    """smoke mutmut_31 (return gate 3328) + 28/29 again."""
    empty = _smoke_result()
    out, _m, _d, p = _run_smoke(caplog, empty, counts={"cam-1": 5})
    assert out is None, "shipped: has_detections False -> None"
    assert p._smoke_consecutive_counts == {"cam-1": 0}
    assert mod_records(caplog) == []


def test_c19_smoke_error_handler_metrics_and_message(caplog):
    """smoke mutmut_32/33/34 (3331) + 35 (3332)."""
    out, m, _detect, p = _run_smoke(caplog, _smoke_result(), load_exc=RuntimeError("boom"))
    assert out is None
    assert m["record_enrichment_model_error"].call_args_list == [call("smoke_fire_detection")]
    assert m["observe_enrichment_model_duration"].call_args_list == []
    assert m["record_enrichment_model_call"].call_args_list == []
    assert p._smoke_consecutive_counts == {}
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert recs[0].levelno == logging.DEBUG
    assert recs[0].getMessage() == "Smoke/fire detection skipped: boom"


# ==================================================== THREATS VIA SERVICE ==
class _RemoteThreats:
    """Remote /threat-detect payload stand-in."""

    def __init__(self, threats) -> None:
        self.threats_detected = list(threats)


def _run_threats(caplog, *, exc: BaseException | None = None, remote=None):
    p = pipeline()
    client = MagicMock()
    client.detect_threats = AsyncMock(side_effect=exc) if exc else AsyncMock(return_value=remote)
    p._get_enrichment_client = MagicMock(return_value=client)
    with caplog.at_level(logging.DEBUG, logger=MODLOG), metrics(THREATS) as m:
        out = asyncio.run(live(THREATS)(p, IMAGE))
    return out, m, client, p


def test_c19_threats_via_service_success_pins_call_and_result(caplog):
    """threats mutmut_1 (5182), 2/3/4 (5183), 5 (5184), 6 (5187), 7 (5187)."""
    remote = _RemoteThreats(
        [
            {"class_name": "gun", "confidence": 0.9, "bbox": [0.1, 0.2, 0.3, 0.4]},
            {"type": "box", "confidence": 0.2},
        ]
    )
    out, m, client, _p = _run_threats(caplog, remote=remote)
    assert out is not None, "shipped: a truthy remote payload becomes a ThreatDetectionResult"
    assert [(t.class_name, t.confidence, t.bbox, t.is_high_priority) for t in out.threats] == [
        ("gun", 0.9, (0.1, 0.2, 0.3, 0.4), True),
        ("box", 0.2, (0.0, 0.0, 0.0, 0.0), False),
    ]
    assert (out.has_threats, out.has_high_priority) == (True, True)
    assert client.detect_threats.await_args.args == (IMAGE,)
    assert m["record_enrichment_model_call"].call_args_list == [call("threat-via-service")]
    assert m["observe_enrichment_model_duration"].call_args_list == [
        call("threat-via-service", 2.0)
    ]
    assert m["record_enrichment_model_error"].call_args_list == []
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert recs[0].levelno == logging.INFO
    assert recs[0].getMessage() == (
        "Threat detection (via service): has_threats=True, has_high_priority=True, count=2"
    )
    assert extra_values(recs, "threat_count") == [2]


def test_c19_threats_parse_error_handler_metrics(caplog):
    """threats mutmut_8-14 (observe site 5263) + 15/16/17 (error site 5265)."""
    out, m, _client, _p = _run_threats(caplog, exc=ValueError("bad json payload"))
    assert out is None, "shipped: the parse handler returns None"
    assert m["observe_enrichment_model_duration"].call_args_list == [
        call("threat-via-service", 2.0)
    ]
    assert m["record_enrichment_model_error"].call_args_list == [call("threat-via-service")]


def test_c19_threats_parse_error_handler_message_and_payload(caplog):
    """threats mutmut_18/21/24/25/26 (msg 5267), 19/22 (extra 5268),
    20/23 (exc_info 5269)."""
    out, _m, _client, _p = _run_threats(caplog, exc=ValueError("bad json payload"))
    assert out is None
    recs = mod_records(caplog)
    assert len(recs) == 1, [(r.levelno, r.getMessage()) for r in recs]
    assert recs[0].levelno == logging.ERROR
    assert recs[0].getMessage() == "Threat detection parse error"
    assert extra_values(recs, "service") == ["threat-via-service"]
    assert extra_values(recs, "error_type") == ["ValueError"]
    assert recs[0].exc_info, "shipped: the parse handler logs with exc_info=True"
