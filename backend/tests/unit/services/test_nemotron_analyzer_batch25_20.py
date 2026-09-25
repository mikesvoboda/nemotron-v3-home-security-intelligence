"""Batch-25 part 20 — chunk "NemotronAnalyzer.run_shadow_analysis#chunk1" (53 keys).

Every key in /tmp/wp-batch25/chunks/chunk-20.json is a survivor of
NemotronAnalyzer.run_shadow_analysis
(backend/services/nemotron_analyzer.py:926-1001). The function has exactly four
observables, and the tests below pin them AS SHIPPED:

  (a) the call-site argument shapes it hands to its two collaborators
      `self._call_llm_with_version(...)` (L957-958 V1, L973-974 V2) and
      `self._log_shadow_result(...)` (L984-989). Both collaborators are patched
      with INSTANCE-level autospec mocks, so the spec is the bound method: no
      `self` in call_args, an omitted DEFAULTED kwarg stays omitted from
      call_args, and an omitted REQUIRED argument raises TypeError from the
      autospec spec check *before* the mock records the call (probed:
      "missing a required argument: 'context'", call_count == 0).
  (b) the returned dict's five key names and values (L995-1001)
  (c) the ERROR record "V1 prompt failed in shadow analysis: {e}" (L961)
  (d) the WARNING record "Shadow (V2) prompt failed, continuing with V1: {e}"
      (L993)

Latencies are made exact with a phase clock: `time.monotonic` is patched to
return a constant that the fake LLM advances *after* each call
(100.0 -> 100.5 after V1 -> 100.75 after V2), so the shipped arithmetic
(L963, L976: `(monotonic() - start) * 1000`) yields v1_latency_ms=500.0 and
v2_latency_ms=250.0 while any consumer (including the event loop) reading the
clock never disturbs the sequence. The values match the shipped probe
(/tmp/wp-batch25/probes/ad20/probe_shipped.py), which additionally pinned
  call(camera_id='cam-1', v1_result=V1, v2_result=V2,
      v1_latency_ms=500.0, v2_latency_ms=250.0)  and  score_diff == 50.

Key -> shape group -> killing observable (feed.json functions[
'xǁNemotronAnalyzerǁrun_shadow_analysis'].shapes: 53 groups of 1 key each;
occurrence order confirmed against the instrumented copy
mutants/backend/services/nemotron_analyzer.py variant bodies
xǁNemotronAnalyzerǁrun_shadow_analysis__mutmut_<N>):

  V1 call site (L958):    4 context->None | 5 prompt_version->None
                          6 context dropped | 7 prompt_version dropped
  v1_latency_ms (L963):   8 ->None | 9 *1000 -> /1000 | 10 - -> + | 11 ->1001
  pre-branch defaults:    12 v2_result None->"" | 13 v2_latency 0.0->None
                          14 ->1.0 | 15 score_diff 0.0->None | 16 ->1.0
  V2 call site (L974):    19 20 21 22 mirror 4 5 6 7
  v2_latency_ms (L976):   23 ->None | 24 *1000 -> /1000 | 25 - -> + | 26 ->1001
  v1_result.get (L979):   28 "risk_score"->None | 29 default ->None
                          31 default argument dropped (.get with 1 arg)
                          32 ->"XXrisk_scoreXX" | 33 ->"RISK_SCORE"
                          34 default ->1
  v2_result.get (L980):   36 37 39 40 41 42 mirror 28 29 31 32 33 34
  score_diff (L981):      43 whole RHS ->None | 45 "-" -> "+"
  log kwargs (L985-989):  46 camera_id->None | 47 v1_result->None
                          48 v2_result->None | 49 v1_latency_ms->None
                          50 v2_latency_ms->None | 51 camera_id dropped
                          52 v1_result dropped | 53 v2_result dropped
                          54 v1_latency_ms dropped | 55 v2_latency_ms dropped
  return-dict keys:       58/59 "shadow_result", 60/61 "score_diff",
                          62/63 "v1_latency_ms", 64/65 "v2_latency_ms" —
                          each renamed once to "XX<x>XX", once to UPPER

Nothing here is equivalent. 28/29/31/36/37/39 look value-dead only because
the V1/V2 fake dicts always carry `risk_score`, and the locals v1_score /
v2_score (L979-980) are never read after L981 — but their product score_diff
IS returned (L998), so drives whose result dicts omit `risk_score` make every
default value and the key literal observable again (29/31/37/39 then raise
TypeError inside the V2 try and surface through observable (d)). The two
spellings differ — 29/37 pass None explicitly, 31/39 DROP the default
argument (`.get("risk_score", )` with a trailing comma is a one-argument
`.get()` returning None, not an empty tuple) — but both behave identically
and are killed by the same drives.

killed_by_draft: NONE. The repo's only run_shadow_analysis tests
(backend/tests/unit/services/test_prompt_experiment_integration.py:258-395
and :684) mock _call_llm_with_version with `async def mock(*args,
prompt_version=None)`, patch _log_shadow_result with a bare AsyncMock, and
assert `result["primary_result"]["risk_score"]`, `mock_log.
assert_called_once()` and `result is not None` — call-shape-blind and
value-blind. The batch-25 draft battery (/tmp/wp-batch25/
test_nemotron_analyzer_batch25.py, 24 tests) never touches
run_shadow_analysis.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_20.py -p no:cacheprovider -o addopts= -q
"""

from __future__ import annotations

import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# The part file lives outside the repo tree, so backend/tests/conftest.py does
# NOT apply. Mirror the minimum env vars that conftest sets BEFORE any backend
# import (values copied verbatim from backend/tests/conftest.py).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

from backend.config.prompt_experiment import PromptExperimentConfig
from backend.core.config import Settings
from backend.services.nemotron_analyzer import NemotronAnalyzer

LOGGER = "backend.services.nemotron_analyzer"

# Shipped literals, copied from the source lines each mutant rewrites.
V1_VERSION = "v1_original"  # PromptVersion.V1_ORIGINAL.value
V2_VERSION = "v2_calibrated"  # PromptVersion.V2_CALIBRATED.value
V2_FAIL_MSG = "Shadow (V2) prompt failed, continuing with V1: v2-boom"

# Phase clock: monotonic returns `now`; the fake LLM advances it once per
# completed call (100.0 -> 100.5 -> 100.75). Shipped arithmetic then yields
# v1_latency_ms = 500.0 and v2_latency_ms = 250.0.
CLOCK_STEPS = [100.5, 100.75]
V1_LAT = 500.0
V2_LAT = 250.0

V1_RESULT = {"risk_score": 80, "risk_level": "high", "summary": "V1"}
V2_RESULT = {"risk_score": 30, "risk_level": "low", "summary": "V2"}
RETURN_KEYS = {"primary_result", "shadow_result", "score_diff", "v1_latency_ms", "v2_latency_ms"}
LOG_KWARGS = {
    "camera_id": "cam-1",
    "v1_result": V1_RESULT,
    "v2_result": V2_RESULT,
    "v1_latency_ms": V1_LAT,
    "v2_latency_ms": V2_LAT,
}


class PhaseClock:
    """time.monotonic replacement: constant value, advanced by the fake LLM."""

    def __init__(self):
        self.now = 100.0
        self._steps = list(CLOCK_STEPS)

    def __call__(self):
        return self.now

    def advance(self):
        if self._steps:
            self.now = self._steps.pop(0)


def _mock_settings():
    """Settings mirroring the repo unit fixture (values copied, not invented)."""
    m = MagicMock(spec=Settings)
    # P0.3 flags (#6678): pydantic v2 field names are not in
    # dir(Settings), so a spec'd mock must pin them explicitly.
    m.nemotron_constrained_decoding_enabled = False
    m.nemotron_constrained_fail_closed = True
    m.nemotron_constrained_probe_enabled = True
    m.nemotron_constrained_probe_required_build = None
    m.nemotron_verification_engine = "llama.cpp"
    m.nemotron_model_id = "Nemotron-3-Nano-30B-A3B-Q4_K_M"
    m.nemotron_url = "http://localhost:8091"
    m.nemotron_api_key = None
    m.ai_connect_timeout = 10.0
    m.nemotron_read_timeout = 120.0
    m.ai_health_timeout = 5.0
    m.nemotron_max_retries = 2
    m.severity_low_max = 29
    m.severity_medium_max = 59
    m.severity_high_max = 84
    m.nemotron_context_window = 4096
    m.nemotron_max_output_tokens = 1536
    m.context_utilization_warning_threshold = 0.80
    m.context_truncation_enabled = True
    m.llm_tokenizer_encoding = "cl100k_base"
    m.image_quality_enabled = False
    m.ai_warmup_enabled = True
    m.ai_cold_start_threshold_seconds = 300.0
    m.nemotron_warmup_prompt = "Test warmup prompt"
    m.scene_change_resize_width = 640
    m.use_enrichment_service = False
    m.ai_max_concurrent_inferences = 4
    m.nemotron_use_guided_json = False
    m.nemotron_guided_json_fallback = True
    m.batch_coalescing_enabled = False
    m.batch_coalescing_max_size = 10
    m.batch_coalescing_time_window = 5.0
    m.priority_queue_enabled = False
    m.priority_high_labels = ["weapon", "intruder", "fire"]
    m.priority_medium_labels = ["person", "unknown"]
    return m


@pytest.fixture
def analyzer():
    """NemotronAnalyzer built under the same get_settings patches as the repo fixture."""
    from backend.core.redis import RedisClient
    from backend.services.analyzer_facade import reset_analyzer_facade
    from backend.services.inference_semaphore import reset_inference_semaphore
    from backend.services.severity import reset_severity_service
    from backend.services.token_counter import reset_token_counter

    settings = _mock_settings()
    redis_client = MagicMock(spec=RedisClient)
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock(return_value=True)
    redis_client.delete = AsyncMock(return_value=1)
    redis_client.publish = AsyncMock(return_value=1)
    with (
        patch(
            "backend.services.nemotron_analyzer.get_settings",
            return_value=settings,
            autospec=True,
        ),
        patch("backend.services.severity.get_settings", return_value=settings, autospec=True),
        patch(
            "backend.services.token_counter.get_settings",
            return_value=settings,
            autospec=True,
        ),
        patch("backend.core.config.get_settings", return_value=settings, autospec=True),
        patch(
            "backend.services.inference_semaphore.get_settings",
            return_value=settings,
            autospec=True,
        ),
    ):
        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()
        try:
            yield NemotronAnalyzer(redis_client=redis_client)
        finally:
            reset_severity_service()
            reset_token_counter()
            reset_analyzer_facade()
            reset_inference_semaphore()


def _version_of(c):
    """Prompt version carried by one recorded `_call_llm_with_version` call."""
    if "prompt_version" in c.kwargs:
        return c.kwargs["prompt_version"]
    return c.args[1] if len(c.args) > 1 else "__no_version_argument__"


class Drive:
    """Everything one drive of run_shadow_analysis makes observable."""

    def __init__(
        self,
        *,
        result,
        exc,
        llm_calls,
        v1_calls,
        v2_calls,
        log_calls,
        v1_seen,
        v2_seen,
        errors,
        warnings,
    ):
        self.result = result
        self.exc = exc
        self.llm_calls = llm_calls  # autospec call_args_list, both versions
        self.v1_calls = v1_calls  # recorded calls whose version is not V2
        self.v2_calls = v2_calls  # recorded calls with prompt_version == V2
        self.log_calls = log_calls  # autospec call_args_list of _log_shadow_result
        self.v1_seen = v1_seen  # (args, kwargs) the fake actually received
        self.v2_seen = v2_seen
        self.errors = errors  # ERROR record messages, in order
        self.warnings = warnings  # WARNING record messages, in order

    @property
    def log_kwargs(self):
        assert len(self.log_calls) == 1, f"expected exactly one log call, got {self.log_calls}"
        return self.log_calls[0].kwargs


async def drive(
    analyzer,
    *,
    camera_id="cam-1",
    context="CTX",
    v1=None,
    v2=None,
    shadow_mode=True,
    v2_fails=False,
):
    """Run the shipped run_shadow_analysis with both collaborators autospec'd."""
    analyzer.set_experiment_config(PromptExperimentConfig(shadow_mode=shadow_mode))
    v1 = dict(V1_RESULT) if v1 is None else dict(v1)
    v2 = dict(V2_RESULT) if v2 is None else dict(v2)
    clock = PhaseClock()

    records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = Collect()
    logger = logging.getLogger(LOGGER)
    logger.addHandler(handler)

    v1_seen: list = []
    v2_seen: list = []

    async def llm(*args, **kwargs):
        pv = kwargs.get("prompt_version", args[1] if len(args) > 1 else V1_VERSION)
        if pv == V2_VERSION:
            v2_seen.append((args, kwargs))
            clock.advance()
            if v2_fails:
                raise RuntimeError("v2-boom")
            return dict(v2)
        v1_seen.append((args, kwargs))
        clock.advance()
        return dict(v1)

    result = None
    exc = None
    try:
        with (
            patch.object(
                analyzer, "_call_llm_with_version", autospec=True, side_effect=llm
            ) as llm_mock,
            patch.object(analyzer, "_log_shadow_result", autospec=True) as log_mock,
            patch("time.monotonic", autospec=True, side_effect=clock),
        ):
            try:
                result = await analyzer.run_shadow_analysis(camera_id=camera_id, context=context)
            except Exception as e:  # recorded, not raised to pytest
                exc = e
        all_calls = list(llm_mock.call_args_list)
        return Drive(
            result=result,
            exc=exc,
            llm_calls=all_calls,
            v1_calls=[c for c in all_calls if _version_of(c) != V2_VERSION],
            v2_calls=[c for c in all_calls if _version_of(c) == V2_VERSION],
            log_calls=list(log_mock.call_args_list),
            v1_seen=v1_seen,
            v2_seen=v2_seen,
            errors=[
                r.getMessage() for r in records if r.name == LOGGER and r.levelno == logging.ERROR
            ],
            warnings=[
                r.getMessage() for r in records if r.name == LOGGER and r.levelno == logging.WARNING
            ],
        )
    finally:
        logger.removeHandler(handler)


def _assert_return_shape(d: Drive) -> None:
    """Shipped contract of every non-failing drive: no exception, five keys."""
    assert d.exc is None, f"unexpected exception: {d.exc!r}"
    assert set(d.result) == RETURN_KEYS
    assert d.result["primary_result"] == V1_RESULT


def _assert_full_shadow(d: Drive) -> None:
    """The shipped shadow-mode happy path, values and all."""
    _assert_return_shape(d)
    assert d.result["shadow_result"] == V2_RESULT
    assert d.result["score_diff"] == 50
    assert d.result["v1_latency_ms"] == V1_LAT
    assert d.result["v2_latency_ms"] == V2_LAT
    assert d.errors == []
    assert d.warnings == []


# --- keys 4, 5, 6, 7 (V1 call site, L958) ------------------------------------
@pytest.mark.asyncio
async def test_v1_call_site_forwards_context_and_v1_version(analyzer):
    """Kills 4, 5, 6, 7.

    Shipped L957-958 makes the V1 call as call('CTX', prompt_version=
    'v1_original') and the fake receives exactly that.
      4  context -> None         -> the fake receives (None, version)
      5  prompt_version -> None  -> the fake receives ('CTX', None)
      6  context dropped         -> autospec spec check raises TypeError
                                    "missing a required argument: 'context'"
                                    *before* the mock records the call; it
                                    propagates out of run_shadow_analysis
                                    through the L959-962 log+re-raise arm, so
                                    the drive has exc set and no result
      7  prompt_version dropped  -> call_args carries no version at all and
                                    the drive loses its V2 leg
    """
    d = await drive(analyzer)
    _assert_full_shadow(d)
    assert len(d.v1_calls) == 1, "kills 7 (a dropped version leaves no V2 discrimination)"
    assert (d.v1_calls[0].args, d.v1_calls[0].kwargs) == (
        ("CTX",),
        {"prompt_version": V1_VERSION},
    )
    assert d.v1_seen == [(("CTX",), {"prompt_version": V1_VERSION})], "kills 4 and 5"


# --- keys 19, 20, 21, 22 (V2 call site, L974) -------------------------------
@pytest.mark.asyncio
async def test_v2_call_site_forwards_context_and_v2_version(analyzer):
    """Kills 19, 20, 21, 22 — the same four shapes on the V2 call site.

    19 context -> None        -> v2_seen receives (None, 'v2_calibrated')
    20 prompt_version -> None -> v2_seen receives ('CTX', None)
    21 context dropped         -> spec-check TypeError inside the V2 try,
                                  caught at L992: one WARNING, no recorded
                                  V2 call, shadow_result None, score_diff 0
    22 prompt_version dropped  -> no call in the recorded list carries
                                  prompt_version='v2_calibrated'
    """
    d = await drive(analyzer)
    _assert_full_shadow(d)
    assert len(d.v2_calls) == 1, "kills 21 and 22"
    assert (d.v2_calls[0].args, d.v2_calls[0].kwargs) == (
        ("CTX",),
        {"prompt_version": V2_VERSION},
    )
    assert d.v2_seen == [(("CTX",), {"prompt_version": V2_VERSION})], "kills 19 and 20"


# --- keys 8, 9, 10, 11 (v1_latency_ms, L963) -------------------------------
@pytest.mark.asyncio
async def test_v1_latency_ms_is_delta_times_1000_in_result_and_log_call(analyzer):
    """Kills 8, 9, 10, 11.

    Shipped L963 with clock 100.0 -> 100.5 gives exactly 500.0, which the
    function both returns (L999) and forwards to the log call (L988).
    Mutated: 8 -> None in both places; 9 -> 0.5; 10 -> 200500.0;
    11 (x1001) -> 500.5.
    """
    d = await drive(analyzer)
    _assert_full_shadow(d)
    assert d.result["v1_latency_ms"] == V1_LAT
    assert d.log_kwargs["v1_latency_ms"] == V1_LAT


# --- keys 23, 24, 25, 26 (v2_latency_ms, L976) -----------------------------
@pytest.mark.asyncio
async def test_v2_latency_ms_is_delta_times_1000_in_result_and_log_call(analyzer):
    """Kills 23, 24, 25, 26.

    Shipped L976 with clock 100.5 -> 100.75 gives 250.0 in the return dict
    (L1000) and in the log call's v2_latency_ms kwarg (L989). Mutated:
    23 -> None; 24 -> 0.25; 25 -> 201250.0; 26 -> 250.25.
    """
    d = await drive(analyzer)
    _assert_full_shadow(d)
    assert d.result["v2_latency_ms"] == V2_LAT
    assert d.log_kwargs["v2_latency_ms"] == V2_LAT


# --- keys 12, 13, 14, 15, 16 (pre-branch defaults, L966-968) ---------------
@pytest.mark.asyncio
async def test_non_shadow_mode_returns_the_three_initial_defaults(analyzer):
    """Kills 12, 13, 14, 15, 16.

    With config.shadow_mode False the L970 guard skips the whole V2 block, so
    the defaults initialised at L966-968 are the entire payload of
    shadow_result / v2_latency_ms / score_diff. As shipped:
      {'primary_result': V1, 'shadow_result': None, 'score_diff': 0.0,
       'v1_latency_ms': 500.0, 'v2_latency_ms': 0.0}
    with no log call and no log records. 12 -> "" ; 13 -> None ; 14 -> 1.0 ;
    15 -> None ; 16 -> 1.0.
    """
    d = await drive(analyzer, shadow_mode=False)
    _assert_return_shape(d)
    assert d.result == {
        "primary_result": V1_RESULT,
        "shadow_result": None,
        "score_diff": 0.0,
        "v1_latency_ms": V1_LAT,
        "v2_latency_ms": 0.0,
    }
    assert d.log_calls == []
    assert d.errors == []
    assert d.warnings == []
    assert len(d.v1_calls) == 1 and d.v2_calls == []


# --- keys 28-34, 36-42, 43, 45 (the score_diff arithmetic, L979-981) -------
@pytest.mark.asyncio
async def test_score_diff_uses_risk_score_with_default_zero(analyzer):
    """Kills 28, 29, 31, 32, 33, 34, 36, 37, 39, 40, 41, 42, 43, 45.

    Drives shipped L979-981 (`v1_result.get("risk_score", 0)` /
    `v2_result.get("risk_score", 0)` / `abs(v1_score - v2_score)`) through
    four inputs whose score_diff is pinned from the shipped probe:
      both carry risk_score -> 50  (kills 28 whose key becomes None: 30; the
                                    key renames 32/33 -> 30, 36/40/41 -> 80;
                                    45 whose '-' became '+': 110; 43 -> None)
      v2 without risk_score -> P0.3 DRIFT RE-PIN (#6678): shipped became
                                    .get("risk_score") with the honest-
                                    incomparable rule -> None side => -1.0
      v1 without risk_score -> 30  (kills 34 default 1 -> 29; 29/31 -> abort)
      both without          -> 0   (kills 29/31/37/39 via the abort WARNING and
                                    34/42 -> abs(1-1)=0 but 34/42 already died
                                    in the single-side drives above)
    """
    d = await drive(analyzer)
    assert d.exc is None and d.warnings == []
    assert d.result["score_diff"] == 50, "kills 28 32 33 36 40 41 43 45"

    d_v2 = await drive(analyzer, v2={"risk_level": "low"})
    # P0.3 (#6678): NULL score is INCOMPARABLE -> -1.0, never a laundered 0.
    # Pre-drift this pinned 80; 37/39/42 claims are historical (nemotron is
    # out of the mutation denominator -- this battery is regression coverage).
    assert d_v2.result["score_diff"] == -1.0
    assert d_v2.result["shadow_result"] == {"risk_level": "low"}

    d_v1 = await drive(analyzer, v1={"risk_level": "high"})
    assert d_v1.result["score_diff"] == -1.0  # P0.3: None side -> -1.0 (was 30)

    d_none = await drive(analyzer, v1={"risk_level": "high"}, v2={"risk_level": "low"})
    assert d_none.result["score_diff"] == -1.0  # P0.3: both None -> -1.0 (was 0)
    assert d_none.warnings == []
    assert d_none.result["shadow_result"] == {"risk_level": "low"}


# --- keys 43, 49, 50, 55 (post-assignment failure arm) ---------------------
@pytest.mark.asyncio
async def test_v2_arm_failure_after_log_call_keeps_computed_score_diff(analyzer):
    """Kills 49, 50, 55 (43 dies again, primarily in the score-diff test).

    All three land at or after the log call, so a failing log call is what
    separates them from the healthy drive: with _log_shadow_result raising
    (swallowed by L992) the SHIPPED function still returns score_diff 50 with
    both latencies — score_diff was computed at L981 *before* the call.
      49/50 (a latency kwarg -> None) -> awaited kwargs change.
      55 (v2_latency_ms kwarg dropped) -> legal (it is the only DEFAULTED
         parameter of _log_shadow_result) and leaves a four-kwarg await.
    """
    analyzer.set_experiment_config(PromptExperimentConfig(shadow_mode=True))
    boom = AsyncMock(side_effect=RuntimeError("log-boom"))
    clock = PhaseClock()

    async def llm(context, prompt_version=V1_VERSION):
        clock.advance()
        return dict(V1_RESULT) if prompt_version == V1_VERSION else dict(V2_RESULT)

    with (
        patch.object(analyzer, "_call_llm_with_version", autospec=True, side_effect=llm),
        patch.object(analyzer, "_log_shadow_result", boom),
        patch("time.monotonic", autospec=True, side_effect=clock),
    ):
        result = await analyzer.run_shadow_analysis(camera_id="cam-1", context="CTX")

    assert result["score_diff"] == 50, "kills 43 (None != 50)"
    assert result["shadow_result"] == V2_RESULT
    assert result["v1_latency_ms"] == V1_LAT and result["v2_latency_ms"] == V2_LAT
    assert boom.await_count == 1
    assert boom.await_args.kwargs == LOG_KWARGS, "kills 49, 50, 55"


# --- keys 46, 47, 48, 51, 52, 53, 54, 55 (log-call payload) ----------------
@pytest.mark.asyncio
async def test_log_shadow_result_receives_all_five_kwargs_by_value(analyzer):
    """Kills 46 (camera_id -> None), 47 (v1_result -> None), 48 (v2_result ->
    None), 51/52/53/54 (camera_id / v1_result / v2_result / v1_latency_ms
    dropped) and 55 (v2_latency_ms dropped).

    A non-default camera id pins that the caller's camera_id is forwarded by
    value rather than replaced by None (46), and the shipped five-kwarg call
    is recorded exactly once. 51-54 each drop a REQUIRED parameter of
    _log_shadow_result (L1066-1071), so the autospec spec check raises
    TypeError inside the V2 try (caught at L992): zero recorded calls plus
    exactly one WARNING. 55 drops the only DEFAULTED parameter, which is
    legal and leaves a four-kwarg call that never equals the pinned shape.
    """
    d = await drive(analyzer, camera_id="gate-7")
    _assert_full_shadow(d)
    assert len(d.log_calls) == 1, "kills 51 52 53 54 (no call is recorded)"
    assert d.warnings == [], "kills 51 52 53 54 (spec-check TypeError arm)"
    kwargs = dict(d.log_kwargs)
    assert kwargs["camera_id"] == "gate-7", "kills 46"
    kwargs["camera_id"] = "cam-1"
    assert kwargs == LOG_KWARGS, "kills 47 48 55"


# --- keys 58-65 (return-dict key names, L996-1000) --------------------------
@pytest.mark.asyncio
async def test_return_dict_key_names_in_both_modes(analyzer):
    """Kills 58, 59, 60, 61, 62, 63, 64, 65.

    Each of the four non-primary keys of the returned dict is renamed twice
    (once to "XX<x>XX", once to UPPER). Both the shadow-mode drive and the
    non-shadow drive are asserted so a rename cannot hide behind an exception
    path — the L995-1001 dict literal is the sole observable for these eight
    keys.
    """
    d = await drive(analyzer)
    _assert_full_shadow(d)
    assert set(d.result) == RETURN_KEYS, "kills 58 59 60 61 62 63 64 65 (shadow mode)"

    d2 = await drive(analyzer, shadow_mode=False)
    assert set(d2.result) == RETURN_KEYS, "kills 58 59 60 61 62 63 64 65 (non-shadow mode)"


# --- the shipped exception arms (kills 6; corroborates 21, 31, 39, 51-54) --
@pytest.mark.asyncio
async def test_v1_failure_propagates_after_error_log(analyzer):
    """Kills 6 and pins the shipped L959-962 arm.

    With the V1 call's `context` dropped, the autospec spec check raises
    TypeError inside the V1 try; the shipped handler logs one ERROR
    ("V1 prompt failed in shadow analysis: ...") and RE-RAISES, so the caller
    gets an exception, no result dict, and neither collaborator records
    anything. On shipped code the same drive completes with no ERROR record,
    both LLM calls recorded and one log call.
    """
    d = await drive(analyzer)
    assert d.exc is None, "kills 6 (the mutant propagates a spec TypeError)"
    assert d.errors == [], "kills 6 (shipped logs ERROR only when V1 really fails)"
    assert d.result is not None and set(d.result) == RETURN_KEYS
    assert len(d.llm_calls) == 2, "kills 6, 21, 51-54"
    assert len(d.log_calls) == 1, "kills 6, 51, 52, 53, 54"


@pytest.mark.asyncio
async def test_v2_failure_continues_with_v1_defaults(analyzer):
    """Kills 21, 31, 39, 51, 52, 53, 54 (second, arm-shaped kill) and pins the
    shipped L992-993 arm.

    Shipped: when the V2 call itself fails, the arm is swallowed with exactly
    one WARNING carrying the shipped message, no log call, and the three
    L966-968 defaults survive in the return dict. A mutant that turns any
    in-try expression into a TypeError (21 dropped context; 31/39 a None
    default on a dict without `risk_score`; 51-54 a dropped required kwarg on
    the log call) reproduces that WARNING+defaults signature on a drive where
    shipped code emits no WARNING at all — pinned here and in the two tests
    above via `warnings == []`.
    """
    d = await drive(analyzer, v1={"risk_level": "high"}, v2={"risk_level": "low"})
    assert d.warnings == [], "kills 31 and 39"
    assert d.result["score_diff"] == -1.0  # P0.3: None -> incomparable sentinel
    assert d.result["shadow_result"] == {"risk_level": "low"}

    d2 = await drive(analyzer, v2_fails=True)
    assert d2.result == {
        "primary_result": V1_RESULT,
        "shadow_result": None,
        "score_diff": 0.0,
        "v1_latency_ms": V1_LAT,
        "v2_latency_ms": 0.0,
    }
    assert d2.warnings == [V2_FAIL_MSG]
    assert d2.log_calls == []
    assert d2.errors == []
