#!/usr/bin/env python3
"""Tests for scripts/audit/battery_census.py (O1.7).

    uv run python -m pytest scripts/audit/test_battery_census.py -q

The fixture tree pins the detection decisions:
  * test_<module>_batch28_22.py (sequence-suffixed, the audit's own example)
    is a battery file whose module is gpu_monitor, not gpu_monitor_batch28;
  * an ordinary test_foo.py and a test_batchless.py are NOT batteries;
  * a parametrize with a literal list multiplies the collected count; a
    non-literal arg counts as 1 and is FLAGGED (never silently guessed).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "audit" / "battery_census.py"

BATTERY = '''\
import pytest


class TestGpu:
    def test_one(self):
        assert 1

    def test_two(self):
        assert 2

    @pytest.mark.parametrize("level", ["a", "b", "c"])
    def test_param(self, level):
        assert level


def test_top_level():
    assert True
'''

FLAGGED = '''\
import pytest


@pytest.mark.parametrize("n", range(4))
def test_dynamic(n):
    assert n
'''


def build_tree(root: Path) -> None:
    tests = root / "backend" / "tests" / "unit" / "services"
    tests.mkdir(parents=True)
    (tests / "test_gpu_monitor_batch28_22.py").write_text(BATTERY, encoding="utf-8")
    (tests / "test_gpu_monitor_batch29.py").write_text(FLAGGED, encoding="utf-8")
    (tests / "test_gpu_monitor_helpers.py").write_text("def test_plain():\n    assert 1\n", encoding="utf-8")
    (tests / "test_batchless.py").write_text("def test_b():\n    assert 1\n", encoding="utf-8")


def run_script(tree: Path) -> tuple[int, dict, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tree)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, json.loads(proc.stdout) if proc.returncode == 0 else {}, proc.stderr


def test_fixture_census(tmp_path: Path):
    build_tree(tmp_path)
    rc, result, _ = run_script(tmp_path)
    assert rc == 0
    assert result["file_count"] == 2  # both batch files; helpers and batchless excluded
    by_path = {r["path"].rsplit("/", 1)[-1]: r for r in result["files"]}
    b28 = by_path["test_gpu_monitor_batch28_22.py"]
    assert b28["module"] == "gpu_monitor"
    assert b28["tests"] == 6  # 2 class + 3x param + 1 top-level
    assert by_path["test_gpu_monitor_batch29.py"]["flagged_parametrize"] == 1
    assert result["total_tests"] == 7  # the flagged parametrize counts as 1, not 4
    assert result["flagged_files"] == 1


def test_letter_suffix_without_separator_is_a_battery(tmp_path: Path):
    """`test_logs_batch13b.py` is a battery (review finding, 2026-10-09).

    The contract glob is test_*_batchNN*.py — `*` matches the bare letter.
    The first regex required [_+.] before any suffix and silently dropped 8
    such files (1,758 lines; 123+8=131 ~= the audit's [A] 130, evidence the
    [A] corpus included them). This pins the widened regex; the "batched"
    sibling pins that widening did not over-match a plain English word.
    """
    tests = tmp_path / "backend" / "tests" / "unit" / "api" / "routes"
    tests.mkdir(parents=True)
    (tests / "test_logs_batch13b.py").write_text(BATTERY, encoding="utf-8")
    (tests / "test_logs_batched.py").write_text(BATTERY, encoding="utf-8")  # no digits: not a battery
    rc, result, _ = run_script(tmp_path)
    assert rc == 0
    assert result["file_count"] == 1
    row = result["files"][0]
    assert row["path"].endswith("test_logs_batch13b.py")
    assert row["module"] == "logs"  # not "logs_batch13b"


def test_real_tree_has_no_unmatched_battery_names():
    """Tree guard: every test_*_batchNN*.py file (the contract glob) is counted.

    A fixture cannot catch a future name shape the regex misses — this walks
    the real tree and fails loudly on any contract-glob file the script's own
    regex skips, which is the silent-skip class this census exists to avoid.
    """
    from battery_census import BATTERY_RE  # noqa: PLC0415 — pin lives with the script

    skip = {".git", "__pycache__", "node_modules", ".venv", ".pytest_cache", ".mypy_cache"}
    missed = [
        p.relative_to(REPO_ROOT).as_posix()
        for p in REPO_ROOT.rglob("test_*_batch[0-9]*.py")
        if not any(part in skip for part in p.relative_to(REPO_ROOT).parts[:-1])
        and not BATTERY_RE.match(p.name)
    ]
    assert not missed, f"contract-glob battery files the regex silently skips: {missed}"


def test_summary_line(tmp_path: Path):
    build_tree(tmp_path)
    rc, _, err = run_script(tmp_path)
    assert rc == 0
    assert "O1.7 battery-census: 2 battery files" in err
    assert "1 with non-literal parametrize args" in err


def test_parse_failure_is_loud(tmp_path: Path):
    tests = root = tmp_path / "t"
    tests.mkdir()
    (tests / "test_x_batch1.py").write_text("def broken(:\n", encoding="utf-8")
    rc, _, err = run_script(tmp_path)
    assert rc == 1
    assert "parse failure" in err
