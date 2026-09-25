"""Batch-25 chunk dead-11-1 kill battery — NemotronAnalyzer.analyze_detection_fast_path.

Chunk: /tmp/wp-batch25/chunks2/dead-11-1.json (50 keys, identical to
chunks/chunk-11.json). Full key form:
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁanalyze_detection_fast_path__mutmut_<n>

SCOPE — THIS FILE COVERS EXACTLY TWO KEYS: 368 and 377.
The other 48 keys of the chunk are killed by the sibling green battery
/tmp/wp-batch25/parts/test_batch25_11.py and are NOT duplicated here (each is
attributed in verdicts_/tmp/wp-batch25/chunks2/dead-11-1.json). 368 and 377 were
re-measured here and are NOT killed by that battery: running the whole of
test_batch25_11.py against mutmut body 368 and against body 377 gives
``17 passed`` (verified with the in-memory install described under RED-CHECK),
so its docstring claims for those two numbers are wrong and they remained
survivors. They are killed here.

MEASURED SHIPPED BEHAVIOR (probes run against the unmodified shipped function
through the harness below; the tests pin these values, production does not
bend):

  * Session 2 builds LLMInteraction(..., context_sources=context_sources)
    (nemotron_analyzer.py:3508-3514) and the value that lands on the ORM object
    is exactly whatever ``self._build_context_sources(...)`` returned — with the
    builder stubbed to ``{"SENT-368": 1}`` the shipped object carries
    ``{"SENT-368": 1}`` (probe3: MUTNUM=0). Body 368 deletes the
    ``context_sources=context_sources,`` argument line from the constructor, so
    the nullable JSONB column falls back to ``None`` (probe3: MUTNUM=368 ->
    ``LI.context_sources = None``). The column is read back off the object the
    code handed to ``session.add`` — an identity-preserving observable that no
    downstream code path can paper over.
  * right after that flush the shipped code logs
    ``logger.debug(f"Created LLMInteraction {llm_interaction.id} for event {event.id}")``
    (:3517-3519) with NO extra=. With llm_interaction.id / event.id injected as
    777 / 555 by the fake ``session.add``, the record's msg is exactly
    ``"Created LLMInteraction 777 for event 555"`` (probe3: MUTNUM=0). Body 377
    replaces the f-string with ``None``, so the SAME call still emits one DEBUG
    record but with ``record.msg is None`` (probe3: MUTNUM=377 -> ``None``) —
    i.e. there is no crash and no missing record, only the message identity is
    gone. That is why only an EXACT message-equality assertion kills it, and why
    the sibling battery (which never asserts this record's message) passed.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_dead-11-1.py -p no:cacheprovider -o addopts= -q

RED-CHECK (no source writes were used for this adjudication): install one mutmut
body in memory — exec the instrumented body
(/tmp/wp-batch25/instrumented-nemotron_analyzer.py, span from
/tmp/wp-batch25/instrumented.py.spans) with the shipped module __dict__ as its
globals, then swap ``NemotronAnalyzer.analyze_detection_fast_path`` — which is
exactly the mutant-body harness /tmp/wp-batch25/parts/test_batch25_10.py uses.
Driver: /tmp/wp-batch25/scratch/red11/ (conftest/plugin + results.txt). Expected:
368 fails test_fast_path_llminteraction_context_sources_reached_constructor,
377 fails test_fast_path_llminteraction_debug_message_identity. Applying the
shape to the source instead of the in-memory body also fails: 368's plus text
leaves the constructor call valid (observable above), so no "un-importable"
out is available for either key.

AUTOSPEC NOTE (WP4.2 ratchet): every unittest.mock patch CALL SITE in this file
carries autospec=True. The metric/time/log-context collaborators are not needed
by these two keys, so they are not patched at all — the only mocks are the
module-level ``get_session`` and the analyzer's own ``_call_llm`` /
``_build_context_sources`` / ``_get_facade`` / ``_broadcast_event`` /
``_trigger_event_created_webhook`` seams.

OCCURRENCE-TWIN RULE: no shape in this chunk occurs twice. Cross-checked against
feed.json functions[...].shapes — the multi-key fingerprints in this function
(61/109, 122/327/347/353, 134/159, 156/189, 234/326, 289/333, 325/359, ...) carry
keys outside 368..431, so 368 and 377 have no twins to carry.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# This file lives OUTSIDE the repo tree, so backend/tests/conftest.py does NOT
# apply. The minimum env vars are mirrored here BEFORE any backend import, with
# values copied verbatim from backend/tests/conftest.py:107 (:363, :385, :114)
# and backend/tests/unit/conftest.py:97-98.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")
os.environ.setdefault("API_KEY_ENABLED", "true")  # pragma: allowlist secret
os.environ.setdefault("API_KEYS", '["test-unit-api-key-12345"]')  # pragma: allowlist secret

from sqlalchemy.engine import Result, ScalarResult
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import Settings
from backend.core.redis import RedisClient
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.models.llm_interaction import LLMInteraction
from backend.services.nemotron_analyzer import NemotronAnalyzer

_NS = "backend.services.nemotron_analyzer"

_DETECTION_TIME = datetime(2025, 12, 23, 14, 45, 0, tzinfo=UTC)
_RISK_DATA = {
    "risk_score": 75,
    "risk_level": "high",
    "summary": "Suspicious activity detected near front door",
    "reasoning": "Person detected at unusual time with vehicle present",
}
_EVENT_ID = 555
_LLM_ID = 777
_AUDIT_ID = 999
# Injected return value of _build_context_sources; rides into the ORM object.
_CONTEXT_SOURCES = {"SENT-368": 1}

_STD_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)
# Attributes ContextFilter writes on every record (backend/core/logging.py) plus
# "message", cached by the pytest logging plugin. Constant, never chunk-relevant.
_CONTEXT_NOISE = frozenset(
    {
        "request_id",
        "correlation_id",
        "trace_id",
        "span_id",
        "connection_id",
        "task_id",
        "job_id",
        "hostname",
        "container_id",
        "app_version",
        "environment",
        "message",
    }
)


@pytest.fixture
def mock_redis_client():
    """Mock Redis client (mirrors repo test_nemotron_analyzer.py:43)."""
    client = MagicMock(spec=RedisClient)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.publish = AsyncMock(return_value=1)
    return client


@pytest.fixture
def mock_settings():
    """Settings mock, values copied from repo test_nemotron_analyzer.py:56.

    background_evaluation_enabled is set False so the shipped
    _enqueue_for_evaluation returns at its documented early exit.
    """
    mock = MagicMock(spec=Settings)
    values = {
        "nemotron_url": "http://localhost:8091",
        "nemotron_api_key": None,
        "ai_connect_timeout": 10.0,
        "nemotron_read_timeout": 120.0,
        "ai_health_timeout": 5.0,
        "nemotron_max_retries": 2,
        "severity_low_max": 29,
        "severity_medium_max": 59,
        "severity_high_max": 84,
        "nemotron_context_window": 4096,
        "nemotron_max_output_tokens": 1536,
        "context_utilization_warning_threshold": 0.80,
        "context_truncation_enabled": True,
        "llm_tokenizer_encoding": "cl100k_base",
        "image_quality_enabled": False,
        "ai_warmup_enabled": True,
        "ai_cold_start_threshold_seconds": 300.0,
        "nemotron_warmup_prompt": "Test warmup prompt",
        "scene_change_resize_width": 640,
        "use_enrichment_service": False,
        "ai_max_concurrent_inferences": 4,
        "nemotron_use_guided_json": False,
        "nemotron_guided_json_fallback": True,
        "batch_coalescing_enabled": False,
        "batch_coalescing_max_size": 10,
        "batch_coalescing_time_window": 5.0,
        "priority_queue_enabled": False,
        "priority_high_labels": ["weapon", "intruder", "fire"],
        "priority_medium_labels": ["person", "unknown"],
        "background_evaluation_enabled": False,
    }
    for name, value in values.items():
        setattr(mock, name, value)
    return mock


@pytest.fixture
def analyzer(mock_redis_client, mock_settings):
    """NemotronAnalyzer with every get_settings site patched (repo fixture :135)."""
    with (
        patch(f"{_NS}.get_settings", return_value=mock_settings, autospec=True),
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


def _session_ctx():
    """get_session() context mock: camera query, detection query, then inert.

    ``add`` assigns the primary keys shipped code reads straight back out of the
    objects it just added, so the test injects the identities that the
    LLMInteraction debug message interpolates (777) and the one whose
    context_sources column is the 368 observable (the LLMInteraction itself).
    """
    camera = Camera(
        id="front_door",
        name="Front Door Camera",
        folder_path="/export/foscam/front_door",
        status="online",
    )
    detection = Detection(
        id=42,
        camera_id="front_door",
        file_path="/export/foscam/front_door/alert_img.jpg",
        detected_at=_DETECTION_TIME,
        object_type="person",
        confidence=0.98,
    )
    session = AsyncMock(spec=AsyncSession)

    camera_result = MagicMock(spec=Result)
    camera_result.scalar_one_or_none.return_value = camera
    detection_result = MagicMock(spec=Result)
    detection_result.scalar_one_or_none.return_value = detection
    scalars = MagicMock(spec=ScalarResult)
    scalars.all.return_value = []
    inert_result = MagicMock(spec=Result)
    inert_result.scalars.return_value = scalars
    counter = {"n": 0}

    async def execute(query, *args, **kwargs):
        counter["n"] += 1
        if counter["n"] == 1:
            return camera_result
        if counter["n"] == 2:
            return detection_result
        return inert_result

    added: list[object] = []

    def add(obj):
        added.append(obj)
        if isinstance(obj, Event):
            obj.id = _EVENT_ID
        elif isinstance(obj, EventAudit):
            obj.id = _AUDIT_ID
        elif isinstance(obj, LLMInteraction):
            obj.id = _LLM_ID

    session.execute = execute
    session.add = add
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    ctx = AsyncMock(spec=AsyncSession)
    ctx.__aenter__.return_value = session
    ctx.__aexit__.return_value = None
    return ctx, added


def _drive(analyzer):
    """Run analyze_detection_fast_path("front_door", "42") once; collect records.

    Returns the records captured at DEBUG level and the objects handed to
    session.add. Everything the two keys do not touch is stubbed to a benign
    mock so the Session-2 block under test is reached and finishes.
    """
    records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def handle(self, record):
            record.derived = frozenset(record.__dict__) - _STD_RECORD_KEYS - _CONTEXT_NOISE
            records.append(record)

    handler = Collect()
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)

    facade = MagicMock()
    cache = MagicMock()
    cache.invalidate_event_stats = AsyncMock()
    facade.get_cache_service = AsyncMock(return_value=cache)

    ctx, added = _session_ctx()
    patchers = {
        "get_session": patch(f"{_NS}.get_session", autospec=True),
        "_call_llm": patch.object(
            analyzer, "_call_llm", new_callable=AsyncMock, return_value=dict(_RISK_DATA)
        ),
        "_build_context_sources": patch.object(
            analyzer, "_build_context_sources", autospec=True, return_value=_CONTEXT_SOURCES
        ),
        "_broadcast_event": patch.object(analyzer, "_broadcast_event", new_callable=AsyncMock),
        "_webhook": patch.object(
            analyzer, "_trigger_event_created_webhook", new_callable=AsyncMock
        ),
        "_get_facade": patch.object(analyzer, "_get_facade", autospec=True, return_value=facade),
    }
    started = {}
    try:
        for name, patcher in patchers.items():
            started[name] = patcher.start()
        started["get_session"].return_value = ctx
        returned = None
        exc = None
        try:
            returned = asyncio.run(analyzer.analyze_detection_fast_path("front_door", "42"))
        except BaseException as err:
            exc = err
        interactions = [o for o in added if isinstance(o, LLMInteraction)]
        return {
            "records": records,
            "added": added,
            "interaction": interactions[0] if interactions else None,
            "returned": returned,
            "exc": exc,
        }
    finally:
        for patcher in reversed(list(patchers.values())):
            patcher.stop()
        root.removeHandler(handler)
        root.setLevel(previous_level)


def test_fast_path_llminteraction_context_sources_reached_constructor(analyzer):
    """Kills mutmut_368 (full name = backend.services.nemotron_analyzer.
    xǁNemotronAnalyzerǁanalyze_detection_fast_path__mutmut_368).

    Body 368 deletes the ``context_sources=context_sources,`` argument from the
    Session-2 ``LLMInteraction(...)`` construction (shape: the kwarg line plus
    the closing paren -> just the closing paren). Shipped, the value returned by
    ``self._build_context_sources(...)`` is passed through and read back here off
    the object handed to ``session.add`` — with the builder stubbed to
    ``{"SENT-368": 1}`` (an injected identity, so the assertion cannot be
    satisfied by anything the mutant itself produced). Under 368 the kwarg is
    never passed and the nullable JSONB column is None, so the equality fails.
    The Event and the rest of the tail must still be intact: this test also
    proves the drive reached (and did not abort in) the LLMInteraction try block,
    which is what makes the missing argument observable rather than incidental.
    """
    run = _drive(analyzer)
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"
    assert run["returned"] is run["added"][0]

    li = run["interaction"]
    assert li is not None, "Session 2 must have added an LLMInteraction"
    assert li.event_id == _EVENT_ID
    assert li.raw_response == ""
    # measured shipped _build_enrichment_snapshot output for this scenario
    # (enrichment_tracking.has_data is False -> EnrichmentResult absent)
    assert li.enrichment_snapshot == {
        "detection_ids": [42],
        "enrichment_available": False,
        "context_available": False,
    }
    assert li.household_matches is None
    # THE 368 KILL
    assert li.context_sources == _CONTEXT_SOURCES
    assert li.context_sources is not None, "368 drops the constructor kwarg -> column None"

    # the block finished (no swallowed exception), so the observables above are
    # the shipped ones and not an early-exit artifact
    assert not [r for r in run["records"] if r.msg == "LLMInteraction creation failed"]


def test_fast_path_llminteraction_debug_message_identity(analyzer):
    """Kills mutmut_377 (full name = backend.services.nemotron_analyzer.
    xǁNemotronAnalyzerǁanalyze_detection_fast_path__mutmut_377).

    Body 377 replaces the f-string in
    ``logger.debug(f"Created LLMInteraction {llm_interaction.id} for event {event.id}")``
    with ``None``. Measured: the mutant still emits exactly one DEBUG record at
    that site (nothing crashes, no record is lost) — its ``record.msg`` is None.
    So the only observable is message identity, and an exact-equality assertion
    is the kill: with the ids injected as 777 / 555 by the fake ``session.add``,
    shipped emits ``"Created LLMInteraction 777 for event 555"`` exactly once and
    NO debug record with a None message. Under 377 the required message is absent
    and a None-msg record exists: both assertions fail. The sibling battery
    test_batch25_11.py never asserts this record, which is why 377 survived it.
    """
    run = _drive(analyzer)
    assert run["exc"] is None, f"shipped fast path must return, got {run['exc']!r}"

    expected = f"Created LLMInteraction {_LLM_ID} for event {_EVENT_ID}"
    hits = [r for r in run["records"] if r.msg == expected]
    assert len(hits) == 1, f"expected exactly one {expected!r} record, got {len(hits)}"
    assert hits[0].levelno == logging.DEBUG
    assert hits[0].derived == frozenset(), "shipped passes no extra= at this site"

    # 377's msg=None must not be silently present anywhere in this drive
    assert not [r for r in run["records"] if r.msg is None], "a None-msg record is mutant 377"
    # and the site ran for the interaction this test injected
    assert run["interaction"] is not None and run["interaction"].id == _LLM_ID
