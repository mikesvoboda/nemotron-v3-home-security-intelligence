#!/usr/bin/env python3
"""Tests for get_changed_files in scripts/check-test-coverage-gate.py (WP0.9 family).

Run explicitly; outside testpaths:

    uv run python -m pytest scripts/test_check_gate_changed_files.py -q

The PRE-EXISTING parser bug: `git diff --name-status --numstat` does NOT emit
numstat's 3-field lines — git's own doc says name-status wins, and lines come
out as `M\tpath` (2 fields). The old parser required >=3 fields, so EVERY line
was skipped and get_changed_files returned [] for any diff — the requirement
half of the gate was blind from birth (the pre-WP0.9 `if not changes: return 0`
hid even the emptiness). WP0.9's drop-diff fix made the blindness visible
("No changed files detected" printed on a 30-file branch); this pins the fix.

Scratch repos use REAL git so the parser is tested against git's actual output
formats, not a guess of them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-test-coverage-gate.py"


def get_changed_files_fn():
    import importlib.util

    spec = importlib.util.spec_from_file_location("ctcg_cf", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.get_changed_files


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(args, cwd=repo, check=True)
    return repo


def commit_all(repo: Path, msg: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", msg], cwd=repo, check=True)


def test_modified_file_parsed(tmp_path, monkeypatch):
    """THE regression: `M\\tpath` 2-field lines were silently dropped."""
    repo = init_repo(tmp_path)
    monkeypatch.chdir(repo)
    (repo / "f.py").write_text("a\n" * 10)
    commit_all(repo, "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    (repo / "f.py").write_text("a\n" * 10 + "b\n" * 5)
    commit_all(repo, "mod")

    changes = get_changed_files_fn()(base)
    assert [c.path for c in changes] == ["f.py"], f"modified file lost by parser: {changes}"
    assert changes[0].status == "modified"
    assert changes[0].additions == 5 and changes[0].deletions == 0


def test_added_and_deleted_parsed(tmp_path, monkeypatch):
    repo = init_repo(tmp_path)
    monkeypatch.chdir(repo)
    (repo / "gone.py").write_text("x\n")
    commit_all(repo, "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    (repo / "gone.py").unlink()
    (repo / "new.py").write_text("new\n")
    commit_all(repo, "swap")

    changes = {c.path: c.status for c in get_changed_files_fn()(base)}
    assert changes == {"gone.py": "deleted", "new.py": "added"}


def test_binary_file_not_fatal(tmp_path, monkeypatch):
    """Binary diffs report '-' for numstat counts — must not crash or vanish."""
    repo = init_repo(tmp_path)
    monkeypatch.chdir(repo)
    (repo / "blob.bin").write_bytes(b"\x00\x01")
    commit_all(repo, "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02\x03")
    commit_all(repo, "bin")

    changes = get_changed_files_fn()(base)
    assert [c.path for c in changes] == ["blob.bin"]
    assert changes[0].additions == 0 and changes[0].deletions == 0


def test_rename_parsed(tmp_path, monkeypatch):
    repo = init_repo(tmp_path)
    monkeypatch.chdir(repo)
    (repo / "old_name.py").write_text("same\n" * 20)
    commit_all(repo, "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(["git", "mv", "old_name.py", "new_name.py"], cwd=repo, check=True)
    commit_all(repo, "rename")

    changes = get_changed_files_fn()(base)
    assert [c.path for c in changes] == ["new_name.py"], "rename should track to the new path"
    assert changes[0].status == "renamed"
