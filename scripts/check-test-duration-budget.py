#!/usr/bin/env python3
"""Fail any test whose call time exceeds a real-sleep budget (owner rulings 74 + 93).

**The rule (ruling 93, 2026-10-11, amending ruling 74).** Verbatim: "Hard fail:
any unit test over **4.0 s**, with **no** 'healthy in the previous main run'
downgrade. That missing downgrade is what this gate adds over the Test
Performance Audit. Warn: any unit test over **1.5 s** is listed in the job
summary; it never fails the run. **No baseline file.**"

What this is NOT, and why it exists beside the audit rather than inside it:
``scripts/audit-test-durations.py`` limits unit tests at 4.0 s and, since WP1.3,
downgrades a mild breach on a test that was healthy in its own previous run to a
warning. That downgrade is the right answer to a measured problem (one timing
sample on a contended shared runner reddened 15/45 PR runs on identical code)
and the wrong answer to the question this gate asks. A hand-written ``sleep(1.8)``
is not noise — it is the same value every run — so forgiving a duration by
history forgives exactly the thing being hunted. This gate therefore reads no
previous run and no exemption file of any kind: one corpus, one pass.

Budgets are the audit's OWN CI-set limits, and the gate's whole content is the
missing downgrade, not a stricter line:

    hard  unit         4.0 s   (= the audit's UNIT_TEST_THRESHOLD)
    hard  integration 10.0 s   (= its INTEGRATION_TEST_THRESHOLD)
    hard  e2e         10.0 s   (= its E2E_TEST_THRESHOLD)
    hard  slow        60.0 s   (= its SLOW_TEST_THRESHOLD, kept — see below)
    warn  unit         1.5 s   (listed in the job summary, never fails)

Why the hard line moved from ruling 74's 1.5 s to 4.0 s: the measured over-1.5
victim set rotates between same-code runs — over the three shipping green-main
corpora it is 31/22/17 ids with an intersection of only 10, and up to 20 ids
newly cross the line in one direction between two runs (29 in symmetric
difference; 12/13/10 NEWCOMERS per PR run was the first-flight baseline
figure, a different measurement) — so a hard threshold inside the runner's
noise band is a lottery, not a signal, and with the file gone there is
nothing to hold the rotation. 4.0 s is where all three green corpora flip ZERO
ids (measured max unit duration 6.01 s, and that one is tracked-slow). The 1.5 s
line keeps its information value exactly where ruling 93 put it: loudly listed,
never red. The corpus's p99.9 sits at 1.90 s, so the WARN band is precisely the
"something slept" neighborhood.

The ``slow`` tier keeps its 60 s cap (recorded interpretation for the reviewer):
ruling 74 deliberately judged tracked-slow at the unit budget because its
exemptions lived in one shrink-only file. That file is now retired, and the
audit's tracked-slow list IS a human-adjudication channel — an entry needs a
measured corpus breach AND a ``tpa_slow_list`` census line — so the bucket the
classifier does not call unit keeps the audit's own cap. Without it, the rtsp
socket-timeout test (measured 6.01 s on main) is a permanent false-red nobody
can merge against, and "permanent red" silences a gate faster than any flag.

Usage:
    python scripts/check-test-duration-budget.py <results-dir>

Environment variables (the CI step is the single place the owner's numbers are
written; same shape as the audit's ``UNIT_TEST_THRESHOLD``):
    SLEEP_GATE_UNIT_BUDGET         unit hard budget, seconds (default 4.0)
    SLEEP_GATE_INTEGRATION_BUDGET  integration hard budget, seconds (default 10.0)
    SLEEP_GATE_E2E_BUDGET          e2e hard budget, seconds (default 10.0)
    SLEEP_GATE_SLOW_BUDGET         tracked-slow cap, seconds (default 60.0)
    SLEEP_GATE_WARN_BUDGET         unit warn threshold, seconds (default 1.5)

The WARN list is also appended to ``$GITHUB_STEP_SUMMARY`` when set, because
"listed in the job summary" names the destination, not a metaphor. A summary
that cannot be written (odd permissions, a path that is a directory) degrades to
a stderr note — the WARN tier exists to never change the verdict, and an
I/O error must not become one.

Tier classification is the AUDIT'S OWN ``categorize_test``, imported rather than
reimplemented: the gate and the audit must never disagree about what tier a test
is. (This lane's first pass path-guessed tiers and over-counted the subject set
-- the classifier's number is the one that re-measures: 46 unit ids over 1.5 s
in the three shipping corpora, because ``categorize_test`` routes the
299-collected-test ``test_gpu_monitor_batch28_*`` cluster to ``integration`` on
its "gpu" substring and the five over-1.5 s tracked-slow members to ``slow``.
The naive guess's total is deliberately NOT quoted: self-review F4 showed it
depends on the guesser's own heuristic -- two re-implementations of "path only"
got two different totals off the same corpora.)

Fail-closed on zero evidence, copied reasoning from the audit's WP0.5 rule: both
artifact downloads in the job this runs in carry ``continue-on-error: true``, so
a broken upload looks exactly like an empty corpus — a gate that exits 0 here is
switched off by the thing it should catch. The same rule covers the corrupt
shape: XML files that PARSE to no durations at all (truncated upload, writer
killed mid-flush) fail too, because "N files, 0 durations" over-budgets nothing
and would otherwise PASS vacuously on data it never read.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import defusedxml.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_SCRIPT = Path(__file__).resolve().parent / "audit-test-durations.py"

# tier -> default budget; values are the audit's own CI-set thresholds.
DEFAULT_UNIT_BUDGET = 4.0
DEFAULT_INTEGRATION_BUDGET = 10.0
DEFAULT_E2E_BUDGET = 10.0
DEFAULT_SLOW_BUDGET = 60.0
DEFAULT_WARN_BUDGET = 1.5


def load_categorize() -> Any:
    """The audit's tier classifier, by path (its filename has a dash).

    Import is safe: audit-test-durations.py runs nothing at module scope beyond
    definitions — ``main()`` sits behind an ``if __name__ == "__main__"`` guard
    at its end — so this costs no work and triggers no network or file access.
    """
    spec = importlib.util.spec_from_file_location("_r93_audit_classifier", AUDIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load the tier classifier from {AUDIT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.categorize_test


categorize_test = load_categorize()


def get_budgets() -> dict[str, float]:
    """Budget per tier, env-overridable. Unknown tiers get the unit budget."""
    unit = float(os.environ.get("SLEEP_GATE_UNIT_BUDGET", str(DEFAULT_UNIT_BUDGET)))
    return {
        "unit": unit,
        "integration": float(
            os.environ.get("SLEEP_GATE_INTEGRATION_BUDGET", str(DEFAULT_INTEGRATION_BUDGET))
        ),
        "e2e": float(os.environ.get("SLEEP_GATE_E2E_BUDGET", str(DEFAULT_E2E_BUDGET))),
        "slow": float(os.environ.get("SLEEP_GATE_SLOW_BUDGET", str(DEFAULT_SLOW_BUDGET))),
    }


def get_warn_budget() -> float:
    """The unit-tier WARN threshold (ruling 93: 1.5 s, listed, never fails)."""
    return float(os.environ.get("SLEEP_GATE_WARN_BUDGET", str(DEFAULT_WARN_BUDGET)))


# ---------------------------------------------------------------------------
# The per-module import budget ([r172], issue #7102).
#
# #7102 measured the gap: junit splits cost across two elements —
# ``<testcase time>`` covers the test body, ``<testsuite time>`` includes
# collection and module import — and every read in this file used the first.
# A module that stalls at import measured 0.023 s to the gate while its suite
# spent 12.434 s, and the stall was invisible to both the corpus pass and the
# re-run that exonerated a breach on it ("corpus 12.40s, re-ran 0.42s" — the
# exoneration was granted on a number that excludes the cost under review).
#
# [r172]'s package text is the spec: "computes each module's import cost as
# <testsuite time> minus the sum of its <testcase time>s and applies UR-125's
# numbers per module, with UR-125's single re-run and shared re-run cap;
# per-test budgets and worst_durations() keep their meaning."
#
# The suite element is the finest unit junit attributes collection cost to:
# under xdist a shard's suite mixes modules, so the corpus-side number is
# per-suite (named by its file and the module span of its cases), and the
# re-run — one module, no xdist, the same argv shape the per-test re-run
# uses — is where a single module's cost is measured exactly. That is why the
# re-run, not the corpus pass, is the verdict path for the per-module budget.
#
# It ships WARNING-ONLY ([r172]'s own clause): the over-threshold list is
# posted and the run stays green; the failing turn comes after a scheduled
# nightly has posted the list and each over-threshold module is either fixed
# or entered in the audit's SLOW_TEST_PATTERNS with a measured note. The fail
# knob below exists and is pinned so that later turn is a one-line env change,
# not new code.
# ---------------------------------------------------------------------------

DEFAULT_MODULE_BUDGET = 4.0  # UR-125's unit hard number, applied per module
DEFAULT_MODULE_WARN = 1.5  # UR-125's warn number, applied per module


def get_module_budget() -> float:
    """The per-module hard budget ([r172]: UR-125's numbers per module)."""
    return float(os.environ.get("SLEEP_GATE_MODULE_BUDGET", str(DEFAULT_MODULE_BUDGET)))


def get_module_warn() -> float:
    """The per-module WARN threshold (UR-125's warn number, per module)."""
    return float(os.environ.get("SLEEP_GATE_MODULE_WARN", str(DEFAULT_MODULE_WARN)))


def module_fail_mode() -> bool:
    """Is the module budget failing, or warning-only? Warning-only ships.

    Off is the default and the shipped mode; the nightly's evidence is what
    turns it on, per [r172]. The knob names no module and reads no history,
    so it is not the exemption channel ruling 93 deleted — it is the
    scheduled verdict flip the package text describes.
    """
    return os.environ.get("SLEEP_GATE_MODULE_FAIL", "").strip() not in ("", "0", "false", "no")


def budget_for(category: str, budgets: dict[str, float]) -> float:
    """The budget that applies to one tier.

    Tracked tiers get their own line; the audit's four are all pinned above.
    An unknown future category falls to the unit budget — the strictest
    sensible default, so a new tier in the classifier becomes a loud review
    conversation here rather than a silent exemption.
    """
    return budgets.get(category, budgets["unit"])


# ---------------------------------------------------------------------------
# UR-125 AS AMENDED: a breach must REPRODUCE before it goes red, in each tier the
# clause names.
#
# Verbatim: "The real-sleep gate fails a unit test over 4.0 s only when the
# breach reproduces: the gate re-runs that one test once, in the same job, and
# the run is red only if the re-run also breaches; a test that passes on its
# re-run is listed as a warning with both timings." RULING 151 then extended the
# same sentence: "An integration test over its 10.0 s budget gets the same
# single re-run, and is red only if the re-run also breaches; at most 5 re-runs
# per job in each tier."
#
# So the clause names TWO tiers and this block implements both. It is not
# "everything that is not unit": see ``RERUN_TIERS`` for why e2e and slow stay
# out, and why that is a reason ruling 151 did not remove rather than an
# oversight it should have.
#
# Three properties the rest of this block exists to keep true, each with a pin:
# * the re-run is OFF unless the CI step turns it on. A junit corpus describes
#   the machine that wrote it, so replaying one anywhere else compares two
#   boxes and could CLEAR a genuine breach; the audit job is the one place the
#   checkout IS the tree that produced the junit. Unset, this script is ruling
#   93 byte for byte — and the knob names no test, widens no budget and reads
#   no previous run, so it is not the exemption channel ruling 93 deleted.
# * an UNVERIFIED re-run stays RED. "Could not check" is not "passed", the same
#   WP0.5 doctrine the corpus-level checks apply to a missing corpus.
# * the report says which of its three states it is in (confirmed / did not
#   reproduce / not enabled), so "off" never reads as "the rule".
# ---------------------------------------------------------------------------

# Re-runs are one per breaching test; the cap bounds what a pathological corpus
# can cost the job rather than letting a red shard spawn hundreds. Breaches past
# the cap stay RED — the cap can only ever be strict.
#
# The cap is PER TIER because that is what the rulebook states: UR-125 in
# docs/uplevel/rules.md reads "at most 5 re-runs per job in each tier", and cites
# rulings 93, 122 and 151. Precision about the source matters here: ruling 151's
# OWN words are "At most 5 re-runs per job, as for unit tests" — the "in each
# tier" scoping is UR-125's codification of that clause, recorded with the
# ruling. The distinction is not cosmetic: ``breaches`` is sorted longest-first
# and the two eligible tiers have budgets 4.0 s apart, so the integration
# breaches are almost always the longer ones. A single pooled slice of 5 would
# therefore spend the whole allowance on integration and leave the unit tier —
# the one this clause has served since ruling 122 — with none. Worst case for
# the job is now len(RERUN_TIERS) * MAX_RERUNS sleeps, 10, up from 5; that is
# what the per-tier scoping costs, and the number is pinned to UR-125 by
# test_the_cap_value_is_the_number_the_rulebook_states, not restated here.
#
# Do the time arithmetic with it (review finding 4): each re-run is capped by
# DEFAULT_RERUN_TIMEOUT + DEFAULT_RERUN_GRACE, 150 s, so 10 hanging re-runs are a
# 1,500 s ceiling inside a job whose timeout-minutes is 15 (900 s, ci.yml's
# test-performance-audit job) — the job budget is the binding limit, and it binds
# once the 7th hanging re-run ACROSS BOTH TIERS starts: 6 x 150 s already consumes
# the whole 900 s budget, so the 6th leaves no headroom and the 7th is cancelled.
# The bound is pooled, not per tier — 3 + 3 hangs the job as hard as 6 + 0.
# Recorded so the next reader does that sum here instead of across four
# files. What changed since this paragraph was written: that ceiling used to be
# FICTIONAL, because --timeout is a per-test timer and a collection-time stall
# outranks it (see DEFAULT_RERUN_GRACE), so the 1,200 s figure was "the job gets
# cancelled at 900 s" wearing a friendlier number. The parent bound makes the
# arithmetic real for up to 6 hanging re-runs; past that the job still cancels,
# which is why the cap is 5 and not, say, 40.
MAX_RERUNS = 5

# Tiers the reproduce-before-red clause covers, ruling 122 (unit) + ruling 151
# (integration). Deliberately an explicit set and NOT "any tier but unit".
#
# ``e2e`` stays out because the audit job has no browser and no ``npm ci``, so a
# Playwright re-run there is a doomed subprocess rather than a measurement. That
# reason is nearly dormant, and the exact numbers matter here. Measured on
# ``main``'s newest green CI run (``38457693762``), all three
# ``playwright-test-results-*`` artifacts: 961 testcases, of which 960 are skips
# carrying ``time="0"`` ("E2E tests flaky in CI - run locally") — and
# ``worst_durations`` drops zero-duration rows, so those 960 never enter this
# corpus. But ONE id is live and timed: F1.2's ``verdict-engine banner`` spec at
# 2.441 s, which classifies ``e2e`` and sits under the 10.0 s budget, so today it
# produces no breach. That is a one-regression margin, not a stable state: the
# same spec is on record (ruling 93) at 23.1 s, which WOULD breach, and a
# complement-style filter would then spawn a browser-less doomed subprocess in
# the audit job and call its non-zero exit "verified". Spelling the set out is
# what keeps that path from opening silently. ``slow`` stays out
# because its members are slow by measured census, not by one starved run: a
# re-run there buys a 60 s-class sleep and returns the same verdict. Neither
# reason is weakened by ruling 151, which named only the integration tier.
RERUN_TIERS = ("unit", "integration")

# Sentinel exit code for "the re-run SKIPPED". pytest exits 0 for a skip, so
# the real code would read as a clean run to ``reproduce``; this private value
# carries the one fact the exit code cannot — that the marker element was
# present and nothing executed. Not a pytest code on purpose: it is in no
# pytest documentation a reader could match an observed 0 against.
SKIPPED_RERUN_EXIT = 90

# Sentinel exit code for "the re-run child was KILLED BY THE GATE because it
# would not finish". Same reasoning as ``SKIPPED_RERUN_EXIT`` for the number:
# ``124`` is the GNU coreutils wall-clock convention, not a pytest code, and a
# reader who sees 124 in a pytest report will go looking for a pytest meaning
# that is not there. 91 is deliberately outside every set a reader could match.
TIMED_OUT_RERUN_EXIT = 91

# Seconds the gate lets the child past its own ``--timeout`` before reaping it.
# The parent bound is NOT redundant with ``--timeout``, which is why it exists:
# pytest-timeout arms its timer per TEST ITEM, during runtest, so a stall that
# happens during collection -- a module-level import, a fixture collected at
# import, a network call at module scope -- is before any timer is armed and the
# flag never fires. Measured on this repo's pytest: a module that sleeps 12.4 s
# at import, re-run with ``--timeout=3``, exits 0 (``1 passed``) after 13.4 s of
# wall clock with ``<testcase time="0.023">``. The only reaper for that shape
# was the job's own ``timeout-minutes: 15``, which cancels the run: no report,
# no verdict, and the audit's own findings lost with it. So the child keeps its
# ``--timeout`` for the case it does handle (a slow test: it kills the test,
# writes the junit, exits, and the gate reads a real duration), and the parent
# bound handles the case it cannot. Grace, not equality, so the child's own path
# wins whenever it is going to: pytest needs the slack to write the junit and
# tear down. ``SLEEP_GATE_RERUN_GRACE`` is the test hook, same shape as
# ``SLEEP_GATE_RERUN_TIMEOUT``.
DEFAULT_RERUN_GRACE = 30.0


# The re-run's own per-test ceiling. Inherited ``timeout = 5``
# (pyproject.toml:546 — its OWN ini key, not part of ``addopts``) is UNDER the
# 4.0 s budget it is supposed to adjudicate: a 4.5 s test would be killed by
# pytest-timeout at 5 s and the plugin's ceiling, not the owner's number, would
# decide the verdict. This --timeout overrides it by being on the command line;
# ``-o addopts=`` does not touch it. Generous on purpose — the budget still
# decides; this only decides "did not finish".
DEFAULT_RERUN_TIMEOUT = 120.0


def rerun_enabled() -> bool:
    """Is the re-run on? Only the audit job's step sets this (see ci.yml)."""
    return os.environ.get("SLEEP_GATE_RERUN", "").strip() not in ("", "0", "false", "no")


def rerun_command() -> list[str]:
    """The argv prefix used to re-run one test.

    Default is ``<this interpreter> -m pytest`` — not a bare ``pytest`` that
    could resolve to something off PATH. The gate is started by the same
    interpreter the job installed the dev extra for, so module invocation is
    the one spelling guaranteed to reach the pytest that ran the corpus.
    ``SLEEP_GATE_PYTEST`` replaces the prefix (tests point it at a stub).
    """
    override = os.environ.get("SLEEP_GATE_PYTEST", "").strip()
    if override:
        return shlex.split(override)
    return [sys.executable, "-m", "pytest"]


def pytest_target_for(test_id: str) -> str:
    """junit's ``dotted.classname::name`` → pytest's ``path/to/file.py::…``.

    The inversion has to get the module boundary right, not just the dots: a
    class member's junit classname is ``pkg.mod.TestKlass`` with ``name`` a
    method, and pytest wants ``pkg/mod.py::TestKlass::method``. Getting this
    subtly wrong is the nastiest failure this block can have — every re-run
    selects zero tests, the gate reports "could not verify" forever, and it
    looks like a rigorous gate that happens to see no flakes.

    Module segments are the leading ones that are not capitalised: PEP-8 module
    names are lowercase and a class is the first capitalised segment, which is
    also how the repo's own ids arrive from junit. No filesystem probe: the
    corpus may describe files this checkout no longer has, and a probe that
    missed would silently change the target shape.
    """
    classname, _, name = test_id.partition("::")
    parts = [p for p in classname.split(".") if p]
    cut = next((i for i, p in enumerate(parts) if p[:1].isupper()), len(parts))
    module = "/".join(parts[:cut]) + ".py" if cut else classname.replace(".", "/") + ".py"
    return "::".join([module, *parts[cut:], name])


def _repro_timeout() -> float:
    return float(os.environ.get("SLEEP_GATE_RERUN_TIMEOUT", str(DEFAULT_RERUN_TIMEOUT)))


def _repro_grace() -> float:
    return float(os.environ.get("SLEEP_GATE_RERUN_GRACE", str(DEFAULT_RERUN_GRACE)))


def _rerun_duration(target: str) -> tuple[float | None, int]:
    """Re-run one test once; return ``(seconds or None, pytest exit code)``.

    The argv is deliberately not the job's, and the two poisonings it clears
    come from two ini places: ``-o addopts=`` clears ``pyproject.toml``'s
    ``addopts`` (``:545`` — ``-n 8 --dist=worksteal``; re-measuring a sleep
    under 8-way contention would CONFIRM a breach using the very starvation the
    amendment forgives), while the ini's separate ``timeout = 5`` (``:546``,
    NOT inside ``addopts`` — ``-o addopts=`` cannot touch it) is outranked only
    by the explicit ``--timeout`` below. ``cwd`` is the repo root because the
    target is a repo-relative path.

    Returns ``None`` for the duration whenever there is no usable number — no
    junit, an unparseable one, or a zero-duration testcase, which junit emits
    for a skip and which the corpus pass already refuses to read as "fast".

    The wait is bounded. ``--timeout`` in the argv is NOT that bound, whatever
    the name suggests: pytest-timeout arms per test item, so it cannot see a
    stall that happens during collection, and this function's own ``cwd`` is the
    repo root, so a stall of that shape costs the whole audit job.
    """
    argv = [
        *rerun_command(),
        "-o",
        "addopts=",
        "-p",
        "no:randomly",
        f"--timeout={_repro_timeout():g}",
        "--junit-xml=@TEMP@",
        target,
    ]
    with tempfile.TemporaryDirectory(prefix="sleep-gate-repro-") as tmpdir:
        xml_path = Path(tmpdir) / "repro.xml"
        argv[argv.index("--junit-xml=@TEMP@")] = f"--junit-xml={xml_path}"
        try:
            # Fixed argv list, no shell, cwd pinned to REPO_ROOT; S603 is
            # ignored for scripts/ in pyproject.toml on exactly that rationale.
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                cwd=REPO_ROOT,
                timeout=_repro_timeout() + _repro_grace(),
            )
        except subprocess.TimeoutExpired:
            # The child would not finish inside its own ceiling plus the
            # grace, so the gate killed it (stdlib run() sends SIGKILL before
            # re-raising, so nothing is orphaned). Deliberately NOT folded into
            # the OSError arm below: "could not start" and "started and hung"
            # are different diagnoses and the report has to tell them apart.
            # TimeoutExpired is not a subclass of OSError, so it would
            # otherwise escape and take the whole gate down with a traceback.
            print(
                "  (re-run timed out and was killed; no duration measured)",
                file=sys.stderr,
            )
            return None, TIMED_OUT_RERUN_EXIT
        except OSError as exc:
            # The prefix itself will not start (bad SLEEP_GATE_PYTEST, no
            # interpreter). That is "not verified", not "passed".
            print(f"  (re-run could not start: {exc})", file=sys.stderr)
            return None, 127
        # returncode is carried out with the duration and decides the state in
        # reproduce(): 0 = passed, 1 = failed, 5 = nothing collected. Only a
        # clean 0 can exonerate anything (UR-125: "passes on its re-run").
        if not xml_path.is_file():
            return None, proc.returncode
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            return None, proc.returncode
        durations: list[float] = []
        suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
        for suite in suites:
            for case in suite.findall("testcase"):
                # A skip ran nothing, and "ran nothing" is a non-witness even
                # though pytest exits 0 for it and still reports a tiny
                # nonzero time (fixture teardown — 0.035s measured). Read the
                # marker BEFORE the duration or the teardown time clears the
                # breach: this is the only degraded-audit-env shape that exits
                # clean, because this job has no services: block and no
                # DATABASE_URL while unit tests skip on env (GPU, docker, a
                # file the job need not check out).
                if case.find("skipped") is not None:
                    return None, SKIPPED_RERUN_EXIT
                try:
                    d = float(case.get("time", "0"))
                except ValueError:
                    continue
                if d > 0:
                    durations.append(d)
        if not durations:
            return None, proc.returncode
        return max(durations), proc.returncode


def reproduce(
    breaches: list[tuple[float, str, str, float]],
) -> dict[str, tuple[str, float | None, int]]:
    """One re-run per eligible-tier breach: ``test_id -> (state, seconds, exit)``.

    ``state`` is ``confirmed`` (re-ran and breached again), ``cleared`` (passed
    under budget), ``skipped`` (the re-run skipped, so it measured nothing —
    see ``SKIPPED_RERUN_EXIT``) or ``unverified`` (nothing about this run says
    the duration was a fluke — including "it failed fast", which is a caught
    test, not an exonerated one). ``skipped``, ``timed_out`` and ``unverified`` all
    keep the breach RED; they differ only in what the report gets to say about
    why. ``timed_out`` rides in ``unverified`` for the verdict and is named in
    the row, exactly as ``skipped`` is.
    Tiers outside ``RERUN_TIERS`` are not returned: the clause names unit and
    (since ruling 151) integration, and for the other two the reason is
    measurement, not caution — see that constant.
    """
    states: dict[str, tuple[str, float | None, int]] = {}
    if not rerun_enabled():
        return states
    # The cap is applied per tier, so each tier's longest MAX_RERUNS breaches get
    # a re-run rather than the corpus's longest overall (see MAX_RERUNS).
    for tier in RERUN_TIERS:
        eligible = [b for b in breaches if b[2] == tier]
        if len(eligible) > MAX_RERUNS:
            print(
                f"  note: {len(eligible)} {tier} breaches, only the {MAX_RERUNS} slowest "
                "get a re-run; the rest stay RED unverified",
                file=sys.stderr,
            )
        for _, test_id, _category, budget in eligible[:MAX_RERUNS]:
            seconds, code = _rerun_duration(pytest_target_for(test_id))
            if code == SKIPPED_RERUN_EXIT:
                # Checked before the generic None arm: a skip also has no usable
                # duration, and the generic arm would report it as "exit 90", a
                # number pytest has no meaning for. The reader needs the reason.
                states[test_id] = ("skipped", None, code)
            elif code == TIMED_OUT_RERUN_EXIT:
                # Also checked before the generic None arm: a timeout has no
                # duration either, and the generic arm would print it as a
                # pytest exit code the reader cannot look up.
                states[test_id] = ("timed_out", None, code)
            elif seconds is None:
                states[test_id] = ("unverified", None, code)
            elif code != 0:
                states[test_id] = ("unverified", seconds, code)
            elif seconds > budget:
                states[test_id] = ("confirmed", seconds, code)
            else:
                states[test_id] = ("cleared", seconds, code)
    return states


def worst_durations(
    results_dir: Path,
) -> tuple[dict[str, tuple[float, str]], int, int]:
    """``test id -> (worst duration, tier)`` over every XML in the corpus.

    Returns ``(worst, xml_file_count, timed_testcase_count)``. The third count
    is taken BEFORE the benchmark tier is dropped, so the caller can tell "the
    corpus is corrupt/partial" (files, but no testcase has a usable duration)
    from "the corpus is legitimately all-benchmark" (durations present, tier
    filtered out).

    Duplicates take the MAX: junit emits one ``<testcase>`` per invocation, so a
    parameterised id appears several times and a shard retry can repeat an id
    outright. The first or the mean would let a test that breached once look
    cheap.

    Zero-duration testcases are skipped exactly as the audit skips them — that is
    a skipped test, not a fast one.
    """
    worst: dict[str, tuple[float, str]] = {}
    xml_count = 0
    timed_cases = 0
    for xml_file in sorted(results_dir.glob("**/*.xml")):
        xml_count += 1
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError as exc:
            print(f"Warning: could not parse {xml_file}: {exc}", file=sys.stderr)
            continue
        suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
        for suite in suites:
            for case in suite.findall("testcase"):
                classname = case.get("classname", "")
                name = case.get("name", "")
                try:
                    duration = float(case.get("time", "0"))
                except ValueError:
                    duration = 0.0
                if duration <= 0:
                    continue
                timed_cases += 1  # before the benchmark drop — see docstring
                category = categorize_test(classname, name, str(xml_file))
                if category == "benchmark":
                    continue  # measured latency on purpose; the audit drops these
                test_id = f"{classname}::{name}"
                current = worst.get(test_id)
                if current is None or duration > current[0]:
                    worst[test_id] = (duration, category)
    return worst, xml_count, timed_cases


def suite_import_costs(
    results_dir: Path,
) -> tuple[list[tuple[float, float, float, str, list[str]]], list[str]]:
    """Per-suite collection cost: ``(cost, suite_time, body_sum, label, span)``.

    [r172]'s per-module import budget, corpus side. junit attributes
    collection and module import to the ``<testsuite>`` element, not to any
    testcase, so the import cost is the suite's ``time`` minus the sum of
    its ``<testcase time>``s — the difference is what #7102 measured a
    module-level sleep hiding inside (12.434 s suite, 0.023 s testcase).

    Both sides of the subtraction are returned because both belong on the
    report line, the same way a WARN row carries corpus and re-run together:
    the import cost alone invites "trust me", while the pair lets a reader
    recompute the difference and see that the testcase's own number kept its
    meaning (0.023 s stays 0.023 s — the stall went to the suite's row, not
    the test's).

    The suite is the finest unit junit attributes collection cost to. Under
    xdist one suite mixes many modules, so the corpus-side number is
    per-suite: it is named by its XML file and the suite element's ``name``
    attribute, with the module span of its cases listed so a reader can see
    what it covers. The RE-RUN is where a single module's cost is measured
    exactly — one module, no xdist, its own suite element — which is why
    the re-run, not this corpus pass, decides the per-module verdict.

    All testcase times count toward the sum, failed and skipped included:
    junit records what ran, and the collection cost is what is left over.
    Benchmark testcases are the one exception, and on the OTHER side of the
    ledger: the per-test pass drops the benchmark tier as intentionally slow,
    so a benchmark's body time is not body-time the import cost may claim as
    credit — it is added back into the suite time before the real testcases
    are subtracted. Dropping it from both sides (the first version) let a
    benchmark's own duration shrink the module's reported import cost, which
    is the same misattribution #7102 is about, pointed the other way.

    Returns ``(costs sorted longest-first, unmeasured)``. A suite element
    with no usable ``time`` attribute goes on the ``unmeasured`` list —
    reading it as 0 would silently exempt the one shape a truncated writer
    produces; the report names it instead.
    """
    costs: list[tuple[float, float, float, str, list[str]]] = []
    unmeasured: list[str] = []
    for xml_file in sorted(results_dir.glob("**/*.xml")):
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError:
            continue  # worst_durations already warns on this file
        suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
        for suite in suites:
            label = f"{xml_file.name} / {suite.get('name', '?')}"
            raw = suite.get("time")
            if raw is None:
                unmeasured.append(label)
                continue
            try:
                suite_time = float(raw)
            except ValueError:
                unmeasured.append(label)
                continue
            case_sum = 0.0
            benchmark_sum = 0.0
            modules: list[str] = []
            for case in suite.findall("testcase"):
                classname = case.get("classname", "")
                case_name = case.get("name", "")
                raw_case = case.get("time")
                try:
                    case_time = float(raw_case) if raw_case is not None else 0.0
                except ValueError:
                    case_time = 0.0
                if categorize_test(classname, case_name) == "benchmark":
                    # See the docstring: a benchmark's body time is not
                    # credit against the collection cost. Back into the
                    # suite time, not out of both sides.
                    benchmark_sum += case_time
                    continue
                case_sum += case_time
                if classname:
                    # The module span: the same module cut pytest_target_for
                    # makes — the leading lowercase segments. One module per
                    # classname prefix; keep first-seen order, dedup cheaply.
                    parts = [p for p in classname.split(".") if p]
                    cut = next((i for i, p in enumerate(parts) if p[:1].isupper()), len(parts))
                    module = ".".join(parts[:cut]) if cut else classname
                    if module and module not in modules:
                        modules.append(module)
            costs.append(
                (suite_time + benchmark_sum - case_sum, suite_time, case_sum, label, modules)
            )
    costs.sort(key=lambda c: -c[0])
    return costs, unmeasured


def rerun_module_cost(target: str) -> tuple[float | None, int]:
    """Re-run one MODULE once; return ``(import cost or None, pytest exit code)``.

    The child is the same argv shape the per-test re-run uses (``-o addopts=``
    clears the ini's xdist/starvation, ``-p no:randomly`` fixes the shuffle,
    ``--timeout`` keeps the per-test ceiling) and runs the module, not a test
    inside it — so the child's own suite element carries exactly one module's
    collection cost, and suite-minus-sum on the child's junit is the number
    the corpus could only approximate. The same parent bound (``--timeout``
    plus grace) applies, for the same reason: a collection stall is before
    any per-test timer.

    ``None`` means no usable number — no junit, unparseable, or a suite with
    no ``time`` attribute — and keeps the breach RED (unverified is not
    passed), the same doctrine ``_rerun_duration`` applies.
    """
    argv = [
        *rerun_command(),
        "-o",
        "addopts=",
        "-p",
        "no:randomly",
        f"--timeout={_repro_timeout():g}",
        "--junit-xml=@TEMP@",
        target,
    ]
    with tempfile.TemporaryDirectory(prefix="sleep-gate-module-repro-") as tmpdir:
        xml_path = Path(tmpdir) / "module-repro.xml"
        argv[argv.index("--junit-xml=@TEMP@")] = f"--junit-xml={xml_path}"
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                cwd=REPO_ROOT,
                timeout=_repro_timeout() + _repro_grace(),
            )
        except subprocess.TimeoutExpired:
            # A collection stall is exactly the shape the parent bound exists
            # for (no per-test timer is ever armed); killed, and that is NOT
            # a pass.
            print(
                "  (module re-run timed out and was killed; no cost measured)",
                file=sys.stderr,
            )
            return None, TIMED_OUT_RERUN_EXIT
        except OSError as exc:
            print(f"  (module re-run could not start: {exc})", file=sys.stderr)
            return None, 127
        if not xml_path.is_file():
            return None, proc.returncode
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            return None, proc.returncode
        suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
        for suite in suites:
            raw = suite.get("time")
            if raw is None:
                continue
            try:
                suite_time = float(raw)
            except ValueError:
                continue
            case_sum = 0.0
            for case in suite.findall("testcase"):
                try:
                    case_sum += float(case.get("time", "0"))
                except ValueError:
                    pass
            return suite_time - case_sum, proc.returncode
        return None, proc.returncode


def module_test_path(suite_modules: list[str], xml_name: str) -> str:
    """The repo-relative module path a module re-run targets.

    Taken from the suite's case classnames (the same cut
    ``pytest_target_for`` makes) so the re-run measures the module the
    corpus saw. A suite mixing modules under xdist names its first module —
    the honest target, and the report says the cost it measured was the
    suite's. ``xml_name`` is the fallback label when no classname carried a
    usable module shape.
    """
    for module in suite_modules:
        parts = [p for p in module.split(".") if p]
        cut = next((i for i, p in enumerate(parts) if p[:1].isupper()), len(parts))
        if cut:
            return "/".join(parts[:cut]) + ".py"
    return xml_name


def cleared_rows_outside_warns(
    breaches: list[tuple[float, str, str, float]],
    warns: list[tuple[float, str]],
    cleared: dict[str, tuple[str, float | None, int]],
) -> list[tuple[float, str]]:
    """Cleared breaches the unit-tier WARN list cannot carry: ``(seconds, id)``.

    The WARN list is unit-tier by ruling 93 and a deliberate comment (listing a
    legal 2.6 s banner spec as "slow" would train everyone to skim it). A cleared
    UNIT breach is over the 1.5 s warn threshold by arithmetic, so it reaches the
    report for free — but a cleared INTEGRATION breach is not, and once the
    re-run took it out of ``red`` there was no list left that mentioned it. This
    is why extending the eligibility filter alone would have shipped the
    leniency without UR-125's "listed as a warning" half: a green run recording
    nothing about a 12.4 s event.
    """
    already_listed = {test_id for _duration, test_id in warns}
    return [
        (duration, test_id)
        for duration, test_id, _category, _budget in breaches
        if test_id in cleared and test_id not in already_listed
    ]


def write_step_summary(
    warns: list[tuple[float, str]],
    breaches: list[tuple[float, str]],
    cleared: dict[str, tuple[str, float | None, int]] | None = None,
    extra_cleared: list[tuple[float, str]] | None = None,
    module_rows: list[str] | None = None,
) -> None:
    """Append the WARN section to ``$GITHUB_STEP_SUMMARY``; never fail on it.

    Ruling 93's "listed in the job summary" is a destination: the owner reads
    the numbers on the run page, not in a scrollback log. Breached unit tests
    appear here too — the failing run is exactly when the distribution matters
    most. An unwritable path prints a stderr note and returns: this function
    changing anyone's verdict would defeat the tier it serves.

    ``cleared`` is the UR-125 re-run result for breaches that did not
    reproduce. Unit ones are already in WARNS (a 4.5 s unit test is over the
    1.5 s warn threshold by definition), so they get ONE row here rather than a
    second section — and that row carries the corpus timing AND the re-run
    timing, because a row that shows only the flattering number deletes the
    event the owner declined to forgive. ``extra_cleared`` holds the cleared
    breaches WARNS cannot hold, i.e. non-unit tiers since ruling 151; they get
    the same two-timing row, in their own section, so the summary never depends
    on the WARN list's tier scope to mention them.

    ``module_rows`` is [r172]'s section, pre-rendered markdown by the caller:
    the over-threshold modules (and the unmeasured suites) are the nightly's
    posted list, and the caller renders it because only it knows whether the
    run was in the warning-only or the failing mode.
    """
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary_path or not (warns or breaches or extra_cleared or module_rows):
        return
    cleared = cleared or {}
    extra_cleared = extra_cleared or []
    lines = [
        "## Real-sleep duration budget (ruling 93, UR-125 as amended)",
        "",
        f"Unit tests over the {get_warn_budget()}s WARN threshold "
        "(warn never fails the run; hard budgets are in the job log):",
        "",
    ]
    for duration, test_id in warns:
        if test_id in cleared:
            replay = cleared[test_id][1]
            tail = f"{replay:.2f}s" if replay is not None else "no timing"
            lines.append(
                f"- `{test_id}` — {duration:.2f}s over budget, re-ran {tail} "
                "(did not reproduce; listed, not failed)"
            )
            continue
        lines.append(f"- `{test_id}` — {duration:.2f}s")
    if extra_cleared:
        lines += [
            "",
            "Over budget, did not reproduce on its re-run (listed, not failed):",
            "",
        ]
        for duration, test_id in extra_cleared:
            replay = cleared[test_id][1]
            tail = f"{replay:.2f}s" if replay is not None else "no timing"
            lines.append(
                f"- `{test_id}` — {duration:.2f}s over budget, re-ran {tail} "
                "(did not reproduce; listed, not failed)"
            )
    if breaches:
        lines += ["", "Hard-budget breaches (this run is RED):", ""]
        lines += [f"- `{test_id}` — {duration:.2f}s" for duration, test_id in breaches]
    if module_rows:
        lines += module_rows
    lines.append("")
    try:
        # GITHUB_STEP_SUMMARY is set by the Actions runner, never derived from
        # corpus data — same shape as scripts/analyze-flaky-tests.py.
        with open(summary_path, "a", encoding="utf-8") as handle:  # nosemgrep: path-traversal-open
            handle.write("\n".join(lines))
    except OSError as exc:
        print(f"Warning: could not write $GITHUB_STEP_SUMMARY: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail tests over their real-sleep budget (rulings 74 + 93).",
    )
    parser.add_argument("results_dir", help="directory of junit XMLs (scanned recursively)")
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(
            f"Error: results directory not found: {results_dir} — the gate ran with no "
            "test data; failing rather than passing vacuously.",
            file=sys.stderr,
        )
        return 1

    worst, xml_count, timed_cases = worst_durations(results_dir)
    if xml_count == 0:
        # WP0.5's rule, inherited: this job's artifact downloads are
        # continue-on-error, so an empty corpus is what a broken upload looks
        # like. Exit 0 here would be a gate silently switched off.
        print(
            f"Error: no JUnit XML found under {results_dir} — the gate ran with no test "
            "data; failing rather than passing vacuously.",
            file=sys.stderr,
        )
        return 1
    if xml_count and timed_cases == 0:
        # The same WP0.5 reasoning one level deeper: xml_count counts FILES, and
        # a file contributes to it before it parses (and even when every
        # <testcase> inside it carries no usable time= — a truncated upload, a
        # writer killed mid-flush). Zero timed testcases over N files is that
        # broken-upload shape with the files present; over-budget stays empty
        # and the gate would PASS vacuously on data it never read. The predicate
        # is timed_cases, NOT "worst is empty": a corpus of only benchmark tests
        # has durations and legitimately an empty subject set (the tier is
        # excluded by design), and must stay green.
        print(
            f"Error: {xml_count} JUnit XML file(s) under {results_dir} yielded 0 "
            "test(s) with a recorded duration — corrupt or partial junit, not an "
            "empty corpus; failing rather than passing vacuously.",
            file=sys.stderr,
        )
        return 1

    budgets = get_budgets()
    warn_budget = get_warn_budget()

    breaches = sorted(
        (
            (duration, test_id, category, budget_for(category, budgets))
            for test_id, (duration, category) in worst.items()
            if duration > budget_for(category, budgets)
        ),
        key=lambda b: -b[0],
    )
    # The WARN list is the unit tier only — ruling 93 says "any unit test over
    # 1.5 s". Other tiers keep their own limits and their own summary noise;
    # listing a 2.6 s banner spec (legal at its 10.0 s limit) as "slow" would
    # train everyone to skim the list, and the tracked-slow census members
    # would live in it permanently.
    warns = sorted(
        (
            (duration, test_id)
            for test_id, (duration, category) in worst.items()
            if category == "unit" and duration > warn_budget
        ),
        key=lambda w: -w[0],
    )

    # [r172]: the per-module import budget, corpus side. Computed regardless
    # of mode so the report always says what it read (including the
    # unmeasured suites); the verdict use of it is gated on the module knobs
    # below, and warning-only ships.
    module_costs, module_unmeasured = suite_import_costs(results_dir)
    module_budget = get_module_budget()
    module_warn = get_module_warn()
    module_breaches = [
        (cost, suite_time, body_sum, label, modules)
        for cost, suite_time, body_sum, label, modules in module_costs
        if cost > module_budget
    ]
    module_warns = [
        (cost, suite_time, body_sum, label, modules)
        for cost, suite_time, body_sum, label, modules in module_costs
        if module_warn < cost <= module_budget
    ]

    print("=" * 70)
    print("REAL-SLEEP DURATION BUDGET GATE (rulings 74 + 93, UR-125 as amended)")
    print("=" * 70)
    print(
        f"Budgets: unit={budgets['unit']}s, integration={budgets['integration']}s, "
        f"e2e={budgets['e2e']}s, slow={budgets['slow']}s, warn(unit)={warn_budget}s"
    )
    print(f"Corpus: {xml_count} XML file(s), {len(worst)} test(s) with a recorded duration")

    # UR-125 as amended (rulings 122 + 151): a breach in an eligible tier has to
    # REPRODUCE before it reddens the run. One re-run per breaching id, in this
    # job, on this checkout. Everything below is decided by what those re-runs
    # said, so the header states which regime this run was under rather than
    # asserting ruling 93's "every breach is RED" unconditionally -- that sentence
    # is exactly what the amendments changed, and a report that denies it while
    # downgrading is the WP0.5 "off reads as the rule" shape.
    states = reproduce(breaches)
    cleared = {t: s for t, s in states.items() if s[0] == "cleared"}
    confirmed = {t: s for t, s in states.items() if s[0] == "confirmed"}
    # ``skipped`` rides in ``unverified`` for the verdict (both stay RED, and
    # ``red`` is computed from ``cleared`` alone) but is reported by name.
    unverified = {t: s for t, s in states.items() if s[0] in ("unverified", "skipped", "timed_out")}
    # Counted per tier, because that is how the cap is applied and the header has
    # to describe the rule the gate is actually honouring. A unit-only count here
    # would print "0 breach(es) get a re-run" on a run that re-runs five
    # integration ids.
    tier_counts = {tier: sum(1 for b in breaches if b[2] == tier) for tier in RERUN_TIERS}
    eligible_count = sum(tier_counts.values())
    # The number of re-runs is read BACK from ``states``, not recomputed from the
    # cap: `reproduce()` is the only thing that knows what it actually ran, and a
    # second slice here would be a second place to be wrong. The distinction is
    # load-bearing at an over-cap corpus — "6 eligible get one re-run each (max
    # 5)" is a sentence the run does not honour (it re-runs 5), and that
    # overstatement predates ruling 151; this is the commit that rewrites the
    # line, so the line has to carry both numbers now.
    # ``states`` is keyed by exactly the ids reproduce() actually re-ran, so the
    # re-run count is read straight off it. An earlier version derived a per-tier
    # re-run map here and summed it back to one number; that split reached no
    # output, so a mutant collapsing every tier to "unit" printed a byte-identical
    # line and no pin could see it (UR-89 batch-3 finding 3.4). The header reports
    # per-tier ELIGIBLE counts from ``tier_counts`` above; per-tier re-run counts
    # are not a reported dimension, so they are not computed as one.
    re_run_count = len(states)

    if not rerun_enabled():
        if eligible_count:
            print(
                "Re-run of a breach: NOT ENABLED (SLEEP_GATE_RERUN unset), so every "
                "breach below is unverified and ruling 93's verdict stands: RED."
            )
        else:
            print("Re-run of a breach: not enabled (no eligible breach to reproduce anyway).")
    else:
        per_tier = ", ".join(f"{n} {tier}" for tier, n in tier_counts.items())
        # Both counts, named by what they are. "N eligible get one re-run each"
        # lied whenever N > the per-tier cap (it re-ran fewer), and the old
        # single-count line could not express the difference at all; see the
        # pin at test_the_header_names_eligible_and_re_run_counts_separately.
        print(
            f"Re-run of a breach: ENABLED — {eligible_count} eligible breach(es) "
            f"({per_tier}); {re_run_count} get one re-run each (cap {MAX_RERUNS} "
            "per tier); only a reproduced breach is RED."
        )
    print("No previous-run downgrade and no exemption file.")
    print()

    if warns:
        print(f"WARN (unit tests over {warn_budget}s — listed, never failing): {len(warns)}")
        print("-" * 40)
        for duration, test_id in warns:
            cleared_here = cleared.get(test_id)
            if cleared_here:
                # Both timings on the ONE line that names the test. Showing only
                # the flattering 0.40 s would erase the 4.5 s event from the
                # record, which is the downgrade the owner did not grant.
                print(
                    f"  WARN {test_id} — corpus {duration:.2f}s, re-ran "
                    f"{cleared_here[1]:.2f}s (over budget, did not reproduce)"
                )
                continue
            print(f"  WARN {duration:.2f}s (warn budget: {warn_budget}s)")
            print(f"    {test_id}")
        print()

    # A breach that cleared is no longer a breach; it is the warning above.
    red = [b for b in breaches if b[1] not in cleared]

    # ---- [r172]: the per-module import budget --------------------------------
    #
    # Warning-only ships: the over-threshold list is posted, the run stays
    # green. With SLEEP_GATE_MODULE_FAIL set, a module import cost over the
    # hard budget is a breach and the re-run decides it, exactly as UR-125
    # does for a test: one re-run of the module, and only a reproduced cost
    # reddens the run. The cap is SHARED with the per-test re-runs ([r172]:
    # "shared re-run cap") — the module re-runs draw on the unit tier's
    # allowance after the test breaches have taken theirs, and a module that
    # gets no slot stays RED unverified in the fail mode (never passed).
    module_re_runs: dict[str, tuple[str, float | None, int]] = {}
    module_failed = False
    if module_breaches or module_warns or module_unmeasured:
        if module_fail_mode():
            print(
                f"Module import budget: FAILING at {module_budget}s "
                f"({len(module_breaches)} over budget) — [r172], post-nightly mode"
            )
        else:
            print(
                f"Module import budget: WARNING-ONLY at {module_budget}s hard / "
                f"{module_warn}s warn ({len(module_breaches)} over the hard line, "
                f"{len(module_warns)} in the warn band) — [r172]; the run stays green"
            )
        for label in module_unmeasured:
            print(f"  MODULE {label}: suite carries no time attribute — not measured")
        for cost, suite_time, body_sum, label, modules in module_breaches:
            if module_fail_mode():
                # The shared cap: module re-runs draw on the unit tier's
                # allowance after the per-test re-runs have taken theirs.
                # reproduce() ran min(len(unit breaches), MAX_RERUNS) re-runs;
                # the slots left are what modules get. An over-cap module
                # stays RED unverified — "could not check" is not "passed".
                unit_taken = min(sum(1 for b in breaches if b[2] == "unit"), MAX_RERUNS)
                slots_left = MAX_RERUNS - unit_taken
                if slots_left <= 0:
                    # Named for what it is, not just what happened: the tier's
                    # allowance was spent on test re-runs, so this module's
                    # cost stays unverified this job. The report word is
                    # load-bearing — a denied re-run is never a pass, and the
                    # reader needs to see the cap, not infer it.
                    module_re_runs[label] = ("unverified", None, -1)
                    print(
                        f"  note: the unit tier's re-run cap ({MAX_RERUNS}) is spent on "
                        f"test re-runs; the module re-run is denied this job"
                    )
                elif rerun_enabled():
                    target = module_test_path(modules, label.split(" / ")[0])
                    cost2, code = rerun_module_cost(target)
                    if cost2 is None:
                        module_re_runs[label] = ("unverified", None, code)
                    elif cost2 > module_budget and code == 0:
                        module_re_runs[label] = ("confirmed", cost2, code)
                    elif code == 0:
                        module_re_runs[label] = ("cleared", cost2, code)
                    else:
                        module_re_runs[label] = ("unverified", cost2, code)
                else:
                    module_re_runs[label] = ("unverified", None, -1)
                state, replay, code = module_re_runs[label]
                if state == "confirmed":
                    module_failed = True
                    print(
                        f"  BREACH {cost:.2f}s import cost (budget: {module_budget}s) "
                        f"[module] — re-ran {replay:.2f}s and BREACHED AGAIN"
                    )
                    print(
                        f"    {label} — suite {suite_time:.2f}s, testcases "
                        f"{body_sum:.2f}s (the difference is the import cost)"
                    )
                    print(f"    module span: {', '.join(modules) if modules else 'unknown'}")
                elif state == "cleared":
                    print(
                        f"  MODULE {label} — {cost:.2f}s import cost "
                        f"(suite {suite_time:.2f}s, testcases {body_sum:.2f}s), re-ran "
                        f"{replay:.2f}s (did not reproduce; listed, not failed)"
                    )
                else:
                    if code > 0:
                        detail = f"pytest exit {code}"
                    elif slots_left <= 0:
                        detail = (
                            "the tier's re-run cap was spent on test re-runs, "
                            "so the module cost stays unverified"
                        )
                    elif not rerun_enabled():
                        detail = "re-run not enabled"
                    else:
                        detail = "no junit or no usable suite time"
                    print(
                        f"  BREACH {cost:.2f}s import cost (budget: {module_budget}s) "
                        f"[module] — re-run not verified ({detail}; not a pass)"
                    )
                    print(
                        f"    {label} — suite {suite_time:.2f}s, testcases "
                        f"{body_sum:.2f}s (the difference is the import cost)"
                    )
                    print(f"    module span: {', '.join(modules) if modules else 'unknown'}")
                    module_failed = True
            else:
                print(
                    f"  MODULE {label} — {cost:.2f}s import cost "
                    f"(suite {suite_time:.2f}s, testcases {body_sum:.2f}s; over the "
                    f"{module_budget}s line, warning-only)"
                )
                print(f"    module span: {', '.join(modules) if modules else 'unknown'}")
        for cost, suite_time, body_sum, label, modules in module_warns:
            print(
                f"  MODULE WARN {cost:.2f}s import cost "
                f"(suite {suite_time:.2f}s - bodies {body_sum:.2f}s, warn: {module_warn}s)"
            )
            print(f"    {label} (module span: {', '.join(modules) if modules else 'unknown'})")
        if module_breaches or module_warns:
            print()

    # ...unless the warning above is unit-tier and this breach is not. A cleared
    # integration breach appears in neither the WARN section (unit-only by ruling
    # 93) nor the red list, so without its own section it would be a green run
    # that records nothing about a 12.4 s event — UR-125's "listed as a warning
    # with both timings" is half of the clause, not a courtesy.
    listed_elsewhere = cleared_rows_outside_warns(breaches, warns, cleared)
    if listed_elsewhere:
        print(f"OVER BUDGET, DID NOT REPRODUCE (listed, never failing): {len(listed_elsewhere)}")
        print("-" * 40)
        for duration, test_id in listed_elsewhere:
            replay = cleared[test_id][1]
            tail = f"{replay:.2f}s" if replay is not None else "no timing"
            print(
                f"  WARN {test_id} — corpus {duration:.2f}s, re-ran {tail} "
                "(over budget, did not reproduce)"
            )
        print()

    # Written on RED runs too — the summary's value peaks exactly when the
    # gate has just refused a merge.
    #
    # [r172]'s module rows are rendered HERE, not in write_step_summary,
    # because the mode is the caller's knowledge: warning-only ships (the
    # run stays green and the list is the nightly's posted evidence), the
    # fail mode reddens. Either way the list carries both sides of the
    # arithmetic per row so a reader can recompute the difference — the
    # same doctrine as the WARN rows above. The unmeasured suites are in
    # the list too: reading a truncated suite's time as 0 would silently
    # exempt the exact shape a truncated writer produces.
    module_rows: list[str] = []
    if module_breaches or module_warns or module_unmeasured:
        mode = (
            "failing — a reproduced import breach reddens this run"
            if module_fail_mode()
            else "warning-only — the run stays green"
        )
        module_rows += [
            "",
            "## Module import budget ([r172], UR-125's numbers per module)",
            "",
            f"Per-suite import cost = suite time minus testcase body times "
            f"(benchmarks added back); budget {module_budget}s hard / "
            f"{module_warn}s warn. Mode: {mode}.",
            "",
        ]
        for label in module_unmeasured:
            module_rows.append(f"- `{label}` — suite carries no time attribute; not measured")
        for cost, suite_time, body_sum, label, _modules in module_breaches:
            again = module_re_runs.get(label)
            if module_fail_mode() and again and again[0] == "confirmed":
                tail = f"re-ran {again[1]:.2f}s and breached again"
            elif module_fail_mode() and again:
                tail = "re-run not verified (not a pass)"
            else:
                tail = "warning-only"
            module_rows.append(
                f"- `{label}` — {cost:.2f}s import cost over the {module_budget}s "
                f"budget ({tail}); suite {suite_time:.2f}s, testcases {body_sum:.2f}s"
            )
        for cost, suite_time, body_sum, label, _modules in module_warns:
            module_rows.append(
                f"- `{label}` — {cost:.2f}s import cost (warn band, "
                f"{module_warn}s to {module_budget}s); suite {suite_time:.2f}s, "
                f"testcases {body_sum:.2f}s"
            )
    write_step_summary(
        warns, [(d, t) for d, t, _, _ in red], cleared, listed_elsewhere, module_rows
    )

    if red:
        print(f"BREACHES (over the hard budget): {len(red)}")
        print("-" * 40)
        for duration, test_id, category, budget in red:
            verdict = f"  BREACH {duration:.2f}s (budget: {budget}s) [{category}]"
            again = confirmed.get(test_id)
            if again:
                verdict += f" — re-ran {again[1]:.2f}s and BREACHED AGAIN"
            elif unverified.get(test_id, ("",))[0] == "skipped":
                verdict += " — re-run SKIPPED (executed nothing; not a pass)"
            elif unverified.get(test_id, ("",))[0] == "timed_out":
                verdict += " — re-run TIMED OUT (killed by the gate; not a pass)"
            elif test_id in unverified:
                code = unverified[test_id][2]
                replay = unverified[test_id][1]
                timing = f"{replay:.2f}s, " if replay is not None else ""
                verdict += f" — re-run not verified ({timing}pytest exit {code})"
            print(verdict)
            print(f"    {test_id}")
        print()
        print("=" * 70)
        notes = ""
        if unverified:
            notes = (
                f" {len(unverified)} of them could not be verified by a re-run, which is "
                "NOT a pass (UR-125 exonerates only a test that passes on its re-run)."
            )
        print(
            f"RESULT: FAIL - {len(red)} test(s) over their real-sleep budget."
            f"{notes} A seconds-scale test in a re-run tier is a real sleep: "
            "give it a fake/injected clock "
            "or make it genuinely faster. There is no file to add it to."
        )
        return 1

    if module_failed:
        # [r172]'s failing mode: a module import cost that reproduced on its
        # re-run (or a denied one — unverified is never a pass). This arm
        # only runs when the per-test verdict was green, so the RESULT line
        # says exactly what failed: the modules, not the tests.
        print("=" * 70)
        confirmed_modules = sum(1 for s, _, _ in module_re_runs.values() if s == "confirmed")
        unverified_modules = sum(1 for s, _, _ in module_re_runs.values() if s == "unverified")
        print(
            f"RESULT: FAIL - {len(module_breaches)} module(s) over their import budget."
            + (
                f" {confirmed_modules} confirmed on the module re-run; "
                f"{unverified_modules} unverified (NOT a pass — UR-125 exonerates "
                "only what a re-run exonerates)."
                if unverified_modules
                else " All confirmed on the module re-run."
            )
            + " Trim the module's import-time work (defer heavy imports, split the "
            "module) — SLOW_TEST_PATTERNS is per-test and does not take a module."
        )
        return 1

    if cleared:
        # "no test over its budget" is false here: one WAS over, and a re-run
        # is what let it through. Saying so keeps the green honest — the
        # downgrade is the point of the amendment, not a fact to hide.
        print(
            f"RESULT: PASS - nothing over budget reproduced on its re-run. "
            f"{len(cleared)} test(s) were over budget in the corpus and cleared a "
            "re-run; they are listed as warnings above."
        )
        return 0
    print("RESULT: PASS - no test over its real-sleep budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
