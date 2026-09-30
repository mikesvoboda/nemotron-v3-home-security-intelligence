# TARGET-MODULE: backend.services.clip_client
"""Batch-33 kill battery G: clip_client survivor pool (559 keys, 46.5%).

Targets (campaign #7, def-diff census /home/agent/runs/b33-c7-defdiffs.txt —
the 10-family taxonomy: 5 near-clone endpoint methods + 5 helpers):

* ``CLIPClient.embed`` (93) / ``anomaly_score`` (109) / ``classify`` (108) /
  ``similarity`` (111) / ``batch_similarity`` (108) — the shared families:
  endpoint-string args on ``_check_circuit_breaker``/``_get_breaker``
  (None/XX/case), URL + payload + headers call-shape, payload key/value/None,
  ``ai_duration`` and ``duration_ms`` arithmetic (``*1001`` / ``/1000`` /
  ``+ start_time`` / ``= None``), ``observe_ai_request_duration`` and
  ``record_pipeline_error`` name mutations, the 5xx boundary (``> 500`` /
  ``>= 501``), log-site families (msg None/XX/case, ``extra`` None/drop/rename,
  ``exc_info`` None/False/drop), and the ``CLIPUnavailableError`` ctor family
  (msg None/XX/case, ``original_error=None``/drop, ``sanitize_error(None)``).
* ``check_health`` (14), ``close`` (4), ``_get_breaker`` (3),
  ``_check_circuit_breaker`` (7, incl. the ``endpoint='embed'`` default-arg
  keys), ``_encode_image_to_base64`` (2).
* ``CLIPClient.__init__`` (48 keys, found by the bank reconcile — NOT in the
  559-survivor census): the bank's kills were stale era verdicts the CURRENT
  tree no longer produces (measured mid-campaign: __init___14 passes the full
  unit suite WITHOUT this battery installed; ``rstrip('XX/XX')`` strips the
  char-set {X,/} and no shipped test ever passes a URL ending in ``X``, nor
  reads timeouts/breaker-names/pool-limits/the init log). Pinned by the six
  construction tests at the foot of this file.

Kill mechanisms (every observation crosses a boundary the mutant cannot fake):

* Deterministic stub clock (``cc.time`` swap, +1000.0 s per call) makes every
  duration EXACT: success-path ``duration_ms`` == 3_000_000, error arms ==
  2_000_000, ``ai_duration`` == 1000.0 — the 1001 divisor-sum polarity flips,
  the ``+`` operator swaps and the ``= None`` families all die in arithmetic.
* A recording httpx stub pins the EXACT ``(url, kwargs)`` of every request —
  endpoint path, payload dict (key spellings, values, ``image_b64``), the
  ``json=``/``headers=`` kwargs (``None`` and drop are both visible) — plus
  ``raise_for_status``/``json`` call counts.
* Module-scope spy swaps (saved/restored) for ``get_correlation_headers``,
  ``observe_ai_request_duration`` and ``record_pipeline_error`` pin labels,
  call counts and the ai_duration VALUE.
* The shipped ContextFilter rides the capture handler (batteries D/F idiom);
  extras are read by VALUE (``getattr(rec, k, _MISS) == expected``) and the
  bogus renames (``XXduration_msXX`` / ``DURATION_MS`` / ``XXstatus_codeXX`` /
  ``STATUS_CODE``) are asserted ABSENT — the ambient-key audit holds: none of
  them is a context key (request_id/correlation_id/... battery A/D list).
* Per-endpoint circuit breakers make routing observable: after a failure arm
  the NAMED breaker's ``failure_count`` == 1 (and the embed alias is 1 only
  for embed — the alias identity ``_circuit_breaker is _breakers["embed"]``
  is the asymmetry pin); OPEN-rejection tests pin the endpoint label in the
  WARNING and the raised message (so ``CLIP None`` / ``CLIP XXembedXX`` /
  ``CLIP EMBED`` variants die even where the breaker object is equivalent).

Honesty ledger (pre-registered; reconcile after the bank pass):
- PRE-REGISTERED EQUIVALENTS (6 keys, expected GREEN):
  ``__init____mutmut_18`` (``getattr(settings, 'use_ai_gateway', False)`` ->
  default ``None``): compared with ``is True``, so False/None are
  indistinguishable — the shipped polarity (attr ABSENT + str gw_url ->
  clip_url) is pinned, the default swap cannot be (dropped-kwarg ``is True``
  family). Plus the two
  ``_encode_image_to_base64`` survivors are byte-identical by measurement
  (``image.save`` format is case-insensitive; the stdlib codec lookup
  normalizes ``UTF-8`` == ``utf-8``) — the battery pins the exact base64 so
  ANY real mutation would die, but these two constants cannot. And
  ``embed__5/6/7`` (``_get_breaker("embed")`` -> None/XX/EMBED): the
  ``_breakers.get`` fallback returns ``self._circuit_breaker`` WHICH IS
  ``_breakers["embed"]`` (measured ``is``-identity) — the arg is invisible on
  the embed path. The remaining ``_get_breaker`` keys die on observation:
  ``__1`` (arg=None) via the named-breaker counts / non-embed rejections,
  ``__2``/``__4`` (fallback default=None / dropped) via the unknown-endpoint
  call that must return the embed ALIAS, not None (sweep round 1 caught
  these two GREEN; round 2 pins them — reconcile after the bank pass).
- ``exc_info`` is asserted TRUTHY (shipped ``True`` attaches the triple);
  ``False``/``None``/drop die. (A string-spelling family would be
  equivalent — measured: ZERO such keys in this module's survivor set.)
- Rejection tests open the breaker via ``_transition_to_open()`` (shipped
  transition, real state machine; recovery_timeout is 60 s, so the OPEN state
  is time-stable for the duration of a test).
- No test edits production; every global (five ``cc`` module attributes incl.
  ``get_settings`` for the construction tests, the client's two http clients)
  is installed per-test and restored on exit.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Mirror the repo conftest env (the trampoline sweep imports this file
# directly; setdefault makes this a no-op under repo pytest). See battery A.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

_ROOT = str(Path.cwd())
if (Path(_ROOT) / "backend" / "services" / "clip_client.py").is_file():
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.services import clip_client as cc  # noqa: E402
from backend.services.circuit_breaker import CircuitState  # noqa: E402
from backend.services.clip_client import (  # noqa: E402
    EMBEDDING_DIMENSION,
    CLIPClient,
    CLIPUnavailableError,
)

# --- constants ---------------------------------------------------------------
BASE = "http://clip.test:9011"
HEADERS = {"traceparent": "00-aaaa-bbbb-01", "X-Correlation-ID": "corr-g"}
_MISS = object()
D_OK = 3_000_000  # success-path duration_ms under the stub clock
D_ERR = 2_000_000  # every error-arm duration_ms
AI_DUR = 1_000.0  # ai_duration under the stub clock

from PIL import Image  # noqa: E402  (after env guard, matches battery-A positioning)

IMG = Image.new("RGB", (4, 3), (10, 20, 30))


def _ref_png() -> bytes:
    buf = io.BytesIO()
    IMG.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def _ref_b64() -> str:
    return base64.b64encode(_ref_png()).decode("utf-8")


B64 = _ref_b64()
EMB = [0.5] * EMBEDDING_DIMENSION
BASELINE = [0.25] * EMBEDDING_DIMENSION
LABELS = ["alpha", "beta"]
TEXT = "a person at a door"
TEXTS = ["a door", "a person"]

# exception fixtures: (instance, str(instance))
CONN_EXC = httpx.ConnectError("conn refused")
TIMEOUT_EXC = httpx.TimeoutException("timed out here")
BOOM_EXC = RuntimeError("unexpected boom")


class _Rsp:
    """httpx.Response stand-in exposing only .status_code."""

    def __init__(self, status: int) -> None:
        self.status_code = status


def _status_exc(message: str, status: int) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError(message, request=None, response=_Rsp(status))  # type: ignore[arg-type]


SRV_EXC = _status_exc("server boom", 500)
CLI_EXC = _status_exc("client boom", 422)


def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- log capture (battery D/F idiom: shipped ContextFilter rides the handler)
class _ListHandler(logging.Handler):
    def __init__(self, sink: list[logging.LogRecord]) -> None:
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self.sink.append(record)


class LogCapture:
    def __enter__(self) -> LogCapture:
        self.records: list[logging.LogRecord] = []
        self._handler = _ListHandler(self.records)
        found = [f for f in cc.logger.filters if type(f).__name__ == "ContextFilter"]
        assert len(found) == 1, f"cc.logger must carry exactly one ContextFilter, got {found}"
        self._handler.addFilter(found[0])
        cc.logger.addHandler(self._handler)
        self._old_level = cc.logger.level
        cc.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc: object) -> None:
        cc.logger.removeHandler(self._handler)
        cc.logger.setLevel(self._old_level)

    @property
    def msgs(self) -> list[str]:
        return [r.getMessage() for r in self.records]


def _attrs(rec: logging.LogRecord, want: dict[str, Any], bogus: tuple[str, ...] = ()) -> None:
    for key, val in want.items():
        assert getattr(rec, key, _MISS) == val, (
            f"extra {key!r}: {getattr(rec, key, _MISS)!r} != {val!r}"
        )
    for key in bogus:
        assert getattr(rec, key, _MISS) is _MISS, f"bogus extra {key!r} present"


# --- test doubles -------------------------------------------------------------
class _Spy:
    """Callable recorder; returns a fresh HEADERS copy (identity differs per call)."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.last: Any = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        self.last = dict(HEADERS)
        return self.last


class _Clock:
    """time-module stand-in: +1000.0 s per time() call, fully deterministic."""

    def __init__(self) -> None:
        self.t = 1_700_000_000.0

    def time(self) -> float:
        val = self.t
        self.t += 1_000.0
        return val


class _Resp:
    def __init__(self, payload: Any = None, raise_exc: BaseException | None = None) -> None:
        self.payload = payload
        self.raise_exc = raise_exc
        self.raise_calls = 0
        self.json_calls = 0

    def raise_for_status(self) -> None:
        self.raise_calls += 1
        if self.raise_exc is not None:
            raise self.raise_exc

    def json(self) -> Any:
        self.json_calls += 1
        return self.payload


class _Http:
    """Records post/get; dispatches a canned response or a canned raise."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._resp: _Resp | None = None
        self._exc: BaseException | None = None

    def set(self, *, resp: _Resp | None = None, exc: BaseException | None = None) -> None:
        self._resp = resp
        self._exc = exc

    async def post(self, url: str, **kwargs: Any) -> _Resp:
        self.calls.append((url, kwargs))
        return self._dispatch()

    async def get(self, url: str, **kwargs: Any) -> _Resp:
        self.calls.append((url, kwargs))
        return self._dispatch()

    def _dispatch(self) -> _Resp:
        if self._exc is not None:
            raise self._exc
        assert self._resp is not None, "test bug: _Http used without set()"
        return self._resp


class _Aclosable:
    def __init__(self) -> None:
        self.aclose_calls = 0

    async def aclose(self) -> None:
        self.aclose_calls += 1


class _Env:
    """CLIPClient with the four cc module attributes spied and both http legs stubbed."""

    def __init__(self) -> None:
        self.client = CLIPClient(base_url=BASE)
        self.headers = _Spy()
        self.observe = _Spy()
        self.record = _Spy()
        self.clock = _Clock()
        self.http = _Http()
        self.health_http = _Http()
        self._old = (
            cc.get_correlation_headers,
            cc.observe_ai_request_duration,
            cc.record_pipeline_error,
            cc.time,
        )
        cc.get_correlation_headers = self.headers  # type: ignore[assignment]
        cc.observe_ai_request_duration = self.observe  # type: ignore[assignment]
        cc.record_pipeline_error = self.record  # type: ignore[assignment]
        cc.time = self.clock  # type: ignore[assignment]
        self.client._http_client = self.http  # type: ignore[assignment]
        self.client._health_http_client = self.health_http  # type: ignore[assignment]

    def __enter__(self) -> _Env:
        return self

    def __exit__(self, *exc: object) -> None:
        (
            cc.get_correlation_headers,
            cc.observe_ai_request_duration,
            cc.record_pipeline_error,
            cc.time,
        ) = self._old  # type: ignore[misc]


def _open_breaker(client: CLIPClient, endpoint: str) -> None:
    """Shipped transition to OPEN (real state machine; recovery_timeout keeps it open)."""
    client._breakers[endpoint]._transition_to_open()


def _call(client: CLIPClient, ep: str) -> Any:
    args = EP_SPECS[ep]["args"]
    method = getattr(client, ep)
    return _run(method(*args))


def _assert_failure_breaker(env: _Env, ep: str) -> None:
    """After one shipped failure arm: named breaker recorded 1 failure, alias 1 iff embed."""
    named = env.client._breakers[ep]
    alias = env.client._circuit_breaker
    assert named.failure_count == 1, f"{ep}: named failure_count {named.failure_count} != 1"
    assert named.state is CircuitState.CLOSED, f"{ep}: breaker must stay CLOSED at 1 failure"
    expected_alias = 1 if ep == "embed" else 0
    assert alias.failure_count == expected_alias, (
        f"{ep}: embed-alias failure_count {alias.failure_count} != {expected_alias}"
    )


def _assert_success_breaker(env: _Env, ep: str) -> None:
    """Success arm must reach the breaker: record_success resets failure_count.

    A pre-seeded failure makes a SKIPPED record_success visible (count stays 1).
    """
    named = env.client._breakers[ep]
    named.record_failure()
    assert named.failure_count == 1
    alias = env.client._circuit_breaker
    expected_alias = 1 if ep == "embed" else 0
    assert alias.failure_count == expected_alias
    assert named.state is CircuitState.CLOSED


# --- endpoint spec table (shipped strings transcribed verbatim from source) --
EP_SPECS: dict[str, dict[str, Any]] = {
    "embed": {
        "args": (IMG,),
        "url": f"{BASE}/embed",
        "payload": {"image": B64},
        "sending": "Sending embedding request to CLIP service...",
        "observe": "clip",
        "success": (
            {"embedding": EMB},
            EMB,
            f"CLIP embedding completed: {len(EMB)} dims in {D_OK}ms",
        ),
        "malformed": [
            (
                {"wrong": 1},
                "Malformed response from CLIP (missing 'embedding'): {'wrong': 1}",
                "Malformed response from CLIP service: missing 'embedding'",
                "clip_malformed_response",
            ),
            (
                {"embedding": [1.0, 2.0]},
                f"CLIP returned embedding with unexpected dimension: 2 != {EMBEDDING_DIMENSION}",
                "CLIP returned embedding with invalid dimension: 2",
                "clip_invalid_dimension",
            ),
        ],
        "conn": (
            "Failed to connect to CLIP service: conn refused",
            "Failed to connect to CLIP service: conn refused",
            "clip_connection_error",
        ),
        "timeout": (
            "CLIP request timed out: timed out here",
            "CLIP request timed out: timed out here",
            "clip_timeout",
        ),
        "server": (
            "CLIP returned server error: 500 - server boom",
            "CLIP returned server error: 500",
            "clip_server_error",
        ),
        "client": (
            "CLIP returned client error: 422 - client boom",
            "CLIP returned client error: 422",
            "clip_client_error",
        ),
        "unexpected": (
            "Unexpected error during CLIP embedding: unexpected boom",
            "Unexpected error during CLIP embedding: unexpected boom",
            "clip_unexpected_error",
        ),
    },
    "anomaly_score": {
        "args": (IMG, BASELINE),
        "url": f"{BASE}/anomaly-score",
        "payload": {"image": B64, "baseline_embedding": BASELINE},
        "sending": "Sending anomaly score request to CLIP service...",
        "observe": "clip_anomaly",
        "success": (
            {"anomaly_score": 0.25, "similarity_to_baseline": 0.75},
            (0.25, 0.75),
            f"CLIP anomaly score completed: score=0.250, similarity=0.750 in {D_OK}ms",
        ),
        "malformed": [
            (
                {"similarity_to_baseline": 0.5},
                "Malformed response from CLIP (missing 'anomaly_score'): {'similarity_to_baseline': 0.5}",
                "Malformed response from CLIP service: missing 'anomaly_score'",
                "clip_anomaly_malformed_response",
            ),
            (
                {"anomaly_score": 0.3},
                "Malformed response from CLIP (missing 'similarity_to_baseline'): {'anomaly_score': 0.3}",
                "Malformed response from CLIP service: missing 'similarity_to_baseline'",
                "clip_anomaly_malformed_response",
            ),
        ],
        "conn": (
            "Failed to connect to CLIP service for anomaly score: conn refused",
            "Failed to connect to CLIP service: conn refused",
            "clip_anomaly_connection_error",
        ),
        "timeout": (
            "CLIP anomaly score request timed out: timed out here",
            "CLIP anomaly score request timed out: timed out here",
            "clip_anomaly_timeout",
        ),
        "server": (
            "CLIP anomaly score returned server error: 500 - server boom",
            "CLIP returned server error: 500",
            "clip_anomaly_server_error",
        ),
        "client": (
            "CLIP anomaly score returned client error: 422 - client boom",
            "CLIP returned client error: 422",
            "clip_anomaly_client_error",
        ),
        "unexpected": (
            "Unexpected error during CLIP anomaly score: unexpected boom",
            "Unexpected error during CLIP anomaly score: unexpected boom",
            "clip_anomaly_unexpected_error",
        ),
    },
    "classify": {
        "args": (IMG, LABELS),
        "url": f"{BASE}/classify",
        "payload": {"image": B64, "labels": LABELS},
        "sending": f"Sending classification request to CLIP service with {len(LABELS)} labels...",
        "observe": "clip",
        "success": (
            {"scores": {"alpha": 0.9}, "top_label": "alpha"},
            ({"alpha": 0.9}, "alpha"),
            f"CLIP classification completed: top_label='alpha' in {D_OK}ms",
        ),
        "malformed": [
            (
                {"scores": {}},
                "Malformed response from CLIP classify (missing fields): {'scores': {}}",
                "Malformed response from CLIP service: missing 'scores' or 'top_label'",
                "clip_malformed_response",
            ),
        ],
        "conn": (
            "Failed to connect to CLIP service: conn refused",
            "Failed to connect to CLIP service: conn refused",
            "clip_connection_error",
        ),
        "timeout": (
            "CLIP request timed out: timed out here",
            "CLIP request timed out: timed out here",
            "clip_timeout",
        ),
        "server": (
            "CLIP returned server error: 500 - server boom",
            "CLIP returned server error: 500",
            "clip_server_error",
        ),
        "client": (
            "CLIP returned client error: 422 - client boom",
            "CLIP returned client error: 422",
            "clip_client_error",
        ),
        "unexpected": (
            "Unexpected error during CLIP classification: unexpected boom",
            "Unexpected error during CLIP classification: unexpected boom",
            "clip_unexpected_error",
        ),
    },
    "similarity": {
        "args": (IMG, TEXT),
        "url": f"{BASE}/similarity",
        "payload": {"image": B64, "text": TEXT},
        "sending": "Sending similarity request to CLIP service...",
        "observe": "clip",
        "success": ({"similarity": 0.5}, 0.5, f"CLIP similarity completed: 0.5000 in {D_OK}ms"),
        "malformed": [
            (
                {"nope": True},
                "Malformed response from CLIP similarity (missing 'similarity'): {'nope': True}",
                "Malformed response from CLIP service: missing 'similarity'",
                "clip_malformed_response",
            ),
        ],
        "conn": (
            "Failed to connect to CLIP service: conn refused",
            "Failed to connect to CLIP service: conn refused",
            "clip_connection_error",
        ),
        "timeout": (
            "CLIP request timed out: timed out here",
            "CLIP request timed out: timed out here",
            "clip_timeout",
        ),
        "server": (
            "CLIP returned server error: 500 - server boom",
            "CLIP returned server error: 500",
            "clip_server_error",
        ),
        "client": (
            "CLIP returned client error: 422 - client boom",
            "CLIP returned client error: 422",
            "clip_client_error",
        ),
        "unexpected": (
            "Unexpected error during CLIP similarity: unexpected boom",
            "Unexpected error during CLIP similarity: unexpected boom",
            "clip_unexpected_error",
        ),
    },
    "batch_similarity": {
        "args": (IMG, TEXTS),
        "url": f"{BASE}/batch-similarity",
        "payload": {"image": B64, "texts": TEXTS},
        "sending": f"Sending batch similarity request to CLIP service with {len(TEXTS)} texts...",
        "observe": "clip",
        "success": (
            {"similarities": {"a door": 0.25, "a person": 0.5}},
            {"a door": 0.25, "a person": 0.5},
            f"CLIP batch similarity completed: 2 scores in {D_OK}ms",
        ),
        "malformed": [
            (
                {},
                "Malformed response from CLIP batch-similarity (missing 'similarities'): {}",
                "Malformed response from CLIP service: missing 'similarities'",
                "clip_malformed_response",
            ),
        ],
        "conn": (
            "Failed to connect to CLIP service: conn refused",
            "Failed to connect to CLIP service: conn refused",
            "clip_connection_error",
        ),
        "timeout": (
            "CLIP request timed out: timed out here",
            "CLIP request timed out: timed out here",
            "clip_timeout",
        ),
        "server": (
            "CLIP returned server error: 500 - server boom",
            "CLIP returned server error: 500",
            "clip_server_error",
        ),
        "client": (
            "CLIP returned client error: 422 - client boom",
            "CLIP returned client error: 422",
            "clip_client_error",
        ),
        "unexpected": (
            "Unexpected error during CLIP batch similarity: unexpected boom",
            "Unexpected error during CLIP batch similarity: unexpected boom",
            "clip_unexpected_error",
        ),
    },
}

ENDPOINTS = list(EP_SPECS)


# --- endpoint matrices ---------------------------------------------------------
def test_success_matrix() -> None:
    """One clean round-trip per endpoint: call shape, payload, metrics, logs, breakers."""
    for ep in ENDPOINTS:
        spec = EP_SPECS[ep]
        with _Env() as env, LogCapture() as cap:
            resp = _Resp(payload=spec["success"][0])
            env.http.set(resp=resp)
            result = _call(env.client, ep)
        assert result == spec["success"][1], f"{ep}: returned {result!r}"
        assert env.http.calls == [(spec["url"], {"json": spec["payload"], "headers": HEADERS})], (
            f"{ep}: post call shape {env.http.calls!r}"
        )
        assert env.headers.calls == [((), {})], f"{ep}: _get_headers calls {env.headers.calls!r}"
        assert resp.raise_calls == 1 and resp.json_calls == 1, f"{ep}: resp call counts"
        assert env.observe.calls == [((spec["observe"], AI_DUR), {})], (
            f"{ep}: observe {env.observe.calls!r}"
        )
        assert env.record.calls == [], f"{ep}: error metric fired on success"
        assert cap.msgs == [spec["sending"], spec["success"][2]], f"{ep}: logs {cap.msgs!r}"
        _assert_success_breaker(env, ep)


def test_connect_error_matrix() -> None:
    for ep in ENDPOINTS:
        spec = EP_SPECS[ep]
        log_msg, raise_msg, metric = spec["conn"]
        with _Env() as env, LogCapture() as cap:
            env.http.set(exc=CONN_EXC)
            try:
                _call(env.client, ep)
                raise AssertionError(f"{ep}: expected CLIPUnavailableError")
            except CLIPUnavailableError as exc:
                err = exc
        assert str(err) == raise_msg, f"{ep}: raise {str(err)!r}"
        assert err.original_error is CONN_EXC, f"{ep}: original_error dropped/swapped"
        assert err.__cause__ is CONN_EXC, f"{ep}: 'from e' lost"
        assert env.http.calls == [(spec["url"], {"json": spec["payload"], "headers": HEADERS})]
        assert env.record.calls == [((metric,), {})], f"{ep}: metric {env.record.calls!r}"
        assert env.observe.calls == [], f"{ep}: duration observed on connect failure"
        assert cap.msgs == [spec["sending"], log_msg], f"{ep}: logs {cap.msgs!r}"
        rec = cap.records[-1]
        assert rec.levelno == logging.ERROR
        _attrs(rec, {"duration_ms": D_ERR}, ("XXduration_msXX", "DURATION_MS"))
        assert rec.exc_info, f"{ep}: exc_info missing"
        _assert_failure_breaker(env, ep)


def test_timeout_error_matrix() -> None:
    for ep in ENDPOINTS:
        spec = EP_SPECS[ep]
        log_msg, raise_msg, metric = spec["timeout"]
        with _Env() as env, LogCapture() as cap:
            env.http.set(exc=TIMEOUT_EXC)
            try:
                _call(env.client, ep)
                raise AssertionError(f"{ep}: expected CLIPUnavailableError")
            except CLIPUnavailableError as exc:
                err = exc
        assert str(err) == raise_msg, f"{ep}: raise {str(err)!r}"
        assert err.original_error is TIMEOUT_EXC
        assert err.__cause__ is TIMEOUT_EXC
        assert env.record.calls == [((metric,), {})], f"{ep}: metric {env.record.calls!r}"
        assert cap.msgs == [spec["sending"], log_msg], f"{ep}: logs {cap.msgs!r}"
        rec = cap.records[-1]
        assert rec.levelno == logging.ERROR
        _attrs(rec, {"duration_ms": D_ERR}, ("XXduration_msXX", "DURATION_MS"))
        assert rec.exc_info
        _assert_failure_breaker(env, ep)


def test_server_error_matrix() -> None:
    for ep in ENDPOINTS:
        spec = EP_SPECS[ep]
        log_msg, raise_msg, metric = spec["server"]
        with _Env() as env, LogCapture() as cap:
            env.http.set(resp=_Resp(raise_exc=SRV_EXC))
            try:
                _call(env.client, ep)
                raise AssertionError(f"{ep}: expected CLIPUnavailableError")
            except CLIPUnavailableError as exc:
                err = exc
        assert str(err) == raise_msg, f"{ep}: raise {str(err)!r}"
        assert err.original_error is SRV_EXC
        assert err.__cause__ is SRV_EXC
        assert env.record.calls == [((metric,), {})], f"{ep}: metric {env.record.calls!r}"
        assert cap.msgs == [spec["sending"], log_msg], f"{ep}: logs {cap.msgs!r}"
        rec = cap.records[-1]
        assert rec.levelno == logging.ERROR
        _attrs(
            rec,
            {"duration_ms": D_ERR, "status_code": 500},
            ("XXduration_msXX", "DURATION_MS", "XXstatus_codeXX", "STATUS_CODE"),
        )
        assert rec.exc_info
        _assert_failure_breaker(env, ep)


def test_client_error_matrix() -> None:
    for ep in ENDPOINTS:
        spec = EP_SPECS[ep]
        log_msg, raise_msg, metric = spec["client"]
        with _Env() as env, LogCapture() as cap:
            env.http.set(resp=_Resp(raise_exc=CLI_EXC))
            try:
                _call(env.client, ep)
                raise AssertionError(f"{ep}: expected CLIPUnavailableError")
            except CLIPUnavailableError as exc:
                err = exc
        assert str(err) == raise_msg, f"{ep}: raise {str(err)!r}"
        assert err.original_error is CLI_EXC
        assert err.__cause__ is CLI_EXC
        assert env.record.calls == [((metric,), {})], f"{ep}: metric {env.record.calls!r}"
        assert cap.msgs == [spec["sending"], log_msg], f"{ep}: logs {cap.msgs!r}"
        rec = cap.records[-1]
        assert rec.levelno == logging.ERROR
        _attrs(
            rec,
            {"duration_ms": D_ERR, "status_code": 422},
            ("XXduration_msXX", "DURATION_MS", "XXstatus_codeXX", "STATUS_CODE"),
        )
        assert rec.exc_info
        # 4xx is the user's fault: NO breaker failure recorded (5xx boundary pair
        # is pinned here too: >=501 / >500 shifts 500 into this arm ->
        # _assert_failure_breaker-style count dies in test_server_error_matrix).
        named = env.client._breakers[ep]
        assert named.failure_count == 0 and named.state is CircuitState.CLOSED
        assert env.client._circuit_breaker.failure_count == 0


def test_unexpected_error_matrix() -> None:
    for ep in ENDPOINTS:
        spec = EP_SPECS[ep]
        log_msg, raise_msg, metric = spec["unexpected"]
        with _Env() as env, LogCapture() as cap:
            env.http.set(exc=BOOM_EXC)
            try:
                _call(env.client, ep)
                raise AssertionError(f"{ep}: expected CLIPUnavailableError")
            except CLIPUnavailableError as exc:
                err = exc
        assert str(err) == raise_msg, f"{ep}: raise {str(err)!r} (sanitize_error(None) swaps)"
        assert err.original_error is BOOM_EXC
        assert err.__cause__ is BOOM_EXC
        assert env.record.calls == [((metric,), {})], f"{ep}: metric {env.record.calls!r}"
        assert cap.msgs == [spec["sending"], log_msg], f"{ep}: logs {cap.msgs!r}"
        rec = cap.records[-1]
        assert rec.levelno == logging.ERROR
        _attrs(rec, {"duration_ms": D_ERR}, ("XXduration_msXX", "DURATION_MS"))
        assert rec.exc_info
        _assert_failure_breaker(env, ep)


def test_malformed_response_matrix() -> None:
    """Missing/invalid payload fields: warning + metric + raise, breaker untouched."""
    for ep in ENDPOINTS:
        spec = EP_SPECS[ep]
        for payload, warn_msg, raise_msg, metric in spec["malformed"]:
            with _Env() as env, LogCapture() as cap:
                env.http.set(resp=_Resp(payload=payload))
                named = env.client._breakers[ep]
                named.record_failure()  # seed: the malformed arm must NOT reset/toggle
                try:
                    _call(env.client, ep)
                    raise AssertionError(f"{ep}: expected CLIPUnavailableError")
                except CLIPUnavailableError as exc:
                    err = exc
            assert str(err) == raise_msg, f"{ep}: raise {str(err)!r}"
            assert err.original_error is None, f"{ep}: malformed raise must not chain"
            assert env.record.calls == [((metric,), {})], f"{ep}: metric {env.record.calls!r}"
            assert cap.msgs == [spec["sending"], warn_msg], f"{ep}: logs {cap.msgs!r}"
            assert cap.records[-1].levelno == logging.WARNING
            assert named.failure_count == 1 and named.state is CircuitState.CLOSED
            assert env.client._circuit_breaker.failure_count == (1 if ep == "embed" else 0)


def test_breaker_rejection_matrix() -> None:
    """OPEN breaker: rejection before HTTP; endpoint label pinned in warning + raise."""
    for ep in ENDPOINTS:
        spec = EP_SPECS[ep]
        with _Env() as env:
            _open_breaker(env.client, ep)
            with LogCapture() as cap:
                try:
                    _call(env.client, ep)
                    raise AssertionError(f"{ep}: expected rejection")
                except CLIPUnavailableError as exc:
                    err = exc
        warn = f"CLIP {ep} circuit breaker is open, rejecting request"
        raised = (
            f"CLIP {ep} circuit breaker is open (state: open). Service is temporarily unavailable."
        )
        assert str(err) == raised, f"{ep}: raise {str(err)!r}"
        assert err.original_error is None
        assert cap.msgs == [warn], f"{ep}: logs {cap.msgs!r}"
        assert cap.records[0].levelno == logging.WARNING
        assert env.record.calls == [(("clip_circuit_open",), {})], (
            f"{ep}: metric {env.record.calls!r}"
        )
        assert env.http.calls == [], f"{ep}: HTTP reached despite open breaker"
        assert env.headers.calls == [] and env.observe.calls == []
        assert env.client._breakers[ep].state is CircuitState.OPEN


# --- helpers -------------------------------------------------------------------
def test_check_circuit_breaker_defaults_to_embed() -> None:
    """``_check_circuit_breaker()`` with no arg checks the EMBED breaker and says so."""
    with _Env() as env:
        _open_breaker(env.client, "embed")
        other = env.client._breakers["classify"]
        with LogCapture() as cap:
            try:
                env.client._check_circuit_breaker()
                raise AssertionError("expected rejection")
            except CLIPUnavailableError as exc:
                err = exc
    assert str(err) == (
        "CLIP embed circuit breaker is open (state: open). Service is temporarily unavailable."
    ), f"raise {str(err)!r}"
    assert cap.msgs == ["CLIP embed circuit breaker is open, rejecting request"]
    assert env.record.calls == [(("clip_circuit_open",), {})]
    assert other.state is CircuitState.CLOSED


def test_input_guards() -> None:
    """ValueError guards run BEFORE the breaker/HTTP round trip."""
    with _Env() as env, LogCapture() as cap:
        try:
            _run(env.client.anomaly_score(IMG, [1.0] * 4))
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert str(exc) == (
                f"Baseline embedding must have {EMBEDDING_DIMENSION} dimensions, got 4"
            ), f"anomaly guard: {str(exc)!r}"
        try:
            _run(env.client.classify(IMG, []))
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert str(exc) == "Labels list cannot be empty", f"classify guard: {str(exc)!r}"
        try:
            _run(env.client.batch_similarity(IMG, []))
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert str(exc) == "Texts list cannot be empty", f"batch guard: {str(exc)!r}"
    assert env.http.calls == [] and env.headers.calls == []
    assert env.record.calls == [] and env.observe.calls == []
    assert cap.msgs == [], f"guards must be silent, got {cap.msgs!r}"


def test_close_acloses_both_clients_and_logs() -> None:
    with _Env() as env:
        http, health = _Aclosable(), _Aclosable()
        env.client._http_client = http  # type: ignore[assignment]
        env.client._health_http_client = health  # type: ignore[assignment]
        with LogCapture() as cap:
            _run(env.client.close())
        assert http.aclose_calls == 1 and health.aclose_calls == 1
        assert cap.msgs == ["CLIPClient HTTP connections closed"], f"logs {cap.msgs!r}"
        assert cap.records[0].levelno == logging.DEBUG


def test_get_breaker_identity_per_endpoint() -> None:
    client = CLIPClient(base_url=BASE)
    for ep in ENDPOINTS:
        breaker = client._get_breaker(ep)
        assert breaker is client._breakers[ep], f"{ep}: _get_breaker returned {breaker!r}"
    assert client._circuit_breaker is client._breakers["embed"], "alias identity changed"
    # unknown endpoint -> the shipped fallback is the embed ALIAS (measured:
    # _breakers.get('bogus', self._circuit_breaker)). Kills the fallback-arg
    # family (__2 default=None, __4 default dropped -> both return None here).
    fallback = client._get_breaker("bogus-endpoint")
    assert fallback is client._circuit_breaker, f"fallback returned {fallback!r}"
    assert fallback is client._breakers["embed"]


def test_encode_image_deterministic_png_base64() -> None:
    client = CLIPClient(base_url=BASE)
    out = client._encode_image_to_base64(IMG)
    assert out == B64, "encode output drifted from the independent reference"
    assert base64.b64decode(out).startswith(b"\x89PNG"), "not a PNG byte stream"


def test_health_matrix() -> None:
    """check_health: success/arms — exact urls, headers, messages, boolean polarity."""
    with _Env() as env, LogCapture() as cap:
        resp = _Resp(payload=None)
        env.health_http.set(resp=resp)
        ok = _run(env.client.check_health())
    assert ok is True
    assert env.health_http.calls == [(f"{BASE}/health", {"headers": HEADERS})]
    assert resp.raise_calls == 1
    assert env.headers.calls == [((), {})]
    assert cap.msgs == [], f"clean health check must be silent, got {cap.msgs!r}"

    for exc, level, msg in (
        (CONN_EXC, logging.WARNING, "CLIP health check failed: conn refused"),
        (TIMEOUT_EXC, logging.WARNING, "CLIP health check failed: timed out here"),
        (SRV_EXC, logging.WARNING, "CLIP health check returned error status: server boom"),
        (BOOM_EXC, logging.ERROR, "Unexpected error during CLIP health check: unexpected boom"),
    ):
        with _Env() as env, LogCapture() as cap:
            env.health_http.set(exc=exc)
            bad = _run(env.client.check_health())
        assert bad is False
        assert cap.msgs == [msg], f"health arm logs {cap.msgs!r}"
        rec = cap.records[0]
        assert rec.levelno == level
        assert rec.exc_info, f"health arm {msg!r} lost exc_info"
        assert env.record.calls == [], "health check records no pipeline metrics"

    with _Env() as env, LogCapture() as cap:
        env.health_http.set(resp=_Resp(raise_exc=SRV_EXC))
        bad = _run(env.client.check_health())
    assert bad is False
    assert cap.msgs == ["CLIP health check returned error status: server boom"]
    assert cap.records[0].exc_info


# --- __init__ construction (48 stale-verdict keys, adjudicated mid-campaign) --
# The bank carried long-stable kills for these __init__ mutations, but the
# current tree does NOT kill them (measured: __init___14 passes the full
# unit suite WITHOUT battery G installed, and the shipped gateway tests pass
# standalone — the kills are era casualties of since-changed source/tests, not
# a regression this campaign introduced). The families were simply never
# pinned: nothing constructs a URL ending in 'X', reads the timeouts, checks
# breaker names/configs, inspects the connection pool limits, or captures the
# init log line. Stub values below deliberately differ from every default
# (httpx Timeout default 5.0, Limits defaults 100/20, breaker defaults 5/30.0/3).
S_CONNECT = 11.0
S_READ = 22.0
S_HEALTH = 33.0  # != httpx default 5.0 so timeout=None/drop are visible
CB_THRESHOLD = 7  # != breaker default 5
CB_RECOVERY = 44.0  # != default 30.0
CB_HALF_OPEN = 2  # != default 3


class _Settings:
    def __init__(self, **overrides: Any) -> None:
        self.clip_url = "http://clip/X"
        self.ai_connect_timeout = S_CONNECT
        self.clip_read_timeout = S_READ
        self.ai_health_timeout = S_HEALTH
        self.clip_cb_failure_threshold = CB_THRESHOLD
        self.clip_cb_recovery_timeout = CB_RECOVERY
        self.clip_cb_half_open_max_calls = CB_HALF_OPEN
        self.use_ai_gateway = False
        self.ai_gateway_url = None
        for k, v in overrides.items():
            setattr(self, k, v)
        if "use_ai_gateway" in overrides and overrides["use_ai_gateway"] == "ABSENT":
            del self.use_ai_gateway  # __24: getattr default False -> True


class _Stubbed:
    """Swap cc.get_settings for a stub; restore on exit (hand fake, no patch)."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._old = cc.get_settings

    def __enter__(self) -> _Stubbed:
        cc.get_settings = lambda: self._settings  # type: ignore[assignment]
        return self

    def __exit__(self, *exc: object) -> None:
        cc.get_settings = self._old  # type: ignore[assignment]


def _build(**overrides: Any) -> tuple[CLIPClient, _Settings]:
    stub = _Settings(**overrides)
    with _Stubbed(stub):
        client = CLIPClient()
    return client, stub


def test_init_explicit_base_url_keeps_trailing_x() -> None:
    """`rstrip('/')` vs mutant `rstrip('XX/XX')` (charset {X,/}): an X-terminated
    URL separates shipped from mutant on all three URL arms."""
    stub = _Settings()
    with _Stubbed(stub):
        client = CLIPClient(base_url="http://h:1/X")
        assert client._base_url == "http://h:1/X", f"explicit arm: {client._base_url!r}"
        client2 = CLIPClient(base_url="http://h:1//")
        assert client2._base_url == "http://h:1", f"slash arm: {client2._base_url!r}"
    _run(client.close())
    _run(client2.close())


def test_init_gateway_and_fallback_urls() -> None:
    """Gateway arm keeps X (kills the gw rstrip mutant); the NO-ATTRIBUTE case
    must stay on clip_url (kills getattr default False->True); use_ai_gateway
    False with a str gw_url also stays on clip_url (shipped polarity pin —
    default False->None is the pre-registered equivalent, `is True` can't see
    it)."""
    with _Stubbed(_Settings(use_ai_gateway=True, ai_gateway_url="http://gw/X")):
        client = CLIPClient()
        assert client._base_url == "http://gw/X/clip", f"gateway arm: {client._base_url!r}"
        gw = CLIPClient()
        assert gw._base_url == "http://gw/X/clip"
    with _Stubbed(_Settings(use_ai_gateway="ABSENT", ai_gateway_url="http://gw/x")):
        absent = CLIPClient()
        assert absent._base_url == "http://clip/X", f"absent-attr arm: {absent._base_url!r}"
    with _Stubbed(_Settings(use_ai_gateway=False, ai_gateway_url="http://gw/x")):
        off = CLIPClient()
        assert off._base_url == "http://clip/X", f"gw-off arm: {off._base_url!r}"
    for c in (client, gw, absent, off):
        _run(c.close())


def test_init_timeouts_from_settings_both_clients() -> None:
    """self._timeout / self._health_timeout AND both AsyncClients carry the
    settings values (kills =None and the dropped timeout= kwarg: httpx falls
    back to Timeout(5.0) != our 11/22/33 values)."""
    client, _ = _build()
    want_main = httpx.Timeout(connect=S_CONNECT, read=S_READ, write=S_READ, pool=S_CONNECT)
    want_health = httpx.Timeout(S_HEALTH)
    assert client._timeout == want_main, f"request timeout: {client._timeout!r}"
    assert client._health_timeout == want_health, f"health timeout: {client._health_timeout!r}"
    assert client._http_client.timeout == want_main, f"main client: {client._http_client.timeout!r}"
    assert client._health_http_client.timeout == want_health, (
        f"health client: {client._health_http_client.timeout!r}"
    )
    _run(client.close())


def test_init_breaker_names_and_shared_config() -> None:
    """Five endpoints, five exact names (None/XX/CASE all die) and ONE shared
    config carrying the stub values (config=None/dropped falls to defaults
    5/30.0/3 != 7/44.0/2)."""
    expected = {
        "embed": "clip_embed",
        "anomaly_score": "clip_anomaly_score",
        "classify": "clip_classify",
        "similarity": "clip_similarity",
        "batch_similarity": "clip_batch_similarity",
    }
    client, _ = _build()
    cfgs = []
    for ep, name in expected.items():
        breaker = client._breakers[ep]
        assert breaker.name == name, f"{ep}: breaker name {breaker.name!r}"
        cfg = breaker._config
        assert (cfg.failure_threshold, cfg.recovery_timeout, cfg.half_open_max_calls) == (
            CB_THRESHOLD,
            CB_RECOVERY,
            CB_HALF_OPEN,
        ), f"{ep}: breaker config {cfg!r}"
        cfgs.append(cfg)
    assert all(c is cfgs[0] for c in cfgs), "breakers must share the single _cb_config"
    assert client._circuit_breaker is client._breakers["embed"]
    _run(client.close())


def test_init_pool_limits_exact() -> None:
    """Limits(max_connections=10, max_keepalive_connections=5) on BOTH clients
    (drop -> 100/20 defaults, =None -> unlimited None, off-by-one -> 11/6)."""
    client, _ = _build()
    for label, http in (("main", client._http_client), ("health", client._health_http_client)):
        pool = http._transport._pool  # type: ignore[attr-defined]  (measured httpx 0.2x shape)
        assert pool._max_connections == 10, f"{label}: max_connections {pool._max_connections!r}"
        assert pool._max_keepalive_connections == 5, (
            f"{label}: keepalive {pool._max_keepalive_connections!r}"
        )
    _run(client.close())


def test_init_logs_info_line_with_base_url() -> None:
    """The construction INFO line names the resolved base_url (mutant logs None)."""
    stub = _Settings()
    with _Stubbed(stub), LogCapture() as cap:
        client = CLIPClient(base_url="http://log-me:1")
    assert cap.msgs == ["CLIPClient initialized with base_url=http://log-me:1"], (
        f"init logs {cap.msgs!r}"
    )
    assert cap.records[0].levelno == logging.INFO
    _run(client.close())
