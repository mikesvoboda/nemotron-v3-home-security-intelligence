#!/usr/bin/env python3
"""Anti-rot (VD-1b): the SHIPPED pipeline's emitted symbol must agree with an
independent arm that re-derives the fence set itself.

Run explicitly; outside testpaths (like every scripts/test_*.py gate suite):

    uv run python -m pytest scripts/test_pipeline_vs_independent_arm.py -q

WHY THIS SUITE EXISTS. The shipped extractor hoists the code-fence scan out of
its per-citation loop (`markdown.py:282`, one `_fenced_ranges(body)` per
document) and passes the result down as `fences=body_fences` (`:300`). The
sibling suite `test_the_hoisted_fence_scan_still_judges_every_citation` compares
the extractor's OWN arms per position but never calls
`extract_markdown_citations` — so the shipped call site's `fences=` argument is
pinned by nothing, and the hoist can be gutted three ways (`fences=[]`, sweep
deleted, `fences[1:]`) while that guard stays green. This file closes that hole:
at every citation whose answer actually reads the fence set, the symbol the
pipeline emitted must equal what an independent self-sweeping arm concludes.

Written by the VD-1 reviewer (vd1-review-3) as a mutation-verified handoff; the
three arms below were re-reddened on this tree before shipping, and the numbers
in the failure messages are those re-measurements, not the reviewer's.

The expensive self-sweep arm is paid ONLY at fence-decisive positions — same
doctrine as the shipped guard, and safe: `[1:]` and `[]` can only ever REMOVE
fence evidence, so every position they change is already decisive.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.validate_docs.parsers.markdown as md
from scripts.validate_docs.config import looks_like_host_address

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_the_shipped_pipeline_agrees_with_an_independent_fence_arm() -> None:
    mismatches: list[str] = []
    drift: list[str] = []
    compared = dependents = 0
    for doc in sorted((PROJECT_ROOT / "docs").rglob("*.md")):
        content = doc.read_text(encoding="utf-8")
        _, body = md._extract_frontmatter(content)
        positions = [
            m.start()
            for m in md.INLINE_CITATION_PATTERN.finditer(body)
            if not looks_like_host_address(m.group(1))
        ]
        if not positions or "```" not in body:
            continue
        fences = md._fenced_ranges(body)
        shipped = [
            c
            for c in md.extract_markdown_citations(content, str(doc))
            if c.raw_text.startswith("`")
        ]
        if len(shipped) != len(positions):
            drift.append(f"{doc.relative_to(PROJECT_ROOT)}: {len(positions)} positions vs {len(shipped)} cites")
            continue
        for pos, cite in zip(positions, shipped):
            with_fences = md._extract_symbol_from_context(body, pos, fences=fences)
            bare = md._extract_symbol_from_context(body, pos, fences=[])
            if with_fences == bare:
                continue  # the answer never reads the fence set
            dependents += 1
            independent = md._extract_symbol_from_context(body, pos)  # self-sweep = pre-fix semantics
            compared += 1
            if cite.symbol_name != independent:
                mismatches.append(
                    f"{doc.relative_to(PROJECT_ROOT)} pos={pos} shipped={cite.symbol_name!r} independent={independent!r}"
                )
    assert not drift, f"arm alignment drifted (do NOT trust a silent skip): {drift[:4]}"
    assert dependents >= 10, f"only {dependents} fence-dependent citations — corpus drifted, guard is vacuous"
    assert compared == dependents
    assert not mismatches, f"pipeline disagrees at {len(mismatches)} positions: {mismatches[:5]}"
