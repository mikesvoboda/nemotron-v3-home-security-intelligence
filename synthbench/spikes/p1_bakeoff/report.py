"""P1 report (spec §3.7): aggregates records, groups, measures and the owner's ratings,
proposes a pick per slot, and writes docs/benchmarks/synthbench/p1-bakeoff.md.

    uv run python -m synthbench.spikes.p1_bakeoff.report

Reads <root>/records.jsonl (required), groups.jsonl, measures.jsonl and ratings.json
(each optional). The report holds aggregate metrics only; media stays under <root>.
judge.jsonl (optional, judge.py) adds the VLM judge's section: evidence, never a pick input.
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
VOLUME_MAX_SECONDS = 10.0  # per image at 1080p-equivalent: s/MP x P1080_MP
P1080_MP = 1920 * 1080 / 1e6  # 2.07 MP
COMPOSITOR_MIN_GOOD = 0.5  # both the threat and the identity good rate
COMPOSITOR_MIN_FACES = 8  # of the 15 identity shots, before identity drift counts
CLEAN_SETTLES = frozenset({"dropped", "no_drop"})  # anything else flags the model's VRAM numbers
# A slot whose best eligible model scores 0 (no good rating, no exact plate) proposes nobody:
# for the t2i slots that is spec §3.7's fallback trigger (a prop reference sheet).
BELOW_FLOOR = "none (below floor)"

_CASE_IDS = frozenset(case.id for case in CASES)
_THREAT_ORDER = tuple(case.id for case in CASES if case.id in THREAT_CASES)
_IMAGE_CASE_ORDER = (*(case.id for case in CASES), "identity_reference", "identity")
_ORDER = {model: i for i, model in enumerate(T2I_MODELS + I2V_MODELS)}

SLOT_RULES: dict[str, str] = {
    "t2i_quality": "highest threat good rate; tie: lower median seconds",
    "t2i_volume": (
        f"highest threat good rate among models at <= {VOLUME_MAX_SECONDS:.0f} median seconds "
        f"at 1080p-equivalent (s/MP x {P1080_MP:.2f})"
    ),
    "compositor": (
        f"lowest identity drift among edit models with threat and identity good rates >= "
        f"{COMPOSITOR_MIN_GOOD:.0%} and a face found in >= {COMPOSITOR_MIN_FACES} of 15 shots"
    ),
    "text": "highest plate exact rate; tie: lower mean CER",
    "animator": "highest clip good rate; tie: lower frame drift",
}

# The VLM judge (judge.py) is evidence, never a gate: propose_picks never reads it.
JUDGE_CAVEAT = (
    "judge = claude-flagship (Qwen3.8-Flash-Next); the pipeline's VLM stage is Qwen3VL-4B "
    "(same family), so the judge is evidence, not a gate."
)
JUDGE_KINDS = ("threat", "identity", "clip")  # the case types with a judge_good verdict


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


def _megapixels(rows: list[dict[str, Any]]) -> float | None:
    """The render size in MP (per frame for clips); None for rows without a size."""
    sizes = [row["width"] * row["height"] for row in rows if row.get("width") and row.get("height")]
    return _median([pixels / 1e6 for pixels in sizes])


def _per_mp(seconds: float | None, megapixels: float | None) -> float | None:
    return None if seconds is None or not megapixels else seconds / megapixels


def _good(
    rows: list[dict[str, Any]], ratings: dict[str, dict[str, Any]]
) -> tuple[float | None, int]:
    """Share of `good` among the rated rows, and how many were rated."""
    rated = [ratings.get(row["output"], {}).get("rating") for row in rows]
    hits = [rating == "good" for rating in rated if rating in RATINGS]
    return _rate(hits), len(hits)


def _threat_good(
    rows: list[dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
    refused: frozenset[str] = frozenset(),
) -> tuple[float | None, int]:
    """Share of `good` over threat jobs: the rated scenes (ok outputs not `refused`), plus
    every refusal (rated or not) and every failed job as not good. Unknown (None, 0) while
    none of the scenes is rated."""
    scenes = [row for row in rows if row["ok"] and row["output"] not in refused]
    rated = [
        ratings[row["output"]]["rating"] == "good"
        for row in scenes
        if ratings.get(row["output"], {}).get("rating") in RATINGS
    ]
    if scenes and not rated:
        return None, 0
    hits = rated + [False] * (len(rows) - len(scenes))
    return _rate(hits), len(hits)


def _owl_hit(measure: dict[str, Any]) -> bool:
    first_query_score: float = next(iter(measure["owl"].values()))  # measured in query order
    return first_query_score >= OWL_HIT


def _refusals(
    ok_rows: list[dict[str, Any]], measures: dict[str, dict[str, Any]]
) -> tuple[int, int]:
    """(refused, measured): the ok outputs measure.py flagged `refused`, and those it checked
    (a measure row from before refusal detection has no `refused` and is not counted)."""
    flags = [
        bool(measures[r["output"]]["refused"])
        for r in ok_rows
        if "refused" in measures.get(r["output"], {})
    ]
    return sum(flags), len(flags)


def _refusal_cases(
    ok_rows: list[dict[str, Any]], measures: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """The R1 form: each case (cases.py order, then identity) where the model's refusals are
    at least half its measured outputs."""
    found: list[dict[str, Any]] = []
    for case in _IMAGE_CASE_ORDER:
        refused, n = _refusals([row for row in ok_rows if row["case"] == case], measures)
        if refused and 2 * refused >= n:
            found.append({"case": case, "refused": refused, "n": n})
    return found


def _threat_cases(
    rows: list[dict[str, Any]],
    measures: dict[str, dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
    refused: frozenset[str] = frozenset(),
) -> dict[str, dict[str, Any]]:
    """Per threat case the model rendered: good rate (as _threat_good), OWL hit rate over
    the scenes, and the refusals over the measured outputs."""
    cases: dict[str, dict[str, Any]] = {}
    for case in _THREAT_ORDER:
        case_rows = [row for row in rows if row["case"] == case]
        if not case_rows:
            continue
        good, good_n = _threat_good(case_rows, ratings, refused)
        owl = [
            _owl_hit(measures[row["output"]])
            for row in case_rows
            if row["ok"]
            and row["output"] not in refused
            and measures.get(row["output"], {}).get("owl")
        ]
        case_refused, measured = _refusals([row for row in case_rows if row["ok"]], measures)
        cases[case] = {
            "good_rate": good,
            "good_n": good_n,
            "owl_hit_rate": _rate(owl),
            "owl_n": len(owl),
            "refused": case_refused,
            "refused_n": measured,
        }
    return cases


def _identity(
    ok_rows: list[dict[str, Any]],
    measures: dict[str, dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
    refused: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Drift and faces over the identity shots that are scenes: a refused shot is left out,
    and a refused reference leaves no reference to drift from."""
    reference: list[float] | None = None
    for row in ok_rows:
        if row["case"] == "identity_reference" and row["output"] not in refused:
            reference = measures.get(row["output"], {}).get("face")
    drifts: list[float] = []
    faces = no_face = 0
    for row in ok_rows:
        measure = measures.get(row["output"], {})
        if row["case"] != "identity" or "face" not in measure or row["output"] in refused:
            continue
        if measure["face"] is None:
            no_face += 1
            continue
        faces += 1
        if reference is not None:
            drifts.append(cosine_distance(reference, measure["face"]))
    good, good_n = _good([row for row in ok_rows if row["case"] == "identity"], ratings)
    return {
        "identity_drift_median": _median(drifts),
        "identity_faces": faces,
        "identity_no_face": no_face,
        "identity_good_rate": good,  # the reference (case identity_reference) is not rated here
        "identity_good_n": good_n,
    }


def _image_stats(
    rows: list[dict[str, Any]],
    measures: dict[str, dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
    refused: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    ok_rows = [row for row in rows if row["ok"]]
    owl_hits: list[bool] = []
    plates: list[dict[str, Any]] = []
    for row in ok_rows:
        measure = measures.get(row["output"], {})
        if row["case"] in _CASE_IDS and measure.get("owl") and row["output"] not in refused:
            owl_hits.append(_owl_hit(measure))
        if "plate_exact" in measure:
            plates.append(measure)
    cers = [p["plate_cer"] for p in plates if p.get("plate_cer") is not None]
    median = _warm_median_seconds(ok_rows)
    megapixels = _megapixels(rows)
    per_mp = _per_mp(median, megapixels)
    threat_good, threat_n = _threat_good(
        [row for row in rows if row["case"] in THREAT_CASES], ratings, refused
    )
    refusal_count, refusal_n = _refusals(ok_rows, measures)
    return {
        "refused": refusal_count,
        "refusal_n": refusal_n,
        "refusal_rate": refusal_count / refusal_n if refusal_n else None,
        "refusal_cases": _refusal_cases(ok_rows, measures),
        "median_seconds": median,
        "megapixels": megapixels,
        "seconds_per_mp": per_mp,
        "median_seconds_1080p": None if per_mp is None else per_mp * P1080_MP,
        "threat_good_rate": threat_good,
        "threat_good_n": threat_n,
        "owl_hit_rate": _rate(owl_hits),
        "owl_hit_n": len(owl_hits),
        "plate_exact_rate": _rate([bool(p["plate_exact"]) for p in plates]),
        "plate_n": len(plates),
        "plate_mean_cer": statistics.fmean(cers) if cers else None,
        "threat_cases": _threat_cases(rows, measures, ratings, refused),
    } | _identity(ok_rows, measures, ratings, refused)


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
    median = _warm_median_seconds(ok_rows)
    megapixels = _megapixels(rows)  # per frame
    frames = _median([row["frames"] for row in rows if row.get("frames")])
    frame_mp = None if megapixels is None or frames is None else megapixels * frames
    good, good_n = _good(ok_rows, ratings)
    return {
        "median_seconds_per_clip": median,
        "megapixels": megapixels,
        "frames": frames,
        "seconds_per_mp": _per_mp(median, frame_mp),  # per frame-megapixel
        "frame_drift_median": _median(drifts),
        "clip_good_rate": good,
        "clip_good_n": good_n,
    }


def cohen_kappa(*, tp: int, fp: int, fn: int, tn: int) -> float | None:
    """Cohen's kappa of two binary raters from their confusion counts; None when chance
    agreement is total (both raters used one class only) or there are no cells."""
    n = tp + fp + fn + tn
    chance = (tp + fn) * (tp + fp) + (fp + tn) * (fn + tn)  # x n^2
    if not n or chance == n * n:
        return None
    observed = (tp + tn) / n
    return (observed - chance / (n * n)) / (1 - chance / (n * n))


def _confusion(pairs: list[tuple[bool, bool]]) -> dict[str, Any]:
    """(owner good, judge good) pairs: counts, agreement and Cohen's kappa."""
    tp = sum(1 for owner, judge in pairs if owner and judge)
    fn = sum(1 for owner, judge in pairs if owner and not judge)
    fp = sum(1 for owner, judge in pairs if not owner and judge)
    tn = len(pairs) - tp - fn - fp
    return {
        "n": len(pairs),
        "agreement": (tp + tn) / len(pairs) if pairs else None,
        "kappa": cohen_kappa(tp=tp, fp=fp, fn=fn, tn=tn),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
    }


def judge_calibration(
    ratings: dict[str, dict[str, Any]],
    judge: Iterable[dict[str, Any]],
    refused: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Judge vs owner over the cells the owner rated and the judge gave a verdict on, the
    `refused` outputs left out (no scene to agree on): owner `good` is positive,
    `partial`/`fail` negative, against the judge's `judge_good`. Overall and per
    JUDGE_KINDS; `rated` counts every rating, judged or not."""
    pairs: dict[str, list[tuple[bool, bool]]] = {kind: [] for kind in ("overall", *JUDGE_KINDS)}
    for output, row in latest(judge).items():
        rating = ratings.get(output, {}).get("rating")
        derived = row.get("derived") or {}
        if rating not in RATINGS or row.get("error") or derived.get("judge_good") is None:
            continue
        if output in refused:  # a safety card: no scene for the owner and judge to agree on
            continue
        pair = (rating == "good", bool(derived["judge_good"]))
        pairs["overall"].append(pair)
        if derived.get("case_type") in JUDGE_KINDS:
            pairs[derived["case_type"]].append(pair)
    rated = sum(1 for value in ratings.values() if value.get("rating") in RATINGS)
    return {"rated": rated, "kinds": {kind: _confusion(p) for kind, p in pairs.items()}}


def _judge_stats(
    rows: list[dict[str, Any]],
    judged: dict[str, dict[str, Any]],
    refused: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """One model's judge verdicts over its ok outputs that are scenes (latest judge row per
    output): a refused output is left out of every judge column."""
    found = [
        judged[row["output"]]
        for row in rows
        if row["ok"] and row["output"] in judged and row["output"] not in refused
    ]
    derived = [j["derived"] for j in found if not j.get("error") and j.get("derived")]
    good = [bool(d["judge_good"]) for d in derived if d.get("judge_good") is not None]
    props = [bool(d["prop_match"]) for d in derived if d.get("prop_match") is not None]
    realistic = [bool(d.get("realistic")) for d in derived]
    artifacts = [d.get("artifact_count") or 0 for d in derived]
    return {
        "judge_n": len(derived),
        "judge_errors": sum(1 for j in found if j.get("error")),
        "judge_good_rate": _rate(good),
        "judge_good_n": len(good),
        "judge_prop_match_rate": _rate(props),
        "judge_prop_match_n": len(props),
        "judge_realistic_rate": _rate(realistic),
        "judge_realistic_n": len(realistic),
        "judge_artifact_mean": statistics.fmean(artifacts) if artifacts else None,
        "judge_artifact_n": len(artifacts),
    }


def _judge_summary(
    by_model: dict[str, list[dict[str, Any]]],
    ratings: dict[str, dict[str, Any]],
    judge: Iterable[dict[str, Any]],
    refused: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """The VLM judge's evidence: per-model verdicts and the calibration, refusals left out.
    Never a pick input."""
    judged = latest(judge)
    return {
        "rows": len(judged),
        "judge_models": sorted(
            {str(r["judge_model"]) for r in judged.values() if r.get("judge_model")}
        ),
        "models": {
            model: _judge_stats(by_model[model], judged, refused)
            for model in sorted(by_model, key=_model_order)
        },
        "calibration": judge_calibration(ratings, judged.values(), refused),
    }


def summarize(
    records: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    measures: list[dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
    judge: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Per image model (`models`) and per clip model (`clip_models`) metrics, and the VLM
    judge's evidence (`judge`, from judge.jsonl's rows; none by default). An output
    measure.py flagged `refused` (the model's safety card) is not a scene: it counts as not
    good in the threat good rates and is left out of OWL, identity drift and the judge."""
    by_model: dict[str, list[dict[str, Any]]] = {}
    for row in latest(records).values():
        by_model.setdefault(row["model"], []).append(row)
    groups_by_model: dict[str, list[dict[str, Any]]] = {}
    for group in groups:  # a resumed run appends a row per model group
        groups_by_model.setdefault(group["model"], []).append(group)
    by_output = latest(measures)
    refused = frozenset(output for output, m in by_output.items() if m.get("refused"))
    images: dict[str, dict[str, Any]] = {}
    clips: dict[str, dict[str, Any]] = {}
    for model in sorted(by_model, key=_model_order):
        vram = _vram(groups_by_model.get(model, []))
        image_rows = [row for row in by_model[model] if row["kind"] != "i2v"]
        clip_rows = [row for row in by_model[model] if row["kind"] == "i2v"]
        if image_rows:
            images[model] = (
                _counts(image_rows) | vram | _image_stats(image_rows, by_output, ratings, refused)
            )
        if clip_rows:
            clips[model] = _counts(clip_rows) | vram | _clip_stats(clip_rows, by_output, ratings)
    return {
        "models": images,
        "clip_models": clips,
        "judge": _judge_summary(by_model, ratings, judge, refused),
    }


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


def _at_least(value: float | None, floor: float) -> bool:
    return value is not None and value >= floor


def fallback_cases(summary: dict[str, Any]) -> list[str]:
    """Threat cases where no model has a single `good` (failed jobs and refusals count as
    not good): spec §3.7's prop reference sheet candidates. A case waits while any model's
    rate for it is unknown (none of its scenes rated), so a model that refused the case
    outright cannot list it before the others are rated."""
    cases: list[str] = []
    for case in _THREAT_ORDER:
        rates = [
            stats["threat_cases"][case]["good_rate"]
            for stats in summary["models"].values()
            if case in stats["threat_cases"]
        ]
        if rates and None not in rates and max(rates) <= 0:
            cases.append(case)
    return cases


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
                s["median_seconds_1080p"] is not None
                and s["median_seconds_1080p"] <= VOLUME_MAX_SECONDS
            ),
        ),
        "compositor": _best(
            images,
            "identity_drift_median",
            higher=False,
            where=lambda m, s: (
                m in EDIT_MODELS
                and _at_least(s["threat_good_rate"], COMPOSITOR_MIN_GOOD)
                and _at_least(s["identity_good_rate"], COMPOSITOR_MIN_GOOD)
                and s["identity_faces"] >= COMPOSITOR_MIN_FACES
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


def _fmt_n(value: Any, spec: str, n: int) -> str:
    """A rate (or median) with how many outputs it is over."""
    return "n/a" if value is None else f"{_fmt(value, spec)} (n={n})"


def _flags(flags: list[str]) -> str:
    return ", ".join(flags) if flags else "-"


def _case_cell(stats: dict[str, Any] | None) -> str:
    if stats is None:
        return "-"
    good = _fmt_n(stats["good_rate"], "%", stats["good_n"])
    owl = _fmt_n(stats["owl_hit_rate"], "%", stats["owl_n"])
    refused = f" · refused {stats['refused']}/{stats['refused_n']}" if stats["refused"] else ""
    return f"good {good} · OWL {owl}{refused}"


def _refused_cell(stats: dict[str, Any]) -> str:
    if not stats["refusal_n"]:
        return "n/a"
    return f"{stats['refused']}/{stats['refusal_n']} ({stats['refusal_rate']:.0%})"


def _refusal_lines(summary: dict[str, Any]) -> list[str]:
    """Per model, the cases it refused at least half the time (R1 evidence)."""
    lines = [
        "Refusals (R1): cases where a model painted its safety card instead of the scene for "
        "at least half its measured outputs:",
        "",
    ]
    found = [
        f"- {model}: "
        + ", ".join(f"{c['case']} {c['refused']}/{c['n']}" for c in stats["refusal_cases"])
        for model, stats in summary["models"].items()
        if stats["refusal_cases"]
    ]
    return [*lines, *(found or ["- none"])]


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
            _refused_cell(s),
            _fmt(s["median_seconds"], ".1f"),
            _fmt(s["megapixels"], ".2f"),
            _fmt(s["seconds_per_mp"], ".1f"),
            _fmt(s["peak_vram_gib"], ".1f"),
            _fmt(s["net_peak_vram_gib"], ".1f"),
            _flags(s["vram_flags"]),
            _fmt_n(s["threat_good_rate"], "%", s["threat_good_n"]),
            _fmt_n(s["owl_hit_rate"], "%", s["owl_hit_n"]),
            _fmt_n(s["plate_exact_rate"], "%", s["plate_n"]),
            _fmt(s["plate_mean_cer"], ".2f"),
            _fmt_n(s["identity_good_rate"], "%", s["identity_good_n"]),
            _fmt_n(s["identity_drift_median"], ".3f", s["identity_faces"]),
            str(s["identity_no_face"]),
        ]
        for model, s in summary["models"].items()
    ]
    lines += _table(
        [
            "model",
            "ok",
            "failed",
            "refused",
            "median s",
            "MP",
            "s/MP",
            "peak VRAM GiB",
            "net peak GiB",
            "VRAM flags",
            "threat good",
            "OWL hit",
            "plate exact",
            "plate CER",
            "identity good",
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
            _fmt(s["megapixels"], ".2f"),
            _fmt(s["frames"], ".0f"),
            _fmt(s["seconds_per_mp"], ".2f"),
            _fmt(s["peak_vram_gib"], ".1f"),
            _fmt(s["net_peak_vram_gib"], ".1f"),
            _flags(s["vram_flags"]),
            _fmt(s["frame_drift_median"], ".3f"),
            _fmt_n(s["clip_good_rate"], "%", s["clip_good_n"]),
        ]
        for model, s in summary["clip_models"].items()
    ]
    lines += _table(
        [
            "model",
            "ok",
            "failed",
            "median s/clip",
            "MP/frame",
            "frames",
            "s per frame-MP",
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
        "- **MP**: the model's native render size in megapixels (per frame for clips). "
        "**s/MP**: median seconds per megapixel; for clips, per frame-megapixel (median "
        f"seconds / (MP x frames)). The `t2i_volume` bar applies to the 1080p-equivalent time, "
        f"s/MP x {P1080_MP:.2f}.",
        "- **peak VRAM GiB**: the GPU's `memory.used` peak during the model group, every "
        "process on the GPU included. **net peak GiB**: that peak minus the baseline read "
        "after ComfyUI's `/free` settled, the max over the model's groups.",
        "- **VRAM flags**: how `/free` settled when it was not clean (`timeout`: the peak may "
        "include the previous model; `unreadable`: no baseline).",
        "- **(n=...)**: how many outputs a rate or median is over.",
        "- **refused**: ok images whose OCR text is the model's safety card (\"Image blocked "
        'by safety filter"), over the images measured for it. A refusal is not a scene: it '
        "counts as not good in **threat good** and is left out of **OWL hit**, **identity "
        "drift**, **no face** and the judge's columns.",
        "- **threat good**: share of `good` over the model's threat jobs: the owner's rated "
        "scenes, plus every refusal (rated or not) and every failed job as not good (n/a "
        "until a threat scene is rated). **identity good** / **clip good**: share of `good` "
        "among the owner's rated identity shots (the reference not counted) / clips.",
        f"- **OWL hit**: share of case images whose first OWLv2 query scores >= {OWL_HIT:.2f}. "
        "**plate**: EasyOCR against the `legible_plate` target, compared on its "
        "alphanumerics only.",
        "- **identity drift**: median facenet cosine distance of the identity shots to the "
        "model's own reference portrait, over the shots where a face was found (its n); "
        "**no face**: shots where none was.",
        "- OWLv2, EasyOCR and facenet measure every image (and clip frame) resized, aspect "
        "kept, to about 1.03 MP (1344x768, the smallest native size).",
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
        "## Threat props per case",
        "",
    ]
    models = list(summary["models"])
    lines += _table(
        ["case", *models],
        [
            [case, *(_case_cell(summary["models"][m]["threat_cases"].get(case)) for m in models)]
            for case in _THREAT_ORDER
            if any(case in stats["threat_cases"] for stats in summary["models"].values())
        ],
    )
    lines += [
        "",
        "§3.7 fallback candidates (prop reference sheet): "
        f"{', '.join(fallback_cases(summary)) or 'none'}",
        "",
        "A case is a candidate when no model has a single `good` for it (failed jobs and "
        "refusals count as not good). It waits while any model's rate for it is n/a (none of "
        "its scenes rated yet).",
        "",
        *_refusal_lines(summary),
        "",
        "## Risks R1-R3 outcome",
        "",
        "- **R1** (threat props): _TODO (Task 8): which threat props each model could or "
        "could not render (start from the per-case table, its fallback candidates and the "
        "refusals)._",
        "- **R2** (ComfyUI on arm64/sm_103): _TODO (Task 8): held, or the fallback used._",
        "- **R3** (candidate facts): _TODO (Task 8): existence, sizes and gating confirmed._",
        "",
    ]
    lines += _judge_markdown(summary.get("judge"))
    return "\n".join(lines)


def _judge_markdown(judge: dict[str, Any] | None) -> list[str]:
    """The VLM judge section: per-model verdict columns and the judge-vs-owner calibration."""
    lines = ["## VLM judge (evidence, not a gate)", "", JUDGE_CAVEAT, ""]
    if not judge or not judge["rows"]:
        return [
            *lines,
            "No judge rows yet: with the flagship up, run "
            "`uv run python -m synthbench.spikes.p1_bakeoff.judge` (writes <root>/judge.jsonl).",
            "",
        ]
    lines += _table(
        ["model", "judged", "errors", "judge good", "prop match", "realistic", "artifacts"],
        [
            [
                model,
                str(s["judge_n"]),
                str(s["judge_errors"]),
                _fmt_n(s["judge_good_rate"], "%", s["judge_good_n"]),
                _fmt_n(s["judge_prop_match_rate"], "%", s["judge_prop_match_n"]),
                _fmt_n(s["judge_realistic_rate"], "%", s["judge_realistic_n"]),
                _fmt_n(s["judge_artifact_mean"], ".2f", s["judge_artifact_n"]),
            ]
            for model, s in judge["models"].items()
        ],
    )
    names = ", ".join(f"`{name}`" for name in judge.get("judge_models", [])) or "n/a"
    lines += [
        "",
        f"- Judge model id in judge.jsonl: {names}.",
        "- The judge sees only the pixels (an image, or a clip's first, middle and last "
        "frames) and one fixed instruction, never the prompt or the case, and fills a fixed "
        "JSON description; `judge.py`'s `derive` compares it with the case's known facts. "
        "`propose_picks` never reads it.",
        "- **judged** / **errors**: ok outputs with a judge answer / with a failed judge call "
        "(timeout, the judge's own refusal, bad JSON). **judge good**: threat cases: the prop "
        "named, photorealistic, not assessed benign (the hazards `child_alone_pool` and "
        "`smoke_from_eave` may be); identity shots: the case's lighting, photorealistic, at "
        "least one person; clips: photorealistic, no artifacts. The plate case has none "
        "(plate CER is its measure). **prop match**: threat cases only; a term matches when "
        "all its words are in one described item, in any order; `pried_window` and "
        "`forced_door` count only words for the damage, never a bare window or door. "
        "**realistic**: the judge said photorealistic `yes`. **artifacts**: mean flaws listed "
        "per output. Outputs the image model refused (its safety card) are left out of every "
        "column and of the calibration.",
        "",
        "### Judge vs owner",
        "",
    ]
    calibration = judge["calibration"]
    if not calibration["rated"]:
        return [*lines, "no owner ratings yet", ""]
    if not calibration["kinds"]["overall"]["n"]:
        return [*lines, "No rated cell has a judge verdict yet.", ""]
    lines += _table(
        ["cells", "n", "agreement", "Cohen's kappa", "TP", "FN", "FP", "TN"],
        [
            [
                kind,
                str(c["n"]),
                _fmt(c["agreement"], "%"),
                _fmt(c["kappa"], ".2f"),
                *(str(c[k]) for k in ("tp", "fn", "fp", "tn")),
            ]
            for kind, c in calibration["kinds"].items()
        ],
    )
    return [
        *lines,
        "",
        "Over the cells the owner rated and the judge gave a verdict on: owner `good` is "
        "positive, `partial` or `fail` negative, against **judge good**. TP: both good; FN: "
        "owner good, judge not; FP: judge good, owner not; TN: neither. Kappa is n/a when both "
        "raters used one class only.",
        "",
    ]


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
        judge=read_jsonl(root / "judge.jsonl", missing_ok=True),
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
