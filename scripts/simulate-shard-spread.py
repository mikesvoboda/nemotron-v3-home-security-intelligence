#!/usr/bin/env python3
"""Simulate shard time-spread and churn under the four (durations x algorithm)
configurations, using a module-BLOCK permutation model of pytest-randomly.

    uv run python scripts/simulate-shard-spread.py [--runs 12]

WHY THIS EXISTS (batch-9 row 2, backend lane, 2026-10-09): PR bodies must not
rest on /tmp scratch (contract rule 3 — "work from /tmp does not count as
evidence"). Every spread/churn figure in that package's Evidence 5 came from
this instrument, so the instrument ships. Its two claims:

  A. per-run spread: "today" (no durations file + default duration_based_chunks)
     simulates mean ~1.5x at 24 seeds — between the two real observations
     from green main runs (2.207x on 37940703535, 1.207x on 37933347572,
     per-testcase junit sums; the real runs' extra spread is runner timing
     variance this placement-only model does not try to reproduce).
     FILE + least_duration simulates ~1.00x.

  B. roulette-on-insert: inserting a 20-test file moves up to 30 existing
     tests under "today" — position-dependent (max 30 when the new block
     precedes all three count boundaries: each absorbs 5/10/15 fewer pushes;
     ~12-20 mid-list) — while FILE + least_duration is NEARLY INCREMENTAL
     (0 existing movers here). That surprised the author, and a prior version of this instrument
     claimed the opposite (~6,200 movers) — a corpus artifact: its id list
     carried 4 phantom ids that took the file-mean weight, a few seconds of
     pure-mean load oscillating the least-loaded heap at group boundaries
     (verified: 3,127+3,073 group-0<->3 swaps from the same code on the stale
     corpus, 0 on the committed file). The corrected claim was arbitrated
     against the REAL plugin on a synthetic 10-test corpus: this file's
     assign() reproduces its per-group membership exactly. least_duration is
     greedy longest-processing-time, so a small insert only cascades when the
     weights it adds straddle a group's balance point — repacking when the
     tree genuinely changed, but far less than chunks' seed roulette feared.

MODEL (what it abstracts, what it does not):
  * pytest-randomly 5.0.0 (_reorganize_items) shuffles items WITHIN a module
    file, then permutes whole module BLOCKS by a seed-keyed sort. We model the
    block permutation as random.Random(seed).shuffle over module order — the
    real key is _crc32(f"{seed}::{module.__name}"), a different bijection with
    the same statistical character; conclusions here are per-seed averages, so
    the exact key does not matter, the uniformity does.
  * chunks / least_duration are reimplementations of
    pytest_split/algorithms.py DurationBasedChunksAlgorithm /
    LeastDurationAlgorithm (including least_duration's str(item) pre-sort —
    simulated with "<Function {tail}>" strings, which is what makes its tie
    class visible) over the COMMITTED .test_durations weights.
  * Real times come from .test_durations itself (it IS the artifact of run
    37940703535's per-testcase junits, minted by scripts/mint-test-durations.py).
    A fresh mint overwrites it, so --durations defaults to the file but can be
    pointed at another mints' output.

Deterministic: seeds are a fixed range (3001..3000+runs), no clock, no RNG
outside random.Random(seed). The sim's absolute spread numbers are model
output — the EVIDENCE for the real problem is scripts/test_shard_durations.py's
docstring (numbers recomputed from the two runs' junit artifacts), and the sim's
job is to explain WHY the two configurations differ and rank them.
"""

from __future__ import annotations

import argparse
import collections
import heapq
import json
import random
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPLITS = 4  # both sharded legs run --splits 4 (ci.yml unit tier, integration leg)


def load_unit(durations_path: Path) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Unit-tier weights + module -> items in collection order."""
    durations = json.loads(durations_path.read_text())
    unit = {k: v for k, v in durations.items() if k.startswith("backend/tests/unit/")}
    modules: dict[str, list[str]] = collections.defaultdict(list)
    for nodeid in sorted(unit):
        modules[nodeid.split("::", 1)[0]].append(nodeid)
    return unit, modules


def order_for(seed: int, modules: "dict[str, list[str]] | list[str]") -> list[str]:
    """Module-block permutation for one seed (see MODEL in the docstring).

    Accepts the module->items mapping or a bare list of module names (for
    callers holding an ordered module list of their own).
    """
    mods = list(modules.keys() if isinstance(modules, dict) else modules)
    random.Random(seed).shuffle(mods)
    items: list[str] = []
    for m in mods:
        block = list(modules[m])
        random.Random(seed * 31 + len(block)).shuffle(block)
        items += block
    return items


def assign(items: list[str], durations: dict[str, float], algo: str) -> dict[str, int]:
    """Group index per item, mirroring pytest_split/algorithms.py."""
    avg = sum(durations.values()) / len(durations) if durations else 1.0
    if algo == "chunks":
        # DurationBasedChunksAlgorithm: walk the collected ORDER, cut when the
        # running weight passes time_per_group. Missing keys take the mean —
        # with NO file at all every weight is the mean, so the cut is a count
        # cut, which is what CI's sharded legs do today.
        weights = [durations.get(i, avg) for i in items]
        per_group = sum(weights) / SPLITS
        groups: dict[str, int] = {}
        gi, acc = 0, 0.0
        for item, w in zip(items, weights):
            if gi < SPLITS - 1 and acc >= per_group:
                gi += 1
                acc = 0.0
            groups[item] = gi
            acc += w
        return groups
    # LeastDurationAlgorithm: pre-sort by str(item) (tie-break), then by
    # duration descending, then greedy least-loaded-heap.
    name = {i: f"<Function {i.rsplit('::', 1)[-1]}>" for i in items}
    pairs = sorted(zip(items, (durations.get(i, avg) for i in items)), key=lambda t: name[t[0]])
    pairs = sorted(pairs, key=lambda t: t[1], reverse=True)
    heap = [(0.0, g) for g in range(SPLITS)]
    heapq.heapify(heap)
    groups = {}
    for item, w in pairs:
        load, gi = heapq.heappop(heap)
        groups[item] = gi
        heapq.heappush(heap, (load + w, gi))
    return groups


def spread(groups: dict[str, int], weights: dict[str, float]) -> float:
    per = [0.0] * SPLITS
    for item, g in groups.items():
        per[g] += weights.get(item, 0.0)
    return max(per) / min(per)


CONFIGS = [
    ("today: no file + chunks", "no", "chunks"),
    ("no file + least_duration", "no", "least"),
    ("FILE + chunks", "file", "chunks"),
    ("FILE + least_duration", "file", "least"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--durations", default=str(REPO / ".test_durations"), type=Path)
    ap.add_argument("--runs", default=12, type=int, help="seeds to average over")
    args = ap.parse_args()

    unit, modules = load_unit(args.durations)
    print(f"corpus: {args.durations.name}: {len(unit)} unit nodeids in "
          f"{len(modules)} modules, {sum(unit.values()):.1f}s\n")

    def d_for(kind: str) -> dict[str, float]:
        return {} if kind == "no" else unit

    print("A. per-run spread (max/min shard seconds), one seed per run:")
    for label, kind, algo in CONFIGS:
        sp = [spread(assign(order_for(s, modules), d_for(kind), algo), unit)
              for s in range(3001, 3001 + args.runs)]
        print(f"   {label:26s} mean {statistics.mean(sp):5.2f}x  max {max(sp):5.2f}x")
    print("   (real: 2.207x on run 37940703535, 1.207x on 37933347572 — "
          "junit per-testcase sums, not model output)")

    print("\nB. insert a 20-test module; existing tests that change shard:")
    newmod = "backend/tests/unit/services/test_brand_new_10.py"
    new = [f"{newmod}::test_new{i}" for i in range(20)]
    for label, kind, algo in CONFIGS:
        movers = []
        for s in range(3001, 3001 + min(args.runs, 6)):
            base = order_for(s, modules)
            # the new module's block lands at a seed-chosen position among
            # module blocks (that is where pytest-randomly puts it)
            pos = random.Random(s * 7 + 13).randrange(len(modules))
            cut = sum(len(modules[m]) for m in list(modules)[:pos])
            withn = base[:cut] + new + base[cut:]
            m0 = assign(base, d_for(kind), algo)
            m1 = assign(withn, d_for(kind), algo)
            movers.append(sum(1 for k in m0 if m0[k] != m1[k]))
        print(f"   {label:26s} existing movers per seed: {movers}")


if __name__ == "__main__":
    main()
