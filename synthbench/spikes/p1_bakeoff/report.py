"""P1 report (spec §3.7): aggregates records, groups, measures and the owner's ratings,
proposes a pick per slot, and writes docs/benchmarks/synthbench/p1-bakeoff.md.

    uv run python -m synthbench.spikes.p1_bakeoff.report

Reads <root>/records.jsonl (required), groups.jsonl, measures.jsonl and ratings.json
(each optional). The report holds aggregate metrics only; media stays under <root>.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from synthbench.spikes.p1_bakeoff.cases import CASES, EDIT_MODELS, I2V_MODELS, T2I_MODELS
from synthbench.spikes.p1_bakeoff.measure import cosine_distance

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO_ROOT / "docs/benchmarks/synthbench/p1-bakeoff.md"

THREAT_CASES = frozenset(
    {
        "handgun_in_hand",
        "knife",
        "crowbar_at_door",
        "balaclava_ir_night",
        "forced_door",
        "pried_window",
        "child_alone_pool",
        "smoke_from_eave",
    }
)
RATINGS = ("good", "partial", "fail")
OWL_HIT = 0.30  # a case image "shows" its prop when OWLv2 scores the first query this high
MIN_OK_SHARE = 0.5  # a model with fewer ok jobs than this is never picked
VOLUME_MAX_SECONDS = 10.0
COMPOSITOR_MIN_GOOD = 0.5
CLEAN_SETTLES = frozenset({"dropped", "no_drop"})  # anything else flags the model's VRAM numbers
# A slot whose best eligible model scores 0 (no good rating, no exact plate) proposes nobody:
# for the t2i slots that is spec §3.7's fallback trigger (a prop reference sheet).
BELOW_FLOOR = "none (below floor)"

_CASE_IDS = frozenset(case.id for case in CASES)
_ORDER = {model: i for i, model in enumerate(T2I_MODELS + I2V_MODELS)}

SLOT_RULES: dict[str, str] = {
    "t2i_quality": "highest threat good rate; tie: lower median seconds",
    "t2i_volume": (
        f"highest threat good rate among models at <= {VOLUME_MAX_SECONDS:.0f} median seconds"
    ),
    "compositor": (
        f"lowest identity drift among edit models with threat good rate >= "
        f"{COMPOSITOR_MIN_GOOD:.0%}"
    ),
    "text": "highest plate exact rate; tie: lower mean CER",
    "animator": "highest clip good rate; tie: lower frame drift",
}


def read_jsonl(path: Path, *, missing_ok: bool = False) -> list[dict[str, Any]]:
    if missing_ok and not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def latest(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Rows keyed by `output`: a resumed job's last row wins, at its first row's position."""
    return {row["output"]: row for row in rows}


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _rate(hits: list[bool]) -> float | None:
    return sum(hits) / len(hits) if hits else None


def _gib(mib: float) -> float:
    return round(mib / 1024, 1)


def _model_order(model: str) -> tuple[int, str]:
    return _ORDER.get(model, len(_ORDER)), model


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    ok = sum(1 for row in rows if row["ok"])
    return {"ok": ok, "failed": len(rows) - ok}


def _warm_median_seconds(ok_rows: list[dict[str, Any]]) -> float | None:
    """Median seconds without the cold job that loaded the model (all jobs if only cold ones)."""
    timed = [row for row in ok_rows if row.get("seconds") is not None]
    warm = [row["seconds"] for row in timed if not row.get("cold", False)]
    return _median(warm or [row["seconds"] for row in timed])


def _vram(groups: list[dict[str, Any]]) -> dict[str, Any]:
    peaks = [g["peak_vram_mib"] for g in groups if g.get("peak_vram_mib") is not None]
    nets = [
        g["peak_vram_mib"] - g["baseline_vram_mib"]
        for g in groups
        if g.get("peak_vram_mib") is not None and g.get("baseline_vram_mib") is not None
    ]
    flags = {g["settle"] for g in groups if g.get("settle")} - CLEAN_SETTLES
    return {
        "peak_vram_gib": _gib(max(peaks)) if peaks else None,
        "net_peak_vram_gib": _gib(max(nets)) if nets else None,
        "vram_flags": sorted(flags),
    }


def _good_rate(rows: list[dict[str, Any]], ratings: dict[str, dict[str, Any]]) -> float | None:
    rated = [ratings.get(row["output"], {}).get("rating") for row in rows]
    return _rate([rating == "good" for rating in rated if rating in RATINGS])


def _identity(ok_rows: list[dict[str, Any]], measures: dict[str, dict[str, Any]]) -> dict[str, Any]:
    reference: list[float] | None = None
    for row in ok_rows:
        if row["case"] == "identity_reference":
            reference = measures.get(row["output"], {}).get("face")
    drifts: list[float] = []
    no_face = 0
    for row in ok_rows:
        measure = measures.get(row["output"], {})
        if row["case"] != "identity" or "face" not in measure:
            continue
        if measure["face"] is None:
            no_face += 1
        elif reference is not None:
            drifts.append(cosine_distance(reference, measure["face"]))
    return {"identity_drift_median": _median(drifts), "identity_no_face": no_face}


def _image_stats(
    rows: list[dict[str, Any]],
    measures: dict[str, dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ok_rows = [row for row in rows if row["ok"]]
    owl_hits: list[bool] = []
    plates: list[dict[str, Any]] = []
    for row in ok_rows:
        measure = measures.get(row["output"], {})
        if row["case"] in _CASE_IDS and measure.get("owl"):
            first_query_score = next(iter(measure["owl"].values()))  # measured in query order
            owl_hits.append(first_query_score >= OWL_HIT)
        if "plate_exact" in measure:
            plates.append(measure)
    cers = [p["plate_cer"] for p in plates if p.get("plate_cer") is not None]
    return {
        "median_seconds": _warm_median_seconds(ok_rows),
        "threat_good_rate": _good_rate(
            [row for row in ok_rows if row["case"] in THREAT_CASES], ratings
        ),
        "owl_hit_rate": _rate(owl_hits),
        "plate_exact_rate": _rate([bool(p["plate_exact"]) for p in plates]),
        "plate_mean_cer": statistics.fmean(cers) if cers else None,
    } | _identity(ok_rows, measures)


def _clip_stats(
    rows: list[dict[str, Any]],
    measures: dict[str, dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ok_rows = [row for row in rows if row["ok"]]
    drifts = [
        measures[row["output"]]["frame_drift_max"]
        for row in ok_rows
        if measures.get(row["output"], {}).get("frame_drift_max") is not None
    ]
    return {
        "median_seconds_per_clip": _warm_median_seconds(ok_rows),
        "frame_drift_median": _median(drifts),
        "clip_good_rate": _good_rate(ok_rows, ratings),
    }


def summarize(
    records: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    measures: list[dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Per image model (`models`) and per clip model (`clip_models`) metrics."""
    by_model: dict[str, list[dict[str, Any]]] = {}
    for row in latest(records).values():
        by_model.setdefault(row["model"], []).append(row)
    groups_by_model: dict[str, list[dict[str, Any]]] = {}
    for group in groups:  # a resumed run appends a row per model group
        groups_by_model.setdefault(group["model"], []).append(group)
    by_output = latest(measures)
    images: dict[str, dict[str, Any]] = {}
    clips: dict[str, dict[str, Any]] = {}
    for model in sorted(by_model, key=_model_order):
        vram = _vram(groups_by_model.get(model, []))
        image_rows = [row for row in by_model[model] if row["kind"] != "i2v"]
        clip_rows = [row for row in by_model[model] if row["kind"] == "i2v"]
        if image_rows:
            images[model] = (
                _counts(image_rows) | vram | _image_stats(image_rows, by_output, ratings)
            )
        if clip_rows:
            clips[model] = _counts(clip_rows) | vram | _clip_stats(clip_rows, by_output, ratings)
    return {"models": images, "clip_models": clips}


def _eligible(stats: dict[str, Any]) -> bool:
    ok: int = stats["ok"]
    failed: int = stats["failed"]
    return ok + failed > 0 and ok / (ok + failed) >= MIN_OK_SHARE


def _best(
    table: dict[str, dict[str, Any]],
    metric: str,
    *,
    higher: bool = True,
    tiebreak: str | None = None,
    where: Callable[[str, dict[str, Any]], bool] = lambda _model, _stats: True,
) -> str:
    """The eligible model with the best `metric`; a tie goes to the lower `tiebreak`.

    A higher-is-better metric must beat 0 (BELOW_FLOOR otherwise); a lower-is-better one
    (identity drift) relies on the caller's `where` floor.
    """
    candidates = [
        (model, stats)
        for model, stats in table.items()
        if _eligible(stats) and stats.get(metric) is not None and where(model, stats)
    ]
    if not candidates:
        return "none"

    def key(item: tuple[str, dict[str, Any]]) -> tuple[float, float, str]:
        model, stats = item
        tie = stats.get(tiebreak) if tiebreak else None
        primary = -stats[metric] if higher else stats[metric]
        return primary, math.inf if tie is None else tie, model

    model, stats = min(candidates, key=key)
    if higher and stats[metric] <= 0:
        return BELOW_FLOOR
    return model


def propose_picks(summary: dict[str, Any]) -> dict[str, str]:
    """One model per slot (SLOT_RULES); "none" when no eligible model has the metric, and
    BELOW_FLOOR when the best one scores 0."""
    images, clips = summary["models"], summary["clip_models"]
    return {
        "t2i_quality": _best(images, "threat_good_rate", tiebreak="median_seconds"),
        "t2i_volume": _best(
            images,
            "threat_good_rate",
            tiebreak="median_seconds",
            where=lambda _m, s: (
                s["median_seconds"] is not None and s["median_seconds"] <= VOLUME_MAX_SECONDS
            ),
        ),
        "compositor": _best(
            images,
            "identity_drift_median",
            higher=False,
            where=lambda m, s: (
                m in EDIT_MODELS
                and s["threat_good_rate"] is not None
                and s["threat_good_rate"] >= COMPOSITOR_MIN_GOOD
            ),
        ),
        "text": _best(images, "plate_exact_rate", tiebreak="plate_mean_cer"),
        "animator": _best(clips, "clip_good_rate", tiebreak="frame_drift_median"),
    }


def _fmt(value: Any, spec: str = "") -> str:
    if value is None:
        return "n/a"
    if spec == "%":
        return f"{value:.0%}"
    return format(value, spec)


def _flags(flags: list[str]) -> str:
    return ", ".join(flags) if flags else "-"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + " --- |" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def to_markdown(
    summary: dict[str, Any],
    picks: dict[str, str],
    *,
    date: str | None = None,
    commit: str | None = None,
    root: str = "/export/synthbench/p1",
) -> str:
    lines = [
        "# Synthbench P1 bake-off",
        "",
        f"- Date: {date or 'n/a'}",
        f"- Commit: {commit or 'n/a'}",
        f"- Corpus: aggregate metrics only; media stays in {root}",
        "- Generated by `uv run python -m synthbench.spikes.p1_bakeoff.report` "
        "(spec §3.7, plan Task 8).",
        "",
        "## Image models",
        "",
    ]
    image_rows = [
        [
            model,
            str(s["ok"]),
            str(s["failed"]),
            _fmt(s["median_seconds"], ".1f"),
            _fmt(s["peak_vram_gib"], ".1f"),
            _fmt(s["net_peak_vram_gib"], ".1f"),
            _flags(s["vram_flags"]),
            _fmt(s["threat_good_rate"], "%"),
            _fmt(s["owl_hit_rate"], "%"),
            _fmt(s["plate_exact_rate"], "%"),
            _fmt(s["plate_mean_cer"], ".2f"),
            _fmt(s["identity_drift_median"], ".3f"),
            str(s["identity_no_face"]),
        ]
        for model, s in summary["models"].items()
    ]
    lines += _table(
        [
            "model",
            "ok",
            "failed",
            "median s",
            "peak VRAM GiB",
            "net peak GiB",
            "VRAM flags",
            "threat good",
            "OWL hit",
            "plate exact",
            "plate CER",
            "identity drift",
            "no face",
        ],
        image_rows,
    )
    lines += ["", "## Clip models", ""]
    clip_rows = [
        [
            model,
            str(s["ok"]),
            str(s["failed"]),
            _fmt(s["median_seconds_per_clip"], ".1f"),
            _fmt(s["peak_vram_gib"], ".1f"),
            _fmt(s["net_peak_vram_gib"], ".1f"),
            _flags(s["vram_flags"]),
            _fmt(s["frame_drift_median"], ".3f"),
            _fmt(s["clip_good_rate"], "%"),
        ]
        for model, s in summary["clip_models"].items()
    ]
    lines += _table(
        [
            "model",
            "ok",
            "failed",
            "median s/clip",
            "peak VRAM GiB",
            "net peak GiB",
            "VRAM flags",
            "frame drift",
            "clip good",
        ],
        clip_rows,
    )
    lines += [
        "",
        "How to read the tables:",
        "",
        "- **median s**: over ok jobs, leaving out each model group's cold first job (it "
        "includes the model load); a model with only cold jobs falls back to them.",
        "- **peak VRAM GiB**: the GPU's `memory.used` peak during the model group, every "
        "process on the GPU included. **net peak GiB**: that peak minus the baseline read "
        "after ComfyUI's `/free` settled, the max over the model's groups.",
        "- **VRAM flags**: how `/free` settled when it was not clean (`timeout`: the peak may "
        "include the previous model; `unreadable`: no baseline).",
        f"- **threat good** / **clip good**: share of `good` among the owner's rated ok "
        f"outputs. **OWL hit**: share of case images whose first OWLv2 query scores "
        f">= {OWL_HIT:.2f}. **plate**: EasyOCR against the `legible_plate` target.",
        "- **identity drift**: median facenet cosine distance of the identity shots to the "
        "model's own reference portrait; **no face**: shots where no face was found.",
        "",
        "## Proposed picks (owner approves into spec rev 2)",
        "",
    ]
    lines += _table(
        ["slot", "proposed", "rule"],
        [[slot, picks.get(slot, "none"), rule] for slot, rule in SLOT_RULES.items()],
    )
    lines += [
        "",
        f"Models with under {MIN_OK_SHARE:.0%} of their jobs ok are never proposed. "
        "`none` means no eligible model has the metric (nothing rated or measured). "
        f"`{BELOW_FLOOR}` means the best eligible model scored 0: for `t2i_quality` and "
        "`t2i_volume` that is spec §3.7's fallback trigger (a prop reference sheet, then a "
        "LoRA); for `text` and `animator` no model qualifies.",
        "",
        "## Risks R1-R3 outcome",
        "",
        "- **R1** (threat props): _TODO (Task 8): which threat props each model could or "
        "could not render._",
        "- **R2** (ComfyUI on arm64/sm_103): _TODO (Task 8): held, or the fallback used._",
        "- **R3** (candidate facts): _TODO (Task 8): existence, sizes and gating confirmed._",
        "",
    ]
    return "\n".join(lines)


def _commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
    except OSError, subprocess.SubprocessError:
        return None
    return out or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m synthbench.spikes.p1_bakeoff.report")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "p1",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    root: Path = args.root
    ratings_path = root / "ratings.json"
    if ratings_path.exists():
        ratings = json.loads(ratings_path.read_text())
    else:
        sys.stderr.write(f"[p1-report] warning: no {ratings_path}; rated metrics are n/a\n")
        ratings = {}
    summary = summarize(
        read_jsonl(root / "records.jsonl"),
        read_jsonl(root / "groups.jsonl", missing_ok=True),
        read_jsonl(root / "measures.jsonl", missing_ok=True),
        ratings,
    )
    text = to_markdown(
        summary,
        propose_picks(summary),
        date=datetime.now(UTC).date().isoformat(),
        commit=_commit(),
        root=str(root),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    sys.stdout.write(f"{args.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
