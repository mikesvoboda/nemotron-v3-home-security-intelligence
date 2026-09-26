"""Chunk-16 kill battery: ``EnrichmentPipeline._run_reid`` /
``_estimate_poses_via_service`` / ``_assess_image_quality`` mutation survivors.

Every assertion was PROBED against the pristine shipped source — shipped
behaviour is pinned, never bent.

Harness notes
-------------
Module-level helpers are patched at the IMPORT SITE
(``backend.services.enrichment_pipeline.<name>``) from a *module-scoped* autouse
fixture: the adjudication plugin snapshots the live module dict during its
function-scoped autouse fixture setup, so a function-scoped patch fixture would
run too late and be invisible inside an exec'd mutant body.  Collaborators
reached through ``self`` (services, crop) are patched as attributes on the
pipeline object, which is exactly what the mutant body sees.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import httpx
import pytest
from PIL import Image

import backend.services.enrichment_pipeline as M
from backend.core.exceptions import EnrichmentUnavailableError
from backend.services.enrichment_client import EnrichmentClient, KeypointData, PoseAnalysisResult
from backend.services.image_quality_loader import ImageQualityResult
from backend.services.reid_service import EntityEmbedding, EntityMatch, ReIdentificationService
from backend.services.vision_extractor import BatchExtractionResult, PersonAttributes

pytestmark = pytest.mark.asyncio

MOD_LOGGER = "backend.services.enrichment_pipeline"
EMBEDDING = [0.25, 0.5, 0.75]
BBOX_INTS = (100, 100, 200, 300)
BBOX_TUPLE = (100.0, 100.0, 200.0, 300.0)


# ---------------------------------------------------------------------------
# patch surface
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True, scope="module")
def g():
    """Patch every module-level name the three methods consume (import site)."""
    with (
        patch.object(M, "record_enrichment_model_call", autospec=True) as calls,
        patch.object(M, "record_enrichment_model_error", autospec=True) as errs,
        patch.object(M, "observe_enrichment_model_duration", autospec=True) as durs,
        patch.object(M, "assess_image_quality", autospec=True) as assess,
        patch.object(M, "get_enrichment_client", autospec=True) as client_getter,
        patch.object(M, "get_reid_service", autospec=True) as reid_getter,
        patch.object(M, "get_vision_extractor", autospec=True) as vision_getter,
        patch.object(M, "get_scene_change_detector", autospec=True) as scene_getter,
        patch.object(M, "get_scene_ocr_service", autospec=True) as ocr_getter,
        patch.object(M, "get_household_matcher", autospec=True) as hh_getter,
        patch.object(M, "get_model_manager", autospec=True) as mgr_getter,
    ):
        yield {
            "calls": calls,
            "errs": errs,
            "durs": durs,
            "assess": assess,
            "client_getter": client_getter,
        }


@pytest.fixture(autouse=True)
def _fresh(g):
    """Zero the recorded calls of the shared module-level mocks between tests."""
    for key in ("calls", "errs", "durs"):
        g[key].mock.reset_mock()
    g["assess"].mock.reset_mock()
    yield


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------
def _img(w: int = 640, h: int = 480) -> Image.Image:
    return Image.new("RGB", (w, h), color=(10, 20, 30))


def _bbox(x1=100.0, y1=100.0, x2=200.0, y2=300.0) -> M.BoundingBox:
    return M.BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)


def _det(
    class_name: str = "person",
    *,
    bbox: M.BoundingBox | None = ...,  # type: ignore[assignment]
    det_id: int | None = 7,
    video_width: int | None = None,
    video_height: int | None = None,
) -> M.DetectionInput:
    return M.DetectionInput(
        class_name=class_name,
        confidence=0.9,
        bbox=_bbox() if bbox is ... else bbox,
        id=det_id,
        video_width=video_width,
        video_height=video_height,
    )


def _mm(value=None, exc: Exception | None = None) -> MagicMock:
    """model_manager mock whose ``load(name)`` yields ``value`` (or raises exc)."""

    class _Ctx:
        async def __aenter__(self):
            if exc is not None:
                raise exc
            return value

        async def __aexit__(self, *_a):
            return None

    mm = MagicMock(name="model_manager")
    mm.load = MagicMock(name="load", side_effect=lambda *_a, **_k: _Ctx())
    return mm


def _mm_exc(exc: Exception) -> MagicMock:
    mm = MagicMock(name="model_manager")
    mm.load = MagicMock(name="load", side_effect=exc)
    return mm


def _quality(
    *,
    score: float = 12.0,
    brisque: float = 88.0,
    low: bool = True,
    issues: list[str] | None = None,
) -> ImageQualityResult:
    return ImageQualityResult(
        quality_score=score,
        brisque_score=brisque,
        is_blurry=True,
        is_noisy=False,
        is_low_quality=low,
        quality_issues=["blur"] if issues is None else issues,
    )


def _reid_service() -> AsyncMock:
    svc = create_autospec(ReIdentificationService, instance=True)
    svc.generate_embedding.return_value = list(EMBEDDING)
    svc.find_matching_entities.return_value = []
    svc.store_embedding.return_value = None
    return svc


def _reid_pipeline(svc=None, redis=None, mm=None):
    svc = svc if svc is not None else _reid_service()
    redis = redis if redis is not None else MagicMock(name="redis")
    pipeline = M.EnrichmentPipeline(
        model_manager=mm if mm is not None else _mm(),
        redis_client=redis,
        reid_service=svc,
        reid_enabled=True,
    )
    return pipeline, svc, redis


def _remote_pose(posture: str = "standing", confs: tuple[float, ...] = (0.4, 0.8)):
    return PoseAnalysisResult(
        keypoints=[
            KeypointData(name=f"kp{i}", x=0.1 * i, y=0.2 * i, confidence=c)
            for i, c in enumerate(confs)
        ],
        posture=posture,
        alerts=[],
        inference_time_ms=3.0,
    )


def _pose_pipeline(crop=None, client=None):
    """Pipeline with the REAL ``_crop_to_bbox`` unless overridden by ``crop``."""
    client = client if client is not None else create_autospec(EnrichmentClient, instance=True)
    pipeline = M.EnrichmentPipeline(
        model_manager=_mm(),
        pose_estimation_enabled=True,
        enrichment_client=client,
    )
    crop = _img(64, 100) if crop is None else crop
    pipeline._crop_to_bbox = AsyncMock(name="_crop_to_bbox", return_value=crop)
    return pipeline, client, crop


def _quality_pipeline(mm=None, model_data=None):
    return M.EnrichmentPipeline(
        model_manager=mm if mm is not None else _mm(model_data or {"brisque_fn": "fn"}),
        image_quality_enabled=True,
    )


def _client_raising(exc: Exception) -> AsyncMock:
    client = create_autospec(EnrichmentClient, instance=True)
    client.analyze_pose.side_effect = exc
    return client


_STD_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "taskName",
    "thread",
    "threadName",
}


def _extras(record) -> set[str]:
    """Names the caller passed via ``extra={...}`` (whatever they are called)."""
    return {k for k in record.__dict__ if k not in _STD_RECORD_ATTRS}


def _records(caplog, needle: str, *, level: str | None = None):
    return [
        r
        for r in caplog.records
        if r.name == MOD_LOGGER
        and needle in r.getMessage()
        and (level is None or r.levelname == level)
    ]


def _entity(svc) -> EntityEmbedding:
    store = svc.store_embedding.await_args
    assert store is not None, "store_embedding never awaited"
    return store.args[1]


# ===========================================================================
# _run_reid — happy path, entity typing, stored payload
# ===========================================================================
async def test_reid_vehicle_detection_full_contract(g, caplog):
    """Vehicle detection: embedding args, cache, match routing, stored entity.

    Pins shipped lines 5795-5841 of _run_reid (generate_embedding call shape,
    clip_embeddings cache, find_matching_entities kwargs, match routing and the
    EntityEmbedding payload).
    """
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    pipeline, svc, redis = _reid_pipeline()
    match = [EntityMatch(entity=MagicMock(), similarity=0.91, time_gap_seconds=12.0)]
    svc.find_matching_entities.return_value = match
    result = M.EnrichmentResult()
    image = _img()

    await pipeline._run_reid([_det("car", det_id=7)], image, "front_door", result)

    gen = svc.generate_embedding.await_args
    assert gen is not None
    assert gen.args == (image,)
    assert gen.kwargs == {"bbox": BBOX_INTS}
    assert result.clip_embeddings == {"7": list(EMBEDDING)}

    fme = svc.find_matching_entities.await_args
    assert fme is not None
    assert fme.args == (redis, list(EMBEDDING))
    assert fme.kwargs == {"entity_type": "vehicle", "exclude_detection_id": "7"}
    assert result.vehicle_reid_matches == {"7": match}
    assert result.person_reid_matches == {}

    store = svc.store_embedding.await_args
    assert store is not None
    assert svc.store_embedding.await_count == 1
    assert store.args[0] is redis


async def test_reid_entity_type_is_forwarded_verbatim():
    """entity_type reaches find_matching_entities and EntityEmbedding verbatim."""
    pipeline, svc, _redis = _reid_pipeline()
    result = M.EnrichmentResult()

    await pipeline._run_reid([_det("person", det_id=7)], _img(), "cam", result)

    assert svc.find_matching_entities.await_args.kwargs["entity_type"] == "person"
    assert _entity(svc).entity_type == "person"


async def test_reid_clip_embedding_cached():
    """result.clip_embeddings[det_id] holds the generated embedding."""
    pipeline, svc, _redis = _reid_pipeline()
    result = M.EnrichmentResult()

    await pipeline._run_reid([_det("person", det_id=7)], _img(), "cam", result)

    assert result.clip_embeddings == {"7": list(EMBEDDING)}


async def test_reid_embedding_receives_frame_and_bbox():
    """generate_embedding is awaited as (image, bbox=<scaled int tuple>)."""
    pipeline, svc, _redis = _reid_pipeline()
    image = _img()

    await pipeline._run_reid([_det("person", det_id=7)], image, "cam", M.EnrichmentResult())

    gen = svc.generate_embedding.await_args
    assert gen is not None
    assert gen.args == (image,)
    assert gen.kwargs == {"bbox": BBOX_INTS}


async def test_reid_bbox_none_when_bbox_absent():
    """A detection without a bbox is embedded with bbox=None (not '')."""
    pipeline, svc, _redis = _reid_pipeline()

    await pipeline._run_reid([_det("person", bbox=None)], _img(), "cam", M.EnrichmentResult())

    assert svc.generate_embedding.await_args.kwargs == {"bbox": None}


async def test_reid_bbox_scaled_to_resized_frame():
    """Bbox is scaled when the frame size differs from the source video size."""
    pipeline, svc, _redis = _reid_pipeline()
    det = _det("person", det_id=7, video_width=1280, video_height=960)

    await pipeline._run_reid([det], _img(640, 480), "cam", M.EnrichmentResult())

    assert svc.generate_embedding.await_args.kwargs == {"bbox": (50, 50, 100, 150)}


async def test_reid_bbox_unscaled_when_video_dims_absent():
    """One/none of video_width/video_height -> shipped keeps the raw int tuple."""
    pipeline, svc, _redis = _reid_pipeline()
    det = _det("person", det_id=7, video_width=1280)

    await pipeline._run_reid([det], _img(640, 480), "cam", M.EnrichmentResult())

    assert svc.generate_embedding.await_args.kwargs == {"bbox": BBOX_INTS}


async def test_reid_entity_embedding_payload():
    """EntityEmbedding fields are exactly what shipped stores."""
    pipeline, svc, redis = _reid_pipeline()

    await pipeline._run_reid([_det("car", det_id=7)], _img(), "front_door", M.EnrichmentResult())

    store = svc.store_embedding.await_args
    assert store is not None
    assert store.args[0] is redis
    assert svc.store_embedding.await_count == 1
    ent = store.args[1]
    assert ent.embedding == list(EMBEDDING)
    assert ent.detection_id == "7"


async def test_reid_camera_id_falls_back_to_lowercase_unknown():
    """camera_id=None stores the shipped lowercase sentinel 'unknown'."""
    pipeline, svc, _redis = _reid_pipeline()

    await pipeline._run_reid([_det("person")], _img(), None, M.EnrichmentResult())

    assert _entity(svc).camera_id == "unknown"


async def test_reid_camera_id_passes_through_when_present():
    """A caller-supplied camera_id is stored unchanged (or-branch live)."""
    pipeline, svc, _redis = _reid_pipeline()

    await pipeline._run_reid([_det("person")], _img(), "back_yard", M.EnrichmentResult())

    assert _entity(svc).camera_id == "back_yard"


async def test_reid_timestamp_is_aware_utc():
    """timestamp is a tz-aware UTC datetime, not None and not naive."""
    pipeline, svc, _redis = _reid_pipeline()

    await pipeline._run_reid([_det("person")], _img(), "cam", M.EnrichmentResult())

    ts = _entity(svc).timestamp
    assert isinstance(ts, datetime)
    assert ts.tzinfo is not None
    assert ts.utcoffset().total_seconds() == 0.0
    assert ts <= datetime.now(UTC)


async def test_reid_attributes_default_to_empty_dict():
    """No vision extraction -> attributes == {} (never None)."""
    pipeline, svc, _redis = _reid_pipeline()

    await pipeline._run_reid([_det("person")], _img(), "cam", M.EnrichmentResult())

    assert _entity(svc).attributes == {}


async def test_reid_person_attributes_extracted():
    """Vision-extraction person attributes are copied into the stored entity."""
    pipeline, svc, _redis = _reid_pipeline()
    result = M.EnrichmentResult()
    result.vision_extraction = BatchExtractionResult(
        person_attributes={
            "7": PersonAttributes(
                clothing="black jacket",
                carrying="backpack",
                is_service_worker=False,
                action="walking",
                caption="cap",
            )
        },
        vehicle_attributes={},
    )

    await pipeline._run_reid([_det("person", det_id=7)], _img(), "cam", result)

    assert _entity(svc).attributes == {"clothing": "black jacket", "carrying": "backpack"}


async def test_reid_unexpected_error_log_payload(caplog):
    """Unexpected failure -> ERROR with sanitized message, extras and traceback."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    boom = RuntimeError("boom-secret")
    svc = _reid_service()
    svc.generate_embedding.side_effect = boom
    pipeline, _svc, _redis = _reid_pipeline(svc=svc)

    await pipeline._run_reid([_det("car", det_id=7)], _img(), "cam", M.EnrichmentResult())

    recs = _records(caplog, "Re-id failed")
    assert len(recs) == 1
    rec = recs[0]
    assert rec.levelname == "ERROR"
    assert rec.getMessage() == "Re-id failed for detection 7: boom-secret"
    assert rec.exc_info is not None
    assert rec.exc_info[1] is boom
    assert _extras(rec) >= {"detection_id", "error_type", "entity_type"}
    assert rec.detection_id == "7"
    assert rec.error_type == "RuntimeError"
    assert rec.entity_type == "vehicle"


async def test_reid_transient_error_log_payload(caplog):
    """Transient (httpx) failure -> WARNING carrying the same extras."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    svc = _reid_service()
    svc.generate_embedding.side_effect = httpx.ConnectError("no route")
    pipeline, _svc, _redis = _reid_pipeline(svc=svc)

    await pipeline._run_reid([_det("person", det_id=7)], _img(), "cam", M.EnrichmentResult())

    recs = _records(caplog, "Re-id failed")
    assert len(recs) == 1
    assert recs[0].levelname == "WARNING"
    assert _extras(recs[0]) >= {"detection_id", "error_type", "entity_type"}
    assert recs[0].error_type == "ConnectError"
    assert recs[0].detection_id == "7"
    assert recs[0].entity_type == "person"


async def test_reid_parse_error_log_payload(caplog):
    """ValueError path -> ERROR with exc_info bound to that exception."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    boom = ValueError("bad-payload")
    svc = _reid_service()
    svc.generate_embedding.side_effect = boom
    pipeline, _svc, _redis = _reid_pipeline(svc=svc)

    await pipeline._run_reid([_det("person", det_id=7)], _img(), "cam", M.EnrichmentResult())

    recs = _records(caplog, "Re-id failed")
    assert len(recs) == 1
    assert recs[0].exc_info is not None
    assert recs[0].exc_info[1] is boom
    assert recs[0].error_type == "ValueError"


# ===========================================================================
# _estimate_poses_via_service
# ===========================================================================
async def test_pose_empty_persons_returns_empty_dict(g):
    """No persons -> shipped returns the empty dict (never None, no metrics)."""
    pipeline, client, _crop = _pose_pipeline()

    out = await pipeline._estimate_poses_via_service([], _img())

    assert out == {}
    client.analyze_pose.assert_not_awaited()
    assert g["calls"].call_args_list == []


async def test_pose_crop_failure_skips_person(g):
    """A None crop is skipped; the loop continues and no remote call happens."""
    pipeline, client, _crop = _pose_pipeline()
    pipeline._crop_to_bbox = AsyncMock(return_value=None)

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=3)], _img())

    assert out == {}
    client.analyze_pose.assert_not_awaited()
    assert pipeline._crop_to_bbox.await_count == 1


async def test_pose_getter_returns_pipeline_client(g):
    """_get_enrichment_client returns the injected client and it is used."""
    pipeline, client, _crop = _pose_pipeline()
    client.analyze_pose.return_value = _remote_pose()

    assert pipeline._get_enrichment_client() is client

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=7)], _img())
    assert list(out) == ["7"]


async def test_pose_getter_uses_module_factory(g):
    """Without an injected client the module-level getter supplies one."""
    fresh = create_autospec(EnrichmentClient, instance=True)
    fresh.analyze_pose.return_value = _remote_pose()
    g["client_getter"].return_value = fresh
    pipeline = M.EnrichmentPipeline(model_manager=_mm(), enrichment_client=None)
    pipeline._crop_to_bbox = AsyncMock(return_value=_img(64, 100))

    assert pipeline._get_enrichment_client() is fresh


async def test_pose_model_call_and_remote_arity(g):
    """One call metric recorded; remote call has 2 positionals (crop, bbox)."""
    pipeline, client, crop = _pose_pipeline()
    client.analyze_pose.return_value = _remote_pose()

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=7)], _img())

    assert [c.args[0] for c in g["calls"].call_args_list] == ["pose-via-service"]
    call = client.analyze_pose.await_args
    assert call is not None
    assert len(call.args) == 2 and not call.kwargs
    assert call.args[0] is crop
    assert call.args[1] == BBOX_TUPLE
    assert len(out) == 1


async def test_pose_crop_receives_frame_and_bbox():
    """_crop_to_bbox is awaited with (image, person.bbox)."""
    image = _img()
    pipeline, client, _crop = _pose_pipeline()
    person = _det("person", det_id=7)

    await pipeline._estimate_poses_via_service([person], image)

    call = pipeline._crop_to_bbox.await_args
    assert call is not None
    assert call.args == (image, person.bbox)
    assert client.analyze_pose.await_count == 1


async def test_pose_result_keyed_by_detection_id():
    """Result key is str(person.id) when the detection has an id."""
    pipeline, client, _crop = _pose_pipeline()
    client.analyze_pose.return_value = _remote_pose()

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=7)], _img())

    assert list(out) == ["7"]


async def test_pose_result_keyed_by_index_when_id_missing():
    """Result key falls back to str(index) when person.id is falsy."""
    pipeline, client, _crop = _pose_pipeline()
    client.analyze_pose.return_value = _remote_pose()

    out = await pipeline._estimate_poses_via_service(
        [_det("person", det_id=None), _det("person", det_id=11), _det("person", det_id=None)],
        _img(),
    )

    assert list(out) == ["0", "11", "2"]


async def test_pose_result_fields_converted():
    """Remote PoseAnalysisResult -> local PoseResult conversion is pinned."""
    pipeline, client, _crop = _pose_pipeline()
    client.analyze_pose.return_value = _remote_pose(posture="crouching", confs=(0.4, 0.8))

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=7)], _img())

    res = out["7"]
    assert res.pose_class == "crouching"
    assert res.pose_confidence == pytest.approx(0.6)
    assert sorted(res.keypoints) == ["kp0", "kp1"]
    assert res.keypoints["kp1"].name == "kp1"
    assert res.bbox == list(BBOX_TUPLE)


async def test_pose_missing_bbox_passes_none_bbox(g):
    """person.bbox=None -> shipped sends bbox=None and keeps going.

    Pins the False-branch of ``person.bbox.to_tuple() if person.bbox else None``
    (shipped line 4918) and the ``list(bbox_tuple) if bbox_tuple else None``
    guard at line 4950 — a person without a box is still sent to the service
    with a None bbox instead of crashing the attribute access.
    """
    pipeline, client, crop = _pose_pipeline()
    client.analyze_pose.return_value = None

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=7, bbox=None)], _img())

    assert out == {}
    call = client.analyze_pose.await_args
    assert call is not None
    assert call.args == (crop, None)


async def test_pose_duration_observed_as_elapsed(g):
    """Duration is observed for the live model name as a real elapsed seconds.

    Pins shipped line 4924: ``observe_enrichment_model_duration("pose-via-service",
    duration)`` where ``duration = perf_counter() - start_time`` — a non-negative
    float far below any plausible wall time for one HTTP call.
    """
    pipeline, client, _crop = _pose_pipeline()
    client.analyze_pose.return_value = _remote_pose()

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=7)], _img())

    assert out
    call = g["durs"].call_args
    assert call is not None
    assert call.args[0] == "pose-via-service"
    assert isinstance(call.args[1], float)
    assert 0.0 <= call.args[1] < 5.0


async def test_pose_unavailable_error_path(g, caplog):
    """EnrichmentUnavailableError -> duration + error metric + warning, no result."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    client = _client_raising(EnrichmentUnavailableError("down"))
    pipeline, _c, _crop = _pose_pipeline(client=client)

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=7)], _img())

    assert out == {}
    dur = g["durs"].call_args
    assert dur is not None
    assert dur.args[0] == "pose-via-service"
    assert isinstance(dur.args[1], float) and 0.0 <= dur.args[1] < 5.0
    assert [c.args[0] for c in g["errs"].call_args_list] == ["pose-via-service"]
    recs = _records(caplog, "pose estimation", level="WARNING")
    assert len(recs) == 1


async def test_pose_unexpected_error_path(g, caplog):
    """A generic exception is logged with traceback and swallowed."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    client = _client_raising(RuntimeError("kaboom"))
    pipeline, _c, _crop = _pose_pipeline(client=client)

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=7)], _img())

    assert out == {}
    assert [c.args[0] for c in g["errs"].call_args_list] == ["pose-via-service"]
    recs = _records(caplog, "unexpected error")
    assert len(recs) == 1
    assert recs[0].exc_info is not None


async def test_pose_parse_error_log_payload(g, caplog):
    """(ValueError, KeyError, TypeError) handler: duration, metric, message, extras.

    Pins shipped lines 5001-5014 in full, including the elapsed-time observation
    and the ``record_enrichment_model_error("pose-via-service")`` counter.
    """
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    boom = KeyError("nope")
    client = _client_raising(boom)
    pipeline, _c, _crop = _pose_pipeline(client=client)

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=7)], _img())

    assert out == {}
    dur = g["durs"].call_args
    assert dur is not None
    assert dur.args[0] == "pose-via-service"
    assert isinstance(dur.args[1], float)
    assert 0.0 <= dur.args[1] < 5.0
    assert [c.args[0] for c in g["errs"].call_args_list] == ["pose-via-service"]
    recs = _records(caplog, "parse error")
    assert len(recs) == 1
    rec = recs[0]
    assert rec.getMessage() == "Pose estimation parse error for 7"
    assert rec.levelname == "ERROR"
    assert rec.exc_info is not None
    assert rec.exc_info[1] is boom
    assert _extras(rec) >= {"service", "error_type", "detection_id"}
    assert rec.service == "pose-via-service"
    assert rec.error_type == "KeyError"
    assert rec.detection_id == "7"


async def test_pose_client_error_log_payload(g, caplog):
    """HTTP 4xx handler: message plus service/detection_id/status_code extras."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)

    class _Resp:
        status_code = 422

    client = _client_raising(httpx.HTTPStatusError("bad", request=MagicMock(), response=_Resp()))
    pipeline, _c, _crop = _pose_pipeline(client=client)

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=7)], _img())

    assert out == {}
    dur = g["durs"].call_args
    assert dur is not None
    assert dur.args[0] == "pose-via-service"
    assert isinstance(dur.args[1], float)
    assert 0.0 <= dur.args[1] < 5.0
    assert [c.args[0] for c in g["errs"].call_args_list] == ["pose-via-service"]
    recs = _records(caplog, "client error")
    assert len(recs) == 1
    rec = recs[0]
    assert rec.getMessage() == "Pose estimation client error for 7 (HTTP 422)"
    assert rec.service == "pose-via-service"
    assert rec.detection_id == "7"
    assert rec.status_code == 422


async def test_pose_server_error_log_payload(g, caplog):
    """HTTP 5xx handler: warning with the same extras."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)

    class _Resp:
        status_code = 503

    client = _client_raising(httpx.HTTPStatusError("boom", request=MagicMock(), response=_Resp()))
    pipeline, _c, _crop = _pose_pipeline(client=client)

    out = await pipeline._estimate_poses_via_service([_det("person", det_id=7)], _img())

    assert out == {}
    dur = g["durs"].call_args
    assert dur is not None
    assert dur.args[0] == "pose-via-service"
    assert isinstance(dur.args[1], float)
    assert 0.0 <= dur.args[1] < 5.0
    assert [c.args[0] for c in g["errs"].call_args_list] == ["pose-via-service"]
    recs = _records(caplog, "server error")
    assert len(recs) == 1
    assert recs[0].levelname == "WARNING"
    assert recs[0].service == "pose-via-service"
    assert recs[0].status_code == 503


# ===========================================================================
# _assess_image_quality
# ===========================================================================
async def test_quality_happy_path_metrics_and_pass_through(g):
    """Two call metrics in order, one duration, args passed through verbatim."""
    g["assess"].return_value = _quality(low=False)
    pipeline = _quality_pipeline()
    image = _img()

    out = await pipeline._assess_image_quality(image, camera_id="front_door")

    assert out.is_low_quality is False
    assert [c.args[0] for c in g["calls"].call_args_list] == ["brisque", "brisque-quality"]
    dur = g["durs"].call_args
    assert dur is not None
    assert dur.args[0] == "brisque-quality"
    assert isinstance(dur.args[1], float) and dur.args[1] >= 0.0
    call = g["assess"].await_args
    assert call is not None
    assert call.args[0] == {"brisque_fn": "fn"}
    assert call.args[1] is image


async def test_quality_low_quality_debug_message(g, caplog):
    """Low-quality debug line carries camera suffix, score and issues."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    g["assess"].return_value = _quality(score=12.0, issues=["blur"])
    pipeline = _quality_pipeline()

    out = await pipeline._assess_image_quality(_img(), camera_id="cam1")

    assert out.is_low_quality is True
    recs = _records(caplog, "Low quality image")
    assert len(recs) == 1
    assert recs[0].levelname == "DEBUG"
    assert (
        recs[0].getMessage()
        == "Low quality image detected (camera: cam1): score=12, issues=['blur']"
    )


async def test_quality_low_quality_without_camera_id(g, caplog):
    """camera_id=None -> empty suffix (not None, not a placeholder)."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    g["assess"].return_value = _quality(score=12.0, issues=["blur"])
    pipeline = _quality_pipeline()

    await pipeline._assess_image_quality(_img())

    recs = _records(caplog, "Low quality image")
    assert len(recs) == 1
    assert recs[0].getMessage() == "Low quality image detected: score=12, issues=['blur']"


async def test_quality_key_error_maps_to_runtime(g, caplog):
    """KeyError from the model manager -> warning + RuntimeError from None."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    pipeline = _quality_pipeline(mm=_mm_exc(KeyError("brisque-quality")))

    with pytest.raises(RuntimeError) as excinfo:
        await pipeline._assess_image_quality(_img(), camera_id="cam1")

    assert str(excinfo.value) == "brisque-quality model not configured"
    assert excinfo.value.__cause__ is not None
    recs = _records(caplog, "MODEL_ZOO", level="WARNING")
    assert len(recs) == 1
    assert recs[0].getMessage() == "brisque-quality model not available in MODEL_ZOO"
    assert [c.args[0] for c in g["errs"].call_args_list] == ["brisque-quality"]


async def test_quality_runtime_disabled_is_debug_only(g, caplog):
    """A 'disabled' RuntimeError is expected: debug log, no error metric, re-raise."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    pipeline = _quality_pipeline(mm=_mm_exc(RuntimeError("BRISQUE is disabled in this build")))

    with pytest.raises(RuntimeError) as excinfo:
        await pipeline._assess_image_quality(_img(), camera_id="cam1")

    assert "disabled" in str(excinfo.value).lower()
    assert g["errs"].call_args_list == []
    recs = _records(caplog, "skipped", level="DEBUG")
    assert len(recs) == 1


async def test_quality_runtime_other_error_records_metric(g, caplog):
    """A non-'disabled' RuntimeError records an error and logs at ERROR."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    pipeline = _quality_pipeline(mm=_mm_exc(RuntimeError("gpu exploded")))

    with pytest.raises(RuntimeError):
        await pipeline._assess_image_quality(_img(), camera_id="cam1")

    assert [c.args[0] for c in g["errs"].call_args_list] == ["brisque-quality"]
    recs = _records(caplog, "runtime", level="ERROR")
    assert len(recs) == 1


async def test_quality_generic_error_records_metric(g, caplog):
    """Any other exception is logged with traceback and re-raised with a metric."""
    caplog.set_level(logging.DEBUG, logger=MOD_LOGGER)
    pipeline = _quality_pipeline(mm=_mm_exc(ValueError("nope")))

    with pytest.raises(ValueError):
        await pipeline._assess_image_quality(_img(), camera_id="cam1")

    assert [c.args[0] for c in g["errs"].call_args_list] == ["brisque-quality"]
    recs = _records(caplog, "Image quality assessment error", level="ERROR")
    assert len(recs) == 1
