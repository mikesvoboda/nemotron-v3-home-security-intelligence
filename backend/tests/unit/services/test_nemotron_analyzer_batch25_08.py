"""Batch-25 chunk-08 kill battery: NemotronAnalyzer._call_llm#chunk4 (33 keys).

Every mutant in this chunk sits on a single statement inside
backend/services/nemotron_analyzer.py :: NemotronAnalyzer._call_llm
(lines 4167-4249). Each test below asserts behavior that was PROBED from the
shipped function first (scratch probe: /tmp/wp-batch25/probes/chunk08/
probe_shipped.py — 4 passed) — production is pinned exactly AS SHIPPED; no
source change is proposed anywhere in this file.

This file lives OUTSIDE the repo tree, so the repo conftest does not apply:
the minimum env vars mirror backend/tests/conftest.py values verbatim
(ENVIRONMENT / PYROSCOPE_ENABLED / PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION /
DATABASE_URL / OTEL_ENABLED — copied, not invented), and every mock patch
carries autospec=True per the CI ratchet.

Occurrence-twin note: all 33 keys are group_size-1 shape groups (feed.json
functions["xǁNemotronAnalyzerǁ_call_llm"].shapes[299..331]), verified by
diffing every instrumented variant body against the shipped function — each
variant changes exactly one expression, so one named key per test is the
complete twin set for that shape.
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# Mirror of backend/tests/conftest.py env defaults (copied values), required
# because this file sits outside the repo tree and repo conftest.py does not
# apply. Settings() raises without DATABASE_URL; ENVIRONMENT=test keeps the
# weak-password validator off.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("OTEL_ENABLED", "false")


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def mock_settings():
    """Copy of backend/tests/unit/services/test_nemotron_analyzer.py::mock_settings."""
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
def analyzer(mock_settings):
    """NemotronAnalyzer with mocked settings, mirrors the repo fixture."""
    from backend.core.redis import RedisClient
    from backend.services.nemotron_analyzer import NemotronAnalyzer

    mock_redis_client = MagicMock(spec=RedisClient)
    mock_redis_client.get = AsyncMock(return_value=None)
    mock_redis_client.set = AsyncMock(return_value=True)

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


ARGS = dict(
    camera_name="Front Door",
    start_time="2025-12-23T14:30:00",
    end_time="2025-12-23T14:31:00",
    detections_list="1. 14:30:00 - person (confidence: 0.95)",
)


def _ok_response(content: str):
    """MagicMock httpx.Response with a completion payload (repo-test idiom)."""
    import httpx

    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"content": content, "usage": {}}
    return resp


def _boom():
    """The unexpected-error fixture: RuntimeError (not ValueError/TimeoutError/
    httpx.HTTPStatusError, which all have dedicated earlier except clauses)."""
    return RuntimeError("kaboom failure")


# ------------------------------------------------------- success-path tail


@pytest.mark.asyncio
async def test_success_result_carries_prompt_and_metrics(analyzer):
    """Kills xǁNemotronAnalyzerǁ_call_llm__mutmut_575, mutmut_576, mutmut_577.

    Shipped (line 4249): `risk_data["llm_prompt"] = prompt` — the returned
    dict carries the EXACT prompt string the analyzer POSTed (probe: shipped
    returns str len 3642 == payload["prompt"], and the dict has no
    "XXllm_promptXX"/"LLM_PROMPT" key). Pins:
      575 (`= None`): value must equal the sent prompt, not None.
      576/577 (key renamed): "llm_prompt" present and equal; no extra key
      leaks into the returned dict.
    """

    content = json.dumps(
        {"risk_score": 77, "risk_level": "high", "summary": "sum", "reasoning": "rea"}
    )
    with patch("httpx.AsyncClient.post", autospec=True) as mock_post:
        mock_post.return_value = _ok_response(content)
        result = await analyzer._call_llm(**ARGS)

    sent_prompt = mock_post.call_args.kwargs["json"]["prompt"]
    assert result["llm_prompt"] == sent_prompt
    assert isinstance(result["llm_prompt"], str)
    assert "XXllm_promptXX" not in result
    assert "LLM_PROMPT" not in result
    # shipped also pins raw_response to the completion text (line 4253) —
    # guards this test against mistaking the wrong echo key for llm_prompt
    assert result["raw_response"] == content


@pytest.mark.asyncio
async def test_success_metrics_get_real_risk_level_and_template(analyzer):
    """Kills xǁNemotronAnalyzerǁ_call_llm__mutmut_566, mutmut_569.

    Shipped (lines 4228-4229):
      record_event_by_risk_level(risk_data["risk_level"])
      record_prompt_template_used(template_name)
    Probe: shipped calls both exactly once with the validated level ("high")
    and the template name ("basic" — no enriched/enrichment context in ARGS).
    Both mutants pass None; autospec keeps the non-nullable signature so a
    spy can pin the exact arguments.
    """

    content = json.dumps(
        {"risk_score": 77, "risk_level": "high", "summary": "sum", "reasoning": "rea"}
    )
    with (
        patch("httpx.AsyncClient.post", autospec=True) as mock_post,
        patch(
            "backend.services.nemotron_analyzer.record_event_by_risk_level", autospec=True
        ) as risk_spy,
        patch(
            "backend.services.nemotron_analyzer.record_prompt_template_used", autospec=True
        ) as tmpl_spy,
    ):
        mock_post.return_value = _ok_response(content)
        result = await analyzer._call_llm(**ARGS)

    assert result["risk_level"] == "high"  # sanity: value passed downstream is this
    risk_spy.assert_called_once_with("high")
    tmpl_spy.assert_called_once_with("basic")


# ------------------------------------------------- 4xx client-error branch


@pytest.mark.asyncio
async def test_client_error_log_record_carries_status_code_extra(analyzer, caplog):
    """Kills xǁNemotronAnalyzerǁ_call_llm__mutmut_506, mutmut_507.

    Shipped (line 4169): logger.error(f"Nemotron client error {status_code}:
    {e}", extra={"status_code": status_code}) for the 4xx branch, then
    `raise` re-raises immediately. Probe: shipped emits exactly one POST and
    the ERROR LogRecord has attribute status_code == 400. Mutants rename the
    extra key ("XXstatus_codeXX" / "STATUS_CODE"), so the record loses the
    attribute — pinned by attribute identity, not by the message text
    (which embeds the code independently of `extra`).
    """
    import httpx

    req = MagicMock(spec=httpx.Request)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 400
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=req, response=resp
    )
    caplog.set_level("ERROR")
    with patch("httpx.AsyncClient.post", autospec=True) as mock_post:
        mock_post.return_value = resp
        with pytest.raises(httpx.HTTPStatusError):
            await analyzer._call_llm(**ARGS)

    assert mock_post.call_count == 1  # shipped: no retry for 4xx
    rec = next(
        r
        for r in caplog.records
        if "Nemotron client error" in r.getMessage() and r.levelname == "ERROR"
    )
    assert rec.getMessage() == "Nemotron client error 400: Bad Request"
    assert rec.status_code == 400


# ------------------------------------------- unexpected-error record_exception


@pytest.mark.asyncio
async def test_unexpected_error_record_exception_arguments(analyzer):
    """Kills xǁNemotronAnalyzerǁ_call_llm__mutmut_509, mutmut_510, mutmut_511,
    mutmut_512, mutmut_513, mutmut_514, mutmut_515, mutmut_516, mutmut_517,
    mutmut_518, mutmut_519, mutmut_520.

    Shipped (line 4180):
      record_exception(e, {"error_type": "unexpected", "attempt": attempt + 1})
    Probe: with _max_retries=2 and post() always raising, shipped records the
    exception once per attempt, each time with the exception object itself and
    attempts [1, 2] (attempt + 1). Autospec'd spy pins every mutated operand:
      509 (None for e): args[0] is the raised RuntimeError, twice.
      510 (attributes -> None): args[1] is the exact dict.
      511 (drop exception arg): autospec TypeError under the mutant + args[0] pin.
      512 (drop attributes arg): same.
      513/514 ("error_type" key renamed): dict pins the exact key.
      515/516 (value mutated): dict pins the exact lowercase "unexpected".
      517/518 ("attempt" key renamed): dict pins the exact key.
      519/520 (attempt + 1 -> -1 / +2): pinned attempt-number sequence [1, 2].
    """

    boom = _boom()
    with (
        patch("httpx.AsyncClient.post", autospec=True) as mock_post,
        patch("backend.services.nemotron_analyzer.record_exception", autospec=True) as spy,
    ):
        mock_post.side_effect = boom
        with pytest.raises(Exception):
            await analyzer._call_llm(**ARGS)

    assert mock_post.call_count == 2
    assert spy.call_count == 2
    for i, call in enumerate(spy.call_args_list):
        assert call.args[0] is boom
        assert call.args[1] == {"error_type": "unexpected", "attempt": i + 1}


@pytest.mark.asyncio
async def test_unexpected_error_retry_warning_exact_message(analyzer, caplog):
    """Kills xǁNemotronAnalyzerǁ_call_llm__mutmut_532, mutmut_536,
    mutmut_537, mutmut_538.

    Shipped (lines 4183-4191): the retry logger.warning builds
      f"Unexpected Nemotron error (attempt {attempt + 1}/{self._max_retries}), "
      f"retrying in {delay}s: {sanitize_error(e)}"
    Probe: shipped emits exactly
      "Unexpected Nemotron error (attempt 1/2), retrying in 1s: kaboom failure"
    Pins (exact message equality on the retry WARNING):
      532 (both f-string args -> None): message becomes "None" -> fails.
      536/537 (attempt + 1 -> -1 / +2): attempt counter must read 1.
      538 (sanitize_error(None)): shipped sanitize_error(None) renders "None"
      (str(None), no credential/path matches), so the sanitized real error
      text must appear and the literal tail must NOT be "None".
    """

    caplog.set_level("WARNING")
    with patch("httpx.AsyncClient.post", autospec=True) as mock_post:
        mock_post.side_effect = _boom()
        with pytest.raises(Exception):
            await analyzer._call_llm(**ARGS)

    retry_msgs = [
        r.getMessage()
        for r in caplog.records
        if r.levelname == "WARNING" and "Unexpected Nemotron error" in r.getMessage()
    ]
    assert retry_msgs == ["Unexpected Nemotron error (attempt 1/2), retrying in 1s: kaboom failure"]
    # 538 also kills via the ERROR line? No — 538 mutates ONLY the retry
    # warning's sanitize_error arg; pin the exhaustion ERROR line as shipped
    # anyway so this test cannot drift into asserting a mutant-friendly shape.
    err_msgs = [
        r.getMessage()
        for r in caplog.records
        if r.levelname == "ERROR" and "Unexpected Nemotron error" in r.getMessage()
    ]
    assert err_msgs == ["Unexpected Nemotron error after 2 attempts: kaboom failure"]


# ------------------------------------------------- retry-exhaustion tail


@pytest.mark.asyncio
async def test_exhaustion_span_attributes_exact_failure_pair(analyzer):
    """Kills xǁNemotronAnalyzerǁ_call_llm__mutmut_548, mutmut_549,
    mutmut_550, mutmut_551, mutmut_552.

    Shipped (lines 4204-4207), inside the `for ... else:` clause reached when
    every attempt fails WITHOUT break:
      add_span_attributes(llm_success=False, llm_attempts=self._max_retries)
    Setup: post() raises on BOTH attempts (shipped failure path), so the
    loop exhausts range(2) and the else clause runs. add_span_attributes is
    then called exactly twice in this run — the span-open call (llm_service=
    …, line 3963) and this failure call; the success-path call (line 4029,
    llm_success=True) is never reached, so exactly ONE recorded call carries
    llm_success. Pins that call's exact kwargs dict:
      548 (False -> None) / 550 (kwarg removed) / 552 (False -> True):
        llm_success must be False.
      549 (None) / 551 (kwarg removed): llm_attempts must be 2 (max_retries).
    """

    from backend.core.telemetry import add_span_attributes

    with (
        patch("httpx.AsyncClient.post", autospec=True) as mock_post,
        patch(
            "backend.services.nemotron_analyzer.add_span_attributes",
            side_effect=lambda **kw: add_span_attributes(**kw),
            autospec=True,
        ) as spy,
    ):
        mock_post.side_effect = _boom()
        with pytest.raises(Exception):
            await analyzer._call_llm(**ARGS)

    assert mock_post.call_count == 2  # both attempts failed -> else clause
    calls = [c.kwargs for c in spy.call_args_list]
    assert sum(1 for c in calls if "llm_success" in c) == 1
    failure = next(c for c in calls if "llm_success" in c)
    assert failure == {"llm_success": False, "llm_attempts": 2}


@pytest.mark.asyncio
async def test_exhaustion_error_wraps_original_exception(analyzer):
    """Kills xǁNemotronAnalyzerǁ_call_llm__mutmut_555, mutmut_557.

    Shipped (lines 4208-4212):
      if last_exception:
          raise AnalyzerUnavailableError(error_msg, original_error=last_exception)
          from last_exception
    Probe: shipped raises AnalyzerUnavailableError with .original_error being
    the SAME object the post() side_effect raised.
      555 (original_error=None): pinned identity `err.original_error is boom`.
      557 (kwarg removed -> default None): same identity assertion kills it;
        the `from last_exception` clause is untouched by 557, so __cause__
        alone would NOT kill it — the pinned attribute is the load-bearing
        assertion (documented here so the red-check isn't misread).
    """

    from backend.core.exceptions import AnalyzerUnavailableError

    boom = _boom()
    with patch("httpx.AsyncClient.post", autospec=True) as mock_post:
        mock_post.side_effect = boom
        with pytest.raises(AnalyzerUnavailableError) as ei:
            await analyzer._call_llm(**ARGS)

    err = ei.value
    assert str(err) == "Nemotron LLM call failed after 2 attempts"
    assert err.original_error is boom
    # shipped-chained cause (unchanged by 557, pinned for shipped fidelity)
    assert err.__cause__ is boom


@pytest.mark.asyncio
async def test_parse_failure_attaches_raw_completion(analyzer):
    """Kills xǁNemotronAnalyzerǁ_call_llm__mutmut_560.

    Shipped (line 4220): `parse_err.raw_completion = completion_text` before
    re-raising the parse ValueError. Probe: shipped ValueError carries
    .raw_completion == "no json here at all" (the completion text). The
    mutant sets it to None — pinned by value AND by attribute presence.
    """

    with patch("httpx.AsyncClient.post", autospec=True) as mock_post:
        mock_post.return_value = _ok_response("no json here at all")
        with pytest.raises(ValueError) as ei:
            await analyzer._call_llm(**ARGS)

    assert ei.value.raw_completion == "no json here at all"


# ------------------------------------------------- calibration monitor glue


@pytest.mark.asyncio
async def test_calibration_monitor_record_score_called_once(analyzer):
    """Kills xǁNemotronAnalyzerǁ_call_llm__mutmut_573, mutmut_574.

    Shipped (lines 4235-4246):
      cal_monitor = get_calibration_monitor()
      if cal_monitor is not None:
          await cal_monitor.record_score(risk_data["risk_score"])
    get_calibration_monitor() is a function-local import (line 4235), so the
    patch target is the calibration_monitor module attribute itself. The
    monitor identity is passed through the module global so the shipped None
    guard actually executes (a fake whose record_score raises would be
    swallowed by the shipped non-critical except — the spy below proves the
    call happened, which the guard-gating mutants 573/574 both break:
      573 (`cal_monitor = None`): branch never taken -> 0 calls.
      574 (`if cal_monitor is None:`): branch skipped for a real monitor -> 0 calls.
    """

    cal_mod = pytest.importorskip("backend.services.calibration_monitor")
    monitor = MagicMock()
    monitor.record_score = AsyncMock(return_value=None)
    content = json.dumps(
        {"risk_score": 77, "risk_level": "high", "summary": "sum", "reasoning": "rea"}
    )
    with (
        patch("httpx.AsyncClient.post", autospec=True) as mock_post,
        patch.object(cal_mod, "get_calibration_monitor", return_value=monitor, autospec=True),
    ):
        mock_post.return_value = _ok_response(content)
        result = await analyzer._call_llm(**ARGS)

    assert result["risk_score"] == 77
    monitor.record_score.assert_awaited_once_with(77)
