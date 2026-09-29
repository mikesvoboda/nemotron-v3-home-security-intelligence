"""`report --batch <b>`: report.md and sheet.html for the owner (design §3 step 8).

report.md has counts by state, rerolls by reason, failed events, render timing and snapshot
holds. sheet.html is a contact sheet of every event's current still, opened from the corpus on
the host. Both are views: every run replaces them.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path

from pydantic import ValidationError

from synthbench.commands.common import (
    EXIT_OK,
    Parser,
    batch_name,
    now_iso,
    open_batch,
    read,
    read_index,
    replace_text,
    taxonomy,
)
from synthbench.contract.corpus import BatchRecord
from synthbench.contract.provenance import Provenance
from synthbench.contract.spec import Spec
from synthbench.status import SnapshotStatus, read_status, snapshots_file

STATES = (
    "not prompted",
    "awaiting render",
    "awaiting still",
    "awaiting verdict",
    "ready",
    "failed",
)


def event_state(spec: Spec, prov: Provenance | None, status: str | None) -> str:
    if not spec.frozen or prov is None:
        return "not prompted"
    if status == "failed":
        return "failed"
    last = prov.attempts[-1]
    if last.render is None:
        return "awaiting render"
    if last.still is None:
        return "awaiting still"
    if last.triage is None:
        return "awaiting verdict"
    return "ready" if last.triage.verdict == "ok" else "failed"


@dataclass(frozen=True)
class Event:
    spec: Spec
    prov: Provenance | None
    state: str


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "report", help="write the batch's report.md and sheet.html", allow_abbrev=False
    )
    parser.add_argument("--batch", type=batch_name, required=True, help="batch name")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_batch(tax, env, args.batch)
    index = read_index(store)
    events: list[Event] = []
    for event_id in record.event_ids:
        spec = read(store, store.spec_file(event_id), Spec)
        path = store.provenance_file(event_id)
        prov = read(store, path, Provenance) if path.exists() else None
        row = index.get(event_id)
        events.append(Event(spec, prov, event_state(spec, prov, row.status if row else None)))
    folder = store.batch_dir(record.name)
    replace_text(
        store,
        folder / "report.md",
        markdown(record, events, _snapshot_note(snapshots_file(env)), now_iso()),
    )
    replace_text(store, folder / "sheet.html", sheet(record, events))
    states = Counter(event.state for event in events)
    summary = ", ".join(f"{state} {states[state]}" for state in STATES if states[state])
    sys.stdout.write(
        f"report {record.name}: {summary}\n  {folder / 'report.md'}\n  {folder / 'sheet.html'}\n"
    )
    return EXIT_OK


def _snapshot_note(path: Path) -> str:
    if not path.exists():
        return "No snapshot status yet: the snapshot timer has not run."
    try:
        status = read_status(path, SnapshotStatus)
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        return f"Cannot read {path} ({type(error).__name__})."
    if status.hold is None:
        return f"None. {status.snapshots} snapshot(s) kept as of {status.time:%Y-%m-%d %H:%M} UTC."
    hold = status.hold
    paths = "\n".join(f"- `{p}`" for p in hold.paths)
    return (
        f"**Held:** `{hold.snapshot}` holds the only copy of {hold.count} removed or changed "
        f"file(s); the owner resolves it (operator runbook). First paths:\n\n{paths}"
    )


def _still_link(spec: Spec, prov: Provenance | None) -> str | None:
    """A still's path relative to batches/<b>/, where the views live."""
    still = prov.attempts[-1].still if prov else None
    if still is None:
        return None
    return f"../../events/{spec.event_id[0]}/{spec.event_id}/{still.path}"


def markdown(record: BatchRecord, events: Sequence[Event], snapshots: str, generated: str) -> str:
    states = Counter(event.state for event in events)
    attempts = [a for event in events if event.prov for a in event.prov.attempts]
    reasons = Counter(a.triage.reason for a in attempts if a.triage and a.triage.reason)
    failed = [event for event in events if event.state == "failed"]
    seconds = sorted(a.render_seconds for a in attempts if a.render_seconds is not None)
    job_failures = [
        (event.spec.event_id, failure)
        for event in events
        if event.prov
        for a in event.prov.attempts
        for failure in a.render_failures
    ]
    only = f", only {', '.join(record.only)}" if record.only else ""
    lines = [
        f"# Batch {record.name} (corpus {record.version})",
        "",
        f"Generated {generated} by `python -m synthbench report`: {record.n} events, sampler "
        f"seed {record.seed}{only}.",
        "",
        "## Progress",
        "",
        "| State | Events |",
        "| --- | ---: |",
        *(f"| {state} | {states[state]} |" for state in STATES),
        "",
        "## Rerolls by reason",
        "",
    ]
    if reasons:
        lines += ["| Reason | Verdicts |", "| --- | ---: |"]
        lines += [f"| {reason} | {count} |" for reason, count in sorted(reasons.items())]
    else:
        lines.append("None.")
    lines += ["", "## Failed events", ""]
    if failed:
        lines += ["| Event | Scenario | Reroll reasons |", "| --- | --- | --- |"]
        for event in failed:
            assert event.prov is not None
            why = ", ".join(
                a.triage.reason for a in event.prov.attempts if a.triage and a.triage.reason
            )
            lines.append(f"| {event.spec.event_id} | {event.spec.cell.scenario} | {why} |")
        by_scenario = Counter(event.spec.cell.scenario for event in failed)
        lines += [
            "",
            "Failed by scenario: "
            + ", ".join(f"{s} {c}" for s, c in sorted(by_scenario.items()))
            + ".",
        ]
    else:
        lines.append("None.")
    lines += ["", "## Render timing", ""]
    if seconds:
        p90 = seconds[int(0.9 * (len(seconds) - 1))]
        lines.append(
            f"{len(seconds)} image(s) rendered: median {statistics.median(seconds):.1f} s, "
            f"p90 {p90:.1f} s, total {sum(seconds) / 60:.1f} min."
        )
    else:
        lines.append("No image rendered yet.")
    lines.append(f"Failed render jobs: {len(job_failures)}.")
    lines += [f"- {event_id}: {failure.error}" for event_id, failure in job_failures[:20]]
    lines += ["", "## Snapshot holds", "", snapshots, "", "## Events", ""]
    lines += [
        "| Event | Scenario | Label | Lighting | Weather | Attempt | State | Still |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for event in events:
        spec = event.spec
        k = event.prov.attempts[-1].k if event.prov else 0
        link = _still_link(spec, event.prov)
        still = f"[still]({link})" if link else "-"
        lines.append(
            f"| {spec.event_id} | {spec.cell.scenario} | {spec.label} | {spec.cell.lighting} | "
            f"{spec.cell.weather} | {k} | {event.state} | {still} |"
        )
    return "\n".join(lines) + "\n"


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font: 14px system-ui, sans-serif; margin: 16px; background: #111; color: #ddd; }}
main {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(480px, 1fr)); gap: 12px; }}
figure {{ margin: 0; background: #1c1c1c; padding: 8px; border-left: 4px solid #555; }}
figure.ready {{ border-color: #3a3; }}
figure.failed {{ border-color: #c33; }}
figure.awaiting-verdict {{ border-color: #ca3; }}
img {{ width: 100%; height: auto; }}
.none {{ padding: 40px; text-align: center; color: #777; }}
</style></head><body><h1>{title}</h1><main>
{cards}
</main></body></html>
"""


def sheet(record: BatchRecord, events: Sequence[Event]) -> str:
    cards: list[str] = []
    for event in events:
        spec = event.spec
        last = event.prov.attempts[-1] if event.prov else None
        link = _still_link(spec, event.prov)
        image = (
            f'<img src="{escape(link)}" loading="lazy" alt="{escape(spec.event_id)}">'
            if link
            else '<div class="none">no still yet</div>'
        )
        verdict = "no verdict"
        if last is not None and last.triage is not None:
            verdict = last.triage.verdict + (
                f" ({last.triage.reason})" if last.triage.reason else ""
            )
        caption = (
            f"<b>{escape(spec.event_id)}</b> {escape(spec.cell.scenario)} - {escape(spec.label)} - "
            f"{escape(spec.cell.lighting)}, {escape(spec.cell.weather)} - attempt "
            f"{last.k if last else 0} - {escape(event.state)} - {escape(verdict)}"
            f"<br>{escape(spec.prompt or '')}"
        )
        css = escape(event.state.replace(" ", "-"))
        cards.append(f'<figure class="{css}">{image}<figcaption>{caption}</figcaption></figure>')
    title = escape(f"Batch {record.name} ({record.version})")
    return _HTML.format(title=title, cards="\n".join(cards))
