"""Tests for scripts/check-test-duration-budget.py (owner ruling 74).

**The rule.** "Real sleeps in unit tests are caught by a post-run gate script
over the per-test durations CI already records. It runs after the unit shards,
like the Test Performance Audit, and fails any unit test whose call time
exceeds a budget well under the audit's 4.0 s limit, with **no 'healthy in the
previous run' downgrade**. … Tests over the budget today are listed in the PR
and either fixed in it or held in a **baseline file that may only shrink**."

Three properties the Test Performance Audit deliberately does NOT have, and
which are the whole point of this gate — so they are pinned here rather than
assumed:

1. **No previous-run downgrade.** The audit's WP1.3 ``--baseline-dir`` machinery
   turns a mild breach on a baseline-healthy test into a warning. This gate may
   not: it reads no previous run, accepts no baseline directory, and has no
   fetch step behind it. ``test_the_script_has_no_previous_run_machinery`` pins
   that structurally (argparse + AST) instead of trusting absence-of-behavior,
   because the audit is 500 lines of exactly that machinery one import away.
2. **The exemption list may only shrink.** A committed baseline holds today's
   over-budget tests; the update mode REFUSES to add an id — the same
   human-only adjudication rule as ``scripts/ratchet-check.py``, which refuses
   to *raise* a suppression count. Refuse loudly rather than write
   byte-identically: a PR reaching for the update flag to widen an exemption
   has to be told no in words.
3. **Fail closed on zero evidence.** A missing or empty results dir is a
   pipeline break, not a pass — the audit's own WP0.5 reasoning, "no more
   'skip + exit 0' on missing data … zero XML is a pipeline break -> fail".
   That rule reaches one level deeper than file *count*: XML files that carry
   no usable duration at all (truncated upload, writer killed mid-flush) are
   the same broken-upload shape, and an ``--update`` over a corpus that never
   mentions an exempt id must refuse rather than turn the shrink into a wipe.

Tier classification is NOT reimplemented in either file: the gate calls the
audit's ``categorize_test``, so the two can never disagree about what tier a
test is. (This lane's measurement pass path-guessed tiers first and counted 63
over-budget unit ids where the classifier counts 46 — it routes the
``test_gpu_monitor_batch28_*`` cluster to ``integration`` on its "gpu"
substring. That 17-id disagreement is why the reuse is itself a tested
assertion.)

**Fixture-path hazard, and why the corpus dir is named ``corpus``.**
``categorize_test`` classifies from the whole file path, and pytest's
``tmp_path`` embeds the *test function's own name*. A test named
``test_integration_…`` therefore classifies every fixture it writes as
integration no matter what the fixture says. The tier-sensitive tests below are
named accordingly (integration-named tests assert integration, unit-named tests
avoid the substrings "e2e", "integration", "contract", "chaos", "gpu",
"security"), and the e2e cases carry the tier in the *filename* the way
Playwright does. ``corpus`` is tier-neutral by construction.

The two Done-when cases are replayed as corpus fixtures at the durations their
fixing commits recorded: ``test_get_redis_optional_returns_none_on_connection_
error`` at 3.85 s (commit ``99394f95d``, which zeroed ``_calculate_backoff_
delay``) and the verdict-banner Playwright spec at 23.1 s (commit ``3cdce4e3f``,
which replaced real 15 s readiness waits with a fake clock). Both are GREEN in
today's corpus *because they were fixed* — the gate has to have reddened them
at the durations they had, which is what those two numbers demonstrate.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "check-test-duration-budget.py"
BASELINE = REPO_ROOT / "scripts" / "duration-budget-baseline.json"

# Same knob set the script reads; the CI step sets the same three values.
BUDGETS = {
    "SLEEP_GATE_UNIT_BUDGET": "1.5",
    "SLEEP_GATE_INTEGRATION_BUDGET": "6.0",
    "SLEEP_GATE_E2E_BUDGET": "5.0",
}

REDIS_CASE = (
    "backend.tests.unit.core.test_redis",
    "test_get_redis_optional_returns_none_on_connection_error",
)
BANNER_CASE = (
    "specs/verdict-engine-banner.spec.ts",
    "verdict-engine banner (F1.2) > banner appears when the engine goes down and clears when it recovers",
)


def _xml(testcases: list[tuple[str, str, float]]) -> str:
    """A junit file: one ``<testcase>`` per test, as pytest's reporter emits."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<testsuite name="s">']
    for classname, name, t in testcases:
        lines.append(f'  <testcase classname="{classname}" name="{name}" time="{t}"/>')
    lines.append("</testsuite>")
    return "\n".join(lines) + "\n"


def _results(tmp_path: Path, *files: tuple[str, str]) -> Path:
    """Write ``(filename, xml-text)`` pairs into a results dir.

    One level deep under a tier-neutral ``corpus/shard/`` dir, the way CI's
    ``merge-multiple`` artifact download nests them — so the recursive glob is
    exercised rather than assumed, and nothing about the tier comes from the
    directory name.
    """
    out = tmp_path / "corpus" / "shard"
    out.mkdir(parents=True, exist_ok=True)
    for filename, text in files:
        (out / filename).write_text(text, encoding="utf-8")
    return tmp_path / "corpus"


def _run(
    results_dir: Path,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **BUDGETS}
    env.pop("SLEEP_GATE_BASELINE", None)
    env.pop("SLEEP_GATE_UPDATE", None)
    env.update(env_extra or {})
    return subprocess.run(  # noqa: S603  # intentional - tests our own script, offline
        [sys.executable, str(SCRIPT), str(results_dir)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _baseline(tmp_path: Path, ids: list[str]) -> Path:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(ids, indent=2), encoding="utf-8")
    return path


def _out(run: subprocess.CompletedProcess[str]) -> str:
    return run.stdout + run.stderr


# --------------------------------------------------------------------------
# The ruling's Done-when pair: a test over budget fails, one under passes.
# --------------------------------------------------------------------------


def test_a_unit_test_over_budget_fails_the_gate(tmp_path: Path) -> None:
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.slow.test_sleeper", "test_sleeps", 2.0)])),
    )
    run = _run(results)
    assert run.returncode != 0, (
        "a unit test at 2.0 s is over the 1.5 s budget; exit 0 here is the "
        f"ruling unimplemented\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )
    assert "test_sleeps" in _out(run), "the breach must name the test"
    assert "1.5" in _out(run), "the message must state the budget it breached"


def test_a_unit_test_under_budget_passes_the_gate(tmp_path: Path) -> None:
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.quick.test_fast", "test_fast", 0.2)])),
    )
    run = _run(results)
    assert run.returncode == 0, (
        "a unit test at 0.2 s is under budget; a gate that reddens ordinary "
        f"tests is noise the owner silences\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )


# --------------------------------------------------------------------------
# No previous-run downgrade — the limb the ruling names explicitly. Pinned
# three ways, because the neighbouring audit is the opposite behaviour and is
# one import away.
# --------------------------------------------------------------------------


def test_a_breach_with_no_baseline_file_at_all_is_red(tmp_path: Path) -> None:
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.slow.test_sleeper", "test_a", 2.0)])),
    )
    run = _run(results, {"SLEEP_GATE_BASELINE": str(tmp_path / "absent.json")})
    assert run.returncode != 0, (
        "a missing baseline file must mean NO exemptions, not 'everything is "
        f"exempt'\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )


def test_a_breach_not_listed_in_an_existing_baseline_is_red(tmp_path: Path) -> None:
    """The forbidden downgrade in the shape it would actually arrive.

    A baseline that exists, parses, and does not name this id must soften
    nothing. The audit's WP1.3 rule would warn here — "healthy in the previous
    run" — which is exactly the behaviour the ruling names and removes.
    """
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.slow.test_sleeper", "test_a", 2.0)])),
    )
    run = _run(results, {"SLEEP_GATE_BASELINE": str(_baseline(tmp_path, ["some.other::test"]))})
    assert run.returncode != 0, (
        "an existing baseline that does not list the id must not downgrade the "
        f"breach\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )


def _usage_flags() -> set[str]:
    """Every ``--flag`` the script passes to ``add_argument``.

    Built from the calls, not from a substring scan of the file: a substring
    scan of the source would trip on the word "baseline" (which this script
    legitimately uses for its one exemption FILE) and would let a flag merely
    *lacking* the forbidden substring through.
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    flags: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_argument":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        flags.add(arg.value)
    return flags


def test_the_script_has_no_previous_run_machinery() -> None:
    """Structural pin on "no 'healthy in the previous run' downgrade".

    Two arms. (a) No CLI flag names a baseline DIRECTORY or a previous /
    reference corpus — one shrink-only exemption FILE is the whole story.
    (b) No glob in the source lacks a wildcard: the audit finds the previous run
    by globbing the directory it was handed, so a script that only ever globs
    ``*.xml`` out of the results dir cannot be reading a second corpus.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)

    offending = sorted(
        f
        for f in _usage_flags()
        if "baseline-dir" in f or "previous" in f or f in {"--ref", "--reference", "--against"}
    )
    assert not offending, f"previous-run flags are the downgrade the ruling forbids: {offending}"

    GLOBS = {"glob", "rglob"}
    ENUMERATORS = {"iterdir", "listdir", "scandir", "walk"}
    glob_targets: list[str] = []
    enumerated: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # attr access (path.glob) or bare name (os.walk / os.listdir)
        fname = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if fname in GLOBS:
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    glob_targets.append(arg.value)
        elif fname in ENUMERATORS:
            # The audit finds the previous run by enumerating a directory.
            # This script has exactly one corpus to scan, via one wildcard glob
            # of the results dir — any OTHER directory enumeration is that
            # channel, so it is banned outright rather than inspected.
            enumerated.append(fname)
    assert glob_targets and all("*" in g for g in glob_targets), (
        "a glob with no wildcard is scanning some corpus other than the results "
        f"dir: {glob_targets}"
    )
    assert not enumerated, (
        "iterdir/listdir/scandir/walk is how a second corpus gets read (a "
        f"wildcard glob was the only permitted scan): {enumerated}"
    )
    # BASELINE_DIR (upper-case) is the AUDIT's env name for its previous-run
    # directory, read at audit-test-durations.py:371. The lower-case token above
    # would not catch a gate that grew an os.environ.get("BASELINE_DIR") arm —
    # the downgrade channel re-entering through the env instead of a flag.
    for forbidden in ("baseline_dir", "previous_run", "fetch-ci-artifacts", "BASELINE_DIR"):
        assert forbidden not in src, f"{forbidden} is the previous-run machinery the ruling removes"


def test_a_sibling_baseline_dir_is_not_read(tmp_path: Path) -> None:
    """The downgrade pinned BEHAVIORALLY, in the shape CI actually ships it.

    The audit's fetch step (ci.yml "Fetch baseline junit") writes the previous
    run's junit into ``baseline/`` — a SIBLING of ``test-results/``. So the
    honest test of "no previous-run downgrade" hands the gate that exact layout:
    a breaching corpus beside a baseline corpus in which the same test was
    healthy. The audit, given ``--baseline-dir``, downgrades that breach to a
    warning (WP1.3's mild-spike rule). This gate must stay RED — same fixture,
    opposite verdict, and the difference IS the ruling.

    A mutant that reads a sibling dir through any idiom the structural pin
    above happens to miss still dies here, because unlike the pin this fixture
    actually creates the directory.
    """
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.slow.test_sleeper", "test_a", 2.0)])),
    )
    prev = tmp_path / "baseline" / "shard"
    prev.mkdir(parents=True)
    (prev / "unit.xml").write_text(
        _xml([("backend.tests.unit.slow.test_sleeper", "test_a", 0.05)]),
        encoding="utf-8",
    )
    run = _run(results)
    assert run.returncode != 0, (
        "a healthy baseline/ sibling must buy nothing — this is precisely the "
        "'healthy in the previous run' downgrade the ruling forbids, and the "
        f"audit would have warned here\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )


# --------------------------------------------------------------------------
# Shrink-only baseline.
# --------------------------------------------------------------------------


def test_a_baselined_id_is_exempt(tmp_path: Path) -> None:
    """The baseline's whole job: hold today's over-budget tests, nothing else."""
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.slow.test_sleeper", "test_a", 2.0)])),
    )
    run = _run(
        results,
        {
            "SLEEP_GATE_BASELINE": str(
                _baseline(tmp_path, ["backend.tests.unit.slow.test_sleeper::test_a"])
            )
        },
    )
    assert run.returncode == 0, (
        "an id in the shrink-only baseline must be exempt — the ruling holds "
        "today's breaches in the file, and it is the only exemption there is"
        f"\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )


def test_update_refuses_to_add_an_id(tmp_path: Path) -> None:
    """The baseline may only shrink, so an update must REFUSE a new id.

    Refuse loudly rather than write byte-identically: a PR that adds a slow
    test and reaches for the update flag has to be told no. Same adjudication
    rule as ``scripts/ratchet-check.py``, whose ``--update`` "refuses to raise
    — the adjudication must be a human's diff".
    """
    baseline = _baseline(tmp_path, ["backend.tests.unit.known::test_old"])
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    ("backend.tests.unit.known", "test_old", 2.0),
                    ("backend.tests.unit.fresh", "test_sleeps", 3.0),
                ]
            ),
        ),
    )
    before = baseline.read_text(encoding="utf-8")
    run = _run(results, {"SLEEP_GATE_BASELINE": str(baseline), "SLEEP_GATE_UPDATE": "1"})
    assert run.returncode != 0, (
        "an update over a corpus with an un-baselined breach must fail: exiting "
        "clean would let a new slow test launder itself into the exemption file"
        f"\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )
    assert baseline.read_text(encoding="utf-8") == before, (
        "an update may only SHRINK the baseline; it must not have written the new id"
    )
    assert "backend.tests.unit.fresh::test_sleeps" in _out(run), (
        "the refusal must name the id it refuses to add"
    )


def test_xml_files_without_durations_fail_the_gate(tmp_path: Path) -> None:
    """Files present, durations absent → RED, not a vacuous PASS.

    ``xml_count`` counts FILES and is incremented before the parse, so a
    truncated upload (or a writer killed mid-flush) yields "N files, 0 tests
    with a recorded duration". Over-budget is then empty and the plain-PASS
    branch is one line away — the gate would certify a corpus it never read.
    The WP0.5 rule that covers an empty dir has to reach this shape too.
    """
    out = tmp_path / "corpus" / "shard"
    out.mkdir(parents=True)
    (out / "unit.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuite name="s">'
        '<testcase classname="backend.tests.unit.trunc.test_a" name="test_a" time=""/>'
        '<testcase classname="backend.tests.unit.trunc.test_b" name="test_b"/>'
        '<testcase classname="backend.tests.unit.trunc.test_c" name="test_c" time="n/a"/>'
        "</testsuite>\n",
        encoding="utf-8",
    )
    run = _run(tmp_path / "corpus")
    assert run.returncode != 0, (
        "junit files with no usable durations must fail the gate: exit 0 here "
        "passes vacuously on unread data, the exact fail-open the zero-XML rule "
        f"exists to prevent\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )
    assert "0 test(s) with a recorded duration" in _out(run), (
        "the message must say what was missing — files found, durations absent — "
        f"so it is diagnosable as corruption rather than an empty corpus: {_out(run)}"
    )


def test_update_over_a_partial_corpus_refuses_to_wipe_the_baseline(
    tmp_path: Path,
) -> None:
    """``--update`` over a corpus that omits exempt ids must REFUSE, not wipe.

    The add-guard has a mirror nobody wrote until this was measured: an
    exemption may only drop on EVIDENCE that the test is now fast, and a corpus
    that never mentions the test is unevidence — it is what running the update
    against ONE shard looks like. Executed at head ``00d58ce5d`` with a single
    real unit shard as the corpus, the shipped mode took the baseline 51 → 8
    and exited 0, dropping genuinely slow ids (the rtsp connect timeout,
    r8_s2b, the job_progress pair) that simply were not in that shard; the next
    full run then redden ~43 tests nobody touched. A real deletion is a human's
    one-line diff, exactly like an addition.
    """
    baseline = _baseline(
        tmp_path,
        [
            "backend.tests.unit.steady::test_stays_over",
            "backend.tests.unit.gone::test_not_in_this_corpus",
        ],
    )
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml([("backend.tests.unit.steady", "test_stays_over", 2.0)]),
        ),
    )
    before = baseline.read_text(encoding="utf-8")
    run = _run(results, {"SLEEP_GATE_BASELINE": str(baseline), "SLEEP_GATE_UPDATE": "1"})
    assert run.returncode != 0, (
        "an update whose corpus does not cover an exempt id must fail: exiting 0 "
        "over a partial corpus is how a 51-id file becomes an 8-id file, and every "
        f"later PR pays for it\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )
    assert baseline.read_text(encoding="utf-8") == before, (
        "the refusal must write nothing — an unevidenced shrink is still a wipe"
    )
    assert "backend.tests.unit.gone::test_not_in_this_corpus" in _out(run), (
        "the refusal must name the id whose shrink it cannot evidence"
    )
    assert "partial corpus" in _out(run), (
        "the message must name the real cause, not just the symptom, or the next "
        f"author reaches for a wider hammer: {_out(run)}"
    )


def test_update_shrinks_a_baseline(tmp_path: Path) -> None:
    """…and the shrink half of shrink-only still works: a fixed test's id leaves.

    Without this arm the test above could be satisfied by an update mode that
    always fails — a disabled feature, not a shrink-only one.
    """
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            [
                "backend.tests.unit.fixed::test_was_slow",
                "backend.tests.unit.steady::test_stays",
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    ("backend.tests.unit.fixed", "test_was_slow", 0.1),
                    ("backend.tests.unit.steady", "test_stays", 2.0),
                ]
            ),
        ),
    )
    run = _run(results, {"SLEEP_GATE_BASELINE": str(baseline), "SLEEP_GATE_UPDATE": "1"})
    assert run.returncode == 0, (
        "a corpus whose only breach is already baselined must let the update run"
        f"\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )
    ids = json.loads(baseline.read_text(encoding="utf-8"))
    assert ids == ["backend.tests.unit.steady::test_stays"], (
        f"the update drops the id of a test that is no longer over budget: {ids}"
    )


# --------------------------------------------------------------------------
# The two 10-10 Done-when cases, replayed at the durations they had.
# --------------------------------------------------------------------------


def test_the_redis_backoff_case_would_have_failed_the_gate(tmp_path: Path) -> None:
    """Done-when case 1: 3.85 s of real exponential backoff in a UNIT test.

    ``99394f95d`` zeroed ``RedisClient._calculate_backoff_delay`` for the two
    ``get_redis_optional`` failure tests; before it, ``connect()`` slept its real
    1 s + 2 s + jitter across three attempts. 3.85 s is what that commit
    records (4.11/4.31 s on main) — a 2.6x breach of the 1.5 s unit budget. Note
    the shape the audit could not catch: jitter moved it under 4. s sometimes,
    which is exactly why the budget sits at 1.5 and not near the audit's limit.
    """
    results = _results(tmp_path, ("unit-shard.xml", _xml([(*REDIS_CASE, 3.85)])))
    run = _run(results)
    assert run.returncode != 0, (
        "the redis backoff test at 3.85 s is the class of breach this gate "
        f"exists for\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )
    assert REDIS_CASE[1] in _out(run), "the breach must name the redis test"


def test_the_banner_case_would_have_failed_the_gate(tmp_path: Path) -> None:
    """Done-when case 2: 23.1 s of real readiness waiting in the banner spec.

    ``3cdce4e3f`` replaced two real 15 s polls with a fake clock. The corpus file
    is Playwright's own junit reporter (``e2e-results.xml``), which the audit job
    downloads into the same ``test-results/`` dir, so ``categorize_test`` sees
    the e2e tier and the 5.0 s e2e budget applies — the interpretation recorded
    in the PR body: a strictly unit-scoped gate cannot make an e2e spec fail, and
    the ruling names this case.
    """
    results = _results(tmp_path, ("e2e-results.xml", _xml([(*BANNER_CASE, 23.1)])))
    run = _run(results)
    assert run.returncode != 0, (
        "23.1 s against a 5.0 s e2e budget is 4.6x over; this is the second "
        f"named Done-when case\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )
    assert "verdict-engine" in _out(run), "the breach must name the banner spec"


def test_the_fixed_banner_spec_at_2600ms_is_green(tmp_path: Path) -> None:
    """The same spec after the fix: 2.6 s, under the 5.0 s e2e budget.

    Measured, not invented — the current corpus's banner spec runs 1.58-2.60 s.
    Without this arm, a gate that reddens every e2e test would pass the case
    above for the wrong reason.
    """
    results = _results(
        tmp_path,
        ("e2e-results.xml", _xml([("specs/verdict-engine-banner.spec.ts", "banner clears", 2.6)])),
    )
    run = _run(results)
    assert run.returncode == 0, (
        "the fixed banner spec is the green half of the banner Done-when case"
        f"\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )


def test_the_fixed_redis_test_at_232ms_is_green(tmp_path: Path) -> None:
    """And the redis case today, at its real corpus duration, is green.

    0.232 s is the middle of what the three green main runs record (0.188 /
    0.232 / 0.282 — measured per-run, shard-3, same id) now that the backoff is
    patched away — the pair with the 3.85 s case is the whole point of the gate:
    the fix moves a test from 2.6x over budget to well under it.
    """
    results = _results(tmp_path, ("unit-shard.xml", _xml([(*REDIS_CASE, 0.232)])))
    run = _run(results)
    assert run.returncode == 0, (
        f"the fixed redis test is 0.23 s\nstdout: {run.stdout}\nstderr: {run.stderr}"
    )


def test_skips_are_not_evidence_of_a_fast_test(tmp_path: Path) -> None:
    """``time="0"`` / no-``time`` is a SKIP, not a measured-fast pass.

    Both corpus shapes are real: pytest omits the ``time`` attribute on skipped
    testcases entirely (the script's ``case.get("time", "0")`` default is that
    arm) and Playwright's reporter emits ``time="0"`` for skipped specs — both
    verified in the three green main corpora. Dropping duration<=0 (the
    audit's convention) is load-bearing in two places, and both arms below die
    if the drop is removed:

    (a) an ALL-skipped corpus — a tier whose tests all skipped is "0 test(s)
        with a recorded duration", the corrupt-upload shape, RED. Record skips
        at 0.0 instead and the same corpus becomes a healthy PASS.
    (b) an exempt id whose only sample this run is a skip, in a corpus that
        DOES hold a duration for some other test (so the zero-durations guard
        above is satisfied and the run reaches update mode). ``--update`` must
        REFUSE — absent from ``worst`` is an unevidenced shrink, the F3 guard —
        not read the skip as 0.0 s and drop the exemption. A skip laundering an
        exemption away is exactly the silent-wipe channel F3 closed, arriving
        through the reporter instead of the corpus dir.
    """
    skipped = (
        '  <testcase classname="backend.tests.unit.skips.test_a" name="test_one"><skipped/></testcase>'
        '  <testcase classname="backend.tests.unit.skips.test_b" name="test_two" time="0.0"/>'
    )
    all_skips = _results(
        tmp_path,
        (
            "unit.xml",
            f'<?xml version="1.0" encoding="utf-8"?><testsuite name="s">\n{skipped}\n</testsuite>\n',
        ),
    )
    run = _run(all_skips)
    assert run.returncode != 0, (
        "an all-skipped corpus recorded 0 durations — fail-closed, not a "
        f"vacuous pass on skipped tests\n{_out(run)}"
    )
    assert "0 test(s) with a recorded duration" in _out(run), (
        f"the message must name the zero-duration shape\n{_out(run)}"
    )

    exempt_id = "backend.tests.unit.skips.test_a::test_one"
    body = '  <testcase classname="backend.tests.unit.skips.test_c" name="test_three" time="0.1"/>'
    mixed = _results(
        tmp_path,
        (
            "mixed.xml",
            f'<?xml version="1.0" encoding="utf-8"?><testsuite name="s">\n{skipped}\n{body}\n</testsuite>\n',
        ),
    )
    baseline = _baseline(tmp_path, [exempt_id])
    before = baseline.read_text(encoding="utf-8")
    run = _run(mixed, {"SLEEP_GATE_BASELINE": str(baseline), "SLEEP_GATE_UPDATE": "1"})
    assert run.returncode != 0, (
        "the exempt id appears ONLY as a skip here — it has no duration, so the "
        f"update must refuse rather than launder the exemption away\n{_out(run)}"
    )
    assert "REFUSING TO UPDATE" in _out(run), f"the refusal must be stated\n{_out(run)}"
    assert exempt_id in _out(run), f"the refusal must name {exempt_id}\n{_out(run)}"
    assert baseline.read_text(encoding="utf-8") == before, "a refusal writes nothing"


def test_baseline_matching_is_exact_id_not_substring(tmp_path: Path) -> None:
    """A baseline entry exempts its EXACT id and nothing that merely contains it.

    The match direction is what the shipped code does incidentally (a set of
    ``classname::name`` strings) but no earlier pin demanded: matching by
    SUBSTRING or PREFIX would pass every existing exemption test while quietly
    exempting a neighbour that shares the id's text — the class-name prefix
    case is a whole second test file disappearing from the gate.
    """
    listed = "backend.tests.unit.exact.test_a::test_fast"
    lookalikes = [
        "backend.tests.unit.exact.test_a::test_fast_variant",  # name extension
        "backend.tests.unit.exact.test_a::x_test_fast",  # substring, not prefix
        "backend.tests.unit.exact_sub.test_a::test_fast",  # near-miss classname
    ]
    cases = [(cn, nm, 2.0) for cn, nm in (i.split("::") for i in lookalikes)]
    results = _results(tmp_path, ("unit.xml", _xml(cases)))
    baseline = _baseline(tmp_path, [listed])
    run = _run(results, {"SLEEP_GATE_BASELINE": str(baseline)})
    assert run.returncode != 0, (
        "a baseline entry must not exempt tests that merely contain it — the "
        f"three lookalikes are over budget and unlisted\n{_out(run)}"
    )
    for id_ in lookalikes:
        assert id_ in _out(run), f"the breach report must name {id_}"


# --------------------------------------------------------------------------
# Fail closed on zero XML.
# --------------------------------------------------------------------------


def test_zero_xml_fails_the_gate(tmp_path: Path) -> None:
    """No XML at all is a pipeline break, never a pass.

    Mirror of the audit's WP0.5 rule: "the audit only runs when its tier ran …
    so zero XML is a pipeline break -> fail". Not hypothetical here — both
    artifact downloads in this job carry ``continue-on-error: true``, so a
    broken upload looks exactly like an empty corpus and a gate that exits 0 on
    it is switched off silently.
    """
    results = tmp_path / "corpus"
    results.mkdir()
    run = _run(results)
    assert run.returncode != 0, f"zero XML must be RED\n{_out(run)}"


def test_a_missing_results_dir_fails_the_gate(tmp_path: Path) -> None:
    run = _run(tmp_path / "never-written")
    assert run.returncode != 0, f"a missing dir is the same vacuous-green risk\n{_out(run)}"


# --------------------------------------------------------------------------
# Per-tier budgets (each "well under" its own audit limit).
# --------------------------------------------------------------------------


def test_orchestrator_under_its_tier_budget_is_green(tmp_path: Path) -> None:
    """5.5 s is legal for integration (budget 6.0), not for unit.

    Named for the measured max: the 3 green main runs top out at 5.44 s on
    ``test_orchestrator_integration::test_api_start_stopped_service``, so a
    5.5 s integration test is today's normal and the budget must clear it.
    """
    results = _results(
        tmp_path,
        ("integration.xml", _xml([("backend.tests.integration.test_orch", "test_start", 5.5)])),
    )
    run = _run(results)
    assert run.returncode == 0, f"integration's budget is 6.0 s, not the unit 1.5\n{_out(run)}"


def test_orchestrator_over_its_tier_budget_is_red(tmp_path: Path) -> None:
    results = _results(
        tmp_path,
        ("integration.xml", _xml([("backend.tests.integration.test_orch", "test_start", 6.5)])),
    )
    run = _run(results)
    assert run.returncode != 0, f"6.5 s is over the 6.0 s integration budget\n{_out(run)}"
    assert "6" in _out(run), "the message must state the budget breached"


def test_a_unit_breach_is_not_forgiven_by_a_looser_tier_budget(tmp_path: Path) -> None:
    """5.5 s is green for integration and red for unit: the tier is load-bearing.

    The classifier picks the tier, so a plain unit test cannot borrow the
    integration budget by living in a file with a long name.
    """
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.services.test_things", "test_slow", 5.5)])),
    )
    run = _run(results)
    assert run.returncode != 0, (
        "a plain unit test at 5.5 s is over the 1.5 s unit budget even though "
        f"the same duration is legal for integration\n{_out(run)}"
    )


def test_the_gate_reuses_the_audits_classifier(tmp_path: Path) -> None:
    """The classifier, not a path guess, decides the tier — 17 ids of proof.

    This lane's measurement pass path-guessed tiers and reported 63 over-budget
    unit ids where the classifier reports 46, because ``categorize_test`` sends
    any test with "gpu" in it to ``integration`` on its substring pattern. If
    the gate classified differently from the audit, the baseline the PR records
    would not be the baseline the gate reads. Pinned on a case the classifier
    actually decides: a ``gpu``-named unit test gets the 6.0 s integration
    budget, so 5.5 s is GREEN for it and red for its neighbours.
    """
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    (
                        "backend.tests.unit.services.test_gpu_monitor_batch28_12",
                        "test_statement_is_executed_once",
                        5.5,
                    )
                ]
            ),
        ),
    )
    run = _run(results)
    assert run.returncode == 0, (
        "categorize_test routes any 'gpu' test to integration (6.0 s budget); a "
        "path-guessing gate would call this unit and red it at 1.5 — the 63-vs-46 "
        f"disagreement this assertion exists to prevent\n{_out(run)}"
    )


def test_the_audits_slow_bucket_is_judged_at_the_unit_budget(tmp_path: Path) -> None:
    """One exemption file, not a second allowlist.

    The audit keeps a ``slow`` category with its own 60 s cap and
    ``SLOW_TEST_PATTERNS`` list. The ruling wants exemptions in a single
    shrink-only baseline, so this gate gives ``slow`` no 60 s cap — it falls to
    the unit budget and its breaches must be baselined like everyone else's.
    ``test_rtsp_test_service::test_connection_timeout`` (6.01 s, a real socket
    timeout) is the entry that makes it concrete.

    Run against an ABSENT baseline, deliberately: this id is one of the 51 in
    the shipped file, so leaving the default in place would test the exemption
    and not the judgment. What is under test is that 6.007 s is a BREACH at all
    — the reason the id is in the file is that it would otherwise be red. The
    companion assertion that it is exempted lives in
    ``test_the_shipped_baseline_exempts_its_own_ids``.
    """
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    (
                        "backend.tests.unit.services.test_rtsp_test_service.TestRTSPTestService",
                        "test_connection_timeout",
                        6.007,
                    )
                ]
            ),
        ),
    )
    run = _run(results, {"SLEEP_GATE_BASELINE": str(tmp_path / "none.json")})
    assert run.returncode != 0, (
        "the audit's tracked-slow test at 6.007 s must be RED with no exemption "
        "in front of it — a 60 s slow cap would be the second allowlist the "
        f"ruling rules out\n{_out(run)}"
    )
    assert "budget: 1.5s" in _out(run), (
        "the breach must be measured against the UNIT budget, not the audit's "
        f"60 s slow cap\n{_out(run)}"
    )


def test_the_shipped_baseline_exempts_its_own_ids(tmp_path: Path) -> None:
    """…and with the shipped file in front of it, that same test is green.

    The two halves together are the claim: judged at 1.5 s (red), exempted by
    the one shrink-only file (green). Also the only assertion that the
    committed baseline is wired to the script's default path, so a rename that
    orphans the file cannot leave the gate silently exemption-less — or, worse,
    a gate pointed at a file nobody reads.
    """
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    (
                        "backend.tests.unit.services.test_rtsp_test_service.TestRTSPTestService",
                        "test_connection_timeout",
                        6.007,
                    )
                ]
            ),
        ),
    )
    run = _run(results, {"SLEEP_GATE_BASELINE": str(BASELINE)})
    assert run.returncode == 0, f"the committed baseline must exempt its own id\n{_out(run)}"


# --------------------------------------------------------------------------
# Budgets come from env, so the CI step and the tests share one knob.
# --------------------------------------------------------------------------


def test_budgets_are_env_overridable(tmp_path: Path) -> None:
    """One knob for CI and tests, the audit's ``UNIT_TEST_THRESHOLD`` shape.

    Overridability is what lets the Done-when pair be tested at the script's
    real code path instead of at a hard-coded constant, and keeps the owner's
    three numbers written in exactly one place in CI.
    """
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.unit.side.test_a", "test_b", 2.0)])),
    )
    loose = _run(results, {"SLEEP_GATE_UNIT_BUDGET": "3.0"})
    assert loose.returncode == 0, f"unit budget 3.0 must let 2.0 s pass\n{_out(loose)}"
    tight = _run(results, {"SLEEP_GATE_UNIT_BUDGET": "0.5"})
    assert tight.returncode != 0, f"unit budget 0.5 must red 2.0 s\n{_out(tight)}"


# --------------------------------------------------------------------------
# Duplicate ids take the MAX; every breach is reported.
# --------------------------------------------------------------------------


def test_duplicate_ids_are_judged_on_the_max(tmp_path: Path) -> None:
    """A parameterised id appears once per invocation, and a shard retry can
    emit the same id twice in one corpus.

    Judging the first sample or the mean would let a test that breached once
    look cheap. The corpus measurement used max-across-runs and so does the gate.
    """
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    ("backend.tests.unit.rep.test_repeat", "test_three_times", 0.2),
                    ("backend.tests.unit.rep.test_repeat", "test_three_times", 2.4),
                    ("backend.tests.unit.rep.test_repeat", "test_three_times", 0.3),
                ]
            ),
        ),
    )
    run = _run(results)
    assert run.returncode != 0, (
        "the 2.4 s sample is the one that counts; the mean (0.97 s) would pass "
        f"and hide the sleep\n{_out(run)}"
    )


def test_every_breach_is_listed_not_just_the_first(tmp_path: Path) -> None:
    """A gate that stops at the first breach makes the author re-run per test.

    The baseline is a list of EVERY over-budget id, so one pass has to print the
    whole list.
    """
    results = _results(
        tmp_path,
        (
            "unit.xml",
            _xml(
                [
                    ("backend.tests.unit.a.test_a", "test_one", 2.0),
                    ("backend.tests.unit.b.test_b", "test_two", 3.0),
                    ("backend.tests.unit.c.test_c", "test_three", 9.0),
                ]
            ),
        ),
    )
    run = _run(results)
    out = _out(run)
    assert run.returncode != 0
    for name in ("test_one", "test_two", "test_three"):
        assert name in out, f"every breach must be listed, missing {name}: {out}"


def test_benchmark_tests_stay_excluded(tmp_path: Path) -> None:
    """The audit's benchmark exclusion carries over.

    Benchmarks measure latency on purpose and the audit already drops them; a
    gate that reddened a deliberate benchmark would be silenced on contact,
    taking the real rule with it.
    """
    results = _results(
        tmp_path,
        ("unit.xml", _xml([("backend.tests.benchmarks.test_latency", "test_p99", 40.0)])),
    )
    run = _run(results)
    assert run.returncode == 0, f"a benchmark at 40 s is excluded\n{_out(run)}"


# --------------------------------------------------------------------------
# The committed artifacts, so the shipped numbers are the tested ones.
# --------------------------------------------------------------------------


def test_the_committed_baseline_holds_the_measured_51_ids() -> None:
    """The MEASURE/DECIDE record: 46 unit-tier + 5 slow-tier ids, nothing else.

    51 is the count the PR body records from the three green main runs
    (38072983861 / 38074430466 / 38078235885), max-across-runs, under a 1.5 s
    unit budget. Pinned as a count and not only a set: a silent prune or a
    hand-added id has to be a red test, not a quiet drift in an exemption list.
    """
    ids = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert isinstance(ids, list), "the baseline is a JSON array of test ids"
    assert len(ids) == 51, f"expected the measured 46 + 5 = 51 ids, got {len(ids)}"
    assert len(set(ids)) == len(ids), "duplicate ids would hide a breach"
    assert ids == sorted(ids), "sorted so a prune shows as a clean diff"
    assert all("::" in i for i in ids), "ids are classname::name, the gate's key"


def test_the_shipped_baseline_does_not_exempt_the_done_when_cases() -> None:
    """Anti-rubber-stamp for the test above.

    A baseline that baselined the two named Done-when cases would make this
    file's own Done-when tests pass trivially. The exemptions and the
    demonstrations have to stay disjoint, or the exemption list has swallowed
    the rule.
    """
    ids = set(json.loads(BASELINE.read_text(encoding="utf-8")))
    assert f"{REDIS_CASE[0]}::{REDIS_CASE[1]}" not in ids, (
        "the redis case must not be exempted — it is the demonstration"
    )
    assert not any("verdict-engine-banner" in i for i in ids), (
        "the banner case must not be exempted either"
    )


def test_the_script_docstring_records_the_budgets() -> None:
    """The script's own header carries the numbers (audit-style usage block)."""
    doc = ast.get_docstring(ast.parse(SCRIPT.read_text(encoding="utf-8"))) or ""
    assert "1.5" in doc and "6.0" in doc and "5.0" in doc, (
        f"budgets belong in the usage text, as the audit's thresholds are: {doc[:400]}"
    )
