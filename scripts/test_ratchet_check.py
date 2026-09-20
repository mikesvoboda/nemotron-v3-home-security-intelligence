#!/usr/bin/env python3
"""Tests for scripts/ratchet-check.py (WP1.3).

Run explicitly; outside testpaths:

    uv run python -m pytest scripts/test_ratchet_check.py -q

The ratchet is Phase 1's enforcement gate, so its tests pin the CONTRACT the
plan states: a synthetic count INCREASE must fail; a DECREASE must pass and
lower the baseline (--update); and the done-when — adding an unregistered
@pytest.mark.skip fails. Also pinned: the pair-sides of each rule (a registry
entry whose site vanished is stale, an increase WITH an entry still needs the
baseline adjudicated in the same commit), because a one-sided gate leaks in
the untested direction.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RATCHET = REPO_ROOT / "scripts" / "ratchet-check.py"
CENSUS = REPO_ROOT / "scripts" / "suppression-census.py"

# Minimal census-valid tree: one skip decorator + one excluded tree is enough
# surface to exercise increase/decrease on real census machinery.
TREE = {
    "scripts/collection-sanity-allowlist.txt": "",
    ".github/flake-allowlist.yml": "flakes: []\n",
    "frontend/vite.config.ts": (
        "export default defineConfig({test: {exclude: [...configDefaults.exclude]}})\n"
    ),
    "scripts/validate.sh": "#!/usr/bin/env bash\npytest backend/tests/unit\n",
    "pyproject.toml": '[tool.coverage.run]\nomit = ["backend/tests/*"]\n',
    "backend/tests/unit/test_a.py": (
        "import pytest\n@pytest.mark.skip(reason='site one')\ndef test_one():\n    pass\n"
    ),
    # WP2.4b: the imperative-skip channel. One guard that names host
    # machinery (census host_probe True) and one that only names a repo
    # path (probe False) — the LAUNDER rule must tell them apart.
    "backend/tests/unit/test_host.py": (
        "import os\nimport shutil\nimport pytest\n\n\n"
        "def test_host_shape():\n"
        '    if not shutil.which("ffmpeg"):\n'
        '        pytest.skip("ffmpeg missing on this host")\n'
        "    assert True\n\n\n"
        "def test_repo_shape():\n"
        '    cfg = "nginx.conf"\n'
        "    if not os.path.exists(cfg):\n"
        '        pytest.skip("no nginx.conf in tree")\n'
        "    assert True\n"
    ),
}

ADDED_SKIP = (
    "import pytest\n"
    "@pytest.mark.skip(reason='site one')\n"
    "def test_one():\n    pass\n"
    "@pytest.mark.skip(reason='sneaked in')\n"
    "def test_sneaked():\n    pass\n"
)


def locations(root: Path) -> dict[str, list[dict]]:
    r = subprocess.run(
        [sys.executable, str(CENSUS), "--root", str(root), "--locations"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(r.stdout)


def mint_state(root: Path) -> None:
    """Seed baseline+registry from the tree AS IT IS — the starting state a
    PR branches from. Registry rows carry the required schema fields so the
    ratchet's structural check passes; ids are census-exact."""
    loc = locations(root)
    baseline = {cat: len(items) for cat, items in loc.items()}
    registry = {
        cat: [
            {
                "id": it["id"],
                "kind": "environment",
                "owner": "tester",
                "tracking": None,
                "expires": None,
                "reason": it["reason"] or None,
            }
            for it in items
        ]
        for cat, items in loc.items()
    }
    (root / ".github").mkdir(parents=True, exist_ok=True)
    (root / ".github/suppression-baseline.json").write_text(json.dumps(baseline, indent=2))
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(registry, sort_keys=False))


def run_ratchet(root: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RATCHET), "--root", str(root), *flags],
        capture_output=True,
        text=True,
        check=False,
    )


def build(tmp_path: Path) -> Path:
    for rel, content in TREE.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
    mint_state(tmp_path)
    # mint_state defaults every kind to environment (schema-valid for the
    # increase/decrease tests). WP2.4b's LAUNDER rule makes environment a
    # CLAIM the rule must pass on every entry, so the default build keeps it
    # honest: imperative sites carry their census probe (host-shaped -> keep
    # environment) or fall to todo; and the one probe-False site carries a
    # written justification, the per-entry channel the rule shares with the
    # generator (test_repo_shape's guard names a repo FILE — an
    # environment-shaped deferral that's legitimate when documented).
    loc = locations(tmp_path)
    probe = {it["id"]: it["host_probe"] for it in loc["pytest_skip_imperative"]}
    reg = registry_of(tmp_path)
    for row in reg["pytest_skip_imperative"]:
        if not probe[row["id"]]:
            row["kind"] = "todo"
            row["tracking"] = "UNTRACKED:GENERAL"
            row["expires"] = "2026-12-31"
    just = JUSTIFIED_PATHS & {row["id"] for row in reg["pytest_skip_imperative"]}
    for row in reg["pytest_skip_imperative"]:
        if row["id"] in just:
            row["kind"] = "environment"
            row["tracking"] = None
            row["expires"] = None
            row["host_justification"] = "fixture: repo file, environment-shaped deferral"
    (tmp_path / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    return tmp_path


# The fixture's per-entry justified set: the repo-file site, justified in the
# build; the LAUNDER tests move it around to prove both directions.
JUSTIFIED_PATHS = {"backend/tests/unit/test_host.py:15"}
HOST_SITE = "backend/tests/unit/test_host.py:8"
REPO_SITE = "backend/tests/unit/test_host.py:15"


# ---- WP2.4b: environment is a CLAIM, not a default -----------------------
# The leak: registry-gen defaulted EVERY imperative pytest.skip to
# kind=environment — an exempt kind, so no tracking, no expiry, no ratchet
# teeth, forever. A skip guarded on `os.path.exists(repo_file)` (a check that
# can only be false in a broken checkout) was classified identically to a
# skip guarded on `shutil.which("ffmpeg")`. The fix: the census stamps every
# imperative site with host_probe (does the guard name host machinery?),
# kind=environment is legal on such a site ONLY with a census probe or a
# written per-entry host_justification — and both channels are machine-
# checked here, so the default-to-environment channel is closed permanently.


def _rows(root: Path, cat: str) -> list[dict]:
    return [r for r in registry_of(root)[cat] if r["id"] == REPO_SITE]


def _save_row(root: Path, row: dict) -> None:
    reg = registry_of(root)
    reg["pytest_skip_imperative"] = [
        row if r["id"] == row["id"] else r for r in reg["pytest_skip_imperative"]
    ]
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))


def test_environment_without_probe_or_justification_fails(tmp_path):
    """THE done-when (WP2.4b): a repo-shaped imperative skip laundered to
    environment fails CI naming the site and the channel that would close it."""
    root = build(tmp_path)
    (row,) = _rows(root, "pytest_skip_imperative")
    row["kind"] = "environment"
    row.pop("host_justification", None)
    _save_row(root, row)
    r = run_ratchet(root)
    assert r.returncode == 1
    assert "LAUNDER" in r.stderr
    assert REPO_SITE in r.stderr


def test_justified_environment_site_passes(tmp_path):
    """The per-entry channel: a written justification buys environment for a
    probe-False site (and the build uses it — pinned here explicitly)."""
    root = build(tmp_path)
    (row,) = _rows(root, "pytest_skip_imperative")
    assert row["kind"] == "environment" and row.get("host_justification")
    assert run_ratchet(root).returncode == 0


def test_host_probe_buys_environment_without_justification(tmp_path):
    """The mechanical channel: a guard naming shutil.which needs no prose."""
    root = build(tmp_path)
    reg = registry_of(root)
    (host_row,) = [r for r in reg["pytest_skip_imperative"] if r["id"] == HOST_SITE]
    assert host_row["kind"] == "environment" and "host_justification" not in host_row
    assert run_ratchet(root).returncode == 0


def test_justification_on_non_environment_entry_fails(tmp_path):
    """The pair-side: a justification on a todo entry is a field no rule will
    ever enforce — decoration (same exemption-integrity class as a date on an
    exempt kind)."""
    root = build(tmp_path)
    (row,) = _rows(root, "pytest_skip_imperative")
    row["kind"] = "todo"
    row["tracking"] = "UNTRACKED:GENERAL"
    row["expires"] = "2026-12-31"
    row["host_justification"] = "leftover"
    _save_row(root, row)
    r = run_ratchet(root)
    assert r.returncode == 1
    assert "host_justification" in r.stderr


def baseline_of(root: Path) -> dict[str, int]:
    return json.loads((root / ".github/suppression-baseline.json").read_text())


def registry_of(root: Path) -> dict:
    return yaml.safe_load((root / ".github/suppression-registry.yml").read_text())


def test_green_on_minted_state(tmp_path):
    root = build(tmp_path)
    r = run_ratchet(root)
    assert r.returncode == 0, r.stderr


def test_increase_without_registry_entry_fails(tmp_path):
    """THE done-when: add an unregistered @pytest.mark.skip -> CI fails,
    naming both the category and the offending id."""
    root = build(tmp_path)
    (root / "backend/tests/unit/test_a.py").write_text(ADDED_SKIP)
    r = run_ratchet(root)
    assert r.returncode == 1
    assert "pytest_skip" in r.stderr
    assert "test_a.py::test_sneaked" in r.stderr


def test_decrease_passes_and_update_lowers(tmp_path):
    """Decreases pass immediately (ratchet only falls) and --update mints the
    lower baseline without hand-editing the JSON."""
    root = build(tmp_path)
    # Removing the suppression means removing its registry entry too —
    # test_stale_registry_entry_fails pins that the ZOMBIE side fails CI, so
    # the honest decrease carries both. (Registry gen would do this for you.)
    (root / "backend/tests/unit/test_a.py").write_text("def test_one():\n    pass\n")
    reg = registry_of(root)
    reg["pytest_skip"] = []
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    r = run_ratchet(root)
    assert r.returncode == 0, r.stderr
    assert baseline_of(root)["pytest_skip"] == 1  # not yet lowered by a mere check
    r = run_ratchet(root, "--update")
    assert r.returncode == 0, r.stderr
    assert baseline_of(root)["pytest_skip"] == 0
    assert run_ratchet(root).returncode == 0


def test_update_never_raises(tmp_path):
    """--update is one-way: the ONLY way up is a hand-bumped baseline in a
    commit a human reviewed — an increase needs an entry AND adjudication."""
    root = build(tmp_path)
    (root / "backend/tests/unit/test_a.py").write_text(ADDED_SKIP)
    r = run_ratchet(root, "--update")
    assert r.returncode == 1
    assert baseline_of(root)["pytest_skip"] == 1  # baseline untouched


def test_increase_with_entry_and_bumped_baseline_passes(tmp_path):
    """The sanctioned upward path: registry regenerated (entry exists for the
    new id) and the baseline raised in the same commit."""
    root = build(tmp_path)
    (root / "backend/tests/unit/test_a.py").write_text(ADDED_SKIP)
    reg = registry_of(root)
    reg["pytest_skip"].append(
        {
            "id": "backend/tests/unit/test_a.py::test_sneaked",
            "kind": "environment",
            "owner": "tester",
            "tracking": None,
            "expires": None,
            "reason": "sneaked in",
        }
    )
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    bl = baseline_of(root)
    bl["pytest_skip"] = 2
    (root / ".github/suppression-baseline.json").write_text(json.dumps(bl, indent=2))
    r = run_ratchet(root)
    assert r.returncode == 0, r.stderr


def test_increase_with_entry_but_stale_baseline_fails(tmp_path):
    root = build(tmp_path)
    (root / "backend/tests/unit/test_a.py").write_text(ADDED_SKIP)
    reg = registry_of(root)
    reg["pytest_skip"].append(
        {"id": "backend/tests/unit/test_a.py::test_sneaked", "kind": "environment"}
    )
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    r = run_ratchet(root)
    assert r.returncode == 1
    assert "baseline" in r.stderr.lower()


def test_stale_registry_entry_fails(tmp_path):
    """The other direction: the suppression was removed but its entry wasn't
    — a zombie registry silently launders the next re-addition."""
    root = build(tmp_path)
    (root / "backend/tests/unit/test_a.py").write_text("def test_one():\n    pass\n")
    r = run_ratchet(root)
    assert r.returncode == 1
    assert "test_a.py::test_one" in r.stderr
    assert "stale" in r.stderr.lower()


def test_entry_missing_required_fields_fails(tmp_path):
    """owner+expiry schema bites: a hand-edited entry without a kind/owner is
    not an adjudication."""
    root = build(tmp_path)
    reg = registry_of(root)
    reg["pytest_skip"][0].pop("kind")
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    r = run_ratchet(root)
    assert r.returncode == 1
    assert "kind" in r.stderr


def test_nonexempt_entry_without_tracking_fails(tmp_path):
    root = build(tmp_path)
    reg = registry_of(root)
    reg["pytest_skip"][0]["kind"] = "todo"
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    r = run_ratchet(root)
    assert r.returncode == 1
    assert "tracking" in r.stderr.lower()


# ---- WP1.4: expiry enforcement -------------------------------------------
# --today exists for these tests (and for "what breaks on 2026-10-16?"
# drills); CI never passes it, so the real clock rules there.


def test_expired_entry_fails_naming_the_owner(tmp_path):
    """THE done-when: an entry dated in the past fails CI with a message
    naming the owner. Not a warning — the plan is explicit."""
    root = build(tmp_path)
    reg = registry_of(root)
    reg["pytest_skip"][0]["kind"] = "flaky"
    reg["pytest_skip"][0]["tracking"] = "NEM-1"
    reg["pytest_skip"][0]["expires"] = "2026-01-01"
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    r = run_ratchet(root, "--today", "2026-09-16")
    assert r.returncode == 1
    assert "EXPIRED" in r.stderr
    assert "tester" in r.stderr  # names the owner, per the done-when
    assert "test_a.py::test_one" in r.stderr


def test_future_entry_passes(tmp_path):
    root = build(tmp_path)
    reg = registry_of(root)
    reg["pytest_skip"][0]["kind"] = "flaky"
    reg["pytest_skip"][0]["tracking"] = "NEM-1"
    reg["pytest_skip"][0]["expires"] = "2099-01-01"
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    r = run_ratchet(root, "--today", "2026-09-16")
    assert r.returncode == 0, r.stderr


def test_expiry_boundary_is_inclusive(tmp_path):
    """expires: 2026-10-15 is green ON the 15th, red on the 16th — the R-T9
    ruling deadline behaves deterministically at the seam."""
    root = build(tmp_path)
    reg = registry_of(root)
    reg["pytest_skip"][0]["kind"] = "defect"
    reg["pytest_skip"][0]["tracking"] = "R-T9-MQTTPUMP"
    reg["pytest_skip"][0]["expires"] = "2026-10-15"
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    assert run_ratchet(root, "--today", "2026-10-15").returncode == 0
    assert run_ratchet(root, "--today", "2026-10-16").returncode == 1


def test_expiry_string_format_enforced(tmp_path):
    """An expiry that cannot be parsed cannot be enforced, so an unparseable
    expiry is itself a failure — never a silent skip of the check."""
    root = build(tmp_path)
    reg = registry_of(root)
    reg["pytest_skip"][0]["kind"] = "todo"
    reg["pytest_skip"][0]["tracking"] = "NEM-1"
    reg["pytest_skip"][0]["expires"] = "someday"
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    r = run_ratchet(root, "--today", "2026-09-16")
    assert r.returncode == 1
    assert "ISO" in r.stderr


def test_exempt_kind_with_expiry_fails(tmp_path):
    """environment/scoped are the spec's EXEMPT kinds: exempt means no
    deadline, so a date on one is a misclassification — either the kind is
    wrong or the date is decoration the gate would never enforce."""
    root = build(tmp_path)
    reg = registry_of(root)
    reg["pytest_skip"][0]["expires"] = "2099-01-01"  # kind stays environment
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    r = run_ratchet(root, "--today", "2026-09-16")
    assert r.returncode == 1
    assert "null" in r.stderr.lower()


def test_nonexempt_entry_requires_expiry(tmp_path):
    root = build(tmp_path)
    reg = registry_of(root)
    reg["pytest_skip"][0]["kind"] = "todo"
    reg["pytest_skip"][0]["tracking"] = "NEM-1"
    reg["pytest_skip"][0]["expires"] = None
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    r = run_ratchet(root, "--today", "2026-09-16")
    assert r.returncode == 1
    assert "expires" in r.stderr.lower()


def test_exempt_entry_requires_null_tracking(tmp_path):
    """The symmetric side: an environment entry CLAIMING a tracking ref is
    hiding a real finding behind an exemption (or misclassified) — the two
    kinds of entry must not blur. `scoped` is exempt from the date but not
    from tracking: it names the schedule that runs the tree."""
    root = build(tmp_path)
    reg = registry_of(root)
    reg["pytest_skip"][0]["tracking"] = "NEM-999"  # kind stays environment
    (root / ".github/suppression-registry.yml").write_text(yaml.dump(reg, sort_keys=False))
    r = run_ratchet(root, "--today", "2026-09-16")
    assert r.returncode == 1
    assert "null" in r.stderr.lower()


@pytest.mark.timeout(180)  # real-tree census twice over (locations + rerun) ~30-60s
def test_real_tree_ratchet_is_green():
    """The seeded baseline + complete registry (every WP1.4 expiry rule
    included, real clock) must pass the gate on HEAD — if this rots, every
    CI run on every PR rots with it."""
    r = subprocess.run(
        [sys.executable, str(RATCHET)], capture_output=True, text=True, check=False, cwd=REPO_ROOT
    )
    assert r.returncode == 0, f"ratchet on real tree failed: {r.stderr[-600:]}"
