"""Coverage of a synthbench corpus version: what the sampler drew, and what it will tend to draw.

Read-only. Run from the repository root (the agent's workspace or the host checkout):

    uv run python .claude/skills/synthbench-generation/coverage.py
    uv run python .claude/skills/synthbench-generation/coverage.py --batch batch-1
    uv run python .claude/skills/synthbench-generation/coverage.py --expected 400
    uv run python .claude/skills/synthbench-generation/coverage.py --expected 100 --only a,b

--expected simulates the next N events the way `sample` draws them (the prior counts are the
corpus's own, failed events included), averaged over --runs seeds. It writes nothing.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

# The repository root: this file is .claude/skills/<name>/coverage.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.model import load_taxonomy
from synthbench.taxonomy.sampler import MAX_BATCH, sample_specs

AXES = ("scenario", "group", "label", "property", "zone", "camera", "lighting", "weather")


def facts(spec: Spec, indoor: set[str]) -> dict[str, list[str]]:
    cell = spec.cell
    camera = f"{cell.camera} (indoor)" if cell.camera in indoor else cell.camera
    return {
        "scenario": [cell.scenario],
        "group": [cell.group],
        "label": [spec.label],
        "property": [cell.property_type],
        "zone": [cell.zone],
        "camera": [camera],
        "lighting": [cell.lighting],
        "weather": [cell.weather],
        "artifacts": list(cell.artifacts) or ["(none)"],
        "classes": sorted({s.cls for s in spec.subjects} | {p.cls for p in spec.props}),
    }


def tally(specs: Iterable[Spec], indoor: set[str]) -> tuple[int, dict[str, Counter[str]]]:
    counts: dict[str, Counter[str]] = {axis: Counter() for axis in (*AXES, "artifacts", "classes")}
    total = 0
    for spec in specs:
        total += 1
        for axis, values in facts(spec, indoor).items():
            counts[axis].update(values)
    return total, counts


def show(title: str, total: int, counts: dict[str, Counter[str]], scale: float = 1.0) -> None:
    sys.stdout.write(f"\n## {title}: {total / scale:.0f} events\n")
    for axis, counter in counts.items():
        cells = ", ".join(
            f"{k} {v / scale:.0f} ({100 * v / total:.0f}%)" for k, v in counter.most_common()
        )
        per = " (per event, may exceed 100%)" if axis in {"artifacts", "classes"} else ""
        sys.stdout.write(f"- {axis}{per}: {cells}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch", action="append", help="only these batches (repeatable)")
    parser.add_argument("--expected", type=int, default=0, help="simulate the next N events")
    parser.add_argument("--only", default="", help="comma-separated scenario ids, as sample")
    parser.add_argument("--runs", type=int, default=20, help="seeds to average for --expected")
    args = parser.parse_args()

    tax = load_taxonomy()
    indoor = {c.id for c in tax.cameras if c.indoor}
    store = CorpusStore.from_env(tax.version, os.environ)
    index = store.latest_index() if store.index_file.exists() else {}
    rows = [r for r in index.values() if not args.batch or r.batch in args.batch]
    specs = [store.read(store.spec_file(r.event_id), Spec) for r in rows]
    status = Counter(f"{r.batch}:{r.status}" for r in rows)
    sys.stdout.write(f"# {tax.version} at {store.version_dir}\n")
    sys.stdout.write("statuses: " + ", ".join(f"{k} {v}" for k, v in sorted(status.items())) + "\n")

    # Scenario balance over the whole version (sample's prior counts include failed events).
    prior = Counter(store.read(store.spec_file(e), Spec).cell.scenario for e in index)
    weights = {s.id: s.weight for s in tax.scenarios}
    whole = sum(prior.values())
    sys.stdout.write(f"\n## scenario balance over all {whole} events (count vs weighted share)\n")
    for sid, weight in sorted(weights.items(), key=lambda kv: -kv[1]):
        share = whole * weight / sum(weights.values())
        sys.stdout.write(f"- {sid}: {prior[sid]} vs {share:.1f} ({prior[sid] - share:+.1f})\n")

    total, counts = tally(specs, indoor)
    show("drawn so far" + (f" ({', '.join(args.batch)})" if args.batch else ""), total, counts)

    if args.expected > 0:
        only = [s for s in args.only.split(",") if s] or None
        simulated: list[Spec] = []
        for run in range(args.runs):
            carried = Counter(prior)
            left, part = args.expected, 0
            while left > 0:
                n = min(left, MAX_BATCH)
                drawn = sample_specs(
                    tax, version=tax.version, batch=f"sim{run}-{part}", n=n,
                    seed=1_000_003 * run + part, prior=carried, only=only,
                )  # fmt: skip
                carried.update(s.cell.scenario for s in drawn)
                simulated.extend(drawn)
                left, part = left - n, part + 1
        sim_total, sim_counts = tally(simulated, indoor)
        show(f"expected next {args.expected} (mean of {args.runs} seeds)", sim_total, sim_counts,
             scale=args.runs)  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
