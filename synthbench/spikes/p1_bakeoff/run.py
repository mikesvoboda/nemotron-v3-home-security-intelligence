"""Run the P1 bake-off. Inside a GPU window:

    uv run python -m synthbench.generate.window run -- \
        uv run python -m synthbench.spikes.p1_bakeoff.run all

`--dry-run` prints the pending jobs per model and kind and starts nothing; with
nothing pending the runner returns before it starts ComfyUI. Resumable: an output
is finished when its file exists and its latest record is ok; outputs are written
atomically. One row per job goes to <root>/records.jsonl (with `cold` for the job
that loaded the model); one row per model group (seconds, peak VRAM, how /free
settled and the VRAM baseline after it) to <root>/groups.jsonl. A failed job is
recorded, never fatal: "model X cannot render Y" is a bake-off result. A lost
renderer (an httpx transport error) and two timeouts in a row within a model group
are infrastructure, not the model: they stop the run, the window restores the
flagship, and a resume in a later window retries.
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
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Protocol

import httpx

from synthbench.generate.comfy import graphs, serve
from synthbench.generate.comfy.client import ComfyClient, Graph
from synthbench.generate.window import raise_on_sigterm
from synthbench.spikes.p1_bakeoff.cases import I2V_MODELS, T2I_MODELS
from synthbench.spikes.p1_bakeoff.plan import Job, clip_jobs, image_jobs, pending

# ComfyUI's /free returns before its worker unloads anything (PF19b): see settle_vram.
SETTLE_POLL_S = 0.5
SETTLE_TOLERANCE_MIB = 256
SETTLE_GRACE_S = 15.0
SETTLE_TIMEOUT_S = 60.0

# How often a job polls ComfyUI's history: a coarse poll would pad every job's seconds.
JOB_POLL_S = 0.1

# How often the VRAM sampler reads memory.used: a VAE-decode spike lasts well under 1 s.
VRAM_SAMPLE_S = 0.25

# This many timeouts in a row within a model group mean a hung worker, not a slow model.
MAX_CONSECUTIVE_TIMEOUTS = 2

# What a failed VRAM reading raises: nvidia-smi missing, exiting non-zero or hanging, or bad output.
_READ_ERRORS = (OSError, subprocess.SubprocessError, ValueError)

SettleStatus = Literal["dropped", "no_drop", "timeout", "unreadable"]


class RunAborted(RuntimeError):
    """The renderer looks hung: stop the run, let the window restore, resume later."""


@dataclass(frozen=True)
class Settle:
    status: SettleStatus
    last_mib: int | None  # the last reading: the group's baseline VRAM; None when unreadable


class Client(Protocol):
    def free(self) -> None: ...

    def upload_image(self, path: Path) -> str: ...

    def run(self, graph: Graph, *, timeout_s: float, poll_s: float) -> list[bytes]: ...


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


def _read_vram() -> int | None:
    try:
        return _query_used_mib()
    except _READ_ERRORS:
        return None


def _warn(message: str) -> None:
    sys.stderr.write(f"[p1-bakeoff] warning: {message}\n")


def settle_vram(
    before_mib: int | None,
    *,
    read: Callable[[], int] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Settle:
    """Wait until /free's unload has visibly freed VRAM, from `before_mib` read before /free.

    Steady readings alone prove nothing: under the native caching allocator memory.used
    stays flat while weights copy out and drops only at empty_cache. So, polling the
    sampler's query (by default) every SETTLE_POLL_S:
      - "dropped": a reading fell more than SETTLE_TOLERANCE_MIB below `before_mib`, then
        two consecutive readings agreed within it;
      - "no_drop": nothing fell within SETTLE_GRACE_S (the first group; nothing resident);
      - "timeout": SETTLE_TIMEOUT_S passed after a drop that never held (one warning line);
      - "unreadable": VRAM could not be read (one warning line, no waiting).
    The caller proceeds whatever the status, and records it with `last_mib`.
    """
    if before_mib is None:
        _warn("cannot read VRAM before /free; not waiting for it to settle")
        return Settle("unreadable", None)
    query = _query_used_mib if read is None else read
    start = clock()
    dropped_to: int | None = None  # the latest reading since VRAM fell below before_mib
    try:
        while True:
            sleep(SETTLE_POLL_S)
            current = query()
            if dropped_to is None:
                if current < before_mib - SETTLE_TOLERANCE_MIB:
                    dropped_to = current
                elif clock() - start >= SETTLE_GRACE_S:
                    return Settle("no_drop", current)
            elif abs(current - dropped_to) <= SETTLE_TOLERANCE_MIB:
                return Settle("dropped", current)
            else:
                dropped_to = current
            if clock() - start >= SETTLE_TIMEOUT_S:
                _warn(
                    f"VRAM still changing {SETTLE_TIMEOUT_S:.0f}s after /free ({before_mib} MiB "
                    f"before, {current} now); this group's peak may include the previous model"
                )
                return Settle("timeout", current)
    except _READ_ERRORS as exc:
        _warn(f"cannot read VRAM ({type(exc).__name__}: {exc}); not waiting for /free to settle")
        return Settle("unreadable", None)


class VramSampler:
    """Samples GPU memory.used (MiB) every VRAM_SAMPLE_S; .peak_mib after exit.

    .peak_mib stays None when no sample succeeded: an unknown peak, never a 0.
    """

    def __init__(self, interval_s: float = VRAM_SAMPLE_S) -> None:
        self.peak_mib: int | None = None
        self._interval = interval_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _sample(self) -> None:
        used = _read_vram()
        if used is not None:
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


def _write_atomic(path: Path, data: bytes) -> None:
    """Write a temp file beside `path`, then rename it over `path`.

    An interrupted write never leaves a partial file at `path`, which `pending` would take
    as done and later jobs (identity edits, clips) would read as their input.
    """
    part = path.with_name(f"{path.name}.part")
    try:
        part.write_bytes(data)
        part.replace(path)  # os.replace: atomic within one filesystem
    finally:
        part.unlink(missing_ok=True)


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


def run_job(job: Job, client: Client, root: Path, *, cold: bool = False) -> dict[str, Any]:
    """`cold`: the first job of its model group, whose seconds include loading the model.

    Records every failure except a lost renderer (httpx.TransportError), which it raises
    unrecorded: that is not the model's failure, and a resume retries the job.
    """
    started = time.monotonic()
    # inputs as a list: the JSONL row must read back equal to the returned record
    record: dict[str, Any] = asdict(job) | {
        "inputs": list(job.inputs),
        "cold": cold,
        "ok": False,
        "error": None,
        "seconds": None,
    }
    try:
        names = [client.upload_image(root / p) for p in job.inputs]
        blobs = client.run(
            _graph(job, names),
            timeout_s=1800.0 if job.kind == "i2v" else 600.0,
            poll_s=JOB_POLL_S,
        )
        if not blobs:
            raise RuntimeError("the graph produced no output file")
        out = root / job.output
        out.parent.mkdir(parents=True, exist_ok=True)
        _write_atomic(out, blobs[0])
        record["ok"] = True
    except httpx.TransportError:
        raise  # the renderer is gone or not answering: stop the run, resume later
    except Exception as exc:  # a failure is a bake-off result, never fatal
        record["error"] = f"{type(exc).__name__}: {exc}"[:500]
    record["seconds"] = round(time.monotonic() - started, 3)
    _append(root / "records.jsonl", record)
    return record


def _timed_out(record: dict[str, Any]) -> bool:
    """run_job records a failure as "<exception type>: <message>"."""
    return str(record["error"] or "").startswith(f"{TimeoutError.__name__}:")


def execute(jobs: list[Job], client: Client, root: Path) -> None:
    """Run the jobs group by group. Raises RunAborted after MAX_CONSECUTIVE_TIMEOUTS timeouts
    in a row within a group, and a lost renderer's transport error: both stop the run."""
    root.mkdir(parents=True, exist_ok=True)
    for model, group_iter in itertools.groupby(jobs, key=lambda j: j.model):
        group = list(group_iter)
        # ComfyUI keeps earlier groups' models resident; unload them so that
        # this group's peak VRAM is its own model's (spec §3.7).
        before_mib = _read_vram()
        client.free()
        settle = settle_vram(before_mib)  # /free returns before the unload happens (PF19b)
        started = time.monotonic()
        with VramSampler() as vram:
            timeouts = 0
            for index, job in enumerate(group):
                record = run_job(job, client, root, cold=index == 0)
                timeouts = timeouts + 1 if _timed_out(record) else 0
                if timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                    raise RunAborted(
                        f"{timeouts} jobs of {model} in a row timed out: ComfyUI's worker "
                        "looks hung. Stopping the run so the window restores the flagship; "
                        "resume in a later window (the timed-out jobs render again)."
                    )
        _append(
            root / "groups.jsonl",
            {
                "model": model,
                "jobs": len(group),
                "seconds": round(time.monotonic() - started, 1),
                "peak_vram_mib": vram.peak_mib,
                "settle": settle.status,
                "baseline_vram_mib": settle.last_mib,
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the pending jobs per model and kind; start nothing",
    )
    args = parser.parse_args(argv)
    wanted = {m for m in args.models.split(",") if m}
    unknown = sorted(wanted - {*T2I_MODELS, *I2V_MODELS})
    if unknown:
        parser.error(
            f"unknown --models {','.join(unknown)} (known: {','.join(T2I_MODELS + I2V_MODELS)})"
        )
    jobs = (image_jobs() if args.stage in {"images", "all"} else []) + (
        clip_jobs() if args.stage in {"clips", "all"} else []
    )
    jobs = [j for j in pending(jobs, args.root) if not wanted or j.model in wanted]
    if args.dry_run:
        counts = Counter((job.model, job.kind) for job in jobs)  # in job (stage-major) order
        lines = [f"{model} {kind} {n}" for (model, kind), n in counts.items()]
        sys.stdout.write("\n".join([*lines, f"total {len(jobs)}"]) + "\n")
        return 0
    if not jobs:
        sys.stderr.write("[p1-bakeoff] nothing pending; not starting ComfyUI\n")
        return 0
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
