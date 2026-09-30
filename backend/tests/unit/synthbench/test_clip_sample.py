"""`clip sample` (clips design §3.1): the draw, the pilot rule and the round's files."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from synthbench import cli
from synthbench.clips import settings as clip_settings
from synthbench.clips.gate import ClipGate, gate_file, meets_bar
from synthbench.clips.sample import Candidate, draw, split
from synthbench.contract.clip import ClipSettings, ClipSpec, RoundRecord, source_facts
from synthbench.contract.provenance import Provenance
from synthbench.status import write_status

from backend.tests.unit.synthbench import helpers as h

PILOT = "clips-pilot-1"


def _sample(root: Path, name: str = PILOT, n: int = 4) -> int:
    return h.run(root, "clip", "sample", "--round", name, "--n", str(n))


def _record(root: Path, name: str = PILOT) -> RoundRecord:
    store = h.store(root)
    return store.read(store.round_file(name), RoundRecord)


def _gate(
    root: Path, round_name: str, passed_all: int, n: int, settings: ClipSettings | None = None
) -> None:
    gate = ClipGate(
        round=round_name,
        n=n,
        passed_all=passed_all,
        rate=passed_all / n,
        passed=meets_bar(passed_all, n),
        settings=settings or clip_settings.current(),
        time=datetime(2026, 10, 1, tzinfo=UTC),
    )
    write_status(gate_file(h.env(root)), gate)


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


def test_the_draw_is_seeded_and_ignores_input_order() -> None:
    groups, lights = ("threat", "benign"), ("day", "ir_night", "dusk")
    pool = [Candidate(f"B-b-{i:03d}", groups[i % 2], lights[i % 3]) for i in range(30)]
    first = draw(pool, 6, seed=7)
    assert first == draw(list(reversed(pool)), 6, seed=7)
    assert [c.group for c in first].count("threat") == 3
    assert len({c.event_id for c in first}) == 6


def test_a_gate_must_add_up() -> None:
    settings = clip_settings.current()
    time = datetime(2026, 10, 1, tzinfo=UTC)
    ClipGate(round="r", n=5, passed_all=4, rate=0.8, passed=True, settings=settings, time=time)
    with pytest.raises(ValidationError):
        ClipGate(round="r", n=5, passed_all=4, rate=0.5, passed=True, settings=settings, time=time)
    with pytest.raises(ValidationError):
        ClipGate(round="r", n=5, passed_all=3, rate=0.6, passed=True, settings=settings, time=time)


def test_the_bar_is_80_percent_of_n() -> None:
    assert meets_bar(16, 20)
    assert not meets_bar(15, 20)
    assert meets_bar(4, 5)


def test_the_first_round_is_a_pilot_of_at_most_20(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    h.ready_batch(tmp_path, n=4)
    assert _sample(tmp_path, n=21) == cli.EXIT_ERROR
    assert "the pilot: --n at most 20" in capsys.readouterr().err
    assert _sample(tmp_path, n=3) == cli.EXIT_OK
    record = _record(tmp_path)
    assert record.pilot
    assert record.n == 3
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


def test_a_pilot_awaiting_its_audit_stops_the_next_round(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    h.ready_batch(tmp_path, n=6)
    assert _sample(tmp_path, n=2) == cli.EXIT_OK
    assert _sample(tmp_path, "clips-2", 2) == cli.EXIT_ASK
    assert f"pilot round {PILOT} awaits the owner's audit" in capsys.readouterr().err


def test_a_failed_gate_stops_new_rounds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    h.ready_batch(tmp_path, n=6)
    assert _sample(tmp_path, n=2) == cli.EXIT_OK
    _gate(tmp_path, PILOT, 1, 2)
    assert _sample(tmp_path, "clips-2", 2) == cli.EXIT_ASK
    assert "failed the owner's audit" in capsys.readouterr().err


def test_a_passed_gate_allows_volume_from_stills_without_a_clip(tmp_path: Path) -> None:
    h.ready_batch(tmp_path, n=8)
    assert _sample(tmp_path, n=2) == cli.EXIT_OK
    _gate(tmp_path, PILOT, 2, 2)
    assert _sample(tmp_path, "clips-2", 6) == cli.EXIT_OK
    second = _record(tmp_path, "clips-2")
    assert not second.pilot
    assert not set(second.source_event_ids) & set(_record(tmp_path).source_event_ids)
    assert _sample(tmp_path, "clips-3", 1) == cli.EXIT_ERROR  # every still has a clip now


def test_a_gate_for_other_settings_means_a_new_pilot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    h.ready_batch(tmp_path, n=4)
    _gate(tmp_path, "old-pilot", 20, 20, settings=clip_settings.current().updated(frames=124))
    assert _sample(tmp_path, n=21) == cli.EXIT_ERROR
    assert "the pilot" in capsys.readouterr().err
    assert _sample(tmp_path, n=2) == cli.EXIT_OK
    assert _record(tmp_path).pilot


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
    path = store.spec_file(f"C-{PILOT}-000")
    clip = store.read(path, ClipSpec)
    store.replace_json(path, clip.updated(risk_band=(1, 2)))  # no scenario has this band
    assert _sample(tmp_path, n=2) == cli.EXIT_ASK
    assert "changed by hand" in capsys.readouterr().err


def test_an_unreadable_gate_exits_2(tmp_path: Path) -> None:
    h.ready_batch(tmp_path, n=2)
    path = gate_file(h.env(tmp_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{", encoding="utf-8")
    assert _sample(tmp_path, n=2) == cli.EXIT_ASK


def test_a_corpus_without_stills_exits_1(tmp_path: Path) -> None:
    assert _sample(tmp_path, n=2) == cli.EXIT_ERROR
