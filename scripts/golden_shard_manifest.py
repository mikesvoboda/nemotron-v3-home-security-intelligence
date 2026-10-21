#!/usr/bin/env python3
"""Regenerate frontend/golden-shards.json from the measured per-file medians.

**[r282]** Playwright's count-based ``--shard=i/N`` splits spec files by count,
not duration. This script replaces that split for the golden project with a
measured one: it reads ``scripts/golden-shard-durations.json`` (per-file median
wall seconds, provenance-recorded), greedy-packs the files longest-processing-
time-first into N shards, and writes the manifest the golden project selects
its files from.

Determinism is a contract: the manifest is checked in, and a repo pin runs this
script twice and byte-compares it with the checked-in file. So the output has
no timestamps and sorts every list; two runs on the same input are identical.

The backend golden leg is not in the pack: it runs on shard 1 only ([r264]'s
rule, kept because the measurement supports it -- its 84s median is pre-loaded
onto shard 1 before packing so the pack balances the Playwright portion around
it). The leg's cost lives in the harness, not in a spec file, so packing it
would couple the manifest to the harness's shape.

Usage::

    uv run python -I scripts/golden_shard_manifest.py \
        --medians scripts/golden-shard-durations.json \
        --out frontend/golden-shards.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BACKEND_LEG_SECONDS = 84.0  # the backend golden leg's median, shard 1 only ([r264])
DEFAULT_SHARDS = 4


def pack(files: dict[str, float], shard_count: int, preload: float) -> list[list[str]]:
    """Greedy longest-processing-time-first packing; ties broken by file path.

    Files go to the currently-least-loaded shard. The preload sits on shard 1
    before packing starts (the backend leg's cost), so the pack balances the
    spec files around it rather than pretending shard 1 is empty.
    """
    loads = [0.0] * shard_count
    shards: list[list[str]] = [[] for _ in range(shard_count)]
    loads[0] = preload
    for path, duration in sorted(files.items(), key=lambda kv: (-kv[1], kv[0])):
        index = loads.index(min(loads))
        loads[index] += duration
        shards[index].append(path)
    return shards


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--medians", type=Path, default=Path("scripts/golden-shard-durations.json"))
    parser.add_argument("--out", type=Path, default=Path("frontend/golden-shards.json"))
    parser.add_argument("--shards", type=int, default=DEFAULT_SHARDS)
    args = parser.parse_args()

    data = json.loads(args.medians.read_text())
    files = {path: entry["median"] for path, entry in sorted(data["files"].items())}
    shards = pack(files, args.shards, BACKEND_LEG_SECONDS)
    loads = [round(sum(files[f] for f in shard), 3) for shard in shards]
    loads[0] += BACKEND_LEG_SECONDS
    manifest = {
        "shard_count": args.shards,
        "backend_leg_shard": 1,
        "shards": shards,
        "loads_seconds": loads,
    }
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}: {args.shards} shards, loads {loads}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
