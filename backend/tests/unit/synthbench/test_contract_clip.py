"""Clip events (clips design §2): the contract models and the store's clip paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from synthbench import cli
from synthbench.contract.clip import (
    ClipAttempt,
    ClipIndexRow,
    ClipProvenance,
    ClipSource,
    ClipSpec,
    ClipTriage,
    RoundRecord,
    clip_id,
    clip_name,
    source_facts,
    strip_name,
)
from synthbench.contract.corpus import BatchRecord
from synthbench.contract.provenance import OutputFile
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore

from backend.tests.unit.synthbench import helpers as h

SHA = "a" * 64


def _clip(spec: Spec, round_name: str = "clips-pilot-1", number: int = 0) -> ClipSpec:
    return ClipSpec.from_source(spec, round_name=round_name, number=number, k=1, render_sha256=SHA)


def _row(event_id: str = "C-r-000", status: str = "sampled") -> ClipIndexRow:
    return ClipIndexRow.model_validate(
        {
            "event_id": event_id,
            "round": "r",
            "source": "B-b-000",
            "scenario": "loitering",
            "label": "incident",
            "status": status,
            "time": "2026-09-30T00:00:00+00:00",
        }
    )


def test_a_clip_copies_its_source_still_facts(tmp_path: Path) -> None:
    spec = h.sample(tmp_path, n=1)[0]
    clip = _clip(spec)
    assert clip.event_id == "C-clips-pilot-1-000"
    assert clip.tier == "B"
    assert clip.facts() == source_facts(spec)
    assert clip.source == ClipSource(event_id=spec.event_id, k=1, render_sha256=SHA)
    assert not clip.frozen


@pytest.mark.parametrize(
    "event_id", ["C-other-000", "C-clips-pilot-1-00", "B-clips-pilot-1-000"], ids=str
)
def test_a_clip_id_is_c_round_nnn(tmp_path: Path, event_id: str) -> None:
    clip = _clip(h.sample(tmp_path, n=1)[0])
    with pytest.raises(ValidationError, match="C-<round>-NNN"):
        clip.updated(event_id=event_id)


def test_a_clip_source_is_a_tier_b_still() -> None:
    with pytest.raises(ValidationError, match="Tier B still"):
        ClipSource(event_id="C-r-000", k=1, render_sha256=SHA)


def test_the_motion_and_suffix_freeze_together_once(tmp_path: Path) -> None:
    clip = _clip(h.sample(tmp_path, n=1)[0])
    with pytest.raises(ValidationError, match="frozen together"):
        clip.updated(prompt="walks to the door")
    frozen = clip.with_prompt("walks to the door", "Fixed camera.")
    assert frozen.frozen
    with pytest.raises(ValueError, match="a new motion is a new clip event"):
        frozen.with_prompt("runs", "Fixed camera.")


def test_an_attempt_records_its_input_clip_and_strip_together() -> None:
    clip = OutputFile(path=clip_name(1, 7), sha256=SHA)
    strip = OutputFile(path=strip_name(1, 7), sha256=SHA)
    ClipAttempt(k=1, seed=7, prompt_sha256=SHA, input_sha256=SHA, clip=clip, strip=strip)
    with pytest.raises(ValidationError, match="together"):
        ClipAttempt(k=1, seed=7, prompt_sha256=SHA, clip=clip)
    with pytest.raises(ValidationError, match="triage needs a clip"):
        ClipAttempt(k=1, seed=7, prompt_sha256=SHA, triage=ClipTriage(verdict="ok"))


def test_a_clip_reroll_needs_a_clip_reason() -> None:
    with pytest.raises(ValidationError):
        ClipTriage(verdict="reroll")
    with pytest.raises(ValidationError):
        ClipTriage.model_validate({"verdict": "reroll", "reason": "blank"})  # a still reason
    assert ClipTriage(verdict="reroll", reason="morphing").reason == "morphing"


def test_clip_attempts_are_numbered_and_capped_at_three() -> None:
    attempts = [ClipAttempt(k=k, seed=k, prompt_sha256=SHA) for k in (1, 2, 3, 4)]
    ClipProvenance(event_id="C-r-000", attempts=tuple(attempts[:3]))
    with pytest.raises(ValidationError, match="at most 3"):
        ClipProvenance(event_id="C-r-000", attempts=tuple(attempts))
    with pytest.raises(ValidationError, match=r"1\.\.n in order"):
        ClipProvenance(event_id="C-r-000", attempts=(attempts[1],))


def _round(n: int = 2, **changes: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "name": "r",
        "version": "tierb-v0",
        "seed": 1,
        "n": n,
        "settings": {
            "frames": 243,
            "fps": 24,
            "size": [1344, 768],
            "weights": SHA,
            "clip_suffix_sha256": SHA,
        },
        "allocation": {"threat": {"day": n}},
        "event_ids": [clip_id("r", i) for i in range(n)],
        "source_event_ids": [f"B-b-{i:03d}" for i in range(n)],
        "created": "2026-09-30T00:00:00+00:00",
    }
    return document | changes


def test_a_round_lists_its_clips_in_order_one_distinct_source_each() -> None:
    assert RoundRecord.model_validate(_round()).event_ids == ("C-r-000", "C-r-001")
    with pytest.raises(ValidationError, match="in order"):
        RoundRecord.model_validate(_round(event_ids=["C-r-001", "C-r-000"]))
    with pytest.raises(ValidationError, match="distinct source"):
        RoundRecord.model_validate(_round(source_event_ids=["B-b-000", "B-b-000"]))
    with pytest.raises(ValidationError, match="add up to n"):
        RoundRecord.model_validate(_round(allocation={"threat": {"day": 1}}))


def test_clip_events_and_rounds_have_their_own_paths(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    assert store.event_dir("C-r-000") == tmp_path / "tierb-v0" / "events" / "C" / "C-r-000"
    assert store.round_file("r") == tmp_path / "tierb-v0" / "rounds" / "r" / "round.json"
    with pytest.raises(ValueError, match="round name"):
        store.round_dir("../x")


def test_the_clip_index_is_its_own_log(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    store.append_clip_index([_row(), _row(status="prompted")])
    assert store.latest_clip_index() == {"C-r-000": _row(status="prompted")}
    assert store.latest_index() == {}
    assert not store.index_file.exists()


def test_append_jsonl_appends_only_logs_inside_the_version(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path, "tierb-v0")
    with pytest.raises(ValueError, match=r"\.jsonl"):
        store.append_jsonl(store.round_dir("r") / "round.json", [_row()])
    with pytest.raises(ValueError, match="outside"):
        store.append_jsonl(tmp_path / "elsewhere.jsonl", [_row()])


def test_the_still_commands_do_not_see_clip_events(tmp_path: Path) -> None:
    specs = h.ready_batch(tmp_path, n=4)
    store = h.store(tmp_path)
    clip = _clip(specs[0], round_name="r")
    store.write_new(store.spec_file(clip.event_id), clip)
    store.append_clip_index([_row(clip.event_id)])
    assert set(store.latest_index()) == {spec.event_id for spec in specs}
    assert h.run(tmp_path, "export", "vss") == cli.EXIT_OK
    assert not [p for p in (tmp_path / "exports").rglob("*") if "C-r-" in p.name]
    assert h.run(tmp_path, "sample", "--batch", "next", "--n", "2") == cli.EXIT_OK
    record = store.read(store.batch_file("next"), BatchRecord)
    assert sum(record.prior_counts.values()) == len(specs)
