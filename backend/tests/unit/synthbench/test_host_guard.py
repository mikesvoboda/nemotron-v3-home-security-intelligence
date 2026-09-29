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


def _guard(tmp_path: Path, flagship: FakeFlagship, stops: list[int]) -> Guard:
    return Guard(
        tmp_path / "flagship.json",
        get=flagship.get,
        stop_renderer=lambda: stops.append(1),
        now=lambda: h.NOW,
        say=lambda _message: None,
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
        now=lambda: h.NOW,
        say=lambda _message: None,
    )
    status = guard.tick()
    assert (status.healthy, status.running, status.failures) == (False, None, 1)


def test_stop_renderer_stops_the_unit_then_any_hand_started_container() -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    stop_renderer(run)
    assert calls[0] == ["systemctl", "--user", "stop", "synthbench-renderer.service"]
    assert calls[1][-4:] == ["--ignore", "--time", "30", "synthbench-comfyui"]
