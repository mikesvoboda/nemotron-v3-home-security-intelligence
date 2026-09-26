"""Chunk-06 kill battery — ``EnrichmentPipeline._run_parallel_enrichment`` (120 keys).

Every assertion pins behaviour MEASURED against the pristine shipped module
(``git show HEAD:backend/services/enrichment_pipeline.py``; the method body is
shipped L2345-L2870).  Shipped line numbers are quoted in verdicts_06.json.

One measurement rig (``Ctx``), several scenarios.  Rig facts:

* every enrichment worker is a recording stub whose ``co_code.co_name`` is the
  worker name, so each ``bounded_gather`` batch is identified by *content*
  (robust against mutants that move tasks between batches) instead of call
  order;
* ``bounded_gather`` is patched at the IMPORT site with a ``wraps=`` mock, so
  the real bounded_gather still runs (real ordering, real per-task timeouts,
  real ``return_exceptions`` behaviour) while its kwargs are recorded;
* ``add_span_event``, ``observe_enrichment_pipeline_stage`` and
  ``record_cascade_model_deferred`` are patched at the IMPORT site;
* ``time.monotonic`` is a deterministic counter advancing ``STEP`` per read, so
  ``phase1_duration`` is exactly 1.5 — which makes ``* 1000`` (1500),
  ``* 1001`` (1501), ``/ 1000`` (0) and ``monotonic() + start`` (~1e2+) mutually
  distinguishable;
* the module logger is captured, so the ``Phase 1 + Florence completed ...``
  line and the ``Cascade: Florence-2 deferred for N/M ...`` line are pinned
  verbatim.

``_pipeline_timeout`` is the shipped test-tier setting (30.0 s), so the shipped
per-group timeouts are 30*0.7 = 21.0 (GPU) and 30*0.5 = 15.0 (CPU).

No sleeps, no network, no DB, no model loading.  ``asyncio.run`` per scenario
(never asyncio fixtures) so the file is independent of the asyncio plugin.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any
from unittest.mock import MagicMock, patch

from PIL import Image

import backend.services.enrichment_pipeline as M

MODULE = "backend.services.enrichment_pipeline"
START = "enrichment_pipeline.super_phase_start"
COMPLETE = "enrichment_pipeline.super_phase_complete"
STEP = 1.5
BOX_T = (1.0, 2.0, 3.0, 4.0)
CAM = "CAM-A"
DET_KEYS = {"class_name", "confidence", "bbox", "detection_id"}
GPU_KW = {"limit": 2, "task_timeout": 21.0, "return_exceptions": True}
CPU_KW = {"limit": 5, "task_timeout": 15.0, "return_exceptions": True}
P2_KW = {"limit": 5, "return_exceptions": True}
_UNSET = object()


class Boom(RuntimeError):
    """Named error so ``error_type=type(exc).__name__`` is pin-able."""


class _Plate:
    """Minimal stand-in for ``LicensePlateResult`` (only ``.text`` is read)."""

    def __init__(self, text: str = "") -> None:
        self.text = text


def _bbox() -> M.BoundingBox:
    return M.BoundingBox(x1=1.0, y1=2.0, x2=3.0, y2=4.0)


def _det(
    cls: str = "package",
    conf: float = 0.8,
    did: int | None = 7,
    bbox: Any = _UNSET,
) -> M.DetectionInput:
    return M.DetectionInput(
        class_name=cls, confidence=conf, bbox=(_bbox() if bbox is _UNSET else bbox), id=did
    )


def _stub(
    name: str,
    ret: Any = None,
    exc: BaseException | None = None,
    holder: list[Any] | None = None,
) -> Any:
    """Recording async stub whose ``co_name`` is ``name``.

    Deliberately tolerant of any positional arity: a mutant that drops or
    replaces an argument must show up in the recorded tuple, not as an
    unrelated TypeError, so the pin reads as an argument mismatch.
    """

    async def impl(*args: Any) -> Any:
        if holder is not None:
            holder.append(args)
        if exc is not None:
            raise exc
        return ret

    impl.__code__ = impl.__code__.replace(co_name=name, co_qualname=name)
    return impl


class _Extractor:
    """Fake vision extractor with the shipped 2-positional-arg signature."""

    def __init__(self, ret: Any = "FLOSCAR", exc: BaseException | None = None) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.ret = ret
        self.exc = exc

    async def extract_batch_attributes(self, image: Any, detections: Any) -> Any:
        self.calls.append((image, detections))
        if self.exc is not None:
            raise self.exc
        return self.ret


class _Detector:
    """Fake scene-change detector with the shipped 2-positional-arg signature."""

    def __init__(self, ret: Any = "SCENEMARK", exc: BaseException | None = None) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.ret = ret
        self.exc = exc

    def detect_changes(self, camera_id: Any, current_frame: Any) -> Any:
        self.calls.append((camera_id, current_frame))
        if self.exc is not None:
            raise self.exc
        return self.ret


_OFF = dict(
    license_plate_enabled=False,
    face_detection_enabled=False,
    ocr_enabled=False,
    vision_extraction_enabled=False,
    reid_enabled=False,
    scene_change_enabled=False,
    violence_detection_enabled=False,
    weather_classification_enabled=False,
    clothing_classification_enabled=False,
    clothing_segmentation_enabled=False,
    vehicle_damage_detection_enabled=False,
    vehicle_classification_enabled=False,
    image_quality_enabled=False,
    pet_classification_enabled=False,
    depth_estimation_enabled=False,
    pose_estimation_enabled=False,
    action_recognition_enabled=False,
    scene_ocr_enabled=False,
    household_matching_enabled=False,
    age_classification_enabled=False,
    gender_classification_enabled=False,
    smoke_fire_detection_enabled=False,
    yolo_world_enabled=False,
    osnet_reid_enabled=False,
    low_light_enhancement_enabled=False,
)

_WORKERS: dict[str, tuple[Any, BaseException | None]] = {
    "_safe_detect_faces": ([], None),
    "_safe_detect_license_plates": ([], None),
    "_safe_detect_plates_fast_alpr": ([], None),
    "_safe_detect_violence": ("VIOL", None),
    "_safe_estimate_poses": ({"POSE": "KEYS"}, None),
    "_safe_classify_person_clothing": ("CLOTH", None),
    "_safe_classify_vehicle_types": ("VEH", None),
    "_safe_classify_pets": ("PET", None),
    "_safe_classify_demographics": ((None, None), None),
    "_safe_extract_osnet_embeddings": ({}, None),
    "_safe_detect_smoke_fire": ("SMOKEMARK", None),
    "_safe_detect_yolo_world": ("YW", None),
    "_safe_assess_image_quality": ("IQMARK", None),
    "_safe_classify_weather": ("WXMARK", None),
    "_safe_analyze_depth": ("DEPTH", None),
    "_safe_detect_vehicle_damage": ("DAMAGE", None),
    "_safe_run_scene_ocr_frame": ("FRMOCRTOKEN", None),
    "_safe_segment_person_clothing": ("SEG", None),
    "_safe_clip_scene_classify": (({"a": 1.0}, "label"), None),
    "_safe_clip_threat_match": ("THREATMATCH", None),
    "_safe_run_scene_ocr_crops": ("CROPRESULT", None),
    "_recognize_actions_from_skeleton": ("ACTIONMARK", None),
    "_read_plates": (None, None),
    "_run_reid": (None, None),
    "_run_clip_anomaly_detection": (None, None),
    "_run_household_matching": (None, None),
    "_enrich_persons_via_unified_service": (None, None),
    "_enrich_vehicles_via_unified_service": (None, None),
    "_enrich_animals_via_unified_service": (None, None),
    "_estimate_poses_via_service": ({"POSE": "KEYS"}, None),
    "_detect_threats_via_service": ("THREATSVC", None),
    "_compute_reid_via_service": (None, None),
}


def _globals() -> dict[str, Any]:
    """The real globals dict of the method under test.

    Pristine: that is ``M.__dict__`` itself, so patching it is exactly the
    documented ``backend.services.enrichment_pipeline.X`` import-site patch.
    Under a mutant the plugin has exec'd the variant body into its own dict,
    and that dict — not ``M.__dict__`` — is what the running code resolves
    names against; patching it keeps the rig faithful in both worlds.

    Third world (MEASURED in the mutants/ tree at ep0 re-bank gate 2026-09-26):
    mutmut 3.8's trampoline wraps every module function, so ``f.__globals__``
    is the TRAMPOLINE MODULE's dict — patching it changes nothing and both
    the trampoline and the shipped variants resolve ``M.__dict__``. The
    trampoline carries ``__wrapped__`` (functools.wraps) pointing at the
    implementation whose globals ARE ``M.__dict__``; the ep_plugin world has
    no ``__wrapped__``, so this branch fires in exactly that one world.
    """
    f = M.EnrichmentPipeline._run_parallel_enrichment
    if f.__globals__ is not M.__dict__:
        w = getattr(f, "__wrapped__", None)
        if w is not None and w.__globals__ is M.__dict__:
            return M.__dict__
    return f.__globals__


@contextlib.contextmanager
def _patched(**values: Any) -> Any:
    g = _globals()
    saved = {k: g[k] for k in values if k in g}
    g.update(values)
    try:
        yield
    finally:
        for key in values:
            if key in saved:
                g[key] = saved[key]
            else:
                g.pop(key, None)


class Ctx:
    """Measurement rig plus shipped-behaviour probe helpers."""

    def __init__(self, **flags: Any) -> None:
        self.holders: dict[str, list[Any]] = {}
        self.extractor = _Extractor()
        self.detector = _Detector()
        all_flags = dict(_OFF)
        all_flags.update(flags)
        with (
            patch(f"{MODULE}.get_vision_extractor", return_value=self.extractor, create=True),
            patch(f"{MODULE}.get_reid_service", return_value=MagicMock(), create=True),
            patch(f"{MODULE}.get_scene_change_detector", return_value=self.detector, create=True),
            patch(f"{MODULE}.get_scene_ocr_service", return_value=MagicMock(), create=True),
        ):
            self.pipe = M.EnrichmentPipeline(model_manager=MagicMock(), **all_flags)
        self.pipe._quality_level = "full"
        self.pipe._vision_extractor = self.extractor
        self.pipe._scene_detector = self.detector
        self.pipe._is_fast_alpr_available = lambda: False
        for name, (ret, exc) in _WORKERS.items():
            self.set_worker(name, ret=ret, exc=exc)
        self.images: dict[Any, Any] = {"sentinel": "IMAGESDICT"}
        self.result = M.EnrichmentResult()
        self.logs: list[str] = []
        self.image: Any = None

    def set_worker(self, name: str, *, ret: Any = None, exc: BaseException | None = None) -> None:
        holder = self.holders.setdefault(name, [])
        holder.clear()
        setattr(self.pipe, name, _stub(name, ret, exc, holder))

    def args_for(self, name: str) -> list[tuple[Any, ...]]:
        return self.holders[name]

    def run(
        self,
        dets: list[Any],
        *,
        camera_id: str | None = CAM,
        images: dict[Any, Any] | None = None,
    ) -> BaseException | None:
        """Run the shipped method under patched telemetry/metrics/clock.

        Returns the raised exception (``SyntaxError`` for unparseable mutants,
        ``TypeError`` for arity-shifting ones) or ``None``.
        """
        img = Image.new("RGB", (16, 12), color=(9, 9, 9))
        self.image = img
        images = self.images if images is None else images
        reads = [0.0]

        def fake() -> float:
            reads[0] += STEP
            return reads[0]

        class _Clock:
            """Stand-in for the ``time`` module seen ONLY by enrichment_pipeline.

            ``patch.object(M.time, ...)`` would replace ``time.monotonic``
            process-wide and drive the asyncio event loop's clock past its own
            deadline, so the module reference itself is swapped instead.
            """

            monotonic = staticmethod(fake)
            time = staticmethod(__import__("time").time)
            perf_counter = staticmethod(__import__("time").perf_counter)

        class _Cap(logging.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.msgs: list[str] = []

            def emit(self, record: logging.LogRecord) -> None:
                self.msgs.append(record.getMessage())

        cap = _Cap()
        lg = M.logger
        previous_level = lg.level
        lg.addHandler(cap)
        lg.setLevel(logging.DEBUG)
        self.logs = cap.msgs
        self.bg = MagicMock(wraps=M.bounded_gather)
        self.span = MagicMock()
        self.stage = MagicMock()
        self.defer = MagicMock()

        async def _go() -> None:
            await self.pipe._run_parallel_enrichment(
                result=self.result,
                pil_image=img,
                high_conf_detections=dets,
                images=images,
                camera_id=camera_id,
            )

        err: BaseException | None = None
        with _patched(
            bounded_gather=self.bg,
            add_span_event=self.span,
            observe_enrichment_pipeline_stage=self.stage,
            record_cascade_model_deferred=self.defer,
            time=_Clock(),
        ):
            try:
                asyncio.run(asyncio.wait_for(_go(), timeout=20))
            except BaseException as exc:  # noqa: BLE001 - recorded, asserted below
                err = exc
        lg.removeHandler(cap)
        lg.setLevel(previous_level)
        return err

    # -- derived views ------------------------------------------------------
    def gathers(self) -> dict[frozenset[str], dict[str, Any]]:
        """frozenset(coroutine names) -> kwargs, for every ``bounded_gather`` call."""
        out: dict[frozenset[str], dict[str, Any]] = {}
        for call in self.bg.call_args_list:
            coros = call.args[0]
            names = frozenset(
                getattr(getattr(c, "cr_code", None), "co_name", f"<{type(c).__name__}>")
                for c in coros
            )
            out[names] = dict(call.kwargs)
        return out

    def span_events(self) -> list[tuple[Any, Any]]:
        return [
            (c.args[0] if c.args else _UNSET, c.args[1] if len(c.args) > 1 else _UNSET)
            for c in self.span.call_args_list
        ]

    def stages(self) -> list[tuple[Any, Any]]:
        return [(c.args[0], c.args[1]) for c in self.stage.call_args_list]

    def defers(self) -> list[tuple[Any, ...]]:
        return [c.args for c in self.defer.call_args_list]

    def errors(self) -> list[tuple[str, str | None]]:
        return [(e.operation, e.error_type) for e in self.result.structured_errors]


# ---------------------------------------------------------------------------
# scenarios.  Each one asserts its own shipped pre-condition so a broken rig
# can never masquerade as a mutant kill.
# ---------------------------------------------------------------------------
def s_cpu3() -> Ctx:
    """Local path, 3 phase-1 tasks, all CPU-bound, no florence (L2536-L2568)."""
    c = Ctx(
        image_quality_enabled=True,
        weather_classification_enabled=True,
        scene_ocr_enabled=True,
    )
    assert c.run([_det("package", 0.95, 7)]) is None
    assert c.span_events()[0][1]["phase1_task.count"] == 3, c.span_events()
    return c


def s_flo1() -> Ctx:
    """CPU task + florence with 1 ambiguous + 1 high-conf detection (L2576-L2597)."""
    c = Ctx(weather_classification_enabled=True, vision_extraction_enabled=True)
    assert c.run([_det("package", 0.55, 7), _det("package", 0.95, 8)]) is None
    assert c.extractor.calls, "florence task never awaited"
    assert c.span_events()[0][1]["phase1_task.count"] == 1, c.span_events()
    return c


def s_flo_err() -> Ctx:
    """GPU (yolo-world) + CPU tasks, florence task raises (L2701-L2734)."""
    c = Ctx(
        yolo_world_enabled=True,
        weather_classification_enabled=True,
        vision_extraction_enabled=True,
    )
    c.extractor.exc = Boom("florence down")
    assert c.run([_det("package", 0.55, 7), _det("package", 0.95, 8)]) is None
    assert c.extractor.calls, "florence task never awaited"
    assert ("vision_extraction", "Boom") in c.errors(), c.errors()
    return c


def s_split() -> Ctx:
    """2 GPU-bound + 2 CPU-bound phase-1 tasks, no florence (L2655-L2699)."""
    c = Ctx(
        smoke_fire_detection_enabled=True,
        yolo_world_enabled=True,
        weather_classification_enabled=True,
        scene_ocr_enabled=True,
    )
    assert c.run([_det("package", 0.95, 7)]) is None
    g = c.gathers()
    assert frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"}) in g, g
    return c


def s_service() -> Ctx:
    """Unified-service path: every phase-1 task goes to the CPU group (L2657)."""
    c = Ctx(
        smoke_fire_detection_enabled=True,
        yolo_world_enabled=True,
        use_enrichment_service=True,
    )
    assert c.run([_det("person", 0.95, 7)]) is None
    attrs = c.span_events()[0][1]
    assert attrs["use_enrichment_service"] is True, attrs
    assert len(c.gathers()) == 1, c.gathers()
    return c


def s_action() -> Ctx:
    """Florence + pose + skeleton action recognition, local path (L2715-L2729)."""
    c = Ctx(
        pose_estimation_enabled=True,
        action_recognition_enabled=True,
        vision_extraction_enabled=True,
    )
    assert c.run([_det("person", 0.55, 7)]) is None
    assert c.result.pose_results == {"POSE": "KEYS"}, c.result.pose_results
    assert c.args_for("_recognize_actions_from_skeleton"), "action call not reached"
    return c


def s_action_err() -> Ctx:
    """s_action with the skeleton-action worker raising (L2728-L2729)."""
    c = Ctx(
        pose_estimation_enabled=True,
        action_recognition_enabled=True,
        vision_extraction_enabled=True,
    )
    c.set_worker("_recognize_actions_from_skeleton", exc=Boom("stgcn down"))
    assert c.run([_det("person", 0.55, 7)]) is None
    assert ("action_recognition", "Boom") in c.errors(), c.errors()
    return c


def s_no_poses() -> Ctx:
    """Action enabled, persons present, NO pose results (gate L2715-L2720).

    A weather task keeps the super-phase block alive so the action gate is
    actually evaluated (with an empty ``phase1_tasks`` dict the whole block is
    skipped and the gate is never reached).
    """
    c = Ctx(action_recognition_enabled=True, weather_classification_enabled=True)
    assert c.run([_det("person", 0.95, 7)]) is None
    assert c.result.weather_classification == "WXMARK", c.result.weather_classification
    assert c.result.pose_results == {}, c.result.pose_results
    assert not c.args_for("_recognize_actions_from_skeleton")
    return c


def s_phase2() -> Ctx:
    """Phase 2: local re-ID + scene change + scene-OCR-crop (L2770-L2804)."""
    c = Ctx(
        reid_enabled=True,
        redis_client=MagicMock(name="redis"),
        scene_change_enabled=True,
        scene_ocr_enabled=True,
    )
    assert c.run([_det("person", 0.95, 7)]) is None
    key = frozenset({"_reid_local_task", "_scene_change_task", "_scene_ocr_crop_task"})
    assert c.gathers().get(key) == P2_KW, c.gathers()
    return c


def s_phase2_reid_err() -> Ctx:
    """s_phase2 with the re-ID worker raising (phase-2 routing L2813-L2815)."""
    c = Ctx(
        reid_enabled=True,
        redis_client=MagicMock(name="redis"),
        scene_change_enabled=True,
        scene_ocr_enabled=True,
    )
    c.set_worker("_run_reid", exc=Boom("reid down"))
    assert c.run([_det("person", 0.95, 7)]) is None
    assert c.errors() == [("re_identification", "Boom")], c.errors()
    return c


def s_scene_err() -> Ctx:
    """s_phase2 with the scene-change detector raising (pins key L2790)."""
    c = Ctx(
        scene_change_enabled=True,
        scene_ocr_enabled=True,
    )
    c.detector.exc = Boom("scene down")
    assert c.run([_det("person", 0.95, 7)]) is None
    assert c.errors() == [("scene_change_detection", "Boom")], c.errors()
    return c


def s_ocr() -> Ctx:
    """Phase 2 OCR + scene-OCR-crop; crop sees the phase-1 frame OCR (L2759-L2804)."""
    c = Ctx(ocr_enabled=True, scene_ocr_enabled=True)
    c.result.license_plates = [_Plate(""), _Plate("ABC123"), _Plate("")]
    assert c.run([_det("package", 0.95, 7)]) is None
    assert c.args_for("_read_plates"), "_read_plates never reached"
    assert c.args_for("_safe_run_scene_ocr_crops"), "crop task never reached"
    # the phase-1 frame OCR is handed to the crop worker (shipped L2799-L2802)
    assert c.args_for("_safe_run_scene_ocr_crops")[0][2] == "FRMOCRTOKEN", c.args_for(
        "_safe_run_scene_ocr_crops"
    )
    return c


def s_ocr_err() -> Ctx:
    """s_ocr with ``_read_plates`` raising (pins the phase-2 key L2765)."""
    c = Ctx(ocr_enabled=True)
    c.result.license_plates = [_Plate("")]
    c.set_worker("_read_plates", exc=Boom("paddle down"))
    assert c.run([_det("package", 0.95, 7)]) is None
    assert c.errors() == [("ocr", "Boom")], c.errors()
    return c


def s_crop_err() -> Ctx:
    """s_ocr with the scene-OCR-crop worker raising (pins key L2804)."""
    c = Ctx(scene_ocr_enabled=True)
    c.set_worker("_safe_run_scene_ocr_crops", exc=Boom("crop down"))
    assert c.run([_det("package", 0.95, 7)]) is None
    assert c.errors() == [("scene_ocr_crop", "Boom")], c.errors()
    return c


def s_no_camera() -> Ctx:
    """Scene-change gate with ``camera_id=None`` (gate L2782)."""
    c = Ctx(scene_change_enabled=True, scene_ocr_enabled=True)
    assert c.run([_det("package", 0.95, 7)], camera_id=None) is None
    assert not c.detector.calls, c.detector.calls
    return c


def s_no_dets() -> Ctx:
    """Scene-OCR-crop gate with zero detections (gate L2794-L2798)."""
    c = Ctx(scene_ocr_enabled=True)
    assert c.run([]) is None
    assert not c.args_for("_safe_run_scene_ocr_crops")
    return c


def s_all() -> Ctx:
    """Every pinned region at once (L2584-L2815)."""
    c = Ctx(
        smoke_fire_detection_enabled=True,
        weather_classification_enabled=True,
        scene_ocr_enabled=True,
        scene_change_enabled=True,
        reid_enabled=True,
        redis_client=MagicMock(name="redis"),
        ocr_enabled=True,
        pose_estimation_enabled=True,
        action_recognition_enabled=True,
        vision_extraction_enabled=True,
    )
    c.result.license_plates = [_Plate("")]
    assert c.run([_det("person", 0.55, 7)]) is None
    assert c.errors() == [], c.errors()
    return c


# ===========================================================================
# A) Florence-2 ``det_dicts`` payload + call (shipped L2584-L2595)
# ===========================================================================
def test_florence_dict_class_name_key() -> None:
    (_image, dets) = s_flo1().extractor.calls[0]
    assert [d["class_name"] for d in dets] == ["package"], dets
    assert DET_KEYS <= set(dets[0]), dets[0]


def test_florence_dict_confidence_key() -> None:
    (_image, dets) = s_flo1().extractor.calls[0]
    assert [d["confidence"] for d in dets] == [0.55], dets
    assert set(dets[0]) == DET_KEYS, dets[0]


def test_florence_dict_confidence_key_case() -> None:
    (_image, dets) = s_flo1().extractor.calls[0]
    assert set(dets[0]) == DET_KEYS, dets[0]
    assert dets[0]["confidence"] == 0.55, dets[0]


def test_florence_dict_bbox_key() -> None:
    (_image, dets) = s_flo1().extractor.calls[0]
    assert [d["bbox"] for d in dets] == [BOX_T], dets


def test_florence_dict_bbox_key_case() -> None:
    (_image, dets) = s_flo1().extractor.calls[0]
    assert set(dets[0]) == DET_KEYS, dets[0]
    assert dets[0]["bbox"] == BOX_T, dets[0]


def test_florence_dict_bbox_value_survives_guard() -> None:
    """``d.bbox.to_tuple() if d.bbox else None`` -> the real tuple for a real bbox."""
    (_image, dets) = s_flo1().extractor.calls[0]
    assert dets[0]["bbox"] is not None and dets[0]["bbox"] == BOX_T, dets[0]


def test_florence_dict_bbox_true_branch() -> None:
    (_image, dets) = s_flo1().extractor.calls[0]
    assert dets[0]["bbox"] == BOX_T, dets[0]


def test_florence_dict_bbox_none_passthrough() -> None:
    """Shipped accepts ``bbox=None`` (slots dataclass, no runtime guard) and the
    ``if d.bbox else None`` guard yields ``None`` — the call still happens."""
    c = Ctx(vision_extraction_enabled=True)
    assert c.run([_det("package", 0.55, 7, bbox=None)]) is None
    assert c.result.vision_extraction == "FLOSCAR", c.result.vision_extraction
    (image, dets) = c.extractor.calls[0]
    assert image is c.image, c.extractor.calls
    assert dets[0]["bbox"] is None, dets[0]


def test_florence_dict_id_key() -> None:
    (_image, dets) = s_flo1().extractor.calls[0]
    assert [d["detection_id"] for d in dets] == ["7"], dets
    assert set(dets[0]) == DET_KEYS, dets[0]


def test_florence_dict_id_key_case() -> None:
    (_image, dets) = s_flo1().extractor.calls[0]
    assert set(dets[0]) == DET_KEYS, dets[0]
    assert "detection_id" in dets[0], dets[0]


def test_florence_dict_id_false_when_id_present() -> None:
    """With ``d.id`` set the id must be ``str(d.id)``, never the enumerate index."""
    (_image, dets) = s_flo1().extractor.calls[0]
    assert dets[0]["detection_id"] == "7", dets[0]


def test_florence_dict_id_true_branch_uses_id() -> None:
    c = Ctx(vision_extraction_enabled=True)
    assert c.run([_det("package", 0.55, 7)]) is None
    (_image, dets) = c.extractor.calls[0]
    assert dets[0]["detection_id"] == "7", dets[0]


def test_florence_dict_id_idless_falls_back_to_index() -> None:
    c = Ctx(vision_extraction_enabled=True)
    assert c.run([_det("package", 0.55, None), _det("package", 0.6, None)]) is None
    (_image, dets) = c.extractor.calls[0]
    assert [d["detection_id"] for d in dets] == ["0", "1"], dets


def test_florence_dict_id_stringified() -> None:
    c = Ctx(vision_extraction_enabled=True)
    assert c.run([_det("package", 0.55, 7)]) is None
    (_image, dets) = c.extractor.calls[0]
    assert dets[0]["detection_id"] == "7", dets[0]


def test_florence_call_image_first() -> None:
    c = s_flo1()
    (image, dets) = c.extractor.calls[0]
    assert image is c.image, "shipped passes (pil_image, det_dicts)"
    assert isinstance(dets, list), dets


def test_florence_call_dets_second() -> None:
    c = s_flo1()
    (image, dets) = c.extractor.calls[0]
    assert len(dets) == 1 and dets[0]["class_name"] == "package", dets
    assert image is c.image, "second argument must be the det_dicts list"


def test_florence_call_positional_count() -> None:
    c = s_flo1()
    assert len(c.extractor.calls) == 1, c.extractor.calls
    assert len(c.extractor.calls[0]) == 2, c.extractor.calls


def test_florence_call_two_positionals() -> None:
    c = s_flo1()
    (image, dets) = c.extractor.calls[0]
    assert image is c.image and isinstance(dets, list), c.extractor.calls


def test_florence_deferred_count_log() -> None:
    c = s_flo1()
    assert "Florence-2 deferred for 1/2 high-confidence detections" in "\n".join(c.logs), c.logs


def test_florence_deferred_metric_fires() -> None:
    c = s_flo1()
    assert ("florence2", "high_confidence") in c.defers(), c.defers()


def test_florence_deferred_metric_gate_zero() -> None:
    """``deferred_count == 0`` (all detections ambiguous) records no deferral."""
    c = Ctx(vision_extraction_enabled=True)
    assert c.run([_det("package", 0.55, 7)]) is None
    assert ("florence2", "high_confidence") not in c.defers(), c.defers()
    assert ("florence2", "all_high_confidence") not in c.defers(), c.defers()


def test_florence_result_assigned() -> None:
    assert s_flo1().result.vision_extraction == "FLOSCAR"


def test_florence_result_assigned_again() -> None:
    c = s_flo1()
    assert c.result.vision_extraction == "FLOSCAR", c.result.vision_extraction
    assert not any(op == "vision_extraction" for op, _ in c.errors()), c.errors()


def test_florence_exception_routed() -> None:
    c = s_flo_err()
    assert c.errors() == [("vision_extraction", "Boom")], c.errors()
    assert c.result.vision_extraction is None, c.result.vision_extraction


# ===========================================================================
# B) super-phase START span event (shipped L2641-L2650)
# ===========================================================================
def test_start_span_positional_name() -> None:
    (name, attrs) = s_cpu3().span_events()[0]
    assert name == START, name
    assert isinstance(attrs, dict), attrs


def test_start_span_attrs_none() -> None:
    (_name, attrs) = s_cpu3().span_events()[0]
    assert set(attrs) == {
        "phase1_task.count",
        "phase1_tasks",
        "florence_enabled",
        "use_enrichment_service",
    }, attrs


def test_start_span_no_attrs() -> None:
    (name, attrs) = s_cpu3().span_events()[0]
    assert name == START, name
    assert isinstance(attrs, dict) and len(attrs) == 4, attrs


def test_start_span_single_arg_call() -> None:
    (name, attrs) = s_cpu3().span_events()[0]
    assert name == START, name
    assert attrs["phase1_task.count"] == 3, attrs


def test_start_span_name_variant_lower() -> None:
    (name, _attrs) = s_cpu3().span_events()[0]
    assert name == START, name


def test_start_span_name_variant_upper() -> None:
    (name, _attrs) = s_cpu3().span_events()[0]
    assert name == START, name


def test_start_span_count_key() -> None:
    assert s_cpu3().span_events()[0][1]["phase1_task.count"] == 3


def test_start_span_count_key_case() -> None:
    attrs = s_cpu3().span_events()[0][1]
    assert "phase1_task.count" in attrs, attrs
    assert attrs["phase1_task.count"] == 3, attrs


def test_start_span_tasks_key() -> None:
    assert "weather_classification" in s_cpu3().span_events()[0][1]["phase1_tasks"]


def test_start_span_tasks_key_case() -> None:
    attrs = s_cpu3().span_events()[0][1]
    assert "phase1_tasks" in attrs, attrs
    assert "weather_classification" in attrs["phase1_tasks"], attrs


def test_start_span_tasks_join_sep() -> None:
    value = s_cpu3().span_events()[0][1]["phase1_tasks"]
    assert value == "image_quality, weather_classification, scene_ocr_frame", value


def test_start_span_service_key() -> None:
    assert s_service().span_events()[0][1]["use_enrichment_service"] is True


def test_start_span_service_key_case() -> None:
    attrs = s_service().span_events()[0][1]
    assert "use_enrichment_service" in attrs, attrs
    assert attrs["use_enrichment_service"] is True, attrs


def test_start_span_florence_flag_true() -> None:
    assert s_flo1().span_events()[0][1]["florence_enabled"] is True


def test_start_span_florence_flag_false() -> None:
    assert s_cpu3().span_events()[0][1]["florence_enabled"] is False


# ===========================================================================
# C) GPU/CPU partition, florence placement, per-group timeouts
#    (shipped L2655-L2699)
# ===========================================================================
def test_partition_gpu_cpu_batches() -> None:
    g = s_split().gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    cpu = frozenset({"_safe_classify_weather", "_safe_run_scene_ocr_frame"})
    assert g[gpu] == GPU_KW, g
    assert g[cpu] == CPU_KW, g


def test_partition_service_path_all_cpu() -> None:
    """``use_enrichment_service=True`` -> no task is placed in the GPU group."""
    c = s_service()
    g = c.gathers()
    key = frozenset(
        {
            "_enrich_persons_via_unified_service",
            "_detect_threats_via_service",
            "_safe_detect_smoke_fire",
            "_safe_detect_yolo_world",
        }
    )
    assert g[key] == CPU_KW, g


def test_partition_local_path_splits_gpu() -> None:
    """With the service off, GPU-named tasks get ``limit=2`` / ``21.0``."""
    g = s_split().gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    assert g[gpu]["limit"] == 2, g[gpu]
    assert g[gpu]["task_timeout"] == 21.0, g[gpu]


def test_partition_negation_keeps_gpu() -> None:
    g = s_split().gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    assert gpu in g, g
    assert g[gpu]["limit"] == 2, g[gpu]


def test_partition_membership_keeps_gpu() -> None:
    g = s_split().gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    assert g[gpu]["limit"] == 2 and g[gpu]["task_timeout"] == 21.0, g[gpu]


def test_florence_joins_gpu_group() -> None:
    g = s_flo1().gathers()
    key = frozenset({"extract_batch_attributes"})
    assert g[key] == GPU_KW, g


def test_florence_coro_in_gpu_batch() -> None:
    c = s_flo1()
    g = c.gathers()
    assert frozenset({"extract_batch_attributes"}) in g, g
    assert g[frozenset({"extract_batch_attributes"})]["limit"] == 2, g


def test_florence_coro_only_in_gpu_batch() -> None:
    c = s_split()
    g = c.gathers()
    assert frozenset({"extract_batch_attributes"}) not in g, g
    assert c.span_events()[0][1]["florence_enabled"] is False, c.span_events()


def test_gpu_group_limit_two() -> None:
    g = s_split().gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    assert g[gpu]["limit"] == 2, g[gpu]


def test_gpu_group_timeout_value() -> None:
    g = s_split().gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    assert g[gpu]["task_timeout"] == 21.0, g[gpu]


def test_gpu_timeout_not_none() -> None:
    g = s_split().gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    assert "task_timeout" in g[gpu], g[gpu]
    assert g[gpu]["task_timeout"] == 21.0, g[gpu]


def test_gpu_timeout_no_florence_still_21() -> None:
    g = s_split().gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    assert g[gpu]["task_timeout"] == 21.0, g[gpu]


def test_florence_group_timeout_21() -> None:
    g = s_flo1().gathers()
    assert g[frozenset({"extract_batch_attributes"})]["task_timeout"] == 21.0, g


def test_cpu_group_timeout_15() -> None:
    g = s_split().gathers()
    cpu = frozenset({"_safe_classify_weather", "_safe_run_scene_ocr_frame"})
    assert g[cpu]["task_timeout"] == 15.0, g[cpu]


def test_gpu_group_limit_present() -> None:
    g = s_split().gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    assert "limit" in g[gpu], g[gpu]
    assert g[gpu]["limit"] == 2, g[gpu]


def test_gpu_timeout_kwarg_present() -> None:
    g = s_split().gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    assert "task_timeout" in g[gpu], g[gpu]


def test_gpu_group_limit_three_rejected() -> None:
    g = s_split().gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    assert g[gpu]["limit"] == 2, g[gpu]


def test_cpu_group_timeout_not_none() -> None:
    g = s_split().gathers()
    cpu = frozenset({"_safe_classify_weather", "_safe_run_scene_ocr_frame"})
    assert "task_timeout" in g[cpu], g[cpu]
    assert g[cpu]["task_timeout"] == 15.0, g[cpu]


def test_cpu_timeout_kwarg_present() -> None:
    g = s_split().gathers()
    cpu = frozenset({"_safe_classify_weather", "_safe_run_scene_ocr_frame"})
    assert "task_timeout" in g[cpu], g[cpu]


def test_cpu_group_timeout_value_again() -> None:
    g = s_split().gathers()
    cpu = frozenset({"_safe_classify_weather", "_safe_run_scene_ocr_frame"})
    assert g[cpu]["task_timeout"] == 15.0, g[cpu]


def test_phase1_result_pairing() -> None:
    """``zip(keys, results, strict=True)`` maps each result to its own key."""
    c = s_split()
    assert c.result.weather_classification == "WXMARK", c.result
    assert c.result.smoke_fire_detection == "SMOKEMARK", c.result


# ===========================================================================
# D) skeleton action recognition: gate, call args, error routing
#    (shipped L2715-L2729)
# ===========================================================================
def test_action_gate_requires_pose_results() -> None:
    c = s_no_poses()
    assert not c.args_for("_recognize_actions_from_skeleton"), c.args_for(
        "_recognize_actions_from_skeleton"
    )


def test_action_call_pose_arg() -> None:
    (args,) = s_action().args_for("_recognize_actions_from_skeleton")
    assert args[0] == {"POSE": "KEYS"}, args


def test_action_call_persons_arg() -> None:
    (args,) = s_action().args_for("_recognize_actions_from_skeleton")
    assert [d.id for d in args[1]] == [7], args


def test_action_call_camera_arg() -> None:
    (args,) = s_action().args_for("_recognize_actions_from_skeleton")
    assert args[2] == CAM, args


def test_action_call_positional_count() -> None:
    (args,) = s_action().args_for("_recognize_actions_from_skeleton")
    assert len(args) == 3, args
    assert args[2] == CAM, args


def test_action_call_persons_count() -> None:
    (args,) = s_action().args_for("_recognize_actions_from_skeleton")
    assert len(args) == 3, args
    assert [d.id for d in args[1]] == [7], args


def test_action_call_trailing_comma_arity() -> None:
    (args,) = s_action().args_for("_recognize_actions_from_skeleton")
    assert len(args) == 3, args
    assert args[0] == {"POSE": "KEYS"}, args


def test_action_result_assigned() -> None:
    assert s_action().result.action_results == "ACTIONMARK"


def test_action_error_operation() -> None:
    assert s_action_err().errors() == [("action_recognition", "Boom")]


def test_action_error_operation_case() -> None:
    c = s_action_err()
    assert [op for op, _ in c.errors()] == ["action_recognition"], c.errors()


def test_action_error_exception_kept() -> None:
    c = s_action_err()
    assert c.errors()[0][1] == "Boom", c.errors()


def test_florence_error_exception_kept() -> None:
    c = s_flo_err()
    assert c.errors()[0] == ("vision_extraction", "Boom"), c.errors()


# ===========================================================================
# E) phase-1 timing, metric label, COMPLETE span, debug log
#    (shipped L2737-L2751)
# ===========================================================================
def test_phase1_duration_positive() -> None:
    assert s_cpu3().stages()[0] == ("phase1_and_florence", 1.5)


def test_phase1_stage_label() -> None:
    assert s_cpu3().stages()[0][0] == "phase1_and_florence", s_cpu3().stages()


def test_phase1_stage_label_lower() -> None:
    assert s_cpu3().stages()[0][0] == "phase1_and_florence"


def test_phase1_stage_label_upper() -> None:
    assert s_cpu3().stages()[0][0] == "phase1_and_florence"


def test_complete_span_positional_name() -> None:
    (_start, second) = s_cpu3().span_events()
    assert second[0] == COMPLETE, second
    assert isinstance(second[1], dict), second


def test_complete_span_attrs_keys() -> None:
    attrs = s_cpu3().span_events()[1][1]
    assert set(attrs) == {"phase1_task.count", "florence_enabled", "duration_ms"}, attrs


def test_complete_span_no_attrs() -> None:
    (name, attrs) = s_cpu3().span_events()[1]
    assert name == COMPLETE, name
    assert isinstance(attrs, dict) and len(attrs) == 3, attrs


def test_complete_span_single_arg_call() -> None:
    (name, attrs) = s_cpu3().span_events()[1]
    assert name == COMPLETE, name
    assert attrs["duration_ms"] == 1500, attrs


def test_complete_span_name_lower() -> None:
    assert s_cpu3().span_events()[1][0] == COMPLETE


def test_complete_span_name_upper() -> None:
    assert s_cpu3().span_events()[1][0] == COMPLETE


def test_complete_span_count_key() -> None:
    assert s_cpu3().span_events()[1][1]["phase1_task.count"] == 3


def test_complete_span_count_key_case() -> None:
    attrs = s_cpu3().span_events()[1][1]
    assert "phase1_task.count" in attrs, attrs
    assert attrs["phase1_task.count"] == 3, attrs


def test_complete_span_duration_ms_key() -> None:
    assert s_cpu3().span_events()[1][1]["duration_ms"] == 1500


def test_complete_span_duration_ms_key_case() -> None:
    attrs = s_cpu3().span_events()[1][1]
    assert "duration_ms" in attrs, attrs
    assert attrs["duration_ms"] == 1500, attrs


def test_complete_span_duration_ms_scale_ms() -> None:
    assert s_cpu3().span_events()[1][1]["duration_ms"] == 1500


def test_complete_span_duration_ms_scale_s() -> None:
    attrs = s_cpu3().span_events()[1][1]
    assert attrs["duration_ms"] == 1500, attrs


def test_complete_span_duration_ms_offbyone() -> None:
    assert s_cpu3().span_events()[1][1]["duration_ms"] == 1500


def test_debug_log_no_florence() -> None:
    assert "Phase 1 + Florence completed in 1.50s (3 phase1 tasks)" in s_cpu3().logs


def test_debug_log_florence_suffix() -> None:
    assert "Phase 1 + Florence completed in 1.50s (1 phase1 tasks + florence)" in s_flo1().logs


def test_debug_log_florence_suffix_text() -> None:
    assert any(line.endswith("+ florence)") for line in s_flo1().logs), s_flo1().logs


def test_debug_log_florence_suffix_case() -> None:
    assert any(line.endswith("+ florence)") for line in s_flo1().logs), s_flo1().logs


def test_debug_log_no_florence_exact() -> None:
    assert "Phase 1 + Florence completed in 1.50s (3 phase1 tasks)" in s_cpu3().logs


def test_debug_log_empty_suffix_exact() -> None:
    assert "Phase 1 + Florence completed in 1.50s (3 phase1 tasks)" in s_cpu3().logs


def test_debug_log_message_present() -> None:
    assert any("Phase 1 + Florence completed" in line for line in s_cpu3().logs), s_cpu3().logs


# ===========================================================================
# F) phase 2: OCR / re-ID / scene change / scene-OCR-crop
#    (shipped L2755-L2815)
# ===========================================================================
def test_ocr_call_plates_arg() -> None:
    (args,) = s_ocr().args_for("_read_plates")
    assert [p.text for p in args[0]] == ["", ""], args
    assert len(args) == 2, args


def test_ocr_call_images_arg() -> None:
    c = s_ocr()
    (args,) = c.args_for("_read_plates")
    assert args[1] is c.images, args


def test_ocr_task_key() -> None:
    assert s_ocr_err().errors() == [("ocr", "Boom")]


def test_ocr_task_key_case() -> None:
    assert [op for op, _ in s_ocr_err().errors()] == ["ocr"]


def test_reid_gate_requires_redis() -> None:
    """``reid_enabled`` without ``redis_client`` schedules no re-ID task (L2770-L2780)."""
    c = Ctx(reid_enabled=True, scene_ocr_enabled=True)
    assert c.run([_det("person", 0.95, 7)]) is None
    assert not c.args_for("_run_reid"), c.args_for("_run_reid")
    assert not any("_reid_local_task" in key for key in c.gathers()), c.gathers()


def test_reid_gate_requires_enabled() -> None:
    """``reid_enabled=False`` schedules no re-ID task even with a redis client.

    The shipped conjunction at L2770 needs BOTH operands, so the local re-ID
    task disappears when the flag is off — no matter that ``pil_image`` is
    truthy and ``redis_client`` is set.
    """
    c = Ctx(
        reid_enabled=False,
        redis_client=MagicMock(name="redis"),
        weather_classification_enabled=True,
    )
    assert c.run([_det("person", 0.95, 7)]) is None
    assert c.result.weather_classification == "WXMARK", c.result.weather_classification
    assert not c.args_for("_run_reid"), c.args_for("_run_reid")
    assert not any("_reid_local_task" in key for key in c.gathers()), c.gathers()


def test_scene_gate_requires_camera() -> None:
    c = s_no_camera()
    assert not c.detector.calls, c.detector.calls
    assert c.result.scene_change is None, c.result.scene_change


def test_scene_gate_requires_camera_again() -> None:
    c = s_no_camera()
    assert c.result.scene_change is None, c.result.scene_change
    assert not c.detector.calls, c.detector.calls


def test_scene_call_camera_arg() -> None:
    (args,) = s_phase2().detector.calls
    assert args[0] == CAM, args


def test_scene_call_frame_arg() -> None:
    (args,) = s_phase2().detector.calls
    assert args[1] is not None and args[1].shape == (12, 16, 3), args


def test_scene_call_positional_count() -> None:
    c = s_phase2()
    assert len(c.detector.calls) == 1, c.detector.calls
    assert len(c.detector.calls[0]) == 2, c.detector.calls


def test_scene_detector_called_once_with_two_args() -> None:
    c = s_phase2()
    assert len(c.detector.calls[0]) == 2, c.detector.calls
    assert c.result.scene_change == "SCENEMARK", c.result.scene_change


def test_scene_task_key() -> None:
    assert s_scene_err().errors() == [("scene_change_detection", "Boom")]


def test_scene_ocr_crop_gate_requires_detections() -> None:
    assert not s_no_dets().args_for("_safe_run_scene_ocr_crops")


def test_crop_frame_ocr_arg() -> None:
    (args,) = s_ocr().args_for("_safe_run_scene_ocr_crops")
    assert args[2] == "FRMOCRTOKEN", args


def test_crop_result_assigned() -> None:
    c = s_ocr()
    assert c.result.scene_ocr == "CROPRESULT", c.result.scene_ocr
    assert c.args_for("_safe_run_scene_ocr_crops"), "crop coroutine dropped"


def test_crop_image_arg() -> None:
    c = s_ocr()
    (args,) = c.args_for("_safe_run_scene_ocr_crops")
    assert args[0] is c.image, args


def test_crop_detections_arg() -> None:
    (args,) = s_ocr().args_for("_safe_run_scene_ocr_crops")
    assert [d.id for d in args[1]] == [7], args


def test_crop_frame_result_arg() -> None:
    (args,) = s_ocr().args_for("_safe_run_scene_ocr_crops")
    assert args[2] == "FRMOCRTOKEN", args


def test_crop_positional_count_three() -> None:
    (args,) = s_ocr().args_for("_safe_run_scene_ocr_crops")
    assert len(args) == 3, args


def test_crop_positional_count_not_two() -> None:
    (args,) = s_ocr().args_for("_safe_run_scene_ocr_crops")
    assert len(args) == 3, args
    assert args[0] is not None and not hasattr(args[0], "id"), args


def test_crop_full_wiring() -> None:
    c = s_ocr()
    (args,) = c.args_for("_safe_run_scene_ocr_crops")
    assert len(args) == 3, args
    assert args[0] is c.image, args
    assert [d.id for d in args[1]] == [7], args
    assert args[2] == "FRMOCRTOKEN", args
    assert c.result.scene_ocr == "CROPRESULT", c.result.scene_ocr


def test_crop_task_is_scheduled() -> None:
    c = s_ocr()
    assert frozenset({"_ocr_task", "_scene_ocr_crop_task"}) in c.gathers(), c.gathers()


def test_crop_task_key() -> None:
    assert [op for op, _ in s_crop_err().errors()] == ["scene_ocr_crop"]


def test_crop_task_key_exact() -> None:
    assert s_crop_err().errors() == [("scene_ocr_crop", "Boom")]


def test_phase2_error_key_routing() -> None:
    assert s_phase2_reid_err().errors() == [("re_identification", "Boom")]


def test_phase2_duration_positive() -> None:
    assert s_phase2().stages()[1] == ("phase2", 1.5), s_phase2().stages()


def test_phase2_zip_keeps_pairing() -> None:
    c = s_phase2_reid_err()
    assert c.errors()[0] == ("re_identification", "Boom"), c.errors()
    assert c.result.scene_change == "SCENEMARK", c.result.scene_change


def test_phase2_error_exception_kept() -> None:
    c = s_phase2_reid_err()
    assert c.errors()[0][1] == "Boom", c.errors()


def test_baseline_gpu_cpu_phase2() -> None:
    """Whole-method shipped baseline: batch shapes, spans, results, no errors."""
    c = s_split()
    g = c.gathers()
    gpu = frozenset({"_safe_detect_smoke_fire", "_safe_detect_yolo_world"})
    cpu = frozenset({"_safe_classify_weather", "_safe_run_scene_ocr_frame"})
    assert g[gpu] == GPU_KW and g[cpu] == CPU_KW, g
    assert [n for n, _ in c.span_events()] == [START, COMPLETE], c.span_events()
    assert c.stages()[0][0] == "phase1_and_florence", c.stages()
    assert c.result.weather_classification == "WXMARK", c.result
    assert c.errors() == [], c.errors()


def test_baseline_all_features() -> None:
    """Florence + phase-1 groups + all three phase-2 tasks + both spans."""
    c = s_all()
    (image, dets) = c.extractor.calls[0]
    assert image is c.image, c.extractor.calls
    assert [d["detection_id"] for d in dets] == ["7"], dets
    assert len(c.args_for("_read_plates")[0]) == 2, c.args_for("_read_plates")
    assert len(c.detector.calls[0]) == 2, c.detector.calls
    assert c.detector.calls[0][0] == CAM, c.detector.calls
    assert len(c.args_for("_safe_run_scene_ocr_crops")[0]) == 3
    assert [n for n, _ in c.span_events()] == [START, COMPLETE], c.span_events()
    assert c.span_events()[0][1]["florence_enabled"] is True, c.span_events()
    assert [s[0] for s in c.stages()[:2]] == ["phase1_and_florence", "phase2"], c.stages()
    assert c.result.scene_ocr == "CROPRESULT", c.result.scene_ocr
    assert c.result.action_results == "ACTIONMARK", c.result.action_results
