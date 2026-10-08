"""O1.9 (D12) box 3 (MEASURE): a job that deploys or validates nothing, and only prints a checklist, goes.

The plan asked for a measurement, not an opinion, so both jobs were measured at
run ``37726762316`` (head ``acfe5b56``, 2026-10-08) job-by-job — the run's only
failure was ``Smoke Test Deployment``:

* ``Deploy to Staging`` — **success**. Its steps are
  ``echo "Staging Deployment Instructions" … "NOTE: This is a manual deployment
  step."`` and an echo of an eight-box checklist. It deploys nothing: its
  ``environment:`` points at ``http://staging.example.com # Update with actual
  staging URL``. Its one real action is uploading
  ``docs/DEPLOYMENT_VERIFICATION_CHECKLIST.md``, a file that does not exist
  (``ls: cannot access 'docs/DEPLOYMENT_VERIFICATION_CHECKLIST.md'``) — and
  because ``actions/upload-artifact`` defaults to ``if-no-files-found: warn``,
  the step still reported success. A green step that documents a phantom is
  worse than a red one: it is the reason nobody noticed for nine months.
* ``Post-Deployment Validation`` — **skipped** (``if: success()`` on the red
  smoke test, so on every push since January it has not even run). Its body is
  an echo of a deployment-strategy essay plus a ``canary-readiness.txt`` heredoc
  it then uploads. It validates nothing.

Both print checklists. Both go, per the plan's own wording. The general guard
below is the phantom-artifact one, because that is the failure class worth
keeping: an artifact upload that finds no files must not silently succeed. It
was SEEN RED against ``acfe5b56`` (the checklist path is the offender) and stays
green afterwards.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"

# Measured to deploy/validate nothing; see the docstring for both reads.
CHECKLIST_ONLY_JOBS = {"staging-deployment", "post-deployment-validation"}


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def jobs(workflow: dict) -> dict:
    return workflow["jobs"]


def test_the_checklist_only_jobs_are_gone(jobs: dict) -> None:
    assert not (CHECKLIST_ONLY_JOBS & set(jobs)), (
        f"deploy.yml still carries the print-only jobs: {sorted(CHECKLIST_ONLY_JOBS & set(jobs))} "
        "— 'a job that deploys or validates nothing and only prints a checklist goes'"
    )


def test_no_environment_points_at_a_placeholder_url(jobs: dict) -> None:
    """A GitHub ``environment:`` is a real deployment record; ``example.com`` is not.

    Recorded deployments make the environment tab look like a deploy log, so a
    placeholder URL manufactures evidence of deploys that never happened.
    """
    offenders = {
        job_id: str((job.get("environment") or {}).get("url"))
        for job_id, job in jobs.items()
        if job.get("environment")
        and re.search(r"example\.(com|org)|TODO|changeme", str(job.get("environment") or {}))
    }
    assert not offenders, f"jobs declare environments that name a placeholder URL: {offenders}"


def test_every_uploaded_artifact_is_a_file_the_job_produces(jobs: dict) -> None:
    """``upload-artifact`` defaults to ``warn``, so a missing file scores green.

    ``Deploy to Staging`` "documented" ``docs/DEPLOYMENT_VERIFICATION_CHECKLIST.md``
    for months and never once existed. This guard makes the same shape
    unmissable: every artifact path deploy.yml uploads must either exist in the
    tree or be written by an earlier step of the SAME job.
    """
    offenders: list[str] = []
    for job_id, job in jobs.items():
        steps = job.get("steps") or []
        for index, step in enumerate(steps):
            if not str(step.get("uses") or "").startswith("actions/upload-artifact@"):
                continue
            raw = str((step.get("with") or {}).get("path") or "")
            for line in raw.splitlines():
                path = line.strip()
                if not path or "*" in path or path.startswith("/tmp/"):  # noqa: S108
                    continue  # globs and scratch dirs are not doc-phantoms
                if (REPO_ROOT / path).exists():
                    continue
                earlier = "\n".join(str(s.get("run") or "") for s in steps[:index])
                earlier += "\n" + yaml.dump([steps[i].get("with") for i in range(index)])
                if Path(path).name in earlier:
                    continue  # produced by a step above (heredoc, sbom output-file)
                offenders.append(f"{job_id}: {path}")
    assert not offenders, (
        "upload-artifact found no files for these paths and only WARNED, so the "
        f"job still passed: {offenders}"
    )


def test_the_deployment_essay_lives_in_docs_not_in_a_workflow(jobs: dict) -> None:
    """Deployment-strategy prose belongs in docs/, where it can be edited and cited.

    Pinning the deleted job's content: if it returns as an echo, put it in a
    document instead (D5: docs are the home for this material).
    """
    body = yaml.dump(jobs)
    assert "BLUE-GREEN DEPLOYMENT" not in body, (
        "the deployment-strategy essay is back inside deploy.yml"
    )
