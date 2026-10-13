"""Unit tests for scripts/check-uplevel-cites.py — the uplevel cite gate (#7064, UR-89 follow-up).

ABOUTME: ops-b's round-3 finding on #7054 was that the cite instruments were audit-only:
"no scripts/test_uplevel_cites.py exists… until it lands nothing in CI pins these cites,
which is exactly how round 1 shipped 9 false redirects." This file is that missing pin. It
runs the gate on the REAL tree (the green arm — rules.md's repaired cites must stay true)
and on THROWAWAY trees with planted defects (the can-fail arms — a gate that has never
failed on a planted defect has never been shown to be able to fail).

The mutation trees are copies of the real docs/uplevel and data dir under tmp_path; the
gate is pointed at them by argv and READS them — it never writes. Each planted arm names
the defect class #7054 actually shipped: a cite to a section that never existed, a
CAPITALISED prose paraphrase (case-insensitive matching would bless it), a "deleted"
file that is live again, and text written into an emptiness-pinned section (the pin that
forces a moved claim to move its cite).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# timeout 30s (not the 5s tier default): every test here spawns an interpreter and the
# mutation arms copytree the whole corpus (~464KB docs/uplevel + ~200KB snapshot); the
# coverage-gate wrapper documents three CI reds that were pytest-timeout flakes on -n 8
# load, not gate failures (test_check_test_coverage_gate.py).
pytestmark = [pytest.mark.unit, pytest.mark.timeout(30)]

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "check-uplevel-cites.py"
DATA = REPO_ROOT / "backend/tests/unit/scripts/data/uplevel-cites"


def run_gate(root: Path) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), f"{SCRIPT} is missing — the gate itself must exist"
    return subprocess.run(  # noqa: S603  # intentional - tests our own script
        [sys.executable, "-I", str(SCRIPT), str(root)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def make_tree(tmp_path: Path) -> Path:
    """A copy of the live corpus + snapshot data the gate reads; tests defect it, gate reads."""
    root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "docs/uplevel", root / "docs/uplevel")
    shutil.copytree(DATA, root / DATA.relative_to(REPO_ROOT))
    return root


class TestRealTree:
    def test_the_shipped_corpus_passes(self) -> None:
        """The gate every CI shard runs: rules.md's cites resolve and their homes carry
        the claim, at the head under test. Green here is what #7054 rounds 1-3 earned."""
        result = run_gate(REPO_ROOT)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "ALL ULEVEL CITES RESOLVE AND ENTAIL" in result.stdout

    def test_witness_totals_are_printed_not_silent(self) -> None:
        """A resolver that prints nothing about what it saw can 'pass' on an empty scan
        (vacuous-comparison class). The run must state its corpus size and a NON-ZERO count
        of each cite kind, so a run that resolved almost nothing cannot read as green."""
        out = run_gate(REPO_ROOT).stdout
        # floors, not exact counts: docs/uplevel grows legitimately and an exact pin would
        # red the next package doc for no reason. The snapshot IS pinned exactly — it is
        # committed provenance data; a seventh file is a deliberate edit, worth a tripwire.
        live = re.search(r"corpus (\d+) live files", out)
        assert live and int(live.group(1)) >= 15, f"suspiciously small live corpus: {out!r}"
        assert "snapshot 6 files" in out
        resolver = next(ln for ln in out.splitlines() if ln.startswith("resolver:"))
        # Pull each "<N> <kind>" straight off the witness line — no positional arithmetic,
        # which is how a mis-split silently reads the wrong column as a confident number.
        # NOTE findall's tuple order is (count, kind); dict(pairs) would silently key by
        # the NUMBER — the slot-swap trap. Build the dict explicitly in the wanted order.
        found = {
            kind: count
            for count, kind in re.findall(
                r"(\d+) (live sections|claims|snapshot sections)", resolver
            )
        }
        assert set(found) == {"live sections", "claims", "snapshot sections"}, found
        assert all(int(n) > 0 for n in found.values()), f"resolver located 0 of a kind: {found}"

    def test_gate_is_collected_by_ci(self) -> None:
        """The green arm only gates if CI runs this file. ci.yml shards backend/tests/unit/,
        which collects it; if that shard step is removed the pin must say so in the one
        place a reader of ci.yml cannot miss (this test itself then stops running)."""
        ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text()
        assert "pytest backend/tests/unit/ \\" in ci


class TestFixtureRegister:
    def test_snapshot_and_fixture_are_committed_and_nontrivial(self) -> None:
        snaps = sorted(DATA.glob("*.md"))
        assert len(snaps) == 6 and all(p.stat().st_size > 1000 for p in snaps)
        fixture = json.loads((DATA / "entailments.json").read_text())
        assert len(fixture) >= 20
        pins = [c for c in fixture if not c.get("expect_present", True)]
        assert len(pins) >= 3
        # the census control (UR-51d): if the matcher ever says True for ALL FOUR headers
        # including this one, it is matching nothing. Deleting the control silently
        # un-fails the whole snapshot arm — pin its presence here.
        assert any(c["rule"] == "UR-51d-control" for c in pins)


class TestPlantedDefects:
    """Each arm plants the exact defect #7054 shipped (or would have shipped) and requires
    the gate to fail, naming it. An arm that does not fire is not a control."""

    def test_cite_to_a_section_that_never_existed_fires(self, tmp_path: Path) -> None:
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(rules.read_text() + '\nSee roles/lane.md "Section Nobody Wrote".\n')
        result = run_gate(root)
        assert result.returncode == 1
        assert "Section Nobody Wrote" in result.stdout

    def test_capitalised_prose_paraphrase_fires(self, tmp_path: Path) -> None:
        """The case-sensitivity leniency: the real prose is 'independently'; a cite quoting
        'Independently' must NOT be blessed by case-folded matching."""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(rules.read_text() + '\nPer roles/lane.md "Independently".\n')
        result = run_gate(root)
        assert result.returncode == 1
        assert "Independently" in result.stdout

    def test_deleted_file_alive_again_fires(self, tmp_path: Path) -> None:
        """rules.md cites `the deleted 50-coordination.md`; if the file returns, the
        provenance is a lie and the gate must say so (two-sided death proof)."""
        root = make_tree(tmp_path)
        (root / "docs/uplevel/50-coordination.md").write_text("# Back from the dead\n")
        result = run_gate(root)
        assert result.returncode == 1
        assert "NOT dead" in result.stdout

    def test_text_written_into_an_emptiness_pinned_section_fires(self, tmp_path: Path) -> None:
        """UR-91-c4 pins lane.md 'Reviewing another lane's PR' EMPTY of 'reviewed again'.
        Write that text there and the pin must fire, forcing cite and claim to move together."""
        root = make_tree(tmp_path)
        lane = root / "docs/uplevel/roles/lane.md"
        text = lane.read_text()
        anchor = "## Reviewing another lane's PR\n"
        assert anchor in text, "fixture drifted: the pinned section moved"
        # both UR-91-c4 needles, verbatim, in the pinned-empty section
        inject = "\nThe head is reviewed again post merge resolution.\n"
        lane.write_text(text.replace(anchor, anchor + inject))
        result = run_gate(root)
        assert result.returncode == 1
        assert "must NOT say" in result.stdout

    def test_snapshot_prose_quote_still_resolves_case_sensitively(self, tmp_path: Path) -> None:
        """Positive control for the prose arm: the real `corrects … "makes no decisions"`
        cite (lowercase, verbatim) resolves — so the capitalised arm above fails for CASE,
        not because the prose fallback is dead."""
        result = run_gate(make_tree(tmp_path))
        assert result.returncode == 0
        prose = re.search(r"snapshot sections \+ (\d+) phrases", result.stdout)
        assert prose and int(prose.group(1)) >= 1, "prose fallback resolved nothing — dead arm"


class TestSetupRefusals:
    def test_small_corpus_refuses_instead_of_passing(self, tmp_path: Path) -> None:
        """Empty/undersized scans report as SETUP problems, never as green (an empty
        corpus once produced 29 fake 'NOT FOUND's from a wrong cwd; refuse, don't judge)."""
        root = tmp_path / "repo"
        (root / "docs/uplevel").mkdir(parents=True)
        (root / "docs/uplevel/rules.md").write_text("# Rules\n")
        shutil.copytree(DATA, root / DATA.relative_to(REPO_ROOT))
        result = run_gate(root)
        assert result.returncode == 2
        assert "too small" in result.stdout

    def test_missing_fixture_refuses(self, tmp_path: Path) -> None:
        root = make_tree(tmp_path)
        (root / DATA.relative_to(REPO_ROOT) / "entailments.json").unlink()
        result = run_gate(root)
        assert result.returncode == 2
        assert "fixture missing" in result.stdout
