"""The GPU window always restores the flagship (spec §3.6, D9)."""

from __future__ import annotations

import fcntl
import inspect
import json
import os
import signal
import subprocess
import sys
from collections.abc import Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import pytest
from synthbench.generate import window as gw
from synthbench.generate.comfy import serve
from synthbench.generate.podman import podman_argv

# The signals the window defers while it restores the flagship.
EXIT_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)


class FakeRuntime:
    def __init__(
        self,
        *,
        healthy_after: int = 0,
        never_healthy: bool = False,
        stop_error: Exception | None = None,
        running: bool = True,
    ) -> None:
        self.calls: list[str] = []
        self.running = running
        self._healthy_after = healthy_after
        self._never = never_healthy
        self._stop_error = stop_error
        self._polls = 0

    def stop(self, container: str) -> None:
        self.calls.append("stop")
        if self._stop_error is not None:
            raise self._stop_error
        self.running = False

    def start(self, container: str) -> None:
        self.calls.append("start")
        self.running = True

    def is_healthy(self, container: str) -> bool:
        self.calls.append("healthy?")
        if self._never or not self.running:
            return False
        self._polls += 1
        return self._polls > self._healthy_after


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def paths(tmp_path: Path) -> gw.WindowPaths:
    return gw.WindowPaths(tmp_path / "state")


class SignalLeaked(Exception):
    """A signal reached the caller's handler while the window was restoring."""


@pytest.fixture
def trapped_signals() -> Iterator[None]:
    """Make the caller's SIGTERM/SIGHUP/SIGINT handlers raise SignalLeaked.

    A signal the window fails to defer then fails the test, instead of killing pytest
    (the SIGTERM and SIGHUP default action) or aborting the session (KeyboardInterrupt).
    """

    def trap(signum: int, _frame: object) -> None:
        raise SignalLeaked(signum)

    saved = {sig: signal.signal(sig, trap) for sig in EXIT_SIGNALS}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


def _deliver_through_the_installed_handler(signum: int) -> None:
    """Call the Python handler now installed for signum, as CPython does when it arrives."""
    handler = signal.getsignal(signum)
    assert callable(handler)
    handler(signum, None)


def _window(
    rt: FakeRuntime, paths: gw.WindowPaths, clock: FakeClock | None = None, **kw: Any
) -> AbstractContextManager[None]:
    """The window with fakes; `before_restore` defaults to a no-op, never the real podman."""
    fake = clock or FakeClock()
    kw.setdefault("before_restore", lambda: None)
    return gw.gpu_window(rt, paths, sleep=fake.sleep, clock=fake, say=lambda _m: None, **kw)


class TestWindowPaths:
    def test_state_lives_under_synthbench_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("SYNTHBENCH_ROOT", str(tmp_path))
        wp = gw.WindowPaths.from_env()
        assert (wp.marker, wp.lock) == (
            tmp_path / "state/window.open",
            tmp_path / "state/window.lock",
        )
        monkeypatch.delenv("SYNTHBENCH_ROOT")
        assert gw.WindowPaths.from_env().state_dir == Path("/export/synthbench/state")


class TestGpuWindow:
    def test_stops_runs_and_restores_in_order(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime()
        seen: list[tuple[bool, bool]] = []
        with _window(rt, paths):
            seen.append((rt.running, paths.marker.exists()))
        assert seen == [(False, True)]
        assert rt.calls == ["stop", "start", "healthy?"]
        assert not paths.marker.exists()

    def test_the_marker_records_the_container(self, paths: gw.WindowPaths) -> None:
        with _window(FakeRuntime(), paths):
            assert json.loads(paths.marker.read_text())["container"] == gw.FLAGSHIP

    def test_a_body_error_still_restores(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime()
        with pytest.raises(ValueError, match="boom"), _window(rt, paths):
            raise ValueError("boom")
        assert rt.running and not paths.marker.exists()

    def test_ctrl_c_still_restores(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime()
        with pytest.raises(KeyboardInterrupt), _window(rt, paths):
            raise KeyboardInterrupt
        assert rt.running

    @pytest.mark.usefixtures("trapped_signals")
    def test_sigterm_still_restores_and_the_old_handler_returns(
        self, paths: gw.WindowPaths
    ) -> None:
        rt = FakeRuntime()
        before = signal.getsignal(signal.SIGTERM)
        with pytest.raises(SystemExit) as exc, _window(rt, paths):
            os.kill(os.getpid(), signal.SIGTERM)
        assert exc.value.code == 128 + signal.SIGTERM
        assert rt.running
        assert signal.getsignal(signal.SIGTERM) == before

    @pytest.mark.usefixtures("trapped_signals")
    def test_a_sighup_still_restores_and_the_old_handlers_return(
        self, paths: gw.WindowPaths
    ) -> None:
        # A terminal or SSH hangup (uv forwards SIGHUP to its child) must not end the
        # window with the flagship down.
        rt = FakeRuntime()
        caller = {sig: signal.getsignal(sig) for sig in EXIT_SIGNALS}
        with pytest.raises(SystemExit) as exc, _window(rt, paths):
            os.kill(os.getpid(), signal.SIGHUP)
        assert exc.value.code == 128 + signal.SIGHUP
        assert rt.calls == ["stop", "start", "healthy?"]
        assert rt.running and not paths.marker.exists()
        assert {sig: signal.getsignal(sig) for sig in caller} == caller

    def test_a_failed_stop_still_starts_the_flagship(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime(stop_error=RuntimeError("docker stop failed"))
        with pytest.raises(RuntimeError, match="docker stop failed"), _window(rt, paths):
            pass
        assert "start" in rt.calls

    def test_waits_for_healthy(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime(healthy_after=3)
        clock = FakeClock()
        with _window(rt, paths, clock=clock, poll_s=15.0):
            pass
        assert clock.now == 45.0

    def test_a_restore_timeout_keeps_the_marker(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime(never_healthy=True)
        with (
            pytest.raises(gw.FlagshipNotRestored),
            _window(rt, paths, timeout_s=60.0, poll_s=15.0),
        ):
            pass
        assert paths.marker.exists()

    def test_a_leftover_marker_restores_before_stopping(self, paths: gw.WindowPaths) -> None:
        paths.state_dir.mkdir(parents=True)
        paths.marker.write_text("{}")
        rt = FakeRuntime(running=False)
        with _window(rt, paths):
            pass
        assert rt.calls.index("start") < rt.calls.index("stop")

    def test_a_busy_lock_refuses_without_touching_the_flagship(self, paths: gw.WindowPaths) -> None:
        paths.state_dir.mkdir(parents=True)
        fd = os.open(paths.lock, os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            rt = FakeRuntime()
            with pytest.raises(gw.WindowBusy), _window(rt, paths):
                pass
            assert rt.calls == []
        finally:
            os.close(fd)

    def test_before_restore_runs_before_the_flagship_starts(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime()
        with (
            pytest.raises(ValueError, match="x"),
            _window(rt, paths, before_restore=lambda: rt.calls.append("hook")),
        ):
            raise ValueError("x")
        assert rt.calls.index("hook") < rt.calls.index("start")

    @pytest.mark.usefixtures("trapped_signals")
    def test_a_sigterm_during_before_restore_waits_for_the_flagship(
        self, paths: gw.WindowPaths
    ) -> None:
        rt = FakeRuntime()
        caller = {sig: signal.getsignal(sig) for sig in EXIT_SIGNALS}
        with (
            pytest.raises(SystemExit) as exc,
            _window(rt, paths, before_restore=lambda: os.kill(os.getpid(), signal.SIGTERM)),
        ):
            pass
        assert exc.value.code == 128 + signal.SIGTERM
        assert rt.calls == ["stop", "start", "healthy?"]
        assert rt.running and not paths.marker.exists()
        assert {sig: signal.getsignal(sig) for sig in caller} == caller

    @pytest.mark.usefixtures("trapped_signals")
    @pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGHUP], ids=["SIGINT", "SIGHUP"])
    def test_a_sigint_or_sighup_while_restoring_waits_for_the_flagship(
        self, paths: gw.WindowPaths, signum: int
    ) -> None:
        class InterruptedStart(FakeRuntime):
            def start(self, container: str) -> None:
                _deliver_through_the_installed_handler(signum)
                super().start(container)

        rt = InterruptedStart()
        caller = {sig: signal.getsignal(sig) for sig in EXIT_SIGNALS}
        with pytest.raises(SystemExit) as exc, _window(rt, paths):
            pass
        assert exc.value.code == 128 + signum
        assert rt.calls == ["stop", "start", "healthy?"]
        assert rt.running and not paths.marker.exists()
        assert {sig: signal.getsignal(sig) for sig in caller} == caller

    @pytest.mark.usefixtures("trapped_signals")
    def test_a_signal_during_the_leftover_restore_does_not_abort_it(
        self, paths: gw.WindowPaths
    ) -> None:
        class InterruptedStart(FakeRuntime):
            def start(self, container: str) -> None:
                os.kill(os.getpid(), signal.SIGTERM)
                super().start(container)

        paths.state_dir.mkdir(parents=True)
        paths.marker.write_text("{}")
        rt = InterruptedStart(running=False)
        caller = {sig: signal.getsignal(sig) for sig in EXIT_SIGNALS}
        opened = False
        with pytest.raises(SystemExit) as exc, _window(rt, paths):
            opened = True
        assert exc.value.code == 128 + signal.SIGTERM
        assert rt.calls == ["start", "healthy?"]
        assert rt.running and not paths.marker.exists()
        assert not opened
        assert {sig: signal.getsignal(sig) for sig in caller} == caller

    def test_a_broken_log_pipe_still_restores(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime()
        closing = False

        def say(message: str) -> None:  # `... |& tee log`, and tee died with the Ctrl-C
            nonlocal closing
            closing = closing or message.startswith("closing")
            if closing:
                raise BrokenPipeError

        clock = FakeClock()
        with gw.gpu_window(
            rt, paths, before_restore=lambda: None, sleep=clock.sleep, clock=clock, say=say
        ):
            pass
        assert closing
        assert "start" in rt.calls
        assert rt.running and not paths.marker.exists()

    def test_a_stop_that_lands_after_the_first_start_is_started_again(
        self, paths: gw.WindowPaths
    ) -> None:
        class LateStop(FakeRuntime):
            """Ctrl-C kills the `docker stop` CLI, but dockerd finishes the stop anyway:
            the first start is a no-op on the still-running container, then it stops."""

            stop_pending = False

            def stop(self, container: str) -> None:
                self.calls.append("stop")
                self.stop_pending = True
                raise KeyboardInterrupt

            def start(self, container: str) -> None:
                if self.stop_pending:
                    self.calls.append("start")
                    self.stop_pending = False
                    self.running = False
                    return
                super().start(container)

        rt = LateStop()
        with pytest.raises(KeyboardInterrupt), _window(rt, paths):
            pass
        assert rt.calls == ["stop", "start", "healthy?", "start", "healthy?"]
        assert rt.running and not paths.marker.exists()

    def test_the_gpu_containers_are_stopped_by_default(self) -> None:
        # A later caller of the context manager must not restore the flagship with the
        # renderer still resident.
        default = inspect.signature(gw.gpu_window).parameters["before_restore"].default
        assert default is gw.stop_gpu_containers


class TestRestore:
    def test_a_failed_reissued_start_is_logged_and_the_wait_goes_on(self) -> None:
        class BlipOnSecondStart(FakeRuntime):
            starts = 0

            def start(self, container: str) -> None:
                self.starts += 1
                if self.starts == 2:  # dockerd blips while the flagship comes up
                    self.calls.append("start failed")
                    raise subprocess.CalledProcessError(
                        1, ["docker", "start"], stderr=b"Cannot connect to the Docker daemon\n"
                    )
                super().start(container)

        rt = BlipOnSecondStart(healthy_after=2)
        clock = FakeClock()
        said: list[str] = []
        gw.restore(rt, sleep=clock.sleep, clock=clock, say=said.append)
        assert rt.calls == ["start", "healthy?", "start failed", "healthy?", "start", "healthy?"]
        assert rt.running
        assert len(said) == 1 and "Cannot connect to the Docker daemon" in said[0]

    def test_a_failed_first_start_still_raises(self) -> None:
        class NoDaemon(FakeRuntime):
            def start(self, container: str) -> None:
                self.calls.append("start")
                raise subprocess.CalledProcessError(1, ["docker", "start"])

        rt = NoDaemon()
        clock = FakeClock()
        with pytest.raises(subprocess.CalledProcessError):
            gw.restore(rt, sleep=clock.sleep, clock=clock, say=lambda _m: None)
        assert rt.calls == ["start"]


class FakePodman:
    """Stands in for subprocess.run: each `ps` takes the next of `listings`; `stop` answers
    `stop`. An answer is (returncode, stdout, stderr), or an exception to raise."""

    def __init__(
        self,
        *listings: tuple[int, str, str] | Exception,
        stop: tuple[int, str, str] | Exception = (0, "", ""),
    ) -> None:
        self.calls: list[list[str]] = []
        self._listings = iter(listings)
        self._stop = stop

    def __call__(self, argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        answer = next(self._listings) if "ps" in argv else self._stop
        if isinstance(answer, Exception):
            raise answer
        return subprocess.CompletedProcess(argv, *answer)


class TestStopGpuContainers:
    def test_lists_stops_and_lists_again_in_the_synthbench_store(self) -> None:
        run = FakePodman((0, "abc\n", ""), (0, "", ""))
        said: list[str] = []
        gw.stop_gpu_containers(run=run, say=said.append)
        prefix = podman_argv()
        listing = [*prefix, "ps", "-q", "--filter", gw.GPU_LABEL_FILTER]
        assert run.calls == [listing, [*prefix, "stop", "--time", "30", "abc"], listing]
        assert said == []

    def test_nothing_running_is_one_quiet_listing(self) -> None:
        run = FakePodman((0, "", ""))
        said: list[str] = []
        gw.stop_gpu_containers(run=run, say=said.append)
        assert len(run.calls) == 1 and said == []

    def test_a_failed_listing_is_logged_with_its_exit_code_and_stderr(self) -> None:
        said: list[str] = []
        gw.stop_gpu_containers(
            run=FakePodman((125, "", "Error: database is locked\n")), say=said.append
        )
        assert len(said) == 1 and "125" in said[0] and "database is locked" in said[0]

    def test_a_listing_that_raises_is_logged_and_never_raises(self) -> None:
        said: list[str] = []
        hung = subprocess.TimeoutExpired(["podman", "ps"], 30)
        gw.stop_gpu_containers(run=FakePodman(hung), say=said.append)
        assert len(said) == 1 and "TimeoutExpired" in said[0]

    @pytest.mark.parametrize(
        "stop",
        [(125, "", "Error: container abc: timed out\n"), OSError("podman: not found")],
        ids=["exit 125", "raises"],
    )
    def test_a_failed_stop_is_logged_and_the_survivor_named(
        self, stop: tuple[int, str, str] | Exception
    ) -> None:
        run = FakePodman((0, "abc\n", ""), (0, "abc\n", ""), stop=stop)
        said: list[str] = []
        gw.stop_gpu_containers(run=run, say=said.append)
        assert len(run.calls) == 3
        assert len(said) == 2
        assert "abc" in said[0] and ("125" in said[0] or "not found" in said[0])
        assert "still running" in said[1] and "abc" in said[1]

    def test_a_broken_log_never_raises(self) -> None:
        def say(_message: str) -> None:
            raise BrokenPipeError

        gw.stop_gpu_containers(run=FakePodman((125, "", "Error: x\n")), say=say)

    def test_the_filter_matches_the_label_serve_puts_on_the_renderer(self) -> None:
        assert f"label={serve.GPU_LABEL}" == gw.GPU_LABEL_FILTER


class TestMain:
    def test_run_returns_the_child_exit_code(self, paths: gw.WindowPaths) -> None:
        rt = FakeRuntime()
        code = gw.main(
            ["run", "--", sys.executable, "-c", "import sys; sys.exit(3)"],
            runtime=rt,
            paths=paths,
            before_restore=lambda: None,
        )
        assert code == 3
        assert rt.calls[:2] == ["stop", "start"]

    def test_run_without_a_command_is_a_usage_error(self, paths: gw.WindowPaths) -> None:
        with pytest.raises(SystemExit):
            gw.main(["run"], runtime=FakeRuntime(), paths=paths)

    def test_status_prints_marker_and_health(
        self, paths: gw.WindowPaths, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert gw.main(["status"], runtime=FakeRuntime(), paths=paths) == 0
        assert json.loads(capsys.readouterr().out) == {"marker": False, "flagship_healthy": True}

    def test_restore_clears_the_marker(self, paths: gw.WindowPaths) -> None:
        paths.state_dir.mkdir(parents=True)
        paths.marker.write_text("{}")
        rt = FakeRuntime(running=False)
        assert gw.main(["restore"], runtime=rt, paths=paths) == 0
        assert rt.calls == ["start", "healthy?"]
        assert not paths.marker.exists()

    def test_restore_refuses_while_a_live_window_holds_the_lock(
        self, paths: gw.WindowPaths, capsys: pytest.CaptureFixture[str]
    ) -> None:
        paths.state_dir.mkdir(parents=True)
        paths.marker.write_text("{}")
        fd = os.open(paths.lock, os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            rt = FakeRuntime(running=False)
            assert gw.main(["restore"], runtime=rt, paths=paths) != 0
            assert rt.calls == []
            assert paths.marker.exists()
            assert "refusing to restore" in capsys.readouterr().err
        finally:
            os.close(fd)
