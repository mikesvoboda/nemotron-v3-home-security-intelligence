"""`report.md` (aggregate only: Task 7 commits it) and `report.html` (the failure gallery)."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path
from typing import Any

CONDITIONS = (
    "**Conditions.** The truth is declared by the sampler and unverified; the owner's audit below "
    "gives its error rate. Stills with an ideal detector: the VLM gets each event's declared "
    "subjects and props as detections (object type and confidence 1.0, no box) and no specialist "
    "context; a real detector misses some of them, so this is optimistic. Accuracy only: the "
    "GB300 is shared, so no latency or memory figure here stands for a deployment. Ambiguous "
    "events are not scored."
)
CELLS = (
    'Each cell reads rate [95% Wilson interval] (n); under n = 10 it reads "insufficient". '
    "S2 is benign scenes scored medium or above; S3 is incidents scored at or above their level."
)


def fmt(cell: Mapping[str, Any] | None) -> str:
    """One metric cell as text."""
    if cell is None:
        return "—"
    if cell["insufficient"]:
        return f"insufficient (n={cell['n']})"
    lo, hi = cell["wilson_95"]
    return f"{cell['rate']:.1%} [{lo * 100:.1f}-{hi * 100:.1f}] (n={cell['n']})"


def _table(header: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    lines += ["| " + " | ".join(str(value) for value in row) + " |" for row in rows]
    return lines


def _headline(models: Mapping[str, Any], key: str) -> list[str]:
    rows = [
        [
            model,
            m[key]["n"],
            fmt(m[key]["s2_cell"]),
            fmt(m[key]["s3_cell"]),
            fmt(m[key]["s3_excluding_zero_floor_cell"]),
            fmt(m[key]["refusal_cell"]),
            fmt(m[key]["uncertain_cell"]),
        ]
        for model, m in models.items()
    ]
    header = ("Model", "Items", "S2", "S3", "S3, low floor excluded", "Refusals", "Uncertain")
    return _table(header, rows)


def _identity(identity: Mapping[str, Any]) -> list[str]:
    export, audit = identity.get("export", {}), identity.get("audit", {})
    lines = [
        f"- Scored at commit `{identity.get('commit', '?')}`, scoring version "
        f"{identity.get('score_version', '?')}, {identity.get('created_utc', '?')}.",
        f"- Corpus {', '.join(identity.get('corpus_version', [])) or '?'}; export "
        f"`{export.get('path', '?')}`: {export.get('items', '?')} sets, labels sha256 "
        f"`{export.get('labels_sha256', '?')}`.",
        f"- Audit log `{audit.get('path', '?')}`, sha256 `{audit.get('sha256') or 'none yet'}`.",
        "- vLLM models: the image is pinned by digest in the operator runbook's start command; "
        "no endpoint reports it.",
        "",
    ]
    header = ("Model", "Replay", "Transport", "Endpoint", "Build", "Weights", "Replay commit")
    rows = [
        [
            r.get("model"),
            f"`{r.get('replay_id')}`",
            r.get("transport"),
            r.get("url"),
            r.get("build") or "—",
            r.get("weights"),
            f"`{r.get('commit')}`",
        ]
        for r in identity.get("replays", [])
    ]
    return lines + _table(header, rows)


def _audit(audit: Mapping[str, Any]) -> list[str]:
    lines = [f"{audit['answered']} of {audit['sampled']} sampled stills have a scene answer.", ""]
    rows = [
        [key, q["answered"], q["yes"], q["no"], q["unclear"], fmt(q["error"])]
        for key, q in audit["questions"].items()
    ]
    lines += _table(("Question", "Answered", "Yes", "No", "Unclear", "Truth error"), rows)
    errors = len(audit["generation_errors"])
    lines += [
        "",
        f"{errors} event(s) whose scene the owner answered no are generation errors: they are "
        "excluded from every metric, never counted as model errors.",
    ]
    return lines


def _band(models: Mapping[str, Any]) -> list[str]:
    rows = []
    for model, m in models.items():
        for label, b in m["all"]["band"].items():
            below, above = b["mean_distance_below"], b["mean_distance_above"]
            rows.append(
                [
                    model,
                    label,
                    b["n"],
                    fmt(b["inside"]),
                    fmt(b["below"]),
                    fmt(b["above"]),
                    "—" if below is None else below,
                    "—" if above is None else above,
                ]
            )
    header = ("Model", "Label", "Scored", "Inside", "Below", "Above", "Mean below", "Mean above")
    return _table(header, rows)


def _verdicts(models: Mapping[str, Any]) -> list[str]:
    rows = []
    for model, m in models.items():
        mix = m["all"]["verdicts"]["verdict_mix"]
        s5 = m["all"]["s5"]
        rows.append(
            [
                model,
                ", ".join(f"{verdict} {count}" for verdict, count in mix.items()) or "—",
                s5["unparseable"],
                s5["unavailable"],
                s5["unclassifiable"],
            ]
        )
    return _table(("Model", "Verdicts", "Unparseable", "Unavailable", "No cause"), rows)


def _slices(models: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for model, m in models.items():
        lines += ["", f"### {model}"]
        for name, values in m["slices"].items():
            rows = [[value, fmt(c["s2"]), fmt(c["s3"])] for value, c in values.items()]
            lines += ["", f"**{name}**", "", *_table((name, "S2", "S3"), rows)]
    return lines


def _comparison(pairs: Sequence[Mapping[str, Any]]) -> list[str]:
    if not pairs:
        return ["One model scored: nothing to compare."]
    rows = [
        [
            f"{p['a']} / {p['b']}",
            p["agree"]["n"],
            fmt(p["agree"]),
            len(p["a_wrong_b_right"]),
            len(p["b_wrong_a_right"]),
        ]
        for p in pairs
    ]
    header = (
        "Models",
        "Common items",
        "Agreement",
        "Only the first wrong",
        "Only the second wrong",
    )
    return _table(header, rows)


def markdown(metrics: Mapping[str, Any], identity: Mapping[str, Any]) -> str:
    """The aggregate report: rates, n and intervals, never a per-item row."""
    models = metrics["models"]
    lines = [
        f"# Synthbench P5a scores: {identity.get('score_id', '?')}",
        "",
        CONDITIONS,
        "",
        CELLS,
        "",
        "## Run identity",
        "",
        *_identity(identity),
        "",
        "## Headline: every scored item",
        "",
        *_headline(models, "all"),
        "",
        "## Headline: audited stills whose scene the owner confirmed",
        "",
        *_headline(models, "audited"),
        "",
        "## Audit",
        "",
        *_audit(metrics["audit"]),
        "",
        "## Risk band",
        "",
        *_band(models),
        "",
        "## Verdicts and refusals",
        "",
        *_verdicts(models),
        "",
        "## Slices",
        *_slices(models),
        "",
        "## Comparison",
        "",
        *_comparison(metrics["comparison"]),
    ]
    return "\n".join(lines) + "\n"


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font: 14px system-ui, sans-serif; margin: 16px; background: #111; color: #ddd; }}
main {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 12px; }}
figure {{ margin: 0; background: #1c1c1c; padding: 8px; border-left: 4px solid #c33; }}
img {{ width: 100%; height: auto; }}
</style></head><body><h1>{title}</h1><p>{conditions}</p>
{sections}
</body></html>
"""
_GALLERIES = (
    ("miss", "Incidents scored below their level"),
    ("false_alarm", "Benign scenes scored medium or above"),
)


def _card(row: Mapping[str, Any], out_dir: Path) -> str:
    source = os.path.relpath(row["still"], out_dir)
    cell = row["cell"]
    lo, hi = row["band"]
    caption = (
        f"<b>{escape(row['event_id'])}</b> {escape(cell['scenario'])}, {escape(cell['lighting'])}, "
        f"{escape(cell['weather'])}; band {lo}-{hi}, level {escape(row['floor'])}; scored "
        f"{row['risk_score']} ({escape(row['verdict'])})<br>{escape(row['reasoning'] or '')}"
    )
    return (
        f'<figure><img src="{escape(source)}" loading="lazy" alt="{escape(row["event_id"])}">'
        f"<figcaption>{caption}</figcaption></figure>"
    )


def html(identity: Mapping[str, Any], results: Sequence[Mapping[str, Any]], out_dir: Path) -> str:
    """The failure gallery, per model: each still with its facts and the VLM's reasoning."""
    sections: list[str] = []
    for model in dict.fromkeys(row["model"] for row in results):
        for wanted, heading in _GALLERIES:
            cards = [
                _card(row, out_dir)
                for row in results
                if row["model"] == model and row["outcome"] == wanted and not row["excluded"]
            ]
            sections.append(
                f"<h2>{escape(model)}: {escape(heading)} ({len(cards)})</h2>"
                f"<main>{''.join(cards)}</main>"
            )
    title = escape(f"Synthbench P5a failures: {identity.get('score_id', '?')}")
    conditions = escape(CONDITIONS.replace("**", ""))
    return _HTML.format(title=title, conditions=conditions, sections="\n".join(sections))
