"""synthbench/taxonomy/coverage.py: the model behind `corpus coverage`, checked against the sampler.

The command is only worth reading if its numbers are the sampler's own distribution, so the
central tests draw real specs and compare them with what the model predicted. The rest pin the
arithmetic a planner reads off the report. (First written by the generation agent, 2026-09-29.)
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from synthbench.contract.spec import Spec
from synthbench.taxonomy.coverage import (
    AXES,
    SPACES,
    Space,
    cell_probs,
    cover,
    even_draws,
    expected_counts,
    marginals,
    n_for_count,
    n_for_cover,
    space_size,
)
from synthbench.taxonomy.model import Taxonomy, load_taxonomy
from synthbench.taxonomy.sampler import sample_specs

TAX = load_taxonomy()  # at import: collection pays for the load, not a timed test
TINY = load_taxonomy(Path(__file__).with_name("fixtures") / "tiny_taxonomy.yaml")


def _draw(tax: Taxonomy, batch: str, n: int, seed: int) -> list[Spec]:
    return sample_specs(tax, version=tax.version, batch=batch, n=n, seed=seed)


def _key(spec: Spec, space: Space) -> tuple[str, ...]:
    cell = spec.cell
    if space == "full":
        return (
            cell.scenario,
            cell.property_type,
            cell.zone,
            cell.camera,
            cell.lighting,
            cell.weather,
        )
    if space == "scenario+property+light+weather":
        return (cell.scenario, cell.property_type, cell.lighting, cell.weather)
    return (cell.scenario, cell.zone, cell.lighting, cell.weather)


def test_cell_probabilities_sum_to_one() -> None:
    cells = cell_probs(TAX)
    assert len(cells) == 7157  # the legal cell count the owner's spread question rests on
    assert sum(cell.probability for cell in cells) == pytest.approx(1.0)


def test_every_drawn_cell_is_in_the_model() -> None:
    cells = {cell.key("full") for cell in cell_probs(TAX)}
    drawn = {_key(spec, "full") for spec in _draw(TAX, "probe", 500, 41)}
    assert drawn <= cells, "the sampler drew a cell the model does not contain"


def test_marginals_match_a_real_draw() -> None:
    """The exact marginals are what `sample_specs` converges to, not a nearby approximation."""
    table = marginals(cell_probs(TINY))
    drawn: Counter[str] = Counter()
    total = 0
    for seed in range(12):
        for spec in _draw(TINY, f"m{seed}", 200, seed):
            drawn[spec.cell.property_type] += 1
            total += 1
    for value, probability in table["property"].items():
        # 2,400 draws: 3 sigma on a ~50% value is ~3pp, so 5pp is a real failure.
        assert drawn[value] / total == pytest.approx(probability, abs=0.05)


def test_expected_counts_follow_the_scenarios_actually_drawn() -> None:
    """Given each scenario's draw count, every other axis's expected counts match a real draw.

    Lighting and weather are weighted draws: a model that treats them as uniform fails here.
    """
    cells = cell_probs(TAX)
    specs = [s for seed in range(4) for s in _draw(TAX, f"e{seed}", 500, seed)]
    expected = expected_counts(cells, Counter(spec.cell.scenario for spec in specs))
    for axis in AXES[1:]:
        field = "property_type" if axis == "property" else axis
        drawn = Counter(getattr(spec.cell, field) for spec in specs)
        assert sum(expected[axis].values()) == pytest.approx(len(specs)), axis
        for value, count in expected[axis].items():
            # 2,000 draws: 3 sigma on the largest value (~60%) is ~66 events.
            assert drawn[value] == pytest.approx(count, abs=70), (axis, value)


def test_cover_matches_a_real_draw() -> None:
    cells = cell_probs(TINY)
    space: Space = "scenario+property+light+weather"
    rows = {_key(spec, space) for spec in _draw(TINY, "cover", 50, 7)}
    assert cover(cells, space, even_draws(cells, 50)) == pytest.approx(len(rows), abs=4)


def test_cover_counts_rows_already_drawn_as_touched() -> None:
    cells = cell_probs(TINY)
    space: Space = "scenario+zone+light+weather"
    drawn = {_key(spec, space) for spec in _draw(TINY, "seen", 6, 3)}
    assert cover(cells, space, {}, drawn=drawn) == len(drawn)
    before = cover(cells, space, even_draws(cells, 20))
    assert cover(cells, space, even_draws(cells, 20), drawn=drawn) > before
    illegal = {("no_such_scenario", "porch", "day", "clear")}
    assert cover(cells, space, {}, drawn=drawn | illegal) == len(drawn), "counted a row outside"


def test_cover_is_monotone_and_bounded_by_the_space() -> None:
    cells = cell_probs(TINY)
    for space in SPACES:
        rows = space_size(cells, space)
        values = [cover(cells, space, even_draws(cells, n)) for n in (0, 5, 25, 100, 500, 5000)]
        assert values == sorted(values), space
        assert values[0] == pytest.approx(0.0)
        assert values[-1] <= rows
        assert cover(cells, space, even_draws(cells, 1_000_000)) == pytest.approx(rows)


def test_n_for_cover_is_the_point_where_coverage_arrives() -> None:
    cells = cell_probs(TINY)
    for space in SPACES:
        rows = space_size(cells, space)
        n = n_for_cover(cells, space, 0.5)
        assert cover(cells, space, even_draws(cells, n)) >= 0.5 * rows
        assert cover(cells, space, even_draws(cells, n - 1)) < 0.5 * rows


def test_n_for_count_scales_inversely_and_never_promises_the_impossible() -> None:
    assert n_for_count(0.25, 30) == 120
    assert n_for_count(1.0, 30) == 30
    assert n_for_count(0.0, 30) == float("inf")


def test_spaces_are_nested_in_row_count() -> None:
    """Coarsening a space cannot add rows, and `full` is the finest of the three."""
    cells = cell_probs(TINY)
    sizes = {space: space_size(cells, space) for space in SPACES}
    assert sizes["full"] == len(cells)
    assert sizes["scenario+property+light+weather"] <= sizes["full"]
    assert sizes["scenario+zone+light+weather"] <= sizes["full"]
    assert all(size > 0 for size in sizes.values())


def test_every_axis_is_a_distribution() -> None:
    table = marginals(cell_probs(TINY))
    assert set(table) == set(AXES)
    for axis in AXES:
        assert sum(table[axis].values()) == pytest.approx(1.0), axis
