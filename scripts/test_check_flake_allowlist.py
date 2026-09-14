"""Tests for scripts/check-flake-allowlist.py (run explicitly; outside testpaths)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-flake-allowlist.py"
REPO_ALLOWLIST = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "flake-allowlist.yml"
)


def run_on(tmp_path: Path, body: str) -> subprocess.CompletedProcess:
    al = tmp_path / "allowlist.yml"
    al.write_text(body, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(al), "--today", "2026-10-01"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_entry_passes(tmp_path):
    r = run_on(
        tmp_path,
        "flakes:\n  - id: test_foo\n    tracking: NEM-9999\n    expires: 2026-12-31\n",
    )
    assert r.returncode == 0, r.stderr


def test_missing_tracking_fails(tmp_path):
    r = run_on(tmp_path, "flakes:\n  - id: test_foo\n    expires: 2026-12-31\n")
    assert r.returncode == 1
    assert "tracking" in r.stderr.lower()


def test_missing_expiry_fails(tmp_path):
    r = run_on(tmp_path, "flakes:\n  - id: test_foo\n    tracking: NEM-1\n")
    assert r.returncode == 1


def test_expired_entry_fails(tmp_path):
    r = run_on(
        tmp_path,
        "flakes:\n  - id: test_foo\n    tracking: NEM-1\n    expires: 2026-09-01\n",
    )
    assert r.returncode == 1
    assert "expired" in r.stderr.lower()


def test_repo_allowlist_is_valid_today():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
