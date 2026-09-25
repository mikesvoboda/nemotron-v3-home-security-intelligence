"""Batch-25 kill battery — chunk "NemotronAnalyzer.warmup#chunk1" (49 keys).

Every key in this chunk is a survivor of
backend/services/nemotron_analyzer.py::NemotronAnalyzer.warmup
(shipped lines 1466-1517). The method has four observable surfaces, all of
which the shipped code actually writes, and this file pins each of them:

  * the disabled branch: one DEBUG record with the exact
    "Nemotron warmup disabled by configuration" message, then True — and
    NOTHING else (no metric call, no probe, no _track_inference, no flag write)
  * the warmth FLAG lifecycle on the instance: _is_warming is exactly True
    while the readiness probe runs (so get_warmth_state() reports
    "warming") and exactly False again in the finally block
  * the three imported metric helpers: set_model_warmth_state("nemotron",
    "warming") -> ... -> ("nemotron","warm")/("nemotron","cold"),
    observe_model_warmup_duration("nemotron", duration) and
    record_model_cold_start("nemotron") on the cold path only
  * the log records: INFO "Starting Nemotron model warmup...", INFO
    f"Nemotron warmup completed in {duration:.2f}s" carrying
    extra={"duration","was_cold"}, and WARNING
    "Nemotron warmup failed - model not ready"

Spies go on backend.core.metrics (warmup does a LOCAL
`from backend.core.metrics import ...` inside its body, so patching the same
name on backend.services.nemotron_analyzer would intercept nothing) and the
module attribute `time` is replaced by a fixed ladder so `duration` is exact
and therefore mutant-comparable (the `+`/`-` swap in warmup__mutmut_25 turns
3.5 into 2003.5 instead of merely perturbing a real-clock reading).

This file lives OUTSIDE the repo tree, so the repo conftest.py does not apply:
the minimum env vars the repo conftest sets are mirrored below and
pytestmark = pytest.mark.unit is declared. asyncio_mode=auto is not picked up
either, so every async test carries an explicit @pytest.mark.asyncio.
Every mock patch call site carries autospec=True (CI ratchet).
"""

from __future__ import annotations

import logging
import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("OTEL_ENABLED", "false")

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

import backend.services.nemotron_analyzer as NA
from backend.services.nemotron_analyzer import NemotronAnalyzer

LOG_NAME = "backend.services.nemotron_analyzer"

DISABLED_MSG = "Nemotron warmup disabled by configuration"
START_MSG = "Starting Nemotron model warmup..."
FAILED_MSG = "Nemotron warmup failed - model not ready"

_MISSING = object()


class _Clock:
    """time.monotonic() stand-in replaying a fixed ladder, then 1e9."""

    def __init__(self, values) -> None:
        self._values = list(values)
        self.calls = 0

    def monotonic(self) -> float:
        self.calls += 1
        if self._values:
            return self._values.pop(0)
        return 1e9


class _LogCap(logging.Handler):
    """Collects (level, message, extra-attr snapshot) tuples for one logger."""

    def __init__(self, logger_name: str, attrs: tuple[str, ...]) -> None:
        super().__init__()
        self.attrs = attrs
        self.records: list[tuple[int, object, dict]] = []
        self._logger = logging.getLogger(logger_name)
        self._prev_level = self._logger.level

    def emit(self, record: logging.LogRecord) -> None:
        snap = {k: getattr(record, k, _MISSING) for k in self.attrs}
        self.records.append((record.levelno, record.getMessage(), snap))

    def __enter__(self) -> _LogCap:
        self._logger.addHandler(self)
        self._logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc) -> None:
        self._logger.removeHandler(self)
        self._logger.setLevel(self._prev_level)


async def run_warmup(
    *,
    enabled: bool = True,
    last_inference: float | None = None,
    threshold: float = 300.0,
    probe_result: bool = True,
    clock_ladder: tuple[float, ...] = (),
) -> dict:
    """Drive the SHIPPED warmup() with spies; returns everything it touched.

    _is_warming / get_warmth_state() are sampled INSIDE the readiness probe
    (the only window where the "warming" state is observable) and again after
    the call returns, still inside the fake-clock scope so the ladder keeps
    every duration exact.
    """
    an = NemotronAnalyzer.__new__(NemotronAnalyzer)
    an._warmup_enabled = enabled
    an._is_warming = False
    an._last_inference_time = last_inference
    an._cold_start_threshold = threshold

    warmth_calls: list[tuple] = []
    observe_calls: list[tuple] = []
    cold_calls: list[tuple] = []
    facts: dict = {}

    def _warmth(model, state):
        warmth_calls.append((model, state))

    def _observe(model, duration):
        observe_calls.append((model, duration))

    def _cold(model):
        cold_calls.append((model,))

    async def _probe(self):
        facts["is_warming_during"] = self._is_warming
        facts["state_during"] = self.get_warmth_state()
        return probe_result

    clock = _Clock(clock_ladder)
    with (
        patch.object(NA, "time", new=clock),
        patch("backend.core.metrics.set_model_warmth_state", autospec=True, side_effect=_warmth),
        patch(
            "backend.core.metrics.observe_model_warmup_duration",
            autospec=True,
            side_effect=_observe,
        ),
        patch("backend.core.metrics.record_model_cold_start", autospec=True, side_effect=_cold),
        patch.object(NemotronAnalyzer, "model_readiness_probe", autospec=True, side_effect=_probe),
    ):
        ret = await an.warmup()
        facts["is_warming_after"] = an._is_warming
        facts["state_after"] = an.get_warmth_state()
        facts["last_inference_after"] = an._last_inference_time

    facts.update(
        ret=ret,
        warmth_calls=warmth_calls,
        observe_calls=observe_calls,
        cold_calls=cold_calls,
        clock_calls=clock.calls,
    )
    return facts


# Ladders. Every value is consumed by exactly one shipped time.monotonic():
# COLD:  is_cold() short-circuits on _last_inference_time is None (no tick),
#        1000.0 start_time | 1003.5 duration end | 1010.0 _track_inference |
#        1011.0 the post-run get_warmth_state() sample.
COLD_LADDER = (1000.0, 1003.5, 1010.0, 1011.0)
# WARM: is_cold() ticks (1005.0 - 1000.0 = 5.0 < 300 -> not cold), then the
#       same four sites from 2000.0.
WARM_LADDER = (1005.0, 2000.0, 2003.5, 2010.0, 2011.0)
# FAILURE: only start_time + duration end are reached (no _track_inference).
FAIL_LADDER = (1000.0, 1003.5, 1011.0)

DURATION = 3.5
COMPLETED_MSG = "Nemotron warmup completed in 3.50s"


# ---------------------------------------------------------------------------
# disabled branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_warmup_disabled_logs_exact_debug_message_and_does_nothing_else():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_2,
    ...__mutmut_3, ...__mutmut_4, ...__mutmut_5.

    Pins the shipped disabled branch (backend/services/nemotron_analyzer.py:
    1485-1487): exactly one DEBUG record whose message IS
    "Nemotron warmup disabled by configuration", then return True with no
    metric call, no readiness probe and no warmth-flag write. Mutants
    warmup__mutmut_2 (message -> None), __mutmut_3 (XX-wrapped),
    __mutmut_4 (lowercased) and __mutmut_5 (uppercased) each break the
    message-equality assertion below.
    """
    with _LogCap(LOG_NAME, ("duration", "was_cold")) as cap:
        facts = await run_warmup(enabled=False, clock_ladder=())

    assert facts["ret"] is True
    messages = [(lvl, msg) for lvl, msg, _ in cap.records]
    assert messages == [(logging.DEBUG, DISABLED_MSG)]
    # nothing else happens on this path
    assert facts["warmth_calls"] == []
    assert facts["observe_calls"] == []
    assert facts["cold_calls"] == []
    assert facts["is_warming_after"] is False
    assert facts["last_inference_after"] is None
    assert facts["clock_calls"] == 0


# ---------------------------------------------------------------------------
# warmth-flag lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_warmup_sets_the_warming_flag_true_while_the_probe_runs():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_8,
    ...__mutmut_9.

    Line 1490 `self._is_warming = True` is only observable through the probe
    window: sampled inside model_readiness_probe the shipped flag is exactly
    True (identity, not truthiness) and get_warmth_state() therefore reports
    state "warming". __mutmut_8 (-> None) and __mutmut_9 (-> False) are both
    falsy, so the sampled state falls through to "cold"/"warm".
    """
    facts = await run_warmup(clock_ladder=COLD_LADDER)

    assert facts["ret"] is True
    assert facts["is_warming_during"] is True
    assert facts["state_during"] == {"state": "warming", "last_inference_seconds_ago": None}


@pytest.mark.asyncio
async def test_warmup_clears_the_warming_flag_in_the_finally_block():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_65,
    ...__mutmut_66.

    The finally at line 1517 must leave _is_warming exactly False on BOTH
    exits, so the post-run get_warmth_state() reports the real warmth ("warm"
    after a successful cold warmup, "cold" after a failed one). __mutmut_65
    (-> None) and __mutmut_66 (-> True) leave a flag that is not False and
    keep the state stuck at "warming".
    """
    ok = await run_warmup(clock_ladder=COLD_LADDER)
    assert ok["ret"] is True
    assert ok["is_warming_after"] is False
    assert ok["state_after"] == {"state": "warm", "last_inference_seconds_ago": 1.0}
    assert ok["last_inference_after"] == 1010.0

    bad = await run_warmup(probe_result=False, clock_ladder=FAIL_LADDER)
    assert bad["ret"] is False
    assert bad["is_warming_after"] is False
    assert bad["state_after"] == {"state": "cold", "last_inference_seconds_ago": None}
    assert bad["last_inference_after"] is None


# ---------------------------------------------------------------------------
# metric calls: warmth gauge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_warmup_opens_with_the_warming_gauge_under_the_nemotron_label():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_10,
    ...__mutmut_11, ...__mutmut_14, ...__mutmut_15, ...__mutmut_16,
    ...__mutmut_17.

    Line 1491 calls set_model_warmth_state("nemotron", "warming") before the
    probe runs. The gauge maps the state string
    {"cold":0,"warming":1,"warm":2} (backend/core/metrics.py:3375) and labels
    by model, so a NULLed/"XX.."/upper-cased argument changes the exported
    series or its value. Asserted here is the exact first call.
    """
    facts = await run_warmup(clock_ladder=COLD_LADDER)

    assert facts["warmth_calls"][0] == ("nemotron", "warming")


@pytest.mark.asyncio
async def test_warmup_success_closes_with_the_warm_gauge_under_the_nemotron_label():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_35,
    ...__mutmut_36, ...__mutmut_39, ...__mutmut_40, ...__mutmut_41,
    ...__mutmut_42.

    Line 1506 is the second (and last) gauge write of a successful warmup, so
    the shipped sequence over the whole call is exactly
    [("nemotron","warming"), ("nemotron","warm")] on both the cold and the
    warm entry path.
    """
    cold = await run_warmup(clock_ladder=COLD_LADDER)
    assert cold["warmth_calls"] == [("nemotron", "warming"), ("nemotron", "warm")]

    warm = await run_warmup(last_inference=1000.0, clock_ladder=WARM_LADDER)
    assert warm["warmth_calls"] == [("nemotron", "warming"), ("nemotron", "warm")]


@pytest.mark.asyncio
async def test_warmup_failure_writes_the_cold_gauge_and_no_warm_gauge():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_52,
    ...__mutmut_53, ...__mutmut_56, ...__mutmut_57, ...__mutmut_58,
    ...__mutmut_59.

    The not-ready branch (line 1513) sets ("nemotron","cold") and never
    "warm": the shipped sequence is exactly
    [("nemotron","warming"), ("nemotron","cold")] with the gauge landing on
    0 for the nemotron label.
    """
    facts = await run_warmup(probe_result=False, clock_ladder=FAIL_LADDER)

    assert facts["ret"] is False
    assert facts["warmth_calls"] == [("nemotron", "warming"), ("nemotron", "cold")]


# ---------------------------------------------------------------------------
# metric calls: duration histogram + cold-start counter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_warmup_observations_carry_the_subtraction_based_duration():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_25.

    `duration = time.monotonic() - start_time` (line 1499) is pinned twice
    over with the ladder 1000.0 -> 1003.5: the histogram observation is
    exactly 3.5 and the completion log line reads "...completed in 3.50s".
    __mutmut_25's `+` yields 2003.5 / "2003.50s".
    """
    with _LogCap(LOG_NAME, ("duration", "was_cold")) as cap:
        facts = await run_warmup(clock_ladder=COLD_LADDER)

    assert facts["observe_calls"] == [("nemotron", DURATION)]
    completed = [(lvl, msg) for lvl, msg, _ in cap.records if lvl == logging.INFO][-1]
    assert completed == (logging.INFO, COMPLETED_MSG)


@pytest.mark.asyncio
async def test_warmup_duration_is_observed_under_the_nemotron_label():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_26,
    ...__mutmut_30, ...__mutmut_31.

    Line 1500 hands the histogram exactly ("nemotron", duration) — and it is
    observed on the FAILURE path too, before the branch.
    """
    ok = await run_warmup(clock_ladder=COLD_LADDER)
    assert ok["observe_calls"] == [("nemotron", DURATION)]

    bad = await run_warmup(probe_result=False, clock_ladder=FAIL_LADDER)
    assert bad["observe_calls"] == [("nemotron", DURATION)]


@pytest.mark.asyncio
async def test_cold_warmup_records_a_cold_start_under_the_nemotron_label():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_32,
    ...__mutmut_33, ...__mutmut_34.

    Entering warmup with _last_inference_time None makes is_cold() True, so a
    successful warmup increments the cold-start counter exactly once with
    "nemotron" (line 1505).
    """
    facts = await run_warmup(clock_ladder=COLD_LADDER)

    assert facts["cold_calls"] == [("nemotron",)]


@pytest.mark.asyncio
async def test_warm_warmup_skips_the_cold_start_counter_and_logs_was_cold_false():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_7.

    `was_cold = self.is_cold()` (line 1489) feeds BOTH the
    record_model_cold_start gate and the completion log's was_cold extra.
    With a recent _last_inference_time the shipped run records no cold start
    and logs was_cold False; __mutmut_7 replaces the call with None, which
    suppresses the counter even on the cold path (pinned by the sibling test)
    and logs was_cold None here.
    """
    with _LogCap(LOG_NAME, ("duration", "was_cold")) as cap:
        facts = await run_warmup(last_inference=1000.0, clock_ladder=WARM_LADDER)

    assert facts["ret"] is True
    assert facts["cold_calls"] == []
    completed = [r for r in cap.records if r[1] == COMPLETED_MSG]
    assert len(completed) == 1
    _lvl, _msg, extra = completed[0]
    assert extra["was_cold"] is False
    assert extra["duration"] == DURATION


@pytest.mark.asyncio
async def test_cold_warmup_logs_was_cold_true_in_the_completion_extra():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_7.

    Second, value-side pin of the same shape group: on the cold entry path
    the completion record's was_cold extra must be exactly True.
    """
    with _LogCap(LOG_NAME, ("duration", "was_cold")) as cap:
        facts = await run_warmup(clock_ladder=COLD_LADDER)

    assert facts["ret"] is True
    completed = [r for r in cap.records if r[1] == COMPLETED_MSG]
    assert len(completed) == 1
    _lvl, _msg, extra = completed[0]
    assert extra["was_cold"] is True


# ---------------------------------------------------------------------------
# log records
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_warmup_logs_the_exact_startup_info_message():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_18,
    ...__mutmut_19, ...__mutmut_20, ...__mutmut_21.

    Line 1494 emits INFO "Starting Nemotron model warmup..." as the first
    record of an enabled run, before the probe. The NULLed / XX-wrapped /
    lower-cased / upper-cased variants each break message equality.
    """
    with _LogCap(LOG_NAME, ("duration", "was_cold")) as cap:
        await run_warmup(clock_ladder=COLD_LADDER)

    assert cap.records[0] == (logging.INFO, START_MSG, {"duration": _MISSING, "was_cold": _MISSING})


@pytest.mark.asyncio
async def test_warmup_completion_log_carries_message_plus_duration_was_cold_extra():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_43,
    ...__mutmut_44, ...__mutmut_46, ...__mutmut_47, ...__mutmut_48,
    ...__mutmut_49, ...__mutmut_50.

    Lines 1507-1510 emit INFO f"Nemotron warmup completed in {duration:.2f}s"
    with extra={"duration": duration, "was_cold": was_cold}. Pinned: the
    rendered message (kills __mutmut_43's None msg), and the presence AND
    value of both extra attributes on the record — extra=None (__mutmut_44),
    the dropped kwarg (__mutmut_46) and the four renamed keys
    (__mutmut_47 "XXdurationXX", __mutmut_48 "DURATION", __mutmut_49
    "XXwas_coldXX", __mutmut_50 "WAS_COLD") all leave record.duration or
    record.was_cold missing.
    """
    with _LogCap(LOG_NAME, ("duration", "was_cold")) as cap:
        facts = await run_warmup(clock_ladder=COLD_LADDER)

    assert facts["ret"] is True
    messages = [msg for _lvl, msg, _x in cap.records]
    assert START_MSG in messages
    completed = [r for r in cap.records if r[1] == COMPLETED_MSG]
    assert len(completed) == 1
    level, msg, extra = completed[0]
    assert level == logging.INFO
    assert msg == COMPLETED_MSG
    assert extra == {"duration": DURATION, "was_cold": True}


@pytest.mark.asyncio
async def test_warmup_failure_logs_the_exact_warning_message_and_no_completion():
    """Kills backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁwarmup__mutmut_60,
    ...__mutmut_61, ...__mutmut_62, ...__mutmut_63.

    Line 1514 is WARNING "Nemotron warmup failed - model not ready" and it is
    the run's last record (no completion INFO on this path).
    """
    with _LogCap(LOG_NAME, ("duration", "was_cold")) as cap:
        facts = await run_warmup(probe_result=False, clock_ladder=FAIL_LADDER)

    assert facts["ret"] is False
    assert [(lvl, msg) for lvl, msg, _x in cap.records] == [
        (logging.INFO, START_MSG),
        (logging.WARNING, FAILED_MSG),
    ]
