#!/usr/bin/env python3
"""Tests for scripts/audit/literal_groups.py (O1.7).

    uv run python -m pytest scripts/audit/test_literal_groups.py -q

The fixture tree pins the reuse contract with scripts/parametrize-guard.py
and the one shape this census adds over it:
  * three same-class methods identical modulo literals form ONE group of 3
    (the guard would hide this class entirely below its --min 8 default);
  * a fourth method differing beyond literals (a different call target) is
    NOT in the group — masked-body identity, imported from the guard;
  * two methods whose pytest.raises match= values differ do NOT group even
    with identical bodies — the raises-bucket guard, imported from the guard;
  * module-level duplicates bucket under class "" and still group.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "audit" / "literal_groups.py"

FIXTURE = '''\
import pytest


class TestSmallDupes:
    def test_a(self):
        assert fn("x") == 1

    def test_b(self):
        assert fn("y") == 2

    def test_c(self):
        assert fn("z") == 3

    def test_different_call(self):
        assert other("x") == 1


class TestRaisesSplit:
    def test_a(self):
        with pytest.raises(ValueError, match="alpha"):
            fn("x")

    def test_b(self):
        with pytest.raises(ValueError, match="beta"):
            fn("y")

    def test_c(self):
        with pytest.raises(ValueError, match="alpha"):
            fn("z")

    def test_d(self):
        with pytest.raises(ValueError, match="alpha"):
            fn("w")


def test_mod_a():
    assert top("x")


def test_mod_b():
    assert top("y")


def test_mod_c():
    assert top("z")
'''


def build_tree(root: Path) -> None:
    tests = root / "pkg" / "tests"
    tests.mkdir(parents=True)
    (tests / "test_fixture_shapes.py").write_text(FIXTURE, encoding="utf-8")


def run_script(tree: Path, extra: list[str] = ()) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tree), *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"script failed: {proc.stderr[-500:]}"
    return json.loads(proc.stdout)


def test_fixture_groups(tmp_path: Path):
    build_tree(tmp_path)
    result = run_script(tmp_path)
    groups = {
        (g["class"], tuple(g["members"])): g for g in result["groups_detail"]
    }
    # the 3-method literal cluster, excluding the different-call method
    dupes = [g for (cls, _), g in groups.items() if cls == "TestSmallDupes"]
    assert len(dupes) == 1 and dupes[0]["size"] == 3
    assert "test_different_call" not in dupes[0]["members"]
    # raises-bucket split: the three alpha members group; the beta member
    # never joins them despite an otherwise identical masked body
    raises = [g for (cls, _), g in groups.items() if cls == "TestRaisesSplit"]
    assert len(raises) == 1
    assert set(raises[0]["members"]) == {"test_a", "test_c", "test_d"}
    # guard contract: raises_matches stores ast.unparse output, which keeps
    # the source quotes — 'alpha' with them, by design (imported, not ours)
    assert raises[0]["raises_match"] == ["'alpha'"]
    # module-level trio groups under class ""
    mod = [g for (cls, _), g in groups.items() if cls == ""]
    assert len(mod) == 1 and mod[0]["size"] == 3


def test_counts_and_summary(tmp_path: Path):
    build_tree(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    result = json.loads(proc.stdout)
    assert result["min_group_size"] == 3
    assert result["groups"] == 3  # TestSmallDupes trio, TestRaisesSplit alpha trio, module trio
    assert result["functions"] == 9
    assert "O1.7 literal-groups: 3 groups of >=3" in proc.stderr


def test_min_raises_the_bar(tmp_path: Path):
    build_tree(tmp_path)
    result = run_script(tmp_path, ["--min", "4"])
    assert result["groups"] == 0


def test_installed_packages_are_not_scanned(tmp_path: Path):
    """A census of whatever pip resolved is not a baseline anyone can re-run.

    Measured on the first real run: without the .venv entry in SKIP_DIRNAMES
    this census counted 103 of its 605 groups inside INSTALLED packages' own
    test files (this environment has 1,831 test_*.py under .venv), so the
    figure moved with the lockfile and one vendor file written in newer syntax
    would have tripped the loud SyntaxError exit on every run. Same set the
    sibling censuses already use.
    """
    build_tree(tmp_path)
    vendored = tmp_path / ".venv" / "lib" / "site-packages" / "vendor" / "tests"
    vendored.mkdir(parents=True)
    vendored.joinpath("test_vendor.py").write_text(FIXTURE, encoding="utf-8")
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "test_js.py").write_text(
        FIXTURE, encoding="utf-8"
    )
    result = run_script(tmp_path)
    assert result["groups"] == 3  # the fixture tree's trio count, unchanged
    assert result["files"] == 1
    assert not any(".venv" in g["file"] or "node_modules" in g["file"] for g in result["groups_detail"])


def test_parse_failure_is_loud(tmp_path: Path):
    (tmp_path / "test_broken.py").write_text("def broken(:\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "parse failure" in proc.stderr
