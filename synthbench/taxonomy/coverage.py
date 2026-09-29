"""What the sampler draws from a taxonomy, exactly: the model behind `corpus coverage`.

The sampler (`sampler.py`) balances only the scenario axis. Inside a scenario the (property,
zone, camera) cell is uniform over `compatible_cells`, then lighting and weather are weighted
choices, so each legal cell's chance per event is

    p(cell) = (weight_s / sum_weight) * (1 / cells_s) * (light_w / light_sum) * (sky_w / sky_sum)

Everything here is a pure function of a `Taxonomy` and plain counts: it reads and writes nothing.
First written by the generation agent (2026-09-29), from its hand-rolled spread analysis.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Literal

from synthbench.taxonomy.model import (
    CameraDef,
    Taxonomy,
    compatible_cells,
    lighting_options,
    weather_options,
)

# A design space is a projection of the full cell (scenario, property, zone, camera, lighting,
# weather); the axes it drops are left to the sampler. `full` is what random sampling must
# overcome; a coarser space is what a designed quota could ask for once per row.
Space = Literal["full", "scenario+property+light+weather", "scenario+zone+light+weather"]
SPACES: tuple[Space, ...] = (
    "full",
    "scenario+property+light+weather",
    "scenario+zone+light+weather",
)

# The axes a marginal is shown for. Only scenario is balanced; the rest follow from it.
AXES: tuple[str, ...] = ("scenario", "property", "zone", "camera", "lighting", "weather")
_FIELD = {"property": "property_type"}  # axis name -> CellProb attribute, where they differ

# Per scenario: how many events it gets (float for a long-run share, int from `allocate`).
Draws = Mapping[str, float]


@dataclass(frozen=True)
class CellProb:
    """One legal cell and its exact chance per event under the sampler."""

    scenario: str
    property_type: str
    zone: str
    camera: str
    lighting: str
    weather: str
    probability: float

    def value(self, axis: str) -> str:
        value: str = getattr(self, _FIELD.get(axis, axis))
        return value

    def key(self, space: Space) -> tuple[str, ...]:
        """The cell projected onto a design space; cells sharing a key are one row of it."""
        if space == "full":
            return (
                self.scenario,
                self.property_type,
                self.zone,
                self.camera,
                self.lighting,
                self.weather,
            )
        if space == "scenario+property+light+weather":
            return (self.scenario, self.property_type, self.lighting, self.weather)
        return (self.scenario, self.zone, self.lighting, self.weather)


def cell_probs(tax: Taxonomy) -> tuple[CellProb, ...]:
    """Every legal cell with its chance per event; the chances sum to 1."""
    cameras: dict[str, CameraDef] = {camera.id: camera for camera in tax.cameras}
    total_weight = sum(scenario.weight for scenario in tax.scenarios)
    out: list[CellProb] = []
    for scenario in tax.scenarios:
        cells = compatible_cells(tax, scenario)
        share = scenario.weight / total_weight
        for property_type, zone, camera_id in cells:
            camera = cameras[camera_id]
            lights = lighting_options(tax, scenario, camera)
            skies = weather_options(tax, scenario, camera)
            light_sum = sum(option.weight for option in lights)
            sky_sum = sum(option.weight for option in skies)
            out.extend(
                CellProb(
                    scenario=scenario.id,
                    property_type=property_type,
                    zone=zone,
                    camera=camera_id,
                    lighting=light.id,
                    weather=sky.id,
                    probability=share
                    / len(cells)
                    * (light.weight / light_sum)
                    * (sky.weight / sky_sum),
                )
                for light in lights
                for sky in skies
            )
    return tuple(out)


def marginals(cells: tuple[CellProb, ...]) -> dict[str, dict[str, float]]:
    """Each axis value's chance per event: the shape random sampling converges to."""
    out: dict[str, dict[str, float]] = {axis: {} for axis in AXES}
    for cell in cells:
        for axis in AXES:
            value = cell.value(axis)
            out[axis][value] = out[axis].get(value, 0.0) + cell.probability
    return out


def _scenario_shares(cells: tuple[CellProb, ...]) -> dict[str, float]:
    shares: dict[str, float] = {}
    for cell in cells:
        shares[cell.scenario] = shares.get(cell.scenario, 0.0) + cell.probability
    return shares


def even_draws(cells: tuple[CellProb, ...], n: float) -> dict[str, float]:
    """Each scenario's long-run share of n events."""
    return {scenario: n * share for scenario, share in _scenario_shares(cells).items()}


def expected_counts(cells: tuple[CellProb, ...], draws: Draws) -> dict[str, dict[str, float]]:
    """Each axis value's expected count, given how many events each scenario gets."""
    shares = _scenario_shares(cells)
    out: dict[str, dict[str, float]] = {axis: {} for axis in AXES}
    for cell in cells:
        events = draws.get(cell.scenario, 0) * cell.probability / shares[cell.scenario]
        for axis in AXES:
            value = cell.value(axis)
            out[axis][value] = out[axis].get(value, 0.0) + events
    return out


def within_scenario(cells: tuple[CellProb, ...], axis: str, value: str) -> dict[str, float]:
    """For each scenario that can show the value: the share of its events that do."""
    shares = _scenario_shares(cells)
    hit: dict[str, float] = {}
    for cell in cells:
        if cell.value(axis) == value:
            hit[cell.scenario] = hit.get(cell.scenario, 0.0) + cell.probability
    return {scenario: p / shares[scenario] for scenario, p in hit.items()}


def space_size(cells: tuple[CellProb, ...], space: Space) -> int:
    """How many distinct rows the cells have once projected onto a design space."""
    return len({cell.key(space) for cell in cells})


def n_for_count(probability: float, count: int) -> float:
    """Events a random draw needs for a value's expected count to reach `count` (inf if never)."""
    return math.inf if probability <= 0.0 else math.ceil(count / probability)


def cover(
    cells: tuple[CellProb, ...],
    space: Space,
    draws: Draws,
    drawn: Collection[tuple[str, ...]] = (),
) -> float:
    """Expected count of the space's rows touched: the `drawn` ones, plus those that `draws`
    reaches.

    Every space starts with the scenario, so each row belongs to one scenario s. A row with
    within-scenario chance q is missed by all of s's m_s events with probability (1 - q)^m_s.
    """
    shares = _scenario_shares(cells)
    within: dict[tuple[str, ...], float] = {}
    for cell in cells:
        row = cell.key(space)
        within[row] = within.get(row, 0.0) + cell.probability / shares[cell.scenario]
    seen = set(drawn)
    touched = 0.0
    for row, q in within.items():
        if row in seen:
            touched += 1.0
        else:
            # min(): float sums can put a scenario's only row a hair above 1.
            touched -= math.expm1(draws.get(row[0], 0) * math.log1p(-min(q, 1.0 - 1e-15)))
    return touched


def n_for_cover(cells: tuple[CellProb, ...], space: Space, fraction: float) -> int:
    """The smallest n whose long-run draws are expected to touch `fraction` of the space.

    Coverage of the last rows is the slow part (the coupon-collector tail), so this bisects on
    `cover`, which only grows with n.
    """
    target = fraction * space_size(cells, space)
    lo, hi = 1, space_size(cells, space)
    while cover(cells, space, even_draws(cells, hi)) < target and hi < 100_000_000:
        hi *= 2
    while lo < hi:
        mid = (lo + hi) // 2
        if cover(cells, space, even_draws(cells, mid)) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo
