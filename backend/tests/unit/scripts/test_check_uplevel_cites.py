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
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# timeout 60s, with the subprocess's own timeout at 30 inside it: the marks must be
# staggered, not equal. An equal mark means pytest-timeout kills the TEST at the same
# instant the subprocess.run would time out the CHILD — the timer that fires first
# decides whether a slow CI box sees a clean timeout report or a test-level kill.
# Measured full-suite durations at the bottom of this comment's history: ~464KB
# docs/uplevel + ~184KB data copytree per mutation arm, ~1-2s gate run each.
# (Precedent for headroom over flakes, not guesswork: test_check_test_coverage_gate.py.)
pytestmark = [pytest.mark.unit, pytest.mark.timeout(60)]

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
        """The gate's green arm: rules.md's cites resolve and their homes carry the claim,
        at the head under test. Green here is what #7054 rounds 1-3 earned. (On docs-only
        PRs the unit shards skip — see test_ci_runs_the_gate_on_docs_only_diffs for the
        step that actually runs this file there.)"""
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
        # The skip-set and the integrity arm must print what they cover: 12 mentions
        # ride the ARTIFACTS skip today and 6 snapshots ride SHA256SUMS — a silent
        # leniency is an invisible coverage hole (self-review #7064, MAJOR-1 family).
        skipped = re.search(r"(\d+) non-corpus mentions skipped", out)
        assert skipped and int(skipped.group(1)) >= 1, f"skip witness missing/zero: {out!r}"
        integ = re.search(r"integrity: (\d+) snapshots match SHA256SUMS", out)
        assert integ and int(integ.group(1)) == 6, f"integrity witness wrong: {out!r}"
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

    @pytest.mark.timeout(10)
    def test_ci_runs_the_gate_on_docs_only_diffs(self) -> None:
        """Self-review #7064 (reviewer finding #1): the old pin grepped ci.yml for
        "pytest backend/tests/unit/ \\" — TRUE even in runs where that step never
        executes, because the shard job is gated on backend/should-run-all and a docs-only
        PR makes both false (measured at #7054's be801744d: shards skipped, "Backend Unit
        Tests" success). A grep-true-but-never-executed pin is the vacuous-green class.
        Parse the real workflow instead: this file's path must be a literal argv token of
        a step in the unfiltered collection-sanity job — the tier that DOES run on docs
        diffs, which is exactly the corpus this gate reads."""
        import yaml  # local: the pin's authority IS the parse, not a fallback grep

        ci = yaml.safe_load((REPO_ROOT / ".github/workflows/ci.yml").read_text())
        step = next(
            s
            for s in ci["jobs"]["collection-sanity"]["steps"]
            if "anti-rot gates" in (s.get("name") or "")
        )
        rel = "backend/tests/unit/scripts/test_check_uplevel_cites.py"
        assert rel in shlex.split(step["run"]), f"{rel} absent from the step argv"
        # the step must survive the tier's own skip paths: any real path filter here
        # would make the join vacuous again
        assert "paths" not in ci["jobs"]["collection-sanity"]
        # and no condition on the STEP itself — the vacuous-green class recurses:
        # the join line survives while a re-added backend/detect-changes `if:` makes
        # the step skip on exactly the docs-only diffs it exists for (measured on
        # this file as a mutation plant: rc=1 with the message below)
        assert "if" not in step, f"the join step grew a skip condition: {step['if']!r}"

    @pytest.mark.timeout(10)
    def test_collection_step_fires_despite_the_backend_path_gates(self) -> None:
        """The negative half: prove WHERE the vacuous green was. The unit shard's if-clause
        must stay gated on backend/should-run-all (a docs-only PR skips it — the #7054
        shape), while collection-sanity's if-clause must stay draft-only. Asserting BOTH
        sides keeps this test from going vacuous if someone un-gates the shards: it would
        then fail here and force a deliberate re-read of what the join is for."""
        import yaml

        ci = yaml.safe_load((REPO_ROOT / ".github/workflows/ci.yml").read_text())
        shard_if = ci["jobs"]["unit-tests"]["if"]
        assert "backend" in shard_if and "should-run-all" in shard_if
        sanity_if = ci["jobs"]["collection-sanity"]["if"]
        assert "draft" in sanity_if and "backend" not in sanity_if


class TestFixtureRegister:
    def test_snapshot_and_fixture_are_committed_and_nontrivial(self) -> None:
        snaps = sorted(DATA.glob("*.md"))
        # A floor tied to what these files actually are: byte-frozen copies of whole plan docs,
        # smallest 10,517 B measured at this head (largest 49,646). `> 1000` could not notice five
        # of the six being replaced by stubs, which is the failure this check exists to catch —
        # provenance verdicts are only as good as the record they read. Kept as a floor rather
        # than exact bytes on purpose: exact sizes are already pinned by SHA256SUMS, and pinning
        # them twice here adds no check, only a second place to update.
        assert len(snaps) == 6, [p.name for p in snaps]
        sizes = {p.name: p.stat().st_size for p in snaps}
        assert all(s > 5_000 for s in sizes.values()), sizes
        fixture = json.loads((DATA / "entailments.json").read_text())
        assert len(fixture) >= 20
        pins = [c for c in fixture if not c.get("expect_present", True)]
        assert len(pins) >= 3
        # the census control (UR-51d): if the matcher ever says True for ALL FOUR headers
        # including this one, it is matching nothing. Deleting the control silently
        # un-fails the whole snapshot arm — pin its presence here.
        assert any(c["rule"] == "UR-51d-control" for c in pins)
        # the §-narrowing negative (UR-32c-widen): a pin that only fires when the
        # resolver widens an item-scoped cite. Its needle must stay a TRUE negative,
        # or the arm is a no-op (control-needle-needs-a-floor-and-a-negative).
        widen = next(c for c in fixture if c["rule"] == "UR-32c-widen")
        assert widen["expect_present"] is False and widen.get("item") == 3
        # the integrity manifest covers exactly the six, or the gate's integrity arm
        # is verifying a different set than the one provenance reads.
        sums = (DATA / "SHA256SUMS").read_text()
        named = [ln.split("  ")[-1] for ln in sums.splitlines() if not ln.startswith("#")]
        assert sorted(named) == [p.name for p in snaps], (named, [p.name for p in snaps])


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

    def test_live_prose_fallback_is_alive(self, tmp_path: Path) -> None:
        """MAJOR 2 (self-review): the LIVE-side prose fallback had zero citations and zero
        arms — deleting `elif q in joined(target)` from resolve() kept every test green.
        Plant a cite quoting a verbatim lowercase phrase that exists in lane.md's prose and
        is NOT a heading/label, and require the live-phrase tally to move 0 → 1 at rc=0."""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(
            rules.read_text() + '\nPer roles/lane.md "Review each PR independently".\n'
        )
        result = run_gate(root)
        assert result.returncode == 0, result.stdout  # a dead fallback would FAIL the cite
        # A FLOOR, not "1 verbatim phrases": the exact pin contradicted this file's own rule
        # (test_witness_totals_are_printed_not_silent: "floors, not exact counts — docs/uplevel
        # grows legitimately"). The second author who cites a live lowercase prose phrase would
        # have reddened this test for writing documentation. The arm's claim is "the fallback is
        # ALIVE", which is count >= 1; the plant guarantees the count moves off zero.
        phrases = re.search(r"(\d+) verbatim phrases", result.stdout)
        assert phrases and int(phrases.group(1)) >= 1, (
            f"live prose fallback resolved nothing — dead arm: {result.stdout!r}"
        )

    def test_snapshot_byte_drift_fires(self, tmp_path: Path) -> None:
        """MINOR 3: provenance verdicts rest on the six frozen snapshots; SHA256SUMS is
        their integrity arm. One appended byte in a record must redden the gate."""
        root = make_tree(tmp_path)
        snap = root / DATA.relative_to(REPO_ROOT) / "30-ops.md"
        snap.write_text(snap.read_text() + "tampered\n")
        result = run_gate(root)
        assert result.returncode == 1
        assert "DRIFTED from SHA256SUMS" in result.stdout

    def test_cite_target_absent_from_live_tree_fires(self, tmp_path: Path) -> None:
        """:281 — the fourth adjudicated UNPINNED branch (old :228). A cite to a file that was
        never live and is not a snapshot. The three sibling arms cover dead-file, dead-section
        and ambiguous-name; this is the plain 'no such file' path, and it is the one a typo in a
        brand-new cite takes."""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(rules.read_text() + '\nPer roles/no-such-lane.md "Whatever".\n')
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "cite target roles/no-such-lane.md not found live" in result.stdout, result.stdout

    def test_dead_name_absent_from_the_snapshot_fires(self, tmp_path: Path) -> None:
        """:257 — 'the deleted 30-ops.md' is proven dead, and the quoted name is neither a
        heading, a label, nor prose in the pre-reorg record. Without this the gate would bless a
        provenance claim with no antecedent: the file really died, but it never SAID that."""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(
            rules.read_text() + '\nCorrects the deleted 30-ops.md "Phrase Nowhere On Record".\n'
        )
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "not a heading/label in the pre-reorg snapshot" in result.stdout, result.stdout

    def test_dead_section_whose_record_is_gone_fires(self, tmp_path: Path) -> None:
        """:217 — a `section` provenance cite whose file has no snapshot at all. The claim needs
        two sides and one is missing entirely: nothing can show the section ever existed."""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(
            rules.read_text() + '\nSee the deleted 60-never-recorded.md section "Some Heading".\n'
        )
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "snapshot lacks 60-never-recorded.md for its dead-section cite" in result.stdout, (
            result.stdout
        )

    def test_snapshot_record_goes_missing_fires_both_arms(self, tmp_path: Path) -> None:
        """:237 + :332 — remove a committed snapshot from the data dir. TWO arms must speak: the
        manifest no longer matches the directory, and the provenance cite that read that record
        now has no antecedent. A single plant covering both is the honest shape — they describe
        one event seen from the integrity side and the resolver side."""
        root = make_tree(tmp_path)
        (root / DATA.relative_to(REPO_ROOT) / "30-ops.md").unlink()
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "but the data dir has" in result.stdout, result.stdout
        assert "for its provenance cite" in result.stdout, result.stdout

    def test_scanned_source_missing_fires(self, tmp_path: Path) -> None:
        """:193 — the corpus is big enough to judge (16 files, floor is 5) but the SCANNED rule
        file itself is gone. Without this arm the gate can report a clean run while having read
        no sources at all: the loop simply has nothing to iterate."""
        root = make_tree(tmp_path)
        (root / "docs/uplevel/rules.md").unlink()
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "scanned source rules.md missing" in result.stdout, result.stdout

    def test_bare_ambiguous_cite_with_claims_fires(self, tmp_path: Path) -> None:
        """MINOR 7: bare `r2-sheet.md` matches BOTH the live doc and templates/r2-sheet.md
        today. A bare cite that QUOTES claims must not have them checked against whichever
        match the walker happened to yield first — ambiguity is named, not picked."""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(rules.read_text() + '\nPer r2-sheet.md "Claim On Ambiguous Name".\n')
        result = run_gate(root)
        assert result.returncode == 1
        assert "ambiguous" in result.stdout

    def test_live_backed_artifact_name_is_still_checked(self, tmp_path: Path) -> None:
        """The ARTIFACTS skip is CONDITIONAL on liveness: 00-audit.md is in the skip-set AND
        is a live doc, so a cite to a section that never existed there must still fire.
        Under the old unconditional name-skip this plant resolved to nothing at rc=0."""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(rules.read_text() + '\nPer 00-audit.md "Section Nobody Wrote".\n')
        result = run_gate(root)
        assert result.returncode == 1
        assert "Section Nobody Wrote" in result.stdout

    def test_widen_pin_fires_when_item_three_widens(self, tmp_path: Path) -> None:
        """UR-32c-widen (fixture case, expect_present=false): 'git fetch' belongs to item 1
        of lane.md's tick; item 3 (Reviews first) must NOT carry it. Write it into item 3 and
        the emptiness pin fires — the call-site control the selftest's toy section cannot be.
        If §-narrowing ever WIDENS (whole-section read), step 1's git-fetch would sit inside
        item 3's block and this fires even with no prose edit — which is why the needle was
        chosen to be true-absent from item 3 and true-present in the un-narrowed section."""
        root = make_tree(tmp_path)
        lane = root / "docs/uplevel/roles/lane.md"
        text = lane.read_text()
        m = re.search(r"^3\. .*?(?=^4\. )", text, re.S | re.M)
        assert m, "fixture drifted: item 3 of 'The tick' moved"
        lane.write_text(
            text[: m.end()] + "   `git fetch origin` runs at review time too.\n" + text[m.end() :]
        )
        result = run_gate(root)
        assert result.returncode == 1
        assert "UR-32c-widen" in result.stdout


class TestCiteJoiners:
    """`per X.md "a", "b"` was checked; `… "a" and "b"` was silently unchecked (peer arm-audit's
    Task D, reproduced on this tree: same bogus name, same sentence, only the joiner differed —
    `and` rc=0 with the name never printed, `,` rc=1 naming it). The gate-level pair below pins
    both directions of the widening; the selftest arms inside the script pin the parse itself."""

    BOGUS = "Zqxj No Such Joined Section"

    def test_and_joined_bogus_name_fires(self, tmp_path: Path) -> None:
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        text = rules.read_text()
        plant = f'\nProbe: per rules.md "Claiming and assigning work" and "{self.BOGUS}".\n'
        assert text.count(self.BOGUS) == 0
        rules.write_text(text + plant)
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert self.BOGUS in result.stdout, result.stdout

    def test_oxford_or_joined_bogus_name_fires(self, tmp_path: Path) -> None:
        # roles/owner-partner.md:51 uses the `", X" or "Y"` shape in prose; the cite form must
        # capture its tail name too, not just the first.
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        text = rules.read_text()
        plant = f'\nProbe: per rules.md "Claiming and assigning work", or "{self.BOGUS}".\n'
        assert text.count(self.BOGUS) == 0
        rules.write_text(text + plant)
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert self.BOGUS in result.stdout, result.stdout

    def test_and_followed_by_prose_does_not_swallow_a_later_quote(self, tmp_path: Path) -> None:
        # The other direction: a joiner that reaches to the next quote turns rules.md:32-shaped
        # prose (`… as an unnumbered "coordinator decision" and sends anything else …`) into a
        # two-name cite and manufactures reds. Chain must stop when no cite unit follows.
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        text = rules.read_text()
        plant = (
            '\nProbe: per rules.md "Claiming and assigning work" and sends '
            '"Zqxj Mere Prose Quote" home.\n'
        )
        assert text.count("Zqxj Mere Prose Quote") == 0
        rules.write_text(text + plant)
        result = run_gate(root)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Zqxj Mere Prose Quote" not in result.stdout, result.stdout


def _point_gate_at(tmp_path: Path) -> Path:
    """Copy the gate INTO the throwaway tree so a test can mutate the SCRIPT.

    run_gate() passes the real script plus a root argv, which pins every arm to the shipped
    source. Data plants (docs, snapshots, fixtures) can mutate the tree; a CODE plant has to
    mutate the script, and the script must then resolve DATA relative to the tree it judges —
    which it does: DATA is a relative Path joined to `root` everywhere, and `root` is argv[0].
    """
    root = make_tree(tmp_path)
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT, scripts / "check-uplevel-cites.py")
    return root


def _replace_in_gate(path: Path, old: str, new: str) -> None:
    """A mutation plant that CANNOT fail silently. Asserting the occurrence count before
    writing is the difference between a mutation test and a green run that proved nothing
    (memory: absent-needle-makes-mutation-control-a-noop — my own first attempt at this in
    #7064 no-op'd on a wrong path and printed a reassuring 17 passed)."""
    text = path.read_text()
    assert text.count(old) == 1, f"plant did not land: {old!r} occurs {text.count(old)}x"
    path.write_text(text.replace(old, new))


def _fixture(root: Path) -> list[dict]:
    rel = DATA.relative_to(REPO_ROOT)
    return json.loads((root / rel / "entailments.json").read_text())


def _write_fixture(root: Path, rows: list[dict]) -> None:
    rel = DATA.relative_to(REPO_ROOT)
    (root / rel / "entailments.json").write_text(json.dumps(rows, indent=2) + "\n")


class TestEntailmentArmEdges:
    """The entail() arms the mutation census found UNREACHED (17 of 22 failure sites entered
    by no test — /tmp/corr/reach-probe2.py, whose reach.json is the raw per-site counts).

    Each arm asserts the branch's MESSAGE, never rc: two of these branches exit 1 on the same
    plant, and a test that says only `returncode == 1` is satisfied by whichever sibling fires
    first — the failure-block-attribution trap, learned the hard way by the reviewer whose
    letter I am folding (arm-audit rule 2)."""

    def test_presence_needle_case_is_folded_both_sides(self, tmp_path: Path) -> None:
        """joined() lowercases the haystack. Comparing a needle as-written made a sentence-case
        fixture needle UNSATISFIABLE: the row can never go green, and the red reads like a
        content violation in the docs rather than a bug in the gate. Every needle shipped at
        2e80eca72 happened to be lowercase, so this was latent until a fixture edit walked in."""
        root = make_tree(tmp_path)
        rows = _fixture(root)
        row = next(r for r in rows if r["rule"] == "UR-32c")
        row["needles"] = ["Reviews First"]  # real text in item 3, capitals folded away
        _write_fixture(root, rows)
        result = run_gate(root)
        assert result.returncode == 0, result.stdout

    def test_emptiness_pin_needle_case_is_folded_too(self, tmp_path: Path) -> None:
        """The dangerous half of the same asymmetry. A presence row with an unsatisfiable
        needle is a loud false red; an emptiness PIN with one is a SILENT green — the check
        that text is absent can never fire, so the pin reports pass whether or not the text
        came back. Plant the text and require the pin to say so."""
        root = make_tree(tmp_path)
        rows = _fixture(root)
        row = next(r for r in rows if r["rule"] == "UR-91-c4")
        row["needles"] = ["Reviewed Again"]  # capitals; 'reviewed again' is what we inject
        _write_fixture(root, rows)
        lane = root / "docs/uplevel/roles/lane.md"
        anchor = "## Reviewing another lane's PR\n"
        text = lane.read_text()
        assert anchor in text, "fixture drifted: the pinned section moved"
        lane.write_text(text.replace(anchor, anchor + "\nThe head is Reviewed Again today.\n"))
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "UR-91-c4" in result.stdout, result.stdout
        assert "must NOT say" in result.stdout

    def test_presence_row_with_no_needle_fires(self, tmp_path: Path) -> None:
        """:369 — 'lacks any of'. Unreachable by the shipped fixture because every row has at
        least one matching needle. An empty needle list is a vacuous presence claim: the row
        says 'this section proves UR-x' and checks nothing."""
        root = make_tree(tmp_path)
        rows = _fixture(root)
        next(r for r in rows if r["rule"] == "UR-89")["needles"] = []
        _write_fixture(root, rows)
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "UR-89" in result.stdout and "lacks any of" in result.stdout, result.stdout

    def test_fixture_naming_an_absent_file_fires(self, tmp_path: Path) -> None:
        """:347 — a fixture row whose file was renamed away is NOT an entailment failure, it
        is a blind check, and it must be said out loud as its own message."""
        root = make_tree(tmp_path)
        rows = _fixture(root)
        next(r for r in rows if r["rule"] == "UR-89")["file"] = "roles/lane-moved-away.md"
        _write_fixture(root, rows)
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "absent at" in result.stdout, result.stdout

    def test_fixture_naming_a_moved_section_reports_blind_not_entailed(
        self, tmp_path: Path
    ) -> None:
        """:352 + :375 — the section can't be located. Two branches must BOTH speak: the miss
        itself, and the floor that refuses to let an unlocated section count as an entailment.
        Without the floor a gate can 'pass' while judging none of the register."""
        root = make_tree(tmp_path)
        rows = _fixture(root)
        next(r for r in rows if r["rule"] == "UR-89")["section"] = "Section Since Renamed"
        _write_fixture(root, rows)
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "Section Since Renamed" in result.stdout, result.stdout
        assert "blind check" in result.stdout, "the located-N/N floor did not fire"

    def test_manifest_missing_refuses_instead_of_skipping(self, tmp_path: Path) -> None:
        """A fail path my whole census frame could not see: it RETURNS a fail list rather than
        appending to one, so a `grep -n fails.append` enumeration — the frame my own note
        mutation-census-frame-from-source-not-claim tells me to build from — misses it. Deleting
        the manifest must not turn snapshot integrity into an unchecked pass."""
        root = make_tree(tmp_path)
        (root / DATA.relative_to(REPO_ROOT) / "SHA256SUMS").unlink()
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "SHA256SUMS missing" in result.stdout, result.stdout

    def test_manifest_covering_nothing_reports_vacuous(self, tmp_path: Path) -> None:
        """The second non-append fail path. A manifest emptied to comments only lists zero
        files; the loop over it then verifies zero snapshots and n=0 would print beside
        'integrity: 0 snapshots match' as if that were a pass. It is a skipped loop."""
        root = make_tree(tmp_path)
        man = root / DATA.relative_to(REPO_ROOT) / "SHA256SUMS"
        man.write_text("# hand-maintained; see scripts/check-uplevel-cites.py\n")
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "integrity arm is vacuous" in result.stdout, result.stdout


class TestScopeClaimArms:
    """The four § arms the fix head added to resolve() — a § cite claims a section HAS item N.
    None of these branches was entered by any test before this head (probe: tree=0 at :221,
    :241, :284, :288), which is how the shipped grammar could fail to deliver the item at all
    and stay green."""

    def test_live_section_scope_claim_false_fires(self, tmp_path: Path) -> None:
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(rules.read_text() + '\nPer roles/lane.md "The tick" §99.\n')
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "§99" in result.stdout and "has no item 99" in result.stdout, result.stdout

    def test_live_section_scope_claim_true_passes(self, tmp_path: Path) -> None:
        """The positive control. Without it the arm above is worthless: a check that fails on
        §99 and on §3 alike is not checking the item, it is failing every § cite — and the
        corpus would go red for the wrong reason the moment anyone wrote a true §."""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(rules.read_text() + '\nPer roles/lane.md "The tick" §3.\n')
        result = run_gate(root)
        assert result.returncode == 0, result.stdout
        assert "ALL ULEVEL CITES RESOLVE" in result.stdout

    def test_live_prose_phrase_cannot_carry_a_scope(self, tmp_path: Path) -> None:
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(
            rules.read_text() + '\nPer roles/lane.md "Review each PR independently" §2.\n'
        )
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "scopes a § to a prose phrase" in result.stdout, result.stdout

    def test_snapshot_section_scope_claim_false_fires(self, tmp_path: Path) -> None:
        """A provenance cite may scope into the SNAPSHOT: 'the deleted X section "Y" §3' claims
        the pre-reorg file had an item 3 there. Plant it against a real snapshot heading."""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(
            rules.read_text()
            + '\nCorrects the deleted 10-backend.md section "B1.1 VLM timeout ladder (D1)" §99.\n'
        )
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "§99" in result.stdout, result.stdout
        assert "pre-reorg scope claim is false" in result.stdout, result.stdout

    def test_snapshot_section_scope_claim_false_fires_markerless(self, tmp_path: Path) -> None:
        """:241 — the MARKERLESS deleted form (`the deleted X "Y" §N`, no `section` keyword)
        still resolves Y against the snapshot's headings, and a § there is still a claim. The
        corpus has no § on this branch at all, so the branch could invert and stay green."""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(
            rules.read_text() + '\nCorrects the deleted 50-coordination.md "Roles" §4.\n'
        )
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "§4 has no item 4" in result.stdout, result.stdout

    def test_snapshot_prose_phrase_cannot_carry_a_scope(self, tmp_path: Path) -> None:
        """The deleted-side twin of the live prose arm. `corrects the deleted 50-coordination.md
        \"Roles\", \"makes no decisions\"` is the corpus's own idiom: \"Roles\" is a snapshot
        SECTION and \"makes no decisions\" is PROSE reached through the fallback — so the § on
        the second one scopes to nothing. (My first plant here used \"Roles\" and the gate
        correctly answered `has no item 4`, which is the arm above.)"""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(
            rules.read_text()
            + '\nCorrects the deleted 50-coordination.md "makes no decisions" §4.\n'
        )
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "scopes a § to a prose phrase" in result.stdout, result.stdout

    def test_deleted_section_missing_from_snapshot_fires(self, tmp_path: Path) -> None:
        """:217 (adjudicated UNPINNED as old :180). A dead-section provenance needs BOTH sides:
        absent now, present in the snapshot. The corpus has no cite of this form, so the arm
        that proves the antecedent existed was never entered."""
        root = make_tree(tmp_path)
        rules = root / "docs/uplevel/rules.md"
        rules.write_text(
            rules.read_text() + '\nSee the deleted README.md section "Section Gone For Real".\n'
        )
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "absent from the pre-reorg snapshot" in result.stdout, result.stdout

    def test_deleted_section_live_again_fires(self, tmp_path: Path) -> None:
        """:210 — the dead-SECTION branch (a dead heading in a live file). The sibling arm
        test_deleted_file_alive_again_fires covers the dead-FILE branch only, and the two
        print different messages, so pinning rc would let one stand in for the other."""
        root = make_tree(tmp_path)
        readme = root / "docs/uplevel/README.md"
        readme.write_text(readme.read_text() + "\n## The path\n\nBack from the dead.\n")
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "is live in README.md again" in result.stdout, result.stdout


class TestSelfCiteCannotQuoteItself:
    """A cite written IN rules.md pointing AT rules.md used to be proved by its own sentence.

    resolve() checked the phrase fallback with `q in joined(target)`, and `target` is the file's
    own text — which contains the citing sentence. So `per rules.md "Some Phrase"` passed on a
    phrase that exists nowhere except inside the cite's own quotes, and the witness line printed
    `+ 1 verbatim phrases` for a count the gate had just invented. Found by peer arm-audit (Task
    C) and re-measured on this branch: plant lands, rc=0, tally inflates.

    These two tests are a PAIR on purpose — one plant that must now fail, one that must stay
    green — because a fix that merely rejects every self-cite would look equally "working" while
    deleting a legitimate cite form. Same two-sided shape as the case-fold arms."""

    PHRASE = "Zqxj Self Cite Sentinel"

    def _plant(self, root: Path, decoy: bool) -> Path:
        rules = root / "docs/uplevel/rules.md"
        text = rules.read_text()
        if decoy:
            # real prose elsewhere in the file: the phrase is evidence independent of the cite
            anchor = "\n\n## Claiming and assigning work"
            assert text.count(anchor) == 1, "rules.md anchor moved — plant would be a no-op"
            text = text.replace(
                anchor, f"\nAn ordinary sentence that says {self.PHRASE} for real.{anchor}", 1
            )
        rules.write_text(text + f'\nProbe: per rules.md "{self.PHRASE}".\n')
        body = rules.read_text()
        assert body.count(self.PHRASE) == (2 if decoy else 1), "plant did not land"
        return rules

    def test_self_cite_quoting_only_itself_fires(self, tmp_path: Path) -> None:
        root = make_tree(tmp_path)
        self._plant(root, decoy=False)
        result = run_gate(root)
        assert result.returncode == 1, result.stdout
        assert "not found in live rules.md" in result.stdout, result.stdout

    def test_self_cite_with_real_prose_elsewhere_still_passes(self, tmp_path: Path) -> None:
        root = make_tree(tmp_path)
        self._plant(root, decoy=True)
        result = run_gate(root)
        assert result.returncode == 0, result.stdout
        assert "ALL ULEVEL CITES RESOLVE" in result.stdout, result.stdout
        # and it is counted as a phrase, not silently skipped — the tally is the witness that the
        # branch ran, not just that nothing complained.
        assert "1 verbatim phrases" in result.stdout, result.stdout

    def test_the_shipped_corpus_has_no_self_cite_to_begin_with(self) -> None:
        """The fix is prospective: no cite in rules.md points AT rules.md today (gate parser, raw
        `.count("rules.md")`, and a grep all agree: 0). Pinned on the CITE SHAPE the guard
        governs — a self-target plus a quoted name — not on every prose mention, which would red
        a legitimate `rules.md:419` cross-reference the gate itself is content to pass. If this
        trips, the new cite is being judged by the self-cite rule now: make sure its phrase is
        real prose outside the cite, not just quoted."""
        text = (REPO_ROOT / "docs/uplevel/rules.md").read_text()
        self_cites = re.findall(r'rules\.md(?:\s+section)?\s+"[^"]+"', text)
        assert not self_cites, f"new self-cites in rules.md: {self_cites[:3]}"


class TestSelftestWitness:
    """main() prints `selftest: N/N arms fired`. At 2e80eca72 that number was the literal 4, so
    `st = selftest()` -> `st = []` left rc=0, the suite green, and stdout still complimenting
    itself. The count is derived now; these arms are what keeps it derived."""

    def test_witness_count_is_derived_and_at_least_the_shipped_arms(self) -> None:
        out = run_gate(REPO_ROOT).stdout
        m = re.search(r"selftest: (\d+)/(\d+) arms fired", out)
        assert m, f"the derived witness line is gone: {out.splitlines()[:2]!r}"
        fired, total = int(m.group(1)), int(m.group(2))
        assert fired == total, f"{fired}/{total}: a blind arm must never reach this line"
        # FLOOR, not equality. This pin was `== 11`, which reddened the moment the self-cite arms
        # (13) were added — the exact brittleness this file's own rule retired the "1 verbatim
        # phrases" pin for. `fired == total` is vacuous by construction (the witness prints
        # len(st)/len(st)), so the ONLY real signal here is that the arm population cannot silently
        # SHRINK; equality on the count adds a second failure mode that fires for legitimate work.
        assert total >= 17, (
            f"selftest arms fell to {total}: an arm was deleted or stopped being reached, and the "
            "witness would still print N/N green"
        )

    def _run_script(self, script: Path, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603  # intentional - tests our own mutated copy
            [sys.executable, "-I", str(script), str(root)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_a_broken_capability_withholds_the_tree_verdicts(self, tmp_path: Path) -> None:
        """Break a REAL capability — drop the `**N.` alternative from the item locator, which
        is the snapshot form every §-cite into a snapshot depends on — and require the run to
        refuse at rc=2, name which arm broke, and NOT certify the tree.

        My first plant here substituted `True` for an arm's predicate instead. That is not
        blindness: the tuples are (instrument_works, message_if_blind), so `True` fabricates a
        PASSING arm, and no instrument can detect an arm that lies about working. The honest
        plant breaks the thing the arm checks."""
        root = _point_gate_at(tmp_path)
        script = root / "scripts/check-uplevel-cites.py"
        _replace_in_gate(
            script,
            r'        start = rf"^[ ]*(?:{item}\.\s|\*\*{item}\.\s)"',
            r'        start = rf"^[ ]*(?:{item}\.\s)"',
        )
        result = self._run_script(script, root)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "SELF-TEST FAILED" in result.stdout
        assert "verdicts withheld" in result.stdout
        assert "ALL ULEVEL CITES" not in result.stdout, "certified the tree while blind"

    def test_the_refusal_itself_is_a_gate_not_a_report(self, tmp_path: Path) -> None:
        """Two-part plant: break the same capability AND replace the guard's predicate so the
        selftest still RUNS and still counts 11/11 while its verdicts are ignored. The output
        is then a fully confident, fully false certification — `selftest: 11/11 arms fired`
        beside a broken matcher, which is the #7064 hole in its second form. If the guard is a
        report rather than a gate, this run certifies the tree."""
        root = _point_gate_at(tmp_path)
        script = root / "scripts/check-uplevel-cites.py"
        _replace_in_gate(
            script,
            r'        start = rf"^[ ]*(?:{item}\.\s|\*\*{item}\.\s)"',
            r'        start = rf"^[ ]*(?:{item}\.\s)"',
        )
        _replace_in_gate(
            script,
            "    blind = [msg for ok, msg in st if not ok]",
            "    blind = []",
        )
        result = self._run_script(script, root)
        assert "ALL ULEVEL CITES" not in result.stdout, (
            f"the refusal was decorative: {result.stdout!r}"
        )
        assert result.returncode != 0, result.stdout

    def test_bypassing_selftest_cannot_certify_the_tree(self, tmp_path: Path) -> None:
        """The mutation that was undetectable at 2e80eca72: `st = selftest()` -> `st = []`.

        Two separate halves, both needed. (a) The WITNESS must be derived, so the line reads
        0/0 instead of the hard-coded 4 it used to print. (b) ZERO ARMS MUST REFUSE THE RUN —
        `blind` is computed FROM st, so an empty st gives an empty blind list and the guard
        never fires; with only (a) fixed, the gate printed `selftest: 0/0 arms fired` and
        `ALL ULEVEL CITES RESOLVE` on the very next line, rc=0. Measured, this window, against
        the intermediate head: that is what I wrote first and what this test caught."""
        root = _point_gate_at(tmp_path)
        script = root / "scripts/check-uplevel-cites.py"
        _replace_in_gate(script, "    st = selftest()", "    st = []")
        result = self._run_script(script, root)
        assert "selftest ran 0 arms" in result.stdout, result.stdout
        assert result.returncode == 2, result.stdout
        assert "ALL ULEVEL CITES" not in result.stdout, (
            "zero arms fired yet the tree was certified — that is the #7064 hole"
        )
        assert "selftest: 0/0" not in result.stdout, (
            "the derived witness line is printed for a run that withheld its verdicts"
        )


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
