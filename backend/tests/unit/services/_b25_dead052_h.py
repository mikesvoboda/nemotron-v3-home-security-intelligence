"""Shared harness for the batch-25 dead-05-2 kill battery.

Owns BOTH files of this chunk (battery + harness), so the "do not edit files
you do not own" rule is respected. Everything here is measurement plumbing for
the SHIPPED NemotronAnalyzer._call_llm
(backend/services/nemotron_analyzer.py:3811-4267):

  * env mirrored from backend/tests/conftest.py (values copied, not invented),
  * a fake httpx client / facade / cost tracker that RECORDS every call,
  * an OpenTelemetry SDK TracerProvider + InMemorySpanExporter so the shipped
    `llm_inference` span (name + attributes) is observable,
  * recorders for the two DEBUG log sites,
  * a frozen time.monotonic and a recording asyncio.timeout stand-in,
  * mutmut's OWN mutant bodies (spliced from
    /tmp/wp-batch25/instrumented-nemotron_analyzer.py via
    instrumented.py.spans) installed as an INSTANCE attribute for the
    duration of one drive, so a test can be red-checked without touching the
    repository.

COLLABORATOR SWAPS (WP4.2 note): the mock-patch call sites below carry
autospec=True (record_nemotron_tokens, add_span_attributes,
set_pipeline_context_attributes, set_llm_inference_attributes,
set_inference_result_attributes, AIModelAttributes, time.monotonic,
asyncio.timeout, NemotronAnalyzer._get_facade). Swaps that must deliver a REAL
recording object rather than a mock (nem.tracer, the instance-level
_check_guided_json_support stub, the mutant __dict__/instance swap) are direct
assignments with restore in finally: autospec is unsatisfiable there by
construction, because autospec would build the spec FROM the shipped object
the swap exists to replace.

The mutant body is exec'd with a snapshot of the module __dict__ taken INSIDE
the patch block, so the mutant sees the same patched collaborators as the
shipped function does.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import json
import logging
import os
import re
import sys
import types
from unittest.mock import patch

REPO = str(__import__("pathlib").Path(__file__).resolve().parents[4])

SHIP_SRC = REPO + "/backend/services/nemotron_analyzer.py"

# --- minimum env, values copied from backend/tests/conftest.py ---------------
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
COMPLETION_URL = f"{LLM_URL}/completion"
API_KEY = "sk-nem-dead052"  # pragma: allowlist secret  # nosemgrep: hardcoded-password
CAMERA = "Front Door"

MSG_GUIDED_YES = "Using guided_json for structured LLM output"
MSG_NO_SUPPORT = "Endpoint does not support guided_json, using regex fallback"

SCHEMA_KEYS = list(RISK_ANALYSIS_JSON_SCHEMA.get("properties", {}).keys())

RISK_BODY = json.dumps(
    {
        "risk_score": 60,
        "risk_level": "high",
        "summary": "Unusual activity",
        "reasoning": "Person at odd hours",
    }
)

FN = "xǁNemotronAnalyzerǁ_call_llm"
INSTRUMENTED = "/tmp/wp-batch25/instrumented-nemotron_analyzer.py"
SPANS = "/tmp/wp-batch25/instrumented.py.spans"

# Red-check forcing: run() honours FORCE["m"] when non-zero.
FORCE = {"m": 0}

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
# mutmut body splicing (same machinery as parts/test_batch25_10.py)
# ---------------------------------------------------------------------------
def _ensure():
    """Lazy loader for the WP25_MUTT mutant machinery ONLY (never on import,
    never on a shipped-behavior test): the /tmp/wp-batch25 instrumented copy
    is a self-verification artifact, absent in CI."""
    g = globals()
    if "_SH" in g:
        return
    sh = open(SHIP_SRC).read().split("\n")  # nosemgrep: path-traversal-open
    g["_SH"] = sh
    g["_S"] = next(i for i, ln in enumerate(sh) if ln.startswith("    async def _call_llm("))
    g["_E"] = next(
        j
        for j in range(g["_S"] + 1, len(sh))
        if sh[j].startswith("    async def ") or sh[j].startswith("    def ")
    )
    g["_SPANS"] = json.load(open(SPANS))["spans"]
    g["_ILINES"] = open(INSTRUMENTED).read().split("\n")


def __getattr__(name):  # PEP 562: bind loader globals on first real access
    if name in ("_SH", "_S", "_E", "_SPANS", "_ILINES"):
        _ensure()
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@functools.lru_cache(maxsize=512)
def mutant_source(mnum: int) -> str:
    _ensure()
    g = globals()
    _SPANS, _ILINES, _SH, _S, _E = g["_SPANS"], g["_ILINES"], g["_SH"], g["_S"], g["_E"]
    a, b = _SPANS["%s__mutmut_%d" % (FN, mnum)]
    body = _ILINES[a - 1 : b]
    if body[0].strip() == "":
        body = body[1:]
    body[0] = re.sub(
        r"async def " + FN + r"__mutmut_\d+",
        "async def _call_llm",
        body[0],
        count=1,
    )
    while len(body) < _E - _S:
        body.append("")
    body = body[: _E - _S]
    return "\n".join(_SH[:_S] + body + _SH[_E:])


def compile_mutant(mnum: int):
    """mutmut's body for <mnum>, exec'd against the CURRENT module globals."""
    ns = dict(nem.__dict__)
    ns.pop("__name__", None)
    exec(compile(mutant_source(mnum), nem.__file__, "exec"), ns)  # nosemgrep: dangerous-eval
    return ns["NemotronAnalyzer"]._call_llm


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeClient:
    """httpx.AsyncClient stand-in: post() is keyword-only for json/headers,
    like the real signature, so a mutant that drops a keyword raises."""

    def __init__(self, payload) -> None:
        self.payload = payload
        self.calls: list[tuple] = []

    async def post(self, url, *, json, headers):
        self.calls.append((url, json, headers))
        if isinstance(self.payload, BaseException):
            raise self.payload
        return FakeResponse(self.payload)


class RecordingCostTracker:
    def __init__(self) -> None:
        self.track_calls: list[dict] = []
        self.increment_calls: int = 0

    def track_llm_usage(self, **kwargs) -> None:
        self.track_calls.append(kwargs)

    def increment_event_count(self) -> None:
        self.increment_calls += 1


class FakeFacade:
    def __init__(self, semaphore: asyncio.Semaphore, tracker: RecordingCostTracker) -> None:
        self._semaphore = semaphore
        self._tracker = tracker
        self.calls: list[str] = []

    def get_inference_semaphore(self):
        self.calls.append("get_inference_semaphore")
        return self._semaphore

    def get_cost_tracker(self):
        self.calls.append("get_cost_tracker")
        return self._tracker


class Clock:
    """time.monotonic replacement: a constant value, advanced only by a test."""

    def __init__(self, start: float = 100.0) -> None:
        self.t = start
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return self.t


class RecordingTimeout:
    """asyncio.timeout stand-in: records enter/exit counts and the deadline."""

    def __init__(self) -> None:
        self.whens: list = []
        self.entered = 0
        self.exited = 0

    def _factory(self, when):
        self.whens.append(when)
        outer = self

        class _CM:
            async def __aenter__(self):
                outer.entered += 1
                return self

            async def __aexit__(self, *exc):
                outer.exited += 1
                return False

        return _CM()


class RecordingSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict = {}
        self.exceptions: list = []

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value

    def set_attributes(self, attrs) -> None:
        self.attributes.update(attrs)

    def record_exception(self, exc, attributes=None) -> None:
        self.exceptions.append((exc, attributes))

    def set_status(self, *a, **kw) -> None:
        return None

    def is_recording(self) -> bool:
        return True

    def add_event(self, *a, **kw) -> None:
        return None

    def end(self, *a, **kw) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class RecordingTracer:
    """Real OTel-shaped tracer: the SAME span object is current for the whole
    `with` block, so add_span_attributes (patched to record against the
    current span) lands on the object AIModelAttributes saw."""

    def __init__(self) -> None:
        self.spans: list[RecordingSpan] = []
        self._current: RecordingSpan | None = None

    def start_as_current_span(self, name, *a, **kw):
        span = RecordingSpan(name)
        self.spans.append(span)
        outer = self

        class _CM:
            async def __aenter__(self):  # pragma: no cover - sync path used
                return span

            def __aexit__(self, *exc):  # pragma: no cover - sync path used
                return False

            def __enter__(self):
                outer._current = span
                return span

            def __exit__(self, *exc):
                outer._current = None
                return False

        return _CM()

    def get_span(self) -> RecordingSpan | None:
        return self._current


class _Recorder(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


# ---------------------------------------------------------------------------
# the drive
# ---------------------------------------------------------------------------
class Drive:
    """Every observable channel of one _call_llm run."""

    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)

    # -- channel: returned risk dict / raised error -------------------------
    @property
    def ok(self) -> bool:
        return self.exc is None

    # -- channel: span ------------------------------------------------------
    @property
    def span(self) -> RecordingSpan:
        assert len(self.tracer.spans) == 1, self.tracer.spans
        return self.tracer.spans[0]

    @property
    def attrs(self) -> dict:
        return self.span.attributes

    # -- channel: DEBUG log records on the guided_json sites ---------------
    @property
    def debug_texts(self) -> list[str]:
        return [r.getMessage() for r in self.debug_records]

    def one_debug(self, message: str) -> logging.LogRecord:
        hits = [r for r in self.debug_records if r.getMessage() == message]
        assert len(hits) == 1, f"want one {message!r}, got {self.debug_texts}"
        return hits[0]

    def extra_of(self, message: str) -> dict:
        return extras(self.one_debug(message))

    def silent_of(self, *messages: str) -> None:
        bad = sorted({m for m in self.debug_texts if m in messages})
        assert bad == [], f"unexpected debug record(s) {bad} in {self.debug_texts}"

    # -- helpers ------------------------------------------------------------
    def kwargs_of(self, mock) -> list[dict]:
        """Keyword dicts of every recorded call of an autospec mock."""
        return [dict(c.kwargs) for c in mock.call_args_list]

    def assert_semaphore_free(self) -> None:
        assert self.semaphore._value == self.semaphore_limit, (
            "inference semaphore was not released by the shipped `async with`"
        )


def build_analyzer(
    *,
    payload,
    guided: bool,
    supports: bool | None,
    llm_url: str,
    api_key: str | None,
    max_retries: int,
) -> NemotronAnalyzer:
    a = NemotronAnalyzer.__new__(NemotronAnalyzer)
    a._llm_url = llm_url
    a._api_key = api_key
    a._use_guided_json = guided
    a._supports_guided_json = supports
    a._max_retries = max_retries
    a._facade = None
    if guided:

        async def _stub():
            return supports

        a._check_guided_json_support = _stub  # instance-level REAL stub
    return a


@contextlib.contextmanager
def patched_env(
    tracer: RecordingTracer, clock: Clock, timeout: RecordingTimeout, facade: FakeFacade
):
    """Patch every collaborator _call_llm touches on the driven path.

    The snapshot for the mutant exec is taken INSIDE this block (see
    compile_mutant), so mutant and shipped code see the same collaborators.
    """
    with (
        patch.object(nem, "tracer", new=tracer),
        patch.object(
            NemotronAnalyzer,
            "_get_facade",
            autospec=True,
            side_effect=lambda self_: facade,
        ),
        patch.object(nem, "record_nemotron_tokens", autospec=True) as tokens,
        patch.object(nem, "AIModelAttributes", autospec=True) as ai_attrs,
        patch.object(nem, "set_pipeline_context_attributes", autospec=True) as pipe_attrs,
        patch.object(nem, "add_span_attributes", autospec=True) as legacy,
        patch.object(nem, "set_llm_inference_attributes", autospec=True),
        patch.object(nem, "set_inference_result_attributes", autospec=True),
        patch("time.monotonic", autospec=True, side_effect=clock),
        patch("asyncio.timeout", autospec=True, side_effect=timeout._factory),
    ):
        yield {
            "tokens": tokens,
            "ai_attrs": ai_attrs,
            "pipe_attrs": pipe_attrs,
            "legacy": legacy,
        }


def run(
    mutant: int = 0,
    *,
    payload=None,
    content: str | None = RISK_BODY,
    usage=None,
    guided: bool = False,
    supports: bool | None = None,
    llm_url: str = LLM_URL,
    api_key: str | None = None,
    max_retries: int = 1,
    clock_start: float = 100.0,
    camera: str = CAMERA,
):
    """Drive _call_llm once (shipped, or mutmut body <mutant>) and record all
    observable channels."""
    mnum = FORCE["m"] or mutant
    if payload is None:
        payload = {"usage": usage or {}}
        if content is not None:
            payload["content"] = content

    tracer = RecordingTracer()
    clock = Clock(clock_start)
    timeout = RecordingTimeout()
    tracker = RecordingCostTracker()
    semaphore = asyncio.Semaphore(1)
    facade = FakeFacade(semaphore, tracker)
    client = FakeClient(payload)

    analyzer = build_analyzer(
        payload=payload,
        guided=guided,
        supports=supports,
        llm_url=llm_url,
        api_key=api_key,
        max_retries=max_retries,
    )
    analyzer._http_client = client

    logger = logging.getLogger(LOGGER)
    handler = _Recorder()
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    result: dict = {}
    exc: BaseException | None = None
    settings = nem.get_settings()
    try:
        with patched_env(tracer, clock, timeout, facade) as mocks:
            if mnum:
                analyzer._call_llm = types.MethodType(compile_mutant(mnum), analyzer)
            try:
                result = asyncio.run(
                    analyzer._call_llm(
                        camera_name=camera,
                        start_time="2026-01-01T00:00:00",
                        end_time="2026-01-01T00:05:00",
                        detections_list="1. 00:00:00 - person (confidence: 0.95)",
                    )
                )
            except BaseException as e:
                exc = e
            token_calls = [dict(c.kwargs) for c in mocks["tokens"].call_args_list]
            ai_calls = [dict(c.kwargs) for c in mocks["ai_attrs"].set_on_span.call_args_list]
            pipe_calls = [
                (tuple(c.args), dict(c.kwargs)) for c in mocks["pipe_attrs"].call_args_list
            ]
            legacy_calls = [dict(c.kwargs) for c in mocks["legacy"].call_args_list]
    finally:
        logger.setLevel(previous)
        logger.removeHandler(handler)

    return Drive(
        mutant=mnum,
        analyzer=analyzer,
        client=client,
        posts=list(client.calls),
        result=result,
        exc=exc,
        tracer=tracer,
        clock=clock,
        timeout=timeout,
        facade=facade,
        tracker=tracker,
        semaphore=semaphore,
        semaphore_limit=1,
        debug_records=[r for r in handler.records if r.levelno == logging.DEBUG],
        records=list(handler.records),
        token_calls=token_calls,
        ai_calls=ai_calls,
        pipe_calls=pipe_calls,
        legacy_calls=legacy_calls,
        settings=settings,
    )


def expected_timeout(settings) -> float:
    """explicit_timeout as shipped computes it (nemotron_analyzer.py:3910)."""
    return settings.nemotron_read_timeout + settings.ai_connect_timeout


def payload_of(d: Drive, index: int = 0) -> dict:
    return d.posts[index][1]


def shipped_payload(d: Drive, index: int = 0) -> dict:
    """The shipped request body, with the prompt taken from the driven run."""
    return payload_of(d, index)
