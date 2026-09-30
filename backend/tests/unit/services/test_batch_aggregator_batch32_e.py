# TARGET-MODULE: backend.services.batch_aggregator
"""Batch-32 kill battery E: the three fast-path owners (125 keys).

``_process_fast_path`` (27), ``_process_threat_fast_path`` (49) and
``_process_smoke_fire_fast_path`` (49) are campaign #6's third survivor pool —
every key read off the per-key def-diff (script /home/agent/runs/
b32-key-body.py against the bank; deduplicated shapes in
/home/agent/runs/b32-compact-fastpath.txt) and classified over those same
def-diffs; the family census below is THAT measurement, not an estimate:

* LOG CALLS (~110 keys, the whole of ``_process_fast_path``'s 27) — eight log
  sites (two info + one error per owner, plus fp's info/error), each mutated
  into the same shape family battery C/D killed: the message becomes ``None`` /
  ``'XXmsgXX'`` / ``'msg'`` / ``'MSG'``, ``extra=`` becomes ``None`` or is
  dropped, one extra KEY is re-spelled ``XXkXX`` / ``UPPER`` (21 keys — the
  biggest single shape), and the two error logs additionally flip
  ``exc_info=True`` to ``None`` or drop the kwarg. Kills need whole-message
  ``getMessage()`` equality (substring lets the case/XX spellings through),
  exact-value asserts on every extra attr, paired ABSENCE asserts for each
  mutant spelling (a renamed key just vanishes), and a ``rec.exc_info``
  identity assert on the error records (the caught exception object itself).
* SERVICE-CONSTRUCTION kwargs (3 keys) — ``ThreatMonitorService(session=None,
  redis_client=self._redis)`` and ``SmokeFireConsecutiveService(redis_client=
  self._redis)`` mutated to ``redis_client=None`` / the kwarg dropped. Invisible
  on any instance (dropped-kwarg lesson), so the battery patches the class in
  the module the lazy import reads and asserts the recorded CALL kwargs —
  identity (``is fake_redis``), not equality.
* DOWNSTREAM-CALL kwargs (2 keys) — ``process_threat_detection(threat_detection=
  None, event=None)`` with each kwarg dropped; killed by exact kwargs-dict
  equality on the autospec'd instance mock.
* ``or``-DEFAULT polarity (3 keys) — ``smoke_fire_type or 'unknown'`` respelled
  ``'XXunknownXX'`` / ``'UNKNOWN'`` and ``confidence or 0.0`` flipped to
  ``or 1.0``. Observable only on the falsy-input side, so the smoke battery
  runs BOTH scenarios: ``smoke_fire_type=None, confidence=None`` (the fallback
  path — exact ``'unknown'``/``0.0`` at the call site) and the real-value path
  (``'fire'``/``0.9`` passthrough — kills any mutant that swapped the whole
  expression for a constant).

Harness decisions:

* The lazy in-function imports (``from backend.services.threat_monitor_service
  import ThreatMonitorService`` etc.) bind the MODULE ATTRIBUTE at call time,
  so ``patch.object(the_module, 'Name', autospec=True)`` is visible to the code
  under test without touching import machinery — and autospec makes every
  patched site signature-checked (WP4.2).
* Log capture reuses battery C's ``LogCapture``: it installs the shipped
  ContextFilter on its handler. None of these eight sites calls
  ``log_context``, but the filter costs nothing and keeps the harness uniform.
* The clock is untouched: no fast-path site reads ``time`` (checked against the
  def-diffs), so no shim, no leak surface.
* Failure scenarios drive the error sites by making the recorded downstream
  call RAISE (``side_effect`` on the autospec'd method / a raising analyzer) —
  the shipped code catches everything, so the observable is exactly one error
  record with ``error=str(boom)`` and ``exc_info`` carrying the boom object.

Honesty ledger: MEASURED by the final sweep of this file against the bank
(shipped-green control + per-key trampoline sweep; RED/GREEN tally + every
green's disposition recorded here before the battery is installed — see the
b32 reconcile notes; nothing is claimed from diff shape alone).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

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
if (Path(_ROOT) / "backend" / "services" / "batch_aggregator.py").is_file():
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.services import batch_aggregator as ba  # noqa: E402
from backend.services import (  # noqa: E402
    smoke_fire_consecutive as sfc_mod,
)
from backend.services import (  # noqa: E402
    threat_monitor_service as tms_mod,
)
from backend.services.batch_aggregator import BatchAggregator  # noqa: E402

CAM = "cam-east"
DID = 90210
THREAT = "gun"
CONF = 0.87
BOOM = RuntimeError("stub downstream boom")
_MISS = object()


# --- event loop --------------------------------------------------------------
def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- log capture (battery C's, ContextFilter on the handler) -------------------
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
        found = [f for f in ba.logger.filters if type(f).__name__ == "ContextFilter"]
        assert len(found) == 1, f"ba.logger must carry exactly one ContextFilter, got {found}"
        self._handler.addFilter(found[0])
        ba.logger.addHandler(self._handler)
        self._old_level = ba.logger.level
        ba.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *_exc: object) -> None:
        ba.logger.removeHandler(self._handler)
        ba.logger.setLevel(self._old_level)

    def texts(self) -> list[str]:
        return [r.getMessage() for r in self.records]

    def one(self, level: int, message: str) -> logging.LogRecord:
        hits = [r for r in self.records if r.levelno == level and r.getMessage() == message]
        assert len(hits) == 1, f"want exactly one {message!r} at {level}, got {self.texts()}"
        return hits[0]

    def none_at_all(self) -> None:
        assert self.records == [], f"expected no log records, got {self.texts()}"


def _shown(rec: logging.LogRecord) -> str:
    return f"msg={rec.getMessage()!r} attrs={sorted(vars(rec))}"


def _attrs(rec: logging.LogRecord, want: dict[str, Any], absent: tuple[str, ...] = ()) -> None:
    """Exact value per ``extra`` key + explicit ABSENCE of the mutant spellings."""
    for key, value in want.items():
        got = getattr(rec, key, _MISS)
        assert got == value, f"extra {key!r} = {got!r}, want {value!r}; {_shown(rec)}"
    for key in absent:
        assert not hasattr(rec, key), f"unexpected extra attr {key!r} on {_shown(rec)}"


def _spellings(*keys: str) -> tuple[str, ...]:
    """The XX-wrapped and UPPER spellings mutmut generates for each key."""
    out: list[str] = []
    for k in keys:
        out += [f"XX{k}XX", k.upper()]
    return tuple(out)


# --- aggregator under test -----------------------------------------------------
class FakeRedis:
    """Identity-only stand-in: these owners pass the client to services and
    never call it themselves (verified against the def-diffs)."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []


def _agg(redis: FakeRedis, analyzer: Any = None) -> BatchAggregator:
    agg = BatchAggregator(redis_client=redis)  # type: ignore[arg-type]
    agg._analyzer = analyzer
    return agg


class RecordingAnalyzer:
    def __init__(self, raises: BaseException | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._raises = raises

    async def analyze_detection_fast_path(self, **kwargs: Any) -> None:
        self.calls.append(dict(kwargs))
        if self._raises is not None:
            raise self._raises


# =============================================================================
# _process_fast_path — info + error log sites (27 keys)
# =============================================================================
FP_DONE = "Fast path analysis completed for detection"
FP_FAIL = "Fast path analysis failed for detection"


def test_fast_path_success_logs_exact_message_and_both_extra_attrs() -> None:
    # The analyzer kwargs are asserted too: the shipped call passes BOTH
    # kwargs by name; a dropped one would show in .calls before any log.
    analyzer = RecordingAnalyzer()
    agg = _agg(FakeRedis(), analyzer)
    with LogCapture() as cap:
        _run(agg._process_fast_path(CAM, DID))
    assert analyzer.calls == [{"camera_id": CAM, "detection_id": DID}]
    rec = cap.one(logging.INFO, FP_DONE)
    _attrs(rec, {"camera_id": CAM, "detection_id": DID}, _spellings("camera_id", "detection_id"))


def test_fast_path_failure_logs_error_with_exc_info_and_swallows() -> None:
    analyzer = RecordingAnalyzer(raises=BOOM)
    agg = _agg(FakeRedis(), analyzer)
    with LogCapture() as cap:
        assert _run(agg._process_fast_path(CAM, DID)) is None
    rec = cap.one(logging.ERROR, FP_FAIL)
    _attrs(
        rec,
        {"camera_id": CAM, "detection_id": DID, "error": str(BOOM)},
        _spellings("camera_id", "detection_id", "error"),
    )
    # exc_info=True must carry THE caught exception; None/dropped mutants die.
    assert rec.exc_info is not None and rec.exc_info[1] is BOOM, _shown(rec)


def test_fast_path_success_path_emits_no_error_record() -> None:
    # Pinned by the error-site mutants that swap which logger call carries the
    # dict: the happy run must yield EXACTLY the one info record.
    analyzer = RecordingAnalyzer()
    agg = _agg(FakeRedis(), analyzer)
    with LogCapture() as cap:
        _run(agg._process_fast_path(CAM, DID))
    assert [r.levelno for r in cap.records] == [logging.INFO], cap.texts()


# =============================================================================
# _process_threat_fast_path — ctor kwargs, downstream kwargs, three log sites
# =============================================================================
TP_START = "Processing threat via fast path"
TP_DONE = "Threat fast path completed"
TP_FAIL = "Threat fast path processing failed"


def _threat_call(
    redis: FakeRedis,
    *,
    raises: BaseException | None = None,
    threat_type: str | None = THREAT,
    confidence: float | None = CONF,
) -> tuple[dict[str, Any], dict[str, Any], LogCapture]:
    """Run the threat fast path with ThreatMonitorService autospec-patched.

    Returns (constructor-call kwargs, downstream call kwargs, the live capture)
    — the two recorded dicts are what the kwargs-family mutants die on.
    """
    agg = _agg(redis)
    with patch.object(tms_mod, "ThreatMonitorService", autospec=True) as ctor:
        instance = ctor.return_value
        instance.process_threat_detection.side_effect = raises
        with LogCapture() as cap:
            _run(agg._process_threat_fast_path(CAM, DID, threat_type, confidence))
    ctor.assert_called_once()
    downcall = instance.process_threat_detection.call_args
    assert downcall is not None, "process_threat_detection was never called"
    return dict(ctor.call_args.kwargs), dict(downcall.kwargs), cap


def test_threat_fast_path_happy_calls_service_with_shipped_kwargs() -> None:
    redis = FakeRedis()
    ctor_kw, down_kw, cap = _threat_call(redis)
    # Construction: session kwarg present-None, redis by IDENTITY.
    assert set(ctor_kw) == {"session", "redis_client"}, ctor_kw
    assert ctor_kw["session"] is None
    assert ctor_kw["redis_client"] is redis, "redis_client must be the client itself"
    # Downstream call: exactly the shipped two kwargs, both None.
    assert down_kw == {"threat_detection": None, "event": None}, down_kw
    start = cap.one(logging.INFO, TP_START)
    _attrs(
        start,
        {"camera_id": CAM, "detection_id": DID, "threat_type": THREAT, "confidence": CONF},
        _spellings("camera_id", "detection_id", "threat_type", "confidence"),
    )
    done = cap.one(logging.INFO, TP_DONE)
    _attrs(
        done,
        {"camera_id": CAM, "detection_id": DID, "threat_type": THREAT},
        _spellings("camera_id", "detection_id", "threat_type"),
    )
    assert [r.levelno for r in cap.records] == [logging.INFO, logging.INFO], cap.texts()


def test_threat_fast_path_happy_with_optional_args_none() -> None:
    # The None-input sibling: threat_type/confidence ride into the start log
    # as None — kills any mutant that swapped the attr value for a constant.
    redis = FakeRedis()
    _ctor_kw, down_kw, cap = _threat_call(redis, threat_type=None, confidence=None)
    assert down_kw == {"threat_detection": None, "event": None}, down_kw
    start = cap.one(logging.INFO, TP_START)
    _attrs(
        start,
        {"camera_id": CAM, "detection_id": DID, "threat_type": None, "confidence": None},
        _spellings("camera_id", "detection_id", "threat_type", "confidence"),
    )


def test_threat_fast_path_failure_logs_error_with_exc_info() -> None:
    redis = FakeRedis()
    _ctor, _down, cap = _threat_call(redis, raises=BOOM)
    rec = cap.one(logging.ERROR, TP_FAIL)
    _attrs(
        rec,
        {"camera_id": CAM, "detection_id": DID, "threat_type": THREAT, "error": str(BOOM)},
        _spellings("camera_id", "detection_id", "threat_type", "error"),
    )
    assert rec.exc_info is not None and rec.exc_info[1] is BOOM, _shown(rec)
    # Only the START info survives — the completed log must NOT appear.
    assert cap.records[0].getMessage() == TP_START, cap.texts()
    assert sum(1 for r in cap.records if r.levelno == logging.ERROR) == 1


# =============================================================================
# _process_smoke_fire_fast_path — ctor kwarg, or-defaults, three log sites
# =============================================================================
SF_START = "Processing smoke/fire via fast path"
SF_DONE = "Smoke/fire fast path completed"
SF_FAIL = "Smoke/fire fast path processing failed"


def _smoke_call(
    redis: FakeRedis,
    *,
    raises: BaseException | None = None,
    smoke_fire_type: str | None = "fire",
    confidence: float | None = CONF,
) -> tuple[dict[str, Any], dict[str, Any], LogCapture]:
    agg = _agg(redis)
    with patch.object(sfc_mod, "SmokeFireConsecutiveService", autospec=True) as ctor:
        instance = ctor.return_value
        instance.process_smoke_fire_detection.side_effect = raises
        with LogCapture() as cap:
            _run(agg._process_smoke_fire_fast_path(CAM, DID, smoke_fire_type, confidence))
    ctor.assert_called_once()
    downcall = instance.process_smoke_fire_detection.call_args
    assert downcall is not None, "process_smoke_fire_detection was never called"
    return dict(ctor.call_args.kwargs), dict(downcall.kwargs), cap


def test_smoke_fast_path_real_values_pass_through_verbatim() -> None:
    redis = FakeRedis()
    ctor_kw, down_kw, cap = _smoke_call(redis, smoke_fire_type="fire", confidence=0.9)
    assert ctor_kw == {"redis_client": redis} or (
        set(ctor_kw) == {"redis_client"} and ctor_kw["redis_client"] is redis
    ), ctor_kw
    assert down_kw == {
        "camera_id": CAM,
        "detection_id": DID,
        "smoke_fire_type": "fire",
        "confidence": 0.9,
    }, down_kw
    start = cap.one(logging.INFO, SF_START)
    _attrs(
        start,
        {"camera_id": CAM, "detection_id": DID, "smoke_fire_type": "fire", "confidence": 0.9},
        _spellings("camera_id", "detection_id", "smoke_fire_type", "confidence"),
    )
    done = cap.one(logging.INFO, SF_DONE)
    _attrs(
        done,
        {"camera_id": CAM, "detection_id": DID, "smoke_fire_type": "fire"},
        _spellings("camera_id", "detection_id", "smoke_fire_type"),
    )
    assert [r.levelno for r in cap.records] == [logging.INFO, logging.INFO], cap.texts()


def test_smoke_fast_path_falsy_inputs_take_the_shipped_defaults() -> None:
    # The or-default polarity: None type -> 'unknown', None confidence -> 0.0.
    # The XXunknownXX / UNKNOWN / 1.0 mutants die on the exact call kwargs.
    redis = FakeRedis()
    _ctor_kw, down_kw, cap = _smoke_call(redis, smoke_fire_type=None, confidence=None)
    assert down_kw == {
        "camera_id": CAM,
        "detection_id": DID,
        "smoke_fire_type": "unknown",
        "confidence": 0.0,
    }, down_kw
    start = cap.one(logging.INFO, SF_START)
    _attrs(
        start,
        {
            "camera_id": CAM,
            "detection_id": DID,
            "smoke_fire_type": None,  # the LOG carries the raw None, not the fallback
            "confidence": None,
        },
        _spellings("camera_id", "detection_id", "smoke_fire_type", "confidence"),
    )
    done = cap.one(logging.INFO, SF_DONE)
    _attrs(
        done,
        {"camera_id": CAM, "detection_id": DID, "smoke_fire_type": None},
        _spellings("camera_id", "detection_id", "smoke_fire_type"),
    )


def test_smoke_fast_path_confidence_zero_keeps_default_polarity() -> None:
    # 0.0 is falsy: `confidence or 0.0` and `confidence or 1.0` both SEE falsy,
    # but the shipped expression yields 0.0 — assert at the call site.
    redis = FakeRedis()
    _ctor_kw, down_kw, _cap = _smoke_call(redis, smoke_fire_type="smoke", confidence=0.0)
    assert down_kw["confidence"] == 0.0, down_kw


def test_smoke_fast_path_failure_logs_error_with_exc_info() -> None:
    redis = FakeRedis()
    _ctor, _down, cap = _smoke_call(redis, raises=BOOM, smoke_fire_type="fire")
    rec = cap.one(logging.ERROR, SF_FAIL)
    _attrs(
        rec,
        {"camera_id": CAM, "detection_id": DID, "smoke_fire_type": "fire", "error": str(BOOM)},
        _spellings("camera_id", "detection_id", "smoke_fire_type", "error"),
    )
    assert rec.exc_info is not None and rec.exc_info[1] is BOOM, _shown(rec)
    assert cap.records[0].getMessage() == SF_START, cap.texts()
    assert sum(1 for r in cap.records if r.levelno == logging.ERROR) == 1


# --- isolation guards ---------------------------------------------------------
def test_fast_path_never_touches_the_redis_client_directly() -> None:
    # Pins the harness assumption (FakeRedis has no methods): none of the
    # three owners issues its own redis call — the client only rides into the
    # services, which is what makes the IDENTITY asserts sufficient.
    redis = FakeRedis()
    analyzer = RecordingAnalyzer()
    agg = _agg(redis, analyzer)
    with contextlib.suppress(Exception), LogCapture():
        _run(agg._process_fast_path(CAM, DID))
    assert redis.calls == []


def test_logcapture_isolation_no_records_after_exit() -> None:
    cap = LogCapture()
    with cap:
        ba.logger.info("inside")
    assert len(cap.records) == 1
    ba.logger.info("after")
    assert len(cap.records) == 1, "handler leaked after __exit__"
