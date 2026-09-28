"""P1 contact sheet (spec §3.7): a static HTML page the owner rates.

    uv run python -m synthbench.spikes.p1_bakeoff.sheet    # writes <root>/sheet.html

One section per case (the identity reference and shots share one section, clip cases
follow), one row per model, one column per seed (per shot for identity). Each ok cell
has good / partial / fail radios named by the record's output path and a note; a failed
cell shows its error, and a cell measure.py flagged `refused` says REFUSED (model safety
card) above its radios. "Download ratings.json" saves {output: {rating, note}}: put it at
<root>/ratings.json for report.py. Ratings also autosave in the browser's localStorage,
so a reload keeps them. With <root>/judge.jsonl (judge.py), each cell also carries the VLM
judge's threat assessment and prop match, hidden until "show the VLM judge" is ticked:
seeing it before rating could bias the ratings the judge is calibrated against.
"""

from __future__ import annotations

import argparse
import html
import os
import sys
from pathlib import Path
from typing import Any

from synthbench.spikes.p1_bakeoff.cases import CASES, CLIPS, IDENTITY_PERSON
from synthbench.spikes.p1_bakeoff.report import RATINGS, latest, read_jsonl

_BLURBS: dict[str, str] = (
    {case.id: case.scene for case in CASES}
    | {"identity": f"Identity: {IDENTITY_PERSON}. First column: the model's reference."}
    | {clip.id: f"Clip from keyframe {clip.keyframe}: {clip.motion}" for clip in CLIPS}
)
_SECTION_ORDER = {section: i for i, section in enumerate(_BLURBS)}

_STYLE = """
body { font: 13px system-ui, sans-serif; margin: 0 1em 4em; background: #111; color: #ddd; }
header { position: sticky; top: 0; z-index: 1; background: #111; padding: .5em 0;
  border-bottom: 1px solid #333; }
table { border-collapse: collapse; }
th, td { border: 1px solid #333; padding: 4px; vertical-align: top; text-align: left; }
img, video { width: 320px; display: block; }
.m { font-size: 11px; color: #aaa; max-width: 320px; }
.err { color: #f77; max-width: 320px; white-space: pre-wrap; }
.refused { color: #fb3; font-weight: bold; }
.note { width: 310px; }
"""

_SCRIPT = """
const KEY = "p1-ratings:" + document.body.dataset.root;
const TOTAL = Number(document.body.dataset.total);
function collect() {
  const out = {};
  for (const el of document.querySelectorAll("input[type=radio]:checked")) {
    out[el.name] = {rating: el.value, note: ""};
  }
  for (const el of document.querySelectorAll("input[data-note]")) {
    if (!el.value) continue;
    out[el.dataset.note] = out[el.dataset.note] || {rating: null, note: ""};
    out[el.dataset.note].note = el.value;
  }
  return out;
}
function show(ratings) {
  const rated = Object.values(ratings).filter((v) => v.rating).length;
  document.getElementById("count").textContent = `${rated} / ${TOTAL} rated`;
}
function save() {
  const ratings = collect();
  localStorage.setItem(KEY, JSON.stringify(ratings));
  show(ratings);
}
function restore() {
  const ratings = JSON.parse(localStorage.getItem(KEY) || "{}");
  for (const el of document.querySelectorAll("input[type=radio]")) {
    el.checked = (ratings[el.name] || {}).rating === el.value;
  }
  for (const el of document.querySelectorAll("input[data-note]")) {
    el.value = (ratings[el.dataset.note] || {}).note || "";
  }
  show(ratings);
}
document.addEventListener("change", save);
document.addEventListener("input", save);
document.getElementById("download").addEventListener("click", () => {
  const body = JSON.stringify(collect(), null, 2);
  const url = URL.createObjectURL(new Blob([body], {type: "application/json"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = "ratings.json";
  link.click();
  // revoked later: some browsers start the download only after this handler returns
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
restore();
"""


# measure.py read the model's safety card in the image; the cell keeps its rating radios.
REFUSED_LABEL = "REFUSED (model safety card)"

# The VLM judge's lines stay hidden until the owner asks for them (rate first).
_JUDGE_STYLE = "body:not(.show-judge) .judge { display: none; }"
_JUDGE_TOGGLE = (
    '<label><input type="checkbox" id="show-judge"> show the VLM judge</label> '
    '<span class="m">(rate first: its verdicts can bias your ratings)</span>'
)
_JUDGE_SCRIPT = """
const showJudge = document.getElementById("show-judge");
showJudge.addEventListener("change", () => {
  document.body.classList.toggle("show-judge", showJudge.checked);
});
"""


def _judge_text(row: dict[str, Any]) -> str:
    """The judge's threat assessment and prop match (threat cases), or its error."""
    if row.get("error"):
        return f"judge error: {row['error']}"
    answer = row.get("answer") or {}
    derived = row.get("derived") or {}
    parts = [f"judge: {answer.get('threat_assessment') or 'n/a'}"]
    if derived.get("prop_match") is not None:
        parts.append(f"prop {'yes' if derived['prop_match'] else 'no'}")
    return " · ".join(parts)


def _section(record: dict[str, Any]) -> str:
    return "identity" if record["case"] == "identity_reference" else str(record["case"])


def _column(record: dict[str, Any]) -> str:
    """The seed ("11") for case and clip outputs; the shot ("reference", "0_day") for identity."""
    return Path(record["output"]).stem


def _column_order(column: str) -> tuple[int, int, str]:
    if column == "reference":
        return 0, 0, column
    return (1, int(column), column) if column.isdigit() else (2, 0, column)


def _measure_text(measure: dict[str, Any]) -> str:
    parts: list[str] = []
    if "error" in measure:  # measure.py could not measure this output
        parts.append(f"measure error: {measure['error']}")
    if "owl" in measure:
        parts.append(" · ".join(f"{q} {score:.2f}" for q, score in measure["owl"].items()))
    if "plate_exact" in measure:
        verdict = "exact" if measure["plate_exact"] else f"CER {measure['plate_cer']:.2f}"
        parts.append(f"plate: {measure.get('plate_text') or '(none read)'} ({verdict})")
    if "face" in measure:
        parts.append("face: found" if measure["face"] is not None else "face: none")
    if "frames_with_face" in measure:
        drift = measure.get("frame_drift_max")
        drift_text = "n/a" if drift is None else f"{drift:.3f}"
        parts.append(f"face in {measure['frames_with_face']} frames · max drift {drift_text}")
    return " | ".join(parts)


def _cell(
    record: dict[str, Any], measure: dict[str, Any], judge: dict[str, Any] | None = None
) -> str:
    esc = html.escape
    output = record["output"]
    if not record["ok"]:
        return f'<td><div class="err">{esc(str(record.get("error") or "failed"))}</div></td>'
    seconds = record.get("seconds")
    timing = (
        "" if seconds is None else f"{seconds:.1f} s" + (" (cold)" if record.get("cold") else "")
    )
    if record["kind"] == "i2v":
        media = f'<video controls preload="metadata" src="{esc(output)}"></video>'
    else:
        media = (
            f'<a href="{esc(output)}" target="_blank">'
            f'<img loading="lazy" src="{esc(output)}" alt="{esc(output)}"></a>'
        )
    radios = "".join(
        f'<label><input type="radio" name="{esc(output)}" value="{r}"> {r}</label> '
        for r in RATINGS
    )
    judge_line = f'<div class="m judge">{esc(_judge_text(judge))}</div>' if judge else ""
    refused = f'<div class="refused">{REFUSED_LABEL}</div>' if measure.get("refused") else ""
    return (
        f"<td>{media}{refused}"
        f'<div class="m">{esc(_measure_text(measure))}</div>'
        f'<div class="m">{esc(timing)}</div>'
        f"{judge_line}<div>{radios}</div>"
        f'<input class="note" type="text" placeholder="note" data-note="{esc(output)}">'
        "</td>"
    )


def render(
    records: list[dict[str, Any]],
    measures: list[dict[str, Any]],
    root: Path | None,
    judge: list[dict[str, Any]] | None = None,
) -> str:
    """The contact sheet. Media paths are the records' outputs, relative to `root`,
    where the sheet is written; `root` itself only labels the page. `judge`: judge.jsonl's
    rows, shown under each cell on request."""
    esc = html.escape
    by_output = latest(measures)
    by_judge = latest(judge or [])
    sections: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}  # section/model/column
    for record in latest(records).values():
        model_cells = sections.setdefault(_section(record), {})
        model_cells.setdefault(record["model"], {})[_column(record)] = record
    ok_total = sum(
        1 for cells in sections.values() for m in cells.values() for r in m.values() if r["ok"]
    )
    label = str(root) if root is not None else "."
    order = sorted(sections, key=lambda s: (_SECTION_ORDER.get(s, len(_BLURBS)), s))
    body: list[str] = []
    for section in order:
        rows = sections[section]
        columns = sorted({c for cells in rows.values() for c in cells}, key=_column_order)
        body.append(f'<section id="{esc(section)}"><h2>{esc(section)}</h2>')
        body.append(f'<p class="m">{esc(_BLURBS.get(section, ""))}</p><table>')
        body.append("<tr><th>model</th>" + "".join(f"<th>{esc(c)}</th>" for c in columns) + "</tr>")
        for model, cells in rows.items():
            tds = "".join(
                _cell(
                    cells[c],
                    by_output.get(cells[c]["output"], {}),
                    by_judge.get(cells[c]["output"]),
                )
                if c in cells
                else "<td></td>"
                for c in columns
            )
            body.append(f"<tr><th>{esc(model)}</th>{tds}</tr>")
        body.append("</table></section>")
    nav = " · ".join(f'<a href="#{esc(s)}">{esc(s)}</a>' for s in order)
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en"><head><meta charset="utf-8">',
            f"<title>P1 bake-off contact sheet: {esc(label)}</title>",
            *([f"<style>{_JUDGE_STYLE}</style>"] if by_judge else []),
            f"<style>{_STYLE}</style></head>",
            f'<body data-root="{esc(label)}" data-total="{ok_total}">',
            "<header><h1>P1 bake-off contact sheet</h1>",
            '<button id="download" type="button">Download ratings.json</button> ',
            '<span id="count"></span>',
            *([_JUDGE_TOGGLE] if by_judge else []),
            f'<div class="m">Save the download as {esc(label)}/ratings.json. Ratings '
            "autosave in this browser.</div>",
            f'<div class="m">{nav}</div></header>',
            *body,
            f"<script>{_SCRIPT}</script>",
            *([f"<script>{_JUDGE_SCRIPT}</script>"] if by_judge else []),
            "</body></html>",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.spikes.p1_bakeoff.sheet")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "p1",
    )
    root: Path = parser.parse_args(argv).root
    records = read_jsonl(root / "records.jsonl")
    measures = read_jsonl(root / "measures.jsonl", missing_ok=True)
    judge = read_jsonl(root / "judge.jsonl", missing_ok=True)
    out = root / "sheet.html"
    out.write_text(render(records, measures, root, judge))
    sys.stdout.write(f"{out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
