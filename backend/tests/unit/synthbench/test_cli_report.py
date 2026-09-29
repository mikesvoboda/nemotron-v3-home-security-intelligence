"""`report --batch <b>` (agent-driven design §3 step 8)."""

from __future__ import annotations

import json
from pathlib import Path

from synthbench import cli
from synthbench.commands import report
from synthbench.contract.corpus import BatchRecord
from synthbench.contract.provenance import Provenance
from synthbench.status import SnapshotHold, SnapshotStatus, snapshots_file, write_status

from backend.tests.unit.synthbench import helpers as h


def _report(root: Path) -> str:
    assert h.run(root, "report", "--batch", "pilot-1") == cli.EXIT_OK
    return (h.store(root).batch_dir("pilot-1") / "report.md").read_text(encoding="utf-8")


def _verdicts(root: Path, rows: list[dict[str, object]]) -> None:
    path = h.store(root).batch_dir("pilot-1") / "triage.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_the_report_counts_states_reasons_and_timing(tmp_path: Path) -> None:
    specs = h.stilled_batch(tmp_path, n=10)  # one triage reroll allowed
    rows: list[dict[str, object]] = [
        {"event_id": specs[0].event_id, "k": 1, "verdict": "reroll", "reason": "blank"},
        {"event_id": specs[1].event_id, "k": 1, "verdict": "reroll", "reason": "no_person"},
    ]
    rows += [{"event_id": s.event_id, "k": 1, "verdict": "ok"} for s in specs[2:9]]
    _verdicts(tmp_path, rows)
    assert h.run(tmp_path, "triage", "--batch", "pilot-1") == cli.EXIT_ASK  # specs[1]: over the cap
    text = _report(tmp_path)
    assert "| ready | 7 |" in text
    assert "| awaiting render | 1 |" in text  # specs[0], attempt 2
    assert "| failed | 1 |" in text  # specs[1]
    assert "| awaiting verdict | 1 |" in text  # specs[9]
    assert "| blank | 1 |" in text
    assert "| no_person | 1 |" in text
    assert "10 image(s) rendered: median 8.0 s" in text
    assert "No snapshot status yet" in text
    assert f"| {specs[1].event_id} | {specs[1].cell.scenario} | no_person |" in text


def test_p90_uses_nearest_rank_not_a_floor_index(tmp_path: Path) -> None:
    """Nearest-rank p90 (ceil(0.9 * n)-th smallest) of [5.0, 5.0, 8.3] is 8.3, not the floor
    index's 5.0."""
    specs = h.frozen_batch(tmp_path, n=3)
    store = h.store(tmp_path)
    for spec, seconds in zip(specs, [5.0, 5.0, 8.3], strict=True):
        path = store.provenance_file(spec.event_id)
        prov = store.read(path, Provenance)
        attempt = prov.attempts[-1]
        store.replace_json(path, prov.updated(attempts=(attempt.updated(render_seconds=seconds),)))
    text = _report(tmp_path)
    assert "3 image(s) rendered: median 5.0 s, p90 8.3 s" in text


def test_the_sheet_links_each_still(tmp_path: Path) -> None:
    specs = h.stilled_batch(tmp_path, n=2)
    _report(tmp_path)
    html = (h.store(tmp_path).batch_dir("pilot-1") / "sheet.html").read_text(encoding="utf-8")
    store = h.store(tmp_path)
    for spec in specs:
        still = store.read(store.provenance_file(spec.event_id), Provenance).attempts[-1].still
        assert still is not None
        assert f'src="../../events/B/{spec.event_id}/{still.path}"' in html


def test_the_sheet_escapes_prompts(tmp_path: Path) -> None:
    (spec,) = h.frozen_batch(tmp_path, n=1)
    store = h.store(tmp_path)
    record = store.read(store.batch_file("pilot-1"), BatchRecord)
    odd = spec.updated(prompt="a man & a <b>dog</b>")
    html = report.sheet(record, [report.Event(odd, None, "not prompted")])
    assert "a man &amp; a &lt;b&gt;dog&lt;/b&gt;" in html
    assert "<b>dog</b>" not in html


def test_the_report_shows_a_snapshot_hold_and_can_be_rewritten(tmp_path: Path) -> None:
    h.stilled_batch(tmp_path, n=1)
    name = "primary/export/synthbench/corpus@synthbench-20260928T000000Z"
    hold = SnapshotHold(snapshot=name, count=2, paths=("/synthbench/corpus/x.png",))
    write_status(
        snapshots_file(h.env(tmp_path)), SnapshotStatus(time=h.NOW, snapshots=6, hold=hold)
    )
    assert f"**Held:** `{name}`" in _report(tmp_path)
    assert "**Held:**" in _report(tmp_path)  # a second run replaces the views
