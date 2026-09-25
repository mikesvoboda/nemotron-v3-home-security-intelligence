"""Batch-25 FINAL kill battery — chunk tail-2: NemotronAnalyzer._call_llm (25 keys).

Chunk file: /tmp/wp-batch25/chunks3/tail-2.json (25 keys).
Full mutant key = "backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ"
"call_llm__mutmut_<n>"; the tests below name <n>.

Source under test: backend/services/nemotron_analyzer.py lines 3811-4267. All 25
keys sit on the telemetry attribute call sites that run BEFORE the retry loop:
the template_name literal/condition (:3863-3865 -> keys 13, 14),
AIModelAttributes.set_on_span (:3948-3954 -> 124-131),
set_pipeline_context_attributes (:3957-3960 -> 133, 134, 136, 137, 138, 139)
and the legacy add_span_attributes call (:3963-3969 -> 140-148).

READ-ONLY: nothing under /agents/agent-veranda3/workspace and nothing under
/home/agent/lanes is written by this file. All writes live under /tmp/wp-batch25/.

This file lives OUTSIDE the repo tree so the repo conftest.py does NOT apply:
``pytestmark = pytest.mark.unit`` is declared below and the settings env vars
are mirrored from backend/tests/conftest.py (values copied, not invented)
BEFORE the backend import. Async is driven with an explicit ``asyncio.run``
inside sync tests because pytest-asyncio's ``asyncio_mode = "auto"`` ini is not
picked up for /tmp paths.

GREEN vs RED: run WITHOUT the environment variable WP25_MUTT2 and every test
drives the SHIPPED function, so a green run here is a pin of shipped behavior.
With WP25_MUTT2="<n>" the autouse fixture below installs mutmut's OWN body for
mutant <n> (spliced out of /tmp/wp-batch25/instrumented-nemotron_analyzer.py via
instrumented.py.spans — not a text heuristic) for the duration of every test, so
the run goes red exactly where <n>'s rewrite is observable. The splice is
diffed against the shipped file at compile time, so a no-op splice fails loudly.

THE OBSERVABLE (measured: /tmp/wp-batch25/probes/finaltail2/p_map.py,
p_senti.py, and independently by the earlier
/tmp/wp-batch25/probes/dead052/p1.py + p2.py): the shipped span
``llm_inference`` is exported by a REAL opentelemetry-sdk TracerProvider into an
InMemorySpanExporter, and its finished attribute map is asserted KEY-FOR-KEY
EQUAL to an expected dict. One channel is sufficient for all 25 keys, for two
measured reasons:

  (1) value/literal/case mutants (13, 124-131, 138, 139) change an attribute
      VALUE. Full-map equality catches every rewrite, including the case-only
      ones ("MODEL_ZOO" vs "model_zoo", "NVIDIA" vs "nvidia", "CUDA:0" vs
      "cuda:0", "ANALYZE" vs "analyze") because the pin is exact equality.
  (2) None-valued and dropped-kwarg mutants (133, 134, 136, 137, 140-148)
      REMOVE the attribute instead of changing it:
      backend/core/telemetry_ai_conventions.py:135-145 and :306-311 guard every
      set_attribute call with ``if <kwarg> is not None``, and
      backend/core/telemetry.py:482-485 hands the value straight to
      span.set_attribute, which the SDK RECORDS-BUT-DROPS for None. Measured in
      probes/dead052/p2.py: "Invalid type NoneType for attribute 'k_none'
      value..." with ``span.attributes`` left EMPTY. So a None/drop mutant
      surfaces as a MISSING KEY, which full-map equality also catches.

``time.monotonic`` is frozen during the drive, which makes the two
duration-derived attributes exactly 0.0 ((100.0 - 100.0) * 1000) and pins the
token-derived attributes to the fixture usage. Two values in the expected dict
are RE-DERIVED from the same driven request — prompt_length from
``len(payload["prompt"])`` and llm_url from the URL actually posted — so the
pin cannot drift with the prompt templates or with settings and cannot become a
tautology.

TWO DRIVES are asserted: the BASIC drive (no enrichment -> template_name
"basic") and the MODEL_ZOO drive (an EnrichmentResult -> template_name
"model_zoo"). The model_zoo drive is REQUIRED, not decorative: keys 13 and 14
rewrite the :3865 ternary's true-branch literal and its ``or`` operator, and
both rewrites are invisible on the basic drive (measured — for 13/14 only the
model_zoo-asserting tests go red). 142/145/148 are asserted on both drives so
their kill does not depend on a single call path. Each docstring names the drive
that carries the kill.

AUTOSPEC NOTE (WP4.2 ratchet): the only unittest.mock patch CALL SITE in this
file is ``patch.object(nem, "get_settings", autospec=True, ...)``. The tracer
swap and the mutant install are NOT mock-patch sites — the tracer swap assigns
a REAL SDK recording object (autospec would build its spec from the shipped
tracer and reject an SDK-shaped replacement) and the mutant install is a direct
class __dict__ swap of the function under test, for which autospec=True is
unsatisfiable by construction (autospec would build the spec FROM the shipped
function the swap replaces). Both restores run in ``finally``/teardown.

EQUIVALENT: none. Every one of the 25 shapes rewrites a reachable operand of a
call whose result lands on the exported span, and each was observed red under
its own mutmut body (/tmp/wp-batch25/redcheck_final_tail2.log).
"""

from __future__ import annotations

import asyncio
import difflib
import functools
import json
import os
import re
import sys
import time
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

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

REPO = str(__import__("pathlib").Path(__file__).resolve().parents[4])

SHIP_SRC = REPO + "/backend/services/nemotron_analyzer.py"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

import backend.services.nemotron_analyzer as nem
from backend.services.enrichment_pipeline import EnrichmentResult
from backend.services.nemotron_analyzer import NemotronAnalyzer

FN = "xǁNemotronAnalyzerǁ_call_llm"
INSTRUMENTED = "/tmp/wp-batch25/instrumented-nemotron_analyzer.py"
SPANS = "/tmp/wp-batch25/instrumented.py.spans"
CHUNK = "/tmp/wp-batch25/chunks3/tail-2.json"

LLM_URL = "http://nim.test:8000/v1"
CAMERA = "Front Door"
DETECTION = "1. 00:00:00 - person (confidence: 0.95)"
FROZEN = 100.0  # the value time.monotonic returns during the driven call

RISK_BODY = json.dumps(
    {
        "risk_score": 60,
        "risk_level": "high",
        "summary": "Unusual activity",
        "reasoning": "Person at odd hours",
    }
)
USAGE = {"prompt_tokens": 7, "completion_tokens": 3}

# Frozen part of the expected span map, MEASURED from the shipped call under the
# frozen clock (probes/finaltail2/p_map.py). prompt_length and template_name are
# supplied per-drive by expected_attrs().
EXPECTED_AI = {
    "ai.model.name": "nemotron-mini-4b-instruct",
    "ai.model.version": "1.0.0",
    "ai.model.provider": "nvidia",
    "ai.inference.device": "cuda:0",
    "ai.inference.batch_size": 1,
}
EXPECTED_PIPELINE = {
    "pipeline.camera_id": CAMERA,
    "pipeline.stage": "analyze",
}
EXPECTED_LEGACY = {
    "llm_service": "nemotron",
    "pipeline_stage": "llm_analysis",
}
EXPECTED_LATE = {
    "llm_duration_ms": 0.0,
    "llm_success": True,
    "llm_attempts": 1,
    "input_tokens": USAGE["prompt_tokens"],
    "output_tokens": USAGE["completion_tokens"],
    "llm.prompt_tokens": USAGE["prompt_tokens"],
    "llm.completion_tokens": USAGE["completion_tokens"],
    "llm.total_tokens": USAGE["prompt_tokens"] + USAGE["completion_tokens"],
    "ai.inference.duration_ms": 0.0,
    "ai.inference.status": "success",
}

# The shipped site each number sits on, per the instrumented-body diff.
SHIPPED_SITE = {
    13: "template_name 'model_zoo' literal (:3865)",
    14: "template_name condition `or` (:3865)",
    124: "set_on_span model_name -> 'XXnemotron-mini-4b-instructXX' (:3950)",
    125: "set_on_span model_name -> 'NEMOTRON-MINI-4B-INSTRUCT' (:3950)",
    126: "set_on_span model_version -> 'XX1.0.0XX' (:3951)",
    127: "set_on_span model_provider -> 'XXnvidiaXX' (:3952)",
    128: "set_on_span model_provider -> 'NVIDIA' (:3952)",
    129: "set_on_span device -> 'XXcuda:0XX' (:3953)",
    130: "set_on_span device -> 'CUDA:0' (:3953)",
    131: "set_on_span batch_size -> 2 (:3954)",
    133: "set_pipeline camera_id -> None (:3959)",
    134: "set_pipeline stage -> None (:3960)",
    136: "set_pipeline camera_id kwarg DROPPED (:3959)",
    137: "set_pipeline stage kwarg DROPPED (:3960)",
    138: "set_pipeline stage -> 'XXanalyzeXX' (:3960)",
    139: "set_pipeline stage -> 'ANALYZE' (:3960)",
    140: "add_span_attributes llm_service -> None (:3964)",
    141: "add_span_attributes llm_url -> None (:3965)",
    142: "add_span_attributes template_name -> None (:3966)",
    143: "add_span_attributes prompt_length -> None (:3967)",
    144: "add_span_attributes pipeline_stage -> None (:3968)",
    145: "add_span_attributes guided_json_enabled -> None (:3969)",
    146: "add_span_attributes llm_service kwarg DROPPED (:3964)",
    147: "add_span_attributes llm_url kwarg DROPPED (:3965)",
    148: "add_span_attributes template_name kwarg DROPPED (:3966)",
}

CHUNK_KEYS = [
    "backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_call_llm__mutmut_%d" % n
    for n in [
        13,
        14,
        124,
        125,
        126,
        127,
        128,
        129,
        130,
        131,
        133,
        134,
        136,
        137,
        138,
        139,
        140,
        141,
        142,
        143,
        144,
        145,
        146,
        147,
        148,
    ]
]
CHUNK_NUMS = sorted(int(k.split("mutmut_")[-1]) for k in CHUNK_KEYS)


# =============================================================================
# mutant machinery (mutmut's own bodies, function region only)
# =============================================================================
_SH = _S = _E = _SPANS = _ILINES = None


def _load():
    """Lazy loader for the WP25_MUTT mutant machinery ONLY — the /tmp
    instrumented copy + spans are self-verification artifacts, absent in CI."""
    global _SH, _S, _E, _SPANS, _ILINES
    if _SH is not None:
        return
    _SH = open(SHIP_SRC).read().split("\n")  # nosemgrep: path-traversal-open
    _S = next(i for i, ln in enumerate(_SH) if ln.startswith("    async def _call_llm("))
    _E = next(
        j
        for j in range(_S + 1, len(_SH))
        if _SH[j].startswith("    async def ") or _SH[j].startswith("    def ")
    )
    _SPANS = json.load(open(SPANS))["spans"]
    _ILINES = open(INSTRUMENTED).read().split("\n")


@functools.lru_cache(maxsize=1024)
def mutant_code(mnum: int):
    """Compile mutmut's body for mutant <mnum> into a class-wrapped snippet."""
    _load()
    a, b = _SPANS["%s__mutmut_%d" % (FN, mnum)]
    body = list(_ILINES[a - 1 : b])
    while body and body[0].strip() == "":
        body = body[1:]
    while body and body[-1].strip() == "":
        body.pop()
    body[0] = re.sub(
        r"async def " + FN + r"__mutmut_\d+",
        "async def _call_llm",
        body[0],
        count=1,
    )
    merged = _SH[:_S] + body + _SH[_E:]
    diff = [
        ln
        for ln in difflib.unified_diff(_SH, merged, lineterm="", n=0)
        if ln[:1] in "+-" and ln[:3] not in ("+++", "---")
    ]
    assert diff, f"mutant {mnum} splice is a no-op"
    # nosemgrep: dangerous-eval
    return compile(
        # nosemgrep: dangerous-eval
        "class _MutCls:\n" + "\n".join(body),
        nem.__file__,
        "exec",
    )  # nosemgrep: dangerous-eval


def install_mutant(mnum: int):
    """Swap mutmut's body into the class for the duration of a test.

    NOT a mock-patch site (see module docstring): a direct class __dict__ swap.
    The exec is LAZY (per call) against a dict copy of the module __dict__ so
    the body sees the tracer swap _drive installs — mirroring mutmut's
    instrumented copy, where the variant body IS the module body. Re-executing
    the whole module top-level would rebind ``tracer`` via get_tracer() and
    export zero spans, which is a fake all-kill; it is avoided for that reason.
    """
    code = mutant_code(mnum)
    original = NemotronAnalyzer._call_llm

    def dispatch(self, *args, **kwargs):
        ns = dict(nem.__dict__)
        ns.pop("__name__", None)
        exec(code, ns)  # nosemgrep: dangerous-eval
        return ns["_MutCls"]._call_llm(self, *args, **kwargs)

    NemotronAnalyzer._call_llm = dispatch
    return original


@pytest.fixture(autouse=True)
def _mutant_install():
    """WP25_MUTT2="<n>" drives every test in this file under mutmut's own body
    for mutant <n> of _call_llm; unset means the shipped function runs."""
    spec = os.environ.get("WP25_MUTT2")
    if not spec:
        yield None
        return
    n = int(spec)
    assert n in CHUNK_NUMS, f"{n} is not a key of chunk tail-2"
    original = install_mutant(n)
    try:
        yield n
    finally:
        NemotronAnalyzer._call_llm = original


# =============================================================================
# fakes for the driven path
# =============================================================================
class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeClient:
    """httpx.AsyncClient stand-in: post() is keyword-only for json/headers like
    the real signature, so a mutant that drops a keyword raises."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def post(self, url, *, json, headers):
        self.calls.append((url, json, headers))
        return FakeResponse({"content": RISK_BODY, "usage": USAGE})


class RecordingCostTracker:
    def __init__(self) -> None:
        self.track_calls: list[dict] = []
        self.increment_calls = 0

    def track_llm_usage(self, **kwargs) -> None:
        self.track_calls.append(kwargs)

    def increment_event_count(self) -> None:
        self.increment_calls += 1


class FakeFacade:
    """Facade stand-in delivering REAL objects where the shipped code needs
    them: an actual asyncio.Semaphore for `async with`, and a cost tracker whose
    calls are counted."""

    def __init__(self) -> None:
        self.semaphore = asyncio.Semaphore(1)
        self.tracker = RecordingCostTracker()
        self.enricher = object()

    def get_inference_semaphore(self):
        return self.semaphore

    def get_cost_tracker(self):
        return self.tracker

    def get_context_enricher(self):
        return self.enricher


class Settings:
    """The settings _call_llm reads, forced to fixed integers so the expected
    request/pin values cannot drift with the repo defaults."""

    nemotron_read_timeout = 120
    ai_connect_timeout = 5
    nemotron_max_output_tokens = 1024


# =============================================================================
# the drive
# =============================================================================
class Run:
    """One driven _call_llm call: exported span + request body + result/error."""

    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)

    @property
    def post(self) -> tuple:
        return self.posts[0]

    @property
    def payload(self) -> dict:
        return self.post[1]

    @property
    def prompt(self) -> str:
        return self.payload["prompt"]


def drive(*, enrichment: bool = False) -> Run:
    """Run _call_llm once against a REAL TracerProvider/InMemorySpanExporter.

    Which body runs (shipped or a mutmut one) is decided by the autouse
    _mutant_install fixture, so this function is identical in the green and the
    red invocation.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    sdk_tracer = provider.get_tracer("wp-batch25-final-tail-2")

    facade = FakeFacade()
    analyzer = NemotronAnalyzer.__new__(NemotronAnalyzer)
    analyzer._llm_url = LLM_URL
    analyzer._api_key = None
    analyzer._use_guided_json = False
    analyzer._supports_guided_json = None
    analyzer._max_retries = 1
    analyzer._facade = facade
    analyzer._http_client = FakeClient()
    analyzer._context_enricher = facade.enricher

    kwargs: dict = {
        "camera_name": CAMERA,
        "start_time": "2026-01-01T00:00:00",
        "end_time": "2026-01-01T00:05:00",
        "detections_list": DETECTION,
    }
    if enrichment:
        kwargs["enrichment_result"] = EnrichmentResult()

    old_tracer = nem.tracer
    old_mono = time.monotonic
    result: dict = {}
    error: BaseException | None = None
    try:
        # NOT a mock-patch site (module docstring): the replacement must be a
        # REAL SDK tracer, which autospec (spec'd from the shipped tracer)
        # would reject.
        nem.tracer = sdk_tracer
        time.monotonic = lambda: FROZEN
        with patch.object(nem, "get_settings", autospec=True, return_value=Settings()):
            try:
                result = asyncio.run(analyzer._call_llm(**kwargs))
            except BaseException as e:
                error = e
    finally:
        time.monotonic = old_mono
        nem.tracer = old_tracer

    spans = exporter.get_finished_spans()
    return Run(
        enrichment=enrichment,
        analyzer=analyzer,
        facade=facade,
        posts=list(analyzer._http_client.calls),
        result=result,
        error=error,
        span_count=len(spans),
        span_name=spans[0].name if spans else None,
        attrs=dict(spans[0].attributes) if spans else {},
    )


# =============================================================================
# the pin: full-map equality of the exported llm_inference attributes
# =============================================================================
def expected_attrs(r: Run) -> dict:
    """Shipped attribute map for THIS run: frozen literals plus the two values
    re-derived from the driven request."""
    assert r.error is None, repr(r.error)
    assert r.span_count == 1, f"want exactly one span, got {r.span_count}"
    assert r.span_name == "llm_inference", r.span_name
    assert r.post[0] == f"{LLM_URL}/completion", r.post[0]
    return {
        **EXPECTED_AI,
        **EXPECTED_PIPELINE,
        **EXPECTED_LEGACY,
        **EXPECTED_LATE,
        "llm_url": r.post[0][: -len("/completion")],
        "template_name": "model_zoo" if r.enrichment else "basic",
        "prompt_length": len(r.prompt),
        "guided_json_enabled": False,
    }


def assert_shipped(*, enrichment: bool = False) -> Run:
    """Drive shipped behavior and assert the exported span equals the shipped
    attribute map, key for key."""
    r = drive(enrichment=enrichment)
    want = expected_attrs(r)
    assert want["prompt_length"] == len(r.payload["prompt"])
    assert want["llm_url"] == LLM_URL
    got = r.attrs
    missing = sorted(k for k in want if k not in got)
    changed = {k: (want[k], got[k]) for k in want if k in got and got[k] != want[k]}
    extra = sorted(k for k in got if k not in want)
    assert got == want, (
        "llm_inference attributes diverged from shipped "
        f"(drive={'model_zoo' if enrichment else 'basic'}, "
        f"WP25_MUTT2={os.environ.get('WP25_MUTT2')}): "
        f"missing={missing} changed={changed} unexpected={extra}"
    )
    return r


# =============================================================================
# shipped baseline (documented pins; identical assertions run under every
# mutant via the tests below)
# =============================================================================
class TestShippedBaseline:
    def test_basic_drive_span_and_request(self):
        """Shipped behavior of the tail-2 region on the basic drive: exactly one
        ``llm_inference`` span carrying the AI-model, pipeline-context and
        legacy attribute sets built at
        backend/services/nemotron_analyzer.py:3948-3969, with template_name
        'basic' and prompt_length == len(posted prompt). Also pins that the two
        re-derived expectations are live rather than fixtures."""
        r = assert_shipped()
        assert len(r.posts) == 1, r.posts
        assert r.result["risk_score"] == 60, r.result
        assert r.result["raw_response"] == RISK_BODY
        posted_len = len(r.payload["prompt"])
        assert posted_len > 0
        assert r.attrs["prompt_length"] == posted_len
        assert r.attrs["llm_url"] == r.post[0][: -len("/completion")] == LLM_URL
        assert r.attrs["template_name"] == "basic"
        # the payload the prompt length was measured against is the posted one
        assert r.payload["max_tokens"] == Settings.nemotron_max_output_tokens
        # semaphore released by the shipped `async with`
        assert r.facade.semaphore._value == 1
        # cost tracker got exactly one usage record + one event increment
        assert r.facade.tracker.increment_calls == 1
        assert len(r.facade.tracker.track_calls) == 1

    def test_model_zoo_drive_span(self):
        """Shipped behavior on the enrichment drive: supplying an
        EnrichmentResult makes template_name 'model_zoo' (:3863-3865) while
        every other tail-2 attribute keeps its shipped value, and the two
        drives post different prompts (so prompt_length is a live pin)."""
        r = assert_shipped(enrichment=True)
        assert r.attrs["template_name"] == "model_zoo"
        assert r.attrs["prompt_length"] == len(r.prompt)
        assert r.attrs["prompt_length"] != drive().attrs["prompt_length"]


# =============================================================================
# keys 13, 14 — the template_name literal and condition (:3863-3865)
# =============================================================================
class TestTemplateName:
    def test_basic_drive_pins_template_name(self):
        """Pins the basic drive's shipped map (template_name 'basic').

        MEASURED (redcheck_final_tail2.log): 13 and 14 both leave this drive's
        map INTACT and are killed by the model_zoo drive below — on the basic
        drive has_enriched_context is False and enrichment_result is None, so
        13's rewritten 'MODEL_ZOO' literal is never reached (the else-branch
        'basic' is shipped-identical) and 14's `and` is False exactly where the
        shipped `or` is also False. This test is what makes the shipped
        else-branch value honest, and it is the test that carries every other
        key in this chunk (124-148) whose rewrite is visible on both drives.
        """
        assert_shipped()

    def test_model_zoo_drive_pins_template_name(self):
        """Kills 13 ('model_zoo' -> 'MODEL_ZOO' at :3865) and 14 (`or` -> `and`).

        Only the enrichment drive reaches the rewritten operand: with an
        EnrichmentResult supplied the shipped condition yields 'model_zoo'
        while 13 yields 'MODEL_ZOO' and 14 — whose `and` is False because
        has_enriched_context is False when only enrichment_result is given —
        yields 'basic'. Both rewrites therefore surface as a changed
        template_name against the shipped 'model_zoo', and both leave the basic
        drive untouched (measured: for 13 and 14 ONLY the four model_zoo-asserting
        tests go red). The shipped 'model_zoo' value here is independently
        established by TestShippedBaseline.test_model_zoo_drive_span.
        """
        assert_shipped(enrichment=True)


# =============================================================================
# keys 124-131 — AIModelAttributes.set_on_span (:3948-3954)
# =============================================================================
class TestAiModelAttributes:
    def test_model_name_spelled_exactly(self):
        """Kills 124, 125 ('nemotron-mini-4b-instruct' ->
        'XXnemotron-mini-4b-instructXX' and -> 'NEMOTRON-MINI-4B-INSTRUCT').

        set_on_span copies model_name verbatim onto the span as ai.model.name
        (telemetry_ai_conventions.py:135-136), so either rewrite changes the
        exported value; the pin is exact string equality, which the upper-case
        form cannot pass.
        """
        assert_shipped()

    def test_model_version_spelled_exactly(self):
        """Kills 126 ('1.0.0' -> 'XX1.0.0XX') on the set_on_span model_version
        operand at :3951 -> ai.model.version."""
        assert_shipped()

    def test_model_provider_spelled_exactly(self):
        """Kills 127 ('nvidia' -> 'XXnvidiaXX') and 128 (-> 'NVIDIA') on the
        set_on_span model_provider operand at :3952 -> ai.model.provider."""
        assert_shipped()

    def test_device_spelled_exactly(self):
        """Kills 129 ('cuda:0' -> 'XXcuda:0XX') and 130 (-> 'CUDA:0') on the
        set_on_span device operand at :3953 -> ai.inference.device."""
        assert_shipped()

    def test_batch_size_value(self):
        """Kills 131 (batch_size 1 -> 2) on the set_on_span batch_size operand
        at :3954 -> ai.inference.batch_size, pinned to the shipped integer 1."""
        assert_shipped()


# =============================================================================
# keys 133, 134, 136, 137, 138, 139 — set_pipeline_context_attributes
# (:3957-3960)
# =============================================================================
class TestPipelineContextAttributes:
    def test_camera_id_attribute_present(self):
        """Kills 133 (camera_id=camera_name -> camera_id=None) and 136 (the
        camera_id kwarg removed) at :3959.

        Both route a None/absent camera_id into the helper, whose
        ``if camera_id is not None`` guard (telemetry_ai_conventions.py:306-307)
        skips set_attribute entirely — so pipeline.camera_id is MISSING from the
        exported span rather than changed. The pin demands the key with the
        sanitized camera value."""
        assert_shipped()

    def test_stage_value_spelled_exactly(self):
        """Kills 138 ('analyze' -> 'XXanalyzeXX') and 139 (-> 'ANALYZE') on the
        stage operand at :3960 -> pipeline.stage, pinned case-sensitively."""
        assert_shipped()

    def test_stage_attribute_present(self):
        """Kills 134 (stage='analyze' -> stage=None) and 137 (the stage kwarg
        removed, last-line form) at :3960: pipeline.stage disappears through the
        helper's None guard. pipeline.camera_id must survive alongside, which the
        key-for-key equality enforces."""
        assert_shipped()


# =============================================================================
# keys 140-148 — the legacy add_span_attributes call (:3963-3969)
# =============================================================================
class TestLegacySpanAttributes:
    def test_llm_service_present(self):
        """Kills 140 (llm_service='nemotron' -> None) and 146 (kwarg dropped).

        backend/core/telemetry.py:482-485 passes each keyword straight to
        span.set_attribute; the SDK records-but-drops a None value (measured:
        "Invalid type NoneType for attribute 'k_none' value..." with
        span.attributes left empty — probes/dead052/p2.py), so both mutants
        surface as a missing llm_service key."""
        assert_shipped()

    def test_llm_url_present(self):
        """Kills 141 (llm_url=self._llm_url -> None) and 147 (kwarg dropped) at
        :3965. The expected llm_url is derived from the URL this same run
        actually posted, so the pin tracks shipped behavior instead of a
        fixture, and a missing key still fails equality."""
        assert_shipped()

    def test_template_name_present_on_both_drives(self):
        """Kills 142 (template_name=template_name -> None) and 148 (kwarg
        dropped) at :3966: the template_name key disappears. Asserted on both
        drives so the key's absence is caught on the enrichment path
        ('model_zoo') as well as on the basic path ('basic')."""
        assert_shipped()
        assert_shipped(enrichment=True)

    def test_prompt_length_present(self):
        """Kills 143 (prompt_length=len(prompt) -> None) at :3967. The expected
        value is re-derived from the driven request body on every assertion, so
        the shipped operand is verified as ``len`` of the posted prompt and a
        None (dropped) value cannot satisfy the key."""
        r = assert_shipped()
        assert r.attrs["prompt_length"] == len(r.payload["prompt"])

    def test_pipeline_stage_present(self):
        """Kills 144 (pipeline_stage='llm_analysis' -> None) at :3968. Note the
        two distinct shipped keys this separates: the legacy pipeline_stage
        ('llm_analysis', this call) and pipeline.stage ('analyze', set at
        :3960) — full-map equality requires both, so 144 cannot masquerade as
        134/137/139."""
        assert_shipped()

    def test_guided_json_enabled_present(self):
        """Kills 145 (guided_json_enabled=use_guided_json_for_request -> None)
        at :3969. Every drive here runs with _use_guided_json False, so the
        shipped operand is the literal False; the expectation is that literal
        False (not merely 'a bool'), so a dropped key fails equality. Repeated on
        the model_zoo drive so the kill does not depend on one call path."""
        assert_shipped()
        assert_shipped(enrichment=True)


# =============================================================================
# chunk bookkeeping
# =============================================================================
def test_chunk_is_well_formed():
    """The chunk this file covers is exactly the 25 advertised keys, each with a
    recorded shipped site, and every key is exercised by at least one test above
    (checked structurally: the set of numbers named in the test docstrings)."""
    assert len(CHUNK_NUMS) == 25, CHUNK_NUMS
    assert len(set(CHUNK_NUMS)) == 25, CHUNK_NUMS
    assert (
        sorted(
            [
                13,
                14,
                124,
                125,
                126,
                127,
                128,
                129,
                130,
                131,
                133,
                134,
                136,
                137,
                138,
                139,
                140,
                141,
                142,
                143,
                144,
                145,
                146,
                147,
                148,
            ]
        )
        == CHUNK_NUMS
    ), CHUNK_NUMS
    assert set(SHIPPED_SITE) == set(CHUNK_NUMS), sorted(set(CHUNK_NUMS) ^ set(SHIPPED_SITE))
    named: set[int] = set()
    for cls in (
        TestTemplateName,
        TestAiModelAttributes,
        TestPipelineContextAttributes,
        TestLegacySpanAttributes,
    ):
        for name in dir(cls):
            if name.startswith("test_"):
                named |= {
                    int(t)
                    for t in re.findall(
                        r"^(?:Kills|.*?Kills)\s+(.*)$", getattr(cls, name).__doc__ or "", re.M
                    )
                    for t in re.findall(r"\b(\d{2,3})\b", t)
                }
    missing = sorted(set(CHUNK_NUMS) - named)
    assert missing == [], f"numbers not named by any test docstring: {missing}"
