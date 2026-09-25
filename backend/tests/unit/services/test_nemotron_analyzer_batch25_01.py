"""Batch-25 kill battery, part 01 — cluster "NemotronAnalyzer.analyze_batch#chunk2".

All 129 keys are mutants of NemotronAnalyzer.analyze_batch
(backend/services/nemotron_analyzer.py:2341-3141). Every assertion below was
produced by running the SHIPPED function and recording what it actually does
(probe: /tmp/wp-batch25/probes/ad01/probe_harness.py), never by asserting what
an idealized implementation "should" do.

Families (all pinned through one driven pipeline per test):
  * detections_for_enrichment payload literal (2536-2558)      -> 26 keys
  * enrichment-data map det_id / det_enrichment (2585-2595)    ->  2 keys
  * household block seed/call/DEBUG record (2601-2615)          -> 19 keys
  * trajectory call (2735-2737)                               ->  6 keys
  * nemotron_analysis.start span (2749-2762)                  -> 23 keys
  * tail spans' detection.count key (3078, 3136)              ->  4 keys
  * _det_dicts confidence/class summary (2766-2773)           ->  8 keys
  * "Starting LLM analysis" INFO record (2777-2782)           -> 13 keys
  * _call_llm keyword list (2783-2794)                        -> 14 keys
  * llm_duration_ms/seconds on success (2795-2796) and
    exception (2820-2821) paths                               -> 10 keys
  * enriched_context at audit/snapshot/sources (2956/2988/2994) -> 4 keys

Key identity is occurrence order among identical minus/plus shapes
(OCCURRENCE-TWIN RULE): every twin of a shape group is carried in full.
"""

from __future__ import annotations

import os

# Mirror the minimum env vars backend/tests/conftest.py sets (copy, don't invent)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.unit

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.services.context_enricher import EnrichedContext
from backend.services.enrichment_pipeline import (
    BoundingBox,
    EnrichmentResult,
    EnrichmentStatus,
    EnrichmentTrackingResult,
    LicensePlateResult,
)
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.services.pipeline_quality_audit_service import PipelineQualityAuditService
from backend.services.prompt_auto_tuner import PromptAutoTuner

BATCH = "b25_part01_batch"
CAM = "b25_probe_cam"
CAM_NAME = "Probe Cam"
T1 = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
T2 = datetime(2025, 12, 23, 14, 31, 0, tzinfo=UTC)
LOG = "backend.services.nemotron_analyzer"

DEFAULT_RISK = {
    "risk_score": 71,
    "risk_level": "high",
    "summary": "probe summary",
    "reasoning": "probe reasoning",
}


@pytest.fixture
def mock_redis_client():
    from backend.core.redis import RedisClient

    mock_client = MagicMock(spec=RedisClient)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.publish = AsyncMock(return_value=1)
    return mock_client


@pytest.fixture
def mock_settings():
    from backend.core.config import Settings

    mock = MagicMock(spec=Settings)
    # P0.3 flags (#6678): pydantic v2 field names are not in
    # dir(Settings), so a spec'd mock must pin them explicitly.
    mock.nemotron_constrained_decoding_enabled = False
    mock.nemotron_constrained_fail_closed = True
    mock.nemotron_constrained_probe_enabled = True
    mock.nemotron_constrained_probe_required_build = None
    mock.nemotron_verification_engine = "llama.cpp"
    mock.nemotron_model_id = "Nemotron-3-Nano-30B-A3B-Q4_K_M"
    mock.nemotron_url = "http://localhost:8091"
    mock.nemotron_api_key = None
    mock.ai_connect_timeout = 10.0
    mock.nemotron_read_timeout = 120.0
    mock.ai_health_timeout = 5.0
    mock.nemotron_max_retries = 2
    mock.severity_low_max = 29
    mock.severity_medium_max = 59
    mock.severity_high_max = 84
    mock.nemotron_context_window = 4096
    mock.nemotron_max_output_tokens = 1536
    mock.context_utilization_warning_threshold = 0.80
    mock.context_truncation_enabled = True
    mock.llm_tokenizer_encoding = "cl100k_base"
    mock.image_quality_enabled = False
    mock.ai_warmup_enabled = True
    mock.ai_cold_start_threshold_seconds = 300.0
    mock.nemotron_warmup_prompt = "Test warmup prompt"
    mock.scene_change_resize_width = 640
    mock.use_enrichment_service = False
    mock.ai_max_concurrent_inferences = 4
    mock.nemotron_use_guided_json = False
    mock.nemotron_guided_json_fallback = True
    mock.batch_coalescing_enabled = False
    mock.batch_coalescing_max_size = 10
    mock.batch_coalescing_time_window = 5.0
    mock.priority_queue_enabled = False
    mock.priority_high_labels = ["weapon", "intruder", "fire"]
    mock.priority_medium_labels = ["person", "unknown"]
    mock.background_evaluation_enabled = False
    return mock


@pytest.fixture
def analyzer(mock_redis_client, mock_settings):
    with (
        patch(
            "backend.services.nemotron_analyzer.get_settings",
            return_value=mock_settings,
            autospec=True,
        ),
        patch("backend.services.severity.get_settings", return_value=mock_settings, autospec=True),
        patch(
            "backend.services.token_counter.get_settings", return_value=mock_settings, autospec=True
        ),
        patch("backend.core.config.get_settings", return_value=mock_settings, autospec=True),
        patch(
            "backend.services.inference_semaphore.get_settings",
            return_value=mock_settings,
            autospec=True,
        ),
    ):
        from backend.services.analyzer_facade import reset_analyzer_facade
        from backend.services.inference_semaphore import reset_inference_semaphore
        from backend.services.severity import reset_severity_service
        from backend.services.token_counter import reset_token_counter

        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()
        yield NemotronAnalyzer(redis_client=mock_redis_client)
        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()


def det(det_id, obj_type, confidence, *, bbox=None, video=None, track=None, at=T1):
    kw = {}
    if bbox is not None:
        kw.update(zip(("bbox_x", "bbox_y", "bbox_width", "bbox_height"), bbox, strict=True))
    if video is not None:
        kw.update(zip(("video_width", "video_height"), video, strict=True))
    return Detection(
        id=det_id,
        camera_id=CAM,
        file_path=f"/export/foscam/{CAM}/img{det_id}.jpg",
        detected_at=at,
        object_type=obj_type,
        confidence=confidence,
        track_id=track,
        **kw,
    )


def base_dets():
    """Two detections: one fully populated, one with no type/confidence/bbox."""
    return [
        det(9001, "person", 0.95, bbox=(10, 20, 100, 50), video=(1920, 1080), track="trk-1", at=T1),
        det(9002, None, None, at=T2),
    ]


def three_dets():
    """base_dets plus a type-less detection that DOES carry a confidence."""
    return [*base_dets(), det(9003, None, 0.5, at=T2)]


def plate_tracking():
    """Enrichment whose only per-detection data belongs to detection 9001."""
    return EnrichmentTrackingResult(
        status=EnrichmentStatus.FULL,
        successful_models=["license_plate"],
        failed_models=[],
        errors={},
        data=EnrichmentResult(
            license_plates=[
                LicensePlateResult(
                    bbox=BoundingBox(x1=100, y1=100, x2=200, y2=150),
                    text="ABC123",
                    confidence=0.95,
                    ocr_confidence=0.90,
                    source_detection_id=9001,
                )
            ],
            faces=[],
            processing_time_ms=75.0,
        ),
    )


def empty_tracking():
    return EnrichmentTrackingResult(
        status=EnrichmentStatus.FULL,
        successful_models=["face"],
        failed_models=[],
        errors={},
        data=EnrichmentResult(license_plates=[], faces=[], processing_time_ms=50.0),
    )


TAMPERED = SimpleNamespace(acknowledged=False, change_type="view_tampered", similarity_score=0.5)
TAMPER_CONTEXT = (
    "## CAMERA HEALTH ALERT\n"
    "Possible TAMPERING detected (similarity: 50%)\n"
    "CRITICAL: Verify camera integrity\n"
    "ESCALATION: If unknown person detected, escalate to CRITICAL priority"
)


class FakeTime:
    """Clocked stand-in for the ``time`` attribute of backend.services.nemotron_analyzer.

    ``time()`` walks ``seq`` (repeating its last value), so every
    ``time.time()`` call site in analyze_batch gets a deterministic reading and
    the duration arithmetic is computable to the millisecond.
    """

    def __init__(self, seq):
        self.seq = list(seq)
        self.i = 0

    def time(self):
        value = self.seq[min(self.i, len(self.seq) - 1)]
        self.i += 1
        return value

    def monotonic(self):  # pragma: no cover - not reached on this path
        return self.time()


class Run:
    """Observables captured from one analyze_batch() drive."""

    def __init__(self) -> None:
        self.spans: list[tuple[str, object]] = []
        self.enrich = None
        self.hh = None
        self.traj = None
        self.llm = None
        self.observe = None
        self.event = None
        self.session = None
        self.records: list[logging.LogRecord] = []

    def span(self, name):
        for n, attrs in self.spans:
            if n == name:
                return attrs
        return None

    def span_names(self):
        return [n for n, _ in self.spans]

    def added(self, cls):
        return [
            call.args[0]
            for call in self.session.add.call_args_list
            if isinstance(call.args[0], cls)
        ]


async def drive(
    analyzer,
    caplog,
    *,
    dets=None,
    tracking=None,
    enriched_context=None,
    scene_changes=(),
    tuning="",
    household="HH-CTX",
    household_raises=False,
    llm_error=None,
    fake_time=None,
    audit_service=None,
):
    """Run analyze_batch against shipped code with every external seam mocked.

    Returns a :class:`Run` of captured observables. Nothing here asserts — the
    tests do the pinning, so a mutant that changes one literal surfaces as one
    named failed assertion.
    """
    caplog.set_level(logging.DEBUG, logger=LOG)
    run = Run()

    dets = base_dets() if dets is None else dets
    tracking = plate_tracking() if tracking is None else tracking

    session = AsyncMock(spec=AsyncSession)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    camera = Camera(id=CAM, name=CAM_NAME, folder_path=f"/export/foscam/{CAM}", status="online")
    cam_res = MagicMock()
    cam_res.scalar_one_or_none.return_value = camera
    det_res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = dets
    det_res.scalars.return_value = scalars
    generic = MagicMock()
    queue = [cam_res, det_res]

    async def execute(query, *args, **kwargs):
        if queue:
            return queue.pop(0)
        return generic

    session.execute = execute
    session.add = MagicMock()
    session.flush = AsyncMock()

    def record_span(name, attributes=None, timestamp_ns=None):
        run.spans.append((name, attributes))

    async def captured_enrich(batch_id, detections_for_enrichment, camera_id=None):
        run.enrich = SimpleNamespace(
            batch_id=batch_id, dfe=detections_for_enrichment, camera_id=camera_id
        )
        return tracking

    async def captured_llm(**kwargs):
        if llm_error is not None:
            raise llm_error
        return dict(DEFAULT_RISK)

    async def captured_household(detections_data, enrichment_result):
        run.hh = SimpleNamespace(data=detections_data, result=enrichment_result)
        if household_raises:
            raise RuntimeError("boom")
        return household

    async def captured_trajectory(detections_data, enrichment_result, camera_id):
        run.traj = SimpleNamespace(data=detections_data, result=enrichment_result, camera=camera_id)

    def observe_duration(service, seconds):
        run.observe = (service, seconds)

    tuner = MagicMock(spec=PromptAutoTuner)
    tuner.get_tuning_context = AsyncMock(return_value=tuning)

    patches = [
        patch("backend.services.nemotron_analyzer.get_session", autospec=True),
        patch(
            "backend.services.nemotron_analyzer.add_span_event",
            autospec=True,
            side_effect=record_span,
        ),
        patch(
            "backend.services.nemotron_analyzer.observe_ai_request_duration",
            autospec=True,
            side_effect=observe_duration,
        ),
        patch.object(
            analyzer, "_get_enriched_context", autospec=True, return_value=enriched_context
        ),
        patch.object(
            analyzer, "_get_recent_scene_changes", autospec=True, return_value=list(scene_changes)
        ),
        patch.object(
            analyzer, "_get_household_context", autospec=True, side_effect=captured_household
        ),
        patch.object(
            analyzer,
            "_enrich_with_trajectory_analysis",
            autospec=True,
            side_effect=captured_trajectory,
        ),
        patch.object(analyzer, "_broadcast_event", autospec=True, return_value=None),
        patch.object(analyzer, "_trigger_event_created_webhook", autospec=True, return_value=None),
        patch.object(
            analyzer, "_get_enrichment_result_from_data", autospec=True, side_effect=captured_enrich
        ),
        patch.object(analyzer, "_call_llm", autospec=True, side_effect=captured_llm),
        patch(
            "backend.services.prompt_auto_tuner.get_prompt_auto_tuner",
            autospec=True,
            return_value=tuner,
        ),
    ]
    if fake_time is not None:
        patches.append(patch("backend.services.nemotron_analyzer.time", new=fake_time))
    if audit_service is not None:
        patches.append(
            patch(
                "backend.services.pipeline_quality_audit_service.get_audit_service",
                new=MagicMock(return_value=audit_service),
            )
        )

    started = [p.start() for p in patches]
    try:
        started[0].return_value = session  # get_session() -> our AsyncMock session
        run.session = session
        run.llm = analyzer._call_llm  # the live autospec mock, captured before stop()
        run.event = await analyzer.analyze_batch(
            batch_id=BATCH, camera_id=CAM, detection_ids=[d.id for d in dets]
        )
    finally:
        for p in patches:
            p.stop()
    run.records = [r for r in caplog.records if r.name == LOG]
    return run


# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detection_payload_literal(analyzer, caplog):
    """Kills 26 keys of backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch:
    __mutmut_171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183,
    184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196.

    Shipped (2536-2558) hands the enrichment pipeline one dict per detection
    with exactly these keys/values, and the bounding_box sub-dict ONLY when
    ``d.bbox_x is not None``. Every key rename (XXfoo / FOO upper), and the
    ``and False`` / ``or True`` / ``is None`` flips of the bbox guard, change
    this payload — exact equality against the shipped shape kills all of them.
    Detection 9002 (bbox_x None) is what separates the ``or True`` widening
    (177) from shipped.
    """
    run = await drive(analyzer, caplog, tracking=empty_tracking())

    assert run.enrich is not None
    assert run.enrich.batch_id == BATCH
    assert run.enrich.camera_id == CAM
    assert run.enrich.dfe == [
        {
            "id": 9001,
            "object_type": "person",
            "confidence": 0.95,
            "file_path": f"/export/foscam/{CAM}/img9001.jpg",
            "bounding_box": {"bbox_x": 10, "bbox_y": 20, "bbox_width": 100, "bbox_height": 50},
            "video_width": 1920,
            "video_height": 1080,
            "detected_at": T1,
            "track_id": "trk-1",
            "camera_id": CAM,
        },
        {
            "id": 9002,
            "object_type": None,
            "confidence": None,
            "file_path": f"/export/foscam/{CAM}/img9002.jpg",
            "bounding_box": None,
            "video_width": None,
            "video_height": None,
            "detected_at": T2,
            "track_id": None,
            "camera_id": CAM,
        },
    ]


@pytest.mark.asyncio
async def test_enrichment_data_map_keyed_by_detection_id(analyzer, caplog):
    """Kills 2 keys of backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch:
    __mutmut_210 (``det_id = int(det_data["id"])`` -> None) and __mutmut_214
    (``det_enrichment = enrichment_result.to_storage_dict(det_id)`` -> None).

    Shipped (2585-2595) maps ``int(det_data["id"]) -> to_storage_dict(det_id)``
    and logs one DEBUG per populated detection. With the only plate attributed
    to detection 9001 the shipped map holds exactly one entry: the debug record
    reads detection_id 9001 / enrichment_keys ["license_plate"] and the
    ``database_write.complete`` span reports ``enrichment_data.count == 1``.
    Both mutants populate nothing (count 0, no debug record).
    """
    run = await drive(analyzer, caplog)

    debugs = [
        r for r in run.records if r.getMessage() == "Prepared enrichment data for detection 9001"
    ]
    assert len(debugs) == 1
    assert getattr(debugs[0], "detection_id", None) == 9001
    assert getattr(debugs[0], "enrichment_keys", None) == ["license_plate"]

    tail = run.span("database_write.complete")
    assert tail is not None
    assert tail["enrichment_data.count"] == 1
    assert run.event.risk_score == 71


@pytest.mark.asyncio
async def test_household_failure_keeps_empty_string_seed(analyzer, caplog):
    """Kills 2 keys of backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch:
    __mutmut_216 (``household_context = ""`` -> None) and __mutmut_217
    (``household_context = ""`` -> "XXXX").

    The seed is only observable when the household call RAISES (shipped
    2601-2615 swallows and continues). Shipped then forwards ``""`` to the LLM
    and reports has_household_context False; None/XXXX forward divergent values
    (217 additionally flips the span boolean to True).
    """
    run = await drive(analyzer, caplog, household_raises=True)

    warnings = [r for r in run.records if r.getMessage() == "Failed to perform household matching"]
    assert len(warnings) == 1
    assert getattr(warnings[0], "error", None) == "boom"

    assert run.llm.call_args.kwargs["household_context"] == ""
    assert run.span("nemotron_analysis.start")["has_household_context"] is False


@pytest.mark.asyncio
async def test_household_call_and_debug_record(analyzer, caplog):
    """Kills 17 keys of backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch
    (household block, shipped 2601-2611): __mutmut_218, 219, 220, 221, 222 (the
    ``_get_household_context`` call and its two arguments) and __mutmut_223,
    224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234 (the DEBUG record's
    message and its ``extra`` dict).

    Shipped calls ``_get_household_context(detections_for_enrichment,
    enrichment_result)`` — the very list object built for enrichment, plus the
    extracted EnrichmentResult — and on a truthy result logs
    ``"Household matching completed for batch"`` at DEBUG with
    ``extra={"batch_id": ..., "has_matches": bool(household_context)}``. The
    record is looked up via the has_matches attribute (intact under message-only
    mutants) and every extra key; the autospec seam turns the arity mutants
    (221/222) into a hidden TypeError, which the captured-call pins catch.
    """
    run = await drive(analyzer, caplog, household="HH-CTX")

    assert run.hh is not None
    assert run.hh.data is run.enrich.dfe
    assert isinstance(run.hh.result, EnrichmentResult)
    assert run.hh.result.has_license_plates

    assert run.llm.call_args.kwargs["household_context"] == "HH-CTX"

    matches = [r for r in run.records if getattr(r, "has_matches", None) is True]
    assert len(matches) == 1
    rec = matches[0]
    assert rec.levelno == logging.DEBUG
    assert rec.getMessage() == "Household matching completed for batch"
    assert getattr(rec, "batch_id", None) == BATCH


@pytest.mark.asyncio
async def test_trajectory_call_arguments(analyzer, caplog):
    """Kills 6 keys of backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch:
    __mutmut_236, 237, 238, 239, 240, 241.

    Shipped (2735-2737) calls ``_enrich_with_trajectory_analysis(
    detections_for_enrichment, enrichment_result, camera_id)`` inside a
    swallow-all try. The autospec seam converts the arity mutants (239/240/241)
    into a TypeError that the except branch hides, and the None-substitution
    mutants (236/237/238) only change WHICH object arrives — so the pin is the
    recorded call itself: identity of the detection list, the enrichment
    result, and the camera id string.
    """
    run = await drive(analyzer, caplog)

    assert run.traj is not None
    assert run.traj.data is run.enrich.dfe
    assert run.traj.result is not None and run.traj.result.has_license_plates
    assert run.traj.camera == CAM


@pytest.mark.asyncio
async def test_nemotron_analysis_start_span(analyzer, caplog):
    """Kills 23 keys of backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch
    at the ``nemotron_analysis.start`` span (shipped 2749-2762): __mutmut_243,
    244, 245, 246, 247, 248 (event-name / attribute-dict removal or rename) and
    __mutmut_253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265,
    266, 267, 268, 269 (individual attribute keys and value expressions).

    Exact attribute equality needs all three booleans non-degenerate:
    enriched_context IS None (259's ``is None`` inversion shows), an
    enrichment result IS present (262), household context is truthy (265's
    ``bool(None)``).
    """
    run = await drive(analyzer, caplog, household="HH-CTX")

    assert "nemotron_analysis.start" in run.span_names()
    assert run.span("nemotron_analysis.start") == {
        "batch.id": BATCH,
        "camera.id": CAM,
        "camera.name": CAM_NAME,
        "detection.count": 2,
        "has_enriched_context": False,
        "has_enrichment_result": True,
        "has_household_context": True,
        "batch_priority": "P2_NORMAL",
        "coalesced_count": 1,
    }


@pytest.mark.asyncio
async def test_tail_span_detection_count_key(analyzer, caplog):
    """Kills the occurrence twins __mutmut_639 and __mutmut_715
    (``"detection.count"`` -> ``"XXdetection.countXX"``) and __mutmut_640 and
    __mutmut_716 (``"detection.count"`` -> ``"DETECTION.COUNT"``) of
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch —
    shipped 3078 (``database_write.complete``) and 3136
    (``batch_analysis.complete``).

    Both spans also carry wall-clock durations, so the pin is the key SET plus
    the stable values — exactly what a key rename breaks.
    """
    run = await drive(analyzer, caplog)

    db_write = run.span("database_write.complete")
    assert db_write is not None
    assert set(db_write) == {"batch.id", "event.id", "detection.count", "enrichment_data.count"}
    assert db_write["detection.count"] == 2
    assert db_write["batch.id"] == BATCH

    done = run.span("batch_analysis.complete")
    assert done is not None
    assert set(done) == {
        "batch.id",
        "event.id",
        "camera.id",
        "risk.score",
        "risk.level",
        "detection.count",
        "total.duration_ms",
    }
    assert done["detection.count"] == 2


@pytest.mark.asyncio
async def test_detection_dicts_for_confidence_summary(analyzer, caplog):
    """Kills 8 keys of backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch:
    __mutmut_270 (whole ``_det_dicts`` comprehension -> None), 272
    (``"confidence"`` -> ``"CONFIDENCE"``), 273/274 (``"class_name"`` ->
    ``XXclass_nameXX``/``CLASS_NAME``), 275 (``or`` -> ``and``), 276/277
    (``"unknown"`` -> ``XXunknownXX``/``UNKNOWN``), 278 (``is not None`` ->
    ``is None`` filter flip).

    Shipped (2766-2773) builds one ``{"confidence": ..., "class_name":
    d.object_type or "unknown"}`` per detection THAT HAS a confidence and
    passes it as ``_call_llm(detection_dicts=...)``. The third detection has no
    object_type but confidence 0.5 (exposes 275/276/277); the confidence-less
    second row exposes 278; 270/272/273/274 break the equality directly.
    """
    run = await drive(analyzer, caplog, dets=three_dets(), tracking=empty_tracking())

    assert run.llm.call_args.kwargs["detection_dicts"] == [
        {"confidence": 0.95, "class_name": "person"},
        {"confidence": 0.5, "class_name": "unknown"},
    ]


@pytest.mark.asyncio
async def test_starting_llm_log_record(analyzer, caplog):
    """Kills 13 keys of backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch
    at the "Starting LLM analysis" INFO record (shipped 2777-2782):
    __mutmut_279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291.

    Shipped logs the lazy ``%d`` template with ``_threading.active_count()`` as
    its sole positional argument and ``extra={"batch_id": ..., "camera_id":
    ...}``. Pinning ``record.msg``, ``record.args`` and both extra attributes
    separately covers the message-only, argument-only and extra-only mutants.
    The record is found by msg prefix WITHOUT touching batch_id, so
    extra-removal mutants fail an assertion rather than the lookup.
    """
    run = await drive(analyzer, caplog)

    recs = [
        r for r in run.records if str(getattr(r, "msg", "")).startswith("Starting LLM analysis")
    ]
    assert len(recs) == 1
    rec = recs[0]
    assert rec.levelno == logging.INFO
    assert rec.msg == "Starting LLM analysis for batch (active threads: %d)"
    assert len(rec.args) == 1
    assert type(rec.args[0]) is int
    assert rec.args[0] >= 1
    assert rec.getMessage() == f"Starting LLM analysis for batch (active threads: {rec.args[0]})"
    assert getattr(rec, "batch_id", None) == BATCH
    assert getattr(rec, "camera_id", None) == CAM


@pytest.mark.asyncio
async def test_call_llm_keyword_arguments(analyzer, caplog):
    """Kills 14 keys of backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch
    at the ``_call_llm`` call (shipped 2783-2794): __mutmut_293, 294, 295, 296,
    297, 299, 300, 301, 302 (each keyword replaced by ``None``) and
    __mutmut_307, 309, 310, 311, 312 (each keyword deleted).

    Every keyword is driven to a NON-default, non-None value (enriched context
    present, one unacknowledged scene change, auto-tuning text, household text,
    populated detection dicts) so BOTH mutation directions diverge from
    shipped: "None" replaces the value, deletion makes the recorded kwargs
    shorter.
    """
    ctx = EnrichedContext(camera_name=CAM_NAME, camera_id=CAM)
    run = await drive(
        analyzer,
        caplog,
        enriched_context=ctx,
        scene_changes=[TAMPERED],
        tuning="TUNE-CTX",
        household="HH-CTX",
    )

    kwargs = run.llm.call_args.kwargs
    assert list(kwargs) == [
        "camera_name",
        "start_time",
        "end_time",
        "detections_list",
        "enriched_context",
        "enrichment_result",
        "camera_health_context",
        "auto_tuning_context",
        "household_context",
        "detection_dicts",
    ]
    assert kwargs["camera_name"] == CAM_NAME
    assert kwargs["start_time"] == "2025-12-23T14:30:00+00:00"
    assert kwargs["end_time"] == "2025-12-23T14:31:00+00:00"
    assert kwargs["detections_list"] == (
        "  1. 14:30:00 - person (confidence: 0.95 EXCELLENT)\n"
        "  2. 14:31:00 - unknown (confidence: N/A)"
    )
    assert kwargs["enriched_context"] is ctx
    assert kwargs["enrichment_result"] is not None
    assert kwargs["enrichment_result"].has_license_plates
    assert kwargs["camera_health_context"] == TAMPER_CONTEXT
    assert kwargs["auto_tuning_context"] == "TUNE-CTX"
    assert kwargs["household_context"] == "HH-CTX"
    assert kwargs["detection_dicts"] == [{"confidence": 0.95, "class_name": "person"}]


@pytest.mark.asyncio
async def test_llm_duration_success_path(analyzer, caplog):
    """Kills 5 keys of backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch
    (SUCCESS-path twins, shipped 2795-2796): __mutmut_313 (``llm_duration_ms =
    None``), __mutmut_315 (``* 1000`` -> ``/ 1000``), __mutmut_316 (``-`` ->
    ``+`` in ms expr), __mutmut_317 (``* 1000`` -> ``* 1001``), __mutmut_319
    (``-`` -> ``+`` in seconds expr).

    ``time`` is swapped for a scripted clock, so the shipped arithmetic is
    exactly computable: readings [.., 10.0 (llm_start), 11.5, 11.5, ..] give
    ``llm_duration_ms == 1500`` (published as the nemotron_analysis.complete
    span's analysis.duration_ms) and ``llm_duration_seconds == 1.5`` (published
    to observe_ai_request_duration("nemotron", 1.5)). Mutants: 313 -> None,
    315 -> 0, 316 -> 21500, 317 -> 1501, 319 -> 21.5.
    """
    clock = FakeTime([0.0, 10.0, 11.5, 11.5, 20.0, 20.0])
    run = await drive(analyzer, caplog, fake_time=clock)

    span = run.span("nemotron_analysis.complete")
    assert span is not None
    assert span["analysis.duration_ms"] == 1500
    assert run.observe == ("nemotron", 1.5)
    assert run.event.risk_score == 71


@pytest.mark.asyncio
async def test_llm_duration_failure_path(analyzer, caplog):
    """Kills the EXCEPTION-path occurrence twins __mutmut_365, __mutmut_367,
    __mutmut_368, __mutmut_369, __mutmut_371 of
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch
    (identical minus/plus shapes to 313/315/316/317/319; shipped 2820-2821).

    When ``_call_llm`` raises, shipped still times the call, observes the
    duration and logs the error with ``extra={"duration_ms": ...}`` before
    installing the 50/medium fallback. Same scripted clock pins the five
    mutants exactly as the success-path test pins its twins.
    """
    clock = FakeTime([0.0, 10.0, 11.5, 11.5, 20.0, 20.0])
    run = await drive(analyzer, caplog, llm_error=RuntimeError("llm down"), fake_time=clock)

    errors = [r for r in run.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].getMessage() == "LLM analysis failed for batch"
    assert getattr(errors[0], "duration_ms", None) == 1500
    assert run.observe == ("nemotron", 1.5)
    assert run.event.risk_score == 50
    assert run.event.risk_level == "medium"


@pytest.mark.asyncio
async def test_enriched_context_reaches_audit_and_observability(analyzer, caplog):
    """Kills 4 keys of backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch:
    __mutmut_536 and __mutmut_540 (``enriched_context=`` at
    create_partial_audit, shipped 2954-2957; None / deleted) and __mutmut_556,
    __mutmut_562 (``enriched_context=`` at _build_enrichment_snapshot 2986-2989
    and _build_context_sources 2992-2995, both -> None).

    With a real EnrichedContext in play: the spec'd audit service must receive
    that object (540's deletion makes the autospec validation raise, killing
    the audit call entirely — a caught TypeError but zero calls), and both
    helper outputs land on the LLMInteraction row where shipped records
    ``context_available: True``.
    """
    from backend.models.llm_interaction import LLMInteraction

    ctx = EnrichedContext(camera_name=CAM_NAME, camera_id=CAM)
    audit_service = create_autospec(PipelineQualityAuditService, instance=True)
    run = await drive(analyzer, caplog, enriched_context=ctx, audit_service=audit_service)

    assert audit_service.create_partial_audit.call_count == 1
    assert audit_service.create_partial_audit.call_args.kwargs["enriched_context"] is ctx

    interactions = run.added(LLMInteraction)
    assert len(interactions) == 1
    assert interactions[0].enrichment_snapshot["context_available"] is True
    assert interactions[0].enrichment_snapshot["enrichment_available"] is True
    assert interactions[0].context_sources["context_available"] is True
