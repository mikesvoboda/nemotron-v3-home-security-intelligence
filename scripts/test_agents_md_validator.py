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
    # UR-89 review scratch — same cure, same evidence, one config line down.
    ".tickscratch",
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
    "backend/api/routes",
    "backend/api/schemas",
    "backend/core",
    "backend/models",
    "backend/services",
    "frontend",
    "frontend/src",
    "frontend/src/components/ai",
    "frontend/src/components/analytics",
    "frontend/src/components/common",
    "frontend/src/components/dashboard",
    "frontend/src/components/developer-tools",
    "frontend/src/components/events",
    "frontend/src/components/face-recognition",
    "frontend/src/components/jobs",
    "frontend/src/components/settings",
    "frontend/src/components/system",
    "frontend/src/components/zones",
    "frontend/src/hooks",
    "frontend/src/pages",
    "frontend/src/services",
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
# arm (docs/developer/agents-md-standard.md's named examples + cross-lane/CI
# contracts). Pinned separately
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
# W3.2 (ruling 33): the per-file fall-only baselines, one per boundary file,
# byte-pinned like the caps. These are the pre-W3.2 line counts (post-rewrite
# for the seven backend files this PR lands) — a rewrite lowers the number in
# the same PR, a raise is the hand-edit-a-human-reviews path ratchet-check.py
# documents. A value that does not match the committed config fails the pin
# below; the config diff itself is the reviewed artifact.
EXPECTED_LINE_BASELINES = {
    "AGENTS.md": 509,
    ".github/AGENTS.md": 355,
    "ai/AGENTS.md": 442,
    "backend/AGENTS.md": 150,
    "frontend/AGENTS.md": 676,
    "monitoring/AGENTS.md": 383,
    "scripts/AGENTS.md": 1214,
    "setup_lib/AGENTS.md": 167,
    "synthbench/AGENTS.md": 40,
    "ai/gateway/AGENTS.md": 45,
    "backend/ai_contract/AGENTS.md": 34,
    "backend/api/AGENTS.md": 127,
    "backend/core/AGENTS.md": 177,
    "backend/models/AGENTS.md": 129,
    "backend/services/AGENTS.md": 168,
    "frontend/src/AGENTS.md": 961,
    "synthbench/contract/AGENTS.md": 35,
    ".github/codeql/custom-queries/AGENTS.md": 381,
    "ai/gateway/export/AGENTS.md": 27,
    "backend/api/routes/AGENTS.md": 112,
    "backend/api/schemas/AGENTS.md": 106,
    "frontend/src/hooks/AGENTS.md": 2149,
    "frontend/src/pages/AGENTS.md": 123,
    "frontend/src/services/AGENTS.md": 931,
    "frontend/src/types/AGENTS.md": 406,
    "frontend/src/utils/AGENTS.md": 521,
    "frontend/src/components/ai/AGENTS.md": 416,
    "frontend/src/components/analytics/AGENTS.md": 400,
    "frontend/src/components/common/AGENTS.md": 1102,
    "frontend/src/components/dashboard/AGENTS.md": 512,
    "frontend/src/components/developer-tools/AGENTS.md": 318,
    "frontend/src/components/events/AGENTS.md": 515,
    "frontend/src/components/face-recognition/AGENTS.md": 280,
    "frontend/src/components/jobs/AGENTS.md": 308,
    "frontend/src/components/settings/AGENTS.md": 393,
    "frontend/src/components/system/AGENTS.md": 361,
    "frontend/src/components/zones/AGENTS.md": 430,
}
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
    line_baseline=_SENTINEL,
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
    write_config(root, baseline=baseline, boundary=boundary, caps=caps, line_baseline=line_baseline)
    return root


def write_config(
    root: Path,
    *,
    baseline=_SENTINEL,
    boundary=_SENTINEL,
    caps=_SENTINEL,
    line_baseline=_SENTINEL,
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
        # them low on purpose. The line baseline defaults to cover the same
        # one entry at a generous number — W3.2's loader requires it, so a
        # fixture config without it is exit 2, not a reporting arm.
        "boundary_list": (
            [{"path": ".", "reason": "the fixture's only boundary"}]
            if boundary is _SENTINEL
            else boundary
        ),
        "line_caps": (
            {"root": 1000, "lane_root": 1000, "package": 1000} if caps is _SENTINEL else caps
        ),
        "line_caps_baseline": (
            {"AGENTS.md": 1000} if line_baseline is _SENTINEL else line_baseline
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


def test_non_boundary_code_dir_does_not_require_agents_md(tmp_path):
    """W3.1 (ruling 300 item 2): the validator no longer requires an AGENTS.md
    in every directory with >= 2 code files; only boundary_list directories
    require one."""
    root = build(tmp_path, files={"src/a.py": "", "src/b.py": "", "src/c.py": ""})
    r = run_validator(root)
    assert r.returncode == 0, r.stderr
    types = [i["type"] for i in report_of(root)["issues"]]
    assert "missing_agents_md" not in types


def test_missing_boundary_agents_md_fails(tmp_path):
    """W3.1 (ruling 300 item 2): the validator requires an AGENTS.md at each
    boundary_list directory, failing when one is missing."""
    root = build(
        tmp_path,
        boundary=[
            {"path": ".", "reason": "root"},
            {"path": "backend", "reason": "lane root"},
        ],
        line_baseline={"AGENTS.md": 100, "backend/AGENTS.md": 100},
    )
    r = run_validator(root)
    assert r.returncode == 1
    report = report_of(root)
    missing = [i for i in report["issues"] if i["type"] == "missing_agents_md"]
    assert len(missing) == 1
    assert missing[0]["directory"] == "backend/"
    assert any("backend/" in v for v in report["ratchet"]["violations"])
    assert "backend/" in r.stderr


def test_outside_boundary_agents_md_is_reported_without_failing(tmp_path):
    """W3.1 (ruling 300 item 2): the validator reports, without failing, every
    AGENTS.md outside boundary_list until the last lane's W3.1 PR switches it
    to failing."""
    root = build(
        tmp_path,
        files={"docs/sub/AGENTS.md": "# Sub\n", "backend/sub/AGENTS.md": "# Sub2\n"},
        boundary=[{"path": ".", "reason": "root"}],
    )
    r = run_validator(root)
    assert r.returncode == 0, r.stderr
    report = report_of(root)
    outside = report["ratchet"]["outside_boundaries"]
    assert outside["failing"] is False
    assert outside["count"] == 2
    assert outside["files"] == ["backend/sub/AGENTS.md", "docs/sub/AGENTS.md"]
    assert report["ratchet"]["violations"] == []

    r_loud = subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r_loud.returncode == 0
    assert "[outside-boundary] docs/sub/AGENTS.md" in r_loud.stderr
    assert "[outside-boundary] backend/sub/AGENTS.md" in r_loud.stderr


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
        "outside_boundaries",
    }
    assert ratchet["outside_boundaries"] == {"count": 0, "files": [], "failing": False}


def test_line_caps_report_every_tier_and_baseline_fails(tmp_path):
    """W2.1's reporting arm, all four tier arms, in one fixture — and W3.2's
    flip (ruling 33): the per-file line baselines now FAIL the run.

    The two arms are deliberately different instruments:
    - Tier caps stay REPORTING-ONLY (`failing` is about the baseline arm).
      Over-cap boundary files are the lanes' W3.2 work lists, and failing on
      them from one lane's PR would gate a lane's tree on another lane's
      rewrite — 17 of the 18 files over cap on the real tree belong to the
      frontend/ops lanes. The SET is what is pinned — path, tier, cap,
      measured — not a count.
    - The per-file baselines are the growth ratchet the tier caps never had:
      measured > committed baseline is a violation naming the file; the way
      down is rewrite-then-lower (census pattern), and a fall below the
      baseline is free. `failing: True` + `mode: baseline` are pinned so the
      flip is on the record — a return to reporting-only is a reviewed edit,
      not a silent drift.

    The fixture's first run is green with every file OVER its tier cap —
    over-cap-but-at-baseline is exactly the W3.2 steady state the ruling
    describes (the work list reports; the gate does not block). A cap that
    failed on adoption would redden every PR touching a file scheduled for
    rewrite (measured in PR #6920: 29 of the 42 then-listed boundary files
    were over cap).

    The `backend/models` fixture entry is the case the real tree cannot supply:
    a file whose line count EQUALS its cap AND its baseline, which must NOT be
    reported by either arm (a cap is a maximum, a baseline a floor for growth —
    both compare with `>`). No committed boundary file sits at either edge —
    the smallest |lines - cap| on the real tree is 8 (frontend/src/components/
    jobs, 308 against the 300 cap; developer-tools is 318), and shifting every
    cap by ±5 leaves the over-set unchanged — so a `>` slipping to `>=` is
    invisible to every real-tree assertion in this file. Confirmed by mutation,
    not inference: flipping either comparison reddens THIS test and leaves the
    real-tree tests green. That is the pair-sides rule's untested direction,
    pinned here instead."""
    boundary = [
        {"path": ".", "reason": "root"},
        {"path": "backend", "reason": "lane root"},
        {"path": "ai/gateway", "reason": "package"},
        {"path": "scripts", "reason": "lane root, under cap"},
        {"path": "backend/models", "reason": "package, exactly at cap"},
    ]
    long_enough = "# Fixture\n\n" + "body\n" * 20
    root = build(
        tmp_path,
        files={
            "backend/AGENTS.md": long_enough,
            "ai/gateway/AGENTS.md": long_enough,
            "scripts/AGENTS.md": "# Short\n",
            # exactly the package cap (10 lines) and exactly its baseline, no
            # more — measured by the same splitlines rule the validator uses,
            # so this is equality, not a newline-counting artefact.
            "backend/models/AGENTS.md": "body\n" * 10,
        },
        boundary=boundary,
        caps={"root": 3, "lane_root": 10, "package": 10},
        line_baseline={
            "AGENTS.md": 30,
            "backend/AGENTS.md": 30,
            "ai/gateway/AGENTS.md": 30,
            "scripts/AGENTS.md": 30,  # 1 line: far BELOW its baseline — a fall is free
            "backend/models/AGENTS.md": 10,
        },
    )
    r = run_validator(root)
    # Green with every file over its tier cap: the caps arm reports, the
    # baseline arm is not exceeded. This is the W3.2 steady state.
    assert r.returncode == 0, r.stdout + r.stderr
    report = report_of(root)
    block = report["ratchet"]["line_caps"]
    assert block["failing"] is True  # the W3.2 flip (ruling 33), pinned on the record
    assert block["mode"] == "baseline"
    assert block["boundaries"] == 5
    assert block["measured"] == 5
    assert block["over_baseline"] == []  # at-baseline and below are not over
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
    # and the green run's violations are empty: over-cap never reached them.
    assert report["ratchet"]["violations"] == []

    # THE FAILING ARM: grow a boundary file past its committed baseline and
    # the run fails, the violation naming the file, measured, baseline. The
    # file was already over its tier cap; the caps arm stayed silent about
    # it — the growth is what turned the run red. (BASE_MD is 5 lines;
    # +30 lands at 35 against the 30 baseline.)
    amend(root, "body\n" * 30)  # 5 -> 35 > 30, the over-cap set unchanged
    r_grown = run_validator(root)
    assert r_grown.returncode == 1
    grown = report_of(root)["ratchet"]
    assert grown["line_caps"]["over_baseline"] == [
        {
            "path": "AGENTS.md",
            "measured": 35,
            "baseline": 30,
            "reason": "over its committed baseline by 5 lines",
        }
    ]
    assert any(
        "line baseline exceeded: AGENTS.md measured 35 > baseline 30" in v
        for v in grown["violations"]
    ), grown["violations"]
    # the tier-cap over-set is unchanged — the red is the baseline's, not the
    # caps' (the caps block itself still reports and still does not fail).
    assert {e["path"] for e in grown["line_caps"]["over"]} == set(over)

    # The way down: rewrite below the baseline and the run is green again
    # with no config edit — the gate reads the tree, not a memo. (Lowering
    # the baseline to the new count is the same-PR census-pattern edit; a
    # LOWER number cannot redden anything.)
    (root / "AGENTS.md").write_text("# Fixture\n\n" + "body\n" * 20)
    r_rewritten = run_validator(root)
    assert r_rewritten.returncode == 0, r_rewritten.stdout + r_rewritten.stderr
    assert report_of(root)["ratchet"]["line_caps"]["over_baseline"] == []

    # A boundary with no AGENTS.md is recorded in line_caps["over"] with
    # measured=None AND fails the run under W3.1's boundary requirement.
    write_config(
        root,
        boundary=[
            *boundary,
            {"path": "synthbench/contract", "reason": "boundary with no AGENTS.md"},
        ],
        caps={"root": 3, "lane_root": 10, "package": 10},
        line_baseline={
            "AGENTS.md": 30,
            "backend/AGENTS.md": 30,
            "ai/gateway/AGENTS.md": 30,
            "scripts/AGENTS.md": 30,
            "backend/models/AGENTS.md": 10,
            # a listed-but-absent file still carries a key; inert until the
            # file exists (the hole is the missing_agents_md arm's failure)
            "synthbench/contract/AGENTS.md": 10,
        },
    )
    r_hole = run_validator(root)
    assert r_hole.returncode == 1
    hole_block = report_of(root)["ratchet"]["line_caps"]
    assert hole_block["boundaries"] == 6
    assert hole_block["measured"] == 5
    hole = {e["path"]: e for e in hole_block["over"]}["synthbench/contract/AGENTS.md"]
    assert hole["measured"] is None
    assert hole["tier"] == "package"


def test_caps_apply_to_boundary_files_only(tmp_path):
    """The other side of the rule. A non-boundary AGENTS.md far over every
    cap is NOT on the work list: files outside the boundary list are W3.1
    deletions, and capping a file scheduled to disappear is noise, not a
    ratchet. A one-sided test would pass if the arm measured every AGENTS.md
    it walked."""
    root = build(
        tmp_path,
        files={"backend/satellite/AGENTS.md": "# Satellite\n\n" + "body\n" * 200},
        boundary=[{"path": ".", "reason": "the only boundary"}],
        caps={"root": 1000, "lane_root": 1000, "package": 10},
    )
    r = run_validator(root)
    assert r.returncode == 0, r.stdout + r.stderr
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


def test_review_scratch_is_excluded_from_the_scan(tmp_path):
    """UR-89 review materialisation must not reach the ratchet, the census or
    the boundary rule — the W1.1 `site/` hazard wearing different clothes.

    W1.1's comment above states the mechanism once, for everyone: "Gitignored,
    but rglob does not read .gitignore." A `.tickscratch/<name>/tree/` is a
    FULL materialised checkout living at the repo root, and its AGENTS.md files
    are copied from older heads — so its internal citations point at paths that
    exist in ITS tree, not this one, and the dead-reference arm (zero tolerance
    since W1.3) fires on copied text no PR caused. Measured 2026-10-17 in a
    workspace holding one: 6 red here — 32 violations incl. three dead links
    inside the scratch copy, `test_real_tree_scanned_count_floor` (36 -> 48, the
    census inflated by a copied tree), and the boundary diff growing
    `.tickscratch/battery/tree/scripts`. A gitignore entry cures nothing here:
    the validator walks with rglob and never asks git.

    Pinned on a synthetic root like every fixture in this file — the live root
    having a scratch tree is an environment property — but through the REAL
    validator subprocess, so the prune is executed, not described. The
    positive-control arm is what keeps it honest: identical scratch content at
    a non-excluded path MUST still go red, so the green arm cannot be the green
    of a broken instrument (or of a prune so wide it ate the tree).
    """
    tree = build(
        tmp_path,
        files={
            # the live, scannable pair: root AGENTS.md links notes.md (BASE_MD)
            "notes.md": "present target for the base link\n",
            # the scratch shape: a copied AGENTS.md citing a path that exists
            # only inside the copied tree — exactly the W1.3 zero-tolerance trip.
            ".tickscratch/wt-a/tree/AGENTS.md": (
                "# Scratch copy\n\nLive: [notes](copied-notes.md)\n"
            ),
            ".tickscratch/wt-a/tree/code.py": "X = 1\n",
            ".tickscratch/wt-a/tree/other.py": "Y = 2\n",
            # the control: byte-same content under a NON-excluded name.
            "notscratch/wt-a/tree/AGENTS.md": (
                "# Scratch copy\n\nLive: [notes](copied-notes.md)\n"
            ),
            "notscratch/wt-a/tree/code.py": "X = 1\n",
            "notscratch/wt-a/tree/other.py": "Y = 2\n",
        },
    )
    # control first: the instrument detects this exact content when it is in
    # scope. If this assert ever passes without an exclusion the validator has
    # stopped scanning nested AGENTS.md files, and the green arm is meaningless.
    control = run_validator(tree)
    assert control.returncode != 0, (
        "positive control went green — copied scratch at a NON-excluded path "
        "must trip the ratchet, or the green below certifies nothing"
    )
    control_blob = json.dumps(report_of(tree))
    assert "notscratch/wt-a/tree/AGENTS.md" in control_blob, control_blob[:400]

    # the arm under test: the same copied text, now under the excluded name.
    tree2 = build(
        tmp_path / "b",
        files={
            "notes.md": "present target for the base link\n",
            ".tickscratch/wt-a/tree/AGENTS.md": (
                "# Scratch copy\n\nLive: [notes](copied-notes.md)\n"
            ),
            ".tickscratch/wt-a/tree/code.py": "X = 1\n",
            ".tickscratch/wt-a/tree/other.py": "Y = 2\n",
        },
    )
    res = run_validator(tree2)
    assert res.returncode == 0, res.stderr or res.stdout
    report_blob = json.dumps(report_of(tree2))
    assert ".tickscratch" not in report_blob, report_blob[:400]
    assert ".tickscratch" in set(COMMITTED_CONFIG["exclude_directories"]), (
        "the validator's rglob descends into UR-89 review scratch trees at the "
        "repo root; exclude it like site/ (see the W1.1 note in "
        ".agents-md-validator.yml) — .gitignore does not reach rglob"
    )


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
    tree (post-#7246: the cut shrank the frontend, moving the band's edges),
    thresholds 10 through 39 ALL land inside it (30 of the 60 values), so the
    band rules out <= 9 (53 entries) and >= 40 (28 entries) and says nothing at
    all about 20 vs 15. It is kept as a coarse guard: a rule edit that puts a
    threshold's output outside the band is selecting the wrong thing.

    What does discriminate 20 is structural, and it is a keep-argument rather
    than a cut-argument: the committed set is a PLATEAU, equal at thresholds
    19 and 20, so the exact number inside the plateau is not load-bearing —
    what is load-bearing is the plateau's two edges, and both are asserted
    below.

    - Its top edge: >= 21 drops setup_lib, which has exactly 20 code files and
      NO kept ancestor at all — it is a top-level package, so at >= 21 the tree
      carries a real package that no boundary file covers. Every other entry a
      tighter cut drops is a satellite that folds into frontend/src (at the
      F3.2 tree these were all frontend dirs already under the plateau — the
      cut of #7246 dropped stores/alerts/contexts/entities from 20-23 files to
      6-18 and removed them from the list entirely; their AGENTS.md files left
      with the dirs' last loads, re-derived below like everything else).
      setup_lib is also, measured, the ONLY entry the size rule keeps with no
      proper kept ancestor: the other 21 have one. So "20" is "the largest
      threshold that still covers the one orphan package".
    - Its bottom edge: every entry a looser cut adds is a parent-split —
      >= 18 adds exactly one dir, entities (18 code files, under the listed
      frontend/src); >= 17 adds components/settings/prompts (17, under the
      listed components/settings); >= 16 adds backend/api/middleware (16,
      under the listed backend/api); >= 15 adds frontend audit and
      common/skeletons (B3.3 box 4 retired the vision-model forms, dropping
      model-forms out of the kept set and moving every marginal dir's
      threshold down one). The standard's
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
        """The rule as the config comment states it, at one threshold (W3.2 box 4:
        the 20-code-file membership rule with RULE_EXCEPTION_NOT_LISTED as its
        one pinned exception)."""
        kept = {
            d
            for d, n in counts.items()
            if n >= threshold and not self_indexed(d) and d not in RULE_EXCEPTION_NOT_LISTED
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
    # B3.2 (2026-10-21) deleted 94 backend modules and 116 test files, taking
    # the >=20-file directory count (`big`) to 38.
    assert len(big) >= 35 and committed - big, "the rule is doing nothing"
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
    # The band as a COARSE guard only — see the docstring: thresholds 10..39 all
    # land inside it at this tree, so being in-band is not the argument for 20.
    # Only the looser side is asserted, because that is the side that stays true
    # as the tree grows (more dirs -> bigger lists); asserting the tight side
    # (>= 40 falls out at 28 today) would redden a green rule for an unrelated
    # package gaining files. F3.2's cut moved the loose edge from threshold 10
    # (52 entries, outside) to 9 (53 entries, still outside) — derive(10) is 49
    # now, inside the band; the pin follows the tree per the docstring's
    # re-derivation clause. B3.3 box 4 (#7322) retired the four vision-model
    # forms, dropping model-forms from 11 to 3 code files and out of the kept
    # set: the whole curve moved down ~2 entries — derive(9) is 50 now, at the
    # band's top edge and INSIDE, so the loose edge moves to 8 (54, outside),
    # and derive(10) is 47.
    assert len(derive(5)) > 50 and len(derive(8)) > 50, "a looser threshold now fits the band"

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
    - The tier CENSUS of the committed list. The report's `measured == 38`
      says every listed path resolved to a file; it does not say the 38 still SORT
      1/7/30. A lane root that loses its AGENTS.md, or a boundary renamed out of
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

    # W3.2 (ruling 33): the fourth pinned key. One baseline per boundary file,
    # matching the list 1:1 — dropping a key is the cheapest way to disable
    # the new gate (the loader refuses), and a raise fits a grown file.
    # EXPECTED_LINE_BASELINES are the post-rewrite counts the seven backend
    # W3.2 files landed at plus the pre-rewrite counts elsewhere; values fall
    # as lanes rewrite, and a value change is a reviewed same-PR edit.
    # (Compared as FILE paths: the baseline is keyed by the AGENTS.md path,
    # the boundary list by directories — "." maps to "AGENTS.md".)
    boundary_files = {
        "AGENTS.md" if e["path"] == "." else f"{e['path']}/AGENTS.md"
        for e in COMMITTED_CONFIG["boundary_list"]
    }
    assert set(COMMITTED_CONFIG["line_caps_baseline"]) == boundary_files, (
        "line_caps_baseline keys must match boundary_list 1:1 — a missing key "
        "silently unchecks a file and an extra one means the list moved"
    )
    assert COMMITTED_CONFIG["line_caps_baseline"] == EXPECTED_LINE_BASELINES

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
    assert census["package"] == len(EXPECTED_BOUNDARY_PATHS) - 1 - 7 == 29, census
    assert sum(census.values()) == len(EXPECTED_BOUNDARY_PATHS) == 37, (
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
    floor.

    W3.1 (ruling 300 item 2): the floor is now the boundary_list count (37),
    and every scanned file is accounted for as either a boundary file or a
    reported outside-boundary file, so no later W3.1 deletion of non-boundary
    AGENTS.md files can fail this gate."""
    rc, report, _stderr = real_run
    assert rc == 0
    outside = report["ratchet"]["outside_boundaries"]
    assert outside["failing"] is False
    assert report["total_agents_md_files"] >= len(EXPECTED_BOUNDARY_PATHS) == 37
    assert report["total_agents_md_files"] == len(EXPECTED_BOUNDARY_PATHS) + outside["count"]
    assert report["summary"]["missing_agents_md"] == 0


@pytest.mark.timeout(180)
def test_real_tree_caps_arm_denominator(real_run):
    """W2.1's own denominator, pinned on the REAL run rather than only on
    fixtures. test_line_caps_report_every_tier_and_never_fail proves the arm
    works on a built tree; nothing until here proves it is measuring THIS one.
    The three numbers are the non-vacuity claim the PR body makes — "measured ==
    boundaries == 38 is what makes the list non-vacuous" — and a report that
    quietly measured 30 of 38 would have said so here instead of in review.

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
    covers because a fixture cannot be the real 38 files.

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
    assert caps["boundaries"] == len(EXPECTED_BOUNDARY_PATHS) == 37, caps["boundaries"]
    assert caps["measured"] == caps["boundaries"], (
        f"a listed boundary resolved to no scanned AGENTS.md: measured "
        f"{caps['measured']} of {caps['boundaries']} — the denominator is a hole, "
        "not a count"
    )
    # W3.2 (ruling 33): the flip, on the record — the baseline arm is the
    # failing arm and the tier caps stay reporting. `failing` is pinned True
    # the way it was pinned False before W3.2: the mode is a reviewed edit,
    # not silent drift. And the run is green WITH the arm failing only
    # because over_baseline is empty — the real tree sits at or below every
    # baseline (asserted per-file below), which is what green now means.
    assert caps["failing"] is True
    assert caps["mode"] == "baseline"
    assert caps["over_baseline"] == [], (
        "the real tree is over a committed line baseline — counts may only "
        "fall: rewrite the file to the standard (W3.2) or lower the baseline "
        "in the same PR (census pattern)"
    )
    assert caps["caps"] == EXPECTED_LINE_CAPS

    expected_over: set[str] = set()
    for dir_path in sorted(EXPECTED_BOUNDARY_PATHS):
        rel = "AGENTS.md" if dir_path == "." else f"{dir_path}/AGENTS.md"
        lines = len((REPO_ROOT / rel).read_text(encoding="utf-8").splitlines())
        # per-file: measured at or below its committed baseline (the gate's
        # green condition, checked against the test's own literal, not the
        # module's)
        assert lines <= EXPECTED_LINE_BASELINES[rel], (
            f"{rel} measures {lines} > baseline {EXPECTED_LINE_BASELINES[rel]} "
            "from the test's own literal — the arm let a growth through"
        )
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
