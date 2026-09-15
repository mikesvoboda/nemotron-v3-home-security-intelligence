"""Unit tests for scripts/check-version-consistency.sh.

ABOUTME: The runtime-version drift gate (the "ci.yml said 3.11 while uv ran
3.14" bug class). Tests build throwaway repo trees and assert the gate passes
when declarations agree and fails — naming each drift — when they don't.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "check-version-consistency.sh"


def make_tree(tmp_path: Path) -> Path:
    """Minimal repo tree carrying every file the gate reads, all consistent."""
    tree = tmp_path
    (tree / ".github" / "workflows").mkdir(parents=True)
    (tree / "scripts").mkdir(parents=True)
    (tree / "frontend").mkdir(parents=True)
    (tree / "backend").mkdir(parents=True)

    shutil.copy(REPO_ROOT / ".nvmrc", tree / ".nvmrc")
    shutil.copy(REPO_ROOT / ".python-version", tree / ".python-version")
    shutil.copy(REPO_ROOT / "pyproject.toml", tree / "pyproject.toml")
    shutil.copy(
        REPO_ROOT / ".github" / "workflows" / "ci.yml", tree / ".github" / "workflows" / "ci.yml"
    )
    shutil.copy(REPO_ROOT / "frontend" / "package.json", tree / "frontend" / "package.json")
    shutil.copy(REPO_ROOT / "frontend" / "Dockerfile", tree / "frontend" / "Dockerfile")
    shutil.copy(REPO_ROOT / "backend" / "Dockerfile", tree / "backend" / "Dockerfile")
    shutil.copy(REPO_ROOT / "scripts" / "validate.sh", tree / "scripts" / "validate.sh")
    return tree


def run_gate(tree: Path) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603  # intentional - tests our own script
        [  # noqa: S607  # partial path OK for test script
            "bash",
            str(SCRIPT),
            str(tree),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


class TestGatePassesOnConsistentTree:
    def test_consistent_tree_exits_zero(self, tmp_path):
        tree = make_tree(tmp_path)
        result = run_gate(tree)
        assert result.returncode == 0, result.stderr
        assert "consistency OK" in result.stdout

    def test_real_repo_passes(self):
        """The shipping tree itself must satisfy the gate (guards the allowlist)."""
        result = subprocess.run(  # noqa: S603  # intentional - tests our own script
            [  # noqa: S607  # partial path OK for test script
                "bash",
                str(SCRIPT),
            ],  # default root = parent of scripts/
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


class TestGateCatchesDrift:
    def test_python_label_fiction(self, tmp_path):
        """The exact 2025-2026 bug: ci.yml labels say 3.11, uv runs 3.14."""
        tree = make_tree(tmp_path)
        ci = tree / ".github" / "workflows" / "ci.yml"
        ci.write_text(
            ci.read_text().replace("python-version: ['3.14']", "python-version: ['3.11']")
        )
        result = run_gate(tree)
        assert result.returncode == 1
        assert "make the label honest" in result.stderr

    def test_node_eol_regression(self, tmp_path):
        tree = make_tree(tmp_path)
        ci = tree / ".github" / "workflows" / "ci.yml"
        ci.write_text(ci.read_text().replace("NODE_VERSION: '24'", "NODE_VERSION: '20'"))
        result = run_gate(tree)
        assert result.returncode == 1
        assert "pins Node 20" in result.stderr

    def test_dockerfile_off_truth(self, tmp_path):
        tree = make_tree(tmp_path)
        df = tree / "frontend" / "Dockerfile"
        df.write_text(df.read_text().replace("node:24.21.0", "node:20.19.6"))
        result = run_gate(tree)
        assert result.returncode == 1
        assert "frontend/Dockerfile" in result.stderr

    def test_pyproject_split(self, tmp_path):
        tree = make_tree(tmp_path)
        pp = tree / "pyproject.toml"
        pp.write_text(
            pp.read_text().replace('requires-python = ">=3.14"', 'requires-python = ">=3.12"')
        )
        result = run_gate(tree)
        assert result.returncode == 1
        assert "requires-python" in result.stderr

    def test_allowlisted_tooling_pin_passes(self, tmp_path):
        """Deliberate off-runtime pins (build-setup.yml 3.12) must not fail."""
        tree = make_tree(tmp_path)
        wf = tree / ".github" / "workflows"
        shutil.copy(REPO_ROOT / ".github" / "workflows" / "build-setup.yml", wf / "build-setup.yml")
        result = run_gate(tree)
        assert result.returncode == 0, result.stderr

    def test_unallowlisted_python_pin_fails(self, tmp_path):
        """A NEW workflow pinning off-truth python without the allowlist fails."""
        tree = make_tree(tmp_path)
        wf = tree / ".github" / "workflows"
        (wf / "brand-new.yml").write_text("jobs:\n  x:\n    - python-version: '3.9'\n")
        result = run_gate(tree)
        assert result.returncode == 1
        assert "brand-new.yml" in result.stderr

    def test_validate_sh_drift(self, tmp_path):
        tree = make_tree(tmp_path)
        v = tree / "scripts" / "validate.sh"
        # A re-introduced hardcoded literal must agree with .nvmrc or fail.
        v.write_text(v.read_text() + "\nREQUIRED_NODE_MAJOR=18\n")
        result = run_gate(tree)
        assert result.returncode == 1
        assert "validate.sh" in result.stderr

    def test_engines_excludes_node_major(self, tmp_path):
        tree = make_tree(tmp_path)
        pkg = tree / "frontend" / "package.json"
        pkg.write_text(pkg.read_text().replace(">=24.0.0", ">=23.0.0 <24.0.0"))
        result = run_gate(tree)
        assert result.returncode == 1
        assert "engines" in result.stderr


class TestMissingSourceOfTruth:
    def test_missing_nvmrc_fails_loudly(self, tmp_path):
        tree = make_tree(tmp_path)
        (tree / ".nvmrc").unlink()
        result = run_gate(tree)
        assert result.returncode == 1
        assert ".nvmrc missing" in result.stderr

    def test_missing_python_version_fails_loudly(self, tmp_path):
        tree = make_tree(tmp_path)
        (tree / ".python-version").unlink()
        result = run_gate(tree)
        assert result.returncode == 1
        assert ".python-version missing" in result.stderr
