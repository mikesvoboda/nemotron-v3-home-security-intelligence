#!/usr/bin/env python3
"""Tests for scripts/validate_docs symbol-context inference (VD-1).

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_validate_docs_symbol_context.py -q

WHY THIS SUITE EXISTS. The AST tier (level 2) checks a citation against a
symbol name INFERRED from the prose around it: `_extract_symbol_from_context`
takes a +/-100-character window around each backticked cite and
SYMBOL_CONTEXT_PATTERN's first keyword-adjacent identifier wins. The pattern
had no leading word boundary and no class filter, and the window was used both
to FIND and to JUDGE the match, so ordinary English became required symbols.
Every false inference is a hard `Symbol '<x>' not found` ERROR, and because
cli.py keeps only the most severe result per citation (:261-267), the false
error REPLACES that citation's healthy level-1 pass in the report: prose edits
turn unrelated, correct citations red.

Measured over docs/reference + docs/uplevel at 1980ae451: the whole AST tier
emits 14 rows, of which 10 are these false positives and 4 are genuine line
drift. Both halves are pinned here — the negatives per defect class, and
positives so a filter that rejects everything cannot pass. Prose is verbatim
from the shipped tree (feature-inventory.md rows F-033/F-125 at ca80efb2e;
backend-entry-points.md lines 506/752/769/1274/1369/1422/1436/1533).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.validate_docs.config import SYMBOL_CONTEXT_PATTERN
from scripts.validate_docs.parsers.markdown import _extract_symbol_from_context

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CITE = "`backend/api/routes/summaries.py:150`"
WINDOW = 100  # the extractor's documented default


def infer(prose_before_cite: str) -> str | None:
    """Invoke the extractor exactly as its caller does: cite offset in content."""
    content = prose_before_cite + CITE + " trailing prose keeps the window open."
    return _extract_symbol_from_context(content, content.index(CITE))


# ==========================================================================
# Class 1 — mid-word keyword match. `bullet` ends in `let`; the shipped
# pattern matched "let TEXT" INSIDE the word and demanded a symbol TEXT.
# Verbatim feature-inventory.md row 159: sym='TEXT' -> SummaryCards.tsx:99.
# ==========================================================================


def test_midword_let_does_not_infer_a_symbol() -> None:
    assert infer("instead of the SAME endpoint, and bullet TEXT is asserted ") is None


def test_pattern_anchors_the_keyword_at_a_word_boundary() -> None:
    # The pattern itself is the unit under test: a keyword must start a word.
    assert SYMBOL_CONTEXT_PATTERN.search("bullet TEXT") is None
    assert SYMBOL_CONTEXT_PATTERN.search("the class CacheEntry").group(1) == "CacheEntry"


# ==========================================================================
# Class 2 — English captured as a symbol. These are prose, not code, and the
# discriminator is the author's own mark: a symbol reference is written in
# backticks, an English word is not.
#   "same repo method with `\"untrusted\"`"  -> sym='with'   (entry-points:506)
#   "the **only** method of this service"   -> sym='of'     (entry-points:1274)
#   "the same contract-drift class as OP-1's F-158" -> sym='as' (inv row 291)
# ==========================================================================


def test_prose_with_is_not_a_symbol() -> None:
    assert infer('same repo method with `"untrusted"` (:749) → ') is None


def test_prose_of_is_not_a_symbol() -> None:
    assert infer("the **only** method of this service any route reaches (") is None


def test_prose_as_is_not_a_symbol() -> None:
    assert infer("— the same contract-drift class as OP-1's F-158 (the legacy ") is None


def test_word_after_class_that_is_not_a_code_span_is_not_a_symbol() -> None:
    # Verbatim from backend-entry-points.md:1533's neighbour: on the real line
    # `:208` is its own span, so "a class docstring" sits in prose. The shipped
    # window started mid-line, which paired the closing backtick with a later
    # opening one and made the prose LOOK like code -> sym='docstring'.
    assert infer("zero non-test callers (the `:208` hit is a class docstring); ") is None


# ==========================================================================
# Class 3 — a file PATH's first segment captured as a symbol.
#   "(class `backend/services/reid_service.py:339`)" -> sym='backend'
#   (entry-points:752 and :769; three rows)
# ==========================================================================


def test_path_segment_after_class_is_not_a_symbol() -> None:
    assert infer("→ `ReIdentificationService` (class ") is None


def test_window_clipped_path_is_not_a_symbol() -> None:
    # Reproduces sym='bac' (entry-points:752) and sym='b' (:769): the keyword
    # pair sits AFTER the cite, so the window's right edge cuts the identifier
    # mid-token and the extractor judges the fragment, not the word. The pad is
    # computed, not guessed, so the clip is guaranteed by construction.
    tail = "(class `backend/services/x.py:9`)"
    clip = "(class `ba"  # what the window must end with: 'backend' cut to 'ba'
    # The window is [pos-100, pos+100) and the keyword pair sits AFTER the
    # cite, so the pad is whatever leaves exactly `clip` at the right edge.
    pad = " " * (WINDOW - len(CITE) - len(clip))
    assert len(pad) > 0, "fixture too wide for the extractor's window"
    content = "a lead-in sentence. " + CITE + pad + tail
    pos = content.index(CITE)
    window_tail = content[pos : pos + WINDOW]
    assert window_tail.endswith("(class `ba"), (
        "fixture drifted: window tail is "
        + repr(window_tail[-14:])
        + " — the clip must fall inside 'backend' for this test to mean anything"
    )
    assert _extract_symbol_from_context(content, pos) is None


# ==========================================================================
# POSITIVE CONTROLS — the tier's only 4 true findings, verbatim, all genuine
# line drift. A fix that stops inferring these has deleted coverage, not
# removed noise.
# ==========================================================================


def test_def_inside_a_code_span_still_infers_its_symbol() -> None:
    assert infer("Lifespan is `backend/main.py:781` (`async def lifespan`); ") == "lifespan"


def test_class_inside_a_code_span_still_infers_its_symbol() -> None:
    assert infer("`class _ThreadWatchdog(threading.Thread)` ") == "_ThreadWatchdog"


def test_legit_def_still_infers_its_symbol() -> None:
    assert infer("the route calls `def fetch_state` before returning ") == "fetch_state"


# ==========================================================================
# Severity contract — an INFERRED symbol is a guess about prose the author did
# not write, so it may warn but must never fail a citation. Author-declared
# symbols (the `path:symbol:line` form, markdown.py's frontmatter/part-2 path)
# keep ERROR severity: those are claims.
# ==========================================================================


def test_inferred_symbol_mismatch_is_advisory_not_a_failure() -> None:
    from scripts.validate_docs.config import Citation, CitationStatus
    from scripts.validate_docs.validators.ast_python import validate_python_ast

    bogus = Citation(
        file_path="backend/main.py",
        start_line=1,
        end_line=None,
        symbol_name="definitely_not_a_real_symbol_xyz",
        doc_file="docs/reference/backend-entry-points.md",
        doc_line=1,
        raw_text="`backend/main.py:1`",
        symbol_inferred=True,
    )
    result = validate_python_ast(bogus, PROJECT_ROOT)
    assert result.status == CitationStatus.WARNING, (
        "an inferred symbol that fails to resolve must be advisory: the author "
        "never wrote this name, so it cannot be what blocks a PR"
    )


def test_author_declared_symbol_mismatch_still_fails() -> None:
    # The `path:symbol:line` citation form is a claim the author typed; it
    # keeps ERROR severity. A fix that downgrades EVERY symbol mismatch has
    # disarmed the tier's real check, not just the guessed-name artifact.
    from scripts.validate_docs.config import Citation, CitationStatus
    from scripts.validate_docs.validators.ast_python import validate_python_ast

    declared = Citation(
        file_path="backend/main.py",
        start_line=1,
        end_line=None,
        symbol_name="definitely_not_a_real_symbol_xyz",
        doc_file="docs/reference/backend-entry-points.md",
        doc_line=1,
        raw_text="`backend/main.py:definitely_not_a_real_symbol_xyz:1`",
        symbol_inferred=False,
    )
    result = validate_python_ast(declared, PROJECT_ROOT)
    assert result.status == CitationStatus.ERROR


if __name__ == "__main__":
    raise SystemExit(re and __import__("pytest").main([__file__, "-q"]))
