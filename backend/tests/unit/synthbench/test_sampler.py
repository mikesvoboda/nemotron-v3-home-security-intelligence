"""The seeded quota sampler (spec §7.2): determinism, quota coverage and legal cells."""

from __future__ import annotations

import hashlib
import random
from typing import Any

import pytest
from synthbench.contract.spec import Spec
from synthbench.taxonomy.model import (
    compatible_cells,
    lighting_options,
    load_taxonomy,
    weather_options,
)
from synthbench.taxonomy.sampler import (
    MAX_BATCH,
    allocate,
    default_seed,
    in_hours,
    sample_specs,
    time_in_hours,
)

TAX = load_taxonomy()  # at import: collection pays for the load, not a timed test
SCENARIOS = {s.id: s for s in TAX.scenarios}
CAMERAS = {c.id: c for c in TAX.cameras}
LIGHTING = {x.id: x for x in TAX.lighting}
ARTIFACTS = {a.id: a for a in TAX.artifacts}


def _specs(**overrides: Any) -> list[Spec]:
    args: dict[str, Any] = {"version": "tierb-v0", "batch": "pilot-1", "n": 60, "seed": 7}
    args.update(overrides)
    return sample_specs(TAX, **args)


def test_the_same_request_gives_the_same_specs() -> None:
    assert _specs() == _specs()


def test_the_seed_and_the_batch_name_both_change_the_draws() -> None:
    base = [s.cell for s in _specs()]
    assert [s.cell for s in _specs(seed=8)] != base
    assert [s.cell for s in _specs(batch="pilot-2")] != base


def test_event_ids_count_up_within_the_batch() -> None:
    assert [s.event_id for s in _specs(n=3)] == ["B-pilot-1-000", "B-pilot-1-001", "B-pilot-1-002"]


def test_every_scenario_stays_within_one_of_its_weighted_share() -> None:
    counts: dict[str, int] = {}
    total_weight = sum(s.weight for s in TAX.scenarios)
    total = 0
    for n in (10, 50, 37, 200, 3):  # each batch carries its predecessors' counts forward
        for scenario_id in allocate(TAX, n, counts):
            counts[scenario_id] = counts.get(scenario_id, 0) + 1
        total += n
        for scenario in TAX.scenarios:
            share = scenario.weight / total_weight * total
            assert abs(counts.get(scenario.id, 0) - share) < 1, (scenario.id, total)


def test_allocation_fills_the_scenario_earlier_batches_left_short() -> None:
    prior = {s.id: 5 for s in TAX.scenarios if s.id != "knife_visible"}
    assert allocate(TAX, 1, prior) == ["knife_visible"]


def test_only_restricts_the_scenarios_and_rejects_unknown_ids() -> None:
    picked = set(allocate(TAX, 20, {}, only=["firearm_visible", "knife_visible"]))
    assert picked == {"firearm_visible", "knife_visible"}
    with pytest.raises(ValueError, match="unknown scenarios: nope"):
        allocate(TAX, 1, {}, only=["nope"])


@pytest.mark.parametrize("n", [0, MAX_BATCH + 1])
def test_batch_size_is_bounded(n: int) -> None:
    with pytest.raises(ValueError, match=f"1..{MAX_BATCH}"):
        _specs(n=n)


def test_every_spec_is_a_legal_cell() -> None:
    for spec in _specs(n=300):
        scenario = SCENARIOS[spec.cell.scenario]
        camera = CAMERAS[spec.cell.camera]
        cell = (spec.cell.property_type, spec.cell.zone, spec.cell.camera)
        assert cell in compatible_cells(TAX, scenario)
        assert spec.cell.lighting in {x.id for x in lighting_options(TAX, scenario, camera)}
        assert spec.cell.weather in {w.id for w in weather_options(TAX, scenario, camera)}
        assert in_hours(spec.scene_time, LIGHTING[spec.cell.lighting].hours), spec.event_id
        assert (spec.label, spec.risk_band) == (scenario.label, scenario.risk_band)
        assert spec.cell.group == scenario.group


def test_artifacts_respect_their_requirements() -> None:
    seen: set[str] = set()
    for spec in _specs(n=400, seed=3):
        for artifact_id in spec.cell.artifacts:
            artifact = ARTIFACTS[artifact_id]
            seen.add(artifact_id)
            assert not artifact.lighting or spec.cell.lighting in artifact.lighting
            assert not artifact.weather or spec.cell.weather in artifact.weather
            assert not (CAMERAS[spec.cell.camera].indoor and artifact.outdoor_only)
    assert seen, "400 draws produced no artifact at all"


def test_subjects_and_props_follow_the_scenario() -> None:
    for spec in _specs(n=200, seed=11):
        scenario = SCENARIOS[spec.cell.scenario]
        assert [s.role for s in spec.subjects] == [d.role for d in scenario.subjects]
        for subject, definition in zip(spec.subjects, scenario.subjects, strict=True):
            assert subject.cls in definition.one_of
            assert ("clothing" in subject.attributes) == (subject.cls in TAX.clothed)
        for prop, definition in zip(spec.props, scenario.props, strict=True):
            assert prop.cls in definition.one_of
            holder = None if definition.held_by is None else f"S{definition.held_by + 1}"
            assert prop.held_by == holder


def test_specs_leave_the_prompt_to_the_agent() -> None:
    assert all(s.prompt is None and s.camera_suffix is None for s in _specs(n=20))


def test_scene_times_wrap_midnight() -> None:
    rng = random.Random("wrap")  # noqa: S311  # a seeded test draw, not security
    night = (("20:00", "05:29"),)
    times = [time_in_hours(night, rng) for _ in range(2000)]
    assert all(in_hours(t, night) for t in times)
    assert any(t >= "20:00" for t in times) and any(t <= "05:29" for t in times)
    assert not in_hours("12:00", night)
    assert in_hours("05:29", night) and not in_hours("05:30", night)


def test_the_default_seed_is_stable_across_runs() -> None:
    assert default_seed("pilot-1") == int(hashlib.sha256(b"pilot-1").hexdigest()[:8], 16)


def test_specs_survive_a_json_round_trip() -> None:
    for spec in _specs(n=40):
        assert Spec.model_validate_json(spec.model_dump_json(exclude_none=True)) == spec
