"""Batch-26 chunk-08 kill battery — EnrichmentPipeline.enrich_batch + enrich_batch_with_tracking.

Shipped source of truth: backend/services/enrichment_pipeline.py
  enrich_batch                  : shipped lines 5555-5730
  enrich_batch_with_tracking    : shipped lines 7269-7485

Every assertion here was PROBED against the pristine shipped module first (probes/c08/probe*.py).
Seams used (all at the IMPORT SITE, per campaign rules):
  * `backend.services.enrichment_pipeline.add_span_event`  (module-level import, ship line 79)
  * `backend.core.metrics.<helper>` + `backend.services.enrichment_pipeline.<helper>`
    — enrich_batch_with_tracking does `from backend.core.metrics import (...)` INSIDE the def
      (ship 7289-7294), so that module is the binding the shipped/variant body resolves;
      enrich_batch's cascade helpers resolve on the enrichment_pipeline module (ship 66-78).
  * `backend.services.enrichment_pipeline.EnrichmentPipeline.<collaborator>`
No sleeps, no network, no DB I/O.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from unittest import mock

import backend.core.metrics as MET
import backend.services.enrichment_pipeline as M
import pytest

CAM = "cam-front"
IMG = "shared-frame.jpg"  # enrich_batch/_load_image are mocked: content is never touched
CAR = "car"  # measured: in M.VEHICLE_CLASSES
DOG = "dog"  # measured: in M.ANIMAL_CLASSES
PERSON = "person"  # measured: M.PERSON_CLASS == "person"


# ----------------------------------------------------------------------------- helpers


def det(cls: str, conf: float = 0.9, did: int | None = None):
    return M.DetectionInput(
        class_name=cls,
        confidence=conf,
        id=did,
        bbox=M.BoundingBox(x1=0.0, y1=0.0, x2=8.0, y2=8.0, confidence=conf),
    )


def stub_result(**overrides):
    """A bare shipped EnrichmentResult; enrich_batch is stubbed so no model ever runs."""
    r = M.EnrichmentResult()
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def pipeline(**kw):
    return M.EnrichmentPipeline(**kw)


METRICS = (
    "set_enrichment_success_rate",
    "record_enrichment_failure",
    "record_enrichment_partial_batch",
    "record_enrichment_batch_status",
    "record_cascade_skipped",
    "record_cascade_processed",
)


def _exec_namespaces():
    """Global dicts a mutant body may resolve module-level names against.

    ep_plugin binds a variant by exec'ing it against a SNAPSHOT copy of the live module dict, so
    a plain mock.patch.object(M, ...) is seen by the shipped body (whose globals are M.__dict__)
    but not by the bound variant. Under a real mutmut build the mutant's globals *are* the module
    dict, so mirroring the patch into the exec namespace is what faithfully reproduces shipped
    semantics. No-op when the plugin is not loaded / no mutant is bound.
    """
    dicts = [M.__dict__]
    try:  # pragma: no cover - only present during mutation probes
        import ep_plugin

        if ep_plugin._STATE.get("mod") is not None:
            dicts.append(ep_plugin._MOD)
    except Exception:  # noqa: BLE001, S110 - plugin absent in normal runs
        pass
    return dicts


@contextlib.contextmanager
def patch_global(name, value):
    """Patch a module-level binding everywhere a (mutant) body can see it."""
    sentinels = []
    dicts = _exec_namespaces()
    for d in dicts:
        sentinels.append((d, d.get(name, mock.DEFAULT)))
        d[name] = value
    try:
        yield value
    finally:
        for d, old in sentinels:
            if old is mock.DEFAULT:
                d.pop(name, None)
            else:
                d[name] = old


@contextlib.contextmanager
def metrics():
    """Patch the enrichment metric helpers at both live import sites (see module docstring)."""
    mocks = {name: mock.MagicMock(name=name) for name in METRICS}
    with contextlib.ExitStack() as stack:
        for name, obj in mocks.items():
            stack.enter_context(mock.patch.object(MET, name, obj))
            stack.enter_context(patch_global(name, obj))
        yield mocks


def rates(mocks):
    """Exact ordered [(model, rate)] of every set_enrichment_success_rate call."""
    return [tuple(c.args) for c in mocks["set_enrichment_success_rate"].call_args_list]


def rate_calls(mocks, model):
    return [r for r in rates(mocks) if r[0] == model]


def run_tracking(pip, *, dets, images, camera, stub):
    """Drive enrich_batch_with_tracking with self.enrich_batch stubbed to `stub`.

    Returns (tracking_result, metric_mocks). The mock objects keep their recorded calls after
    the patch is torn down, so assertions are still meaningful on return.
    """
    eb = mock.AsyncMock(name="enrich_batch", return_value=stub)
    with metrics() as mocks:
        with mock.patch.object(M.EnrichmentPipeline, "enrich_batch", new=eb):
            tracking = asyncio.run(pip.enrich_batch_with_tracking(dets, images, camera))
        assert eb.await_count == 1, "shipped tracking awaits enrich_batch exactly once"
        return tracking, mocks


def ep_logs(caplog):
    return [r for r in caplog.records if r.name.endswith("enrichment_pipeline")]


# ============================================================ shipped configuration pins


def test_t08_shipped_defaults_are_all_enabled():
    """Measured shipped ctor defaults that every tracking gate reads (ship 2063-2122)."""
    pip = pipeline()
    assert pip.min_confidence == 0.5
    assert pip.license_plate_enabled is True
    assert pip.face_detection_enabled is True
    assert pip.vision_extraction_enabled is True
    assert pip.reid_enabled is True
    assert pip.scene_change_enabled is True
    assert pip.violence_detection_enabled is True
    assert pip.weather_classification_enabled is True
    assert pip.clothing_classification_enabled is True
    assert pip.clothing_segmentation_enabled is True
    assert pip.vehicle_damage_detection_enabled is True
    assert pip.vehicle_classification_enabled is True
    assert pip.image_quality_enabled is True  # settings.image_quality_enabled in the test env
    assert pip.pet_classification_enabled is True
    assert pip.depth_estimation_enabled is True
    assert pip.low_light_enhancement_enabled is True
    assert pip.redis_client is None
    assert M.PERSON_CLASS == "person"
    assert CAR in M.VEHICLE_CLASSES
    assert DOG in M.ANIMAL_CLASSES


def test_t08_start_span_event_name_and_payload():
    """ship 5585-5594: add_span_event('enrichment_pipeline.start', {5 exact keys}, positional)."""
    pip = pipeline()
    span = mock.MagicMock(name="add_span_event")
    with (
        patch_global("add_span_event", span),
        mock.patch.object(M.EnrichmentPipeline, "_load_image", new_callable=mock.AsyncMock),
        mock.patch.object(
            M.EnrichmentPipeline, "_maybe_enhance_low_light", new_callable=mock.AsyncMock
        ),
        mock.patch.object(
            M.EnrichmentPipeline, "_run_parallel_enrichment", new_callable=mock.AsyncMock
        ),
        metrics(),
    ):
        asyncio.run(pip.enrich_batch([det(PERSON), det(CAR, conf=0.8)], {None: IMG}, CAM))
    assert len(span.call_args_list) >= 1
    first = span.call_args_list[0]
    assert first.kwargs == {}
    assert len(first.args) == 2, f"span event takes (name, attributes), got {first.args!r}"
    assert first.args[0] == "enrichment_pipeline.start"
    assert first.args[1] == {
        "detection.count": 2,
        "camera.id": CAM,
        "license_plate.enabled": True,
        "face_detection.enabled": True,
        "vision_extraction.enabled": True,
    }


def test_t08_start_span_event_camera_id_falls_back_to_unknown():
    """ship 5589: `camera_id or "unknown"` — a falsy camera id becomes the literal 'unknown'."""
    pip = pipeline()
    span = mock.MagicMock(name="add_span_event")
    with (
        patch_global("add_span_event", span),
        metrics(),
    ):
        asyncio.run(pip.enrich_batch([], {}, None))
    assert span.call_args_list[0].args[1] == {
        "detection.count": 0,
        "camera.id": "unknown",
        "license_plate.enabled": True,
        "face_detection.enabled": True,
        "vision_extraction.enabled": True,
    }, span.call_args_list[0].args


def test_t08_no_detections_cascade_debug_and_empty_result(caplog):
    """ship 5596-5600: record_cascade_skipped + that exact debug line, then an empty result."""
    pip = pipeline()
    span = mock.MagicMock(name="add_span_event")
    # The ctor emits its own INFO line and caplog's handler captures from the
    # START of the test (at_level only tunes levels, it does not reset the
    # buffer) — drop what predates the window. Under CI's seed this ctor INFO
    # landed inside the assertion window and reddened these three tests
    # (run 36252719350 shard 1); same defense as batch26_19.
    caplog.clear()
    with (
        caplog.at_level(logging.DEBUG, logger="backend.services.enrichment_pipeline"),
        patch_global("add_span_event", span),
        metrics() as mocks,
    ):
        out = asyncio.run(pip.enrich_batch([], {None: IMG}, CAM))
    msgs = [r.getMessage() for r in ep_logs(caplog)]
    assert msgs == ["Cascade: no detections, skipping all enrichment"], msgs
    assert len(ep_logs(caplog)) == 1, ep_logs(caplog)
    mocks["record_cascade_skipped"].assert_called_once_with()
    mocks["record_cascade_processed"].assert_not_called()
    assert isinstance(out, M.EnrichmentResult)
    assert out.errors == []
    assert span.call_args_list[0].args[0] == "enrichment_pipeline.start"


def test_t08_confidence_cascade_debug_record_fields(caplog):
    """ship 5618-5626: lazy %-format pins BOTH the detection count and the threshold."""
    pip = pipeline()
    caplog.clear()  # ctor INFO precedes the window (see the note above)
    with (
        caplog.at_level(logging.DEBUG, logger="backend.services.enrichment_pipeline"),
        patch_global("add_span_event", mock.MagicMock()),
        mock.patch.object(M.EnrichmentPipeline, "_load_image", new_callable=mock.AsyncMock),
        mock.patch.object(
            M.EnrichmentPipeline, "_maybe_enhance_low_light", new_callable=mock.AsyncMock
        ),
        metrics() as mocks,
    ):
        out = asyncio.run(pip.enrich_batch([det(PERSON, conf=0.1)], {None: IMG}, CAM))
    recs = ep_logs(caplog)
    assert len(recs) == 1, [r.getMessage() for r in recs]
    assert (
        recs[0].msg == "Cascade: %d detections all below min_confidence=%.2f, skipping enrichment"
    )
    assert recs[0].args == (1, 0.5), recs[0].args
    assert (
        recs[0].getMessage()
        == "Cascade: 1 detections all below min_confidence=0.50, skipping enrichment"
    )
    mocks["record_cascade_skipped"].assert_called_once_with()
    mocks["record_cascade_processed"].assert_not_called()
    assert out.errors == []
    assert out.faces == []


def test_t08_low_light_enhancement_requires_a_loaded_image():
    """ship 5602-5613: `_maybe_enhance_low_light` runs only when pil_image is truthy.

    A: no shared-image key  -> _load_image and _maybe_enhance_low_light both skipped.
    B: shared image decodes to None -> _load_image awaited, enhancement NOT called.
    C: shared image decodes to an object -> enhanced exactly once, enhanced frame passed downstream.
    """
    sentinel = object()
    # A
    pip = pipeline()
    with (
        patch_global("add_span_event", mock.MagicMock()),
        mock.patch.object(M.EnrichmentPipeline, "_load_image", new_callable=mock.AsyncMock) as load,
        mock.patch.object(
            M.EnrichmentPipeline, "_maybe_enhance_low_light", new_callable=mock.AsyncMock
        ) as enhance,
        mock.patch.object(
            M.EnrichmentPipeline, "_run_parallel_enrichment", new_callable=mock.AsyncMock
        ) as par,
        metrics() as mocks,
    ):
        asyncio.run(pip.enrich_batch([det(PERSON)], {}, CAM))
    load.assert_not_called()
    enhance.assert_not_called()
    par.assert_not_awaited()
    mocks["record_cascade_processed"].assert_called_once_with()

    # B
    pip_b = pipeline()
    with (
        patch_global("add_span_event", mock.MagicMock()),
        mock.patch.object(
            M.EnrichmentPipeline, "_load_image", new_callable=mock.AsyncMock, return_value=None
        ) as load_b,
        mock.patch.object(
            M.EnrichmentPipeline, "_maybe_enhance_low_light", new_callable=mock.AsyncMock
        ) as enhance_b,
        mock.patch.object(
            M.EnrichmentPipeline, "_run_parallel_enrichment", new_callable=mock.AsyncMock
        ) as par_b,
        metrics(),
    ):
        asyncio.run(pip_b.enrich_batch([det(PERSON)], {None: IMG}, CAM))
    load_b.assert_awaited_once_with(IMG)
    enhance_b.assert_not_called()
    par_b.assert_not_awaited()

    # C
    pip_c = pipeline()
    enhanced = object()
    with (
        patch_global("add_span_event", mock.MagicMock()),
        mock.patch.object(
            M.EnrichmentPipeline, "_load_image", new_callable=mock.AsyncMock, return_value=sentinel
        ),
        mock.patch.object(
            M.EnrichmentPipeline,
            "_maybe_enhance_low_light",
            new_callable=mock.AsyncMock,
            return_value=enhanced,
        ) as enhance_c,
        mock.patch.object(
            M.EnrichmentPipeline, "_run_parallel_enrichment", new_callable=mock.AsyncMock
        ) as par_c,
        metrics(),
    ):
        asyncio.run(pip_c.enrich_batch([det(PERSON)], {None: IMG}, CAM))
    enhance_c.assert_awaited_once_with(sentinel)
    assert par_c.await_args.kwargs["pil_image"] is enhanced


def test_t08_low_light_enhancement_skipped_when_disabled():
    """ship 5612: the conjunction also requires self.low_light_enhancement_enabled."""
    pip = pipeline(low_light_enhancement_enabled=False)
    with (
        patch_global("add_span_event", mock.MagicMock()),
        mock.patch.object(
            M.EnrichmentPipeline, "_load_image", new_callable=mock.AsyncMock, return_value=object()
        ),
        mock.patch.object(
            M.EnrichmentPipeline, "_maybe_enhance_low_light", new_callable=mock.AsyncMock
        ) as enhance,
        mock.patch.object(
            M.EnrichmentPipeline, "_run_parallel_enrichment", new_callable=mock.AsyncMock
        ),
        metrics(),
    ):
        asyncio.run(pip.enrich_batch([det(PERSON)], {None: IMG}, CAM))
    enhance.assert_not_called()


def test_t08_start_and_complete_span_events_bracket_the_run():
    """ship 5585-5594 + 5682-5706: exactly two span events, start then complete."""
    pip = pipeline()
    span = mock.MagicMock(name="add_span_event")
    with (
        patch_global("add_span_event", span),
        mock.patch.object(
            M.EnrichmentPipeline, "_load_image", new_callable=mock.AsyncMock, return_value=object()
        ),
        mock.patch.object(
            M.EnrichmentPipeline, "_maybe_enhance_low_light", new_callable=mock.AsyncMock
        ),
        mock.patch.object(
            M.EnrichmentPipeline, "_run_parallel_enrichment", new_callable=mock.AsyncMock
        ),
        metrics() as mocks,
    ):
        out = asyncio.run(pip.enrich_batch([det(PERSON)], {None: IMG}, CAM))
    assert [c.args[0] for c in span.call_args_list] == [
        "enrichment_pipeline.start",
        "enrichment_pipeline.complete",
    ]
    complete = span.call_args_list[1].args[1]
    assert complete["parallel_execution"] is True
    assert complete["error.count"] == 0
    assert complete["image_quality.assessed"] is False
    assert complete["processing.duration_ms"] >= 0
    mocks["record_cascade_processed"].assert_called_once_with()
    assert out.processing_time_ms >= 0.0


# ==================================================== enrich_batch_with_tracking (7269-7485)


def test_t08_empty_detections_report_skipped_with_no_data():
    """ship 7302-7311: no detections -> SKIPPED, empty lists, data=None, batch status 'skipped'."""
    pip = pipeline()
    with metrics() as mocks:
        tracking = asyncio.run(pip.enrich_batch_with_tracking([], {None: IMG}, CAM))
    assert tracking.status == M.EnrichmentStatus.SKIPPED
    assert tracking.successful_models == []
    assert tracking.failed_models == []
    assert tracking.errors == {}
    assert tracking.data is None
    assert tracking.success_rate == 1.0
    assert mocks["record_enrichment_batch_status"].call_args_list == [mock.call("skipped")]
    mocks["record_enrichment_partial_batch"].assert_not_called()
    assert rates(mocks) == []


def test_t08_vision_success_appends_and_rates_one():
    """ship 7376-7379: enabled + shared image + no vision error + output present -> 1.0."""
    pip = pipeline()
    stub = stub_result(vision_extraction=object())
    tracking, mocks = run_tracking(
        pip, dets=[det(PERSON)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.successful_models == [
        "face",
        "vision",
        "scene_change",
        "clothing",
        "segformer",
    ]
    assert tracking.failed_models == []
    assert rates(mocks) == [
        ("face", 1.0),
        ("vision", 1.0),
        ("scene_change", 1.0),
        ("clothing", 1.0),
        ("segformer", 1.0),
    ]
    assert tracking.status == M.EnrichmentStatus.FULL


def test_t08_vision_failure_rates_zero():
    """ship 7380-7381 + 7339-7345: 'vision_extraction failed:' -> failed 'vision', rate 0.0."""
    pip = pipeline()
    stub = stub_result(errors=["vision_extraction failed: florence unavailable"])
    tracking, mocks = run_tracking(
        pip, dets=[det(PERSON)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.failed_models == ["vision"]
    assert tracking.errors == {"vision": "vision_extraction failed: florence unavailable"}
    assert tracking.successful_models == ["face", "scene_change", "clothing", "segformer"]
    mocks["record_enrichment_failure"].assert_called_once_with("vision")
    assert rates(mocks) == [
        ("face", 1.0),
        ("vision", 0.0),
        ("scene_change", 1.0),
        ("clothing", 1.0),
        ("segformer", 1.0),
    ]
    assert tracking.status == M.EnrichmentStatus.PARTIAL


def test_t08_no_shared_image_closes_every_image_gated_model():
    """ship 7349-7350 + gates at 7376/7383/7390/7397/7404/7411/7418/7425/7432/7439/7446/7453.

    `pil_image_available = images.get(None) is not None`. With no shared image EVERY image-gated
    model is unattempted even when its enable flag is True, its class trigger is present and the
    stubbed result carries that model's output; only the two image-independent gates report
    success (license_plate on vehicles, face on persons).
    """
    pip = pipeline(redis_client=object())
    stub = stub_result(
        vision_extraction=object(),
        weather_classification=object(),
        image_quality=object(),
        depth_analysis=object(),
    )
    dets = [det(CAR), det(PERSON, did=1), det(PERSON, did=2), det(DOG)]
    tracking, mocks = run_tracking(pip, dets=dets, images={}, camera=CAM, stub=stub)
    assert tracking.successful_models == ["license_plate", "face"]
    assert tracking.failed_models == []
    assert rates(mocks) == [("license_plate", 1.0), ("face", 1.0)]
    assert tracking.status == M.EnrichmentStatus.FULL


def test_t08_reid_is_not_attempted_without_redis_client():
    """ship 7383: the reid gate additionally requires self.redis_client."""
    pip = pipeline(redis_client=None)
    tracking, mocks = run_tracking(
        pip, dets=[det(PERSON)], images={None: IMG}, camera=CAM, stub=stub_result()
    )
    assert tracking.successful_models == ["face", "scene_change", "clothing", "segformer"]
    assert rate_calls(mocks, "reid") == []


def test_t08_scene_change_is_not_attempted_without_camera_id():
    """ship 7390: the scene_change gate additionally requires a truthy camera_id."""
    pip = pipeline()
    tracking, mocks = run_tracking(
        pip, dets=[det(PERSON)], images={None: IMG}, camera=None, stub=stub_result()
    )
    assert tracking.successful_models == ["face", "clothing", "segformer"]
    assert rate_calls(mocks, "scene_change") == []


def test_t08_violence_requires_two_high_confidence_persons():
    """ship 7397 + 7357-7359: the violence gate needs >= 2 high-confidence persons."""
    one, mocks_one = run_tracking(
        pipeline(), dets=[det(PERSON)], images={None: IMG}, camera=CAM, stub=stub_result()
    )
    assert one.successful_models == ["face", "scene_change", "clothing", "segformer"]
    assert rate_calls(mocks_one, "violence") == []
    two, mocks_two = run_tracking(
        pipeline(),
        dets=[det(PERSON, did=1), det(PERSON, did=2)],
        images={None: IMG},
        camera=CAM,
        stub=stub_result(),
    )
    assert two.successful_models == [
        "face",
        "scene_change",
        "violence",
        "clothing",
        "segformer",
    ]
    assert rates(mocks_two) == [
        ("face", 1.0),
        ("scene_change", 1.0),
        ("violence", 1.0),
        ("clothing", 1.0),
        ("segformer", 1.0),
    ]


def test_t08_pet_requires_an_animal_detection():
    """ship 7446: the pet gate needs a high-confidence ANIMAL_CLASSES detection."""
    no_pet, mocks_a = run_tracking(
        pipeline(), dets=[det(CAR)], images={None: IMG}, camera=CAM, stub=stub_result()
    )
    assert "pet" not in no_pet.successful_models
    assert rate_calls(mocks_a, "pet") == []
    with_pet, mocks_b = run_tracking(
        pipeline(), dets=[det(DOG)], images={None: IMG}, camera=CAM, stub=stub_result()
    )
    assert with_pet.successful_models == ["scene_change", "pet"]
    assert rates(mocks_b) == [("scene_change", 1.0), ("pet", 1.0)]


def test_t08_depth_gate_requires_a_high_confidence_detection():
    """ship 7453: the depth gate is `enabled and pil_image_available and high_conf_detections`.

    A single below-threshold detection empties high_conf_detections, so depth stays unattempted
    even though the stubbed result carries depth output.
    """
    stub = stub_result(depth_analysis=object())
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(CAR, conf=0.1)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.successful_models == ["scene_change"]
    assert rate_calls(mocks, "depth") == []


def test_t08_absent_model_outputs_are_never_recorded_as_successes():
    """Cross-check of the bare-stub baseline: untriggered/absent models produce NO rate call."""
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(DOG)], images={None: IMG}, camera=CAM, stub=stub_result()
    )
    assert tracking.successful_models == ["scene_change", "pet"]
    assert rates(mocks) == [("scene_change", 1.0), ("pet", 1.0)]
    for model in (
        "vision",
        "weather",
        "image_quality",
        "depth",
        "clothing",
        "segformer",
        "vehicle_damage",
        "vehicle_class",
        "license_plate",
        "violence",
        "reid",
    ):
        assert model not in tracking.successful_models
        assert rate_calls(mocks, model) == [], model


# ------------------------------------------------------------------- weather (7404-7409)


def test_t08_weather_success_pins_rate_one():
    """ship 7404-7407: no weather error AND result.weather_classification present -> 'weather', 1.0."""
    stub = stub_result(weather_classification=object())
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(PERSON)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.successful_models == [
        "face",
        "scene_change",
        "weather",
        "clothing",
        "segformer",
    ]
    assert rates(mocks) == [
        ("face", 1.0),
        ("scene_change", 1.0),
        ("weather", 1.0),
        ("clothing", 1.0),
        ("segformer", 1.0),
    ]


def test_t08_weather_without_output_is_unattempted():
    """ship 7405: result.weather_classification None -> no entry and NO rate call at all."""
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(PERSON)], images={None: IMG}, camera=CAM, stub=stub_result()
    )
    assert "weather" not in tracking.successful_models
    assert rate_calls(mocks, "weather") == []


def test_t08_weather_error_with_stale_output_rates_zero():
    """ship 7405-7409: a weather error wins over a stale weather_classification object."""
    stub = stub_result(
        errors=["weather_classification failed: siglip timeout"],
        weather_classification=object(),
    )
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(PERSON)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.failed_models == ["weather"]
    assert "weather" not in tracking.successful_models
    assert rates(mocks) == [
        ("face", 1.0),
        ("scene_change", 1.0),
        ("weather", 0.0),
        ("clothing", 1.0),
        ("segformer", 1.0),
    ]
    assert tracking.status == M.EnrichmentStatus.PARTIAL


def test_t08_weather_error_without_output_still_rates_zero():
    """ship 7408-7409: the elif branch fires on the failed name alone."""
    stub = stub_result(errors=["weather_classification failed: siglip timeout"])
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(PERSON)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.failed_models == ["weather"]
    assert rates(mocks) == [
        ("face", 1.0),
        ("scene_change", 1.0),
        ("weather", 0.0),
        ("clothing", 1.0),
        ("segformer", 1.0),
    ]


# -------------------------------------------------------- vehicle damage + class (7425-7437)


def test_t08_vehicle_damage_and_class_success_append_and_rate_one():
    """ship 7425-7435: a vehicle batch with a shared image succeeds license_plate, scene_change,
    vehicle_damage and vehicle_class, each at rate 1.0, in gate order."""
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(CAR)], images={None: IMG}, camera=CAM, stub=stub_result()
    )
    assert tracking.successful_models == [
        "license_plate",
        "scene_change",
        "vehicle_damage",
        "vehicle_class",
    ]
    assert rates(mocks) == [
        ("license_plate", 1.0),
        ("scene_change", 1.0),
        ("vehicle_damage", 1.0),
        ("vehicle_class", 1.0),
    ]
    assert tracking.failed_models == []
    assert tracking.status == M.EnrichmentStatus.FULL


def test_t08_vehicle_damage_failure_rates_zero_and_keeps_vehicle_class():
    """ship 7429-7430: 'vehicle_damage_detection failed:' -> failed, 0.0; vehicle_class unaffected."""
    stub = stub_result(errors=["vehicle_damage_detection failed: yolov11 oom"])
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(CAR)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.failed_models == ["vehicle_damage"]
    assert tracking.errors == {"vehicle_damage": "vehicle_damage_detection failed: yolov11 oom"}
    assert tracking.successful_models == ["license_plate", "scene_change", "vehicle_class"]
    mocks["record_enrichment_failure"].assert_called_once_with("vehicle_damage")
    assert rates(mocks) == [
        ("license_plate", 1.0),
        ("scene_change", 1.0),
        ("vehicle_damage", 0.0),
        ("vehicle_class", 1.0),
    ]


def test_t08_vehicle_class_failure_rates_zero_and_keeps_vehicle_damage():
    """ship 7436-7437: 'vehicle_classification failed:' maps to model 'vehicle_class', rate 0.0."""
    stub = stub_result(errors=["vehicle_classification failed: resnet weights missing"])
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(CAR)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.failed_models == ["vehicle_class"]
    assert tracking.successful_models == ["license_plate", "scene_change", "vehicle_damage"]
    assert rates(mocks) == [
        ("license_plate", 1.0),
        ("scene_change", 1.0),
        ("vehicle_damage", 1.0),
        ("vehicle_class", 0.0),
    ]


# --------------------------------------------------------- image quality (7439-7444)


def test_t08_image_quality_success_requires_result_object():
    """ship 7439-7442: needs no image_quality error AND result.image_quality is not None."""
    absent, mocks_a = run_tracking(
        pipeline(), dets=[det(CAR)], images={None: IMG}, camera=CAM, stub=stub_result()
    )
    assert "image_quality" not in absent.successful_models
    assert rate_calls(mocks_a, "image_quality") == []

    present, mocks_b = run_tracking(
        pipeline(),
        dets=[det(CAR)],
        images={None: IMG},
        camera=CAM,
        stub=stub_result(image_quality=object()),
    )
    assert present.successful_models == [
        "license_plate",
        "scene_change",
        "vehicle_damage",
        "vehicle_class",
        "image_quality",
    ]
    assert rates(mocks_b) == [
        ("license_plate", 1.0),
        ("scene_change", 1.0),
        ("vehicle_damage", 1.0),
        ("vehicle_class", 1.0),
        ("image_quality", 1.0),
    ]


def test_t08_image_quality_failure_rates_zero():
    """ship 7443-7444: 'image_quality_assessment failed:' -> failed, 0.0, no success entry."""
    stub = stub_result(
        errors=["image_quality_assessment failed: pyiqa numpy2 break"],
        image_quality=object(),
    )
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(CAR)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.failed_models == ["image_quality"]
    assert "image_quality" not in tracking.successful_models
    assert rates(mocks) == [
        ("license_plate", 1.0),
        ("scene_change", 1.0),
        ("vehicle_damage", 1.0),
        ("vehicle_class", 1.0),
        ("image_quality", 0.0),
    ]


def test_t08_image_quality_error_without_output_still_rates_zero():
    """ship 7443-7444 (elif branch): the failed name alone is enough."""
    stub = stub_result(errors=["image_quality_assessment failed: pyiqa numpy2 break"])
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(CAR)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.failed_models == ["image_quality"]
    assert rate_calls(mocks, "image_quality") == [("image_quality", 0.0)]


# --------------------------------------------------------------- depth (7453-7458)


def test_t08_depth_success_requires_depth_analysis():
    """ship 7453-7456: needs no depth error AND result.depth_analysis present."""
    absent, mocks_a = run_tracking(
        pipeline(), dets=[det(CAR)], images={None: IMG}, camera=CAM, stub=stub_result()
    )
    assert "depth" not in absent.successful_models
    assert rate_calls(mocks_a, "depth") == []

    present, mocks_b = run_tracking(
        pipeline(),
        dets=[det(CAR)],
        images={None: IMG},
        camera=CAM,
        stub=stub_result(depth_analysis=object()),
    )
    assert present.successful_models == [
        "license_plate",
        "scene_change",
        "vehicle_damage",
        "vehicle_class",
        "depth",
    ]
    assert rates(mocks_b) == [
        ("license_plate", 1.0),
        ("scene_change", 1.0),
        ("vehicle_damage", 1.0),
        ("vehicle_class", 1.0),
        ("depth", 1.0),
    ]


def test_t08_depth_failure_rates_zero():
    """ship 7457-7458: 'depth_estimation failed:' -> failed 'depth', rate 0.0."""
    stub = stub_result(
        errors=["depth_estimation failed: metric depth oom"], depth_analysis=object()
    )
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(CAR)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.failed_models == ["depth"]
    assert "depth" not in tracking.successful_models
    assert rates(mocks) == [
        ("license_plate", 1.0),
        ("scene_change", 1.0),
        ("vehicle_damage", 1.0),
        ("vehicle_class", 1.0),
        ("depth", 0.0),
    ]


# ----------------------------------------------------------- status + payload tail (7461-7485)


def test_t08_batch_status_records_the_status_value():
    """ship 7461-7464: record_enrichment_batch_status is called once with status.value."""
    tracking, mocks = run_tracking(
        pipeline(), dets=[det(PERSON)], images={None: IMG}, camera=CAM, stub=stub_result()
    )
    assert tracking.status == M.EnrichmentStatus.FULL
    assert mocks["record_enrichment_batch_status"].call_args_list == [mock.call("full")]


def test_t08_partial_metric_fires_only_for_partial():
    """ship 7465-7466: record_enrichment_partial_batch only when compute_status -> PARTIAL."""
    full, mocks_a = run_tracking(
        pipeline(), dets=[det(PERSON)], images={None: IMG}, camera=CAM, stub=stub_result()
    )
    assert full.status == M.EnrichmentStatus.FULL
    mocks_a["record_enrichment_partial_batch"].assert_not_called()

    partial, mocks_b = run_tracking(
        pipeline(),
        dets=[det(PERSON)],
        images={None: IMG},
        camera=CAM,
        stub=stub_result(errors=["vision_extraction failed: boom"]),
    )
    assert partial.status == M.EnrichmentStatus.PARTIAL
    mocks_b["record_enrichment_partial_batch"].assert_called_once_with()
    assert mocks_b["record_enrichment_batch_status"].call_args_list == [mock.call("partial")]


def test_t08_tracking_data_field_is_the_enrichment_result():
    """ship 7469-7475: data=result by identity, with errors/failed/successful wired in."""
    stub = stub_result(errors=["vision_extraction failed: boom"])
    tracking, _ = run_tracking(
        pipeline(), dets=[det(PERSON)], images={None: IMG}, camera=CAM, stub=stub
    )
    assert tracking.data is stub
    assert tracking.has_data is True
    assert tracking.errors == {"vision": "vision_extraction failed: boom"}
    assert tracking.failed_models == ["vision"]
    assert tracking.successful_models == ["face", "scene_change", "clothing", "segformer"]
    assert tracking.to_dict() == {
        "status": "partial",
        "successful_models": ["face", "scene_change", "clothing", "segformer"],
        "failed_models": ["vision"],
        "errors": {"vision": "vision_extraction failed: boom"},
        "success_rate": 0.8,
    }


def test_t08_tracking_info_log_message_is_pinned(caplog):
    """ship 7477-7483: one INFO line carrying camera id, status, counts and success-rate percent."""
    stub = stub_result(errors=["vision_extraction failed: boom"])
    pip = pipeline()  # built before caplog opens: the ctor emits its own INFO line
    eb = mock.AsyncMock(return_value=stub)
    caplog.clear()  # as above: at_level tunes levels, it does not reset the buffer
    with (
        caplog.at_level(logging.INFO, logger="backend.services.enrichment_pipeline"),
        metrics(),
        mock.patch.object(M.EnrichmentPipeline, "enrich_batch", new=eb),
    ):
        asyncio.run(pip.enrich_batch_with_tracking([det(PERSON)], {None: IMG}, CAM))
    msgs = [r.getMessage() for r in ep_logs(caplog)]
    assert msgs == [
        "Enrichment tracking for camera cam-front: status=partial, success=4, failed=1, success_rate=80%"
    ], msgs


def test_t08_uncaught_errors_propagate_and_run_parallel_once():
    """Ship wiring: the tracking wrapper adds no try/except, so an enrich_batch raise escapes."""
    pip = pipeline()
    boom = mock.AsyncMock(side_effect=RuntimeError("enrichment exploded"))
    with (
        metrics(),
        mock.patch.object(M.EnrichmentPipeline, "enrich_batch", new=boom),
        pytest.raises(RuntimeError, match="enrichment exploded"),
    ):
        asyncio.run(pip.enrich_batch_with_tracking([det(PERSON)], {None: IMG}, CAM))
    assert boom.await_count == 1
