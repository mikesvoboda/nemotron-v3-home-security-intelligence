"""Main-green slice 11: a step must not conclude "none found" from a Linear error body.

Measured at main tip ``93a45f39`` (row 74). Two jobs of the SAME
``Linear CI Status Sync`` workflow read the SAME ``LINEAR_API_KEY``, and the
logs show opposite outcomes from the SAME dead credential:

- job ``Create Linear Issue on Main CI Failure`` (run ``36898232006``) printed
  ``{"errors":[{"message":"Authentication required, not authenticated", ...
  "statusCode":401 ...}]}`` at 17:17:09 and exited 1. Red, and honest.
- job ``Close Linear Issue on Main CI Success`` (run ``36899341707``) printed
  ``No open CI failure issues found`` at 17:26:09 and exited 0. GREEN, and
  FALSE -- under a 401 the search never ran, so the job cannot know whether a
  CI-failure issue is open.

The mechanism is three lines of ``.github/workflows/linear-ci-status.yml`` in
the ``main-branch-success`` job, reproduced locally at this ref:

    ISSUES=$(echo "$SEARCH_RESULT" | jq -r '.data.issues.nodes')      # line 586
    ISSUE_COUNT=$(echo "$ISSUES" | jq 'length')                        # line 587
    if [ "$ISSUE_COUNT" = "0" ]; then echo "No open CI failure issues found"; exit 0; fi

Feeding it the 401 envelopes produces exactly the observed verdict --
``{"error":...}`` -> ``nodes=null`` -> ``length=0`` -> "No open CI failure
issues found". An error body and a genuinely empty result are
indistinguishable to that comparison, so the job reports ALL CLEAR on every
main push for as long as the credential is invalid, and -- worse -- it will
report all clear on the day a real CI-failure issue IS open, because the
search that would find it failed.

This is the goal's own kind of defect, the one slice 9 exists for: not a red
check-run, a GREEN job that states something false.

The rule is deliberately narrow. A violation needs all three properties: the
step calls ``api.linear.app``, it pulls a LIST (``.data.<x>.nodes``) out of the
response, and it branches on ``jq 'length'`` -- i.e. it concludes from a
count. Before doing that it must prove the extraction is a list (``jq -e 'type
== "array"'``) or inspect ``.errors``. Measured across all 13 workflow files
that call Linear: 32 steps call the API and only THIS ONE concludes an all-clear
from a response count. The other 31 are notification paths that either sit
behind ``if: failure()`` or never print a verdict, so a missing ``.errors``
check there costs a lost ticket, not a false statement about the world -- and a
guard that flagged all 32 would be a guard that cries wolf.
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

CALLS_LINEAR = re.compile(r"api\.linear\.app")
LIST_FROM_RESPONSE = re.compile(r"\.data\.[A-Za-z_][A-Za-z0-9_]*\.nodes\b")
CONCLUDES_FROM_COUNT = re.compile(r"\|\s*jq\s+['\"]length['\"]")
PROVES_THE_LIST = re.compile(r"type\s*==\s*[\"']array[\"']|jq[^|\n]*\.errors")


def _linear_steps(workflow_path: Path) -> list[tuple[str, str, str]]:
    """``(job, step name, run body)`` for every step that calls the Linear API."""
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    steps: list[tuple[str, str, str]] = []
    for job_id, job in sorted((workflow.get("jobs") or {}).items()):
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            run = step.get("run") if isinstance(step, dict) else None
            if isinstance(run, str) and CALLS_LINEAR.search(run):
                steps.append((job_id, str(step.get("name") or "<unnamed>"), run))
    return steps


def _unproved_count_verdicts(steps: list[tuple[str, str, str]]) -> list[str]:
    """Steps that answer a question from a response COUNT they never proved."""
    offenders: list[str] = []
    for job_id, step_name, run in steps:
        concludes_from_count = LIST_FROM_RESPONSE.search(run) and CONCLUDES_FROM_COUNT.search(run)
        if concludes_from_count and not PROVES_THE_LIST.search(run):
            offenders.append(f"{job_id}: {step_name}")
    return offenders


@pytest.mark.parametrize("workflow_path", WORKFLOWS, ids=lambda p: p.name)
def test_no_linear_step_concludes_none_found_from_an_unproven_count(workflow_path: Path) -> None:
    offenders = _unproved_count_verdicts(_linear_steps(workflow_path))
    assert not offenders, (
        f"{workflow_path.name}: steps answered from a Linear response count without "
        f"proving the response was a list. On an auth or transport error "
        f"`.data.issues.nodes` is null, `jq length` of null is 0, and the step "
        f"prints an ALL-CLEAR verdict it never earned -- measured: "
        f"`Close Linear Issue on Main CI Success` printed 'No open CI failure issues "
        f"found' at 17:26:09 on a push whose sibling job was 401-ing at 17:17:09 "
        f"(runs 36899341707 / 36898232006). Offenders: {offenders}"
    )


def test_the_guard_can_see_the_measured_defect() -> None:
    """The rule fires on the real text, so it is not a guard that passes vacuously.

    ``linear-ci-status.yml``'s close-job step is the defect measured at
    ``93a45f39``; if a future edit removes the pattern this test notices that the
    guard's own premise has been retired, rather than going quiet.
    """
    body = (
        'SEARCH_RESULT=$(curl -s -X POST https://api.linear.app/graphql -d "$q")\n'
        "ISSUES=$(echo \"$SEARCH_RESULT\" | jq -r '.data.issues.nodes')\n"
        "ISSUE_COUNT=$(echo \"$ISSUES\" | jq 'length')\n"
        'if [ "$ISSUE_COUNT" = "0" ]; then echo "No open CI failure issues found"; exit 0; fi\n'
    )
    assert _unproved_count_verdicts([("main-branch-success", "sample", body)]) == [
        "main-branch-success: sample"
    ]


def test_the_guard_accepts_a_proved_list() -> None:
    """The fix shape is accepted, so the rule is about the proof and not a style pick."""
    proved = (
        'SEARCH_RESULT=$(curl -s -X POST https://api.linear.app/graphql -d "$q")\n'
        'if ! echo "$SEARCH_RESULT" | jq -e \'.data.issues.nodes | type == "array"\' '
        '> /dev/null 2>&1; then echo "unknown"; exit 0; fi\n'
        "ISSUE_COUNT=$(echo \"$SEARCH_RESULT\" | jq '.data.issues.nodes | length')\n"
    )
    assert _unproved_count_verdicts([("main-branch-success", "sample", proved)]) == []
