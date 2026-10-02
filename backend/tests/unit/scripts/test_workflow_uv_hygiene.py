"""Main-green slice 10 (class F): a job whose `uv` setup cannot work does not
fail loudly where the bug is — it fails at install, and its whole history then
reads as "the feature itself is red".

Measured for row 69 at main tip ``85673029``: ``Sync Linear to GitHub Issues``
(job ``110355742227``, run ``36858225577``) died in Install-dependencies with
``error: The interpreter at /usr is externally managed`` exit 2 — ``uv pip
install --system`` (``.github/workflows/linear-github-sync.yml:146`` at that
ref) pointed at the runner's Debian-managed ``/usr`` Python, which refuses
system installs (PEP 668). Its recorded history is ALL failure: 188 of the
190 runs of workflow ``220886700`` GitHub still lists (Jan 6 → Oct 1) ended
``failure`` — and the only two successes, Jan 6 and 7, ran the PREVIOUS shape
of this step (``pip install httpx`` under ``setup-python``, read at
``7770606c``). The first failure is ``2026-01-08T06:24Z``, whose ``head_sha``
is ``ade184b4`` — the very commit that introduced ``uv pip install --system``.
So nobody could tell whether the SYNC ever ran, and it never has: the install
step killed the job first, for nine months, on every event.

What correct looks like HERE is measured, not assumed:
- every workflow that runs ``uv sync`` invokes project-dependency scripts as
  ``uv run python scripts/...`` — ci.yml alone at ``:98``, ``:130``, ``:159``,
  ``:207``, ``:233``, ``:241``, ``:1580``, ``:1583``, ``:1589``, ``:2649`` —
  because ``uv sync`` builds ``.venv/`` and a bare ``python`` silently bypasses
  it;
- SEVEN sibling jobs do run bare ``python3`` in a uv job today
  (api-contract:contract-tests, ci-analytics:check-alerts, ci:flake-report,
  flaky-test-detection:analyze-flaky-tests, test-coverage-gate x2,
  weekly-test-report:weekly-report). Each was measured, not excused: every one
  imports ONLY stdlib (AST over the real file/heredoc text), so bypassing
  ``.venv`` cannot break it. Guard 2 is therefore dependency-aware — flagging
  those 7 would be a guard that cries wolf, and a wolf-guard trains everyone
  to ignore the wolf. If one of them ever grows a third-party import, this
  guard starts failing on it, which is the correct time to care;
- of the 16 workflow files that pin ``PYTHON_VERSION`` for a uv job, 41 uv
  jobs say ``3.14``; the ONE outlier said ``3.12`` while root
  ``pyproject.toml:5`` requires ``>=3.14`` — a lower pin cannot even load the
  tree's own lock.

Red-first at ``8ac34ac2`` (main tip ``87613120``): 3 failed, all three in
``linear-github-sync.yml:sync-issues`` — ``--system``, bare ``python`` on a
script that ``import httpx``, and the 3.12 pin — and the sweep says this class
is exactly that one job. After the fix: 0 violations, 0 failures.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")) + sorted(
    (REPO_ROOT / ".github" / "workflows").glob("*.yaml")
)
# Settled pin for uv jobs (measured pre-fix: of 42 pinned uv jobs, 41 said
# 3.14 and one said 3.12) and the floor of the root project itself:
# pyproject.toml:5 requires >=3.14.
UV_PYTHON_PIN = "3.14"
# Command position: optional VAR=value prefixes, then the executable token.
COMMAND_POSITION = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*(python(?:3(?:\.\d+)?)?)\b(.*)$")
UV_COMMAND = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*uv\b")
HEREDOC_TAG = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")


def _step_run(step: object) -> str:
    """A step's shell text, tolerating the string-shorthand step form."""
    if isinstance(step, str):
        return step
    if isinstance(step, dict):
        return str(step.get("run") or "")
    return ""


def _third_party_imports(source: str) -> list[str]:
    """Top-level import roots not in the running interpreter's stdlib."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ["<unparseable>"]
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            candidates = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import: part of the package being run
                continue
            candidates = [(node.module or "").split(".")[0]]
        else:
            continue
        for root in candidates:
            if root and root not in sys.stdlib_module_names:
                roots.add(root)
    return sorted(roots)


def _resolve_script(rest: str, job: dict, step: object) -> str | None:
    """Source text of the .py the invocation names; None if it names no .py."""
    tokens = rest.split()
    if not tokens:
        return None
    name = tokens[0].removeprefix("./")
    if not name.endswith(".py"):
        return None
    dirs = [REPO_ROOT]
    job_defaults = job.get("defaults")
    if isinstance(job_defaults, dict) and isinstance(job_defaults.get("run"), dict):
        wd = job_defaults["run"].get("working-directory")
        if isinstance(wd, str):
            dirs.insert(0, REPO_ROOT / wd)
    if isinstance(step, dict) and isinstance(step.get("working-directory"), str):
        dirs.insert(0, REPO_ROOT / step["working-directory"])
    for d in dirs:
        candidate = d / name
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="replace")
    return "<missing file>"  # a .py the repo does not have: still a finding


def _bare_python_needing_project_deps(run_text: str, job: dict, step: object) -> list[str]:
    """Bare-python invocations whose code imports something only .venv has."""
    findings: list[str] = []
    lines = run_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#") or "uv run" in line or line.startswith("uvx"):
            continue
        match = COMMAND_POSITION.match(line)
        if not match:
            continue
        rest = match.group(2)
        heredoc = HEREDOC_TAG.search(rest)
        if heredoc:
            tag = heredoc.group(1)
            body = []
            while i < len(lines) and lines[i].strip() != tag:
                body.append(lines[i])
                i += 1
            deps = _third_party_imports("\n".join(body))
            if deps:
                findings.append(f"heredoc <<{tag} imports {deps}")
            continue
        source = _resolve_script(rest, job, step)
        if source is None:
            continue
        deps = _third_party_imports(source)
        if deps:
            findings.append(f"{rest.strip()[:60]} imports {deps}")
    return findings


def _job_steps(job: dict) -> list[object]:
    steps = job.get("steps")
    return steps if isinstance(steps, list) else []


def _uses_uv(job: dict) -> bool:
    """A job provisions uv either via setup-uv or by running the uv binary."""
    for step in _job_steps(job):
        if isinstance(step, dict) and "setup-uv" in str(step.get("uses") or ""):
            return True
        for raw in _step_run(step).splitlines():
            if UV_COMMAND.match(raw.strip()):
                return True
    return False


@pytest.fixture(scope="module")
def workflow_jobs() -> list[tuple[Path, str, dict, dict]]:
    out: list[tuple[Path, str, dict, dict]] = []
    for path in WORKFLOWS:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        workflow_env = doc.get("env") if isinstance(doc.get("env"), dict) else {}
        jobs = doc.get("jobs") or {}
        out.extend(
            (path, job_id, job, workflow_env)
            for job_id, job in sorted(jobs.items())
            if isinstance(job, dict)
        )
    return out


def test_no_workflow_installs_into_the_runner_system_python(
    workflow_jobs: list[tuple[Path, str, dict, dict]],
) -> None:
    """``uv pip install --system`` targets /usr, which the runner refuses (PEP 668)."""
    offenders = sorted(
        f"{path.name}:{job_id}"
        for path, job_id, job, _ in workflow_jobs
        if "uv pip install --system" in "\n".join(_step_run(s) for s in _job_steps(job))
    )
    assert not offenders, (
        "jobs install with `uv pip install --system`, which dies on the runner's "
        "externally-managed /usr interpreter (measured: 188 of workflow "
        "220886700's 190 recorded runs failed, and the first failure's head_sha "
        "is the commit that added this pattern — the audit step never executed "
        f"in any of them): {offenders}"
    )


def test_uv_jobs_run_dependency_needing_scripts_through_uv(
    workflow_jobs: list[tuple[Path, str, dict, dict]],
) -> None:
    """After `uv sync` the env lives in .venv — bare python cannot see project deps."""
    offenders: list[str] = []
    for path, job_id, job, _ in workflow_jobs:
        if not _uses_uv(job):
            continue
        hits: list[str] = []
        for step in _job_steps(job):
            hits.extend(_bare_python_needing_project_deps(_step_run(step), job, step))
        if hits:
            offenders.append(f"{path.name}:{job_id} -> {hits}")
    assert not offenders, (
        "uv jobs run code that imports non-stdlib packages with a bare python at "
        "the command position — that interpreter is not .venv, so the import "
        "fails; the sibling pattern in ci.yml is `uv run python scripts/...` "
        "(:98,:130,:159,:207,:233,:241,:1580,:1583,:1589,:2649). Stdlib-only "
        "bare python is NOT flagged (measured clean in 7 sibling jobs): "
        f"{offenders}"
    )


def test_uv_jobs_agree_on_the_python_pin(workflow_jobs: list[tuple[Path, str, dict, dict]]) -> None:
    """A uv job whose env pins PYTHON_VERSION must pin what the tree requires."""
    offenders: list[str] = []
    for path, job_id, job, workflow_env in workflow_jobs:
        if not _uses_uv(job):
            continue
        job_env = job.get("env") if isinstance(job.get("env"), dict) else {}
        pin = job_env.get("PYTHON_VERSION", workflow_env.get("PYTHON_VERSION"))
        if pin is not None and str(pin).strip("'\"") != UV_PYTHON_PIN:
            offenders.append(f"{path.name}:{job_id} pins {pin}")
    assert not offenders, (
        f"uv jobs pinning a python other than {UV_PYTHON_PIN}: pyproject.toml:5 "
        f"requires >=3.14 and the other 41 uv jobs (across the other 15 "
        f"pinning files) already say {UV_PYTHON_PIN}; a lower pin guarantees "
        f"drift from uv.lock: {offenders}"
    )
