"""Batch 26 part 22 — mutation kill battery for backend/services/enrichment_pipeline.py.

Covers the eight homes owning chunk-22's 120 mutmut survivor keys:

  EnrichmentResult.to_storage_dict                         (shipped 1860-2015)
  EnrichmentPipeline._should_run_for_quality               (shipped 2331-2343)
  EnrichmentPipeline._enrich_vehicles_via_unified_service  (shipped 4103-4150)
  EnrichmentPipeline._detect_plates_fast_alpr              (shipped 6012-6076)
  EnrichmentPipeline._run_yolo_detection                   (shipped 6352-6394)
  EnrichmentPipeline._run_face_detection                   (shipped 6397-6440)
  EnrichmentPipeline._segment_person_clothing              (shipped 6728-6786)
  EnrichmentPipeline._detect_vehicle_damage                (shipped 6945-7010)

Every assertion pins SHIPPED behaviour that was PROBED against pristine HEAD
source first (rule 1) — including the quirks (``max(...)`` tie -> first
element, unknown quality level defaults to the most permissive tier, ``str(i)``
fallback key when ``detection.id`` is falsy).

Seam topology (important for the mutant sweep): ``probes/ep_plugin.py`` exec's a
variant body against a *snapshot* of the module dict taken when the variant is
bound, so a name patched inside a test body would be invisible to the variant.
The four seams that live as names in ``backend.services.enrichment_pipeline``
are therefore installed by a MODULE-scoped autouse fixture — they are already in
``M.__dict__`` when the snapshot is taken, so shipped code and variant code
observe the identical seam.  Everything else (``logger``, ``asyncio``,
``time``, the result dataclasses) is left LIVE: the real Logger is what feeds
caplog, so ``logger.warning(None)`` vs ``logger.warning(f"...")`` is pinned by
the record message itself.  Method seams (``_crop_to_bbox``,
``_get_image_for_detection``, ``_map_unified_to_enrichment_result``,
``_enrich_single_detection_unified``) are class attributes and are patched
per-test with autospec, and the two loaders the shipped bodies import *at call
time* (``fast_alpr_loader.run_fast_alpr``, ``segformer_loader.segment_clothing``)
are patched at their source module, which is live for both.

Class-free plain functions; coroutines driven with asyncio.run.  No sleeps, no
network, no DB, no real models.
"""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import ExitStack, contextmanager, nullcontext
from unittest.mock import MagicMock, patch

import pytest

import backend.services.enrichment_pipeline as M

EP = "backend.services.enrichment_pipeline."
LOGNAME = M.logger.name

IMG = M.Image.new("RGB", (16, 16), "gray")


# ---------------------------------------------------------------------------
# shipped-signature fakes for the module-level seams (installed module-scoped)
# ---------------------------------------------------------------------------


async def _fake_damage(model, image, confidence_threshold=0.25, iou_threshold=0.45):
    """Shipped ``detect_vehicle_damage(model, image, ...) -> VehicleDamageResult``."""
    return M.VehicleDamageResult(detections=[])


_SEAM_TARGETS = {
    "record_enrichment_model_call": None,
    "record_enrichment_model_error": None,
    "observe_enrichment_model_duration": None,
    "detect_vehicle_damage": _fake_damage,
}


@pytest.fixture(scope="module", autouse=True)
def seams():
    """Install the EP-module seams once, so the plugin's global snapshot sees them."""
    holder = MagicMock(name="seams")
    with ExitStack() as st:
        for name in _SEAM_TARGETS:
            setattr(holder, name, st.enter_context(patch(EP + name, autospec=True)))
        yield holder


@pytest.fixture(autouse=True)
def fresh(seams):
    """Zero the seams and restore shipped side effects before every test."""
    for name, side in _SEAM_TARGETS.items():
        mock = getattr(seams, name)
        mock.reset_mock()
        mock.side_effect = side
    return seams


class _Ctx:
    """Pipeline under test + a ``model_manager`` stub recording ``load(name)``."""

    def __init__(self, raises=None):
        self.raises = raises
        self.load_calls: list[object] = []
        self.p = M.EnrichmentPipeline.__new__(M.EnrichmentPipeline)
        self.p.model_manager = self

    def load(self, name):
        self.load_calls.append(name)
        if self.raises is not None:
            raise self.raises
        if name == "segformer-b2-clothes":
            return nullcontext(("SEGFORMER-MODEL", "SEGFORMER-PROCESSOR"))
        if name == "fast-alpr":
            return nullcontext("ALPR-CLIENT")
        return nullcontext("MODEL")


def pipe(raises=None):
    return _Ctx(raises)


def labels(mock):
    """Positional first argument of every recorded call (the metric ``model``)."""
    out = []
    for call in mock.call_args_list:
        args, kwargs = call
        out.append(args[0] if args else kwargs.get("model"))
    return out


def durations(mock):
    out = []
    for call in mock.call_args_list:
        args, kwargs = call
        model = args[0] if args else kwargs.get("model")
        dur = args[1] if len(args) > 1 else kwargs.get("duration_seconds")
        out.append((model, dur))
    return out


@contextmanager
def logs(caplog):
    """Capture the enrichment_pipeline logger at DEBUG (mutant-visible, live object)."""
    with caplog.at_level(logging.DEBUG, logger=LOGNAME):
        yield caplog


def messages(caplog):
    return [r.getMessage() for r in caplog.records]


def one_message(caplog, pattern):
    hits = [r.getMessage() for r in caplog.records if pattern in r.getMessage()]
    assert len(hits) == 1, f"expected exactly one record containing {pattern!r}, got {hits!r}"
    return hits[0]


# ---------------------------------------------------------------------------
# input builders (real dataclasses wherever the shipped code touches them)
# ---------------------------------------------------------------------------


def det(det_id, bbox=(1, 2, 9, 8), class_name="car"):
    return M.DetectionInput(
        class_name=class_name,
        confidence=0.9,
        bbox=M.BoundingBox(*bbox, confidence=0.75),
        id=det_id,
    )


class _Tensor(list):
    """``det.xyxy[0]`` / ``det.conf[0]`` stand-in: a list that also has ``tolist()``."""

    def tolist(self):
        return list(self)


class _Box:
    def __init__(self, xyxy=(0.0, 1.0, 2.0, 3.0), conf=0.5):
        self.xyxy = [_Tensor(xyxy)]
        self.conf = [conf]  # shipped does float(det.conf[0]) — a plain number


class _Det:
    """One YOLO ``Results`` element — only ``.boxes`` is read downstream."""

    def __init__(self, boxes):
        self.boxes = boxes


class _FalsyNonEmpty:
    """Falsy but ``len() == 1`` and indexable — splits ``detections and`` from ``or``."""

    def __bool__(self):
        return False

    def __len__(self):
        return 1

    def __getitem__(self, i):
        return _Det([_Box(xyxy=[1.0, 2.0, 3.0, 4.0], conf=0.5)])


class _TruthyEmpty:
    """Truthy but ``len() == 0`` and indexable — splits ``> 0`` from ``>= 0``."""

    def __bool__(self):
        return True

    def __len__(self):
        return 0

    def __getitem__(self, i):
        return _Det([_Box(xyxy=[1.0, 2.0, 3.0, 4.0], conf=0.5)])


def pl(det_id, conf, text=""):
    return M.LicensePlateResult(
        bbox=M.BoundingBox(1.0, 2.0, 3.0, 4.0, confidence=conf),
        text=text,
        confidence=conf,
        ocr_confidence=conf,
        source_detection_id=det_id,
    )


def face(det_id):
    return M.FaceResult(
        bbox=M.BoundingBox(5.0, 6.0, 7.0, 8.0, confidence=0.5),
        confidence=0.5,
        source_detection_id=det_id,
    )


_UNSET = object()


def _one_det():
    return [_Det([_Box(xyxy=[0.0, 1.0, 2.0, 3.0], conf=0.5)])]


_ONE_DET = _one_det()  # fresh list per module load; predict hands it out read-only


class _Model:
    """Loaded-model stand-in: shipped code calls ``model.predict(image, verbose=False)``."""

    def __init__(self, calls=None, result=_UNSET, raises=None):
        self.calls = calls if calls is not None else []
        self.result = result
        self.raises = raises

    def predict(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.raises is not None:
            raise self.raises
        return _ONE_DET if self.result is _UNSET else self.result


def _always(result=_UNSET):
    """Model whose predict ignores its args and returns *result* (default: one det)."""
    return _Model(result=result)


def _raising(exc):
    return _Model(raises=exc)


# ---------------------------------------------------------------------------
# method seams + call-time loader imports
# ---------------------------------------------------------------------------


async def _seg_ok(model, processor, person_crop, min_coverage=0.01):
    return M.ClothingSegmentationResult(
        clothing_items={"hat"}, has_face_covered=True, has_bag=False
    )


class _Plate:
    """One ``FastALPRResult``: bbox/text/confidence/detection_confidence are read."""

    def __init__(self, bbox, text, confidence, detection_confidence):
        self.bbox = bbox
        self.text = text
        self.confidence = confidence
        self.detection_confidence = detection_confidence


async def _alpr_ok(alpr, image, min_confidence=0.3):
    return [_Plate(bbox=[10, 11, 12, 13], text="ABC123", confidence=0.9, detection_confidence=0.8)]


def crop_recorder(seen, results=None):
    async def crop(self, image, bbox):
        seen.append((image, bbox))
        if results is None:
            assert isinstance(image, M.Image.Image), f"image arg must be a PIL image: {image!r}"
            assert isinstance(bbox, M.BoundingBox), f"bbox arg must be a BoundingBox: {bbox!r}"
            return IMG
        return results[len(seen) - 1]

    return crop


def image_stub(seen, value=IMG):
    """``_get_image_for_detection(self, detection, images)`` recorder."""

    def get_image(self, detection, images):
        seen.append((detection, images))
        return value

    return get_image


@contextmanager
def alpr_loader(fake=_alpr_ok):
    with patch(
        "backend.services.fast_alpr_loader.run_fast_alpr", autospec=True, side_effect=fake
    ) as m:
        yield m


@contextmanager
def seg_loader(fake=_seg_ok):
    with patch(
        "backend.services.segformer_loader.segment_clothing", autospec=True, side_effect=fake
    ) as m:
        yield m


@contextmanager
def crop(seen, results=None):
    with patch.object(
        M.EnrichmentPipeline,
        "_crop_to_bbox",
        autospec=True,
        side_effect=crop_recorder(seen, results),
    ) as m:
        yield m


@contextmanager
def images(seen, value=IMG):
    with patch.object(
        M.EnrichmentPipeline,
        "_get_image_for_detection",
        autospec=True,
        side_effect=image_stub(seen, value),
    ) as m:
        yield m


# ===========================================================================
# EnrichmentPipeline._run_yolo_detection — shipped 6352-6394
# ===========================================================================


def test_yolo_predict_called_with_image_positionally_and_verbose_false():
    calls: list = []
    p = pipe()
    out = asyncio.run(p.p._run_yolo_detection(_Model(calls), IMG, 42))
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert args == (IMG,), f"shipped passes the image positionally, exactly once: {args!r}"
    assert list(kwargs) == ["verbose"], f"shipped passes only verbose=: {kwargs!r}"
    assert kwargs["verbose"] is False, f"shipped passes verbose=False: {kwargs!r}"
    assert len(out) == 1


def test_yolo_only_real_detections_are_mapped(caplog):
    """``if detections and len(detections) > 0`` — falsy or zero-length yields []."""
    p = pipe()
    with logs(caplog):
        assert asyncio.run(p.p._run_yolo_detection(_always([]), IMG, 1)) == []
        assert asyncio.run(p.p._run_yolo_detection(_always(None), IMG, 1)) == []
        assert asyncio.run(p.p._run_yolo_detection(_always(_FalsyNonEmpty()), IMG, 1)) == []
        assert asyncio.run(p.p._run_yolo_detection(_always(_TruthyEmpty()), IMG, 1)) == []
    assert [m for m in messages(caplog) if "YOLO detection failed" in m] == []


def test_yolo_maps_bbox_positionally_and_confidence_in_two_places():
    box = _Box(xyxy=[1.25, 2.5, 3.75, 5.0], conf=0.875)
    p = pipe()
    out = asyncio.run(p.p._run_yolo_detection(_always([_Det([box])]), IMG, 77))
    assert len(out) == 1
    r = out[0]
    assert isinstance(r, M.LicensePlateResult)
    assert r.bbox.to_dict() == {
        "x1": 1.25,
        "y1": 2.5,
        "x2": 3.75,
        "y2": 5.0,
        "confidence": 0.875,
    }
    assert r.confidence == 0.875
    assert r.source_detection_id == 77
    assert r.text == "" and r.ocr_confidence == 0.0


def test_yolo_failure_warns_with_the_error_and_returns_empty(caplog):
    p = pipe()
    with logs(caplog):
        out = asyncio.run(p.p._run_yolo_detection(_raising(RuntimeError("kaput")), IMG, 3))
    assert out == []
    assert one_message(caplog, "YOLO detection failed") == "YOLO detection failed: kaput"


# ===========================================================================
# EnrichmentPipeline._run_face_detection — shipped 6397-6440
# ===========================================================================


def test_face_predict_called_with_image_positionally_and_verbose_false():
    calls: list = []
    p = pipe()
    out = asyncio.run(p.p._run_face_detection(_Model(calls), IMG, 8))
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert args == (IMG,), f"shipped passes the image positionally: {args!r}"
    assert list(kwargs) == ["verbose"] and kwargs["verbose"] is False
    assert len(out) == 1


def test_face_only_real_detections_are_mapped(caplog):
    p = pipe()
    with logs(caplog):
        assert asyncio.run(p.p._run_face_detection(_always([]), IMG, 1)) == []
        assert asyncio.run(p.p._run_face_detection(_always(None), IMG, 1)) == []
        assert asyncio.run(p.p._run_face_detection(_always(_FalsyNonEmpty()), IMG, 1)) == []
        assert asyncio.run(p.p._run_face_detection(_always(_TruthyEmpty()), IMG, 1)) == []
    assert [m for m in messages(caplog) if "Face detection failed" in m] == []


def test_face_maps_bbox_positionally_and_confidence_in_two_places():
    box = _Box(xyxy=[9.5, 8.5, 7.5, 6.5], conf=0.25)
    p = pipe()
    out = asyncio.run(p.p._run_face_detection(_always([_Det([box])]), IMG, 21))
    assert len(out) == 1
    r = out[0]
    assert isinstance(r, M.FaceResult)
    assert r.bbox.to_dict() == {
        "x1": 9.5,
        "y1": 8.5,
        "x2": 7.5,
        "y2": 6.5,
        "confidence": 0.25,
    }
    assert r.confidence == 0.25
    assert r.source_detection_id == 21


def test_face_failure_warns_with_the_error_and_returns_empty(caplog):
    p = pipe()
    with logs(caplog):
        out = asyncio.run(p.p._run_face_detection(_raising(RuntimeError("facesdead")), IMG, 3))
    assert out == []
    assert one_message(caplog, "Face detection failed") == "Face detection failed: facesdead"


# ===========================================================================
# EnrichmentPipeline._should_run_for_quality — shipped 2331-2343
# ===========================================================================


def _sq(quality_level):
    p = M.EnrichmentPipeline.__new__(M.EnrichmentPipeline)
    p._quality_level = quality_level
    return p


def test_quality_gate_full_matrix_of_levels_and_tiers():
    """Every (current x tier) pair over the three named levels plus unknowns.

    Pins ``level_order`` key-for-key and both ``.get(..., 2)`` defaults: an
    unknown *level* behaves like "full" (default 2) while an unknown *tier*
    requires "full" (default 2).
    """
    expected = {
        "full": {"minimal": True, "standard": True, "full": True, "bogus": True},
        "standard": {"minimal": True, "standard": True, "full": False, "bogus": False},
        "minimal": {"minimal": True, "standard": False, "full": False, "bogus": False},
        "bogus": {"minimal": True, "standard": True, "full": True, "bogus": True},
    }
    for level, row in expected.items():
        p = _sq(level)
        for tier, want in row.items():
            assert p._should_run_for_quality(tier) is want, f"level={level!r} tier={tier!r}"


def test_quality_gate_is_exact_case_on_tier_and_level():
    """The mapping is lowercase-only: an unknown spelling falls to the default 2."""
    assert _sq("full")._should_run_for_quality("FULL") is True  # unknown tier -> 2
    assert _sq("standard")._should_run_for_quality("Standard") is False
    assert _sq("minimal")._should_run_for_quality("MINIMAL") is False
    assert _sq("FULL")._should_run_for_quality("full") is True  # unknown level -> 2
    assert _sq("minimal")._should_run_for_quality("minimal") is True


# ===========================================================================
# EnrichmentResult.to_storage_dict — shipped 1860-2015
# ===========================================================================


def test_storage_plate_is_highest_ocr_confidence_with_first_winning_ties():
    """``max(plates, key=lambda p: p.ocr_confidence or 0.0)`` (shipped line 1938)."""
    got = M.EnrichmentResult(license_plates=[pl(7, 0.1, "LOW"), pl(7, 0.9, "HIGH")])
    assert got.to_storage_dict(7)["license_plate"]["text"] == "HIGH"
    got = M.EnrichmentResult(license_plates=[pl(7, 0.9, "HIGH"), pl(7, 0.1, "LOW")])
    assert got.to_storage_dict(7)["license_plate"]["text"] == "HIGH"
    # equal keys: max() keeps the first candidate encountered
    got = M.EnrichmentResult(license_plates=[pl(7, 0.4, "AAA"), pl(7, 0.4, "BBB")])
    assert got.to_storage_dict(7)["license_plate"]["text"] == "AAA"


def test_storage_plate_none_confidence_sorts_as_zero():
    """``p.ocr_confidence or 0.0`` — a None-confidence plate loses to 0.2, never wins."""
    none_plate = M.LicensePlateResult(
        bbox=M.BoundingBox(0.0, 0.0, 1.0, 1.0),
        text="NONE",
        confidence=0.5,
        ocr_confidence=None,
        source_detection_id=7,
    )
    d = M.EnrichmentResult(license_plates=[none_plate, pl(7, 0.2, "REAL")]).to_storage_dict(7)
    assert d["license_plate"]["text"] == "REAL"
    d = M.EnrichmentResult(license_plates=[none_plate]).to_storage_dict(7)
    assert d["license_plate"]["text"] == "NONE"
    assert d["license_plate"]["ocr_confidence"] is None


def test_storage_uses_only_plates_and_faces_for_this_detection():
    mine, theirs = pl(7, 0.5, "MINE"), pl(8, 0.99, "THEIRS")
    d = M.EnrichmentResult(license_plates=[mine, theirs], faces=[face(8)]).to_storage_dict(7)
    assert d["license_plate"]["text"] == "MINE"
    assert "face_count" not in d and "faces" not in d and "face_detected" not in d
    assert M.EnrichmentResult(license_plates=[theirs]).to_storage_dict(7) is None


def test_storage_face_block_sets_detected_count_and_serialised_list():
    """Shipped sets ``face_detected``/``face_count``/``faces`` (lines 1943-1946)."""
    r = M.EnrichmentResult(faces=[face(7), face(7), face(8)])
    d = r.to_storage_dict(7)
    assert d["face_detected"] is True
    assert d["face_count"] == 2
    assert d["faces"] == [face(7).to_dict(), face(7).to_dict()]
    assert [f["source_detection_id"] for f in d["faces"]] == [7, 7]
    d1 = M.EnrichmentResult(faces=[face(7)]).to_storage_dict(7)
    assert d1["face_count"] == 1 and isinstance(d1["faces"], list) and len(d1["faces"]) == 1
    assert M.EnrichmentResult(faces=[face(8)]).to_storage_dict(7) is None


def test_storage_clip_embedding_keyed_by_detection_context():
    """CLIP + vehicle re-id matches -> ``vehicle_visual``; unmatched CLIP also -> ``vehicle_visual``."""
    r = M.EnrichmentResult(
        clip_embeddings={"7": [0.25, 0.5]}, vehicle_reid_matches={"7": [MagicMock()]}
    )
    assert r.to_storage_dict(7)["embeddings"] == {"vehicle_visual": [0.25, 0.5]}
    r = M.EnrichmentResult(clip_embeddings={"7": [0.125]})
    assert r.to_storage_dict(7)["embeddings"] == {"vehicle_visual": [0.125]}
    assert M.EnrichmentResult(clip_embeddings={"9": [0.5]}).to_storage_dict(7) is None


def test_storage_dict_shape_with_plate_and_face_together():
    d = M.EnrichmentResult(license_plates=[pl(7, 0.3, "XYZ")], faces=[face(7)]).to_storage_dict(7)
    assert set(d) == {"license_plate", "face_detected", "face_count", "faces"}
    assert re.fullmatch(r"[A-Z]{3}", d["license_plate"]["text"])
    assert d["license_plate"]["bbox"] == M.BoundingBox(1.0, 2.0, 3.0, 4.0, confidence=0.3).to_dict()


# ===========================================================================
# EnrichmentPipeline._detect_plates_fast_alpr — shipped 6012-6076
# ===========================================================================


def test_fast_alpr_loads_the_named_model_once():
    seen_img: list = []
    seen_crop: list = []
    p = pipe()
    with images(seen_img), crop(seen_crop), alpr_loader():
        out = asyncio.run(p.p._detect_plates_fast_alpr([det(11), det(12)], {11: IMG, 12: IMG}))
    assert p.load_calls == ["fast-alpr"], f"shipped loads exactly 'fast-alpr': {p.load_calls!r}"
    assert len(out) == 2


def test_fast_alpr_image_lookup_receives_detection_then_images():
    seen_img: list = []
    seen_crop: list = []
    d1, d2 = det(11), det(12)
    mapping = {11: IMG, 12: IMG}
    p = pipe()
    with images(seen_img), crop(seen_crop), alpr_loader():
        asyncio.run(p.p._detect_plates_fast_alpr([d1, d2], mapping))
    assert seen_img == [(d1, mapping), (d2, mapping)], f"arg order/arity: {seen_img!r}"


def test_fast_alpr_crop_receives_image_then_detection_bbox():
    seen_img: list = []
    seen_crop: list = []
    d = det(5, bbox=(1.0, 2.0, 9.0, 8.0))
    p = pipe()
    with images(seen_img), crop(seen_crop), alpr_loader():
        asyncio.run(p.p._detect_plates_fast_alpr([d], {5: IMG}))
    assert seen_crop == [(IMG, d.bbox)], f"crop args: {seen_crop!r}"


def test_fast_alpr_loader_receives_client_then_crop_and_maps_result():
    seen_img: list = []
    seen_crop: list = []
    p = pipe()
    with images(seen_img), crop(seen_crop), alpr_loader() as run:
        out = asyncio.run(p.p._detect_plates_fast_alpr([det(11)], {11: IMG}))
    assert len(run.call_args_list) == 1
    args, kwargs = run.call_args_list[0]
    assert len(args) == 2 and not kwargs, f"shipped passes 2 positionals: {args!r} {kwargs!r}"
    assert args[0] == "ALPR-CLIENT", f"first arg is the loaded client: {args[0]!r}"
    assert args[1] is IMG, f"second arg is the cropped image: {args[1]!r}"
    assert len(out) == 1
    r = out[0]
    assert r.bbox.to_tuple() == (10, 11, 12, 13)
    assert r.bbox.confidence == 0.0
    assert r.text == "ABC123"
    assert r.confidence == 0.8 and r.ocr_confidence == 0.9
    assert r.source_detection_id == 11


def test_fast_alpr_skips_vehicle_without_image():
    seen_crop: list = []
    p = pipe()
    with images([], value=None), crop(seen_crop), alpr_loader() as run:
        out = asyncio.run(p.p._detect_plates_fast_alpr([det(1)], {1: IMG}))
    assert out == [] and seen_crop == [] and run.call_args_list == []


def test_fast_alpr_skips_vehicle_without_crop():
    seen_img: list = []
    p = pipe()
    with images(seen_img), crop([], results=[None]), alpr_loader() as run:
        out = asyncio.run(p.p._detect_plates_fast_alpr([det(1)], {1: IMG}))
    assert out == [] and run.call_args_list == []


def test_fast_alpr_keyerror_warns_exact_message_and_falls_back(caplog):
    p = pipe(raises=KeyError("fast-alpr"))
    with (
        logs(caplog),
        patch.object(
            M.EnrichmentPipeline, "_detect_license_plates", autospec=True, return_value=["LEGACY"]
        ) as legacy,
    ):
        out = asyncio.run(p.p._detect_plates_fast_alpr([det(1)], {1: IMG}))
    assert out == ["LEGACY"]
    assert legacy.call_args_list
    assert one_message(caplog, "falling back") == (
        "fast-alpr model not available, falling back to YOLO11 + PaddleOCR"
    )


# ===========================================================================
# EnrichmentPipeline._segment_person_clothing — shipped 6728-6786
# ===========================================================================


def test_segment_loads_the_named_model_and_labels_the_metric(seams):
    p = pipe()
    with crop([]), seg_loader():
        out = asyncio.run(p.p._segment_person_clothing([det(1, class_name="person")], IMG))
    assert p.load_calls == ["segformer-b2-clothes"], f"load(): {p.load_calls!r}"
    assert list(out) == ["1"]
    assert labels(seams.record_enrichment_model_call) == ["segformer-b2-clothes"]


def test_segment_loader_receives_model_processor_crop_in_order():
    seen: list = []

    async def rec(model, processor, person_crop, min_coverage=0.01):
        seen.append((model, processor, person_crop))
        return M.ClothingSegmentationResult(clothing_items={"hat"})

    p = pipe()
    with crop([]), seg_loader(rec):
        asyncio.run(p.p._segment_person_clothing([det(2, class_name="person")], IMG))
    assert len(seen) == 1
    model, processor, crop_img = seen[0]
    assert model == "SEGFORMER-MODEL" and processor == "SEGFORMER-PROCESSOR"
    assert crop_img is IMG


def test_segment_key_is_string_id_and_stores_the_result():
    p = pipe()
    with crop([]), seg_loader():
        out = asyncio.run(
            p.p._segment_person_clothing(
                [det(3, class_name="person"), det(4, class_name="person")], IMG
            )
        )
    assert list(out) == ["3", "4"]
    assert out["3"].clothing_items == {"hat"} and out["3"].has_face_covered is True


def test_segment_falls_back_to_index_key_when_id_is_falsy():
    """``str(person.id) if person.id else str(i)`` — id 0/None keys by enumerate index."""
    p = pipe()
    with crop([]), seg_loader():
        out = asyncio.run(
            p.p._segment_person_clothing(
                [det(0, class_name="person"), det(None, class_name="person")], IMG
            )
        )
    assert list(out) == ["0", "1"], f"index fallback keys: {list(out)!r}"


def test_segment_debug_line_names_the_detection_and_flags(caplog):
    seen: list = []

    async def rec(model, processor, person_crop, min_coverage=0.01):
        seen.append(person_crop)
        return M.ClothingSegmentationResult(
            clothing_items={"hat"}, has_face_covered=True, has_bag=False
        )

    p = pipe()
    with logs(caplog), crop([]), seg_loader(rec):
        asyncio.run(p.p._segment_person_clothing([det(3, class_name="person")], IMG))
    assert one_message(caplog, "clothing items") == (
        "Person 3 clothing items: {'hat'}, face_covered=True, has_bag=False"
    )


def test_segment_empty_input_touches_nothing(seams):
    p = pipe()
    with crop([]), seg_loader() as seg:
        out = asyncio.run(p.p._segment_person_clothing([], IMG))
    assert out == {} and p.load_calls == [] and seg.call_args_list == []
    assert labels(seams.record_enrichment_model_call) == []


def test_segment_skips_person_with_no_crop_and_continues(seams):
    p = pipe()
    with crop([], results=[None, IMG]), seg_loader() as seg:
        out = asyncio.run(
            p.p._segment_person_clothing(
                [det(1, class_name="person"), det(2, class_name="person")], IMG
            )
        )
    assert list(out) == ["2"] and len(seg.call_args_list) == 1
    assert labels(seams.record_enrichment_model_call) == ["segformer-b2-clothes"]


def test_segment_keyerror_warns_exact_message(seams, caplog):
    p = pipe(raises=KeyError("segformer-b2-clothes"))
    with logs(caplog), crop([]), seg_loader():
        out = asyncio.run(p.p._segment_person_clothing([det(1, class_name="person")], IMG))
    assert out == {}
    assert labels(seams.record_enrichment_model_call) == []
    assert one_message(caplog, "not available") == (
        "segformer-b2-clothes model not available in MODEL_ZOO"
    )


# ===========================================================================
# EnrichmentPipeline._detect_vehicle_damage — shipped 6945-7010
# ===========================================================================


def test_damage_loads_named_model_and_labels_metric(seams):
    seen: list = []
    expected = M.VehicleDamageResult(detections=[])
    seams.detect_vehicle_damage.side_effect = lambda *a, **k: expected
    p = pipe()
    with crop(seen):
        out = asyncio.run(p.p._detect_vehicle_damage([det(21)], IMG))
    assert p.load_calls == ["vehicle-damage-detection"], f"load(): {p.load_calls!r}"
    assert out == {"21": expected}
    assert labels(seams.record_enrichment_model_call) == ["vehicle-damage-detection"]


def test_damage_loader_receives_model_then_crop(seams):
    seen: list = []
    p = pipe()
    with crop(seen):
        asyncio.run(p.p._detect_vehicle_damage([det(21)], IMG))
    assert seen == [(IMG, det(21).bbox)]
    args, kwargs = seams.detect_vehicle_damage.call_args_list[0]
    assert len(args) == 2 and not kwargs, f"shipped passes 2 positionals: {args!r} {kwargs!r}"
    assert args[0] == "MODEL" and args[1] is IMG


def test_damage_falls_back_to_index_key_when_id_is_falsy():
    p = pipe()
    with crop([]):
        out = asyncio.run(p.p._detect_vehicle_damage([det(0), det(None)], IMG))
    assert list(out) == ["0", "1"], f"index fallback keys: {list(out)!r}"


def test_damage_empty_input_touches_nothing(seams):
    p = pipe()
    with crop([]):
        out = asyncio.run(p.p._detect_vehicle_damage([], IMG))
    assert out == {} and p.load_calls == []
    assert seams.detect_vehicle_damage.call_args_list == []
    assert labels(seams.record_enrichment_model_call) == []


def test_damage_skips_vehicle_with_no_crop(seams):
    p = pipe()
    with crop([], results=[None]):
        out = asyncio.run(p.p._detect_vehicle_damage([det(1)], IMG))
    assert out == {} and seams.detect_vehicle_damage.call_args_list == []


def test_damage_keyerror_warns_exact_message(seams, caplog):
    p = pipe(raises=KeyError("vehicle-damage-detection"))
    with logs(caplog), crop([]):
        out = asyncio.run(p.p._detect_vehicle_damage([det(1)], IMG))
    assert out == {}
    assert one_message(caplog, "not available") == (
        "vehicle-damage-detection model not available in MODEL_ZOO"
    )


def test_damage_warns_per_vehicle_on_loader_failure(seams, caplog):
    async def boom(model, image, *a, **k):
        raise ValueError("nop")

    seams.detect_vehicle_damage.side_effect = boom
    p = pipe()
    with logs(caplog), crop([]):
        out = asyncio.run(p.p._detect_vehicle_damage([det(0), det(6)], IMG))
    assert out == {}
    got = sorted(m for m in messages(caplog) if "Vehicle damage detection failed" in m)
    assert got == [
        "Vehicle damage detection failed for vehicle 0: nop",
        "Vehicle damage detection failed for vehicle 6: nop",
    ]
    assert labels(seams.record_enrichment_model_call) == []


# ===========================================================================
# EnrichmentPipeline._enrich_vehicles_via_unified_service — shipped 4103-4150
# ===========================================================================


def _single_ok(self, detection, image, kind, camera_id=None):
    return (str(detection.id), {"kind": kind})


@contextmanager
def unified(single=_single_ok, mapres=None):
    """Patch the per-detection task and the mapper with shipped-signature fakes."""
    mapped: list = []

    def _map(self, result, det_id, unified_result, detection_type):
        mapped.append((det_id, unified_result, detection_type))

    with (
        patch.object(
            M.EnrichmentPipeline,
            "_enrich_single_detection_unified",
            autospec=True,
            side_effect=single,
        ),
        patch.object(
            M.EnrichmentPipeline,
            "_map_unified_to_enrichment_result",
            autospec=True,
            side_effect=mapres or _map,
        ),
    ):
        yield mapped


def test_unified_vehicles_records_call_then_duration_under_same_label(seams):
    p = pipe()
    r = M.EnrichmentResult()
    with unified():
        asyncio.run(p.p._enrich_vehicles_via_unified_service([det(31)], IMG, r))
    assert labels(seams.record_enrichment_model_call) == ["unified-enrich-vehicle"]
    obs = durations(seams.observe_enrichment_model_duration)
    assert [m for m, _ in obs] == ["unified-enrich-vehicle"]
    ((_model, dur),) = obs
    assert isinstance(dur, float) and 0.0 <= dur < 10.0, f"elapsed must be a real duration: {dur!r}"
    assert labels(seams.record_enrichment_model_error) == []


def test_unified_vehicles_builds_one_task_per_vehicle_with_vehicle_kind():
    kinds: list = []

    async def single(self, detection, image, kind, camera_id=None):
        kinds.append((detection.id, image, kind))
        return (str(detection.id), {})

    dets = [det(1), det(2)]
    p = pipe()
    with unified(single):
        asyncio.run(p.p._enrich_vehicles_via_unified_service(dets, IMG, M.EnrichmentResult()))
    assert kinds == [(1, IMG, "vehicle"), (2, IMG, "vehicle")]


def test_unified_vehicles_maps_each_result_with_the_task_key(seams):
    dets = [det(11), det(12)]

    async def shuffled(self, detection, image, kind, camera_id=None):
        return (f"K{detection.id}", {})

    p = pipe()
    with unified(shuffled) as mapped:
        asyncio.run(p.p._enrich_vehicles_via_unified_service(dets, IMG, M.EnrichmentResult()))
    assert mapped == [("K11", {}, "vehicle"), ("K12", {}, "vehicle")]


def test_unified_vehicles_isolates_a_failing_task_from_its_siblings(seams, caplog):
    """``return_exceptions=True``: one failure must not abort or cancel the others."""
    done: list = []

    async def single(self, detection, image, kind, camera_id=None):
        if detection.id == 1:
            raise RuntimeError("only-one-fails")
        await asyncio.sleep(0)
        done.append(detection.id)
        return (str(detection.id), {})

    p = pipe()
    with logs(caplog), unified(single) as mapped:
        asyncio.run(
            p.p._enrich_vehicles_via_unified_service(
                [det(1), det(2), det(3)], IMG, M.EnrichmentResult()
            )
        )
    assert done == [2, 3]
    assert [d for d, _u, _k in mapped] == ["2", "3"]
    assert labels(seams.record_enrichment_model_error) == ["unified-enrich-vehicle"]
    msg = one_message(caplog, "Unified enrichment failed for vehicle")
    assert "1: " in msg and "only-one-fails" in msg


def test_unified_vehicles_empty_input_records_nothing(seams):
    p = pipe()
    with unified():
        asyncio.run(p.p._enrich_vehicles_via_unified_service([], IMG, M.EnrichmentResult()))
    assert labels(seams.record_enrichment_model_call) == []
    assert durations(seams.observe_enrichment_model_duration) == []


def test_unified_vehicles_debug_line_reports_count_and_elapsed(caplog):
    p = pipe()
    with logs(caplog), unified():
        asyncio.run(
            p.p._enrich_vehicles_via_unified_service([det(1), det(2)], IMG, M.EnrichmentResult())
        )
    msg = one_message(caplog, "Unified vehicle enrichment complete")
    m = re.fullmatch(r"Unified vehicle enrichment complete: 2 vehicles in (\d+\.\d\d)s", msg)
    assert m, f"shipped debug line shape: {msg!r}"
    assert 0.0 <= float(m.group(1)) < 60.0, msg


# ===========================================================================
# cross-path pins (same chunk keys, shared call shapes)
# ===========================================================================


def test_plate_and_face_detectors_build_the_same_bbox_layout():
    box = _Box(xyxy=[0.5, 1.5, 2.5, 3.5], conf=0.75)
    p = pipe()
    m = _always([_Det([box])])
    plates = asyncio.run(p.p._run_yolo_detection(m, IMG, 1))
    faces = asyncio.run(p.p._run_face_detection(m, IMG, 1))
    assert plates[0].bbox.to_dict() == faces[0].bbox.to_dict()
    assert plates[0].bbox.to_dict() == {
        "x1": 0.5,
        "y1": 1.5,
        "x2": 2.5,
        "y2": 3.5,
        "confidence": 0.75,
    }


def test_fast_alpr_and_legacy_plate_path_crop_with_the_same_arguments():
    fast: list = []
    legacy: list = []
    d = det(4, bbox=(2.0, 3.0, 4.0, 5.0))
    p = pipe()
    with images([]), crop(fast), alpr_loader():
        asyncio.run(p.p._detect_plates_fast_alpr([d], {4: IMG}))
    with (
        crop(legacy),
        patch.object(M.EnrichmentPipeline, "_run_yolo_detection", autospec=True, return_value=[]),
    ):
        asyncio.run(p.p._detect_license_plates([d], {4: IMG}))
    assert fast == [(IMG, d.bbox)]
    assert legacy == [(IMG, d.bbox)]


def test_damage_and_segmentation_label_the_metric_with_their_own_model_names(seams):
    p = pipe()
    with crop([]):
        asyncio.run(p.p._detect_vehicle_damage([det(1)], IMG))
    assert labels(seams.record_enrichment_model_call) == ["vehicle-damage-detection"]
    p2 = pipe()
    with crop([]), seg_loader():
        asyncio.run(p2.p._segment_person_clothing([det(1, class_name="person")], IMG))
    assert labels(seams.record_enrichment_model_call) == [
        "vehicle-damage-detection",
        "segformer-b2-clothes",
    ]
