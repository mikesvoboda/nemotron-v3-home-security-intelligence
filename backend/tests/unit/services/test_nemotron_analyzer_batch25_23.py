"""Batch-25 part 23 — chunk "tail:extract_json_objects+6more#chunk1" (98 keys).

Chunk functions and their shipped sites in backend/services/nemotron_analyzer.py:

  _extract_json_objects                    module-level, L159-198        (43 keys)
  NemotronAnalyzer._validate_and_truncate_prompt  L4419-4470              (21 keys)
  NemotronAnalyzer._record_experiment_result      L1113-1139              (17 keys)
  NemotronAnalyzer.record_rollout_analysis        L1222-1256              (13 keys)
  NemotronAnalyzer.set_ab_test_config             L820-836                 (2 keys)
  NemotronAnalyzer._get_batch_coalescer           L633-645                 (1 key)
  NemotronAnalyzer.set_rollout_manager            L1145-1170               (1 key)

DISPOSITION SUMMARY (98 keys, each exactly once — see verdicts_23.json):
  killed_by_draft  35  (all in _extract_json_objects; the batch-25 draft battery
                        /tmp/wp-batch25/test_nemotron_analyzer_batch25.py already
                        kills them — verified mechanically, see below)
  killable         57  (the 8 remaining _extract_json_objects keys minus the 6
                        proven equivalents, plus all 55 keys of the other six
                        functions — no repo test and no draft test kills them)
  equivalent        6  (proven; the only six _extract_json_objects keys that no
                        input can separate)
  true_gap          0

HOW THE 35 killed_by_draft WERE ESTABLISHED (not by reading the draft): the 43
_extract_json_objects variants were extracted verbatim from the instrumented copy
(mutants/backend/services/nemotron_analyzer.py) into
/tmp/wp-batch25/mutbodies23.py, then each of the 5 passing draft extraction tests
(test_nested_json_via_balanced_extractor, test_string_literal_braces_skipped,
test_escape_inside_string, test_truncated_json_recovered,
test_no_json_raises_valueerror) was re-run with ``_extract_json_objects`` swapped
for the variant body, under a SIGALRM budget (/tmp/wp-batch25/draftcheck23b.py).
Baseline with __mutmut_orig: 5/5 PASS. 35 of the 43 survivors change at least one
outcome. The 8 that do not are 14, 17, 24, 25, 26, 29 (proven equivalent below)
and 53, 54 — i.e. the draft credits are exactly "the 8 no-draft-kill keys"
reported by that script.

EQUIVALENCE PROOFS (6 keys, the only 6 that no input separates).
 exhaustively checked, not assumed: every string of length <= 5 over the alphabet
 {, }, ", backslash, a, colon, space, x — 37,449 inputs — with a 0.2 s budget per call
 (/tmp/wp-batch25/exh23.py): divergent-texts = 0 for 14, 17, 24, 25, 26, 29.
 Structurally, why each is a no-op:
   14 + 29  `in_string = False` -> `in_string = None` (L173 initializer and L183
            string-close; the shape's two occurrences, so the twin pair is carried
            together). in_string is never compared, returned or sliced — its ONLY
            read is the truth test `if in_string:` (L178), and None is falsy
            exactly as False is.
   17       `found_end = False` -> `found_end = None` (L175). Only read is
            `if not found_end:` (L196-197) -> same branch either way.
   24/25/26 escape-guard operand `j + 1 < n` -> `j - 1 < n` / `j + 2 < n` /
            `j + 1 <= n` (L179). The guard is only evaluated with c == "\\" inside a
            string. Where the three variants flip the outcome they differ only by
            whether the inner loop takes ONE extra step into text the loop bound
            then discards: the emitted slice text[i : j + 1] is produced only in the
            depth == 0 arm, which the extra step cannot reach (at most one character
            remains, and it can only close the string, not close an object), so both
            paths leave `results` and `found_end` identical and fall into the same
            `if not found_end: break` (L191-197).

WHY THE ONLY TWO NON-DRAFT-KILL, NON-EQUIVALENT EXTRACTION KEYS NEED A TEST:
  53  `i = j + 1` -> `i = j - 1` (L193, the emit-time restart): an exhaustive
      search ({, }, ", backslash, a, x up to length 6) found NO input where the
      mutant terminates with a different result — every discriminating input makes
      it never return (the restart lands back on the consumed "}" and re-emits the
      same slice forever). Non-termination is its only observable, so the kill is a
      budgeted test (pytest-timeout, the repo's own tier) driven by `{}`.
  54  `i = j + 1` -> `i = j + 2`: skips one byte after each emitted object;
      observable only when the next object starts IMMEDIATELY after the previous
      "}" AND the skipped byte matters, i.e. after a zero-width restart. Draft
      inputs use a space separator ("{"a":1} {"b":2}"), which is invariant.
  58 (`j += 1` -> `j += 2`, L195) IS draft-killed — draftcheck23b.py measured
      test_string_literal_braces_skipped / test_escape_inside_string /
      test_nested_json_via_balanced_extractor all change outcome. It is therefore
      classified killed_by_draft; the restart-group test for key 53 happens to
      separate 58 as well (no input can hit 53's non-termination without also
      walking the doubled step over an object terminator) and says so in its
      docstring, but no key here depends on that overlap.

OCCURRENCE TWINS carried whole (never a subset):
  14 <-> 29   (`in_string = False` -> None; occurrences L171 initializer, L178
               string-close) — both equivalent.
  15 <-> 30   (`in_string = False` -> True) — both killed_by_draft.
  record_rollout_analysis: 5<->11, 6<->12, 7<->13 (kwarg -> None),
               8<->14, 9<->15 (kwarg dropped), 10<->16 (kwarg + closing paren)
               — control arm then treatment arm. Both keys of every group are
               carried, and each is killed by the test that drives its OWN arm
               (measured: 5/6/7/8/9/10 fail the control-arm test, 11/12/13/14/15/16
               fail the treatment-arm test). Key 4 (`if group == ...` -> `!=`, the
               guard both arms hang off) is killed by BOTH tests, so it is named in
               both docstrings.

NOTHING HERE IS MARKED EQUIVALENT ON THE DOSSIER'S WORD. The frozen dossier
(archive/wp25-feed/wp44-triage/nemotron_analyzer.md) was not consulted for
verdicts; every claim above is from the shipped source and the instrumented
variant bodies, and the six equivalents carry the exhaustive-enumeration proof.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_23.py -p no:cacheprovider -o addopts= -q
"""

from __future__ import annotations

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# The part file lives outside the repo tree, so backend/tests/conftest.py does NOT
# apply. Mirror the minimum env vars that conftest sets BEFORE any backend import
# (values copied verbatim from backend/tests/conftest.py:107-114,363-385 — not
# invented).
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("OTEL_ENABLED", "false")

from backend.config.prompt_ab_rollout import (
    ABRolloutConfig,
    ABRolloutManager,
    AutoRollbackConfig,
    ExperimentGroup,
)
from backend.config.prompt_experiment import PromptVersion
from backend.services.nemotron_analyzer import (
    NemotronAnalyzer,
    _extract_json_objects,
)
from backend.services.prompt_service import ABTestConfig
from backend.services.token_counter import (
    TokenValidationResult,
    TruncationResult,
)

LOGGER = "backend.services.nemotron_analyzer"

# Shipped literals, copied from the source lines each mutant rewrites (values
# confirmed by probing the SHIPPED functions, /tmp/wp-batch25/probe23.py +
# probe23b.py — production is pinned as shipped, never as expected).
TRUNC_MSG = "Prompt truncated to fit context window"
EXPERIMENT_MSG = "Experiment result recorded"
AB_MSG = "A/B testing configured: control=v1, treatment=v2, split=42.0%"
ROLLOUT_MSG = (
    "A/B rollout manager configured: experiment=chunk23-experiment, treatment=30%, active=True"
)
AB_TYPEERROR = "config must be an ABTestConfig instance"

PROMPT = "PROMPT_TEXT"
MAX_OUTPUT_TOKENS = 1536
AVAILABLE_TOKENS = 2560
TRUNCATED_PROMPT = "TRUNCATED_PROMPT"


def _analyzer() -> NemotronAnalyzer:
    """__new__ skips the heavy __init__; these seven targets touch only the
    attributes each test sets explicitly (never model/client wiring)."""
    return NemotronAnalyzer.__new__(NemotronAnalyzer)


@pytest.fixture
def records():
    """Collect every record the shipped code writes on the analyzer module logger.

    The shipped functions are at DEBUG/WARNING level and the module logger
    inherits the root level, so the level is forced to DEBUG for the test and
    restored after — without it a `logger.debug(...)` call is dropped before the
    handler and the extra= payload (the whole observable) never materialises.
    """
    logger = logging.getLogger(LOGGER)
    collected: list[logging.LogRecord] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            collected.append(record)

    handler = _Collect()
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield collected
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


# =========================================================================
# _extract_json_objects — the 3 keys no existing test separates
# (the other 40 of the 43: 35 killed_by_draft, 6 equivalent -> see the
#  module docstring and verdicts_23.json)
# =========================================================================


class TestExtractJsonObjectsRestartAccounting:
    """The emit-time restart `i = j + 1` (L193) and the inner scan step `j += 1` (L195).

    Every value asserted below was read off the SHIPPED function, and the kill for
    each key was confirmed by re-running the group against the extracted variant
    body (/tmp/wp-batch25/redmap23.py, 0.15 s budget per call). The three input
    groups were chosen to be MUTUALLY EXCLUSIVE wherever that is possible:
    measured, `i = j - 1` (key 53) hangs on exactly the inputs where an object is
    emitted from a 0- or 1-byte body, and those same inputs are also the only ones
    that expose the doubled scan step (key 58) — no input separates 53 without also
    separating 58, so key 58 is legitimately named by two tests and key 53 by one.
    """

    @pytest.mark.timeout(10)
    def test_zero_and_single_byte_object_bodies(self):
        """Kills backend.services.nemotron_analyzer.x__extract_json_objects__mutmut_53
        and ...x__extract_json_objects__mutmut_58.

        Sites: L193 `i = j + 1` -> `i = j - 1` (key 53 — the SECOND occurrence of
        the `i = j + 1` shape, the restart taken when an object is emitted, not the
        non-"{" skip at L170) and L195 `j += 1` -> `j += 2` (key 58).

        Shipped behavior pinned: `{}` -> `['{}']`, `'{} '` -> `['{}']`, `'{}{'` ->
        `['{}']` — an object whose "}" is the final byte is emitted exactly once and
        the outer loop then ends, because the restart lands on i == n.

        Mutant behavior.
          53: `i = j - 1` restarts back ON the "}" just consumed, so the outer loop
              re-enters the scan from the same index, re-emits the same slice and
              never advances: `_extract_json_objects("{}")` DOES NOT RETURN. The
              kill is delivered by pytest-timeout — the repo's own tier
              (pyproject.toml timeout = 5, timeout_method = "signal"; the mutmut
              runner runs --timeout=120), which is precisely how mutmut banks this
              key. Exhaustively searched ({, }, ", backslash, a, x over lengths
              <= 6): every input where 53 differs from shipped does so by not
              terminating — non-termination is the only observable this mutant has,
              so a budgeted test is the only possible kill.
          58: with the scan stepping two bytes, all three inputs return `[]` — the
              extractor stops finding an object that is plainly there. This
              cross-kill is unavoidable: key 53's only discriminating inputs are
              0/1-byte bodies, which are exactly what a doubled step walks over.
              (58 is killed_by_draft — named here only because no input reaches
              53 without also exposing 58.)
        """
        assert _extract_json_objects("{}") == ["{}"]
        assert _extract_json_objects("{} ") == ["{}"]
        assert _extract_json_objects("{}{") == ["{}"]

    def test_adjacent_objects_survive_the_restart_plus_one(self):
        """Kills backend.services.nemotron_analyzer.x__extract_json_objects__mutmut_54.

        Shape: L193 `i = j + 1` -> `i = j + 2` (same line and occurrence as key 53,
        the other mutation of that restart).

        Shipped behavior pinned: when the next object starts IMMEDIATELY after the
        previous "}", the restart must land on that "{" — `{"a":1}{"b":2}` -> both
        objects; `{"a":1}{b:2}` -> `['{"a":1}', '{b:2}']` (the second is not valid
        JSON, but this extractor is syntax-only and the caller filters by
        json.loads); `{"s":"a"}{{b}}` -> `['{"s":"a"}', '{{b}}']` (the second object
        opens with a nested brace).

        Mutant behavior: the restart overshoots by exactly one byte — the byte the
        next object's "{" occupies — so the mutant returns `['{"a":1}']`,
        `['{"a":1}']` and `['{"s":"a"}', '{b}']`: the second object is lost or its
        lead brace is eaten. These three inputs are 54-EXCLUSIVE (neither 53 nor 58
        differs from shipped on any of them), which is why this test names one key.
        The draft battery cannot see any of this: its only two-object input
        separates the objects with a space, where the skipped byte is inert
        whitespace.
        """
        assert _extract_json_objects('{"a":1}{"b":2}') == ['{"a":1}', '{"b":2}']
        assert _extract_json_objects('{"a":1}{b:2}') == ['{"a":1}', "{b:2}"]
        assert _extract_json_objects('{"s":"a"}{{b}}') == ['{"s":"a"}', "{{b}}"]


# =========================================================================
# NemotronAnalyzer._validate_and_truncate_prompt (21 keys)
# =========================================================================


def _drive_truncate(analyzer, *, is_valid: bool = False):
    """Run the shipped truncation arm with the token counter stubbed at its import site.

    Returns (result, counter, metric) where metric is the patched
    backend.core.metrics.record_prompt_truncated. Patch call sites carry
    autospec=True per the CI ratchet.
    """
    settings = MagicMock()
    settings.nemotron_max_output_tokens = MAX_OUTPUT_TOKENS
    settings.context_truncation_enabled = True

    counter = MagicMock()
    counter.validate_prompt.return_value = TokenValidationResult(
        is_valid=is_valid,
        prompt_tokens=5000,
        available_tokens=AVAILABLE_TOKENS,
        context_window=4096,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        utilization=2.0,
        warning=None if is_valid else "Prompt exceeds context window",
    )
    counter.truncate_enrichment_data.return_value = TruncationResult(
        truncated_prompt=TRUNCATED_PROMPT,
        was_truncated=True,
        original_tokens=5000,
        final_tokens=2000,
        sections_removed=["enrichment_context"],
    )

    with (
        patch(
            "backend.services.nemotron_analyzer.get_settings",
            return_value=settings,
            autospec=True,
        ),
        patch(
            "backend.services.token_counter.get_token_counter",
            return_value=counter,
            autospec=True,
        ),
        patch(
            "backend.core.metrics.record_prompt_truncated",
            autospec=True,
        ) as metric,
    ):
        result = analyzer._validate_and_truncate_prompt(PROMPT)
    return result, counter, metric


class TestValidateAndTruncatePromptCallContract:
    """The two token-counter calls and their exact arguments (7 keys)."""

    def test_counter_receives_prompt_and_settings_budget(self, records):
        """Kills xǁNemotronAnalyzerǁ_validate_and_truncate_prompt__mutmut_4, 5, 7,
        11, 12, 13, 14 (all seven keys of the two call-site shape groups).

        Sites (nemotron_analyzer.py:4441 and :4454):
          4   validate_prompt(prompt, ...)  -> validate_prompt(None, ...)
          5   ... settings.nemotron_max_output_tokens -> None
          7   validate_prompt(prompt, budget)       -> validate_prompt(prompt,)
          11  truncate_enrichment_data(prompt, ...)  -> (None, ...)
          12  ... validation.available_tokens        -> None
          13  truncate_enrichment_data(prompt, avail) -> (available_tokens)  [1-arg]
          14  truncate_enrichment_data(prompt, avail) -> (prompt,)           [1-arg]

        Shipped behavior pinned (probe: `call('PROMPT_TEXT', 1536)` and
        `call('PROMPT_TEXT', 2560)`): the prompt travels to BOTH calls and the
        budget travels as the second positional argument to both. Nothing else
        about the drive is sensitive to these seven mutations — the stubbed
        counter answers any argument list with the same canned
        is_valid=False / was_truncated=True result, and the log record reads only
        the *result* objects — which is exactly why no existing test kills them:
        test_nemotron_analyzer.py:4053/4092 assert only the returned prompt and
        `assert_called_once()` (name- and argument-blind).
        """
        result, counter, metric = _drive_truncate(_analyzer())
        assert result == TRUNCATED_PROMPT
        assert metric.call_count == 1
        counter.validate_prompt.assert_called_once_with(PROMPT, MAX_OUTPUT_TOKENS)
        counter.truncate_enrichment_data.assert_called_once_with(PROMPT, AVAILABLE_TOKENS)

    def test_valid_prompt_short_circuits_without_truncation(self, records):
        """Anchors the arm the seven call-contract keys live in: with
        is_valid=True the shipped function returns the prompt untouched, logs
        nothing and never truncates. Guards the other assertions against a
        stub that would make the truncation arm unconditional. Kills nothing on
        its own (documented here so the class is honest about which asserts are
        load-bearing).
        """
        result, counter, metric = _drive_truncate(_analyzer(), is_valid=True)
        assert result == PROMPT
        assert records == []
        metric.assert_not_called()
        counter.truncate_enrichment_data.assert_not_called()


class TestValidateAndTruncatePromptTruncationLog:
    """The WARNING record the truncation arm writes (14 keys)."""

    def test_warning_message_and_extra_payload_are_the_exact_contract(self, records):
        """Kills xǁNemotronAnalyzerǁ_validate_and_truncate_prompt__mutmut_15, 16,
        18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29.

        Sites (nemotron_analyzer.py:4457-4467):
          15  message -> None                16  extra=None
          18  the whole extra={...} block deleted (call ends at the message)
          19/20/21  message -> "XXPrompt truncated to fit context windowXX" /
                      "prompt truncated to fit context window" /
                      "PROMPT TRUNCATED TO FIT CONTEXT WINDOW"
          22/23  "original_tokens"  -> "XXoriginal_tokensXX"  / "ORIGINAL_TOKENS"
          24/25  "final_tokens"     -> "XXfinal_tokensXX"     / "FINAL_TOKENS"
          26/27  "sections_removed" -> "XXsections_removedXX" / "SECTIONS_REMOVED"
          28/29  "available_tokens" -> "XXavailable_tokensXX" / "AVAILABLE_TOKENS"

        The observable is the LogRecord itself: `Logger.makeRecord` copies the
        extra= mapping into record.__dict__, so a renamed key is a missing
        attribute and a deleted extra= is no attribute at all. The record is
        selected structurally (carries original_tokens) so the message mutants
        cannot dodge the selection, then its message, level and all four values
        are pinned to the shipped probe output. No repo test kills any of these:
        the three repo truncation tests never attach a log handler, and nothing
        in the repo reads these four extra keys.
        """
        result, counter, metric = _drive_truncate(_analyzer())
        assert result == TRUNCATED_PROMPT
        carriers = [r for r in records if hasattr(r, "original_tokens")]
        assert len(carriers) == 1, (
            "expected exactly one record carrying the truncation extra= payload "
            f"(mutant dropped extra= or renamed its keys); got {records!r}"
        )
        record = carriers[0]
        assert record.levelno == logging.WARNING
        assert record.getMessage() == TRUNC_MSG
        assert record.original_tokens == 5000
        assert record.final_tokens == 2000
        assert record.sections_removed == ["enrichment_context"]
        assert record.available_tokens == AVAILABLE_TOKENS


# =========================================================================
# NemotronAnalyzer._record_experiment_result (17 keys)
# =========================================================================


class TestRecordExperimentResult:
    """The latency metric and the DEBUG record (nemotron_analyzer.py:1129-1139)."""

    def test_latency_metric_receives_version_value_and_seconds(self, records):
        """Kills xǁNemotronAnalyzerǁ_record_experiment_result__mutmut_1, 5, 6.

        Site (L1130): record_prompt_latency(version.value, latency_ms / 1000)
          1  version.value -> None
          5  latency_ms / 1000 -> latency_ms * 1000
          6  latency_ms / 1000 -> latency_ms / 1001

        Shipped behavior pinned (probe: `call('v2_calibrated', 0.15)`): the metric
        label is the enum VALUE and the sample is milliseconds converted to
        SECONDS. The metric is looked up as a module attribute of
        backend.core.metrics by the function-local import, so patching there is
        the shipped seam. Nothing else in the drive is sensitive to the three
        mutants: the DEBUG record below carries latency_ms unscaled, which is why
        the repo's only exercise of this method
        (test_prompt_experiment_integration.py:693-740) asserts nothing at all
        about the metric — it just calls the method and says "complete without
        error", so it kills zero keys of this chunk.
        """
        analyzer = _analyzer()
        with patch("backend.core.metrics.record_prompt_latency", autospec=True) as metric:
            analyzer._record_experiment_result(
                camera_id="front_door",
                version=PromptVersion.V2_CALIBRATED,
                risk_score=45,
                latency_ms=150.0,
            )
        metric.assert_called_once_with(PromptVersion.V2_CALIBRATED.value, 150.0 / 1000)

    def test_debug_record_message_and_extra_payload_are_exact(self, records):
        """Kills xǁNemotronAnalyzerǁ_record_experiment_result__mutmut_7, 8, 10, 11,
        12, 13, 14, 15, 16, 17, 18, 19, 20, 21.

        Sites (L1131-1139):
          7   message -> None
          8   extra={...} -> extra=None
          10  the whole extra={...} block deleted (call ends at the message)
          11/12/13  message -> "XXExperiment result recordedXX" /
                    "experiment result recorded" / "EXPERIMENT RESULT RECORDED"
          14/15  "camera_id"  -> "XXcamera_idXX"  / "CAMERA_ID"
          16/17  "version"    -> "XXversionXX"    / "VERSION"
          18/19  "risk_score" -> "XXrisk_scoreXX" / "RISK_SCORE"
          20/21  "latency_ms" -> "XXlatency_msXX" / "LATENCY_MS"

        Shipped behavior pinned (probe): DEBUG-level record, message
        "Experiment result recorded", extra = {camera_id, version, risk_score,
        latency_ms} with the RAW millisecond value (not the seconds the metric
        gets) and the enum VALUE (not the enum repr). Selected structurally via
        camera_id, so the message mutants cannot slip past the selection; the
        extra=None / deleted-extra mutants are caught by the count assertion.
        """
        analyzer = _analyzer()
        with patch("backend.core.metrics.record_prompt_latency", autospec=True) as metric:
            analyzer._record_experiment_result(
                camera_id="front_door",
                version=PromptVersion.V2_CALIBRATED,
                risk_score=45,
                latency_ms=150.0,
            )
        assert metric.call_count == 1
        carriers = [r for r in records if hasattr(r, "camera_id")]
        assert len(carriers) == 1, (
            f"expected exactly one record carrying the experiment extra= payload; got {records!r}"
        )
        record = carriers[0]
        assert record.levelno == logging.DEBUG
        assert record.getMessage() == EXPERIMENT_MSG
        assert record.camera_id == "front_door"
        assert record.version == "v2_calibrated"
        assert record.risk_score == 45
        assert record.latency_ms == 150.0


# =========================================================================
# NemotronAnalyzer.record_rollout_analysis (13 keys)
# =========================================================================


def _drive_rollout(group, *, latency_ms, risk_score, has_error):
    """Route one analysis through the shipped function with a recording manager."""
    analyzer = _analyzer()
    manager = MagicMock()
    manager.get_group_for_camera.return_value = group
    analyzer._rollout_manager = manager
    analyzer.record_rollout_analysis(
        camera_id="cam-23",
        latency_ms=latency_ms,
        risk_score=risk_score,
        has_error=has_error,
    )
    return manager


class TestRecordRolloutAnalysisArms:
    """Both arms forward all three arguments to their own group (13 keys).

    OCCURRENCE-TWIN pairs (one shape group, two occurrences — control arm first,
    treatment arm second, so both keys are always carried together):
      5<->11 latency_ms=None   6<->12 risk_score=None   7<->13 has_error=None
      8<->14 latency_ms kwarg deleted   9<->15 risk_score kwarg deleted
      10<->16 has_error kwarg + closing paren deleted (call collapses to one line)
    """

    def test_control_arm_forwards_all_three_arguments(self, records):
        """Kills xǁNemotronAnalyzerǁrecord_rollout_analysis__mutmut_4, 5, 6, 7, 8,
        9, 10 and — because key 4 is the branch guard shared by both arms — the
        treatment-arm twins are killed by the sibling test below.

        Sites (nemotron_analyzer.py:1245-1250):
          4   `if group == ExperimentGroup.CONTROL:` -> `if group != ...` (the two
              arms swap bodies)
          5   latency_ms=latency_ms  -> latency_ms=None      (control arm)
          6   risk_score=risk_score  -> risk_score=None      (control arm)
          7   has_error=has_error    -> has_error=None       (control arm)
          8   latency_ms kwarg deleted                        (control arm)
          9   risk_score kwarg deleted                       (control arm)
          10  has_error kwarg deleted                       (control arm)

        Shipped behavior pinned (probe):
        `call(latency_ms=100.0, risk_score=50, has_error=True)` on the CONTROL
        recorder and nothing on the treatment recorder. has_error=True is
        deliberate: with the shipped default (False) or a falsy score, mutants 7/8/9
        are indistinguishable from shipped on this call — the manager's own
        defaults are has_error=False and None scores, so only a truthy value for
        every argument makes the deleted/None-ised kwarg observable. The repo's
        only exercise (test_prompt_ab_rollout_integration.py:265-279) drives both
        groups with truthy latency/score but asserts only
        `<group>_metrics.total_analyses == 1`, which no argument mutation changes —
        measured: swapping in all 13 variant bodies leaves that file 10/10 green,
        hence zero killed_by_draft here.
        """
        manager = _drive_rollout(
            ExperimentGroup.CONTROL, latency_ms=100.0, risk_score=50, has_error=True
        )
        manager.record_control_analysis.assert_called_once_with(
            latency_ms=100.0, risk_score=50, has_error=True
        )
        manager.record_treatment_analysis.assert_not_called()

    def test_treatment_arm_forwards_all_three_arguments(self, records):
        """Kills xǁNemotronAnalyzerǁrecord_rollout_analysis__mutmut_4, 11, 12, 13,
        14, 15, 16 (key 4 again via the swapped guard, plus the treatment-arm
        twins of the groups above).

        Same sites as above, treatment occurrences (nemotron_analyzer.py:1251-1253):
          11  latency_ms=None   12  risk_score=None   13  has_error=None
          14  latency_ms kwarg deleted  15  risk_score kwarg deleted
          16  has_error kwarg deleted

        Shipped behavior pinned (probe): the treatment recorder gets
        `call(latency_ms=175.5, risk_score=71, has_error=True)` and the control
        recorder stays uncalled. Both arms are asserted in both directions
        (called-with / not-called) so the guard mutant 4 — which routes a CONTROL
        camera to the treatment recorder and vice versa — fails in either drive.
        """
        manager = _drive_rollout(
            ExperimentGroup.TREATMENT, latency_ms=175.5, risk_score=71, has_error=True
        )
        manager.record_treatment_analysis.assert_called_once_with(
            latency_ms=175.5, risk_score=71, has_error=True
        )
        manager.record_control_analysis.assert_not_called()


# =========================================================================
# set_ab_test_config (2 keys) / _get_batch_coalescer (1) / set_rollout_manager (1)
# =========================================================================


class TestSetAbTestConfig:
    """TypeError text and the INFO line (nemotron_analyzer.py:828, 833-836)."""

    def test_type_error_text_is_the_shipped_sentence(self):
        """Kills xǁNemotronAnalyzerǁset_ab_test_config__mutmut_3.

        Site (L828): raise TypeError("config must be an ABTestConfig instance") ->
        "XXconfig must be an ABTestConfig instanceXX". The repo test
        (test_nemotron_analyzer.py:3866-3869) uses
        `pytest.raises(TypeError, match="config must be an ABTestConfig instance")`,
        and re.search happily finds that substring inside the XX-wrapped text — so
        it kills nothing. An exact string comparison is what separates them.
        """
        with pytest.raises(TypeError) as excinfo:
            _analyzer().set_ab_test_config({"invalid": "dict"})
        assert str(excinfo.value) == AB_TYPEERROR

    def test_info_line_reports_control_treatment_and_split(self, records):
        """Kills xǁNemotronAnalyzerǁset_ab_test_config__mutmut_9.

        Site (L833-836): the whole f-string message expression -> None, i.e. the
        INFO call survives with a None message. Shipped behavior pinned (probe):
        exactly one INFO record reading
        "A/B testing configured: control=v1, treatment=v2, split=42.0%" — note the
        "v" prefixes and the `:.1%` percent rendering of traffic_split, both of
        which the None mutant destroys. The repo's success test
        (test_nemotron_analyzer.py:3848-3863) asserts only that the two attributes
        are not None, so it is blind to the message. The config is asserted to
        have been installed as well, since the shipped function's side effect is
        the real contract the mutant leaves intact.
        """
        analyzer = _analyzer()
        config = ABTestConfig(
            control_version=1,
            treatment_version=2,
            traffic_split=0.42,
            model="nemotron",
            enabled=True,
        )
        analyzer.set_ab_test_config(config)
        infos = [r for r in records if r.levelno == logging.INFO]
        assert [r.getMessage() for r in infos] == [AB_MSG]
        assert analyzer._ab_config is config
        assert analyzer._ab_tester is not None


class TestGetBatchCoalescer:
    """The singleton fallback passes the analyzer's Redis client (1 key)."""

    def test_singleton_fallback_receives_the_analyzer_redis_client(self):
        """Kills xǁNemotronAnalyzerǁ_get_batch_coalescer__mutmut_2.

        Site (nemotron_analyzer.py:644):
        `return get_batch_coalescer(redis_client=self._redis)` -> `redis_client=None`.

        Shipped behavior pinned (probe: `call(redis_client=<sentinel>)`, result is
        the factory's return value): with no injected coalescer the singleton
        factory is called with EXACTLY one keyword argument carrying the
        analyzer's own client — that is how coalescing persists candidates. The
        mutant silently degrades to a Redis-less coalescer while still returning a
        coalescer, so no caller-visible behavior changes. There is no repo test
        for this method at all (`grep -rn _get_batch_coalescer backend/tests/` is
        empty), hence not killed_by_draft. The sentinel object is compared by
        identity, so a None (or any other client) fails.
        """
        analyzer = _analyzer()
        analyzer._batch_coalescer = None
        client = object()
        analyzer._redis = client
        with patch(
            "backend.services.nemotron_analyzer.get_batch_coalescer", autospec=True
        ) as factory:
            result = analyzer._get_batch_coalescer()
        factory.assert_called_once_with(redis_client=client)
        assert result is factory.return_value

    def test_injected_coalescer_short_circuits_the_factory(self):
        """Anchors the other arm of the shipped guard: an injected coalescer is
        returned verbatim and the singleton factory is never consulted. Kills
        nothing in this chunk (the guard's keys are not survivors here); pinned so
        the sibling test's premise — that the factory path is the fallback — is
        actually exercised by the shipped guard.
        """
        analyzer = _analyzer()
        injected = object()
        analyzer._batch_coalescer = injected
        analyzer._redis = object()
        with patch(
            "backend.services.nemotron_analyzer.get_batch_coalescer", autospec=True
        ) as factory:
            assert analyzer._get_batch_coalescer() is injected
        factory.assert_not_called()


class TestSetRolloutManager:
    """The INFO line names experiment, treatment share and active state (1 key)."""

    def test_info_line_reports_experiment_treatment_and_active(self, records):
        """Kills xǁNemotronAnalyzerǁset_rollout_manager__mutmut_3.

        Site (nemotron_analyzer.py:1165-1170): the whole f-string message
        expression -> None, i.e. the INFO call survives with a None message.
        Shipped behavior pinned (probe): exactly one INFO record reading
        "A/B rollout manager configured: experiment=chunk23-experiment,
        treatment=30%, active=True" — three manager-derived values interpolated
        into one sentence with a `:.0%` percent render, all three of which the
        mutant erases. treatment_percentage=0.30 is deliberate: `:.0%` of the 0.5
        default is "50%", which a sibling-format mutant could survive, whereas
        here the sentence is pinned byte-for-byte. The repo's exercise
        (test_prompt_ab_rollout_integration.py:156 and 452) asserts only
        `analyzer.get_rollout_manager() is manager`, so it never reads the
        message — hence not killed_by_draft. The assignment side effect is
        asserted too, because the mutant keeps it.
        """
        manager = ABRolloutManager(
            ABRolloutConfig(
                treatment_percentage=0.30,
                experiment_name="chunk23-experiment",
            ),
            AutoRollbackConfig(),
        )
        manager.start()
        analyzer = _analyzer()
        analyzer.set_rollout_manager(manager)
        infos = [r for r in records if r.levelno == logging.INFO]
        assert [r.getMessage() for r in infos] == [ROLLOUT_MSG]
        assert analyzer.get_rollout_manager() is manager
