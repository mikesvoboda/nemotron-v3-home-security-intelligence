"""Batch-26 adjudication part 12 — enrichment_pipeline mutation survivors (chunk-12).

Shape groups (120 keys; every key sits in its own shape group, so no twin sharing):
  * EnrichmentPipeline._map_unified_to_enrichment_result  L3850-L4048 (pet + depth branches)
  * EnrichmentPipeline._classify_clothing_via_service     L4757-L4880
  * EnrichmentPipeline._classify_pets_via_service         L4345-L4468
  * EnrichmentResult.to_context_string                    L1162-L1190 (vision + re-id blocks)

Harness notes (why the fixtures look like this)
-----------------------------------------------
ep_plugin exec's a variant in a SNAPSHOT COPY of the module dict, so names the
variant looks up (``logger``, ``record_enrichment_model_call``,
``observe_enrichment_model_duration``, ``sanitize_error``, the locally imported
formatters) still resolve to the SHIPPED objects.  Nothing is therefore
monkeypatched at module level:

* metrics are asserted through the real prometheus_client label values, so a
  mutated metric label is visible without patching;
* log records are captured through a handler attached to the live logger
  object, so ``extra=``/``msg=``/``exc_info=`` mutations are observable;
* ``time.perf_counter`` is scripted for the whole session (module-scoped
  autouse) so ``duration_ms`` is exactly 1250 and no mutant can produce a
  negative elapsed time;
* ``_crop_to_bbox``/``_load_image`` run for real on a 640x480 PIL image - the
  only stub is an out-of-bounds bbox, which shipped code turns into ``None``.

All expected values were probed against the pristine workspace source.
"""

from __future__ import annotations

import asyncio
import datetime
import logging

import pytest
from PIL import Image
from prometheus_client import REGISTRY
from unittest.mock import AsyncMock, MagicMock

import backend.services.enrichment_pipeline as M
from backend.core.exceptions import EnrichmentUnavailableError
from backend.services.reid_service import EntityEmbedding, EntityMatch
from backend.services.vision_extractor import BatchExtractionResult

CALLS = "hsi_enrichment_model_calls_total"
DUR = "hsi_enrichment_model_duration_seconds_count"
LOG = M.__name__
MISSING = "<<absent>>"
NL2 = chr(10) + chr(10)  # to_context_string() joins its blocks with a blank line

_DEBUG_CLO = "Person 7 clothing (via service): blue jacket (88%)"
_DEBUG_PET = "Animal 7 classified (via service) as dog (94% confidence)"
_UNAVAIL_CLO = "Enrichment service unavailable for person 7"
_UNAVAIL_PET = "Enrichment service unavailable for animal 7"
_UNEXP_CLO = "Clothing classification unexpected error for 7: boom [REDACTED]"
_UNEXP_PET = "Pet classification unexpected error for 7: boom [REDACTED]"


# ---------------------------------------------------------------- clock ----
@pytest.fixture(autouse=True, scope="session")
def scripted_clock():
    """time.perf_counter() walks 1000.0, 1001.25, 1002.5 ... for the session.

    Module scoped because ep_plugin exec's variants in a snapshot copy of the
    module dict: a function-scoped monkeypatch could be bypassed by a variant
    that captured the shipped module globals.
    """
    import time

    state = {"t": 1000.0}
    real = time.perf_counter

    def tick() -> float:
        state["t"] += 1.25
        return state["t"]

    time.perf_counter = tick
    try:
        yield
    finally:
        time.perf_counter = real


# ----------------------------------------------------------- log capture ----
class _Cap(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.level = logging.DEBUG
        self.recs: list[logging.LogRecord] = []

    def handle(self, record: logging.LogRecord) -> bool:
        self.recs.append(record)
        return True


@pytest.fixture
def cap():
    """Capture records emitted through the live module logger object."""
    lg = logging.getLogger(LOG)
    handler = _Cap()
    old_level = lg.level
    lg.addHandler(handler)
    lg.setLevel(logging.DEBUG)
    try:
        yield handler
    finally:
        lg.removeHandler(handler)
        lg.setLevel(old_level)


def _msg(rec: logging.LogRecord) -> str:
    try:
        return rec.getMessage()
    except Exception:  # a mutant made the call ill-formed (e.g. msg=None)
        return "<unformattable>"


def _label(name: str, model: str):
    try:
        return REGISTRY.get_sample_value(name, {"model": model})
    except Exception:
        return "label-error"


def _label0(name: str, model: str) -> float:
    """Same reader, but a not-yet-created label child counts as 0.0.

    The first test in the session that touches a label would otherwise read
    ``None`` and the delta assertion would depend on execution order.
    """
    v = _label(name, model)
    return 0.0 if v is None else v


# ------------------------------------------------------------- builders ----
def _run(coro):
    return asyncio.run(coro)


def _det(det_id, x1=10.0, y1=20.0, x2=30.0, y2=40.0):
    return M.DetectionInput(
        class_name="person",
        confidence=0.9,
        bbox=M.BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        id=det_id,
    )


_OUT_OF_BOUNDS = dict(x1=700.0, y1=500.0, x2=800.0, y2=600.0)


def _img():
    return Image.new("RGB", (640, 480), (1, 2, 3))


def _pipe(client):
    p = object.__new__(M.EnrichmentPipeline)
    p._enrichment_client = client
    return p


def _cres():
    r = MagicMock(name="remote_clothing")
    r.top_category = "jacket"
    r.confidence = 0.875
    r.is_suspicious = True
    r.is_service_uniform = True
    r.description = "blue jacket"
    r.all_scores = {"jacket": 0.5}
    return r


def _pres():
    r = MagicMock(name="remote_pet")
    r.pet_type = "dog"
    r.confidence = 0.9375
    r.is_household_pet = False
    return r


def _client(fn, ret=None, exc=None):
    """MagicMock client whose enrichment method is an AsyncMock (awaitable)."""
    c = MagicMock(name="enrichment_client")
    m = AsyncMock(name=fn)
    if exc is not None:
        m.side_effect = exc
    else:
        m.return_value = ret
    setattr(c, fn, m)
    return c


def _pet_payload_a():
    return {"pet_type": "dog", "confidence": 0.91, "is_household_pet": False}


def _pet_payload_b():
    return {"type": "cat", "confidence": 0.66, "is_household_pet": False}


def _pet_payload_c():
    return {}


def _unified(pet_data, depth=None):
    u = M.UnifiedEnrichmentResult()
    u.pet = pet_data
    u.depth = depth
    return u


def _map(pet_data, det_id="d7", depth=None):
    res = M.EnrichmentResult()
    M.EnrichmentPipeline._map_unified_to_enrichment_result(
        object.__new__(M.EnrichmentPipeline), res, det_id, _unified(pet_data, depth), "animal"
    )
    return res


def _match(detection_id):
    return EntityMatch(
        entity=EntityEmbedding(
            entity_type="person",
            embedding=[0.1, 0.2],
            camera_id="cam1",
            timestamp=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            detection_id=detection_id,
        ),
        similarity=0.87,
        time_gap_seconds=30.0,
    )


def _vision_none():
    """Real BatchExtractionResult that formats to the "No vision ..." string."""
    return BatchExtractionResult()


def _vision_some():
    """Duck-typed extraction result whose formatter output is non-empty."""
    be = MagicMock(name="vision")
    for name in (
        "vehicle_attributes",
        "person_attributes",
        "scene_analysis",
        "environment_context",
        "florence_enhanced",
    ):
        setattr(be, name, MagicMock(name=name))
    be.vehicle_attributes = {}
    be.person_attributes = {"p1": MagicMock(name="person_attrs")}
    be.florence_enhanced = None
    return be


def _ctx(res):
    return M.EnrichmentResult.to_context_string(res)


def test_map_116_pet_branch_scenario_b():
    """L4026-L4030 mapped PetClassificationResult for scenario B (pet payload with only the type alias)."""
    res = _map(_pet_payload_b())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["cat", 0.66, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_117_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_118_pet_branch_scenario_b():
    """L4026-L4030 mapped PetClassificationResult for scenario B (pet payload with only the type alias)."""
    res = _map(_pet_payload_b())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["cat", 0.66, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_119_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_120_pet_branch_scenario_b():
    """L4026-L4030 mapped PetClassificationResult for scenario B (pet payload with only the type alias)."""
    res = _map(_pet_payload_b())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["cat", 0.66, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_121_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_122_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_123_pet_branch_scenario_b():
    """L4026-L4030 mapped PetClassificationResult for scenario B (pet payload with only the type alias)."""
    res = _map(_pet_payload_b())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["cat", 0.66, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_124_pet_branch_scenario_c():
    """L4026-L4030 mapped PetClassificationResult for scenario C (empty pet payload)."""
    res = _map(_pet_payload_c())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["unknown", 0.0, True]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_125_pet_branch_scenario_b():
    """L4026-L4030 mapped PetClassificationResult for scenario B (pet payload with only the type alias)."""
    res = _map(_pet_payload_b())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["cat", 0.66, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_126_pet_branch_scenario_c():
    """L4026-L4030 mapped PetClassificationResult for scenario C (empty pet payload)."""
    res = _map(_pet_payload_c())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["unknown", 0.0, True]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_127_pet_branch_scenario_b():
    """L4026-L4030 mapped PetClassificationResult for scenario B (pet payload with only the type alias)."""
    res = _map(_pet_payload_b())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["cat", 0.66, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_128_pet_branch_scenario_b():
    """L4026-L4030 mapped PetClassificationResult for scenario B (pet payload with only the type alias)."""
    res = _map(_pet_payload_b())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["cat", 0.66, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_129_pet_branch_scenario_c():
    """L4026-L4030 mapped PetClassificationResult for scenario C (empty pet payload)."""
    res = _map(_pet_payload_c())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["unknown", 0.0, True]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_130_pet_branch_scenario_c():
    """L4026-L4030 mapped PetClassificationResult for scenario C (empty pet payload)."""
    res = _map(_pet_payload_c())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["unknown", 0.0, True]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_131_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_132_pet_branch_scenario_c():
    """L4026-L4030 mapped PetClassificationResult for scenario C (empty pet payload)."""
    res = _map(_pet_payload_c())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["unknown", 0.0, True]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_133_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_134_pet_branch_scenario_c():
    """L4026-L4030 mapped PetClassificationResult for scenario C (empty pet payload)."""
    res = _map(_pet_payload_c())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["unknown", 0.0, True]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_135_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_136_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_137_pet_branch_scenario_c():
    """L4026-L4030 mapped PetClassificationResult for scenario C (empty pet payload)."""
    res = _map(_pet_payload_c())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["unknown", 0.0, True]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_138_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_139_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_140_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_141_pet_branch_scenario_c():
    """L4026-L4030 mapped PetClassificationResult for scenario C (empty pet payload)."""
    res = _map(_pet_payload_c())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["unknown", 0.0, True]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_142_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_143_pet_branch_scenario_c():
    """L4026-L4030 mapped PetClassificationResult for scenario C (empty pet payload)."""
    res = _map(_pet_payload_c())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["unknown", 0.0, True]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_144_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_145_pet_branch_scenario_a():
    """L4026-L4030 mapped PetClassificationResult for scenario A (pet payload with pet_type/confidence/is_household_pet keys)."""
    res = _map(_pet_payload_a())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["dog", 0.91, False]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_146_pet_branch_scenario_c():
    """L4026-L4030 mapped PetClassificationResult for scenario C (empty pet payload)."""
    res = _map(_pet_payload_c())
    assert list(res.pet_classifications) == ["d7"]
    got = res.pet_classifications["d7"]
    assert [got.animal_type, got.confidence, got.is_household_pet] == ["unknown", 0.0, True]
    assert got.cat_score == 0.0 and got.dog_score == 0.0
    assert res.depth_analysis is None


def test_map_147_depth_branch_logs_for_a_dict_depth(cap):
    """L4034-L4047 `if unified.depth is not None` logs the supplemental depth note."""
    res = _map(None, det_id="d7", depth={"mean_depth": 1.5})
    assert res.pet_classifications == {}
    assert res.depth_analysis is None
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert _msg(cap.recs[0]) == "Depth data from unified endpoint for d7: mean=1.5"


def test_clo_4():
    """L4777 record_enrichment_model_call("clothing-via-service") - the prometheus label."""
    before = _label0(CALLS, "clothing-via-service")
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(CALLS, "clothing-via-service")
    assert isinstance(after, float)
    assert after - before == 1.0
    assert _label(CALLS, "None") in (None, 0.0)


def test_clo_5():
    """L4777 record_enrichment_model_call("clothing-via-service") - the prometheus label."""
    before = _label0(CALLS, "clothing-via-service")
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(CALLS, "clothing-via-service")
    assert isinstance(after, float)
    assert after - before == 1.0
    assert _label(CALLS, "XXclothing-via-serviceXX") in (None, 0.0)


def test_clo_6():
    """L4777 record_enrichment_model_call("clothing-via-service") - the prometheus label."""
    before = _label0(CALLS, "clothing-via-service")
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(CALLS, "clothing-via-service")
    assert isinstance(after, float)
    assert after - before == 1.0
    assert _label(CALLS, "CLOTHING-VIA-SERVICE") in (None, 0.0)


def test_clo_10():
    """L4780 det_id = str(x.id) if x.id else str(i) - falsy ids fall back to the index."""
    client = _client("classify_clothing", _cres())
    dets = [_det(9), _det(None), _det(0)]
    out = _run(_pipe(client)._classify_clothing_via_service(dets, _img()))
    assert list(out) == ["9", "1", "2"]
    assert getattr(client, "classify_clothing").call_count == 3


def test_clo_12():
    """L4780 det_id = str(x.id) if x.id else str(i) - falsy ids fall back to the index."""
    client = _client("classify_clothing", _cres())
    dets = [_det(9), _det(None), _det(0)]
    out = _run(_pipe(client)._classify_clothing_via_service(dets, _img()))
    assert list(out) == ["9", "1", "2"]
    assert getattr(client, "classify_clothing").call_count == 3


def test_clo_20():
    """L4786 a failed crop CONTINUES the loop, it does not stop it."""
    client = _client("classify_clothing", _cres())
    dets = [_det(None, **_OUT_OF_BOUNDS), _det(None)]
    out = _run(_pipe(client)._classify_clothing_via_service(dets, _img()))
    assert list(out) == ["1"]
    assert getattr(client, "classify_clothing").call_count == 1


def test_clo_21():
    """L4788 bbox_tuple is bbox.to_tuple(), passed to the client."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_clothing").call_args
    assert a.args[1] == (10.0, 20.0, 30.0, 40.0)
    assert a.args[1] is not None


def test_clo_22():
    """L4788 bbox_tuple is bbox.to_tuple(), passed to the client."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_clothing").call_args
    assert a.args[1] == (10.0, 20.0, 30.0, 40.0)
    assert a.args[1] is not None


def test_clo_23():
    """L4788 bbox_tuple is bbox.to_tuple(), passed to the client."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_clothing").call_args
    assert a.args[1] == (10.0, 20.0, 30.0, 40.0)
    assert a.args[1] is not None


def test_clo_25():
    """L4789 the client receives the real PIL crop as first positional arg."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_clothing").call_args
    assert isinstance(a.args[0], Image.Image)
    assert a.args[0].size == (20, 20)


def test_clo_26():
    """L4788 bbox_tuple is bbox.to_tuple(), passed to the client."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_clothing").call_args
    assert a.args[1] == (10.0, 20.0, 30.0, 40.0)
    assert a.args[1] is not None


def test_clo_27():
    """L4789 the client call is (crop, bbox_tuple) - two positional args."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_clothing").call_args
    assert len(a.args) == 2
    assert not a.kwargs


def test_clo_28():
    """L4789 the client call is (crop, bbox_tuple) - two positional args."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_clothing").call_args
    assert len(a.args) == 2
    assert not a.kwargs


def test_clo_30(cap):
    """L4791 duration = perf_counter() - start_time and the success extra duration_ms == 1250 under the scripted clock."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert out["7"].confidence == 0.875
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert getattr(cap.recs[0], "duration_ms", MISSING) == 1250
    assert _msg(cap.recs[0]) == _DEBUG_CLO


def test_clo_31():
    """L4792 observe_enrichment_model_duration("clothing-via-service", duration) - the label."""
    before = _label0(DUR, "clothing-via-service")
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(DUR, "clothing-via-service")
    assert after is not None
    assert after - before == 1.0
    assert _label(DUR, "None") in (None, 0.0)


def test_clo_35():
    """L4792 observe_enrichment_model_duration("clothing-via-service", duration) - the label."""
    before = _label0(DUR, "clothing-via-service")
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(DUR, "clothing-via-service")
    assert after is not None
    assert after - before == 1.0
    assert _label(DUR, "XXclothing-via-serviceXX") in (None, 0.0)


def test_clo_36():
    """L4792 observe_enrichment_model_duration("clothing-via-service", duration) - the label."""
    before = _label0(DUR, "clothing-via-service")
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(DUR, "clothing-via-service")
    assert after is not None
    assert after - before == 1.0
    assert _label(DUR, "CLOTHING-VIA-SERVICE") in (None, 0.0)


def test_clo_40():
    """L4798 ClothingClassification.all_scores is a fresh empty dict."""
    remote = _cres()
    client = _client("classify_clothing", remote)
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    cls = out["7"]
    assert cls.all_scores == {}
    assert cls.all_scores is not remote.all_scores


def test_clo_42():
    """L4800 is_service_uniform is copied from the remote result."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    cls = out["7"]
    assert cls.is_service_uniform is True
    assert cls.top_category == "jacket"


def test_clo_43():
    """L4801 raw_description is remote_result.description."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert out["7"].raw_description == "blue jacket"


def test_clo_46():
    """L4798 ClothingClassification.all_scores is a fresh empty dict."""
    remote = _cres()
    client = _client("classify_clothing", remote)
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    cls = out["7"]
    assert cls.all_scores == {}
    assert cls.all_scores is not remote.all_scores


def test_clo_48():
    """L4800 is_service_uniform is copied from the remote result."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    cls = out["7"]
    assert cls.is_service_uniform is True
    assert cls.top_category == "jacket"


def test_clo_49():
    """L4801 raw_description is remote_result.description."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert out["7"].raw_description == "blue jacket"


def test_clo_50(cap):
    """L4804 the success log message is this exact f-string."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert _msg(cap.recs[0]) == _DEBUG_CLO


def test_clo_51(cap):
    """L4806 the success log extra carries service/detection_id/duration_ms."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "clothing-via-service"
    assert getattr(r0, "detection_id", MISSING) == "7"
    assert getattr(r0, "duration_ms", MISSING) == 1250


def test_clo_52(cap):
    """L4804 the success log message is this exact f-string."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert _msg(cap.recs[0]) == _DEBUG_CLO


def test_clo_53(cap):
    """L4806 the success log extra carries service/detection_id/duration_ms."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "clothing-via-service"
    assert getattr(r0, "detection_id", MISSING) == "7"
    assert getattr(r0, "duration_ms", MISSING) == 1250


def test_clo_60(cap):
    """L4806 the success log extra carries service/detection_id/duration_ms."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "clothing-via-service"
    assert getattr(r0, "detection_id", MISSING) == "7"
    assert getattr(r0, "duration_ms", MISSING) == 1250


def test_clo_61(cap):
    """L4806 the success log extra carries service/detection_id/duration_ms."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "clothing-via-service"
    assert getattr(r0, "detection_id", MISSING) == "7"
    assert getattr(r0, "duration_ms", MISSING) == 1250


def test_clo_62(cap):
    """L4791 duration = perf_counter() - start_time and the success extra duration_ms == 1250 under the scripted clock."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert out["7"].confidence == 0.875
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert getattr(cap.recs[0], "duration_ms", MISSING) == 1250
    assert _msg(cap.recs[0]) == _DEBUG_CLO


def test_clo_63(cap):
    """L4791 duration = perf_counter() - start_time and the success extra duration_ms == 1250 under the scripted clock."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert out["7"].confidence == 0.875
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert getattr(cap.recs[0], "duration_ms", MISSING) == 1250
    assert _msg(cap.recs[0]) == _DEBUG_CLO


def test_clo_64(cap):
    """L4791 duration = perf_counter() - start_time and the success extra duration_ms == 1250 under the scripted clock."""
    client = _client("classify_clothing", _cres())
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert out["7"].confidence == 0.875
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert getattr(cap.recs[0], "duration_ms", MISSING) == 1250
    assert _msg(cap.recs[0]) == _DEBUG_CLO


def test_clo_75(cap):
    """L4819 unavailable path logs the warning and returns {} (no raise)."""
    client = _client("classify_clothing", exc=EnrichmentUnavailableError("svc down"))
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.WARNING]
    assert _msg(cap.recs[0]) == _UNAVAIL_CLO


def test_clo_78(cap):
    """L4820 the unavailable warning carries service/error_type/detection_id."""
    client = _client("classify_clothing", exc=EnrichmentUnavailableError("svc down"))
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.WARNING]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "clothing-via-service"
    assert getattr(r0, "error_type", MISSING) == "EnrichmentUnavailableError"
    assert getattr(r0, "detection_id", MISSING) == "7"


def test_clo_98(cap):
    """L4871 unexpected-error path logs the sanitized message and returns {}."""
    client = _client("classify_clothing", exc=RuntimeError("boom password=hunter2"))
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    assert _msg(cap.recs[0]) == _UNEXP_CLO
    assert "hunter2" not in _msg(cap.recs[0])


def test_clo_100(cap):
    """L4877 exc_info=True attaches the live exception to the record."""
    exc = RuntimeError("boom password=hunter2")
    client = _client("classify_clothing", exc=exc)
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    assert cap.recs[0].exc_info is not None
    assert cap.recs[0].exc_info[1] is exc


def test_clo_102(cap):
    """L4872 the unexpected-error record carries service/error_type/detection_id."""
    exc = RuntimeError("boom password=hunter2")
    client = _client("classify_clothing", exc=exc)
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "clothing-via-service"
    assert getattr(r0, "error_type", MISSING) == "RuntimeError"
    assert getattr(r0, "detection_id", MISSING) == "7"
    assert r0.exc_info[1] is exc


def test_clo_103(cap):
    """L4877 exc_info=True attaches the live exception to the record."""
    exc = RuntimeError("boom password=hunter2")
    client = _client("classify_clothing", exc=exc)
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    assert cap.recs[0].exc_info is not None
    assert cap.recs[0].exc_info[1] is exc


def test_clo_104(cap):
    """L4871 unexpected-error path logs the sanitized message and returns {}."""
    client = _client("classify_clothing", exc=RuntimeError("boom password=hunter2"))
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    assert _msg(cap.recs[0]) == _UNEXP_CLO
    assert "hunter2" not in _msg(cap.recs[0])


def test_clo_114(cap):
    """L4877 exc_info=True attaches the live exception to the record."""
    exc = RuntimeError("boom password=hunter2")
    client = _client("classify_clothing", exc=exc)
    out = _run(_pipe(client)._classify_clothing_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    assert cap.recs[0].exc_info is not None
    assert cap.recs[0].exc_info[1] is exc


def test_pet_4():
    """L4365 record_enrichment_model_call("pet-via-service") - the prometheus label."""
    before = _label0(CALLS, "pet-via-service")
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(CALLS, "pet-via-service")
    assert isinstance(after, float)
    assert after - before == 1.0
    assert _label(CALLS, "None") in (None, 0.0)


def test_pet_5():
    """L4365 record_enrichment_model_call("pet-via-service") - the prometheus label."""
    before = _label0(CALLS, "pet-via-service")
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(CALLS, "pet-via-service")
    assert isinstance(after, float)
    assert after - before == 1.0
    assert _label(CALLS, "XXpet-via-serviceXX") in (None, 0.0)


def test_pet_6():
    """L4365 record_enrichment_model_call("pet-via-service") - the prometheus label."""
    before = _label0(CALLS, "pet-via-service")
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(CALLS, "pet-via-service")
    assert isinstance(after, float)
    assert after - before == 1.0
    assert _label(CALLS, "PET-VIA-SERVICE") in (None, 0.0)


def test_pet_10():
    """L4369 det_id = str(x.id) if x.id else str(i) - falsy ids fall back to the index."""
    client = _client("classify_pet", _pres())
    dets = [_det(9), _det(None), _det(0)]
    out = _run(_pipe(client)._classify_pets_via_service(dets, _img()))
    assert list(out) == ["9", "1", "2"]
    assert getattr(client, "classify_pet").call_count == 3


def test_pet_12():
    """L4369 det_id = str(x.id) if x.id else str(i) - falsy ids fall back to the index."""
    client = _client("classify_pet", _pres())
    dets = [_det(9), _det(None), _det(0)]
    out = _run(_pipe(client)._classify_pets_via_service(dets, _img()))
    assert list(out) == ["9", "1", "2"]
    assert getattr(client, "classify_pet").call_count == 3


def test_pet_20():
    """L4376 a failed crop CONTINUES the loop, it does not stop it."""
    client = _client("classify_pet", _pres())
    dets = [_det(None, **_OUT_OF_BOUNDS), _det(None)]
    out = _run(_pipe(client)._classify_pets_via_service(dets, _img()))
    assert list(out) == ["1"]
    assert getattr(client, "classify_pet").call_count == 1


def test_pet_21():
    """L4377 bbox_tuple is bbox.to_tuple(), passed to the client."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_pet").call_args
    assert a.args[1] == (10.0, 20.0, 30.0, 40.0)
    assert a.args[1] is not None


def test_pet_22():
    """L4377 bbox_tuple is bbox.to_tuple(), passed to the client."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_pet").call_args
    assert a.args[1] == (10.0, 20.0, 30.0, 40.0)
    assert a.args[1] is not None


def test_pet_23():
    """L4377 bbox_tuple is bbox.to_tuple(), passed to the client."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_pet").call_args
    assert a.args[1] == (10.0, 20.0, 30.0, 40.0)
    assert a.args[1] is not None


def test_pet_25():
    """L4378 the client receives the real PIL crop as first positional arg."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_pet").call_args
    assert isinstance(a.args[0], Image.Image)
    assert a.args[0].size == (20, 20)


def test_pet_26():
    """L4377 bbox_tuple is bbox.to_tuple(), passed to the client."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_pet").call_args
    assert a.args[1] == (10.0, 20.0, 30.0, 40.0)
    assert a.args[1] is not None


def test_pet_27():
    """L4378 the client call is (crop, bbox_tuple) - two positional args."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_pet").call_args
    assert len(a.args) == 2
    assert not a.kwargs


def test_pet_28():
    """L4378 the client call is (crop, bbox_tuple) - two positional args."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    a = getattr(client, "classify_pet").call_args
    assert len(a.args) == 2
    assert not a.kwargs


def test_pet_30(cap):
    """L4380 duration = perf_counter() - start_time and the success extra duration_ms == 1250 under the scripted clock."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert out["7"].confidence == 0.9375
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert getattr(cap.recs[0], "duration_ms", MISSING) == 1250
    assert _msg(cap.recs[0]) == _DEBUG_PET


def test_pet_31():
    """L4381 observe_enrichment_model_duration("pet-via-service", duration) - the label."""
    before = _label0(DUR, "pet-via-service")
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(DUR, "pet-via-service")
    assert after is not None
    assert after - before == 1.0
    assert _label(DUR, "None") in (None, 0.0)


def test_pet_35():
    """L4381 observe_enrichment_model_duration("pet-via-service", duration) - the label."""
    before = _label0(DUR, "pet-via-service")
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(DUR, "pet-via-service")
    assert after is not None
    assert after - before == 1.0
    assert _label(DUR, "XXpet-via-serviceXX") in (None, 0.0)


def test_pet_36():
    """L4381 observe_enrichment_model_duration("pet-via-service", duration) - the label."""
    before = _label0(DUR, "pet-via-service")
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    after = _label(DUR, "pet-via-service")
    assert after is not None
    assert after - before == 1.0
    assert _label(DUR, "PET-VIA-SERVICE") in (None, 0.0)


def test_pet_40():
    """L4386 cat_score is the literal 0.0 for the service path."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out["7"].cat_score == 0.0
    assert out["7"].animal_type == "dog"


def test_pet_41():
    """L4387 dog_score is the literal 0.0 for the service path."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out["7"].dog_score == 0.0
    assert out["7"].animal_type == "dog"


def test_pet_47():
    """L4388 is_household_pet is copied from the remote result."""
    remote = _pres()
    assert remote.is_household_pet is False
    client = _client("classify_pet", remote)
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out["7"].is_household_pet is False


def test_pet_48():
    """L4386 cat_score is the literal 0.0 for the service path."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out["7"].cat_score == 0.0
    assert out["7"].animal_type == "dog"


def test_pet_49():
    """L4387 dog_score is the literal 0.0 for the service path."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out["7"].dog_score == 0.0
    assert out["7"].animal_type == "dog"


def test_pet_50(cap):
    """L4391 the success log message is this exact f-string."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert _msg(cap.recs[0]) == _DEBUG_PET


def test_pet_51(cap):
    """L4393 the success log extra carries service/detection_id/duration_ms."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "pet-via-service"
    assert getattr(r0, "detection_id", MISSING) == "7"
    assert getattr(r0, "duration_ms", MISSING) == 1250


def test_pet_52(cap):
    """L4391 the success log message is this exact f-string."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert _msg(cap.recs[0]) == _DEBUG_PET


def test_pet_53(cap):
    """L4393 the success log extra carries service/detection_id/duration_ms."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "pet-via-service"
    assert getattr(r0, "detection_id", MISSING) == "7"
    assert getattr(r0, "duration_ms", MISSING) == 1250


def test_pet_60(cap):
    """L4393 the success log extra carries service/detection_id/duration_ms."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "pet-via-service"
    assert getattr(r0, "detection_id", MISSING) == "7"
    assert getattr(r0, "duration_ms", MISSING) == 1250


def test_pet_61(cap):
    """L4393 the success log extra carries service/detection_id/duration_ms."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "pet-via-service"
    assert getattr(r0, "detection_id", MISSING) == "7"
    assert getattr(r0, "duration_ms", MISSING) == 1250


def test_pet_62(cap):
    """L4380 duration = perf_counter() - start_time and the success extra duration_ms == 1250 under the scripted clock."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert out["7"].confidence == 0.9375
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert getattr(cap.recs[0], "duration_ms", MISSING) == 1250
    assert _msg(cap.recs[0]) == _DEBUG_PET


def test_pet_63(cap):
    """L4380 duration = perf_counter() - start_time and the success extra duration_ms == 1250 under the scripted clock."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert out["7"].confidence == 0.9375
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert getattr(cap.recs[0], "duration_ms", MISSING) == 1250
    assert _msg(cap.recs[0]) == _DEBUG_PET


def test_pet_64(cap):
    """L4380 duration = perf_counter() - start_time and the success extra duration_ms == 1250 under the scripted clock."""
    client = _client("classify_pet", _pres())
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert list(out) == ["7"]
    assert out["7"].confidence == 0.9375
    assert [r.levelno for r in cap.recs] == [logging.DEBUG]
    assert getattr(cap.recs[0], "duration_ms", MISSING) == 1250
    assert _msg(cap.recs[0]) == _DEBUG_PET


def test_pet_75(cap):
    """L4408 unavailable path logs the warning and returns {} (no raise)."""
    client = _client("classify_pet", exc=EnrichmentUnavailableError("svc down"))
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.WARNING]
    assert _msg(cap.recs[0]) == _UNAVAIL_PET


def test_pet_78(cap):
    """L4409 the unavailable warning carries service/error_type/detection_id."""
    client = _client("classify_pet", exc=EnrichmentUnavailableError("svc down"))
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.WARNING]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "pet-via-service"
    assert getattr(r0, "error_type", MISSING) == "EnrichmentUnavailableError"
    assert getattr(r0, "detection_id", MISSING) == "7"


def test_pet_98(cap):
    """L4461 unexpected-error path logs the sanitized message and returns {}."""
    client = _client("classify_pet", exc=RuntimeError("boom password=hunter2"))
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    assert _msg(cap.recs[0]) == _UNEXP_PET
    assert "hunter2" not in _msg(cap.recs[0])


def test_pet_100(cap):
    """L4467 exc_info=True attaches the live exception to the record."""
    exc = RuntimeError("boom password=hunter2")
    client = _client("classify_pet", exc=exc)
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    assert cap.recs[0].exc_info is not None
    assert cap.recs[0].exc_info[1] is exc


def test_pet_102(cap):
    """L4462 the unexpected-error record carries service/error_type/detection_id."""
    exc = RuntimeError("boom password=hunter2")
    client = _client("classify_pet", exc=exc)
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    r0 = cap.recs[0]
    assert getattr(r0, "service", MISSING) == "pet-via-service"
    assert getattr(r0, "error_type", MISSING) == "RuntimeError"
    assert getattr(r0, "detection_id", MISSING) == "7"
    assert r0.exc_info[1] is exc


def test_pet_103(cap):
    """L4467 exc_info=True attaches the live exception to the record."""
    exc = RuntimeError("boom password=hunter2")
    client = _client("classify_pet", exc=exc)
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    assert cap.recs[0].exc_info is not None
    assert cap.recs[0].exc_info[1] is exc


def test_pet_104(cap):
    """L4461 unexpected-error path logs the sanitized message and returns {}."""
    client = _client("classify_pet", exc=RuntimeError("boom password=hunter2"))
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    assert _msg(cap.recs[0]) == _UNEXP_PET
    assert "hunter2" not in _msg(cap.recs[0])


def test_pet_114(cap):
    """L4467 exc_info=True attaches the live exception to the record."""
    exc = RuntimeError("boom password=hunter2")
    client = _client("classify_pet", exc=exc)
    out = _run(_pipe(client)._classify_pets_via_service([_det(7)], _img()))
    assert out == {}
    assert [r.levelno for r in cap.recs] == [logging.ERROR]
    assert cap.recs[0].exc_info is not None
    assert cap.recs[0].exc_info[1] is exc


def test_ctx_4_no_vision_string_is_suppressed():
    """L1174-L1178 an extraction result that formats to "No vision ..." adds nothing.

    Measured: a bare BatchExtractionResult is truthy and formats to
    "No vision extraction data available.", and the shipped context string for
    that result carries no vision block at all.
    """
    ber = _vision_none()
    assert ber.__class__ is BatchExtractionResult and bool(ber)
    obj = M.EnrichmentResult()
    obj.vision_extraction = ber
    assert _ctx(obj) == "No additional context extracted."


def test_ctx_7_vision_gate_prefix_is_no_vision_case_sensitive():
    """L1175 the gate is exactly `vision_str.startswith("No vision")`.

    Both measured observations below are produced by shipped code, and they are
    the only two outcomes the startswith() argument can ever flip: a string that
    begins with the shipped prefix "No vision" is suppressed, and one that
    begins with the same words in lower case is kept.
    """
    import backend.services.vision_extractor as VE

    real = VE.format_batch_extraction_result
    obj = M.EnrichmentResult()
    obj.vision_extraction = _vision_some()
    obj2 = M.EnrichmentResult()
    obj2.vision_extraction = _vision_some()
    try:
        VE.format_batch_extraction_result = lambda *a, **k: "No vision extraction data available."
        assert _ctx(obj) == "No additional context extracted."
        VE.format_batch_extraction_result = lambda *a, **k: "no vision extraction data available."
        assert _ctx(obj2) == NL2.join(
            ["## Vision Analysis", "no vision extraction data available."]
        )
    finally:
        VE.format_batch_extraction_result = real


def test_ctx_8_vision_gate_prefix_is_no_vision_case_sensitive():
    """L1175 the gate is exactly `vision_str.startswith("No vision")`.

    Both measured observations below are produced by shipped code, and they are
    the only two outcomes the startswith() argument can ever flip: a string that
    begins with the shipped prefix "No vision" is suppressed, and one that
    begins with the same words in lower case is kept.
    """
    import backend.services.vision_extractor as VE

    real = VE.format_batch_extraction_result
    obj = M.EnrichmentResult()
    obj.vision_extraction = _vision_some()
    obj2 = M.EnrichmentResult()
    obj2.vision_extraction = _vision_some()
    try:
        VE.format_batch_extraction_result = lambda *a, **k: "No vision extraction data available."
        assert _ctx(obj) == "No additional context extracted."
        VE.format_batch_extraction_result = lambda *a, **k: "no vision extraction data available."
        assert _ctx(obj2) == NL2.join(
            ["## Vision Analysis", "no vision extraction data available."]
        )
    finally:
        VE.format_batch_extraction_result = real


def test_ctx_9_vision_gate_prefix_is_no_vision_case_sensitive():
    """L1175 the gate is exactly `vision_str.startswith("No vision")`.

    Both measured observations below are produced by shipped code, and they are
    the only two outcomes the startswith() argument can ever flip: a string that
    begins with the shipped prefix "No vision" is suppressed, and one that
    begins with the same words in lower case is kept.
    """
    import backend.services.vision_extractor as VE

    real = VE.format_batch_extraction_result
    obj = M.EnrichmentResult()
    obj.vision_extraction = _vision_some()
    obj2 = M.EnrichmentResult()
    obj2.vision_extraction = _vision_some()
    try:
        VE.format_batch_extraction_result = lambda *a, **k: "No vision extraction data available."
        assert _ctx(obj) == "No additional context extracted."
        VE.format_batch_extraction_result = lambda *a, **k: "no vision extraction data available."
        assert _ctx(obj2) == NL2.join(
            ["## Vision Analysis", "no vision extraction data available."]
        )
    finally:
        VE.format_batch_extraction_result = real


def test_ctx_11_vision_analysis_header_line():
    """L1176 the header line emitted before a usable vision string is exact."""
    import backend.services.vision_extractor as VE

    real = VE.format_batch_extraction_result
    obj = M.EnrichmentResult()
    obj.vision_extraction = _vision_some()
    try:
        VE.format_batch_extraction_result = lambda *a, **k: "PERSONS-BODY"
        assert _ctx(obj) == NL2.join(["## Vision Analysis", "PERSONS-BODY"])
    finally:
        VE.format_batch_extraction_result = real


def test_ctx_12_vision_analysis_header_line():
    """L1176 the header line emitted before a usable vision string is exact."""
    import backend.services.vision_extractor as VE

    real = VE.format_batch_extraction_result
    obj = M.EnrichmentResult()
    obj.vision_extraction = _vision_some()
    try:
        VE.format_batch_extraction_result = lambda *a, **k: "PERSONS-BODY"
        assert _ctx(obj) == NL2.join(["## Vision Analysis", "PERSONS-BODY"])
    finally:
        VE.format_batch_extraction_result = real


def test_ctx_13_vision_analysis_header_line():
    """L1176 the header line emitted before a usable vision string is exact."""
    import backend.services.vision_extractor as VE

    real = VE.format_batch_extraction_result
    obj = M.EnrichmentResult()
    obj.vision_extraction = _vision_some()
    try:
        VE.format_batch_extraction_result = lambda *a, **k: "PERSONS-BODY"
        assert _ctx(obj) == NL2.join(["## Vision Analysis", "PERSONS-BODY"])
    finally:
        VE.format_batch_extraction_result = real


def test_ctx_15_vehicle_only_matches_still_emit_the_reid_block():
    """L1180 `person_reid_matches or vehicle_reid_matches` - either side suffices."""
    obj = M.EnrichmentResult()
    obj.person_reid_matches = {}
    obj.vehicle_reid_matches = {"v1": [_match("v1")]}
    text = _ctx(obj)
    assert "## Re-Identification" in text
    assert "## Vehicle Re-Identification" in text
    assert "Camera: cam1, Time: 30 seconds ago (similarity: 87%)" in text


def test_ctx_16_reid_body_is_the_formatter_output():
    """L1181-L1184 the re-id body line is format_full_reid_context() output."""
    from backend.services.reid_service import format_full_reid_context

    pm = {"p1": [_match("p1")]}
    body = format_full_reid_context(pm, {})
    obj = M.EnrichmentResult()
    obj.person_reid_matches = pm
    obj.vehicle_reid_matches = {}
    assert _ctx(obj) == NL2.join(["## Re-Identification", body])
    assert "## Person Re-Identification" in body
