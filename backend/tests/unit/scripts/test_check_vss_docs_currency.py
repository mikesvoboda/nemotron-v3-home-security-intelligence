"""Unit tests for scripts/check-vss-docs-currency.py.

ABOUTME: The stale-status guard for docs/vss-integration/ — the defect class where a meta-doc's own
Status line outlives the code (README:6 and AGENTS:6 both said "nothing implemented yet" for six
days after 4bfd6fa4 shipped the VLM path as the default). Tests build throwaway doc trees and assert
the gate passes when a dated correction naming the stale sentence precedes it, and fails, naming the
file, when it does not.

The two hazard cases are ones this gate had and lost: a correction that QUOTES the stale sentence
must not create a false failure (the quote is the first hit, so "is there a banner above it?" is
asked of the banner itself), and an unrelated dated banner at the top of a doc (00-context.md's
Errata line) must not be read as correcting a claim it never mentions.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "check-vss-docs-currency.py"

README = "docs/vss-integration/README.md"
AGENTS = "docs/vss-integration/AGENTS.md"
CONTEXT = "docs/vss-integration/00-context.md"

# The claim each doc carries, as the gate's CLAIMS table states it.
CLAIMS = {
    README: "nothing implemented yet",
    AGENTS: "Nothing is implemented yet",
    CONTEXT: "Research in progress",
}


def banner_for(claim: str) -> str:
    """A correction in the form the gate accepts: dated, and it names the sentence it retires."""
    return (
        f'> **Currency (2026-09-29) [V].** The line below ("{claim}") is stale. See the ledger.\n\n'
    )


def corrected_doc(rel: str) -> str:
    """A doc in the passing shape: dated banner naming the claim, then the claim standing below it."""
    claim = CLAIMS[rel]
    return banner_for(claim) + f"# {Path(rel).name}\n\n**{claim}.** The record of 2026-09-23.\n"


def make_tree(tmp_path: Path, *, banners: bool = True) -> Path:
    """A doc tree in the shape the gate reads: the false claim, optionally corrected above it."""
    tree = tmp_path / "docs" / "vss-integration"
    tree.mkdir(parents=True)
    stale = {
        README: "# VSS Integration\n\n> **Status (2026-09-23): design approved, nothing implemented yet.**\n",
        AGENTS: "# Agent Guide\n\n**Nothing is implemented yet.** Pick your branch.\n",
        CONTEXT: "# Context\n\n**Status:** Research in progress. Nothing here is a commitment.\n",
    }
    for rel, body in stale.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((banner_for(CLAIMS[rel]) if banners else "") + body, encoding="utf-8")
    return tmp_path


def run_gate(tree: Path) -> subprocess.CompletedProcess[str]:
    # Assert existence HERE, not per-test: a missing script exits nonzero, which would make
    # every TestFails case pass for the wrong reason.
    assert SCRIPT.is_file(), f"{SCRIPT} is missing — the gate itself must exist"
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), str(tree)],
        capture_output=True,
        text=True,
        check=False,
    )


class TestPasses:
    def test_dated_banner_above_the_claim_passes(self, tmp_path: Path) -> None:
        tree = make_tree(tmp_path)
        result = run_gate(tree)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_doc_with_no_false_claim_needs_no_banner(self, tmp_path: Path) -> None:
        tree = make_tree(tmp_path, banners=False)
        for rel in (README, AGENTS, CONTEXT):
            (tree / rel).write_text(
                f"# {Path(rel).name}\n\nCurrent as of the ledger.\n", encoding="utf-8"
            )
        result = run_gate(tree)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_banner_that_quotes_the_claim_does_not_defeat_the_gate(self, tmp_path: Path) -> None:
        """Good prose quotes the sentence it retires — and then the quote is the claim's first hit.

        Asked naively ("is a banner above the first hit?") the question lands on the banner itself
        and a correctly-written correction fails the gate.
        """
        tree = make_tree(tmp_path, banners=False)
        (tree / AGENTS).write_text(
            banner_for(CLAIMS[AGENTS])
            + f"# Agent Guide\n\n**{CLAIMS[AGENTS]}.** Pick your branch.\n",
            encoding="utf-8",
        )
        for rel in (README, CONTEXT):
            (tree / rel).write_text(corrected_doc(rel), encoding="utf-8")
        result = run_gate(tree)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_claim_split_across_banner_lines_still_counts_as_named(self, tmp_path: Path) -> None:
        """The docs are prose-wrapped: a quoted sentence breaks mid-phrase and must still match."""
        tree = make_tree(tmp_path, banners=False)
        (tree / README).write_text(
            "# VSS Integration\n\n"
            "> **Currency (2026-09-29) [V].** The line below was true when written:\n"
            "> design approved, nothing\n> implemented yet.\n\n"
            "> **Status (2026-09-23): design approved, nothing implemented yet.**\n",
            encoding="utf-8",
        )
        for rel in (AGENTS, CONTEXT):
            (tree / rel).write_text(corrected_doc(rel), encoding="utf-8")
        result = run_gate(tree)
        assert result.returncode == 0, result.stdout + result.stderr


class TestFails:
    def test_uncorrected_claim_fails_and_names_the_file(self, tmp_path: Path) -> None:
        tree = make_tree(tmp_path, banners=False)
        result = run_gate(tree)
        assert result.returncode != 0
        assert README in result.stdout

    def test_banner_below_the_claim_fails(self, tmp_path: Path) -> None:
        """Order is the whole point: a correction the reader meets after the lie corrects nothing."""
        tree = make_tree(tmp_path, banners=False)
        (tree / README).write_text(
            "# VSS Integration\n\n"
            "> **Status (2026-09-23): design approved, nothing implemented yet.**\n\n"
            + banner_for(CLAIMS[README])
            + "late, so useless.\n",
            encoding="utf-8",
        )
        result = run_gate(tree)
        assert result.returncode != 0
        assert README in result.stdout

    def test_undated_banner_is_not_a_correction(self, tmp_path: Path) -> None:
        tree = make_tree(tmp_path, banners=False)
        (tree / AGENTS).write_text(
            "# Agent Guide\n\n> **Currency.** Things changed.\n\n**Nothing is implemented yet.**\n",
            encoding="utf-8",
        )
        result = run_gate(tree)
        assert result.returncode != 0
        assert AGENTS in result.stdout

    def test_a_banner_that_ATE_the_claim_is_not_a_correction(self, tmp_path: Path) -> None:
        """The frozen-prose rule has teeth: the stale sentence stays, the banner precedes it.

        Deleting the line and quoting it in the banner reads well and is out of bounds — this
        directory is the research record (docs/vss-integration/AGENTS.md, "Patterns").
        """
        tree = make_tree(tmp_path, banners=False)
        claim = CLAIMS[CONTEXT]
        (tree / CONTEXT).write_text(
            "# Context\n\n" + banner_for(claim) + "**Status:** superseded by the spec.\n",
            encoding="utf-8",
        )
        result = run_gate(tree)
        assert result.returncode != 0
        assert CONTEXT in result.stdout
        assert "ONLY inside the dated banner" in result.stdout

    def test_an_unrelated_dated_banner_is_not_a_correction(self, tmp_path: Path) -> None:
        """00-context.md's real hazard: an Errata banner about OTHER claims sat above the status
        line and satisfied a gate that only asked "is any dated banner above it?"."""
        tree = make_tree(tmp_path, banners=False)
        (tree / CONTEXT).write_text(
            "# Context\n\n"
            "> **Errata (2026-09-23):** E2, E3 correct claims in this document.\n\n"
            "**Status:** Research in progress. Nothing here is a commitment.\n",
            encoding="utf-8",
        )
        result = run_gate(tree)
        assert result.returncode != 0
        assert CONTEXT in result.stdout


class TestRepoItself:
    def test_the_real_tree_is_clean(self) -> None:
        """The gate's real job: the shipped tree carries a dated correction over each stale line."""
        result = run_gate(REPO_ROOT)
        assert result.returncode == 0, result.stdout + result.stderr
