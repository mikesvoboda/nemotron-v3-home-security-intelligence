"""`clip report --round <r>`: report.md and sheet.html for the owner (clips design §3.4).

report.md has counts by state, the draw, rerolls by reason, failed clips, render timing and
the renderer switches. sheet.html plays each clip beside its source still. Both are views:
every run replaces them.
"""

from __future__ import annotations

import argparse
import math
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
    CorpusError,
    Parser,
    now_iso,
    open_round,
    read,
    read_clip_index,
    replace_text,
    round_name,
    taxonomy,
)
from synthbench.contract.clip import ClipProvenance, ClipSpec, RoundRecord, SwitchRow
from synthbench.contract.provenance import Provenance
from synthbench.contract.store import CorpusStore

STATES = ("not prompted", "awaiting render", "awaiting verdict", "ready", "failed")


def clip_state(spec: ClipSpec, prov: ClipProvenance | None, status: str | None) -> str:
    if not spec.frozen or prov is None:
        return "not prompted"
    if status == "failed":
        return "failed"
    last = prov.attempts[-1]
    if last.clip is None:
        return "awaiting render"
    if last.triage is None:
        return "awaiting verdict"
    return "ready" if last.triage.verdict == "ok" else "failed"


def source_still(store: CorpusStore, spec: ClipSpec) -> Path | None:
    """The source still's camera still: the pinned attempt's `still`."""
    source = spec.source
    attempt = read(store, store.provenance_file(source.event_id), Provenance).attempts[source.k - 1]
    if attempt.still is None:
        return None
    return store.event_dir(source.event_id) / attempt.still.path


@dataclass(frozen=True)
class Clip:
    spec: ClipSpec
    prov: ClipProvenance | None
    state: str
    still: str | None  # the source still, relative to rounds/<r>/


def add_parser(actions: argparse._SubParsersAction[Parser]) -> None:
    parser = actions.add_parser(
        "report", help="write the round's report.md and sheet.html", allow_abbrev=False
    )
    parser.add_argument(
        "--round", dest="round_name", type=round_name, required=True, help="round name"
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_round(tax, env, args.round_name)
    index = read_clip_index(store)
    clips: list[Clip] = []
    for event_id in record.event_ids:
        spec = read(store, store.spec_file(event_id), ClipSpec)
        path = store.provenance_file(event_id)
        prov = read(store, path, ClipProvenance) if path.exists() else None
        row = index.get(event_id)
        still = source_still(store, spec)
        link = None if still is None else "../../" + str(still.relative_to(store.version_dir))
        clips.append(Clip(spec, prov, clip_state(spec, prov, row.status if row else None), link))
    folder = store.round_dir(record.name)
    switches = _switches(folder / "switches.jsonl")
    replace_text(store, folder / "report.md", markdown(record, clips, switches, now_iso()))
    replace_text(store, folder / "sheet.html", sheet(record, clips))
    states = Counter(clip.state for clip in clips)
    summary = ", ".join(f"{state} {states[state]}" for state in STATES if states[state])
    sys.stdout.write(
        f"clip report {record.name}: {summary}\n  {folder / 'report.md'}\n"
        f"  {folder / 'sheet.html'}\n"
    )
    return EXIT_OK


def _switches(path: Path) -> list[SwitchRow]:
    if not path.exists():
        return []
    try:
        return [
            SwitchRow.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise CorpusError("read", path, error) from error


def _media(clip: Clip, kind: str) -> str | None:
    """The current attempt's clip or strip, relative to rounds/<r>/."""
    last = clip.prov.attempts[-1] if clip.prov else None
    output = None if last is None else (last.clip if kind == "clip" else last.strip)
    if output is None:
        return None
    return f"../../events/C/{clip.spec.event_id}/{output.path}"


def markdown(
    record: RoundRecord, clips: Sequence[Clip], switches: Sequence[SwitchRow], generated: str
) -> str:
    states = Counter(clip.state for clip in clips)
    attempts = [a for clip in clips if clip.prov for a in clip.prov.attempts]
    reasons = Counter(a.triage.reason for a in attempts if a.triage and a.triage.reason)
    seconds = sorted(a.render_seconds for a in attempts if a.render_seconds is not None)
    failures = [
        (clip.spec.event_id, failure)
        for clip in clips
        if clip.prov
        for a in clip.prov.attempts
        for failure in a.render_failures
    ]
    jobs = [(event_id, f) for event_id, f in failures if f.kind == "job"]
    s = record.settings
    lines = [
        f"# Clip round {record.name} (corpus {record.version})",
        "",
        f"Generated {generated} by `python -m synthbench clip report`: {record.n} clips, "
        f"draw seed {record.seed}; {s.frames} frames at {s.fps} fps, "
        f"{s.size[0]}x{s.size[1]}.",
        "",
        "## Progress",
        "",
        "| State | Clips |",
        "| --- | ---: |",
        *(f"| {state} | {states[state]} |" for state in STATES),
        "",
        "## The draw",
        "",
        "| Group | Lighting | Clips |",
        "| --- | --- | ---: |",
        *(
            f"| {group} | {lighting} | {count} |"
            for group, lights in sorted(record.allocation.items())
            for lighting, count in sorted(lights.items())
        ),
        "",
        "## Rerolls by reason",
        "",
    ]
    if reasons:
        lines += ["| Reason | Verdicts |", "| --- | ---: |"]
        lines += [f"| {reason} | {count} |" for reason, count in sorted(reasons.items())]
    else:
        lines.append("None.")
    failed = [clip for clip in clips if clip.state == "failed"]
    lines += ["", "## Failed clips", ""]
    if failed:
        lines += ["| Clip | Source | Scenario | Reroll reasons |", "| --- | --- | --- | --- |"]
        for clip in failed:
            why = ", ".join(
                a.triage.reason
                for a in (clip.prov.attempts if clip.prov else ())
                if a.triage and a.triage.reason
            )
            lines.append(
                f"| {clip.spec.event_id} | {clip.spec.source.event_id} | "
                f"{clip.spec.cell.scenario} | {why} |"
            )
    else:
        lines.append("None.")
    lines += ["", "## Render timing", ""]
    if seconds:
        p90 = seconds[math.ceil(0.9 * len(seconds)) - 1]
        lines.append(
            f"{len(seconds)} clip(s) rendered: median {statistics.median(seconds):.1f} s, "
            f"p90 {p90:.1f} s, total {sum(seconds) / 60:.1f} min."
        )
    else:
        lines.append("No clip rendered yet.")
    lines.append(f"Failed render jobs: {len(jobs)}.")
    lines += [f"- {event_id}: {failure.error}" for event_id, failure in jobs[:20]]
    if unreachable := len(failures) - len(jobs):
        lines.append(f"Renderer unreachable: {unreachable} time(s).")
    lines += ["", "## Renderer switches", ""]
    if switches:
        lines += ["| Time | Previous | Free GiB | Warm-up s |", "| --- | --- | ---: | ---: |"]
        lines += [
            f"| {row.time} | {row.previous} | {row.free_gib:.1f} | {row.warmup_seconds:.1f} |"
            for row in switches
        ]
    else:
        lines.append("None.")
    lines += ["", "## Clips", ""]
    lines += [
        "| Clip | Source | Scenario | Label | Lighting | Attempt | State | Clip | Strip |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for clip in clips:
        spec = clip.spec
        k = clip.prov.attempts[-1].k if clip.prov else 0
        video, strip = _media(clip, "clip"), _media(clip, "strip")
        lines.append(
            f"| {spec.event_id} | {spec.source.event_id} | {spec.cell.scenario} | {spec.label} "
            f"| {spec.cell.lighting} | {k} | {clip.state} | "
            f"{f'[clip]({video})' if video else '-'} | {f'[strip]({strip})' if strip else '-'} |"
        )
    return "\n".join(lines) + "\n"


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font: 14px system-ui, sans-serif; margin: 16px; background: #111; color: #ddd; }}
main {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(640px, 1fr)); gap: 12px; }}
figure {{ margin: 0; background: #1c1c1c; padding: 8px; border-left: 4px solid #555; }}
figure.ready {{ border-color: #3a3; }}
figure.failed {{ border-color: #c33; }}
figure.awaiting-verdict {{ border-color: #ca3; }}
.pair {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
video, img {{ width: 100%; height: auto; }}
.none {{ padding: 40px; text-align: center; color: #777; }}
</style></head><body><h1>{title}</h1><main>
{cards}
</main></body></html>
"""


def sheet(record: RoundRecord, clips: Sequence[Clip]) -> str:
    cards: list[str] = []
    for clip in clips:
        spec = clip.spec
        last = clip.prov.attempts[-1] if clip.prov else None
        video = _media(clip, "clip")
        player = (
            f'<video src="{escape(video)}" controls loop muted preload="metadata"></video>'
            if video
            else '<div class="none">no clip yet</div>'
        )
        still = (
            f'<img src="{escape(clip.still)}" loading="lazy" alt="source still">'
            if clip.still
            else '<div class="none">no source still</div>'
        )
        verdict = "no verdict"
        if last is not None and last.triage is not None:
            verdict = last.triage.verdict + (
                f" ({last.triage.reason})" if last.triage.reason else ""
            )
        caption = (
            f"<b>{escape(spec.event_id)}</b> from {escape(spec.source.event_id)} - "
            f"{escape(spec.cell.scenario)} - {escape(spec.label)} - {escape(spec.cell.lighting)}, "
            f"{escape(spec.cell.weather)} - attempt {last.k if last else 0} - "
            f"{escape(clip.state)} - {escape(verdict)}<br>{escape(spec.prompt or '')}"
        )
        css = escape(clip.state.replace(" ", "-"))
        cards.append(
            f'<figure class="{css}"><div class="pair">{player}{still}</div>'
            f"<figcaption>{caption}</figcaption></figure>"
        )
    title = escape(f"Clip round {record.name} ({record.version})")
    return _HTML.format(title=title, cards="\n".join(cards))
