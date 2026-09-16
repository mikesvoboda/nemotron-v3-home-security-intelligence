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
    return tmp_path


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


@pytest.mark.timeout(180)  # real-tree census twice over (locations + rerun) ~30-60s
def test_real_tree_ratchet_is_green():
    """The seeded baseline + complete registry must pass the gate on HEAD —
    if this rots, every CI run on every PR rots with it."""
    r = subprocess.run(
        [sys.executable, str(RATCHET)], capture_output=True, text=True, check=False, cwd=REPO_ROOT
    )
    assert r.returncode == 0, f"ratchet on real tree failed: {r.stderr[-600:]}"
