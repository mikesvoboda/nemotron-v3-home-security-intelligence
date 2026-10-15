"""`[r149f]`: Flaky Test Detection reports to its run summary (ruling 149 follow-up).

The package, verbatim from the ``[r149f]`` section of ``docs/uplevel/packages/ops.md``:

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
column shows them).

**What the UR-89 self-review added on top** (report ``6158211742``), because those two assertions
were necessary but not sufficient:

* ``test_the_warn_step_survives_a_malformed_report_under_bash_e`` — the step's "Never fails the
  job" comment and ``docs/developer/flaky-test-detection.md``'s red/green split only agree if the
  count line is guarded, since Actions runs the step under ``bash -e``. It executes the step body
  in that shell rather than grepping it.
* ``test_the_summary_renders_the_table_from_a_real_nightly_report`` — the Done-when's "lists the
  flaky tests" half, which the dispatch run could not show (it had zero flakes). It renders the
  committed REAL nightly report:
  ``backend/tests/unit/scripts/data/flaky-run-summary/nightly-38372397543.json``
* the counts pin widened to TWO rows with disjoint digit sets, so a hardcoded cell or a
  pass/fail swap cannot pass — one row cannot tell "these counts render" from "some digits render".

**Red-first (UR-69), written before the change** at claim head ``d51c3d23f``:
``test_issue_creation_step_is_gone`` is RED (the github-script step is present) and
``test_the_summary_shows_pass_and_fail_counts`` is RED (the table has no such column). The
survivor pins pass on the current file on purpose — they hold invariants the change must NOT
break, so a change that deletes the analysis or the artifact to "remove the issue step" turns
one red. The three pins added later are GREEN at head by design (they hold the repairs that
``aa692768e`` and the review batch make true) and were each mutation-tested: removing the guard,
assigning an empty fallback, hardcoding the counts cell, and swapping the count fields all turn
one of them red.

**What these pins refuse to over-specify.** Structure and content, not prose. The summary tests
call the real function and assert the pass and fail numbers appear as numbers (via digit-boundary
lookaround on the synthetic row, a counts-PAIR on the real corpus), which lets a reviewer reformat
the table — add columns, rename headers, switch ``2 / 7`` for two cells — without breaking a pin.
The table half of the Done-when is now exercised on real data in-repo; the "job goes green on a
runner" half is deliberately NOT pinned in YAML — it is already true of the code, and only a real
run can observe it.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "flaky-test-detection.yml"
SCRIPT = REPO_ROOT / "scripts" / "analyze-flaky-tests.py"
ANALYZE_JOB = "analyze-flaky-tests"
ARTIFACT_NAME = "flaky-test-report"
# The committed real nightly report this file renders (see the harness pin): the
# genuine flaky-test-report artifact of nightly run 38372397543, whose Analyze job
# (115221182007) is the run the package's Done-when points at.
DATA = REPO_ROOT / "backend/tests/unit/scripts/data/flaky-run-summary"
REAL_REPORT = DATA / "nightly-38372397543.json"


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


# --- the warn step runs in the runner's real shell (finding: comment vs -e) ---

# Actions gives a `run:` step with no `shell:` the Linux default `bash -e {0}`.
# This step is information-only by intent, but under `-e` a bare command
# substitution aborts the step the instant python exits non-zero -- which is what
# a truncated or empty flaky-test-report.json does -- before the trailing
# `exit 0` is ever reached. `_runner_shell()` reproduces that shell, so the pin
# exercises the hazard rather than describing it.
ACTIONS_DEFAULT_SHELL = ["bash", "-e"]


def _warn_step_body() -> str:
    step = [s for s in _steps(ANALYZE_JOB) if s.get("name") == "Warn on new flaky tests"]
    assert step, "the analyze job must still carry the console-warning step"
    return _run(step[0])


def _run_warn_step(tmp_path: Path, report_text: str | None) -> subprocess.CompletedProcess[str]:
    """Execute the real step body in the Actions default shell with `report_text`
    as flaky-test-report.json (None = no report file at all)."""
    if report_text is not None:
        (tmp_path / "flaky-test-report.json").write_text(report_text, encoding="utf-8")
    body = tmp_path / "warn_step_body.sh"
    body.write_text(_warn_step_body(), encoding="utf-8")
    return subprocess.run(  # noqa: S603  # intentional - tests our own script
        [*ACTIONS_DEFAULT_SHELL, str(body)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_warn_step_survives_a_malformed_report_under_bash_e(tmp_path: Path) -> None:
    """ "Never fails the job" (the step's own comment, and the red/green split in
    ``docs/developer/flaky-test-detection.md``) is only true if the count line is
    guarded, because Actions runs the step under `bash -e`.

    Three report states are run through the step body in that shell; each must
    exit 0. The two malformed ones are the mutants: strip `|| NEW_FLAKY_COUNT=0`
    from the step and both go rc=1 (JSONDecodeError aborts before `exit 0`). The
    no-file case is the positive control that the harness CAN reach rc 0, so a
    red below means the guard regressed, not that the probe is broken.
    """
    cases = {
        "truncated mid-write": '{"total_flaky": 3, "tests": [{"nodeid": "a::b',
        "zero bytes": "",
    }
    for label, report in cases.items():
        done = _run_warn_step(tmp_path, report)
        assert done.returncode == 0, (
            f"the warn step FAILED on a {label} report under `bash -e` (rc="
            f"{done.returncode}); a green analysis is the expected state, so this "
            "step must be information-only. Guard the substitution "
            "(`|| NEW_FLAKY_COUNT=0`) -- the trailing `exit 0` cannot help, `-e` "
            f"aborts before it. stderr:\n{done.stderr}"
        )
        # Matched on the shell's ERROR POSITION (`warn_step_body.sh: line 8: [: : integer
        # expected`), not on the wording: bash builds say "integer expected" and "integer
        # expression expected" for the same fault, so a phrase needle would silently stop
        # matching. No python traceback line has `[: ` in it, so this cannot fire on the
        # JSONDecodeError that the guard is there to absorb.
        complaints = [ln for ln in done.stderr.splitlines() if "[: " in ln and "expected" in ln]
        assert not complaints, (
            "the fallback must set NEW_FLAKY_COUNT=0, not merely swallow the exit: an empty "
            "operand still trips `[ -gt 0 ]`, which the step only survives because `-e` does "
            f"not abort on a failed test. Shell complaints:\n{complaints}"
        )

    # controls: a valid report still prints the warning, a missing report is a
    # clean no-op -- both rc 0, proving the two assertions above are load-bearing.
    valid = _run_warn_step(tmp_path, '{"total_flaky": 2, "tests": []}')
    assert valid.returncode == 0 and "WARNING: Detected 2" in valid.stdout
    assert _run_warn_step(tmp_path, None).returncode == 0


def test_the_summary_shows_pass_and_fail_counts(analyze_module, tmp_path, monkeypatch) -> None:
    """The run summary lists, per flaky test, the test id AND ITS OWN pass/fail counts.

    Asserted on each flaky test's TABLE ROW, not the whole summary, and this distinction is the
    whole difficulty of the pin: the same function appends a "Recommended Actions" list whose
    second item begins ``2. Registering the flake …``. A whole-summary search for a standalone
    ``2`` therefore passes with no counts anywhere — the prose's numbered list supplies the digit.
    Scoping to the row is what makes the pin mean what it says.

    TWO rows with DISJOINT digit sets, because a single row cannot tell "this test's counts are
    rendered" from "some digits are rendered". One row ``passed=2, failed=7`` survives both
    mutants a reviewer should fear: hardcoding the cell as the literal ``| 2 / 7 |`` (no real
    count can ever reach the summary) leaves the row unchanged, and swapping the fields to
    ``{failed} / {passed}`` keeps both digits standing alone. So the second flaky test is
    ``passed=9, failed=1, total_runs=10`` — disjoint digits, and each row's own digits are absent
    from its other cells: ``13%``/``0.67`` carry neither ``2`` nor ``7``, and ``90%``/``0.10``/the
    trailing ``10`` carry neither ``9`` nor a standalone ``1`` (a digit follows, so the lookahead
    rejects them). Per row the pin requires its own pass digit present, its own fail digit present,
    and the pass digit BEFORE the fail digit — which is what makes a swapped or canned cell red.

    Matched with digit-boundary lookaround so a ``72%`` or ``0.78``-style cell can never fake a
    count. The ORDER assertion still admits ``2 / 7`` in one cell and ``| 2 | 7 |`` in two cells:
    it holds a shape (this test's counts, in this order), not my phrasing.
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
        },
        {
            "nodeid": "backend.tests.unit.test_flaky_mod::test_drags",
            "pass_rate": 9 / 10,
            "total_runs": 10,
            "passed": 9,
            "failed": 1,
            "reruns": 0,
            "flakiness_score": 0.111,
            "run_count": 2,
        },
    ]
    analyze_module.write_github_summary(flaky, quarantined=set())

    text = summary.read_text(encoding="utf-8")
    for name, passed, failed in (("test_flips", 2, 7), ("test_drags", 9, 1)):
        rows = [line for line in text.splitlines() if name in line]
        assert rows, (
            "the Done-when's 'summary lists the flaky tests': the summary must carry the test id "
            f"(nodeid) for {name}. Summary was:\n{text}"
        )
        row = "\n".join(rows)
        at = {}
        for label, value in (("pass", passed), ("fail", failed)):
            m = re.search(rf"(?<!\d){value}(?!\d)", row)
            assert m, (
                f"the package names 'pass/fail count over the runs'; the summary shows a Pass Rate "
                f"and a total-run count but not {name}'s own {label} count ({value}) on its own "
                f"row. (Scoped to the row because the Recommended-Actions prose has a numbered item "
                f"'2.' that would otherwise fake a 2.) Row was:\n{row}"
            )
            at[label] = m.start()
        assert at["pass"] < at["fail"], (
            f"{name}'s counts render fail-before-pass ({row!r}) — the fields are swapped, or the "
            "cell is canned text that happens to hold both digits."
        )


# --- the Done-when's second half: the summary table RENDERS -------------------


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.split("|")]


def _row_shows_counts(row: str, passed: int, failed: int) -> bool:
    """True if the row carries this test's counts, in this order, as one cell
    (``0 / 15``) or two adjacent cells (``| 0 | 15 |``).

    Pair-based rather than one-digit-at-a-time on purpose. The digit-boundary
    lookaround used for the synthetic pin above cannot be reused on the real
    corpus: ``test_the_accept_sweep_finds_the_known_sites`` has ``passed=0`` and a
    Pass Rate cell of ``0%``, so a standalone-``0`` search is satisfied by the
    RATE even with no counts column at all. Requiring the pair closes that hole,
    and it still admits both reformulations the shape is meant to allow.
    """
    cells = _cells(row)
    pair = re.compile(rf"^{passed}\s*/\s*{failed}$")
    for cell in cells:
        if pair.match(cell):
            return True
    return any(
        cells[i] == str(passed) and cells[i + 1] == str(failed) for i in range(len(cells) - 1)
    )


def test_the_summary_renders_the_table_from_a_real_nightly_report(
    analyze_module, tmp_path, monkeypatch
) -> None:
    """The Done-when's "and its summary lists the flaky tests", exercised on the REAL report.

    Why this pin exists: the ``workflow_dispatch`` run that proves the job goes green
    (38480776978) had ZERO flakes, so ``write_github_summary`` took its no-flakes branch and
    wrote no table -- the Done-when's second half was never observed on a runner. The nightly
    report committed here IS the artifact from the run that had flakes (nightly run 38372397543,
    artifact 11801280471, whose Analyze job 115221182007 failed only in the now-deleted
    ``Create issue for new flaky tests`` step), so feeding it here renders the summary from real
    data instead of from a hand-written dict. Its full path:
    ``backend/tests/unit/scripts/data/flaky-run-summary/nightly-38372397543.json``

    The corpus is genuinely awkward in the ways a synthetic one would not be: nodeids of 97-117
    chars (all four hit the 60-char truncation), a never-passing test at ``0 / 15``, and two
    ``test_summaries_api`` cases that share the counts ``4 / 3`` and are distinguishable only by
    their nodeids.

    This is a golden-INPUT test, not a mock of the fix: ``write_github_summary`` takes the list
    of per-test dicts and the artifact holds exactly that list, so nothing here emulates the
    behaviour under test.
    """
    report = json.loads(REAL_REPORT.read_text(encoding="utf-8"))
    assert report["total_flaky"] == len(report["tests"]) == 4, (
        "the committed corpus is the four flakes nightly run 38372397543 reported; if it "
        "changed, re-derive the expectations below rather than trusting this count"
    )

    summary = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    analyze_module.write_github_summary(report["tests"], quarantined=set())
    text = summary.read_text(encoding="utf-8")

    assert "No flaky tests detected." not in text, (
        "with four real flakes the summary took its no-flakes branch"
    )
    rows = [line for line in text.splitlines() if line.startswith("| ") and "`" in line]
    assert len(rows) == report["total_flaky"], (
        f"the table must carry one row per flaky test ({report['total_flaky']}), got "
        f"{len(rows)}:\n{text}"
    )

    for test in report["tests"]:
        # 40 < 57, so this survives the documented truncation ("..." + last 57 chars), and it is
        # long enough to separate the two summaries_api cases that share counts.
        tail = test["nodeid"][-40:]
        mine = [r for r in rows if tail in r]
        assert mine, (
            f"the summary does not list the flaky test {test['nodeid']!r} (searched for its "
            f"truncated tail {tail!r}). Summary was:\n{text}"
        )
        assert _row_shows_counts(mine[0], test["passed"], test["failed"]), (
            f"{test['nodeid']} reports passed={test['passed']}, failed={test['failed']} but its "
            f"row shows neither as a pair: {mine[0]!r}"
        )

    # Positive control on the SAME call: the no-flakes branch still works, so the
    # assertions above are about the data, not about a renderer that always prints a
    # table. Without this, an always-table renderer would pass this pin vacuously.
    empty = tmp_path / "empty_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(empty))
    analyze_module.write_github_summary([], quarantined=set())
    assert "No flaky tests detected." in empty.read_text(encoding="utf-8")


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


#: A path cite in this file's PROSE is a backticked span — SINGLE or DOUBLE backticks — that ends
#: in a file extension. Both spellings count on purpose: the bug that prompted this pin was written
#: in SINGLE backticks (see the pin's docstring), so a pin that read only double backticks would
#: wave the exact failure mode through. The extension must abut the closing backtick, so ``bash -e``,
#: ``DATA``, and a LINE cite like ``analyze-flaky-tests.py:199-200`` are NOT matched — they name a
#: shell, a constant, or a location (whose `scripts/` prefix is elided by design), not a repo path.
_PATH_EXT = re.compile(r"\.(?:json|md|py|yml|txt)$")


def _path_cites(text: str) -> list[str]:
    """Every backticked, extension-ending span in ``text``, in one OR two backticks.

    Split on the DOUBLE delimiter first so a double cite consumes both backticks and is never also
    read as two single cites; then take the single-backtick spans of what remains. This delimiter-
    consuming split is why the extractor is sound where a newline-spanning REGEX is not: regex
    backtick-pairing straddles two adjacent cites and invents spans the file does not contain
    (measured: ~20 phantom spans on clean prose). A span that CONTAINS a newline — a cite rewrapped
    across a line — flattens to a path with an interior space and so resolves to nothing and fails
    the pin, rather than silently escaping coverage; the file therefore keeps every path cite
    contiguous on one line.
    """
    halves = text.split("``")
    spans = list(halves[1::2]) + " ".join(halves[0::2]).split("`")[1::2]
    return [s.strip() for s in spans if _PATH_EXT.search(" ".join(s.split()))]


def _prose(path: Path) -> str:
    """Concatenated docstring text of every module/class/function in ``path`` — prose only.

    Code is excluded on purpose. This file's own fixtures quote report text that contains
    backticked, extension-ending strings, and the pin below plants a control cite of its own; a
    whole-file scan would match those and read red on a file whose prose is clean. "Every path
    the prose cites exists" is the claim worth pinning; nothing here promises anything about
    strings that appear in code.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = [ast.get_docstring(tree) or ""]
    nodes = ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef
    found += [ast.get_docstring(node) or "" for node in ast.walk(tree) if isinstance(node, nodes)]
    return "\n".join(found)


def test_every_path_cite_in_this_file_resolves() -> None:
    """Every path this file's prose cites is a file that exists, and the fixture cite is EXACT.

    Why this exists: the #7090 review and my own retirement note both cited the committed nightly
    report at a repo-root path built by dropping the ``backend/tests/unit/scripts/`` prefix off the
    real one — in SINGLE backticks — and no file lives there. The report is committed under the test
    directory (the ``DATA`` constant above; the repo's own convention, the same shape
    ``check-uplevel-cites.py:41`` uses for its baseline). The prose was written from memory of the
    artifact's name rather than from a file listing, and a reader who follows the cite finds nothing.
    UR-31 says a cited file comes from output the author ran; this makes that checkable rather than
    a habit. That failure was single-backtick, so the extractor reads BOTH backtick spellings.

    The trap this pins AROUND is why the fixture assertion is EXACT-EQUALITY over extracted spans
    and not a substring search: the stale spelling is a SUFFIX of the correct one, so the obvious
    "stale_string not in text" guard fails against the FIXED file — an absence check written that
    way certifies the bug and reports the repair as the red. Comparing whole extracted cites (list
    membership is element equality) is the shape that goes red on the stale cite, green on the
    fixed one. This docstring builds the stale string by concatenation and never spells it inside
    backticks, because the extractor would (correctly) try to resolve it — and so must every future
    edit to this file.

    Positive controls, because a clean verdict from a dead instrument certifies nothing: the
    extractor is run on a planted pair in BOTH backtick spellings and must return exactly that
    pair, and the cited files must be git-TRACKED (a cite to an untracked scratch file would pass a
    bare ``is_file()`` check while violating UR-10 contract rule 3, "commit every fixture").
    """
    cites = sorted(set(_path_cites(_prose(Path(__file__)))))
    assert cites, "the cite extractor matched nothing — a dead extractor would certify any path"

    # Control covers both spellings: the stale bug was single-backtick, so a control that only
    # planted double-backtick cites could not tell a working extractor from one that ignores singles.
    control = "``docs/uplevel/packages/ops.md`` and `data/planted/nothere.json` and ``gone.md``"
    assert sorted(_path_cites(control)) == [
        "data/planted/nothere.json",
        "docs/uplevel/packages/ops.md",
        "gone.md",
    ], "the extractor itself is broken, so its verdict on this file means nothing"

    # Two checks, two diagnoses, in that order: a path that does not EXIST is a different defect
    # from one that exists but was never committed, and collapsing them (git ls-files drops both)
    # would report "not committed" for a cite that no one ever wrote — misdirecting whoever reads it.
    missing = [c for c in cites if not (REPO_ROOT / c).is_file()]
    assert not missing, (
        f"path cites that resolve to nothing: {missing} — a cite whose last line is a wrapped "
        "continuation lands here too, because flattening leaves an interior space"
    )

    # Committedness, not just existence (F5): a cite to an untracked file passes is_file() but
    # breaks UR-10 rule 3. git ls-files lists only tracked paths, so an untracked cite is dropped.
    git = shutil.which("git")
    assert git, "git is not on PATH — the committedness check cannot run"
    tracked = set(
        subprocess.run(  # noqa: S603  # intentional - asks git about our own tree
            [git, "ls-files", "--", *cites],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    )
    untracked = [c for c in cites if c not in tracked]
    assert not untracked, f"path cites that are not committed to git: {untracked}"

    fixture = str(REAL_REPORT.relative_to(REPO_ROOT))
    assert fixture in cites, (
        "the prose must cite the fixture at the exact path the loader above reads"
    )
    stale = "data/" + fixture.split("/data/")[1]
    assert stale != fixture and stale not in cites, (
        f"the repo-root spelling {stale} is back in the prose; it is a SUFFIX of the real path, "
        "so it can only be caught by exact comparison, never by a substring search"
    )

    # F4 (self-review): a control that only exercises the REGEX certifies the regex, not the region
    # harvest. These two strings live in exactly one region each, so dropping either region from
    # _prose (the mutation that would silently un-check half the file) fails here first.
    module_only = "(ruling 149 follow-up)"
    function_only = "must not retire the analysis that produces the list"
    prose = _prose(Path(__file__))
    assert module_only in prose, (
        "the MODULE docstring left the harvest — half the file is unchecked"
    )
    assert function_only in prose, "a FUNCTION docstring left the harvest — the pins are unchecked"
    # …and the negative witness: neither phrase is in the other's region, so these two asserts pin
    # WHICH region is harvested, not merely that _prose returns a blob that happens to contain both.
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    assert module_only not in "".join(
        ast.get_docstring(n) or "" for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
    ), "module_only is not module-only — the liveness control above proves nothing"


def test_the_module_docstring_quotes_the_package_clause_verbatim() -> None:
    """The "verbatim from ops.md" quote IS the register clause, checked by TEXT not by line number.

    F1 (self-review): the docstring used to cite ``docs/uplevel/packages/ops.md``:385-388, a range
    that was true when the file shipped and then drifted when later register PRs pushed ops.md
    down — the exact rot this PR exists to kill, reproduced one docstring line away from the two
    cites it fixes. A line number is a brittle referent; the clause TEXT is not. So the claim is
    pinned as text equality (whitespace-collapsed, because the register re-wraps as neighbours
    change) between three places that must agree: this module docstring, the register file, and
    the clause below.
    """
    clause = " ".join(
        (
            "Remove the issue-creation step from",
            "`.github/workflows/flaky-test-detection.yml`;",
            "the Analyze Flaky Tests job writes its flaky list",
            "(test id, pass/fail count over the runs) to the run summary instead,",
            "and goes green when the analysis itself succeeds.",
            "The coordinator routes the list (UR-116).",
        )
    ).split()
    clause = " ".join(clause)
    register = (REPO_ROOT / "docs/uplevel/packages/ops.md").read_text(encoding="utf-8")
    assert " ".join(register.split()).find(clause) != -1, (
        "the clause this module docstring quotes verbatim is no longer in ops.md — the quote drifted"
    )
    docstring = ast.get_docstring(ast.parse(Path(__file__).read_text(encoding="utf-8"))) or ""
    assert " ".join(docstring.split()).find(clause) != -1, (
        "the module docstring no longer quotes the clause it claims to quote verbatim"
    )
    # Positive control: the search has teeth — one word off and it must NOT find the clause.
    mutated = clause.replace("coordinator routes", "coordinator ignores", 1)
    assert " ".join(register.split()).find(mutated) == -1, (
        "a mutated clause still matched — the verbatim check is a no-op"
    )
