"""Run the pinned ComfyUI renderer under rootless podman (spec §3.1).

The container sees /export/models read-only at the SAME path, so the symlink
farm under /export/models/comfyui resolves inside it. It writes outputs under
$SYNTHBENCH_ROOT/comfy-out, listens on 127.0.0.1 only, and carries the
synthbench.gpu=1 label that the GPU window uses to stop it before the
flagship restarts. Image and container live in the synthbench podman store
(synthbench.generate.podman), never in the default one on the root fs.

Container output goes to $SYNTHBENCH_ROOT/logs/comfyui.log (k8s-file), not
journald on the root fs; the file outlives --rm, so a crash can be read after
the container is gone. `up` stops waiting as soon as the container is gone.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from synthbench.generate.podman import podman_argv, podman_env, podman_root

IMAGE = "localhost/synthbench-comfyui:v0.37.0"
CONTAINER = "synthbench-comfyui"
GPU_LABEL = "synthbench.gpu=1"
CONTAINERFILE_DIR = Path(__file__).resolve().parent

Runner = Callable[..., subprocess.CompletedProcess[str]]


class ServeError(RuntimeError):
    """podman could not start the renderer, or the renderer exited while starting."""


@dataclass(frozen=True)
class ServeConfig:
    port: int
    models_root: Path
    out_dir: Path
    cache_dir: Path

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def log_file(self) -> Path:
        """<SYNTHBENCH_ROOT>/logs/comfyui.log; out_dir is <SYNTHBENCH_ROOT>/comfy-out."""
        return self.out_dir.parent / "logs" / "comfyui.log"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ServeConfig:
        e = os.environ if env is None else env
        root = Path(e.get("SYNTHBENCH_ROOT", "/export/synthbench"))
        return cls(
            port=int(e.get("SYNTHBENCH_COMFYUI_PORT", "8188")),
            models_root=Path(e.get("HF_HOME", "/export/models")),
            out_dir=root / "comfy-out",
            cache_dir=root / "cache",
        )


def build_args() -> list[str]:
    return [
        *podman_argv(),
        "build",
        "-t",
        IMAGE,
        "-f",
        str(CONTAINERFILE_DIR / "Containerfile"),
        str(CONTAINERFILE_DIR),
    ]


def build(run: Runner = subprocess.run) -> None:
    """Build into the synthbench store; the base-image pull stages under <root>/tmp."""
    root = podman_root()
    (root / "storage").mkdir(parents=True, exist_ok=True)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    run(build_args(), check=True, env=podman_env())


def run_args(cfg: ServeConfig) -> list[str]:
    return [
        *podman_argv(),
        "run",
        "-d",
        "--rm",
        "--name",
        CONTAINER,
        "--label",
        GPU_LABEL,
        "--log-driver",
        "k8s-file",
        "--log-opt",
        f"path={cfg.log_file}",
        "--device",
        "nvidia.com/gpu=all",
        "--shm-size",
        "16g",
        "-p",
        f"127.0.0.1:{cfg.port}:8188",
        "-v",
        f"{cfg.models_root}:{cfg.models_root}:ro",
        "-v",
        f"{cfg.out_dir}:/opt/ComfyUI/output",
        "-v",
        f"{cfg.cache_dir}:/root/.cache",
        IMAGE,
    ]


def start(cfg: ServeConfig, run: Runner = subprocess.run) -> None:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        run(run_args(cfg), check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise ServeError(
            f"podman run {CONTAINER} failed (exit {e.returncode}): {(e.stderr or '').strip()}"
        ) from e


def stop(run: Runner = subprocess.run) -> None:
    run(
        [*podman_argv(), "stop", "--ignore", "--time", "30", CONTAINER],
        check=False,
        capture_output=True,
        text=True,
    )


def container_alive(run: Runner = subprocess.run) -> bool:
    """False once the renderer container is gone (--rm removes it when ComfyUI exits).

    `podman container exists` exits 1 for "no such container"; any other failure
    (125) is a podman error, not evidence that ComfyUI exited.
    """
    done = run(
        [*podman_argv(), "container", "exists", CONTAINER],
        check=False,
        capture_output=True,
        text=True,
    )
    return done.returncode != 1


def wait_ready(
    base_url: str,
    *,
    timeout_s: float = 600.0,
    poll_s: float = 2.0,
    get: Callable[..., httpx.Response] = httpx.get,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    alive: Callable[[], bool] | None = None,
    log_file: Path | None = None,
) -> dict[str, Any]:
    """Poll /system_stats until ComfyUI answers; returns its JSON.

    With `alive`, a container that is already gone raises ServeError at once
    instead of after `timeout_s`. `log_file` is named in every failure.
    """
    see_log = f"; see {log_file}" if log_file else ""
    deadline = clock() + timeout_s
    while True:
        try:
            resp = get(f"{base_url}/system_stats", timeout=5.0)
            if resp.status_code == 200:
                stats: dict[str, Any] = resp.json()
                return stats
        except httpx.HTTPError:
            pass
        if alive is not None and not alive():
            raise ServeError(f"the ComfyUI container exited before {base_url} answered{see_log}")
        if clock() >= deadline:
            raise TimeoutError(f"ComfyUI at {base_url} not ready after {timeout_s:.0f}s{see_log}")
        sleep(poll_s)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.generate.comfy.serve")
    parser.add_argument("command", choices=["build", "up", "down"])
    args = parser.parse_args(argv)
    cfg = ServeConfig.from_env()
    if args.command == "build":
        build()
        return 0
    if args.command == "up":
        start(cfg)
        stats = wait_ready(cfg.base_url, alive=container_alive, log_file=cfg.log_file)
        sys.stdout.write(json.dumps(stats, indent=1) + "\n")
        return 0
    stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
