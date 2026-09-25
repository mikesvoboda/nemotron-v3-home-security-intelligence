"""Batch-25 kill battery draft: backend/services/nemotron_analyzer.py survivors.

Targets the two pure-ish helpers with the highest survivor density measured
from mutants/backend/services/nemotron_analyzer.py.meta this session:
_parse_llm_response (59 survivors) and _validate_risk_data (53), plus
_extract_json_objects (43 module-level). Kill assertions come from the
adjudication data in /tmp/wp-batch25/vrd_matrix.json (input classes
empty_strings / score_101 / no_sr_no_level / fb_float / fb_str75 /
fb_str_neg5 / fb_str_150) — production behavior is asserted AS SHIPPED.

RED-CHECK (post-bank, on a lane): apply each mutant named in a docstring,
run the named test, expect failure. Mutant keys below are the OCCURRENCE-
TWIN keys from the meta (identity = occurrence order among identical
minus/plus shapes — carry all keys, never a remapped subset).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from backend.services.nemotron_analyzer import (
    NemotronAnalyzer,
    _extract_json_objects,
)


def _analyzer() -> NemotronAnalyzer:
    # __new__ skips the heavy __init__ (model/client wiring); the helpers
    # under test touch only arguments, never instance state.
    return NemotronAnalyzer.__new__(NemotronAnalyzer)


class TestParseLlmResponsePreambleTrim:
    """Preamble trim: cleaned_text = cleaned_text[first_brace:]."""

    def test_trim_slice_kills_first_brace_offset_mutants(self):
        # kills mutants that re-slice [first_brace:], [first_brace+1:],
        # [first_brace-1:], or replace find("{") with rfind("{") on the
        # trim line (occurrence: the trim inside the preamble branch)
        a = _analyzer()
        got = a._parse_llm_response('I think the answer is {"risk_score": 7}')
        assert got["risk_score"] == 7

    def test_empty_preamble_not_skipped_mutants(self):
        # kills mutants flipping `if preamble:` to `if not preamble:` or
        # `if preamble is not None:` (whitespace-only preamble must NOT be
        # treated as content; with `if preamble is not None:` the slice
        # still happens — killed via the off-by-one slice shape below)
        a = _analyzer()
        got = a._parse_llm_response('   {"risk_score": 3}')
        assert got == {"risk_score": 3}

    def test_first_brace_is_0_boundary(self):
        # first_brace > 0 -> >= 0 mutants still work here; combined with the
        # next test (brace at index>0 with EMPTY preamble after strip) the
        # >= mutant skips nothing... assert the shipped contract precisely:
        # text whose brace sits at index 0 must fast-path parse.
        a = _analyzer()
        got = a._parse_llm_response('{"risk_score": 5, "risk_level": "high"}')
        assert got["risk_score"] == 5
        assert got["risk_level"] == "high"


class TestParseLlmResponseThinkHandling:
    """Think-block strip + unterminated-think recovery."""

    def test_closed_think_stripped(self):
        # kills _THINK_PATTERN.sub("", ...) -> sub("X", ...) / pattern
        # mutants on the first sub line (line 4281 site)
        a = _analyzer()
        got = a._parse_llm_response('<think>reasoning here</think>\n{"risk_score": 8}')
        assert got["risk_score"] == 8

    def test_unterminated_think_recovers_from_brace(self):
        # kills `think_start = cleaned_text.find("<|im_start|>")` -> None/const
        # mutants (they TypeError inside find("{", think_start) or pick the
        # wrong brace) and the len(parts) > 1 threshold mutants
        a = _analyzer()
        got = a._parse_llm_response('<|im_start|>my reasoning {"risk_score": 5}')
        assert got["risk_score"] == 5

    def test_unterminated_think_brace_before_marker(self):
        # SHIPPED (probe 2026-09-24): unterminated think with a brace BEFORE
        # the marker returns the FIRST balanced object, not the later one —
        # the else-branch takes parts[-1] of the marker split and parses it.
        # Pins that shipped shape; mutants routing to find("{", think_start)
        # (returning the 9) die here.
        a = _analyzer()
        got = a._parse_llm_response('{"risk_score": 1}<|im_start|>x{"risk_score": 9}')
        assert got["risk_score"] == 1

    def test_split_marker_mutants(self):
        # split("<|im_start|>") -> split(None)/split() mutants: an unterminated
        # think with inner whitespace must still take the else-branch
        # (len(parts) == 1 on the marker split); whitespace split makes
        # len(parts) > 1 and returns the last WORD, not the JSON slice.
        a = _analyzer()
        got = a._parse_llm_response('<|im_start|>deep thought here {"risk_score": 6}')
        assert got["risk_score"] == 6


class TestParseLlmResponseFastPath:
    def test_fast_path_requires_risk_score(self):
        # kills `and "risk_score" in data` removal: a dict WITHOUT
        # risk_score must NOT be returned by the fast path — the balanced
        # extraction then finds the later object in text.
        a = _analyzer()
        with pytest.raises(ValueError):
            a._parse_llm_response('{"summary": "no score here"}')

    def test_fast_path_dict_check(self):
        # SHIPPED (probe 2026-09-24): a JSON ARRAY fails the fast-path
        # isinstance(data, dict) gate, then _extract_json_objects finds the
        # inner object -> returns it. Pins shipped; mutants that make the
        # fast path accept arrays (dict(list) -> TypeError / return list)
        # or that break the fallback extraction die here.
        a = _analyzer()
        assert a._parse_llm_response('[{"risk_score": 2}]') == {"risk_score": 2}


class TestParseLlmResponseBalancedExtraction:
    def test_nested_json_via_balanced_extractor(self):
        # kills off-by-one mutants in _extract_json_objects slicing
        # (results.append(text[i : j + 1]) -> j, i+1, etc.) with a nested
        # payload whose inner braces the single-level _JSON_PATTERN cannot
        # match — fast path fails on trailing text, extraction must succeed
        a = _analyzer()
        text = 'noise {"risk_score": 4, "evidence": {"zones": [{"z": 1}]}} tail'
        got = a._parse_llm_response(text)
        assert got["risk_score"] == 4
        assert got["evidence"]["zones"][0]["z"] == 1

    def test_string_literal_braces_skipped(self):
        # kills in_string toggle mutants (`elif c == '"': in_string = True`
        # / the escape skip `j += 2`): a "{" INSIDE a string must not open
        # a new depth level
        assert _extract_json_objects('{"a": "x{y"} {"risk_score": 9}') == [
            '{"a": "x{y"}',
            '{"risk_score": 9}',
        ]

    def test_escape_inside_string(self):
        # kills `if c == "\\" and j + 1 < n` -> `if c == "\\"` mutants:
        # an escaped quote inside a string must not close the string
        # shipped: \" stays inside the string, the { after it is string
        # content, the object closes at its real }; a mutant that drops the
        # j += 2 escape-skip treats \" as string-end, the { as a new depth
        # level, and the object never balances -> [] / wrong slices.
        s = '{"a": "q\\"{x"} {"risk": 1}'
        assert _extract_json_objects(s) == ['{"a": "q\\"{x"}', '{"risk": 1}']


class TestParseLlmResponseTruncation:
    def test_truncated_json_recovered(self):
        # kills the suffix tuple mutants (each literal in
        # ('"}', '"}', '" }', "}", '"}}}')) — this payload needs '"}'
        # exactly to balance
        a = _analyzer()
        got = a._parse_llm_response('{"risk_score": 5, "summary": "partial')
        assert got["risk_score"] == 5

    def test_no_json_raises_valueerror(self):
        a = _analyzer()
        with pytest.raises(ValueError):
            a._parse_llm_response("no json at all")


class TestValidateRiskDataFallbacks:
    """_validate_risk_data: strict -> lenient -> defaults ladder."""

    def test_well_formed_passes_strict(self):
        a = _analyzer()
        got = a._validate_risk_data(
            {"risk_score": 70, "risk_level": "medium", "summary": "s", "reasoning": "r"}
        )
        assert got["risk_score"] == 70
        assert got["risk_level"] == "medium"

    def test_score_101_clamped_by_lenient(self):
        # vrd class score_101: out-of-range strict-rejected -> lenient path
        # clamps to 100; kills clamp mutants (max(0,min(100,x)) -> 0/100/
        # no-clamp variants) in BOTH lenient and default paths
        a = _analyzer()
        got = a._validate_risk_data({"risk_score": 101})
        assert got["risk_score"] == 100

    def test_score_negative_clamped_low(self):
        a = _analyzer()
        got = a._validate_risk_data({"risk_score": -5})
        assert got["risk_score"] == 0

    def test_score_string_numeric_coerced(self):
        # fb_str75 / fb_str_neg5 / fb_str_150 classes: string scores take
        # the int(float(score)) branch; kills the isinstance(score, str)
        # branch mutants (removal, inversion, str->int direct)
        a = _analyzer()
        assert a._validate_risk_data({"risk_score": "75"})["risk_score"] == 75
        assert a._validate_risk_data({"risk_score": "-5"})["risk_score"] == 0
        assert a._validate_risk_data({"risk_score": "150"})["risk_score"] == 100

    def test_score_float_string_coerced(self):
        a = _analyzer()
        assert a._validate_risk_data({"risk_score": "72.5"})["risk_score"] == 72

    def test_score_bool_takes_int_branch(self):
        # SHIPPED (probe 2026-09-24): bool IS int under
        # `isinstance(score, int | float)` (line 49), so a bool score takes
        # the numeric branch — True -> 1, False -> 0 — it does NOT fall to
        # the default ladder. Pinned to the measured shipped values.
        a = _analyzer()
        assert a._validate_risk_data({"risk_score": True})["risk_score"] == 1
        assert a._validate_risk_data({"risk_score": False})["risk_score"] == 0

    def test_unparseable_score_uses_default_50(self):
        # kills the inner `except ValueError` / TypeError swallow mutants:
        # unparseable string score must fall to the DEFAULT 50 (no_sr path
        # would give a different level), NOT raise
        a = _analyzer()
        got = a._validate_risk_data({"risk_score": "abc"})
        assert got["risk_score"] == 50

    def test_score_list_uses_default(self):
        # fb_list_score: not int/float/str -> untouched -> default ladder
        a = _analyzer()
        got = a._validate_risk_data({"risk_score": [7]})
        assert got["risk_score"] == 50

    def test_no_sr_no_level_defaults(self):
        # the biggest killable class (no_sr_no_level, 26 of 51 adjudicated
        # mutants): empty dict -> full default ladder: score 50, inferred
        # level, canned summary/reasoning strings. Kills every mutant that
        # changes a default, the get() keys, or the canned strings.
        a = _analyzer()
        got = a._validate_risk_data({})
        assert got["risk_score"] == 50
        assert got["summary"] == "Risk analysis completed"
        assert got["reasoning"] == "No detailed reasoning provided"

    def test_default_path_preserves_available_summary(self):
        a = _analyzer()
        got = a._validate_risk_data({"risk_score": "abc", "summary": "keep me"})
        assert got["risk_score"] == 50
        assert got["summary"] == "keep me"
