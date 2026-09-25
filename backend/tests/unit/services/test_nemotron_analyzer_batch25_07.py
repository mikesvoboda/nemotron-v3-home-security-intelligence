"""Batch-25 part 07 — chunk "NemotronAnalyzer._call_llm#chunk3" (130 keys).

All 130 survivors live in the retry-handler arms of NemotronAnalyzer._call_llm
(backend/services/nemotron_analyzer.py:4035-4200): the ConnectError,
TimeoutException, asyncio TimeoutError, HTTPStatusError-5xx and
HTTPStatusError-4xx arms. Every mutant is observable through exactly one of
four shipped-behavior channels, all pinned here AS SHIPPED:

  A. record_pipeline_error(<literal>) — module-level spy, exact argument.
  B. record_exception(<exc>, <attrs>) — module-level spy, exact call sequence.
  C. the retry WARNING log — exact message + exact curated `extra=` payload.
  D. the exhaustion ERROR log (client arm: the single client-error log) —
     exact message + curated extras + exc_info.

max_retries=2 (mirrors the repo unit fixture) so attempt 0 emits the WARNING
and attempt 1 takes the exhaustion branch. Backoff sleep is mocked.
The values below (130.0 = nemotron_read_timeout 120 + ai_connect_timeout 10)
were probed against the SHIPPED function before being asserted.

Mutant identity = occurrence order among identical minus/plus shapes; each
docstring names every occurrence-twin key its assertions kill, and twin groups
that span branches (e.g. "max_retries"->"MAX_RETRIES" at 307/358/409/471/544)
are killed by one test per branch — never a subset of the group.
"""

from __future__ import annotations

import logging
import os
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

pytestmark = pytest.mark.unit

# Mirror the minimum env the repo conftest sets (this file lives outside the
# repo tree, so backend/tests/conftest.py does not apply). Values copied from
# /agents/agent-veranda3/workspace/backend/tests/conftest.py.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

import httpx

from backend.core.config import Settings
from backend.core.exceptions import AnalyzerUnavailableError
from backend.services.nemotron_analyzer import NemotronAnalyzer

LOGGER = "backend.services.nemotron_analyzer"

# Curated view of a LogRecord's `extra=` payload: only keys this chunk mutates.
CURATED = ("attempt", "max_retries", "retry_delay", "attempts", "status_code", "explicit_timeout")


def _extra(record: logging.LogRecord) -> dict:
    return {k: getattr(record, k) for k in CURATED if hasattr(record, k)}


def _http_status_error(code: int) -> httpx.HTTPStatusError:
    request = MagicMock(spec=httpx.Request)
    request.method = "POST"
    request.url = "http://localhost:8091/completion"
    response = MagicMock(spec=httpx.Response)
    response.status_code = code
    response.request = request
    return httpx.HTTPStatusError(f"boom-{code}", request=request, response=response)


@pytest.fixture
def mock_settings():
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
def analyzer(mock_settings):
    """NemotronAnalyzer built under the same five get_settings patches as the repo fixture."""
    from backend.core.redis import RedisClient
    from backend.services.analyzer_facade import reset_analyzer_facade
    from backend.services.inference_semaphore import reset_inference_semaphore
    from backend.services.severity import reset_severity_service
    from backend.services.token_counter import reset_token_counter

    redis_client = MagicMock(spec=RedisClient)
    redis_client.get = AsyncMock(return_value=None)
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


class Drive:
    """Observables of one _call_llm run whose POST always fails."""

    def __init__(self, exc, rpe, rex, records):
        self.exc = exc  # exception _call_llm raised
        self.rpe = rpe  # record_pipeline_error spy
        self.rex = rex  # record_exception spy
        self.records = records  # LogRecords emitted on the module logger

    def one(self, level: int) -> logging.LogRecord:
        hits = [r for r in self.records if r.levelno == level]
        assert len(hits) == 1, f"expected exactly one level-{level} record, got {hits}"
        return hits[0]

    @property
    def warn(self) -> logging.LogRecord:
        return self.one(logging.WARNING)

    @property
    def error(self) -> logging.LogRecord:
        return self.one(logging.ERROR)


async def drive(analyzer, post_failure, caplog):
    """Run _call_llm with POST raising post_failure; capture all four channels."""
    rpe = MagicMock()
    rex = MagicMock()
    records = []

    class Collect(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = Collect()
    logger = logging.getLogger(LOGGER)
    logger.addHandler(handler)
    try:
        with caplog.at_level(logging.DEBUG, logger=LOGGER):
            with (
                patch(
                    "backend.services.nemotron_analyzer.record_pipeline_error",
                    autospec=True,
                    side_effect=rpe,
                ) as rpe_mock,
                patch(
                    "backend.services.nemotron_analyzer.record_exception",
                    autospec=True,
                    side_effect=rex,
                ) as rex_mock,
                patch("httpx.AsyncClient.post", autospec=True, side_effect=post_failure),
                patch("asyncio.sleep", autospec=True),
            ):
                try:
                    await analyzer._call_llm(
                        camera_name="Front Door",
                        start_time="2025-12-23T14:30:00",
                        end_time="2025-12-23T14:31:00",
                        detections_list="1. 14:30:00 - person",
                    )
                    raised = None
                except Exception as err:
                    raised = err
    finally:
        logger.removeHandler(handler)
    return Drive(raised, rpe_mock, rex_mock, [r for r in records if r.name == LOGGER])


def _rex_calls(spy) -> list:
    """(exception type name, attributes arg) for every record_exception call."""
    return [
        (
            type(c.args[0]).__name__ if isinstance(c.args[0], BaseException) else repr(c.args[0]),
            c.args[1] if len(c.args) > 1 else c.kwargs.get("attributes"),
        )
        for c in spy.call_args_list
    ]


# ---------------------------------------------------------------------------
# httpx.ConnectError arm — shipped source lines 4035-4063
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_exhaustion_records_pipeline_error_literal(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_311, _312, _313.

    Pins channel A of the ConnectError exhaustion arm: exactly one
    record_pipeline_error("nemotron_connection_error") call. The three mutants
    pass None / "XXnemotron_connection_errorXX" / "NEMOTRON_CONNECTION_ERROR".
    """
    d = await drive(analyzer, httpx.ConnectError("conn-fail"), caplog)
    assert isinstance(d.exc, AnalyzerUnavailableError)
    assert d.rpe.call_args_list == [call("nemotron_connection_error")]


@pytest.mark.asyncio
async def test_connection_exhaustion_error_log_message_and_attempts(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_314, _315, _318, _320, _321.

    Pins channel D of the ConnectError exhaustion arm: ERROR record message
    "Nemotron connection error after 2 attempts: conn-fail" (kills _314's
    None message) with curated extra {"attempts": 2} (kills _315 extra=None,
    _318 dropped extra=, _320 "XXattemptsXX", _321 "ATTEMPTS").
    """
    d = await drive(analyzer, httpx.ConnectError("conn-fail"), caplog)
    assert d.error.getMessage() == "Nemotron connection error after 2 attempts: conn-fail"
    assert _extra(d.error) == {"attempts": 2}


@pytest.mark.asyncio
async def test_connection_exhaustion_error_log_has_exc_info(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_316, _319, _322.

    Pins exc_info=True on the ConnectError exhaustion ERROR record: exc_info
    is a 3-tuple whose value is the ConnectError. The mutants use
    exc_info=None / exc_info=False / a dropped exc_info line (all -> None).
    """
    d = await drive(analyzer, httpx.ConnectError("conn-fail"), caplog)
    assert d.error.exc_info is not None
    assert isinstance(d.error.exc_info[1], httpx.ConnectError)


@pytest.mark.asyncio
async def test_connection_retry_warning_log_message_and_extras(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_307, _308, _309.

    Pins channel C of the ConnectError retry arm (attempt 0 of 2): WARNING
    message "Nemotron connection error (attempt 1/2), retrying in 1s:
    conn-fail" with curated extra {"attempt": 1, "max_retries": 2,
    "retry_delay": 1}. Kills _307 ("max_retries"->"MAX_RETRIES"), _308
    ("retry_delay"->"XXretry_delayXX"), _309 ("retry_delay"->"RETRY_DELAY").
    """
    d = await drive(analyzer, httpx.ConnectError("conn-fail"), caplog)
    assert d.warn.getMessage() == (
        "Nemotron connection error (attempt 1/2), retrying in 1s: conn-fail"
    )
    assert _extra(d.warn) == {"attempt": 1, "max_retries": 2, "retry_delay": 1}


# ---------------------------------------------------------------------------
# httpx.TimeoutException arm — shipped source lines 4065-4086
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_exhaustion_records_pipeline_error_literal(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_362, _363, _364.

    Channel A of the TimeoutException exhaustion arm: exactly one
    record_pipeline_error("nemotron_timeout"). Mutants pass None /
    "XXnemotron_timeoutXX" / "NEMOTRON_TIMEOUT".
    """
    d = await drive(analyzer, httpx.TimeoutException("to-fail"), caplog)
    assert isinstance(d.exc, AnalyzerUnavailableError)
    assert d.rpe.call_args_list == [call("nemotron_timeout")]


@pytest.mark.asyncio
async def test_timeout_retry_records_exception_attributes(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_324, _325, _326, _327, _328, _329, _330, _331, _332, _333, _334, _335.

    Channel B of the TimeoutException arm: record_exception(e, {"error_type":
    "timeout", "attempt": N}) on BOTH attempts (1 then 2). Kills None-exception
    (_324), None-attributes (_325), dropped-first-arg (_326), dropped-second-arg
    (_327), key renames _328/_329/_332/_333, value case _330/_331, and the
    attempt offset mutants _334 (attempt - 1) / _335 (attempt + 2).
    """
    d = await drive(analyzer, httpx.TimeoutException("to-fail"), caplog)
    assert _rex_calls(d.rex) == [
        ("TimeoutException", {"error_type": "timeout", "attempt": 1}),
        ("TimeoutException", {"error_type": "timeout", "attempt": 2}),
    ]


@pytest.mark.asyncio
async def test_timeout_retry_warning_log_message_and_extras(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_347, _351, _352, _358, _359, _360.

    Channel C of the TimeoutException retry arm: WARNING message "Nemotron
    timeout (attempt 1/2), retrying in 1s: to-fail" (kills _347 None message,
    _351 attempt - 1, _352 attempt + 2) with curated extra {"attempt": 1,
    "max_retries": 2, "retry_delay": 1} (kills _358 "MAX_RETRIES", _359
    "XXretry_delayXX", _360 "RETRY_DELAY").
    """
    d = await drive(analyzer, httpx.TimeoutException("to-fail"), caplog)
    assert d.warn.getMessage() == "Nemotron timeout (attempt 1/2), retrying in 1s: to-fail"
    assert _extra(d.warn) == {"attempt": 1, "max_retries": 2, "retry_delay": 1}


@pytest.mark.asyncio
async def test_timeout_exhaustion_error_log_message_and_attempts(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_365, _366, _369, _371, _372.

    Channel D of the TimeoutException exhaustion arm: ERROR message "Nemotron
    timeout after 2 attempts: to-fail" (kills _365) with curated extra
    {"attempts": 2} (kills _366 extra=None, _369 dropped extra=, _371
    "XXattemptsXX", _372 "ATTEMPTS").
    """
    d = await drive(analyzer, httpx.TimeoutException("to-fail"), caplog)
    assert d.error.getMessage() == "Nemotron timeout after 2 attempts: to-fail"
    assert _extra(d.error) == {"attempts": 2}


@pytest.mark.asyncio
async def test_timeout_exhaustion_error_log_has_exc_info(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_367, _370, _373.

    exc_info=True on the TimeoutException exhaustion ERROR record (tuple value
    is the TimeoutException); mutants _367 (None), _370 (dropped line), _373
    (False) all leave record.exc_info None.
    """
    d = await drive(analyzer, httpx.TimeoutException("to-fail"), caplog)
    assert d.error.exc_info is not None
    assert isinstance(d.error.exc_info[1], httpx.TimeoutException)


# ---------------------------------------------------------------------------
# asyncio.timeout TimeoutError arm — shipped source lines 4088-4118
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asyncio_timeout_exhaustion_records_pipeline_error_literal(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_415, _416, _417.

    Channel A of the asyncio-timeout exhaustion arm: exactly one
    record_pipeline_error("nemotron_asyncio_timeout"). Mutants pass None /
    "XXnemotron_asyncio_timeoutXX" / "NEMOTRON_ASYNCIO_TIMEOUT".
    """
    d = await drive(analyzer, TimeoutError("ato-fail"), caplog)
    assert isinstance(d.exc, AnalyzerUnavailableError)
    assert d.rpe.call_args_list == [call("nemotron_asyncio_timeout")]


@pytest.mark.asyncio
async def test_asyncio_timeout_retry_records_exception_attributes(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_375, _376, _377, _378, _379, _380, _381, _382, _383, _384, _385, _386.

    Channel B of the asyncio-timeout arm: record_exception(e, {"error_type":
    "asyncio_timeout", "attempt": N}) on both attempts. Kills None-exception
    (_375), None-attributes (_376), dropped-first-arg (_377), dropped attrs
    block (_378), key renames _379/_380/_383/_384, value case _381/_382, and
    attempt offsets _385 (attempt - 1) / _386 (attempt + 2).
    """
    d = await drive(analyzer, TimeoutError("ato-fail"), caplog)
    assert _rex_calls(d.rex) == [
        ("TimeoutError", {"error_type": "asyncio_timeout", "attempt": 1}),
        ("TimeoutError", {"error_type": "asyncio_timeout", "attempt": 2}),
    ]


@pytest.mark.asyncio
async def test_asyncio_timeout_retry_warning_log_message_and_extras(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_398, _399, _401, _402, _403, _409, _410, _411, _412, _413.

    Channel C of the asyncio-timeout retry arm: WARNING message "Nemotron
    asyncio timeout (attempt 1/2), retrying in 1s: request timed out after
    130.0s" (kills _398 None message, _402 attempt - 1, _403 attempt + 2) with
    curated extra {"attempt": 1, "max_retries": 2, "retry_delay": 1,
    "explicit_timeout": 130.0} (kills _399 extra=None, _401 dropped extra
    block, _409 "MAX_RETRIES", _410 "XXretry_delayXX", _411 "RETRY_DELAY",
    _412 "XXexplicit_timeoutXX", _413 "EXPLICIT_TIMEOUT"). 130.0 =
    nemotron_read_timeout + ai_connect_timeout.
    """
    d = await drive(analyzer, TimeoutError("ato-fail"), caplog)
    assert d.warn.getMessage() == (
        "Nemotron asyncio timeout (attempt 1/2), retrying in 1s: request timed out after 130.0s"
    )
    assert _extra(d.warn) == {
        "attempt": 1,
        "max_retries": 2,
        "retry_delay": 1,
        "explicit_timeout": 130.0,
    }


@pytest.mark.asyncio
async def test_asyncio_timeout_exhaustion_error_log_message_and_extras(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_401, _418, _419, _422, _424, _425, _426, _427.

    Channel D of the asyncio-timeout exhaustion arm: ERROR message "Nemotron
    asyncio timeout after 2 attempts: request timed out after 130.0s" (kills
    _418) with curated extra {"attempts": 2, "explicit_timeout": 130.0} (kills
    _401 dropped extra block, _419 extra=None, _422 dropped extra=, _424
    "XXattemptsXX", _425 "ATTEMPTS", _426 "XXexplicit_timeoutXX",
    _427 "EXPLICIT_TIMEOUT").
    """
    d = await drive(analyzer, TimeoutError("ato-fail"), caplog)
    assert d.error.getMessage() == (
        "Nemotron asyncio timeout after 2 attempts: request timed out after 130.0s"
    )
    assert _extra(d.error) == {"attempts": 2, "explicit_timeout": 130.0}


@pytest.mark.asyncio
async def test_asyncio_timeout_exhaustion_error_log_has_exc_info(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_420, _423, _428.

    exc_info=True on the asyncio-timeout exhaustion ERROR record; mutants
    _420 (None), _423 (dropped line), _428 (False) leave exc_info None.
    """
    d = await drive(analyzer, TimeoutError("ato-fail"), caplog)
    assert d.error.exc_info is not None
    assert isinstance(d.error.exc_info[1], TimeoutError)


# ---------------------------------------------------------------------------
# httpx.HTTPStatusError 5xx arm — shipped source lines 4120-4158
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_server_error_exhaustion_records_pipeline_error_literal(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_475, _476, _477.

    Channel A of the 5xx exhaustion arm: exactly one
    record_pipeline_error("nemotron_server_error"). Mutants pass None /
    "XXnemotron_server_errorXX" / "NEMOTRON_SERVER_ERROR".
    """
    d = await drive(analyzer, _http_status_error(503), caplog)
    assert isinstance(d.exc, AnalyzerUnavailableError)
    assert d.rpe.call_args_list == [call("nemotron_server_error")]


@pytest.mark.asyncio
async def test_server_error_retry_records_exception_attributes(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_433, _434, _435, _436, _437, _438, _439, _440, _441, _442.

    Channel B of the 5xx arm: record_exception(e, {"error_type":
    "server_error", "status_code": 503, "attempt": N}) on both attempts. Kills
    None-exception (_433), None-attributes (_434), dropped e line (_435),
    dropped attrs block (_436), key renames _437/_438/_441/_442 and value
    case _439/_440. _441/_442 are the first occurrence twins of the
    "status_code" rename group (with _464/_485 killed in the log-channel tests).
    """
    d = await drive(analyzer, _http_status_error(503), caplog)
    assert _rex_calls(d.rex) == [
        ("HTTPStatusError", {"error_type": "server_error", "status_code": 503, "attempt": 1}),
        ("HTTPStatusError", {"error_type": "server_error", "status_code": 503, "attempt": 2}),
    ]


@pytest.mark.asyncio
async def test_server_error_retry_warning_log_message_and_extras(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_458, _459, _461, _462, _463, _464, _465, _471, _472, _473.

    Channel C of the 5xx retry arm: WARNING message "Nemotron server error 503
    (attempt 1/2), retrying in 1s" (kills _458 None message, _462 attempt - 1,
    _463 attempt + 2) with curated extra {"status_code": 503, "attempt": 1,
    "max_retries": 2, "retry_delay": 1} (kills _459 extra=None, _461 dropped
    extra block, _464 "XXstatus_codeXX", _465 "STATUS_CODE", _471
    "MAX_RETRIES", _472 "XXretry_delayXX", _473 "RETRY_DELAY"). _464/_465 are
    the second occurrence twins of the "status_code" rename groups; their
    third twins _484/_485 are killed by the exhaustion-log test, their first
    twins _441/_442 by the record_exception test.
    """
    d = await drive(analyzer, _http_status_error(503), caplog)
    assert d.warn.getMessage() == "Nemotron server error 503 (attempt 1/2), retrying in 1s"
    assert _extra(d.warn) == {
        "status_code": 503,
        "attempt": 1,
        "max_retries": 2,
        "retry_delay": 1,
    }


@pytest.mark.asyncio
async def test_server_error_exhaustion_error_log_message_and_extras(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_478, _479, _482, _484, _485, _486, _487.

    Channel D of the 5xx exhaustion arm: ERROR message "Nemotron server error
    503 after 2 attempts" (kills _478) with curated extra {"status_code": 503,
    "attempts": 2} (kills _479 extra=None, _482 dropped extra=, _484
    "XXstatus_codeXX", _485 "STATUS_CODE", _486 "XXattemptsXX", _487
    "ATTEMPTS").
    """
    d = await drive(analyzer, _http_status_error(503), caplog)
    assert d.error.getMessage() == "Nemotron server error 503 after 2 attempts"
    assert _extra(d.error) == {"status_code": 503, "attempts": 2}


@pytest.mark.asyncio
async def test_server_error_exhaustion_error_log_has_exc_info(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_480, _483, _488.

    exc_info=True on the 5xx exhaustion ERROR record; mutants _480 (None),
    _483 (dropped line), _488 (False) leave exc_info None.
    """
    d = await drive(analyzer, _http_status_error(503), caplog)
    assert d.error.exc_info is not None
    assert isinstance(d.error.exc_info[1], httpx.HTTPStatusError)


# ---------------------------------------------------------------------------
# httpx.HTTPStatusError 4xx arm (no retry, immediate re-raise) — lines 4159-4173
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_error_records_pipeline_error_literal(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_489, _490, _491.

    Channel A of the client-error arm: exactly one
    record_pipeline_error("nemotron_client_error") and the ORIGINAL
    HTTPStatusError re-raised (not wrapped). Mutants pass None /
    "XXnemotron_client_errorXX" / "NEMOTRON_CLIENT_ERROR".
    """
    d = await drive(analyzer, _http_status_error(404), caplog)
    assert isinstance(d.exc, httpx.HTTPStatusError)
    assert d.rpe.call_args_list == [call("nemotron_client_error")]


@pytest.mark.asyncio
async def test_client_error_records_exception_attributes(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_492, _493, _494, _495, _496, _497, _498, _499, _500, _501.

    Channel B of the client-error arm: exactly one
    record_exception(e, {"error_type": "client_error", "status_code": 404}).
    Kills None-exception (_492), None-attributes (_493), dropped-first-arg
    (_494), dropped attrs block (_495), key renames _496/_497/_500/_501 and
    value case _498/_499.
    """
    d = await drive(analyzer, _http_status_error(404), caplog)
    assert _rex_calls(d.rex) == [
        ("HTTPStatusError", {"error_type": "client_error", "status_code": 404}),
    ]


@pytest.mark.asyncio
async def test_client_error_log_message_and_extras(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_502, _503, _505.

    Channel D of the client-error arm (single ERROR record, no exc_info in
    shipped code): message "Nemotron client error 404: boom-404" (kills _502)
    with curated extra {"status_code": 404} (kills _503 extra=None, _505
    dropped extra=).
    """
    d = await drive(analyzer, _http_status_error(404), caplog)
    assert d.error.getMessage() == "Nemotron client error 404: boom-404"
    assert _extra(d.error) == {"status_code": 404}


# ---------------------------------------------------------------------------
# catch-all Exception arm — shipped source lines 4177-4199
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unexpected_retry_warning_log_message_and_extras(analyzer, caplog):
    """Kills nemotron_analyzer__mutmut_544, _545, _546.

    Channel C of the unexpected-error retry arm (5th occurrence twin of the
    "max_retries"/"retry_delay" warning-extra shapes): WARNING message
    "Unexpected Nemotron error (attempt 1/2), retrying in 1s: generic-boom"
    with curated extra {"attempt": 1, "max_retries": 2, "retry_delay": 1}.
    Kills _544 ("MAX_RETRIES"), _545 ("XXretry_delayXX"), _546 ("RETRY_DELAY").
    """
    d = await drive(analyzer, RuntimeError("generic-boom"), caplog)
    assert d.warn.getMessage() == (
        "Unexpected Nemotron error (attempt 1/2), retrying in 1s: generic-boom"
    )
    assert _extra(d.warn) == {"attempt": 1, "max_retries": 2, "retry_delay": 1}
