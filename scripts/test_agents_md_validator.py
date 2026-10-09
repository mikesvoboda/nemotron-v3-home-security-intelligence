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
(test_committed_exclusion_sets_are_pinned), dead references carry ZERO
tolerance — W1.3 drained and REMOVED dead_reference_allowlist, and the
loader rejects the key's PRESENCE (re-adding an excuse list is a gate-disable
attempt, pinned by test_config_failures_exit_2), resolution is ANCHORED (a path
that exists only inside an excluded directory is dead on every machine), and
retired-name counting is whole-word over the scanned AGENTS.md set only —
"ENRICHMENT_LIGHT_URL" is not "enrichment", and a README next door is not an
AGENTS.md.

Infrastructure vs content is a hard line: a run that COULD NOT happen (config
unreadable, PyYAML missing, baseline incomplete) exits 2 — never 1, which
would blame a docs PR for a broken gate; a CONTENT violation exits 1; and the
report's issues[]/summary{} shape stays byte-identical for
agents_md_linear_sync.py, with the ratchet's own state in one additive
top-level "ratchet" block.
"""

from __future__ import annotations

import collections
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "agents_md_validator.py"
COMMITTED_CONFIG = yaml.safe_load((REPO_ROOT / ".agents-md-validator.yml").read_text())

RETIRED_NAMES = ("florence", "nemotron", "enrichment", "xclip", "demographics")

# Laundering tripwires. exclude_directories and exclude_reference_patterns
# sit in the SAME file as the baselines, and widening either laundrows the
# gate. The design panel's "+exclude backend keeps the SAME dead pairs while
# nemotron 143 -> 83" belongs to the pre-anchor draft: under the shipped
# anchored resolution the pair census DOES react (the same edit reports 138
# stale references, 129 violations). What launders silently is the retired-
# name arm (nemotron 143 -> 83, florence 93 -> 70, no complaint at all), and
# one added exclude_reference_patterns line silently excuses a dead pair from
# report, gate and census alike. Pin the committed sets here: any change must
# edit this constant in the same, reviewed PR.
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

# W1.1's 12-vs-13 trap pair lives here as a lesson, not a constant: anchored
# resolution called `.venv/` dead on EVERY tree (absent on CI, excluded-but-
# present on dev), so W1.1 admitted it; W1.3 drained it by rewriting the
# citation to name the real mechanism instead of the phantom directory (see
# test_committed_tree_has_no_venv_pair).
BASE_MD = """# Fixture

Live: [notes](notes.md)

Names: florence nemotron enrichment xclip demographics.
"""

# W1.3 REMOVED dead_reference_allowlist: the fixture is green by having NO
# dead references (zero tolerance), so there is nothing to mint and no excuse
# list to hand-write. No --mint/--update flag exists on purpose: a flag that
# rewrites a baseline is an opt-out with no diff.
BASE_BASELINE = dict.fromkeys(RETIRED_NAMES, 1)

# W2.1 laundering tripwires, same reasoning as EXPECTED_EXCLUDE_DIRECTORIES:
# boundary_list sits in the SAME file as the baselines, and entries outside it
# are the files W3.1 DELETES — so dropping an entry launders a real AGENTS.md
# into a future deletion, and adding one launders a satellite back into the
# keep set, breaking the plan's "Expect 30 to 50 entries" band one quiet edit
# at a time. line_caps is the third edge: raising a cap to fit a file that
# grew is a baseline raise wearing a different key. Pin all three here; a
# change must edit these constants in the same, reviewed PR.
#
# The list is the membership rule's output, not a hand-tuned set — the rule
# (root + seven lane roots + every >=20-code-file non-test/non-docs/non-archive
# dir that HAS an AGENTS.md + the named/contract dirs) is re-derived from the
# live tree by test_committed_boundary_list_covers_the_rule; this constant
# catches the list drifting WITHOUT the tree moving.
EXPECTED_BOUNDARY_PATHS = {
    ".",
    ".github",
    "ai",
    "ai/gateway",
    "ai/gateway/export",
    ".github/codeql/custom-queries",
    "backend",
    "backend/ai_contract",
    "backend/api",
    "backend/api/middleware",
    "backend/api/routes",
    "backend/api/schemas",
    "backend/core",
    "backend/models",
    "backend/services",
    "frontend",
    "frontend/src",
    "frontend/src/components/ai",
    "frontend/src/components/alerts",
    "frontend/src/components/analytics",
    "frontend/src/components/common",
    "frontend/src/components/dashboard",
    "frontend/src/components/developer-tools",
    "frontend/src/components/entities",
    "frontend/src/components/events",
    "frontend/src/components/face-recognition",
    "frontend/src/components/jobs",
    "frontend/src/components/settings",
    "frontend/src/components/system",
    "frontend/src/components/zones",
    "frontend/src/contexts",
    "frontend/src/hooks",
    "frontend/src/pages",
    "frontend/src/services",
    "frontend/src/stores",
    "frontend/src/types",
    "frontend/src/utils",
    "monitoring",
    "scripts",
    "setup_lib",
    "synthbench",
    "synthbench/contract",
}
# The seven lane roots, spelled out rather than imported. derive() below and
# the tier census here both used set(v.LANE_ROOTS), which made the module's own
# constant free: narrowing LANE_ROOTS to two entries launders five lane-root
# AGENTS.md files into the package tier (cap 500 -> 300) and this file still
# reports green, because derive() rebuilt `roots` from the edited set. Pin the
# set as a literal and assert it against the module (see
# test_committed_boundary_list_and_caps_are_pinned) so the tier a file is
# measured against is a reviewed number, not a module-local one.
EXPECTED_LANE_ROOTS = {
    ".github",
    "ai",
    "backend",
    "frontend",
    "monitoring",
    "scripts",
    "synthbench",
}
# The >= 20 rule does not explain these; they are the rule's named/contract
# arm (40-docs.md's exemplars + cross-lane/CI contracts). Pinned separately
# from the main set so adding a 43rd entry says WHY, in a reviewable place.
# setup_lib is NOT here — it has exactly 20 code files and survives the >= 20
# rule on its own; its own exception is softer (it sits on
# no_agents_md_required, yet the list keeps it — asserted where the rule is).
EXPECTED_RULE_EXCEPTIONS = {
    ".github/codeql/custom-queries",  # CI contract
    "ai/gateway",  # the wire-API contract
    "ai/gateway/export",
    "backend/ai_contract",  # standard-named
    "backend/api",
    "frontend/src",  # standard-named
    "synthbench/contract",  # cross-lane event contract
}
EXPECTED_LINE_CAPS = {"root": 600, "lane_root": 500, "package": 300}
# The rule's one live NOT-listed exception, with its reason (config comment
# carries the same one): >= 20 code files but no AGENTS.md today, and W3.1
# adds none — a listed boundary without a file is a permanent null hole in
# the map the caps arm measures.
RULE_EXCEPTION_NOT_LISTED = {"synthbench/commands"}

_SENTINEL = object()


def build(
    where: Path,
    *,
    md: str = BASE_MD,
    files: dict[str, str] | None = None,
    baseline=_SENTINEL,
    boundary=_SENTINEL,
    caps=_SENTINEL,
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
    write_config(root, baseline=baseline, boundary=boundary, caps=caps)
    return root


def write_config(
    root: Path,
    *,
    baseline=_SENTINEL,
    boundary=_SENTINEL,
    caps=_SENTINEL,
) -> Path:
    config = {
        "exclude_directories": [*COMMITTED_CONFIG["exclude_directories"], "site"],
        "no_agents_md_required": [],
        "code_extensions": list(COMMITTED_CONFIG["code_extensions"]),
        "min_code_files": COMMITTED_CONFIG["min_code_files"],
        "exclude_reference_patterns": list(COMMITTED_CONFIG["exclude_reference_patterns"]),
        "retired_name_baseline": dict(BASE_BASELINE) if baseline is _SENTINEL else baseline,
        # W2.1 keys are loader-mandatory, so the fixture carries them too.
        # The fixture's only scanned file is the root AGENTS.md, so the root
        # boundary is the honest one-entry list; caps default generous so the
        # green fixture stays green on the reporting arm unless a test pins
        # them low on purpose.
        "boundary_list": (
            [{"path": ".", "reason": "the fixture's only boundary"}]
            if boundary is _SENTINEL
            else boundary
        ),
        "line_caps": (
            {"root": 1000, "lane_root": 1000, "package": 1000} if caps is _SENTINEL else caps
        ),
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
# Done-when A: a dead reference fails, full stop — W1.3 removed the excuse list
# --------------------------------------------------------------------------


def test_green_fixture_is_green(tmp_path):
    """The harness is not vacuously red: the clean fixture passes and reports
    NO dead pairs — under W1.3 zero tolerance, green means EMPTY, not
    "everything excused"."""
    root = build(tmp_path)
    r = run_validator(root)
    assert r.returncode == 0, r.stderr
    assert dead_pairs(report_of(root)) == set()


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


def test_dead_reference_fails_and_the_key_stays_dead(tmp_path):
    """Both sides of zero tolerance (W1.3 removed the allowlist): a dead
    reference reddens the run directly, AND re-adding the config key is
    infrastructure, not an excuse channel — the loader exits 2 on its mere
    presence, so no PR can reinstate pardons by editing YAML."""
    root = build(tmp_path)
    amend(root, "\nDead: `ghost/b/`.\n")
    r = run_validator(root)
    assert r.returncode == 1
    assert "ghost/b/" in r.stderr
    cfg_path = root / ".agents-md-validator.yml"
    cfg = yaml.safe_load(cfg_path.read_text())
    cfg["dead_reference_allowlist"] = [
        {"agents_md": "AGENTS.md", "reference": "ghost/b/", "tracking": "fixture"}
    ]
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    r = run_validator(root)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "dead_reference_allowlist" in r.stderr


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
    r = run_validator(root)  # rc 1: zero tolerance — dead is dead, no excuse list
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
    # Anchored on the message, not bare digits: an earlier version asserted
    # "2" and "1" in stderr, and a mutant that hardcoded a different baseline
    # STILL PASSED because the "1 violation(s)" summary line supplies the "1".
    assert "measured 2 > baseline 1" in r.stderr


def test_enrichment_light_url_is_not_enrichment(tmp_path):
    """Whole-word is load-bearing, pinned: \\w includes the underscore, so
    the shipped identifier ENRICHMENT_LIGHT_URL is NOT an `enrichment`
    mention under \\b — and it is not hypothetical, docker-compose.prod.yml
    and setup.py export it today. A substring implementation would count it
    (and every other *_ENRICHMENT_* form), measuring a different quantity
    than the plan named and reddening any PR that names the identifier.
    This fixture passes whole-word and REDDENS under substring (2 > 1).
    (This pin previously rode on pose, which the owner ruled OUT of the
    ratchet on #6870 — the name is dominated by the live Triton `pose`
    model. The boundary lesson is name-independent; the underscore case is
    the one the shipped identifier set actually exercises.)"""
    root = build(tmp_path)
    amend(root, "\nCompose exports ENRICHMENT_LIGHT_URL for the gateway.\n")
    r = run_validator(root)
    assert r.returncode == 0, r.stderr


def test_substitution_does_not_green_a_total(tmp_path):
    """Per-name baselines, not one total: +1 florence bought with -1
    demographics holds the total at baseline (5 == 5) — a totals-only
    implementation returns green here and launders by substitution."""
    root = build(
        tmp_path,
        md="# Fixture\n\nLive: [notes](notes.md)\n\n"
        "Names: florence florence nemotron enrichment xclip.\n",
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


# W3.1 boundary mode (UR-21) — the wiring this file's W1.1 scope pin deferred:
# "required at each boundary, forbidden elsewhere". W1.1's replaced pin read
# "missing_agents_md stays reporting-only"; the pair-sides below are its
# successor. The arms are CONTENT (exit 1), not infra: a docs PR that deletes
# a boundary file or adds a satellite caused the violation itself.
#
# issues[] stays byte-frozen for linear_sync (test_report_shape_is_frozen),
# so the two sides enter the report differently BY DESIGN: the missing side
# REUSES the missing_agents_md type (linear_sync's tickets now mean "a hole in
# the boundary map", not a satellite flood), while the forbidden side is a
# violation string with no issue type at all — the same rail unbalanced_fences
# rides. A new issue type here would make linear_sync claim issues it cannot
# name; the type-freeze pair-side below pins that.


def test_boundary_mode_satellite_code_dir_is_green(tmp_path):
    """The UR-21 floor: a non-boundary directory with code files requires NO
    AGENTS.md and reports nothing — the rule is about FILES at boundaries, not
    dirs needing one. W1.1's code-file census is retired; a mutant that keeps
    flagging satellite dirs fails here (issue side) and below (exit side)."""
    root = build(tmp_path, files={"src/a.py": "", "src/b.py": "", "src/c.py": ""})
    r = run_validator(root)
    assert r.returncode == 0, r.stderr
    types = [i["type"] for i in report_of(root)["issues"]]
    assert "missing_agents_md" not in types


def test_boundary_mode_missing_boundary_file_fails(tmp_path):
    """Required side, violating half: a listed boundary without its AGENTS.md
    is a hole in the prune map — exit 1, and the issue rides the EXISTING
    missing_agents_md type so linear_sync keeps its ticket stream. The root
    AGENTS.md is what build() writes, so the fixture deletes the second
    boundary's file to open the hole."""
    root = build(
        tmp_path,
        files={"backend/keep.py": ""},
        boundary=[
            {"path": ".", "reason": "the fixture root"},
            {"path": "backend", "reason": "a boundary whose file went missing"},
        ],
    )
    (root / "backend" / "AGENTS.md").exists()  # build never writes one; sanity
    r = run_validator(root)
    assert r.returncode == 1, r.stdout + r.stderr
    holes = [i for i in report_of(root)["issues"] if i["type"] == "missing_agents_md"]
    assert [i["directory"] for i in holes] == ["backend/"]


def test_boundary_mode_missing_boundary_pair_side(tmp_path):
    """Required side, green half: the same two-boundary fixture WITH the file
    present stays green — otherwise the missing arm above passes on a rule
    that simply fails every two-boundary tree."""
    root = build(
        tmp_path,
        files={"backend/keep.py": "", "backend/AGENTS.md": "# Backend\n\nlive: [n](../notes.md)\n"},
        boundary=[
            {"path": ".", "reason": "the fixture root"},
            {"path": "backend", "reason": "a boundary with its file"},
        ],
    )
    r = run_validator(root)
    assert r.returncode == 0, r.stdout + r.stderr


def test_boundary_mode_satellite_agents_md_forbidden(tmp_path):
    """Forbidden side, violating half: an AGENTS.md outside the boundary list
    fails the run (UR-21: files live only at boundaries) — but as a violation
    STRING only. The forbidden file must appear in NO issue: the issue-type
    vocabulary is byte-frozen, so the forbidden arm rides the fence arm's rail
    (a violation with no issues[] entry)."""
    root = build(
        tmp_path,
        files={"src/extra/AGENTS.md": "# Satellite\n\nlive: [n](../../notes.md)\n"},
        boundary=[{"path": ".", "reason": "the only boundary"}],
    )
    r = run_validator(root)
    assert r.returncode == 1, r.stdout + r.stderr
    out = r.stdout + r.stderr
    assert "src/extra/AGENTS.md" in out and "boundary" in out.lower()
    report = report_of(root)
    assert [i for i in report["issues"] if i.get("agents_md") == "src/extra/AGENTS.md"] == []
    assert set(report["summary"]) == {"stale_references", "missing_agents_md", "dead_links"}


def test_boundary_mode_forbidden_pair_side(tmp_path):
    """Forbidden side, green half: with no satellite file the same fixture is
    green (build()'s root AGENTS.md is the listed boundary) — the arm fails
    satellites, not every tree."""
    root = build(tmp_path, boundary=[{"path": ".", "reason": "the only boundary"}])
    r = run_validator(root)
    assert r.returncode == 0, r.stdout + r.stderr


def test_boundary_mode_deleting_the_satellite_is_the_fix(tmp_path):
    """The remediation direction W3.1's deletion batches rely on: the red run
    flips green by DELETING the satellite (no excuse flag, no config edit) —
    the violation message names the file, and the same tree minus the file is
    green with issues[] unchanged."""
    root = build(
        tmp_path,
        files={"src/extra/AGENTS.md": "# Satellite\n\nlive: [n](../../notes.md)\n"},
        boundary=[{"path": ".", "reason": "the only boundary"}],
    )
    assert run_validator(root).returncode == 1
    (root / "src" / "extra" / "AGENTS.md").unlink()
    r = run_validator(root)
    assert r.returncode == 0, r.stdout + r.stderr
    assert report_of(root)["issues"] == []


def test_boundary_mode_no_opt_out_flag(tmp_path):
    """No invented off-switch for the new arms: the red fixture stays red
    under every plausible-sounding flag (the documented-option-set doctrine
    extended to W3.1's rule — boundary mode is not negotiable by argv)."""
    root = build(
        tmp_path,
        files={"src/extra/AGENTS.md": "# Satellite\n\nlive: [n](../../notes.md)\n"},
        boundary=[{"path": ".", "reason": "the only boundary"}],
    )
    for opt in ("--no-boundary", "--boundary-off", "--legacy-missing", "--ignore-satellites"):
        r = run_validator(root, flags=[opt])
        assert r.returncode == 2, f"{opt} was accepted"
        assert "unrecognized" in (r.stderr + r.stdout).lower()


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
        "allowlist_present": lambda: cfg.update(
            dead_reference_allowlist=[
                {"agents_md": "AGENTS.md", "reference": "ghost/a.py", "tracking": "x"}
            ]
        ),
        "bad_regex": lambda: cfg["exclude_reference_patterns"].append("te(."),
        # W2.1's two arms, same doctrine as the baselines: dropping a key is
        # the cheapest way to disable the arm, so absent is infrastructure.
        "no_boundaries": lambda: cfg.pop("boundary_list"),
        "boundary_incomplete": lambda: cfg.update(
            boundary_list=[{"path": ".", "reason": "ok"}, {"path": "backend"}]
        ),
        "boundary_duplicate": lambda: cfg.update(
            boundary_list=[
                {"path": ".", "reason": "once"},
                {"path": ".", "reason": "twice — a set with two labels on one dir"},
            ]
        ),
        "missing_tier": lambda: cfg["line_caps"].pop("package"),
    }[kind]()
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))


@pytest.mark.parametrize(
    ("kind", "needle"),
    [
        ("broken", "yaml"),
        ("list", "mapping"),
        ("no_baseline", "retired_name_baseline"),
        ("missing_name", "demographics"),
        ("allowlist_present", "dead_reference_allowlist"),
        ("bad_regex", "exclude_reference_patterns"),
        ("no_boundaries", "boundary_list"),
        ("boundary_incomplete", "reason"),
        ("boundary_duplicate", "duplicate"),
        ("missing_tier", "package"),
    ],
)
def test_config_failures_exit_2(tmp_path, kind, needle):
    """Absent baseline keys are NOT read as 0 (would fire on every existing
    mention) and NOT read as unchecked (deleting a key would be the cheapest
    way to disable the gate). They are infrastructure: exit 2, no report. The
    allowlist_present row is the mirror image: since W1.3 the REMOVED key's
    presence is the gate-disable attempt, so re-adding it exits 2 too —
    the anti-rot side of the drain.

    W2.1 rides the same doctrine: no_boundaries (deleting boundary_list would
    be deleting W3.1's prune map), boundary_incomplete (a boundary with no
    reason is a boundary nobody can defend at review), boundary_duplicate
    (the list is a SET — two labels on one dir is the map disagreeing with
    itself), missing_tier (a cap config missing the package tier would leave
    every non-root boundary file uncapped, which is 'caps off' wearing a
    config file)."""
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
    139 scanned files are unbalanced today (245 before W3.1 batch 1's
    deletions, 139 after batch 8; re-measured at each: still zero), so failing on imbalance costs
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
    # W2.1 doc-sync: the additive block gained line_caps. issues[]/summary{}
    # are frozen for the linear sync; the ratchet keys are additively allowed,
    # so a new one is allowed by construction — this pin makes its arrival a
    # reviewed edit to THIS line instead of an invisible addition.
    assert set(ratchet) == {
        "counts",
        "baseline",
        "violations",
        "unbalanced_fences",
        "line_caps",
    }


def test_line_caps_report_every_tier_and_never_fail(tmp_path):
    """W2.1's reporting arm, all four tier arms + the missing-file arm, in
    one fixture, and the mode: caps NEVER fail the run until W3.2 flips
    `failing`. Over-cap boundary files are W3.2's work list, so the SET is
    what is pinned — path, tier, cap, measured — not a count.

    A cap that failed on adoption would redden every PR touching a file that
    is itself scheduled to be rewritten (measured in PR #6920: 29 of the 42
    committed boundary files are over cap today, backend/services by 2864
    lines). Green-on-caps is therefore the pinned behaviour, not an oversight
    — and `failing: False` is pinned False so W3.2's flip is a reviewed edit
    to the validator, not a silent drift.

    The `backend/models` fixture entry is the case the real tree cannot supply:
    a file whose line count EQUALS its cap, which must NOT be reported (a cap is
    a maximum, not a trigger). No committed boundary file sits at one — the
    smallest |lines - cap| anywhere on the real tree is 18
    (frontend/src/components/developer-tools, 318 against the 300 cap), and
    shifting every cap by ±5 leaves the over-set at 29 — so a `>` slipping to
    `>=` is invisible to every real-tree assertion in this file. Confirmed by
    mutation, not inference: flipping the comparison reddens THIS test and leaves
    all five real-tree tests green. That is the pair-sides rule's untested
    direction, pinned here instead."""
    boundary = [
        {"path": ".", "reason": "root"},
        {"path": "backend", "reason": "lane root"},
        {"path": "ai/gateway", "reason": "package"},
        {"path": "scripts", "reason": "lane root, under cap"},
        {"path": "synthbench/contract", "reason": "boundary with no AGENTS.md"},
        {"path": "backend/models", "reason": "package, exactly at cap"},
    ]
    long_enough = "# Fixture\n\n" + "body\n" * 20
    root = build(
        tmp_path,
        files={
            "backend/AGENTS.md": long_enough,
            "ai/gateway/AGENTS.md": long_enough,
            "scripts/AGENTS.md": "# Short\n",
            # exactly the package cap (10 lines), no more — measured by the same
            # splitlines rule the validator uses, so this is equality, not a
            # newline-counting artefact.
            "backend/models/AGENTS.md": "body\n" * 10,
        },
        boundary=boundary,
        caps={"root": 3, "lane_root": 10, "package": 10},
    )
    r = run_validator(root)
    # W3.1 changed WHY this run is red, not the caps claim. The fixture's
    # synthbench/contract boundary has no AGENTS.md — under W2.1 that was
    # merely reported; under W3.1 a hole in the boundary map is a CONTENT
    # violation, so rc is 1. What "caps NEVER fail" now means, pinned exactly:
    # no violation string is cap-derived, and the caps block's own verdict
    # field stays False.
    assert r.returncode == 1, r.stdout + r.stderr
    report = report_of(root)
    block = report["ratchet"]["line_caps"]
    assert block["failing"] is False
    assert block["boundaries"] == 6
    assert block["measured"] == 5  # the sixth has no AGENTS.md to measure
    over = {e["path"]: e for e in block["over"]}
    assert over["AGENTS.md"]["tier"] == "root"
    assert over["backend/AGENTS.md"]["tier"] == "lane_root"
    assert over["ai/gateway/AGENTS.md"]["tier"] == "package"
    assert over["backend/AGENTS.md"]["cap"] == 10
    assert over["AGENTS.md"]["measured"] > over["AGENTS.md"]["cap"]
    assert "scripts/AGENTS.md" not in over  # under cap => not on the work list
    # exactly AT cap => not over. The line above covers under-cap; this covers
    # the boundary itself (see the docstring: the real tree has no such file).
    assert "backend/models/AGENTS.md" not in over, (
        "a file whose line count equals its cap was reported over — the "
        "comparison is `> cap` (a maximum), not `>= cap` (a trigger)"
    )
    # The missing-file arm is REPORTED, not skipped: a boundary the scan never
    # saw is a hole in the prune map, and skipping it would shrink the map
    # silently (the vacuous-comparison failure mode).
    hole = over["synthbench/contract/AGENTS.md"]
    assert hole["measured"] is None
    assert hole["tier"] == "package"
    # Caps stay reporting-only in the strongest sense available since W3.1:
    # the gate's verdict vector is non-empty ONLY because of the boundary hole
    # — zero cap-derived strings. The same fixture minus the hole is green:
    # test_boundary_mode_missing_boundary_pair_side.
    violations = report["ratchet"]["violations"]
    assert len(violations) == 1 and "synthbench/contract/" in violations[0]
    assert not [v for v in violations if "cap" in v.lower()]


def test_caps_apply_to_boundary_files_only(tmp_path):
    """The other side of the rule. A non-boundary AGENTS.md far over every
    cap is NOT on the work list: capping a file the boundary rule has already
    condemned is noise, not a ratchet. A one-sided test would pass if the arm
    measured every AGENTS.md it walked.

    W3.1's pair-side caveat, stated honestly: this fixture now exits 1 (the
    satellite is forbidden) where it exited 0 under W2.1 — the caps assertion
    is what this test is FOR, and the run being red is pinned separately by
    the boundary-mode tests. The caps block still measures only the boundary
    file, which is exactly the claim being pinned."""
    root = build(
        tmp_path,
        files={"backend/satellite/AGENTS.md": "# Satellite\n\n" + "body\n" * 200},
        boundary=[{"path": ".", "reason": "the only boundary"}],
        caps={"root": 1000, "lane_root": 1000, "package": 10},
    )
    r = run_validator(root)
    assert r.returncode == 1, r.stdout + r.stderr  # forbidden since W3.1
    block = report_of(root)["ratchet"]["line_caps"]
    assert [e["path"] for e in block["over"]] == []
    assert block["boundaries"] == 1
    assert block["measured"] == 1


def test_documented_option_set_only(tmp_path):
    """No invented opt-out: every undocumented flag fails closed (argparse,
    rc 2) — no --update (it would rewrite the hand-commented baseline or
    destroy its comments), no --no-teeth/--soft/--warn-only, no --allow FILE
    (an argv excuse list leaves no diff — and since W1.3 neither does the
    YAML key), no --strict (the safe
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
    pins that the committed config does NOT carry the removed allowlist key —
    the loader exits 2 on its presence, so this is a green-build pin, not
    style."""
    assert set(COMMITTED_CONFIG["exclude_directories"]) == EXPECTED_EXCLUDE_DIRECTORIES
    assert set(COMMITTED_CONFIG["exclude_reference_patterns"]) == (
        EXPECTED_EXCLUDE_REFERENCE_PATTERNS
    )
    assert set(COMMITTED_CONFIG["retired_name_baseline"]) == set(RETIRED_NAMES)
    assert "dead_reference_allowlist" not in COMMITTED_CONFIG


@pytest.mark.timeout(180)  # the walk over every code file in the tree
def test_committed_boundary_list_covers_the_rule():
    """W2.1's Done-when half: the committed list IS the membership rule,
    re-derived here from the live tree rather than compared to a transcription
    of itself.

    The rule (config header, same words): root + the seven lane roots + every
    directory with >= 20 code files that is not a test/docs/archive dir and
    HAS an AGENTS.md today + the dirs the standard names or that guard a
    cross-lane/CI contract.

    >= 20 is a measured choice, not a round one, and it is measured HERE rather
    than quoted from a census nobody can re-run. State what the measurement
    supports, including the part that refutes the argument the first version of
    this docstring made. The plan says "Expect 30 to 50 entries"; that band is a
    WEAK filter here, not a selector — measured over thresholds 1..60 at this
    tree, thresholds 11 through 46 ALL land inside it (36 of the 60 values), so
    the band rules out >= 10 (52 entries) and >= 47 (29) and says nothing at all
    about 20 vs 15. It is kept as a coarse guard: a rule edit that puts a
    threshold's output outside the band is selecting the wrong thing.

    What does discriminate 20 is structural, and it is a keep-argument rather
    than a cut-argument: the committed set is a PLATEAU, equal at thresholds
    18, 19 and 20, so the exact number inside the plateau is not load-bearing —
    what is load-bearing is the plateau's two edges, and both are asserted
    below.

    - Its top edge: >= 21 drops setup_lib, which has exactly 20 code files and
      NO kept ancestor at all — it is a top-level package, so at >= 21 the tree
      carries a real package that no boundary file covers. Every other entry a
      tighter cut drops (frontend/src/stores at 21; components/alerts and
      src/contexts at 22) is a satellite that folds into frontend/src.
      setup_lib is also, measured, the ONLY entry the size rule keeps with no
      proper kept ancestor: the other 26 have one. So "20" is "the largest
      threshold that still covers the one orphan package".
    - Its bottom edge: every entry a looser cut adds is a parent-split —
      >= 17 and >= 16 add exactly one dir, components/settings/prompts (17 code
      files, under the listed components/settings); >= 15 adds audit,
      common/skeletons and src/schemas, all under frontend/src. The standard's
      doctrine is that a satellite folds into its nearest kept ancestor, so no
      threshold below the plateau can be defended on the rule's own terms. (A
      previous draft of this paragraph claimed the marginal additions were "all
      top-level packages, none a parent-split" — that is the exact inverse of
      what the loop below asserts, which is why the loop asserts it rather than
      the prose claiming it.)

    The plateaus, band memberships and ancestor relations above are RE-DERIVED
    from the live tree below, not quoted: a tree that grows a top-level package
    past 20 files, orphans an entry, or moves a satellite, moves these
    assertions with it. The numbers are stated so a reader can re-run the
    measurement and see the argument, not so this file can be believed.

    Non-vacuity, since a rule that keeps everything and a rule that keeps
    nothing both "match" a hand-written list if written carelessly: the
    >= 20 population BEFORE the test/docs/archive cut must be strictly larger
    than the kept set (the cut removed real dirs), at least one >= 20 dir is
    deliberately not listed (the has-an-AGENTS.md arm, RULE_EXCEPTION_NOT_
    LISTED), and the named/contract arm must be non-empty.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import agents_md_validator as v  # the module under test, function-scoped

    config = v.load_config(REPO_ROOT / ".agents-md-validator.yml", REPO_ROOT)
    # relative_to, not str(p): find_directories_with_code returns absolute
    # dirs when handed an absolute root (the validator's own main() hands it a
    # relative one, which is why the report's keys are repo-relative). The
    # config's paths and the report's are both repo-relative — compare like
    # for like, or every entry mismatches on the prefix.
    counts = {
        str(p.relative_to(REPO_ROOT)): len(f)
        for p, f in v.find_directories_with_code(REPO_ROOT, config).items()
    }

    def self_indexed(dir_path: str) -> bool:
        parts = PurePosixPath(dir_path).parts
        return any(p in ("tests", "__tests__", "test", "archive") for p in parts) or (
            parts[:1] == ("docs",)
        )

    # EXPECTED_LANE_ROOTS, NOT set(v.LANE_ROOTS): deriving `roots` from the
    # module makes the module's own constant free here, so editing LANE_ROOTS
    # would move this test's expectations with it. The module's copy is asserted
    # equal to the literal in test_committed_boundary_list_and_caps_are_pinned.
    roots = EXPECTED_LANE_ROOTS | {"."}

    def derive(threshold: int) -> set[str]:
        """The rule as the config comment states it, at one threshold."""
        kept = {
            d
            for d, n in counts.items()
            if n >= threshold and not self_indexed(d) and (REPO_ROOT / d / "AGENTS.md").is_file()
        }
        return kept | roots | EXPECTED_RULE_EXCEPTIONS

    big = {d for d, n in counts.items() if n >= 20}
    rule_kept = {d for d in big if not self_indexed(d) and (REPO_ROOT / d / "AGENTS.md").is_file()}
    derived = derive(20)
    assert derived == rule_kept | roots | EXPECTED_RULE_EXCEPTIONS  # derive == the spelled-out set

    committed = {entry["path"] for entry in config.boundary_list}
    assert derived == committed, (
        f"rule-kept-not-listed: {sorted(derived - committed)}; "
        f"listed-not-by-rule: {sorted(committed - derived)}"
    )
    # The cuts and the exceptions did real work (anti-vacuity).
    assert len(big) > len(rule_kept), "the test/docs/archive cut removed nothing"
    # The has-an-AGENTS.md arm's exceptions: >= 20 code files, NOT
    # self-indexed, and still not kept. This set changing means someone gave
    # (or removed) a file at a dir the rule was measured against — re-check
    # whether it should now be listed.
    no_file = {
        d for d in big if not self_indexed(d) and not (REPO_ROOT / d / "AGENTS.md").is_file()
    }
    assert no_file - roots == RULE_EXCEPTION_NOT_LISTED, (
        f"the >= 20 dirs with no AGENTS.md changed: {sorted(no_file - roots)}"
    )
    # The named/contract arm is not vacuous either: none of it would survive
    # the >= 20 rule on its own.
    assert EXPECTED_RULE_EXCEPTIONS - rule_kept - roots == EXPECTED_RULE_EXCEPTIONS
    assert len(big) >= 40 and committed - big, "the rule is doing nothing"
    # setup_lib's softer exception, spelled out because it is the only entry
    # the two lists disagree about: no_agents_md_required says the file is not
    # REQUIRED, boundary_list says it is KEPT (its config reason says so).
    # Both are true — the first is W3.1's required-rule input, the second its
    # delete-don't-add input. Assert it stays a deliberate overlap, not a
    # copy-paste: drop it and W3.1 deletes the file the exception comment
    # exists to protect.
    assert "setup_lib/" in config.no_agents_md_required
    assert "setup_lib" in committed

    # Every entry: a real directory, a real AGENTS.md, a non-empty reason
    # (the loader enforces the reason too — this is the cheap version of
    # "the committed config would not have parsed at all", and it names the
    # offender instead of exiting 2 from inside the import).
    for entry in config.boundary_list:
        d = entry["path"]
        assert (REPO_ROOT / d).is_dir(), d
        assert (REPO_ROOT / d / "AGENTS.md").is_file(), f"{d} has no AGENTS.md"
        assert entry["reason"].strip(), d
    assert 30 <= len(committed) <= 50, f"outside the plan's 30-50 band: {len(committed)}"
    # The band as a COARSE guard only — see the docstring: thresholds 11..46 all
    # land inside it at this tree, so being in-band is not the argument for 20.
    # Only the looser side is asserted, because that is the side that stays true
    # as the tree grows (more dirs -> bigger lists); asserting the tight side
    # (>= 47 falls out at 29 today) would redden a green rule for an unrelated
    # package gaining files.
    assert len(derive(5)) > 50 and len(derive(10)) > 50, "a looser threshold now fits the band"

    def proper_ancestors(candidate: str, base: set[str]) -> list[str]:
        """Kept directories that STRICTLY contain `candidate`. `.` is out — it is
        the root and matches every path. The candidate itself is out because
        Path.is_relative_to is REFLEXIVE: a base that contains the candidate
        would otherwise report it as its own parent. (The first version of this
        filter dropped only `.`; harmless where it sat, because a marginal
        candidate is by construction absent from the base — but this helper runs
        against both the committed set and other thresholds' sets below.)"""
        return [
            kept
            for kept in base
            if kept not in (".", candidate) and PurePosixPath(candidate).is_relative_to(kept)
        ]

    # --- 20 sits on a PLATEAU, and the plateau's two edges are the argument ---
    plateau = [t for t in range(10, 31) if derive(t) == committed]
    assert 20 in plateau, (
        f">= 20 no longer reproduces the committed list (sizes: {sorted(plateau)})"
    )
    assert len(plateau) >= 2, "the threshold is knife-edge, not a plateau — re-derive the census"
    assert 17 not in plateau and 21 not in plateau, (
        "the plateau widened past 17/21 — re-read the edges"
    )
    # The TOP edge, and why the plateau's top is the right place to sit: >= 21
    # drops setup_lib (exactly 20 code files), the one entry with NO kept
    # ancestor — a top-level package that at >= 21 would be covered by no
    # boundary file at all. Every other drop at 21 is a satellite that folds
    # into frontend/src.
    dropped = committed - derive(21)
    assert dropped, ">= 21 is identical to >= 20 — the top edge is doing nothing"
    assert {d for d in dropped if not proper_ancestors(d, derive(21))} == {"setup_lib"}, (
        f"which entries >= 21 drops (or their ancestry) changed: {sorted(dropped)} — "
        "the keep-argument for the threshold is that exactly one of them is an orphan"
    )
    # The same property stated about the whole kept set rather than one step: of
    # the entries the SIZE rule explains (not a lane root, not a named/contract
    # exception), setup_lib is the only orphan. If a second orphan appears the
    # threshold has to be re-argued, because "largest threshold that still
    # covers the orphan packages" is a different number.
    size_kept = derive(20) - roots - EXPECTED_RULE_EXCEPTIONS
    assert {d for d in size_kept if not proper_ancestors(d, committed)} == {"setup_lib"}
    # The BOTTOM edge: everything a looser cut adds is a parent-split, so no
    # threshold below the plateau is defensible on the standard's own doctrine
    # (a satellite folds into its nearest kept ancestor rather than duplicating
    # its map). A new TOP-level package crossing one of these file counts makes
    # this fire — that is the threshold being re-debated on real evidence, which
    # is the intended behaviour, not a flake.
    for looser in (15, 16, 17):
        added = derive(looser) - committed
        assert added, (
            f">= {looser} adds nothing over the committed set — the cut is not the discriminator"
        )
        for candidate in added:
            assert proper_ancestors(candidate, committed), (
                f"{candidate} is a top-level package >= {looser} would keep and "
                "the standard's satellite doctrine cannot fold away"
            )


def test_committed_boundary_list_and_caps_are_pinned():
    """The laundering tripwire for the two W2.1 keys (see the EXPECTED_*
    constants): the list set, and the caps. Raising a cap to fit a file that
    grew is a baseline raise by another name — W3.2 rewrites the file.

    Three more edges ride here, all of them the "silently smaller denominator"
    shape the caps arm is exposed to:
    - v.LANE_ROOTS vs the literal. The tier a file is measured against comes
      from this set, and the module's copy was the only version of it that the
      tests read — so shrinking it (say to {"backend", "frontend"}) re-tiers five
      lane roots from cap 500 to cap 300, moves the over-cap set, and reddens
      nothing here because derive() rebuilt `roots` from the same edited set.
      That is the review-blind edit the docstring above is about.
    - The tier CENSUS of the committed list. The report's `measured == 42` says
      every listed path resolved to a file; it does not say the 42 still SORT
      1/7/34. A lane root that loses its AGENTS.md, or a boundary renamed out of
      a lane root, silently moves files between caps.
    - The census is asserted against boundary_tier(), the module's own
      classifier, which is the right way round for a pin: the literals fix HOW
      MANY files belong in each tier, the module supplies which. Any edit that
      moves a file between tiers then reddens one of the three counts — dropping
      the root special case puts "." in the package tier (cap 300 against a
      505-line root file), returning lane_root by path depth instead of by
      LANE_ROOTS moves frontend/src up a tier, and a typo'd tier name fails the
      total. A hard-coded path-per-tier list would have caught the same edits but
      would have to be rewritten to match whatever the bug turned out to be.
    """
    assert {e["path"] for e in COMMITTED_CONFIG["boundary_list"]} == EXPECTED_BOUNDARY_PATHS
    assert COMMITTED_CONFIG["line_caps"] == EXPECTED_LINE_CAPS
    assert set(COMMITTED_CONFIG["line_caps"]) == {"root", "lane_root", "package"}

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import agents_md_validator as v

    assert set(v.LANE_ROOTS) == EXPECTED_LANE_ROOTS, (
        "the module's lane-root set moved without the test's literal — the tier "
        "(and therefore the cap) of every boundary file under it moved with it"
    )
    committed = {e["path"] for e in COMMITTED_CONFIG["boundary_list"]}
    census = collections.Counter(v.boundary_tier(p) for p in committed)
    assert census["root"] == 1, census
    assert census["lane_root"] == len(EXPECTED_LANE_ROOTS) == 7, census
    assert census["package"] == len(EXPECTED_BOUNDARY_PATHS) - 1 - 7 == 34, census
    assert sum(census.values()) == len(EXPECTED_BOUNDARY_PATHS) == 42, (
        f"boundary_tier() returned a tier outside the three capped ones: {census}"
    )


def test_committed_tree_has_no_venv_pair():
    """The 12-vs-13 pair, drained rather than admitted: the codeql custom-
    queries citation that anchored resolution called dead on EVERY tree (so a
    dev-machine "fix" could never green CI) now names the real mechanism — the
    committed codeql config's paths-ignore patterns — which exists on both CI
    and dev trees. The bare backticked form is the extractable pair; the
    real-tree zero-dead test below is the general pin."""
    text = (REPO_ROOT / ".github/codeql/custom-queries/AGENTS.md").read_text()
    assert "codeql-config.yml" in text
    assert "`" + ".venv/" + "`" not in text


@pytest.fixture(scope="module")
def real_run(tmp_path_factory):
    """One validator run on the REAL tree at the committed config; the four
    real-tree tests read its rc and report instead of each re-walking."""
    out = tmp_path_factory.mktemp("real") / "report.json"
    proc = run_validator(output=str(out))
    with out.open() as f:
        return proc.returncode, json.load(f), proc.stderr


@pytest.mark.timeout(180)  # the walk over 139 files; pyproject global timeout=5
def test_real_tree_is_green(real_run):
    """DONE-WHEN "the run passes on the current tree", executed here — and
    this file runs inside collection-sanity's anti-rot step, which CI Gate
    requires (direct needs + check_job, ci.yml), so THIS assertion is the
    required enforcement the standalone agents-md.yml workflow — which gates
    nothing — never was."""
    rc, _report, stderr = real_run
    assert rc == 0, stderr


@pytest.mark.timeout(180)
def test_real_tree_has_zero_dead_references(real_run):
    """W1.3's Done-when, asserted: the real tree reports NO dead file
    references at all — the number the gate stands on, not a census matched
    against an excuse list. Anchored resolution is what makes the assertion
    machine-independent: W1.1's dev-vs-clean-clone delta (13 == 13 pairs) is
    now 0 == 0."""
    rc, report, stderr = real_run
    assert rc == 0, stderr
    assert dead_pairs(report) == set(), f"dead pairs: {sorted(dead_pairs(report))}"


@pytest.mark.timeout(180)
def test_real_tree_scanned_count_floor(real_run):
    """The denominator is pinned because exclude_directories widening launders
    the retired-name arm silently (measured: +exclude backend drops nemotron
    143 -> 83 and florence 93 -> 70 with no baseline edit). The dead-reference
    arm at least reacts under anchored resolution — the same edit reports 138
    stale references — but a shrunk denominator is invisible without this
    floor. A FLOOR, not equality: W3.1 may legitimately add AGENTS.md files;
    if the set SHRINKS, someone widened an exclusion — update the floor and
    say why in the same PR.

    A second legitimate shrink exists: W3.1's own deletions. The tree measured
    245 before batch 1 — 42 boundaries plus 203 satellites — and the floor
    moved to 235 = 245 - 10 when that batch deleted the ten synthbench
    satellite guides, then to 225 = 235 - 10 at batch 2 (the ten ai/ satellite
    guides under the ai, ai/gateway and ai/gateway/export boundaries), then to
    217 = 225 - 8 at batch 3 (the eight scripts/ satellites under the scripts
    lane root), then to 211 = 217 - 6 at batch 4 (the six monitoring/
    satellites under the monitoring lane root), then to 205 = 211 - 6 at batch
    5 (the six tail singletons: tests, tests/benchmark, tests/load, data,
    docker, archive/vsftpd — none of them a boundary), then to 160 = 205 - 45
    at batch 6 (the backend/tests/** subtree — 45 guides, none of them a
    boundary; the parent backend/tests/AGENTS.md was a zero-byte file), then to
    149 = 160 - 11 at batch 7 (the eleven remaining backend non-test satellites:
    repositories, examples, jobs, core/websocket, config, scripts,
    services/orchestrator, evaluation, api/utils, core/middleware,
    ai_contract/fake — the core/middleware guide documented a directory whose
    only file was that guide), then to 139 = 149 - 10 at batch 8 (the ten
    frontend/src test-tree and mock-cluster guides: mocks, __mocks__,
    hooks/__mocks__, test, test/factories, __tests__, test-utils,
    hooks/__tests__, hooks/__tests__/integration, types/__tests__ — none of
    them a boundary; an eleventh deletion, the integration README twin,
    republished the same fiction and is not an AGENTS.md, so the floor moves by
    ten, not eleven). Each
    later batch drops
    the floor by its batch size; a shrink that matches no deletion census in a
    PR body is still the exclusion-widening tell."""
    rc, report, _stderr = real_run
    assert rc == 0
    assert report["total_agents_md_files"] >= 139


@pytest.mark.timeout(180)
def test_real_tree_caps_arm_denominator(real_run):
    """W2.1's own denominator, pinned on the REAL run rather than only on
    fixtures. test_line_caps_report_every_tier_and_never_fail proves the arm
    works on a built tree; nothing until here proves it is measuring THIS one.
    The three numbers are the non-vacuity claim the PR body makes — "measured ==
    boundaries == 42 is what makes the list non-vacuous" — and a report that
    quietly measured 30 of 42 would have said so here instead of in review.

    What is asserted is the arm's ARITHMETIC on the real tree, recomputed here
    from the filesystem — not its SIZE. The over-cap count (29 at adoption) is
    deliberately NOT pinned, and not for want of a way: a fall-only baseline over
    the set would work mechanically, but it would turn a reporting-only arm into
    a gate — any PR that pushed a boundary file over its cap would go red, which
    is W3.2's failing mode arriving through the side door. The package ships
    "reporting until W3.2", it says so in the config, and #6920's Question 3
    asks the owner whether a growth ratchet should exist before W3.2 at all.
    Pinning it here would answer that ruling with a commit. So the set is read,
    reported and checked for internal consistency, and its length is left to the
    report the lane reads.

    The recompute shares the validator's counting rule on purpose (splitlines,
    per the comment at agents_md_validator.py:782). That makes this test blind to
    a change in HOW lines are counted; it is aimed at the join — config path ->
    scanned file -> tier -> cap -> over — which is where a rename, a mis-tiered
    directory, or an off-by-one comparison would hide, and which no fixture
    covers because a fixture cannot be the real 42 files.

    The expected tier below is spelled out from the LITERALS, not from
    v.boundary_tier(). The first draft of this test called the module for it, and
    a mutation run caught the cost: deleting boundary_tier's root case failed
    test_line_caps_report_every_tier_and_never_fail and the pin test, but NOT
    this test — asking the module what tier it used and checking the module's
    answer against the module's answer is the vacuous comparison this file's
    header calls the laundering case. Checking tier/cap per entry against the
    literals is what makes a mis-tier move this test.
    """
    rc, report, stderr = real_run
    assert rc == 0, stderr
    caps = report["ratchet"]["line_caps"]
    assert caps["boundaries"] == len(EXPECTED_BOUNDARY_PATHS) == 42, caps["boundaries"]
    assert caps["measured"] == caps["boundaries"], (
        f"a listed boundary resolved to no scanned AGENTS.md: measured "
        f"{caps['measured']} of {caps['boundaries']} — the denominator is a hole, "
        "not a count"
    )
    assert caps["failing"] is False, "the caps arm went failing ahead of W3.2"
    assert caps["caps"] == EXPECTED_LINE_CAPS

    expected_over: set[str] = set()
    for dir_path in sorted(EXPECTED_BOUNDARY_PATHS):
        rel = "AGENTS.md" if dir_path == "." else f"{dir_path}/AGENTS.md"
        lines = len((REPO_ROOT / rel).read_text(encoding="utf-8").splitlines())
        tier = (
            "root"
            if dir_path == "."
            else "lane_root"
            if dir_path in EXPECTED_LANE_ROOTS
            else "package"
        )
        cap = EXPECTED_LINE_CAPS[tier]
        if lines > cap:
            expected_over.add(rel)
        entry = next((e for e in caps["over"] if e["path"] == rel), None)
        if entry is not None:
            assert entry["tier"] == tier, rel
            assert entry["cap"] == cap, rel
            assert entry["measured"] == lines, f"{rel} measured {entry['measured']} != {lines}"

    reported = {e["path"] for e in caps["over"]}
    assert reported == expected_over, (
        f"the arm's over set disagrees with a recomputation from disk — "
        f"arm-only {sorted(reported - expected_over)}, recomputed-only {sorted(expected_over - reported)}"
    )
    assert all(e["measured"] > e["cap"] for e in caps["over"] if e["measured"] is not None), (
        f"an entry in over is not actually over its cap: {caps['over']}"
    )


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
