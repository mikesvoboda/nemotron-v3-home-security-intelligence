#!/usr/bin/env python3
"""Tests for scripts/check-test-timeouts.py (PRE-EXISTING fix, pre-push gate).

Run explicitly; outside testpaths:

    uv run python -m pytest scripts/test_check_test_timeouts.py -q

The contract under test is the one the script DOCUMENTS to developers:
"Solve by adding comment: # mocked, # patched, # cancelled" (its own help
output, SAFE_COMMENTS). backend/tests/chaos/test_worker_chaos.py carried
12 long-sleep sites annotated "# chaos test - mocked" / "# chaos test timing -
mocked" — the author followed the documented contract, but the checker's
`"# mocked" in line` substring test never matches "chaos test - mocked", so
every site flagged. The file predates the hook (d5eb7b54/#3181) and had simply
never been through it. These fixtures pin BOTH readings so the fix can't
silently drift: a comment that contains the documented token passes, and the
bare hyphenated variant is judged deliberately (see the parametrized pair).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-test-timeouts.py"

SAMPLE = """
import asyncio

async def test_worker_survives_crash():
    await worker.start()
    await asyncio.sleep({sleep})  {comment}
    assert worker.running
"""


def run_checker(tmp_path: Path, content: str) -> tuple[int, str]:
    f = tmp_path / "test_sample_chaos.py"
    f.write_text(content)
    r = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(f)],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.returncode, r.stdout


def test_documented_token_passes(tmp_path):
    """'# mocked' — exactly what the script's own help text prescribes."""
    rc, out = run_checker(tmp_path, SAMPLE.format(sleep=2.0, comment="# mocked"))
    assert rc == 0, f"documented safe comment was flagged: {out}"


def test_long_sleep_without_comment_fails(tmp_path):
    """The gate still bites with no safe annotation — fix must not launder."""
    rc, out = run_checker(tmp_path, SAMPLE.format(sleep=2.0, comment=""))
    assert rc == 1, f"unannotated long sleep passed the check: {out}"


def test_prose_keeps_documented_token(tmp_path):
    """The form shipped in test_worker_chaos.py after the repair: '# mocked'
    up front (the contract token the substring check demands) with the
    author's context preserved behind it — pinning exactly what the tree now
    uses so a future edit that drops the token goes red here first."""
    rc, out = run_checker(tmp_path, SAMPLE.format(sleep=1.5, comment="# mocked: chaos test"))
    assert rc == 0, f"shipped comment form was flagged: {out}"


def test_hyphenated_variant_is_the_defect(tmp_path):
    """'# chaos test - mocked' — the form the chaos file shipped: does NOT
    contain '# mocked', so the documented contract is not met and the flag is
    CORRECT. This pins that the checker was not bent; the comments were."""
    rc, out = run_checker(tmp_path, SAMPLE.format(sleep=1.5, comment="# chaos test - mocked"))
    assert rc == 1, f"checker was widened past its contract: {out}"
