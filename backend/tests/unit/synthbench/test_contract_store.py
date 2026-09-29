"""Where a corpus version's files live, and the append-only writer (design §2)."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
from pathlib import Path

import pytest
from synthbench.contract.corpus import CorpusManifest, IndexRow
from synthbench.contract.spec import Cell, Spec, Subject
from synthbench.contract.store import CorpusStore, sha256_file, to_json

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
    assert default.version_dir == Path("/synthbench/corpus/tierb-v0")
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
    tier_a = "A-lakehouse-dock_cam2-00417"
    assert store.event_dir(tier_a) == tmp_path / "tierb-v0" / "events" / "A" / tier_a


@pytest.mark.parametrize(
    "event_id", ["C-x-000", "B", "b-pilot-1-000", "B-a/../escape", "B-x/y", "B-.."]
)
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


def test_written_files_are_world_readable(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    store.write_new(store.manifest_file, _manifest())
    store.append_index([_row("B-pilot-1-000")])
    store.replace_text(store.spec_file("B-pilot-1-000"), "{}\n")
    for path in (store.manifest_file, store.index_file, store.spec_file("B-pilot-1-000")):
        assert stat.S_IMODE(path.stat().st_mode) == 0o644, path


def test_write_new_bytes_stores_exact_bytes_and_never_replaces(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    path = store.event_dir("B-pilot-1-000") / "renders" / "a1-s5.png"
    store.write_new_bytes(path, b"\x89PNG first")
    with pytest.raises(FileExistsError):
        store.write_new_bytes(path, b"\x89PNG second")
    assert path.read_bytes() == b"\x89PNG first"
    assert sha256_file(path) == hashlib.sha256(b"\x89PNG first").hexdigest()
    assert [p.name for p in path.parent.iterdir()] == ["a1-s5.png"]


def test_write_new_falls_back_where_hard_links_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(self: Path, _target: Path) -> None:
        raise PermissionError(errno.EPERM, "Operation not permitted", str(self))

    monkeypatch.setattr(Path, "hardlink_to", refuse)
    store = CorpusStore(tmp_path, "tierb-v0")
    store.write_new(store.manifest_file, _manifest())
    assert store.read(store.manifest_file, CorpusManifest) == _manifest()
    with pytest.raises(FileExistsError):
        store.write_new(store.manifest_file, _manifest(created="2026-09-29T00:00:00+00:00"))
    assert [p.name for p in store.version_dir.iterdir()] == ["corpus.json"]


def test_other_link_failures_propagate_and_leave_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: Path, _target: Path) -> None:
        raise OSError(errno.EIO, "Input/output error", str(self))

    monkeypatch.setattr(Path, "hardlink_to", broken)
    store = CorpusStore(tmp_path, "tierb-v0")
    with pytest.raises(OSError, match="Input/output error"):
        store.write_new(store.manifest_file, _manifest())
    assert list(store.version_dir.iterdir()) == []


def test_nothing_is_written_outside_the_version(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus", "tierb-v0")
    with pytest.raises(ValueError, match="outside corpus version"):
        store.write_new_bytes(tmp_path / "elsewhere.png", b"x")
    with pytest.raises(ValueError, match="outside corpus version"):
        store.replace_text(store.version_dir / ".." / "other-v0" / "x.json", "{}\n")


def test_replace_text_swaps_json_and_views_atomically(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    path = store.spec_file("B-pilot-1-000")
    store.replace_text(path, '{"a": 1}\n')
    store.replace_text(path, '{"a": 2}\n')
    assert path.read_text(encoding="utf-8") == '{"a": 2}\n'
    assert [p.name for p in path.parent.iterdir()] == ["spec.json"]
    view = store.batch_dir("pilot-1") / "report.md"
    store.replace_text(view, "# report\n")
    assert view.read_text(encoding="utf-8") == "# report\n"
    with pytest.raises(ValueError, match="change in place"):
        store.replace_text(path.with_name("a1.png"), "x")


def test_an_index_append_is_one_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sizes: list[int] = []
    real_write = os.write

    def counting(fd: int, data: bytes) -> int:
        sizes.append(len(data))
        return real_write(fd, data)

    monkeypatch.setattr(os, "write", counting)
    store = CorpusStore(tmp_path, "tierb-v0")
    store.append_index([_row("B-pilot-1-000"), _row("B-pilot-1-001"), _row("B-pilot-1-002")])
    assert len(sizes) == 1
    assert len(store.latest_index()) == 3
