"""O1.9 (D12) box 4: ``rollback.yml`` is deleted — the owner's ruling, 2026-10-08.

The file looked like an automated rollback and was a bug reporter with a
misleading name, read from ``origin/main``'s copy of it this turn:

* it fires on ``workflow_run: workflows: ['Deploy'] / types: [completed]`` with
  ``evaluate-rollback`` gated on ``conclusion == 'failure'`` — so it fires on
  every red ``Deploy``, and until this package ``Deploy`` was red on every push
  because the smoke test asserted a contract the CI stack cannot satisfy (D12);
* its ``rollback`` job is named "Rollback to Stable Images" and runs no ``docker
  tag``, no ``docker push`` and no redeploy — grepping main's copy for any of
  those returns nothing but output-variable plumbing. Its own step admits it
  (``rollback.yml:116``): ``# In a real scenario with auto-scaling groups or
  Kubernetes, you would update the deployment config here``;
* its cost was an "Automated Rollback" incident issue per red deploy: **56 open**
  when this package's evidence was captured, newest #6882 ("Deployment failed
  for 36c1a1a", 2026-10-08T06:54:59Z) — filed while this package was in flight,
  by a Deploy whose only red job was the health check this PR fixes.

(Earlier drafts of this file also cited a ``rollback-summary`` ``needs:`` bug
that printed "ROLLBACK NOT NEEDED" beside a real rollback decision. That bug is
real — main's own comment at the job records it, measured at commit 85673029,
and ``test_workflow_needs_declared.py`` guards it — but main fixed it before
this package started: the job has ``needs: evaluate-rollback`` now. It is not a
reason for the deletion, so it is not claimed as one.)

The owner's ruling (#6854 comment ``6051919463``, 2026-10-08T04:01:24Z, quoted
in #6875's coordinator comment ``6052031466`` of 2026-10-08T04:11:11Z, for
UR-29):

> **O1.9's Batch 3 question: (a), delete ``rollback.yml``.** A red ``Deploy``
> run is the signal, and the daily batch reports it.

This guard pins the deletion so the file cannot come back as a "helpful"
addition, and keeps the companion test (``test_rollback_workflow_permissions.py``,
which tested the deleted file's permission scoping) from orphaning. The red
``Deploy`` run itself is now the signal; the daily batch reports it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
ROLLBACK_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "rollback.yml"
ROLLBACK_TEST = (
    REPO_ROOT / "backend" / "tests" / "unit" / "scripts" / ("test_rollback_workflow_permissions.py")
)


def test_the_rollback_workflow_is_deleted() -> None:
    assert not ROLLBACK_WORKFLOW.exists(), (
        ".github/workflows/rollback.yml is back. It files an incident issue per "
        "red deploy and rolls nothing back (no docker tag/push anywhere in it); "
        "the owner ruled it deleted on 2026-10-08 — a red Deploy is the signal"
    )


def test_the_companion_permission_test_is_deleted_too() -> None:
    """A test for a deleted workflow is a test that can never fail again."""
    assert not ROLLBACK_TEST.exists(), (
        "test_rollback_workflow_permissions.py still tests a workflow that no "
        "longer exists — green coverage of nothing"
    )


def test_no_deploy_reactor_opens_github_issues() -> None:
    """The incident-issuer is gone; nothing else may take its place silently.

    ``workflow_run`` consumers of ``Deploy`` remain legitimate —
    linear-ci-status.yml syncs Linear state on completion for both conclusions.
    What must not return is a job that FILES A GITHUB ISSUE because a deploy went
    red: the owner's ruling moves failure reporting to the daily batch. Parsed:
    each workflow's ``on.workflow_run.workflows`` list decides whether it reacts
    to Deploy at all; its ``run:`` steps decide whether it files issues.
    """
    offenders = []
    for path in sorted((REPO_ROOT / ".github" / "workflows").glob("*.y*ml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        # YAML 1.1 reads the bare key `on` as True, so check both spellings.
        on = doc.get("on") if "on" in doc else doc.get(True)
        if not isinstance(on, dict):
            continue
        run_trigger = on.get("workflow_run")
        if not isinstance(run_trigger, dict):
            continue
        reacts_to_deploy = "Deploy" in [str(n) for n in (run_trigger.get("workflows") or [])]
        if not reacts_to_deploy:
            continue
        files_issues = []
        for job in (doc.get("jobs") or {}).values():
            for step in (job.get("steps") or []) if isinstance(job, dict) else []:
                uses = str(step.get("uses") or "")
                script = str((step.get("with") or {}).get("script") or "")
                run = str(step.get("run") or "")
                if uses.startswith("actions/github-script@") and "issues.create" in script:
                    files_issues.append(str(step.get("name") or "github-script"))
                elif "gh issue create" in run:
                    files_issues.append(str(step.get("name") or "gh issue create"))
        if files_issues:
            offenders.append(f"{path.name}: {files_issues}")
    assert not offenders, (
        f"workflows that react to a Deploy run and file GitHub issues — the "
        f"owner's ruling puts that in the daily batch: {offenders}"
    )
