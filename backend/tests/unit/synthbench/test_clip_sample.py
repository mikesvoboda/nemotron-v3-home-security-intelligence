"""`clip sample` (clips design §3.1): the draw and the round's files. There is no pilot rule
(spec C13)."""

from __future__ import annotations

from pathlib import Path

import pytest
from synthbench import cli
from synthbench.clips import settings as clip_settings
from synthbench.clips.sample import Candidate, draw, split
from synthbench.contract.clip import ClipSpec, RoundRecord, source_facts
from synthbench.contract.provenance import Provenance

from backend.tests.unit.synthbench import helpers as h

ROUND = "clips-1"


def _sample(root: Path, name: str = ROUND, n: int = 4) -> int:
    return h.run(root, "clip", "sample", "--round", name, "--n", str(n))


def _record(root: Path, name: str = ROUND) -> RoundRecord:
    store = h.store(root)
    return store.read(store.round_file(name), RoundRecord)


def _tree(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in h.store(root).version_dir.rglob("*") if p.is_file()}


def test_split_is_even_with_the_remainder_to_the_largest_groups() -> None:
    counts = {"threat": 196, "hard_negative": 145, "benign": 64, "suspicious": 45, "ambiguous": 9}
    assert split(counts, 20) == dict.fromkeys(counts, 4)
    assert split(counts, 22) == {
        "ambiguous": 4,
        "benign": 4,
        "hard_negative": 5,
        "suspicious": 4,
        "threat": 5,
    }
    assert split({"a": 1, "b": 10}, 6) == {"a": 1, "b": 5}  # a full group's share goes on
    assert split({"a": 2, "b": 0}, 9) == {"a": 2}  # never more than there is
    assert sum(split(counts, 459).values()) == 459  # every ready still in one round


def test_the_draw_is_seeded_and_ignores_input_order() -> None:
    groups, lights = ("threat", "benign"), ("day", "ir_night", "dusk")
    pool = [Candidate(f"B-b-{i:03d}", groups[i % 2], lights[i % 3]) for i in range(30)]
    first = draw(pool, 6, seed=7)
    assert first == draw(list(reversed(pool)), 6, seed=7)
    assert [c.group for c in first].count("threat") == 3
    assert len({c.event_id for c in first}) == 6


def test_a_first_round_may_take_every_ready_still(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    h.ready_batch(tmp_path, n=6)
    assert _sample(tmp_path, n=6) == cli.EXIT_OK
    record = _record(tmp_path)
    assert record.n == 6
    assert record.settings == clip_settings.current()
    assert "Next: write" in capsys.readouterr().out


def test_each_clip_copies_its_source_and_pins_its_render(tmp_path: Path) -> None:
    specs = {spec.event_id: spec for spec in h.ready_batch(tmp_path, n=4)}
    assert _sample(tmp_path, n=4) == cli.EXIT_OK
    store = h.store(tmp_path)
    record = _record(tmp_path)
    assert set(record.source_event_ids) == set(specs)
    for event_id, source_id in zip(record.event_ids, record.source_event_ids, strict=True):
        clip = store.read(store.spec_file(event_id), ClipSpec)
        assert clip.facts() == source_facts(specs[source_id])
        render = store.read(store.provenance_file(source_id), Provenance).attempts[-1].render
        assert render is not None
        assert clip.source.render_sha256 == render.sha256
    rows = store.latest_clip_index()
    assert {row.status for row in rows.values()} == {"sampled"}
    assert {row.source for row in rows.values()} == set(specs)


def test_a_second_round_draws_only_stills_without_a_clip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    h.ready_batch(tmp_path, n=8)
    assert _sample(tmp_path, n=2) == cli.EXIT_OK
    assert _sample(tmp_path, "clips-2", 6) == cli.EXIT_OK
    assert not set(_record(tmp_path, "clips-2").source_event_ids) & set(
        _record(tmp_path).source_event_ids
    )
    assert _sample(tmp_path, "clips-3", 1) == cli.EXIT_ERROR
    assert "every ready still already has a clip" in capsys.readouterr().err


def test_more_clips_than_eligible_stills_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    h.ready_batch(tmp_path, n=3)
    assert _sample(tmp_path, n=4) == cli.EXIT_ERROR
    assert "3 ready still(s) have no clip yet" in capsys.readouterr().err


def test_rerunning_a_round_changes_nothing_and_another_n_exits_1(tmp_path: Path) -> None:
    h.ready_batch(tmp_path, n=4)
    assert _sample(tmp_path, n=3) == cli.EXIT_OK
    before = _tree(tmp_path)
    assert _sample(tmp_path, n=3) == cli.EXIT_OK
    assert _tree(tmp_path) == before
    assert _sample(tmp_path, n=2) == cli.EXIT_ERROR


def test_a_hand_edited_clip_spec_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    h.ready_batch(tmp_path, n=2)
    assert _sample(tmp_path, n=2) == cli.EXIT_OK
    store = h.store(tmp_path)
    path = store.spec_file(f"C-{ROUND}-000")
    clip = store.read(path, ClipSpec)
    store.replace_json(path, clip.updated(risk_band=(1, 2)))  # no scenario has this band
    assert _sample(tmp_path, n=2) == cli.EXIT_ASK
    assert "changed by hand" in capsys.readouterr().err


def test_a_corpus_without_stills_exits_1(tmp_path: Path) -> None:
    assert _sample(tmp_path, n=2) == cli.EXIT_ERROR


def test_nothing_imports_the_gate() -> None:
    import importlib.util

    assert importlib.util.find_spec("synthbench.clips.gate") is None
