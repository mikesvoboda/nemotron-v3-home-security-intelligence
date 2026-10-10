"""Tests for scripts/check-test-coverage-gate.py (WP6-branch, CI flake parity).

The gate's inline full-unit collection run (the no-seam branch of
check_coverage_diff) was the ONLY full-tier pytest invocation in CI without
the repo's rerun convention, so pytest-timeout flakes on -n 8 CI load failed
the required Test Coverage Gate with no real regression (three occurrences on
#6560's stack, each time a DIFFERENT test, all green locally and in the shard
jobs which carry --reruns 2 --reruns-delay 5, ci.yml:675,797).

These tests inspect the script's AST, not its behavior: the collection
subprocess is CI-only glue, and what we are pinning is the argv it builds.
"""

import ast
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "check-test-coverage-gate.py"


def _check_coverage_diff_func() -> ast.FunctionDef:
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    return next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "check_coverage_diff"
    )


def _inline_collection_call() -> ast.Call:
    """The subprocess call node inside check_coverage_diff running pytest -
    the inline full-unit collection. Matches subprocess.run OR Popen: the
    shipped wrapper uses Popen+communicate because run()'s own timeout path
    kills only the DIRECT child and then drains the pipes - an orphaned
    pytest/xdist worker (uv's grandchild) holding stdout open blocks that
    drain, turning a "bounded" step back into a hang (measured 2026-10-10:
    un-wrapped, the fake hung collector returned after the FULL 40s with a
    silent rc-based message)."""
    for node in ast.walk(_check_coverage_diff_func()):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("run", "Popen")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.args
            and isinstance(node.args[0], ast.List)
        ):
            argv = [
                elt.value
                for elt in node.args[0].elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            ]
            if "pytest" in argv:
                return node
    raise AssertionError("no subprocess run/Popen([...pytest...]) call in check_coverage_diff")


def _inline_collection_argv() -> list[str]:
    """argv elements of the inline collection call (see _inline_collection_call)."""
    node = _inline_collection_call()
    return [
        elt.value
        for elt in node.args[0].elts
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
    ]


def test_inline_collection_carries_rerun_parity() -> None:
    """The gate's inline collection matches the shard jobs' rerun convention.

    Extraction is not enforcement (--cov-fail-under=0 already documents
    that): a flake-retry here moves no floor and gates nothing weaker - it
    only stops a 5-second signal-timeout on an unrelated test from reddening
    the required gate.
    """
    argv = _inline_collection_argv()
    assert "--reruns" in argv, (
        "inline collection must carry --reruns like the shard jobs "
        "(ci.yml:675,797): three gate reds on #6560 were pytest-timeout "
        "flakes in THIS subprocess, each a different test"
    )
    assert "--reruns-delay" in argv, "with --reruns-delay, matching the shard convention exactly"
    # the flags must come as separate argv tokens AND carry values
    assert argv[argv.index("--reruns") + 1] == "2"
    assert argv[argv.index("--reruns-delay") + 1] == "5"


def test_inline_collection_still_extraction_only() -> None:
    """Parity fix must not silently turn collection into enforcement."""
    argv = _inline_collection_argv()
    assert "--cov-fail-under=0" in argv, (
        "collection EXISTS to extract the seam number; enforcement belongs "
        "to the shard jobs' floors, not here"
    )


# ---------------------------------------------------------------------------
# R72: the fall-through collection gets a timeout wrapper.
#
# Owner ruling 72 (2026-10-10): "A run that hits the limit fails with a
# message naming the step and the limit; it never passes silently."
# MEASURE (GitHub Actions steps API, 12 success-only runs of the
# "Check test coverage requirements" step on 2026-10-10): median 463 s,
# max 495 s, min 321 s. DECIDE: 900 s = ~1.8x the observed max. The job
# has NO timeout-minutes, so today a hung collection burns the 6 h runner
# default — the 2026-10-10 #6969 incident (inline collection died with a
# pytest INTERNALERROR rc=3) is the sibling failure mode: this step has
# died before; it must die LOUDLY and BOUNDED, never silently or forever.
#
# The kill must take the whole process group (uv spawns pytest as a
# grandchild). Measured 2026-10-10 against a direct-kill-only scratch
# mutant: a bounded second drain keeps the RETURN time bounded anyway
# (returned at ~31s: 1s limit + 30s drain), with the correct named
# message — but the orphaned collector stays ALIVE on the runner for its
# full lifetime (a runaway ~27.5k-test pytest burning CI minutes after
# the gate already gave up). Message pins cannot see that; the process-
# existence pin below can, and it is the production guarantee. The fake
# uv spawns its grandchild under a unique env token so the pin can grep
# exactly it.
# ---------------------------------------------------------------------------


def test_inline_collection_call_carries_a_timeout() -> None:
    """R72 pin: the collection subprocess cannot run unbounded.

    The timeout may sit on the spawn call (subprocess.run(timeout=N)) or on
    the pipe drain (Popen + communicate(timeout=N)) - the shipped form is
    the latter, because run()'s timeout kills only the direct child and
    then drains pipes an orphaned grandchild still holds (see
    test_timeout_path_fails_loudly_and_kills_the_group). What the pin
    refuses either way: an unbounded spawn.
    """
    node = _inline_collection_call()
    limit_expr = next(
        (k.value for k in node.keywords if k.arg == "timeout"),
        None,
    )
    if limit_expr is None:
        assert node.func.attr == "Popen", (
            f"spawn method {node.func.attr} without timeout= is unbounded"
        )
        # Popen shape: the bound must be on a .communicate(timeout=...) in
        # the same function, else the Popen is just as unbounded.
        limit_expr = next(
            (
                k.value
                for n in ast.walk(_check_coverage_diff_func())
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "communicate"
                for k in n.keywords
                if k.arg == "timeout"
            ),
            None,
        )
        assert limit_expr is not None, (
            "ruling 72: Popen without communicate(timeout=...) is the "
            "unbounded shape this pin exists to refuse"
        )
    assert "collect_timeout" in ast.dump(limit_expr).lower() or (
        isinstance(limit_expr, ast.Constant) and limit_expr.value >= 600
    ), (
        "the limit must trace to the MEASURE-decided constant (900s: median "
        "463s / max 495s over 12 success-only runs) - a tight literal "
        "manufactures reds on loaded runners"
    )
    src = _SCRIPT.read_text(encoding="utf-8")
    assert "TimeoutExpired" in src, (
        "hitting the limit must be caught and turned into a named failure, "
        "not an uncaught exception (that reddens with a traceback, not the "
        "step+limit message the ruling requires)"
    )


def _orphan_probe_alive(token: str) -> bool:
    """True while a sh process carrying `token` in its command line lives.

    /proc scan, no ps(1) dependency: every /proc/<pid>/cmdline for our own
    uid contains the token only while the fake collector's grandchild (or
    its timeout(1) parent) is alive. Reaped/zombie processes are excluded —
    a zombie is already dead, just unwaited.
    """
    proc_root = Path("/proc")
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        # entry.name came from the /proc listing filtered to digits: no
        # component here is user-controlled, the traversal this rule warns
        # about is structurally impossible.
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
            if token not in cmd:
                continue
            # field 3 of /proc/<pid>/stat is the state; Z = zombie = dead
            # but unreaped (the killed group's members before init reaps).
            state = (entry / "stat").read_text().rsplit(") ", 1)[1].split()[0]
            if state != "Z":
                return True
        except OSError:
            continue  # raced with exit / not ours to read
    return False


class TestR72TimeoutWrapper:
    """Behavior: a collection that outlives the limit fails LOUDLY —
    message names the step and the limit — and never passes silently.

    Env override COVERAGE_GATE_COLLECT_TIMEOUT is the seam that makes the
    path testable in seconds instead of 900 (also an operator knob for a
    deliberately slow experiment); the constant 900 is the shipped default.
    """

    @staticmethod
    def _gate(tmp_path, monkeypatch, uv_body: str, limit: str):
        import os

        gate = _load_gate(tmp_path)
        bin_ = tmp_path / "bin"
        bin_.mkdir()
        uv = bin_ / "uv"
        uv.write_text(f"#!/bin/sh\n{uv_body}\n")
        uv.chmod(0o755)
        base = tmp_path / "base.json"
        base.write_text('{"percent_covered": 90.0}')
        monkeypatch.setenv("COVERAGE_BASE_JSON", str(base))
        monkeypatch.delenv("COVERAGE_JSON", raising=False)
        monkeypatch.setenv("COVERAGE_GATE_COLLECT_TIMEOUT", limit)
        monkeypatch.setenv("PATH", f"{bin_}:{os.environ['PATH']}")
        monkeypatch.chdir(tmp_path)  # no ./coverage.json seam exists
        return gate

    @pytest.mark.timeout(
        60
    )  # marker beats addopts (measured 2026-10-10); red run waits out the fake
    def test_timeout_path_fails_loudly_and_kills_the_group(self, tmp_path, monkeypatch) -> None:
        """Fake uv: spawns a pipe-holding grandchild and never exits. The
        timeout must (a) fail with a message naming step + limit, and (b)
        leave NO orphaned collector alive — the group kill."""
        import time
        import uuid

        token = f"r72orphan-{uuid.uuid4().hex[:12]}"
        # Fake uv: spawns the loop as a background child (same process
        # group, exactly like uv spawning pytest) and waits. NO timeout(1)
        # wrapper here — measured 2026-10-10: GNU timeout re-groups the
        # monitored command, so the loop would sit OUTSIDE the killable
        # group and the orphan pin would pass vacuously. The loop
        # self-limits to ~25s instead, so a red run of THIS test cannot
        # litter the machine. The token sits INSIDE the -c string (as the
        # loop's own comment): uv's argv never contains it, so the probe
        # greps exactly the grandchild and nothing else — and `#` outside
        # the quotes would comment out the `&` and break the backgrounding.
        hang_uv = (
            f"sh -c 'end=$(( $(date +%s) + 25 )); "
            f"while [ $(date +%s) -lt $end ]; do sleep 0.2; done  # {token}' & wait\n"
        )
        gate = self._gate(tmp_path, monkeypatch, hang_uv, "1")
        t0 = time.monotonic()
        ok, msg = gate.check_coverage_diff(base_branch="unused-base")
        elapsed = time.monotonic() - t0
        assert ok is False, f"timed-out collection must fail the gate, got: {msg}"
        assert "timed out" in msg.lower(), f"message must name the timeout class, got: {msg}"
        assert "1s" in msg or "1 s" in msg, f"message must name the LIMIT, got: {msg}"
        assert "pytest" in msg.lower(), f"message must name the STEP, got: {msg}"
        assert not (tmp_path / "coverage.json").exists()
        # The production guarantee the message pins cannot express: no
        # runaway collector left burning runner minutes after the gate
        # gave up. (Measured: a direct-kill-only mutant passes ALL the
        # message assertions and leaks the grandchild alive.)
        deadline = time.monotonic() + 5.0
        while _orphan_probe_alive(token) and time.monotonic() < deadline:
            time.sleep(0.1)  # grace for SIGTERM delivery
        assert not _orphan_probe_alive(token), (
            f"the collector outlived the timeout: the wrapper killed only its "
            f"direct child and left the grandchild alive (returned in "
            f"{elapsed:.1f}s with the right message — loud but leaky)"
        )

    @pytest.mark.timeout(60)
    def test_sigterm_trapping_collector_is_escalated_to_sigkill(
        self, tmp_path, monkeypatch
    ) -> None:
        """Self-review nit 1 (2026-10-10): the escalation must not hinge on
        the DIRECT child ignoring SIGTERM.

        uv's own disposition is to die on TERM; the SIGTERM-ignoring hang
        class is the GRANDCHILD (a pytest worker mid-C-call, a trap-holding
        shell). With the shipped wrapper the direct child's prompt death
        makes `proc.wait()` return immediately, the wait-timeout-gated
        SIGKILL never fires, and the second drain just gives up at 10 s:
        loud, bounded, and leaky — the orphan lives its full life (measured
        by the reviewer: return at 11.01 s, orphan dead 29.2 s later). This
        fake traps TERM in the grandchild and holds the pipes, exactly the
        nit-1 shape; the guarantee "no runaway collector" must still hold.
        """
        import time
        import uuid

        token = f"r72term-{uuid.uuid4().hex[:12]}"
        # trap '' TERM inside the -c string: group SIGTERM bounces off the
        # grandchild; fake uv itself keeps default disposition (dies), so
        # proc.wait() returns promptly and the wait-gated escalation cannot
        # fire. 25 s self-limit keeps a RED run from littering the machine.
        hang_uv = (
            f'sh -c \'trap "" TERM; end=$(( $(date +%s) + 25 )); '
            f"while [ $(date +%s) -lt $end ]; do sleep 0.2; done  # {token}' & wait\n"
        )
        gate = self._gate(tmp_path, monkeypatch, hang_uv, "1")
        ok, msg = gate.check_coverage_diff(base_branch="unused-base")
        assert ok is False and "timed out" in msg.lower(), msg
        deadline = time.monotonic() + 5.0
        while _orphan_probe_alive(token) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not _orphan_probe_alive(token), (
            "the wrapper escalated to SIGKILL only when the DIRECT child "
            "ignored TERM; uv does not ignore it, so a TERM-trapping "
            "collector outlived the gate (the ruling-72 production "
            "guarantee, missed for its likeliest hang class)"
        )

    @pytest.mark.timeout(60)
    def test_sigterm_trapping_collector_that_released_the_pipes_is_killed(
        self, tmp_path, monkeypatch
    ) -> None:
        """The discriminating case between "SIGKILL when the drain times
        out" and "escalate unconditionally": a TERM-trapping grandchild
        that REDIRECTED its own output (pytest writing reports to disk does
        exactly this) closes the pipes, so the second drain returns in
        milliseconds, never times out, and a drain-timeout-gated SIGKILL
        never fires. The runaway lives with nothing left to even delay the
        gate. Escalation must be unconditional after the group SIGTERM,
        addressed by numeric pgid (== proc.pid under start_new_session,
        still valid after the group leader is reaped; os.getpgid fails
        post-reap — the reviewer measured both)."""
        import time
        import uuid

        token = f"r72free-{uuid.uuid4().hex[:12]}"
        hang_uv = (
            f'sh -c \'trap "" TERM; end=$(( $(date +%s) + 25 )); '
            f"while [ $(date +%s) -lt $end ]; do sleep 0.2; done  # {token}' "
            f">/dev/null 2>&1 & wait\n"
        )
        gate = self._gate(tmp_path, monkeypatch, hang_uv, "1")
        t0 = time.monotonic()
        ok, msg = gate.check_coverage_diff(base_branch="unused-base")
        assert ok is False and "timed out" in msg.lower(), msg
        # the gate itself comes back promptly — the leak is invisible to any
        # message/timing assertion; only the process probe sees it.
        assert time.monotonic() - t0 < 8.0, "a released-pipe drain must not stall"
        deadline = time.monotonic() + 5.0
        while _orphan_probe_alive(token) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not _orphan_probe_alive(token), (
            "TERM-trapping collector that released the pipes outlived the "
            "gate: the drain returned clean, no drain-timeout fired, and "
            "the escalation never ran"
        )

    @pytest.mark.timeout(60)
    def test_timeout_message_carries_the_partial_output_tail(self, tmp_path, monkeypatch) -> None:
        """Nit 2: TimeoutExpired.output carries what WAS read (bytes, even
        under text=True — measured), and the slow-drain case is exactly
        where the operator needs it: the collector's last words before it
        wedged. The shipped branch discarded them (`stdout, stderr = "",
        ""`), so `Tail:` was empty precisely when it mattered.

        Shape note that makes this a real probe: the discard is only
        reachable when the SECOND drain also times out, which needs the
        grandchild to survive the group SIGTERM (trap) and still hold the
        pipes. With a default-disposition loop the drain returns the output
        and the test would pass without the fix — the same vacuous-green
        trap this file already documents for timeout(1)."""
        # (named noise_marker, not token-with-a-SECRET-shaped-value:
        # semgrep's hardcoded-password rule fires on NAME + SHAPE, not
        # on the content actually being a credential)
        noise_marker = "collect-partial-output-noise"
        hang_uv = (
            f"printf 'NOISE-{noise_marker}\\n'; "
            f'sh -c \'trap "" TERM; end=$(( $(date +%s) + 20 )); '
            f"while [ $(date +%s) -lt $end ]; do sleep 0.2; done' & wait\n"
        )
        gate = self._gate(tmp_path, monkeypatch, hang_uv, "1")
        ok, msg = gate.check_coverage_diff(base_branch="unused-base")
        assert ok is False and "timed out" in msg.lower(), msg
        assert noise_marker in msg, (
            f"Tail must carry the partial output the timeout already read "
            f"(TimeoutExpired.output, decoded); got: {msg!r}"
        )

    @pytest.mark.timeout(60)
    def test_fast_collection_still_flows_under_the_wrapper(self, tmp_path, monkeypatch) -> None:
        """The wrapper must not break the normal path: fake uv writes the
        coverage file and exits 0 -> the gate diffs normally (80 < 90 -> a
        real drop verdict, not a timeout message)."""
        gate = self._gate(
            tmp_path,
            monkeypatch,
            'echo \'{"totals": {"percent_covered": 80.0}}\' > coverage.json; exit 0',
            "30",
        )
        ok, msg = gate.check_coverage_diff(base_branch="unused-base")
        assert "timed out" not in msg.lower(), msg
        assert ok is False and "80" in msg, (
            f"normal collection under the wrapper must still produce the "
            f"drop verdict (80 vs base 90), got: ({ok}, {msg})"
        )

    def test_default_limit_is_the_measured_decision(self) -> None:
        """The shipped default is the DECIDE half of ruling 72, pinned to
        the MEASURE: 900 s, recorded with its census in the PR body."""
        src = _SCRIPT.read_text(encoding="utf-8")
        assert "COLLECT_TIMEOUT_SECONDS = 900" in src, (
            "900s = ~1.8x the measured max 495s over 12 success-only runs; "
            "changing the limit is a re-measurement, not a tweak"
        )


def _load_gate(root: Path):
    """Load the gate script as if it LIVED at `root/scripts/`.

    `find_test_file` computes `project_root` from the module's own `__file__`,
    so the honest way to test it against a fixture tree is to place the real
    script in a tmp tree and import that copy - the code under test is
    byte-identical and nothing about path resolution is faked. (Monkeypatching
    the module's `Path` would have redirected `Path(source_file)` but not
    `Path(__file__)`, so the tree it probed would have been the real repo and
    the test would pass or fail for reasons unrelated to the finder.)
    """
    import importlib.util

    script_dir = root / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    copy = script_dir / "check-test-coverage-gate.py"
    copy.write_text(_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("covgate_copy", copy)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestFindTestFileFrontend:
    """`find_test_file` resolved a frontend source to ONE candidate name -
    `<stem>.test` + the source's own suffix - so a `.ts` hook whose suite
    lives at `<stem>.test.tsx` read as "Tests: None found" and the required
    Test Coverage Gate failed the PR for OBEYING it.

    That is not a hypothetical: `frontend/src/hooks/useTopEventsQuery.ts` has
    its suite at `useTopEventsQuery.test.tsx` (a JSX `<QueryClientProvider>`
    wrapper at :47 makes `.ts` genuinely invalid, so the extension is not a
    mistake to "fix" by renaming), and `d1e279fd`'s stack of frontend fixes
    made the hook a substantial change, which is what surfaced it. The
    directory uses BOTH extensions today (see `useAlerts.test.tsx` beside
    `useAlertsQuery.test.ts`), so the finder - not the corpus - is wrong.

    Behavior tests, unlike the AST pins above, because the thing that broke
    is a runtime path-existence decision the AST cannot express.
    """

    def test_ts_source_with_only_a_tsx_suite_resolves(self, tmp_path) -> None:
        gate = _load_gate(tmp_path)
        hooks = tmp_path / "frontend" / "src" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "useThing.ts").write_text("export const useThing = () => null\n")
        (hooks / "useThing.test.tsx").write_text("import {x} from './useThing'\n")
        found = gate.find_test_file("frontend/src/hooks/useThing.ts")
        assert found == "frontend/src/hooks/useThing.test.tsx", (
            "a .ts source with a .tsx suite IS tested; None here is the "
            "false-missing that reddened Test Coverage Gate on #6681"
        )

    def test_tsx_source_with_only_a_ts_suite_resolves(self, tmp_path) -> None:
        """The mirror case, so the fix is a rule and not one file's patch."""
        gate = _load_gate(tmp_path)
        comps = tmp_path / "frontend" / "src" / "components"
        comps.mkdir(parents=True)
        (comps / "Thing.tsx").write_text("export const Thing = () => null\n")
        (comps / "Thing.test.ts").write_text("import {Thing} from './Thing'\n")
        assert gate.find_test_file("frontend/src/components/Thing.tsx") == (
            "frontend/src/components/Thing.test.ts"
        )

    def test_no_suite_at_all_still_returns_none(self, tmp_path) -> None:
        """The gate must keep catching a genuinely untested file - a finder
        that always finds something is a neutered gate, the same vacuous-green
        class this repo refuses everywhere else."""
        gate = _load_gate(tmp_path)
        hooks = tmp_path / "frontend" / "src" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "Untested.ts").write_text("export const x = 1\n")
        assert gate.find_test_file("frontend/src/hooks/Untested.ts") is None

    def test_the_shipped_hook_that_reddened_the_gate_resolves(self) -> None:
        """The real file, against the real tree - the pin that fails if either
        the finder regresses or the corpus renames the suite back to a
        non-matching extension."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("covgate", _SCRIPT)
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        assert gate.find_test_file("frontend/src/hooks/useTopEventsQuery.ts") == (
            "frontend/src/hooks/useTopEventsQuery.test.tsx"
        )
