# Synthbench P2: Contract and Sampler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the event contract (spec, truth and provenance models), the committed Tier B v0
taxonomy, the seeded quota sampler, and `python -m synthbench sample`. That command writes a
batch of fact-only specs into a corpus version, ready for the flagship agent to prompt in P3.

**Architecture:** `synthbench/contract/` holds frozen pydantic models and a small store that
writes JSON atomically and never replaces a file, because the corpus is append-only.
`synthbench/taxonomy/` holds one committed YAML file, its validating loader, and a deterministic
sampler. Scenario counts come from Balinski and Young's quota method. Each event's draws use
`random.Random(f"{seed}:{batch}:{index}")`. `synthbench/cli.py` wires the sampler to the store
behind `python -m synthbench`. No GPU and no network.

**Tech Stack:** Python 3.14, pydantic 2.13 (mypy plugin on), PyYAML 6, argparse. pytest with
xdist, `-p randomly` and pytest-timeout (5 s including setup and teardown). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md` (rev 3:
§1.2, §1.3, §2, §7.1, §7.2), as scoped by
`docs/superpowers/specs/2026-09-28-synthbench-agent-driven-generation-design.md` (§2, §3 step 1,
§9 item 1). Read both before starting.

## Rulings made while planning (the executor does not revisit these)

- **P2-R1: `expectations()`, and the scoring-profile model it takes, move to P5.** The parent
  §7.3 lists `expectations()` under P2. Its inputs are a
  scoring profile (thresholds captured from the benchmark instance when a run starts) and the run
  ledger (§2.2), both defined by P5, and no generation step consumes it. The approved agent-driven
  design (§9) scopes P2 without it.
- **P2-R2: the CLI is `python -m synthbench <command>`.** The repo is not an installable package
  (no `[project.scripts]` or build backend), so a bare `synthbench` command would need packaging
  changes. The design's `synthbench <command>` is shorthand for this.
- **P2-R3: the corpus root is `$SYNTHBENCH_ROOT/corpus`**, defaulting to
  `/export/synthbench/corpus`, which is the ZFS dataset created on 2026-09-28. No new
  environment variable.
- **P2-R4: the label set has no "suspicious"** (§1.3: incident, benign, ambiguous). Suspicious
  scenarios are labeled `incident` with lower risk bands, and hard negatives are `benign`. The
  YAML's scenario list, risk bands and weights are a **v0 draft for the owner to review**. The
  taxonomy header comment says so.
- **P2-R5: scenario allocation uses the quota method.** A plain "largest deficit" rule was
  simulated first and exceeded the ±1 bound (worst 1.04). The quota method's worst case over 300
  random taxonomies × 20 carried-forward batches was 0.985.

## Global Constraints

- The contract is pydantic models in `synthbench/contract/`, each file model with a
  `schema_version` (parent §2.1). Truth stores facts, never expected model outputs (§2.2).
- The corpus lives outside the repo; git holds only schemas, taxonomy and sampler config (§2.6).
  The corpus is **append-only** (design §2): code never deletes, moves or overwrites a corpus
  file. `CorpusStore.write_new` is the only writer and raises `FileExistsError` rather than
  replace.
- Sampler determinism: the same seed, batch and prior counts give identical specs. Quota
  coverage: every scenario stays within 1 of its weighted share (§7.2).
- The sampler fixes every ground-truth fact. Specs leave `prompt` and `camera_suffix` unset;
  P3's `check` sets both together (design G4, §3.1).
- Tier B event ids are `B-<batch>-NNN`. Batch names and corpus versions match
  `[a-z0-9][a-z0-9-]{0,39}`. At most 500 events per batch.
- Exit codes for every command: `0` done, `1` error (fix the request), `2` stop and ask the owner
  (design §3). argparse usage errors must exit **1**, not argparse's default 2.
- Only `synthbench/score/` and `synthbench/run/` may import `backend` (§7.1); P2 adds neither.
- Never import a new module from `synthbench/__init__.py`. It is linted as Python 3.12 because
  the renderer container imports it.
- Tests live in `backend/tests/unit/synthbench/`. No GPU, no network, no real sleeps, and no
  writes outside `tmp_path`. Each test finishes in well under 5 s _including fixture setup_.
  Load the taxonomy at module level so collection pays for it, not a test.
- Content rules (§3.8): scenario content is realistic and non-graphic. No injury detail, no
  real people.
- Lint and types: ruff (S, T20: no `print`, write to `sys.stdout`/`sys.stderr`; PTH; PL; RUF
  including RUF100) and mypy (`disallow_untyped_defs`, pydantic plugin) must pass on
  `synthbench/`. CI's Vulture job scans `backend/`, tests included, at 100% confidence on unused
  parameters. Run it before any push:
  `uv run vulture backend/ vulture_whitelist.py --config pyproject.toml`.
- Commits: `SKIP=semgrep uvx pre-commit run --files <files> && git commit ...`. Never
  `--no-verify`, and never chain with `;`. Messages are conventional commits ending with the
  line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

### Task 1: Contract models

**Files:**

- Create: `synthbench/contract/__init__.py`, `synthbench/contract/common.py`,
  `synthbench/contract/spec.py`, `synthbench/contract/truth.py`,
  `synthbench/contract/provenance.py`, `synthbench/contract/corpus.py`
- Test: `backend/tests/unit/synthbench/test_contract.py`

**Interfaces:**

- Produces (`common.py`): `ContractModel` (base: `extra="forbid"`, frozen, validate by name and
  alias, serialize by alias); `Label`, `FactStatus`, `Tier`, `ScenarioGroup` (Literals); `SLUG`
  (compiled regex); `Box`, `HHMM`, `RiskBand`, `Sha256` (Annotated validated types).
- Produces (`spec.py`): `Cell(scenario, group, property_type, zone, camera, lighting, weather,
artifacts=())`, `Subject(id, cls [JSON "class"], role, attributes={})`,
  `Prop(id, cls [JSON "class"], held_by=None)`, `Spec(schema_version=1, event_id, tier,
corpus_version, batch, cell, scene_time, label, risk_band, subjects=(), props=(), prompt=None,
camera_suffix=None)`.
- Produces (`truth.py`): `Truth` with `Face`, `TruthObject`, `Still`, `CastEntry`,
  `TimelineEntry`, exactly the shape of parent §2.3.
- Produces (`provenance.py`): `MAX_ATTEMPTS = 3`, `TriageReason` (7 literals), `OutputFile`,
  `Triage`, `Attempt`, `Provenance`.
- Produces (`corpus.py`): `TIER_B_RENDER_SIZE = (1280, 720)`, `EventStatus`, `CorpusManifest`,
  `BatchRecord(... prior_counts ...)`, `IndexRow`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_contract.py`:

```python
"""The event contract (spec §2): round-trips, validation, and the `class` JSON key."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from synthbench.contract.corpus import BatchRecord, CorpusManifest, IndexRow
from synthbench.contract.provenance import (
    MAX_ATTEMPTS,
    Attempt,
    OutputFile,
    Provenance,
    Triage,
)
from synthbench.contract.spec import Cell, Prop, Spec, Subject
from synthbench.contract.truth import Truth, TruthObject

SHA = "0" * 64
WHEN = "2026-09-28T00:00:00+00:00"

# Parent spec §2.3's example, verbatim.
TRUTH_EXAMPLE: dict[str, Any] = {
    "schema_version": 1,
    "event_id": "A-lakehouse-dock_cam2-00417",
    "tier": "A",
    "site": "lakehouse",
    "camera": "dock_cam2",
    "scene_time": "02:14",
    "conditions": ["ir_night", "fog"],
    "label": "incident",
    "risk_band": [85, 100],
    "scenario": "armed_intruder_dock",
    "cast": {"S3": {"role": "stranger", "enrolled": False}},
    "stills": [
        {
            "file": "stills/002.jpg",
            "t": 2.4,
            "objects": [
                {
                    "id": "S3",
                    "class": "person",
                    "bbox": [0.58, 0.31, 0.72, 0.93],
                    "zone": "dock",
                    "face": {"visible": True, "height_px": 38},
                    "posture": "crouching",
                },
                {
                    "class": "handgun",
                    "held_by": "S3",
                    "bbox": [0.66, 0.55, 0.69, 0.6],
                    "visible": True,
                },
            ],
            "fact_provenance": {"S3.bbox": "verified", "handgun": "verified"},
        }
    ],
    "timeline": [
        {"actor": "S3", "action": "climbs_onto_dock", "t": [0.0, 1.8]},
        {"actor": "S3", "action": "approaches_door_with_weapon", "t": [1.8, 6.0]},
    ],
}


def _spec(**overrides: Any) -> Spec:
    fields: dict[str, Any] = {
        "event_id": "B-pilot-1-000",
        "tier": "B",
        "corpus_version": "tierb-v0",
        "batch": "pilot-1",
        "cell": Cell(
            scenario="knife_visible",
            group="threat",
            property_type="suburban_house",
            zone="front_porch",
            camera="doorbell_fisheye",
            lighting="day",
            weather="clear",
        ),
        "scene_time": "14:05",
        "label": "incident",
        "risk_band": (80, 100),
        "subjects": (
            Subject(id="S1", cls="person", role="stranger", attributes={"clothing": "gray hoodie"}),
        ),
        "props": (Prop(id="X1", cls="knife", held_by="S1"),),
    }
    fields.update(overrides)
    return Spec(**fields)


def _attempt(k: int) -> Attempt:
    return Attempt(k=k, seed=k, prompt_sha256=SHA)


def test_the_spec_example_truth_round_trips_verbatim() -> None:
    truth = Truth.model_validate(TRUTH_EXAMPLE)
    assert truth.model_dump(mode="json", exclude_none=True) == TRUTH_EXAMPLE


def test_truth_objects_use_the_class_key() -> None:
    obj = TruthObject(cls="handgun", bbox=(0.1, 0.1, 0.2, 0.2))
    assert obj.model_dump(mode="json", exclude_none=True) == {
        "class": "handgun",
        "bbox": [0.1, 0.1, 0.2, 0.2],
    }


@pytest.mark.parametrize(
    "bbox",
    [(0.5, 0.1, 0.4, 0.2), (0.1, 0.1, 0.2, 1.2), (-0.1, 0.0, 0.2, 0.2), (0.1, 0.3, 0.2, 0.3)],
)
def test_boxes_are_normalized_and_non_empty(bbox: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValidationError, match="box must be normalized"):
        TruthObject(cls="person", bbox=bbox)


def test_a_spec_dumps_class_keys_and_no_nulls() -> None:
    dumped = _spec().model_dump(mode="json", exclude_none=True)
    assert dumped["subjects"][0]["class"] == "person"
    assert dumped["props"][0] == {"id": "X1", "class": "knife", "held_by": "S1"}
    assert "prompt" not in dumped
    assert "camera_suffix" not in dumped


def test_a_spec_survives_a_json_round_trip() -> None:
    spec = _spec()
    assert Spec.model_validate_json(spec.model_dump_json(exclude_none=True)) == spec


@pytest.mark.parametrize("scene_time", ["24:00", "7:05", "07:60", "0705"])
def test_scene_time_is_hh_mm(scene_time: str) -> None:
    with pytest.raises(ValidationError, match="HH:MM"):
        _spec(scene_time=scene_time)


@pytest.mark.parametrize("band", [(90, 80), (-1, 10), (50, 101)])
def test_risk_band_is_ordered_within_0_to_100(band: tuple[int, int]) -> None:
    with pytest.raises(ValidationError, match="risk_band"):
        _spec(risk_band=band)


def test_unknown_keys_are_rejected() -> None:
    data = _spec().model_dump(mode="json")
    data["mood"] = "tense"
    with pytest.raises(ValidationError, match="Extra inputs"):
        Spec.model_validate(data)


def test_schema_version_is_pinned() -> None:
    data = _spec().model_dump(mode="json")
    data["schema_version"] = 2
    with pytest.raises(ValidationError):
        Spec.model_validate(data)


@pytest.mark.parametrize("event_id", ["B-other-000", "B-pilot-1-7", "A-pilot-1-000"])
def test_tier_b_event_ids_name_their_batch(event_id: str) -> None:
    with pytest.raises(ValidationError, match="B-<batch>-NNN"):
        _spec(event_id=event_id)


def test_names_are_slugs() -> None:
    with pytest.raises(ValidationError, match="must match"):
        _spec(batch="Pilot 1", event_id="B-Pilot 1-000")


def test_a_prop_is_held_by_a_known_subject() -> None:
    with pytest.raises(ValidationError, match="unknown subject"):
        _spec(props=(Prop(id="X1", cls="knife", held_by="S9"),))


def test_subject_and_prop_ids_are_unique() -> None:
    with pytest.raises(ValidationError, match="unique"):
        _spec(props=(Prop(id="S1", cls="knife"),))


def test_prompt_and_camera_suffix_are_frozen_together() -> None:
    with pytest.raises(ValidationError, match="frozen together"):
        _spec(prompt="a man at a front door holding a knife")
    frozen = _spec(
        prompt="a man at a front door holding a knife",
        camera_suffix="fixed security camera view, no on-screen text, no timestamp, no watermark",
    )
    assert Spec.model_validate_json(frozen.model_dump_json()) == frozen


def test_a_reroll_needs_a_listed_reason() -> None:
    assert Triage(verdict="reroll", reason="blank").reason == "blank"
    assert Triage(verdict="ok").reason is None
    with pytest.raises(ValidationError, match="needs a reason"):
        Triage(verdict="reroll")
    with pytest.raises(ValidationError, match="needs a reason"):
        Triage(verdict="ok", reason="blank")
    with pytest.raises(ValidationError):
        Triage.model_validate({"verdict": "reroll", "reason": "cannot_see_the_knife"})


def test_attempts_are_numbered_and_capped() -> None:
    capped = Provenance(event_id="B-pilot-1-000", attempts=tuple(_attempt(k) for k in (1, 2, 3)))
    assert len(capped.attempts) == MAX_ATTEMPTS
    with pytest.raises(ValidationError, match=r"numbered 1\.\.n"):
        Provenance(event_id="B-pilot-1-000", attempts=(_attempt(1), _attempt(3)))
    with pytest.raises(ValidationError, match=f"at most {MAX_ATTEMPTS}"):
        Provenance(event_id="B-pilot-1-000", attempts=tuple(_attempt(k) for k in range(1, 5)))


@pytest.mark.parametrize("path", ["/abs/a1.png", "../a1.png", ""])
def test_output_paths_stay_inside_the_event_directory(path: str) -> None:
    assert OutputFile(path="renders/a1-s7.png", sha256=SHA).path == "renders/a1-s7.png"
    with pytest.raises(ValidationError, match="relative to the event directory"):
        OutputFile(path=path, sha256=SHA)


@pytest.mark.parametrize("digest", ["ABC", "0" * 63, "g" * 64])
def test_hashes_are_64_lowercase_hex(digest: str) -> None:
    with pytest.raises(ValidationError, match="64 lowercase hex"):
        Attempt(k=1, seed=0, prompt_sha256=digest)


def test_a_batch_record_lists_exactly_n_events() -> None:
    record = BatchRecord(
        name="pilot-1", version="tierb-v0", seed=1, n=1, event_ids=("B-pilot-1-000",), created=WHEN
    )
    assert record.prior_counts == {}
    with pytest.raises(ValidationError, match="n=2"):
        BatchRecord(
            name="pilot-1",
            version="tierb-v0",
            seed=1,
            n=2,
            event_ids=("B-pilot-1-000",),
            created=WHEN,
        )
    with pytest.raises(ValidationError, match="must match"):
        BatchRecord(
            name="Pilot 1", version="tierb-v0", seed=1, n=1, event_ids=("B-x-000",), created=WHEN
        )


def test_manifest_and_index_rows_validate() -> None:
    manifest = CorpusManifest(
        version="tierb-v0", taxonomy_sha256=SHA, render_size=(1280, 720), created=WHEN
    )
    assert manifest.render_size == (1280, 720)
    with pytest.raises(ValidationError, match="must match"):
        CorpusManifest(
            version="tierb v0", taxonomy_sha256=SHA, render_size=(1280, 720), created=WHEN
        )
    with pytest.raises(ValidationError, match="render_size"):
        CorpusManifest(version="tierb-v0", taxonomy_sha256=SHA, render_size=(0, 720), created=WHEN)
    row = IndexRow(
        event_id="B-pilot-1-000",
        batch="pilot-1",
        scenario="knife_visible",
        label="incident",
        status="sampled",
        time=WHEN,
    )
    assert row.status == "sampled"
    with pytest.raises(ValidationError):
        IndexRow.model_validate({**row.model_dump(), "status": "accepted"})
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_contract.py -q -n0 -p no:randomly`
Expected: collection error, `ModuleNotFoundError: No module named 'synthbench.contract'`.

- [ ] **Step 3: Write the contract**

`synthbench/contract/__init__.py`:

```python
"""Event contract (spec §2): spec, truth and provenance models, and the corpus store."""
```

`synthbench/contract/common.py`:

```python
"""Shared contract types (spec §2): the base model, labels, boxes, times, bands and hashes."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict

Label = Literal["incident", "benign", "ambiguous"]
FactStatus = Literal["declared", "verified", "audited"]
Tier = Literal["A", "B"]
ScenarioGroup = Literal["benign", "hard_negative", "suspicious", "threat", "ambiguous"]

# Corpus versions and batch names: lowercase letters, digits and hyphens.
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_HHMM = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ContractModel(BaseModel):
    """Base of every contract model: unknown keys are errors and instances are immutable.

    JSON keys are the aliases (`class`); Python code uses the field names (`cls`).
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


def _check_box(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = value
    if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
        raise ValueError(f"box must be normalized [x0, y0, x1, y1], x0 < x1, y0 < y1: {value}")
    return value


def _check_hhmm(value: str) -> str:
    if not _HHMM.fullmatch(value):
        raise ValueError(f"time must be HH:MM between 00:00 and 23:59: {value!r}")
    return value


def _check_band(value: tuple[int, int]) -> tuple[int, int]:
    low, high = value
    if not 0 <= low <= high <= 100:
        raise ValueError(f"risk_band must be [low, high], 0 <= low <= high <= 100: {value}")
    return value


def _check_sha256(value: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ValueError(f"expected 64 lowercase hex characters: {value!r}")
    return value


Box = Annotated[tuple[float, float, float, float], AfterValidator(_check_box)]
HHMM = Annotated[str, AfterValidator(_check_hhmm)]
RiskBand = Annotated[tuple[int, int], AfterValidator(_check_band)]
Sha256 = Annotated[str, AfterValidator(_check_sha256)]
```

`synthbench/contract/spec.py`:

```python
"""spec.json: an event's intent, written by the sampler (spec §2.1).

The sampler fixes every fact that becomes ground truth. The prompt and the camera suffix are
added later, together and once, before rendering (agent-driven design §3.1).
"""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import Field, model_validator

from synthbench.contract.common import (
    HHMM,
    SLUG,
    ContractModel,
    Label,
    RiskBand,
    ScenarioGroup,
    Tier,
)


class Cell(ContractModel):
    """The taxonomy cell the event was sampled from (spec §1.2)."""

    scenario: str
    group: ScenarioGroup
    property_type: str
    zone: str
    camera: str
    lighting: str
    weather: str
    artifacts: tuple[str, ...] = ()


class Subject(ContractModel):
    """A person, child or animal. Tier B subjects are anonymous (spec §1.1)."""

    id: str
    cls: str = Field(alias="class")
    role: str
    attributes: dict[str, str] = Field(default_factory=dict)


class Prop(ContractModel):
    """An object the image must show; `held_by` names a subject id."""

    id: str
    cls: str = Field(alias="class")
    held_by: str | None = None


class Spec(ContractModel):
    schema_version: Literal[1] = 1
    event_id: str
    tier: Tier
    corpus_version: str
    batch: str
    cell: Cell
    scene_time: HHMM
    label: Label
    risk_band: RiskBand
    subjects: tuple[Subject, ...] = ()
    props: tuple[Prop, ...] = ()
    prompt: str | None = None
    camera_suffix: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for name in (self.corpus_version, self.batch):
            if not SLUG.fullmatch(name):
                raise ValueError(f"{name!r} must match {SLUG.pattern}")
        tier_b_id = rf"B-{re.escape(self.batch)}-\d{{3}}"
        if self.tier == "B" and not re.fullmatch(tier_b_id, self.event_id):
            raise ValueError(f"a Tier B event_id is B-<batch>-NNN, got {self.event_id!r}")
        if not self.event_id.startswith(f"{self.tier}-"):
            raise ValueError(f"event_id {self.event_id!r} must start with {self.tier}-")
        ids = [s.id for s in self.subjects] + [p.id for p in self.props]
        if len(ids) != len(set(ids)):
            raise ValueError(f"subject and prop ids must be unique: {ids}")
        subject_ids = {s.id for s in self.subjects}
        for prop in self.props:
            if prop.held_by is not None and prop.held_by not in subject_ids:
                raise ValueError(f"prop {prop.id} is held by unknown subject {prop.held_by!r}")
        if (self.prompt is None) != (self.camera_suffix is None):
            raise ValueError("prompt and camera_suffix are frozen together")
        return self
```

`synthbench/contract/truth.py`:

```python
"""truth.json: the world facts of each still (spec §2.1-§2.3). P4's packager writes it."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from synthbench.contract.common import (
    HHMM,
    Box,
    ContractModel,
    FactStatus,
    Label,
    RiskBand,
    Tier,
)


class Face(ContractModel):
    visible: bool
    height_px: int | None = Field(default=None, ge=1)


class TruthObject(ContractModel):
    id: str | None = None
    cls: str = Field(alias="class")
    bbox: Box
    zone: str | None = None
    face: Face | None = None
    posture: str | None = None
    held_by: str | None = None
    visible: bool | None = None


class Still(ContractModel):
    file: str
    t: float = Field(default=0.0, ge=0.0)
    objects: tuple[TruthObject, ...] = ()
    fact_provenance: dict[str, FactStatus] = Field(default_factory=dict)


class CastEntry(ContractModel):
    role: str
    enrolled: bool = False


class TimelineEntry(ContractModel):
    actor: str
    action: str
    t: tuple[float, float]

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        start, end = self.t
        if not 0.0 <= start <= end:
            raise ValueError(f"timeline t must be [start, end], 0 <= start <= end: {self.t}")
        return self


class Truth(ContractModel):
    schema_version: Literal[1] = 1
    event_id: str
    tier: Tier
    site: str | None = None
    camera: str
    scene_time: HHMM
    conditions: tuple[str, ...] = ()
    label: Label
    risk_band: RiskBand
    scenario: str
    cast: dict[str, CastEntry] = Field(default_factory=dict)
    stills: tuple[Still, ...]
    timeline: tuple[TimelineEntry, ...] = ()
```

`synthbench/contract/provenance.py`:

```python
"""provenance.json: every attempt at an event (spec §2.1; agent-driven design §2 and §4)."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import Field, model_validator

from synthbench.contract.common import ContractModel, Sha256

# Parent spec §4.2: at most 3 seeds per event, shared by the agent's triage and the verifier.
MAX_ATTEMPTS = 3

# Agent-driven design §4: the only reasons the agent may reroll an event.
TriageReason = Literal[
    "blank",
    "refusal_card",
    "wrong_scene",
    "no_person",
    "broken_anatomy",
    "not_security_camera",
    "text_overlay",
]


class OutputFile(ContractModel):
    """A file an attempt produced, relative to the event directory, with its sha256."""

    path: str
    sha256: Sha256

    @model_validator(mode="after")
    def _relative(self) -> Self:
        pure = PurePosixPath(self.path)
        if not self.path or pure.is_absolute() or ".." in pure.parts:
            raise ValueError(f"path must be relative to the event directory: {self.path!r}")
        return self


class Triage(ContractModel):
    verdict: Literal["ok", "reroll"]
    reason: TriageReason | None = None

    @model_validator(mode="after")
    def _reason_matches_verdict(self) -> Self:
        if (self.verdict == "reroll") != (self.reason is not None):
            raise ValueError("a reroll needs a reason from the list; an ok verdict has none")
        return self


class Attempt(ContractModel):
    k: int = Field(ge=1)
    seed: int = Field(ge=0)
    prompt_sha256: Sha256
    models: dict[str, Sha256] = Field(default_factory=dict)
    render: OutputFile | None = None
    render_seconds: float | None = Field(default=None, ge=0.0)
    still: OutputFile | None = None
    camera_params: str | None = None
    triage: Triage | None = None


class Provenance(ContractModel):
    schema_version: Literal[1] = 1
    event_id: str
    attempts: tuple[Attempt, ...] = ()

    @model_validator(mode="after")
    def _attempts(self) -> Self:
        ks = [attempt.k for attempt in self.attempts]
        if ks != list(range(1, len(ks) + 1)):
            raise ValueError(f"attempts must be numbered 1..n in order, got {ks}")
        if len(ks) > MAX_ATTEMPTS:
            raise ValueError(
                f"at most {MAX_ATTEMPTS} attempts per event (spec §4.2), got {len(ks)}"
            )
        return self
```

`synthbench/contract/corpus.py`:

```python
"""Corpus records (spec §2.6; agent-driven design §2): corpus.json, batch.json, index.jsonl."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from synthbench.contract.common import SLUG, ContractModel, Label, Sha256

# Agent-driven design G7: Tier B renders at 1280x720; the camera stage makes the 1920x1080 still.
TIER_B_RENDER_SIZE = (1280, 720)

EventStatus = Literal["sampled", "prompted", "rendered", "failed"]


class CorpusManifest(ContractModel):
    """corpus.json: what a corpus version is built from. Render size is part of its identity."""

    schema_version: Literal[1] = 1
    version: str
    taxonomy_sha256: Sha256
    render_size: tuple[int, int]
    created: str

    @model_validator(mode="after")
    def _valid(self) -> Self:
        if not SLUG.fullmatch(self.version):
            raise ValueError(f"corpus version {self.version!r} must match {SLUG.pattern}")
        if min(self.render_size) < 1:
            raise ValueError(f"render_size must be positive: {self.render_size}")
        return self


class BatchRecord(ContractModel):
    """batch.json: one sample request, with everything needed to regenerate it exactly."""

    schema_version: Literal[1] = 1
    name: str
    version: str
    seed: int = Field(ge=0)
    n: int = Field(ge=1)
    only: tuple[str, ...] = ()
    prior_counts: dict[str, int] = Field(default_factory=dict)
    event_ids: tuple[str, ...]
    created: str

    @model_validator(mode="after")
    def _valid(self) -> Self:
        for name in (self.name, self.version):
            if not SLUG.fullmatch(name):
                raise ValueError(f"{name!r} must match {SLUG.pattern}")
        if len(self.event_ids) != self.n:
            raise ValueError(f"the batch lists {len(self.event_ids)} events but n={self.n}")
        return self


class IndexRow(ContractModel):
    """One index.jsonl row: an event's state change. The latest row per event wins."""

    event_id: str
    batch: str
    scenario: str
    label: Label
    status: EventStatus
    time: str
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/test_contract.py -q -n0 -p no:randomly`
Expected: all pass. Then `uv run mypy synthbench/contract/` gives `Success`, and
`uv run ruff check synthbench/contract/ backend/tests/unit/synthbench/test_contract.py` is clean.

- [ ] **Step 5: Gate and commit**

```bash
F="synthbench/contract/__init__.py synthbench/contract/common.py synthbench/contract/spec.py synthbench/contract/truth.py synthbench/contract/provenance.py synthbench/contract/corpus.py backend/tests/unit/synthbench/test_contract.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): event contract models - spec, truth, provenance, corpus records

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

If a hook reformats files, re-run the same command so the commit is gated on a clean pass.

---

### Task 2: Corpus store

**Files:**

- Create: `synthbench/contract/store.py`
- Test: `backend/tests/unit/synthbench/test_contract_store.py`

**Interfaces:**

- Consumes: `ContractModel`, `SLUG` (Task 1, `common.py`); `IndexRow`, `CorpusManifest`
  (Task 1, `corpus.py`); `Spec`, `Cell`, `Subject` (tests).
- Produces: `DEFAULT_SYNTHBENCH_ROOT = Path("/export/synthbench")`; `to_json(model) -> str`;
  `CorpusStore(root: Path, version: str)` with `from_env(version, env=None)`, `version_dir`,
  `manifest_file`, `index_file` (properties), `event_dir(event_id)`, `spec_file(event_id)`,
  `provenance_file(event_id)`, `batch_dir(name)`, `batch_file(name)`,
  `write_new(path, model) -> None` (raises `FileExistsError`), `read(path, model_cls)`
  (staticmethod), `append_index(rows) -> None`, `latest_index() -> dict[str, IndexRow]`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_contract_store.py`:

```python
"""Where a corpus version's files live, and the append-only writer (design §2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from synthbench.contract.corpus import CorpusManifest, IndexRow
from synthbench.contract.spec import Cell, Spec, Subject
from synthbench.contract.store import CorpusStore, to_json

WHEN = "2026-09-28T00:00:00+00:00"


def _manifest(created: str = WHEN) -> CorpusManifest:
    return CorpusManifest(
        version="tierb-v0", taxonomy_sha256="a" * 64, render_size=(1280, 720), created=created
    )


def _row(event_id: str, status: str = "sampled") -> IndexRow:
    return IndexRow.model_validate(
        {
            "event_id": event_id,
            "batch": "pilot-1",
            "scenario": "knife_visible",
            "label": "incident",
            "status": status,
            "time": WHEN,
        }
    )


def test_the_corpus_lives_under_synthbench_root(tmp_path: Path) -> None:
    default = CorpusStore.from_env("tierb-v0", {})
    assert default.version_dir == Path("/export/synthbench/corpus/tierb-v0")
    custom = CorpusStore.from_env("tierb-v0", {"SYNTHBENCH_ROOT": str(tmp_path)})
    assert custom.version_dir == tmp_path / "corpus" / "tierb-v0"


def test_the_layout_matches_the_design(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    event = tmp_path / "tierb-v0" / "events" / "B" / "B-pilot-1-000"
    assert store.spec_file("B-pilot-1-000") == event / "spec.json"
    assert store.provenance_file("B-pilot-1-000") == event / "provenance.json"
    assert (
        store.batch_file("pilot-1") == tmp_path / "tierb-v0" / "batches" / "pilot-1" / "batch.json"
    )
    assert store.manifest_file == tmp_path / "tierb-v0" / "corpus.json"
    assert store.index_file == tmp_path / "tierb-v0" / "index.jsonl"


@pytest.mark.parametrize("event_id", ["C-x-000", "B", "b-pilot-1-000"])
def test_event_ids_need_a_tier_prefix(tmp_path: Path, event_id: str) -> None:
    with pytest.raises(ValueError, match="A- or B-"):
        CorpusStore(tmp_path, "tierb-v0").event_dir(event_id)


def test_versions_and_batch_names_are_slugs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must match"):
        CorpusStore(tmp_path, "Tier B")
    with pytest.raises(ValueError, match="must match"):
        CorpusStore(tmp_path, "tierb-v0").batch_dir("../escape")


def test_write_new_creates_and_never_replaces(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    first = _manifest()
    store.write_new(store.manifest_file, first)
    assert store.manifest_file.read_text(encoding="utf-8") == to_json(first)
    with pytest.raises(FileExistsError):
        store.write_new(store.manifest_file, _manifest(created="2026-09-29T00:00:00+00:00"))
    assert store.read(store.manifest_file, CorpusManifest) == first
    assert [p.name for p in store.version_dir.iterdir()] == ["corpus.json"]  # no temp file left


def test_to_json_is_stable_and_uses_aliases() -> None:
    spec = Spec(
        event_id="B-pilot-1-000",
        tier="B",
        corpus_version="tierb-v0",
        batch="pilot-1",
        cell=Cell(
            scenario="delivery_driver",
            group="benign",
            property_type="suburban_house",
            zone="front_porch",
            camera="doorbell_fisheye",
            lighting="day",
            weather="clear",
        ),
        scene_time="10:00",
        label="benign",
        risk_band=(0, 20),
        subjects=(Subject(id="S1", cls="person", role="delivery_driver"),),
    )
    text = to_json(spec)
    assert text.endswith("\n")
    data = json.loads(text)
    assert list(data) == sorted(data)
    assert data["subjects"][0]["class"] == "person"
    assert "null" not in text


def test_the_latest_index_row_wins(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    store.append_index([_row("B-pilot-1-000"), _row("B-pilot-1-001")])
    store.append_index([_row("B-pilot-1-000", "failed")])
    statuses = {event: row.status for event, row in store.latest_index().items()}
    assert statuses == {"B-pilot-1-000": "failed", "B-pilot-1-001": "sampled"}


def test_an_absent_index_is_empty_and_appending_nothing_writes_nothing(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    assert store.latest_index() == {}
    store.append_index([])
    assert not store.index_file.exists()
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_contract_store.py -q -n0 -p no:randomly`
Expected: `ModuleNotFoundError: No module named 'synthbench.contract.store'`.

- [ ] **Step 3: Write the store**

`synthbench/contract/store.py`:

```python
"""Where a corpus version's files live, and how they are written (agent-driven design §2).

The corpus is append-only: write_new creates a file atomically and never replaces one.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TypeVar

from synthbench.contract.common import SLUG, ContractModel
from synthbench.contract.corpus import IndexRow

M = TypeVar("M", bound=ContractModel)

DEFAULT_SYNTHBENCH_ROOT = Path("/export/synthbench")


def to_json(model: ContractModel) -> str:
    """Stable JSON: alias keys, no nulls, sorted keys, one-space indent, trailing newline."""
    payload = model.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, indent=1, sort_keys=True) + "\n"


class CorpusStore:
    """Paths and writes for one corpus version, under <root>/<version>/."""

    def __init__(self, root: Path, version: str) -> None:
        if not SLUG.fullmatch(version):
            raise ValueError(f"corpus version {version!r} must match {SLUG.pattern}")
        self.root = root
        self.version = version

    @classmethod
    def from_env(cls, version: str, env: Mapping[str, str] | None = None) -> CorpusStore:
        """The corpus lives at $SYNTHBENCH_ROOT/corpus (a ZFS dataset on maui, design §6)."""
        environment = os.environ if env is None else env
        root = Path(environment.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
        return cls(root / "corpus", version)

    @property
    def version_dir(self) -> Path:
        return self.root / self.version

    @property
    def manifest_file(self) -> Path:
        return self.version_dir / "corpus.json"

    @property
    def index_file(self) -> Path:
        return self.version_dir / "index.jsonl"

    def event_dir(self, event_id: str) -> Path:
        tier, _, rest = event_id.partition("-")
        if tier not in ("A", "B") or not rest:
            raise ValueError(f"event_id must start with A- or B-: {event_id!r}")
        return self.version_dir / "events" / tier / event_id

    def spec_file(self, event_id: str) -> Path:
        return self.event_dir(event_id) / "spec.json"

    def provenance_file(self, event_id: str) -> Path:
        return self.event_dir(event_id) / "provenance.json"

    def batch_dir(self, name: str) -> Path:
        if not SLUG.fullmatch(name):
            raise ValueError(f"batch name {name!r} must match {SLUG.pattern}")
        return self.version_dir / "batches" / name

    def batch_file(self, name: str) -> Path:
        return self.batch_dir(name) / "batch.json"

    def write_new(self, path: Path, model: ContractModel) -> None:
        """Create path holding model's JSON, atomically. Raises FileExistsError if it exists."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(to_json(model))
                handle.flush()
                os.fsync(handle.fileno())
            path.hardlink_to(tmp)  # a new link never replaces: FileExistsError if path exists
        finally:
            tmp.unlink()

    @staticmethod
    def read(path: Path, model: type[M]) -> M:
        return model.model_validate_json(path.read_text(encoding="utf-8"))

    def append_index(self, rows: Iterable[IndexRow]) -> None:
        lines = [
            json.dumps(row.model_dump(mode="json", exclude_none=True), sort_keys=True) + "\n"
            for row in rows
        ]
        if not lines:
            return
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        with self.index_file.open("a", encoding="utf-8") as handle:
            handle.writelines(lines)
            handle.flush()
            os.fsync(handle.fileno())

    def latest_index(self) -> dict[str, IndexRow]:
        """The latest row per event. The index is append-only, so later rows win."""
        if not self.index_file.exists():
            return {}
        latest: dict[str, IndexRow] = {}
        for line in self.index_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = IndexRow.model_validate_json(line)
                latest[row.event_id] = row
        return latest
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/test_contract_store.py -q -n0 -p no:randomly`
Expected: all pass. `uv run mypy synthbench/contract/` gives `Success`.

- [ ] **Step 5: Gate and commit**

```bash
F="synthbench/contract/store.py backend/tests/unit/synthbench/test_contract_store.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): append-only corpus store - layout, atomic create, index

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The Tier B v0 taxonomy

**Files:**

- Create: `synthbench/taxonomy/__init__.py`, `synthbench/taxonomy/model.py`,
  `synthbench/taxonomy/tier_b_v0.yaml`
- Test: `backend/tests/unit/synthbench/test_taxonomy.py`

**Interfaces:**

- Consumes: `HHMM`, `SLUG`, `Label`, `RiskBand`, `ScenarioGroup` (Task 1, `common.py`).
- Produces: `DEFAULT_TAXONOMY: Path`; models `LightingDef(id, hours, weight, outdoor_only)`,
  `WeatherDef(id, weight)`, `ArtifactDef(id, probability, lighting, weather, outdoor_only)`,
  `CameraDef(id, zones, indoor)`, `PropertyDef(id, zones)`, `SubjectDef(one_of, role)`,
  `PropDef(one_of, held_by)`, `ScenarioDef(id, group, label, risk_band, weight, zones, lighting,
weather, subjects, props)`, `Taxonomy(version, zones, lighting, weather, artifacts, cameras,
properties, colors, garments, clothed, terms, scenarios)`; functions
  `compatible_cells(tax, scenario) -> list[tuple[str, str, str]]` (property, zone, camera),
  `lighting_options(tax, scenario, camera) -> list[LightingDef]`,
  `weather_options(tax, scenario, camera) -> list[WeatherDef]`,
  `artifact_options(tax, camera, lighting_id, weather_id) -> list[ArtifactDef]`,
  `load_taxonomy(path=DEFAULT_TAXONOMY) -> Taxonomy`,
  `taxonomy_sha256(path=DEFAULT_TAXONOMY) -> str`.
- The `terms` lists are what P3's `synthbench check` requires a prompt to mention: one term from
  each subject's and prop's class.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_taxonomy.py`:

```python
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
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_taxonomy.py -q -n0 -p no:randomly`
Expected: `ModuleNotFoundError: No module named 'synthbench.taxonomy'`.

- [ ] **Step 3: Write the model and the YAML**

`synthbench/taxonomy/__init__.py`:

```python
"""The committed taxonomy (spec §1.2) and the seeded sampler that draws specs from it."""
```

`synthbench/taxonomy/model.py`:

```python
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
```

`synthbench/taxonomy/tier_b_v0.yaml`:

```yaml
# Tier B v0 taxonomy slice (spec §1.2; agent-driven design §3).
#
# The sampler draws every ground-truth fact from this file. P3's `synthbench check` requires a
# prompt to use one term from the list of each subject's and prop's class. Editing this file
# changes its sha256, and `python -m synthbench sample` then refuses to add batches to a corpus
# version built from the old file: a changed taxonomy needs a new corpus version.
#
# OWNER REVIEW: the scenario list, labels, risk bands and weights below are a v0 draft (plan
# ruling P2-R4). The spec's label set is incident / benign / ambiguous (§1.3), so suspicious
# scenarios are labeled incident with lower risk bands, and hard negatives are benign by
# definition. Left out of v0: assault (hard to show without injury detail, §3.8) and camera
# tampering (it needs the tampered camera's own view).
#
# Times are quoted: YAML 1.1 reads an unquoted 08:00 as a number.

version: tierb-v0

zones:
  [
    front_porch,
    lobby_door,
    driveway,
    garage_exterior,
    garage_interior,
    backyard,
    pool_deck,
    side_gate,
    patio,
    shed,
    street_edge,
    dock,
    kitchen,
    living_room,
    hallway,
    mailroom,
    parking_lot,
    loading_dock,
  ]

lighting:
  - { id: day, hours: [['08:00', '16:29']], weight: 4 }
  - { id: golden_hour, hours: [['06:30', '07:59'], ['16:30', '18:14']], weight: 1 }
  - { id: dusk, hours: [['18:15', '19:59']], weight: 1 }
  - { id: ir_night, hours: [['20:00', '05:29']], weight: 2 }
  - { id: porch_lit_night, hours: [['20:00', '05:29']], weight: 1, outdoor_only: true }

weather:
  - { id: clear, weight: 6 }
  - { id: rain, weight: 2 }
  - { id: snow, weight: 1 }
  - { id: fog, weight: 1 }

artifacts:
  - id: headlight_glare
    probability: 0.15
    lighting: [dusk, ir_night, porch_lit_night]
    outdoor_only: true
  - { id: lens_droplets, probability: 0.4, weather: [rain], outdoor_only: true }
  - { id: motion_blur, probability: 0.05 }

cameras:
  - { id: doorbell_fisheye, zones: [front_porch, lobby_door] }
  - id: eave_wide
    zones: [front_porch, driveway, backyard, pool_deck, side_gate, patio, shed, street_edge, dock]
  - { id: garage_mounted, zones: [driveway, garage_exterior] }
  - { id: pole_lot, zones: [parking_lot, loading_dock, street_edge] }
  - id: indoor_corner
    zones: [kitchen, living_room, hallway, garage_interior, mailroom]
    indoor: true

properties:
  - id: suburban_house
    zones:
      [
        front_porch,
        driveway,
        garage_exterior,
        garage_interior,
        backyard,
        pool_deck,
        side_gate,
        patio,
        shed,
        street_edge,
        kitchen,
        living_room,
        hallway,
      ]
  - { id: urban_townhouse, zones: [front_porch, street_edge, patio, kitchen, living_room, hallway] }
  - id: rural_farmhouse
    zones: [front_porch, driveway, backyard, side_gate, shed, kitchen, living_room]
  - id: lake_house
    zones: [front_porch, driveway, backyard, pool_deck, patio, dock, kitchen, living_room]
  - { id: apartment_entrance, zones: [lobby_door, mailroom, street_edge] }
  - { id: small_office, zones: [lobby_door, parking_lot, street_edge, hallway] }
  - { id: warehouse, zones: [loading_dock, parking_lot] }

colors: [black, white, gray, navy, red, green, brown, tan, blue, yellow]
garments: [hoodie, jacket, t-shirt, coat, sweater, work shirt, rain jacket, vest]
clothed: [person, child]

terms:
  person: [person, man, woman, figure, someone, individual, adult, teenager]
  child: [child, kid, toddler, boy, girl]
  dog: [dog, puppy]
  cat: [cat, kitten]
  deer: [deer]
  raccoon: [raccoon]
  car: [car, sedan, suv, hatchback, pickup, vehicle]
  package: [package, parcel, box]
  handgun: [handgun, pistol, gun]
  knife: [knife, blade]
  baseball_bat: [baseball bat, bat]
  crowbar: [crowbar, pry bar]
  machete: [machete]
  toy_gun: [toy gun, toy pistol, water gun]
  leaf_blower: [leaf blower]
  hedge_trimmer: [hedge trimmer]
  power_drill: [power drill, drill]
  angle_grinder: [angle grinder, grinder]
  reciprocating_saw: [reciprocating saw, saw]
  flashlight: [flashlight, torch]
  spray_paint: [spray paint, spray can]
  ski_mask: [ski mask, balaclava]
  scarf: [scarf, neck gaiter, face covering]
  pool_net: [pool net, skimmer net, pool skimmer]
  phone: [phone, smartphone]
  smoke: [smoke]
  fire: [fire, flames]

scenarios:
  # --- benign ---
  - id: delivery_driver
    group: benign
    label: benign
    risk_band: [0, 20]
    zones: [front_porch, lobby_door]
    lighting: [day, golden_hour, dusk]
    subjects: [{ one_of: [person], role: delivery_driver }]
    props: [{ one_of: [package], held_by: 0 }]
  - id: resident_arrival
    group: benign
    label: benign
    risk_band: [0, 15]
    zones: [driveway, front_porch, garage_exterior, lobby_door]
    subjects: [{ one_of: [person], role: resident }]
  - id: yard_maintenance
    group: benign
    label: benign
    risk_band: [0, 15]
    zones: [backyard, driveway, side_gate]
    lighting: [day, golden_hour]
    subjects: [{ one_of: [person], role: landscaper }]
    props: [{ one_of: [leaf_blower, hedge_trimmer], held_by: 0 }]
  - id: pool_service
    group: benign
    label: benign
    risk_band: [0, 15]
    zones: [pool_deck]
    lighting: [day]
    subjects: [{ one_of: [person], role: pool_technician }]
    props: [{ one_of: [pool_net], held_by: 0 }]
  - id: pet_activity
    group: benign
    label: benign
    risk_band: [0, 10]
    zones: [backyard, front_porch, driveway, patio, kitchen, living_room]
    subjects: [{ one_of: [dog, cat], role: pet }]
  - id: wildlife
    group: benign
    label: benign
    risk_band: [0, 10]
    zones: [backyard, driveway, street_edge, dock]
    lighting: [day, golden_hour, dusk, ir_night]
    subjects: [{ one_of: [deer, raccoon], role: wildlife }]
  - id: neighbor_passing
    group: benign
    label: benign
    risk_band: [0, 10]
    zones: [street_edge]
    subjects: [{ one_of: [person], role: neighbor }]
  # --- hard negatives: benign scenes that look alarming (spec §1.3) ---
  - id: hooded_jogger
    group: hard_negative
    label: benign
    risk_band: [0, 25]
    zones: [street_edge, driveway]
    lighting: [golden_hour, dusk, ir_night]
    subjects: [{ one_of: [person], role: hooded_jogger }]
  - id: power_tools_at_night
    group: hard_negative
    label: benign
    risk_band: [5, 30]
    zones: [garage_exterior, garage_interior, driveway, backyard]
    lighting: [dusk, ir_night, porch_lit_night]
    subjects: [{ one_of: [person], role: resident_doing_repairs }]
    props: [{ one_of: [power_drill, angle_grinder], held_by: 0 }]
  - id: winter_face_covering
    group: hard_negative
    label: benign
    risk_band: [5, 30]
    zones: [front_porch, driveway, lobby_door]
    weather: [snow]
    subjects: [{ one_of: [person], role: resident_in_winter_clothes }]
    props: [{ one_of: [scarf], held_by: 0 }]
  - id: flashlight_neighbor
    group: hard_negative
    label: benign
    risk_band: [5, 30]
    zones: [backyard, side_gate, street_edge, driveway]
    lighting: [dusk, ir_night, porch_lit_night]
    subjects: [{ one_of: [person], role: neighbor_looking_for_a_pet }]
    props: [{ one_of: [flashlight], held_by: 0 }]
  - id: landscaper_machete
    group: hard_negative
    label: benign
    risk_band: [5, 30]
    zones: [backyard, side_gate]
    lighting: [day, golden_hour]
    subjects: [{ one_of: [person], role: landscaper }]
    props: [{ one_of: [machete], held_by: 0 }]
  # --- ambiguous: scored in their own bucket, never in S2 or S3 (spec §1.3) ---
  - id: costume_weapon
    group: ambiguous
    label: ambiguous
    risk_band: [20, 60]
    zones: [front_porch, street_edge, lobby_door]
    lighting: [golden_hour, dusk, porch_lit_night]
    subjects: [{ one_of: [person, child], role: costumed_visitor }]
    props: [{ one_of: [toy_gun], held_by: 0 }]
  # --- suspicious: labeled incident with lower risk bands (see the header) ---
  - id: loitering
    group: suspicious
    label: incident
    risk_band: [40, 70]
    zones: [front_porch, driveway, street_edge, lobby_door, parking_lot]
    subjects: [{ one_of: [person], role: loiterer }]
  - id: peering_into_windows
    group: suspicious
    label: incident
    risk_band: [50, 80]
    zones: [backyard, side_gate, patio, front_porch]
    subjects: [{ one_of: [person], role: stranger_peering_in }]
  - id: trying_car_doors
    group: suspicious
    label: incident
    risk_band: [55, 85]
    zones: [driveway, street_edge, parking_lot]
    lighting: [dusk, ir_night, porch_lit_night]
    subjects: [{ one_of: [person], role: stranger_trying_door_handles }]
    props: [{ one_of: [car] }]
  - id: casing_with_phone
    group: suspicious
    label: incident
    risk_band: [40, 70]
    zones: [street_edge, driveway, parking_lot]
    subjects: [{ one_of: [person], role: stranger_photographing_the_property }]
    props: [{ one_of: [phone], held_by: 0 }]
  - id: tailgating
    group: suspicious
    label: incident
    risk_band: [45, 75]
    zones: [lobby_door]
    subjects:
      - { one_of: [person], role: resident_entering }
      - { one_of: [person], role: stranger_following_closely }
  # --- threats ---
  - id: firearm_visible
    group: threat
    label: incident
    risk_band: [85, 100]
    weight: 2
    zones: [front_porch, driveway, backyard, side_gate, lobby_door, parking_lot]
    subjects: [{ one_of: [person], role: armed_stranger }]
    props: [{ one_of: [handgun], held_by: 0 }]
  - id: knife_visible
    group: threat
    label: incident
    risk_band: [80, 100]
    weight: 2
    zones: [front_porch, driveway, backyard, side_gate, lobby_door, parking_lot]
    subjects: [{ one_of: [person], role: armed_stranger }]
    props: [{ one_of: [knife], held_by: 0 }]
  - id: blunt_weapon
    group: threat
    label: incident
    risk_band: [75, 100]
    zones: [front_porch, driveway, backyard, parking_lot]
    subjects: [{ one_of: [person], role: armed_stranger }]
    props: [{ one_of: [baseball_bat, crowbar], held_by: 0 }]
  - id: forced_entry
    group: threat
    label: incident
    risk_band: [80, 100]
    weight: 2
    zones: [front_porch, side_gate, patio, garage_exterior, lobby_door]
    subjects: [{ one_of: [person], role: stranger_prying_a_door }]
    props: [{ one_of: [crowbar], held_by: 0 }]
  - id: package_theft
    group: threat
    label: incident
    risk_band: [60, 90]
    weight: 2
    zones: [front_porch, lobby_door, mailroom]
    subjects: [{ one_of: [person], role: stranger_taking_a_package }]
    props: [{ one_of: [package], held_by: 0 }]
  - id: car_break_in
    group: threat
    label: incident
    risk_band: [70, 95]
    zones: [driveway, street_edge, parking_lot]
    lighting: [dusk, ir_night, porch_lit_night]
    subjects: [{ one_of: [person], role: stranger_breaking_a_car_window }]
    props: [{ one_of: [car] }]
  - id: catalytic_converter_theft
    group: threat
    label: incident
    risk_band: [70, 95]
    zones: [driveway, street_edge, parking_lot]
    lighting: [dusk, ir_night, porch_lit_night]
    subjects: [{ one_of: [person], role: stranger_under_a_car }]
    props:
      - { one_of: [car] }
      - { one_of: [reciprocating_saw], held_by: 0 }
  - id: masked_intruder_night
    group: threat
    label: incident
    risk_band: [85, 100]
    weight: 2
    zones: [front_porch, backyard, side_gate, patio, kitchen, living_room, hallway]
    lighting: [ir_night, porch_lit_night]
    subjects: [{ one_of: [person], role: masked_intruder }]
    props: [{ one_of: [ski_mask], held_by: 0 }]
  - id: fence_climbing
    group: threat
    label: incident
    risk_band: [65, 90]
    zones: [side_gate, backyard]
    subjects: [{ one_of: [person], role: stranger_climbing_a_fence }]
  - id: pool_trespass
    group: threat
    label: incident
    risk_band: [55, 85]
    zones: [pool_deck]
    lighting: [dusk, ir_night, porch_lit_night]
    subjects: [{ one_of: [person], role: trespasser }]
  - id: vandalism
    group: threat
    label: incident
    risk_band: [55, 85]
    zones: [garage_exterior, front_porch, street_edge, loading_dock]
    subjects: [{ one_of: [person], role: vandal }]
    props: [{ one_of: [spray_paint], held_by: 0 }]
  - id: person_down
    group: threat
    label: incident
    risk_band: [70, 100]
    zones: [front_porch, driveway, backyard, kitchen, living_room, hallway, parking_lot]
    subjects: [{ one_of: [person], role: collapsed_person }]
  - id: fire_or_smoke
    group: threat
    label: incident
    risk_band: [85, 100]
    weight: 2
    zones: [backyard, garage_exterior, patio, shed, kitchen]
    props: [{ one_of: [smoke, fire] }]
  - id: child_alone_at_pool
    group: threat
    label: incident
    risk_band: [85, 100]
    weight: 2
    zones: [pool_deck]
    lighting: [day, golden_hour, dusk]
    subjects: [{ one_of: [child], role: unsupervised_child }]
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/test_taxonomy.py -q -n0 -p no:randomly`
Expected: all pass. The YAML above is already in prettier's output format, so Step 5's hooks
should leave it unchanged. If they do change it, re-run these tests before committing.

- [ ] **Step 5: Gate and commit**

```bash
F="synthbench/taxonomy/__init__.py synthbench/taxonomy/model.py synthbench/taxonomy/tier_b_v0.yaml backend/tests/unit/synthbench/test_taxonomy.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): Tier B v0 taxonomy with coherence rules and term lists

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The seeded sampler

**Files:**

- Create: `synthbench/taxonomy/sampler.py`
- Test: `backend/tests/unit/synthbench/test_sampler.py`

**Interfaces:**

- Consumes: `Taxonomy`, `ScenarioDef`, `CameraDef`, `compatible_cells`, `lighting_options`,
  `weather_options`, `artifact_options`, `load_taxonomy` (Task 3); `Cell`, `Subject`, `Prop`,
  `Spec` (Task 1).
- Produces: `MAX_BATCH = 500`; `default_seed(batch: str) -> int`;
  `allocate(tax, n, prior: Mapping[str, int], only: Collection[str] | None = None) -> list[str]`;
  `time_in_hours(hours, rng: random.Random) -> str`; `in_hours(hhmm: str, hours) -> bool`;
  `sample_specs(tax, *, version: str, batch: str, n: int, seed: int,
prior: Mapping[str, int] | None = None, only: Collection[str] | None = None) -> list[Spec]`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_sampler.py`:

```python
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
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_sampler.py -q -n0 -p no:randomly`
Expected: `ModuleNotFoundError: No module named 'synthbench.taxonomy.sampler'`.

- [ ] **Step 3: Write the sampler**

`synthbench/taxonomy/sampler.py`:

```python
"""The seeded coverage-matrix sampler (spec §1.2, §7.2): taxonomy -> Tier B specs.

The same seed, batch name and prior counts give identical specs. Scenario counts follow the
taxonomy weights by Balinski and Young's quota method, so across carried-forward batches every
scenario stays within one event of its weighted share.
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
        # earlier-listed scenario. Counts skewed by earlier --only batches can leave nobody
        # eligible; then the whole pool competes.
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
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/test_sampler.py -q -n0 -p no:randomly`
Expected: all pass. Then run `uv run pytest backend/tests/unit/synthbench/test_sampler.py -q -p
randomly -n 4` twice; the results must not depend on order. Then `uv run mypy synthbench/`.

- [ ] **Step 5: Gate and commit**

```bash
F="synthbench/taxonomy/sampler.py backend/tests/unit/synthbench/test_sampler.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): seeded quota sampler - taxonomy to fact-only Tier B specs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `python -m synthbench sample`

**Files:**

- Create: `synthbench/cli.py`, `synthbench/__main__.py`
- Test: `backend/tests/unit/synthbench/test_cli_sample.py`

**Interfaces:**

- Consumes: `CorpusStore`, `to_json` (Task 2); `BatchRecord`, `CorpusManifest`, `IndexRow`,
  `TIER_B_RENDER_SIZE` (Task 1); `Spec` (Task 1); `SLUG` (Task 1); `load_taxonomy`,
  `taxonomy_sha256` (Task 3); `MAX_BATCH`, `default_seed`, `sample_specs` (Task 4).
- Produces: `EXIT_OK = 0`, `EXIT_ERROR = 1`, `EXIT_ASK = 2`;
  `build_parser() -> argparse.ArgumentParser`;
  `main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int`;
  `cmd_sample(args, env) -> int`. P3 adds its commands to `build_parser()` and `main()`.
- Behavior:

  1. Validate the batch name, the version and `--only`: exit 1 on a bad request.
  2. Create `corpus.json` on first use. If it records a different taxonomy sha256, exit 2.
  3. On a new batch, write `batch.json` **before** the specs, with the prior counts it allocated
     from.
  4. On a rerun of the same request (same seed, `n` and `--only`), regenerate from the stored
     prior counts. Write any missing spec, exit 2 if an existing spec differs, and index only
     events missing from the index.
  5. A rerun with different parameters exits 1.

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/synthbench/test_cli_sample.py`:

```python
"""`python -m synthbench sample` (agent-driven design §3 step 1)."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from synthbench import cli
from synthbench.contract.corpus import TIER_B_RENDER_SIZE, BatchRecord, CorpusManifest
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.model import taxonomy_sha256
from synthbench.taxonomy.sampler import default_seed

REPO_ROOT = Path(__file__).resolve().parents[4]


def _run(root: Path, *argv: str) -> int:
    return cli.main(["sample", *argv], env={"SYNTHBENCH_ROOT": str(root)})


def _exit_code(root: Path, *argv: str) -> int:
    """argparse raises SystemExit for usage errors; the command returns its code."""
    try:
        return _run(root, *argv)
    except SystemExit as stop:
        return int(stop.code or 0)


def _store(root: Path) -> CorpusStore:
    return CorpusStore(root / "corpus", "tierb-v0")


def test_sample_writes_manifest_batch_specs_and_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "10") == cli.EXIT_OK
    store = _store(tmp_path)
    record = store.read(store.batch_file("pilot-1"), BatchRecord)
    assert (record.n, record.seed, record.prior_counts) == (10, default_seed("pilot-1"), {})
    specs = [store.read(store.spec_file(event), Spec) for event in record.event_ids]
    assert [s.event_id for s in specs] == [f"B-pilot-1-{i:03d}" for i in range(10)]
    assert all(s.prompt is None for s in specs)
    manifest = store.read(store.manifest_file, CorpusManifest)
    assert manifest.taxonomy_sha256 == taxonomy_sha256()
    assert manifest.render_size == TIER_B_RENDER_SIZE
    index = store.latest_index()
    assert sorted(index) == list(record.event_ids)
    assert {row.status for row in index.values()} == {"sampled"}
    out = capsys.readouterr().out
    assert "batch pilot-1" in out and "10 events" in out


def test_the_same_request_gives_byte_identical_specs(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    for root in (first, second):
        assert _run(root, "--batch", "pilot-1", "--n", "12", "--seed", "5") == cli.EXIT_OK
    specs = sorted((first / "corpus").rglob("spec.json"))
    assert len(specs) == 12
    for path in specs:
        assert path.read_bytes() == (second / path.relative_to(first)).read_bytes()


def test_a_rerun_completes_a_partly_written_batch(tmp_path: Path) -> None:
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "5") == cli.EXIT_OK
    lost = _store(tmp_path).spec_file("B-pilot-1-003")
    original = lost.read_bytes()
    lost.unlink()  # as if the first run died before writing it
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "5") == cli.EXIT_OK
    assert lost.read_bytes() == original
    assert len(_store(tmp_path).latest_index()) == 5


def test_a_rerun_with_other_parameters_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "5") == cli.EXIT_OK
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "6") == cli.EXIT_ERROR
    assert "already exists" in capsys.readouterr().err


def test_a_hand_edited_spec_stops_the_rerun(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "3") == cli.EXIT_OK
    path = _store(tmp_path).spec_file("B-pilot-1-001")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["scene_time"] = "03:33" if data["scene_time"] != "03:33" else "04:44"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "3") == cli.EXIT_ASK
    assert "ask the owner" in capsys.readouterr().err


def test_a_changed_taxonomy_needs_a_new_corpus_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _store(tmp_path)
    store.write_new(
        store.manifest_file,
        CorpusManifest(
            version="tierb-v0",
            taxonomy_sha256="0" * 64,
            render_size=TIER_B_RENDER_SIZE,
            created="2026-09-28T00:00:00+00:00",
        ),
    )
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "2") == cli.EXIT_ASK
    assert "new corpus version" in capsys.readouterr().err
    assert not store.batch_dir("pilot-1").exists()


def test_a_second_batch_records_the_first_batch_counts(tmp_path: Path) -> None:
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "20") == cli.EXIT_OK
    assert _run(tmp_path, "--batch", "batch-2", "--n", "20") == cli.EXIT_OK
    store = _store(tmp_path)
    first = store.read(store.batch_file("pilot-1"), BatchRecord)
    second = store.read(store.batch_file("batch-2"), BatchRecord)
    first_counts = Counter(
        store.read(store.spec_file(e), Spec).cell.scenario for e in first.event_ids
    )
    assert second.prior_counts == dict(first_counts)
    assert len(store.latest_index()) == 40


def test_only_limits_the_scenarios(tmp_path: Path) -> None:
    argv = ("--batch", "pilot-1", "--n", "6", "--only", "knife_visible,firearm_visible")
    assert _run(tmp_path, *argv) == cli.EXIT_OK
    store = _store(tmp_path)
    scenarios = {
        store.read(store.spec_file(f"B-pilot-1-{i:03d}"), Spec).cell.scenario for i in range(6)
    }
    assert scenarios == {"knife_visible", "firearm_visible"}


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (("--batch", "Pilot 1", "--n", "5"), "must match"),
        (("--batch", "pilot-1", "--n", "5", "--only", "nope"), "unknown scenario"),
        (("--batch", "pilot-1", "--n", "0"), "1..500"),
        (
            (
                "--batch",
                "pilot-1",
            ),
            "required",
        ),
    ],
)
def test_bad_requests_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], argv: tuple[str, ...], message: str
) -> None:
    assert _exit_code(tmp_path, *argv) == cli.EXIT_ERROR
    assert message in capsys.readouterr().err
    assert not (tmp_path / "corpus" / "tierb-v0" / "batches").exists()


def test_python_dash_m_synthbench_runs() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "synthbench", "sample", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "--batch" in done.stdout
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_cli_sample.py -q -n0 -p no:randomly`
Expected: `ImportError: cannot import name 'cli' from 'synthbench'`.

- [ ] **Step 3: Write the CLI**

`synthbench/cli.py`:

```python
"""`python -m synthbench <command>`: the synthbench command line (agent-driven design §3).

Every command exits 0 when done, 1 on an error (fix the request and retry), and 2 when the
agent must stop and ask the owner (the corpus or taxonomy is not in the state it expects).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import NoReturn

from synthbench.contract.common import SLUG
from synthbench.contract.corpus import TIER_B_RENDER_SIZE, BatchRecord, CorpusManifest, IndexRow
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.model import load_taxonomy, taxonomy_sha256
from synthbench.taxonomy.sampler import MAX_BATCH, default_seed, sample_specs

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ASK = 2


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on a usage error, but 2 means "ask the owner" here, so exit 1."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


def _batch_size(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"n must be an integer 1..{MAX_BATCH}: {text!r}") from None
    if not 1 <= value <= MAX_BATCH:
        raise argparse.ArgumentTypeError(f"n must be 1..{MAX_BATCH}, got {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="python -m synthbench",
        description=(
            "Synthetic benchmark generation. Exit codes: 0 done, 1 error (fix the request), "
            "2 stop and ask the owner."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    sample = commands.add_parser(
        "sample", help="sample Tier B specs (facts only, no prompt) into a new batch"
    )
    sample.add_argument(
        "--batch", required=True, help="new batch name: lowercase letters, digits and hyphens"
    )
    sample.add_argument(
        "--n", type=_batch_size, required=True, help=f"number of events, 1..{MAX_BATCH}"
    )
    sample.add_argument(
        "--seed", type=int, default=None, help="sampler seed (default: derived from the batch name)"
    )
    sample.add_argument(
        "--only", default="", help="comma-separated scenario ids to sample from (default: all)"
    )
    sample.add_argument(
        "--version", default=None, help="corpus version (default: the taxonomy's version)"
    )
    return parser


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _fail(code: int, message: str) -> int:
    sys.stderr.write(f"synthbench: {message}\n")
    return code


def cmd_sample(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = load_taxonomy()
    batch: str = args.batch
    version: str = args.version or tax.version
    if not SLUG.fullmatch(batch) or not SLUG.fullmatch(version):
        return _fail(
            EXIT_ERROR, f"batch name and version must match {SLUG.pattern}: {batch!r}, {version!r}"
        )
    only = tuple(sorted({s for s in args.only.split(",") if s}))
    if unknown := sorted(set(only) - {s.id for s in tax.scenarios}):
        valid = ", ".join(s.id for s in tax.scenarios)
        return _fail(EXIT_ERROR, f"unknown scenario(s): {', '.join(unknown)}; valid: {valid}")

    store = CorpusStore.from_env(version, env)
    digest = taxonomy_sha256()
    if store.manifest_file.exists():
        if store.read(store.manifest_file, CorpusManifest).taxonomy_sha256 != digest:
            return _fail(
                EXIT_ASK,
                f"the taxonomy changed since corpus version {version} was created, so new "
                "batches would not be comparable. Stop and ask the owner: a changed taxonomy "
                "needs a new corpus version.",
            )
    else:
        store.write_new(
            store.manifest_file,
            CorpusManifest(
                version=version,
                taxonomy_sha256=digest,
                render_size=TIER_B_RENDER_SIZE,
                created=_now(),
            ),
        )

    seed: int = args.seed if args.seed is not None else default_seed(batch)
    batch_file = store.batch_file(batch)
    record = store.read(batch_file, BatchRecord) if batch_file.exists() else None
    if record is not None and (record.seed, record.n, record.only) != (seed, args.n, only):
        return _fail(
            EXIT_ERROR,
            f"batch {batch} already exists with seed={record.seed}, n={record.n}, "
            f"only={','.join(record.only) or 'all'}; choose a new batch name",
        )
    index = store.latest_index()
    if record is not None:
        prior = record.prior_counts
    else:
        prior = dict(Counter(row.scenario for row in index.values()))
    specs = sample_specs(
        tax, version=version, batch=batch, n=args.n, seed=seed, prior=prior, only=only or None
    )
    if record is None:
        store.write_new(
            batch_file,
            BatchRecord(
                name=batch,
                version=version,
                seed=seed,
                n=args.n,
                only=only,
                prior_counts=prior,
                event_ids=tuple(s.event_id for s in specs),
                created=_now(),
            ),
        )

    written = 0
    for spec in specs:
        path = store.spec_file(spec.event_id)
        if not path.exists():
            store.write_new(path, spec)
            written += 1
        elif store.read(path, Spec) != spec:
            return _fail(
                EXIT_ASK,
                f"{path} is not what the sampler produces for batch {batch}: the corpus was "
                "changed by hand. Stop and ask the owner.",
            )
    store.append_index(
        IndexRow(
            event_id=s.event_id,
            batch=batch,
            scenario=s.cell.scenario,
            label=s.label,
            status="sampled",
            time=_now(),
        )
        for s in specs
        if s.event_id not in index
    )
    counts = ", ".join(
        f"{k} {v}" for k, v in sorted(Counter(s.cell.scenario for s in specs).items())
    )
    sys.stdout.write(
        f"batch {batch} in corpus version {version}: {len(specs)} events ({written} written now)\n"
        f"  scenarios: {counts}\n"
        f"  specs: {store.event_dir(specs[0].event_id).parent}/"
        f"{specs[0].event_id} .. {specs[-1].event_id}\n"
    )
    return EXIT_OK


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    environment: Mapping[str, str] = os.environ if env is None else env
    if args.command == "sample":
        return cmd_sample(args, environment)
    raise AssertionError(f"unhandled command {args.command!r}")  # argparse rejects unknown ones
```

`synthbench/__main__.py`:

```python
"""`python -m synthbench <command>`; see synthbench/cli.py."""

import sys

from synthbench.cli import main

sys.exit(main())
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `uv run pytest backend/tests/unit/synthbench/test_cli_sample.py -q -n0 -p no:randomly`
Expected: all pass. Then `uv run mypy synthbench/` gives `Success` and
`uv run ruff check synthbench/ backend/tests/unit/synthbench/` is clean.

- [ ] **Step 5: Gate and commit**

```bash
F="synthbench/cli.py synthbench/__main__.py backend/tests/unit/synthbench/test_cli_sample.py"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "feat(synthbench): python -m synthbench sample - fact-only batches into a corpus version

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Import rule, directory guides, and verification

**Files:**

- Modify: `backend/tests/unit/synthbench/test_import_rule.py` (add one test)
- Create: `synthbench/contract/AGENTS.md`, `synthbench/taxonomy/AGENTS.md`
- Modify: `synthbench/AGENTS.md`, `backend/tests/unit/synthbench/AGENTS.md`

**Interfaces:**

- Consumes: everything above. Produces documentation only, plus one guard test.

- [ ] **Step 1: Write the failing guard test**

Append to `backend/tests/unit/synthbench/test_import_rule.py`:

```python
def test_only_score_and_run_may_import_backend() -> None:
    """Spec §7.1: across all of synthbench, only score/ and run/ may import backend."""
    root = REPO_ROOT / "synthbench"
    allowed = (root / "score", root / "run")
    paths = sorted(p for p in root.rglob("*.py") if not any(p.is_relative_to(a) for a in allowed))
    # an empty walk would pass vacuously; these files come from the contract/sampler plan
    assert root / "cli.py" in paths
    assert root / "contract" / "spec.py" in paths
    assert root / "taxonomy" / "sampler.py" in paths
    offenders = [
        f"{path.relative_to(REPO_ROOT)}: {module}"
        for path in paths
        for module in _imported_modules(path)
        if module == "backend" or module.startswith("backend.")
    ]
    assert offenders == []
```

- [ ] **Step 2: Run it**

Run: `uv run pytest backend/tests/unit/synthbench/test_import_rule.py -q -n0 -p no:randomly`
Expected: PASS, because Tasks 1-5 import no `backend`. Confirm it can fail: temporarily add
`import backend  # noqa: F401` to `synthbench/cli.py`, re-run and see it FAIL naming
`synthbench/cli.py: backend`, then remove the line.

- [ ] **Step 3: Write the directory guides**

`synthbench/contract/AGENTS.md`:

```markdown
# synthbench/contract - Agent Guide

## Purpose

The event contract (spec §2): pydantic models for what an event is meant to show (`spec.json`),
what it does show (`truth.json`) and how it was made (`provenance.json`), plus the corpus records
and the append-only store.

## Files

| File            | What                                                                                                                                           |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `common.py`     | `ContractModel` base (frozen, no extra keys, JSON uses aliases such as `class`), labels, validated `Box`, `HHMM`, `RiskBand`, `Sha256`, `SLUG` |
| `spec.py`       | `Spec`, `Cell`, `Subject`, `Prop`; the sampler writes facts, P3 freezes `prompt` + `camera_suffix` together                                    |
| `truth.py`      | `Truth` and its parts, exactly parent spec §2.3's shape                                                                                        |
| `provenance.py` | `Provenance`, `Attempt`, `Triage` (the 7 reroll reasons), `MAX_ATTEMPTS = 3`                                                                   |
| `corpus.py`     | `CorpusManifest` (corpus.json), `BatchRecord` (batch.json), `IndexRow` (index.jsonl), `TIER_B_RENDER_SIZE`                                     |
| `store.py`      | `CorpusStore`: paths under `$SYNTHBENCH_ROOT/corpus/<version>/`, `write_new` (atomic, never replaces), the index                               |

## Rules

- The corpus is append-only (agent-driven design §2). Write through `CorpusStore.write_new`; it
  raises `FileExistsError` rather than replace. Never delete or rewrite an image.
- Truth stores facts, never expected model outputs (spec §2.2).
- A new field in a file model means a `schema_version` bump and a migration note in the spec.
- No `backend` imports (test: `test_import_rule.py`).
```

`synthbench/taxonomy/AGENTS.md`:

```markdown
# synthbench/taxonomy - Agent Guide

## Purpose

The committed taxonomy (spec §1.2) and the seeded sampler that turns it into fact-only Tier B
specs.

## Files

| File             | What                                                                                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `tier_b_v0.yaml` | zones, lighting (hours), weather, artifacts, cameras, properties, clothing, per-class **term lists**, 32 scenarios with labels, risk bands and weights |
| `model.py`       | pydantic models, coherence rules, `compatible_cells` and the lighting/weather/artifact options, `load_taxonomy`, `taxonomy_sha256`                     |
| `sampler.py`     | `allocate` (Balinski-Young quota method), `sample_specs`, `time_in_hours`, `in_hours`, `default_seed`                                                  |

## Rules

- **Editing the YAML changes its sha256.** `python -m synthbench sample` then exits 2 for a
  corpus version built from the old file: a changed taxonomy needs a new corpus version.
- Quote times in the YAML: YAML 1.1 reads `08:00` as a number.
- Terms are lowercase. P3's `synthbench check` requires a prompt to use one term from each
  subject's and prop's class list.
- The draw order in `sampler._one` is part of the contract. Reordering it changes every spec a
  seed produces.
- The scenario list, labels, risk bands and weights are the owner's to set. The v0 values are a
  draft (plan ruling P2-R4).
```

In `synthbench/AGENTS.md`:

- Replace the line `Phase plans live in \`docs/superpowers/plans/2026-09-27-synthbench-_.md\`.`with`Phase plans live in \`docs/superpowers/plans/_-synthbench-\*.md\`.`
- Add these rows to the Layout table, after the `generate/comfy/` row:

```markdown
| `contract/` | event contract: spec/truth/provenance models, corpus records, append-only `CorpusStore` |
| `taxonomy/` | committed Tier B taxonomy YAML, its coherence rules, the seeded quota sampler |
| `cli.py` + `__main__.py` | `python -m synthbench <command>`; exit 0 done, 1 error, 2 stop and ask the owner |
```

- Add this bullet to Rules:
  `- The corpus lives at \`$SYNTHBENCH_ROOT/corpus\` (the ZFS dataset \`primary/export/synthbench/corpus\`) and is append-only; tests write only under \`tmp_path\`.`

In `backend/tests/unit/synthbench/AGENTS.md`, add these rows to the Directory Structure table:

```markdown
| `test_contract.py` | `synthbench/contract/` models: §2.3 round-trip, validation, `class` alias |
| `test_contract_store.py` | `synthbench/contract/store.py`: layout, atomic create-never-replace, index |
| `test_taxonomy.py` | `synthbench/taxonomy/model.py` + the committed YAML: coherence rules |
| `test_sampler.py` | `synthbench/taxonomy/sampler.py`: determinism, quota coverage, legal cells, midnight wrap |
| `test_cli_sample.py` | `python -m synthbench sample`: writes, reruns, refusals, exit codes |
```

- [ ] **Step 4: Verify everything**

Run each and read the output:

```bash
uv run pytest backend/tests/unit/synthbench/ -q -n0 -p no:randomly
uv run pytest backend/tests/unit/synthbench/ -q -n auto -p randomly
uv run pytest backend/tests/unit/synthbench/ -q -n auto -p randomly
uv run mypy synthbench/ --ignore-missing-imports
uv run ruff check synthbench/ backend/tests/unit/synthbench/
uv run ruff format --check synthbench/ backend/tests/unit/synthbench/
uv run vulture backend/ vulture_whitelist.py --config pyproject.toml
```

Expected: every pytest run passes (the P1 suite's 484 plus the new tests), mypy prints
`Success`, and ruff and vulture print nothing or "All checks passed".

Then a real run in the ZFS dataset's scratch area. Always set `SYNTHBENCH_ROOT` here: without
it the command writes to the real corpus at `/export/synthbench/corpus`, and the first real batch
is P3's pilot, not this plan's.

```bash
export SYNTHBENCH_ROOT=/export/synthbench/tmp/p2-smoke
uv run python -m synthbench sample --batch smoke --n 10
cat "$SYNTHBENCH_ROOT/corpus/tierb-v0/events/B/B-smoke-000/spec.json"
uv run python -m synthbench sample --batch smoke --n 10
rm -rf "$SYNTHBENCH_ROOT" && unset SYNTHBENCH_ROOT
```

Expected:

- The first sample prints `batch smoke in corpus version tierb-v0: 10 events (10 written now)`.
- The `cat` shows one spec with `"class"` keys and no `prompt`.
- The rerun prints `(0 written now)` and exits 0.

- [ ] **Step 5: Gate and commit**

```bash
F="backend/tests/unit/synthbench/test_import_rule.py synthbench/contract/AGENTS.md synthbench/taxonomy/AGENTS.md synthbench/AGENTS.md backend/tests/unit/synthbench/AGENTS.md"
SKIP=semgrep uvx pre-commit run --files $F && git add $F && git commit -m "docs(synthbench): contract and taxonomy guides; import rule covers all of synthbench

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## After the plan

- P3's plan (agent-driven Tier B generation, design §9 item 2) starts from this plan's
  `python -m synthbench` entry point and extends `build_parser()` and `main()` with `check`,
  `render`, `camera`, `triage` and `report`.
- The owner reviews `synthbench/taxonomy/tier_b_v0.yaml` (scenarios, labels, risk bands,
  weights) before P3's first pilot. Any edit before the first real batch is free: no corpus
  version exists yet.
