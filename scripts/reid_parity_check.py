#!/usr/bin/env python
"""B2.2 owner run: person re-ID parity and timing, CPU path against GPU path.

Owner ruling 68: "a command in the PR body that checks parity on the owner's
host with the production weights". Every crop goes through:

- the backend's CPU path: ``osnet_loader.load_osnet_model`` on the production
  checkpoint (sha256-pinned by models.yml), then ``extract_person_embedding``;
- the GPU path: ``POST <gateway>/person-reid`` through ``reid_gateway``, the
  client the switch uses.

It prints the cosine of every pair, per-crop and per-event timing for both
paths, and the gateway's reported model ID against ``osnet_model_id()``. It
exits 0 only when every pair reaches ``PARITY_GATE`` and the IDs match.

Usage (the PR body gives the full host procedure):
    uv run python scripts/reid_parity_check.py \\
        --weights /export/ai_models/model-zoo/osnet-ain-x1-0 \\
        --gateway-url http://127.0.0.1:18090/enrich-lt \\
        --crops /path/to/person/crops
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

#: Ruling 68's gate. A failure is a stop-and-report; it is never loosened.
PARITY_GATE = 0.999

#: Crops per event for the per-event figure. The leg embeds an event's crops one
#: after another (backend/services/vlm_specialists.py:754).
DEFAULT_CROPS_PER_EVENT = 3

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two vectors, each normalised first."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    return float(np.dot(a / np.linalg.norm(a), b / np.linalg.norm(b)))


def timing_summary(samples_ms: list[float], *, crops_per_event: int) -> dict[str, float]:
    """Median and p95 per crop, and the median per-crop time times an event's crops."""
    arr = np.asarray(samples_ms, dtype=np.float64)
    median = float(np.median(arr))
    return {
        "median_ms": median,
        "p95_ms": float(np.percentile(arr, 95)),
        "per_event_ms": median * crops_per_event,
    }


def verdict(cosines: list[float], *, model_ids_match: bool) -> str:
    """PASS only if there were crops, every pair met the gate, and the IDs match."""
    if not cosines or not model_ids_match:
        return "FAIL"
    return "PASS" if min(cosines) >= PARITY_GATE else "FAIL"


def _crops(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in _IMAGE_SUFFIXES)


async def _run(args: argparse.Namespace) -> int:
    from PIL import Image

    from backend.services import osnet_loader, reid_gateway

    row = osnet_loader._osnet_zoo_row()
    handle: dict[str, Any] = await osnet_loader.load_osnet_model(
        str(args.weights), expected_sha256=row.get("sha256") or None
    )
    expected_id = osnet_loader.osnet_model_id()

    paths = _crops(args.crops)
    if not paths:
        print(f"no images in {args.crops}", file=sys.stderr)
        return 2

    cosines: list[float] = []
    cpu_ms: list[float] = []
    gpu_ms: list[float] = []
    gateway_ids: set[str] = set()
    print(f"{'crop':40s} {'size':>9s} {'cosine':>9s} {'cpu ms':>8s} {'gpu ms':>8s}")
    for path in paths:
        crop = Image.open(path).convert("RGB")

        t0 = time.perf_counter()
        local = await osnet_loader.extract_person_embedding(handle, crop)
        t1 = time.perf_counter()
        remote = await reid_gateway.embed_person_via_gateway(crop, base_url=args.gateway_url)
        t2 = time.perf_counter()

        cos = cosine(local.embedding, remote.embedding)
        cosines.append(cos)
        cpu_ms.append((t1 - t0) * 1000)
        gpu_ms.append((t2 - t1) * 1000)
        gateway_ids.add(str(remote.model_id))
        size = f"{crop.width}x{crop.height}"
        print(f"{path.name[:40]:40s} {size:>9s} {cos:9.6f} {cpu_ms[-1]:8.1f} {gpu_ms[-1]:8.1f}")

    ids_match = gateway_ids == {expected_id}
    cpu = timing_summary(cpu_ms, crops_per_event=args.crops_per_event)
    gpu = timing_summary(gpu_ms, crops_per_event=args.crops_per_event)
    print()
    print(f"crops: {len(paths)}  gate: {PARITY_GATE}")
    print(f"cosine: min {min(cosines):.6f}  mean {float(np.mean(cosines)):.6f}")
    for name, s in (("cpu (backend OSNet)", cpu), ("gpu (gateway reid)", gpu)):
        print(
            f"{name:20s} per crop median {s['median_ms']:.1f} ms  p95 {s['p95_ms']:.1f} ms  "
            f"per event ({args.crops_per_event} crops) {s['per_event_ms']:.1f} ms"
        )
    print(f"model id: backend {expected_id}  gateway {sorted(gateway_ids)}")
    result = verdict(cosines, model_ids_match=ids_match)
    print(f"RESULT: {result}")
    return 0 if result == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--weights", type=Path, required=True, help="OSNet checkpoint file or dir")
    ap.add_argument("--gateway-url", required=True, help="the test gateway's /enrich-lt URL")
    ap.add_argument("--crops", type=Path, required=True, help="directory of person crops")
    ap.add_argument("--crops-per-event", type=int, default=DEFAULT_CROPS_PER_EVENT)
    return asyncio.run(_run(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
