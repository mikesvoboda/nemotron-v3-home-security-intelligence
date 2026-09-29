"""`check --batch <b>` (agent-driven design §3 step 3, §3.1): validate, freeze, verify."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from synthbench import cli
from synthbench.contract.provenance import (
    Attempt,
    Provenance,
    Triage,
    attempt_seed,
    render_name,
)
from synthbench.contract.spec import Spec
from synthbench.prompt import rules

from backend.tests.unit.synthbench import helpers as h


def _check(root: Path) -> int:
    return h.run(root, "check", "--batch", "pilot-1")


def test_check_freezes_passing_prompts_and_opens_provenance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.frozen_batch(tmp_path, n=4)
    store = h.store(tmp_path)
    for spec in specs:
        assert spec.prompt == h.good_prompt(spec)
        assert spec.camera_suffix == rules.CAMERA_SUFFIX
        (attempt,) = store.read(store.provenance_file(spec.event_id), Provenance).attempts
        assert (attempt.k, attempt.seed) == (1, attempt_seed(spec.event_id, 1))
        assert attempt.prompt_sha256 == rules.prompt_sha256(spec)
    assert {row.status for row in store.latest_index().values()} == {"prompted"}
    out = capsys.readouterr().out
    assert "4 frozen now" in out
    assert "Next: render --batch pilot-1" in out


def test_one_failing_prompt_freezes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.sample(tmp_path, n=3)
    prompts = {spec.event_id: h.good_prompt(spec) for spec in specs}
    prompts[specs[1].event_id] += " There is blood on the step."
    h.write_prompts(tmp_path, "pilot-1", prompts)
    assert _check(tmp_path) == cli.EXIT_ERROR
    assert f"{specs[1].event_id}: rule 2: remove 'blood'" in capsys.readouterr().err
    store = h.store(tmp_path)
    assert not any(store.read(store.spec_file(s.event_id), Spec).frozen for s in specs)
    assert not any(store.provenance_file(s.event_id).exists() for s in specs)


def test_bad_lines_and_missing_rows_are_the_agents_to_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.sample(tmp_path, n=3)
    path = h.store(tmp_path).batch_dir("pilot-1") / "prompts.jsonl"
    first = json.dumps({"event_id": specs[0].event_id, "prompt": h.good_prompt(specs[0])})
    other = json.dumps({"event_id": "B-other-000", "prompt": "a man"})
    path.write_text(f"{first}\nnot json\n{other}\n{first}\n", encoding="utf-8")
    assert _check(tmp_path) == cli.EXIT_ERROR
    err = capsys.readouterr().err
    assert "line 2: not a prompt row" in err
    assert "line 3: B-other-000 is not in batch pilot-1" in err
    assert f"line 4: a second row for {specs[0].event_id}" in err
    h.write_prompts(tmp_path, "pilot-1", {specs[0].event_id: h.good_prompt(specs[0])})
    assert _check(tmp_path) == cli.EXIT_ERROR
    assert f"{specs[1].event_id}: no row in prompts.jsonl" in capsys.readouterr().err


def test_a_rerun_freezes_nothing_new_and_a_frozen_prompt_never_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.frozen_batch(tmp_path, n=2)
    capsys.readouterr()
    assert _check(tmp_path) == cli.EXIT_OK
    assert "0 frozen now" in capsys.readouterr().out
    lines = h.store(tmp_path).index_file.read_text(encoding="utf-8").splitlines()
    assert sum('"prompted"' in line for line in lines) == 2
    h.write_prompts(tmp_path, "pilot-1", {s.event_id: f"{h.good_prompt(s)} Later." for s in specs})
    assert _check(tmp_path) == cli.EXIT_ERROR
    assert "the frozen prompt never changes" in capsys.readouterr().err


def test_a_hand_edited_fact_stops_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    specs = h.frozen_batch(tmp_path, n=2)
    path = h.store(tmp_path).spec_file(specs[0].event_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["scene_time"] = "03:33" if data["scene_time"] != "03:33" else "04:44"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert _check(tmp_path) == cli.EXIT_ASK
    assert "facts differ from the sampler's" in capsys.readouterr().err


def test_a_changed_suffix_stops_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    path = h.store(tmp_path).spec_file(spec.event_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["camera_suffix"] = "A different camera look."
    path.write_text(json.dumps(data), encoding="utf-8")
    assert _check(tmp_path) == cli.EXIT_ASK
    assert "camera_suffix differs" in capsys.readouterr().err


@pytest.mark.parametrize("damage", ["modified", "missing"])
def test_a_changed_or_missing_image_stops_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damage: str
) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    h.record_output(tmp_path, spec, render=b"\x89PNG original")
    store = h.store(tmp_path)
    seed = attempt_seed(spec.event_id, 1)
    image = store.event_dir(spec.event_id) / render_name(1, seed)
    if damage == "modified":
        image.write_bytes(b"\x89PNG edited")
    else:
        image.unlink()
    assert _check(tmp_path) == cli.EXIT_ASK
    expected = "was modified" if damage == "modified" else "is missing"
    assert f"{render_name(1, seed)} {expected}" in capsys.readouterr().err


def test_an_unexpected_file_stops_check_but_store_temps_do_not(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    renders = h.store(tmp_path).event_dir(spec.event_id) / "renders"
    renders.mkdir()
    (renders / ".a1-s1.png.x1y2.tmp").write_bytes(b"left by a crash")
    assert _check(tmp_path) == cli.EXIT_OK
    (renders / "extra.png").write_bytes(b"?")
    assert _check(tmp_path) == cli.EXIT_ASK
    assert "unexpected file renders/extra.png" in capsys.readouterr().err


def test_check_finishes_a_freeze_that_stopped_before_provenance(tmp_path: Path) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    store = h.store(tmp_path)
    store.provenance_file(spec.event_id).unlink()
    assert _check(tmp_path) == cli.EXIT_OK
    (attempt,) = store.read(store.provenance_file(spec.event_id), Provenance).attempts
    assert attempt.seed == attempt_seed(spec.event_id, 1)


def test_check_needs_a_sampled_batch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert h.run(tmp_path, "check", "--batch", "nope") == cli.EXIT_ERROR
    assert "run sample first" in capsys.readouterr().err


def test_check_names_render_next_only_while_a_render_is_awaited(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.frozen_batch(tmp_path, n=2)
    h.record_output(tmp_path, specs[0], render=b"\x89PNG one")
    capsys.readouterr()
    assert _check(tmp_path) == cli.EXIT_OK
    assert "Next: render --batch pilot-1" in capsys.readouterr().out  # specs[1] awaits one
    store = h.store(tmp_path)  # render failed specs[1] three times: nothing awaits a render
    row = store.latest_index()[specs[1].event_id].updated(status="failed", time="2026-09-28")
    store.append_index([row])
    assert _check(tmp_path) == cli.EXIT_OK
    assert "Next:" not in capsys.readouterr().out


# The triage limits (design §4, P3-R11). triage enforces them, but the agent's clone could be
# edited, so the owner's host check re-validates them from provenance and triage.jsonl.


def _verdicts(root: Path, rows: list[dict[str, object]]) -> None:
    path = h.store(root).batch_dir("pilot-1") / "triage.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _edit_attempts(root: Path, spec: Spec, *, triage: Triage | None, next_attempt: bool) -> None:
    """By hand, as an edited clone could: record a still, set its verdict, open attempt k + 1."""
    h.record_output(root, spec, render=b"\x89PNG " + spec.event_id.encode(), still=b"jpeg")
    store = h.store(root)
    path = store.provenance_file(spec.event_id)
    prov = store.read(path, Provenance)
    last = prov.attempts[-1].updated(triage=triage)
    attempts = [*prov.attempts[:-1], last]
    if next_attempt:
        k = last.k + 1
        seed = attempt_seed(spec.event_id, k)
        attempts.append(Attempt(k=k, seed=seed, prompt_sha256=last.prompt_sha256))
    store.replace_json(path, prov.updated(attempts=tuple(attempts)))


BLANK = Triage(verdict="reroll", reason="blank")


def _ask(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    capsys.readouterr()
    assert _check(root) == cli.EXIT_ASK
    return capsys.readouterr().err


def test_a_legitimate_reroll_within_the_cap_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.stilled_batch(tmp_path, n=10)  # one triage reroll allowed
    rows: list[dict[str, object]] = [
        {"event_id": specs[0].event_id, "k": 1, "verdict": "reroll", "reason": "blank"}
    ]
    rows += [{"event_id": s.event_id, "k": 1, "verdict": "ok"} for s in specs[1:]]
    _verdicts(tmp_path, rows)
    assert h.run(tmp_path, "triage", "--batch", "pilot-1") == cli.EXIT_OK
    h.record_output(tmp_path, specs[0], render=b"\x89PNG second", still=b"jpeg second")
    _verdicts(tmp_path, [*rows, {"event_id": specs[0].event_id, "k": 2, "verdict": "ok"}])
    assert h.run(tmp_path, "triage", "--batch", "pilot-1") == cli.EXIT_OK
    capsys.readouterr()
    assert _check(tmp_path) == cli.EXIT_OK
    assert "22 recorded output file(s) verified" in capsys.readouterr().out


@pytest.mark.parametrize("verdict", [None, Triage(verdict="ok")])
def test_an_attempt_without_a_reroll_verdict_before_it_stops_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], verdict: Triage | None
) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    _edit_attempts(tmp_path, spec, triage=verdict, next_attempt=True)
    if verdict is not None:
        _verdicts(tmp_path, [{"event_id": spec.event_id, "k": 1, "verdict": "ok"}])
    err = _ask(tmp_path, capsys)
    assert f"{spec.event_id}: attempt 2 exists, but attempt 1 has no reroll verdict" in err


def test_a_second_triage_reroll_of_one_event_stops_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    _edit_attempts(tmp_path, spec, triage=BLANK, next_attempt=True)
    _edit_attempts(tmp_path, spec, triage=BLANK, next_attempt=True)
    _verdicts(
        tmp_path,
        [
            {"event_id": spec.event_id, "k": k, "verdict": "reroll", "reason": "blank"}
            for k in (1, 2)
        ],
    )
    err = _ask(tmp_path, capsys)
    assert f"{spec.event_id}: 2 triage rerolls scheduled; one is allowed per event" in err


def test_rerolls_over_the_batch_cap_stop_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)  # a 1-event batch may schedule no triage reroll
    _edit_attempts(tmp_path, spec, triage=BLANK, next_attempt=True)
    _verdicts(
        tmp_path, [{"event_id": spec.event_id, "k": 1, "verdict": "reroll", "reason": "blank"}]
    )
    err = _ask(tmp_path, capsys)
    assert f"batch pilot-1 scheduled 1 triage reroll(s), 0 allowed: {spec.event_id}" in err


@pytest.mark.parametrize("row", ["missing", "different"])
def test_a_verdict_that_is_not_its_triage_row_stops_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], row: str
) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    _edit_attempts(tmp_path, spec, triage=Triage(verdict="ok"), next_attempt=False)
    if row == "different":
        _verdicts(
            tmp_path, [{"event_id": spec.event_id, "k": 1, "verdict": "reroll", "reason": "blank"}]
        )
    err = _ask(tmp_path, capsys)
    expected = (
        "has no row in triage.jsonl" if row == "missing" else "differs from its triage.jsonl row"
    )
    assert f"{spec.event_id}: attempt 1's recorded verdict {expected}" in err
