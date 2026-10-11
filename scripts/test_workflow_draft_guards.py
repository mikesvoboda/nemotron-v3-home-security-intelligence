#!/usr/bin/env python3
"""Ruling 97 part 2 invariant: draft PRs skip the workflows, ready runs them in full.

Two claims are pinned, in both directions (a check that only looks for the
guard's presence is satisfied by a guard on every job, including the jobs that
must not have it):

1. TRIGGERS. Every workflow with a ``pull_request`` trigger must list
   ``ready_for_review`` in its EFFECTIVE activity types. "Effective" is the
   trap: an explicit ``types:`` list REPLACES GitHub's defaults
   ``[opened, synchronize, reopened]``, so a file with no ``types:`` key that
   adds one must spell the trio out too — silently dropping ``reopened`` is
   exactly the regression this catches.

2. GUARDS. There is no workflow-level ``if`` in GitHub Actions (actionlint:
   ``unexpected key "if" for "workflow" section``), so the skip is spelled on
   every job that can start on a pull_request event. This asserts the guard is
   present on those jobs, ABSENT on the jobs that can never see a PR event, and
   AND-ed at the expression's top level — GitHub's expressions bind ``&&``
   tighter than ``||``, so a guard appended to an existing top-level ``||``
   binds to only the last disjunct (the failure mode is a job that still runs
   in full on a draft, which no amount of grep-for-the-string would reveal).

Run: ``uv run python scripts/test_workflow_draft_guards.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

# The canonical guard. One spelling for the whole fleet: for non-PR events the
# first disjunct short-circuits (so push/schedule/dispatch/merge_group runs are
# untouched), and on a pull_request event `draft` is a real boolean.
GUARD = "github.event_name != 'pull_request' || github.event.pull_request.draft != true"

# GitHub's documented default pull_request activity types.
DEFAULT_TYPES = ["opened", "synchronize", "reopened"]

# Jobs exempt from the guard, with the reason the exemption is correct rather
# than merely convenient.
EXEMPT = {
    # Pinned to `always()` by test_check_gate_reachability.py:121, and it must
    # stay runnable: its gate script forgives `skipped` results (ci.yml's
    # check_job()), so a draft run still produces the required
    # `CI Gate (Required Checks)` context instead of no context at all.
    "ci-gate": "the required context must stay present on drafts",
    # These three can never start on a pull_request event, so a guard would be
    # dead code — and in ci.yml it would be HARMFUL dead code:
    # scripts/test_ci_job_graph.py's schedule_only() classifier reads the
    # substring `pull_request` in the job's `if`, and `.pull_request.draft`
    # contains it, so guarding these would strip their schedule-only exemption
    # and redden that gate test.
    "flake-report": "main/dispatch only",
    "frontend-e2e-secondary": "schedule/dispatch only",
    "test-count-verification": "schedule/dispatch only",
}


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def on_section(workflow: dict) -> dict:
    # `on:` parses as boolean True on a YAML 1.1 reader; PyYAML keeps the string.
    return workflow.get("on", workflow.get(True)) or {}


def effective_types(pr: object) -> list[str] | None:
    """Activity types for a pull_request trigger, or None if the file has no such trigger."""
    if pr is None:
        return None
    if isinstance(pr, dict):
        types = pr.get("types")
        return list(types) if types else list(DEFAULT_TYPES)
    return list(DEFAULT_TYPES)


def depth0_ops(expr: str) -> list[tuple[int, str]]:
    """(position, operator) for && / || at paren-depth 0, quote-aware."""
    ops: list[tuple[int, str]] = []
    depth = 0
    quote: str | None = None
    i = 0
    while i < len(expr):
        c = expr[i]
        if quote:
            if c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0:
            if expr.startswith("&&", i):
                ops.append((i, "&&"))
                i += 2
                continue
            if expr.startswith("||", i):
                ops.append((i, "||"))
                i += 2
                continue
        i += 1
    return ops


def normalize(job_if: object) -> str:
    """One-line expression from a job `if`, whatever YAML shape it used."""
    text = str(job_if if job_if is not None else "")
    text = text.replace("${{", " ").replace("}}", " ")
    return " ".join(text.split())


def check_triggers() -> list[str]:
    failures: list[str] = []
    seen = 0
    for path in sorted(WORKFLOWS.glob("*.yml")):
        types = effective_types(on_section(load(path)).get("pull_request"))
        if types is None:
            continue
        seen += 1
        if "ready_for_review" not in types:
            failures.append(
                f"{path.name}: pull_request trigger lacks ready_for_review "
                f"(effective types {types}) — marking a PR ready would start no run"
            )
        if "opened" not in types or "synchronize" not in types:
            failures.append(
                f"{path.name}: explicit types: list {types} dropped a default "
                f"pull_request activity type — that trigger class is now dead"
            )
    if seen != 8:
        failures.append(
            f"expected 8 workflows with a pull_request trigger, found {seen} — "
            "a new PR-triggered workflow needs the guard and ready_for_review too"
        )
    return failures


def check_guards() -> list[str]:
    failures: list[str] = []
    guarded = 0
    for path in sorted(WORKFLOWS.glob("*.yml")):
        on = on_section(load(path))
        if on.get("pull_request") is None:
            continue
        jobs = load(path).get("jobs") or {}
        file_guarded = 0
        for name, cfg in jobs.items():
            expr = normalize(cfg.get("if"))
            exempt_reason = EXEMPT.get(name)
            if GUARD not in expr:
                if name in EXEMPT:
                    continue
                # Reusable-workflow calls and plain jobs alike: anything without
                # an exemption must be guarded, or drafts pay its full runner cost.
                failures.append(
                    f"{path.name}:{name} has no draft guard and is not in EXEMPT — "
                    "a draft push still spends this job's runner (ruling 97 part 2)"
                )
                continue
            file_guarded += 1
            if exempt_reason:
                failures.append(
                    f"{path.name}:{name} carries a draft guard but is exempt ({exempt_reason})"
                )
                continue
            core = expr.strip().strip("()").strip()
            if core == GUARD:
                continue  # was an unconditional job: the guard IS its condition
            ops = depth0_ops(expr)
            if any(op == "||" for _, op in ops):
                failures.append(
                    f"{path.name}:{name} has a depth-0 `||` in its `if` — &&"
                    " binds tighter, so the guard applies to only one "
                    f"disjunct: {expr[:90]!r}"
                )
            if not ops or ops[0][1] != "&&":
                failures.append(
                    f"{path.name}:{name} is not simply guard-AND-condition: {expr[:90]!r}"
                )
                continue
            head = expr[: ops[0][0]].strip()
            if head.strip("() ") != GUARD:
                failures.append(
                    f"{path.name}:{name} guard is not the left operand of the"
                    f" top-level &&: {expr[:90]!r}"
                )
        if file_guarded == 0:
            failures.append(
                f"{path.name}: no job carries the draft guard despite a "
                "pull_request trigger — the whole file silently skipped the edit"
            )
        guarded += file_guarded
    return failures


def main() -> int:
    failures = check_triggers() + check_guards()
    for f in failures:
        print(f"FAIL: {f}", file=sys.stderr)
    if failures:
        return 1
    print(
        "ok: pull_request triggers carry ready_for_review; the draft guard is "
        "pinned on every PR-capable job and absent on the exempt ones"
    )
    return 0


def test_pull_request_triggers_have_ready_for_review() -> None:
    failures = check_triggers()
    assert not failures, "\n".join(failures)


def test_pr_capable_jobs_carry_the_draft_guard() -> None:
    failures = check_guards()
    assert not failures, "\n".join(failures)


if __name__ == "__main__":
    raise SystemExit(main())
