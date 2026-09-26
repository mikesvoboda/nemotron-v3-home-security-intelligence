"""Batch-25 chunk-19 kill battery: NemotronAnalyzer._validate_risk_data (53 keys).

Adjudication basis: shipped source
/agents/agent-veranda3/workspace/backend/services/nemotron_analyzer.py:4348-4417
plus the 53 shape groups in /tmp/wp-batch25/feed.json.  Every value asserted was
read off the SHIPPED function first (probes under /tmp/wp-batch25/probes/ad19/);
nothing here encodes an assumed contract.  Red-check: red19.py + red19_plugin.py
rebuild each of the 53 variants from the instrumented copy, monkeypatch them in
and run this file — the repo is never written.

SCOPE — NO DUPLICATION.  The draft battery
/tmp/wp-batch25/test_nemotron_analyzer_batch25.py::TestValidateRiskDataFallbacks
already kills 34 of the 53 (per-key red-check:
/tmp/wp-batch25/probes/ad19/attr_draft.json) — the string-score clamp line and
its guard/score-read twins (mutmut_21/22/24 and 28-39) and the summary-key /
canned-string twins (47-59, 61-63, 66-68).  Those are classified
killed_by_draft and are NOT re-tested here.  The 19 keys this file owns are the
ones no existing test reaches, and the reason is structural:

  * every draft input either satisfies LLMRiskResponse outright or fails
    LLMRawResponse's before-validator (backend/api/schemas/llm_response.py:567-590
    demands BOTH risk_score and risk_level), so NO draft input ever lands on the
    lenient path (mutmut_4 invisible); and no draft input carries an empty
    summary/reasoning, so the strict and lenient dumps are indistinguishable for
    it (mutmut_2 invisible);
  * no draft test reads a log record, so the whole fallback WARNING call site is
    unobserved (mutmut_6, 7, 9-18);
  * the draft reads values only, never the returned KEY SET (mutmut_45, 46), and
    never feeds a "reasoning" value to the default path (mutmut_60, 64, 65).

Three return shapes make the function observable (all probe-verified):
  * strict path  (4371) -> LLMRiskResponse.model_dump(): 9 keys, an EMPTY-STRING
    summary/reasoning survives verbatim, risk_level is echoed.
  * lenient path (4381) -> raw.to_validated_response().model_dump()
    (llm_response.py:593-650): 9 keys, a falsy summary/reasoning is REPLACED by
    the canned strings (llm_response.py:629-630), an empty risk_level is INFERRED
    from the score (llm_response.py:623-626).
  * default path (4412-4417) -> the 4-key literal plus exactly one WARNING at
    4386-4389, whose ``extra=`` keys land on the LogRecord as attributes
    (ContextFilter, backend/core/logging.py:525-610, preserves explicit extra=
    values; the JSON formatter reads them back at :770-780).

Severity thresholds are pinned by an autospec patch of
backend.services.severity.get_settings (29/59/84 — the shipped Settings defaults
at backend/core/config.py:2359-2376, the same values the repo unit fixture
mock_settings uses) so the inferred level is deterministic whatever the ambient
.env says.  That patch is not a shield: the default-path dict is computed from
``data`` alone and is returned verbatim under every mutant here.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# Mirror the minimum env the repo conftest sets (this file lives outside the
# repo tree, so backend/tests/conftest.py does not apply).  Values copied from
# /agents/agent-veranda3/workspace/backend/tests/conftest.py.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)

from backend.services.nemotron_analyzer import NemotronAnalyzer

LOGGER_NAME = "backend.services.nemotron_analyzer"
CANNED_SUMMARY = "Risk analysis completed"
CANNED_REASONING = "No detailed reasoning provided"
WARNING_TEXT = "Failed to validate LLM response, using defaults"

# LLMRiskResponse.model_dump() key set (backend/api/schemas/llm_response.py:321
# plus to_validated_response()).  The strict AND the lenient path both return
# this 9-key shape; the default path returns the 4-key literal.
SCHEMA_KEYS = {
    "risk_score",
    "risk_level",
    "summary",
    "reasoning",
    "risk_factors",
    "entities",
    "flags",
    "recommended_action",
    "confidence_factors",
}
DEFAULT_KEYS = {"risk_score", "risk_level", "summary", "reasoning"}


def _analyzer() -> NemotronAnalyzer:
    # __new__ skips the heavy __init__ (model/client wiring); the helper under
    # test reads only its argument, never instance state.
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


@contextmanager
def pinned_severity():
    """Pin SeverityService thresholds to the shipped Settings defaults.

    Only the DEFAULT path reaches it (nemotron_analyzer.py:4407-4410), so the
    strict/lenient assertions are untouched by the patch.
    """
    settings = MagicMock()
    settings.severity_low_max = 29
    settings.severity_medium_max = 59
    settings.severity_high_max = 84
    with patch("backend.services.severity.get_settings", autospec=True, return_value=settings):
        yield


@contextmanager
def collected_warnings():
    """Capture WARNING records emitted by the nemotron_analyzer logger only."""
    records: list[logging.LogRecord] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.levelno >= logging.WARNING:
                records.append(record)

    logger = logging.getLogger(LOGGER_NAME)
    original_handlers = list(logger.handlers)
    original_propagate = logger.propagate
    original_level = logger.level
    logger.handlers = [_Collect()]
    logger.propagate = False
    logger.setLevel(logging.WARNING)
    try:
        yield records
    finally:
        logger.handlers = original_handlers
        logger.propagate = original_propagate
        logger.setLevel(original_level)


class TestStrictPathIsTaken:
    """nemotron_analyzer.py:4371 — the strict attempt."""

    def test_strict_path_returns_input_verbatim_and_emits_no_warning(self):
        """Kills ..._validate_risk_data__mutmut_2 (shape:
        LLMRiskResponse.model_validate(data) -> model_validate(None)).  Shipped
        takes the strict path for a well-formed dict, so the EMPTY-STRING summary
        and reasoning come back verbatim in the full 9-key schema dump, the input
        risk_level "low" is echoed rather than re-inferred (SeverityService maps
        70 to "high"), and the fallback WARNING at 4386 never fires.  The mutant
        can never validate ``None``, always falls through, and rewrites those two
        fields to the canned strings (llm_response.py:629-630) while emitting the
        WARNING.

        Keys: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_validate_
        risk_data__mutmut_2
        """
        a = _analyzer()
        with collected_warnings() as records, pinned_severity():
            got = a._validate_risk_data(
                {"risk_score": 70, "risk_level": "low", "summary": "", "reasoning": ""}
            )
        assert records == []
        assert got == {
            "risk_score": 70,
            "risk_level": "low",
            "summary": "",
            "reasoning": "",
            "risk_factors": [],
            "entities": [],
            "flags": [],
            "recommended_action": None,
            "confidence_factors": None,
        }


class TestLenientPathIsTaken:
    """nemotron_analyzer.py:4381 — the lenient attempt.  An EMPTY-STRING
    risk_level passes LLMRiskResponse.validate_risk_level as a plain str without
    being a valid level, so the strict dump echoes "" where the lenient dump
    INFERS the level from the score — the probe-verified observable separating
    the two paths.  (Every input with a VALID risk_level is byte-identical under
    shipped and this mutant, and a payload whose risk_level key is ABSENT is
    rejected outright by LLMRawResponse's before-validator,
    llm_response.py:584-589.)"""

    def test_lenient_path_infers_empty_level_from_score_and_dumps_schema(self):
        """Kills ..._validate_risk_data__mutmut_4 (shape:
        LLMRawResponse.model_validate(data) -> model_validate(None)) — shipped
        accepts {"risk_score": 70, "risk_level": ""} with the lenient schema and
        answers risk_level "high" (infer_risk_level_from_score,
        llm_response.py:623-626) inside the 9-key dump; the mutant skips the
        lenient path and answers 70 with "medium" (SeverityService 29/59/84
        ladder) inside a 4-key dict.

        Keys (whole single-key shape group, carried per the occurrence-twin
        rule): backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_validate_
        risk_data__mutmut_4 — also carried by
        test_lenient_path_replaces_empty_summary_and_reasoning and
        test_lenient_path_supplies_schema_defaults_for_a_missing_summary.
        """
        a = _analyzer()
        with pinned_severity():
            got = a._validate_risk_data(
                {"risk_score": 70, "risk_level": "", "summary": "s", "reasoning": "r"}
            )
        assert set(got) == SCHEMA_KEYS
        assert got["risk_score"] == 70
        assert got["risk_level"] == "high"
        assert got["summary"] == "s"
        assert got["reasoning"] == "r"
        assert got["risk_factors"] == []
        assert got["entities"] == []
        assert got["flags"] == []
        assert got["recommended_action"] is None
        assert got["confidence_factors"] is None

    def test_lenient_path_replaces_empty_summary_and_reasoning(self):
        """Kills ..._validate_risk_data__mutmut_4 (second input of the same
        shape group) — shipped lenient normalization (llm_response.py:629-630)
        substitutes the canned strings for a falsy summary/reasoning, the exact
        mirror of the strict-path assertion above.

        Keys: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_validate_
        risk_data__mutmut_4
        """
        a = _analyzer()
        with pinned_severity():
            got = a._validate_risk_data(
                {"risk_score": 70, "risk_level": "", "summary": "", "reasoning": ""}
            )
        assert got["risk_level"] == "high"
        assert got["summary"] == CANNED_SUMMARY
        assert got["reasoning"] == CANNED_REASONING

    def test_lenient_path_supplies_schema_defaults_for_a_missing_summary(self):
        """Kills ..._validate_risk_data__mutmut_4 (third input of the same shape
        group).  Here the level and the canned strings are what the mutant's
        4-key default literal ALSO produces (default path, score 20 -> "low"),
        so the kill signal is the 9-key shape itself: shipped dumps the five
        NEM-3601/3603 fields (llm_response.py:645-649), the mutant returns only
        4 keys.

        Keys: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_validate_
        risk_data__mutmut_4
        """
        a = _analyzer()
        with pinned_severity():
            got = a._validate_risk_data({"risk_score": 20, "risk_level": ""})
        assert got == {
            "risk_score": 20,
            "risk_level": "low",
            "summary": CANNED_SUMMARY,
            "reasoning": CANNED_REASONING,
            "risk_factors": [],
            "entities": [],
            "flags": [],
            "recommended_action": None,
            "confidence_factors": None,
        }


class TestFallbackWarningSite:
    """nemotron_analyzer.py:4386-4389 — the fallback WARNING call: its message
    literal (4387) and its curated ``extra=`` payload (4388).  Nothing in the
    repo or the draft battery reads a record from this call site, so all 9 keys
    on the line are reachable only through the LogRecord."""

    def test_warning_message_literal_is_exact(self):
        """Kills the four message-literal mutants at nemotron_analyzer.py:4387 —
        mutmut_6 (message -> None, which logging renders as the string "None"),
        mutmut_10 (XX-wrapped), mutmut_11 (lower-cased), mutmut_12
        (upper-cased): shipped text is byte-exact and emitted exactly once per
        default-path call.

        Keys: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_validate_
        risk_data__mutmut_6, ...__mutmut_10, ...__mutmut_11, ...__mutmut_12
        """
        a = _analyzer()
        with collected_warnings() as records, pinned_severity():
            assert a._validate_risk_data({"risk_score": "abc"})["risk_score"] == 50
        assert [r.getMessage() for r in records] == [WARNING_TEXT]

    def test_warning_record_carries_both_curated_extra_fields(self):
        """Kills mutmut_7 (extra={...} -> extra=None) and mutmut_9 (the extra=
        argument dropped, leaving logger.warning(<msg>)) at
        nemotron_analyzer.py:4388 — shipped attaches two curated fields to the
        record, ``validation_errors`` and ``error``; under those two mutants
        neither attribute exists at all.

        Keys: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_validate_
        risk_data__mutmut_7, ...__mutmut_9
        """
        a = _analyzer()
        with collected_warnings() as records, pinned_severity():
            assert a._validate_risk_data({})["risk_score"] == 50
        assert len(records) == 1
        record = records[0]
        assert hasattr(record, "validation_errors")
        assert hasattr(record, "error")
        assert "Missing required fields: risk_score and risk_level" in record.validation_errors
        assert "Missing required fields: risk_score and risk_level" in record.error

    def test_warning_extra_field_names_and_rendered_values_are_exact(self):
        """Kills the six extra= payload mutants at nemotron_analyzer.py:4388 —
        mutmut_13 ("validation_errors" -> "XXvalidation_errorsXX"), mutmut_14
        (-> "VALIDATION_ERRORS"), mutmut_16 ("error" -> "XXerrorXX"), mutmut_17
        (-> "ERROR"): the renamed key is absent, so the strict attribute read
        raises AttributeError; and mutmut_15 (str(e.errors()) -> str(None)),
        mutmut_18 (str(e) -> str(None)): both attributes degrade to the literal
        "None".  The two shipped values are pinned — the e.errors() repr and the
        pydantic str(e) rendering of the LLMRawResponse missing-required-field
        failure.

        Keys: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_validate_
        risk_data__mutmut_13, ...__mutmut_14, ...__mutmut_15, ...__mutmut_16,
        ...__mutmut_17, ...__mutmut_18
        """
        a = _analyzer()
        with collected_warnings() as records, pinned_severity():
            assert a._validate_risk_data({"risk_score": "abc"})["risk_score"] == 50
        record = records[0]
        assert record.validation_errors.startswith("[{'type': 'value_error'")
        assert (
            "'msg': 'Value error, Missing required field: risk_level'" in record.validation_errors
        )
        assert "'input': {'risk_score': 'abc'}" in record.validation_errors
        assert record.error.startswith("1 validation error for LLMRawResponse")
        assert "Value error, Missing required field: risk_level" in record.error
        assert "input_value={'risk_score': 'abc'}" in record.error


class TestDefaultPathOutputDict:
    """nemotron_analyzer.py:4412-4417 — the fallback dict literal: the risk_level
    output key (4414) and the reasoning lookup key (4416).  A renamed key literal
    is invisible to a value-only read, so the KEY SET and the exact input key are
    what these two tests assert."""

    def test_fallback_dict_key_set_is_exactly_four(self):
        """Kills mutmut_45 ("risk_level" -> "XXrisk_levelXX") and mutmut_46 (->
        "RISK_LEVEL") at nemotron_analyzer.py:4414 — the shipped fallback literal
        carries EXACTLY {"risk_score", "risk_level", "summary", "reasoning"}; a
        renamed output key drops "risk_level" and adds the mutant spelling, which
        no value-only read (the draft's style) can observe.

        Keys: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_validate_
        risk_data__mutmut_45, ...__mutmut_46
        """
        a = _analyzer()
        with pinned_severity():
            for data in ({}, {"risk_score": "abc"}, {"summary": "S"}):
                assert set(a._validate_risk_data(dict(data))) == DEFAULT_KEYS

    def test_fallback_dict_reads_reasoning_by_its_exact_input_key(self):
        """Kills mutmut_60 (data.get("reasoning", X) -> data.get(None, X)),
        mutmut_64 (-> data.get("XXreasoningXX", X)) and mutmut_65 (->
        data.get("REASONING", X)) at nemotron_analyzer.py:4416 — shipped reads
        data["reasoning"] by that exact lower-case name and returns it verbatim;
        all three mutants miss the lookup and substitute the canned text
        (probe-verified).  A decoy "REASONING" entry pins the upper-case lookup-
        key mutant.

        Keys: backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_validate_
        risk_data__mutmut_60, ...__mutmut_64, ...__mutmut_65
        """
        a = _analyzer()
        with pinned_severity():
            got = a._validate_risk_data({"reasoning": "R", "REASONING": "DECOY-R"})
        assert got["reasoning"] == "R"
        assert set(got) == DEFAULT_KEYS
