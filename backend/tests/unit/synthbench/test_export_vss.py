"""`export vss` (P5a design §2): ready Tier B events in the VSS eval store's import layout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from synthbench import cli
from synthbench.contract.corpus import BatchRecord
from synthbench.contract.provenance import Provenance
from synthbench.contract.spec import Spec
from synthbench.export import vss

from backend.tests.unit.synthbench import helpers as h

# One scenario per exported group: threat, suspicious, hard_negative, benign.
MIXED = "knife_visible,loitering,hooded_jogger,delivery_driver"

# The 450 exported items of tierb-v0, by scenario and label, transcribed from the frozen sweep's
# items.csv (docs/benchmarks/synthbench/sweep-2026-10-03). The split's whole arithmetic — 64
# holdout and 177 dev incident items beside 209 dev benign — reads off these two tables, and they
# are asserted as data so a re-freeze that changes the population fails here, not in a score.
ALL_19_ITEMS: dict[str, int] = {
    "blunt_weapon": 9,
    "car_break_in": 9,
    "casing_with_phone": 9,
    "catalytic_converter_theft": 9,
    "child_alone_at_pool": 19,
    "fence_climbing": 9,
    "fire_or_smoke": 19,
    "firearm_visible": 19,
    "forced_entry": 19,
    "knife_visible": 19,
    "loitering": 9,
    "masked_intruder_night": 19,
    "package_theft": 19,
    "peering_into_windows": 9,
    "person_down": 9,
    "pool_trespass": 9,
    "tailgating": 9,
    "trying_car_doors": 9,
    "vandalism": 9,
}
BENIGN_ITEMS: dict[str, int] = {
    "delivery_driver": 10,
    "flashlight_neighbor": 29,
    "hooded_jogger": 29,
    "landscaper_machete": 29,
    "neighbor_passing": 9,
    "pet_activity": 8,
    "pool_service": 9,
    "power_tools_at_night": 29,
    "resident_arrival": 10,
    "wildlife": 9,
    "winter_face_covering": 29,
    "yard_maintenance": 9,
}
ITEMS_BY_SCENARIO: dict[str, dict[str, int]] = {
    **{name: {"benign": 0, "incident": n} for name, n in ALL_19_ITEMS.items()},
    **{name: {"benign": n, "incident": 0} for name, n in BENIGN_ITEMS.items()},
}

# The six the published hash order gives (spec "The realized draw"), in rank order.
HOLDOUT_SIX = [
    "tailgating",
    "blunt_weapon",
    "car_break_in",
    "casing_with_phone",
    "knife_visible",
    "peering_into_windows",
]


def _items_in_construction_order(scrambled: bool = False) -> dict[str, dict[str, int]]:
    """The 31-scenario item table, optionally built in the reverse order (bytes must not care)."""
    names = sorted(ITEMS_BY_SCENARIO, reverse=scrambled)
    return {name: dict(ITEMS_BY_SCENARIO[name]) for name in names}


def _scenario_arm() -> dict[str, str]:
    """The full 31-scenario arm table: incident arms from the draw, benign arms by rule (B1)."""
    arm = {row["scenario"]: row["arm"] for row in _draw()["scenarios"]}
    arm.update(dict.fromkeys(BENIGN_ITEMS, "dev"))
    return arm


def _draw() -> dict[str, Any]:
    return vss.draw_split("tierb-v0", sorted(ALL_19_ITEMS))


def _holdout_names(draw: dict[str, Any]) -> list[str]:
    return [row["scenario"] for row in draw["scenarios"] if row["arm"] == "holdout"]


def _manifest() -> dict[str, Any]:
    return vss.split_manifest_document(
        "tierb-v0", _scenario_arm(), items_by_scenario=_items_in_construction_order()
    )


def _ready_batch(root: Path, only: str, n: int, batch: str = "pilot-1") -> list[Spec]:
    """A sampled, frozen batch whose events have a stand-in still and index status `ready`."""
    assert h.run(root, "sample", "--batch", batch, "--n", str(n), "--only", only) == cli.EXIT_OK
    store = h.store(root)
    record = store.read(store.batch_file(batch), BatchRecord)
    specs = [store.read(store.spec_file(event), Spec) for event in record.event_ids]
    h.write_prompts(root, batch, {spec.event_id: h.good_prompt(spec) for spec in specs})
    assert h.run(root, "check", "--batch", batch) == cli.EXIT_OK
    specs = [store.read(store.spec_file(spec.event_id), Spec) for spec in specs]
    for spec in specs:
        tag = spec.event_id.encode()
        h.record_output(root, spec, render=b"png " + tag, still=b"jpeg " + tag)
        row = store.latest_index()[spec.event_id]
        store.append_index([row.model_copy(update={"status": "ready", "time": h.NOW.isoformat()})])
    return specs


def _out(root: Path) -> Path:
    return root / "exports" / h.VERSION / "vss"


def _export(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    assert h.run(root, "export", "vss") == cli.EXIT_OK
    return capsys.readouterr().out


def _tree(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_ready_events_export_to_their_category(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = _ready_batch(tmp_path, MIXED, 8)
    assert "8 written now, 0 unchanged" in _export(tmp_path, capsys)
    assert {vss.CATEGORY[s.cell.group] for s in specs} == {"threats", "suspicious", "normal"}
    for spec in specs:
        category = vss.CATEGORY[spec.cell.group]
        set_dir = _out(tmp_path) / category / spec.event_id
        labels = json.loads((set_dir / "expected_labels.json").read_text(encoding="utf-8"))
        assert labels["category"] == category
        assert labels["risk"] == {"min_score": spec.risk_band[0], "max_score": spec.risk_band[1]}
        assert labels["timestamp"] == vss.scene_timestamp(spec.scene_time, spec.cell.weather)
        assert labels["synthbench"]["event_id"] == spec.event_id
        assert labels["synthbench"]["cell"]["scenario"] == spec.cell.scenario
        assert (set_dir / "still.jpg").read_bytes() == b"jpeg " + spec.event_id.encode()
        sidecar = json.loads((set_dir / "still.json").read_text(encoding="utf-8"))
        assert sidecar["license"] and sidecar["artist"]


def test_only_ready_events_are_exported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    specs = _ready_batch(tmp_path, MIXED, 4)
    store = h.store(tmp_path)
    row = store.latest_index()[specs[0].event_id]
    store.append_index([row.model_copy(update={"status": "failed", "time": h.NOW.isoformat()})])
    out = _export(tmp_path, capsys)
    assert "3 written now" in out
    assert "not exported: failed 1" in out
    assert not list(_out(tmp_path).glob(f"*/{specs[0].event_id}"))


def test_ambiguous_events_are_counted_not_exported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _ready_batch(tmp_path, "costume_weapon", 2)
    out = _export(tmp_path, capsys)
    assert "0 written now" in out
    assert "not exported: ambiguous 2" in out
    assert not list(_out(tmp_path).rglob("expected_labels.json"))


def test_a_second_export_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _ready_batch(tmp_path, MIXED, 4)
    _export(tmp_path, capsys)
    before = _tree(_out(tmp_path))
    assert "0 written now, 4 unchanged" in _export(tmp_path, capsys)
    assert _tree(_out(tmp_path)) == before


def test_a_set_that_differs_from_the_corpus_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = _ready_batch(tmp_path, MIXED, 4)[0]
    _export(tmp_path, capsys)
    next(_out(tmp_path).glob(f"*/{spec.event_id}/expected_labels.json")).write_text("{}\n")
    assert h.run(tmp_path, "export", "vss") == cli.EXIT_ASK
    assert "differs from the corpus" in capsys.readouterr().err


def test_a_label_its_group_disagrees_with_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The label authority is the directory (the importer's rule), so a threat labeled benign
    would import as an incident: the taxonomy disagreeing with itself stops the export."""
    specs = _ready_batch(tmp_path, MIXED, 4)
    threat = next(spec for spec in specs if spec.cell.group == "threat")
    spec_file = h.store(tmp_path).spec_file(threat.event_id)
    document = json.loads(spec_file.read_text(encoding="utf-8"))
    spec_file.write_text(json.dumps(document | {"label": "benign"}), encoding="utf-8")
    assert h.run(tmp_path, "export", "vss") == cli.EXIT_ASK
    assert f"{threat.event_id} is labeled benign" in capsys.readouterr().err


def test_a_still_that_no_longer_matches_its_sha256_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = _ready_batch(tmp_path, MIXED, 2)[0]
    store = h.store(tmp_path)
    still = store.read(store.provenance_file(spec.event_id), Provenance).attempts[-1].still
    assert still is not None
    (store.event_dir(spec.event_id) / still.path).write_bytes(b"tampered")
    assert h.run(tmp_path, "export", "vss") == cli.EXIT_ASK
    assert "does not match its recorded sha256" in capsys.readouterr().err


def test_an_empty_corpus_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert h.run(tmp_path, "export", "vss") == cli.EXIT_ERROR
    assert "nothing to export" in capsys.readouterr().err


def test_the_scene_time_is_dated_by_the_weather() -> None:
    assert vss.scene_timestamp("14:32", "clear") == "2026-04-15T14:32:00-04:00"
    assert vss.scene_timestamp("06:05", "snow") == "2026-01-15T06:05:00-05:00"
    assert "snow" in {weather.id for weather in h.TAX.weather}  # the rule keys on a real id


def test_the_category_vocabulary_is_the_importers() -> None:
    from backend.evaluation.eval_store import _CATEGORY_LABELS

    assert vss.CATEGORY_LABEL == _CATEGORY_LABELS
    # every scenario group is either placed in a category or deliberately excluded
    assert set(vss.CATEGORY) | {"ambiguous"} == {s.group for s in h.TAX.scenarios}


def test_declared_detections_are_the_subjects_then_the_props(tmp_path: Path) -> None:
    specs = _ready_batch(tmp_path, MIXED, 8)
    armed = next(spec for spec in specs if spec.cell.scenario == "knife_visible")
    assert vss.declared_detections(armed) == [
        {"object_type": "person", "confidence": 1.0},
        {"object_type": "knife", "confidence": 1.0},
    ]
    empty = armed.updated(subjects=(), props=())
    assert vss.declared_detections(empty) == []


def test_the_labels_document_carries_declared_detections(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = _ready_batch(tmp_path, MIXED, 8)
    _export(tmp_path, capsys)
    for spec in specs:
        category = vss.CATEGORY[spec.cell.group]
        set_dir = _out(tmp_path) / category / spec.event_id
        labels = json.loads((set_dir / "expected_labels.json").read_text(encoding="utf-8"))
        assert labels["detections"] == vss.declared_detections(spec)
        assert all(set(row) == {"object_type", "confidence"} for row in labels["detections"])


def test_the_export_round_trips_through_the_importer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from backend.evaluation.eval_store import EvalStore
    from backend.evaluation.label_import import import_generated_items

    specs = _ready_batch(tmp_path, MIXED, 6)
    _export(tmp_path, capsys)
    sets = {s.facts["event_id"]: s for s in vss.read_sets(_out(tmp_path))}
    with EvalStore(tmp_path / "eval.sqlite") as store:
        rows = import_generated_items(corpus_dir=_out(tmp_path), store=store)
        assert [row.reason for row in rows if row.skipped] == []
        assert {row.item_id for row in rows} == {s.item_id for s in sets.values()}
        for spec in specs:
            exported = sets[spec.event_id]
            item = store.get_item(exported.item_id)
            assert item is not None
            assert item.expected_label == spec.label
            assert item.expected_risk_score == (spec.risk_band[0] + spec.risk_band[1]) // 2
            assert item.snapshot.timestamp == exported.labels["timestamp"]
            assert item.snapshot.specialist_outputs == {}
            assert item.snapshot.detections == exported.labels["detections"]
            assert item.media_paths == [str(exported.still)]


@pytest.mark.parametrize(
    "out", ["corpus", "corpus/exports", f"exports/../corpus/{h.VERSION}/vss"], ids=str
)
def test_an_out_inside_the_corpus_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], out: str
) -> None:
    """The corpus is append-only: an export (and its staging directory, written beside it) never
    lands inside it."""
    _ready_batch(tmp_path, MIXED, 4)
    before = _tree(tmp_path / "corpus")
    assert h.run(tmp_path, "export", "vss", "--out", str(tmp_path / out)) == cli.EXIT_ERROR
    assert "inside the corpus" in capsys.readouterr().err
    assert _tree(tmp_path / "corpus") == before


class TestSplitDraw:
    """ISS-016 (spec §2): the holdout is a published hash order, not anyone's choice.

    `draw_split` sees only the incident scenarios — a benign name reaching it is the export
    command's error to prevent, which Task 2's population test pins.
    """

    def test_the_registered_seed_is_the_pre_registered_string(self) -> None:
        """Changing this value changes the roster, which is the point of pre-registering it."""
        assert vss.SPLIT_SEEDS == {"tierb-v0": "vss-iss016-s3-holdout-2026-10-06"}
        assert vss.SPLIT_FILE == "splits.json"
        assert vss.SPLIT_HOLDOUT_K == 6

    def test_a_fixed_digest_pins_the_hash_recipe(self) -> None:
        # Computed by hand on 2026-10-06 and transcribed here: a deliberate tripwire, not a magic
        # string. If the recipe (its fields, separator or encoding) changes, this fails first.
        seed = vss.SPLIT_SEEDS["tierb-v0"]
        assert vss.scenario_rank("tierb-v0", seed, "knife_visible").startswith("2aad74ed")
        assert (
            vss.scenario_rank("tierb-v0", seed, "knife_visible")
            == hashlib.sha256(f"tierb-v0|{seed}|knife_visible".encode()).hexdigest()
        )

    def test_the_realized_draw_is_the_six_the_spec_publishes(self) -> None:
        draw = _draw()
        assert draw["seed"] == vss.SPLIT_SEEDS["tierb-v0"]
        assert draw["k"] == vss.SPLIT_HOLDOUT_K
        assert _holdout_names(draw) == HOLDOUT_SIX
        assert [row["scenario"] for row in draw["scenarios"]] == [
            *HOLDOUT_SIX,
            "forced_entry",
            "trying_car_doors",
            "child_alone_at_pool",
            "package_theft",
            "loitering",
            "fire_or_smoke",
            "catalytic_converter_theft",
            "person_down",
            "masked_intruder_night",
            "vandalism",
            "pool_trespass",
            "fence_climbing",
            "firearm_visible",
        ]
        assert all(row["arm"] == "holdout" for row in draw["scenarios"][:6])
        assert all(row["arm"] == "dev" for row in draw["scenarios"][6:])
        # the spec's arithmetic, read off the count table asserted above
        assert sum(ALL_19_ITEMS[name] for name in HOLDOUT_SIX) == 64
        assert sum(n for name, n in ALL_19_ITEMS.items() if name not in HOLDOUT_SIX) == 177
        assert sum(BENIGN_ITEMS.values()) == 209

    def test_the_draw_rows_carry_their_own_digests(self) -> None:
        """The manifest is its own audit trail: the roster is checkable without the seed."""
        draw = _draw()
        digests = [row["rank_sha256"] for row in draw["scenarios"]]
        assert all(len(d) == 64 for d in digests)
        assert digests == sorted(digests)
        for row in draw["scenarios"]:
            assert row["rank_sha256"] == vss.scenario_rank(
                "tierb-v0", vss.SPLIT_SEEDS["tierb-v0"], row["scenario"]
            )

    def test_the_roster_ignores_the_order_names_arrive_in(self) -> None:
        names = sorted(ALL_19_ITEMS)
        drawn = vss.draw_split("tierb-v0", list(reversed(names)))
        assert _holdout_names(drawn) == HOLDOUT_SIX
        rotated = vss.draw_split("tierb-v0", names[7:] + names[:7])
        assert rotated == _draw()  # the identical document, not merely the identical roster

    def test_a_different_seed_draws_a_different_roster(self) -> None:
        seed = vss.SPLIT_SEEDS["tierb-v0"]
        other = vss.draw_split("tierb-v0", sorted(ALL_19_ITEMS), seed=f"{seed}-next")
        assert _holdout_names(other) != HOLDOUT_SIX
        assert other["k"] == vss.SPLIT_HOLDOUT_K  # the roster moved; the size did not

    def test_the_size_never_empties_dev_or_goes_negative(self) -> None:
        """`max(0, min(k, n - 1))` — fires on fixtures and a stunted corpus, never on tierb-v0."""
        assert vss.draw_split("tierb-v0", []) == {
            "seed": vss.SPLIT_SEEDS["tierb-v0"],
            "k": 0,
            "scenarios": [],
        }
        one = vss.draw_split("tierb-v0", ["knife_visible"])
        assert one["k"] == 0 and [r["arm"] for r in one["scenarios"]] == ["dev"]
        two = vss.draw_split("tierb-v0", ["loitering", "knife_visible"], k=9)
        assert two["k"] == 1 and _holdout_names(two) == ["knife_visible"]  # 2aad… beats a911…

    def test_an_unregistered_corpus_version_has_no_seed_to_draw_on(self) -> None:
        """No fallback seed: reusing another corpus's seed would correlate two rosters."""
        with pytest.raises(KeyError, match="tierc-v0"):
            vss.draw_split("tierc-v0", sorted(ALL_19_ITEMS))
        with pytest.raises(KeyError, match="tierc-v0"):
            vss.split_manifest_document(
                "tierc-v0",
                dict.fromkeys(sorted(ALL_19_ITEMS), "dev"),
                items_by_scenario=_items_in_construction_order(),
            )

    def test_the_manifest_covers_every_exported_scenario(self) -> None:
        """Spec §2: `arms` lists all 31 so a reader never re-derives which scenarios exist."""
        manifest = _manifest()
        assert manifest["corpus_version"] == "tierb-v0"
        assert manifest["seed"] == vss.SPLIT_SEEDS["tierb-v0"]
        assert manifest["holdout_k"] == vss.SPLIT_HOLDOUT_K
        assert manifest["unit"] == "scenario"
        assert manifest["arms"] == {
            "holdout": sorted(HOLDOUT_SIX),
            "dev": sorted(set(ALL_19_ITEMS) - set(HOLDOUT_SIX) | set(BENIGN_ITEMS)),
        }
        assert not set(BENIGN_ITEMS) & set(manifest["arms"]["holdout"])  # benign is always dev (B1)
        assert [row["scenario"] for row in manifest["draw"]] == [
            row["scenario"] for row in _draw()["scenarios"]
        ]
        assert set(manifest) == {
            "corpus_version",
            "seed",
            "holdout_k",
            "unit",
            "arms",
            "draw",
            "items",
        }

    def test_an_arm_outside_dev_and_holdout_stops_the_manifest(self) -> None:
        """The module fails two ways only — KeyError for an absent seed, ExportConflict for an
        export that disagrees with the corpus — so a mis-armed scenario is Task 2's exit 2, not a
        bare KeyError the command reads as the seed being missing."""
        arm = {"knife_visible": "dev", "loitering": "test"}
        with pytest.raises(vss.ExportConflict, match=r"loitering is armed 'test'"):
            vss.split_manifest_document(
                "tierb-v0", arm, items_by_scenario={n: ITEMS_BY_SCENARIO[n] for n in arm}
            )

    def test_the_manifest_items_are_the_arm_totals(self) -> None:
        """64/177/209: the split's published arithmetic, from the count table above."""
        assert _manifest()["items"] == {
            "holdout": {"benign": 0, "incident": 64},
            "dev": {"benign": 209, "incident": 177},
        }

    def test_the_manifest_bytes_ignore_dict_construction_order(self) -> None:
        """`splits.json` is canonical bytes, so its sha256 names the split, not a dict's history."""
        arm = _scenario_arm()
        forward = vss.split_manifest_document(
            "tierb-v0", arm, items_by_scenario=_items_in_construction_order()
        )
        reverse = vss.split_manifest_document(
            "tierb-v0",
            {name: arm[name] for name in sorted(arm, reverse=True)},
            items_by_scenario=_items_in_construction_order(scrambled=True),
        )
        assert vss.split_sha256(forward) == vss.split_sha256(reverse)
        assert (
            vss.split_sha256(forward)
            == hashlib.sha256(
                json.dumps(forward, indent=2, sort_keys=True).encode() + b"\n"
            ).hexdigest()
        )

    def test_write_split_is_create_once(self, tmp_path: Path) -> None:
        manifest = _manifest()
        assert vss.write_split(tmp_path, manifest) is True
        assert json.loads((tmp_path / vss.SPLIT_FILE).read_text(encoding="utf-8")) == manifest
        assert vss.write_split(tmp_path, manifest) is False  # identical bytes: left alone
        assert vss.read_split(tmp_path) == manifest
        with pytest.raises(vss.ExportConflict, match="differs"):
            vss.write_split(tmp_path, manifest | {"holdout_k": 5})

    def test_read_split_is_none_for_a_pre_split_export(self, tmp_path: Path) -> None:
        """B6: an export without a manifest stays readable and scores as `split: unrecorded`."""
        assert vss.read_split(tmp_path) is None
        assert vss.write_split(tmp_path, _manifest()) is True
        assert (tmp_path / vss.SPLIT_FILE).is_file()
        assert vss.read_split(tmp_path) == _manifest()
