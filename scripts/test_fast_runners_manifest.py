"""Tests for the manifest contract on both fast-tier runners (WP2.3).

Spec §Phase 2, "Output contract, non-negotiable": every run emits a manifest
distinguishing **not selected for this diff** (normal, visible) from **cannot
run** (defect, non-zero exit). "If those two states ever render alike, this
design has rebuilt the trap the revival escaped."

Test seam: both runners honor PYTEST_CMD / VITEST_CMD overrides (default = the
real invocations), so these tests drive FAKE runners that emit canned pytest/
vitest output and exit codes. What is under test is the runners' MANIFEST and
EXIT-CODE behavior — not pytest itself. The fakes emit shapes calibrated
against real pytest 8 / vitest 4 output (see the anchors inline).

Run explicitly (scripts/ is outside testpaths, same as test_fast_select.py):
    uv run pytest scripts/test_fast_runners_manifest.py -v -p no:randomly -o addopts=""
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND_RUNNER = REPO / "scripts" / "fast-backend-runner.sh"
FRONTEND_RUNNER = REPO / "scripts" / "fast-frontend-runner.sh"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def make_repo(tmp_path: Path) -> Path:
    """Synthetic repo shaped like the real one, with a base commit."""
    run = lambda *a, **k: subprocess.run(  # noqa: E731
        a, cwd=tmp_path, check=True, capture_output=True, text=True, **k
    )
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    for d in ("backend/tests/unit", "backend/tests/contracts", "frontend/src"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / "backend/tests/unit/test_a.py").write_text("def test_a(): pass\n")
    (tmp_path / "backend/tests/unit/test_b.py").write_text("def test_b(): pass\n")
    (tmp_path / "backend/tests/unit/test_c.py").write_text("def test_c(): pass\n")
    (tmp_path / "frontend/src/a.test.ts").write_text("it('a', () => {})\n")
    (tmp_path / "frontend/src/b.test.ts").write_text("it('b', () => {})\n")
    (tmp_path / "frontend/package.json").write_text('{"name":"f"}\n')
    run("git", "add", "-A")
    run("git", "commit", "-qm", "base")
    return tmp_path


def write_fake(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text("#!/bin/sh\n" + body)
    p.chmod(0o755)
    return p


def run_backend(repo: Path, listfile: Path, fake: Path, env_extra: dict | None = None):
    env = dict(os.environ, PYTEST_CMD=str(fake))
    env.update(env_extra or {})
    return subprocess.run(
        ["sh", str(BACKEND_RUNNER), str(listfile)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def manifest_lines(r) -> list[str]:
    return [ln for ln in r.stdout.splitlines() if ln.startswith("MANIFEST")]


# --------------------------------------------------------------------------
# backend runner
# --------------------------------------------------------------------------
def test_backend_manifest_distinguishes_unselected_from_cannot_run(tmp_path):
    """THE contract, both names, one run: test_c.py was not selected (normal)
    while test_b.py cannot run (defect, non-zero)."""
    repo = make_repo(tmp_path)
    (tmp_path / "sel.txt").write_text(
        "backend/tests/unit/test_a.py\nbackend/tests/unit/test_b.py\n"
    )
    # fake pytest: a passes; b ERRORS at collection (shape: real pytest 8
    # prints 'ERROR <file> - <exc>' summary lines and exits 2 on collection
    # errors when --continue-on-collection-errors is not set).
    fake = write_fake(
        tmp_path,
        "fakepytest",
        """
echo "1 passed"
echo "ERROR backend/tests/unit/test_b.py - ImportError: boom"
exit 2
""",
    )
    r = run_backend(repo, tmp_path / "sel.txt", fake)
    m = manifest_lines(r)
    joined = "\n".join(m)
    assert r.returncode != 0, "a selected file that cannot run must exit non-zero"
    assert "MANIFEST CANNOT-RUN" in joined, m
    assert "test_b.py" in joined, m
    # the unselected file is NAMED, under a DIFFERENT name
    assert "NOT-SELECTED" in joined, m
    assert "test_c.py" in joined, m
    assert "MANIFEST CANNOT-RUN: backend/tests/unit/test_c.py" not in joined, m


def test_backend_healthy_run_exits_zero_and_shows_not_selected(tmp_path):
    """A merely-unselected file must not fail the run — and must still be
    visible in the manifest (that visibility is what the spec demands)."""
    repo = make_repo(tmp_path)
    (tmp_path / "sel.txt").write_text("backend/tests/unit/test_a.py\n")
    fake = write_fake(
        tmp_path,
        "fakepytest",
        """
echo "1 passed"
exit 0
""",
    )
    r = run_backend(repo, tmp_path / "sel.txt", fake)
    m = "\n".join(manifest_lines(r))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NOT-SELECTED" in m
    assert "test_c.py" in m and "test_b.py" in m
    assert "CANNOT-RUN" not in m


def test_backend_zero_test_selected_file_is_cannot_run(tmp_path):
    """Spec: 'zero-test files are the second category and must exit
    non-zero.' A selected file that contributes no tests is drift (the map
    points at nothing), not silence."""
    repo = make_repo(tmp_path)
    (tmp_path / "sel.txt").write_text("backend/tests/unit/test_a.py\n")
    # fake pytest reports the file collected but ran zero tests (rc 5 when it
    # is ALL that was asked for — the shape pytest emits for 'no tests ran').
    fake = write_fake(
        tmp_path,
        "fakepytest",
        """
echo "no tests ran in 0.01s"
exit 5
""",
    )
    r = run_backend(repo, tmp_path / "sel.txt", fake)
    m = "\n".join(manifest_lines(r))
    assert r.returncode != 0
    assert "CANNOT-RUN" in m and "test_a.py" in m


def test_backend_empty_selection_is_green_with_full_not_selected(tmp_path):
    """Nothing affected is NORMAL: exit 0, manifest still names everything."""
    repo = make_repo(tmp_path)
    (tmp_path / "sel.txt").write_text("")
    fake = write_fake(tmp_path, "fakepytest", "exit 0\n")
    r = run_backend(repo, tmp_path / "sel.txt", fake)
    m = "\n".join(manifest_lines(r))
    assert r.returncode == 0
    assert "SELECTED: 0" in m
    assert all(f in m for f in ("test_a.py", "test_b.py", "test_c.py"))


def test_backend_genuine_failure_not_relabelled_cannot_run(tmp_path):
    """A plain test FAILURE (rc 1, no ERROR lines) is a different category
    from cannot-run — the manifest must name it as failing tests, and the
    exit stays non-zero either way (this guards against the relabel being
    merely cosmetic on the exit side too)."""
    repo = make_repo(tmp_path)
    (tmp_path / "sel.txt").write_text("backend/tests/unit/test_a.py\n")
    fake = write_fake(
        tmp_path,
        "fakepytest",
        """
echo "FAILED backend/tests/unit/test_a.py::test_a - assert 1 == 2"
exit 1
""",
    )
    r = run_backend(repo, tmp_path / "sel.txt", fake)
    m = "\n".join(manifest_lines(r))
    assert r.returncode != 0
    assert "CANNOT-RUN" not in m
    assert "FAILED" in r.stdout or "FAILING" in m


# --------------------------------------------------------------------------
# frontend runner
# --------------------------------------------------------------------------
def run_frontend(repo: Path, fake: Path, base: str = "HEAD"):
    env = dict(os.environ, VITEST_CMD=str(fake))
    return subprocess.run(
        ["sh", str(FRONTEND_RUNNER), base],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def touch_frontend_source(repo: Path, rel="src/widget.ts"):
    p = repo / "frontend" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("export const w = 1\n")
    subprocess.run(["git", "add", "--", f"frontend/{rel}"], cwd=repo, check=True)


def test_frontend_manifest_names_unselected_and_fails_on_uncollectable(tmp_path):
    repo = make_repo(tmp_path)
    touch_frontend_source(repo)
    # fake vitest: crashed run (uncollectable file) → rc 1 with a stderr shape
    fake = write_fake(
        tmp_path,
        "fakevitest",
        """
echo "Error: Failed to parse dynamic import argument" 1>&2
exit 1
""",
    )
    r = run_frontend(repo, fake)
    m = "\n".join(manifest_lines(r))
    assert r.returncode != 0
    assert "CANNOT-RUN" in m, m
    # the two categories may never render together: a crash is not also
    # "normal zero-selection" (a live probe once printed both lines)
    assert "ZERO-RELATED" not in m, m
    # unselected-but-visible: the other test file named under NOT-SELECTED
    assert "NOT-SELECTED" in m and "b.test.ts" in m, m


def test_frontend_green_run_zero_related_is_not_cannot_run(tmp_path):
    """Zero related tests for a real source change is NOT a crash — vitest
    exits 0 having run nothing. Under the contract the manifest must still
    say WHY (zero related), and the run is green (vitest semantics), with
    everything named NOT-SELECTED."""
    repo = make_repo(tmp_path)
    touch_frontend_source(repo)
    fake = write_fake(
        tmp_path,
        "fakevitest",
        """
echo "Test Files  0 passed (0)"
exit 0
""",
    )
    r = run_frontend(repo, fake)
    m = "\n".join(manifest_lines(r))
    assert r.returncode == 0
    assert "NOT-SELECTED" in m
    assert "CANNOT-RUN" not in m
    assert "ZERO-RELATED" in m, "a green zero-run must be NAMED, not silence"
