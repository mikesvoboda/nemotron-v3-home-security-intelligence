"""`check --batch <b>` (agent-driven design §3 step 3, §3.1): validate, freeze, verify."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from synthbench import cli
from synthbench.contract.provenance import Provenance, attempt_seed, render_name
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
    assert "4 frozen now" in capsys.readouterr().out


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
