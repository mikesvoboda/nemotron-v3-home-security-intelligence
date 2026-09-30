"""`clip check` (clips design §3.2): the motion rules, the source checks and freezing."""

from __future__ import annotations

from pathlib import Path

import pytest
from synthbench import cli
from synthbench.clips import rules as clip_rules
from synthbench.clips.settings import CLIP_SUFFIX
from synthbench.contract.clip import ClipProvenance, ClipSpec
from synthbench.contract.provenance import Provenance, attempt_seed
from synthbench.prompt import rules

from backend.tests.unit.synthbench import helpers as h

PILOT = "clips-pilot-1"


def _check(root: Path) -> int:
    return h.run(root, "clip", "check", "--round", PILOT)


def _motions(specs: list[ClipSpec], **changed: str) -> dict[str, str]:
    return {spec.event_id: changed.get(spec.event_id, h.good_motion(spec)) for spec in specs}


def test_passing_motions_freeze_and_open_attempt_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.frozen_round(tmp_path, n=3)
    store = h.store(tmp_path)
    for spec in specs:
        assert spec.prompt == h.good_motion(spec)
        assert spec.clip_suffix == CLIP_SUFFIX
        prov = store.read(store.provenance_file(spec.event_id), ClipProvenance)
        (first,) = prov.attempts
        assert first.seed == attempt_seed(spec.event_id, 1)
        assert first.prompt_sha256 == clip_rules.motion_sha256(spec)
    assert {row.status for row in store.latest_clip_index().values()} == {"prompted"}
    assert f"Next: clip render --round {PILOT}" in capsys.readouterr().out


def test_a_second_check_freezes_nothing_new(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    h.frozen_round(tmp_path, n=2)
    capsys.readouterr()
    assert _check(tmp_path) == cli.EXIT_OK
    assert "0 frozen now" in capsys.readouterr().out


def test_a_motion_must_name_every_subject_and_prop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.clip_round(tmp_path, n=4)
    cast = next(spec for spec in specs if spec.subjects)
    h.write_motions(tmp_path, PILOT, _motions(specs, **{cast.event_id: "Leaves move."}))
    assert _check(tmp_path) == cli.EXIT_ERROR
    assert f"{cast.event_id}: rule 1" in capsys.readouterr().err


@pytest.mark.parametrize(
    "extra", ["The camera pans to the left.", "Cut to the street.", "A moment later, silence."]
)
def test_camera_moves_and_cuts_break_rule_5(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], extra: str
) -> None:
    specs = h.clip_round(tmp_path, n=2)
    motion = f"{h.good_motion(specs[0])} {extra}"
    h.write_motions(tmp_path, PILOT, _motions(specs, **{specs[0].event_id: motion}))
    assert _check(tmp_path) == cli.EXIT_ERROR
    assert f"{specs[0].event_id}: rule 5" in capsys.readouterr().err


def test_a_missing_row_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    specs = h.clip_round(tmp_path, n=2)
    h.write_motions(tmp_path, PILOT, {specs[0].event_id: h.good_motion(specs[0])})
    assert _check(tmp_path) == cli.EXIT_ERROR
    assert f"{specs[1].event_id}: no row in motions.jsonl" in capsys.readouterr().err


def test_a_row_for_a_clip_outside_the_round_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.clip_round(tmp_path, n=2)
    h.write_motions(tmp_path, PILOT, _motions(specs) | {"C-other-000": "x"})
    assert _check(tmp_path) == cli.EXIT_ERROR
    assert f"C-other-000 is not in round {PILOT}" in capsys.readouterr().err


def test_a_frozen_motion_never_changes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    specs = h.frozen_round(tmp_path, n=2)
    h.write_motions(tmp_path, PILOT, _motions(specs, **{specs[0].event_id: "Leaves move."}))
    assert _check(tmp_path) == cli.EXIT_ERROR
    assert "the frozen motion never changes" in capsys.readouterr().err


def test_a_changed_source_render_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.frozen_round(tmp_path, n=2)
    store = h.store(tmp_path)
    source = specs[0].source.event_id
    render = store.read(store.provenance_file(source), Provenance).attempts[-1].render
    assert render is not None
    (store.event_dir(source) / render.path).write_bytes(h.png(color=(1, 2, 3)))
    assert _check(tmp_path) == cli.EXIT_ASK
    assert "was modified" in capsys.readouterr().err


def test_a_source_that_is_no_longer_ready_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.frozen_round(tmp_path, n=2)
    store = h.store(tmp_path)
    row = store.latest_index()[specs[0].source.event_id]
    store.append_index([row.model_copy(update={"status": "failed"})])
    assert _check(tmp_path) == cli.EXIT_ASK
    assert "no longer ready" in capsys.readouterr().err


def test_copied_facts_that_differ_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.frozen_round(tmp_path, n=2)
    store = h.store(tmp_path)
    store.replace_json(store.spec_file(specs[0].event_id), specs[0].updated(risk_band=(1, 2)))
    assert _check(tmp_path) == cli.EXIT_ASK
    assert "facts differ from the source still's" in capsys.readouterr().err


def test_an_unexpected_file_in_a_clip_event_exits_2(tmp_path: Path) -> None:
    specs = h.frozen_round(tmp_path, n=1)
    folder = h.store(tmp_path).event_dir(specs[0].event_id) / "clips"
    folder.mkdir()
    (folder / "extra.mp4").write_bytes(b"x")
    assert _check(tmp_path) == cli.EXIT_ASK


def test_an_attempt_without_a_reroll_before_it_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.frozen_round(tmp_path, n=1)
    store = h.store(tmp_path)
    path = store.provenance_file(specs[0].event_id)
    prov = store.read(path, ClipProvenance)
    # An attempt 2 with no reroll verdict on attempt 1: only an edited file makes this.
    second = prov.attempts[0].updated(k=2, seed=attempt_seed(specs[0].event_id, 2))
    store.replace_json(path, prov.updated(attempts=(prov.attempts[0], second)))
    assert _check(tmp_path) == cli.EXIT_ASK
    assert "attempt 1 has no reroll verdict" in capsys.readouterr().err


def test_no_fact_term_is_a_camera_move() -> None:
    clashes = [
        (term, phrase)
        for terms in h.TAX.terms.values()
        for term in terms
        for phrase in clip_rules.camera_moves()
        if rules.contains_phrase(term, phrase)
    ]
    assert clashes == []


def test_the_index_row_names_the_source(tmp_path: Path) -> None:
    specs = h.frozen_round(tmp_path, n=1)
    row = h.store(tmp_path).latest_clip_index()[specs[0].event_id]
    assert (row.source, row.status) == (specs[0].source.event_id, "prompted")
