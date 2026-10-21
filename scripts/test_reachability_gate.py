#!/usr/bin/env python3
"""Tests for scripts/reachability_gate.py (O3.4 — Reachability gates in CI).

Run explicitly; outside testpaths (wired into collection-sanity's anti-rot step):

    uv run python -m pytest scripts/test_reachability_gate.py -q

Pins both halves of O3.4 (docs/uplevel/packages/ops.md, owner ruling 257):
  1. Python reachability (O2.3): fails when a new non-shipping Python module
     appears without a keep.toml entry (new = not in the baseline recorded at
     F3.2's merge, before B3.2 deletes the approved module list), or when
     reachability.py reports unresolved first-party dynamic imports or missing
     declared entry points.
  2. Frontend reachability (F3.2 / ruling 257): fails when `knip --production`
     reports a new unused file or a new unused export not in the baseline F3.2
     (#7246) recorded at its merge (`ca0e5a081`), or when knip output is
     missing/malformed (fail-closed).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE_SCRIPT = REPO_ROOT / "scripts" / "reachability_gate.py"
BASELINE_JSON = REPO_ROOT / "scripts" / "reachability" / "baseline.json"


def _load_gate() -> Any:
    assert GATE_SCRIPT.is_file(), f"missing gate script: {GATE_SCRIPT}"
    spec = importlib.util.spec_from_file_location("reachability_gate", GATE_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def synthetic_repo(tmp_path: Path) -> Path:
    """Minimal repo with one entry point, one live module, and one baseline dead module."""
    _write(
        tmp_path,
        "scripts/reachability/entry_points.toml",
        'entries = ["pkg/main.py"]\ndynamic_allow = []\n',
    )
    _write(tmp_path, "scripts/reachability/keep.toml", "keep = []\n")
    _write(tmp_path, "pkg/__init__.py", "from pkg.live import LIVE\n")
    _write(tmp_path, "pkg/main.py", "from pkg import LIVE\n")
    _write(tmp_path, "pkg/live.py", "LIVE = 1\n")
    _write(tmp_path, "pkg/legacy_dead.py", "DEAD = 1\n")
    _write(
        tmp_path,
        "scripts/reachability/baseline.json",
        json.dumps(
            {
                "schema_version": 1,
                "pinned_at_commit": "ca0e5a081",
                "python": {"not_shipping": ["pkg/legacy_dead.py"]},
                "knip": {
                    "files": ["src/types/enrichment.ts"],
                    "exports": {"src/services/api.ts": ["legacyUnusedExport"]},
                    "dependencies": ["tslib"],
                },
            },
            indent=2,
        )
        + "\n",
    )
    return tmp_path


def test_python_gate_passes_when_not_shipping_is_subset_of_baseline(
    synthetic_repo: Path,
) -> None:
    gate = _load_gate()
    baseline = gate.load_baseline(synthetic_repo / "scripts/reachability/baseline.json")
    findings = gate.check_python_reachability(
        synthetic_repo,
        baseline,
        entries_path=synthetic_repo / "scripts/reachability/entry_points.toml",
        keep_path=synthetic_repo / "scripts/reachability/keep.toml",
        candidate_dirs=["pkg"],
    )
    assert findings == []

    # Deleting a baseline non-shipping module (as B3.2 does) also passes without
    # requiring a lockstep baseline edit.
    (synthetic_repo / "pkg/legacy_dead.py").unlink()
    findings_after_delete = gate.check_python_reachability(
        synthetic_repo,
        baseline,
        entries_path=synthetic_repo / "scripts/reachability/entry_points.toml",
        keep_path=synthetic_repo / "scripts/reachability/keep.toml",
        candidate_dirs=["pkg"],
    )
    assert findings_after_delete == []


def test_python_gate_fails_on_new_non_shipping_module_without_keep_entry(
    synthetic_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    gate = _load_gate()
    _write(synthetic_repo, "pkg/unimported_new.py", "X = 42\n")
    rc = gate.main(
        [
            "--python",
            "--root",
            str(synthetic_repo),
            "--baseline",
            str(synthetic_repo / "scripts/reachability/baseline.json"),
            "--entries",
            str(synthetic_repo / "scripts/reachability/entry_points.toml"),
            "--keep",
            str(synthetic_repo / "scripts/reachability/keep.toml"),
            "--candidate-dir",
            "pkg",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "pkg/unimported_new.py" in captured.err


def test_python_gate_passes_when_new_module_has_keep_entry(synthetic_repo: Path) -> None:
    gate = _load_gate()
    _write(synthetic_repo, "pkg/kept_new.py", "KEPT = True\n")
    _write(
        synthetic_repo,
        "scripts/reachability/keep.toml",
        '[[keep]]\nmodule = "pkg/kept_new"\nreason = "F-999 complete feature"\n',
    )
    baseline = gate.load_baseline(synthetic_repo / "scripts/reachability/baseline.json")
    findings = gate.check_python_reachability(
        synthetic_repo,
        baseline,
        entries_path=synthetic_repo / "scripts/reachability/entry_points.toml",
        keep_path=synthetic_repo / "scripts/reachability/keep.toml",
        candidate_dirs=["pkg"],
    )
    assert findings == []


def test_python_gate_fails_on_unresolved_dynamic_import_or_missing_entry(
    synthetic_repo: Path,
) -> None:
    gate = _load_gate()
    _write(
        synthetic_repo,
        "pkg/main.py",
        'import importlib\nfrom pkg import LIVE\nimportlib.import_module("pkg.secret_dyn")\n',
    )
    _write(
        synthetic_repo,
        "scripts/reachability/entry_points.toml",
        'entries = ["pkg/main.py", "pkg/missing_entry.py"]\ndynamic_allow = []\n',
    )
    baseline = gate.load_baseline(synthetic_repo / "scripts/reachability/baseline.json")
    findings = gate.check_python_reachability(
        synthetic_repo,
        baseline,
        entries_path=synthetic_repo / "scripts/reachability/entry_points.toml",
        keep_path=synthetic_repo / "scripts/reachability/keep.toml",
        candidate_dirs=["pkg"],
    )
    joined = "\n".join(findings)
    assert "pkg.secret_dyn" in joined
    assert "pkg/missing_entry.py" in joined


def test_knip_gate_passes_when_files_and_exports_are_subset_of_baseline(
    synthetic_repo: Path,
) -> None:
    gate = _load_gate()
    baseline = gate.load_baseline(synthetic_repo / "scripts/reachability/baseline.json")
    knip_report = {
        "files": ["src/types/enrichment.ts"],
        "issues": [
            {
                "file": "src/services/api.ts",
                "exports": [{"name": "legacyUnusedExport", "line": 10}],
            }
        ],
    }
    assert gate.check_knip_reachability(knip_report, baseline) == []
    # Empty report (after baseline items are cleaned up) also passes.
    assert gate.check_knip_reachability({"files": [], "issues": []}, baseline) == []


def test_knip_gate_fails_on_new_unused_file_and_new_unused_export(
    synthetic_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    gate = _load_gate()
    knip_json_path = _write(
        synthetic_repo,
        "knip-out.json",
        json.dumps(
            {
                "files": [
                    "src/types/enrichment.ts",
                    "src/components/OrphanWidget.tsx",
                ],
                "issues": [
                    {
                        "file": "src/services/api.ts",
                        "exports": [
                            {"name": "legacyUnusedExport", "line": 10},
                            {"name": "newDeadHelper", "line": 99},
                        ],
                    },
                    {
                        "file": "src/utils/fresh.ts",
                        "exports": [{"name": "unusedFreshFn", "line": 4}],
                    },
                ],
            }
        ),
    )
    rc = gate.main(
        [
            "--knip",
            "--baseline",
            str(synthetic_repo / "scripts/reachability/baseline.json"),
            "--knip-json",
            str(knip_json_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "src/components/OrphanWidget.tsx" in captured.err
    assert "src/services/api.ts: newDeadHelper" in captured.err
    assert "src/utils/fresh.ts: unusedFreshFn" in captured.err
    assert "legacyUnusedExport" not in captured.err


def test_knip_gate_fails_closed_on_malformed_knip_output(
    synthetic_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    gate = _load_gate()
    bad_json_path = _write(synthetic_repo, "bad-knip.json", "{not-json")
    rc = gate.main(
        [
            "--knip",
            "--baseline",
            str(synthetic_repo / "scripts/reachability/baseline.json"),
            "--knip-json",
            str(bad_json_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert "knip" in captured.err.lower()


def test_both_legs_run_and_report_together_when_both_fail(
    synthetic_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    gate = _load_gate()
    _write(synthetic_repo, "pkg/new_dead_mod.py", "DEAD = 2\n")
    knip_json_path = _write(
        synthetic_repo,
        "knip-both.json",
        json.dumps(
            {
                "files": ["src/components/NewDead.tsx"],
                "issues": [],
            }
        ),
    )
    rc = gate.main(
        [
            "--root",
            str(synthetic_repo),
            "--baseline",
            str(synthetic_repo / "scripts/reachability/baseline.json"),
            "--entries",
            str(synthetic_repo / "scripts/reachability/entry_points.toml"),
            "--keep",
            str(synthetic_repo / "scripts/reachability/keep.toml"),
            "--candidate-dir",
            "pkg",
            "--knip-json",
            str(knip_json_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "pkg/new_dead_mod.py" in captured.err
    assert "src/components/NewDead.tsx" in captured.err


@pytest.mark.timeout(120)
def test_real_tree_baseline_and_python_reachability_are_clean() -> None:
    gate = _load_gate()
    assert BASELINE_JSON.is_file(), f"missing committed baseline: {BASELINE_JSON}"
    baseline = gate.load_baseline(BASELINE_JSON)
    assert baseline["schema_version"] == 1
    assert baseline["pinned_at_commit"] == "ca0e5a081"

    # Python leg passes on the real tree.
    py_findings = gate.check_python_reachability(REPO_ROOT, baseline)
    assert py_findings == [], f"real tree failed Python reachability gate: {py_findings}"

    # F3.2 (#7246) merge baseline invariants (ruling 257).
    assert baseline["knip"]["files"] == [
        "src/components/system/WorkerActionConfirmDialog.tsx",
        "src/types/enrichment.ts",
    ]
    total_baseline_exports = sum(len(v) for v in baseline["knip"]["exports"].values())
    assert total_baseline_exports == 475
    assert len(baseline["knip"]["exports"]) == 222

    # Reconstruct the baseline knip JSON and verify check_knip_reachability passes on it,
    # and fails if one extra file or export is added.
    baseline_knip_report = {
        "files": list(baseline["knip"]["files"]),
        "issues": [
            {
                "file": file_path,
                "exports": [{"name": exp, "line": 1} for exp in exports],
            }
            for file_path, exports in baseline["knip"]["exports"].items()
        ],
    }
    assert gate.check_knip_reachability(baseline_knip_report, baseline) == []
    mutated_report = {
        "files": [*baseline["knip"]["files"], "src/components/ThrowawayUnimported.tsx"],
        "issues": baseline_knip_report["issues"],
    }
    assert gate.check_knip_reachability(mutated_report, baseline) != []
