"""Batch-25 part 16 — chunk "NemotronAnalyzer._check_guided_json_support#chunk1" (130 keys).

Target: NemotronAnalyzer._check_guided_json_support, shipped at
backend/services/nemotron_analyzer.py:434-579. All 130 keys in
/tmp/wp-batch25/chunks/chunk-16.json sit inside that one function.

The function is observable through exactly four channels, all pinned here AS
SHIPPED (every expected value below was probed against the shipped function
before it was asserted — see /tmp/wp-batch25/probes/p16/):

  A. the single probe POST — positional URL, the `headers=` keyword and the
     `json=` payload literal (client stand-in records all three; its signature
     `post(self, url, *, headers, json)` mirrors httpx.AsyncClient.post, whose
     headers/json are keyword-only, so a dropped keyword raises TypeError).
  B. the return value + the `self._supports_guided_json` cache slot
     (True on 2xx, False on a definitive reject, None = "not cached" whenever
     every attempt failed transiently).
  C. the number of POSTs / the `asyncio.sleep` argument sequence — the retry
     bookkeeping (3 attempts, delays 1.0 then 2.0, nothing after that).
  D. the log records on logger "backend.services.nemotron_analyzer": exact
     message text AND the exact `extra=` payload as a whole dict.

Site map (instrumented variant bodies
xǁNemotronAnalyzerǁ_check_guided_json_support__mutmut_N in
mutants/backend/services/nemotron_analyzer.py, diffed line-by-line against the
__mutmut_orig body; shipped line numbers on the right):

  payload/URL construction (channel A) ............ :455, :457, :464-471
    2..14  test_schema dict (13 shapes)            :455   -> channel A
    22     retry_delays [1,2,4] -> [1,2,5]          :457   -> EQUIVALENT (see below)
    25     url -> None                              :465
    26     headers -> None;  29  headers= dropped   :466
    36,37,38  "max_tokens" key/value                :469
    39,40,41  "temperature" key/value               :470
    42..45    "nvext"/"guided_json" keys            :471
  success guard + its INFO ........................ :476-483
    46,47    `response.status_code < 300` widened   :476   -> channels B/C
    50,51,53,54,55,56,57,58,59,60,61,62  INFO text / extra= / dropped extra=
                                                      :478-480 -> channel D
  response-object 4xx guard + its INFO ............. :484-491
    72,73,74,75,76,77,78,79,80,81,82  INFO text / extra= / dropped extra=
                                                      :487-489 -> channel D
  raised-HTTPStatusError arm ....................... :493-527
    84,85,86,87  `400 <= e.response.status_code < 500` widened/narrowed :495
    (all four sit on the RAISED-error guard, all four are killed by driving a
     real httpx.HTTPStatusError at the discriminating status — 400 for 84/85,
     500 for 86/87. The response-object twin of that guard (:485) contributes
     no key to this chunk at all — no shape group of this function has
     `elif 400 <= response.status_code < 500` as its minus, i.e. those mutants
     were already killed in the banked run.)
    88,89,90     `elif attempt < max_retries - 1`    :499   -> channel C
    91           delay = retry_delays[attempt] -> None :500 -> channel C
    92,93,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111
                 retry WARNING text / extra= / dropped extra=  :501-509
    112          asyncio.sleep(delay) -> sleep(None) :511   -> channel C
  connection-error arm (ConnectError/TimeoutException) :529-555
    117,118,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136
                 retry WARNING text / extra= / dropped extra=  :532-540
    138,139,141,142,145,146,147,148,149  exhaustion WARNING text / extra=
                                                      :546-552
  unexpected-Exception arm .......................... :557-579
    157,159,163,164,165,166,167,168,169,170,171,172,173,174,175
                 retry WARNING text / extra= / dropped extra=  :560-568
    178,180,184,185,186,187,188  exhaustion WARNING text / extra=
                                                      :574-579

OCCURRENCE TWEINS CARRIED IN FULL. Several shape groups occur once per
except-arm, so one shape has 3 or 5 keys spread over different branches; the
test that kills one member of such a group kills ALL its members, and every
docstring below names the complete member list (never a subset):
  extra={"llm_url","error","attempt","max_retries","retry_delay_seconds"}
    -> None .................. 93 (server), 118 (connection), 157 (unexpected)
  dropped `extra=` line, retry arms ......... 95, 120, 159
  "llm_url" -> "XXllm_urlXX"/"LLM_URL" ..... 99/124/145/163/184,
                                              100/125/146/164/185
  "error" -> "XXerrorXX"/"ERROR" ........... 101/126/147/165/186,
                                              102/127/148/166/187
  "error": str(e) -> str(None) ............. 103, 128, 149, 167, 188
  "attempt" key spellings .................. 104/129/168, 105/130/169
  "attempt": attempt-1 / attempt+2 ......... 106/131/170, 107/132/171
  "max_retries" spellings .................. 108/133/172, 109/134/173
  "retry_delay_seconds" spellings .......... 110/135/174, 111/136/175
  exhaustion extra={...} -> None ........... 139 (connection), 178 (unexpected)
  dropped `extra=` line, exhaustion arms ... 141 (connection), 180 (unexpected)
  "llm_url"/"error" in exhaustion extras ... 145/184, 146/185, 147/186,
                                             148/187, 149/188

THE ONE EQUIVALENT: key 22 (`retry_delays = [1.0, 2.0, 4.0]` -> `[..., 5.0]`).
Proof by reachability, not by a dossier claim: the mutated element is index 2.
`delay = retry_delays[attempt]` executes only in the retry arms, whose guard
`attempt < max_retries - 1` (shipped :499, :531, :559) is False at
attempt == 2, and `max_retries = 3` (:456) bounds the loop to attempts
0,1,2 (:459). So index 2 is never read: with the shipped list the observable
sleep sequence is [(1.0,), (2.0,)], and with the mutated list it is identical.
The counterfactual seal that makes the argument non-vacuous is survivor key 152
(`"attempts": max_retries` -> `"XXattemptsXX"` in the *connection exhaustion*
extra, which IS observed by test_conn_exhaustion_*): an index-independent
mutation of the same arm is a survivor, so the arm is covered and the
"unreachable operand" claim is about index 2 specifically, not about dead code.
Keys 88/89/90/91/112 sit on the same guards but change control flow or the
sleep argument and ARE killed (see test bodies).

NO KEY IN THIS CHUNK IS killed_by_draft. The draft battery
(/tmp/wp-batch25/test_nemotron_analyzer_batch25.py) only drives
_parse_llm_response / _validate_risk_data / _extract_json_objects. The repo
tests that exercise this function —
backend/tests/unit/services/test_nemotron_guided_json.py:227-399 and
backend/tests/unit/services/test_nemotron_analyzer.py:4761-4839 — assert only
the return value, the `_supports_guided_json` cache slot, `post.call_count` and
`mock_sleep.call_count`. There is no assertion anywhere on (a) the probe URL,
headers or payload literals, (b) any log message or `extra=` payload of this
function (grep: no `assert` + "guided_json support" in either file), or (c) the
sleep *arguments* (call_count / assert_any_call(1.0) only, which cannot see a
mutated payload). Hence zero overlap and all remaining 129 keys are killable.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_16.py -p no:cacheprovider -o addopts= -q
RED-CHECK (on a lane): apply one key at a time to
backend/services/nemotron_analyzer.py (never two — the repo shares an import
chain), run the named test, expect failure.
"""

from __future__ import annotations

import contextlib
import logging
import os
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

# This file lives outside the repo tree, so backend/tests/conftest.py does NOT
# apply. Mirror the minimum env that conftest sets before importing backend
# (values copied verbatim from backend/tests/conftest.py, not invented).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

import httpx

from backend.services import nemotron_analyzer as nem

LOGGER = "backend.services.nemotron_analyzer"
LLM_URL = "http://nim.test:8000/v1"
FAKE_LLM_KEY = "sk-nem-batch25"
PROBE_URL = f"{LLM_URL}/completion"

# Channel A expectations, pinned as literals (probe of the shipped function).
TEST_SCHEMA = {"type": "object", "properties": {"test": {"type": "string"}}}
PAYLOAD = {
    "prompt": "Say hello",
    "max_tokens": 10,
    "temperature": 0.0,
    "nvext": {"guided_json": TEST_SCHEMA},
}

# Channel D message literals, copied from the shipped call sites.
MSG_OK = "Nemotron endpoint supports guided_json structured generation"
MSG_4XX = "Nemotron endpoint does not support guided_json, using regex fallback"
MSG_HSE_4XX = "Nemotron endpoint does not support guided_json (HTTP error), using regex fallback"
MSG_SRV_RETRY = "Failed to check guided_json support (server error), retrying"
MSG_SRV_EXH = "Failed to check guided_json support after all retries (server error)"
MSG_CON_RETRY = "Failed to check guided_json support (connection error), retrying"
MSG_CON_EXH = "Failed to check guided_json support after all retries (connection error)"
MSG_UNX_RETRY = "Failed to check guided_json support (unexpected error), retrying"
MSG_UNX_EXH = "Failed to check guided_json support after all retries (unexpected error)"

# Record attributes that are NOT part of an `extra=` payload: the 100%-standard
# LogRecord set plus everything backend/core/logging.py:ContextFilter.filter
# injects onto the module logger (verified attribute-by-attribute against a
# probe run, so `extras()` below yields EXACTLY the shipped extra= dict).
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


class _Client:
    """Stand-in for the persistent httpx client used by the health probe.

    The signature is deliberate: `headers` and `json` are keyword-only, like
    httpx.AsyncClient.post, so a mutant that drops one of the keywords raises
    TypeError inside the shipped try block instead of silently succeeding.
    """

    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.calls: list[tuple] = []

    async def post(self, url, *, headers, json):
        self.calls.append((url, headers, json))
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return httpx.Response(item)


class _Recorder(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def hstatuserror(code: int, message: str) -> httpx.HTTPStatusError:
    """A REAL httpx.HTTPStatusError (so `str(e)` == message, as shipped logs it)."""
    request = httpx.Request("POST", PROBE_URL)
    return httpx.HTTPStatusError(
        message, request=request, response=httpx.Response(code, request=request)
    )


class Drive:
    """All four observable channels of one _check_guided_json_support run."""

    def __init__(self, result, cached, calls, records, sleeper):
        self.result = result
        self.cached = cached
        self.calls = calls
        self.records = records
        self.sleeper = sleeper

    # -- channel B ---------------------------------------------------------
    def settled_as(self, value) -> None:
        assert self.result is value, self.records
        assert self.cached is value, self.records

    def not_cached(self) -> None:
        assert self.result is False, self.records
        assert self.cached is None, self.records

    # -- channel C ---------------------------------------------------------
    @property
    def posts(self) -> int:
        return len(self.calls)

    @property
    def sleep_args(self) -> list[tuple]:
        return [tuple(c.args) for c in self.sleeper.call_args_list]

    # -- channel D ---------------------------------------------------------
    def texts(self) -> list[str]:
        return [r.getMessage() for r in self.records]

    def record(self, level: int, message: str) -> logging.LogRecord:
        hits = [r for r in self.records if r.levelno == level and r.getMessage() == message]
        assert len(hits) == 1, f"want exactly one {level} {message!r}, got {self.texts()}"
        return hits[0]

    def silent_of(self, *messages: str) -> None:
        bad = sorted({m for m in self.texts() if m in messages})
        assert bad == [], f"unexpected log message(s): {bad} in {self.texts()}"

    def silent(self) -> None:
        assert self.records == [], self.texts()


@contextlib.contextmanager
def _captured_logger():
    handler = _Recorder()
    logger = logging.getLogger(LOGGER)
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)  # INFO records are emitted by shipped code
    try:
        yield handler
    finally:
        logger.setLevel(previous)
        logger.removeHandler(handler)


async def drive(script: list) -> Drive:
    """Run the shipped function against a scripted probe-response sequence."""
    analyzer = nem.NemotronAnalyzer.__new__(nem.NemotronAnalyzer)
    analyzer._supports_guided_json = None
    analyzer._llm_url = LLM_URL
    analyzer._api_key = FAKE_LLM_KEY
    client = _Client(script)
    analyzer._health_http_client = client
    with _captured_logger() as handler, patch("asyncio.sleep", autospec=True) as sleeper:
        result = await analyzer._check_guided_json_support()
    return Drive(result, analyzer._supports_guided_json, client.calls, handler.records, sleeper)


# ---------------------------------------------------------------------------
# channel A — the probe request itself (shipped :464-471)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_probe_posts_completion_url_with_auth_headers_keyword():
    """Kills mutmut_25, mutmut_26, mutmut_29.

    Pins the shipped POST call: positional URL f"{self._llm_url}/completion"
    and headers=self._get_auth_headers() — which for a configured key is
    exactly {"X-API-Key": FAKE_LLM_KEY}. _25 posts to None (URL assert fails), _26
    posts headers=None (headers assert fails: an unauthenticated probe would be
    401'd by a real NIM endpoint and mis-detected as "no guided_json"), _29
    drops the `headers=` keyword entirely — the keyword-only signature makes
    that a TypeError inside the shipped try, which the `except Exception` arm
    swallows, so the INFO record below never appears and the cache stays unset.
    """
    d = await drive([200])
    assert d.calls == [(PROBE_URL, {"X-API-Key": FAKE_LLM_KEY}, PAYLOAD)]
    d.settled_as(True)
    assert d.posts == 1
    d.record(logging.INFO, MSG_OK)


@pytest.mark.asyncio
async def test_probe_payload_literal_is_the_minimal_guided_json_request():
    """Kills mutmut_2..14, mutmut_36..45.

    Pins the shipped probe body dict exactly: {"prompt": "Say hello",
    "max_tokens": 10, "temperature": 0.0, "nvext": {"guided_json":
    {"type": "object", "properties": {"test": {"type": "string"}}}}}. Keys
    2-14 are the thirteen `test_schema` shapes (None, "XXtypeXX"/"TYPE",
    "XXobjectXX"/"OBJECT", "XXpropertiesXX"/"PROPERTIES", "XXtestXX"/"TEST",
    inner "XXtypeXX"/"TYPE", "XXstringXX"/"STRING") — a full-dict equality
    cannot be satisfied by any of them; keys 36-45 are the five payload-key
    renames and the two value bumps (max_tokens 11, temperature 1.0). All 24
    ride this one channel: the payload is the only thing that asks the endpoint
    for structured generation, so a mutated key or value silently disables the
    feature the probe exists to detect.
    """
    d = await drive([200])
    _url, _headers, payload = d.calls[0]
    assert payload == PAYLOAD
    assert payload["nvext"]["guided_json"] == {
        "type": "object",
        "properties": {"test": {"type": "string"}},
    }
    assert payload["max_tokens"] == 10
    assert payload["temperature"] == 0.0
    d.settled_as(True)


# ---------------------------------------------------------------------------
# channel B/C — the two status guards (shipped :476, :485, :495)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_only_sub_300_responses_count_as_guided_json_support():
    """Kills mutmut_46, mutmut_47.

    Pins the shipped success guard `response.status_code < 300` (:476): 200 and
    204 settle True after ONE post, while a 300 or 500 *response object*
    matches neither this guard nor the 4xx elif — such an attempt simply falls
    out of the try block, so shipped posts all 3 times, emits NO log record and
    calls NO sleep (nothing in the no-branch path sleeps or logs) and leaves the
    cache unset. _46 (`<= 300`) and _47 (`< 301`) both classify 300 as
    supported, so there they return True after one post with the success INFO.
    """
    ok = await drive([200])
    ok.settled_as(True)
    assert ok.posts == 1
    assert ok.sleep_args == []

    no_content = await drive([204])
    no_content.settled_as(True)
    assert no_content.posts == 1

    for status in (300, 500):
        fall_through = await drive([status, status, status])
        fall_through.not_cached()
        assert fall_through.posts == 3
        assert fall_through.sleep_args == []
        fall_through.silent()


@pytest.mark.asyncio
async def test_raised_status_error_guard_covers_400_through_499_only():
    """Kills mutmut_84, mutmut_85, mutmut_86, mutmut_87.

    Pins `if 400 <= e.response.status_code < 500` in the HTTPStatusError arm
    (:495) from all four sides. A raised 400 (and a raised 499) IS a definitive
    "unsupported" answer: one post, return False, cache False, and exactly one
    record — the INFO "(HTTP error)" line with extra=
    {"llm_url": LLM_URL, "status_code": <code>} — and no sleep. A raised 500 is
    NOT: it takes the retry arm (sleep 1.0, second post, success INFO, cache
    True) and must never log either reject line. _84 (`401 <=`) and _85 (`400 <`)
    both drop the 400 lower edge into the retry path; _86 (`<= 500`) and _87
    (`< 501`) both pull 500 into the definitive-reject path, where the run stops
    after one post with the cache set to False.
    """
    for code in (400, 499):
        d = await drive([hstatuserror(code, f"client error {code}"), 200, 200])
        d.settled_as(False)
        assert d.posts == 1
        assert d.sleep_args == []
        d.silent_of(MSG_4XX, MSG_SRV_RETRY, MSG_SRV_EXH, MSG_OK)
        assert len(d.records) == 1
        assert extras(d.record(logging.INFO, MSG_HSE_4XX)) == {
            "llm_url": LLM_URL,
            "status_code": code,
        }

    transient = await drive([hstatuserror(500, "server error 500"), 200, 200])
    transient.settled_as(True)
    assert transient.posts == 2
    assert transient.sleep_args == [(1.0,)]
    transient.silent_of(MSG_HSE_4XX, MSG_4XX)


# ---------------------------------------------------------------------------
# channel D — the success INFO (:478-480)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_info_log_message_and_attempts_extra_on_each_attempt():
    """Kills mutmut_50, _51, _53, _54, _55, _56, _57, _58, _59, _60, _61, _62.

    Pins the shipped INFO record on the success path: message "Nemotron endpoint
    supports guided_json structured generation" with extra= EXACTLY
    {"llm_url": LLM_URL, "attempts": attempt + 1}. Driven twice so the counter
    is pinned at both attempt 0 and attempt 1 — that is what separates the
    shipped `attempt + 1` from _61 (`attempt - 1`) and _62 (`attempt + 2`) in
    either direction. _50 (message -> None), _54/_55/_56 (XX-wrapped / lower /
    upper message), _51 (`extra=None`), _53 (dropped `extra=` line) and the key
    renames _57/_58 ("llm_url") and _59/_60 ("attempts") all fail the same two
    assertions: message identity and whole-dict extra equality. A dropped
    extra= is invisible to a key-by-key check (logging just omits the
    attributes), which is why the payload is compared as a dict.
    """
    first = await drive([200])
    first.settled_as(True)
    first.silent_of(MSG_4XX, MSG_HSE_4XX, MSG_SRV_RETRY, MSG_CON_RETRY, MSG_UNX_RETRY)
    ok = first.record(logging.INFO, MSG_OK)
    assert extras(ok) == {"llm_url": LLM_URL, "attempts": 1}

    # attempt 1 of the same shape: the ONLY value the shipped counter can take
    # (a plain 5xx response object matches neither guard, so that attempt falls
    # through silently — no competing INFO record and no sleep, which is itself
    # the shipped behavior pinned by test_only_sub_300_responses...).
    second = await drive([500, 200, 200])
    second.settled_as(True)
    assert second.posts == 2
    assert second.sleep_args == []
    ok2 = second.record(logging.INFO, MSG_OK)
    assert extras(ok2) == {"llm_url": LLM_URL, "attempts": 2}


# ---------------------------------------------------------------------------
# channel D — the response-object reject INFO (:487-489)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_info_log_message_and_status_code_extra():
    """Kills mutmut_72, _73, _74, _75, _76, _77, _78, _79, _80, _81, _82.

    Pins the shipped INFO record for a 4xx *response object* (status 422):
    message "Nemotron endpoint does not support guided_json, using regex
    fallback" with extra= EXACTLY {"llm_url": LLM_URL, "status_code": 422},
    return False / cache False / one post / no sleep. _72 replaces the message
    with None, _74 DELETES the message argument (logging then renders an empty
    message and the extras still exist — only whole-record pinning catches it),
    _75 deletes the `extra=` line, _73 passes extra=None, _76/_77/_78 are the
    XX-/lower-/upper-case message variants and _79/_80/_81/_82 rename "llm_url"
    and "status_code".
    """
    d = await drive([422])
    d.settled_as(False)
    assert d.posts == 1
    assert d.sleep_args == []
    d.silent_of(MSG_OK, MSG_HSE_4XX)
    assert len(d.records) == 1
    rec = d.record(logging.INFO, MSG_4XX)
    assert extras(rec) == {"llm_url": LLM_URL, "status_code": 422}


# ---------------------------------------------------------------------------
# HTTPStatusError arm — server-error retry WARNING (:499-511)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_server_error_retry_warning_message_extras_and_backoff():
    """Kills mutmut_91, _92, _112, and every
    server-retry extra/message key: _93, _95, _96, _97, _98, _99, _100, _101,
    _102, _103, _104, _105, _106, _107, _108, _109, _110, _111.

    Drives [HTTPStatusError(500), 200]: the shipped retry arm logs WARNING
    "Failed to check guided_json support (server error), retrying" with extra=
    EXACTLY {"llm_url", "error": "server error 500", "attempt": 1,
    "max_retries": 3, "retry_delay_seconds": 1.0} and then sleeps with THAT
    delay, so two independent channels are pinned and each of the two delay
    mutants shows up in only one of them:
      _91 (`delay = None` at :500) poisons the payload — retry_delay_seconds
        becomes None, so the whole-dict extras equality below fails.
      _112 (`asyncio.sleep(None)` at :511) leaves the WARNING byte-identical
        and is visible ONLY in the sleep argument, which is why it is asserted
        to be exactly [(1.0,)]; asyncio.sleep is mocked, so nothing raises and a
        call-count-only check (what the repo tests do) cannot see it.
    Message variants _92 (None), _96/_97/_98 (XX/lower/upper), `extra=None` _93
    and the dropped extra _95 die on the same two assertions, as do the key
    renames _99-_111 and the str(None) error value _103 ("None" !=
    "server error 500"). The retry-GUARD mutants (_88, _89, _90) are NOT
    observable here — attempt 0 retries under all of them — so they are pinned
    by the exhaustion drive in the next test.
    """
    d = await drive([hstatuserror(500, "server error 500"), 200, 200])
    d.settled_as(True)
    assert d.posts == 2
    assert d.sleep_args == [(1.0,)]
    d.silent_of(MSG_UNX_RETRY, MSG_UNX_EXH, MSG_SRV_EXH, MSG_CON_RETRY, MSG_CON_EXH)
    rec = d.record(logging.WARNING, MSG_SRV_RETRY)
    assert extras(rec) == {
        "llm_url": LLM_URL,
        "error": "server error 500",
        "attempt": 1,
        "max_retries": 3,
        "retry_delay_seconds": 1.0,
    }
    d.record(logging.INFO, MSG_OK)


@pytest.mark.asyncio
async def test_server_error_exhaustion_stops_at_three_attempts_and_does_not_cache():
    """Kills mutmut_88, mutmut_89, mutmut_90. The HSE exhaustion message/extras
    are pinned here as shipped shape, not as a kill claim (that key group,
    150/151, belongs to another chunk).

    Drives three raised 5xx errors: the shipped run logs the retry WARNING at
    attempts 1 and 2 (delays 1.0, then 2.0) and the exhaustion WARNING
    "Failed to check guided_json support after all retries (server error)" with
    extra= {"llm_url", "error", "attempts": 3}, posts exactly 3 times, returns
    False and does NOT cache.

    All three retry-GUARD mutants of :499 are observable only here (at attempt
    0 they all still take the retry arm, so the one-retry drive above cannot
    separate them):
      _88 (`attempt <= max_retries - 1`) and _89 (`attempt < max_retries + 1`)
        keep the arm open at attempt 2, so they read retry_delays[2] == 4.0,
        sleep a THIRD time and emit a THIRD retry WARNING with no exhaustion
        record — killed by the sleep/record pins below.
      _90 (`attempt < max_retries - 2`) closes the arm one attempt EARLY: it
        takes exhaustion at attempt 1, so it posts only 2 times, sleeps
        [(1.0,)] once and logs a single retry WARNING — killed by the post
        count, the sleep sequence and the retry-WARNING count.
    The _88/_89 side of this pinning is also what makes the _22 equivalence
    non-vacuous: retry_delays[2] is consulted ONLY if this guard admits
    attempt 2, and the shipped guard does not, so the mutated 5.0 element is
    never read (see the module docstring proof).
    """
    d = await drive([hstatuserror(500, "server error 500")] * 3)
    d.not_cached()
    assert d.posts == 3
    assert d.sleep_args == [(1.0,), (2.0,)]
    assert d.texts().count(MSG_SRV_RETRY) == 2
    exh = d.record(logging.WARNING, MSG_SRV_EXH)
    assert extras(exh) == {"llm_url": LLM_URL, "error": "server error 500", "attempts": 3}
    assert d.records[-1] is exh
    retry1 = next(r for r in d.records if r.getMessage() == MSG_SRV_RETRY)
    assert extras(retry1)["retry_delay_seconds"] == 1.0


# ---------------------------------------------------------------------------
# connection-error arm — retry WARNING (:531-543)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_error_retry_warning_arm_membership_and_extras():
    """Kills mutmut_117, _118, _120, _121, _122, _123, _124, _125, _126, _127,
    _128, _129, _130, _131, _132, _133, _134, _135, _136 (and the same guards
    pin 152/153/154, which live in another chunk).

    Pins that httpx.ConnectError is handled by the CONNECTION arm
    (`except (httpx.ConnectError, httpx.TimeoutException)`): the retry WARNING
    must be "Failed to check guided_json support (connection error), retrying"
    — never the server-error or unexpected-error variant — with extra= EXACTLY
    {"llm_url", "error": "connect refused", "attempt": 1, "max_retries": 3,
    "retry_delay_seconds": 1.0}, followed by sleep(1.0) and the attempt-2
    success INFO. _117 (message None), _121/_122/_123 (XX/lower/upper), _118
    (extra=None), the dropped `extra=` _120 and the key/value renames
    _124-_136 ("XXllm_urlXX"/"LLM_URL", "XXerrorXX"/"ERROR", str(None),
    "XXattemptXX"/"ATTEMPT", attempt-1, attempt+2, "XXmax_retriesXX"/
    "MAX_RETRIES", "XXretry_delay_secondsXX"/"RETRY_DELAY_SECONDS") all break
    the message identity or the whole-dict extras equality.
    """
    d = await drive([httpx.ConnectError("connect refused"), 200, 200])
    d.settled_as(True)
    assert d.posts == 2
    assert d.sleep_args == [(1.0,)]
    d.silent_of(MSG_SRV_RETRY, MSG_SRV_EXH, MSG_UNX_RETRY, MSG_UNX_EXH)
    rec = d.record(logging.WARNING, MSG_CON_RETRY)
    assert extras(rec) == {
        "llm_url": LLM_URL,
        "error": "connect refused",
        "attempt": 1,
        "max_retries": 3,
        "retry_delay_seconds": 1.0,
    }
    assert extras(d.record(logging.INFO, MSG_OK)) == {"llm_url": LLM_URL, "attempts": 2}


# ---------------------------------------------------------------------------
# connection-error arm — exhaustion WARNING (:545-552)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_error_exhaustion_warning_message_extras_and_no_cache():
    """Kills mutmut_138, _139, _141, _142, _145, _146, _147, _148, _149.

    Three ConnectErrors: shipped logs two retry WARNINGs (attempts 1 and 2)
    then the exhaustion WARNING "Failed to check guided_json support after all
    retries (connection error)" with extra= EXACTLY {"llm_url", "error": "nope",
    "attempts": 3} — note the exhaustion extras use the PLURAL "attempts" key
    with max_retries as its value, while the retry extras use singular
    "attempt"; that difference is what the twin key groups keep honest. Return
    False with the cache left unset (so a later call re-probes) and sleeps
    [1.0, 2.0]. _138 replaces the message with None, _142 the XX-wrapped
    message, _139 `extra=None`, _141 the dropped `extra=` line, and
    _145/_146/_147/_148/_149 rename "llm_url"/"error" or replace the error text
    with str(None); a dropped extra= or a None message is exactly the case the
    whole-dict + whole-message comparison catches.
    """
    d = await drive([httpx.ConnectError("nope")] * 3)
    d.not_cached()
    assert d.posts == 3
    assert d.sleep_args == [(1.0,), (2.0,)]
    assert d.texts().count(MSG_CON_RETRY) == 2
    d.silent_of(MSG_OK, MSG_SRV_RETRY, MSG_SRV_EXH, MSG_UNX_RETRY, MSG_UNX_EXH)
    exh = d.record(logging.WARNING, MSG_CON_EXH)
    assert extras(exh) == {"llm_url": LLM_URL, "error": "nope", "attempts": 3}
    assert d.records[-1] is exh


# ---------------------------------------------------------------------------
# unexpected-error arm — retry WARNING (:559-571)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unexpected_error_retry_warning_is_its_own_arm():
    """Kills mutmut_157, _159, _163, _164, _165, _166, _167, _168, _169, _170,
    _171, _172, _173, _174, _175.

    A plain RuntimeError is not an httpx error and not an HTTPStatusError, so it
    lands in the catch-all arm and must log "Failed to check guided_json
    support (unexpected error), retrying" with extra= EXACTLY {"llm_url",
    "error": "kaboom", "attempt": 1, "max_retries": 3,
    "retry_delay_seconds": 1.0}, sleep 1.0, then succeed on attempt 2. Pinning
    the message here is not redundant with the other two arms: all three arms
    share the identical extra= shape group, so this is the only thing that
    attributes keys 157/159/163-175 to THIS occurrence rather than to the
    server- or connection-error twins.
    """
    d = await drive([RuntimeError("kaboom"), 200, 200])
    d.settled_as(True)
    assert d.posts == 2
    assert d.sleep_args == [(1.0,)]
    d.silent_of(MSG_SRV_RETRY, MSG_SRV_EXH, MSG_CON_RETRY, MSG_CON_EXH, MSG_UNX_EXH)
    rec = d.record(logging.WARNING, MSG_UNX_RETRY)
    assert extras(rec) == {
        "llm_url": LLM_URL,
        "error": "kaboom",
        "attempt": 1,
        "max_retries": 3,
        "retry_delay_seconds": 1.0,
    }


# ---------------------------------------------------------------------------
# unexpected-error arm — exhaustion WARNING (:573-579)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unexpected_error_exhaustion_warning_message_extras_and_no_cache():
    """Kills mutmut_178, _180, _184, _185, _186, _187, _188.

    Three RuntimeErrors: the shipped exhaustion record is WARNING "Failed to
    check guided_json support after all retries (unexpected error)" with extra=
    EXACTLY {"llm_url", "error": "kaboom", "attempts": 3} — the third member of
    the exhaustion-extra shape group whose twins 139/141 are pinned by the
    connection test above. Return False, cache left unset, 3 posts, sleeps
    [1.0, 2.0], and the exhaustion record is the LAST record emitted (the arm
    runs to completion). _178 is `extra=None`, _180 the dropped `extra=` line,
    _184/_185 the "llm_url" renames, _186/_187 the "error" renames and _188 the
    str(None) error value.
    """
    d = await drive([RuntimeError("kaboom")] * 3)
    d.not_cached()
    assert d.posts == 3
    assert d.sleep_args == [(1.0,), (2.0,)]
    assert d.texts().count(MSG_UNX_RETRY) == 2
    d.silent_of(MSG_OK, MSG_SRV_RETRY, MSG_SRV_EXH, MSG_CON_RETRY, MSG_CON_EXH)
    exh = d.record(logging.WARNING, MSG_UNX_EXH)
    assert extras(exh) == {"llm_url": LLM_URL, "error": "kaboom", "attempts": 3}
    assert d.records[-1] is exh


# ---------------------------------------------------------------------------
# arm membership for TimeoutException (pins that 117-136 belong to the
# connection arm's shape group, not to the unexpected arm's)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_exception_reuses_the_connection_arm_warning_text():
    """Pins arm membership for the connection-arm shape group (117-136 twins).

    httpx.TimeoutException shares the `except (httpx.ConnectError,
    httpx.TimeoutException)` clause, so its retry WARNING must be the
    CONNECTION variant with error "read timeout" — not the unexpected-error
    variant that the catch-all arm would log if the tuple membership changed.
    Same extras contract as the ConnectError drive.
    """
    d = await drive([httpx.TimeoutException("read timeout"), 200, 200])
    d.settled_as(True)
    assert d.posts == 2
    assert d.sleep_args == [(1.0,)]
    d.silent_of(MSG_UNX_RETRY, MSG_UNX_EXH, MSG_SRV_RETRY)
    rec = d.record(logging.WARNING, MSG_CON_RETRY)
    assert extras(rec) == {
        "llm_url": LLM_URL,
        "error": "read timeout",
        "attempt": 1,
        "max_retries": 3,
        "retry_delay_seconds": 1.0,
    }
