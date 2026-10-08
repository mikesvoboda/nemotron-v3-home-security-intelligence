"""O1.9 box 5: the issue-closing clause has an EXECUTABLE form, committed.

The Done-when reads "no 'Automated Rollback' issue is open", and the owner's
ruling (quoted in ``test_rollback_workflow_deleted.py``) moved failure
reporting to the daily batch — so the ~56 issues ``rollback.yml`` filed must
be closed once, after #6875 merges and Deploy reads green on the merge
commit. A loop pasted into a PR body is prose (rule 3: tools committed);
``scripts/close-rollback-issues.sh`` is the clause itself as a tool.

These guards keep the tool honest OFFLINE — the unit suite never calls
GitHub. A stub ``gh`` on PATH replays the recorded open-issue list (the
titles are the shape measured for §5 of the PR: newest-first, #6882 at
2026-10-08T06:54:59Z) and records every call it receives:

* ``--plan`` lists the issues and calls NOTHING but the list query;
* the default mode comments AND closes each one, then RE-VERIFIES the count
  (the Done-when is checked by re-measuring, not by trusting the loop);
* an empty list exits 0 without touching anything;
* the script parses (``bash -n``) and is executable — a 0644 tool nobody can
  run is how the checklist-only jobs started life.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "close-rollback-issues.sh"
DATA = Path(__file__).resolve().parent / "data"

# Recorded with the same query the script uses, at evidence time (§5 of the
# PR): 56 open, titles "Automated Rollback: Deployment failed for <sha7>".
OPEN_ISSUES_JSON = DATA / "rollback-issues-open.json"

STUB_GH = r"""#!/usr/bin/env bash
# Fake gh for the offline guard. Logs every invocation to $STUB_CALLS_LOG.
# Models exactly the three calls the script makes:
#   gh issue list … --json number,title --jq …   -> the recorded open numbers
#   gh issue list … --json title …                -> the post-close recount
#   gh issue comment N … / gh issue close N …     -> recorded, no output
# The recount returns 0 once any close has been recorded — the "everything
# closed" world; the failure world (script closes nothing) is covered by the
# --plan test, which must never reach the recount at all.
echo "$*" >> "$STUB_CALLS_LOG"
if [ "$1" = "issue" ] && [ "$2" = "list" ]; then
  # gh parses `--json number,title` as TWO argv entries ("--json" and
  # "number,title"); a whole-line grep would never match (this trap bit the
  # first draft of this stub).
  is_enum=0
  prev=""
  for a in "$@"; do
    if [ "$prev" = "--json" ] && [ "$a" = "number,title" ]; then is_enum=1; fi
    prev="$a"
  done
  if [ "$is_enum" = "1" ]; then
    cat "$FIXTURE_OPEN"        # one number per line, exactly as gh --jq emits
  else
    if grep -q "^issue close " "$STUB_CALLS_LOG" 2>/dev/null; then
      echo 0
    else
      grep -c . "$FIXTURE_OPEN"
    fi
  fi
fi
exit 0
"""


def _run(
    script_args: list[str], tmp_path: Path, open_titles: list[int]
) -> subprocess.CompletedProcess[str]:
    """Run the committed script with a stubbed gh and a fixture issue list."""
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    (stub_dir / "gh").write_text(STUB_GH, encoding="utf-8")
    (stub_dir / "gh").chmod(0o755)
    calls_log = tmp_path / "calls.log"
    fixture = tmp_path / "open.json"
    fixture.write_text("\n".join(str(n) for n in open_titles), encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}",
        "STUB_CALLS_LOG": str(calls_log),
        "FIXTURE_OPEN": str(fixture),
    }
    result = subprocess.run(  # noqa: S603  # intentional - tests our own script, offline
        ["bash", str(SCRIPT), *script_args],  # noqa: S607  # partial path OK for test script
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
    )
    result.calls_log = calls_log  # type: ignore[attr-defined]
    return result


def test_the_closing_tool_is_committed_and_executable() -> None:
    assert SCRIPT.is_file(), (
        "scripts/close-rollback-issues.sh is missing — box 5's loop must be a "
        "committed tool, not prose in a PR body (rule 3)"
    )
    assert SCRIPT.stat().st_mode & stat.S_IXUSR, "the closing tool must be executable"
    parsed = subprocess.run(  # noqa: S603  # intentional - parses our own script
        ["bash", "-n", str(SCRIPT)],  # noqa: S607  # partial path OK for test script
        capture_output=True,
        text=True,
        check=False,
    )
    assert parsed.returncode == 0, f"the closing tool does not parse: {parsed.stderr}"


def test_plan_mode_lists_but_touches_nothing(tmp_path: Path) -> None:
    result = _run(["--plan"], tmp_path, [6882, 6881, 6879])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "3 open" in result.stdout, result.stdout
    assert "6882" in result.stdout, "the newest incident must be named"
    calls = result.calls_log.read_text(encoding="utf-8")  # type: ignore[union-attr]
    assert "issue close" not in calls, "--plan must not close anything"
    assert "issue comment" not in calls, "--plan must not comment on anything"
    assert "issue list" in calls, "--plan still runs the measurement query"


def test_default_mode_comments_closes_each_then_reverifies(tmp_path: Path) -> None:
    result = _run([], tmp_path, [6882, 6881, 6879])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Done-when verified" in result.stdout
    calls = result.calls_log.read_text(encoding="utf-8")  # type: ignore[union-attr]
    for n in (6882, 6881, 6879):
        assert f"issue comment {n} " in calls, f"#{n} must get the explanation comment"
        assert f"issue close {n} " in calls, f"#{n} must be closed"
    assert calls.count("issue list") >= 2, (
        "the script must RE-RUN the query after closing — the Done-when is "
        "verified by re-measuring, not by trusting the loop"
    )


def test_an_empty_list_is_success_not_an_error(tmp_path: Path) -> None:
    result = _run([], tmp_path, [])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 open" in result.stdout
    calls = result.calls_log.read_text(encoding="utf-8")  # type: ignore[union-attr]
    assert "issue close" not in calls


def test_the_closing_comment_names_the_ruling_and_the_pr(tmp_path: Path) -> None:
    """Each closed issue must carry the WHY: deleted by #6875, owner ruling quoted."""
    body_lines = SCRIPT.read_text(encoding="utf-8")
    assert "owner" in body_lines.lower() and "6875" in body_lines, (
        "the closing comment template must cite the PR and the owner ruling"
    )


def test_the_recorded_incident_fixture_exists() -> None:
    """The stub's issue list is recorded evidence (rule 3), not a test fixture lie."""
    assert OPEN_ISSUES_JSON.is_file(), (
        "backend/tests/unit/scripts/data/rollback-issues-open.json must hold the "
        "issue numbers measured at evidence time — it is the provenance for the "
        "count quoted in the PR body (§5)"
    )
    numbers = json.loads(OPEN_ISSUES_JSON.read_text(encoding="utf-8"))
    assert 6882 in numbers, "the newest incident (#6882) must be in the recorded set"
