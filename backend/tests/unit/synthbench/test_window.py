"""The GPU window always restores the flagship (spec §3.6, D9)."""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import sys
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import pytest
from synthbench.generate import window as gw
from synthbench.generate.podman import podman_argv


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


def _window(
    rt: FakeRuntime, paths: gw.WindowPaths, clock: FakeClock | None = None, **kw: Any
) -> AbstractContextManager[None]:
    fake = clock or FakeClock()
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


class TestStopGpuContainers:
    def test_lists_and_stops_labeled_containers_in_the_synthbench_store(self) -> None:
        calls: list[list[str]] = []

        def run(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, "abc\n" if "ps" in argv else "", "")

        gw.stop_gpu_containers(run=run)
        prefix = podman_argv()
        assert calls == [
            [*prefix, "ps", "-q", "--filter", gw.GPU_LABEL_FILTER],
            [*prefix, "stop", "--time", "30", "abc"],
        ]


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
        assert gw.main(["restore"], runtime=FakeRuntime(running=False), paths=paths) == 0
        assert not paths.marker.exists()
