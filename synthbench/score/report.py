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
    "product model (a system message, a token budget, a read timeout, thinking off, a build, "
    "server flags the operator declared): the Conditions per model table in report.md lists "
    "each model's."
)
CELLS = (
    'Each cell reads rate [95% Wilson interval] (n); under n = 10 it reads "insufficient". '
    "S2 is benign scenes scored medium or above; S3 is incidents scored at or above their "
    "level. The clustered columns resample SCENARIOS, not items (ISS-043): items share a "
    "scenario, so the Wilson interval understates the uncertainty whenever a scenario's "
    "errors come in groups; the clustered reading is the one to read when the two disagree."
)
UNRECORDED = "unrecorded"  # identity.split's source for an export written before ISS-016
# §5's headings, verbatim. The two arms share `_headline`, so their columns are literally the
# columns of the all-items table a reader has already been shown.
SAYS = "## What this split can and cannot say"
DEV_HEADLINE = "## Headline: dev split (tuning may see this)"
HOLDOUT_HEADLINE = "## Headline: holdout split (tuning never saw this)"
DEV_SLICE = "### Scenario slice, dev only"
DEV_COMPARISON = "### Comparison: dev split (where the OD-26 rule decides)"
HOLDOUT_COMPARISON = (
    "### Comparison: holdout split (the generalization check; the rule is not applied)"
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


def _split_row(split: Mapping[str, Any]) -> str:
    """The Run identity's `Split` row (spec §5). A recorded split quotes the manifest this score
    cross-checked, so every number in the row is the score's own; an export predating ISS-016 says
    so and the report prints none of the split's sections."""
    if not split.get("sha256"):  # unrecorded, or no split block at all (B6's shape)
        return f"- Split: {UNRECORDED} — this export predates ISS-016"
    items = split.get("items", {})
    holdout, dev = items.get("holdout", {}), items.get("dev", {})
    dev_items = int(dev.get("benign", 0)) + int(dev.get("incident", 0))
    return (
        f"- Split: {split.get('source')} sha256 {split.get('sha256')}; seed {split.get('seed')}; "
        f"holdout {split.get('holdout_k')} scenarios / {holdout.get('incident')} incident items; "
        f"dev {dev_items} ({dev.get('benign')} benign)"
    )


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
        _split_row(identity.get("split", {})),
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


def _build(value: str | None) -> str:
    """The build the endpoint reported to `check` (recorded as `build`). An endpoint that answers
    `/props` always reports one, and an empty answer reads the same as an older record's missing
    key: `—`, because nothing was observed (as opposed to server settings: never DECLARED)."""
    return value if value else "—"


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
            _build(r.get("build")),
            # ISS-087: `shown`, not `_build`, because the absence means something different: the
            # operator never declared what the endpoint was started with. The `|` escape is for
            # this table only — it is markdown's column separator, and an unescaped one in the
            # free text of a declaration shifts every later cell's label; `run.json` and
            # `metrics.json` keep the string exactly as the operator gave it.
            shown(r.get("server_settings"), lambda text: text.replace("|", "\\|")),
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
        "Build",
        "Server settings",
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


def _recorded(split: Mapping[str, Any]) -> bool:
    """Whether this score read a split (Task 5's identity block). Everything §5 adds hangs on
    this one test, so an export predating ISS-016 prints the report it printed before."""
    return bool(split.get("sha256"))


def _can_and_cannot(split: Mapping[str, Any]) -> list[str]:
    """§5's bounds section, printed only when a split is recorded. The n it discounts the holdout
    by is this run's own (the manifest `load_split` accepted), never the shipped corpus's."""
    items = split.get("items", {})
    holdout = items.get("holdout", {})
    return [
        SAYS,
        "",
        f"- The holdout is {holdout.get('incident', '?')} incident items over "
        f"{split.get('holdout_k')} scenarios. That is a leak detector, not a precise estimate: "
        "items share a scenario, so the scenario-cluster interval on this many items is several "
        "times wider than the same count of independent items would be. A holdout rate here "
        "checks that tuning on dev did not collapse generalization; it is not a competing "
        "measurement of the 90% bar.",
        "- The draw is unstratified (ISS-016 B4), so the holdout's group mix is the hash's luck "
        "rather than a design choice, and it can land suspicious-heavy — the leg where recall is "
        "worst. A holdout S3 below dev's is therefore expected for any prompt that has not fixed "
        "that leg: read the dev-versus-holdout gap, never the holdout's level as a bar attempt.",
        "- S2 is measured on dev by design: every benign scenario stays in dev (ISS-016 B1), so "
        "the holdout says nothing at all about false alarms.",
        "- Tuning rule: holdout stills and failures are excluded from `report.html`, the gallery "
        "tuning reads, so a prompt tuned on this run's dev material has not seen them.",
        "",
    ]


def _dev_benign(models: Mapping[str, Any], split: Mapping[str, Any]) -> int | None:
    """The dev arm's benign item count, as the dev table beside the footnote shows it. Taken from
    the run's own dev headlines; the manifest's own count is the fallback for a score with no
    model block to read."""
    counts = [int(m["dev"]["s2"]["n"]) for m in models.values() if "dev" in m]
    if counts:
        return max(counts)
    benign = split.get("items", {}).get("dev", {}).get("benign")
    return None if benign is None else int(benign)


def _holdout_s2_note(models: Mapping[str, Any], split: Mapping[str, Any]) -> list[str]:
    """Why the holdout's S2 cell is empty. The count is computed, never the shipped corpus's."""
    if any(int(m["holdout"]["s2"]["n"]) for m in models.values() if "holdout" in m):
        return []  # a stratified draw would have benign items here: nothing to explain
    benign = _dev_benign(models, split)
    if benign is None:
        return []
    return [
        "",
        f"Footnote: no benign items in the holdout: S2 is measured on dev, which holds all "
        f"{benign} benign items by design (ISS-016 B1).",
    ]


def _scenario_slice_dev(models: Mapping[str, Any]) -> list[str]:
    """§5's one slice addition: the per-scenario failure detail a tuner reads to pick what to fix,
    over dev rows only (B7). The other slice dimensions stay all-items — they are aggregates, not
    the unit of the split, and suppressing them would cost comparability for nothing."""
    lines = [DEV_SLICE]
    for model, m in models.items():
        values = m.get("scenario_slice_dev") or {}
        rows = [[value, fmt(c["s2"]), fmt(c["s3"])] for value, c in values.items()]
        lines += ["", f"**{model}**", "", *_table(("Scenario", "S2", "S3"), rows)]
    return lines


def _slices(models: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for model, m in models.items():
        lines += ["", f"### {model}"]
        for name, values in m["slices"].items():
            rows = [[value, fmt(c["s2"]), fmt(c["s3"])] for value, c in values.items()]
            lines += ["", f"**{name}**", "", *_table((name, "S2", "S3"), rows)]
    return lines


def _identical(count: Mapping[str, Any] | None) -> str:
    """One pair's ISS-087 identical count as a cell: `2 of 6`. An empty cell is a record written
    before the key existed — see `_comparison` for why that case removes the column instead of
    printing a dash for a report whose numbers were already committed."""
    return "" if count is None else f"{count['k']} of {count['n']}"


def _comparison(pairs: Sequence[Mapping[str, Any]], note: bool = True) -> list[str]:
    """One comparison table; `note` prints ISS-043's closing reading after it. With a recorded
    split the report prints two tables and one note (`note=False` on the first), because the
    reading below is the same sentence for both sides of the split."""
    if not pairs:
        return ["One model scored: nothing to compare."]
    # The identical column is LAST, so every column a reader has already compared keeps its
    # position, and it appears only when the data carries the count: a frozen `metrics.json` from
    # before ISS-087 keeps the table it was written with, which is the report a claim rests on.
    header = [
        "Models",
        "Common items",
        "Agreement",
        "Only the first wrong",
        "Only the second wrong",
        "S2 discordants first / second (McNemar p)",
        "dS2 [cluster CI]",
        "S3 discordants first / second (McNemar p)",
        "dS3 [cluster CI]",
    ]
    counts = [_identical(p.get("identical")) for p in pairs]
    if any(counts):
        header += ["Identical items (same outcome and score)"]
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
    if any(counts):
        for row, count in zip(rows, counts, strict=True):
            row.append(count)
    lines = _table(header, rows)
    if note:
        lines += [
            "",
            "The paired columns are ISS-043's: McNemar's exact p treats the discordant ITEMS as "
            "independent, the dS2/dS3 interval resamples SCENARIOS (OD-26's form). A comparison "
            "whose dS interval spans 0 is inside the run-to-run and scenario noise: neither arm "
            "moved, whatever the point rates look like side by side.",
        ]
    return lines


def _comparisons(metrics: Mapping[str, Any]) -> list[str]:
    """Today's single table, or §5's two: dev first because that is where the OD-26 rule decides,
    holdout second as the generalization check the rule is not applied to. The all-items
    comparison the split_comparison sits beside keeps printing in `## Comparison`'s own voice when
    no split was recorded, so pre-split records read unchanged."""
    split = metrics.get("split_comparison")
    if not split:
        return _comparison(metrics["comparison"])
    return [
        DEV_COMPARISON,
        "",
        *_comparison(split["dev"], note=False),
        "",
        HOLDOUT_COMPARISON,
        "",
        # The reading applies to both tables and is printed once, after them — unless one model
        # was scored and neither table exists, where a note about paired tests would mislead.
        *_comparison(split["holdout"], note=bool(split["dev"] or split["holdout"])),
    ]


def markdown(
    metrics: Mapping[str, Any], identity: Mapping[str, Any], root: Path | None = None
) -> str:
    """The aggregate report: rates, n and intervals, never a per-item row. Paths show relative
    to `root` ($SYNTHBENCH_ROOT)."""
    models = metrics["models"]
    split = identity.get("split", {})
    recorded = _recorded(split)
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
    ]
    if recorded:
        lines += _can_and_cannot(split)
    lines += [
        "## Headline: every scored item",
        "",
        *_headline(models, "all"),
        "",
    ]
    if recorded:
        # Same helper, same columns, different label: a reader compares the arms against the
        # all-items table because the tables are the same shape.
        lines += [
            DEV_HEADLINE,
            "",
            *_headline(models, "dev"),
            "",
            *_scenario_slice_dev(models),
            "",
            HOLDOUT_HEADLINE,
            "",
            *_headline(models, "holdout"),
            *_holdout_s2_note(models, split),
            "",
        ]
    lines += [
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
        *_comparisons(metrics),
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


def _shown(row: Mapping[str, Any]) -> bool:
    """Whether this row's still may enter the gallery (ISS-016 B7).

    The gallery is what prompt tuning actually looks at, so a holdout still reaching it is a
    leak, not a cosmetic slip — which is why this is `report.py`'s only `raise` and why it
    happens before any card is built: the score directory is left half-written as evidence.
    `unrecorded` renders because that gallery predates the split; a row with no `split` at all
    is the shape that cannot be checked, so it is refused rather than guessed at.
    """
    if "split" not in row:
        raise ValueError(
            f"the gallery row for {row.get('item_id')} carries no `split`: the failure gallery "
            "shows dev and unrecorded stills only (ISS-016 B7), and a row that cannot be "
            "checked for its arm cannot be shown"
        )
    return row["split"] in ("dev", UNRECORDED)


def html(identity: Mapping[str, Any], results: Sequence[Mapping[str, Any]], out_dir: Path) -> str:
    """The failure gallery, per model: each still with its facts and the VLM's reasoning. The
    stills are dev's and, for a pre-split export, all of them (`_shown`). The heading for every
    scored model is today's, so the filter changes which cards appear and nothing else."""
    shown = [row for row in results if _shown(row)]
    sections: list[str] = []
    for model in dict.fromkeys(row["model"] for row in results):
        for wanted, heading in _GALLERIES:
            cards = [
                _card(row, out_dir)
                for row in shown
                if row["model"] == model and row["outcome"] == wanted and not row["excluded"]
            ]
            sections.append(
                f"<h2>{escape(model)}: {escape(heading)} ({len(cards)})</h2>"
                f"<main>{''.join(cards)}</main>"
            )
    title = escape(f"Synthbench P5a failures: {identity.get('score_id', '?')}")
    conditions = escape(CONDITIONS.replace("**", ""))
    return _HTML.format(title=title, conditions=conditions, sections="\n".join(sections))
