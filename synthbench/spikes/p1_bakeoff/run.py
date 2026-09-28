"""Run the P1 bake-off. Inside a GPU window:

    uv run python -m synthbench.generate.window run -- \
        uv run python -m synthbench.spikes.p1_bakeoff.run all

Resumable (finished outputs are skipped). One row per job goes to
<root>/records.jsonl; one row per model group (seconds, peak VRAM) to
<root>/groups.jsonl. A failed job is recorded, never fatal: "model X cannot
render Y" is a bake-off result.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol

from synthbench.generate.comfy import graphs, serve
from synthbench.generate.comfy.client import ComfyClient, Graph
from synthbench.generate.window import raise_on_sigterm
from synthbench.spikes.p1_bakeoff.plan import Job, clip_jobs, image_jobs, pending

# ComfyUI's /free unloads asynchronously: wait until VRAM stops moving before sampling.
SETTLE_POLL_S = 0.5
SETTLE_TOLERANCE_MIB = 256
SETTLE_TIMEOUT_S = 30.0

# What a failed VRAM reading raises: nvidia-smi missing, exiting non-zero or hanging, or bad output.
_READ_ERRORS = (OSError, subprocess.SubprocessError, ValueError)


class Client(Protocol):
    def free(self) -> None: ...

    def upload_image(self, path: Path) -> str: ...

    def run(self, graph: Graph, *, timeout_s: float) -> list[bytes]: ...


def parse_used_mib(text: str) -> int:
    return max(int(line.strip()) for line in text.splitlines() if line.strip())


def _query_used_mib() -> int:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    ).stdout
    return parse_used_mib(out)


def _warn(message: str) -> None:
    sys.stderr.write(f"[p1-bakeoff] warning: {message}\n")


def settle_vram(
    *,
    read: Callable[[], int] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Wait out /free's asynchronous unload, so a group's peak is not the previous model's.

    Reads memory.used (the sampler's query by default) every SETTLE_POLL_S until two
    consecutive readings differ by at most SETTLE_TOLERANCE_MIB, and returns True. After
    SETTLE_TIMEOUT_S, or when VRAM cannot be read, it writes one warning line and returns
    False; the caller proceeds either way.
    """
    query = _query_used_mib if read is None else read
    deadline = clock() + SETTLE_TIMEOUT_S
    try:
        previous = query()
        while True:
            sleep(SETTLE_POLL_S)
            current = query()
            if abs(current - previous) <= SETTLE_TOLERANCE_MIB:
                return True
            if clock() >= deadline:
                _warn(
                    f"VRAM still changing {SETTLE_TIMEOUT_S:.0f}s after /free "
                    f"({previous} -> {current} MiB); this group's peak may include the last model"
                )
                return False
            previous = current
    except _READ_ERRORS as exc:
        _warn(f"cannot read VRAM ({type(exc).__name__}: {exc}); not waiting for /free to settle")
        return False


class VramSampler:
    """Samples GPU memory.used (MiB) once a second; .peak_mib after exit.

    .peak_mib stays None when no sample succeeded: an unknown peak, never a 0.
    """

    def __init__(self, interval_s: float = 1.0) -> None:
        self.peak_mib: int | None = None
        self._interval = interval_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _sample(self) -> None:
        try:
            used = _query_used_mib()
        except _READ_ERRORS:
            return
        self.peak_mib = used if self.peak_mib is None else max(self.peak_mib, used)

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            self._sample()

    def __enter__(self) -> VramSampler:
        self._sample()  # synchronous first sample: a group shorter than one interval still counts
        self._thread.start()
        return self

    def __exit__(
        self, _t: type[BaseException] | None, _e: BaseException | None, _tb: TracebackType | None
    ) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self._sample()


def _append(path: Path, row: dict[str, Any]) -> None:
    with path.open("a") as fh:
        fh.write(json.dumps(row) + "\n")


def _graph(job: Job, names: list[str]) -> Graph:
    if job.kind == "t2i":
        return graphs.T2I_BUILDERS[job.model](
            job.prompt, seed=job.seed, width=job.width, height=job.height
        )
    if job.kind == "edit":
        return graphs.EDIT_BUILDERS[job.model](
            job.prompt, images=names, seed=job.seed, width=job.width, height=job.height
        )
    return graphs.I2V_BUILDERS[job.model](
        job.prompt,
        image=names[0],
        seed=job.seed,
        width=job.width,
        height=job.height,
        frames=job.frames,
    )


def run_job(job: Job, client: Client, root: Path) -> dict[str, Any]:
    started = time.monotonic()
    # inputs as a list: the JSONL row must read back equal to the returned record
    record: dict[str, Any] = asdict(job) | {
        "inputs": list(job.inputs),
        "ok": False,
        "error": None,
        "seconds": None,
    }
    try:
        names = [client.upload_image(root / p) for p in job.inputs]
        blobs = client.run(_graph(job, names), timeout_s=1800.0 if job.kind == "i2v" else 600.0)
        if not blobs:
            raise RuntimeError("the graph produced no output file")
        out = root / job.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blobs[0])
        record["ok"] = True
    except Exception as exc:  # a failure is a bake-off result, never fatal
        record["error"] = f"{type(exc).__name__}: {exc}"[:500]
    record["seconds"] = round(time.monotonic() - started, 3)
    _append(root / "records.jsonl", record)
    return record


def execute(jobs: list[Job], client: Client, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for model, group_iter in itertools.groupby(jobs, key=lambda j: j.model):
        group = list(group_iter)
        # ComfyUI keeps earlier groups' models resident; unload them so that
        # this group's peak VRAM is its own model's (spec §3.7).
        client.free()
        settle_vram()  # /free returns before the unload finishes (PF19)
        started = time.monotonic()
        with VramSampler() as vram:
            for job in group:
                run_job(job, client, root)
        _append(
            root / "groups.jsonl",
            {
                "model": model,
                "jobs": len(group),
                "seconds": round(time.monotonic() - started, 1),
                "peak_vram_mib": vram.peak_mib,
            },
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.spikes.p1_bakeoff.run")
    parser.add_argument("stage", choices=["images", "clips", "all"])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "p1",
    )
    parser.add_argument("--models", default="", help="comma-separated model filter")
    args = parser.parse_args(argv)
    wanted = {m for m in args.models.split(",") if m}
    jobs = (image_jobs() if args.stage in {"images", "all"} else []) + (
        clip_jobs() if args.stage in {"clips", "all"} else []
    )
    jobs = [j for j in pending(jobs, args.root) if not wanted or j.model in wanted]
    signal.signal(signal.SIGTERM, raise_on_sigterm)
    cfg = serve.ServeConfig.from_env()
    serve.start(cfg)
    try:
        serve.wait_ready(cfg.base_url, alive=serve.container_alive, log_file=cfg.log_file)
        client = ComfyClient(cfg.base_url)
        try:
            execute(jobs, client, args.root)
        finally:
            client.close()
    finally:
        serve.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
