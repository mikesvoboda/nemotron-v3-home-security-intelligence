"""Chunk-10 kill battery: enrichment_pipeline mutation survivors.

Scope (all measured against pristine shipped source, HEAD
backend/services/enrichment_pipeline.py):
  * EnrichmentPipeline._classify_person_clothing  (shipped lines 6576-6726)
  * EnrichmentPipeline._classify_pets             (shipped lines 7112-7267)
  * EnrichmentPipeline.enrich_batch               (shipped lines 5555-5731;
    the completion log line 5708-5729 clip_threats / clip_anomaly clauses)

Every assertion pins OBSERVED shipped behaviour (probe harness
/tmp/wp-ep/probes/c10/probe_cls.py).  Patches are applied at the IMPORT site
(`backend.services.enrichment_pipeline.X`).

HARNESS NOTE (important, and the reason for the module-scoped patch fixture):
ep_plugin binds a mutant by exec'ing its body in a SNAPSHOT of the live module
dict taken at bind time (function scope, autouse).  A module-level global that
is patched inside a test body therefore is NOT visible to the mutant - the
mutant resolves the shipped original and the kill is masked.  Consequently every
MODULE-LEVEL collaborator (record_enrichment_model_call, classify_clothing,
classify_pet, add_span_event, record_cascade_*) is patched by the module-scoped
fixture below, which runs BEFORE the plugin's bind, and the mocks are simply
re-configured per test.  Methods (`self._crop_to_bbox`) are instance/class
attributes resolved at call time and may be patched per test.
Async is driven through asyncio.run because the verification invocation runs
with `-o addopts=` (no asyncio_mode=auto from pyproject).
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import backend.services.enrichment_pipeline as M
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
)

BOX = BoundingBox(x1=0, y1=0, x2=10, y2=10)
MODEL_SENTINEL = {"model": "SENTINEL-MODEL-DATA"}
CROP_SENTINEL = "SENTINEL-CROP"
LOGGER_NAME = "backend.services.enrichment_pipeline"


# --------------------------------------------------------------------------
# module-scoped import-site patches (mutant-visible: see module docstring)
# --------------------------------------------------------------------------
class Collab:
    def __init__(self):
        self.model_calls = MagicMock(name="record_enrichment_model_call")
        self.classify_clothing = AsyncMock(name="classify_clothing")
        self.classify_pet = AsyncMock(name="classify_pet")
        self.span = MagicMock(name="add_span_event")
        self.cascade_processed = MagicMock(name="record_cascade_processed")
        self.cascade_skipped = MagicMock(name="record_cascade_skipped")

    def reset(self):
        for m in (
            self.model_calls,
            self.classify_clothing,
            self.classify_pet,
            self.span,
            self.cascade_processed,
            self.cascade_skipped,
        ):
            m.reset_mock()
        self.classify_clothing.side_effect = None
        self.classify_clothing.return_value = None
        self.classify_pet.side_effect = None
        self.classify_pet.return_value = None


_COLLAB = Collab()


@pytest.fixture(scope="module", autouse=True)
def _collab_module():
    with (
        patch.object(M, "record_enrichment_model_call", new=_COLLAB.model_calls),
        patch.object(M, "classify_clothing", new=_COLLAB.classify_clothing),
        patch.object(M, "classify_pet", new=_COLLAB.classify_pet),
        patch.object(M, "add_span_event", new=_COLLAB.span),
        patch.object(M, "record_cascade_processed", new=_COLLAB.cascade_processed),
        patch.object(M, "record_cascade_skipped", new=_COLLAB.cascade_skipped),
    ):
        yield _COLLAB


@pytest.fixture(autouse=True)
def collab():
    _COLLAB.reset()
    return _COLLAB


# --------------------------------------------------------------------------
# log capture
# --------------------------------------------------------------------------
class Cap(logging.Handler):
    """LogRecords emitted by the pipeline logger while attached."""

    def __init__(self):
        super().__init__()
        self.recs: list[logging.LogRecord] = []

    def emit(self, record):
        self.recs.append(record)

    def clear(self):
        del self.recs[:]

    @staticmethod
    def text(record):
        # safe: a mutant that produces an un-formattable message must fail the
        # assertion below rather than blow up inside the matcher
        try:
            return record.getMessage()
        except Exception as exc:  # pragma: no cover - mutant-only path
            return f"<getMessage-raised:{type(exc).__name__}:{exc}>"

    def one(self, levelname, needle):
        hits = [r for r in self.recs if r.levelname == levelname and needle in self.text(r)]
        assert len(hits) == 1, (
            f"expected exactly 1 {levelname} record containing {needle!r}, got "
            f"{[(r.levelname, self.text(r)) for r in self.recs]}"
        )
        return hits[0]

    def messages(self):
        return [self.text(r) for r in self.recs]


@pytest.fixture
def logs():
    lg = logging.getLogger(LOGGER_NAME)
    cap = Cap()
    saved = (list(lg.handlers), lg.level, lg.propagate)
    lg.handlers = [cap]
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    try:
        yield cap
    finally:
        lg.handlers = saved[0]
        # MUST go through setLevel(): py3.13+ caches isEnabledFor results
        # per logger and only setLevel() calls manager._clear_cache().
        # A direct `lg.level =` restore left the cache saying "DEBUG
        # enabled" for every later test in the same process (MEASURED:
        # batch26_19 record-count flake, seed 1689069813).
        lg.setLevel(saved[1])
        lg.propagate = saved[2]


# --------------------------------------------------------------------------
# other helpers
# --------------------------------------------------------------------------
def det(id_=1, cls="person"):
    return DetectionInput(class_name=cls, confidence=0.9, bbox=BOX, id=id_)


def loader(exc=None):
    """Fake model_manager: `async with load(name) as data` yields/raises."""
    mm = MagicMock(name="model_manager")
    ctx = mm.load.return_value
    if exc is None:
        ctx.__aenter__ = AsyncMock(return_value=MODEL_SENTINEL)
    else:
        ctx.__aenter__ = AsyncMock(side_effect=exc)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return mm


def crop_ok():
    return patch.object(
        M.EnrichmentPipeline, "_crop_to_bbox", new=AsyncMock(return_value=CROP_SENTINEL)
    )


def status_error(code):
    req = httpx.Request("POST", "http://enrichment.local/classify")
    resp = httpx.Response(code, request=req)
    return httpx.HTTPStatusError(f"HTTP {code}", request=req, response=resp)


def svc_exc():
    return M.EnrichmentUnavailableError("svc-detail")


# ==========================================================================
# 1. happy paths - shipped success semantics
# ==========================================================================
async def _a_clothing_success_pinned(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader()
    cls = M.ClothingClassification(
        top_category="hoodie", confidence=0.75, raw_description="grey hoodie"
    )
    crop = AsyncMock(return_value=CROP_SENTINEL)
    collab.classify_clothing.return_value = cls
    with patch.object(M.EnrichmentPipeline, "_crop_to_bbox", new=crop):
        out = await pipe._classify_person_clothing([det(7)], "IMG")

    # shipped: metric "clothing" recorded once BEFORE the loop, then
    # "fashion-clip" after each successful classification
    assert [c.args for c in collab.model_calls.call_args_list] == [
        ("clothing",),
        ("fashion-clip",),
    ]
    assert collab.classify_clothing.await_count == 1
    assert collab.classify_clothing.await_args.args == (MODEL_SENTINEL, CROP_SENTINEL)
    assert collab.classify_clothing.await_args.kwargs == {}
    assert list(out.keys()) == ["7"]
    assert out["7"] is cls
    rec = logs.one("DEBUG", "Person 7 clothing: grey hoodie (75%)")
    assert rec.getMessage() == "Person 7 clothing: grey hoodie (75%)"
    assert rec.levelname == "DEBUG"


async def _a_clothing_success_metric_order_two_persons(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader()
    cls = M.ClothingClassification(top_category="tee", confidence=0.5, raw_description="grey tee")
    collab.classify_clothing.return_value = cls
    with crop_ok():
        out = await pipe._classify_person_clothing([det(1), det(2)], "IMG")
    assert [c.args for c in collab.model_calls.call_args_list] == [
        ("clothing",),
        ("fashion-clip",),
        ("fashion-clip",),
    ]
    assert list(out.keys()) == ["1", "2"]
    assert set(logs.messages()) == {
        "Person 1 clothing: grey tee (50%)",
        "Person 2 clothing: grey tee (50%)",
    }


async def _a_pets_success_pinned(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader()
    res = M.PetClassificationResult(animal_type="cat", confidence=0.5, cat_score=0.5, dog_score=0.5)
    crop = AsyncMock(return_value=CROP_SENTINEL)
    collab.classify_pet.return_value = res
    with patch.object(M.EnrichmentPipeline, "_crop_to_bbox", new=crop):
        out = await pipe._classify_pets([det(9, "cat")], "IMG")

    assert [c.args for c in collab.model_calls.call_args_list] == [
        ("pet",),
        ("pet-classifier",),
    ]
    assert collab.classify_pet.await_count == 1
    assert collab.classify_pet.await_args.args == (MODEL_SENTINEL, CROP_SENTINEL)
    assert collab.classify_pet.await_args.kwargs == {}
    assert list(out.keys()) == ["9"]
    assert out["9"] is res
    rec = logs.one("DEBUG", "Animal 9 classified as cat (50% confidence)")
    assert rec.getMessage() == (
        "Animal 9 classified as cat (50% confidence), is_household_pet=True"
    )


async def _a_pets_success_metric_order_two_animals(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader()
    res = M.PetClassificationResult(animal_type="dog", confidence=0.9, cat_score=0.1, dog_score=0.9)
    collab.classify_pet.return_value = res
    with crop_ok():
        out = await pipe._classify_pets([det(1, "dog"), det(2, "dog")], "IMG")
    assert [c.args for c in collab.model_calls.call_args_list] == [
        ("pet",),
        ("pet-classifier",),
        ("pet-classifier",),
    ]
    assert list(out.keys()) == ["1", "2"]
    assert set(logs.messages()) == {
        "Animal 1 classified as dog (90% confidence), is_household_pet=True",
        "Animal 2 classified as dog (90% confidence), is_household_pet=True",
    }


async def _a_clothing_crop_none_skips_first_and_continues(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader()
    cls = M.ClothingClassification(top_category="hat", confidence=0.3, raw_description="wool hat")
    crop = AsyncMock(side_effect=[None, CROP_SENTINEL])
    collab.classify_clothing.return_value = cls
    with patch.object(M.EnrichmentPipeline, "_crop_to_bbox", new=crop):
        out = await pipe._classify_person_clothing([det(None), det(None)], "IMG")
    # shipped: a None crop `continue`s, so the LOOP KEEPS GOING
    assert collab.classify_clothing.await_count == 1
    assert collab.classify_clothing.await_args.args == (MODEL_SENTINEL, CROP_SENTINEL)
    assert list(out.keys()) == ["1"]
    assert [c.args for c in collab.model_calls.call_args_list] == [
        ("clothing",),
        ("fashion-clip",),
    ]
    # shipped: a skipped crop emits no log record at all
    assert logs.messages() == ["Person 1 clothing: wool hat (30%)"]


async def _a_pets_crop_none_skips_first_and_continues(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader()
    res = M.PetClassificationResult(animal_type="cat", confidence=0.8, cat_score=0.8, dog_score=0.2)
    crop = AsyncMock(side_effect=[None, CROP_SENTINEL])
    collab.classify_pet.return_value = res
    with patch.object(M.EnrichmentPipeline, "_crop_to_bbox", new=crop):
        out = await pipe._classify_pets([det(None, "cat"), det(None, "cat")], "IMG")
    assert collab.classify_pet.await_count == 1
    assert collab.classify_pet.await_args.args == (MODEL_SENTINEL, CROP_SENTINEL)
    assert list(out.keys()) == ["1"]
    assert [c.args for c in collab.model_calls.call_args_list] == [
        ("pet",),
        ("pet-classifier",),
    ]
    assert logs.messages() == ["Animal 1 classified as cat (80% confidence), is_household_pet=True"]


async def _a_clothing_index_key_for_falsy_ids(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader()
    cls = M.ClothingClassification(
        top_category="jacket", confidence=0.4, raw_description="black jacket"
    )
    collab.classify_clothing.return_value = cls
    with crop_ok():
        out = await pipe._classify_person_clothing([det(None), det(0)], "IMG")
    # shipped: falsy id (None AND 0) falls back to the enumerate index
    assert list(out.keys()) == ["0", "1"]
    assert set(logs.messages()) == {
        "Person 0 clothing: black jacket (40%)",
        "Person 1 clothing: black jacket (40%)",
    }


async def _a_pets_index_key_for_falsy_ids(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader()
    res = M.PetClassificationResult(animal_type="dog", confidence=0.6, cat_score=0.4, dog_score=0.6)
    collab.classify_pet.return_value = res
    with crop_ok():
        out = await pipe._classify_pets([det(None, "dog"), det(0, "dog")], "IMG")
    assert list(out.keys()) == ["0", "1"]
    assert set(logs.messages()) == {
        "Animal 0 classified as dog (60% confidence), is_household_pet=True",
        "Animal 1 classified as dog (60% confidence), is_household_pet=True",
    }


async def _a_clothing_per_person_failure_continues_loop(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader()
    cls = M.ClothingClassification(
        top_category="vest", confidence=0.2, raw_description="hi-vis vest"
    )

    async def classify(_model, crop):
        if crop == "BAD":
            raise ValueError(f"boom-{crop}")
        return cls

    crop = AsyncMock(side_effect=["BAD", "BAD", CROP_SENTINEL])
    collab.classify_clothing.side_effect = classify
    with patch.object(M.EnrichmentPipeline, "_crop_to_bbox", new=crop):
        out = await pipe._classify_person_clothing([det(11), det(12), det(13)], "IMG")
    # shipped: a per-person failure logs and CONTINUES with the next person
    assert collab.classify_clothing.await_count == 3
    assert list(out.keys()) == ["13"]
    assert out["13"] is cls
    assert logs.messages() == [
        "Clothing classification failed for person 11: boom-BAD",
        "Clothing classification failed for person 12: boom-BAD",
        "Person 13 clothing: hi-vis vest (20%)",
    ]
    assert [c.args for c in collab.model_calls.call_args_list] == [
        ("clothing",),
        ("fashion-clip",),
    ]


async def _a_pets_per_animal_failure_continues_loop(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader()
    res = M.PetClassificationResult(animal_type="dog", confidence=0.7, cat_score=0.3, dog_score=0.7)

    async def classify(_model, crop):
        if crop == "BAD":
            raise RuntimeError(f"boom-{crop}")
        return res

    crop = AsyncMock(side_effect=["BAD", "BAD", CROP_SENTINEL])
    collab.classify_pet.side_effect = classify
    with patch.object(M.EnrichmentPipeline, "_crop_to_bbox", new=crop):
        out = await pipe._classify_pets([det(21, "dog"), det(22, "dog"), det(23, "dog")], "IMG")
    assert collab.classify_pet.await_count == 3
    assert list(out.keys()) == ["23"]
    assert out["23"] is res
    assert logs.messages() == [
        "Pet classification failed for animal 21: boom-BAD",
        "Pet classification failed for animal 22: boom-BAD",
        "Animal 23 classified as dog (70% confidence), is_household_pet=True",
    ]
    assert [c.args for c in collab.model_calls.call_args_list] == [
        ("pet",),
        ("pet-classifier",),
    ]


async def _a_clothing_empty_persons_is_noop(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = MagicMock()
    out = await pipe._classify_person_clothing([], "IMG")
    assert out == {}
    pipe.model_manager.load.assert_not_called()
    collab.model_calls.assert_not_called()
    assert logs.messages() == []


async def _a_pets_empty_animals_is_noop(logs, collab):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = MagicMock()
    out = await pipe._classify_pets([], "IMG")
    assert out == {}
    pipe.model_manager.load.assert_not_called()
    collab.model_calls.assert_not_called()
    assert logs.messages() == []


# ==========================================================================
# 2. exception-arm pinning - _classify_person_clothing
# ==========================================================================
async def _a_clothing_keyerror_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(KeyError("fashion-clip"))
    out = await pipe._classify_person_clothing([det(1)], "IMG")
    assert out == {}
    assert pipe.model_manager.load.call_args_list == [(("fashion-clip",), {})]
    assert len(logs.recs) == 1
    rec = logs.one("WARNING", "model not available")
    assert rec.getMessage() == "fashion-clip model not available in MODEL_ZOO"
    assert rec.exc_info is None
    assert rec.detection_type == "person"
    assert rec.operation == "clothing_classification"
    assert rec.error_category == "parse_error"
    assert getattr(rec, "is_transient", None) is None
    assert not hasattr(rec, "is_transient")


async def _a_clothing_service_unavailable_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(svc_exc())
    out = await pipe._classify_person_clothing([det(1)], "IMG")
    assert out == {}
    assert len(logs.recs) == 1
    rec = logs.one("WARNING", "service unavailable")
    assert rec.getMessage() == "Clothing classification service unavailable: svc-detail"
    assert rec.detection_type == "person"
    assert rec.operation == "clothing_classification"
    assert rec.error_type == "EnrichmentUnavailableError"
    assert rec.error_category == "service_unavailable"
    assert rec.is_transient is True


async def _a_clothing_connect_error_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(httpx.ConnectError("conn-refused"))
    out = await pipe._classify_person_clothing([det(1)], "IMG")
    assert out == {}
    assert len(logs.recs) == 1
    rec = logs.one("WARNING", "connection failed")
    assert rec.getMessage() == "Clothing classification connection failed: conn-refused"
    assert rec.error_type == "ConnectError"
    assert rec.error_category == "service_unavailable"
    assert rec.is_transient is True


async def _a_clothing_timeout_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(httpx.TimeoutException("slowpoke"))
    out = await pipe._classify_person_clothing([det(1)], "IMG")
    assert out == {}
    assert len(logs.recs) == 1
    rec = logs.one("WARNING", "timed out")
    assert rec.getMessage() == "Clothing classification timed out: slowpoke"
    assert rec.detection_type == "person"
    assert rec.operation == "clothing_classification"
    assert rec.error_type == "TimeoutException"
    assert rec.error_category == "timeout"
    assert rec.is_transient is True


async def _a_clothing_server_error_500_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(status_error(500))
    out = await pipe._classify_person_clothing([det(1)], "IMG")
    assert out == {}
    assert len(logs.recs) == 1
    rec = logs.one("WARNING", "server error")
    assert rec.getMessage() == "Clothing classification server error (HTTP 500)"
    assert rec.error_type == "HTTPStatusError"
    assert rec.error_category == "server_error"
    assert rec.status_code == 500
    assert rec.is_transient is True


async def _a_clothing_server_error_599_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(status_error(599))
    out = await pipe._classify_person_clothing([det(1)], "IMG")
    assert out == {}
    rec = logs.one("WARNING", "server error")
    assert rec.getMessage() == "Clothing classification server error (HTTP 599)"
    assert rec.error_category == "server_error"
    assert rec.status_code == 599
    assert rec.is_transient is True


async def _a_clothing_client_error_404_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(status_error(404))
    out = await pipe._classify_person_clothing([det(1)], "IMG")
    assert out == {}
    rec = logs.one("ERROR", "client error")
    assert rec.getMessage() == "Clothing classification client error (HTTP 404)"
    assert rec.error_category == "client_error"
    assert rec.status_code == 404
    assert rec.is_transient is False


async def _a_clothing_client_error_600_arm(logs):
    """Shipped boundary: 600 is NOT 5xx, so it lands in the client-error arm."""
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(status_error(600))
    out = await pipe._classify_person_clothing([det(1)], "IMG")
    assert out == {}
    rec = logs.one("ERROR", "client error")
    assert rec.getMessage() == "Clothing classification client error (HTTP 600)"
    assert rec.error_category == "client_error"
    assert rec.status_code == 600
    assert rec.is_transient is False


async def _a_clothing_parse_error_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(ValueError("bad-payload"))
    out = await pipe._classify_person_clothing([det(1)], "IMG")
    assert out == {}
    assert len(logs.recs) == 1
    rec = logs.one("ERROR", "parse error")
    assert rec.getMessage() == "Clothing classification parse error: bad-payload"
    assert rec.error_type == "ValueError"
    assert rec.error_category == "parse_error"
    assert rec.is_transient is False


async def _a_clothing_unexpected_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(RuntimeError("kaboom"))
    out = await pipe._classify_person_clothing([det(1)], "IMG")
    assert out == {}
    assert len(logs.recs) == 1
    rec = logs.one("ERROR", "Clothing classification error")
    assert rec.getMessage() == "Clothing classification error"
    assert rec.exc_info is not None
    assert rec.detection_type == "person"
    assert rec.operation == "clothing_classification"
    assert rec.error_category == "unexpected"
    assert rec.is_transient is True
    assert getattr(rec, "error_type", None) is None
    assert not hasattr(rec, "error_type")


# ==========================================================================
# 3. exception-arm pinning - _classify_pets
# ==========================================================================
async def _a_pets_keyerror_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(KeyError("pet-classifier"))
    out = await pipe._classify_pets([det(1, "cat")], "IMG")
    assert out == {}
    assert pipe.model_manager.load.call_args_list == [(("pet-classifier",), {})]
    assert len(logs.recs) == 1
    rec = logs.one("WARNING", "model not available")
    assert rec.getMessage() == "pet-classifier model not available in MODEL_ZOO"
    assert rec.detection_type == "animal"
    assert rec.operation == "pet_classification"
    assert rec.error_category == "parse_error"
    assert not hasattr(rec, "is_transient")


async def _a_pets_service_unavailable_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(svc_exc())
    out = await pipe._classify_pets([det(1, "cat")], "IMG")
    assert out == {}
    assert len(logs.recs) == 1
    rec = logs.one("WARNING", "service unavailable")
    assert rec.getMessage() == "Pet classification service unavailable: svc-detail"
    assert rec.detection_type == "animal"
    assert rec.operation == "pet_classification"
    assert rec.error_type == "EnrichmentUnavailableError"
    assert rec.error_category == "service_unavailable"
    assert rec.is_transient is True


async def _a_pets_connect_error_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(httpx.ConnectError("conn-refused"))
    out = await pipe._classify_pets([det(1, "cat")], "IMG")
    assert out == {}
    rec = logs.one("WARNING", "connection failed")
    assert rec.getMessage() == "Pet classification connection failed: conn-refused"
    assert rec.error_type == "ConnectError"
    assert rec.error_category == "service_unavailable"
    assert rec.is_transient is True


async def _a_pets_timeout_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(httpx.TimeoutException("slowpoke"))
    out = await pipe._classify_pets([det(1, "cat")], "IMG")
    assert out == {}
    assert len(logs.recs) == 1
    rec = logs.one("WARNING", "timed out")
    assert rec.getMessage() == "Pet classification timed out: slowpoke"
    assert rec.detection_type == "animal"
    assert rec.operation == "pet_classification"
    assert rec.error_type == "TimeoutException"
    assert rec.error_category == "timeout"
    assert rec.is_transient is True


async def _a_pets_server_error_500_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(status_error(500))
    out = await pipe._classify_pets([det(1, "cat")], "IMG")
    assert out == {}
    assert len(logs.recs) == 1
    rec = logs.one("WARNING", "server error")
    assert rec.getMessage() == "Pet classification server error (HTTP 500)"
    assert rec.error_type == "HTTPStatusError"
    assert rec.error_category == "server_error"
    assert rec.status_code == 500
    assert rec.is_transient is True


async def _a_pets_server_error_599_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(status_error(599))
    out = await pipe._classify_pets([det(1, "cat")], "IMG")
    assert out == {}
    rec = logs.one("WARNING", "server error")
    assert rec.getMessage() == "Pet classification server error (HTTP 599)"
    assert rec.error_category == "server_error"
    assert rec.status_code == 599
    assert rec.is_transient is True


async def _a_pets_client_error_404_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(status_error(404))
    out = await pipe._classify_pets([det(1, "cat")], "IMG")
    assert out == {}
    rec = logs.one("ERROR", "client error")
    assert rec.getMessage() == "Pet classification client error (HTTP 404)"
    assert rec.error_category == "client_error"
    assert rec.status_code == 404
    assert rec.is_transient is False


async def _a_pets_client_error_600_arm(logs):
    """Shipped boundary: 600 is NOT 5xx, so it lands in the client-error arm."""
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(status_error(600))
    out = await pipe._classify_pets([det(1, "cat")], "IMG")
    assert out == {}
    rec = logs.one("ERROR", "client error")
    assert rec.getMessage() == "Pet classification client error (HTTP 600)"
    assert rec.error_category == "client_error"
    assert rec.status_code == 600
    assert rec.is_transient is False


async def _a_pets_parse_error_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(TypeError("bad-pet-payload"))
    out = await pipe._classify_pets([det(1, "cat")], "IMG")
    assert out == {}
    assert len(logs.recs) == 1
    rec = logs.one("ERROR", "parse error")
    assert rec.getMessage() == "Pet classification parse error: bad-pet-payload"
    assert rec.error_type == "TypeError"
    assert rec.error_category == "parse_error"
    assert rec.is_transient is False


async def _a_pets_unexpected_arm(logs):
    pipe = EnrichmentPipeline()
    logs.clear()
    pipe.model_manager = loader(RuntimeError("kaboom"))
    out = await pipe._classify_pets([det(1, "cat")], "IMG")
    assert out == {}
    assert len(logs.recs) == 1
    rec = logs.one("ERROR", "Pet classification error")
    assert rec.getMessage() == "Pet classification error"
    assert rec.exc_info is not None
    assert rec.detection_type == "animal"
    assert rec.operation == "pet_classification"
    assert rec.error_category == "unexpected"
    assert rec.is_transient is True
    assert not hasattr(rec, "error_type")


# ==========================================================================
# 4. enrich_batch completion log - clip_threats / clip_anomaly clauses
#    (shipped lines 5708-5729).  The same two flags are mirrored into the
#    enrichment_pipeline.complete span event; asserting that mirror proves the
#    flags really were populated, so the log clauses cannot drift silently.
# ==========================================================================
def _fill(threats, anomaly):
    def _side(*args, **kwargs):
        result = kwargs["result"]
        result.clip_threat_matches = threats
        result.clip_anomaly_score = anomaly

    return _side


async def _run_batch(logs, threats, anomaly):
    from PIL import Image

    img = Image.new("RGB", (8, 8))
    dets = [DetectionInput(class_name="car", confidence=0.9, bbox=BOX, id=1)]
    pipe = EnrichmentPipeline()
    pipe._load_image = AsyncMock(return_value=img)
    pipe._maybe_enhance_low_light = AsyncMock(return_value=img)
    pipe._run_parallel_enrichment = AsyncMock(side_effect=_fill(threats, anomaly))
    logs.clear()
    out = await pipe.enrich_batch(dets, {None: "shared.png"}, camera_id="cam-10")
    _COLLAB.cascade_processed.assert_called_once_with()
    _COLLAB.cascade_skipped.assert_not_called()
    pipe._run_parallel_enrichment.assert_awaited_once()
    complete = [
        c for c in _COLLAB.span.call_args_list if c.args[0] == "enrichment_pipeline.complete"
    ]
    assert len(complete) == 1, [c.args for c in _COLLAB.span.call_args_list]
    rec = logs.one("INFO", "Enrichment complete:")
    return out, rec.getMessage(), complete[0]


async def _a_enrich_batch_clip_clauses_absent(logs):
    out, msg, complete = await _run_batch(logs, None, None)
    assert out.has_clip_threat_matches is False
    assert out.has_clip_anomaly_score is False
    assert complete.args[1]["clip_threat_matches.available"] is False
    assert complete.args[1]["clip_anomaly_score.available"] is False
    assert "clip_threats=no," in msg
    assert "clip_anomaly=no in" in msg
    assert "YES" not in msg and "XXyesXX" not in msg and "XXnoXX" not in msg
    assert "NO" not in msg.split("clip_anomaly=")[1]


async def _a_enrich_batch_clip_clauses_threat_only(logs):
    out, msg, complete = await _run_batch(logs, {"weapon": 0.9}, None)
    assert out.has_clip_threat_matches is True
    assert out.has_clip_anomaly_score is False
    assert complete.args[1]["clip_threat_matches.available"] is True
    assert complete.args[1]["clip_anomaly_score.available"] is False
    assert "clip_threats=yes," in msg
    assert "clip_anomaly=no in" in msg
    assert "YES" not in msg and "XXyesXX" not in msg and "XXnoXX" not in msg


async def _a_enrich_batch_clip_clauses_anomaly_only(logs):
    out, msg, complete = await _run_batch(logs, None, 0.75)
    assert out.has_clip_threat_matches is False
    assert out.has_clip_anomaly_score is True
    assert complete.args[1]["clip_threat_matches.available"] is False
    assert complete.args[1]["clip_anomaly_score.available"] is True
    assert "clip_threats=no," in msg
    assert "clip_anomaly=yes in" in msg
    assert "YES" not in msg and "XXyesXX" not in msg and "XXnoXX" not in msg


# ==========================================================================
# sync drivers
# ==========================================================================
def test_clothing_success_pinned(logs, collab) -> None:
    asyncio.run(_a_clothing_success_pinned(logs, collab))


def test_clothing_success_metric_order_two_persons(logs, collab) -> None:
    asyncio.run(_a_clothing_success_metric_order_two_persons(logs, collab))


def test_pets_success_pinned(logs, collab) -> None:
    asyncio.run(_a_pets_success_pinned(logs, collab))


def test_pets_success_metric_order_two_animals(logs, collab) -> None:
    asyncio.run(_a_pets_success_metric_order_two_animals(logs, collab))


def test_clothing_crop_none_skips_first_and_continues(logs, collab) -> None:
    asyncio.run(_a_clothing_crop_none_skips_first_and_continues(logs, collab))


def test_pets_crop_none_skips_first_and_continues(logs, collab) -> None:
    asyncio.run(_a_pets_crop_none_skips_first_and_continues(logs, collab))


def test_clothing_index_key_for_falsy_ids(logs, collab) -> None:
    asyncio.run(_a_clothing_index_key_for_falsy_ids(logs, collab))


def test_pets_index_key_for_falsy_ids(logs, collab) -> None:
    asyncio.run(_a_pets_index_key_for_falsy_ids(logs, collab))


def test_clothing_per_person_failure_continues_loop(logs, collab) -> None:
    asyncio.run(_a_clothing_per_person_failure_continues_loop(logs, collab))


def test_pets_per_animal_failure_continues_loop(logs, collab) -> None:
    asyncio.run(_a_pets_per_animal_failure_continues_loop(logs, collab))


def test_clothing_empty_persons_is_noop(logs, collab) -> None:
    asyncio.run(_a_clothing_empty_persons_is_noop(logs, collab))


def test_pets_empty_animals_is_noop(logs, collab) -> None:
    asyncio.run(_a_pets_empty_animals_is_noop(logs, collab))


def test_clothing_keyerror_arm(logs) -> None:
    asyncio.run(_a_clothing_keyerror_arm(logs))


def test_clothing_service_unavailable_arm(logs) -> None:
    asyncio.run(_a_clothing_service_unavailable_arm(logs))


def test_clothing_connect_error_arm(logs) -> None:
    asyncio.run(_a_clothing_connect_error_arm(logs))


def test_clothing_timeout_arm(logs) -> None:
    asyncio.run(_a_clothing_timeout_arm(logs))


def test_clothing_server_error_500_arm(logs) -> None:
    asyncio.run(_a_clothing_server_error_500_arm(logs))


def test_clothing_server_error_599_arm(logs) -> None:
    asyncio.run(_a_clothing_server_error_599_arm(logs))


def test_clothing_client_error_404_arm(logs) -> None:
    asyncio.run(_a_clothing_client_error_404_arm(logs))


def test_clothing_client_error_600_arm(logs) -> None:
    asyncio.run(_a_clothing_client_error_600_arm(logs))


def test_clothing_parse_error_arm(logs) -> None:
    asyncio.run(_a_clothing_parse_error_arm(logs))


def test_clothing_unexpected_arm(logs) -> None:
    asyncio.run(_a_clothing_unexpected_arm(logs))


def test_pets_keyerror_arm(logs) -> None:
    asyncio.run(_a_pets_keyerror_arm(logs))


def test_pets_service_unavailable_arm(logs) -> None:
    asyncio.run(_a_pets_service_unavailable_arm(logs))


def test_pets_connect_error_arm(logs) -> None:
    asyncio.run(_a_pets_connect_error_arm(logs))


def test_pets_timeout_arm(logs) -> None:
    asyncio.run(_a_pets_timeout_arm(logs))


def test_pets_server_error_500_arm(logs) -> None:
    asyncio.run(_a_pets_server_error_500_arm(logs))


def test_pets_server_error_599_arm(logs) -> None:
    asyncio.run(_a_pets_server_error_599_arm(logs))


def test_pets_client_error_404_arm(logs) -> None:
    asyncio.run(_a_pets_client_error_404_arm(logs))


def test_pets_client_error_600_arm(logs) -> None:
    asyncio.run(_a_pets_client_error_600_arm(logs))


def test_pets_parse_error_arm(logs) -> None:
    asyncio.run(_a_pets_parse_error_arm(logs))


def test_pets_unexpected_arm(logs) -> None:
    asyncio.run(_a_pets_unexpected_arm(logs))


def test_enrich_batch_clip_clauses_absent(logs) -> None:
    asyncio.run(_a_enrich_batch_clip_clauses_absent(logs))


def test_enrich_batch_clip_clauses_threat_only(logs) -> None:
    asyncio.run(_a_enrich_batch_clip_clauses_threat_only(logs))


def test_enrich_batch_clip_clauses_anomaly_only(logs) -> None:
    asyncio.run(_a_enrich_batch_clip_clauses_anomaly_only(logs))
