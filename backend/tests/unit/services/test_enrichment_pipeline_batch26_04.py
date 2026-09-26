"""Chunk-04 kill battery — enrichment_pipeline mutation survivors (batch 26).

Every assertion was PROBED against pristine shipped HEAD first (rule 1); the
probe is /tmp/wp-ep/probes/c04/probe_shipped.py. Shipped behaviour is pinned
exactly as measured, including shipped oddities: the two *_via_service paths
swallow every exception and return a partial dict, a "disabled" BRISQUE
RuntimeError records no error metric, and _handle_enrichment_error is only ever
called from inside an active except block (which is what makes its
exc_info=True resolve to a real traceback).

Each test drives EVERY site of its twin shape group (e.g. both the unavailable
and the unexpected handler of _classify_vehicle_via_service), so one splice
disposes the whole group.

Seams, both at the IMPORT site:
  * metrics/telemetry helpers imported into
    backend.services.enrichment_pipeline (record_cascade_model_deferred,
    record_enrichment_model_call, record_enrichment_model_error,
    observe_enrichment_model_duration, record_pipeline_error, add_span_event)
    are replaced with recorders in the LIVE module dict;
  * standard-logging records are captured by attaching a handler to the shipped
    module logger (propagate and the existing handler stack are untouched).

Verification note: mutants were bound with
/tmp/wp-ep/probes/c04/c04plugin.py, which exec()s the variant body into the
LIVE module dict (like a real mutmut line-edit), so the import-site recorders
above are observed by mutant code too.  The shared
/tmp/wp-ep/probes/ep_plugin.py instead exec()s into a SNAPSHOT COPY of the
module dict, which would let mutated code reach pristine module globals.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from unittest import mock

import httpx
import pytest
from PIL import Image

import backend.services.enrichment_pipeline as M
from backend.core import metrics as MT
from backend.core.exceptions import EnrichmentUnavailableError
from backend.services.household_matcher import HouseholdMatch

LOG_NAME = "backend.services.enrichment_pipeline"
HUGE = 1e9


# --------------------------------------------------------------------------
# helpers / fixtures
# --------------------------------------------------------------------------
class _Recorder:
    """Records every call; delegates to .impl (no-op by default)."""

    def __init__(self, name):
        self.name = name
        self.calls: list[tuple[tuple, dict]] = []
        self.impl = lambda *a, **k: None

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self.impl(*a, **k)

    @property
    def firsts(self) -> list:
        """First positional argument of each recorded call."""
        return [a[0] for (a, _k) in self.calls]


_HELPERS = (
    "record_cascade_model_deferred",
    "record_enrichment_model_call",
    "record_enrichment_model_error",
    "observe_enrichment_model_duration",
    "record_pipeline_error",
    "add_span_event",
)


@pytest.fixture
def rec(monkeypatch):
    """Swap the metrics/telemetry helpers the shipped module imported."""
    out = {}
    for name in _HELPERS:
        r = _Recorder(name)
        monkeypatch.setattr(M, name, r)
        out[name] = r
    return out


class _Logs:
    def __init__(self):
        self.records: list[logging.LogRecord] = []

    def find(self, needle, level=None):
        return [
            r
            for r in self.records
            if needle in r.getMessage() and (level is None or r.levelno == level)
        ]

    def one(self, needle, level=None):
        hits = self.find(needle, level)
        assert len(hits) == 1, f"expected exactly 1 record with {needle!r}, got {len(hits)}"
        return hits[0]


@pytest.fixture
def logs():
    """Observe the records the shipped module logger emits."""
    logger = logging.getLogger(LOG_NAME)
    holder = _Logs()
    handler = logging.Handler()
    handler.emit = holder.records.append  # type: ignore[method-assign]
    prev_level = logger.level
    logger.addHandler(handler)
    if logger.getEffectiveLevel() > logging.DEBUG:
        logger.setLevel(logging.DEBUG)
    try:
        yield holder
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prev_level)


def _det(cls, i=1, conf=0.95):
    return M.DetectionInput(
        class_name=cls,
        confidence=conf,
        bbox=M.BoundingBox(x1=1, y1=1, x2=10, y2=10),
        id=i,
    )


@contextlib.asynccontextmanager
async def _load_ok(*_a, **_k):
    yield mock.MagicMock(name="model_data")


def _load_keyerror(key):
    def _load(*_a, **_k):
        raise KeyError(key)

    return _load


def _bare_pipe(**kw):
    mm = mock.MagicMock(name="model_manager")
    mm.load.side_effect = _load_ok
    return M.EnrichmentPipeline(model_manager=mm, **kw)


@pytest.fixture
def pipe():
    return _bare_pipe()


def _client(**methods):
    c = mock.MagicMock(name="enrichment_client")
    for k, v in methods.items():
        setattr(c, k, mock.AsyncMock(**v))
    return c


def _img():
    return Image.new("RGB", (32, 32))


def _small(d) -> bool:
    return isinstance(d, (int, float)) and not isinstance(d, bool) and 0.0 <= d < HUGE


def _timed(fn):
    """Run fn() and return (result, its own wall-clock cost).

    Used to pin observed model durations RELATIVE to the cost of the call that
    produced them: shipped code reports `perf_counter() - start`, so the
    reported duration can never exceed what the call actually took (plus
    scheduler slack).  A `perf_counter() + start_time` mutant reports roughly
    twice the clock's own epoch value — enormous next to a sub-millisecond
    mocked call — which an absolute bound alone can miss.
    """
    t0 = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t0


def _plausible(durations, elapsed):
    """Every reported duration is a plausible elapsed time for that call."""
    return all(0.0 <= d <= elapsed + 0.25 for d in durations)


# ==========================================================================
# GROUP: EnrichmentResult.to_dict household-match blocks
#   person block  L1464 "detection_id" / L1467 "similarity" / L1468 "match_type"
#   vehicle block L1476 "detection_id" / L1479 "similarity" / L1480 "match_type"
#   keys: 67,68,73,74,75,76 (person) + 98,99,104,105,106,107 (vehicle)
# ==========================================================================
_PERSON_MATCH = {
    "detection_id": 4,
    "member_id": 11,
    "member_name": "Ana",
    "similarity": 0.66,
    "match_type": "person",
    "member_role": "resident",
    "schedule_status": True,
}
_VEHICLE_MATCH = {
    "detection_id": 5,
    "vehicle_id": 22,
    "vehicle_description": "blue van",
    "similarity": 0.44,
    "match_type": "license_plate",
}


def test_to_dict_household_match_blocks_exact_keys_and_values():
    r = M.EnrichmentResult()
    r.person_household_matches[4] = HouseholdMatch(
        member_id=11,
        member_name="Ana",
        similarity=0.66,
        match_type="person",
        member_role="resident",
        schedule_status=True,
    )
    r.vehicle_household_matches[5] = HouseholdMatch(
        vehicle_id=22,
        vehicle_description="blue van",
        similarity=0.44,
        match_type="license_plate",
    )

    d = r.to_dict()

    assert d["person_household_matches"] == {"4": _PERSON_MATCH}
    assert d["vehicle_household_matches"] == {"5": _VEHICLE_MATCH}


# ==========================================================================
# GROUP: _handle_enrichment_error
#   PARSE_ERROR branch  L2292 extra={"error": ...} / L2293 exc_info=True
#   UNEXPECTED branch   L2306 extra={"error": ...} / L2307 exc_info=True
#   keys: 22,23,25,26,27,28,29 (PARSE) + 32,33,35,36,38,39,40 (UNEXPECTED)
# ==========================================================================
def test_handle_enrichment_error_parse_and_unexpected_log_contract(pipe, logs, rec):
    def _fire(exc, operation="demo_op"):
        """Call the shipped handler from inside an active except block — the
        only way callers use it — so exc_info=True resolves to a real traceback.
        """
        result = M.EnrichmentResult()
        try:
            raise exc
        except type(exc) as live:
            pipe._handle_enrichment_error(operation, live, result)
        return result

    parse_result = _fire(ValueError("bad payload"))
    unexp_result = _fire(IndexError("boom-index"))

    assert parse_result.structured_errors[0].category is M.ErrorCategory.PARSE_ERROR
    assert unexp_result.structured_errors[0].category is M.ErrorCategory.UNEXPECTED
    assert rec["record_pipeline_error"].firsts == [
        "demo_op_error_parse_error",
        "demo_op_error_unexpected",
    ]

    parse_rec = logs.one("demo_op response parsing failed")
    unexp_rec = logs.one("demo_op unexpected error")

    assert parse_rec.levelno == logging.ERROR
    assert unexp_rec.levelno == logging.ERROR

    # extra={"error": error.to_dict()} on BOTH branches
    assert set(parse_rec.error) == {
        "operation",
        "category",
        "reason",
        "error_type",
        "is_transient",
        "details",
    }
    assert parse_rec.error["operation"] == "demo_op"
    assert parse_rec.error["category"] == "parse_error"
    assert parse_rec.error["error_type"] == "ValueError"
    assert parse_rec.error["is_transient"] is False
    assert parse_rec.error["reason"] == "Response parsing failed: bad payload"
    assert unexp_rec.error["category"] == "unexpected"
    assert unexp_rec.error["error_type"] == "IndexError"
    assert unexp_rec.error["is_transient"] is True

    # exc_info=True on BOTH branches
    assert parse_rec.exc_info is not None and parse_rec.exc_info[0] is ValueError
    assert unexp_rec.exc_info is not None and unexp_rec.exc_info[0] is IndexError

    assert parse_result.errors == ["demo_op failed: Response parsing failed: bad payload"]


# ==========================================================================
# GROUP: _run_parallel_enrichment — NEM-5570 cascade Level-2 block
#   L2374 if not persons / L2384 record(model, "no_person_detections")
#   L2385 if not vehicles / L2386 vehicle-model tuple / L2387 record(..., "no_vehicle_detections")
#   L2388 if not animals / L2389 record("pet_class", "no_animal_detections")
#   L2393 cascade debug message format string  (mutated to None -> Logger.debug
#       raises TypeError inside the shipped call, aborting the coroutine)
# ==========================================================================
_PERSON_MODELS = ("face_detection", "pose", "clothing", "action", "reid", "threat", "violence")
_VEHICLE_MODELS = ("license_plate", "vehicle_class", "vehicle_damage")


def _cascade_sinks(pipe, dets, holder=None):
    """Run the shipped cascade block and return its (model, reason) deferrals.

    add_span_event is made to raise, and it is the first call AFTER the cascade
    block (and after the shipped NEM-5570 summary debug log), so the sink list
    is exactly the deferrals for `dets`.  If `holder` is given it also receives
    the log records emitted before the stop.
    """
    seen: list[tuple] = []
    real_cascade = M.record_cascade_model_deferred
    real_span = M.add_span_event

    def _span(*_a, **_k):
        raise RuntimeError("_c04_stop_after_cascade")

    M.record_cascade_model_deferred = lambda model, reason: seen.append((model, reason))
    M.add_span_event = _span
    try:
        with pytest.raises(RuntimeError, match="_c04_stop_after_cascade"):
            asyncio.run(pipe._run_parallel_enrichment(M.EnrichmentResult(), _img(), dets, {}, None))
    finally:
        M.record_cascade_model_deferred = real_cascade
        M.add_span_event = real_span
    return seen


def _cascade_debug_records(logs):
    """The Level-2 summary records (the Florence-2 Level-3 record shares the
    "Cascade: " prefix, so match on the %d-count format string)."""
    return [
        r
        for r in logs.records
        if isinstance(getattr(r, "msg", None), str) and r.msg.startswith("Cascade: %d detections")
    ]


def test_cascade_empty_detection_set_defers_every_model():
    seen = _cascade_sinks(_bare_pipe(), [])
    assert seen == [
        *[(m, "no_person_detections") for m in _PERSON_MODELS],
        *[(m, "no_vehicle_detections") for m in _VEHICLE_MODELS],
        ("pet_class", "no_animal_detections"),
        ("florence2", "all_high_confidence"),
    ]


def test_cascade_mixed_person_vehicle_and_animal_defers_nothing():
    seen = _cascade_sinks(_bare_pipe(), [_det("person", 4), _det("car", 5), _det("cat", 6)])
    assert seen == [("florence2", "all_high_confidence")]


def test_cascade_person_only_set_defers_vehicle_and_pet_models():
    seen = _cascade_sinks(_bare_pipe(), [_det("person", 1)])
    assert [m for m, _r in seen if m in _PERSON_MODELS] == []
    assert [s for s in seen if s[1] == "no_vehicle_detections"] == [
        (m, "no_vehicle_detections") for m in _VEHICLE_MODELS
    ]
    assert ("pet_class", "no_animal_detections") in seen
    assert seen[-1] == ("florence2", "all_high_confidence")


def test_cascade_vehicle_only_set_defers_person_models_with_person_reason():
    seen = _cascade_sinks(_bare_pipe(), [_det("car", 2)])
    assert [s for s in seen if s[1] == "no_person_detections"] == [
        (m, "no_person_detections") for m in _PERSON_MODELS
    ]
    assert [s for s in seen if s[1] == "no_vehicle_detections"] == []
    assert ("pet_class", "no_animal_detections") in seen


def test_cascade_animal_only_set_defers_person_and_vehicle_models():
    seen = _cascade_sinks(_bare_pipe(), [_det("dog", 3)])
    assert [s for s in seen if s[1] == "no_person_detections"] == [
        (m, "no_person_detections") for m in _PERSON_MODELS
    ]
    assert [s for s in seen if s[1] == "no_vehicle_detections"] == [
        (m, "no_vehicle_detections") for m in _VEHICLE_MODELS
    ]
    assert [s for s in seen if s[1] == "no_animal_detections"] == []


def test_cascade_class_partition_and_summary_debug_log(pipe, logs):
    """Shipped NEM-5570 Level-2 block also logs a DEBUG summary whose four %d
    args are (len(detections), len(persons), len(vehicles), len(animals)).
    Pins the class partition (which drives the three `if not <subset>` guards)
    and the summary message + args together.
    """
    _cascade_sinks(
        pipe,
        [_det("person", 61), _det("car", 62), _det("truck", 63), _det("dog", 64)],
    )
    (rec,) = _cascade_debug_records(logs)
    assert rec.msg == "Cascade: %d detections — %d persons, %d vehicles, %d animals"
    assert rec.args == (4, 1, 2, 1)
    assert rec.levelno == logging.DEBUG
    assert rec.getMessage() == "Cascade: 4 detections — 1 persons, 2 vehicles, 1 animals"


def test_cascade_deferrals_reach_the_prometheus_cascade_counter(rec):
    """Shipped helper labels ENRICHMENT_CASCADE_MODELS_DEFERRED_TOTAL(model, reason)."""
    rec["record_cascade_model_deferred"].impl = MT.record_cascade_model_deferred
    rec["add_span_event"].impl = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("_c04_stop_after_cascade")
    )
    with pytest.raises(RuntimeError, match="_c04_stop_after_cascade"):
        asyncio.run(
            _bare_pipe()._run_parallel_enrichment(
                M.EnrichmentResult(), _img(), [_det("person", 7)], {}, None
            )
        )
    hit = {
        s.labels["model"]
        for ds in MT.ENRICHMENT_CASCADE_MODELS_DEFERRED_TOTAL.collect()
        for s in ds.samples
        if s.name.endswith("_total") and s.labels.get("reason") == "no_vehicle_detections"
    }
    assert "vehicle_damage" in hit


# ==========================================================================
# GROUP: _classify_vehicle_via_service
#   unavailable path L4277 observe("vehicle-via-service", perf-start) /
#                     L4279 record_enrichment_model_error / L4282 extra={} /
#                     L4284 "error_type"
#   unexpected  path L4329 observe(...) / L4331 record_enrichment_model_error /
#                     L4334 extra={} / L4336 "error_type"
#   keys: 63,67,68,69,70,71,72,74,81,82,83 + 86,90,91,92,93,94,95,97,107,108,109
# ==========================================================================
def test_vehicle_via_service_both_error_paths_observe_small_labeled_durations(pipe, rec):
    pipe._enrichment_client = _client(
        classify_vehicle={"side_effect": httpx.ConnectError("no route")}
    )
    out_conn, el_conn = _timed(
        lambda: asyncio.run(pipe._classify_vehicle_via_service([_det("car", 11)], _img()))
    )
    pipe._enrichment_client = _client(classify_vehicle={"side_effect": RuntimeError("kaboom")})
    out_err, el_err = _timed(
        lambda: asyncio.run(pipe._classify_vehicle_via_service([_det("car", 12)], _img()))
    )

    assert out_conn == {} and out_err == {}
    calls = rec["observe_enrichment_model_duration"].calls
    assert [a[0] for (a, _k) in calls] == ["vehicle-via-service", "vehicle-via-service"]
    assert all(_small(a[1]) for (a, _k) in calls)
    assert _plausible([a[1] for (a, _k) in calls[:1]], el_conn)
    assert _plausible([a[1] for (a, _k) in calls[1:]], el_err)


def test_vehicle_via_service_both_error_paths_record_model_error(pipe, rec):
    pipe._enrichment_client = _client(
        classify_vehicle={"side_effect": EnrichmentUnavailableError("down")}
    )
    asyncio.run(pipe._classify_vehicle_via_service([_det("car", 13)], _img()))
    pipe._enrichment_client = _client(classify_vehicle={"side_effect": RuntimeError("kaboom")})
    asyncio.run(pipe._classify_vehicle_via_service([_det("car", 14)], _img()))

    assert rec["record_enrichment_model_error"].calls == [
        (("vehicle-via-service",), {}),
        (("vehicle-via-service",), {}),
    ]


def test_vehicle_via_service_both_error_paths_log_structured_extra(pipe, logs):
    pipe._enrichment_client = _client(classify_vehicle={"side_effect": httpx.ConnectError("no")})
    asyncio.run(pipe._classify_vehicle_via_service([_det("car", 15)], _img()))
    pipe._enrichment_client = _client(classify_vehicle={"side_effect": RuntimeError("kaboom")})
    asyncio.run(pipe._classify_vehicle_via_service([_det("car", 16)], _img()))

    warn = logs.one("Enrichment service unavailable for vehicle 15")
    err = logs.one("Vehicle classification unexpected error for 16")
    assert warn.levelno == logging.WARNING
    assert err.levelno == logging.ERROR
    assert warn.service == "vehicle-via-service" and warn.detection_id == "15"
    assert err.service == "vehicle-via-service" and err.detection_id == "16"
    assert warn.exc_info is None
    assert err.exc_info is not None and err.exc_info[0] is RuntimeError


def test_vehicle_via_service_both_error_paths_log_error_type_of_raised_exception(pipe, logs):
    pipe._enrichment_client = _client(classify_vehicle={"side_effect": httpx.ConnectError("no")})
    asyncio.run(pipe._classify_vehicle_via_service([_det("car", 17)], _img()))
    pipe._enrichment_client = _client(classify_vehicle={"side_effect": RuntimeError("kaboom")})
    asyncio.run(pipe._classify_vehicle_via_service([_det("car", 18)], _img()))

    warn = logs.one("Enrichment service unavailable for vehicle 17")
    err = logs.one("Vehicle classification unexpected error for 18")
    assert warn.error_type == "ConnectError"
    assert err.error_type == "RuntimeError"


# ==========================================================================
# GROUP: _classify_pets_via_service
#   unavailable path L4403 record_enrichment_model_error / L4406 extra={} /
#                     L4408 "error_type"
#   unexpected  path L4455 record_enrichment_model_error / L4458 extra={} /
#                     L4460 "error_type"
#   keys: 73,74,76,83,84,85 + 96,97,99,109,110,111
# ==========================================================================
def test_pets_via_service_both_error_paths_record_model_error(pipe, rec):
    pipe._enrichment_client = _client(classify_pet={"side_effect": EnrichmentUnavailableError("d")})
    out_unavail = asyncio.run(pipe._classify_pets_via_service([_det("dog", 21)], _img()))
    pipe._enrichment_client = _client(classify_pet={"side_effect": RuntimeError("pet-boom")})
    out_unexp = asyncio.run(pipe._classify_pets_via_service([_det("dog", 22)], _img()))

    assert out_unavail == {} and out_unexp == {}
    assert rec["record_enrichment_model_error"].calls == [
        (("pet-via-service",), {}),
        (("pet-via-service",), {}),
    ]
    assert rec["observe_enrichment_model_duration"].firsts == ["pet-via-service", "pet-via-service"]


def test_pets_via_service_both_error_paths_log_structured_extra(pipe, logs):
    pipe._enrichment_client = _client(classify_pet={"side_effect": EnrichmentUnavailableError("d")})
    asyncio.run(pipe._classify_pets_via_service([_det("dog", 23)], _img()))
    pipe._enrichment_client = _client(classify_pet={"side_effect": RuntimeError("pet-boom")})
    asyncio.run(pipe._classify_pets_via_service([_det("dog", 24)], _img()))

    warn = logs.one("Enrichment service unavailable for animal 23")
    err = logs.one("Pet classification unexpected error for 24")
    assert warn.levelno == logging.WARNING
    assert err.levelno == logging.ERROR
    assert warn.service == "pet-via-service" and warn.detection_id == "23"
    assert err.service == "pet-via-service" and err.detection_id == "24"
    assert warn.exc_info is None
    assert err.exc_info is not None and err.exc_info[0] is RuntimeError


def test_pets_via_service_both_error_paths_log_error_type_of_raised_exception(pipe, logs):
    pipe._enrichment_client = _client(classify_pet={"side_effect": EnrichmentUnavailableError("d")})
    asyncio.run(pipe._classify_pets_via_service([_det("dog", 25)], _img()))
    pipe._enrichment_client = _client(classify_pet={"side_effect": RuntimeError("pet-boom")})
    asyncio.run(pipe._classify_pets_via_service([_det("dog", 26)], _img()))

    warn = logs.one("Enrichment service unavailable for animal 25")
    err = logs.one("Pet classification unexpected error for 26")
    assert warn.error_type == "EnrichmentUnavailableError"
    assert err.error_type == "RuntimeError"


# ==========================================================================
# GROUP: _safe_classify_demographics (NEM-5566)
#   age block    L3226 start = time.monotonic() / L3231 duration = monotic - start
#   gender block L3246 start = time.monotonic() / L3251 duration = ... - start
#   keys: 23,45 (start) + 39,61 (duration=None) + 40,62 (duration=monotonic+start)
#   Every mutant raises TypeError inside the block's own `except Exception`,
#   which swallows it and records an error metric — so shipped = clean success.
# ==========================================================================
_AGE = M.AgeClassificationResult(
    age_group="adult", confidence=0.7, display_name="Adult", all_scores={"adult": 0.7}
)
_GENDER = M.GenderClassificationResult(
    gender="male", confidence=0.8, male_score=0.8, female_score=0.2
)


def test_safe_classify_demographics_measures_age_and_gender_blocks_cleanly(
    pipe, logs, rec, monkeypatch
):
    monkeypatch.setattr(M, "classify_ages_batch", mock.AsyncMock(return_value=[_AGE]))
    monkeypatch.setattr(M, "classify_genders_batch", mock.AsyncMock(return_value=[_GENDER]))

    (ages, genders), el = _timed(
        lambda: asyncio.run(pipe._safe_classify_demographics([_det("person", 31)], _img()))
    )

    assert list(ages) == ["31"] and list(genders) == ["31"]
    assert rec["record_enrichment_model_error"].calls == []
    assert rec["record_enrichment_model_call"].firsts == [
        "age_classification",
        "gender_classification",
    ]
    seen = rec["observe_enrichment_model_duration"].calls
    assert [a[0] for (a, _k) in seen] == ["age_classification", "gender_classification"]
    assert all(_small(a[1]) for (a, _k) in seen)
    assert _plausible([a[1] for (a, _k) in seen], el)
    (r,) = logs.find("Age classification completed for")
    assert r.args[0] == 1 and _small(r.args[1]) and _plausible([r.args[1]], el)


# ==========================================================================
# GROUP: _analyze_depth
#   success L4515 duration = perf_counter() - start_time / L4516 observe("depth-anything-v2", duration)
#   failure L4524 duration = ... - start_time            / L4525 observe("depth-anything-v2", duration)
#   keys: 40,41,45,46 (success) + 55,56,60,61 (failure)
# ==========================================================================
def test_analyze_depth_success_and_failure_observe_labeled_small_durations(pipe, rec, monkeypatch):
    shipped = M.DepthAnalysisResult(closest_detection_id="41", average_depth=0.4)
    monkeypatch.setattr(M, "analyze_depth", mock.AsyncMock(return_value=shipped))
    out, el_ok = _timed(lambda: asyncio.run(pipe._analyze_depth([_det("person", 41)], _img())))
    assert out is shipped

    async def _boom(*_a, **_k):
        raise ValueError("depth model exploded")

    monkeypatch.setattr(M, "analyze_depth", _boom)

    def _fail():
        with pytest.raises(ValueError, match="depth model exploded"):
            asyncio.run(pipe._analyze_depth([_det("person", 42)], _img()))

    _res, el_fail = _timed(_fail)

    calls = rec["observe_enrichment_model_duration"].calls
    assert [a[0] for (a, _k) in calls] == ["depth-anything-v2", "depth-anything-v2"]
    assert all(_small(a[1]) for (a, _k) in calls)
    assert _plausible([a[1] for (a, _k) in calls[:1]], el_ok)
    assert _plausible([a[1] for (a, _k) in calls[1:]], el_fail)


# ==========================================================================
# GROUP: _detect_violence
#   success   L6512 duration = perf_counter() - start_time / L6513 observe("violence-detection", duration)
#   MODEL_ZOO L6519 duration = ... - start_time            / L6520 observe("violence-detection", duration)
#   keys: 17,18,22,23 (success) + 25,26,30,31 (MODEL_ZOO)
# ==========================================================================
def test_detect_violence_success_and_model_zoo_observe_labeled_small_durations(
    pipe, rec, logs, monkeypatch
):
    shipped = M.ViolenceDetectionResult(
        is_violent=True, confidence=0.9, violent_score=0.9, non_violent_score=0.1
    )
    monkeypatch.setattr(M, "classify_violence", mock.AsyncMock(return_value=shipped))
    out, el_ok = _timed(lambda: asyncio.run(pipe._detect_violence(_img())))
    assert out is shipped
    assert rec["record_enrichment_model_error"].calls == []

    pipe.model_manager.load.side_effect = _load_keyerror("violence-detection")

    def _zoo():
        with pytest.raises(RuntimeError, match="violence-detection model not configured"):
            asyncio.run(pipe._detect_violence(_img()))

    _res, el_zoo = _timed(_zoo)

    calls = rec["observe_enrichment_model_duration"].calls
    assert [a[0] for (a, _k) in calls] == ["violence-detection", "violence-detection"]
    assert all(_small(a[1]) for (a, _k) in calls)
    assert _plausible([a[1] for (a, _k) in calls[:1]], el_ok)
    assert _plausible([a[1] for (a, _k) in calls[1:]], el_zoo)
    assert rec["record_enrichment_model_error"].calls == [(("violence-detection",), {})]
    assert logs.find("violence-detection model not available in MODEL_ZOO")


# ==========================================================================
# GROUP: _classify_weather
#   MODEL_ZOO KeyError L6565 record_enrichment_model_error("weather-classification")
#   generic except     L6571 record_enrichment_model_error("weather-classification")
#   keys: 33,34,35 (KeyError) + 51,52,53 (generic)
# ==========================================================================
def test_classify_weather_both_error_paths_record_model_error(pipe, rec, logs, monkeypatch):
    pipe.model_manager.load.side_effect = _load_keyerror("weather-classification")
    with pytest.raises(RuntimeError, match="weather-classification model not configured"):
        asyncio.run(pipe._classify_weather(_img()))
    assert rec["record_enrichment_model_error"].calls == [(("weather-classification",), {})]
    assert logs.find("weather-classification model not available in MODEL_ZOO")

    pipe.model_manager.load.side_effect = _load_ok  # second path needs the model present

    async def _boom(*_a, **_k):
        raise RuntimeError("gpu exploded")

    monkeypatch.setattr(M, "classify_weather", _boom)
    with pytest.raises(RuntimeError, match="gpu exploded"):
        asyncio.run(pipe._classify_weather(_img()))

    assert rec["record_enrichment_model_error"].calls == [
        (("weather-classification",), {}),
        (("weather-classification",), {}),
    ]
    assert logs.find("Weather classification error")


# ==========================================================================
# GROUP: _assess_image_quality
#   MODEL_ZOO KeyError  L7091 record_enrichment_model_error("brisque-quality")
#   RuntimeError else:  L7101 record_enrichment_model_error("brisque-quality")
#   keys: 37,38,39 (KeyError) + 61,62,63 (RuntimeError else-arm)
# ==========================================================================
def test_assess_image_quality_both_error_paths_record_model_error(pipe, rec, logs, monkeypatch):
    pipe.model_manager.load.side_effect = _load_keyerror("brisque-quality")
    with pytest.raises(RuntimeError, match="brisque-quality model not configured"):
        asyncio.run(pipe._assess_image_quality(_img(), "cam-1"))
    assert rec["record_enrichment_model_error"].calls == [(("brisque-quality",), {})]
    assert logs.find("brisque-quality model not available in MODEL_ZOO")

    pipe.model_manager.load.side_effect = _load_ok  # second path needs the model present

    async def _rt(*_a, **_k):
        raise RuntimeError("quality engine exploded")

    monkeypatch.setattr(M, "assess_image_quality", _rt)
    with pytest.raises(RuntimeError, match="quality engine exploded"):
        asyncio.run(pipe._assess_image_quality(_img(), "cam-1"))

    assert rec["record_enrichment_model_error"].calls == [
        (("brisque-quality",), {}),
        (("brisque-quality",), {}),
    ]
    assert logs.find("Image quality assessment error (runtime)")


def test_assess_image_quality_disabled_runtime_error_records_nothing(pipe, rec, monkeypatch):
    """Shipped: a "disabled" RuntimeError is expected behaviour — no metric."""

    async def _disabled(*_a, **_k):
        raise RuntimeError("BRISQUE quality assessment is disabled")

    monkeypatch.setattr(M, "assess_image_quality", _disabled)
    with pytest.raises(RuntimeError, match="disabled"):
        asyncio.run(pipe._assess_image_quality(_img(), "cam-1"))

    assert rec["record_enrichment_model_error"].calls == []


# ==========================================================================
# GROUP: _run_reid
#   L5804 find_matching_entities(entity_type=entity_type) and
#   L5833 EntityEmbedding(entity_type=entity_type) — same shape, one splice each
#   keys: 38, 60
# ==========================================================================
def test_run_reid_uses_per_detection_entity_type_for_lookup_and_stored_embedding(rec):
    reid = mock.MagicMock(name="reid_service")
    reid.generate_embedding = mock.AsyncMock(side_effect=[[0.1, 0.2], [0.3, 0.4]])
    reid.find_matching_entities = mock.AsyncMock(return_value=[])
    reid.store_embedding = mock.AsyncMock()
    p = _bare_pipe(redis_client=mock.MagicMock(name="redis"), reid_service=reid)
    result = M.EnrichmentResult()

    asyncio.run(p._run_reid([_det("person", 51), _det("car", 52)], _img(), "cam-9", result))

    assert [c.kwargs["entity_type"] for c in reid.find_matching_entities.call_args_list] == [
        "person",
        "vehicle",
    ]
    stored = [c[0][1] for c in reid.store_embedding.call_args_list]
    assert [e.entity_type for e in stored] == ["person", "vehicle"]
    assert [e.detection_id for e in stored] == ["51", "52"]
    assert [e.camera_id for e in stored] == ["cam-9", "cam-9"]
    assert list(result.clip_embeddings) == ["51", "52"]
