"""`export vss --sequences N` (ISS-037): frame-sampled sequence sets beside the stills.

The clip corpus this slice measures against: every READY clip becomes one set of N JPEG
frames sampled at fixed fractions of the mp4, carrying the clip's declared truth. The tests
pin what the funded measurement rests on: the index arithmetic is the published fractions,
the frames really decode from the recorded mp4, the set imports through the shipped
importer, and the stills' importer cannot see any of it.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import av
import pytest
from synthbench import cli
from synthbench.export import sequence, vss

from backend.tests.unit.synthbench import helpers as h

# 48 frames at 24 fps: a real H.264 encode at import (~0.1 s) small enough that the fixture
# below records four of them without paying for the module's default 243-frame mp4. Flat
# pixels, so the frames' JPEG digests stay byte-identical across every test's export.
H_MP4 = h.mp4(frames=48)


def _seqs(export: Path) -> Path:
    return export / sequence.SEQUENCE_DIR


def _export(root: Path, capsys: pytest.CaptureFixture[str], frames: int = 3) -> tuple[Path, str]:
    """`export vss --sequences N` over the fixture's corpus; returns (export dir, stdout)."""
    assert h.run(root, "export", "vss", "--sequences", str(frames)) == cli.EXIT_OK
    return root / "exports" / h.VERSION / "vss", capsys.readouterr().out


def _real_ready_round(root: Path, n: int = 4, name: str = "clips-pilot-1") -> list[Any]:
    """`h.ready_round`'s twin, recorded with real mp4 bytes: the sampling tests decode what
    they sample, so the recorded sha256 must sit under real H.264. Triage still runs (a ready
    clip is one an ok verdict was written against — its bytes do not skip the ritual)."""
    specs = h.frozen_round(root, n=n, name=name)
    for spec in specs:
        h.record_clip(root, spec, clip=H_MP4)
    h.write_clip_triage(
        root, name, [{"event_id": spec.event_id, "k": 1, "verdict": "ok"} for spec in specs]
    )
    assert h.run(root, "clip", "triage", "--round", name) == cli.EXIT_OK
    return specs


def _set_dir(export: Path, spec: Any, frames: int = 3) -> Path:
    return (
        _seqs(export)
        / vss.CATEGORY[spec.cell.group]
        / sequence.sequence_name(spec.event_id, frames)
    )


def test_the_sample_indices_are_the_published_fractions() -> None:
    assert sequence.sample_indices(243, 3) == [24, 121, 218]  # int(243 * 10/50/90%)
    assert sequence.sample_indices(243, 4) == [24, 87, 150, 218]
    assert sequence.sample_indices(4, 4) == [0, 1, 2, 3]  # the smallest clip that yields 4


def test_a_clip_shorter_than_the_sample_is_refused_not_duplicated() -> None:
    """N distinct frames need at least N frames: at the stream's end the clamp stops the
    bump, so a 2-frame "sample 3" would put one moment on the wire twice under two times."""
    with pytest.raises(ValueError, match="no 3 distinct frames"):
        sequence.sample_indices(2, 3)
    with pytest.raises(ValueError, match="frames must be one of"):
        sequence.sample_indices(100, 5)


def test_frame_count_reads_the_real_stream() -> None:
    assert sequence.clip_frame_count(H_MP4) == 48


def test_the_offsets_come_from_the_streams_own_rate() -> None:
    assert sequence.offsets_ms([0, 12, 47], 24.0) == [0, 500, 1958]


def test_the_timeline_is_the_scene_time_plus_the_clips_frame_times() -> None:
    times = sequence.sequence_timestamps("14:32", "clear", [0, 500, 1958])
    assert times[0] == "2026-04-15T14:32:00-04:00"  # the stills' own dating rule
    assert times[1] == "2026-04-15T14:32:00.500000-04:00"
    assert times[2] == "2026-04-15T14:32:01.958000-04:00"
    assert sequence.sequence_timestamps("06:05", "snow", [0])[0].startswith("2026-01-15")


def test_detections_are_one_row_per_object_per_frame_with_its_time() -> None:
    # subjects then props, in spec order — the stills' declared_detections order, and these
    # stubs read like the spec objects the real caller passes (the function reads .cls)
    objects = [SimpleNamespace(cls="person"), SimpleNamespace(cls="knife")]
    rows = sequence.frame_detections(
        objects,
        ["frame1.jpg", "frame2.jpg"],
        ["2026-04-15T14:32:00-04:00", "2026-04-15T14:32:01-04:00"],
    )
    assert [row["id"] for row in rows] == [1, 2, 3, 4]  # batch-global: the wire reads ids so
    assert rows[1] == {
        "id": 2,
        "object_type": "knife",
        "confidence": 1.0,
        "file_path": "frame1.jpg",
        "detected_at": "2026-04-15T14:32:00-04:00",
    }


def test_an_empty_scene_still_declares_one_row() -> None:
    """A production prompt with `Detections: []` refuses to judge (the stills learned this
    the hard way); an empty scene row keeps every exported set judgeable."""
    rows = sequence.frame_detections([], ["frame1.jpg"], ["2026-04-15T14:32:00-04:00"])
    assert [row["object_type"] for row in rows] == ["scene"]


class TestSequenceExport:
    """`export vss --sequences 3` over a round whose clips are real mp4 bytes."""

    @pytest.fixture()
    def specs(self, tmp_path: Path) -> list[Any]:
        return _real_ready_round(tmp_path)

    def test_ready_clips_become_frame_sets_with_the_declared_truth(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], specs: list[Any]
    ) -> None:
        export, out = _export(tmp_path, capsys)
        assert "3-frame sets" in out and "4 written now" in out
        spec = specs[0]
        labels = json.loads((_set_dir(export, spec) / vss.LABELS_FILE).read_text(encoding="utf-8"))
        assert labels["category"] == vss.CATEGORY[spec.cell.group]
        assert labels["risk"] == {"min_score": spec.risk_band[0], "max_score": spec.risk_band[1]}
        facts = labels["synthbench"]
        # the batch is stamped by its earliest frame (production's rule), not its scene start
        assert labels["timestamp"] == facts["frame_times"][0] == facts["frame_times"][0]
        n_objects = max(1, len(spec.subjects) + len(spec.props))
        assert len(labels["detections"]) == 3 * n_objects
        assert {row["file_path"] for row in labels["detections"]} == {
            "frame1.jpg",
            "frame2.jpg",
            "frame3.jpg",
        }
        assert facts["kind"] == "sequence"
        assert facts["frames"] == 3
        assert facts["event_id"] == spec.event_id
        assert facts["cell"]["scenario"] == spec.cell.scenario
        assert facts["timeline"] == "declared scene_time + the clip's own frame times"
        assert facts["source_clip"]["frame_count"] == 48
        assert facts["frame_sha256s"] == [
            hashlib.sha256((_set_dir(export, spec) / f"frame{i}.jpg").read_bytes()).hexdigest()
            for i in (1, 2, 3)
        ]
        sidecar = json.loads((_set_dir(export, spec) / "frame2.json").read_text(encoding="utf-8"))
        assert sidecar["license"] and sidecar["artist"]
        assert sidecar["frame_sha256"] == facts["frame_sha256s"][1]

    def test_the_frames_really_came_from_the_mp4(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], specs: list[Any]
    ) -> None:
        """Not stand-in bytes: each frame decodes at the source resolution, and its offsets
        say which moments of the flat 48-frame render it is."""
        export, _ = _export(tmp_path, capsys)
        set_dir = _set_dir(export, specs[0])
        labels = json.loads((set_dir / vss.LABELS_FILE).read_text(encoding="utf-8"))
        offsets = labels["synthbench"]["frame_offsets_ms"]
        assert offsets == [167, 1000, 1792]  # indices 4/24/43 at the stream's own 24 fps
        for frame_file in ("frame1.jpg", "frame2.jpg", "frame3.jpg"):
            with av.open(io.BytesIO((set_dir / frame_file).read_bytes())) as container:
                frame = next(container.decode(video=0))
            assert frame.to_ndarray(format="rgb24").shape == (768, 1344, 3)

    def test_a_second_export_changes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], specs: list[Any]
    ) -> None:
        export, _ = _export(tmp_path, capsys)
        tree = {p: p.read_bytes() for p in _seqs(export).rglob("*") if p.is_file()}
        _, out = _export(tmp_path, capsys)
        assert "0 written now, 4 unchanged" in out
        assert {p: p.read_bytes() for p in _seqs(export).rglob("*") if p.is_file()} == tree

    def test_a_set_that_differs_from_the_clip_exits_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], specs: list[Any]
    ) -> None:
        export, _ = _export(tmp_path, capsys)
        next(_seqs(export).glob("*/*/frame1.jpg")).write_bytes(b"tampered")
        assert h.run(tmp_path, "export", "vss", "--sequences", "3") == cli.EXIT_ASK
        assert "differs from the corpus" in capsys.readouterr().err

    def test_a_clip_that_no_longer_matches_its_sha256_exits_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], specs: list[Any]
    ) -> None:
        export, _ = _export(tmp_path, capsys)  # a good export first: the refusal is pre-write
        spec = specs[0]
        store = h.store(tmp_path)
        prov = store.read(store.provenance_file(spec.event_id), h.ClipProvenance)
        clip = prov.attempts[-1].clip
        assert clip is not None
        (store.event_dir(spec.event_id) / clip.path).write_bytes(b"tampered")
        assert h.run(tmp_path, "export", "vss", "--sequences", "3") == cli.EXIT_ASK
        assert "does not match its recorded sha256" in capsys.readouterr().err

    def test_a_stand_in_clip_is_named_not_sampled_silently(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The default round records `b"mp4 " + tag` bytes: undecodable, and refused with the
        clip's name — a corpus member whose frames cannot be read must not export half a
        timeline."""
        specs = h.ready_round(tmp_path)
        assert h.run(tmp_path, "export", "vss", "--sequences", "3") == cli.EXIT_ASK
        err = capsys.readouterr().err
        assert specs[0].event_id in err

    def test_sequences_are_invisible_to_the_stills_reader(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], specs: list[Any]
    ) -> None:
        export, _ = _export(tmp_path, capsys)
        stills = vss.read_sets(export)
        assert all(s.facts.get("kind") != "sequence" for s in stills)
        seqs = sequence.read_sequence_sets(export)
        assert len(seqs) == 4
        assert seqs[0].item_id == f"generated:{seqs[0].category}:{specs[0].event_id}__seq3"
        assert seqs[0].still.name == "frame1.jpg"  # the set's first image, from its labels
        assert all(s.still.name.startswith("frame") for s in seqs)

    def test_the_split_never_sees_the_sequences(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], specs: list[Any]
    ) -> None:
        export, _ = _export(tmp_path, capsys)
        manifest = vss.read_split(export)
        assert manifest is not None
        # the manifest's totals are the stills only: sequences join no arm and no count
        total = sum(n for counts in manifest["items"].values() for n in counts.values())
        assert total == len(vss.read_sets(export)) == 4

    def test_the_exported_sequences_import_through_the_shipped_importer(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], specs: list[Any]
    ) -> None:
        from backend.evaluation.eval_store import EvalStore
        from backend.evaluation.label_import import import_generated_items

        export, _ = _export(tmp_path, capsys)
        sets = {s.item_id: s for s in sequence.read_sequence_sets(export)}
        with EvalStore(tmp_path / "eval.sqlite") as store:
            rows = import_generated_items(corpus_dir=_seqs(export), store=store)
            assert [row.reason for row in rows if row.skipped] == []
            assert {row.item_id for row in rows} == set(sets)
            for item_id, exported in sets.items():
                item = store.get_item(item_id)
                assert item is not None
                assert item.expected_label == exported.facts["label"]
                # depth-3 sets import sorted, oldest frame first
                assert [Path(p).name for p in item.media_paths] == [
                    "frame1.jpg",
                    "frame2.jpg",
                    "frame3.jpg",
                ]
                assert item.snapshot.detections == exported.labels["detections"]
                assert item.snapshot.timestamp == exported.labels["timestamp"]

    def test_the_stills_import_cannot_read_a_sequence_set(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], specs: list[Any]
    ) -> None:
        from backend.evaluation.eval_store import EvalStore
        from backend.evaluation.label_import import import_generated_items

        export, _ = _export(tmp_path, capsys)
        with EvalStore(tmp_path / "eval.sqlite") as store:
            rows = import_generated_items(corpus_dir=export, store=store)
            ids = {row.item_id for row in rows}
            assert ids == {s.item_id for s in vss.read_sets(export)}
            assert not any(item_id.endswith("__seq3") for item_id in ids)

    def test_an_out_inside_the_corpus_refuses_before_anything_is_written(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The guard runs before any sampling: the corpus is append-only, and the sequences'
        staging directory lands beside its --out, so `corpus/../corpus/x` inside it is refused
        the same way the stills refuse it."""
        _real_ready_round(tmp_path)
        before = {p: p.read_bytes() for p in (tmp_path / "corpus").rglob("*") if p.is_file()}
        inside = tmp_path / "corpus" / "seq"
        assert (
            h.run(tmp_path, "export", "vss", "--out", str(inside), "--sequences", "3")
            == cli.EXIT_ERROR
        )
        assert "inside the corpus" in capsys.readouterr().err
        after = {p: p.read_bytes() for p in (tmp_path / "corpus").rglob("*") if p.is_file()}
        assert after == before
