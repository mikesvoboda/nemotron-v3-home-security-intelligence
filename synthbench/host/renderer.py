"""The renderer unit's pre-start check and warm-up (agent-driven design §1, §5.3).

systemd runs ComfyUI in the foreground (`podman run --rm`, no -d), so the unit's state is the
container's. `precheck` (ExecStartPre) refuses to start it unless the guard is fresh and the
flagship healthy, the flagship's util gate is at most 0.76, and FLUX.2 [dev] fits beside it.
`warmup` (ExecStartPost) renders one image so FLUX.2 is resident before the agent's first job.

    python -m synthbench.host.renderer precheck|warmup
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

from synthbench.generate.comfy.client import ComfyClient
from synthbench.generate.comfy.graphs import flux2_dev_t2i
from synthbench.generate.comfy.serve import (
    CONTAINER,
    ServeConfig,
    baked_farm_root,
    container_alive,
    wait_ready,
)
from synthbench.generate.window import FLAGSHIP
from synthbench.status import FlagshipUnknown, flagship_file, fresh_flagship

MAX_UTIL = 0.76  # design §5.3: 0.76 x 249.81 GiB passes beside the renderer at its peak
MIN_FREE_GIB = 60.0  # FLUX.2 [dev] peaked at 56.2 GiB beside the flagship, plus --reserve-vram 4
RESERVE_VRAM_ARGS = ("--reserve-vram", "4")
WARMUP_PROMPT = "An empty suburban driveway on an overcast afternoon, photorealistic."

Runner = Callable[..., subprocess.CompletedProcess[str]]
_UTIL = re.compile(r"--gpu-memory-utilization[= ]([0-9]*\.?[0-9]+)")


class PrecheckError(RuntimeError):
    """A pre-start fact could not be read."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def flagship_util(run: Runner = subprocess.run) -> float:
    """The live flagship's --gpu-memory-utilization, from its container's ENGINE_ARGS."""
    done = run(
        ["docker", "inspect", "--format", "{{range .Config.Env}}{{println .}}{{end}}", FLAGSHIP],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if done.returncode != 0:
        raise PrecheckError(f"docker inspect {FLAGSHIP} failed: {(done.stderr or '').strip()}")
    for line in done.stdout.splitlines():
        if line.startswith("ENGINE_ARGS=") and (found := _UTIL.search(line)):
            return float(found.group(1))
    raise PrecheckError(f"{FLAGSHIP} has no --gpu-memory-utilization in ENGINE_ARGS")


def gpu_free_gib(run: Runner = subprocess.run) -> float:
    done = run(
        ["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    try:
        total, used = (float(value) for value in done.stdout.splitlines()[0].split(","))
    except (IndexError, ValueError) as error:
        raise PrecheckError(f"cannot read nvidia-smi: {done.stdout!r} {done.stderr!r}") from error
    return (total - used) / 1024


def prepare(cfg: ServeConfig) -> list[str]:
    """The renderer's directories, and the farm the image was built for."""
    farm, baked = cfg.models_root / "comfyui", baked_farm_root()
    if farm != baked:
        return [f"the farm under HF_HOME is {farm}, but the image loads models from {baked}"]
    for directory in (cfg.out_dir, cfg.cache_dir, cfg.log_file.parent):
        directory.mkdir(parents=True, exist_ok=True)
    return []


def precheck(
    status_file: Path, *, run: Runner = subprocess.run, now: Callable[[], datetime] = _utc_now
) -> list[str]:
    """Every reason not to start the renderer; empty when it may start."""
    problems: list[str] = []
    try:
        if not fresh_flagship(status_file, now()).healthy:
            problems.append("the flagship is not healthy (status/flagship.json)")
    except FlagshipUnknown as error:
        problems.append(f"{error}; start synthbench-guard first")
    try:
        util = flagship_util(run)
        if util > MAX_UTIL:
            problems.append(
                f"the flagship's util gate {util} is above {MAX_UTIL}: it could not boot again "
                "beside the renderer (design §5.3); apply the stack change first"
            )
    except PrecheckError as error:
        problems.append(str(error))
    try:
        free = gpu_free_gib(run)
        if free < MIN_FREE_GIB:
            problems.append(
                f"{free:.1f} GiB free on the GPU; FLUX.2 [dev] needs {MIN_FREE_GIB:.0f}"
            )
    except PrecheckError as error:
        problems.append(str(error))
    if container_alive(run):
        problems.append(
            f"a {CONTAINER} container is already running; stop it with "
            "`python -m synthbench.generate.comfy.serve down`"
        )
    return problems


def warmup(
    cfg: ServeConfig,
    *,
    client: ComfyClient | None = None,
    ready: Callable[[], object] | None = None,
) -> float:
    """Wait for ComfyUI, then render one 1280x720 image; returns its seconds."""
    if ready is None:
        wait_ready(cfg.base_url, alive=container_alive, log_file=cfg.log_file)
    else:
        ready()
    comfy = client if client is not None else ComfyClient(cfg.base_url)
    graph = flux2_dev_t2i(WARMUP_PROMPT, seed=0, width=1280, height=720)
    for node in graph.values():
        if node["class_type"] == "SaveImage":
            node["inputs"]["filename_prefix"] = "synthbench/warmup"
    started = time.monotonic()
    try:
        comfy.run(graph, timeout_s=900)
    finally:
        comfy.close()
    return time.monotonic() - started


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.host.renderer")
    parser.add_argument("command", choices=["precheck", "warmup"])
    args = parser.parse_args(argv)
    cfg = ServeConfig.from_env()
    if args.command == "precheck":
        problems = prepare(cfg) + precheck(flagship_file())
        for problem in problems:
            sys.stderr.write(f"[synthbench-renderer] refusing to start: {problem}\n")
        return 1 if problems else 0
    seconds = warmup(cfg)
    sys.stderr.write(f"[synthbench-renderer] warm-up image rendered in {seconds:.1f} s\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
