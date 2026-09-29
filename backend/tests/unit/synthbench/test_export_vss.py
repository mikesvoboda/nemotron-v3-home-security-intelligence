"""`export vss` (P5a design §2): ready Tier B events in the VSS eval store's import layout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from synthbench import cli
from synthbench.contract.corpus import BatchRecord
from synthbench.contract.provenance import Provenance
from synthbench.contract.spec import Spec
from synthbench.export import vss

from backend.tests.unit.synthbench import helpers as h

# One scenario per exported group: threat, suspicious, hard_negative, benign.
MIXED = "knife_visible,loitering,hooded_jogger,delivery_driver"


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
