"""`report.md` (aggregate only: Task 7 commits it) and `report.html` (the failure gallery)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from html import escape
from pathlib import Path
from typing import Any

CONDITIONS = (
    "**Conditions.** The truth is declared by the sampler and unverified; the owner's audit below "
    "gives its error rate. Stills with an ideal detector: the VLM gets each event's declared "
    "subjects and props as detections (object type and confidence 1.0, no box) and no specialist "
    "context; a real detector misses some of them, so this is optimistic. Accuracy only: the "
    "GB300 is shared, so no latency or memory figure here stands for a deployment. Ambiguous "
    "events are not scored. Comparison models may run under different conditions from the "
    "product model (a system message, a token budget, a read timeout, thinking off): the "
    "Conditions per model table in report.md lists each model's."
)
CELLS = (
    'Each cell reads rate [95% Wilson interval] (n); under n = 10 it reads "insufficient". '
    "S2 is benign scenes scored medium or above; S3 is incidents scored at or above their "
    "level. The clustered columns resample SCENARIOS, not items (ISS-043): items share a "
    "scenario, so the Wilson interval understates the uncertainty whenever a scenario's "
    "errors come in groups; the clustered reading is the one to read when the two disagree."
)


def fmt(cell: Mapping[str, Any] | None) -> str:
    """One metric cell as text."""
    if cell is None:
        return "—"
    if cell["insufficient"]:
        return f"insufficient (n={cell['n']})"
    lo, hi = cell["wilson_95"]
    return f"{cell['rate']:.1%} [{lo * 100:.1f}-{hi * 100:.1f}] (n={cell['n']})"


def fmt_cluster(cluster: Mapping[str, Any] | None) -> str:
    """A scenario-cluster bootstrap as text: `clustered X% [lo-hi] (n, c scenarios)`. The
    point rate is the pooled reading (identical to the Wilson cell's); only the width
    moves - that is the whole comparison ISS-043 asks the reader to make."""
    if cluster is None or cluster["point_pct"] is None:
        return "—"
    lo, hi = cluster["ci_pct"]
    return (
        f"clustered {cluster['point_pct']:.1f}% [{lo:.1f}-{hi:.1f}] "
        f"(n={cluster['n']}, {cluster['clusters']} scenarios)"
    )


def fmt_diff(diff: Mapping[str, Any] | None) -> str:
    """A paired dS2/dS3 as text: `+X.X pts [lo to hi]`, or em-dash when this leg has no
    eligible item (no benign items means no S2 leg, and the report says so by absence)."""
    if diff is None or diff["point_pts"] is None:
        return "—"
    if diff["ci_pts"] is None:
        return f"{diff['point_pts']:+.1f} pts [no clustered draw]"
    lo, hi = diff["ci_pts"]
    return f"{diff['point_pts']:+.1f} pts [{lo:+.1f} to {hi:+.1f}]"


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
            fmt_cluster(m[key].get("s2_cluster")),
            fmt(m[key]["s3_cell"]),
            fmt_cluster(m[key].get("s3_cluster")),
            fmt(m[key]["s3_excluding_zero_floor_cell"]),
            fmt(m[key]["refusal_cell"]),
            fmt(m[key]["uncertain_cell"]),
        ]
        for model, m in models.items()
    ]
    header = (
        "Model",
        "Items",
        "S2",
        "Clustered S2",
        "S3",
        "Clustered S3",
        "S3, low floor excluded",
        "Refusals",
        "Uncertain",
    )
    return _table(header, rows)


def shown_path(path: str | None, root: Path | None) -> str:
    """A path as `report.md` shows it (the report is committed): relative to `$SYNTHBENCH_ROOT`,
    never an absolute host path."""
    if not path:
        return "?"
    target = Path(path)
    if not target.is_absolute():
        return target.as_posix()
    for base in () if root is None else (root, root.resolve()):
        if target.is_relative_to(base):
            return target.relative_to(base).as_posix()
    return f"{target.name} (outside $SYNTHBENCH_ROOT)"


def _identity(identity: Mapping[str, Any], root: Path | None) -> list[str]:
    export, audit = identity.get("export", {}), identity.get("audit", {})
    store = identity.get("eval_store", {})
    lines = [
        f"- Scored at commit `{identity.get('commit', '?')}`, scoring version "
        f"{identity.get('score_version', '?')}, {identity.get('created_utc', '?')}.",
        f"- Corpus {', '.join(identity.get('corpus_version', [])) or '?'}; export "
        f"`{shown_path(export.get('path'), root)}`: {export.get('items', '?')} sets, labels "
        f"sha256 `{export.get('labels_sha256', '?')}`; eval store "
        f"`{shown_path(store.get('path'), root)}`.",
        f"- Audit log `{shown_path(audit.get('path'), root)}`, sha256 "
        f"`{audit.get('sha256') or 'none yet'}`.",
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


def _thinking(value: str | None) -> str:
    """The model's declared thinking condition (`Model.thinking`, recorded in `run.json` as
    `thinking`, decision A7). A run.json from before it was recorded has no key."""
    return "—" if value is None else value


def _conditions(replays: Sequence[Mapping[str, Any]]) -> list[str]:
    """Each model's conditions as its replay recorded them; older replays did not record
    them all."""

    def shown(value: Any, show: Callable[[Any], str]) -> str:
        return "unrecorded" if value is None else show(value)

    def sampling(record: Mapping[str, Any]) -> str:
        # ISS-043: two arms are only comparable if they were sampled alike.
        if record.get("temperature") is None:
            return "unrecorded"
        return f"temp {record['temperature']}" + (
            ", seeded" if record.get("seed") is not None else ", unseeded"
        )

    rows = [
        [
            r.get("model"),
            r.get("transport"),
            "shipped + system message (A7)" if r.get("system_message") else "shipped",
            _thinking(r.get("thinking")),
            shown(r.get("max_tokens"), str),
            shown(r.get("read_timeout"), lambda seconds: f"{seconds:g} s"),
            shown(r.get("enforcement_probe"), lambda on: "on" if on else "off"),
            sampling(r),
        ]
        for r in replays
    ]
    header = (
        "Model",
        "Transport",
        "Prompt",
        "Thinking",
        "Max tokens",
        "Read timeout",
        "Enforcement probe",
        "Sampling",
    )
    lines = _table(header, rows)
    for r in replays:
        if r.get("system_message"):
            lines += [
                "",
                f"{r.get('model')}'s system message, sent ahead of the shipped prompt: "
                f"`{json.dumps(r['system_message'])}`",
            ]
    return lines


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
            f"{p['s2_discordants']['only_a']} / {p['s2_discordants']['only_b']}"
            f" (p={p['s2_discordants']['p']:.3g})",
            fmt_diff(p.get("dS2")),
            f"{p['s3_discordants']['only_a']} / {p['s3_discordants']['only_b']}"
            f" (p={p['s3_discordants']['p']:.3g})",
            fmt_diff(p.get("dS3")),
        ]
        for p in pairs
    ]
    header = (
        "Models",
        "Common items",
        "Agreement",
        "Only the first wrong",
        "Only the second wrong",
        "S2 discordants first / second (McNemar p)",
        "dS2 [cluster CI]",
        "S3 discordants first / second (McNemar p)",
        "dS3 [cluster CI]",
    )
    lines = _table(header, rows)
    lines += [
        "",
        "The paired columns are ISS-043's: McNemar's exact p treats the discordant ITEMS as "
        "independent, the dS2/dS3 interval resamples SCENARIOS (OD-26's form). A comparison "
        "whose dS interval spans 0 is inside the run-to-run and scenario noise: neither arm "
        "moved, whatever the point rates look like side by side.",
    ]
    return lines


def markdown(
    metrics: Mapping[str, Any], identity: Mapping[str, Any], root: Path | None = None
) -> str:
    """The aggregate report: rates, n and intervals, never a per-item row. Paths show relative
    to `root` ($SYNTHBENCH_ROOT)."""
    models = metrics["models"]
    lines = [
        f"# Synthbench P5a scores: {identity.get('score_id', '?')}",
        "",
        CONDITIONS,
        "",
        CELLS,
        "",
        "## Conditions per model",
        "",
        *_conditions(identity.get("replays", [])),
        "",
        "## Run identity",
        "",
        *_identity(identity, root),
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
