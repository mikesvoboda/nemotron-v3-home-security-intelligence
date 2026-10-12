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

Base evidence, measured against origin/main with THIS 17-test suite (the PR body first
quoted "9F/3P", which reproduces no arm; an earlier note said "10F/3P", which the suite has
since outgrown — these counts move with the test count, so they are bound to THIS revision,
not a standing property). Reverting BOTH config.py and parsers/markdown.py to main: 13 failed
/ 4 passed, the 4 green being exactly the positive controls (legit_def, def_inside_a_code_span,
class_inside_a_code_span, fenced_signature). Reverting only parsers/markdown.py (retaining
config's word-boundary anchor): 8 failed / 9 passed. Removing ONLY the anchor from config's
SYMBOL_CONTEXT_PATTERN: 1 failed (test_pattern_anchors_the_keyword_at_a_word_boundary) —
mid-word's own specimen stays green because the code-span rule now also refuses it, so that
class has two guards over one example. The suite is load-bearing in every arm.

Census re-measured on THIS tree after the fix landed: over docs/reference +
docs/uplevel the AST tier reports 5 rows, all warnings (pre-fix, at 1980ae451, the
same command reported 14 rows, of which 10 were false positives — those 10 are the
inferences this suite pins out). Negatives are pinned per defect class and positives
so a filter that rejects everything cannot pass. Fixture prose is verbatim from the
shipped tree (feature-inventory.md rows F-033/F-125 at ca80efb2e; backend-entry-points.md
lines 506/752/769/1274/1369/1422/1436/1533) EXCEPT the `def fetch_state` positive
control, whose name is constructed to fit the rule — marked at its test.
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
    # Verbatim tail of feature-inventory.md row 159 (an earlier draft truncated the
    # prefix and the header's "verbatim" claim was then only half true — the shipped
    # row reads "…against a fresh Node read of the SAME endpoint, and bullet TEXT…").
    assert infer("against a fresh Node read of the SAME endpoint, and bullet TEXT is asserted ") is None


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
    # CONSTRUCTED control (name invented to fit the rule; NOT verbatim tree prose)
    # — proves the rule accepts a backticked def at all. The verbatim positives are
    # the two above them (`async def lifespan`, `class _ThreadWatchdog(...)`).
    assert infer("the route calls `def fetch_state` before returning ") == "fetch_state"


def test_fenced_signature_after_a_cite_is_code_evidence() -> None:
    # The architecture-doc convention is cite, then a fenced signature (390 cite→fence
    # pairs across 70 docs). A fence is the author's STRONGEST code mark; a rule that
    # accepts same-line backticks but not the fence below the cite silently retired
    # real drift — e.g. docs/architecture/background-services/file-watcher.md:296
    # cites file_watcher.py:257-288 while `def is_valid_video` is really at :306.
    content = (
        "Basic existence and size check (`backend/services/file_watcher.py:257-288`):\n"
        "\n"
        "```python\n"
        "def is_valid_video(file_path: str) -> bool:\n"
        '    """docstring"""\n'
        "```\n"
    )
    cite = "`backend/services/file_watcher.py:257-288`"
    assert _extract_symbol_from_context(content, content.index(cite)) == "is_valid_video"


def test_prose_inside_a_fence_is_still_judged_by_the_same_rules() -> None:
    # A fence is code evidence, not a licence: a keyword that only reads as English
    # must not become a symbol just because a fence is nearby.
    content = (
        "See (`backend/services/file_watcher.py:257-288`):\n"
        "\n"
        "```\n"
        "the class of service is selected by the router\n"
        "```\n"
    )
    cite = "`backend/services/file_watcher.py:257-288`"
    assert _extract_symbol_from_context(content, content.index(cite)) is None


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


def test_the_parser_itself_sets_the_inferred_flag_end_to_end() -> None:
    # The severity contract above hands `symbol_inferred` to Citation by hand, so it
    # pins how the VALIDATOR reacts to a flag and never pins the PARSER setting it.
    # Mutation-proved: with markdown.py's `symbol_inferred=symbol_name is not None`
    # replaced by False — or polarity-flipped — the whole suite still passed 13, while
    # the shipped cite at docs/reference/backend-entry-points.md:1436 scored ERROR
    # again, which is the exact defect this PR exists to close. This test runs the real
    # document through the real parser, so deleting or inverting that one line REDS it.
    from scripts.validate_docs.parsers.markdown import extract_markdown_citations

    doc = "docs/reference/backend-entry-points.md"
    content = (PROJECT_ROOT / doc).read_text(encoding="utf-8")
    inferred = [
        c
        for c in extract_markdown_citations(content, doc)
        if c.symbol_name and c.doc_line == 1436
    ]
    assert inferred, "fixture drifted: line 1436 no longer carries an inferred-symbol cite"
    assert all(c.symbol_inferred for c in inferred), (
        "a name the author never typed must arrive marked as inferred, or the "
        "severity split silently reverts to ERROR-on-English"
    )


def test_frontmatter_source_refs_arrive_declared_not_inferred() -> None:
    # The companion to the test above, and the one it does NOT cover. That test pins the
    # PROSE producer (markdown.py's `symbol_inferred=symbol_name is not None`). Declared
    # symbols come from a different producer — YAML `source_refs:` in frontmatter, whose
    # `path:symbol:line` entries the parser builds WITHOUT passing symbol_inferred at all,
    # so they ride the Citation dataclass DEFAULT of False. Nothing pinned that default.
    # Mutation-proved the hole: flipping `Citation.symbol_inferred: bool = False` to True
    # left this whole suite green, while across docs/ it silently downgraded 2 REAL
    # author-declared AST errors (docs/architecture/overview.md:21 `AuditService` and
    # docs/developer/resilience-patterns.md:8 `DANGEROUS_PATTERNS`) from ERROR to WARNING.
    # A declared symbol is the tier's one legitimate hard failure; its severity must not
    # depend on a default nobody asserted. This test runs a real document through the real
    # parser, so flipping that default REDS it.
    from scripts.validate_docs.parsers.markdown import extract_markdown_citations

    doc = "docs/developer/resilience-patterns.md"
    content = (PROJECT_ROOT / doc).read_text(encoding="utf-8")
    declared = [
        c
        for c in extract_markdown_citations(content, doc)
        if c.file_path.endswith("prompt_sanitizer.py") and c.symbol_name == "DANGEROUS_PATTERNS"
    ]
    assert declared, "fixture drifted: DANGEROUS_PATTERNS is no longer a frontmatter source_ref"
    assert all(c.symbol_inferred is False for c in declared), (
        "a frontmatter source_ref is a name the author typed; if it arrives marked as "
        "inferred, every declared-symbol miss is downgraded to a warning and the tier "
        "stops failing anything the author actually claimed"
    )


if __name__ == "__main__":
    raise SystemExit(re and __import__("pytest").main([__file__, "-q"]))
