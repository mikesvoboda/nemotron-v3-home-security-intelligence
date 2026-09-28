"""The committed Tier B taxonomy (spec §1.2) and the rules that keep it coherent."""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Callable
from typing import Any

import pytest
import yaml
from pydantic import ValidationError
from synthbench.taxonomy.model import (
    DEFAULT_TAXONOMY,
    Taxonomy,
    compatible_cells,
    lighting_options,
    load_taxonomy,
    taxonomy_sha256,
    weather_options,
)

TAX = load_taxonomy()  # at import: collection pays for the load, not a timed test
RAW: dict[str, Any] = yaml.safe_load(DEFAULT_TAXONOMY.read_text(encoding="utf-8"))


def _scenario(raw: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    return next(s for s in raw["scenarios"] if s["id"] == scenario_id)


def test_the_committed_taxonomy_loads() -> None:
    assert TAX.version == "tierb-v0"
    groups = {s.group for s in TAX.scenarios}
    assert groups == {"benign", "hard_negative", "suspicious", "threat", "ambiguous"}


def test_labels_follow_the_groups() -> None:
    expected = {
        "benign": "benign",
        "hard_negative": "benign",
        "ambiguous": "ambiguous",
        "suspicious": "incident",
        "threat": "incident",
    }
    for scenario in TAX.scenarios:
        assert scenario.label == expected[scenario.group], scenario.id


def test_every_zone_of_every_scenario_has_a_camera() -> None:
    for scenario in TAX.scenarios:
        covered = {zone for _, zone, _ in compatible_cells(TAX, scenario)}
        assert covered == set(scenario.zones), scenario.id


def test_indoor_cameras_get_clear_weather_and_no_porch_light() -> None:
    indoor = next(c for c in TAX.cameras if c.indoor)
    scenario = next(s for s in TAX.scenarios if s.id == "masked_intruder_night")
    assert [w.id for w in weather_options(TAX, scenario, indoor)] == ["clear"]
    assert [x.id for x in lighting_options(TAX, scenario, indoor)] == ["ir_night"]


def test_the_digest_is_the_file_sha256() -> None:
    assert taxonomy_sha256() == hashlib.sha256(DEFAULT_TAXONOMY.read_bytes()).hexdigest()


def _unknown_zone(raw: dict[str, Any]) -> None:
    _scenario(raw, "delivery_driver")["zones"].append("moon")


def _prop_without_terms(raw: dict[str, Any]) -> None:
    _scenario(raw, "delivery_driver")["props"] = [{"one_of": ["lightsaber"], "held_by": 0}]


def _held_by_missing_subject(raw: dict[str, Any]) -> None:
    _scenario(raw, "delivery_driver")["props"] = [{"one_of": ["package"], "held_by": 5}]


def _duplicate_scenario(raw: dict[str, Any]) -> None:
    raw["scenarios"].append(copy.deepcopy(raw["scenarios"][0]))


def _uppercase_term(raw: dict[str, Any]) -> None:
    raw["terms"]["knife"] = ["Knife"]


def _zone_without_camera(raw: dict[str, Any]) -> None:
    raw["zones"].append("attic")
    raw["properties"][0]["zones"].append("attic")
    _scenario(raw, "delivery_driver")["zones"].append("attic")


def _snow_indoors(raw: dict[str, Any]) -> None:
    _scenario(raw, "pet_activity")["weather"] = ["snow"]


def _unknown_lighting(raw: dict[str, Any]) -> None:
    _scenario(raw, "delivery_driver")["lighting"] = ["noon"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_unknown_zone, "unknown zones"),
        (_prop_without_terms, "no term list"),
        (_held_by_missing_subject, "does not exist"),
        (_duplicate_scenario, "duplicate scenarios"),
        (_uppercase_term, "lowercase"),
        (_zone_without_camera, "no property with a camera covers zone attic"),
        (_snow_indoors, "no weather fits camera indoor_corner"),
        (_unknown_lighting, "unknown lighting or weather"),
    ],
)
def test_inconsistencies_are_reported(
    mutate: Callable[[dict[str, Any]], None], message: str
) -> None:
    raw = copy.deepcopy(RAW)
    mutate(raw)
    with pytest.raises(ValidationError, match=message):
        Taxonomy.model_validate(raw)
