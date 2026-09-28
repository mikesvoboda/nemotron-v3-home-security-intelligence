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
