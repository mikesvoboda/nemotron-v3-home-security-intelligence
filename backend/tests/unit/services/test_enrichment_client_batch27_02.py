"""Campaign #3 batch-27 slice 02 — duration_ms + metric-call-args survivors.

Target file: ``backend/services/enrichment_client.py`` (mutmut survivors,
exit_code == 0, from /tmp/wp-ec/diffs_exact.json):

* every ``duration_ms = int((time.time() - start_time) * 1000)`` site plus the
  consuming ``logger.*(…, extra={"duration_ms": …})`` call (key renames,
  value->None, dropped ``extra=`` kwarg, ``* 1000`` -> ``* 1001`` / ``/ 1000``,
  ``- start_time`` -> ``+ start_time``);
* ``explicit_timeout = enrichment_read_timeout + ai_connect_timeout``, the
  action-path ``action_read_timeout = 60.0`` / ``httpx.Timeout(...)`` family and
  ``asyncio.timeout(explicit_timeout)`` argument mutations (None / negative / +1);
* ``ai_duration = time.time() - ai_start_time`` -> ``+`` (feeds the observe call);
* every surviving argument mutation of ``observe_ai_request_duration``,
  ``record_pipeline_error`` and ``increment_enrichment_retry``.

Technique
---------
A **per-test** deterministic clock replaces ``time.time``.  Only frames whose
``__name__`` is the module under test consume a ``TICK``-second step; every
other caller (event loop, asyncio timeouts, logging) receives the last
published value, so no loop ever sees a moving or negative clock (and
``time.monotonic`` — the loop's own basis — is never touched).  The fixture is
function-scoped and restores the stdlib original in a ``finally`` after every
single test (the session-scope scripted clock in
test_enrichment_pipeline_batch26_12 poisoned 94 later tests in CI shard 4 —
never repeat that); the last test re-asserts the stdlib identities.

Two driving modes:

* *deterministic* — ``asyncio.sleep`` patched out, ``random.uniform`` pinned at
  0.0, timeouts in the future.  Because the clock steps per call site, the
  duration arithmetic is exact (1 read == TICK) in zero wall time, and the
  pristine call path's clock-read count is itself an assertion.
* *fires* — tiny settings (read=0.02 s, connect=0.05 s) make the real
  ``asyncio.timeout(explicit_timeout)`` (0.07 s) cancel a scripted 0.3 s
  response.  Mutating the argument to ``None`` (no timeout), a negative value
  (fires before the attempt completes) or ``+1`` (never fires) changes the
  observable outcome, killing the ``asyncio.timeout``-argument survivors.

Metric calls are spied with side-effect recorders that journal exact positional
args, so the string XXwrap/upper/None mutations, the ``error_type`` ternary
flips and the ``error_metric`` f-string mutations are all visible.  Log
assertions use a handler attached to the live module logger (the caplog
fixture is never used, so buffer-reset semantics do not apply).

All expectations were hand-derived from the pristine shipped source and
re-verified against a clean run of this file.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

import backend.services.enrichment_client as M
from backend.core.exceptions import EnrichmentUnavailableError

MODULE = M.__name__
TICK = 0.625  # module-clock step: per-call-site reads make the math exact
ABSENT = "<<absent>>"

SERVICE_URL = "http://test-enrichment:8094"

# stdlib identities captured at import time, before any fixture can patch
_time_original = time.time
_perf_counter_original = time.perf_counter
_monotonic_original = time.monotonic


# ---------------------------------------------------------------- clock ----
@pytest.fixture(autouse=True)
def stepped_clock() -> Iterator[dict[str, float]]:
    """Step ``time.time`` by TICK inside the module under test (per-test scope).

    Function-scoped by ruling: the patch is installed for ONE test and undone
    in a ``finally`` immediately after it, so nothing downstream can inherit a
    wrapped clock (the batch26_12 session-clock poisoner nuked 94 later tests
    in CI shard 4).  ``time.monotonic``/``perf_counter`` are never touched, so
    the event-loop clock (``loop.time()`` is monotonic-based) is structurally
    unaffected — verified 2026-09-26: a poisoned ``time.monotonic`` moves
    ``loop.time()`` live, while ``loop.time()`` never consults ``time.time``.
    Non-module frames receive the frozen last value, so asyncio/logging never
    see a stepping clock.  Fresh state per test => no cross-test tick coupling.
    """
    real = time.time
    state: dict[str, float] = {"t": 1_700_000_000.0, "n": 0}

    def fake_time() -> float:
        frame = sys._getframe(1)
        if frame.f_globals.get("__name__") == MODULE:
            value = state["t"]
            state["t"] = value + TICK
            state["n"] += 1
            return value
        return state["t"]

    time.time = fake_time
    try:
        assert M.time.time is fake_time  # the module sees the patched clock
        yield state
    finally:
        time.time = real
        # bulletproof restore: the *stdlib* builtin goes back in place, not
        # whatever a foreign module may have installed.
        assert time.time is real is _time_original
        assert M.time.time is _time_original


# --------------------------------------------------------- log capture ----
class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.recs: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.recs.append(record)

    @staticmethod
    def text(rec: logging.LogRecord) -> str:
        try:
            return rec.getMessage()
        except Exception:  # a mutant made the message unformattable
            return "<<unformattable>>"

    def find(self, needle: str) -> logging.LogRecord:
        hits = [r for r in self.recs if needle in self.text(r)]
        assert len(hits) == 1, (
            f"want exactly 1 record containing {needle!r}, got {len(hits)}: "
            f"{[self.text(r)[:80] for r in self.recs]}"
        )
        return hits[0]

    def extra(self, needle: str, key: str) -> Any:
        return getattr(self.find(needle), key, ABSENT)

    def messages(self) -> list[str]:
        return [self.text(r) for r in self.recs]


@pytest.fixture
def logs() -> Iterator[_Records]:
    """Capture handler on the live module logger (function scope, restored)."""
    lg = logging.getLogger(MODULE)
    handler = _Records()
    old_level = lg.level
    lg.addHandler(handler)
    lg.setLevel(logging.DEBUG)
    try:
        yield handler
    finally:
        lg.removeHandler(handler)
        lg.setLevel(old_level)


# ------------------------------------------------------------- metric spy --
@pytest.fixture(autouse=True)
def metric_calls() -> Iterator[list[tuple[Any, ...]]]:
    """Exact positional-arg journal of the three metrics helpers the module calls."""
    calls: list[tuple[Any, ...]] = []

    def _pipeline(error_type: Any) -> None:
        calls.append(("pipeline", error_type))

    def _observe(service: Any, duration_seconds: Any) -> None:
        calls.append(("observe", service, duration_seconds))

    def _retry(endpoint: Any) -> None:
        calls.append(("retry", endpoint))

    with (
        patch.object(M, "record_pipeline_error", side_effect=_pipeline, autospec=True),
        patch.object(M, "observe_ai_request_duration", side_effect=_observe, autospec=True),
        patch.object(M, "increment_enrichment_retry", side_effect=_retry, autospec=True),
    ):
        yield calls


def assert_journal(calls: list[tuple[Any, ...]], expected: list[tuple[Any, ...]]) -> None:
    assert len(calls) == len(expected), f"metric journal {calls} != expected {expected}"
    for got, want in zip(calls, expected, strict=True):
        if want[0] == "observe":
            assert got[0] == want[0] and got[1] == want[1], f"{got} != {want}"
            assert got[2] == pytest.approx(want[2]), f"{got} != {want}"
        else:
            assert got == want, f"{got} != {want}"


# -------------------------------------------------------------- settings ---
class _Settings:
    """Exact attribute surface the module reads (no MagicMock auto-attrs)."""

    ai_gateway_url = None
    use_ai_gateway = False
    enrichment_url = SERVICE_URL
    enrichment_light_url = "http://test-enrichment-light:8096"
    ai_health_timeout = 5.0
    enrichment_cb_failure_threshold = 5
    enrichment_cb_recovery_timeout = 60.0
    enrichment_cb_half_open_max_calls = 3

    def __init__(self, read: float, connect: float, retries: int) -> None:
        self.enrichment_read_timeout = read
        self.ai_connect_timeout = connect
        self.enrichment_max_retries = retries

    def get_enrichment_url_for_model(self, model: str) -> str:
        return SERVICE_URL


def _make_client(read: float, connect: float, retries: int) -> M.EnrichmentClient:
    settings = _Settings(read=read, connect=connect, retries=retries)
    with patch.object(M, "get_settings", return_value=settings, autospec=True):
        client = M.EnrichmentClient()
    for name in client._breakers:  # isolate: breakers never trip, never tick
        client._breakers[name] = MagicMock()
    client._http_client = MagicMock()
    client._http_client.post = AsyncMock()
    client._settings = settings
    return client


@pytest.fixture
def client() -> Iterator[M.EnrichmentClient]:
    """max_retries=3, read=60.0 / connect=10.0 -> explicit_timeout == 70.0."""
    yield _make_client(read=60.0, connect=10.0, retries=3)


# --------------------------------------------------------------- payloads --
VEHICLE_OK = {
    "vehicle_type": "sedan",
    "display_name": "Sedan",
    "confidence": 0.92,
    "is_commercial": False,
    "all_scores": {"sedan": 0.92},
    "inference_time_ms": 42.0,
}
PET_OK = {
    "pet_type": "dog",
    "breed": "labrador",
    "confidence": 0.9,
    "is_household_pet": True,
    "inference_time_ms": 33.0,
}
CLOTHING_OK = {
    "clothing_type": "jacket",
    "color": "blue",
    "style": "casual",
    "confidence": 0.8,
    "top_category": "outerwear",
    "description": "blue jacket",
    "is_suspicious": False,
    "is_service_uniform": False,
    "inference_time_ms": 21.0,
}
DEPTH_OK = {
    "depth_map_base64": "AAA=",
    "min_depth": 0.5,
    "max_depth": 9.0,
    "mean_depth": 3.0,
    "inference_time_ms": 55.0,
}
DISTANCE_OK = {
    "estimated_distance_m": 2.5,
    "relative_depth": 0.4,
    "proximity_label": "close",
    "inference_time_ms": 12.0,
}
POSE_OK = {
    "keypoints": [{"name": "nose", "x": 10.0, "y": 20.0, "confidence": 0.99}],
    "posture": "standing",
    "alerts": [],
    "inference_time_ms": 18.0,
}
ACTION_OK = {
    "action": "loitering",
    "confidence": 0.7,
    "is_suspicious": True,
    "risk_weight": 0.6,
    "all_scores": {"loitering": 0.7},
    "inference_time_ms": 40.0,
}
UNIFIED_OK = {
    "models_loaded": ["vitpose"],
    "inference_time_ms": 31.0,
    "pose": {"keypoints": [], "pose_class": "standing", "confidence": 0.9, "is_suspicious": False},
}


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", f"{SERVICE_URL}/x")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"status {status}", request=request, response=response)


def _response(payload: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return resp


def _post(value: Any = None, error: Any = None, delay: float | None = None) -> AsyncMock:
    """post() returning ``value`` / raising ``error``, optionally after ``delay``."""

    async def _post(*args: Any, **kwargs: Any) -> Any:
        if delay is not None:
            await asyncio.sleep(delay)
        if error is not None:
            raise error
        return value

    return AsyncMock(side_effect=_post)


# ------------------------------------------------------------------ specs --
# Messages are copied verbatim from the pristine source with the fixed inputs
# below substituted.
SPECS: dict[str, dict[str, Any]] = {
    "classify_vehicle": {
        "attr": "classify_vehicle",
        "breaker": "vehicle",
        "metric": "vehicle",
        "endpoint_name": "vehicle",
        "args": ("image",),
        "ok": VEHICLE_OK,
        "ok_checks": lambda r: (r.vehicle_type, r.confidence) == ("sedan", 0.92),
        "unexpected_msg": "Unexpected error during vehicle classification: boom",
        "unexpected_metric": "enrichment_vehicle_unexpected_error",
        "exhaust_msg": "Enrichment vehicle classification failed after {m} retries",
    },
    "classify_pet": {
        "attr": "classify_pet",
        "breaker": "pet",
        "metric": "pet",
        "endpoint_name": "pet",
        "args": ("image",),
        "ok": PET_OK,
        "ok_checks": lambda r: (r.pet_type, r.is_household_pet) == ("dog", True),
        "unexpected_msg": "Unexpected error during pet classification: boom",
        "unexpected_metric": "enrichment_pet_unexpected_error",
        "exhaust_msg": "Enrichment pet classification failed after {m} retries",
    },
    "classify_clothing": {
        "attr": "classify_clothing",
        "breaker": "clothing",
        "metric": "clothing",
        "endpoint_name": "clothing",
        "args": ("image",),
        "ok": CLOTHING_OK,
        "ok_checks": lambda r: (r.clothing_type, r.color) == ("jacket", "blue"),
        "unexpected_msg": "Unexpected error during clothing classification: boom",
        "unexpected_metric": "enrichment_clothing_unexpected_error",
        "exhaust_msg": "Enrichment clothing classification failed after {m} retries",
    },
    "estimate_depth": {
        "attr": "estimate_depth",
        "breaker": "depth",
        "metric": "depth",
        "endpoint_name": "depth",
        "args": ("image",),
        "ok": DEPTH_OK,
        "ok_checks": lambda r: (r.min_depth, r.mean_depth) == (0.5, 3.0),
        "unexpected_msg": "Unexpected error during depth estimation: boom",
        "unexpected_metric": "enrichment_depth_unexpected_error",
        "exhaust_msg": "Enrichment depth estimation failed after {m} retries",
    },
    "estimate_object_distance": {
        "attr": "estimate_object_distance",
        "breaker": "depth",
        "metric": "distance",
        "endpoint_name": "distance",
        "args": ("image", "bbox"),
        "ok": DISTANCE_OK,
        "ok_checks": lambda r: (r.estimated_distance_m, r.proximity_label) == (2.5, "close"),
        "unexpected_msg": "Unexpected error during distance estimation: boom",
        "unexpected_metric": "enrichment_distance_unexpected_error",
        "exhaust_msg": "Enrichment distance estimation failed after {m} retries",
    },
    "analyze_pose": {
        "attr": "analyze_pose",
        "breaker": "pose",
        "metric": "pose",
        "endpoint_name": "pose",
        "args": ("image",),
        "ok": POSE_OK,
        "ok_checks": lambda r: (r.posture, len(r.keypoints)) == ("standing", 1),
        "unexpected_msg": "Unexpected error during pose analysis: boom",
        "unexpected_metric": "enrichment_pose_unexpected_error",
        "exhaust_msg": "Enrichment pose analysis failed after {m} retries",
    },
    "classify_action": {
        "attr": "classify_action",
        "breaker": "action",
        "metric": "action",
        "endpoint_name": "action",
        "args": ("frames",),
        "ok": ACTION_OK,
        "ok_checks": lambda r: (r.action, r.is_suspicious) == ("loitering", True),
        "unexpected_msg": "Unexpected error during action classification: boom",
        "unexpected_metric": "enrichment_action_unexpected_error",
        "exhaust_msg": "Enrichment action classification failed after {m} retries",
    },
}
NAMES = list(SPECS)


def _drive(c: M.EnrichmentClient, name: str) -> Any:
    spec = SPECS[name]
    method = getattr(c, spec["attr"])
    if spec["args"] == ("image",):
        return method(Image.new("RGB", (8, 8), "red"))
    if spec["args"] == ("image", "bbox"):
        return method(Image.new("RGB", (64, 64), "blue"), (10.0, 10.0, 40.0, 40.0))
    return method([Image.new("RGB", (8, 8), "green") for _ in range(2)])


# ============================================ retry-loop failure handlers ==
# scenario -> (injected error, exact log message, expected extra fields,
#              raises?, clock reads made by the pristine path)
RETRY_SCENARIOS: dict[str, tuple[Any, str | None, dict[str, Any], bool, int]] = {
    # first-attempt handlers: start + ai_start + duration == 3 reads -> 2 TICK
    "client_error": (
        _http_error(404),
        "Enrichment returned client error: 404 - status 404",
        {"duration_ms": int(2 * TICK * 1000), "status_code": 404},
        False,
        3,
    ),
    "unexpected_error": (
        RuntimeError("boom"),
        None,  # resolved from spec["unexpected_msg"]
        {"duration_ms": int(2 * TICK * 1000)},
        True,
        3,
    ),
    # final-attempt handlers, 3 attempts, sleeps patched out:
    # start + ai_start x3 + duration == 5 reads -> 4 TICK
    "server_error": (
        _http_error(503),
        "Enrichment returned server error after 3 retries: 503 - status 503",
        {"duration_ms": int(4 * TICK * 1000), "status_code": 503},
        True,
        5,
    ),
    "conn_error": (
        httpx.ConnectError("down"),
        "Enrichment {en} failed after 3 retries: down",
        {"duration_ms": int(4 * TICK * 1000)},
        True,
        5,
    ),
    "httpx_timeout": (
        httpx.TimeoutException("slow"),
        "Enrichment {en} failed after 3 retries: slow",
        {"duration_ms": int(4 * TICK * 1000)},
        True,
        5,
    ),
    "asyncio_timeout": (
        TimeoutError("hang"),
        "Enrichment {en} asyncio timeout after 3 retries: request timed out after 70.0s",
        {"duration_ms": int(4 * TICK * 1000), "explicit_timeout": 70.0},
        True,
        5,
    ),
}


def _journal_for(name: str, scenario: str) -> list[tuple[Any, ...]]:
    metric = SPECS[name]["metric"]
    en = SPECS[name]["endpoint_name"]
    if scenario == "client_error":
        return [("pipeline", f"enrichment_{metric}_client_error")]
    if scenario == "unexpected_error":
        return [("pipeline", SPECS[name]["unexpected_metric"])]
    retries: list[tuple[Any, ...]] = [("retry", en), ("retry", en)]
    tail = {
        "server_error": f"enrichment_{metric}_server_error",
        "conn_error": f"enrichment_{metric}_connection_error",
        "httpx_timeout": f"enrichment_{metric}_timeout",
        "asyncio_timeout": f"enrichment_{metric}_asyncio_timeout",
    }[scenario]
    return retries + [("pipeline", tail)]


@pytest.mark.asyncio
@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("scenario", list(RETRY_SCENARIOS))
async def test_handler_duration_ms_and_metric_journal(
    client: M.EnrichmentClient,
    logs: _Records,
    stepped_clock: dict[str, float],
    metric_calls: list[tuple[Any, ...]],
    name: str,
    scenario: str,
) -> None:
    """duration_ms is exact and the metric arg journal is exact, per handler.

    Site coverage (classify_vehicle line numbers; every sibling method carries
    the identical family, e.g. pet 1438/1459/1483/1507/1519):
      * ``duration_ms = int((time.time() - start_time) * 1000)`` at
        1248/1269/1293/1317/1329 — assign->None, ``* 1001``, ``/ 1000`` and
        ``-`` -> ``+`` all miss the derived value;
      * ``extra={"duration_ms": …, "status_code"/"explicit_timeout": …}`` at
        1252/1275/1299/1323/1334 — XXwrap/upper key renames, ``extra=None`` and
        the dropped-extra kwarg remove the observed fields;
      * the ``error_type`` ternary (1281) and ``error_metric`` f-string (1294)
        via the conn_error vs httpx_timeout journal labels;
      * ``record_pipeline_error`` / ``increment_enrichment_retry`` arguments
        (endpoint_name, not None / not a mutated literal);
      * the ``exc_info=True`` kwarg of each handler's ``logger.error`` call
        (1250/1272/1297/1320/1332-family ``call_arg_mut`` -> ``exc_info=None``
        and the ``drop_arg`` variant that deletes the kwarg entirely): every
        shipped retry handler logs with ``exc_info=True`` (vehicle 1253 /
        1276 / 1300 / 1324 / 1335 and per-method siblings), so the record's
        ``exc_info`` must carry the injected exception type.
    """
    spec = SPECS[name]
    error, msg, extra, raises, reads = RETRY_SCENARIOS[scenario]
    if msg is None:
        msg = spec["unexpected_msg"]
    else:
        msg = msg.format(en=spec["endpoint_name"])

    client._http_client.post = _post(error=error)
    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch.object(M.random, "uniform", return_value=0.0, autospec=True),
    ):
        if raises:
            with pytest.raises(EnrichmentUnavailableError):
                await _drive(client, name)
        else:
            assert await _drive(client, name) is None

    # the pristine path performs exactly `reads` module clock reads
    assert stepped_clock["n"] == reads
    # the two backoff warnings between the 3 attempts, verbatim (pins the
    # retry-warning message sites, e.g. vehicle 1262/1286/1309: endpoint_name,
    # attempt/max_retries counters, deterministic delay 1.0/2.0s,
    # explicit_timeout rendering, and the server status code)
    if scenario in {"server_error", "conn_error", "httpx_timeout", "asyncio_timeout"}:
        en = spec["endpoint_name"]
        if scenario == "server_error":
            want = [
                f"Enrichment {en} retry 1/3, waiting 1.0s after server error 503",
                f"Enrichment {en} retry 2/3, waiting 2.0s after server error 503",
            ]
        elif scenario == "asyncio_timeout":
            want = [
                f"Enrichment {en} asyncio timeout (attempt 1/3), waiting 1.0s: "
                f"request timed out after 70.0s",
                f"Enrichment {en} asyncio timeout (attempt 2/3), waiting 2.0s: "
                f"request timed out after 70.0s",
            ]
        else:
            tail = "connection_error" if scenario == "conn_error" else "timeout"
            want = [
                f"Enrichment {en} retry 1/3, waiting 1.0s after {tail}",
                f"Enrichment {en} retry 2/3, waiting 2.0s after {tail}",
            ]
        got = [m for m in logs.messages() if "waiting" in m]
        assert got == want, (name, scenario, got)
    for key, expected in extra.items():
        assert logs.extra(msg, key) == expected, (name, scenario, key)
    if len(extra) == 1:  # extra carried duration_ms only
        assert logs.extra(msg, "status_code") is ABSENT
        assert logs.extra(msg, "explicit_timeout") is ABSENT
    # shipped handler passed exc_info=True -> traceback attached
    rec = logs.find(msg)
    assert rec.exc_info is not None and rec.exc_info[0] is type(error), (
        name,
        scenario,
        rec.exc_info,
    )
    assert_journal(metric_calls, _journal_for(name, scenario))


# ----------------------------------------------------------- success paths --


@pytest.mark.asyncio
@pytest.mark.parametrize("name", NAMES)
async def test_success_ai_duration_feeds_observe_metric(
    client: M.EnrichmentClient,
    stepped_clock: dict[str, float],
    metric_calls: list[tuple[Any, ...]],
    name: str,
) -> None:
    """ai_duration = time.time() - ai_start_time == TICK feeds the observer.

    Kills the ``Subtract->Add`` survivors on ai_duration (1227/1418/1607/1797/
    2024/2221/2438 — ``+`` yields ~3.4e9) and every
    ``observe_ai_request_duration("enrichment_*", …)`` argument mutation
    (1228/1419/1608/1798/2025/2222/2439: None, XXwrap, upper).  Also pins the
    parsed-result fields, so result-key mutations stay covered.
    """
    spec = SPECS[name]
    client._http_client.post = _post(value=_response(spec["ok"]))

    result = await _drive(client, name)

    assert spec["ok_checks"](result)
    assert stepped_clock["n"] == 3  # start + ai_start + ai_duration
    assert_journal(metric_calls, [("observe", f"enrichment_{spec['metric']}", TICK)])


@pytest.mark.asyncio
async def test_action_httpx_timeout_arguments(client: M.EnrichmentClient) -> None:
    """classify_action posts ``timeout=httpx.Timeout(10, 60, 60, 10)``.

    Kills the 2412 family (action_timeout=None and connect/read/write/pool
    -> None) and ``action_read_timeout = 60.0 -> 61.0`` (2396).
    """
    client._http_client.post = _post(value=_response(ACTION_OK))

    result = await _drive(client, "classify_action")

    assert result.action == "loitering"
    (call,) = client._http_client.post.call_args_list
    timeout = call.kwargs.get("timeout", None)
    assert timeout is not None, "timeout kwarg dropped from post()"
    assert (timeout.connect, timeout.read, timeout.write, timeout.pool) == (
        10.0,
        60.0,
        60.0,
        10.0,
    )


# ------------------------------------------------------- circuit + bbox ----


@pytest.mark.asyncio
@pytest.mark.parametrize("name", NAMES)
async def test_circuit_open_metric_and_no_clock(
    client: M.EnrichmentClient,
    stepped_clock: dict[str, float],
    metric_calls: list[tuple[Any, ...]],
    name: str,
) -> None:
    """A rejected breaker raises before ``start_time`` + enrichment_circuit_open."""
    breaker = client._breakers[SPECS[name]["breaker"]]
    breaker.allow_request.return_value = False

    with pytest.raises(EnrichmentUnavailableError) as excinfo:
        await _drive(client, name)

    assert str(excinfo.value) == ("Enrichment service circuit open - requests temporarily blocked")
    assert_journal(metric_calls, [("pipeline", "enrichment_circuit_open")])
    client._http_client.post.assert_not_called()
    assert stepped_clock["n"] == 0


@pytest.mark.asyncio
async def test_invalid_bbox_metric(client: M.EnrichmentClient, metric_calls: list) -> None:
    """Zero-area bbox -> None + enrichment_distance_invalid_bbox (1974)."""
    result = await client.estimate_object_distance(
        Image.new("RGB", (64, 64), "blue"), (5.0, 5.0, 5.0, 20.0)
    )

    assert result is None
    assert_journal(metric_calls, [("pipeline", "enrichment_distance_invalid_bbox")])
    client._http_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_bbox_outside_image_metric(client: M.EnrichmentClient, metric_calls: list) -> None:
    """Fully off-image bbox -> None + enrichment_distance_bbox_outside_image."""
    result = await client.estimate_object_distance(
        Image.new("RGB", (64, 64), "blue"), (100.0, 100.0, 140.0, 140.0)
    )

    assert result is None
    assert_journal(metric_calls, [("pipeline", "enrichment_distance_bbox_outside_image")])
    client._http_client.post.assert_not_called()


# ==================================================== enrich_detection =====


async def _enrich(
    c: M.EnrichmentClient,
    error: Any = None,
    value: Any = None,
    delay: float | None = None,
) -> Any:
    """Drive enrich_detection with get_settings patched (it calls it internally)."""
    c._http_client.post = _post(value=value, error=error, delay=delay)
    with patch.object(M, "get_settings", return_value=c._settings, autospec=True):
        return await c.enrich_detection(
            b"png-bytes", "person", (1.0, 2.0, 30.0, 40.0), options={"face_visible": True}
        )


ENRICH_SCENARIOS = {
    # handler-error, exact message, expected extra (reads: start + duration)
    "httpx_timeout": (
        httpx.TimeoutException("slow"),
        "Enrichment unified_enrich request timed out",
        {"duration_ms": int(2 * TICK * 1000), "detection_type": "person"},
    ),
    "asyncio_timeout": (
        TimeoutError(),
        "Enrichment unified_enrich asyncio timeout",
        {"duration_ms": int(2 * TICK * 1000), "detection_type": "person"},
    ),
    "http_error": (
        _http_error(503),
        "Enrichment unified_enrich HTTP error: 503",
        {"duration_ms": int(2 * TICK * 1000), "status_code": 503},
    ),
    "connect_error": (
        httpx.ConnectError("down"),
        "Enrichment unified_enrich connection error: down",
        {"duration_ms": int(2 * TICK * 1000)},
    ),
    "unexpected": (
        RuntimeError("boom"),
        "Enrichment unified_enrich unexpected error: boom",
        {"duration_ms": int(2 * TICK * 1000)},
    ),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", list(ENRICH_SCENARIOS))
async def test_enrich_detection_duration_ms(
    client: M.EnrichmentClient,
    logs: _Records,
    stepped_clock: dict[str, float],
    metric_calls: list[tuple[Any, ...]],
    scenario: str,
) -> None:
    """Every handler returns an empty result logging duration_ms == 1250.

    Kills the duration arithmetic at 3208/3217/3225/3233/3241 and the extra=
    mutations at 3211/3228/3236 (duration_ms / detection_type / status_code
    renames, dropped extra kwarg, msg=None).  The exact message also pins
    endpoint_name == "unified_enrich" (3159 mutations).
    """
    error, msg, extra = ENRICH_SCENARIOS[scenario]

    result = await _enrich(client, error=error)

    assert isinstance(result, M.UnifiedEnrichmentResult)
    assert result.models_loaded is None and result.pose is None
    for key, expected in extra.items():
        assert logs.extra(msg, key) == expected, (scenario, key)
    if len(extra) == 1:
        assert logs.extra(msg, "status_code") is ABSENT
        assert logs.extra(msg, "detection_type") is ABSENT
    # shipped: only the generic handler logs with exc_info=True (3245); the
    # four typed handlers (3209/3218/3226/3234) pass no exc_info at all.
    rec = logs.find(msg)
    if scenario == "unexpected":
        assert rec.exc_info is not None and rec.exc_info[0] is RuntimeError
    else:
        assert rec.exc_info is None
    assert_journal(metric_calls, [])
    assert stepped_clock["n"] == 3  # start + ai_start + duration


@pytest.mark.asyncio
async def test_enrich_detection_success(
    client: M.EnrichmentClient,
    stepped_clock: dict[str, float],
    metric_calls: list[tuple[Any, ...]],
) -> None:
    """Success -> observe("enrichment_unified", 0.625) and no error metrics."""
    result = await _enrich(client, value=_response(UNIFIED_OK))

    assert result.models_loaded == ["vitpose"]
    assert result.inference_time_ms == 31.0
    assert result.pose is not None and result.pose.pose_class == "standing"
    assert stepped_clock["n"] == 3  # start + ai_start + ai_duration
    assert_journal(metric_calls, [("observe", "enrichment_unified", TICK)])


# ======================================= asyncio.timeout arg (live clock) ==
# read=0.02 + connect=0.05 -> explicit_timeout == 0.07 s, so the shipped
# asyncio.timeout cancels a 0.3 s response.  ``None`` disables the timeout,
# a negative value fires before the attempt finishes, and +1 (71.0 s) never
# fires — all three change the observable outcome.  The action path uses
# connect=-59.93 so that 60.0 + -59.93 lands on ~0.07 while the mutated
# ``-`` variant (119.93) cannot fire within 0.3 s.


@pytest.mark.asyncio
@pytest.mark.parametrize("name", NAMES)
async def test_asyncio_timeout_fires_with_shipped_budget(
    logs: _Records,
    stepped_clock: dict[str, float],
    metric_calls: list[tuple[Any, ...]],
    name: str,
) -> None:
    """A 0.3 s attempt is cancelled by asyncio.timeout(explicit_timeout == 0.07)."""
    spec = SPECS[name]
    connect = -59.93 if name == "classify_action" else 0.05
    c = _make_client(read=0.02, connect=connect, retries=1)
    c._http_client.post = _post(delay=0.3)

    with pytest.raises(EnrichmentUnavailableError) as excinfo:
        await _drive(c, name)

    assert str(excinfo.value) == spec["exhaust_msg"].format(m=1)
    assert c._http_client.post.call_count == 1
    # the message carries the explicit timeout value; match its 0.07 prefix
    # (the action variant renders as 0.07000000000000028)
    msg = "asyncio timeout after 1 retries: request timed out after 0.07"
    assert logs.extra(msg, "duration_ms") == int(2 * TICK * 1000)
    assert logs.extra(msg, "explicit_timeout") == pytest.approx(0.07)
    assert_journal(metric_calls, [("pipeline", f"enrichment_{spec['metric']}_asyncio_timeout")])
    assert stepped_clock["n"] == 3


@pytest.mark.asyncio
async def test_enrich_detection_asyncio_timeout_fires(
    logs: _Records,
    stepped_clock: dict[str, float],
    metric_calls: list[tuple[Any, ...]],
) -> None:
    """Unified path: the live timeout fires -> empty result, duration_ms 2500."""
    c = _make_client(read=0.02, connect=0.05, retries=1)

    result = await _enrich(c, delay=0.3)

    assert isinstance(result, M.UnifiedEnrichmentResult)
    assert result.models_loaded is None
    msg = "Enrichment unified_enrich asyncio timeout"
    assert logs.extra(msg, "duration_ms") == int(2 * TICK * 1000)
    assert logs.extra(msg, "detection_type") == "person"
    assert_journal(metric_calls, [])
    assert stepped_clock["n"] == 3


@pytest.mark.asyncio
async def test_enrich_detection_success_under_live_timeout_budget(
    stepped_clock: dict[str, float],
    metric_calls: list[tuple[Any, ...]],
) -> None:
    """Live-budget success side of ``explicit_timeout = read + connect``.

    read=1.0 + connect=0.5 -> shipped budget 1.5 s straddles the scripted 1.0 s
    response with a 0.5 s margin on BOTH sides, so no wall-clock race decides
    the outcome.  The Add->Subtract mutant gives 1.0 - 0.5 == 0.5 s and fires
    ~0.5 s early -> empty result and no observe call (killed here); the
    None/no-timeout variant survives this test and is instead killed by the
    fires test above, whose exact ``explicit_timeout == 0.07`` extra can only
    come from ``0.02 + 0.05``.  Durations asserted here come from the fake
    steps (ai_duration == TICK), never from real elapsed time.
    """
    c = _make_client(read=1.0, connect=0.5, retries=1)

    result = await _enrich(c, value=_response(UNIFIED_OK), delay=1.0)

    assert result.models_loaded == ["vitpose"]
    assert result.pose is not None
    assert_journal(metric_calls, [("observe", "enrichment_unified", TICK)])
    assert stepped_clock["n"] == 3  # start + ai_start + ai_duration


# ================================================================ no leak ==


def test_clock_restored_to_stdlib_originals(stepped_clock: dict[str, float]) -> None:
    """Leak gate for the whole module.

    * ``perf_counter`` / ``monotonic`` are never patched here — if any module
      in this process leaks one (the batch26_12 session-clock failure mode),
      the identity check trips;
    * ``time.time`` must be either the stdlib builtin or *this* module's
      fixture clock (a foreign scripted clock fails the qualname check);
    * the fixture's ``finally`` restore is exercised for real: the stdlib
      builtin is re-installed, called, and the fixture clock put back (the
      module-scoped teardown re-asserts the identity once the module ends).
    """
    import time as time_mod

    assert time_mod.perf_counter is _perf_counter_original
    assert time_mod.monotonic is _monotonic_original
    current = time_mod.time
    assert current.__qualname__.startswith("stepped_clock"), f"foreign clock leak: {current!r}"
    time_mod.time = _time_original
    try:
        assert time_mod.time is _time_original and M.time.time is _time_original
        assert isinstance(time_mod.time(), float)
    finally:
        time_mod.time = current
    assert time_mod.time is current and M.time.time is current
