"""Batch 26 part 17 — mutation kill battery for backend/services/enrichment_pipeline.py.

Covers the five home functions owning chunk-17's 120 survivor keys:
  EnrichmentError.from_exception, EnrichmentPipeline._analyze_depth,
  EnrichmentPipeline._classify_weather, EnrichmentPipeline._estimate_poses,
  EnrichmentPipeline._assess_image_quality.

Every assert pins SHIPPED behaviour measured against pristine HEAD source first
(rule 1).  Observation seams are the names imported INTO the module, patched at
the import site (backend.services.enrichment_pipeline.X) with autospec, so a
mutant rebound over the live module dict is observed exactly as shipped code
would be.  `sanitize_error` is deliberately left LIVE: expectations recompute it
from the same exception object, so reason strings are pinned without mocking a
pure formatter.

Class-free plain functions; async driven with asyncio.run (no plugin dependency).
No sleeps, no network, no DB.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import ExitStack, nullcontext
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import backend.services.enrichment_pipeline as M
from backend.services.depth_anything_loader import DepthAnalysisResult, DetectionDepth
from backend.services.image_quality_loader import ImageQualityResult
from backend.services.vitpose_loader import PoseResult
from backend.services.weather_loader import WeatherResult

EP = "backend.services.enrichment_pipeline."
IMG = M.Image.new("RGB", (8, 8), "gray")


# --------------------------------------------------------------------- helpers


def det(det_id="p1", cls="person", bbox=(1, 2, 6, 7)):
    """DetectionInput stand-in: real BoundingBox, controllable id/class/bbox."""
    d = MagicMock(name="DetectionInput")
    d.id = det_id
    d.class_name = cls
    d.bbox = None if bbox is None else M.BoundingBox(*bbox)
    return d


class _Payload:
    """Model payload that works both as `as obj` and as `as (model, processor)`."""

    def __init__(self, name):
        self.name = name
        self.model = f"{name}-model"
        self.processor = f"{name}-processor"

    def __iter__(self):
        return iter((self.model, self.processor))


class _Manager:
    """model_manager stub: .load(name) -> async CM yielding a per-name payload."""

    def __init__(self, raises=None):
        self.raises = raises
        self.calls: list[str] = []
        self.payloads: dict[str, _Payload] = {}

    def load(self, name):
        self.calls.append(name)
        if self.raises is not None:
            raise self.raises
        payload = self.payloads.setdefault(name, _Payload(name))
        return nullcontext(payload)


_SEAMS = (
    "record_enrichment_model_call",
    "record_enrichment_model_error",
    "observe_enrichment_model_duration",
    "analyze_depth",
    "classify_weather",
    "assess_image_quality",
    "extract_poses_batch",
    "logger",
)


class _Ctx:
    """Pipeline under test + the patched seams."""

    def __init__(self, raises):
        self.p = M.EnrichmentPipeline.__new__(M.EnrichmentPipeline)
        self.p.model_manager = _Manager(raises)


def run(raises=None):
    """Patch every seam this chunk touches, then await the async test body(ctx)."""

    def deco(fn):
        def wrapper():
            with ExitStack() as st:
                ctx = _Ctx(raises)
                for name in _SEAMS:
                    # autospec alone observes async-ness too (async defs -> AsyncMock)
                    setattr(ctx, name, st.enter_context(patch(EP + name, autospec=True)))
                return asyncio.run(fn(ctx))

        wrapper.__name__ = fn.__name__
        wrapper.__qualname__ = fn.__qualname__
        wrapper.__doc__ = fn.__doc__
        return wrapper

    return deco


def http_error(code: int) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "http://enrichment.local:8094/v1/enrich")
    resp = httpx.Response(code, request=req)
    return httpx.HTTPStatusError(f"status {code}", request=req, response=resp)


def depth_result(close=True):
    return DepthAnalysisResult(
        detection_depths={
            "p1": DetectionDepth(
                detection_id="p1",
                class_name="person",
                depth_value=0.2,
                proximity_label="close",
            ),
        },
        closest_detection_id="p1",
        has_close_objects=close,
    )


def quality(low=False):
    return ImageQualityResult(
        quality_score=40.0,
        brisque_score=60.0,
        is_blurry=True,
        is_noisy=False,
        is_low_quality=low,
        quality_issues=["blur"] if low else [],
    )


def assert_durations(ctx, model, n=1):
    """Every duration observation the call emitted must carry a real elapsed float.

    Shipped passes `time.perf_counter() - start_time` on BOTH the success and the
    failure path, so `None`/missing is a distinguishable mutant value.
    """
    obs = ctx.observe_enrichment_model_duration.call_args_list
    assert [c.args[0] for c in obs] == [model] * n
    for (_m, dur), _kw in obs:
        assert isinstance(dur, float), f"duration must be a float, got {dur!r}"
        assert 0.0 <= dur < 10.0


def pose(i=0):
    return PoseResult(keypoints={}, pose_class="standing", pose_confidence=0.5 + i * 0.1)


def weather(confidence=0.75):
    return WeatherResult(
        condition="rainy",
        simple_condition="rain",
        confidence=confidence,
        all_scores={"rainy": confidence},
    )


# ===========================================================================
# EnrichmentError.from_exception — 19 keys (shipped lines 389-519)
# ===========================================================================


def test_fe_connect_reason_error_type_transient():
    exc = httpx.ConnectError("conn refused")
    e = M.EnrichmentError.from_exception("opA", exc)
    assert e.operation == "opA"
    assert e.category is M.ErrorCategory.SERVICE_UNAVAILABLE
    assert e.reason == f"Service connection failed: {M.sanitize_error(exc)}"
    assert e.error_type == "ConnectError"
    assert e.is_transient is True


def test_fe_connect_details_identity_and_no_status_code():
    exc = httpx.ConnectError("x")
    d = {"camera_id": "cam-1"}
    e = M.EnrichmentError.from_exception("opA", exc, details=d)
    assert e.details is d
    assert e.details == {"camera_id": "cam-1"}
    assert "status_code" not in e.details


def test_fe_timeout_reason_category_transient():
    exc = TimeoutError("slow")
    e = M.EnrichmentError.from_exception("opB", exc)
    assert e.category is M.ErrorCategory.TIMEOUT
    assert e.reason == f"Request timed out: {M.sanitize_error(exc)}"
    assert e.error_type == "TimeoutError"
    assert e.is_transient is True


def test_fe_timeout_details_identity_not_mutated():
    exc = asyncio.TimeoutError()
    d = {"stage": "depth"}
    e = M.EnrichmentError.from_exception("opB", exc, details=d)
    assert e.reason == f"Request timed out: {M.sanitize_error(exc)}"
    assert e.details is d
    assert d == {"stage": "depth"}
    assert e.error_type == "TimeoutError"


def test_fe_rate_limited_429_reason_and_details():
    e = M.EnrichmentError.from_exception("opC", http_error(429))
    assert e.category is M.ErrorCategory.RATE_LIMITED
    assert e.reason == "Rate limited (HTTP 429)"
    assert e.error_type == "HTTPStatusError"
    assert e.is_transient is True
    assert e.details == {"status_code": 429}


def test_fe_rate_limited_merges_caller_details():
    e = M.EnrichmentError.from_exception("opC", http_error(429), details={"k": 1})
    assert e.details == {"status_code": 429, "k": 1}
    assert e.reason == "Rate limited (HTTP 429)"


def test_fe_server_error_500_reason_transient():
    e = M.EnrichmentError.from_exception("opD", http_error(500))
    assert e.category is M.ErrorCategory.SERVER_ERROR
    assert e.reason == "Server error (HTTP 500)"
    assert e.is_transient is True
    assert e.details == {"status_code": 500}


def test_fe_server_error_599_upper_boundary():
    e = M.EnrichmentError.from_exception("opD", http_error(599))
    assert e.category is M.ErrorCategory.SERVER_ERROR
    assert e.reason == "Server error (HTTP 599)"
    assert e.is_transient is True
    assert e.details == {"status_code": 599}


def test_fe_status_600_falls_through_all_http_buckets():
    # shipped: the 5xx window is half-open, so 600 is UNEXPECTED, not SERVER_ERROR
    exc = http_error(600)
    e = M.EnrichmentError.from_exception("opD", exc)
    assert e.category is M.ErrorCategory.UNEXPECTED
    assert e.reason == f"Unexpected error: {M.sanitize_error(exc)}"
    assert e.is_transient is True
    assert e.details == {"status_code": 600}


def test_fe_client_error_400_reason_permanent():
    e = M.EnrichmentError.from_exception("opE", http_error(400))
    assert e.category is M.ErrorCategory.CLIENT_ERROR
    assert e.reason == "Client error (HTTP 400)"
    assert e.is_transient is False
    assert e.details == {"status_code": 400}


def test_fe_client_error_499_upper_boundary():
    e = M.EnrichmentError.from_exception("opE", http_error(499))
    assert e.category is M.ErrorCategory.CLIENT_ERROR
    assert e.reason == "Client error (HTTP 499)"
    assert e.is_transient is False
    assert e.details == {"status_code": 499}


def test_fe_429_not_client_bucket():
    e = M.EnrichmentError.from_exception("opE", http_error(429))
    assert e.category is M.ErrorCategory.RATE_LIMITED
    assert e.reason == "Rate limited (HTTP 429)"


def test_fe_parse_error_reason_is_not_str_of_none():
    # shipped interpolates sanitize_error(exc), never sanitize_error(None)/"None"
    exc = ValueError("some parse failure")
    e = M.EnrichmentError.from_exception("opG", exc)
    assert e.reason != "Response parsing failed: None"
    assert e.reason != str(None)
    assert "some parse failure" in e.reason


def test_fe_validation_reason_is_not_str_of_none():
    exc = AttributeError("some attr failure")
    e = M.EnrichmentError.from_exception("opH", exc)
    assert e.reason != "Validation failed: None"
    assert "some attr failure" in e.reason


def test_fe_unexpected_reason_is_not_str_of_none():
    exc = FloatingPointError("some odd failure")
    e = M.EnrichmentError.from_exception("opI", exc)
    assert e.reason != "Unexpected error: None"
    assert "some odd failure" in e.reason


def test_fe_ai_service_reason_is_not_str_of_none():
    exc = M.AIServiceError("distinctive service message")
    e = M.EnrichmentError.from_exception("opF", exc)
    assert e.reason == "distinctive service message"
    assert e.reason != "None"


def test_fe_timeout_and_connect_reasons_are_not_none():
    c = httpx.ConnectError("connect-marker")
    t = TimeoutError("timeout-marker")
    assert M.EnrichmentError.from_exception("op", c).reason.endswith(M.sanitize_error(c))
    assert M.EnrichmentError.from_exception("op", t).reason.endswith(M.sanitize_error(t))
    assert M.EnrichmentError.from_exception("op", c).reason is not None
    assert M.EnrichmentError.from_exception("op", t).reason is not None


def test_fe_http_reasons_carry_status_and_are_not_none():
    for code, prefix in (
        (429, "Rate limited (HTTP 429)"),
        (503, "Server error (HTTP 503)"),
        (404, "Client error (HTTP 404)"),
    ):
        e = M.EnrichmentError.from_exception("op", http_error(code))
        assert e.reason == prefix


def test_fe_ai_service_error_reason_is_str_exc():
    exc = M.AIServiceError("ai blew up")
    e = M.EnrichmentError.from_exception("opF", exc)
    assert e.category is M.ErrorCategory.SERVICE_UNAVAILABLE
    assert e.reason == str(exc)
    assert e.error_type == "AIServiceError"
    assert e.is_transient is True


def test_fe_enrichment_unavailable_reason_is_str_exc():
    exc = M.EnrichmentUnavailableError("no enrichment service")
    e = M.EnrichmentError.from_exception("opF", exc)
    assert e.category is M.ErrorCategory.SERVICE_UNAVAILABLE
    assert e.reason == str(exc)
    assert e.error_type == "EnrichmentUnavailableError"
    assert e.is_transient is True
    assert e.details == {}


def test_fe_parse_error_value_reason_permanent():
    exc = ValueError("bad payload bit")
    e = M.EnrichmentError.from_exception("opG", exc)
    assert e.category is M.ErrorCategory.PARSE_ERROR
    assert e.reason == f"Response parsing failed: {M.sanitize_error(exc)}"
    assert e.error_type == "ValueError"
    assert e.is_transient is False


def test_fe_parse_error_json_decode_error_type():
    try:
        json.loads("{not json")
    except json.JSONDecodeError as exc:
        held = exc
    e = M.EnrichmentError.from_exception("opG", held)
    assert e.category is M.ErrorCategory.PARSE_ERROR
    assert e.error_type == "JSONDecodeError"
    assert e.reason == f"Response parsing failed: {M.sanitize_error(held)}"
    assert e.is_transient is False


def test_fe_parse_error_details_identity():
    exc = TypeError("nope")
    d = {"op": "ocr"}
    e = M.EnrichmentError.from_exception("opG", exc, details=d)
    assert e.details is d
    assert d == {"op": "ocr"}
    assert e.reason == f"Response parsing failed: {M.sanitize_error(exc)}"


def test_fe_validation_error_attribute_reason_permanent():
    exc = AttributeError("missing attr")
    e = M.EnrichmentError.from_exception("opH", exc)
    assert e.category is M.ErrorCategory.VALIDATION_ERROR
    assert e.reason == f"Validation failed: {M.sanitize_error(exc)}"
    assert e.error_type == "AttributeError"
    assert e.is_transient is False


def test_fe_validation_error_details_identity():
    exc = AttributeError("missing attr")
    d = {"field": "bbox"}
    e = M.EnrichmentError.from_exception("opH", exc, details=d)
    assert e.details is d
    assert d == {"field": "bbox"}
    assert e.category is M.ErrorCategory.VALIDATION_ERROR


def test_fe_unexpected_runtime_reason_transient_true():
    exc = RuntimeError("weird runtime")
    e = M.EnrichmentError.from_exception("opI", exc)
    assert e.category is M.ErrorCategory.UNEXPECTED
    assert e.reason == f"Unexpected error: {M.sanitize_error(exc)}"
    assert e.error_type == "RuntimeError"
    assert e.is_transient is True


def test_fe_unexpected_custom_type_details_passthrough():
    class Weird(Exception):
        pass

    exc = Weird("custom boom")
    e = M.EnrichmentError.from_exception("opI", exc, details={"z": 1})
    assert e.category is M.ErrorCategory.UNEXPECTED
    assert e.reason == f"Unexpected error: {M.sanitize_error(exc)}"
    assert e.error_type == "Weird"
    assert e.is_transient is True
    assert e.details == {"z": 1}


# ===========================================================================
# EnrichmentPipeline._analyze_depth — 43 keys (shipped lines 4469-4532)
# ===========================================================================


@run()
async def test_depth_empty_detections_bare_result_no_model(ctx):
    out = await ctx.p._analyze_depth([], IMG)
    assert isinstance(out, DepthAnalysisResult)
    assert out.detection_count == 0
    assert out.closest_detection_id is None
    assert out.has_close_objects is False
    assert ctx.record_enrichment_model_call.call_args_list == []
    assert ctx.analyze_depth.call_args_list == []
    assert ctx.p.model_manager.calls == []


@run()
async def test_depth_payload_model_payload_image_dicts_and_sampling_kwarg(ctx):
    fake = depth_result()
    ctx.analyze_depth.return_value = fake
    out = await ctx.p._analyze_depth([det("p1", "person"), det("p2", "car")], IMG)
    assert out is fake
    (payload, image, dets), kwargs = ctx.analyze_depth.call_args
    assert payload is ctx.p.model_manager.payloads["depth-anything-v2-tiny"]
    assert image is IMG
    assert dets == [
        {"detection_id": "p1", "class_name": "person", "bbox": (1, 2, 6, 7)},
        {"detection_id": "p2", "class_name": "car", "bbox": (1, 2, 6, 7)},
    ]
    assert kwargs == {"depth_sampling_method": "center"}
    assert ctx.record_enrichment_model_call.call_args_list == [(("depth",), {})]
    assert ctx.p.model_manager.calls == ["depth-anything-v2-tiny"]


@run()
async def test_depth_detection_id_falls_back_to_index_when_id_falsy(ctx):
    ctx.analyze_depth.return_value = depth_result()
    await ctx.p._analyze_depth([det(None), det(""), det("keep")], IMG)
    (_pl, _im, dets), _kw = ctx.analyze_depth.call_args
    assert [d["detection_id"] for d in dets] == ["0", "1", "keep"]
    assert [d["class_name"] for d in dets] == ["person", "person", "person"]


@run()
async def test_depth_dict_keys_are_bbox_tuple_and_class_name(ctx):
    ctx.analyze_depth.return_value = depth_result()
    await ctx.p._analyze_depth([det("a", "bicycle", bbox=(3, 4, 5, 6))], IMG)
    (_pl, _im, dets), _kw = ctx.analyze_depth.call_args
    assert dets[0]["bbox"] == (3, 4, 5, 6)
    assert dets[0]["class_name"] == "bicycle"
    assert set(dets[0]) == {"detection_id", "class_name", "bbox"}


@run()
async def test_depth_drops_bboxless_detections(ctx):
    ctx.analyze_depth.return_value = depth_result()
    await ctx.p._analyze_depth([det("p1"), det("p2", bbox=None), det("p3")], IMG)
    (_pl, _im, dets), _kw = ctx.analyze_depth.call_args
    assert [d["detection_id"] for d in dets] == ["p1", "p3"]
    assert all(d["bbox"] is not None for d in dets)


@run()
async def test_depth_all_bboxless_bare_result_no_inference(ctx):
    out = await ctx.p._analyze_depth([det("p1", bbox=None)], IMG)
    assert isinstance(out, DepthAnalysisResult)
    assert out.detection_count == 0
    assert ctx.analyze_depth.call_args_list == []
    assert ctx.record_enrichment_model_call.call_args_list == []
    assert ctx.p.model_manager.calls == []
    assert ctx.observe_enrichment_model_duration.call_args_list == []


@run()
async def test_depth_complete_debug_log_close_objects_yes(ctx):
    ctx.analyze_depth.return_value = depth_result(close=True)
    await ctx.p._analyze_depth([det()], IMG)
    assert ctx.logger.debug.call_args_list == [
        (("Depth analysis complete: 1 detections, closest=p1, close_objects=yes",), {})
    ]
    assert ctx.logger.error.call_args_list == []
    assert ctx.logger.info.call_args_list == []
    assert ctx.logger.warning.call_args_list == []
    assert ctx.record_enrichment_model_error.call_args_list == []


@run()
async def test_depth_complete_debug_log_close_objects_no(ctx):
    ctx.analyze_depth.return_value = depth_result(close=False)
    await ctx.p._analyze_depth([det()], IMG)
    (msg,), _kw = ctx.logger.debug.call_args_list[0]
    assert msg == "Depth analysis complete: 1 detections, closest=p1, close_objects=no"


@run()
async def test_depth_inference_failure_reraises_metrics_and_error_log(ctx):
    boom = ValueError("depth model exploded")
    ctx.analyze_depth.side_effect = boom
    with pytest.raises(ValueError) as ei:
        await ctx.p._analyze_depth([det()], IMG)
    assert ei.value is boom
    assert ctx.record_enrichment_model_error.call_args_list == [(("depth-anything-v2",), {})]
    assert ctx.record_enrichment_model_call.call_args_list == [(("depth",), {})]
    (msg,), kwargs = ctx.logger.error.call_args_list[0]
    assert msg == f"Depth analysis failed: {M.sanitize_error(boom)}"
    assert kwargs == {"exc_info": True}
    assert ctx.logger.debug.call_args_list == []
    assert_durations(ctx, "depth-anything-v2")


@run(raises=RuntimeError("model load failed"))
async def test_depth_manager_failure_takes_failure_path(ctx):
    boom = ctx.p.model_manager.raises
    with pytest.raises(RuntimeError) as ei:
        await ctx.p._analyze_depth([det()], IMG)
    assert ei.value is boom
    assert ctx.record_enrichment_model_error.call_args_list == [(("depth-anything-v2",), {})]
    (msg,), kwargs = ctx.logger.error.call_args_list[0]
    assert msg == f"Depth analysis failed: {M.sanitize_error(boom)}"
    assert kwargs == {"exc_info": True}
    assert ctx.analyze_depth.call_args_list == []
    assert_durations(ctx, "depth-anything-v2")


@run()
async def test_depth_duration_is_bounded_float_metric(ctx):
    ctx.analyze_depth.return_value = depth_result()
    await ctx.p._analyze_depth([det()], IMG)
    assert_durations(ctx, "depth-anything-v2")


# ===========================================================================
# EnrichmentPipeline._estimate_poses — 19 keys (shipped lines 4534-4599)
# ===========================================================================


@run()
async def test_poses_empty_persons_empty_dict_no_model(ctx):
    ctx.p._crop_to_bbox = AsyncMock(return_value=IMG)
    out = await ctx.p._estimate_poses([], IMG)
    assert out == {}
    assert ctx.p.model_manager.calls == []
    assert ctx.extract_poses_batch.call_args_list == []
    assert ctx.record_enrichment_model_call.call_args_list == []
    assert ctx.p._crop_to_bbox.await_count == 0


@run()
async def test_poses_happy_crop_args_batch_args_and_result_map(ctx):
    crop = M.Image.new("RGB", (4, 4), "red")
    ctx.p._crop_to_bbox = AsyncMock(return_value=crop)
    fake = [pose(0)]
    ctx.extract_poses_batch.return_value = fake
    out = await ctx.p._estimate_poses([det("p1")], IMG)
    assert ctx.record_enrichment_model_call.call_args_list == [(("pose",), {})]
    ctx.p._crop_to_bbox.assert_awaited_once_with(IMG, M.BoundingBox(1, 2, 6, 7))
    (model, processor, crops, boxes), _kw = ctx.extract_poses_batch.call_args_list[0]
    assert model == "vitpose-small-model"
    assert processor == "vitpose-small-processor"
    assert crops == [crop] and crops[0] is crop
    assert boxes == [[1.0, 2.0, 6.0, 7.0]]
    assert list(out) == ["p1"]
    assert out["p1"] is fake[0]
    assert ctx.logger.debug.call_args_list == [
        (("Pose estimation complete: 1 persons analyzed",), {})
    ]
    assert ctx.logger.error.call_args_list == []
    assert ctx.record_enrichment_model_error.call_args_list == []
    assert_durations(ctx, "vitpose")
    assert ctx.p.model_manager.calls == ["vitpose-small"]


@run()
async def test_poses_det_id_index_fallback_and_bbox_projection(ctx):
    ctx.p._crop_to_bbox = AsyncMock(return_value=IMG)
    ctx.extract_poses_batch.return_value = [pose(0), pose(1)]
    out = await ctx.p._estimate_poses([det(None, bbox=(3, 4, 5, 6)), det("")], IMG)
    (_m, _pr, crops, boxes), _kw = ctx.extract_poses_batch.call_args_list[0]
    assert len(crops) == 2
    assert boxes == [[3.0, 4.0, 5.0, 6.0], [1.0, 2.0, 6.0, 7.0]]
    assert list(out) == ["0", "1"]
    assert ctx.p._crop_to_bbox.await_args_list[0].args[1] == M.BoundingBox(3, 4, 5, 6)


@run()
async def test_poses_skips_bboxless_without_crop_call(ctx):
    ctx.p._crop_to_bbox = AsyncMock(return_value=IMG)
    ctx.extract_poses_batch.return_value = [pose(0)]
    out = await ctx.p._estimate_poses([det("skip", bbox=None), det("keep")], IMG)
    assert ctx.p._crop_to_bbox.await_count == 1
    assert ctx.p._crop_to_bbox.await_args_list[0].args[1] == M.BoundingBox(1, 2, 6, 7)
    (_m, _pr, _c, boxes), _kw = ctx.extract_poses_batch.call_args_list[0]
    assert boxes == [[1.0, 2.0, 6.0, 7.0]]
    assert list(out) == ["keep"]


@run()
async def test_poses_all_bboxless_empty_dict_without_crop_or_inference(ctx):
    ctx.p._crop_to_bbox = AsyncMock(return_value=IMG)
    out = await ctx.p._estimate_poses([det("a", bbox=None), det("b", bbox=None)], IMG)
    assert out == {}
    assert ctx.p._crop_to_bbox.await_count == 0
    assert ctx.extract_poses_batch.call_args_list == []
    assert ctx.record_enrichment_model_call.call_args_list == []
    assert ctx.observe_enrichment_model_duration.call_args_list == []


@run()
async def test_poses_falsy_crop_yields_empty_dict_without_inference(ctx):
    ctx.p._crop_to_bbox = AsyncMock(return_value=None)
    out = await ctx.p._estimate_poses([det("p1")], IMG)
    assert out == {}
    assert ctx.p._crop_to_bbox.await_count == 1
    assert ctx.extract_poses_batch.call_args_list == []
    assert ctx.record_enrichment_model_call.call_args_list == []
    assert ctx.p.model_manager.calls == []
    assert ctx.observe_enrichment_model_duration.call_args_list == []


@run()
async def test_poses_inference_failure_reraises_with_vitpose_metrics(ctx):
    boom = RuntimeError("vitpose died")
    ctx.p._crop_to_bbox = AsyncMock(return_value=IMG)
    ctx.extract_poses_batch.side_effect = boom
    with pytest.raises(RuntimeError) as ei:
        await ctx.p._estimate_poses([det("p1")], IMG)
    assert ei.value is boom
    assert ctx.record_enrichment_model_error.call_args_list == [(("vitpose",), {})]
    (msg,), kwargs = ctx.logger.error.call_args_list[0]
    assert msg == f"Pose estimation failed: {M.sanitize_error(boom)}"
    assert kwargs == {"exc_info": True}
    assert_durations(ctx, "vitpose")


@run()
async def test_poses_duration_is_bounded_float_metric(ctx):
    ctx.p._crop_to_bbox = AsyncMock(return_value=IMG)
    ctx.extract_poses_batch.return_value = [pose(0)]
    await ctx.p._estimate_poses([det("p1")], IMG)
    assert_durations(ctx, "vitpose")


# ===========================================================================
# EnrichmentPipeline._classify_weather — 28 keys (shipped lines 6532-6574)
# ===========================================================================


@run()
async def test_weather_happy_records_both_names_returns_result(ctx):
    fake = weather()
    ctx.classify_weather.return_value = fake
    out = await ctx.p._classify_weather(IMG)
    assert out is fake
    assert ctx.record_enrichment_model_call.call_args_list == [
        (("weather",), {}),
        (("weather-classification",), {}),
    ]
    (model_data, image), _kw = ctx.classify_weather.call_args_list[0]
    assert model_data is ctx.p.model_manager.payloads["weather-classification"]
    assert image is IMG
    assert ctx.p.model_manager.calls == ["weather-classification"]


@run()
async def test_weather_info_log_percent_format_and_no_error_paths(ctx):
    ctx.classify_weather.return_value = weather(0.75)
    await ctx.p._classify_weather(IMG)
    assert ctx.logger.info.call_args_list == [
        (("Weather classified as rain (75% confidence)",), {})
    ]
    assert ctx.logger.error.call_args_list == []
    assert ctx.logger.warning.call_args_list == []
    assert ctx.record_enrichment_model_error.call_args_list == []
    assert_durations(ctx, "weather-classification")


@run()
async def test_weather_info_log_low_confidence_rounding(ctx):
    ctx.classify_weather.return_value = weather(0.062)
    await ctx.p._classify_weather(IMG)
    (msg,), _kw = ctx.logger.info.call_args_list[0]
    assert msg == "Weather classified as rain (6% confidence)"


@run(raises=KeyError("weather-classification"))
async def test_weather_keyerror_becomes_runtimeerror_with_warning(ctx):
    boom = ctx.p.model_manager.raises
    with pytest.raises(RuntimeError) as ei:
        await ctx.p._classify_weather(IMG)
    assert str(ei.value) == "weather-classification model not configured"
    assert ei.value.__cause__ is boom
    assert ctx.logger.warning.call_args_list == [
        (("weather-classification model not available in MODEL_ZOO",), {})
    ]
    assert ctx.logger.error.call_args_list == []
    assert ctx.logger.info.call_args_list == []
    assert ctx.record_enrichment_model_error.call_args_list == [(("weather-classification",), {})]
    assert ctx.record_enrichment_model_call.call_args_list == []
    assert_durations(ctx, "weather-classification")


@run()
async def test_weather_generic_failure_logs_error_and_reraises(ctx):
    boom = ValueError("bad weather payload")
    ctx.classify_weather.side_effect = boom
    with pytest.raises(ValueError) as ei:
        await ctx.p._classify_weather(IMG)
    assert ei.value is boom
    assert ctx.logger.error.call_args_list == [
        (("Weather classification error",), {"exc_info": True})
    ]
    assert ctx.logger.warning.call_args_list == []
    assert ctx.logger.info.call_args_list == []
    assert ctx.record_enrichment_model_error.call_args_list == [(("weather-classification",), {})]
    assert_durations(ctx, "weather-classification")


@run()
async def test_weather_duration_is_bounded_float_metric(ctx):
    ctx.classify_weather.return_value = weather()
    await ctx.p._classify_weather(IMG)
    assert_durations(ctx, "weather-classification")


# ===========================================================================
# EnrichmentPipeline._assess_image_quality — 11 keys (shipped lines 7042-7109)
# ===========================================================================


@run()
async def test_quality_happy_returns_result_records_both_names(ctx):
    fake = quality()
    ctx.assess_image_quality.return_value = fake
    out = await ctx.p._assess_image_quality(IMG, "cam-9")
    assert out is fake
    assert ctx.record_enrichment_model_call.call_args_list == [
        (("brisque",), {}),
        (("brisque-quality",), {}),
    ]
    (model_data, image), _kw = ctx.assess_image_quality.call_args_list[0]
    assert model_data is ctx.p.model_manager.payloads["brisque-quality"]
    assert image is IMG
    assert ctx.p.model_manager.calls == ["brisque-quality"]
    assert ctx.logger.debug.call_args_list == []
    assert ctx.logger.error.call_args_list == []
    assert ctx.logger.warning.call_args_list == []
    assert ctx.record_enrichment_model_error.call_args_list == []


@run()
async def test_quality_low_quality_debug_log_with_camera_and_score(ctx):
    ctx.assess_image_quality.return_value = quality(low=True)
    await ctx.p._assess_image_quality(IMG, "cam-9")
    assert ctx.logger.debug.call_args_list == [
        (("Low quality image detected (camera: cam-9): score=40, issues=['blur']",), {})
    ]
    assert ctx.logger.error.call_args_list == []


@run()
async def test_quality_low_quality_without_camera_omits_suffix(ctx):
    fake = quality(low=True)
    fake.quality_issues = []
    ctx.assess_image_quality.return_value = fake
    await ctx.p._assess_image_quality(IMG)
    (msg,), _kw = ctx.logger.debug.call_args_list[0]
    assert msg == "Low quality image detected: score=40, issues=[]"


@run(raises=KeyError("brisque-quality"))
async def test_quality_keyerror_becomes_runtimeerror_with_warning(ctx):
    boom = ctx.p.model_manager.raises
    with pytest.raises(RuntimeError) as ei:
        await ctx.p._assess_image_quality(IMG)
    assert str(ei.value) == "brisque-quality model not configured"
    assert ei.value.__cause__ is boom
    assert ctx.logger.warning.call_args_list == [
        (("brisque-quality model not available in MODEL_ZOO",), {})
    ]
    assert ctx.record_enrichment_model_error.call_args_list == [(("brisque-quality",), {})]
    assert ctx.logger.error.call_args_list == []


@run()
async def test_quality_runtime_disabled_skips_error_metric_logs_debug(ctx):
    boom = RuntimeError("BRISQUE model is DISABLED by config")
    ctx.assess_image_quality.side_effect = boom
    with pytest.raises(RuntimeError) as ei:
        await ctx.p._assess_image_quality(IMG)
    assert ei.value is boom
    assert [c.args[0] for c in ctx.logger.debug.call_args_list] == [
        f"Image quality assessment skipped: {boom}"
    ]
    assert ctx.logger.error.call_args_list == []
    assert ctx.record_enrichment_model_error.call_args_list == []
    assert ctx.record_enrichment_model_call.call_args_list == [(("brisque",), {})]
    assert [c.args[0] for c in ctx.observe_enrichment_model_duration.call_args_list] == [
        "brisque-quality"
    ]


@run()
async def test_quality_runtime_without_disabled_word_logs_runtime_error(ctx):
    boom = RuntimeError("cv2 crashed internally")
    ctx.assess_image_quality.side_effect = boom
    with pytest.raises(RuntimeError) as ei:
        await ctx.p._assess_image_quality(IMG)
    assert ei.value is boom
    assert ctx.logger.error.call_args_list == [
        (("Image quality assessment error (runtime)",), {"exc_info": True})
    ]
    assert ctx.logger.debug.call_args_list == []
    assert ctx.record_enrichment_model_error.call_args_list == [(("brisque-quality",), {})]


@run()
async def test_quality_non_runtime_error_logs_plain_error_line(ctx):
    boom = ValueError("not a runtime error")
    ctx.assess_image_quality.side_effect = boom
    with pytest.raises(ValueError) as ei:
        await ctx.p._assess_image_quality(IMG)
    assert ei.value is boom
    assert ctx.logger.error.call_args_list == [
        (("Image quality assessment error",), {"exc_info": True})
    ]
    assert ctx.logger.debug.call_args_list == []
    assert ctx.record_enrichment_model_error.call_args_list == [(("brisque-quality",), {})]


@run()
async def test_quality_duration_is_bounded_float_metric(ctx):
    ctx.assess_image_quality.return_value = quality()
    await ctx.p._assess_image_quality(IMG)
    assert_durations(ctx, "brisque-quality")
