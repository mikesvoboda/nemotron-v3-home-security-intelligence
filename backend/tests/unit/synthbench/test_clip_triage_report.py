"""`clip triage` (clips design §3.3) and `clip report` (§3.4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from synthbench import cli
from synthbench.contract.clip import ClipProvenance, ClipSpec, SwitchRow
from synthbench.contract.provenance import attempt_seed

from backend.tests.unit.synthbench import helpers as h

PILOT = "clips-pilot-1"


def _triage(root: Path) -> int:
    return h.run(root, "clip", "triage", "--round", PILOT)


def _row(spec: ClipSpec, k: int = 1, reason: str | None = None) -> dict[str, Any]:
    if reason is None:
        return {"event_id": spec.event_id, "k": k, "verdict": "ok"}
    return {"event_id": spec.event_id, "k": k, "verdict": "reroll", "reason": reason}


def _prov(root: Path, spec: ClipSpec) -> ClipProvenance:
    store = h.store(root)
    return store.read(store.provenance_file(spec.event_id), ClipProvenance)


def _status(root: Path, spec: ClipSpec) -> str:
    return h.store(root).latest_clip_index()[spec.event_id].status


def test_ok_makes_a_clip_ready(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    specs = h.rendered_round(tmp_path, n=2)
    h.write_clip_triage(tmp_path, PILOT, [_row(spec) for spec in specs])
    assert _triage(tmp_path) == cli.EXIT_OK
    assert {_status(tmp_path, spec) for spec in specs} == {"ready"}
    assert "2 ready" in capsys.readouterr().out


def test_a_reroll_schedules_the_next_seed(tmp_path: Path) -> None:
    (spec,) = h.rendered_round(tmp_path, n=1)
    h.write_clip_triage(tmp_path, PILOT, [_row(spec, reason="morphing")])
    assert _triage(tmp_path) == cli.EXIT_OK
    first, second = _prov(tmp_path, spec).attempts
    assert first.triage is not None and first.triage.reason == "morphing"
    assert (second.k, second.seed) == (2, attempt_seed(spec.event_id, 2))
    assert second.prompt_sha256 == first.prompt_sha256
    assert _status(tmp_path, spec) == "rerolled"


def test_a_reroll_on_the_third_seed_fails_the_clip(tmp_path: Path) -> None:
    (spec,) = h.rendered_round(tmp_path, n=1)
    rows: list[dict[str, Any]] = []
    for k in (1, 2, 3):
        if k > 1:
            h.record_clip(tmp_path, spec)  # attempt k's clip, as clip render would store it
        rows.append(_row(spec, k=k, reason="camera_moved"))
        h.write_clip_triage(tmp_path, PILOT, rows)
        assert _triage(tmp_path) == cli.EXIT_OK
    assert len(_prov(tmp_path, spec).attempts) == 3
    assert _status(tmp_path, spec) == "failed"


def test_a_still_reason_is_not_a_clip_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (spec,) = h.rendered_round(tmp_path, n=1)
    h.write_clip_triage(tmp_path, PILOT, [_row(spec, reason="blank")])
    assert _triage(tmp_path) == cli.EXIT_ERROR
    assert "not a triage row" in capsys.readouterr().err


def test_a_verdict_before_the_clip_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (spec,) = h.frozen_round(tmp_path, n=1)
    h.write_clip_triage(tmp_path, PILOT, [_row(spec)])
    assert _triage(tmp_path) == cli.EXIT_ERROR
    assert "has no clip yet" in capsys.readouterr().err


def test_a_verdict_is_final(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (spec,) = h.ready_round(tmp_path, n=1)
    h.write_clip_triage(tmp_path, PILOT, [_row(spec, reason="morphing")])
    assert _triage(tmp_path) == cli.EXIT_ERROR
    assert "a verdict is final" in capsys.readouterr().err


def test_the_report_counts_states_switches_and_links_the_media(tmp_path: Path) -> None:
    specs = h.rendered_round(tmp_path, n=3)
    h.write_clip_triage(tmp_path, PILOT, [_row(specs[0]), _row(specs[1], reason="scene_cut")])
    assert _triage(tmp_path) == cli.EXIT_OK
    store = h.store(tmp_path)
    switch = SwitchRow(time="t", previous="flux2", free_gib=62.1, warmup_seconds=95.5)
    store.append_jsonl(store.round_dir(PILOT) / "switches.jsonl", [switch])
    assert h.run(tmp_path, "clip", "report", "--round", PILOT) == cli.EXIT_OK
    report = (store.round_dir(PILOT) / "report.md").read_text(encoding="utf-8")
    assert "| ready | 1 |" in report
    assert "| awaiting render | 1 |" in report  # the rerolled clip's attempt 2
    assert "| awaiting verdict | 1 |" in report
    assert "| scene_cut | 1 |" in report
    assert "| flux2 | 62.1 | 95.5 |" in report
    sheet = (store.round_dir(PILOT) / "sheet.html").read_text(encoding="utf-8")
    assert f'href="../../events/C/{specs[0].event_id}/clips/' in sheet
    assert f'src="../../events/C/{specs[0].event_id}/strips/' in sheet
    assert f'src="../../events/B/{specs[0].source.event_id}/stills/' in sheet
