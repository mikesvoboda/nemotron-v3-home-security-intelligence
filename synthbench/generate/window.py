"""The GPU window (spec §3.6, D9).

Stops the flagship vLLM, runs generation on the whole GB300, and ALWAYS
restores the flagship: on success, error, Ctrl-C (SIGINT) and SIGTERM. Once
it starts restoring, SIGTERM and SIGINT wait until the flagship is healthy. A
marker file survives a hard kill (SIGKILL, power loss), so the next
invocation restores first. One window at a time (flock); the `restore` CLI
takes the same lock, so it never starts the flagship under a live window.

The flagship runs on the ROOTFUL docker daemon (the dgx-inference stack),
not podman. It is stopped and started at container level: `docker compose
up` on that stack would also restart the stopped Cosmos container.

Use from the main thread only (installs a SIGTERM handler).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Any, Protocol

from synthbench.generate.podman import podman_argv

FLAGSHIP = "dgx-inference-vllm-1"
FLAGSHIP_MODELS_URL = "http://127.0.0.1:8000/v1/models"
# The container's healthcheck StartPeriod is 30 min (probed 2026-09-27).
HEALTH_TIMEOUT_S = 45 * 60.0
POLL_S = 15.0
GPU_LABEL_FILTER = "label=synthbench.gpu=1"

# What signal.signal() takes and returns.
_SignalHandler = Callable[[int, FrameType | None], Any] | int | signal.Handlers | None


class WindowBusy(RuntimeError):
    """Another GPU window is open."""


class FlagshipNotRestored(RuntimeError):
    """The flagship did not become healthy in time; the marker stays for the next run."""


class Runtime(Protocol):
    def stop(self, container: str) -> None: ...

    def start(self, container: str) -> None: ...

    def is_healthy(self, container: str) -> bool: ...


class DockerRuntime:
    """The flagship on the rootful docker daemon."""

    def __init__(self, models_url: str = FLAGSHIP_MODELS_URL) -> None:
        self._models_url = models_url

    def stop(self, container: str) -> None:
        subprocess.run(["docker", "stop", container], check=True, capture_output=True, timeout=600)

    def start(self, container: str) -> None:
        subprocess.run(["docker", "start", container], check=True, capture_output=True, timeout=120)

    def is_healthy(self, container: str) -> bool:
        probe = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{if .State.Health}}{{.State.Health.Status}}{{end}}",
                container,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if probe.returncode != 0 or probe.stdout.strip() != "healthy":
            return False
        try:
            with urllib.request.urlopen(self._models_url, timeout=10) as resp:  # noqa: S310 - fixed loopback URL
                return bool(resp.status == 200)
        except OSError:
            return False


@dataclass(frozen=True)
class WindowPaths:
    state_dir: Path

    @property
    def marker(self) -> Path:
        return self.state_dir / "window.open"

    @property
    def lock(self) -> Path:
        return self.state_dir / "window.lock"

    @classmethod
    def from_env(cls) -> WindowPaths:
        return cls(Path(os.environ.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "state")


def _say(message: str) -> None:
    sys.stderr.write(f"[gpu-window] {message}\n")


def restore(
    runtime: Runtime,
    container: str = FLAGSHIP,
    *,
    timeout_s: float = HEALTH_TIMEOUT_S,
    poll_s: float = POLL_S,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Start the container (a no-op when it already runs) and wait until healthy."""
    runtime.start(container)
    deadline = clock() + timeout_s
    while not runtime.is_healthy(container):
        if clock() >= deadline:
            raise FlagshipNotRestored(f"{container} not healthy {timeout_s:.0f}s after start")
        sleep(poll_s)


def raise_on_sigterm(signum: int, _frame: FrameType | None) -> None:
    raise SystemExit(128 + signum)


@contextmanager
def _window_lock(paths: WindowPaths) -> Iterator[None]:
    """Hold the one-window flock, or raise WindowBusy at once.

    The kernel drops a flock when its holder dies, so a leftover marker never blocks it.
    """
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(paths.lock, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WindowBusy(f"another GPU window holds {paths.lock}") from exc
        yield
    finally:
        os.close(lock_fd)


@contextmanager
def _exit_signals_deferred(sigterm_after: _SignalHandler) -> Iterator[None]:
    """Only record SIGTERM and SIGINT until the block ends; nothing may cut it short.

    Then SIGTERM gets `sigterm_after` and SIGINT its old handler back. If the block
    succeeded and a signal came in, exit as raise_on_sigterm does (128 + signum). If
    the block raised, that error propagates instead: it says more than the signal.
    """
    received: list[int] = []

    def record(signum: int, _frame: FrameType | None) -> None:
        received.append(signum)

    sigint_before: _SignalHandler = signal.getsignal(signal.SIGINT)
    try:
        signal.signal(signal.SIGTERM, record)
        signal.signal(signal.SIGINT, record)
        yield
    finally:
        signal.signal(signal.SIGTERM, sigterm_after)
        signal.signal(signal.SIGINT, sigint_before)
    if received:
        raise SystemExit(128 + received[0])


@contextmanager
def gpu_window(
    runtime: Runtime,
    paths: WindowPaths,
    *,
    container: str = FLAGSHIP,
    before_restore: Callable[[], None] = lambda: None,
    timeout_s: float = HEALTH_TIMEOUT_S,
    poll_s: float = POLL_S,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    say: Callable[[str], None] = _say,
) -> Iterator[None]:
    with _window_lock(paths):
        if paths.marker.exists():
            say("found the marker of an interrupted window: restoring the flagship first")
            restore(
                runtime, container, timeout_s=timeout_s, poll_s=poll_s, sleep=sleep, clock=clock
            )
            paths.marker.unlink()
        say(
            f"stopping {container}: LiteLLM's claude-flagship route and any sandbox agent "
            "on it are down until this window closes"
        )
        paths.marker.write_text(
            json.dumps({"pid": os.getpid(), "container": container, "opened_at": time.time()})
        )
        previous = signal.signal(signal.SIGTERM, raise_on_sigterm)
        try:
            runtime.stop(container)
            yield
        finally:
            with _exit_signals_deferred(sigterm_after=previous):
                try:
                    before_restore()
                finally:
                    say(
                        f"closing: starting {container} and waiting until it is healthy "
                        "(SIGTERM and Ctrl-C take effect after that)"
                    )
                    restore(
                        runtime,
                        container,
                        timeout_s=timeout_s,
                        poll_s=poll_s,
                        sleep=sleep,
                        clock=clock,
                    )
                    paths.marker.unlink(missing_ok=True)
                    say(f"{container} is healthy again")


def stop_gpu_containers(
    run: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
) -> None:
    """Before the flagship restarts, stop every podman container labeled
    synthbench.gpu=1 (the ComfyUI renderer) so nothing else holds GPU memory.
    The renderer lives in the synthbench podman store, hence podman_argv()."""
    prefix = podman_argv()
    listing = run(
        [*prefix, "ps", "-q", "--filter", GPU_LABEL_FILTER],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    for container_id in listing.stdout.split():
        run(
            [*prefix, "stop", "--time", "30", container_id],
            capture_output=True,
            timeout=120,
            check=False,
        )


def _run_child(command: Sequence[str]) -> int:
    child = subprocess.Popen(list(command))
    try:
        return child.wait()
    except BaseException:
        child.terminate()
        try:
            child.wait(timeout=60)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        raise


def main(
    argv: Sequence[str] | None = None,
    *,
    runtime: Runtime | None = None,
    paths: WindowPaths | None = None,
    before_restore: Callable[[], None] = stop_gpu_containers,
) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.generate.window")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run COMMAND inside a GPU window")
    run.add_argument("argv", nargs=argparse.REMAINDER)
    sub.add_parser("restore", help="start the flagship and wait for healthy")
    sub.add_parser("status", help="print the marker and flagship health as JSON")
    args = parser.parse_args(argv)
    rt = runtime or DockerRuntime()
    wp = paths or WindowPaths.from_env()
    if args.command == "run":
        command = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
        if not command:
            parser.error("run needs a command: run -- python -m ...")
        with gpu_window(rt, wp, before_restore=before_restore):
            return _run_child(command)
    if args.command == "restore":
        try:
            with _window_lock(wp):
                restore(rt)
                wp.marker.unlink(missing_ok=True)
        except WindowBusy as exc:
            _say(f"refusing to restore: {exc}; that window restores {FLAGSHIP} when it closes")
            return 1
        return 0
    status = {"marker": wp.marker.exists(), "flagship_healthy": rt.is_healthy(FLAGSHIP)}
    sys.stdout.write(json.dumps(status) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
