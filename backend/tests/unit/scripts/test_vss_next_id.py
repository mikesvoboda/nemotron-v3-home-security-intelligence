"""Unit tests for scripts/vss-next-id.py.

ABOUTME: ISS ids were allocated as "highest plus one" within one branch, so ISS-088 could be minted on
a PR branch while another branch (or the append-only ledger) already held or cited it. The helper scans
EVERY ref and worktree, and the ledger and specs as well as the register, and prints the next free id.
These tests build throwaway git repos with the ids spread across branches the way that collision does.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "vss-next-id.py"
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}
REGISTER = "docs/vss-integration/17-action-plan.md"
LEDGER = "docs/plans/2026-09-23-vss-gaming-gpu-ledger.md"
ERR16 = "docs/vss-integration/16-errata-2026-10-03.md"


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
        env=ENV,
    )
    return done.stdout


def write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def commit(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    write(r, REGISTER, "#### ISS-001 — one\n#### ISS-087 — build\n")
    write(r, ERR16, "**E29. a.**\n\n**E124. b.**\n")
    commit(r, "base")
    return r


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), f"{SCRIPT} is missing"
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--repo", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        env=ENV,
    )


def test_next_issue_id_is_highest_plus_one(repo: Path) -> None:
    out = run(repo, "iss")
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ISS-088"


def test_an_id_minted_on_another_branch_is_seen(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "other")
    write(
        repo,
        REGISTER,
        "#### ISS-001 — one\n#### ISS-087 — build\n#### ISS-088 — minted elsewhere\n",
    )
    commit(repo, "other adds 088")
    git(repo, "checkout", "-q", "main")
    assert run(repo, "iss").stdout.strip() == "ISS-089"


def test_an_id_only_cited_in_the_append_only_ledger_is_seen(repo: Path) -> None:
    write(repo, LEDGER, "row 76 addendum cites ISS-090 and ISS-088.\n")
    commit(repo, "ledger cites 090")
    assert run(repo, "iss").stdout.strip() == "ISS-091"


def test_an_id_only_in_an_uncommitted_worktree_is_seen(repo: Path, tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "wtb", str(wt))
    write(wt, REGISTER, "#### ISS-001 — one\n#### ISS-087 — build\n#### ISS-095 — uncommitted\n")
    assert run(repo, "iss").stdout.strip() == "ISS-096"


def test_a_lettered_suffix_does_not_raise_the_number(repo: Path) -> None:
    write(repo, REGISTER, "#### ISS-001 — one\n#### ISS-087 — build\n#### ISS-087b — collision\n")
    commit(repo, "suffix")
    assert run(repo, "iss").stdout.strip() == "ISS-088"


def test_next_errata_number_is_highest_plus_one(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "other")
    write(repo, ERR16, "**E29. a.**\n\n**E124. b.**\n\n**E126. c.**\n")
    commit(repo, "other adds E126")
    git(repo, "checkout", "-q", "main")
    assert run(repo, "e").stdout.strip() == "E127"


def test_suffix_mode_names_the_first_free_letter(repo: Path) -> None:
    write(repo, REGISTER, "#### ISS-088 — a\n#### ISS-088b — b\n")
    commit(repo, "suffixes")
    out = run(repo, "iss", "--suffix-of", "ISS-088")
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ISS-088c"


def test_a_repo_with_no_ids_starts_at_one(tmp_path: Path) -> None:
    r = tmp_path / "empty"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    write(r, "README.md", "x\n")
    commit(r, "x")
    assert run(r, "iss").stdout.strip() == "ISS-001"


def test_where_lists_every_source_of_the_highest_id(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "other")
    write(repo, REGISTER, "#### ISS-001 — one\n#### ISS-087 — build\n#### ISS-088 — elsewhere\n")
    commit(repo, "other adds 088")
    git(repo, "checkout", "-q", "main")
    out = run(repo, "iss", "--where")
    assert out.returncode == 0, out.stderr
    assert "ISS-088" in out.stdout and "other" in out.stdout
