"""The GPU window (spec §3.6, D9).

Stops the flagship vLLM, runs generation on the whole GB300, and ALWAYS
restores the flagship: on success, error, Ctrl-C (SIGINT), SIGTERM and SIGHUP
(a terminal or SSH hangup). Once it starts restoring, SIGTERM, SIGHUP and
SIGINT wait until the flagship is healthy. A marker file survives a hard kill
(SIGKILL, power loss), so the next invocation restores first. One window at a
time (flock); the `restore` CLI takes the same lock, so it never starts the
flagship under a live window.

The flagship runs on the ROOTFUL docker daemon (the dgx-inference stack),
not podman. It is stopped and started at container level: `docker compose
up` on that stack would also restart the stopped Cosmos container.

Use from the main thread only (installs SIGTERM and SIGHUP handlers).
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
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
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
GPU_LABEL_FILTER = "label=synthbench.gpu=1"  # serve.GPU_LABEL (test-pinned)
# What the window defers while it restores; SIGTERM and SIGHUP also end the body cleanly.
_EXIT_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)

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
        return cls(Path(os.environ.get("SYNTHBENCH_ROOT", "/synthbench")) / "state")


def _say(message: str) -> None:
    sys.stderr.write(f"[gpu-window] {message}\n")


def _quietly(say: Callable[[str], None]) -> Callable[[str], None]:
    """`say` for the restore path, where a failed log write must never keep the flagship
    down (e.g. BrokenPipeError after `... |& tee log` lost tee to the same Ctrl-C)."""

    def say_or_skip(message: str) -> None:
        with suppress(Exception):
            say(message)

    return say_or_skip


def _describe(exc: BaseException) -> str:
    """The exception, plus a failed command's stderr (what docker and podman explain with)."""
    stderr = getattr(exc, "stderr", None)
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    detail = f"{type(exc).__name__}: {exc}"
    return f"{detail} {stderr.strip()}" if isinstance(stderr, str) and stderr.strip() else detail


def restore(
    runtime: Runtime,
    container: str = FLAGSHIP,
    *,
    timeout_s: float = HEALTH_TIMEOUT_S,
    poll_s: float = POLL_S,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    say: Callable[[str], None] = _say,
) -> None:
    """Start the container and wait until healthy, starting it again after every unhealthy poll.

    A start is a no-op on a running container. Repeating it catches a stop that lands after
    the first start (dockerd finishes a stop even when a Ctrl-C killed its CLI) and a
    flagship that crash-exited while coming up. Only the first start may raise (docker
    itself is broken); a repeated start that fails (a dockerd blip) is logged, and the
    deadline, not the blip, ends the wait.
    """
    say_quietly = _quietly(say)
    runtime.start(container)
    deadline = clock() + timeout_s
    while not runtime.is_healthy(container):
        if clock() >= deadline:
            raise FlagshipNotRestored(f"{container} not healthy {timeout_s:.0f}s after start")
        sleep(poll_s)
        try:
            runtime.start(container)
        except Exception as exc:
            say_quietly(f"starting {container} again failed; still waiting: {_describe(exc)}")


def raise_on_sigterm(signum: int, _frame: FrameType | None) -> None:
    """For SIGTERM and SIGHUP: exit 128 + signum through the `finally` blocks."""
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
def _exit_signals_deferred(after: Mapping[int, _SignalHandler] | None = None) -> Iterator[None]:
    """Only record SIGTERM, SIGHUP and SIGINT until the block ends; nothing may cut it short.

    Then each gets its handler from `after`, or the one it had before the block. If the
    block succeeded and a signal came in, exit as raise_on_sigterm does (128 + signum). If
    the block raised, that error propagates instead: it says more than the signal.
    """
    received: list[int] = []

    def record(signum: int, _frame: FrameType | None) -> None:
        received.append(signum)

    handlers: dict[int, _SignalHandler] = {sig: signal.getsignal(sig) for sig in _EXIT_SIGNALS}
    handlers |= after or {}
    try:
        for sig in _EXIT_SIGNALS:
            signal.signal(sig, record)
        yield
    finally:
        for sig in _EXIT_SIGNALS:
            signal.signal(sig, handlers[sig])
    if received:
        raise SystemExit(128 + received[0])


def _gpu_containers(
    run: Callable[..., subprocess.CompletedProcess[Any]],
    prefix: list[str],
    say: Callable[[str], None],
) -> list[str] | None:
    """IDs of the running containers labeled synthbench.gpu=1; None (logged) if podman fails."""
    try:
        listing = run(
            [*prefix, "ps", "-q", "--filter", GPU_LABEL_FILTER],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception as exc:
        say(f"cannot list the GPU containers: {_describe(exc)}")
        return None
    if listing.returncode != 0:
        say(
            f"cannot list the GPU containers: podman ps exited {listing.returncode}: "
            f"{(listing.stderr or '').strip()}"
        )
        return None
    return list(listing.stdout.split())


def stop_gpu_containers(
    run: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
    *,
    say: Callable[[str], None] = _say,
) -> None:
    """Before the flagship restarts, stop every podman container labeled
    synthbench.gpu=1 (the ComfyUI renderer) so nothing else holds GPU memory.
    The renderer lives in the synthbench podman store, hence podman_argv().

    Never raises: the flagship restore runs next, whatever happens here. A podman failure
    is logged with its exit code and stderr, and after stopping it lists again and names
    any container still running.
    """
    say_quietly = _quietly(say)
    prefix = podman_argv()
    running = _gpu_containers(run, prefix, say_quietly)
    for container_id in running or []:
        try:
            done = run(
                [*prefix, "stop", "--time", "30", container_id],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except Exception as exc:
            say_quietly(f"cannot stop GPU container {container_id}: {_describe(exc)}")
            continue
        if done.returncode != 0:
            say_quietly(
                f"cannot stop GPU container {container_id}: podman stop exited "
                f"{done.returncode}: {(done.stderr or '').strip()}"
            )
    if running:
        survivors = _gpu_containers(run, prefix, say_quietly)
        if survivors:
            say_quietly(
                f"still running after the stop: {' '.join(survivors)}; the flagship starts "
                "beside them"
            )


@contextmanager
def gpu_window(
    runtime: Runtime,
    paths: WindowPaths,
    *,
    container: str = FLAGSHIP,
    before_restore: Callable[[], None] = stop_gpu_containers,
    timeout_s: float = HEALTH_TIMEOUT_S,
    poll_s: float = POLL_S,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    say: Callable[[str], None] = _say,
) -> Iterator[None]:
    say_quietly = _quietly(say)
    with _window_lock(paths):
        if paths.marker.exists():
            with _exit_signals_deferred():
                say_quietly(
                    "found the marker of an interrupted window: restoring the flagship first"
                )
                restore(
                    runtime,
                    container,
                    timeout_s=timeout_s,
                    poll_s=poll_s,
                    sleep=sleep,
                    clock=clock,
                    say=say_quietly,
                )
                paths.marker.unlink()
        say(
            f"stopping {container}: LiteLLM's claude-flagship route and any sandbox agent "
            "on it are down until this window closes"
        )
        paths.marker.write_text(
            json.dumps({"pid": os.getpid(), "container": container, "opened_at": time.time()})
        )
        previous: dict[int, _SignalHandler] = {
            sig: signal.signal(sig, raise_on_sigterm) for sig in (signal.SIGTERM, signal.SIGHUP)
        }
        try:
            runtime.stop(container)
            yield
        finally:
            with _exit_signals_deferred(after=previous):
                try:
                    before_restore()
                finally:
                    say_quietly(
                        f"closing: starting {container} and waiting until it is healthy "
                        "(SIGTERM, SIGHUP and Ctrl-C take effect after that)"
                    )
                    restore(
                        runtime,
                        container,
                        timeout_s=timeout_s,
                        poll_s=poll_s,
                        sleep=sleep,
                        clock=clock,
                        say=say_quietly,
                    )
                    paths.marker.unlink(missing_ok=True)
                    say_quietly(f"{container} is healthy again")


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
