"""The seeded coverage-matrix sampler (spec §1.2, §7.2): taxonomy -> Tier B specs.

The same seed, batch name and prior counts give identical specs. Scenario counts follow the
taxonomy weights by Balinski and Young's quota method, so across carried-forward batches drawn
without `only` every scenario stays within one event of its weighted share.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Collection, Mapping, Sequence

from synthbench.contract.spec import Cell, Prop, Spec, Subject
from synthbench.taxonomy.model import (
    CameraDef,
    ScenarioDef,
    Taxonomy,
    artifact_options,
    compatible_cells,
    lighting_options,
    weather_options,
)

MAX_BATCH = 500  # event numbers are three digits: B-<batch>-NNN

_DAY = 24 * 60


def default_seed(batch: str) -> int:
    """A batch's seed when none is given: stable across machines and Python processes."""
    return int(hashlib.sha256(batch.encode()).hexdigest()[:8], 16)


def allocate(
    tax: Taxonomy, n: int, prior: Mapping[str, int], only: Collection[str] | None = None
) -> list[str]:
    """The scenario of each of n new events, given how many each scenario already has."""
    if only is not None and (unknown := sorted(set(only) - {s.id for s in tax.scenarios})):
        raise ValueError(f"unknown scenarios: {', '.join(unknown)}")
    pool = [s for s in tax.scenarios if only is None or s.id in only]
    if not pool:
        raise ValueError("no scenario to sample from")
    total_weight = sum(s.weight for s in pool)
    counts = {s.id: prior.get(s.id, 0) for s in pool}
    picks: list[str] = []
    for _ in range(n):
        size = sum(counts.values()) + 1
        # Quota method: only scenarios still under their upper quota at the new size are
        # eligible; among them the highest weight per (count + 1) wins, and ties go to the
        # earlier-listed scenario. The upper quotas sum to at least the new size, so someone is
        # always eligible; the whole-pool fallback only guards float edge cases.
        eligible = [
            (i, s)
            for i, s in enumerate(pool)
            if counts[s.id] < math.ceil(s.weight / total_weight * size - 1e-9)
        ] or list(enumerate(pool))
        _, _, chosen = max((s.weight / (counts[s.id] + 1), -i, s.id) for i, s in eligible)
        counts[chosen] += 1
        picks.append(chosen)
    return picks


def _minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def time_in_hours(hours: Sequence[tuple[str, str]], rng: random.Random) -> str:
    """A uniform minute in the inclusive ranges. A range whose end is earlier wraps midnight."""
    spans = [
        (_minutes(start), (_minutes(end) - _minutes(start)) % _DAY + 1) for start, end in hours
    ]
    pick = rng.randrange(sum(length for _, length in spans))
    for start, length in spans:
        if pick < length:
            minute = (start + pick) % _DAY
            return f"{minute // 60:02d}:{minute % 60:02d}"
        pick -= length
    raise AssertionError("unreachable: pick is below the total span")


def in_hours(hhmm: str, hours: Sequence[tuple[str, str]]) -> bool:
    """Whether hhmm falls in the inclusive ranges, with the same midnight wrap."""
    minute = _minutes(hhmm)
    return any(
        (minute - _minutes(start)) % _DAY <= (_minutes(end) - _minutes(start)) % _DAY
        for start, end in hours
    )


def sample_specs(
    tax: Taxonomy,
    *,
    version: str,
    batch: str,
    n: int,
    seed: int,
    prior: Mapping[str, int] | None = None,
    only: Collection[str] | None = None,
) -> list[Spec]:
    """n Tier B specs for one batch: facts only, no prompt (agent-driven design §3 step 1)."""
    if not 1 <= n <= MAX_BATCH:
        raise ValueError(f"n must be 1..{MAX_BATCH}, got {n}")
    scenarios = {s.id: s for s in tax.scenarios}
    cameras = {c.id: c for c in tax.cameras}
    order = allocate(tax, n, prior or {}, only)
    return [
        _one(tax, scenarios[scenario_id], cameras, version=version, batch=batch, index=i, seed=seed)
        for i, scenario_id in enumerate(order)
    ]


def _one(
    tax: Taxonomy,
    scenario: ScenarioDef,
    cameras: Mapping[str, CameraDef],
    *,
    version: str,
    batch: str,
    index: int,
    seed: int,
) -> Spec:
    # A str seed is hashed with SHA-512 inside `random`, so the stream is the same in every
    # process, whatever PYTHONHASHSEED is. The draw order below is part of the contract:
    # reordering it changes every spec a seed produces.
    rng = random.Random(f"{seed}:{batch}:{index}")  # noqa: S311  # reproducible, not security
    property_type, zone, camera_id = rng.choice(compatible_cells(tax, scenario))
    camera = cameras[camera_id]
    lights = lighting_options(tax, scenario, camera)
    lighting = rng.choices(lights, weights=[x.weight for x in lights])[0]
    skies = weather_options(tax, scenario, camera)
    weather = rng.choices(skies, weights=[w.weight for w in skies])[0]
    artifacts = tuple(
        artifact.id
        for artifact in artifact_options(tax, camera, lighting.id, weather.id)
        if rng.random() < artifact.probability
    )
    scene_time = time_in_hours(lighting.hours, rng)
    subjects: list[Subject] = []
    for number, definition in enumerate(scenario.subjects, start=1):
        cls = rng.choice(definition.one_of)
        attributes: dict[str, str] = {}
        if cls in tax.clothed:
            attributes["clothing"] = f"{rng.choice(tax.colors)} {rng.choice(tax.garments)}"
        subjects.append(
            Subject(id=f"S{number}", cls=cls, role=definition.role, attributes=attributes)
        )
    props = tuple(
        Prop(
            id=f"X{number}",
            cls=rng.choice(definition.one_of),
            held_by=None if definition.held_by is None else f"S{definition.held_by + 1}",
        )
        for number, definition in enumerate(scenario.props, start=1)
    )
    return Spec(
        event_id=f"B-{batch}-{index:03d}",
        tier="B",
        corpus_version=version,
        batch=batch,
        cell=Cell(
            scenario=scenario.id,
            group=scenario.group,
            property_type=property_type,
            zone=zone,
            camera=camera.id,
            lighting=lighting.id,
            weather=weather.id,
            artifacts=artifacts,
        ),
        scene_time=scene_time,
        label=scenario.label,
        risk_band=scenario.risk_band,
        subjects=tuple(subjects),
        props=props,
    )
