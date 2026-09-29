"""`triage --batch <b>` (agent-driven design §3 step 7, §4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from synthbench import cli
from synthbench.commands.triage import reroll_allowance
from synthbench.contract.provenance import Provenance, attempt_seed
from synthbench.contract.spec import Spec

from backend.tests.unit.synthbench import helpers as h


def _verdicts(root: Path, rows: list[dict[str, Any]]) -> None:
    path = h.store(root).batch_dir("pilot-1") / "triage.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _ok(spec: Spec, k: int = 1) -> dict[str, Any]:
    return {"event_id": spec.event_id, "k": k, "verdict": "ok"}


def _reroll(spec: Spec, reason: str, k: int = 1) -> dict[str, Any]:
    return {"event_id": spec.event_id, "k": k, "verdict": "reroll", "reason": reason}


def _triage(root: Path) -> int:
    return h.run(root, "triage", "--batch", "pilot-1")


def _prov(root: Path, spec: Spec) -> Provenance:
    store = h.store(root)
    return store.read(store.provenance_file(spec.event_id), Provenance)


def _status(root: Path, spec: Spec) -> str:
    return h.store(root).latest_index()[spec.event_id].status


def test_the_allowance_is_a_tenth_of_the_batch_rounded_down() -> None:
    assert [reroll_allowance(n) for n in (5, 9, 10, 19, 50, 500)] == [0, 0, 1, 1, 5, 50]


def test_ok_verdicts_make_events_ready(tmp_path: Path) -> None:
    specs = h.stilled_batch(tmp_path, n=2)
    _verdicts(tmp_path, [_ok(spec) for spec in specs])
    assert _triage(tmp_path) == cli.EXIT_OK
    for spec in specs:
        (attempt,) = _prov(tmp_path, spec).attempts
        assert attempt.triage is not None
        assert attempt.triage.verdict == "ok"
        assert _status(tmp_path, spec) == "ready"


def test_a_reroll_schedules_attempt_2_with_its_own_seed(tmp_path: Path) -> None:
    specs = h.stilled_batch(tmp_path, n=10)
    _verdicts(tmp_path, [_reroll(specs[0], "blank"), *(_ok(s) for s in specs[1:])])
    assert _triage(tmp_path) == cli.EXIT_OK
    first, second = _prov(tmp_path, specs[0]).attempts
    assert first.triage is not None
    assert first.triage.reason == "blank"
    assert (second.k, second.seed) == (2, attempt_seed(specs[0].event_id, 2))
    assert second.prompt_sha256 == first.prompt_sha256
    assert second.render is None
    assert _status(tmp_path, specs[0]) == "rerolled"


def test_a_second_triage_failure_fails_the_event(tmp_path: Path) -> None:
    specs = h.stilled_batch(tmp_path, n=10)
    rows = [_reroll(specs[0], "blank")]
    _verdicts(tmp_path, rows)
    assert _triage(tmp_path) == cli.EXIT_OK
    h.record_output(tmp_path, specs[0], render=b"png 2", still=b"jpeg 2")
    _verdicts(tmp_path, [*rows, _reroll(specs[0], "broken_anatomy", k=2)])
    assert _triage(tmp_path) == cli.EXIT_OK
    assert len(_prov(tmp_path, specs[0]).attempts) == 2
    assert _status(tmp_path, specs[0]) == "failed"


def test_rerolls_past_the_cap_fail_their_events_and_stop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.stilled_batch(tmp_path, n=10)  # one triage reroll allowed
    _verdicts(tmp_path, [_reroll(spec, "no_person") for spec in specs[:3]])
    assert _triage(tmp_path) == cli.EXIT_ASK
    err = capsys.readouterr().err
    assert "exceed 10%" in err
    assert specs[1].event_id in err
    assert specs[2].event_id in err
    assert len(_prov(tmp_path, specs[0]).attempts) == 2
    for spec in specs[1:3]:
        assert len(_prov(tmp_path, spec).attempts) == 1
        assert _status(tmp_path, spec) == "failed"


def test_verdicts_are_final(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    specs = h.stilled_batch(tmp_path, n=2)
    _verdicts(tmp_path, [_ok(specs[0])])
    assert _triage(tmp_path) == cli.EXIT_OK
    _verdicts(tmp_path, [_reroll(specs[0], "blank")])
    assert _triage(tmp_path) == cli.EXIT_ERROR
    assert "a verdict is final" in capsys.readouterr().err


def test_a_verdict_needs_a_still(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (spec,) = h.rendered_batch(tmp_path, n=1)
    _verdicts(tmp_path, [_ok(spec)])
    assert _triage(tmp_path) == cli.EXIT_ERROR
    assert "has no still yet" in capsys.readouterr().err


def test_bad_lines_are_the_agents_to_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.stilled_batch(tmp_path, n=2)
    path = h.store(tmp_path).batch_dir("pilot-1") / "triage.jsonl"
    lines = [
        json.dumps(_reroll(specs[0], "cannot_see_the_knife")),
        json.dumps({"event_id": "B-other-000", "k": 1, "verdict": "ok"}),
        json.dumps(_ok(specs[1])),
        json.dumps(_reroll(specs[1], "blank")),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert _triage(tmp_path) == cli.EXIT_ERROR
    err = capsys.readouterr().err
    assert "line 1: not a triage row" in err
    assert "line 2: B-other-000 is not in batch pilot-1" in err
    assert f"line 4: a second row for {specs[1].event_id} attempt 1" in err
    assert _prov(tmp_path, specs[1]).attempts[0].triage is None  # nothing recorded


def test_a_verdict_on_a_missing_attempt_records_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.stilled_batch(tmp_path, n=2)
    _verdicts(tmp_path, [_ok(specs[0]), _ok(specs[1], k=3)])
    assert _triage(tmp_path) == cli.EXIT_ERROR
    assert f"{specs[1].event_id}: attempt 3 does not exist" in capsys.readouterr().err
    assert _prov(tmp_path, specs[0]).attempts[0].triage is None  # all or nothing


def test_the_summary_counts_stills_awaiting_verdicts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.stilled_batch(tmp_path, n=3)
    _verdicts(tmp_path, [_ok(specs[0])])
    assert _triage(tmp_path) == cli.EXIT_OK
    assert "2 still(s) await a verdict" in capsys.readouterr().out
