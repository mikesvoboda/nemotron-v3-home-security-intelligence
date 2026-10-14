"""Red-`main` fix (UR-112): a PR title interpolated into ``run:`` IS shell source.

Measured on ``main`` at ``a3f975b63``, twice, from two different triggers of the
``Linear CI Status Sync`` workflow, and both times the runner printed the script
it generated before bash rejected it:

- run ``38634638709`` (``push``, job ``Update Linear on PR Merge``) at 20:44:46Z::

    ##[group]Run PR_TITLE="fix(ops): a down engine's answer is UNKNOWN, not "image absent""
    /home/runner/work/_temp/9ddd98f5-e87d-4869-ac96-a338a106a5cf.sh: line 1: absent: command not found
    ##[error]Process completed with exit code 127.

- run ``38634486527`` (``workflow_run``, job ``Update Linear on CI Completion``)
  at 20:43:39Z printed the same line 1 and died the same way.

The title was ``fix(ops): a down engine's answer is UNKNOWN, not "image absent"``
— PR #7133's own, a title with an ordinary quoted phrase in it. Actions
substitutes ``${{ }}`` TEXTUALLY, before bash ever parses the line, so the
title's closing quote ended the string early and ``absent)`` became a command.
Nothing about the title is escaped or quoted by the substitution; ``env:`` is the
only place a value arrives as data.

The red is the smaller half of the defect. Actions runs a
``workflow_run``-triggered job in BASE-repo context, so a fork author's PR title
reaches a shell here even though the PR is from a fork. Of the 8 sites, two sit
in a step that ALSO holds ``LINEAR_API_KEY`` in its own ``env:`` --
``ci-completion / Update Linear issues on CI success`` and ``main-branch-failure
/ Create new Linear issue for CI failure`` -- so a title like
``x"; curl -d @- $LINEAR_API_KEY; #`` is arbitrary script in a step that has a
write-capable Linear credential in scope. (The other six are the same injection
surface one step away from a secret -- still script execution in base context,
just not in the same process environment as the key.) The permissions are
``contents: read``, so the exposure is credential theft, not repo writes.

The rule is the value CLASS, not the ``${{ }}`` syntax, and the census is why.
Across 34 workflows, 464 sites interpolate context into a ``run:`` body, and the
overwhelming majority are machine values that cannot break a quote: 48
``github.repository``, 40 ``github.sha``, 34 ``github.server_url``, 34
``github.run_id``, plus ``matrix.*`` and ``needs.*.result``. A guard that flagged
the syntax would red-flag 464 steps and be disabled inside a week. Keyed on the
free-text leaves instead -- ``title``, ``display_title``, ``branch``,
``head_ref``, ``body``, ``message`` -- it selects exactly the 8 sites this PR
fixes and 0 other sites with those leaves fleet-wide (verified both ways: a
forward leaf census and an inverted machine-value allowlist).

Two adjacent classes are OUT, named so the guard's silence is a decision, not an
oversight. ``github.ref_name`` (a few summary sites) is not a chosen name on a
``pull_request`` run -- it is ``refs/pull/N/merge``. ``github.base_ref`` (2 sites,
in ``ci.yml`` and ``test-coverage-gate.yml``) IS a ref name and
``git check-ref-format`` proves a ref may hold a ``"``, so it is the same quote
hazard -- but a PR's base ref is a branch of the BASE repo, chosen by whoever
opens the PR against an existing branch, not by the fork author. It is a real
sibling at a lower privilege tier and wants its own fix, not a bolt-on here.
``workflow_dispatch`` inputs (11 sites) are typed by someone who already has
write access -- a different tier and a different change.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")) + sorted(
    (REPO_ROOT / ".github" / "workflows").glob("*.yaml")
)

# The leaf name of a context path decides the class: `steps.x.outputs.title` and
# `github.event.workflow_run.display_title` both end in a human-written string.
# `name` is excluded on purpose -- `matrix.image.name` is 11 sites of
# workflow-author-declared value, and a guard that flags the author's own
# constants is a guard that gets turned off.
FREE_TEXT_LEAVES = ("title", "display_title", "branch", "head_ref", "body", "message")


def _free_text_interpolations(run_body: str) -> list[str]:
    """Every ``${{ … }}`` in a ``run:`` body whose value is human-written text.

    The class is the context path's LEAF (``steps.x.outputs.title`` and
    ``github.event.workflow_run.display_title`` both end in a chosen string).
    A ``||`` default cannot rescue the substitution -- the left side is still
    pasted as source -- so every dotted path in the expression is checked. Pure
    so the guard can be shown to bite (see
    ``test_the_guard_can_see_the_measured_defect``): a scan that quietly stopped
    visiting step bodies would report a clean fleet forever.
    """
    offenders: list[str] = []
    for match in re.finditer(r"\$\{\{([^}]*)\}\}", run_body):
        expr = match.group(1).strip()
        for path in re.findall(r"[A-Za-z0-9_.\-]+", expr):
            if path.rsplit(".", 1)[-1].lower() in FREE_TEXT_LEAVES:
                offenders.append(expr)
                break
    return offenders


def _offending_steps(workflow_path: Path) -> list[str]:
    doc: Any = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for job_id, job in sorted((doc.get("jobs") or {}).items()):
        if not isinstance(job, dict):
            continue
        for index, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if not isinstance(run, str):
                continue
            bad = _free_text_interpolations(run)
            if bad:
                name = str(step.get("name") or f"step{index}")
                offenders.append(f"{job_id}: {name} -> {sorted(set(bad))}")
    return offenders


@pytest.mark.parametrize("workflow_path", WORKFLOWS, ids=lambda p: p.name)
def test_no_run_body_interpolates_free_text(workflow_path: Path) -> None:
    offenders = _offending_steps(workflow_path)
    assert not offenders, (
        f"{workflow_path.name}: ``run:`` bodies interpolate a human-written "
        f"string into shell source. Actions substitutes ${{{{ }}}} textually "
        f"before bash parses, so a quote in the value ends the string and the "
        f"rest executes -- measured: PR #7133's title "
        f"'fix(ops): a down engine's answer is UNKNOWN, not \"image absent\"' "
        f"made `line 1: absent: command not found`, exit 127, on main runs "
        f"38634638709 and 38634486527. Pass the value through ``env:`` "
        f"instead. Offenders: {offenders}"
    )


def test_the_guard_can_see_the_measured_defect() -> None:
    """Non-vacuity: the shape that reddened main, in a fixture, must be caught."""
    measured = (
        'PR_TITLE="${{ steps.pr-info.outputs.title }}"\n'
        'PR_BRANCH="${{ steps.pr-info.outputs.branch }}"\n'
        'TITLE_MATCHES=$(echo "$PR_TITLE" | grep -oiE "NEM[_-][0-9]+")\n'
    )
    assert _free_text_interpolations(measured) == [
        "steps.pr-info.outputs.title",
        "steps.pr-info.outputs.branch",
    ]


def test_the_guard_can_see_the_event_side_of_the_same_class() -> None:
    """A ``github.event`` path is caught by leaf, not by the ``steps.`` prefix."""
    assert _free_text_interpolations(
        'COMMIT_MSG="${{ github.event.workflow_run.display_title }}"\n'
    ) == ["github.event.workflow_run.display_title"]


def test_the_guard_accepts_the_fix_shape() -> None:
    """The fix is about WHERE the value arrives, not about banning the variable."""
    fixed = (
        "# PR_TITLE arrives via the step's env: block, so bash never parses it.\n"
        'TITLE_MATCHES=$(echo "$PR_TITLE" | grep -oiE "NEM[_-][0-9]+")\n'
    )
    assert _free_text_interpolations(fixed) == []


@pytest.mark.parametrize(
    "body",
    [
        'SHA="${{ github.sha }}"\n',
        'REPO="${{ github.repository }}"\n',
        'SHARD="${{ matrix.shard }}"\n',
        'RESULT="${{ needs.unit-tests.result }}"\n',
        'IDS="${{ steps.extract-issues.outputs.ids }}"\n',
        'REF="${{ github.ref_name }}"\n',
        'IMAGE="${{ matrix.image.name }}"\n',
    ],
    ids=lambda b: re.search(r"\{\{ *([^ ]+)", b).group(1),  # type: ignore[union-attr]
)
def test_machine_values_still_interpolate_freely(body: str) -> None:
    """The must-ignore half: 456 of the fleet's 464 sites look like this.

    Without this control the rule could be "flag every interpolation" and still
    report a clean fleet -- it is the exceptions that make the census honest.
    """
    assert _free_text_interpolations(body) == []
