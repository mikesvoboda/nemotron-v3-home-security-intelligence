"""P5a's metrics (design §5), over plain data: replay rows, items and audit answers.

S2 and S3 come only from `backend/evaluation/s_metrics.py`, so the benchmark and the VSS harness
share one definition; `outcome` restates their per-row rule for slices, the gallery and the
comparison, and a test holds the two equal.
"""

from __future__ import annotations

import itertools
import statistics
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.evaluation.levels import level_at_or_above, score_to_level
from backend.evaluation.s_metrics import (
    s2_false_positive_rate,
    s3_recall,
    s5_refusals,
    uncertain_rate,
    wilson_interval,
)

Row = dict[str, Any]  # a replay row, as `EvalStore.replay` returns it
MIN_N = 10  # a cell under this many items reads "insufficient (n=…)"
AUDIT_KEYS = ("scene", "prop", "people", "conditions")
RIGHT = {"hit", "clear"}


@dataclass(frozen=True)
class Item:
    """One item as scored: its label and S3 floor from the eval store (the label authority),
    its facts and still from the export."""

    item_id: str
    label: str  # "incident" or "benign"
    floor: str  # S3's expected minimum level
    facts: Mapping[str, Any]  # the export's `synthbench` block
    still: Path

    @property
    def event_id(self) -> str:
        return str(self.facts["event_id"])

    @property
    def band(self) -> tuple[int, int]:
        lo, hi = self.facts["risk_band"]
        return int(lo), int(hi)


def _cell_value(key: str) -> Callable[[Mapping[str, Any]], str]:
    return lambda cell: str(cell[key])


SLICES: tuple[tuple[str, Callable[[Mapping[str, Any]], str]], ...] = (
    ("scenario", _cell_value("scenario")),
    ("group", _cell_value("group")),
    ("lighting", _cell_value("lighting")),
    ("weather", _cell_value("weather")),
    ("property", _cell_value("property_type")),
    ("camera", _cell_value("camera")),
    ("zone", _cell_value("zone")),
    ("artifacts", lambda cell: "drawn" if cell.get("artifacts") else "none"),
)


def cell(k: int, n: int) -> dict[str, Any]:
    """A rate with its n and 95% Wilson interval; under MIN_N items it is insufficient."""
    lo, hi = wilson_interval(k, n)
    return {
        "k": k,
        "n": n,
        "rate": k / n if n else None,
        "wilson_95": [round(lo, 4), round(hi, 4)],
        "insufficient": n < MIN_N,
    }


def outcome(item: Item, row: Row) -> str:
    """A row's result by `s_metrics`' rules: `refused` (no score); an incident is a `hit` at or
    above its floor, else a `miss`; a benign item at medium or above is a `false_alarm`, else
    `clear`."""
    score = row.get("risk_score")
    if score is None:
        return "refused"
    level = score_to_level(int(score))
    if item.label == "incident":
        return "hit" if level_at_or_above(level, item.floor) else "miss"
    return "false_alarm" if level_at_or_above(level, "medium") else "clear"


def band_position(item: Item, score: int) -> tuple[str, int]:
    """Where a score falls against the item's declared risk band, and how far outside it."""
    lo, hi = item.band
    if score < lo:
        return "below", lo - score
    if score > hi:
        return "above", score - hi
    return "inside", 0


def _band(rows: Sequence[Row], items: Mapping[str, Item]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label in ("incident", "benign"):
        placed = [
            band_position(items[row["item_id"]], int(row["risk_score"]))
            for row in rows
            if items[row["item_id"]].label == label and row.get("risk_score") is not None
        ]
        n = len(placed)
        entry: dict[str, Any] = {"n": n}
        for position in ("inside", "below", "above"):
            entry[position] = cell(sum(1 for p, _ in placed if p == position), n)
            distances = [d for p, d in placed if p == position and position != "inside"]
            if position != "inside":
                entry[f"mean_distance_{position}"] = (
                    round(statistics.fmean(distances), 1) if distances else None
                )
        out[label] = entry
    return out


def headline(rows: Sequence[Row], items: Mapping[str, Item]) -> dict[str, Any]:
    """One model's metrics over some rows: `s_metrics`' own dicts plus a cell for each rate."""
    rows = list(rows)
    labels = {item_id: item.label for item_id, item in items.items()}
    floors = {
        item_id: {"label": item.label, "floor": item.floor} for item_id, item in items.items()
    }
    s2 = s2_false_positive_rate(rows, labels)
    s3 = s3_recall(rows, floors)
    s5 = s5_refusals(rows)
    verdicts = uncertain_rate(rows)
    return {
        "n": len(rows),
        "s2": s2,
        "s3": s3,
        "s5": s5,
        "verdicts": verdicts,
        "s2_cell": cell(s2["fp"], s2["n"]),
        "s3_cell": cell(s3["all"]["hit"], s3["all"]["n"]),
        "s3_excluding_zero_floor_cell": cell(
            s3["excluding_zero_floor"]["hit"], s3["excluding_zero_floor"]["n"]
        ),
        "refusal_cell": cell(s5["refusals"], len(rows)),
        "uncertain_cell": cell(verdicts["verdict_mix"].get("uncertain", 0), len(rows)),
        "band": _band(rows, items),
    }


def slices(rows: Sequence[Row], items: Mapping[str, Item]) -> dict[str, dict[str, Any]]:
    """S2 and S3 per value of each slice; None where the value has no item of that label."""
    out: dict[str, dict[str, Any]] = {}
    for name, value_of in SLICES:
        groups: dict[str, list[Row]] = defaultdict(list)
        for row in rows:
            groups[value_of(items[row["item_id"]].facts["cell"])].append(row)
        out[name] = {}
        for value, members in sorted(groups.items()):
            metrics = headline(members, items)
            out[name][value] = {
                "s2": metrics["s2_cell"] if metrics["s2"]["n"] else None,
                "s3": metrics["s3_cell"] if metrics["s3"]["all"]["n"] else None,
            }
    return out


def audit_summary(answers: Mapping[tuple[str, str], str], sampled: Sequence[str]) -> dict[str, Any]:
    """The truth's error rate per question over the sampled stills (`n` of `y` + `n`; `u` is
    counted apart), and the events whose scene the owner answered no: generation errors."""
    questions: dict[str, Any] = {}
    for key in AUDIT_KEYS:
        got = [answers[(event_id, key)] for event_id in sampled if (event_id, key) in answers]
        yes, no, unclear = got.count("y"), got.count("n"), got.count("u")
        questions[key] = {
            "answered": len(got),
            "yes": yes,
            "no": no,
            "unclear": unclear,
            "error": cell(no, yes + no),
        }
    scene = {event_id: answers.get((event_id, "scene")) for event_id in sampled}
    return {
        "sampled": len(sampled),
        "answered": sum(1 for answer in scene.values() if answer is not None),
        "questions": questions,
        "generation_errors": sorted(e for e, answer in scene.items() if answer == "n"),
        "confirmed": sorted(e for e, answer in scene.items() if answer == "y"),
    }


def comparison(
    replays: Sequence[tuple[str, Sequence[Row]]], items: Mapping[str, Item]
) -> list[dict[str, Any]]:
    """Per pair of models, over the items both replayed: how often their outcomes agree, and the
    items one gets wrong (a miss, a false alarm or a refusal) that the other gets right."""
    out: list[dict[str, Any]] = []
    for (a, rows_a), (b, rows_b) in itertools.combinations(replays, 2):
        by_a = {row["item_id"]: outcome(items[row["item_id"]], row) for row in rows_a}
        by_b = {row["item_id"]: outcome(items[row["item_id"]], row) for row in rows_b}
        common = sorted(by_a.keys() & by_b.keys())
        out.append(
            {
                "a": a,
                "b": b,
                "agree": cell(sum(1 for i in common if by_a[i] == by_b[i]), len(common)),
                "a_wrong_b_right": [i for i in common if by_a[i] not in RIGHT and by_b[i] in RIGHT],
                "b_wrong_a_right": [i for i in common if by_b[i] not in RIGHT and by_a[i] in RIGHT],
            }
        )
    return out


def result_rows(
    replays: Sequence[tuple[str, str, Sequence[Row]]],
    items: Mapping[str, Item],
    answers: Mapping[tuple[str, str], str],
    excluded: set[str],
) -> list[dict[str, Any]]:
    """One row per item per model, for `results.jsonl` and the failure gallery."""
    out: list[dict[str, Any]] = []
    for model, replay_id, rows in replays:
        for row in rows:
            item = items[row["item_id"]]
            score = row.get("risk_score")
            position, distance = (
                band_position(item, int(score)) if score is not None else (None, None)
            )
            raw = row.get("raw_response") or {}
            out.append(
                {
                    "model": model,
                    "replay_id": replay_id,
                    "item_id": item.item_id,
                    "event_id": item.event_id,
                    "label": item.label,
                    "floor": item.floor,
                    "band": list(item.band),
                    "verdict": row["verdict"],
                    "risk_score": score,
                    "outcome": outcome(item, row),
                    "band_position": position,
                    "band_distance": distance,
                    "scene_audit": answers.get((item.event_id, "scene")),
                    "excluded": item.event_id in excluded,
                    "cell": dict(item.facts["cell"]),
                    "still": str(item.still),
                    "reasoning": raw.get("reasoning") or raw.get("detail"),
                }
            )
    return out


def score_models(
    replays: Sequence[tuple[str, str, Sequence[Row]]],
    items: Mapping[str, Item],
    answers: Mapping[tuple[str, str], str],
    sampled: Sequence[str],
) -> dict[str, Any]:
    """Every model's headline (on every item, and on the audited stills whose scene the owner
    confirmed), slices, and the comparison. `replays` is (model, replay id, rows). An event the
    owner answered no for is a generation error: it leaves every metric (design §4)."""
    audit = audit_summary(answers, sampled)
    excluded = set(audit["generation_errors"])
    confirmed = set(audit["confirmed"])
    models: dict[str, Any] = {}
    kept_by_model: list[tuple[str, Sequence[Row]]] = []
    for model, replay_id, rows in replays:
        kept = [row for row in rows if items[row["item_id"]].event_id not in excluded]
        audited = [row for row in kept if items[row["item_id"]].event_id in confirmed]
        models[model] = {
            "replay_id": replay_id,
            "excluded": len(rows) - len(kept),
            "all": headline(kept, items),
            "audited": headline(audited, items),
            "slices": slices(kept, items),
        }
        kept_by_model.append((model, kept))
    return {"audit": audit, "models": models, "comparison": comparison(kept_by_model, items)}
