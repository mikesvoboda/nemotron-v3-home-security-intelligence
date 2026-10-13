"""Test hygiene: no test may assert a schedule-window outcome against a LIVE clock.

ABOUTME: The 2026-10-11 23:59 UTC red. `Backend Unit Tests (4/4)` failed
`test_alert_engine.py::test_schedule_matches` -- not because #7016 broke it, but
because the test asserts `matches is True` for the "all day" schedule
`{"start_time": "00:00", "end_time": "23:59"}` while feeding `_evaluate_rule` a
live `datetime.now(UTC)`. `_parse_time("23:59")` returns `time(23, 59)` == 23:59:00
(`alert_engine.py:960`), and `_check_schedule` compares at that resolution
(`:949 start_time <= current_time_only <= end_time`), so 23:59:01..23:59:59 UTC is a
DEAD MINUTE: 59 seconds every day where this test is red no matter what shipped. The
run's own verdict line was stamped 23:59:01Z. Two sibling tests passed by 46 s and
13 s -- three coin flips that happened to land two ways, not two clean tests.

The class, stated structurally so the guard needs no exception list:

    a test that (a) supplies a schedule WINDOW the engine can parse AND
                  (b) lets a LIVE clock reach the evaluation (passes datetime.now()/
                      utc_now_naive(), or omits current_time so the engine substitutes
                      utc_now_naive() at alert_engine.py:188 / :1143)

is clock-dependent, and because the engine compares at one-minute resolution NO
window covers a whole day -- so (a)+(b) is ALWAYS fragile, never merely unlucky. The
fix is the house idiom already used 11 times in the same file at the base commit: pass a FIXED
`current_time` (e.g. `datetime(2025, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))`), or
pass the battery's `CT` constant.

Why an AST scan and not a grep for "datetime.now". Two hazards, both live here:
  - `datetime.now()` is CORRECT in a test that asserts log/recency freshness or stamps
    a fixture; only its arrival at a SCHEDULE evaluation is the defect. Grepping the
    call would flag the correct uses too and train everyone to ignore the wolf (same
    reasoning as scripts/test_workflow_uv_hygiene.py's dependency-aware guard 2).
  - the clock usually arrives INDIRECTLY -- sites 2 and 3 pass no clock at all; they
    omit `current_time` and the engine's `if current_time is None` default injects the
    live one. A grep for `datetime.now` sees neither. So the guard tracks, per call,
    whether the engine will use a live clock, not whether the test wrote the word.

Attribution differs by method because the RULE arrives differently: `_evaluate_rule`
and `test_rule_against_events` take the rule as a real argument (per-CALL: was THAT
call's rule given a window?), while `evaluate_event` loads rules from the mocked
session -- the rule never appears at the call site -- so its attribution is
per-FUNCTION (does this test set up ANY schedule-bearing rule?). Coarser for
`evaluate_event` by necessity; the whole-suite scan named at the end of this docstring
measured it at zero false positives, and a per-function false positive would be the
correct time to care anyway. Where the rule IS an argument the attribution is finer,
and `test_attribution_is_per_call_when_the_rule_is_an_argument` enforces that.

Red-first at this branch's base 31b3e08ea (the linenos below are that commit's): the
scanner flags exactly three calls --
test_alert_engine.py:1029, :1839 and test_alert_engine_batch38_ae.py:1250 -- the
three the 23:59 red exposed. After pinning all three: 0 offenders.

KNOWN LIMIT -- 0 offenders means "no test spells it this way", not "impossible". The
rule reads literal syntax, so a defect escapes when either half arrives indirectly: the
CLOCK through a variable/helper/fixture (`t = datetime.now(UTC)`, then pass `t`), or the
SCHEDULE through a helper-built rule or a post-hoc `.update()`. Widening it to real
dataflow was weighed and not done here: a partial tracker false-positives on the many
legitimate live-clock uses the two hazards above name, and a guard that cries wolf is a
guard people mute -- the exact failure this file cites from
scripts/test_workflow_uv_hygiene.py. So the ratchet holds the line at the spelled form,
which is the form all three real defects took, and the residual is stated rather than
papered over. Raised as reviewer finding R4 on #7017.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TESTS = REPO_ROOT / "backend" / "tests"

# Methods that consult a rule's schedule using a `current_time` the caller controls.
# value = (positional index of the time argument in the BOUND (self-less) call,
#          whether the rule -- the thing carrying the schedule -- is itself an argument,
#          whether that time argument is REQUIRED).
# These are three independent facts and were conflated once: _evaluate_rule's
# current_time is required (its omission is a TypeError, not a live clock) while both
# other methods default it to None and substitute utc_now_naive() -- so for THEM an
# omitted argument is exactly the defect, not a reason to skip.
# test_rule_against_events' rule IS arg0 (rule, events, current_time=None): treating it
# as per-function would flag the schedule-free rule(id=5) call that sits beside the
# schedule-bearing one in the same battery test.
SCHEDULE_METHODS: dict[str, tuple[int, bool, bool]] = {
    "_evaluate_rule": (3, True, True),  # (rule, event, detections, current_time)
    "evaluate_event": (2, False, False),  # (event, detections, current_time=None)
    "test_rule_against_events": (2, True, False),  # (rule, events, current_time=None)
}
LIVE_CLOCKS = {"datetime.now", "datetime.utcnow", "utc_now_naive", "utc_now"}
# HH:MM or HH:MM:SS -- the shape _check_schedule actually compares (see the regex
# caveat on _parseable_window for why "the shape the engine parses" is NOT the right
# rule here, and why this one over-flags on purpose).
# A non-time value like "invalid" must not be flagged, but NOT for the reason an
# earlier draft of this file gave: it does not make _check_schedule return False. It
# raises inside _parse_time, and the except at alert_engine.py:954 RETURNS True at
# :956 -- "if parsing fails, allow the rule" -- so the window is active at EVERY
# instant. Same for a half-window: :941 requires BOTH bounds, so a lone start_time
# skips the comparison and falls through to :958 `return True`. Unparseable and
# half-open windows are therefore clock-INDEPENDENT (always active), which is why the
# scanner stays quiet about them; the quiet is right, the old stated reason was
# backwards. Witness in the repo already: test_alert_engine_batch38_ae.py:967 asserts
# _check_schedule({"start_time": "90:00", "end_time": "17:00"}, ...) IS True.
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")


def _qualified(node: ast.expr) -> str:
    """Dotted name for an attribute/name chain, else ''."""
    if isinstance(node, ast.Attribute):
        base = _qualified(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _is_live_clock(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Call) and _qualified(node.func) in LIVE_CLOCKS


def _parseable_window(node: ast.expr) -> bool:
    """True if this schedule dict constrains WHEN the rule is active, in a way the
    engine acts on: a parseable start_time/end_time pair, or a NON-EMPTY `days` list.

    A `days` list is a window too, and a wider-open one: `_check_schedule:933` looks
    up `DAY_NAMES[local_time.weekday()]`, so `{"days": ["saturday"]}` evaluated at a
    live clock is red on six days a week -- worse than the 59-second-a-day case that
    motivated this file. `{"days": []}` fails the `if days and len(days) > 0` guard at
    `:932` and so constrains nothing (documented all-days), and must stay quiet: that
    empty-days shape is what the dead-minute fix pins site 3 to.

    KNOWN OVER-FLAG, kept on purpose: this gate keys on `_TIME_RE`, which is NOT
    `_parse_time` equivalence. `24:00` and `90:00` match the regex but `time()`
    rejects them, so such a window is always-active (see the `_TIME_RE` comment above)
    and can never be clock-dependent -- yet a literal of that shape AT A LIVE CLOCK
    would be flagged. Relaxing the gate to `_parse_time` equivalence is the wrong fix:
    the class this file prevents is a test reading a schedule outcome off an unpinned
    clock, and a test that does that with a garbage bound is still the bad test even
    though its verdict happens to be deterministic. A false positive here costs a
    one-line pin; a false negative costs a silent 23:59 red for whoever didn't write
    it. No live instance today: the one `90:00` literal (batch38_ae.py:968) sits at a
    FIXED clock, so the scanner does not fire on it."""
    if not isinstance(node, ast.Dict):
        return False
    for key, val in zip(node.keys, node.values, strict=False):
        if not isinstance(key, ast.Constant):
            continue
        if key.value in {"start_time", "end_time"}:
            if (
                isinstance(val, ast.Constant)
                and isinstance(val.value, str)
                and _TIME_RE.match(val.value)
            ):
                return True
        elif key.value == "days":
            if isinstance(val, ast.List) and val.elts:
                return True
    return False


def _test_functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and node.name.startswith(
            "test_"
        ):
            yield node


def _window_assignments(fn: ast.FunctionDef) -> set[str]:
    """Names carrying a parseable schedule in this test, via `x.schedule = {...}` or a
    direct `name = {...}` binding (the fixture pattern `rule = AlertRule(...,
    schedule={...})` is covered by the inline-kwarg scan separately)."""
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and _parseable_window(node.value):
            for tgt in node.targets:
                if isinstance(tgt, ast.Attribute) and tgt.attr == "schedule":
                    names.add(_qualified(tgt.value))
                elif isinstance(tgt, ast.Name):
                    names.add(tgt.id)
    return names


def _window_in_this_test(fn: ast.FunctionDef, sched_names: set[str]) -> bool:
    """Does this test set up a parseable schedule window anywhere -- a tracked name,
    an inline rule(schedule={...}), or a bare schedule kwarg?"""
    if sched_names:
        return True
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            if any(kw.arg == "schedule" and _parseable_window(kw.value) for kw in node.keywords):
                return True
    return False


def _rule_carries_window(node: ast.Call, sched_names: set[str]) -> bool:
    """Per-call: is THIS call's rule argument schedule-bearing -- an inline
    rule(schedule={parseable}) call, or a NAME the test gave a .schedule to?"""
    rule_arg = (
        node.args[0]
        if node.args
        else next((k.value for k in node.keywords if k.arg == "rule"), None)
    )
    if isinstance(rule_arg, ast.Call):
        return any(kw.arg == "schedule" and _parseable_window(kw.value) for kw in rule_arg.keywords)
    if isinstance(rule_arg, ast.Name):
        return _qualified(rule_arg) in sched_names
    return False


def clock_dependent_schedule_calls(tree: ast.AST) -> list[tuple[int, str]]:
    """(lineno, reason) for each test call that evaluates a schedule window at a live clock."""
    hits: list[tuple[int, str]] = []
    for fn in _test_functions(tree):
        sched_names = _window_assignments(fn)
        window_in_fn = _window_in_this_test(fn, sched_names)
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            method = SCHEDULE_METHODS.get(node.func.attr)
            if method is None:
                continue
            time_index, per_call_rule, time_required = method
            # gate (a): does the evaluated rule carry a parseable window?
            if per_call_rule:
                if not _rule_carries_window(node, sched_names):
                    continue
            elif not window_in_fn:  # evaluate_event: rule comes from the session
                continue
            # gate (b): does a live clock reach the evaluation?
            kw = {k.arg: k.value for k in node.keywords}
            time_arg = kw.get("current_time")
            if time_arg is None and len(node.args) > time_index:
                time_arg = node.args[time_index]
            if time_arg is None:
                if time_required:  # a required argument can't be omitted at runtime
                    continue
                hits.append(
                    (
                        node.lineno,
                        f"{node.func.attr}: current_time omitted -> engine uses utc_now_naive()",
                    )
                )
            elif _is_live_clock(time_arg):
                hits.append((node.lineno, f"{node.func.attr}: live clock passed explicitly"))
    return hits


def _candidate_files(root: Path | None = None) -> list[Path]:
    """backend/tests/**/test_*.py that could host the class, chosen by a cheap text
    prefilter so the guard parses a handful of files, not 1135.

    The prefilter is load-bearing, not a speed nicety: the naive unfiltered scan
    (parse AND walk the whole suite inside one test) measured 5.8s on the junit clock,
    which breaches BOTH the 4.0s UNIT_TEST_THRESHOLD the Test Performance Audit
    enforces per test (the audit reads junit per-testcase duration, so setup+call+
    teardown) AND the hard 5s per-test timeout (pyproject.toml:546, owner ruling
    2026-09-14) -- it gets killed mid-scan. A bare parse of the suite is only ~2.6s,
    so it is the walk, not the parse, that pushes past the limit. Guard cost WITH the
    prefilter: the slowest of this file's tests is ~1.5s per testcase (worst measured
    ~1.8s cold), comfortably under 4.0s.

    This prefilter MUST stay a strict superset of what the AST rule can flag, and its
    trigger list therefore has to move in lockstep with gate (a): a flagged file
    necessarily mentions a schedule key that constrains when the rule is active --
    'start_time'/'end_time' OR 'days' -- plus a schedule-consuming method name. When
    gate (a) learned that a non-empty `days` list is a window, 'days' and 'end_time'
    had to join here too, or a day-only schedule in a file that never spells
    'start_time' would go unscanned and the guard would read green while the class it
    exists to prevent sat right there. Measured cost of the wider net: 8 candidate
    files, 0.044s to parse (the narrow net's 5 files are a subset).

    `root` is injectable so a control can plant a days-only file the real tree cannot
    hold (see test_the_prefilter_selects_a_days_only_file); the ratchet passes nothing
    and still scans the real backend/tests."""
    out: list[Path] = []
    for path in (root if root is not None else TESTS).rglob("test_*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError, OSError:
            continue
        if not any(k in text for k in ("start_time", "end_time", "days")):
            continue
        if not any(m in text for m in SCHEDULE_METHODS):
            continue
        out.append(path)
    return out


# ---------------------------------------------------------------- guards for the guard


def test_the_scanner_scans_something() -> None:
    """If the path moved, the scan matches nothing and the suite passes for the wrong
    reason. Assert the prefilter still reaches a plausible candidate set."""
    cands = _candidate_files()
    assert len(cands) >= 3, f"prefilter found only {len(cands)} files under {TESTS} — path moved?"


def test_the_scanner_fires_on_the_real_shape() -> None:
    """Positive control A. A scanner that never fires and a clean tree look identical."""
    sample = (
        "async def test_x():\n"
        "    rule.schedule = {'start_time': '00:00', 'end_time': '23:59'}\n"
        "    await engine._evaluate_rule(rule, event, detections, datetime.now(UTC))\n"
    )
    hits = clock_dependent_schedule_calls(ast.parse(sample))
    assert len(hits) == 1 and hits[0][1].endswith("live clock passed explicitly"), hits


def test_the_scanner_fires_on_an_omitted_clock() -> None:
    """Positive control B — the indirect case (sites 2 and 3): no datetime.now in the
    source at all."""
    sample = (
        "async def test_y():\n"
        "    rule = make_rule(schedule={'start_time': '00:00', 'end_time': '23:59'})\n"
        "    await engine.evaluate_event(event, detections)\n"
    )
    hits = clock_dependent_schedule_calls(ast.parse(sample))
    assert len(hits) == 1 and "omitted" in hits[0][1], hits


def test_the_scanner_stays_quiet_when_the_clock_is_pinned() -> None:
    """Negative control A: same window, fixed time -> not flagged."""
    sample = (
        "async def test_z():\n"
        "    rule.schedule = {'start_time': '00:00', 'end_time': '23:59'}\n"
        "    await engine._evaluate_rule(rule, event, detections, datetime(2025, 1, 6, 12, 0, 0))\n"
    )
    assert clock_dependent_schedule_calls(ast.parse(sample)) == []


def test_the_scanner_stays_quiet_without_a_window() -> None:
    """Negative control B: a live clock reaching a call with no schedule -> the
    correct, unflagged use (asserting freshness, not a schedule outcome)."""
    sample = (
        "async def test_w():\n"
        "    rule.object_types = ['car']\n"
        "    await engine._evaluate_rule(rule, event, detections, datetime.now(UTC))\n"
    )
    assert clock_dependent_schedule_calls(ast.parse(sample)) == []


def test_the_scanner_fires_on_a_day_only_window() -> None:
    """Positive control C: a `days` schedule is a window too, and at a live clock it
    is red SIX days a week -- a worse version of the bug that motivated this file.
    (Measured: {"days": ["saturday"]} -> True only on Saturday, False on all six
    other days.)"""
    sample = (
        "async def test_d():\n"
        "    rule = make_rule(schedule={'days': ['saturday']})\n"
        "    await engine.evaluate_event(event, detections)\n"
    )
    hits = clock_dependent_schedule_calls(ast.parse(sample))
    assert len(hits) == 1 and "omitted" in hits[0][1], hits


def test_the_scanner_stays_quiet_on_an_empty_days_list() -> None:
    """Negative control D: {"days": []} is the documented all-days case -- it
    constrains nothing, so a live clock reaching it is harmless. This is also exactly
    the shape test_test_rule_against_events_rounds was pinned to, so if this control
    ever goes red the fix that removed the dead minute becomes un-landable."""
    sample = (
        "async def test_c():\n"
        "    rule = make_rule(schedule={'days': []})\n"
        "    await engine.test_rule_against_events(rule, events)\n"
    )
    assert clock_dependent_schedule_calls(ast.parse(sample)) == []


def test_the_scanner_ignores_an_unparseable_window() -> None:
    """Negative control C: {'start_time': 'invalid'} is not clock-dependent -> not
    flagged. NOT because the engine rejects the window -- it allows it at every
    instant (`:954` except returns True at `:956`) -- but because an always-active
    window cannot go red at a boundary. Cf. test_alert_engine.py::
    test_handles_rule_evaluation_error, which sets exactly this shape and asserts the
    rule still runs; named, not cited by line number, because this very file's line
    drift moved the number an earlier draft gave."""
    sample = (
        "async def test_v():\n"
        "    rule.schedule = {'start_time': 'invalid'}\n"
        "    await engine.evaluate_event(event, detections)\n"
    )
    assert clock_dependent_schedule_calls(ast.parse(sample)) == []


def test_a_required_time_argument_beats_a_window() -> None:
    """Negative control E: gate (b)'s `time_required` flag is load-bearing.
    _evaluate_rule's current_time has NO default (alert_engine.py:437), so omitting it
    is a TypeError -- the call never runs, so no live clock can reach it and there is
    nothing to pin. Dropping the flag (the M8 mutation, time_required True->False)
    makes this red: it would flag a call that crashes instead of a clock dependency,
    and a ratchet that cries wolf here is a ratchet people learn to ignore."""
    sample = (
        "async def test_r():\n"
        "    rule.schedule = {'start_time': '00:00', 'end_time': '23:59'}\n"
        "    await engine._evaluate_rule(rule, event, detections)\n"
    )
    assert clock_dependent_schedule_calls(ast.parse(sample)) == []


def test_attribution_is_per_call_when_the_rule_is_an_argument() -> None:
    """Positive control E: for a per-CALL method the window must come from THIS call's
    rule. test_rule_against_events' battery calls it twice, schedule-bearing rule(id=6)
    then schedule-free rule(id=5); per-function attribution (the M9 mutation) would
    report both. The offender set must stay {the one line}, or the guard would flag the
    very call that documents why per-call attribution is there."""
    # Same inline-call shape the real battery uses (batch38_ae.py:1228 schedule-free,
    # :1255 schedule-bearing), so this control tests the attribution, not a shape only
    # this file invents.
    sample = (
        "async def test_b():\n"
        "    await engine.test_rule_against_events(rule(id=5, object_types=['car']), events)\n"
        "    await engine.test_rule_against_events(\n"
        "        rule(id=6, schedule={'start_time': '00:00', 'end_time': '23:59'}), events)\n"
    )
    hits = clock_dependent_schedule_calls(ast.parse(sample))
    assert [ln for ln, _ in hits] == [3], hits


def test_the_prefilter_selects_a_days_only_file(tmp_path: Path) -> None:
    """The prefilter's stated invariant -- a strict superset of what the AST rule can
    flag -- was prose-only, and nothing tested it (M11: narrow the net to 'start_time'
    and the guard reads GREEN with a day-only live-clock defect sitting in
    backend/tests/). It is only checkable against a synthetic file: no real candidate
    is days-only, because gate (a) already keeps every days-only live-clock call out of
    the tree -- a planted one would red the ratchet the moment it landed and could not
    be committed. So the scan root is injected. What is under test is the substring
    net, not the repo's contents.

    Both halves are load-bearing. Without the first assertion the file could be one the
    AST rule ignores anyway, and 'the net selected it' would prove nothing; without the
    second, a net that selected EVERYTHING would pass, which is the cost side of the
    same invariant."""
    offender = (
        "async def test_days_only():\n"
        "    rule = make_rule(schedule={'days': ['saturday']})\n"
        "    await engine.evaluate_event(event, detections)\n"
    )
    # Half 1: the fixture IS a defect the AST rule flags -- so the net MUST see it.
    assert len(clock_dependent_schedule_calls(ast.parse(offender))) == 1
    (tmp_path / "test_days_only.py").write_text(offender, encoding="utf-8")
    # A file that spells a trigger word but has no schedule method: out of the net, and
    # staying out of it is the cost side of the superset claim.
    (tmp_path / "test_benign.py").write_text(
        "def test_benign():\n    assert 'days' in {'days': 1}\n", encoding="utf-8"
    )
    # A file with the method but no schedule key: also correctly out.
    (tmp_path / "test_no_window.py").write_text(
        "async def test_nw():\n    await engine.evaluate_event(event, detections)\n",
        encoding="utf-8",
    )
    picked = {p.name for p in _candidate_files(tmp_path)}
    assert picked == {"test_days_only.py"}, picked


# ---------------------------------------------------------------- the ratchet itself


def test_no_test_asserts_a_schedule_window_at_a_live_clock() -> None:
    offenders: list[str] = []
    for path in _candidate_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, reason in clock_dependent_schedule_calls(tree):
            offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}  {reason}")
    assert not offenders, (
        f"{len(offenders)} schedule-window assertion(s) run against a live clock — a "
        "59-second-a-day window in which they are red for reasons nobody shipped "
        "(2026-10-11 23:59 red). Pin current_time to a fixed datetime / CT:\n  "
        + "\n  ".join(sorted(offenders))
    )
