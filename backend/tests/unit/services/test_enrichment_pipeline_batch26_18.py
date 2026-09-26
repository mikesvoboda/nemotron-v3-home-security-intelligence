"""Chunk 18 kill-battery: enrichment_pipeline survivors (batch-26).

Methods under test (all pinned to SHIPPED behaviour, probed before asserting):
- EnrichmentPipeline._safe_clip_scene_classify        (mutmut _1.._15)
- EnrichmentPipeline._estimate_poses                  (mutmut _20.._44)
- EnrichmentPipeline._enrich_single_detection_unified (mutmut _1.._53)
- EnrichmentPipeline._run_household_matching          (mutmut _7.._75)

Two harness facts drive the patch topology:

1. The swap plugin binds a mutant body EXEC'd in a snapshot of the live module
   dict taken at bind time, so a mutant resolves module-level names through THAT
   snapshot. A function-scoped ``patch("backend.services.enrichment_pipeline.X")``
   (applied after the bind) would be invisible to a mutant. The module-level
   names a mutant touches are therefore patched once for the whole file by the
   module-scoped ``_spy_patches`` fixture and reset per test by ``_spies``.
2. ``backend.core.database.get_session`` and
   ``backend.services.clip_client.get_clip_client`` are imported *inside* the
   method bodies, so those lookups really do happen at call time at those import
   sites and per-test patches there work (same topology as the repo's
   test_enrichment_pipeline_household_matching.py).

Log extras are read with ``getattr(record, key, None)`` across ALL matching
records: the repo conftest's logging config attaches extras as record attributes,
not as a custom ``__extra__`` attribute.
"""

from __future__ import annotations

import logging
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from PIL import Image

import backend.services.enrichment_pipeline as M
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    EnrichmentResult,
    LicensePlateResult,
    PoseResult,
)
from backend.services.household_matcher import HouseholdMatch

_PIPE_STATE: dict[str, EnrichmentPipeline] = {}

# Names a mutant body resolves out of the module dict. Patched at MODULE scope so
# they are already swapped when the plugin binds the mutant; reset per test.
_SPY_NAMES = (
    "record_enrichment_model_call",
    "record_enrichment_model_error",
    "observe_enrichment_model_duration",
    "extract_poses_batch",
    "get_household_matcher",
)


# extract_poses_batch is awaited by shipped code, so its stand-in must be awaitable.
_SPY_KINDS = {"extract_poses_batch": AsyncMock}


@pytest.fixture(scope="module", autouse=True)
def _spy_patches():
    with ExitStack() as stack:
        yield {
            name: stack.enter_context(
                patch(
                    f"backend.services.enrichment_pipeline.{name}",
                    _SPY_KINDS.get(name, MagicMock)(name=name),
                )
            )
            for name in _SPY_NAMES
        }


@pytest.fixture(autouse=True)
def _spies(_spy_patches):
    """Fresh call history for every spy, plus a duration-shaped default return."""
    for name, spy in _spy_patches.items():
        spy.reset_mock()
        spy.side_effect = None
        spy.return_value = MagicMock(name=f"{name}-return")
    return _spy_patches


@pytest.fixture
def _cap():
    """Module-logger capture for one test."""
    cap = _Cap()
    try:
        yield cap
    finally:
        cap.close()


def _pipe() -> EnrichmentPipeline:
    """One shared pipeline (construction touches settings/services)."""
    if not _PIPE_STATE:
        _PIPE_STATE["p"] = EnrichmentPipeline(model_manager=MagicMock())
    return _PIPE_STATE["p"]


def _image() -> Image.Image:
    return Image.new("RGB", (8, 8), color=(10, 20, 30))


def _bbox() -> BoundingBox:
    return BoundingBox(x1=1.0, y1=2.0, x2=6.0, y2=4.0)


class _Cap(logging.Handler):
    """Collects every record that passes through the module logger."""

    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self.records: list[logging.LogRecord] = []
        self._old_level = M.logger.level
        M.logger.addHandler(self)
        M.logger.setLevel(logging.DEBUG)

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def close(self) -> None:
        M.logger.removeHandler(self)
        M.logger.setLevel(self._old_level)


class _Records:
    """Every captured record whose ``record.msg`` equals ``msg`` (message template)."""

    def __init__(self, records: list[logging.LogRecord], msg: str) -> None:
        self.all = [r for r in records if r.msg == msg]

    @property
    def count(self) -> int:
        return len(self.all)

    def attr(self, key: str):
        """First value among matching records that actually carry ``key``."""
        vals = [getattr(r, key, None) for r in self.all if hasattr(r, key)]
        return vals[0] if vals else None

    def messages(self) -> list:
        return [r.getMessage() for r in self.all]

    def exc_infos(self) -> list:
        return [r.exc_info for r in self.all]


class _Embed:
    """Object exposing an ``embedding`` attribute (shipped ``hasattr`` branch)."""

    def __init__(self, embedding) -> None:
        self.embedding = embedding


class _ContainerOnly:
    """Membership-testable, non-dict, unindexable payload (shipped: skipped)."""

    def __init__(self, members) -> None:
        self._members = list(members)

    def __contains__(self, item) -> bool:
        return item in self._members

    def __getitem__(self, key):
        raise AssertionError(f"shipped must never index {type(self).__name__}")


class _BlankId:
    """Truthly id whose ``str()`` is empty (shipped det_id fallback probe)."""

    def __bool__(self) -> bool:
        return True

    def __str__(self) -> str:
        return ""

    def __hash__(self) -> int:
        return 7


def _person(det_id=None, bbox: BoundingBox | None = ...) -> DetectionInput:
    return DetectionInput(
        id=det_id,
        class_name="person",
        confidence=0.9,
        bbox=_bbox() if bbox is ... else bbox,
    )


def _det(det_id=42, bbox: BoundingBox | None = ...) -> DetectionInput:
    return DetectionInput(
        id=det_id,
        class_name="person",
        confidence=0.85,
        bbox=_bbox() if bbox is ... else bbox,
    )


def _session_cm(session=None) -> MagicMock:
    cm = MagicMock(name="session-cm")
    cm.__aenter__ = AsyncMock(
        return_value=session if session is not None else MagicMock(name="session")
    )
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _matcher(person_match=None, vehicle_match=None) -> MagicMock:
    matcher = MagicMock(name="household-matcher")
    matcher.match_person = AsyncMock(return_value=person_match)
    matcher.match_vehicle = AsyncMock(return_value=vehicle_match)
    return matcher


def _load_cm(*yielded) -> MagicMock:
    """Async context manager for ``async with model_manager.load(...) as (a, b)``."""
    cm = MagicMock(name="load-cm")
    cm.__aenter__ = AsyncMock(return_value=yielded[0] if len(yielded) == 1 else yielded)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _model_manager() -> MagicMock:
    mm = MagicMock(name="model-manager")
    mm.load.return_value = _load_cm(MagicMock(name="model"), MagicMock(name="processor"))
    return mm


def _pose(pose_class: str) -> PoseResult:
    return PoseResult(keypoints={}, pose_class=pose_class, pose_confidence=0.5)


# ===========================================================================
# _safe_clip_scene_classify
# ===========================================================================


@pytest.mark.asyncio
async def test_clip_scene_success_pinned(_spies) -> None:
    """Shipped success path: metric args, exact classify() args, returned tuple."""
    scores = {"driveway": 0.72, "street": 0.18}
    client = MagicMock()
    client.classify = AsyncMock(return_value=(scores, "driveway"))
    obs: list = []
    _spies["observe_enrichment_model_duration"].side_effect = lambda model, duration: obs.append(
        (model, duration)
    )
    cap = _Cap()
    pipe = _pipe()
    img = _image()
    try:
        with patch(
            "backend.services.clip_client.get_clip_client",
            return_value=client,
            autospec=True,
        ):
            got = await pipe._safe_clip_scene_classify(img)
    finally:
        cap.close()

    # shipped: the call metric is taken once, with the exact service name
    assert _spies["record_enrichment_model_call"].call_args_list == [(("clip-scene-classify",), {})]
    # shipped: the client is consulted once with (image, CLIP_SCENE_LABELS)
    client.classify.assert_awaited_once()
    assert client.classify.await_args.args == (img, M.CLIP_SCENE_LABELS)
    assert client.classify.await_args.kwargs == {}
    assert got == (scores, "driveway")
    # shipped: exactly one duration observation, same name, a real positive duration
    assert [m for m, _d in obs] == ["clip-scene-classify"]
    assert len(obs) == 1
    duration = obs[0][1]
    assert isinstance(duration, float)
    assert 0.0 <= duration < 60.0
    # shipped: success does not count an error; one debug line + three extras
    assert _spies["record_enrichment_model_error"].call_args_list == []
    recs = _Records(cap.records, "CLIP scene classification: top='driveway' (0.72)")
    assert recs.count == 1
    assert recs.attr("service") == "clip-scene-classify"
    assert isinstance(recs.attr("duration_ms"), int)
    assert 0 <= recs.attr("duration_ms") < 60000
    assert recs.attr("top_label") == "driveway"


@pytest.mark.asyncio
async def test_clip_scene_error_path_pinned(_spies) -> None:
    """Shipped failure path: duration observed, error counted, warning shape, None."""
    client = MagicMock()
    client.classify = AsyncMock(side_effect=RuntimeError("clip-blown"))
    obs: list = []
    _spies["observe_enrichment_model_duration"].side_effect = lambda model, duration: obs.append(
        (model, duration)
    )
    cap = _Cap()
    pipe = _pipe()
    try:
        with patch(
            "backend.services.clip_client.get_clip_client",
            return_value=client,
            autospec=True,
        ):
            got = await pipe._safe_clip_scene_classify(_image())
    finally:
        cap.close()

    assert got is None
    assert _spies["record_enrichment_model_call"].call_args_list == [(("clip-scene-classify",), {})]
    # shipped: the failure is still timed once, with the service name
    assert [m for m, _d in obs] == ["clip-scene-classify"]
    assert len(obs) == 1
    assert isinstance(obs[0][1], float)
    assert 0.0 <= obs[0][1] < 60.0
    assert _spies["record_enrichment_model_error"].call_args_list == [
        (("clip-scene-classify",), {})
    ]
    recs = _Records(cap.records, "CLIP scene classification failed: clip-blown")
    assert recs.count == 1
    assert recs.attr("service") == "clip-scene-classify"
    assert recs.attr("error_type") == "RuntimeError"
    assert isinstance(recs.attr("duration_ms"), int)
    assert 0 <= recs.attr("duration_ms") < 60000


# ===========================================================================
# _estimate_poses
# ===========================================================================


@pytest.mark.asyncio
async def test_estimate_poses_success_pinned(_spies) -> None:
    """Shipped crop/batching: model key, float bboxes, det-id fallback, result map."""
    extract = _spies["extract_poses_batch"]
    pose_a, pose_b = _pose("standing"), _pose("crouching")
    crops = [_image(), _image()]
    extract.side_effect = None
    extract.return_value = [pose_a, pose_b]
    pipe = _pipe()
    img = _image()
    with (
        patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock) as crop,
        patch.object(pipe, "model_manager", _model_manager()) as mm,
    ):
        crop.side_effect = list(crops)
        got = await pipe._estimate_poses([_person(7), _person(None)], img)

    assert list(got) == ["7", "1"]
    assert got["7"] is pose_a and got["1"] is pose_b
    assert crop.await_count == 2
    assert [c.args for c in crop.await_args_list] == [(img, _bbox()), (img, _bbox())]
    # shipped: ViTPose is loaded under exactly this registry key
    mm.load.assert_called_once_with("vitpose-small")
    extract.assert_awaited_once()
    assert extract.await_args.kwargs == {}
    _model, _processor, got_crops, got_bboxes = extract.await_args.args
    assert got_crops == crops
    # shipped: the int bbox tuple widened to floats, one entry per kept crop
    assert got_bboxes == [[1.0, 2.0, 6.0, 4.0], [1.0, 2.0, 6.0, 4.0]]
    assert all(isinstance(v, float) for row in got_bboxes for v in row)
    # shipped: the crop metric is taken inside the loaded context, name "pose"
    assert _spies["record_enrichment_model_call"].call_args_list == [(("pose",), {})]
    assert _spies["record_enrichment_model_error"].call_args_list == []


@pytest.mark.asyncio
async def test_estimate_poses_skips_bboxless_and_empty(_spies) -> None:
    """Shipped guards: no persons -> {}, bbox-less persons -> {}, no model load."""
    pipe = _pipe()
    assert await pipe._estimate_poses([], _image()) == {}

    mm = _model_manager()
    with (
        patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock) as crop,
        patch.object(pipe, "model_manager", mm),
    ):
        got = await pipe._estimate_poses([_person(1, bbox=None)], _image())
    assert got == {}
    crop.assert_not_awaited()
    _spies["extract_poses_batch"].assert_not_awaited()
    mm.load.assert_not_called()

    # a crop returning None also short-circuits before the model load
    mm2 = _model_manager()
    with (
        patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock, return_value=None),
        patch.object(pipe, "model_manager", mm2),
    ):
        got = await pipe._estimate_poses([_person(1)], _image())
    assert got == {}
    _spies["extract_poses_batch"].assert_not_awaited()
    mm2.load.assert_not_called()


@pytest.mark.asyncio
async def test_estimate_poses_model_error_reraised(_spies) -> None:
    """Shipped failure path: duration + error metric, sanitised error log, re-raise."""
    boom = RuntimeError("vitpose-blown")
    extract = _spies["extract_poses_batch"]
    extract.side_effect = boom
    obs: list = []
    _spies["observe_enrichment_model_duration"].side_effect = lambda model, duration: obs.append(
        (model, duration)
    )
    pipe = _pipe()
    cap = _Cap()
    try:
        with (
            patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock, return_value=_image()),
            patch.object(pipe, "model_manager", _model_manager()),
        ):
            with pytest.raises(RuntimeError) as excinfo:
                await pipe._estimate_poses([_person(3)], _image())
    finally:
        cap.close()

    assert excinfo.value is boom
    assert [m for m, _d in obs] == ["vitpose"]
    assert len(obs) == 1
    assert isinstance(obs[0][1], float)
    assert 0.0 <= obs[0][1] < 60.0
    assert _spies["record_enrichment_model_error"].call_args_list == [(("vitpose",), {})]
    msg = f"Pose estimation failed: {M.sanitize_error(boom)}"
    recs = _Records(cap.records, msg)
    assert recs.count == 1
    assert "vitpose-blown" in recs.messages()[0]
    # shipped: exc_info=True -> the traceback is attached to the record
    assert recs.exc_infos()[0] is not None
    assert recs.exc_infos()[0][1] is boom


# ===========================================================================
# _enrich_single_detection_unified
# ===========================================================================


@pytest.mark.asyncio
async def test_unified_person_success_pinned() -> None:
    """Shipped person path: det-id fallback, crop args, exact enrich_detection kwargs."""
    det = _det(42)
    crop = _image()
    unified = M.UnifiedEnrichmentResult()
    client = MagicMock()
    client.enrich_detection = AsyncMock(return_value=unified)
    pipe = _pipe()
    img = _image()
    with (
        patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock, return_value=crop) as crop_m,
        patch.object(pipe, "_pil_to_bytes", autospec=True, return_value=b"bytes") as pb,
        patch.object(pipe, "_get_enrichment_client", autospec=True, return_value=client),
        patch.object(pipe, "_get_action_frames", new_callable=AsyncMock, return_value=[img]) as gaf,
    ):
        got = await pipe._enrich_single_detection_unified(det, img, "person", "cam-1")

    assert got == ("42", unified)
    crop_m.assert_awaited_once_with(img, det.bbox)
    pb.assert_called_once_with(crop)
    # shipped default: action_recognition_enabled is True, so frames are gathered
    gaf.assert_awaited_once_with("cam-1", img)
    client.enrich_detection.assert_awaited_once()
    assert client.enrich_detection.await_args.args == ()
    kw = client.enrich_detection.await_args.kwargs
    # shipped: crop bytes, the type verbatim, float bbox tuple, a 1-frame fallback
    # contributes nothing, and options carries the face_visible default True
    assert kw["image"] == b"bytes"
    assert kw["detection_type"] == "person"
    assert kw["bbox"] == det.bbox.to_tuple()
    assert kw["bbox"] == (1.0, 2.0, 6.0, 4.0)
    assert kw["frames"] is None
    assert kw["options"] == {"face_visible": True}


@pytest.mark.asyncio
async def test_unified_vehicle_options_empty_pinned() -> None:
    """Shipped non-person path: no face_visible key, no frame gathering."""
    det = _det(7)
    client = MagicMock()
    client.enrich_detection = AsyncMock(return_value=M.UnifiedEnrichmentResult())
    pipe = _pipe()
    img = _image()
    with (
        patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock, return_value=_image()),
        patch.object(pipe, "_pil_to_bytes", autospec=True, return_value=b"vbytes"),
        patch.object(pipe, "_get_enrichment_client", autospec=True, return_value=client),
        patch.object(
            pipe, "_get_action_frames", new_callable=AsyncMock, return_value=[img, img]
        ) as gaf,
    ):
        got = await pipe._enrich_single_detection_unified(det, img, "vehicle", "cam-1")

    assert got[0] == "7"
    gaf.assert_not_awaited()
    kw = client.enrich_detection.await_args.kwargs
    assert kw["image"] == b"vbytes"
    assert kw["detection_type"] == "vehicle"
    assert kw["bbox"] == (1.0, 2.0, 6.0, 4.0)
    assert kw["frames"] is None
    assert kw["options"] == {}


@pytest.mark.asyncio
async def test_unified_missing_bbox_still_sends_zero_tuple() -> None:
    """Shipped quirk: a crop that succeeds despite bbox=None sends bbox=(0.,0.,0.,0.)."""
    det = _det(5, bbox=None)
    client = MagicMock()
    client.enrich_detection = AsyncMock(return_value=M.UnifiedEnrichmentResult())
    pipe = _pipe()
    with (
        patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock, return_value=_image()),
        patch.object(pipe, "_pil_to_bytes", autospec=True, return_value=b"b"),
        patch.object(pipe, "_get_enrichment_client", autospec=True, return_value=client),
    ):
        got = await pipe._enrich_single_detection_unified(det, _image(), "animal")

    assert got[0] == "5"
    kw = client.enrich_detection.await_args.kwargs
    assert kw["bbox"] == (0.0, 0.0, 0.0, 0.0)
    assert kw["options"] == {}


@pytest.mark.asyncio
async def test_unified_empty_crop_short_circuits() -> None:
    """Shipped short-circuit + det_id fallbacks: 42 -> "42", None -> "0", 0 -> "0"."""
    pipe = _pipe()
    for det_id, expected in ((42, "42"), (None, "0"), (0, "0")):
        client = MagicMock()
        client.enrich_detection = AsyncMock()
        with (
            patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock, return_value=None),
            patch.object(pipe, "_pil_to_bytes", autospec=True) as pb,
            patch.object(pipe, "_get_enrichment_client", autospec=True, return_value=client),
        ):
            got_id, got_result = await pipe._enrich_single_detection_unified(
                _det(det_id), _image(), "person", "cam-1"
            )
        assert got_id == expected
        assert isinstance(got_result, M.UnifiedEnrichmentResult)
        client.enrich_detection.assert_not_awaited()
        pb.assert_not_called()


@pytest.mark.asyncio
async def test_unified_action_frames_multi_pinned() -> None:
    """Shipped multi-frame path: frames gathered with (camera_id, image) and re-encoded."""
    frames = [_image(), _image(), _image()]
    client = MagicMock()
    client.enrich_detection = AsyncMock(return_value=M.UnifiedEnrichmentResult())
    pipe = _pipe()
    img = _image()
    pipe.action_recognition_enabled = True
    with (
        patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock, return_value=_image()),
        patch.object(
            pipe, "_pil_to_bytes", autospec=True, side_effect=[b"img", b"f0", b"f1", b"f2"]
        ),
        patch.object(pipe, "_get_enrichment_client", autospec=True, return_value=client),
        patch.object(
            pipe, "_get_action_frames", new_callable=AsyncMock, return_value=frames
        ) as gaf,
    ):
        got = await pipe._enrich_single_detection_unified(_det(9), img, "person", "cam-9")

    assert got[0] == "9"
    gaf.assert_awaited_once_with("cam-9", img)
    kw = client.enrich_detection.await_args.kwargs
    assert kw["image"] == b"img"
    assert kw["frames"] == [b"f0", b"f1", b"f2"]
    assert kw["options"] == {"face_visible": True}


@pytest.mark.asyncio
async def test_unified_action_frames_two_pinned() -> None:
    """Shipped gate boundary: exactly two buffered frames ARE sent (len > 1)."""
    frames = [_image(), _image()]
    client = MagicMock()
    client.enrich_detection = AsyncMock(return_value=M.UnifiedEnrichmentResult())
    pipe = _pipe()
    img = _image()
    pipe.action_recognition_enabled = True
    with (
        patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock, return_value=_image()),
        patch.object(pipe, "_pil_to_bytes", autospec=True, side_effect=[b"img", b"g0", b"g1"]),
        patch.object(pipe, "_get_enrichment_client", autospec=True, return_value=client),
        patch.object(
            pipe, "_get_action_frames", new_callable=AsyncMock, return_value=frames
        ) as gaf,
    ):
        await pipe._enrich_single_detection_unified(_det(9), img, "person", "cam-9")

    gaf.assert_awaited_once_with("cam-9", img)
    kw = client.enrich_detection.await_args.kwargs
    assert kw["frames"] == [b"g0", b"g1"]


@pytest.mark.asyncio
async def test_unified_action_frames_single_fallback_pinned() -> None:
    """Shipped gate `frames and len(frames) > 1`: a 1-frame fallback sends no frames."""
    client = MagicMock()
    client.enrich_detection = AsyncMock(return_value=M.UnifiedEnrichmentResult())
    pipe = _pipe()
    img = _image()
    pipe.action_recognition_enabled = True
    with (
        patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock, return_value=_image()),
        patch.object(pipe, "_pil_to_bytes", autospec=True, side_effect=[b"img", b"only"]),
        patch.object(pipe, "_get_enrichment_client", autospec=True, return_value=client),
        patch.object(pipe, "_get_action_frames", new_callable=AsyncMock, return_value=[img]) as gaf,
    ):
        await pipe._enrich_single_detection_unified(_det(9), img, "person", "cam-9")

    gaf.assert_awaited_once_with("cam-9", img)
    kw = client.enrich_detection.await_args.kwargs
    assert kw["frames"] is None
    assert kw["image"] == b"img"


@pytest.mark.asyncio
async def test_unified_action_gate_skips_nonperson() -> None:
    """Shipped `and` gate: no frame gathering for a vehicle even when enabled."""
    pipe = _pipe()
    client = MagicMock()
    client.enrich_detection = AsyncMock(return_value=M.UnifiedEnrichmentResult())
    pipe.action_recognition_enabled = True
    with (
        patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock, return_value=_image()),
        patch.object(pipe, "_pil_to_bytes", autospec=True, return_value=b"b"),
        patch.object(pipe, "_get_enrichment_client", autospec=True, return_value=client),
        patch.object(
            pipe, "_get_action_frames", new_callable=AsyncMock, return_value=[_image(), _image()]
        ) as gaf,
    ):
        await pipe._enrich_single_detection_unified(_det(1), _image(), "vehicle", "cam-1")
    gaf.assert_not_awaited()
    kw = client.enrich_detection.await_args.kwargs
    assert kw["frames"] is None
    assert kw["options"] == {}


@pytest.mark.asyncio
async def test_unified_action_gate_skips_when_disabled() -> None:
    """Shipped `and` gate: action recognition off -> no gathering, options still set."""
    pipe = _pipe()
    client = MagicMock()
    client.enrich_detection = AsyncMock(return_value=M.UnifiedEnrichmentResult())
    pipe.action_recognition_enabled = False
    try:
        with (
            patch.object(pipe, "_crop_to_bbox", new_callable=AsyncMock, return_value=_image()),
            patch.object(pipe, "_pil_to_bytes", autospec=True, return_value=b"b"),
            patch.object(pipe, "_get_enrichment_client", autospec=True, return_value=client),
            patch.object(
                pipe,
                "_get_action_frames",
                new_callable=AsyncMock,
                return_value=[_image(), _image()],
            ) as gaf,
        ):
            await pipe._enrich_single_detection_unified(_det(2), _image(), "person", "cam-1")
        gaf.assert_not_awaited()
        kw = client.enrich_detection.await_args.kwargs
        assert kw["frames"] is None
        assert kw["options"] == {"face_visible": True}
    finally:
        pipe.action_recognition_enabled = True


# ===========================================================================
# _run_household_matching
# ===========================================================================


@pytest.mark.asyncio
async def test_household_person_match_pinned(_spies, _cap) -> None:
    """Shipped person match: embedding handoff, int det-id key, log extras."""
    emb = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    match = HouseholdMatch(member_id=11, member_name="Ada", similarity=0.87, match_type="person")
    matcher = _matcher(person_match=match)
    _spies["get_household_matcher"].return_value = matcher
    session = MagicMock(name="session")
    result = EnrichmentResult()
    result.person_embeddings = {"3": _Embed(embedding=emb)}
    result.license_plates = []
    with patch(
        "backend.core.database.get_session", return_value=_session_cm(session), autospec=True
    ):
        await _pipe()._run_household_matching([_person(3)], result)

    # shipped: (embedding, session) handed to the matcher positionally
    matcher.match_person.assert_awaited_once()
    assert matcher.match_person.await_args.kwargs == {}
    args = matcher.match_person.await_args.args
    assert len(args) == 2
    assert args[0] is emb
    assert args[1] is session
    # shipped: the match is keyed by int(det_id)
    assert list(result.person_household_matches) == [3]
    assert result.person_household_matches[3] is match
    matcher.match_vehicle.assert_not_awaited()
    recs = _Records(_cap.records, "Person matched to household member")
    assert recs.count == 1
    assert recs.attr("detection_id") == "3"
    assert recs.attr("member_name") == "Ada"
    assert recs.attr("similarity") == 0.87


@pytest.mark.asyncio
async def test_household_person_dict_embedding_and_list_conversion(_spies) -> None:
    """Shipped branch order: dict payload wins over continue; list payloads convert to float32."""
    emb = np.array([0.5, 0.5], dtype=np.float32)
    matcher = _matcher()
    _spies["get_household_matcher"].return_value = matcher
    result = EnrichmentResult()
    result.person_embeddings = {"1": {"embedding": emb}}
    with patch("backend.core.database.get_session", return_value=_session_cm(), autospec=True):
        await _pipe()._run_household_matching([_person(1)], result)
    matcher.match_person.assert_awaited_once()
    assert matcher.match_person.await_args.args[0] is emb

    # a list payload is converted to a float32 ndarray before matching
    matcher2 = _matcher()
    _spies["get_household_matcher"].return_value = matcher2
    result2 = EnrichmentResult()
    result2.person_embeddings = {"1": {"embedding": [1, 2, 3]}}
    with patch("backend.core.database.get_session", return_value=_session_cm(), autospec=True):
        await _pipe()._run_household_matching([_person(1)], result2)
    matcher2.match_person.assert_awaited_once()
    got = matcher2.match_person.await_args.args[0]
    assert isinstance(got, np.ndarray)
    assert got.dtype == np.float32
    assert got.tolist() == [1.0, 2.0, 3.0]


@pytest.mark.asyncio
async def test_household_person_unconvertible_embedding_skipped(_spies, _cap) -> None:
    """Shipped skip path: an embedding that cannot become an ndarray never reaches the matcher."""
    matcher = _matcher()
    _spies["get_household_matcher"].return_value = matcher
    result = EnrichmentResult()
    # non-iterable payload: np.array(..., dtype=np.float32) raises TypeError
    result.person_embeddings = {"2": _Embed(embedding=object())}
    with patch("backend.core.database.get_session", return_value=_session_cm(), autospec=True):
        await _pipe()._run_household_matching([_person(2)], result)

    matcher.match_person.assert_not_awaited()
    assert result.person_household_matches == {}
    # shipped: the unconvertible-embedding warning names the skipped detection
    msgs = [r.getMessage() for r in _cap.records if "numpy array" in r.getMessage()]
    assert msgs == ["Could not convert embedding to numpy array for person 2"]


@pytest.mark.asyncio
async def test_household_non_dict_container_payload_skipped(_spies) -> None:
    """Shipped branch: a membership-testable non-dict payload is skipped, never indexed."""
    matcher = _matcher()
    _spies["get_household_matcher"].return_value = matcher
    result = EnrichmentResult()
    # `"embedding" in payload` is True, but the payload is neither an object with an
    # `embedding` attribute nor a dict -> shipped falls through to `continue`
    result.person_embeddings = {"4": _ContainerOnly(["embedding"])}
    with patch("backend.core.database.get_session", return_value=_session_cm(), autospec=True):
        await _pipe()._run_household_matching([_person(4)], result)
    matcher.match_person.assert_not_awaited()
    assert result.person_household_matches == {}


@pytest.mark.asyncio
async def test_household_det_id_lookup_key_pinned(_spies) -> None:
    """Shipped keying: the lookup key is str(id) or, when id is falsy, str(index)."""
    matcher = _matcher()
    _spies["get_household_matcher"].return_value = matcher
    result = EnrichmentResult()
    result.person_embeddings = {
        "0": _Embed(embedding=np.zeros(2, dtype=np.float32)),
        "9": _Embed(embedding=np.zeros(2, dtype=np.float32)),
        "1": _Embed(embedding=np.zeros(2, dtype=np.float32)),
    }
    with patch("backend.core.database.get_session", return_value=_session_cm(), autospec=True):
        await _pipe()._run_household_matching([_person(None), _person(9)], result)
    # ids None (index 0 -> key "0") and 9 (index 1 -> key "9") both match up
    assert matcher.match_person.await_count == 2

    # nothing in person_embeddings and no plates -> no matcher calls at all
    matcher2 = _matcher()
    _spies["get_household_matcher"].return_value = matcher2
    result2 = EnrichmentResult()
    with patch("backend.core.database.get_session", return_value=_session_cm(), autospec=True):
        await _pipe()._run_household_matching([_person(4)], result2)
    matcher2.match_person.assert_not_awaited()
    matcher2.match_vehicle.assert_not_awaited()
    assert result2.person_household_matches == {}
    assert result2.vehicle_household_matches == {}


@pytest.mark.asyncio
async def test_household_empty_string_det_id_keys_by_index(_spies) -> None:
    """Shipped `int(det_id) if det_id else i`: an empty-string det_id keys by index."""
    match = HouseholdMatch(member_id=21, member_name="Bo", similarity=0.71)
    matcher = _matcher(person_match=match)
    _spies["get_household_matcher"].return_value = matcher
    result = EnrichmentResult()
    # truthy id whose str() is "" -> det_id == "" -> falsy -> key falls back to i
    result.person_embeddings = {"": _Embed(embedding=np.zeros(2, dtype=np.float32))}
    with patch("backend.core.database.get_session", return_value=_session_cm(), autospec=True):
        await _pipe()._run_household_matching([_person(_BlankId())], result)
    matcher.match_person.assert_awaited_once()
    assert list(result.person_household_matches) == [0]
    assert result.person_household_matches[0] is match


@pytest.mark.asyncio
async def test_household_vehicle_match_pinned(_spies, _cap) -> None:
    """Shipped vehicle match: plate kwargs, det-id key, log extras."""
    match = HouseholdMatch(vehicle_id=5, vehicle_description="Silver Tesla", match_type="plate")
    matcher = _matcher(vehicle_match=match)
    _spies["get_household_matcher"].return_value = matcher
    plate = LicensePlateResult(
        bbox=_bbox(), text="ABC123", confidence=0.9, ocr_confidence=0.8, source_detection_id=7
    )
    result = EnrichmentResult()
    result.license_plates = [plate]
    session = MagicMock(name="session")
    cm = _session_cm(session)
    with patch("backend.core.database.get_session", return_value=cm, autospec=True):
        await _pipe()._run_household_matching([_det(7)], result)

    matcher.match_vehicle.assert_awaited_once()
    assert matcher.match_vehicle.await_args.args == ()
    kw = matcher.match_vehicle.await_args.kwargs
    assert kw["license_plate"] == "ABC123"
    assert kw["vehicle_embedding"] is None
    assert kw["vehicle_type"] == "car"
    assert kw["color"] is None
    assert kw["session"] is session
    assert list(result.vehicle_household_matches) == [7]
    assert result.vehicle_household_matches[7] is match
    matcher.match_person.assert_not_awaited()
    recs = _Records(_cap.records, "Vehicle matched by license plate")
    assert recs.count == 1
    assert recs.attr("detection_id") == 7
    assert recs.attr("plate") == "ABC123"
    assert recs.attr("vehicle_description") == "Silver Tesla"


@pytest.mark.asyncio
async def test_household_vehicle_blank_plate_skipped(_spies) -> None:
    """Shipped gate: plates without text are never offered to the matcher."""
    matcher = _matcher()
    _spies["get_household_matcher"].return_value = matcher
    result = EnrichmentResult()
    result.license_plates = [LicensePlateResult(bbox=_bbox(), text="", source_detection_id=7)]
    with patch("backend.core.database.get_session", return_value=_session_cm(), autospec=True):
        await _pipe()._run_household_matching([_det(7)], result)
    matcher.match_vehicle.assert_not_awaited()
    assert result.vehicle_household_matches == {}
