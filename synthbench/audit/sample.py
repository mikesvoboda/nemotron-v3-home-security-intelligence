"""The owner's audit sample and its questions (P5a design §4)."""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from synthbench.export.vss import ExportedSet

SEED = 20260929
# Stratum (scenario group) -> stills to audit. S3 rests on threat and suspicious, S2 on the rest.
STRATA: tuple[tuple[str, int], ...] = (
    ("threat", 20),
    ("suspicious", 10),
    ("hard_negative", 15),
    ("benign", 15),
)


@dataclass(frozen=True)
class Question:
    """One yes/no/unclear question about a still. `key` is scene, prop, people or conditions."""

    key: str
    text: str


def allocate(counts: Mapping[str, int], k: int) -> dict[str, int]:
    """k draws spread over values in proportion to their counts: at least one per value while k
    allows, never more than a value has. Deterministic: ties go to the earlier value by name."""
    values = sorted(value for value, count in counts.items() if count > 0)
    k = min(k, sum(counts[value] for value in values))
    total = sum(counts[value] for value in values)
    alloc = dict.fromkeys(values, 0)
    for value in sorted(values, key=lambda v: (-counts[v], v))[:k]:
        alloc[value] = 1
    for _ in range(k - sum(alloc.values())):
        open_values = [value for value in values if alloc[value] < counts[value]]
        best = max(open_values, key=lambda v: (counts[v] * k / total - alloc[v], -values.index(v)))
        alloc[best] += 1
    return alloc


def sample(sets: Sequence[ExportedSet], seed: int = SEED) -> list[ExportedSet]:
    """The audit's stills: each stratum's count allocated across its lighting values, drawn with
    a fixed seed. Ordered by stratum, then lighting, then draw."""
    chosen: list[ExportedSet] = []
    for group, k in STRATA:
        by_lighting: dict[str, list[ExportedSet]] = defaultdict(list)
        for exported in sets:
            if exported.facts["cell"]["group"] == group:
                by_lighting[exported.facts["cell"]["lighting"]].append(exported)
        counts = {lighting: len(members) for lighting, members in by_lighting.items()}
        for lighting, n in sorted(allocate(counts, k).items()):
            members = sorted(by_lighting[lighting], key=lambda s: s.item_id)
            rng = random.Random(f"{seed}:{group}:{lighting}")  # noqa: S311  # reproducible
            chosen.extend(rng.sample(members, n))
    return chosen


def _words(identifier: str) -> str:
    return identifier.replace("_", " ")


def questions(facts: Mapping[str, Any]) -> tuple[Question, ...]:
    """The questions for one still, from its exported facts."""
    cell = facts["cell"]
    subjects = facts.get("subjects", [])
    props = facts.get("props", [])
    cast = ", ".join(f"{s['class']} ({_words(s['role'])})" for s in subjects) or "nobody"
    held = f", with {', '.join(_words(p['class']) for p in props)}" if props else ""
    out = [Question("scene", f"Does this show {_words(cell['scenario'])}: {cast}{held}?")]
    if cell["group"] == "threat" and props:
        things = " and the ".join(_words(p["class"]) for p in props)
        out.append(Question("prop", f"Is the {things} visible?"))
    people = sum(1 for s in subjects if s["class"] == "person")
    out.append(Question("people", f"Exactly {people} person(s)?"))
    out.append(
        Question(
            "conditions",
            f"{_words(cell['lighting'])} light and {_words(cell['weather'])} weather?",
        )
    )
    return tuple(out)
