"""The committed Tier B taxonomy (spec §1.2) and the rules that keep it coherent.

Every id the sampler can emit is declared here. Every subject and prop class has a term list,
and P3's `synthbench check` requires a prompt to mention one term from each.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthbench.contract.common import HHMM, SLUG, Label, RiskBand, ScenarioGroup

DEFAULT_TAXONOMY = Path(__file__).with_name("tier_b_v0.yaml")


class _Def(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LightingDef(_Def):
    id: str
    hours: tuple[tuple[HHMM, HHMM], ...] = Field(min_length=1)  # inclusive; may wrap midnight
    weight: float = Field(default=1.0, gt=0)
    outdoor_only: bool = False


class WeatherDef(_Def):
    id: str
    weight: float = Field(default=1.0, gt=0)


class ArtifactDef(_Def):
    id: str
    probability: float = Field(ge=0.0, le=1.0)
    lighting: tuple[str, ...] = ()  # empty: any lighting
    weather: tuple[str, ...] = ()  # empty: any weather
    outdoor_only: bool = False


class CameraDef(_Def):
    id: str
    zones: tuple[str, ...] = Field(min_length=1)
    indoor: bool = False


class PropertyDef(_Def):
    id: str
    zones: tuple[str, ...] = Field(min_length=1)


class SubjectDef(_Def):
    one_of: tuple[str, ...] = Field(min_length=1)
    role: str


class PropDef(_Def):
    one_of: tuple[str, ...] = Field(min_length=1)
    held_by: int | None = Field(default=None, ge=0)  # index into the scenario's subjects


class ScenarioDef(_Def):
    id: str
    group: ScenarioGroup
    label: Label
    risk_band: RiskBand
    weight: float = Field(default=1.0, gt=0)
    zones: tuple[str, ...] = Field(min_length=1)
    lighting: tuple[str, ...] = ()  # empty: any lighting
    weather: tuple[str, ...] = ()  # empty: any weather
    subjects: tuple[SubjectDef, ...] = ()
    props: tuple[PropDef, ...] = ()


class Taxonomy(_Def):
    version: str
    zones: tuple[str, ...] = Field(min_length=1)
    lighting: tuple[LightingDef, ...] = Field(min_length=1)
    weather: tuple[WeatherDef, ...] = Field(min_length=1)
    artifacts: tuple[ArtifactDef, ...] = ()
    cameras: tuple[CameraDef, ...] = Field(min_length=1)
    properties: tuple[PropertyDef, ...] = Field(min_length=1)
    colors: tuple[str, ...] = Field(min_length=1)
    garments: tuple[str, ...] = Field(min_length=1)
    clothed: tuple[str, ...] = ()  # subject classes that get a sampled clothing attribute
    terms: dict[str, tuple[str, ...]]
    scenarios: tuple[ScenarioDef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if problems := _problems(self):
            raise ValueError("taxonomy is inconsistent:\n  " + "\n  ".join(problems))
        return self


def compatible_cells(tax: Taxonomy, scenario: ScenarioDef) -> list[tuple[str, str, str]]:
    """Every (property, zone, camera) that can show the scenario, sorted so draws are stable."""
    return sorted(
        (prop.id, zone, camera.id)
        for prop in tax.properties
        for zone in scenario.zones
        if zone in prop.zones
        for camera in tax.cameras
        if zone in camera.zones
    )


def lighting_options(tax: Taxonomy, scenario: ScenarioDef, camera: CameraDef) -> list[LightingDef]:
    return [
        option
        for option in tax.lighting
        if (not scenario.lighting or option.id in scenario.lighting)
        and not (camera.indoor and option.outdoor_only)
    ]


def weather_options(tax: Taxonomy, scenario: ScenarioDef, camera: CameraDef) -> list[WeatherDef]:
    """Indoors the weather is always clear; outdoors it is whatever the scenario allows."""
    allowed = [w for w in tax.weather if not scenario.weather or w.id in scenario.weather]
    if camera.indoor:
        return [w for w in allowed if w.id == "clear"]
    return allowed


def artifact_options(
    tax: Taxonomy, camera: CameraDef, lighting_id: str, weather_id: str
) -> list[ArtifactDef]:
    return [
        artifact
        for artifact in tax.artifacts
        if (not artifact.lighting or lighting_id in artifact.lighting)
        and (not artifact.weather or weather_id in artifact.weather)
        and not (camera.indoor and artifact.outdoor_only)
    ]


def load_taxonomy(path: Path = DEFAULT_TAXONOMY) -> Taxonomy:
    return Taxonomy.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def taxonomy_sha256(path: Path = DEFAULT_TAXONOMY) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _duplicates(ids: Sequence[str]) -> list[str]:
    return sorted({i for i in ids if ids.count(i) > 1})


def _problems(tax: Taxonomy) -> list[str]:
    problems: list[str] = []
    if not SLUG.fullmatch(tax.version):
        problems.append(f"version {tax.version!r} must match {SLUG.pattern}")
    for kind, ids in (
        ("zones", list(tax.zones)),
        ("lighting", [x.id for x in tax.lighting]),
        ("weather", [x.id for x in tax.weather]),
        ("artifacts", [x.id for x in tax.artifacts]),
        ("cameras", [x.id for x in tax.cameras]),
        ("properties", [x.id for x in tax.properties]),
        ("scenarios", [x.id for x in tax.scenarios]),
    ):
        if dupes := _duplicates(ids):
            problems.append(f"duplicate {kind}: {dupes}")
    zones, lighting, weather = (
        set(tax.zones),
        {x.id for x in tax.lighting},
        {x.id for x in tax.weather},
    )
    holders: list[CameraDef | PropertyDef] = [*tax.cameras, *tax.properties]
    for holder in holders:
        if unknown := sorted(set(holder.zones) - zones):
            problems.append(f"{holder.id}: unknown zones {unknown}")
    for artifact in tax.artifacts:
        if unknown := sorted(set(artifact.lighting) - lighting) + sorted(
            set(artifact.weather) - weather
        ):
            problems.append(f"artifact {artifact.id}: unknown lighting or weather {unknown}")
    if any(camera.indoor for camera in tax.cameras) and "clear" not in weather:
        problems.append("an indoor camera needs a weather entry with id 'clear'")
    for name, words in tax.terms.items():
        if not words or any(not word or word != word.strip().lower() for word in words):
            problems.append(f"terms[{name}] must be non-empty, lowercase and trimmed")
    if unknown := sorted(set(tax.clothed) - set(tax.terms)):
        problems.append(f"clothed classes without a term list: {unknown}")
    for scenario in tax.scenarios:
        problems.extend(_scenario_problems(tax, scenario, zones, lighting, weather))
    return problems


def _scenario_problems(
    tax: Taxonomy, scenario: ScenarioDef, zones: set[str], lighting: set[str], weather: set[str]
) -> list[str]:
    where = f"scenario {scenario.id}"
    problems: list[str] = []
    if unknown := sorted(set(scenario.zones) - zones):
        problems.append(f"{where}: unknown zones {unknown}")
    if unknown := sorted(set(scenario.lighting) - lighting) + sorted(
        set(scenario.weather) - weather
    ):
        problems.append(f"{where}: unknown lighting or weather {unknown}")
    definitions: list[SubjectDef | PropDef] = [*scenario.subjects, *scenario.props]
    classes = {cls for d in definitions for cls in d.one_of}
    if unknown := sorted(classes - set(tax.terms)):
        problems.append(f"{where}: no term list for {unknown}")
    for prop in scenario.props:
        if prop.held_by is not None and prop.held_by >= len(scenario.subjects):
            problems.append(
                f"{where}: a prop is held by subject #{prop.held_by}, which does not exist"
            )
    cameras = {camera.id: camera for camera in tax.cameras}
    cells = compatible_cells(tax, scenario)
    for zone in sorted(set(scenario.zones) & zones):
        if not any(cell_zone == zone for _, cell_zone, _ in cells):
            problems.append(f"{where}: no property with a camera covers zone {zone}")
    for camera_id in sorted({camera_id for _, _, camera_id in cells}):
        camera = cameras[camera_id]
        if not lighting_options(tax, scenario, camera):
            problems.append(f"{where}: no lighting fits camera {camera_id}")
        if not weather_options(tax, scenario, camera):
            problems.append(f"{where}: no weather fits camera {camera_id}")
    return problems
