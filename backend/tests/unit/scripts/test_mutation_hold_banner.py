"""Uplevel O1.1: the mutation hold is stated where a reader meets the superseded docs.

The campaign that climbed toward 85% is held after M54 and superseded by
docs/uplevel/01-mutation-policy.md (UR-2, UR-7). "Land a banner" is only real if a
check fails when a banner is removed, so this test reads the four documents the hold
retires and pins that each opens, in its first lines, pointing at the policy; the L
ledger additionally says no new mutation rows are taken. (01 §M5.)

The four are read from the repo tree, not a fixture: a banner is a fact about a
specific committed file. mutmut's mutant home carries no docs/ copy (pyproject.toml,
the copy-list comment), so the whole module skips when a target is absent rather than
aborting the coverage gather the way a bare assert would (the hazard documented at
backend/tests/unit/scripts/test_check_vss_docs_currency.py:508).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
POLICY = "docs/uplevel/01-mutation-policy.md"

# (relative path, how many opening lines the banner must live within). The three
# superseded docs landed their banners with the design; the L ledger's is O1.1's add.
SUPERSEDED_DOCS = [
    ("docs/plans/2026-09-29-mutation-ladder-85-goal-prompt.md", 8),
    ("docs/goal-prompt-mutation-80-2026-09-22.txt", 3),
    ("docs/goal-prompt-mutation-80-2026-09-23.txt", 3),
    ("docs/plans/2026-09-12-context-map-doc-updates.md", 8),
]

ALL_TARGETS = [POLICY, *(path for path, _ in SUPERSEDED_DOCS)]

# The mutant home has no docs/ tree; a reader there has nothing to check.
pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        not all((REPO_ROOT / rel).exists() for rel in ALL_TARGETS),
        reason="docs/ tree absent (mutmut's mutant home): no banner to check",
    ),
]


def opening(rel: str, lines: int) -> str:
    """The first `lines` lines of a doc, whitespace runs collapsed so a banner wrapped
    across source lines still matches a substring check (as the vss currency gate does)."""
    head = "\n".join((REPO_ROOT / rel).read_text(encoding="utf-8").splitlines()[:lines])
    return re.sub(r"\s+", " ", head)


@pytest.mark.parametrize(("rel", "span"), SUPERSEDED_DOCS)
def test_a_superseded_doc_opens_pointing_at_the_policy(rel: str, span: int) -> None:
    """Each retired doc's first lines name the policy that replaces it (01 §M5)."""
    assert POLICY in opening(rel, span), f"{rel} does not open pointing at {POLICY}"


def test_the_l_ledger_opens_saying_it_takes_no_new_mutation_rows() -> None:
    """The L ledger keeps its rows as history but takes no new ones (01 §M5, UR-7)."""
    ledger = "docs/plans/2026-09-12-context-map-doc-updates.md"
    head = opening(ledger, 10).lower()
    assert "no new mutation" in head, f"{ledger} does not say it takes no new mutation rows"
