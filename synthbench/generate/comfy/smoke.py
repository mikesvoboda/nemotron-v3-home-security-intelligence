"""Queue each registered builder once at low resolution against a running renderer.

    python -m synthbench.generate.comfy.smoke --only t2i:z-image-turbo,t2i:flux2-klein-4b
Writes <SYNTHBENCH_ROOT>/smoke/<kind>_<model>.<ext> and prints seconds per graph.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from synthbench.generate.comfy import graphs
from synthbench.generate.comfy.client import ComfyClient
from synthbench.generate.comfy.serve import ServeConfig

SMOKE_REF = Path(__file__).resolve().parent / "smoke_ref.png"
# (width, height) per kind. LTX-2.5 samples stage 1 at half size on EmptyLTXVLatentVideo's
# 32-pixel grid, which ComfyUI floors silently, so i2v needs sides that are multiples of 64.
SMOKE_SIZES: dict[str, tuple[int, int]] = {"t2i": (512, 288), "edit": (512, 288), "i2v": (512, 320)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.generate.comfy.smoke")
    parser.add_argument("--only", default="", help="comma-separated keys like t2i:z-image-turbo")
    args = parser.parse_args(argv)
    wanted = {k for k in args.only.split(",") if k}
    known = set(graphs.sample_graphs())
    if unknown := wanted - known:
        parser.error(
            f"unknown --only key(s): {', '.join(sorted(unknown))}; "
            f"valid keys: {', '.join(sorted(known))}"
        )
    out_dir = Path(os.environ.get("SYNTHBENCH_ROOT", "/synthbench")) / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = ComfyClient(ServeConfig.from_env().base_url)
    failures = 0
    try:
        ref = client.upload_image(SMOKE_REF)
        for key in sorted(known):
            if wanted and key not in wanted:
                continue
            kind, model = key.split(":", 1)
            width, height = SMOKE_SIZES[kind]
            small = {"seed": 11, "width": width, "height": height}
            if kind == "t2i":
                graph = graphs.T2I_BUILDERS[model]("a front porch in daylight", **small)
            elif kind == "edit":
                graph = graphs.EDIT_BUILDERS[model]("the same scene at dusk", images=[ref], **small)
            else:
                graph = graphs.I2V_BUILDERS[model](
                    "the scene is still", image=ref, frames=17, **small
                )
            started = time.monotonic()
            try:
                blobs = client.run(graph, timeout_s=1800)
                suffix = "mp4" if kind == "i2v" else "png"
                (out_dir / f"{kind}_{model}.{suffix}").write_bytes(blobs[0])
                sys.stdout.write(f"OK   {key:28s} {time.monotonic() - started:7.1f}s\n")
            except Exception as exc:  # smoke reports every failure and continues
                failures += 1
                sys.stdout.write(f"FAIL {key:28s} {type(exc).__name__}: {exc}\n")
    finally:
        client.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
