"""The flagship guard (agent-driven design §1, §5.1).

Every 5 s it checks the flagship vLLM and writes status/flagship.json (time, healthy, running,
waiting). After 3 failed checks in a row it stops the renderer, so a flagship that crashed beside
it can boot again. It never stops or starts the flagship. While an owner GPU window
(synthbench.generate.window) holds the flagship down on purpose, the guard keeps probing and
writing status, but never stops the renderer: the window may be running it itself.

    python -m synthbench.host.guard            # the synthbench-guard unit
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from synthbench.generate.comfy import serve
from synthbench.generate.window import WindowPaths
from synthbench.status import FlagshipStatus, flagship_file, write_status

FLAGSHIP_URL = "http://127.0.0.1:8000"
INTERVAL_S = 5.0
FAILURES_TO_STOP = 3
RENDERER_UNIT = "synthbench-renderer.service"  # host.units.RENDERER reuses this

Runner = Callable[..., subprocess.CompletedProcess[str]]
_METRIC = re.compile(r"^(vllm:num_requests_(?:running|waiting))(?:\{[^}]*\})?\s+(\S+)")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _say(message: str) -> None:
    sys.stderr.write(f"[synthbench-guard] {message}\n")


def _window_open() -> bool:
    """True while an owner GPU window holds the flagship down on purpose (window.py's marker)."""
    return WindowPaths.from_env().marker.exists()


def parse_metrics(text: str) -> tuple[int, int]:
    """(running, waiting) summed over every engine, from vLLM's /metrics."""
    totals: dict[str, float] = {}
    for line in text.splitlines():
        if found := _METRIC.match(line):
            totals[found.group(1)] = totals.get(found.group(1), 0.0) + float(found.group(2))
    wanted = ("vllm:num_requests_running", "vllm:num_requests_waiting")
    if missing := [name for name in wanted if name not in totals]:
        raise ValueError(f"/metrics has no {', '.join(missing)}")
    return int(totals[wanted[0]]), int(totals[wanted[1]])


def probe(url: str, get: Callable[..., httpx.Response]) -> tuple[bool, int | None, int | None]:
    """(healthy, running, waiting); healthy needs /health 200 and readable request metrics."""
    try:
        health = get(f"{url}/health", timeout=3.0)
        metrics = get(f"{url}/metrics", timeout=3.0)
    except httpx.HTTPError:
        return False, None, None
    if health.status_code != 200 or metrics.status_code != 200:
        return False, None, None
    try:
        running, waiting = parse_metrics(metrics.text)
    except ValueError:
        return False, None, None
    return True, running, waiting


def stop_renderer(run: Runner = subprocess.run, *, say: Callable[[str], None] = _say) -> None:
    """Stop the renderer unit; clear whatever it leaves behind, without racing its own cleanup.

    `container_alive` (mere existence) is not enough to gate a second `podman stop`: it is True
    for a container stuck in podman's Removing state too, and a stop there is what exited 125
    live and got it stuck. The unit's own ExecStopPost (`serve cleanup`) removes a stopped
    leftover; this is the guard's fallback for the rest, e.g. a renderer started by hand, outside
    the unit. So this keys on `serve.container_running` instead:

    - systemctl failed (raised, timed out or exited non-zero): fall back to `serve.stop`, as
      before this container-state distinction — a bad systemctl gives no information about the
      container.
    - systemctl succeeded and the container is running (started by hand, or the running check
      itself could not tell and stayed conservative): `serve.stop` can still signal it.
    - systemctl succeeded and the container exists but is not running (podman's Removing state,
      which systemd's default KillMode caused before the unit set KillMode=mixed, or a leftover
      from a crash): `stop` has nothing left to signal, so `serve.force_remove`
      (`podman rm -f --ignore`) clears it directly instead.

    Never raises: a stuck or missing systemctl, a failed running check, or a podman failure in
    the stop or force-remove fallback, is logged through `say` instead, so a bad stop never
    crashes the guard.
    """
    systemctl_ok = False
    try:
        done = run(
            ["systemctl", "--user", "stop", RENDERER_UNIT],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.SubprocessError, OSError) as error:
        say(f"systemctl --user stop {RENDERER_UNIT} failed: {error}")
    else:
        if done.returncode != 0:
            say(
                f"systemctl --user stop {RENDERER_UNIT} exited {done.returncode}: "
                f"{(done.stderr or '').strip()}"
            )
        else:
            systemctl_ok = True

    if not systemctl_ok:
        try:
            serve.stop(run)
        except (subprocess.SubprocessError, OSError) as error:
            say(f"podman stop {serve.CONTAINER} failed: {error}")
        return

    try:
        running = serve.container_running(run)
    except (subprocess.SubprocessError, OSError) as error:
        say(f"podman container inspect {serve.CONTAINER} failed: {error}")
        running = True  # conservative: assume it still needs a graceful stop

    if running:
        try:
            serve.stop(run)
        except (subprocess.SubprocessError, OSError) as error:
            say(f"podman stop {serve.CONTAINER} failed: {error}")
        return

    try:
        serve.force_remove(run)
    except (subprocess.SubprocessError, OSError) as error:
        say(f"podman rm -f {serve.CONTAINER} failed: {error}")


class Guard:
    def __init__(
        self,
        status_file: Path,
        *,
        url: str = FLAGSHIP_URL,
        get: Callable[..., httpx.Response] = httpx.get,
        stop_renderer: Callable[[], None] = stop_renderer,
        window_open: Callable[[], bool] = _window_open,
        now: Callable[[], datetime] = _utc_now,
        say: Callable[[str], None] = _say,
    ) -> None:
        self.status_file = status_file
        self.url = url
        self.get = get
        self.stop_renderer = stop_renderer
        self.window_open = window_open
        self.now = now
        self.say = say
        self.failures = 0
        self.stopped = False
        self.window_warned = False

    def tick(self) -> FlagshipStatus:
        healthy, running, waiting = probe(self.url, self.get)
        self.failures = 0 if healthy else self.failures + 1
        status = FlagshipStatus(
            time=self.now(),
            healthy=healthy,
            running=running,
            waiting=waiting,
            failures=self.failures,
        )
        try:
            write_status(self.status_file, status)  # before any stop: render yields at once
        except OSError as error:
            self.say(f"cannot write {self.status_file}: {error}")
        if healthy:
            if self.stopped:
                self.say(
                    "flagship healthy again; the renderer stays stopped until the owner starts it"
                )
            self.stopped = False
            self.window_warned = False
            return status
        if self.window_open():
            # window.py stopped the flagship on purpose and may run the renderer itself;
            # the guard still probes and writes status (so `render` yields), but never stops it.
            if not self.window_warned:
                self.say("a GPU window is open: the guard leaves the renderer alone")
                self.window_warned = True
            return status
        self.window_warned = False
        if self.failures >= FAILURES_TO_STOP and not self.stopped:
            self.say(
                f"flagship failed {self.failures} health checks in a row: stopping the renderer"
            )
            self.stop_renderer()
            self.stopped = True
        return status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.host.guard")
    parser.add_argument("--flagship-url", default=FLAGSHIP_URL)
    parser.add_argument("--status-file", type=Path, default=None)
    parser.add_argument(
        "--ticks", type=int, default=0, help="stop after this many checks (0: never)"
    )
    args = parser.parse_args(argv)
    guard = Guard(args.status_file or flagship_file(), url=args.flagship_url)
    _say(f"watching {args.flagship_url}; status file {guard.status_file}")
    ticks = 0
    while True:
        guard.tick()
        ticks += 1
        if args.ticks and ticks >= args.ticks:
            return 0
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    sys.exit(main())
