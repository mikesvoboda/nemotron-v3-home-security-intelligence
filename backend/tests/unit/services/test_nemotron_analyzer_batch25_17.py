"""Batch-25 part 17 — chunk "NemotronAnalyzer._check_guided_json_support#chunk2" (17 keys).

All 17 survivors sit in the two retry arms at the tail of
NemotronAnalyzer._check_guided_json_support
(backend/services/nemotron_analyzer.py:434-581), specifically the

  except (httpx.ConnectError, httpx.TimeoutException)  arm  -> L529-553
  except Exception                                      arm  -> L555-579

with max_retries = 3 and retry_delays = [1.0, 2.0, 4.0] (L458-459), so a
drive whose POST *always* fails emits exactly three WARNING records:
"retrying" for attempt 0 and 1, then "after all retries" for attempt 2.

Key -> site map (verified occurrence-by-occurrence against the instrumented
copy mutants/backend/services/nemotron_analyzer.py, variant bodies
xǁNemotronAnalyzerǁ_check_guided_json_support__mutmut_<N>):

  Connection arm (L546-553, the exhaustion log at L546):
    143  msg -> "failed to check guided_json support after all retries (connection error)"
    144  msg -> "FAILED TO CHECK GUIDED_JSON SUPPORT AFTER ALL RETRIES (CONNECTION ERROR)"
    150 + 189   "attempts" -> "XXattemptsXX"   (150 @ L551 conn, 189 @ L577 unexpected)
    151 + 190   "attempts" -> "ATTEMPTS"       (151 @ L551 conn, 190 @ L577 unexpected)

  Unexpected-error arm (L557-579):
    152  L557  if attempt < max_retries - 1  ->  if attempt <= max_retries - 1
    153  L557  if attempt < max_retries - 1  ->  if attempt <  max_retries + 1
    154  L557  if attempt < max_retries - 1  ->  if attempt <  max_retries - 2
    156  L560  retry msg -> None
    160  L560  retry msg -> "XXFailed to check ... retryingXX"
    161  L560  retry msg -> "failed to check guided_json support (unexpected error), retrying"
    162  L560  retry msg -> "FAILED TO CHECK GUIDED_JSON SUPPORT (UNEXPECTED ERROR), RETRYING"
    177  L573  exhaustion msg -> None
    181  L573  exhaustion msg -> "XXFailed to check ... (unexpected error)XX"
    182  L573  exhaustion msg -> "failed to check ... (unexpected error)"
    183  L573  exhaustion msg -> "FAILED TO CHECK ... (UNEXPECTED ERROR)"

Keys 150/189 and 151/190 are OCCURRENCE TWINS: one shape group each, two
occurrences (conn arm then unexpected arm), so both keys of a group are
carried and each occurrence is killed by the test that drives its own arm.

Why nothing here is equivalent: the three WARNING records are the only
observable of the exhaustion arms (the cached flag stays None by design —
L545/L571 "don't cache, will retry on next call" — and `result` stays False),
and the shipped code writes the message literal and the `extra=` key name
straight into the LogRecord, so a renamed/re-cased message or a renamed extra
key is an observable contract break on the log stream. The three branch
mutants change the executed control flow: 152/153 make the guard
always-true so the last attempt takes the retry path (sleep(4.0) and NO
exhaustion record), 154 makes it false from attempt 1 onwards (sleeps only
[1.0] and TWO exhaustion records). Pinned values below come from a probe of
the SHIPPED function (drives: ConnectError("conn-refused") and
ValueError("boom")), not from expectation.

No repo test kills any of these 17 keys. The repo's retry-arm assertions are
name- and message-blind and every one of their observables is invariant under
these mutations: backend/tests/unit/services/test_nemotron_analyzer.py:4813-4841
asserts only post.call_count == 3 and _supports_guided_json is None, and
backend/tests/unit/services/test_nemotron_guided_json.py:276-315 adds
mock_sleep.call_count == 2 / assert_any_call(1.0)/(2.0) — and those two tests
drive only the *connection* arm, which this chunk does not mutate its guard
of. The batch-25 draft battery (/tmp/wp-batch25/test_nemotron_analyzer_batch25.py)
never touches _check_guided_json_support. => zero keys killed_by_draft.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_17.py -p no:cacheprovider -o addopts= -q
"""

from __future__ import annotations

import logging
import os
from unittest.mock import MagicMock, patch

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

import httpx

from backend.core.config import Settings
from backend.services.nemotron_analyzer import NemotronAnalyzer

LOGGER = "backend.services.nemotron_analyzer"

# Shipped literals, copied from the source lines each mutant rewrites.
CONN_RETRY_MSG = "Failed to check guided_json support (connection error), retrying"
CONN_EXHAUST_MSG = "Failed to check guided_json support after all retries (connection error)"
UNEXP_RETRY_MSG = "Failed to check guided_json support (unexpected error), retrying"
UNEXP_EXHAUST_MSG = "Failed to check guided_json support after all retries (unexpected error)"

# Curated view of a LogRecord's `extra=` payload: only the keys this chunk
# mutates (backend/core/logging.py ContextFilter injects request_id/hostname/…
# into every record, so the raw record __dict__ cannot be compared whole).
CURATED = ("llm_url", "error", "attempt", "max_retries", "retry_delay_seconds", "attempts")

LLM_URL = "http://localhost:8091"


def _extra(record: logging.LogRecord) -> dict:
    return {k: getattr(record, k) for k in CURATED if hasattr(record, k)}


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
    m.nemotron_url = LLM_URL
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
    from unittest.mock import AsyncMock

    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock(return_value=True)
    redis_client.delete = AsyncMock(return_value=1)
    redis_client.publish = AsyncMock(return_value=1)
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
    """Everything the shipped function makes observable for one failing drive."""

    def __init__(self, result, cache, posts, sleeps, records):
        self.result = result
        self.cache = cache
        self.posts = posts
        self.sleeps = sleeps  # asyncio.sleep positional args, in order
        self.records = records  # WARNING records on the module logger, in order

    @property
    def messages(self) -> list:
        return [r.getMessage() for r in self.records]

    @property
    def extras(self) -> list:
        return [_extra(r) for r in self.records]


async def drive(analyzer, caplog, post_failure):
    """Run _check_guided_json_support with every POST raising post_failure."""
    records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = Collect()
    logger = logging.getLogger(LOGGER)
    logger.addHandler(handler)
    try:
        with (
            patch("httpx.AsyncClient.post", autospec=True, side_effect=post_failure) as post_mock,
            patch("asyncio.sleep", autospec=True) as sleep_mock,
            caplog.at_level(logging.DEBUG, logger=LOGGER),
        ):
            result = await analyzer._check_guided_json_support()
    finally:
        logger.removeHandler(handler)
    return Drive(
        result,
        analyzer._supports_guided_json,
        post_mock.call_count,
        [c.args for c in sleep_mock.call_args_list],
        [r for r in records if r.name == LOGGER and r.levelno == logging.WARNING],
    )


# Shared invariants of an all-attempts-failed drive, pinned AS SHIPPED:
# max_retries=3 at L458, retry_delays=[1.0,2.0,4.0] at L459, and the
# "don't cache on transient failure" contract at L545/L571.
def _assert_retry_contract(d: Drive) -> None:
    assert d.result is False
    assert d.cache is None
    assert d.posts == 3
    assert d.sleeps == [(1.0,), (2.0,)]
    assert len(d.records) == 3


@pytest.mark.asyncio
async def test_connection_exhaustion_log_message_and_attempts_key(analyzer, caplog):
    """Kills keys 143, 144, 150, 151.

    Pins the connection-arm exhaustion log (nemotron_analyzer.py:546-553)
    exactly as shipped: message
    "Failed to check guided_json support after all retries (connection error)"
    with extra {"llm_url", "error", "attempts": 3}.

    - 143 lower-cases the message, 144 upper-cases it -> message equality.
    - 150 renames the extra key "attempts" -> "XXattemptsXX" (L551) and 151
      renames it to "ATTEMPTS" (same L551 occurrence, other shape group); both
      drop the canonical entry and add a stray one -> extras equality.
      150/189 and 151/190 are occurrence twins (L551 then L577): this drive
      kills the L551 occurrences (150, 151) and
      test_unexpected_exhaustion_log_message_and_attempts_key kills the L577
      occurrences (189, 190), so each group is carried in full.

    The retry-contract half (3 posts, sleeps [1.0, 2.0], cache stays None)
    is re-pinned so the message/extras assertions are known to describe the
    shipped third-attempt path rather than a different control flow.
    """
    d = await drive(analyzer, caplog, httpx.ConnectError("conn-refused"))
    _assert_retry_contract(d)
    assert d.messages == [CONN_RETRY_MSG, CONN_RETRY_MSG, CONN_EXHAUST_MSG]
    assert d.extras[:2] == [
        {
            "llm_url": LLM_URL,
            "error": "conn-refused",
            "attempt": 1,
            "max_retries": 3,
            "retry_delay_seconds": 1.0,
        },
        {
            "llm_url": LLM_URL,
            "error": "conn-refused",
            "attempt": 2,
            "max_retries": 3,
            "retry_delay_seconds": 2.0,
        },
    ]
    assert d.extras[2] == {
        "llm_url": LLM_URL,
        "error": "conn-refused",
        "attempts": 3,
    }


@pytest.mark.asyncio
async def test_unexpected_exhaustion_log_message_and_attempts_key(analyzer, caplog):
    """Kills keys 177, 181, 182, 183, 189, 190 (and, incidentally, 152/153/154).

    Pins the unexpected-error arm's exhaustion log
    (nemotron_analyzer.py:572-579) for a POST that raises a bare ValueError:
    message
    "Failed to check guided_json support after all retries (unexpected error)"
    with extra {"llm_url", "error", "attempts": 3}.

    - 177 replaces the message with None, 181 wraps it in XX…XX, 182
      lower-cases it, 183 upper-cases it -> message equality.
    - 189 renames the extra key "attempts" -> "XXattemptsXX" and 190 renames
      it to "ATTEMPTS" (L577) -> extras equality. 189/150 and 190/151 are
      occurrence twins from one shape group each; each occurrence is killed
      by the test that drives its own arm, so the whole group is carried.

    Driving ValueError (not httpx.ConnectError) is required: only the
    `except Exception` arm at L555 is reached, which is where 177/181/182/183
    and the L577 twin occurrences live.
    """
    d = await drive(analyzer, caplog, ValueError("boom"))
    _assert_retry_contract(d)
    assert d.messages == [UNEXP_RETRY_MSG, UNEXP_RETRY_MSG, UNEXP_EXHAUST_MSG]
    assert d.extras[2] == {
        "llm_url": LLM_URL,
        "error": "boom",
        "attempts": 3,
    }


@pytest.mark.asyncio
async def test_unexpected_retry_warning_message_sequence(analyzer, caplog):
    """Kills keys 156, 160, 161, 162.

    Pins the *ordered message sequence* of the unexpected arm's two retry
    warnings (nemotron_analyzer.py:559-568) — the shipped text is
    "Failed to check guided_json support (unexpected error), retrying",
    emitted once per non-final attempt.

    - 156 passes None as the message (the record's getMessage() is then None),
    - 160 "XXFailed to check …, retryingXX",
    - 161 lower-case, 162 upper-case.
    All four are caught by the sequence equality; the third (exhaustion)
    element is pinned too so a mutant that shifts which line is mutated
    cannot pass by re-labelling a different record.
    """
    d = await drive(analyzer, caplog, ValueError("boom"))
    assert d.messages[:2] == [UNEXP_RETRY_MSG, UNEXP_RETRY_MSG]
    assert d.messages[2] == UNEXP_EXHAUST_MSG


@pytest.mark.asyncio
async def test_unexpected_retry_branch_guard_attempts_and_delays(analyzer, caplog):
    """Kills keys 152, 153, 154.

    Pins the guard `if attempt < max_retries - 1` at nemotron_analyzer.py:557
    through its three observables: exactly two retry warnings carrying
    {"attempt": 1|2, "max_retries": 3, "retry_delay_seconds": 1.0|2.0},
    asyncio.sleep called with (1.0,) then (2.0,) — never (4.0,) — and exactly
    ONE exhaustion record.

    - 152 (`<=`) and 153 (`max_retries + 1`) make the guard always true, so
      attempt 2 takes the retry path: a third "retrying" warning with
      attempt=3/retry_delay_seconds=4.0, sleep(4.0), and NO exhaustion record.
    - 154 (`max_retries - 2`) is false from attempt 1 on, so only sleep(1.0)
      happens and the exhaustion record is emitted TWICE (attempts 1 and 2).
    """
    d = await drive(analyzer, caplog, ValueError("boom"))
    _assert_retry_contract(d)
    assert d.extras[:2] == [
        {
            "llm_url": LLM_URL,
            "error": "boom",
            "attempt": 1,
            "max_retries": 3,
            "retry_delay_seconds": 1.0,
        },
        {
            "llm_url": LLM_URL,
            "error": "boom",
            "attempt": 2,
            "max_retries": 3,
            "retry_delay_seconds": 2.0,
        },
    ]
    exhaustion = [r for r in d.records if r.getMessage() == UNEXP_EXHAUST_MSG]
    assert len(exhaustion) == 1
