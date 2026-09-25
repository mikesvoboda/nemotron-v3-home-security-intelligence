"""Batch-25 kill battery — chunk "NemotronAnalyzer.analyze_batch#chunk5" (4 keys).

All four survivors live in ONE dict: the final add_span_event("batch_analysis.complete", ...)
call of analyze_batch (shipped backend/services/nemotron_analyzer.py:3128-3138):

    add_span_event(
        "batch_analysis.complete",
        {
            "batch.id": batch_id,
            "event.id": event.id,
            "camera.id": camera_id,
            "risk.score": event.risk_score or 0,
            "risk.level": event.risk_level or "unknown",
            "detection.count": len(int_detection_ids),
            "total.duration_ms": total_duration_ms,
        },
    )

Shape groups (feed.json functions['xǁNemotronAnalyzerǁanalyze_batch'].shapes 465-468):
  713: "risk.level": event.risk_level or "XXunknownXX"
  714: "risk.level": event.risk_level or "UNKNOWN"
  717: "XXtotal.duration_msXX": total_duration_ms
  718: "TOTAL.DURATION_MS": total_duration_ms

Reachability of the `or` fallback (required for 713/714 to be killable, not equivalent):
Event.risk_level is `Mapped[str | None] = mapped_column(String, nullable=True)`
(backend/models/event.py:61) — no validator coerces it — and analyze_batch builds the
Event with risk_level=risk_data.get("risk_level", "medium") straight from the _call_llm
payload (nemotron_analyzer.py:2885) with no validation on that path (_validate_risk_data
runs INSIDE _call_llm, nemotron_analyzer.py:4224, which these tests patch out). A blank
risk_level therefore reaches the span-event dict and selects the fallback branch.

Kill seam: add_span_event is imported INTO the nemotron_analyzer module namespace
(nemotron_analyzer.py:82), so patching backend.services.nemotron_analyzer.add_span_event
(autospec) captures the exact attributes dict while leaving every sibling call
(batch_analysis.start, batch_priority.calculated, database_write.complete, ...) as a
no-op on the same spy. Same seam pattern as backend/tests/unit/services/
test_detector_client.py:2238.

No repo test or draft test asserts this span-event dict (grep: no add_span_event patch in
any backend/tests/unit/services/test_nemotron_*.py; the batch-25 draft battery never
drives analyze_batch), so none of the four keys is killed_by_draft.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_04.py -p no:cacheprovider -o addopts= -q
RED-CHECK (on a lane): apply each key individually, run the named test, expect failure.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# The part file lives outside the repo tree, so backend/tests/conftest.py does NOT
# apply. Mirror the minimum env vars that conftest sets BEFORE any backend import
# (values copied verbatim from backend/tests/conftest.py and the sibling lane probe).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

from sqlalchemy.engine import Result, ScalarResult
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.services.nemotron_analyzer import NemotronAnalyzer

_SPAN_TARGET = "backend.services.nemotron_analyzer.add_span_event"
_SESSION_TARGET = "backend.services.nemotron_analyzer.get_session"

_EXPECTED_COMPLETE_KEYS = {
    "batch.id",
    "event.id",
    "camera.id",
    "risk.score",
    "risk.level",
    "detection.count",
    "total.duration_ms",
}


@pytest.fixture
def mock_redis_client():
    """Mock Redis client (mirrors the repo test_nemotron_analyzer.py fixture)."""
    from backend.core.redis import RedisClient

    mock_client = MagicMock(spec=RedisClient)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.publish = AsyncMock(return_value=1)
    return mock_client


@pytest.fixture
def mock_settings():
    """Settings mock copied value-for-value from the repo analyze_batch harness."""
    from backend.core.config import Settings

    mock = MagicMock(spec=Settings)
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
    return mock


@pytest.fixture
def analyzer(mock_redis_client, mock_settings):
    """NemotronAnalyzer with every get_settings site patched (mirrors repo fixture)."""
    with (
        patch(
            "backend.services.nemotron_analyzer.get_settings",
            return_value=mock_settings,
            autospec=True,
        ),
        patch("backend.services.severity.get_settings", return_value=mock_settings, autospec=True),
        patch(
            "backend.services.token_counter.get_settings",
            return_value=mock_settings,
            autospec=True,
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


def _mock_camera() -> Camera:
    return Camera(
        id="front_door",
        name="Front Door Camera",
        folder_path="/export/foscam/front_door",
        status="online",
    )


def _mock_detections() -> list[Detection]:
    base_time = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
    return [
        Detection(
            id=1,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img1.jpg",
            detected_at=base_time,
            object_type="person",
            confidence=0.95,
        ),
        Detection(
            id=2,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img2.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
        ),
    ]


async def _run_analyze_batch(analyzer, risk_data: dict) -> dict:
    """Drive analyze_batch end-to-end (repo-harness mirror) and return the
    attributes dict of the final add_span_event("batch_analysis.complete", ...) call."""
    mock_camera = _mock_camera()
    detections = _mock_detections()

    mock_session = AsyncMock(spec=AsyncSession)

    mock_camera_result = MagicMock(spec=Result)
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    mock_detections_result = MagicMock(spec=Result)
    mock_detections_scalars = MagicMock(spec=ScalarResult)
    mock_detections_scalars.all.return_value = detections
    mock_detections_result.scalars.return_value = mock_detections_scalars

    call_count = 0
    mock_insert_result = MagicMock(spec=Result)

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        if call_count == 2:
            return mock_detections_result
        return mock_insert_result

    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    async def mock_call_llm(*args, **kwargs):
        return dict(risk_data)

    with (
        patch(_SPAN_TARGET, autospec=True) as span_spy,
        patch(_SESSION_TARGET, autospec=True) as mock_get_session,
        patch.object(analyzer, "_call_llm", side_effect=mock_call_llm, autospec=True),
    ):
        mock_context = AsyncMock(spec=AsyncSession)
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        event = await analyzer.analyze_batch(
            batch_id="batch_b25_04",
            camera_id="front_door",
            detection_ids=[1, 2],
        )

    # The pipeline must reach its terminal return for the span event to exist at all.
    assert event.batch_id == "batch_b25_04"

    complete_calls = [
        c.kwargs.get("attributes")
        if "attributes" in c.kwargs
        else (c.args[1] if len(c.args) > 1 else None)
        for c in span_spy.call_args_list
        if (c.args[0] if c.args else c.kwargs.get("name")) == "batch_analysis.complete"
    ]
    assert len(complete_calls) == 1, (
        "analyze_batch must emit exactly one batch_analysis.complete span event, got "
        f"{len(complete_calls)}"
    )
    attrs = complete_calls[0]
    assert isinstance(attrs, dict)
    return attrs


@pytest.mark.asyncio
async def test_batch_analysis_complete_span_attributes_exact_normal_risk_level(analyzer):
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_717
    and backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_718.

    Pins the shipped attribute-set and pass-through values of the terminal
    add_span_event("batch_analysis.complete", ...) dict when the event carries a
    populated risk level (risk_data risk_level="high" flows straight into the Event,
    so the `or` fallbacks are NOT taken): keys are exactly
    {batch.id, event.id, camera.id, risk.score, risk.level, detection.count,
    total.duration_ms} and risk.level == "high". Mutant 717 renames the duration key
    to "XXtotal.duration_msXX" and mutant 718 renames it to "TOTAL.DURATION_MS";
    either rename breaks the exact key-set equality below.
    """
    attrs = await _run_analyze_batch(
        analyzer,
        {
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Person and vehicle at unusual hour",
            "reasoning": "test harness",
        },
    )
    assert set(attrs) == _EXPECTED_COMPLETE_KEYS
    assert attrs["risk.level"] == "high"
    assert attrs["risk.score"] == 75
    assert attrs["batch.id"] == "batch_b25_04"
    assert attrs["camera.id"] == "front_door"
    assert attrs["detection.count"] == 2
    assert isinstance(attrs["total.duration_ms"], int)


@pytest.mark.asyncio
async def test_batch_analysis_complete_span_fallbacks_on_falsy_event_fields(analyzer):
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_713
    and backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_batch__mutmut_714
    (and, via the key-set equality, __mutmut_717 and __mutmut_718 too).

    Pins the shipped fallback branch of the terminal batch_analysis.complete span
    dict when the persisted event carries falsy risk fields: the _call_llm payload
    returns risk_score=0 with risk_level="" (reachable as shipped — Event.risk_level
    is nullable with no validator, backend/models/event.py:61, and analyze_batch
    copies the raw payload value at nemotron_analyzer.py:2885), so
    `event.risk_score or 0` yields 0 and `event.risk_level or "unknown"` yields
    exactly the lowercase literal "unknown". Mutant 713 emits "XXunknownXX" and
    mutant 714 emits "UNKNOWN" in that branch, breaking the equality assertion;
    the exact key-set assertion additionally kills the duration-key renamers 717/718.
    """
    attrs = await _run_analyze_batch(
        analyzer,
        {
            "risk_score": 0,
            "risk_level": "",
            "summary": "Nothing of note",
            "reasoning": "test harness",
        },
    )
    assert set(attrs) == _EXPECTED_COMPLETE_KEYS
    assert attrs["risk.level"] == "unknown"
    assert attrs["risk.score"] == 0
