"""`[r149f]`: Flaky Test Detection reports to its run summary (ruling 149 follow-up).

The package, verbatim from ``docs/uplevel/packages/ops.md``:385-388:

    Remove the issue-creation step from `.github/workflows/flaky-test-detection.yml`; the
    Analyze Flaky Tests job writes its flaky list (test id, pass/fail count over the runs) to
    the run summary instead, and goes green when the analysis itself succeeds. The coordinator
    routes the list (UR-116).

**Done when:** a ``workflow_dispatch`` run's Analyze job is green and its summary lists the
flaky tests.

Why the issue step goes. ``Create issue for new flaky tests`` is an ``actions/github-script``
step that files a GitHub issue from a SCHEDULED (cron) job. UR-116 puts flaky routing with the
coordinator, so this workflow should PUBLISH its findings, not file tickets — a cron opening
issues competes with the coordinator over one list. The findings belong in the run summary.

**What was already true before this package (measured, so the pins stay honest).** The Analyze
job's summary is written by ``scripts/analyze-flaky-tests.py``'s ``write_github_summary``, which
``main`` calls unconditionally, and ``main`` always returns 0 (its own comment: "Return 0 to not
fail CI"). So the job already goes green and already lists the flaky tests by id. This package
therefore is NOT "make it green" and NOT "add a summary from nothing"; the two things it does
ask for and that are not yet true are (a) the issue step is still there, and (b) the summary
prints a Pass Rate and a total-run count but not the pass/fail COUNTS the parenthetical names
(the per-test ``passed``/``failed`` exist at ``analyze-flaky-tests.py:199-200`` but no summary
column shows them). The pins below assert exactly those two, nothing more.

**Red-first (UR-69), written before the change** at claim head ``d51c3d23f``:
``test_issue_creation_step_is_gone`` is RED (the github-script step is present) and
``test_the_summary_shows_pass_and_fail_counts`` is RED (the table has no such column). The
survivor pins pass on the current file on purpose — they hold invariants the change must NOT
break, so a change that deletes the analysis or the artifact to "remove the issue step" turns
one red.

**What these pins refuse to over-specify.** Structure and content, not prose. The summary test
calls the real function and asserts the pass and fail numbers appear as numbers (via digit-
boundary lookaround, so ``72%``/``0.78`` cannot fake a count), which lets a reviewer reformat the
table — add columns, rename headers, switch ``2 / 15`` for two cells — without breaking a pin. The
"green" clause is deliberately NOT pinned in YAML: it is already true of the code, and a real
``workflow_dispatch`` run is where the Done-when is finally observed.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "flaky-test-detection.yml"
SCRIPT = REPO_ROOT / "scripts" / "analyze-flaky-tests.py"
ANALYZE_JOB = "analyze-flaky-tests"
ARTIFACT_NAME = "flaky-test-report"


def _doc() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")) or {}


def _steps(job_id: str) -> list[dict]:
    job = (_doc().get("jobs") or {})[job_id]
    return [s for s in (job.get("steps") or []) if isinstance(s, dict)]


def _run(step: dict) -> str:
    return str(step.get("run") or "")


def _uses(step: dict) -> str:
    return str(step.get("uses") or "")


# --- the issue-creation clause -------------------------------------------------


def test_issue_creation_step_is_gone() -> None:
    """No step in the analyze job files a GitHub issue.

    Asserted on the ACTION, not only the name: a renamed ``github-script`` step would still file
    issues, which is what the clause forbids.
    """
    offenders = [
        step.get("name", "<noname>")
        for step in _steps(ANALYZE_JOB)
        if _uses(step).startswith("actions/github-script")
    ]
    assert offenders == [], (
        "the analyze job still opens issues with actions/github-script; [r149f] retires that and "
        "routes the list to the coordinator (UR-116): " + repr(offenders)
    )


# --- the summary-content clause (script level, not a YAML step) ----------------


@pytest.fixture(scope="module")
def analyze_module():
    """Import the hyphenated script by path, the sibling idiom in this directory."""
    spec = importlib.util.spec_from_file_location("analyze_flaky_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_summary_shows_pass_and_fail_counts(
    analyze_module, tmp_path, monkeypatch
) -> None:
    """The run summary lists, per flaky test, the test id AND its pass/fail counts.

    Asserted on the flaky test's TABLE ROW, not the whole summary, and this distinction is the
    whole difficulty of the pin: the same function appends a "Recommended Actions" list whose
    second item begins ``2. Registering the flake …``. A whole-summary search for a standalone
    ``2`` therefore passes TODAY, with no counts anywhere — the prose's numbered list supplies the
    digit. Scoping to the row is what makes the pin mean what it says.

    Within the row, one flaky test has ``passed=2, failed=7, total_runs=15, pass_rate=2/15``, and
    those digits are chosen so today's row — ``| **NEW** | `…test_flips` | 13% | 0.67 | 15 |`` —
    contains neither as a standalone token: ``13%`` has no ``2``/``7`` at all, and ``0.67`` holds a
    ``7`` only inside ``67`` (a digit follows, so the lookahead rejects it). Matched with digit-
    boundary lookaround so a ``72%`` or ``0.78``-style cell can never fake a count. A bare row is
    all that is required: ``2 / 15`` in one cell and two cells (``| 2 | 7 |``) both satisfy it, so
    the pin holds a SHAPE (the numbers are present) rather than my phrasing.
    """
    summary = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    flaky = [
        {
            "nodeid": "backend.tests.unit.test_flaky_mod::test_flips",
            "pass_rate": 2 / 15,
            "total_runs": 15,
            "passed": 2,
            "failed": 7,
            "reruns": 0,
            "flakiness_score": 0.666,
            "run_count": 3,
        }
    ]
    analyze_module.write_github_summary(flaky, quarantined=set())

    text = summary.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if "test_flips" in line]
    assert rows, (
        "the Done-when's 'summary lists the flaky tests': the summary must carry the test id "
        f"(nodeid). Summary was:\n{text}"
    )
    row = "\n".join(rows)
    for label, value in (("pass", "2"), ("fail", "7")):
        assert re.search(rf"(?<!\d){value}(?!\d)", row), (
            f"the package names 'pass/fail count over the runs'; the summary shows a Pass Rate "
            f"and a total-run count but not the {label} count ({value}) on the flaky test's own "
            f"row. (Scoped to the row because the Recommended-Actions prose has a numbered item "
            f"'2.' that would otherwise fake the pass count.) Row was:\n{row}"
        )


# --- the invariants the change must not break ----------------------------------


def test_the_report_artifact_upload_survives() -> None:
    """The summary ADDS a human view; the machine record and its consumer stay.

    ``update-ci-metrics`` downloads ``flaky-test-report``; deleting the upload to "simplify the
    job" would silently starve it. This makes "keep the artifact" a checked claim.
    """
    uploaders = [
        step
        for step in _steps(ANALYZE_JOB)
        if _uses(step).startswith("actions/upload-artifact")
        and (step.get("with") or {}).get("name") == ARTIFACT_NAME
    ]
    assert uploaders, f"the analyze job must still upload the {ARTIFACT_NAME} artifact"

    consumers = [
        step
        for job in (_doc().get("jobs") or {}).values()
        for step in (job.get("steps") or [])
        if isinstance(step, dict)
        and _uses(step).startswith("actions/download-artifact")
        and (step.get("with") or {}).get("name") == ARTIFACT_NAME
    ]
    assert consumers, (
        f"a job must still download {ARTIFACT_NAME} (update-ci-metrics does); an upload with no "
        "consumer, or a consumer with no upload, is a broken hand-off"
    )


def test_the_analysis_command_still_runs_in_the_analyze_job() -> None:
    """Retiring the issue step must not retire the analysis that produces the list."""
    analyzers = [
        step for step in _steps(ANALYZE_JOB) if "scripts/analyze-flaky-tests.py" in _run(step)
    ]
    assert analyzers, "the job must still run scripts/analyze-flaky-tests.py — that is the analysis"
