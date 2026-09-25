"""Batch-25 FINAL tail-1 kill battery: NemotronAnalyzer._call_llm head region.

Chunk: /tmp/wp-batch25/chunks3/tail-1.json (25 keys). Every test pins SHIPPED
behavior of backend/services/nemotron_analyzer.py:3811-4267 measured by probe
/tmp/wp-batch25/probes/final_tail1/pa.py (no production code bends; the fakes
are collaborators only).

Keys killed here (docstrings name them):
  * ..._call_llm__mutmut_1
  * ..._call_llm__mutmut_10, _11, _12
  * ..._call_llm__mutmut_100, _101, _103, _104, _105, _106, _107, _108
  * ..._call_llm__mutmut_109, _110, _111
  * ..._call_llm__mutmut_113, _114, _115, _116, _117
  * ..._call_llm__mutmut_119, _120, _121, _122, _123

No existing battery covers this chunk: every /tmp/wp-batch25/parts/*.py that
mentions _call_llm only *drives* it as a collaborator of another function
(test_batch25_00.._13/_20 patch it, test_batch25_dead-10-*/dead-11-1 target
analyze_detection_fast_path, test_batch25_16 targets
_check_guided_json_support), and grep for these 25 exact keys across
/tmp/wp-batch25/parts/*.py, /tmp/wp-batch25/test_nemotron_analyzer_batch25.py
and backend/tests/unit/services/test_nemotron_*.py returns zero hits — so
nothing is classified killed_by_draft.

Collaborator swaps all carry autospec=True (sanitize_camera_name,
sanitize_detection_description, _build_prompt,
_validate_and_truncate_prompt, _get_facade, AIModelAttributes,
set_pipeline_context_attributes, add_span_attributes,
set_llm_inference_attributes, set_inference_result_attributes,
record_nemotron_tokens, get_calibration_monitor, time.monotonic,
asyncio.timeout). The two swaps that must deliver a REAL recording object
rather than a spec'd mock are direct assignments with restore in finally,
because autospec is unsatisfiable there by construction: `nem.tracer` (the
spec would be built from the very object the swap replaces) and the
instance-level `_check_guided_json_support` stub (an instance attribute that
does not exist on the class).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

REPO = str(__import__("pathlib").Path(__file__).resolve().parents[4])

# env values copied from backend/tests/conftest.py, not invented
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

if REPO not in sys.path:
    sys.path.insert(0, REPO)

import backend.services.nemotron_analyzer as nem
from backend.api.schemas.llm_response import RISK_ANALYSIS_JSON_SCHEMA
from backend.services.nemotron_analyzer import NemotronAnalyzer

LOGGER = "backend.services.nemotron_analyzer"
LLM_URL = "http://nim.test:8000/v1"
CAMERA_RAW = "Front Door"
SCHEMA_KEYS = list(RISK_ANALYSIS_JSON_SCHEMA.get("properties", {}).keys())

MSG_GUIDED_YES = "Using guided_json for structured LLM output"
MSG_NO_SUPPORT = "Endpoint does not support guided_json, using regex fallback"

PROMPT_SENT = "SENTINEL-PROMPT"
CAM_SENT = "SENTINEL-CAM"
DET_SENT = "SENTINEL-DET"

RISK_BODY = json.dumps(
    {
        "risk_score": 60,
        "risk_level": "high",
        "summary": "Unusual activity",
        "reasoning": "Person at odd hours",
    }
)

_RESERVED = set(vars(logging.LogRecord("p", 0, "p", 1, "m", None, None)).keys()) | {
    "message",
    "asctime",
    "taskName",
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
}


def extras(record: logging.LogRecord) -> dict:
    """The record's extra= payload as a whole dict (exact key set AND values)."""
    return {k: v for k, v in record.__dict__.items() if k not in _RESERVED}


# ---------------------------------------------------------------------------
# fakes (collaborators only — production code is never modified)
# ---------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeClient:
    """httpx.AsyncClient stand-in; post() is keyword-only for json/headers like
    the real signature, so a mutant that drops a keyword raises."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[tuple] = []

    async def post(self, url, *, json, headers):
        self.calls.append((url, json, headers))
        return FakeResponse(self.payload)


class FakeFacade:
    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(1)
        self.track_calls: list[dict] = []
        self.increment_calls = 0

    def get_inference_semaphore(self):
        return self._semaphore

    def get_cost_tracker(self):
        outer = self

        class _T:
            def track_llm_usage(self, **kwargs) -> None:
                outer.track_calls.append(kwargs)

            def increment_event_count(self) -> None:
                outer.increment_calls += 1

        return _T()


class RecordingSpan:
    def __init__(self, name) -> None:
        self.name = name
        self.attributes: dict = {}

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value

    def set_attributes(self, attrs) -> None:
        self.attributes.update(attrs)

    def record_exception(self, exc, attributes=None) -> None:
        return None

    def set_status(self, *a, **kw) -> None:
        return None

    def is_recording(self) -> bool:
        return True

    def add_event(self, *a, **kw) -> None:
        return None

    def end(self, *a, **kw) -> None:
        return None


class RecordingTracer:
    def __init__(self) -> None:
        self.spans: list[RecordingSpan] = []

    def start_as_current_span(self, name, *a, **kw):
        span = RecordingSpan(name)
        self.spans.append(span)

        class _CM:
            def __enter__(self):
                return span

            def __exit__(self, *exc):
                return False

        return _CM()


class _Recorder(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class Drive:
    """Every observable channel of one SHIPPED _call_llm run."""

    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)

    @property
    def span(self) -> RecordingSpan:
        assert len(self.tracer.spans) == 1, self.tracer.spans
        return self.tracer.spans[0]

    def kwargs_of(self, mock) -> list[dict]:
        return [dict(c.kwargs) for c in mock.call_args_list]

    def calls_with_span(self, mock) -> list[tuple]:
        out = []
        for c in mock.call_args_list:
            out.append((tuple(c.args), dict(c.kwargs)))
        return out

    def debug_texts(self) -> list[str]:
        return [r.getMessage() for r in self.debug_records]

    def one_debug(self, message: str) -> logging.LogRecord:
        hits = [r for r in self.debug_records if r.getMessage() == message]
        assert len(hits) == 1, f"want exactly one {message!r}, got {self.debug_texts()}"
        return hits[0]

    def extra_of(self, message: str) -> dict:
        return extras(self.one_debug(message))

    def silent_of(self, *messages: str) -> None:
        bad = sorted({m for m in self.debug_texts() if m in messages})
        assert bad == [], f"unexpected debug record(s) {bad} in {self.debug_texts()}"


def run_call_llm(
    *,
    guided: bool = False,
    supports: bool | None = None,
    enrichment_result=None,
    content: str = RISK_BODY,
    llm_url: str = LLM_URL,
) -> Drive:
    """Drive the SHIPPED _call_llm once against recording collaborators."""
    tracer = RecordingTracer()
    facade = FakeFacade()
    client = FakeClient({"content": content, "usage": {"prompt_tokens": 7, "completion_tokens": 3}})
    build_prompt_calls: list[dict] = []

    analyzer = NemotronAnalyzer.__new__(NemotronAnalyzer)
    analyzer._llm_url = llm_url
    analyzer._api_key = None
    analyzer._use_guided_json = guided
    analyzer._supports_guided_json = supports
    analyzer._max_retries = 1
    analyzer._facade = None
    analyzer._http_client = client
    if guided:

        async def _stub():  # instance-level REAL stub (autospec unsatisfiable)
            return supports

        analyzer._check_guided_json_support = _stub

    logger = logging.getLogger(LOGGER)
    handler = _Recorder()
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        with (
            patch.object(nem, "tracer", new=tracer),  # real recording tracer
            patch.object(
                nem, "sanitize_camera_name", autospec=True, side_effect=lambda n: CAM_SENT
            ) as sanitize_cam,
            patch.object(
                nem,
                "sanitize_detection_description",
                autospec=True,
                side_effect=lambda t: DET_SENT,
            ),
            patch.object(
                NemotronAnalyzer,
                "_build_prompt",
                autospec=True,
                side_effect=lambda self_, **kw: (build_prompt_calls.append(dict(kw)), PROMPT_SENT)[
                    1
                ],
            ),
            patch.object(
                NemotronAnalyzer,
                "_validate_and_truncate_prompt",
                autospec=True,
                side_effect=lambda self_, p: p,
            ),
            patch.object(
                NemotronAnalyzer, "_get_facade", autospec=True, side_effect=lambda self_: facade
            ),
            patch.object(nem, "AIModelAttributes", autospec=True) as ai_attrs,
            patch.object(nem, "set_pipeline_context_attributes", autospec=True),
            patch.object(nem, "add_span_attributes", autospec=True) as legacy,
            patch.object(nem, "set_llm_inference_attributes", autospec=True),
            patch.object(nem, "set_inference_result_attributes", autospec=True),
            patch.object(nem, "record_nemotron_tokens", autospec=True),
            patch(
                "backend.services.calibration_monitor.get_calibration_monitor",
                autospec=True,
                return_value=None,
            ),
            patch("time.monotonic", autospec=True, side_effect=lambda: 100.0),
            patch(
                "asyncio.timeout", autospec=True, side_effect=lambda when: contextlib.nullcontext()
            ),
        ):
            result = asyncio.run(
                analyzer._call_llm(
                    camera_name=CAMERA_RAW,
                    start_time="2026-01-01T00:00:00",
                    end_time="2026-01-01T00:05:00",
                    detections_list="1. 00:00:00 - person (confidence: 0.95)",
                    enrichment_result=enrichment_result,
                )
            )
            posts = list(client.calls)
            prompt_calls = list(build_prompt_calls)
            ai_calls = [
                (tuple(c.args), dict(c.kwargs)) for c in ai_attrs.set_on_span.call_args_list
            ]
            legacy_calls = [dict(c.kwargs) for c in legacy.call_args_list]
            cam_calls = [tuple(c.args) for c in sanitize_cam.call_args_list]
    finally:
        logger.setLevel(previous)
        logger.removeHandler(handler)

    return Drive(
        analyzer=analyzer,
        client=client,
        posts=posts,
        result=result,
        tracer=tracer,
        facade=facade,
        prompt_calls=prompt_calls,
        ai_calls=ai_calls,
        legacy_calls=legacy_calls,
        sanitize_cam_calls=cam_calls,
        debug_records=[r for r in handler.records if r.levelno == logging.DEBUG],
        records=list(handler.records),
    )


# ---------------------------------------------------------------------------
# mutmut_1
# ---------------------------------------------------------------------------
def test_camera_name_is_sanitized_before_prompt_interpolation():
    """Kills _call_llm__mutmut_1 (nemotron_analyzer.py:3856).

    mutmut_1 replaces `camera_name = sanitize_camera_name(camera_name)` with
    `camera_name = None`, i.e. it drops the sanitizer CALL *and* the value.
    Shipped: the raw argument reaches sanitize_camera_name exactly once, the
    sanitizer's return value is what flows into _build_prompt(camera_name=...),
    and nothing downstream is None. (NEM-1722 prompt-injection guard.)
    """
    d = run_call_llm()
    assert d.sanitize_cam_calls == [(CAMERA_RAW,)], d.sanitize_cam_calls
    assert len(d.prompt_calls) == 1, d.prompt_calls
    assert d.prompt_calls[0]["camera_name"] == CAM_SENT, d.prompt_calls[0]
    assert d.result["risk_score"] == 60


# ---------------------------------------------------------------------------
# mutmut_10, mutmut_11, mutmut_12
# ---------------------------------------------------------------------------
def test_template_name_basic_without_enrichment():
    """Kills _call_llm__mutmut_11 (nemotron_analyzer.py:3863-3865).

    mutmut_11 appends `or True` to the ternary condition, which pins
    template_name to "model_zoo" even with enriched_context=None AND
    enrichment_result=None. Shipped: that drive yields the EXACT whole
    legacy-attributes dict with template_name == "basic" (and
    guided_json_enabled False, prompt_length == len(sentinel prompt)).
    """
    d = run_call_llm(enrichment_result=None)
    assert d.legacy_calls[0] == {
        "llm_service": "nemotron",
        "llm_url": LLM_URL,
        "template_name": "basic",
        "prompt_length": len(PROMPT_SENT),
        "pipeline_stage": "llm_analysis",
        "guided_json_enabled": False,
    }, d.legacy_calls[0]


def test_template_name_model_zoo_with_enrichment_result():
    """Kills _call_llm__mutmut_10 and _mutmut_12 (nemotron_analyzer.py:3864).

    mutmut_10 appends `and False` (template collapses to "basic" even when an
    enrichment_result is present) and mutmut_12 renames the true-operand to
    "XXmodel_zooXX". Shipped: with enrichment_result non-None the first
    add_span_attributes call carries template_name exactly "model_zoo", and
    the same object flows to record_prompt_template_used's input.
    """
    marker = SimpleNamespace(baselines=None)
    d = run_call_llm(enrichment_result=marker)
    assert d.prompt_calls[0]["enrichment_result"] is marker
    assert d.legacy_calls[0]["template_name"] == "model_zoo", d.legacy_calls[0]
    assert d.legacy_calls[1]["llm_success"] is True


# ---------------------------------------------------------------------------
# mutmut_100, 101, 103, 104, 105, 106, 107, 108
# ---------------------------------------------------------------------------
def test_guided_json_fallback_debug_message_and_llm_url_extra():
    """Kills _call_llm__mutmut_100, _101, _103, _104, _105, _106, _107, _108
    (nemotron_analyzer.py:3939-3942).

    Guided json enabled + endpoint unsupported must log DEBUG with the EXACT
    message (100 -> None, 104 -> XX-wrapped, 105 -> lowercased, 106 ->
    upper-cased), the EXACT extra key "llm_url" (107 -> "XXllm_urlXX",
    108 -> "LLM_URL") whose value is self._llm_url, and the extra= present at
    all (101 -> extra=None, 103 -> the whole extra kwarg removed). The other
    guided arm stays silent and no nvext/nvext-guided_json key is merged into
    the request body.
    """
    d = run_call_llm(guided=True, supports=False)
    rec = d.one_debug(MSG_NO_SUPPORT)
    assert rec.getMessage() == "Endpoint does not support guided_json, using regex fallback"
    assert extras(rec) == {"llm_url": LLM_URL}, extras(rec)
    d.silent_of(MSG_GUIDED_YES)
    payload = d.posts[0][1]
    assert "nvext" not in payload, sorted(payload)
    assert d.legacy_calls[0]["guided_json_enabled"] is False
    assert d.result["risk_score"] == 60


# ---------------------------------------------------------------------------
# mutmut_109, 110, 111
# ---------------------------------------------------------------------------
def test_llm_inference_span_name_exact():
    """Kills _call_llm__mutmut_109, _110, _111 (nemotron_analyzer.py:3946).

    The span is opened exactly once and named exactly "llm_inference"
    (109 -> None, 110 -> "XXllm_inferenceXX", 111 -> "LLM_INFERENCE").
    """
    d = run_call_llm()
    assert [s.name for s in d.tracer.spans] == ["llm_inference"], [s.name for s in d.tracer.spans]


# ---------------------------------------------------------------------------
# mutmut_113-117, 119-123
# ---------------------------------------------------------------------------
def test_ai_model_attributes_set_on_span_exact_kwargs():
    """Kills _call_llm__mutmut_113, _114, _115, _116, _117 and _119, _120,
    _121, _122, _123 (nemotron_analyzer.py:3948-3955).

    AIModelAttributes.set_on_span is called once with the live span as its
    only positional argument and EXACTLY these five keyword arguments:
    model_name="nemotron-mini-4b-instruct", model_version="1.0.0",
    model_provider="nvidia", device="cuda:0", batch_size=1. The None
    substitutions (113-117) change a value; the keyword removals (119-123,
    123 also swallows the closing paren) shrink the keyword set — both break
    whole-dict equality. precision is deliberately absent from the shipped
    call, so it must stay absent.
    """
    d = run_call_llm()
    assert len(d.ai_calls) == 1, d.ai_calls
    ((args, kwargs),) = d.ai_calls
    assert len(args) == 1 and args[0] is d.span, args
    assert kwargs == {
        "model_name": "nemotron-mini-4b-instruct",
        "model_version": "1.0.0",
        "model_provider": "nvidia",
        "device": "cuda:0",
        "batch_size": 1,
    }, kwargs
