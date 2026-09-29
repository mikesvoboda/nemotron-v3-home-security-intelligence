"""The flagship guard (agent-driven design §1, §5.1): status file, and the renderer stop."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from synthbench.host.guard import Guard, parse_metrics, stop_renderer
from synthbench.status import FlagshipStatus, read_status

from backend.tests.unit.synthbench import helpers as h

METRICS = """# HELP vllm:num_requests_running Number of requests in model execution batches.
vllm:num_requests_running{engine="0",model_name="claude-flagship"} 3.0
vllm:num_requests_waiting{engine="0",model_name="claude-flagship"} 2.0
vllm:num_requests_waiting_by_reason{engine="0",model_name="claude-flagship",reason="capacity"} 7.0
"""


class FakeFlagship:
    def __init__(self) -> None:
        self.healthy = True
        self.urls: list[str] = []

    def get(self, url: str, timeout: float) -> httpx.Response:
        self.urls.append(url)
        if not self.healthy:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200, text=METRICS if url.endswith("/metrics") else "")


def _guard(
    tmp_path: Path,
    flagship: FakeFlagship,
    stops: list[int],
    *,
    window_open: Callable[[], bool] = lambda: False,
    say: Callable[[str], None] = lambda _message: None,
) -> Guard:
    return Guard(
        tmp_path / "flagship.json",
        get=flagship.get,
        stop_renderer=lambda: stops.append(1),
        window_open=window_open,
        now=lambda: h.NOW,
        say=say,
    )


def test_metrics_sum_every_engine_and_skip_the_by_reason_series() -> None:
    assert parse_metrics(METRICS) == (3, 2)
    assert parse_metrics(METRICS + 'vllm:num_requests_running{engine="1"} 4.0\n') == (7, 2)
    assert parse_metrics("vllm:num_requests_running 1\nvllm:num_requests_waiting 0\n") == (1, 0)
    with pytest.raises(ValueError, match="num_requests_waiting"):
        parse_metrics("vllm:num_requests_running 1\n")


def test_each_tick_writes_the_status_file(tmp_path: Path) -> None:
    flagship, stops = FakeFlagship(), []
    status = _guard(tmp_path, flagship, stops).tick()
    assert (status.healthy, status.running, status.waiting, status.failures) == (True, 3, 2, 0)
    assert read_status(tmp_path / "flagship.json", FlagshipStatus) == status
    assert flagship.urls == ["http://127.0.0.1:8000/health", "http://127.0.0.1:8000/metrics"]


def test_three_failed_checks_in_a_row_stop_the_renderer_once_per_outage(tmp_path: Path) -> None:
    flagship, stops = FakeFlagship(), []
    guard = _guard(tmp_path, flagship, stops)
    flagship.healthy = False
    guard.tick()
    guard.tick()
    assert stops == []
    assert guard.tick().failures == 3
    assert stops == [1]
    guard.tick()
    assert stops == [1]
    flagship.healthy = True
    assert guard.tick().failures == 0
    flagship.healthy = False
    for _ in range(3):
        guard.tick()
    assert stops == [1, 1]


@pytest.mark.parametrize(
    "answer",
    [
        lambda url: (
            httpx.Response(503) if url.endswith("/health") else httpx.Response(200, text=METRICS)
        ),
        lambda _url: httpx.Response(200, text="garbage"),
    ],
    ids=["health-503", "no-metrics"],
)
def test_a_bad_answer_counts_as_unhealthy(
    tmp_path: Path, answer: Callable[[str], httpx.Response]
) -> None:
    guard = Guard(
        tmp_path / "flagship.json",
        get=lambda url, **_kw: answer(url),
        stop_renderer=lambda: None,
        window_open=lambda: False,
        now=lambda: h.NOW,
        say=lambda _message: None,
    )
    status = guard.tick()
    assert (status.healthy, status.running, status.failures) == (False, None, 1)


_EXISTS = ["container", "exists", "synthbench-comfyui"]
_INSPECT = ["container", "inspect", "-f", "{{.State.Running}}", "synthbench-comfyui"]
_STOP = ["--ignore", "--time", "30", "synthbench-comfyui"]
_RM = ["rm", "-f", "--ignore", "synthbench-comfyui"]


def test_stop_renderer_force_removes_a_leftover_that_is_not_running() -> None:
    """Systemctl succeeded but the container survived, not running (podman's Removing state:
    systemd's SIGTERM interrupted podman run --rm's own cleanup). `stop` has nothing left to
    signal, so the fallback force-removes it directly instead of racing another stop."""
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[-3:] == _EXISTS:
            return subprocess.CompletedProcess(argv, 0, "", "")  # exists
        if argv[-5:] == _INSPECT:
            return subprocess.CompletedProcess(argv, 0, "false\n", "")  # not running
        return subprocess.CompletedProcess(argv, 0, "", "")

    stop_renderer(run)
    assert calls[0] == ["systemctl", "--user", "stop", "synthbench-renderer.service"]
    assert calls[1][-3:] == _EXISTS
    assert calls[2][-5:] == _INSPECT
    assert calls[3][-4:] == _RM
    assert len(calls) == 4  # serve.stop never ran: nothing left to stop


def test_stop_renderer_stops_a_container_still_running_after_systemctl() -> None:
    """A renderer container started by hand, outside the unit, still gets a graceful stop."""
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[-3:] == _EXISTS:
            return subprocess.CompletedProcess(argv, 0, "", "")  # exists
        if argv[-5:] == _INSPECT:
            return subprocess.CompletedProcess(argv, 0, "true\n", "")  # still running
        return subprocess.CompletedProcess(argv, 0, "", "")

    stop_renderer(run)
    assert calls[0] == ["systemctl", "--user", "stop", "synthbench-renderer.service"]
    assert calls[1][-3:] == _EXISTS
    assert calls[2][-5:] == _INSPECT
    assert calls[3][-4:] == _STOP


def test_stop_renderer_stops_conservatively_when_the_running_check_fails() -> None:
    """systemctl succeeded and the container exists, but podman's own inspect call is broken:
    stay conservative (assume it might still be running) and fall back to a graceful stop
    rather than force-removing blind."""
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[0] == "systemctl":
            return subprocess.CompletedProcess(argv, 0, "", "")  # systemctl succeeds
        if argv[-3:] == _EXISTS:
            return subprocess.CompletedProcess(argv, 0, "", "")  # exists
        if argv[-5:] == _INSPECT:
            raise OSError("podman: too many open files")  # the running check itself breaks
        return subprocess.CompletedProcess(argv, 0, "", "")  # the serve.stop fallback succeeds

    messages: list[str] = []
    stop_renderer(run, say=messages.append)  # must not raise
    assert calls[0] == ["systemctl", "--user", "stop", "synthbench-renderer.service"]
    assert calls[1][-3:] == _EXISTS
    assert calls[2][-5:] == _INSPECT
    assert calls[3][-4:] == _STOP
    assert len(calls) == 4
    assert any("too many open files" in message for message in messages)


def test_stop_renderer_logs_a_non_zero_systemctl_exit_instead_of_dropping_it() -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[0] == "systemctl":
            return subprocess.CompletedProcess(argv, 1, "", "Unit not loaded.\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    messages: list[str] = []
    stop_renderer(run, say=messages.append)
    assert any("Unit not loaded" in message for message in messages)
    assert calls[1][-4:] == _STOP  # a failed systemctl still falls back to serve.stop


def test_stop_renderer_survives_a_systemctl_timeout_and_still_runs_serve_stop() -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[0] == "systemctl":
            raise subprocess.TimeoutExpired(argv, 120)
        return subprocess.CompletedProcess(argv, 0, "", "")

    messages: list[str] = []
    stop_renderer(run, say=messages.append)  # must not raise
    assert calls[0][0] == "systemctl"
    assert calls[1][-4:] == ["--ignore", "--time", "30", "synthbench-comfyui"]
    assert any("systemctl" in message for message in messages)


def test_a_failed_status_write_does_not_stop_the_guard_from_tripping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import synthbench.host.guard as guard_module

    def raising_write_status(path: Path, model: FlagshipStatus) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(guard_module, "write_status", raising_write_status)
    flagship, stops = FakeFlagship(), []
    flagship.healthy = False
    messages: list[str] = []
    guard = _guard(tmp_path, flagship, stops, say=messages.append)
    guard.tick()
    guard.tick()
    status = guard.tick()
    assert status.failures == 3
    assert stops == [1]
    assert any("disk full" in message for message in messages)


def test_while_a_gpu_window_is_open_the_guard_leaves_the_renderer_alone(tmp_path: Path) -> None:
    flagship, stops = FakeFlagship(), []
    flagship.healthy = False
    messages: list[str] = []
    guard = _guard(tmp_path, flagship, stops, window_open=lambda: True, say=messages.append)
    for _ in range(5):
        status = guard.tick()
    assert stops == []
    assert status.healthy is False
    assert read_status(tmp_path / "flagship.json", FlagshipStatus).healthy is False
    # said once, not every tick
    assert messages.count("a GPU window is open: the guard leaves the renderer alone") == 1


def test_the_stop_resumes_once_the_window_closes(tmp_path: Path) -> None:
    flagship, stops = FakeFlagship(), []
    flagship.healthy = False
    window_open = [True]
    guard = _guard(tmp_path, flagship, stops, window_open=lambda: window_open[0])
    for _ in range(3):
        guard.tick()
    assert stops == []
    window_open[0] = False
    guard.tick()
    assert stops == [1]
