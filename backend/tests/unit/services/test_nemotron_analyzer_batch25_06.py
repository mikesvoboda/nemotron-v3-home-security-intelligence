"""Batch-25 kill battery — chunk "NemotronAnalyzer._call_llm#chunk2" (130 keys).

Shipped region: backend/services/nemotron_analyzer.py:3811-4255 (_call_llm).
All 130 keys adjudicated here are KILLABLE and killed by this file; every
mutant writes into an externally visible observable:

  * record_nemotron_tokens / cost_tracker.track_llm_usage /
    set_llm_inference_attributes / set_inference_result_attributes /
    add_span_attributes  -> mocked call kwargs (success path),
  * last_exception       -> AnalyzerUnavailableError.original_error + __cause__,
  * record_exception     -> mocked call args (exception instance + attrs dict),
  * retry predicate + exponential-backoff delay -> the asyncio.sleep sequence
    (autospec-replaced so real time is never billed),
  * logger.warning(...) msg + extra           -> emitted LogRecord fields.

Duration arithmetic (* 1000 vs / 1000 vs * 1001) is pinned WITHOUT patching
time: nemotron_analyzer.time is the shared stdlib module, so monkeypatching
monotonic poisons the event loop (StopIteration inside loop.time()). Instead
the success tests first read the exact duration_seconds the (unmutated) token
call received and require every duration-derived kwarg to equal that same
quantity scaled per argument.

Occurrence-twins (identical minus/plus shapes replicated across the five
except handlers: connection_error / timeout / asyncio_timeout / server_error /
unexpected) are carried in FULL: each twin group's keys are spread across the
five handler tests, one assertion set per handler site.

RED-CHECK: apply each named key (single-occurrence shape or ALL twins of a
shape), run the named test from this file, expect failure.
"""

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

pytestmark = pytest.mark.unit

from backend.core.exceptions import AnalyzerUnavailableError
from backend.services.nemotron_analyzer import NemotronAnalyzer

GOOD_BODY = {
    "content": json.dumps(
        {
            "risk_score": 60,
            "risk_level": "high",
            "summary": "Unusual activity",
            "reasoning": "Person at odd hours",
        }
    )
}

SETTINGS = SimpleNamespace(
    nemotron_max_output_tokens=512,
    nemotron_read_timeout=120.0,
    ai_connect_timeout=10.0,
)


def _make_analyzer(max_retries: int = 3) -> NemotronAnalyzer:
    # __new__ skips the heavy __init__; _call_llm touches only the attrs set
    # here plus the patched seams below.
    a = NemotronAnalyzer.__new__(NemotronAnalyzer)
    a._max_retries = max_retries
    a._use_guided_json = False
    a._llm_url = "http://llm.test:9/v1"
    a._api_key = None
    a._redis = None
    return a


def _facade():
    facade = MagicMock(name="facade")
    facade.get_inference_semaphore.return_value = asyncio.Semaphore(4)
    facade.get_cost_tracker.return_value = MagicMock(name="cost_tracker")
    return facade


def _ok_response(body):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = dict(body)
    return resp


async def _call_with_post(analyzer, post):
    facade = _facade()
    # SimpleNamespace client: the post seam carries ONLY url + json=/headers=
    # kwargs, so no kwargs-scan helper below can mistake it for a telemetry
    # call (none of them uses a duration_seconds kwarg name).
    analyzer._http_client = SimpleNamespace(post=post)
    with (
        patch.object(NemotronAnalyzer, "_build_prompt", autospec=True, return_value="PROMPT"),
        patch.object(
            NemotronAnalyzer, "_validate_and_truncate_prompt", autospec=True, return_value="PROMPT"
        ),
        patch.object(NemotronAnalyzer, "_get_facade", autospec=True, return_value=facade),
        patch(
            "backend.services.nemotron_analyzer.get_settings",
            autospec=True,
            return_value=SETTINGS,
        ),
        patch("backend.services.nemotron_analyzer.observe_risk_score", autospec=True),
        patch("backend.services.nemotron_analyzer.observe_risk_score_distribution", autospec=True),
        patch("backend.services.nemotron_analyzer.record_event_by_risk_level", autospec=True),
        patch("backend.services.nemotron_analyzer.record_prompt_template_used", autospec=True),
    ):
        result = await analyzer._call_llm("cam1", "start", "end", "1. 12:00:00 - person")
    return result, facade


async def _success(usage, max_retries=3):
    a = _make_analyzer(max_retries)
    post = AsyncMock(name="http_post", return_value=_ok_response({**GOOD_BODY, "usage": usage}))
    with (
        patch("backend.services.nemotron_analyzer.record_nemotron_tokens", autospec=True) as tok,
        patch(
            "backend.services.nemotron_analyzer.set_llm_inference_attributes", autospec=True
        ) as llat,
        patch(
            "backend.services.nemotron_analyzer.set_inference_result_attributes", autospec=True
        ) as irat,
        patch("backend.services.nemotron_analyzer.add_span_attributes", autospec=True) as span,
    ):
        result, facade = await _call_with_post(a, post)
    return {
        "result": result,
        "tracker": facade.get_cost_tracker.return_value,
        "tokens": tok,
        "llat": llat,
        "irat": irat,
        "span": span,
        "post": post,
    }


def _kwargs_containing(mock, key):
    """All kwargs dicts recorded on `mock` that contain `key`."""
    dicts = [c.kwargs for c in mock.call_args_list if c.kwargs and key in c.kwargs]
    assert dicts, f"no call on mock carried kwarg {key!r}"
    return dicts


def _assert_ms_scale(mock, key, duration_seconds):
    """Pins `<key> == duration_seconds * 1000` at every call site of `key`.

    duration_seconds is the real (unmutated, unpatched) elapsed time taken
    from the record_nemotron_tokens call, so *1000 vs /1000 vs *1001 are all
    distinguished by one float comparison per site.
    """
    assert duration_seconds is not None
    for d in _kwargs_containing(mock, key):
        assert d[key] == pytest.approx(duration_seconds * 1000), d


async def _drain(exc, max_retries=7):
    """Drive _call_llm to retry exhaustion; return pinned observables."""
    a = _make_analyzer(max_retries)
    facade = _facade()

    async def _post(url, **kwargs):
        raise exc

    a._http_client = SimpleNamespace(post=_post)

    class Capture(logging.Handler):
        def __init__(self):
            super().__init__(level=logging.DEBUG)
            self.records = []

        def emit(self, record):
            self.records.append(record)

    cap = Capture()
    lg = logging.getLogger("backend.services.nemotron_analyzer")
    old_level = lg.level
    lg.addHandler(cap)
    lg.setLevel(logging.DEBUG)
    try:
        with (
            patch.object(NemotronAnalyzer, "_build_prompt", autospec=True, return_value="PROMPT"),
            patch.object(
                NemotronAnalyzer,
                "_validate_and_truncate_prompt",
                autospec=True,
                return_value="PROMPT",
            ),
            patch.object(NemotronAnalyzer, "_get_facade", autospec=True, return_value=facade),
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                autospec=True,
                return_value=SETTINGS,
            ),
            patch("backend.services.nemotron_analyzer.record_exception", autospec=True) as rec,
            patch(
                "backend.services.nemotron_analyzer.record_pipeline_error", autospec=True
            ) as perr,
            patch("backend.services.nemotron_analyzer.add_span_attributes", autospec=True) as span,
            patch("asyncio.sleep", autospec=True) as sleeper,
        ):
            with pytest.raises(AnalyzerUnavailableError) as excinfo:
                await a._call_llm("cam1", "start", "end", "1. 12:00:00 - person")
    finally:
        lg.removeHandler(cap)
        lg.setLevel(old_level)
    warns = [r for r in cap.records if r.levelno == logging.WARNING]
    return {
        "exc": excinfo.value,
        "rec": rec,
        "perr": perr,
        "span": span,
        "sleeps": [c.args[0] for c in sleeper.call_args_list],
        "warns": warns,
    }


def _assert_exhaustion_shape(obs, exc_obj, max_retries, perr_name, error_type, status_code=None):
    """Cross-handler invariants of the retry-exhaustion path.

    Carries the occurrence-twins of shapes replicated at all five handlers:
      - last_exception = e                -> original_error / __cause__ is e,
      - record_exception(e, {...})        -> instance + attrs dict (every
                                             attempt carries "attempt": k),
      - if attempt < max_retries - 1      -> exactly max_retries-1 sleeps,
      - delay = min(2**attempt, 30)       -> the exact sleep sequence,
      - warning extra {...} dict          -> attempt/max_retries/retry_delay
                                             attributes on every warning.
    """
    assert obs["exc"].original_error is exc_obj
    assert obs["exc"].__cause__ is exc_obj
    assert obs["perr"].call_args.args == (perr_name,)
    assert obs["rec"].call_count == max_retries
    expected_attrs = {"error_type": error_type, "attempt": 1}
    if status_code is not None:
        expected_attrs = {"error_type": error_type, "status_code": status_code, "attempt": 1}
    first = obs["rec"].call_args_list[0]
    assert first.args[0] is exc_obj
    assert first.args[1] == expected_attrs
    assert [c.args[1]["attempt"] for c in obs["rec"].call_args_list] == list(
        range(1, max_retries + 1)
    )
    assert obs["sleeps"] == [1, 2, 4, 8, 16, 30]
    assert len(obs["warns"]) == max_retries - 1
    first_warn = obs["warns"][0]
    assert (first_warn.attempt, first_warn.max_retries, first_warn.retry_delay) == (
        1,
        max_retries,
        1,
    )
    last_warn = obs["warns"][-1]
    assert (last_warn.attempt, last_warn.max_retries, last_warn.retry_delay) == (
        max_retries - 1,
        max_retries,
        30,
    )


# ---------------------------------------------------------------------------
# Success path: record_nemotron_tokens duration guard (shapes 128-134)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_duration_recorded_when_both_tokens_positive():
    """Kills _call_llm__mutmut_213 (PLUS adds `and False` -> duration_seconds
    wrongly None for both-positive usage). Shipped passes the real elapsed
    duration when prompt/completion tokens are 10/5."""
    obs = await _success({"prompt_tokens": 10, "completion_tokens": 5})
    (call,) = obs["tokens"].call_args_list
    assert call.kwargs["camera_id"] == "cam1"
    assert call.kwargs["input_tokens"] == 10
    assert call.kwargs["output_tokens"] == 5
    assert call.kwargs["duration_seconds"] is not None
    assert call.kwargs["duration_seconds"] > 0.0


@pytest.mark.asyncio
async def test_token_duration_none_when_both_tokens_zero():
    """Kills _call_llm__mutmut_214 (PLUS `or True` -> passes 0.0 instead of
    None), 216 (`input_tokens >= 0` -> passes duration at 0/0), 218
    (`output_tokens >= 0` -> passes duration at 0/0). Shipped passes
    duration_seconds=None for zero usage."""
    obs = await _success({"prompt_tokens": 0, "completion_tokens": 0})
    (call,) = obs["tokens"].call_args_list
    assert call.kwargs["input_tokens"] == 0
    assert call.kwargs["output_tokens"] == 0
    assert call.kwargs["duration_seconds"] is None


@pytest.mark.asyncio
async def test_token_duration_recorded_when_only_output_positive():
    """Kills _call_llm__mutmut_215 (PLUS `and` -> duration None at 0/7).
    Shipped OR-guard records duration_seconds whenever either count is > 0."""
    obs = await _success({"prompt_tokens": 0, "completion_tokens": 7})
    (call,) = obs["tokens"].call_args_list
    assert call.kwargs["input_tokens"] == 0
    assert call.kwargs["output_tokens"] == 7
    assert call.kwargs["duration_seconds"] is not None


@pytest.mark.asyncio
async def test_token_duration_recorded_when_input_equals_one():
    """Kills _call_llm__mutmut_217 (`input_tokens > 1` boundary) at
    input_tokens=1, output_tokens=0. Shipped guard is `> 0`, so duration is
    recorded."""
    obs = await _success({"prompt_tokens": 1, "completion_tokens": 0})
    (call,) = obs["tokens"].call_args_list
    assert call.kwargs["input_tokens"] == 1
    assert call.kwargs["duration_seconds"] is not None


@pytest.mark.asyncio
async def test_token_duration_recorded_when_output_equals_one():
    """Kills _call_llm__mutmut_219 (`output_tokens > 1` boundary) at
    output_tokens=1, input_tokens=0. Shipped guard is `> 0`, so duration is
    recorded."""
    obs = await _success({"prompt_tokens": 0, "completion_tokens": 1})
    (call,) = obs["tokens"].call_args_list
    assert call.kwargs["output_tokens"] == 1
    assert call.kwargs["duration_seconds"] is not None


# ---------------------------------------------------------------------------
# Success path: cost tracker (shapes 135-138)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cost_tracker_receives_exact_usage_kwargs():
    """Kills _call_llm__mutmut_223 (model=None), 230 (camera_id kwarg
    removed), 231 (model="XXnemotronXX"), 232 (model="NEMOTRON"). Shipped
    tracks with model="nemotron" and camera_id=<sanitized camera>, and the
    same duration_seconds the token call saw."""
    obs = await _success({"prompt_tokens": 10, "completion_tokens": 5})
    (track,) = obs["tracker"].track_llm_usage.call_args_list
    assert track.kwargs["model"] == "nemotron"
    assert track.kwargs["camera_id"] == "cam1"
    assert track.kwargs["input_tokens"] == 10
    assert track.kwargs["output_tokens"] == 5
    assert track.kwargs["duration_seconds"] == pytest.approx(
        obs["tokens"].call_args.kwargs["duration_seconds"]
    )
    obs["tracker"].increment_event_count.assert_called_once()


# ---------------------------------------------------------------------------
# Success path: set_llm_inference_attributes (shapes 139-150)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_inference_span_attributes_exact_success():
    """Kills _call_llm__mutmut_234, 235, 236, 237, 239, 240, 241, 242, 243,
    244, 245 (prompt/completion/total token kwargs -> None/removed and
    total_tokens -> minus; inference_time_ms -> None/removed//1000/*1001).
    Shipped: exact token counts, total=sum, ms == duration_seconds*1000."""
    obs = await _success({"prompt_tokens": 10, "completion_tokens": 5})
    (call,) = obs["llat"].call_args_list
    kw = call.kwargs
    assert kw["prompt_tokens"] == 10
    assert kw["completion_tokens"] == 5
    assert kw["total_tokens"] == 15
    assert set(kw) == {"prompt_tokens", "completion_tokens", "total_tokens", "inference_time_ms"}
    _assert_ms_scale(
        obs["llat"], "inference_time_ms", obs["tokens"].call_args.kwargs["duration_seconds"]
    )


# ---------------------------------------------------------------------------
# Success path: set_inference_result_attributes (shapes 151-158)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inference_result_span_attributes_exact_success():
    """Kills _call_llm__mutmut_247, 248, 250, 251, 252, 253, 254, 255
    (duration_ms -> None/removed//1000/*1001; status -> None/removed/
    "XXsuccessXX"/"SUCCESS"). Shipped: duration_ms == duration_seconds*1000
    and status="success" exactly."""
    obs = await _success({"prompt_tokens": 10, "completion_tokens": 5})
    (call,) = obs["irat"].call_args_list
    kw = call.kwargs
    assert kw["status"] == "success"
    assert set(kw) == {"duration_ms", "status"}
    _assert_ms_scale(obs["irat"], "duration_ms", obs["tokens"].call_args.kwargs["duration_seconds"])


# ---------------------------------------------------------------------------
# Success path: legacy add_span_attributes (shapes 159-173)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_span_attributes_exact_success():
    """Kills _call_llm__mutmut_256, 257, 258, 259, 260, 261, 262, 263, 264,
    265, 266, 267, 268, 269, 270 (llm_duration_ms -> None/removed//1000/
    *1001; llm_success -> None/removed/False; llm_attempts -> None/removed/
    attempt-1/attempt+2; input_tokens & output_tokens -> None/removed).
    Shipped on first-attempt success: llm_attempts=1, llm_success is True,
    exact token counts, ms == duration_seconds*1000."""
    obs = await _success({"prompt_tokens": 10, "completion_tokens": 5})
    success_calls = _kwargs_containing(obs["span"], "llm_success")
    assert len(success_calls) == 1
    (kw,) = success_calls
    assert kw["llm_success"] is True
    assert kw["llm_attempts"] == 1
    assert kw["input_tokens"] == 10
    assert kw["output_tokens"] == 5
    assert set(kw) == {
        "llm_duration_ms",
        "llm_success",
        "llm_attempts",
        "input_tokens",
        "output_tokens",
    }
    _assert_ms_scale(
        obs["span"], "llm_duration_ms", obs["tokens"].call_args.kwargs["duration_seconds"]
    )


# ---------------------------------------------------------------------------
# Retry exhaustion: httpx.ConnectError handler (30 keys)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_error_exhaustion_pins_retry_observables():
    """Kills _call_llm__mutmut_272, 273, 274, 275, 276, 277, 278, 279, 280,
    281, 282, 283, 284, 285, 286, 287, 293, 294, 295, 296, 297, 299, 300,
    301, 302, 303, 304, 305, 306. Shipped connect handler: last_exception
    preserved as original_error/__cause__; record_exception(e,
    {"error_type": "connection_error", "attempt": k}); retry predicate
    attempt < max_retries-1 with delays 1,2,4,8,16,30; warning message and
    extra attempt/max_retries/retry_delay; counter
    "nemotron_connection_error". All twin keys of the five shared shapes are
    carried by the five handler tests collectively."""
    err = httpx.ConnectError("boom")
    max_retries = 7
    obs = await _drain(err, max_retries)
    _assert_exhaustion_shape(obs, err, max_retries, "nemotron_connection_error", "connection_error")
    assert obs["rec"].call_args_list[0].args[1] == {
        "error_type": "connection_error",
        "attempt": 1,
    }
    w0 = obs["warns"][0]
    assert w0.getMessage() == (
        f"Nemotron connection error (attempt 1/{max_retries}), retrying in 1s: boom"
    )
    wlast = obs["warns"][-1]
    assert wlast.getMessage() == (
        f"Nemotron connection error (attempt {max_retries - 1}/{max_retries}), "
        "retrying in 30s: boom"
    )
    assert {"attempt", "max_retries", "retry_delay"} <= set(vars(w0))


# ---------------------------------------------------------------------------
# Retry exhaustion: httpx.TimeoutException handler (14 keys)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_error_exhaustion_pins_retry_observables():
    """Kills _call_llm__mutmut_323, 336, 337, 338, 344, 345, 346, 348, 350,
    353, 354, 355, 356, 357 (occurrence-twins of the five shared shapes at
    the httpx.TimeoutException handler). Shipped: error_type "timeout",
    counter "nemotron_timeout", warning "Nemotron timeout (attempt k/7),
    retrying in Ds: slow" with extra attempt/max_retries/retry_delay."""
    err = httpx.ReadTimeout("slow")
    max_retries = 7
    obs = await _drain(err, max_retries)
    _assert_exhaustion_shape(obs, err, max_retries, "nemotron_timeout", "timeout")
    assert obs["rec"].call_args_list[-1].args[1] == {
        "error_type": "timeout",
        "attempt": max_retries,
    }
    w0 = obs["warns"][0]
    assert w0.getMessage() == f"Nemotron timeout (attempt 1/{max_retries}), retrying in 1s: slow"
    wlast = obs["warns"][-1]
    assert wlast.getMessage() == (
        f"Nemotron timeout (attempt {max_retries - 1}/{max_retries}), retrying in 30s: slow"
    )
    assert {"attempt", "max_retries", "retry_delay"} <= set(vars(wlast))


# ---------------------------------------------------------------------------
# Retry exhaustion: TimeoutError (asyncio.timeout) handler (12 keys)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asyncio_timeout_exhaustion_pins_retry_observables():
    """Kills _call_llm__mutmut_374, 387, 388, 389, 395, 396, 397, 404, 405,
    406, 407, 408 (occurrence-twins at the TimeoutError handler). Shipped:
    error_type "asyncio_timeout", counter "nemotron_asyncio_timeout",
    warning "Nemotron asyncio timeout (attempt k/7), retrying in Ds: request
    timed out after 130.0s" with extra attempt/max_retries/retry_delay."""
    err = TimeoutError("deadline")
    max_retries = 7
    obs = await _drain(err, max_retries)
    _assert_exhaustion_shape(obs, err, max_retries, "nemotron_asyncio_timeout", "asyncio_timeout")
    w0 = obs["warns"][0]
    assert w0.getMessage() == (
        f"Nemotron asyncio timeout (attempt 1/{max_retries}), retrying in 1s: "
        "request timed out after 130.0s"
    )
    wlast = obs["warns"][-1]
    assert wlast.getMessage() == (
        f"Nemotron asyncio timeout (attempt {max_retries - 1}/{max_retries}), "
        "retrying in 30s: request timed out after 130.0s"
    )
    assert {"attempt", "max_retries", "retry_delay"} <= set(vars(w0))


# ---------------------------------------------------------------------------
# Retry exhaustion: httpx.HTTPStatusError 5xx handler (16 keys)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_server_error_exhaustion_pins_retry_observables():
    """Kills _call_llm__mutmut_432, 443, 444, 445, 446, 447, 448, 449, 455,
    456, 457, 466, 467, 468, 469, 470 (occurrence-twins at the HTTP 5xx
    handler). Shipped: record_exception(e, {"error_type": "server_error",
    "status_code": 503, "attempt": k}), counter "nemotron_server_error",
    warning "Nemotron server error 503 (attempt k/7), retrying in Ds" with
    extra status_code/attempt/max_retries/retry_delay."""
    req = httpx.Request("POST", "http://llm.test:9/v1/completion")
    resp = httpx.Response(status_code=503, request=req)
    err = httpx.HTTPStatusError("Server Error", request=req, response=resp)
    max_retries = 7
    obs = await _drain(err, max_retries)
    _assert_exhaustion_shape(
        obs, err, max_retries, "nemotron_server_error", "server_error", status_code=503
    )
    w0 = obs["warns"][0]
    assert w0.getMessage() == f"Nemotron server error 503 (attempt 1/{max_retries}), retrying in 1s"
    wlast = obs["warns"][-1]
    assert wlast.getMessage() == (
        f"Nemotron server error 503 (attempt {max_retries - 1}/{max_retries}), retrying in 30s"
    )
    assert (wlast.status_code, wlast.attempt, wlast.max_retries, wlast.retry_delay) == (
        503,
        max_retries - 1,
        max_retries,
        30,
    )


# ---------------------------------------------------------------------------
# Retry exhaustion: catch-all Exception handler (14 keys)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unexpected_error_exhaustion_pins_retry_observables():
    """Kills _call_llm__mutmut_508, 521, 522, 523, 529, 530, 531, 533, 535,
    539, 540, 541, 542, 543 (occurrence-twins at the catch-all handler).
    Shipped: error_type "unexpected", counter "nemotron_unexpected_error",
    warning "Unexpected Nemotron error (attempt k/7), retrying in Ds:
    kaboom" (sanitize_error'd) with extra attempt/max_retries/retry_delay."""
    err = RuntimeError("kaboom")
    max_retries = 7
    obs = await _drain(err, max_retries)
    _assert_exhaustion_shape(obs, err, max_retries, "nemotron_unexpected_error", "unexpected")
    w0 = obs["warns"][0]
    assert w0.getMessage() == (
        f"Unexpected Nemotron error (attempt 1/{max_retries}), retrying in 1s: kaboom"
    )
    wlast = obs["warns"][-1]
    assert wlast.getMessage() == (
        f"Unexpected Nemotron error (attempt {max_retries - 1}/{max_retries}), retrying in 30s: kaboom"
    )
    assert {"attempt", "max_retries", "retry_delay"} <= set(vars(wlast))
