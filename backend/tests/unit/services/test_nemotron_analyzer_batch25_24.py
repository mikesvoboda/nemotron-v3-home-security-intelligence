"""Batch-25 kill battery — chunk "tail:NemotronAnalyzer._log_success" (97 keys).

Six shipped functions adjudicated (all refs backend/services/nemotron_analyzer.py
on branch mutation-testing-s3, verified against the working tree). Verified by an
out-of-repo RED-CHECK (in-memory mutant binding, harness
/tmp/wp-batch25/probes/c24/redharness.py + rtplugin.py, results
red_results.json): 94/97 keys FAIL their named test, the 3 equivalent keys PASS
the whole file — exactly the predicted split.

  _log_shadow_result          1066-1110   38 keys  ->  37 killable / 1 equivalent
  _get_enrichment_result      2051-2122   21 keys  ->  19 killable / 2 equivalent
  _build_enrichment_snapshot  1716-1782   17 keys  ->  17 killable
  _set_idempotency            1556-1580   14 keys  ->  14 killable
  analyze_batch_streaming     4873-4901    6 keys  ->   6 killable
  get_version_for_analysis     910-924      1 key   ->   1 killable
                                     97 total ->  94 killable /  3 equivalent

HOW THE SEAMS WERE CHOSEN (probe-run against shipped, /tmp/wp-batch25/probes/c24/):

1. LOG PAYLOADS. The shipped module logger (nemotron_analyzer.py:201
   `logger = get_logger(__name__)`, a stdlib logging.Logger carrying
   backend.core.logging.ContextFilter) resolves to effective level WARNING, so
   the shipped `logger.info(...)` in _log_shadow_result (1097) and the
   `logger.debug(...)` in _set_idempotency (1574) are level-filtered in the
   default config (probe7: isEnabledFor(INFO) is False). Every payload mutant in
   this chunk is therefore pinned through pytest's caplog with
   `caplog.at_level(logging.DEBUG, logger="backend.services.nemotron_analyzer")`
   — the canonical in-test level force (no production behavior changes), which
   is what makes the INFO/DEBUG-site mutants killable at all. The WARNING sites
   (_get_enrichment_result 2113, _set_idempotency 1577) are already enabled and
   need no forcing. A strict "attribute must exist" walk is used for the extra=
   keys so a rename/None/removal fails, and shipped VALUES are pinned by
   equality. NOTE: `msg=None` mutants do NOT raise (probe6:
   logging.Logger.makeRecord accepts msg None; `getMessage()` returns "None"),
   so they are killed by value assertion, never by a raises= expectation.

2. METRIC LABEL. _log_shadow_result 1095 `record_shadow_comparison("nemotron")`
   is observable only through PROMPT_SHADOW_COMPARISONS_TOTAL.labels(model=...)
   (backend/core/metrics.py:3884-3891), and the argument passes through
   sanitize_metric_label (backend/core/sanitization.py:359), which LOWERCASES
   (line ~386 `value = str(value).lower().strip()`) and maps falsy to "unknown".
   Probe8 measured: "nemotron"->"nemotron", "NEMOTRON"->"nemotron" (IDENTICAL:
   key 22 is equivalent), "XXnemotronXX"->"xxnemotronxx" (killable),
   None->"unknown" (killable).

3. CALL SHAPES / RETURNS. _get_enrichment_result, analyze_batch_streaming and
   get_version_for_analysis mutate arguments of a call the test can spy
   (AsyncMock on the instance / autospec patch of the module function / autospec
   of the config instance method — probe6 confirmed autospec on an instance
   method records call('cam-A'), i.e. self is NOT recorded).

EQUIVALENCE (3 keys, proofs in verdicts_24.json): key 22 (label sanitizer
lowercases), keys 27/30 of _get_enrichment_result (EnrichmentTrackingResult is
@dataclass(slots=True) with successful_models field(default_factory=list) at
backend/services/enrichment_pipeline.py:538 and data: ... | None = None at :541,
so deleting the literal leaves the constructed object field-wise identical —
probe1: `==` and asdict equality both True).

NO KEY IN THIS CHUNK IS killed_by_draft: all 97 keys are survivors of the banked
corpus, and the batch-25 draft battery
(/tmp/wp-batch25/test_nemotron_analyzer_batch25.py) drives only
_parse_llm_response / _validate_risk_data / _extract_json_objects.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_24.py -p no:cacheprovider -o addopts= -q
RED-CHECK (on a lane): apply each key individually, run the named test, expect failure.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# The part file lives outside the repo tree, so backend/tests/conftest.py does NOT
# apply. Mirror the minimum env vars the repo conftests set BEFORE any backend
# import (values copied verbatim from backend/tests/conftest.py:107/114/363/385
# and backend/tests/unit/conftest.py's UNIT_TEST_API_KEY).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")
os.environ.setdefault("API_KEY_ENABLED", "true")  # pragma: allowlist secret
os.environ.setdefault("API_KEYS", '["test-unit-api-key-12345"]')  # pragma: allowlist secret

import backend.core.metrics as METRICS
from backend.config.prompt_experiment import (
    PromptExperimentConfig,
    PromptVersion,
)
from backend.core.sanitization import sanitize_metric_label
from backend.services.enrichment_pipeline import (
    EnrichmentStatus,
    EnrichmentTrackingResult,
)
from backend.services.nemotron_analyzer import NemotronAnalyzer

LOGGER = "backend.services.nemotron_analyzer"

SHADOW_ATTRS = (
    "camera_id",
    "v1_score",
    "v2_score",
    "score_diff",
    "v1_latency_ms",
    "v2_latency_ms",
    "latency_diff_ms",
)
ENRICH_FAIL_ATTRS = ("batch_id", "error")
IDEM_FAIL_ATTRS = ("batch_id", "event_id", "error")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _analyzer() -> NemotronAnalyzer:
    """__new__ skips the heavy __init__ (settings/model/client wiring).

    The shipped functions under test read only arguments plus
    self._use_enrichment_pipeline / self._run_enrichment_pipeline / self._redis /
    self._experiment_config, all set explicitly by the tests.
    """
    a = NemotronAnalyzer.__new__(NemotronAnalyzer)
    # P0.3 gate attrs (#6678 added them to __init__; __new__ skips it).
    # Values copied from the repo test_nemotron_analyzer.py mock_settings
    # fixture: constrained decoding OFF => legacy path byte-identical.
    a._constrained_enabled = False
    a._constrained_fail_closed = True
    a._constrained_probe_enabled = True
    a._constrained_required_build = None
    a._constrained_enforced = None
    a._fail_closed_active = False
    a._verification_engine = "llama.cpp"
    a._verification_model_id = "Nemotron-3-Nano-30B-A3B-Q4_K_M"
    a._last_call_duration_ms = None
    return a


class _Boom(Exception):
    """str(exc) == the message ALONE (unlike RuntimeError, which prefixes the
    class name), so a `str(e)` -> `str(None)` mutant is visible as "None"."""


@pytest.fixture
def logpipe(caplog):
    """caplog records for the shipped module logger only, level forced to DEBUG.

    The level force is required because the shipped effective level is WARNING
    (probe7): _log_shadow_result's logger.info (1097) and _set_idempotency's
    logger.debug (1574) build NO record otherwise. Production is untouched.
    """
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        yield caplog


def _records(caplog, levelno: int | None = None) -> list[logging.LogRecord]:
    out = [r for r in caplog.records if r.name == LOGGER]
    if levelno is not None:
        out = [r for r in out if r.levelno == levelno]
    return out


def _one(caplog, levelno: int | None = None) -> logging.LogRecord:
    recs = _records(caplog, levelno)
    assert len(recs) == 1, f"expected exactly one record on {LOGGER}, got {recs}"
    return recs[0]


def _attrs(record, names):
    """Strict presence walk: every shipped extra= key must be on the record.

    Fails for extra=None, for a removed extra= argument, and for any
    XX-prefixed/uppercased rename (the mutant then carries a DIFFERENT name and
    the shipped one is absent).
    """
    missing = [n for n in names if not hasattr(record, n)]
    assert not missing, f"record lost shipped extra keys: {missing}"


# ===========================================================================
# _log_shadow_result (1066-1110)
# ===========================================================================


class TestLogShadowResultScoreLookup:
    """v1_result/v2_result .get("risk_score", 0) (1090-1091)."""

    def test_populated_scores_are_read_verbatim(self, logpipe):
        """kills _log_shadow_result keys 2, 6, 7 (v1 lookup site) and
        10, 14, 15 (v2 lookup site).

        shipped 1090-1091:
            v1_score = v1_result.get("risk_score", 0)
            v2_score = v2_result.get("risk_score", 0)
        key 2  -> get(None, 0);            key 6 -> get("XXrisk_scoreXX", 0)
        key 7  -> get("RISK_SCORE", 0)     -> v1_score falls back to 0
        key 10 -> get(None, 0);            key 14 -> get("XXrisk_scoreXX", 0)
        key 15 -> get("RISK_SCORE", 0)     -> v2_score falls back to 0
        Shipped values (probe5): v1_score 60, v2_score 45, score_diff 15.
        """
        a = _analyzer()
        with patch.object(METRICS, "PROMPT_SHADOW_COMPARISONS_TOTAL", autospec=True):
            asyncio.run(
                a._log_shadow_result(
                    camera_id="cam-1",
                    v1_result={"risk_score": 60},
                    v2_result={"risk_score": 45},
                    v1_latency_ms=150.0,
                    v2_latency_ms=180.0,
                )
            )
        rec = _one(logpipe, logging.INFO)
        _attrs(rec, SHADOW_ATTRS)
        assert rec.v1_score == 60
        assert rec.v2_score == 45

    def test_missing_key_falls_back_to_zero_default(self, logpipe):
        """kills _log_shadow_result keys 3, 5, 8 (v1 default) and
        11, 13, 16 (v2 default).

        P0.3 DRIFT RE-PIN (#6678): shipped 1380-1384 now reads .get without
        the 0 default and applies the honest-incomparable rule; with BOTH
        dicts empty the shipped record carries v1_score None / v2_score None
        / score_diff -1.0 (measured).
        key 3 / 11 -> default None  -> score_diff = abs(None - 0) raises TypeError
                                       inside the shipped body (call explodes)
        key 5 / 13 -> `get("risk_score", )` parses as `get("risk_score")`, i.e.
                      default None -> same TypeError explosion
        key 8 / 16 -> default 1     -> v1_score/v2_score 1 and score_diff 1
        """
        a = _analyzer()
        with patch.object(METRICS, "PROMPT_SHADOW_COMPARISONS_TOTAL", autospec=True):
            asyncio.run(a._log_shadow_result(camera_id="c", v1_result={}, v2_result={}))
        rec = _one(logpipe, logging.INFO)
        _attrs(rec, SHADOW_ATTRS)
        assert rec.v1_score is None
        assert rec.v2_score is None
        assert rec.score_diff == -1.0

    def test_score_diff_is_absolute_difference(self, logpipe):
        """kills _log_shadow_result keys 17, 19 (line 1092).

        shipped 1092: score_diff = abs(v1_score - v2_score)
        key 17 -> score_diff = None: the "score_diff" extra key disappears.
        key 19 -> abs(v1_score + v2_score): 15 -> 105.
        A reversed polarity (v1 < v2) keeps the shipped positive sign.
        """
        a = _analyzer()
        with patch.object(METRICS, "PROMPT_SHADOW_COMPARISONS_TOTAL", autospec=True):
            asyncio.run(
                a._log_shadow_result(
                    camera_id="c", v1_result={"risk_score": 60}, v2_result={"risk_score": 45}
                )
            )
            asyncio.run(
                a._log_shadow_result(
                    camera_id="c", v1_result={"risk_score": 45}, v2_result={"risk_score": 60}
                )
            )
        first, second = _records(logpipe, logging.INFO)
        _attrs(first, SHADOW_ATTRS)
        assert first.score_diff == 15
        assert second.score_diff == 15


class TestLogShadowResultMetric:
    """record_shadow_comparison("nemotron") (1095)."""

    def test_metric_label_is_nemotron(self, logpipe):
        """kills _log_shadow_result keys 20, 21 (line 1095).

        shipped 1095: record_shadow_comparison("nemotron")
        The only observable is PROMPT_SHADOW_COMPARISONS_TOTAL.labels(model=safe)
        where safe = sanitize_metric_label(model, max_length=32).
        key 20 -> None  -> sanitize returns "unknown"
        key 21 -> "XXnemotronXX" -> sanitize returns "xxnemotronxx"
        (key 22 "NEMOTRON" sanitizes back to "nemotron" — EQUIVALENT, pinned by
        test_label_sanitizer_lowercases_nemotron.)
        """
        a = _analyzer()
        with patch.object(METRICS, "PROMPT_SHADOW_COMPARISONS_TOTAL", autospec=True) as counter:
            asyncio.run(
                a._log_shadow_result(
                    camera_id="c", v1_result={"risk_score": 60}, v2_result={"risk_score": 45}
                )
            )
        counter.labels.assert_called_once_with(model="nemotron")

    def test_label_sanitizer_lowercases_nemotron(self):
        """EQUIVALENCE PIN for _log_shadow_result key 22 (no kill possible).

        backend/core/sanitization.py:386 lowercases the value before it reaches
        labels(), so record_shadow_comparison("NEMOTRON") produces the byte-
        identical label write "nemotron" (probe8). This assertion is the proof:
        if the sanitizer ever stops case-folding, key 22 becomes killable and
        this pin fails.
        """
        assert sanitize_metric_label("NEMOTRON", max_length=32) == "nemotron"
        assert sanitize_metric_label("nemotron", max_length=32) == "nemotron"
        assert sanitize_metric_label(None, max_length=32) == "unknown"


class TestLogShadowResultInfoPayload:
    """logger.info("Shadow comparison result", extra={...}) (1097-1110)."""

    def _log(self, **kwargs):
        a = _analyzer()
        with patch.object(METRICS, "PROMPT_SHADOW_COMPARISONS_TOTAL", autospec=True):
            asyncio.run(a._log_shadow_result(**kwargs))

    def test_message_identity(self, logpipe):
        """kills _log_shadow_result keys 23, 27, 28, 29 (line 1098).

        shipped 1098: "Shadow comparison result"
        key 23 -> None (makeRecord accepts msg=None; getMessage() -> "None")
        key 27 -> "XXShadow comparison resultXX"
        key 28 -> "shadow comparison result"   (lowercase)
        key 29 -> "SHADOW COMPARISON RESULT"   (uppercase)
        """
        self._log(
            camera_id="cam-9",
            v1_result={"risk_score": 60},
            v2_result={"risk_score": 45},
            v1_latency_ms=150.0,
            v2_latency_ms=180.0,
        )
        rec = _one(logpipe, logging.INFO)
        assert rec.getMessage() == "Shadow comparison result"

    def test_record_level_is_info(self, logpipe):
        """kills _log_shadow_result keys 23, 27, 28, 29 a second way, and pins
        that the shipped call is logger.info (not debug/warning): the record
        levelno must be INFO. (A msg mutation still shows up in test_message_identity.)"""
        self._log(camera_id="c", v1_result={}, v2_result={})
        rec = _one(logpipe)
        assert rec.levelno == logging.INFO

    def test_extra_carries_camera_id(self, logpipe):
        """kills _log_shadow_result keys 30, 31 (line 1100)."""
        self._log(camera_id="cam-42", v1_result={"risk_score": 1}, v2_result={"risk_score": 1})
        rec = _one(logpipe, logging.INFO)
        assert rec.camera_id == "cam-42"

    def test_extra_carries_v1_score(self, logpipe):
        """kills _log_shadow_result keys 32, 33 (line 1101)."""
        self._log(camera_id="c", v1_result={"risk_score": 61}, v2_result={"risk_score": 45})
        rec = _one(logpipe, logging.INFO)
        assert rec.v1_score == 61

    def test_extra_carries_v2_score(self, logpipe):
        """kills _log_shadow_result keys 34, 35 (line 1102)."""
        self._log(camera_id="c", v1_result={"risk_score": 60}, v2_result={"risk_score": 44})
        rec = _one(logpipe, logging.INFO)
        assert rec.v2_score == 44

    def test_extra_carries_score_diff(self, logpipe):
        """kills _log_shadow_result keys 36, 37 (line 1103)."""
        self._log(camera_id="c", v1_result={"risk_score": 80}, v2_result={"risk_score": 20})
        rec = _one(logpipe, logging.INFO)
        assert rec.score_diff == 60

    def test_extra_carries_v1_latency_ms(self, logpipe):
        """kills _log_shadow_result keys 38, 39 (line 1104)."""
        self._log(
            camera_id="c",
            v1_result={"risk_score": 1},
            v2_result={"risk_score": 1},
            v1_latency_ms=123.5,
            v2_latency_ms=180.0,
        )
        rec = _one(logpipe, logging.INFO)
        assert rec.v1_latency_ms == 123.5

    def test_extra_carries_v2_latency_ms(self, logpipe):
        """kills _log_shadow_result keys 40, 41 (line 1105)."""
        self._log(
            camera_id="c",
            v1_result={"risk_score": 1},
            v2_result={"risk_score": 1},
            v1_latency_ms=150.0,
            v2_latency_ms=271.25,
        )
        rec = _one(logpipe, logging.INFO)
        assert rec.v2_latency_ms == 271.25

    def test_extra_carries_latency_diff_key(self, logpipe):
        """kills _log_shadow_result keys 42, 43 (line 1106 key name)."""
        self._log(
            camera_id="c",
            v1_result={"risk_score": 1},
            v2_result={"risk_score": 1},
            v1_latency_ms=150.0,
            v2_latency_ms=180.0,
        )
        rec = _one(logpipe, logging.INFO)
        assert rec.latency_diff_ms == 30.0

    def test_latency_diff_is_subtraction(self, logpipe):
        """kills _log_shadow_result key 44 (line 1106 operand).

        shipped 1106: "latency_diff_ms": v2_latency_ms - v1_latency_ms
        key 44 -> v2 + v1: 30.0 -> 330.0 here; the second (reversed) call pins
        the shipped SIGN as well: 30.0 - 200.0 = -170.0.
        """
        self._log(
            camera_id="c",
            v1_result={"risk_score": 1},
            v2_result={"risk_score": 1},
            v1_latency_ms=150.0,
            v2_latency_ms=180.0,
        )
        self._log(
            camera_id="c",
            v1_result={"risk_score": 1},
            v2_result={"risk_score": 1},
            v1_latency_ms=200.0,
            v2_latency_ms=30.0,
        )
        first, second = _records(logpipe, logging.INFO)
        assert first.latency_diff_ms == 30.0
        assert second.latency_diff_ms == -170.0

    def test_default_latency_arguments(self, logpipe):
        """pins the shipped default-latency arithmetic (1071-1072 default 0.0)
        that keys 24/26 and the extra= mutants are measured against; kills
        _log_shadow_result keys 24 (extra=None) and 26 (extra argument removed)
        together with test_all_extra_keys_are_present.
        """
        self._log(camera_id="cam-def", v1_result={"risk_score": 7}, v2_result={})
        rec = _one(logpipe, logging.INFO)
        _attrs(rec, SHADOW_ATTRS)
        assert rec.v1_latency_ms == 0.0
        assert rec.v2_latency_ms == 0.0
        assert rec.latency_diff_ms == 0.0

    def test_all_extra_keys_are_present(self, logpipe):
        """kills _log_shadow_result keys 24, 26, 30, 31, 32, 33, 34, 35, 36, 37,
        38, 39, 40, 41, 42, 43 by presence walk over the shipped extra= dict.

        key 24 (extra=None) and key 26 (`extra={...},` -> `)`, argument removed)
        drop ALL seven attributes at once; each rename pair drops one under its
        shipped name. logging.Logger.makeRecord copies extra= onto the record
        verbatim, so the walk is exact.
        """
        self._log(
            camera_id="walk",
            v1_result={"risk_score": 60},
            v2_result={"risk_score": 45},
            v1_latency_ms=150.0,
            v2_latency_ms=180.0,
        )
        rec = _one(logpipe, logging.INFO)
        _attrs(rec, SHADOW_ATTRS)
        assert (rec.camera_id, rec.v1_score, rec.v2_score, rec.score_diff) == (
            "walk",
            60,
            45,
            15,
        )
        assert (rec.v1_latency_ms, rec.v2_latency_ms, rec.latency_diff_ms) == (
            150.0,
            180.0,
            30.0,
        )


# ===========================================================================
# _get_enrichment_result (2051-2122)
# ===========================================================================


class TestGetEnrichmentResultDelegation:
    """`await self._run_enrichment_pipeline(detections, camera_id=camera_id)` (2077)."""

    def _analyzer_with_pipeline(self, result=None):
        a = _analyzer()
        a._use_enrichment_pipeline = True
        a._run_enrichment_pipeline = AsyncMock(return_value=result)
        return a

    def test_pipeline_receives_detections_and_camera(self, logpipe):
        """kills get_enrichment_result keys 3, 4, 6 (line 2077).

        shipped 2077: tracking_result = await self._run_enrichment_pipeline(
                          detections, camera_id=camera_id)
        key 3 -> detections=None; key 4 -> camera_id=None;
        key 6 -> `self._run_enrichment_pipeline(detections, )` (camera_id dropped)
        Shipped return with a falsy pipeline result is None (2099), asserted too.
        """
        detections = [{"id": 1}, {"id": 2}]
        a = self._analyzer_with_pipeline(None)
        out = asyncio.run(
            a._get_enrichment_result(batch_id="B1", detections=detections, camera_id="CAM-1")
        )
        assert out is None
        a._run_enrichment_pipeline.assert_awaited_once_with(detections, camera_id="CAM-1")
        assert a._run_enrichment_pipeline.await_args.args[0] is detections

    def test_pipeline_camera_default_is_none(self, logpipe):
        """kills get_enrichment_result key 4 in the default-argument case and
        pins shipped default `camera_id: str | None = None` (2054).
        """
        a = self._analyzer_with_pipeline(None)
        asyncio.run(a._get_enrichment_result(batch_id="B2", detections=[]))
        a._run_enrichment_pipeline.assert_awaited_once_with([], camera_id=None)

    def test_pipeline_signature_is_positional(self, logpipe):
        """kills get_enrichment_result key 5 (line 2077 operand removal).

        key 5 -> `self._run_enrichment_pipeline(camera_id=camera_id)`, i.e. the
        positional `detections` argument is dropped. An AsyncMock would accept
        that silently, so the stand-in here carries the REAL shipped signature
        `_run_enrichment_pipeline(self, detections, camera_id=None)`
        (nemotron_analyzer.py:3664-3665) with detections positional-required:
        under key 5 the call raises TypeError INSIDE the shipped try, the shipped
        `except Exception` (2112) then logs the WARNING and returns a FAILED
        tracking result — so the shipped pair (returns None, logs nothing) fails.
        """
        calls: list[tuple] = []

        async def pipeline(detections, camera_id=None):  # shipped signature
            calls.append((detections, camera_id))

        a = _analyzer()
        a._use_enrichment_pipeline = True
        a._run_enrichment_pipeline = pipeline
        detections = [{"id": 9}]
        out = asyncio.run(
            a._get_enrichment_result(batch_id="B3", detections=detections, camera_id="CAM-9")
        )
        assert out is None
        assert _records(logpipe) == []
        assert calls == [(detections, "CAM-9")]


class TestGetEnrichmentResultExceptLog:
    """the shipped `except Exception` WARNING + FAILED result (2112-2122)."""

    def _fail(self, a_factory=None, message="boom"):
        a = _analyzer()
        a._use_enrichment_pipeline = True

        async def boom(*args, **kwargs):
            raise _Boom(message)

        a._run_enrichment_pipeline = boom
        tracking = asyncio.run(
            a._get_enrichment_result(batch_id="B7", detections=[{"id": 7}], camera_id="CAM-7")
        )
        return tracking

    def test_warning_message_identity(self, logpipe):
        """kills get_enrichment_result keys 7, 13, 14, 15 (line 2114).

        shipped 2114: "Enrichment pipeline failed, continuing without enrichment"
        key 7 -> None; key 13 -> XX-wrapped; key 14 -> lowercased;
        key 15 -> uppercased.
        """
        self._fail(message="boom")
        rec = _one(logpipe, logging.WARNING)
        assert rec.getMessage() == ("Enrichment pipeline failed, continuing without enrichment")

    def test_warning_extra_keys_and_values(self, logpipe):
        """kills get_enrichment_result keys 8, 11, 16, 17, 18, 19, 20 (line 2115).

        shipped 2115: extra={"batch_id": batch_id, "error": str(e)}
        key 8  -> extra=None;  key 11 -> extra argument removed
        key 16/17 -> "batch_id" renamed;  key 18/19 -> "error" renamed
        key 20 -> str(None): error value becomes "None" instead of "boom"
        """
        self._fail(message="boom")
        rec = _one(logpipe, logging.WARNING)
        _attrs(rec, ENRICH_FAIL_ATTRS)
        assert rec.batch_id == "B7"
        assert rec.error == "boom"

    def test_warning_exc_info_is_true(self, logpipe):
        """kills get_enrichment_result keys 9, 12, 21 (line 2116).

        shipped 2116: exc_info=True  -> record.exc_info is the (type, value, tb)
        triple. key 9 -> exc_info=None; key 21 -> exc_info=False; key 12 ->
        argument removed (default False) — all three leave record.exc_info falsy.
        """
        self._fail(message="boom")
        rec = _one(logpipe, logging.WARNING)
        assert rec.exc_info is not None
        assert rec.exc_info[0] is _Boom
        assert isinstance(rec.exc_info[1], _Boom)

    def test_failed_tracking_result_fields(self, logpipe):
        """kills get_enrichment_result key 20 at the errors= literal too, and
        pins the shipped return (2118-2122) that keys 23/27/30 mutate.

        shipped 2118-2122:
            return EnrichmentTrackingResult(
                status=EnrichmentStatus.FAILED,
                successful_models=[],
                failed_models=["all"],
                errors={"all": str(e)},
                data=None,
            )
        key 23 -> successful_models=None (observable on the RETURNED object:
                  shipped is the empty list, and the errors/status/failed fields
                  stay identical) — killed by the explicit field assertions.
        """
        tracking = self._fail(message="kaboom")
        assert tracking.status is EnrichmentStatus.FAILED
        assert tracking.successful_models == []
        assert tracking.successful_models is not None
        assert tracking.failed_models == ["all"]
        assert tracking.errors == {"all": "kaboom"}
        assert tracking.data is None


class TestGetEnrichmentResultDefaultsAreLiteral:
    """EQUIVALENCE PINS for get_enrichment_result keys 27 and 30 (no kill)."""

    def test_dataclass_defaults_make_27_and_30_noops(self):
        """proof: EnrichmentTrackingResult is @dataclass(slots=True) with
        successful_models: list[str] = field(default_factory=list)
        (backend/services/enrichment_pipeline.py:538) and
        data: EnrichmentResult | None = None (:541).

        key 27 deletes `successful_models=[],` and key 30 deletes `data=None,`,
        so both still construct a field-wise IDENTICAL object -> equivalent.
        These three assertions are the pin: they fail the moment a default
        changes, which would turn the two keys killable.
        """
        shipped = EnrichmentTrackingResult(
            status=EnrichmentStatus.FAILED,
            successful_models=[],
            failed_models=["all"],
            errors={"all": "x"},
            data=None,
        )
        without_data = EnrichmentTrackingResult(
            status=EnrichmentStatus.FAILED,
            successful_models=[],
            failed_models=["all"],
            errors={"all": "x"},
        )
        without_successful = EnrichmentTrackingResult(
            status=EnrichmentStatus.FAILED,
            failed_models=["all"],
            errors={"all": "x"},
            data=None,
        )
        assert shipped == without_data == without_successful
        assert dataclasses.asdict(shipped) == dataclasses.asdict(without_data)
        assert shipped.successful_models == [] and shipped.data is None


# ===========================================================================
# _build_enrichment_snapshot (1716-1782)
# ===========================================================================


def _plate(text: str):
    m = MagicMock()
    m.model_dump.return_value = {"text": text}
    return m


def _face(face_id: str):
    m = MagicMock()
    m.model_dump.return_value = {"face_id": face_id}
    return m


def _enrichment(plates=..., faces=..., weather=None, poses=None, actions=None):
    e = MagicMock()
    e.license_plates = [] if plates is ... else plates
    e.faces = [] if faces is ... else faces
    e.weather_classification = weather
    e.pose_results = {} if poses is None else poses
    e.action_results = actions
    return e


def _context(day="tuesday", hour=3, deviation=0.25, zones=("z1",), cross=("c1", "c2")):
    c = MagicMock()
    c.baselines.day_of_week = day
    c.baselines.hour_of_day = hour
    c.baselines.deviation_score = deviation
    c.zones = list(zones)
    c.cross_camera = list(cross)
    return c


class TestBuildEnrichmentSnapshotFlags:
    """the header dict (1736-1740)."""

    def test_availability_flags_both_present(self):
        """kills build_enrichment_snapshot keys 6, 9, 21.

        shipped 1738-1739:
            "enrichment_available": enrichment_result is not None,
            "context_available": enriched_context is not None,
        key 6 -> enrichment_result is None (inverted); key 9 -> enriched_context
        is None (inverted); key 21 -> the `if enriched_context is not None:`
        branch guard at 1763 inverted, so a non-None context contributes NOTHING
        (baselines / zones_count / cross_camera_count disappear).
        """
        a = _analyzer()
        snap = a._build_enrichment_snapshot([1, 2], _enrichment(), _context())
        assert snap["enrichment_available"] is True
        assert snap["context_available"] is True
        assert snap["detection_ids"] == [1, 2]

    def test_availability_flags_both_absent(self):
        """kills build_enrichment_snapshot keys 4, 5, 7, 8 (renames) and 21
        (the inverted 1763 guard now dereferences the None context ->
        AttributeError on enriched_context.baselines).

        shipped 1736-1740 with both optionals None yields EXACTLY three keys.
        """
        a = _analyzer()
        snap = a._build_enrichment_snapshot([7], None, None)
        assert set(snap) == {"detection_ids", "enrichment_available", "context_available"}
        assert snap["enrichment_available"] is False
        assert snap["context_available"] is False


class TestBuildEnrichmentSnapshotLists:
    """license_plates / faces capture (1744-1749)."""

    def test_license_plates_are_serialized_in_order(self):
        """kills build_enrichment_snapshot keys 11, 12, 13, 14, 15 (1744-1746).

        shipped 1744-1746:
            snapshot["license_plates"] = [
                self._to_serializable(p) for p in (enrichment_result.license_plates or [])
            ]
        key 11 -> value None; keys 12/13 -> key renamed;
        key 14 -> self._to_serializable(None) -> every entry becomes None
                  (_to_serializable returns None for None, 1705-1706);
        key 15 -> `(enrichment_result.license_plates and [])` -> [] for a
                  non-empty list.
        """
        a = _analyzer()
        snap = a._build_enrichment_snapshot(
            [1], _enrichment(plates=[_plate("ABC123"), _plate("XYZ789")]), None
        )
        assert snap["license_plates"] == [{"text": "ABC123"}, {"text": "XYZ789"}]

    def test_license_plates_none_falls_back_to_empty_list(self):
        """kills build_enrichment_snapshot key 15's `or []` half and keys 12/13
        again: with license_plates=None the shipped value is [].
        """
        a = _analyzer()
        snap = a._build_enrichment_snapshot([2], _enrichment(plates=None), None)
        assert snap["license_plates"] == []

    def test_faces_are_serialized_in_order(self):
        """kills build_enrichment_snapshot keys 16, 17, 18, 19, 20 (1749).

        shipped 1749:
            snapshot["faces"] = [self._to_serializable(f) for f in (enrichment_result.faces or [])]
        key 16 -> value None; keys 17/18 -> key renamed; key 19 -> entries None;
        key 20 -> `and []` -> [].
        """
        a = _analyzer()
        snap = a._build_enrichment_snapshot(
            [1], _enrichment(faces=[_face("f-1"), _face("f-2")]), None
        )
        assert snap["faces"] == [{"face_id": "f-1"}, {"face_id": "f-2"}]

    def test_faces_none_falls_back_to_empty_list(self):
        """kills build_enrichment_snapshot key 20's `or []` half and keys 17/18."""
        a = _analyzer()
        snap = a._build_enrichment_snapshot([2], _enrichment(faces=None), None)
        assert snap["faces"] == []

    def test_snapshot_key_set_is_exact(self):
        """kills build_enrichment_snapshot keys 11, 12, 13, 16, 17, 18 by exact
        key-set equality of the shipped snapshot (renames and the two `= None`
        value mutants change either the names or the types).
        """
        a = _analyzer()
        snap = a._build_enrichment_snapshot(
            [5], _enrichment(plates=[_plate("P")], faces=[_face("f")]), _context()
        )
        assert set(snap) == {
            "detection_ids",
            "enrichment_available",
            "context_available",
            "license_plates",
            "faces",
            "baselines",
            "zones_count",
            "cross_camera_count",
        }
        assert snap["license_plates"] == [{"text": "P"}]
        assert snap["faces"] == [{"face_id": "f"}]


class TestBuildEnrichmentSnapshotContextBranch:
    """the enriched_context branch (1763-1780)."""

    def test_context_data_is_captured(self):
        """kills build_enrichment_snapshot key 21 (line 1763 guard inversion).

        shipped 1763: if enriched_context is not None:  then baselines (three
        named fields), zones_count = len(zones), cross_camera_count =
        len(cross_camera). Values pinned from the shipped branch, not invented.
        """
        a = _analyzer()
        ctx = _context(day="sunday", hour=23, deviation=1.75, zones=("a", "b", "c"), cross=("x",))
        snap = a._build_enrichment_snapshot([3], None, ctx)
        assert snap["baselines"] == {
            "day_of_week": "sunday",
            "hour_of_day": 23,
            "deviation_score": 1.75,
        }
        assert snap["zones_count"] == 3
        assert snap["cross_camera_count"] == 1


# ===========================================================================
# _set_idempotency (1556-1580)
# ===========================================================================


class TestSetIdempotencySuccess:
    """the redis happy path + logger.debug (1570-1574)."""

    def _analyzer_with_redis(self):
        a = _analyzer()
        a._redis = MagicMock()
        a._redis.set = AsyncMock()
        return a

    def test_redis_set_shape(self, logpipe):
        """pins the shipped redis write (1572-1573) that the debug message
        reports; kills set_idempotency keys 11 and 15 as a side effect of the
        `key` f-string they format (the shipped key string is in the message).
        """
        a = self._analyzer_with_redis()
        asyncio.run(a._set_idempotency("batch_789", 100))
        a._redis.set.assert_awaited_once_with("batch_event:batch_789", "100", expire=3600)

    def test_debug_message_identity(self, logpipe):
        """kills set_idempotency key 11 (line 1574).

        shipped 1574: logger.debug(f"Idempotency key set: {key} -> {event_id}")
        key 11 -> logger.debug(None) -> record.getMessage() == "None".
        Requires the logpipe level force (DEBUG is filtered in production).
        """
        a = self._analyzer_with_redis()
        asyncio.run(a._set_idempotency("batch_789", 100))
        asyncio.run(a._set_idempotency("b2", 42))
        recs = _records(logpipe, logging.DEBUG)
        assert [r.getMessage() for r in recs] == [
            "Idempotency key set: batch_event:batch_789 -> 100",
            "Idempotency key set: batch_event:b2 -> 42",
        ]

    def test_no_redis_returns_immediately(self, logpipe):
        """pins the shipped early return (1568-1569); set_idempotency keys
        11/15 are unreachable in this configuration, which is why the kill above
        must inject a redis client."""
        a = _analyzer()
        a._redis = None
        assert asyncio.run(a._set_idempotency("b", 1)) is None
        assert _records(logpipe) == []


class TestSetIdempotencyFailure:
    """the shipped `except Exception` WARNING (1576-1580)."""

    def _fail(self, message="redis down", batch_id="batch_err", event_id=200):
        a = _analyzer()
        a._redis = MagicMock()
        a._redis.set = AsyncMock(side_effect=_Boom(message))
        assert asyncio.run(a._set_idempotency(batch_id, event_id)) is None

    def test_warning_message_identity(self, logpipe):
        """kills set_idempotency keys 12, 16, 17, 18 (line 1578).

        shipped 1578: "Failed to set idempotency key for batch"
        key 12 -> None; key 16 -> XX-wrapped; key 17 -> lowercased;
        key 18 -> uppercased.
        """
        self._fail()
        rec = _one(logpipe, logging.WARNING)
        assert rec.getMessage() == "Failed to set idempotency key for batch"

    def test_warning_extra_batch_and_event(self, logpipe):
        """kills set_idempotency keys 13, 15, 19, 20, 21, 22 (line 1579).

        shipped 1579: extra={"batch_id": batch_id, "event_id": event_id,
                             "error": str(e)}
        key 13 -> extra=None; key 15 -> extra argument removed;
        keys 19/20 -> "batch_id" renamed; keys 21/22 -> "event_id" renamed.
        """
        self._fail(batch_id="batch_err", event_id=200)
        rec = _one(logpipe, logging.WARNING)
        _attrs(rec, IDEM_FAIL_ATTRS)
        assert rec.batch_id == "batch_err"
        assert rec.event_id == 200

    def test_warning_extra_error_string(self, logpipe):
        """kills set_idempotency keys 13, 15, 23, 24, 25 (line 1579 error entry).

        keys 23/24 rename "error"; key 25 -> str(None) so the value is "None"
        instead of the exception text ("connection refused").
        """
        self._fail(message="connection refused")
        rec = _one(logpipe, logging.WARNING)
        _attrs(rec, IDEM_FAIL_ATTRS)
        assert rec.error == "connection refused"

    def test_warning_has_no_exc_info_and_no_extra_keys(self, logpipe):
        """kills set_idempotency keys 13, 15, 19, 20, 21, 22, 23, 24, 25 by the
        exact (name, value) set of the shipped extra= payload, and pins that the
        shipped WARNING passes no exc_info (unlike _get_enrichment_result:2116).
        """
        self._fail(message="redis down")
        rec = _one(logpipe, logging.WARNING)
        _attrs(rec, IDEM_FAIL_ATTRS)
        assert not rec.exc_info
        payload = {name: getattr(rec, name) for name in IDEM_FAIL_ATTRS}
        assert payload == {"batch_id": "batch_err", "event_id": 200, "error": "redis down"}


# ===========================================================================
# analyze_batch_streaming (4873-4901)
# ===========================================================================


class TestAnalyzeBatchStreamingDelegation:
    """`streaming_analyze(analyzer=self, batch_id=..., camera_id=..., detection_ids=...)`."""

    def test_delegation_kwargs_are_forwarded_verbatim(self):
        """kills analyze_batch_streaming keys 1, 2, 3, 4, 7, 8 (4897-4900).

        shipped 4896-4900:
            async for update in streaming_analyze(
                analyzer=self,
                batch_id=batch_id,
                camera_id=camera_id,
                detection_ids=detection_ids,
            ):
        keys 1-4 replace one kwarg with None; key 7 removes the camera_id kwarg
        (the callee's default camera_id=None then applies); key 8 removes
        detection_ids. Patched at the module attribute the shipped `from ...
        import` re-resolves on every call (4891-4893), with autospec.
        """
        a = _analyzer()
        updates = [{"type": "progress", "pct": 10}, {"type": "complete", "event_id": 5}]
        seen: list[dict] = []

        async def fake(**kwargs):
            seen.append(kwargs)
            for u in updates:
                yield u

        async def drive():
            return [u async for u in a.analyze_batch_streaming("batch-s", "cam-s", [11, 22])]

        with patch(
            "backend.services.nemotron_streaming.analyze_batch_streaming",
            autospec=True,
            side_effect=fake,
        ):
            got = asyncio.run(drive())
        assert got == updates
        assert len(seen) == 1
        assert seen[0]["batch_id"] == "batch-s"
        assert seen[0]["camera_id"] == "cam-s"
        assert seen[0]["detection_ids"] == [11, 22]
        assert seen[0]["analyzer"] is a


# ===========================================================================
# get_version_for_analysis (910-924)
# ===========================================================================


class TestGetVersionForAnalysis:
    """`return config.get_version_for_camera(camera_id)` (924)."""

    def test_camera_id_is_forwarded_to_the_config(self):
        """kills get_version_for_analysis key 2 (line 924).

        key 2 -> config.get_version_for_camera(None). autospec on the instance
        method records the call WITHOUT self (probe6), and the shipped return is
        the config's value passed straight through.
        """
        a = _analyzer()
        config = PromptExperimentConfig(shadow_mode=False, treatment_percentage=1.0)
        a.set_experiment_config(config)
        with patch.object(config, "get_version_for_camera", autospec=True) as spy:
            spy.return_value = PromptVersion.V2_CALIBRATED
            out = a.get_version_for_analysis("cam-A")
        spy.assert_called_once_with("cam-A")
        assert out is PromptVersion.V2_CALIBRATED

    def test_shipped_ab_routing_end_to_end(self):
        """pins the shipped routing (923-924 + prompt_experiment.py:119-128)
        that key 2 would break: with 100% treatment a real camera id must land
        on V2_CALIBRATED, while `get_version_for_camera(None)` would hash None
        and route by hash(None) instead.
        """
        a = _analyzer()
        a.set_experiment_config(PromptExperimentConfig(shadow_mode=False, treatment_percentage=1.0))
        assert a.get_version_for_analysis("front_door") is PromptVersion.V2_CALIBRATED
        a.set_experiment_config(PromptExperimentConfig(shadow_mode=True))
        assert a.get_version_for_analysis("front_door") is PromptVersion.V1_ORIGINAL
