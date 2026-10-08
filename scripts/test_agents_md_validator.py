#!/usr/bin/env python3
"""Tests for scripts/agents_md_validator.py — the W1.1 ratchet with teeth.

Run explicitly; outside testpaths (this joins the anti-rot pytest list in
.github/workflows/ci.yml, which CI Gate requires via collection-sanity):

    uv run python -m pytest scripts/test_agents_md_validator.py -q

The package's Done-when, pinned on fixtures (a synthetic tree in tmp_path, so
exit codes are real and no fixture AGENTS.md is ever committed — the real-tree
run's rglob would fold a committed fixture into the scanned set):

  A. adding a new dead reference to a scanned AGENTS.md fails the run;
  B. adding a retired-name mention above the baseline fails the run;
  and CI passes on the current tree (test_real_tree_is_green — inside the
  required CI-Gate closure via collection-sanity's anti-rot step).

Pair-sides doctrine (test_ratchet_check.py's house rule): every rule is
pinned in BOTH directions — a one-sided gate leaks in the untested direction.
The laundering sides are pinned too: exclusion-set edits are visible diffs
(test_committed_exclusion_sets_are_pinned), the allowlist is keyed on the
PAIR (agents_md, reference) not either half, resolution is ANCHORED (a path
that exists only inside an excluded directory is dead on every machine), and
retired-name counting is whole-word over the scanned AGENTS.md set only —
"purpose" is not "pose", and a README next door is not an AGENTS.md.

Infrastructure vs content is a hard line: a run that COULD NOT happen (config
unreadable, PyYAML missing, baseline incomplete) exits 2 — never 1, which
would blame a docs PR for a broken gate; a CONTENT violation exits 1; and the
report's issues[]/summary{} shape stays byte-identical for
agents_md_linear_sync.py, with the ratchet's own state in one additive
top-level "ratchet" block.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "agents_md_validator.py"
COMMITTED_CONFIG = yaml.safe_load((REPO_ROOT / ".agents-md-validator.yml").read_text())

RETIRED_NAMES = ("florence", "nemotron", "enrichment", "xclip", "pose", "demographics")

# Laundering tripwires. exclude_directories and exclude_reference_patterns
# sit in the SAME file as the baselines, and widening either laundrows the
# gate with no pair-census side effect — the design panel measured +exclude
# `backend` keeping the SAME dead pairs while nemotron 143 -> 83 (the retired
# arm silently halved), and one added exclude_reference_patterns line
# silently excusing a dead pair from report, gate and census alike. Pin the
# committed sets here: any change must edit this constant in the same,
# reviewed PR.
EXPECTED_EXCLUDE_DIRECTORIES = {
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    ".pytest_cache",
    "coverage",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    "mutants",
    "*.egg-info",
    ".tox",
    ".nox",
    # W1.1: mkdocs output is gitignored but not rglob-exempt — one local
    # `mkdocs build` otherwise reddens the gate for reasons no PR caused.
    # Measured effect on the committed baselines: exactly zero.
    "site",
}
EXPECTED_EXCLUDE_REFERENCE_PATTERNS = {
    "example\\.py",
    "your_file\\.py",
    "\\{.*\\}",
    "<.*>",
    "\\$\\{.*\\}",
    "\\$[A-Z_]+",
    "report\\.json$",
    "-report\\.json$",
    "yolo26-vs-yolo26\\.md$",
    "_test\\.(py|tsx?)$",
    "test_.*\\.py$",
    "\\.test\\.tsx$",
    "\\.msw\\.test\\.tsx$",
}

# The pair the package's own first CI run would otherwise lose. Under ANCHORED
# resolution `.venv/` is dead on every tree — absent in CI, or inside an
# excluded component on a dev machine — so the entry stays; whoever measures a
# local 12 must NOT "fix" it away (measured delta, dev vs clean clone: 1).
VENV_PAIR = (".github/codeql/custom-queries/AGENTS.md", ".venv/")

BASE_MD = """# Fixture

Dead: `ghost/a.py` and `ghost/b/`.

Link: [notes](notes.md)

Names: florence nemotron enrichment xclip pose demographics.
"""

# What minting WOULD produce for BASE_MD — hand-written here because no
# --mint/--update flag exists on purpose: a flag that rewrites the baseline
# is an opt-out with no diff. Drain is a hand edit either way.
BASE_ALLOWLIST = [
    {"agents_md": "AGENTS.md", "reference": "ghost/a.py", "tracking": "fixture"},
    {"agents_md": "AGENTS.md", "reference": "ghost/b/", "tracking": "fixture"},
]
BASE_BASELINE = dict.fromkeys(RETIRED_NAMES, 1)

_SENTINEL = object()


def build(
    where: Path,
    *,
    md: str = BASE_MD,
    files: dict[str, str] | None = None,
    allowlist=_SENTINEL,
    baseline=_SENTINEL,
) -> Path:
    """A minimal scannable tree whose config INHERITS the committed exclusion
    lists (hand-transcribed config copies rot) with spliced fixture baselines."""
    root = where / "tree"
    root.mkdir(parents=True)
    (root / "AGENTS.md").write_text(md)
    (root / "notes.md").write_text("present target for the base link\n")
    # A directory alive ONLY under an excluded component (build/ is committed
    # in exclude_directories): anchored resolution calls it dead everywhere.
    (root / "build" / "cache" / "x").mkdir(parents=True)
    for rel, content in (files or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    write_config(root, allowlist=allowlist, baseline=baseline)
    return root


def write_config(
    root: Path,
    *,
    allowlist=_SENTINEL,
    baseline=_SENTINEL,
) -> Path:
    config = {
        "exclude_directories": [*COMMITTED_CONFIG["exclude_directories"], "site"],
        "no_agents_md_required": [],
        "code_extensions": list(COMMITTED_CONFIG["code_extensions"]),
        "min_code_files": COMMITTED_CONFIG["min_code_files"],
        "exclude_reference_patterns": list(COMMITTED_CONFIG["exclude_reference_patterns"]),
        "dead_reference_allowlist": (
            [dict(e) for e in BASE_ALLOWLIST] if allowlist is _SENTINEL else allowlist
        ),
        "retired_name_baseline": dict(BASE_BASELINE) if baseline is _SENTINEL else baseline,
    }
    path = root / ".agents-md-validator.yml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return path


def amend(root: Path, extra: str, name: str = "AGENTS.md") -> None:
    """Append lines to a scanned AGENTS.md — the exact move the Done-when
    says must fail the run."""
    p = root / name
    p.write_text(p.read_text() + extra)


def run_validator(
    root: Path | None = None,
    *,
    flags: list[str] | None = None,
    config: str | None = None,
    env: dict[str, str] | None = None,
    output: str | None = "report.json",
) -> subprocess.CompletedProcess:
    argv = [sys.executable, str(VALIDATOR)]
    if root is not None:
        argv += ["--root", str(root)]
    if config is not None:
        argv += ["--config", config]
    if output is not None:
        argv += ["--output", output, "--format", "json", "--quiet"]
    argv += flags or []
    return subprocess.run(argv, capture_output=True, text=True, check=False, env=env)


def report_of(root: Path) -> dict:
    return json.loads((root / "report.json").read_text())


def dead_pairs(report: dict) -> set[tuple[str, str]]:
    return {
        (i["agents_md"], i["reference"]) for i in report["issues"] if i["type"] == "stale_reference"
    }


# --------------------------------------------------------------------------
# Done-when A: a new dead reference fails — and the allowlist is what excuses
# --------------------------------------------------------------------------


def test_green_fixture_is_green(tmp_path):
    """The harness is not vacuously red: the minted fixture passes, and its
    reported pairs are exactly the allowlisted ones."""
    root = build(tmp_path)
    r = run_validator(root)
    assert r.returncode == 0, r.stderr
    assert dead_pairs(report_of(root)) == {(a["agents_md"], a["reference"]) for a in BASE_ALLOWLIST}


def test_new_dead_reference_fails(tmp_path):
    """DONE-WHEN A. The appended reference is path-shaped on purpose: the
    committed extractor skips bare filenames (too many false positives —
    `newthing.py` would extract nothing and test nothing), so the fixture
    also pins that the pair really reached the report before trusting rc."""
    root = build(tmp_path)
    amend(root, "\nNew: `nowhere/nothing.py`.\n")
    r = run_validator(root)
    assert ("AGENTS.md", "nowhere/nothing.py") in dead_pairs(report_of(root))
    assert r.returncode == 1
    assert "nowhere/nothing.py" in r.stderr and "AGENTS.md" in r.stderr


def test_allowlisted_pair_excused_and_removal_fails(tmp_path):
    """Both sides of bullet 1: the allowlist is consulted (green with the
    entry) AND enforced (red when an entry is hand-removed while the citation
    stands — the drain direction)."""
    root = build(tmp_path)
    assert run_validator(root).returncode == 0
    cfg_path = root / ".agents-md-validator.yml"
    cfg = yaml.safe_load(cfg_path.read_text())
    cfg["dead_reference_allowlist"] = [
        e for e in cfg["dead_reference_allowlist"] if e["reference"] != "ghost/b/"
    ]
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    r = run_validator(root)
    assert r.returncode == 1
    assert "ghost/b/" in r.stderr


def test_allowlist_is_keyed_on_the_pair_not_either_half(tmp_path):
    """Mutants that match by agents_md alone (lends any file's entry to any
    of its references) or by reference alone pass every one-sided fixture.
    Two dead references, entries that each guard the OTHER half: the
    unguarded reference must still redden, naming itself."""
    root = build(
        tmp_path,
        allowlist=[
            {"agents_md": "AGENTS.md", "reference": "ghost/b/", "tracking": "fixture"},
            {"agents_md": "other/AGENTS.md", "reference": "ghost/a.py", "tracking": "fixture"},
        ],
    )
    r = run_validator(root)
    assert r.returncode == 1
    assert "ghost/a.py" in r.stderr
    assert "ghost/b/" not in r.stderr


def test_dead_link_fails(tmp_path):
    """Zero tolerance: the package names no link baseline, and the real tree
    carries 0 dead links at HEAD (measured twice, both trees)."""
    root = build(tmp_path)
    amend(root, "\nSee [the spec](missing.md).\n")
    r = run_validator(root)
    assert r.returncode == 1
    assert "missing.md" in r.stderr


def test_inline_ignore_comment_needs_a_tracking_ref(tmp_path):
    """The pre-existing inline hatch was measured (design panel) to be a
    zero-diff suppression channel for BOTH arms — one HTML comment silences a
    dead reference with no baseline edit. It stays in TRACKED form only,
    `ignore-reference <path> # <ref>` — the house doctrine for every
    suppression — because it is also the documented out for the zero-
    tolerance link arm. A bare comment no longer silences anything and is
    itself named as a violation."""
    root = build(tmp_path)
    amend(
        root,
        "\nSee [the spec](missing.md).\n"
        "<!-- agents-md-validator: ignore-reference missing.md -->\n",
    )
    r = run_validator(root)
    assert r.returncode == 1
    assert "missing.md" in r.stderr
    assert "tracking" in r.stderr.lower()

    tracked = build(tmp_path / "tracked")
    amend(
        tracked,
        "\nSee [the spec](missing.md).\n"
        "<!-- agents-md-validator: ignore-reference missing.md # W1.3/NEM-1 -->\n",
    )
    r = run_validator(tracked)
    assert r.returncode == 0, r.stderr


def test_excluded_dir_reference_is_dead_on_every_machine(tmp_path):
    """The ANCHORED graft, pinned. `build/cache/x/` EXISTS on this machine
    (build() creates it) but lives under an excluded component, so an
    existence hit may not prove it — the pair must reach the report. A naive
    `resolved.exists()` validator reports NO pair here (measured mutant),
    which is the machine-dependent baseline the panel caught: dead on CI,
    alive on dev."""
    root = build(tmp_path, md=BASE_MD + "\nOutput lives in `build/cache/x/`.\n")
    r = run_validator(root)  # rc 1: the pair is not in the fixture allowlist
    assert r.returncode == 1
    assert ("AGENTS.md", "build/cache/x/") in dead_pairs(report_of(root))


# --------------------------------------------------------------------------
# Done-when B: retired-name mentions above baseline — and what is NOT a mention
# --------------------------------------------------------------------------


def test_retired_name_above_baseline_fails(tmp_path):
    """DONE-WHEN B. The fixture baseline is 1 BEFORE the append, minted with
    BASE_MD already carrying one mention per name — a fixture minted at 0
    cannot tell "above baseline" from "any mention fails" (the teeth panel
    ran both implementations and they behaved identically at 0)."""
    root = build(tmp_path)
    amend(root, "\nAnother florence note.\n")
    r = run_validator(root)
    assert r.returncode == 1
    assert "florence" in r.stderr
    assert "2" in r.stderr and "1" in r.stderr  # measured vs baseline


def test_purpose_is_not_pose(tmp_path):
    """Whole-word is load-bearing, pinned: SUBSTRING pose measured 1457
    across the real tree ("purpose", "compose", PoseResult — live English and
    live code), so substring counts a different quantity than the plan named
    and would redden any PR writing the word 'purpose'. This fixture passes
    whole-word and REDDENS under a substring implementation (pose 2 > 1)."""
    root = build(tmp_path)
    amend(root, "\nThe purpose of this compose file is documented elsewhere.\n")
    r = run_validator(root)
    assert r.returncode == 0, r.stderr


def test_substitution_does_not_green_a_total(tmp_path):
    """Per-name baselines, not one total: +1 florence bought with -1 pose
    holds the total at baseline (6 == 6) — a totals-only implementation
    returns green here and launders by substitution."""
    root = build(
        tmp_path,
        md="# Fixture\n\nDead: `ghost/a.py` and `ghost/b/`.\n\n"
        "Link: [notes](notes.md)\n\n"
        "Names: florence florence nemotron enrichment xclip demographics.\n",
    )
    r = run_validator(root)
    assert r.returncode == 1
    assert "florence" in r.stderr


def test_sibling_readme_is_not_scanned(tmp_path):
    """The counting set is exactly find_agents_md_files(), never every *.md:
    a README next door carrying 'florence' must not move the baseline (a
    fixture-local wider-scan mutant fails only here)."""
    root = build(tmp_path, files={"README.md": "florence florence florence\n"})
    r = run_validator(root)
    assert r.returncode == 0, r.stderr


def test_missing_agents_md_stays_reporting_only(tmp_path):
    """Scope pin: missing_agents_md is NOT one of the package's three failure
    conditions — wiring it is W3.1's Phase-3 job. The issue must still be
    REPORTED (linear_sync keeps filing its tickets) while the gate stays
    green."""
    root = build(tmp_path, files={"src/a.py": "", "src/b.py": "", "src/c.py": ""})
    r = run_validator(root)
    assert r.returncode == 0, r.stderr
    types = [i["type"] for i in report_of(root)["issues"]]
    assert "missing_agents_md" in types


# --------------------------------------------------------------------------
# Infrastructure (exit 2) vs content (exit 1) — the line must not blur
# --------------------------------------------------------------------------


def test_missing_pyyaml_exits_2_not_1(tmp_path):
    """The reproduced trap: PyYAML is UNDECLARED (pyproject [project].
    dependencies has none), so on a bare interpreter the config silently
    became DEFAULTS — empty exclude lists, a 4000+ issue walk into
    node_modules, exit 0. A ratchet enforcing a baseline it failed to read is
    worse than today's always-zero gate: it looks like a docs violation. The
    fallback is deleted; and report.json must NOT be written (a DEFAULTS
    report would feed Linear a bogus table)."""
    root = build(tmp_path)
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "yaml.py").write_text('raise ImportError("no yaml")\n')
    r = run_validator(root, env=dict(os.environ, PYTHONPATH=str(shim)))
    assert r.returncode == 2
    assert "yaml" in r.stderr.lower()
    assert not (root / "report.json").exists()


def _mutate(cfg_path: Path, kind: str) -> None:
    if kind == "broken":
        cfg_path.write_text("not: a: valid: : yaml\n")
        return
    if kind == "list":
        cfg_path.write_text("- just\n- a\n- list\n")
        return
    cfg = yaml.safe_load(cfg_path.read_text())
    {
        "missing_name": lambda: cfg["retired_name_baseline"].pop("demographics"),
        "no_baseline": lambda: cfg.pop("retired_name_baseline"),
        "no_allowlist": lambda: cfg.pop("dead_reference_allowlist"),
        "entry_incomplete": lambda: cfg["dead_reference_allowlist"][0].pop("reference"),
        "entry_glob": lambda: cfg["dead_reference_allowlist"][0].update(reference="ghost/*"),
        "bad_regex": lambda: cfg["exclude_reference_patterns"].append("te(."),
    }[kind]()
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))


@pytest.mark.parametrize(
    ("kind", "needle"),
    [
        ("broken", "yaml"),
        ("list", "mapping"),
        ("no_baseline", "retired_name_baseline"),
        ("missing_name", "demographics"),
        ("no_allowlist", "dead_reference_allowlist"),
        ("entry_incomplete", "reference"),
        ("entry_glob", "ghost/*"),
        ("bad_regex", "exclude_reference_patterns"),
    ],
)
def test_config_failures_exit_2(tmp_path, kind, needle):
    """Absent baseline keys are NOT read as 0 (would fire on every existing
    mention) and NOT read as unchecked (deleting a key would be the cheapest
    way to disable the gate). They are infrastructure: exit 2, no report."""
    root = build(tmp_path)
    _mutate(root / ".agents-md-validator.yml", kind)
    r = run_validator(root)
    assert r.returncode == 2, r.stdout + r.stderr
    assert needle.lower() in r.stderr.lower()
    assert not (root / "report.json").exists()


def test_missing_config_exits_2(tmp_path):
    """A typo'd --config used to be silently absorbed as DEFAULTS."""
    root = build(tmp_path)
    r = run_validator(root, config=str(root / "no-such-config.yml"))
    assert r.returncode == 2
    assert "config" in r.stderr.lower()
    assert not (root / "report.json").exists()


def test_unbalanced_fence_is_content_not_infrastructure(tmp_path):
    """An open fence would mask the rest of the file from BOTH arms — an
    editor could park anything under an unclosed fence. Measured: 0 of the
    245 scanned files are unbalanced today, so failing on imbalance costs
    nothing now and removes the dodge forever. It is a CONTENT violation
    (exit 1, names the file), not a gate failure — the gate ran fine; the
    file is wrong."""
    root = build(tmp_path)
    amend(root, "\n```\nloose example that never closes\n")
    r = run_validator(root)
    assert r.returncode == 1, r.stderr
    assert "fence" in r.stderr.lower()


def test_report_shape_is_pinned(tmp_path):
    """agents_md_linear_sync.py buckets issues[] by the three EXACT type
    strings and has_issues() is len(issues)>0 — a fourth issue.type would
    make its Linear task claim issues while naming none, and a key inside
    summary{} would change what print_summary sums. issues[]/summary{} are
    byte-frozen; the ratchet's state rides ONLY in the additive top-level
    ratchet block."""
    root = build(tmp_path)
    run_validator(root)
    report = report_of(root)
    assert set(report["summary"]) == {"stale_references", "missing_agents_md", "dead_links"}
    assert {i["type"] for i in report["issues"]} <= {
        "stale_reference",
        "missing_agents_md",
        "dead_link",
    }
    ratchet = report["ratchet"]
    assert set(ratchet["counts"]) == set(RETIRED_NAMES)
    assert set(ratchet["baseline"]) == set(RETIRED_NAMES)
    assert ratchet["counts"] == dict(BASE_BASELINE)
    assert ratchet["violations"] == []


def test_documented_option_set_only(tmp_path):
    """No invented opt-out: every undocumented flag fails closed (argparse,
    rc 2) — no --update (it would rewrite the hand-commented baseline or
    destroy its comments), no --no-teeth/--soft/--warn-only, no --allow FILE
    (a widened allowlist from argv leaves no diff), no --strict (the safe
    config behaviour is default-on, not a flag a future author forgets).
    --root is the only new flag."""
    root = build(tmp_path)
    for opt in ("--update", "--no-teeth", "--soft", "--warn-only", "--allow", "--strict"):
        r = run_validator(root, flags=[opt])
        assert r.returncode == 2, f"{opt} was accepted"
        assert "unrecognized" in (r.stderr + r.stdout).lower()


# --------------------------------------------------------------------------
# The committed real tree — the side CI Gate actually enforces
# --------------------------------------------------------------------------


def test_committed_exclusion_sets_are_pinned():
    """The laundering tripwire itself (see the EXPECTED_* constants). Also
    enforces the allowlist entry schema the loader requires: non-empty
    agents_md/reference AND a tracking ref — a raise must cost a sentence."""
    assert set(COMMITTED_CONFIG["exclude_directories"]) == EXPECTED_EXCLUDE_DIRECTORIES
    assert set(COMMITTED_CONFIG["exclude_reference_patterns"]) == (
        EXPECTED_EXCLUDE_REFERENCE_PATTERNS
    )
    assert set(COMMITTED_CONFIG["retired_name_baseline"]) == set(RETIRED_NAMES)
    for entry in COMMITTED_CONFIG["dead_reference_allowlist"]:
        assert entry.get("agents_md") and entry.get("reference"), entry
        assert entry.get("tracking"), f"allowlist entry without tracking: {entry}"


def test_committed_allowlist_covers_the_venv_pair():
    """The 12-vs-13 pin — the difference between a green first CI run of this
    very package and a red one. `.venv/` is absent on CI and excluded-but-
    present on dev machines; anchored resolution calls it dead on BOTH, so
    the entry must exist."""
    committed = {
        (e["agents_md"], e["reference"]) for e in COMMITTED_CONFIG["dead_reference_allowlist"]
    }
    assert VENV_PAIR in committed


@pytest.fixture(scope="module")
def real_run(tmp_path_factory):
    """One validator run on the REAL tree at the committed config; the three
    real-tree tests read its rc and report instead of each re-walking."""
    out = tmp_path_factory.mktemp("real") / "report.json"
    proc = run_validator(output=str(out))
    with out.open() as f:
        return proc.returncode, json.load(f), proc.stderr


@pytest.mark.timeout(180)  # the walk over 245 files; pyproject global timeout=5
def test_real_tree_is_green(real_run):
    """DONE-WHEN "the run passes on the current tree", executed here — and
    this file runs inside collection-sanity's anti-rot step, which CI Gate
    requires (direct needs + check_job, ci.yml), so THIS assertion is the
    required enforcement the standalone agents-md.yml workflow — which gates
    nothing — never was."""
    rc, _report, stderr = real_run
    assert rc == 0, stderr


@pytest.mark.timeout(180)
def test_real_tree_allowlist_is_exact(real_run):
    """The may-only-fall check that lives in the TEST, not the exit code: a
    zombie allowlist entry stays GREEN at exit (a docs PR must not be
    reddened for an excuse it did not delete) but is RED here, so the entry
    dies in the same PR that drains the pair. The sets measured identical on
    the dev workspace and a clean clone — 13 == 13 — which is what makes
    this assertion machine-independent."""
    rc, report, stderr = real_run
    assert rc == 0, stderr
    committed = {
        (e["agents_md"], e["reference"]) for e in COMMITTED_CONFIG["dead_reference_allowlist"]
    }
    assert dead_pairs(report) == committed, (
        f"drained entries to delete here: {sorted(committed - dead_pairs(report))}; "
        f"un-admitted dead refs to fix: {sorted(dead_pairs(report) - committed)}"
    )


@pytest.mark.timeout(180)
def test_real_tree_scanned_count_floor(real_run):
    """The denominator is pinned because exclude_directories widening
    laundrows the retired-name arm with NO pair-side effect (measured:
    +exclude backend keeps the same dead pairs while nemotron 143 -> 83).
    A FLOOR, not equality: W3.1 may legitimately add AGENTS.md files; if the
    set SHRINKS, someone widened an exclusion — update the floor and say why
    in the same PR."""
    rc, report, _stderr = real_run
    assert rc == 0
    assert report["total_agents_md_files"] >= 245


@pytest.mark.timeout(180)
def test_real_tree_counts_at_or_below_baseline(real_run):
    """The ratchet DIRECTION, measured — not hard-pinned numbers, which the
    first incidental drain PR would redden: the per-name counts may only
    fall, and the numbers themselves live in the config."""
    rc, report, _stderr = real_run
    assert rc == 0
    counts, baseline = report["ratchet"]["counts"], report["ratchet"]["baseline"]
    for name in RETIRED_NAMES:
        assert counts[name] <= baseline[name], name
