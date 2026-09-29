"""The event contract (spec §2): round-trips, validation, and the `class` JSON key."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from synthbench.contract.corpus import BatchRecord, CorpusManifest, IndexRow, PromptRow, TriageRow
from synthbench.contract.provenance import (
    MAX_ATTEMPTS,
    Attempt,
    OutputFile,
    Provenance,
    RenderFailure,
    Triage,
    attempt_seed,
    render_name,
    still_name,
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


@pytest.mark.parametrize(
    "path", ["/abs/a1.png", "../a1.png", "", ".", "./a1.png", "renders//a1.png", "renders/"]
)
def test_output_paths_stay_inside_the_event_directory(path: str) -> None:
    assert OutputFile(path="renders/a1-s7.png", sha256=SHA).path == "renders/a1-s7.png"
    with pytest.raises(ValidationError, match="relative to the event directory"):
        OutputFile(path=path, sha256=SHA)


def test_updated_revalidates() -> None:
    spec = _spec()
    assert spec.updated(scene_time="23:59").scene_time == "23:59"
    with pytest.raises(ValidationError, match="HH:MM"):
        spec.updated(scene_time="24:00")


def test_facts_leave_out_the_frozen_prompt() -> None:
    spec = _spec()
    frozen = spec.with_prompt("a person at the door", "the suffix")
    assert frozen.frozen
    assert not spec.frozen
    assert frozen.facts() == spec.facts()
    assert "prompt" not in spec.facts()
    assert "camera_suffix" not in spec.facts()
    with pytest.raises(ValueError, match="already has a frozen prompt"):
        frozen.with_prompt("another prompt", "the suffix")


def test_provenance_is_schema_version_2() -> None:
    failure = RenderFailure(time="2026-09-28T00:00:00+00:00", error="TimeoutError: slow")
    attempt = Attempt(k=1, seed=5, prompt_sha256=SHA, render_failures=(failure,))
    prov = Provenance(event_id="B-pilot-1-000", attempts=(attempt,))
    assert prov.schema_version == 2
    assert Provenance.model_validate_json(prov.model_dump_json()) == prov
    data = prov.model_dump(mode="json")
    data["schema_version"] = 1
    with pytest.raises(ValidationError):
        Provenance.model_validate(data)


def test_a_still_needs_its_render_params_and_overlay_time() -> None:
    render = OutputFile(path="renders/a1-s5.png", sha256=SHA)
    still = OutputFile(path="stills/a1-s5.jpg", sha256=SHA)
    done = Attempt(
        k=1,
        seed=5,
        prompt_sha256=SHA,
        render=render,
        still=still,
        camera_params="default-v1",
        overlay_time="2026-03-04 20:15:09",
    )
    assert done.still == still
    with pytest.raises(ValidationError, match="a still needs"):
        Attempt(k=1, seed=5, prompt_sha256=SHA, render=render, still=still)
    with pytest.raises(ValidationError, match="overlay_time"):
        done.updated(overlay_time="2026-03-04T20:15:09")
    with pytest.raises(ValidationError, match="triage needs a still"):
        Attempt(k=1, seed=5, prompt_sha256=SHA, triage=Triage(verdict="ok"))


def test_attempt_seeds_and_file_names_are_stable() -> None:
    first = attempt_seed("B-pilot-1-000", 1)
    assert first == attempt_seed("B-pilot-1-000", 1)
    assert first != attempt_seed("B-pilot-1-000", 2)
    assert 0 <= first < 2**32
    assert render_name(2, 77) == "renders/a2-s77.png"
    assert still_name(2, 77) == "stills/a2-s77.jpg"


def test_agent_rows_validate() -> None:
    row = PromptRow.model_validate_json('{"event_id": "B-pilot-1-000", "prompt": "a man"}')
    assert row.prompt == "a man"
    verdict = TriageRow(event_id="B-pilot-1-000", k=1, verdict="reroll", reason="blank")
    assert verdict.triage() == Triage(verdict="reroll", reason="blank")
    with pytest.raises(ValidationError, match="needs a reason"):
        TriageRow(event_id="B-pilot-1-000", k=1, verdict="reroll")
    with pytest.raises(ValidationError):
        TriageRow.model_validate(
            {"event_id": "B-pilot-1-000", "k": 1, "verdict": "ok", "note": "looks fine"}
        )


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
