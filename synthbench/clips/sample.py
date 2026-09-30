"""`clip sample`'s draw (clips design §3.1, ruling H3-R5).

n clips split as evenly as the groups allow; within a group, the audit sampler's `allocate`
spreads them over lighting values; each (group, lighting) draw is seeded, so the same seed and
the same eligible stills give the same clips.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from synthbench.audit.sample import allocate


@dataclass(frozen=True)
class Candidate:
    """A ready still no clip has taken yet."""

    event_id: str
    group: str
    lighting: str


def split(counts: Mapping[str, int], n: int) -> dict[str, int]:
    """n clips over groups: round-robin from the group with the most candidates (ties by name),
    skipping full groups, so shares are equal, the remainder goes to the largest groups, and a
    small group's unused share goes on to the others."""
    groups = sorted(group for group, count in counts.items() if count > 0)
    target = min(n, sum(counts[group] for group in groups))
    alloc = dict.fromkeys(groups, 0)
    order = sorted(groups, key=lambda group: (-counts[group], group))
    placed = 0
    while placed < target:
        for group in order:
            if placed == target:
                break
            if alloc[group] < counts[group]:
                alloc[group] += 1
                placed += 1
    return alloc


def draw(candidates: Sequence[Candidate], n: int, seed: int) -> list[Candidate]:
    """The round's stills, ordered by group, then lighting, then draw."""
    by_group: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        by_group[candidate.group].append(candidate)
    chosen: list[Candidate] = []
    shares = split({group: len(members) for group, members in by_group.items()}, n)
    for group, k in sorted(shares.items()):
        by_lighting: dict[str, list[Candidate]] = defaultdict(list)
        for candidate in by_group[group]:
            by_lighting[candidate.lighting].append(candidate)
        counts = {lighting: len(members) for lighting, members in by_lighting.items()}
        for lighting, m in sorted(allocate(counts, k).items()):
            members = sorted(by_lighting[lighting], key=lambda c: c.event_id)
            rng = random.Random(f"{seed}:{group}:{lighting}")  # noqa: S311  # reproducible
            chosen.extend(rng.sample(members, m))
    return chosen
