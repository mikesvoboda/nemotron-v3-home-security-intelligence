"""Main-green slice 3: the rollback job must be ALLOWED to file its issue.

``Rollback to Stable Images`` goes red on top of every Deploy-tier red —
it fires on ``workflow_run: Deploy [completed]`` at ``.github/workflows/
rollback.yml:4-8`` whenever the deploy conclusion is ``failure`` — and its
own failure is a permission, measured in the job's log at ``67ca4870``
(run ``36774735698``, job ``110090308559``): step 8 ``Create rollback
issue`` → ``HttpError`` with ``status: 403`` and ``message: 'Resource not
accessible by integration'``, the documentation URL pointing at
``rest/issues/issues#create-an-issue``. Steps 1-7 all succeeded: this is
not the registry, not the checkout, not the report upload.

The job block declares ``permissions: contents: read, packages: read``
and nothing else, while its last step calls ``github.rest.issues.create``
with the default ``GITHUB_TOKEN``. Without ``issues: write`` the token
cannot create an issue, so the incident record the workflow exists to
produce is NEVER created — on top of the red check-run. (The gate itself
was correct as read: deploy run ``36774195879`` genuinely failed after
``merge-core`` had already pushed the new ``:latest``, so deciding to
roll back is the semantically right call; the job is documentary — it
files an issue and uploads a report, it does not repoint tags.)

Fixing slices 1+2 (compose bootable, sign by digest) stops this workflow
FIRING on green deploys; this permission fix stops it FAILING when it
legitimately fires for a deploy that really is broken.

The guard parses the workflow rather than grepping it and was SEEN RED at
main tip (1 failed) before the rollback.yml edit.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "rollback.yml"


@pytest.fixture(scope="module")
def jobs() -> dict:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]


def _calls_issue_api(job: dict) -> bool:
    """True if any step of the job asks the Issues API of anything."""
    for step in job.get("steps") or []:
        text = str(step.get("with") or "") + str(step.get("run") or "")
        if "issues.create" in text or "github.rest.issues" in text:
            return True
    return False


def test_issue_filing_job_has_issues_write(jobs: dict) -> None:
    """Any job that files an issue must declare ``issues: write``.

    Measured red at 67ca4870: the job ran with contents/packages read
    only and the issues.create call died 403 'Resource not accessible by
    integration' — the automated-rollback incident issue has therefore
    never once been created by this workflow.
    """
    offenders = sorted(
        job_id
        for job_id, job in jobs.items()
        if _calls_issue_api(job)
        and (job.get("permissions") or {}).get("issues") != "write"
    )
    assert not offenders, (
        f"jobs call the Issues API without issues: write, so GITHUB_TOKEN "
        f"gets 403 Resource not accessible by integration: {offenders}"
    )
