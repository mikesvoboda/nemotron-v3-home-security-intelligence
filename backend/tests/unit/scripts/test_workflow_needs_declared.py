"""Main-green slice 9: a job that reads ``needs.X`` MUST declare ``needs: X``.

Measured at main tip ``85673029`` (row 69): the rollback chain FIRED —
``Evaluate Rollback Need`` job ``110356356205`` logged ``Detection: smoke-test
job failed`` and set ``should-rollback=true``; its sibling created issue
``#6755``. Yet ``Rollback Summary`` job ``110356356754`` printed
``Status: ROLLBACK NOT NEEDED``. Both prints are in the fetched job logs and
both describe the SAME run — so one of them is fabricated evidence, and CI
cannot tell readers which.

The mechanism is in ``.github/workflows/rollback.yml`` AT THAT REF: the
``rollback-summary`` job (line 293) declares NO ``needs:`` — only
``if: always()`` — while line 306 branches on
``${{ needs.evaluate-rollback.outputs.should-rollback }}``. GitHub resolves
``needs`` only from the declared ``needs:`` map, so the expression expands to
the EMPTY string, ``[ "" == "true" ]`` is false, and the summary prints
``ROLLBACK NOT NEEDED`` for EVERY run of this workflow, forever — including
the runs where a rollback WAS decided. This is exactly the failure class
``main-green`` exists to remove: not a red check-run, a GREEN job that states
something false.

The guard parses every workflow and cross-checks each job's ``needs.<job>``
references against its declared ``needs:`` (string, list, or mapping form —
the mapping form is ``{job: condition}``). A reference to the job's own id is
fine (``needs.<self>.outputs`` never resolves either, but no workflow here
does that; the guard allows it so a future self-reference is not this rule's
problem). It was SEEN RED before the fix: rollback.yml's rollback-summary was
the one violation across every workflow in the repo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")) + sorted(
    (REPO_ROOT / ".github" / "workflows").glob("*.yaml")
)
NEEDS_REF = re.compile(r"needs\.([A-Za-z0-9_][A-Za-z0-9_-]*)")


def _declared_needs(job: dict) -> set[str]:
    """Ids declared in the job's ``needs:`` — all three accepted forms."""
    needs = job.get("needs")
    if isinstance(needs, str):
        return {needs}
    if isinstance(needs, list):
        return set(needs)
    if isinstance(needs, dict):  # needs: {job: condition}
        return set(needs)
    return set()


@pytest.mark.parametrize("workflow_path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_jobs_declare_every_needs_reference(workflow_path: Path) -> None:
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    jobs = workflow.get("jobs") or {}
    offenders: list[str] = []
    for job_id, job in sorted(jobs.items()):
        if not isinstance(job, dict):
            continue
        declared = _declared_needs(job)
        referenced = set(NEEDS_REF.findall(yaml.dump(job)))
        undeclared = sorted(referenced - declared - {job_id})
        if undeclared:
            offenders.append(f"{job_id} references {undeclared} but declares {sorted(declared)}")
    assert not offenders, (
        f"{workflow_path.name}: jobs reading needs.X without declaring needs: X render "
        f"those expressions as empty — CI then PRINTS A FALSE VERDICT "
        f"(rollback.yml's summary printed 'ROLLBACK NOT NEEDED' on a run whose "
        f"sibling job set should-rollback=true and filed issue #6755): {offenders}"
    )
