"""Tests for scripts/check-test-collection.py (run explicitly; outside testpaths)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "check-test-collection.py"


def run_script(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )


@pytest.fixture()
def git_tree(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    return tmp_path


def stage_and_note(git_tree: Path, rel: str, content: bytes) -> None:
    p = git_tree / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    subprocess.run(["git", "add", "--", rel], cwd=git_tree, check=True)


def test_clean_tree_passes(git_tree):
    stage_and_note(git_tree, "backend/tests/unit/test_ok.py", b"def test_a():\n    assert True\n")
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 0, r.stderr


def test_zero_byte_python_test_detected(git_tree):
    stage_and_note(git_tree, "backend/tests/unit/test_empty.py", b"")
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 1
    assert "test_empty.py" in r.stderr + r.stdout


def test_zero_byte_ts_test_detected(git_tree):
    stage_and_note(git_tree, "frontend/src/a.test.ts", b"")
    r = run_script(git_tree, "frontend/src")
    assert r.returncode == 1
    assert "a.test.ts" in r.stderr + r.stdout


def test_def_only_py_collects_zero_tests_detected(git_tree):
    stage_and_note(
        git_tree,
        "backend/tests/unit/test_helpers_only.py",
        b"def helper():\n    return 1\n",
    )
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 1
    assert "test_helpers_only.py" in r.stderr + r.stdout


def test_allow_suppresses(git_tree):
    stage_and_note(git_tree, "backend/tests/unit/test_empty.py", b"")
    r = run_script(git_tree, "backend/tests", "--allow", "backend/tests/unit/test_empty.py")
    assert r.returncode == 0


def test_ignores_untracked(git_tree):
    p = git_tree / "backend/tests/unit/test_scratch.py"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"")  # never git-added
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 0


# --- import-aware heuristic (R-M2-COLLECTION-FINDINGS class 2: wildcard
# re-export shims collect transitively; the pre-fix script flagged them) ---


def test_star_import_from_test_module_collects(git_tree):
    stage_and_note(
        git_tree,
        "backend/tests/integration/test_system_api.py",
        b"def test_a():\n    assert True\n",
    )
    stage_and_note(
        git_tree,
        "backend/tests/integration/test_system.py",
        b"from backend.tests.integration.test_system_api import *  # noqa: F403\n",
    )
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 0, r.stderr


def test_named_test_imports_from_test_module_collect(git_tree):
    stage_and_note(
        git_tree,
        "backend/tests/integration/services/test_model_loaders.py",
        b"class TestLoaders:\n    def test_load(self):\n        assert True\n",
    )
    stage_and_note(
        git_tree,
        "backend/tests/integration/services/test_age_classifier_loader.py",
        b"from backend.tests.integration.services.test_model_loaders import (  # noqa: F401\n"
        b"    TestLoaders,\n"
        b")\n",
    )
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 0, r.stderr


def test_relative_star_import_from_test_module_collects(git_tree):
    stage_and_note(git_tree, "backend/tests/x/test_real.py", b"def test_a():\n    assert True\n")
    stage_and_note(
        git_tree,
        "backend/tests/x/test_shim.py",
        b"from .test_real import *  # noqa: F403\n",
    )
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 0, r.stderr


def test_import_from_non_test_module_still_flagged(git_tree):
    # negative control: importing from a NON-test module must not count
    stage_and_note(
        git_tree,
        "backend/tests/unit/test_no_tests.py",
        b"from backend.services import system  # noqa: F401\n",
    )
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 1
    assert "test_no_tests.py" in r.stderr + r.stdout


def test_importing_helper_from_test_module_counts_as_collects(git_tree):
    # documented blind spot: helper-only import from a test_* module still counts
    stage_and_note(
        git_tree, "backend/tests/x/test_defs_tests.py", b"def test_a():\n    assert True\n"
    )
    stage_and_note(
        git_tree,
        "backend/tests/x/test_imports_helper.py",
        b"from backend.tests.x.test_defs_tests import make_fixture  # noqa: F401\n",
    )
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 0, r.stderr


# --- allowlist file mechanism (R-FCL-T1-ALLOWLIST) ---


def test_allowlist_file_suppresses(git_tree):
    stage_and_note(git_tree, "backend/tests/unit/test_empty.py", b"")
    allowlist = git_tree / "tmp-allowlist.txt"
    allowlist.write_text("# R-TRACKING-REF — zero-byte\nbackend/tests/unit/test_empty.py\n")
    r = run_script(git_tree, "backend/tests", "--allowlist", str(allowlist))
    assert r.returncode == 0, r.stderr


def test_allowlist_file_missing_is_empty(git_tree):
    stage_and_note(git_tree, "backend/tests/unit/test_empty.py", b"")
    r = run_script(
        git_tree,
        "backend/tests",
        "--allowlist",
        str(git_tree / "no-such-allowlist.txt"),
    )
    assert r.returncode == 1
    assert "test_empty.py" in r.stderr + r.stdout


def test_allow_flag_adds_on_top_of_allowlist_file(git_tree):
    stage_and_note(git_tree, "backend/tests/unit/test_empty.py", b"")
    stage_and_note(git_tree, "backend/tests/unit/test_other.py", b"def helper():\n    return 1\n")
    allowlist = git_tree / "tmp-allowlist.txt"
    allowlist.write_text("backend/tests/unit/test_empty.py\n")
    r = run_script(
        git_tree,
        "backend/tests",
        "--allowlist",
        str(allowlist),
        "--allow",
        "backend/tests/unit/test_other.py",
    )
    assert r.returncode == 0, r.stderr


def test_allowlist_file_entry_without_tracking_ref_still_honored(git_tree):
    # comment lines are skipped; an id-only line is an id, not an error
    stage_and_note(git_tree, "backend/tests/unit/test_empty.py", b"")
    allowlist = git_tree / "tmp-allowlist.txt"
    allowlist.write_text("backend/tests/unit/test_empty.py\n")
    r = run_script(git_tree, "backend/tests", "--allowlist", str(allowlist))
    assert r.returncode == 0, r.stderr


def test_allowlist_file_lines_with_trailing_comments(git_tree):
    # the repo's real format: <path>  # <tracking-ref> on one line; '#' starts
    # the comment and the prefix is the id
    stage_and_note(git_tree, "backend/tests/unit/test_empty.py", b"")
    allowlist = git_tree / "tmp-allowlist.txt"
    allowlist.write_text(
        "backend/tests/unit/test_empty.py  # R-TRACKING-REF (M1 ledger) — zero-byte; write-or-delete queued\n"
    )
    r = run_script(git_tree, "backend/tests", "--allowlist", str(allowlist))
    assert r.returncode == 0, r.stderr


def test_allowlist_typo_entry_does_not_suppress(git_tree):
    # malformed id = no match = finding surfaces (never silently swallowed)
    stage_and_note(git_tree, "backend/tests/unit/test_empty.py", b"")
    allowlist = git_tree / "tmp-allowlist.txt"
    allowlist.write_text("backend/tests/unit/test_empty.py.bak  # typo'd id\n")
    r = run_script(git_tree, "backend/tests", "--allowlist", str(allowlist))
    assert r.returncode == 1
    assert "test_empty.py" in r.stderr + r.stdout


def test_repo_allowlist_resolves_next_to_script_not_cwd(git_tree):
    # default path is the SCRIPT's dir, not cwd: a same-named file in cwd must
    # be ignored, and (in this tmp tree) no allowlist sits beside the script
    stage_and_note(git_tree, "backend/tests/unit/test_empty.py", b"")
    (git_tree / "collection-sanity-allowlist.txt").write_text("backend/tests/unit/test_empty.py\n")
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 1
    assert "test_empty.py" in r.stderr + r.stdout
