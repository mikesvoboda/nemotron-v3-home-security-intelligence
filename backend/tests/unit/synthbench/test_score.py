"""`score` (P5a design §5): S2 and S3 from `s_metrics`, slices, the risk band, the audit's
exclusions and truth error, the comparison, the report and the command."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from synthbench import cli
from synthbench.commands.audit import audit_log
from synthbench.export import vss
from synthbench.score.metrics import (
    MIN_N,
    Item,
    band_position,
    outcome,
    result_rows,
    score_models,
)
from synthbench.score.report import html as render_gallery
from synthbench.score.report import markdown
from synthbench.score.scoring import weights_identity

from backend.evaluation.eval_store import EvalStore
from backend.evaluation.label_import import import_generated_items
from backend.evaluation.levels import floor_for_expected_score
from backend.evaluation.s_metrics import s2_false_positive_rate, s3_recall, wilson_interval
from backend.tests.unit.synthbench import helpers as h

BANDS = {"threat": (70, 95), "suspicious": (30, 59), "hard_negative": (0, 25), "benign": (0, 15)}


def _facts(event_id: str, group: str, **cell: Any) -> dict[str, Any]:
    lo, hi = BANDS[group]
    return {
        "event_id": event_id,
        "corpus_version": h.VERSION,
        "batch": "batch-1",
        "label": group,
        "risk_band": [lo, hi],
        "scene_time": "14:32",
        "cell": {
            "scenario": cell.get("scenario", f"{group}_scene"),
            "group": group,
            "property_type": cell.get("property_type", "suburban_house"),
            "zone": cell.get("zone", "front_door"),
            "camera": cell.get("camera", "doorbell"),
            "lighting": cell.get("lighting", "day"),
            "weather": cell.get("weather", "clear"),
            "artifacts": list(cell.get("artifacts", ())),
        },
        "subjects": [{"id": "S1", "class": "person", "role": "visitor", "attributes": {}}],
        "props": [],
        "still_sha256": "0" * 64,
    }


def _item(event_id: str, group: str, **cell: Any) -> Item:
    lo, hi = BANDS[group]
    category = vss.CATEGORY[group]
    return Item(
        item_id=f"generated:{category}:{event_id}",
        label=vss.CATEGORY_LABEL[category],
        floor=floor_for_expected_score((lo + hi) // 2),
        facts=_facts(event_id, group, **cell),
        still=Path(f"/x/{event_id}/still.jpg"),
    )


def _row(item: Item, score: int | None) -> dict[str, Any]:
    if score is None:
        verdict, raw = "verification_failed", {"error": "VlmSchemaError", "detail": "no JSON"}
    else:
        verdict, raw = (
            ("confirmed" if score >= 30 else "rejected"),
            {"reasoning": f"scored {score}"},
        )
    return {"item_id": item.item_id, "verdict": verdict, "risk_score": score, "raw_response": raw}


def _items(*items: Item) -> dict[str, Item]:
    return {item.item_id: item for item in items}


def test_s2_and_s3_are_s_metrics_own_output_and_outcomes_agree() -> None:
    benign = [_item(f"B-b-{i:03d}", "benign") for i in range(12)]
    threats = [_item(f"B-t-{i:03d}", "threat") for i in range(12)]
    items = _items(*benign, *threats)
    rows = [_row(b, 45 if i < 3 else 10) for i, b in enumerate(benign)]
    rows += [_row(t, 90 if i < 8 else (None if i == 8 else 40)) for i, t in enumerate(threats)]
    headline = score_models([("m", "r", rows)], items, {}, [])["models"]["m"]["all"]
    labels = {i: it.label for i, it in items.items()}
    floors = {i: {"label": it.label, "floor": it.floor} for i, it in items.items()}
    assert headline["s2"] == s2_false_positive_rate(rows, labels)
    assert headline["s3"] == s3_recall(rows, floors)
    outcomes = [outcome(items[row["item_id"]], row) for row in rows]
    assert outcomes.count("false_alarm") == headline["s2"]["fp"] == 3
    assert outcomes.count("hit") == headline["s3"]["all"]["hit"] == 8
    assert outcomes.count("miss") == headline["s3"]["all"]["miss"] == 3
    assert outcomes.count("refused") == headline["s3"]["all"]["refused"] == 1
    assert headline["s2_cell"]["n"] == 12 and headline["s3_cell"]["n"] == 12


def test_a_slice_counts_only_its_items_and_a_small_one_is_insufficient() -> None:
    day = [_item(f"B-b-d{i:02d}", "benign") for i in range(MIN_N)]
    night = [
        _item(f"B-b-n{i:02d}", "benign", lighting="ir_night", artifacts=["noise"]) for i in range(3)
    ]
    rows = [_row(b, 50) for b in night] + [_row(b, 5) for b in day]
    slices = score_models([("m", "r", rows)], _items(*day, *night), {}, [])["models"]["m"]["slices"]
    ir_night = slices["lighting"]["ir_night"]["s2"]
    assert (ir_night["k"], ir_night["n"], ir_night["insufficient"]) == (3, 3, True)
    assert slices["lighting"]["day"]["s2"]["insufficient"] is False
    assert slices["lighting"]["day"]["s3"] is None  # no incidents there
    assert slices["artifacts"]["drawn"]["s2"]["n"] == 3
    assert slices["artifacts"]["none"]["s2"]["n"] == MIN_N


def test_the_risk_band_position_and_distance() -> None:
    threat = _item("B-t-000", "threat")  # band 70-95
    assert band_position(threat, 50) == ("below", 20)
    assert band_position(threat, 80) == ("inside", 0)
    assert band_position(threat, 99) == ("above", 4)
    rows = [_row(threat, 50)]
    band = score_models([("m", "r", rows)], _items(threat), {}, [])["models"]["m"]["all"]["band"]
    assert band["incident"]["below"]["k"] == 1
    assert band["incident"]["mean_distance_below"] == 20


def test_a_scene_answered_no_is_a_generation_error_and_leaves_s2_and_s3() -> None:
    wrong, right, unaudited = (_item(f"B-t-{i:03d}", "threat") for i in range(3))
    items = _items(wrong, right, unaudited)
    answers = {(wrong.event_id, "scene"): "n", (right.event_id, "scene"): "y"}
    sampled = [wrong.event_id, right.event_id, unaudited.event_id]
    rows = [_row(item, 20) for item in (wrong, right, unaudited)]
    metrics = score_models([("m", "r", rows)], items, answers, sampled)
    assert metrics["audit"]["generation_errors"] == [wrong.event_id]
    model = metrics["models"]["m"]
    assert model["excluded"] == 1
    assert model["all"]["s3"]["all"]["n"] == 2  # right and unaudited
    assert model["audited"]["s3"]["all"]["n"] == 1  # right only


def test_truth_error_counts_no_over_answered_and_unclear_apart() -> None:
    sampled = ["E1", "E2", "E3", "E4"]
    answers = {("E1", "people"): "y", ("E2", "people"): "n", ("E3", "people"): "u"}
    audit = score_models([], {}, answers, sampled)["audit"]
    people = audit["questions"]["people"]
    assert (people["answered"], people["yes"], people["no"], people["unclear"]) == (3, 1, 1, 1)
    assert (people["error"]["k"], people["error"]["n"]) == (1, 2)
    assert audit["sampled"] == 4
    assert audit["answered"] == 0  # no scene answers yet


def test_the_comparison_lists_the_misses_one_model_catches() -> None:
    a_only, b_only, both = (_item(f"B-t-{i:03d}", "threat") for i in range(3))
    items = _items(a_only, b_only, both)
    rows_a = [_row(a_only, 90), _row(b_only, 20), _row(both, 90)]
    rows_b = [_row(a_only, 20), _row(b_only, 90), _row(both, 90)]
    pair = score_models([("a", "ra", rows_a), ("b", "rb", rows_b)], items, {}, [])["comparison"][0]
    assert (pair["a"], pair["b"]) == ("a", "b")
    assert (pair["agree"]["k"], pair["agree"]["n"]) == (1, 3)
    assert pair["a_wrong_b_right"] == [b_only.item_id]
    assert pair["b_wrong_a_right"] == [a_only.item_id]


def test_the_markdown_is_aggregate_with_n_intervals_and_insufficient() -> None:
    benign = [_item(f"B-b-{i:03d}", "benign") for i in range(12)]
    few = [_item(f"B-t-{i:03d}", "threat") for i in range(3)]
    rows = [_row(b, 10) for b in benign] + [_row(t, 90) for t in few]
    metrics = score_models([("m", "r", rows)], _items(*benign, *few), {}, [])
    text = markdown(metrics, {"score_id": "S", "replays": [], "export": {}, "audit": {}})
    assert re.search(r"0\.0% \[0\.0-\d+\.\d\] \(n=12\)", text)
    assert "insufficient (n=3)" in text
    assert "generated:" not in text and "B-b-" not in text  # no per-item rows


# ISS-043: cluster bootstrap beside Wilson, and the paired test on the comparison.


def test_headline_carries_a_scenario_cluster_bootstrap_beside_wilson() -> None:
    """Three scenarios, one of them ALL false alarms: Wilson reads the 15 benign
    items as independent; the cluster resample can draw the bad scenario thrice
    and must read wider. The point rate is the same 33.3% either way."""
    groups = [
        [_item(f"B-b-{g}{i:02d}", "benign", scenario=f"s{g}") for i in range(5)]
        for g in range(3)  # s0, s1: 0 flagged; s2: all flagged
    ]
    items = _items(*[i for g in groups for i in g])
    rows = [_row(i, 10) for i in groups[0]] + [_row(i, 10) for i in groups[1]]
    rows += [_row(i, 70) for i in groups[2]]

    cluster = score_models([("m", "r", rows)], items, {}, [])["models"]["m"]["all"]["s2_cluster"]
    assert cluster["point_pct"] == pytest.approx(100 * 5 / 15, abs=1e-3)  # 5/15; 4dp JSON rounding
    assert cluster["clusters"] == 3
    lo, hi = wilson_interval(2, 15)  # pinned on its own in test_s_metrics.py
    assert cluster["ci_pct"][0] < 100 * lo  # the clustered reading is the WIDER one
    assert cluster["ci_pct"][1] > 100 * hi


def test_the_comparison_is_paired_with_mcnemar_and_a_cluster_ci() -> None:
    """The 3-item fixture: one item each arm wins -> discordants 1/1, exact p
    1.0 by hand (two fair-coin draws each side). Pooled hits are 2 for each arm
    over the same 3 shared incidents: dS3 = 0.0 points by hand - the paired
    reading says 'this disagreement is within fair-coin noise', which is the
    whole point of testing the discordants instead of the two rates."""
    a_only, b_only, both = (_item(f"B-t-{i:03d}", "threat") for i in range(3))
    items = _items(a_only, b_only, both)
    rows_a = [_row(a_only, 90), _row(b_only, 20), _row(both, 90)]
    rows_b = [_row(a_only, 20), _row(b_only, 90), _row(both, 90)]
    pair = score_models([("a", "ra", rows_a), ("b", "rb", rows_b)], items, {}, [])["comparison"][0]
    assert pair["s3_discordants"]["only_a"] == 1
    assert pair["s3_discordants"]["only_b"] == 1
    assert pair["s3_discordants"]["p"] == pytest.approx(1.0)
    assert pair["dS3"]["point_pts"] == pytest.approx(0.0)
    assert pair["dS3"]["clusters"] == 1  # every fixture item shares one scenario
    assert pair["s2_discordants"]["only_a"] == 0 and pair["s2_discordants"]["p"] == 1.0
    assert pair["dS2"]["point_pts"] is None  # no benign items: no S2 leg


def test_the_report_prints_the_cluster_interval_and_the_paired_test() -> None:
    benign = [_item(f"B-b-{i:03d}", "benign") for i in range(12)]
    threats = [_item(f"B-t-{i:03d}", "threat") for i in range(12)]
    items = _items(*benign, *threats)
    rows_a = [_row(b, 45 if i < 3 else 10) for i, b in enumerate(benign)]
    rows_a += [_row(t, 90 if i < 8 else 40) for i, t in enumerate(threats)]
    rows_b = [_row(b, 10) for b in benign] + [_row(t, 90) for t in threats]
    metrics = score_models([("a", "ra", rows_a), ("b", "rb", rows_b)], items, {}, [])
    text = markdown(metrics, {"score_id": "S", "replays": [], "export": {}, "audit": {}})
    assert "Clustered S2" in text and "Clustered S3" in text
    assert re.search(r"clustered \d+\.\d% \[-?\d+\.\d+-?\d+\.\d\] \(n=\d+, \d+ scenarios\)", text)
    assert "McNemar p" in text
    assert "dS3 [cluster CI]" in text
    assert "generated:" not in text  # still aggregate


# The command, end to end, over a real export and eval store.


def _world(
    root: Path,
    scores: dict[str, dict[str, int | None]],
    records: dict[str, dict[str, Any]] | None = None,
    scenarios: Mapping[str, str] | None = None,
    split: str | None = None,
) -> list[str]:
    """An export of three threats and twelve benign scenes, imported; one replay per model,
    its `run.json` updated with `records[model]`.

    `scenarios` overrides an event's scenario name (the default names one scenario per group).
    `split` records a dev/holdout split on that export, in the store as well as on disk:
    `"recorded"` is the honest pair, the other modes are the drift `score` has to catch — see
    `_record_split`. A run.json for a split export carries the digest the replay measured under
    (Task 4's fields), which `records[model]` may still override.
    """
    events = [(f"B-t-{i:03d}", "threat") for i in range(3)]
    events += [(f"B-b-{i:03d}", "benign") for i in range(12)]
    export = root / "exports" / h.VERSION / "vss"
    for event_id, group in events:
        facts = _facts(event_id, group, scenario=(scenarios or {}).get(event_id, f"{group}_scene"))
        labels = {
            "category": vss.CATEGORY[group],
            "risk": {"min_score": facts["risk_band"][0], "max_score": facts["risk_band"][1]},
            "timestamp": "2026-04-15T14:32:00-04:00",
            "synthbench": facts,
        }
        files = {
            vss.LABELS_FILE: json.dumps(labels).encode(),
            vss.STILL_FILE: b"\xff\xd8\xff" + event_id.encode(),
            vss.SIDECAR_FILE: json.dumps(vss.attribution(h.VERSION)).encode(),
        }
        vss.write_set(export, vss.CATEGORY[group], event_id, files)
    store_path = root / "eval" / h.VERSION / "eval.sqlite"
    store_path.parent.mkdir(parents=True)
    carried = _record_split(export, store_path, split, scenarios or {})
    ids = []
    with EvalStore(store_path) as store:
        assert not [r for r in import_generated_items(corpus_dir=export, store=store) if r.skipped]
        for model, by_event in scores.items():
            run_id = store.start_run(engine="llama.cpp", model=model)
            for event_id, group in events:
                cell: dict[str, Any] = {}
                if scenario := (scenarios or {}).get(event_id):
                    cell["scenario"] = scenario  # the item's facts must match the export's
                item = _item(event_id, group, **cell)
                row = _row(item, by_event.get(event_id, 10 if group == "benign" else 90))
                store.put_result(
                    run_id,
                    item.item_id,
                    verdict=row["verdict"],
                    risk_score=row["risk_score"],
                    raw_response=row["raw_response"],
                )
            replay_id = f"20260930T100000Z-{model}"
            record = {
                "replay_id": replay_id,
                "model": model,
                "served_id": f"{model}-id",
                "transport": "ai-vlm",
                "url": "http://127.0.0.1:8098",
                "build": "b7972",
                "export": str(export),
                "store": str(store_path),
                "eval_run_id": run_id,
                "commit": "abc",
                "started_utc": "2026-09-30T10:00:00+00:00",
            }
            # The split the replay measured under (Task 4's run.json fields); a test's own
            # `records[model]` still wins, which is how the disagreement tests move one of them.
            record |= carried | (records or {}).get(model, {})
            run_dir = root / "runs" / "replays" / replay_id
            run_dir.mkdir(parents=True)
            (run_dir / "run.json").write_text(json.dumps(record))
            ids.append(replay_id)
    return ids


# ISS-016: score reads ONE split truth out of three places that can hold it — the export's
# `splits.json`, the store's `splits` table, and each replay's run.json. Any disagreement between
# them is a refusal (B8), never a silent pick of the convenient one.


def _arms(document: Mapping[str, Any]) -> list[dict[str, str]]:
    """The store's flat rows for a manifest: one per armed scenario, as `put_split` takes them."""
    return [
        {"scenario": name, "arm": arm} for arm, names in document["arms"].items() for name in names
    ]


# The split fixture's scenarios: two incident scenarios (so the draw, clamped to n-1, sends one
# of them to holdout) and one benign scenario holding every benign item. Label-pure, as the corpus
# is (B5), so a scenario belongs to exactly one arm.
SPLIT_SCENARIOS = {
    "B-t-000": "knife_visible",
    "B-t-001": "knife_visible",
    "B-t-002": "loitering",
    **{f"B-b-{i:03d}": "hooded_jogger" for i in range(12)},
}


def _scenario_counts(scenarios: Mapping[str, str]) -> dict[str, dict[str, int]]:
    """The export's per-scenario item counts by label, from the fixture's own event list."""
    counts: dict[str, dict[str, int]] = {}
    for event_id, scenario in scenarios.items():
        label = "incident" if event_id.startswith("B-t") else "benign"
        per = counts.setdefault(scenario, {"benign": 0, "incident": 0})
        per[label] += 1
    return counts


def _drawn(scenarios: Mapping[str, str]) -> dict[str, str]:
    """The fixture's scenario -> arm table: the real hash draw over its incident scenarios, with
    benign joined as dev — the way the export command arms (B1)."""
    counts = _scenario_counts(scenarios)
    incident = [name for name, per in counts.items() if per["incident"]]
    drawn = {
        row["scenario"]: row["arm"] for row in vss.draw_split(h.VERSION, incident)["scenarios"]
    }
    return {name: drawn.get(name, "dev") for name in counts}


def _swap_arm(document: dict[str, Any], counts: Mapping[str, Mapping[str, int]]) -> dict[str, Any]:
    """The same manifest with one scenario armed the other way: roster, draw, size and item counts
    all moved with it, so it is a different split under a different digest — what a hand-edit of
    the store's rows leaves behind."""
    held = document["arms"]["holdout"][0]
    moved = next(n for n in document["arms"]["dev"] if counts[n]["incident"])
    arms = {
        "dev": sorted([n for n in document["arms"]["dev"] if n != moved] + [held]),
        "holdout": sorted([n for n in document["arms"]["holdout"] if n != held] + [moved]),
    }
    arm_of = {name: arm for arm, names in arms.items() for name in names}
    items = {
        arm: {label: sum(counts[name][label] for name in names) for label in ("benign", "incident")}
        for arm, names in arms.items()
    }
    return document | {
        "arms": arms,
        "draw": [row | {"arm": arm_of[row["scenario"]]} for row in document["draw"]],
        "holdout_k": len(arms["holdout"]),
        "items": items,
    }


def _record_split(
    export: Path, store_path: Path, mode: str | None, scenarios: Mapping[str, str]
) -> dict[str, Any]:
    """Write (or withhold) the fixture's split, in both places it is recorded, and give back the
    run.json fields a replay of that export would carry.

    `mode` is the drift to pin, and it says what each of the three places holds. On disk and in the
    store: `"recorded"` the manifest and the same roster in both, `"file_only"` the manifest with
    the store never told, `"store_only"` a roster in the store and no manifest on disk,
    `"rival_in_store"` two different splits, one in each place. In the replay record:
    `"no_replay_record"` an honest manifest AND an honest store, but the run.json carries no
    `split_sha256` key at all — the shape of a replay made before the split existed;
    `"replay_only"` no manifest and an empty store, but the run.json carries a digest.
    `"rival_in_replay"` is the honest pair; the caller moves the replay's digest with `records`.
    `None` leaves the export a pre-split one. The run.json fields are the honest ones for the
    manifest on disk, which is what a replay of that export would have written.
    """
    if mode is None:
        return {}
    # What each place holds, per drift: (the manifest on disk?, the roster in the store?). Every
    # mode not listed here with `False` carries the honest manifest.
    ON_DISK = ("recorded", "file_only", "rival_in_store", "no_replay_record", "rival_in_replay")
    IN_STORE = ("recorded", "store_only", "rival_in_store", "no_replay_record", "rival_in_replay")
    counts = _scenario_counts(scenarios)
    document = vss.split_manifest_document(h.VERSION, _drawn(scenarios), items_by_scenario=counts)
    stored_document = _swap_arm(document, counts) if mode == "rival_in_store" else document
    if mode in ON_DISK:
        vss.write_split(export, document)
    if mode in IN_STORE:
        with EvalStore(store_path) as store:
            store.put_split(
                h.VERSION,
                _arms(stored_document),
                seed=str(stored_document["seed"]),
                manifest_sha256=vss.split_sha256(stored_document),
            )
    if mode == "replay_only":
        # No manifest and an empty store, but the replay names a digest: a store and an export
        # replaced by pre-split copies after the replay ran. The digest is the one the split this
        # export no longer carries would have had.
        return {"split_sha256": vss.split_sha256(document), "split_holdout": []}
    if mode == "no_replay_record":
        # The key absent entirely, which is what a run.json written before Task 4's fields reads
        # like — as opposed to replay's own pre-split shape, which writes the key as null.
        return {}
    if mode == "store_only":
        # replay's own shape for an export with no manifest: the key present and null.
        return {"split_sha256": None, "split_holdout": []}
    return {
        "split_sha256": vss.split_sha256(document),
        "split_holdout": list(document["arms"]["holdout"]),
    }


def _split_fixture(
    root: Path,
    mode: str,
    scores: dict[str, dict[str, int | None]],
    records: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """`_world` over the split fixture's scenarios: two incident ones (the draw, clamped to n-1,
    sends one to holdout) and one benign scenario carrying every benign item."""
    return _world(root, scores, records, scenarios=SPLIT_SCENARIOS, split=mode)


# Task 6 reads the same fixture one level down: `score_models` over these items and rows directly,
# so the arms' arithmetic is checkable without a store, and against an armless run of the very
# same rows.

SPLIT_EVENTS = tuple(
    [(f"B-t-{i:03d}", "threat") for i in range(3)] + [(f"B-b-{i:03d}", "benign") for i in range(12)]
)


def _arms_of(items: Mapping[str, Item], arm_of: Mapping[str, str]) -> dict[str, list[str]]:
    """The fixture's items grouped by the arm of their scenario: the per-side n to check against."""
    out: dict[str, list[str]] = {"dev": [], "holdout": []}
    for item in items.values():
        out[arm_of[str(item.facts["cell"]["scenario"])]].append(item.item_id)
    return out


def _split_unit(
    misses: Sequence[str] = (),
) -> tuple[dict[str, Item], dict[str, str], list[dict[str, Any]]]:
    """The split fixture's items, roster and rows, for `score_models` called directly.

    The fifteen events `_world` exports, each carrying its `SPLIT_SCENARIOS` scenario, beside the
    honest roster `_drawn` computes for those scenarios and one row per item: an incident scores 90
    (a hit) and a benign scene 10 (a clear) unless its event is named in `misses`, which is how a
    test moves one model's outcomes without touching the roster.
    """
    items = _items(
        *[
            _item(event_id, group, scenario=SPLIT_SCENARIOS[event_id])
            for event_id, group in SPLIT_EVENTS
        ]
    )
    rows = [
        _row(
            item,
            20 if item.event_id in misses else 90 if item.label == "incident" else 10,
        )
        for item in items.values()
    ]
    return items, _drawn(SPLIT_SCENARIOS), rows


def _rows(out: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines()]


def _scored_dir(root: Path) -> Path:
    [out] = (root / "runs" / "scores").iterdir()
    return out


def test_a_recorded_split_scores_under_one_roster(tmp_path: Path) -> None:
    """The export's manifest and the store's rows are the same split: score states it once in the
    identity, and every results row carries the arm of its scenario (ISS-016 B5/B8)."""
    ids = _split_fixture(tmp_path, "recorded", {"qwen3-vl-8b": {}})
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_OK
    out = _scored_dir(tmp_path)
    metrics = json.loads((out / "metrics.json").read_text())
    export = tmp_path / "exports" / h.VERSION / "vss"
    manifest = vss.read_split(export)
    assert manifest is not None
    digest = vss.split_sha256(manifest)
    assert metrics["identity"]["split"] == {
        "source": "splits.json",
        "sha256": digest,
        "seed": manifest["seed"],
        "holdout_k": manifest["holdout_k"],
        "holdout": manifest["arms"]["holdout"],
        "items": manifest["items"],
    }
    # The row's arm is its scenario's arm — computed from the scenario, never from the identity.
    arm_of = {name: arm for arm, names in manifest["arms"].items() for name in names}
    rows = _rows(out)
    assert len(rows) == 15  # one model, fifteen items
    assert {row["split"] for row in rows} == {"dev", "holdout"}
    assert [row["split"] for row in rows] == [arm_of[row["cell"]["scenario"]] for row in rows]


def test_the_identity_states_the_holdout_and_its_item_counts(tmp_path: Path) -> None:
    """The two numbers a reader discounts a holdout by: which scenarios tuning never saw, and how
    many items they are. Both come from the manifest the score checked, not from the fixture."""
    ids = _split_fixture(tmp_path, "recorded", {"qwen3-vl-8b": {}})
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_OK
    metrics = json.loads((_scored_dir(tmp_path) / "metrics.json").read_text())
    identity = metrics["identity"]["split"]
    # The hash draw over two incident scenarios puts knife_visible in the holdout (the k=1 clamp
    # of §2's edge), and every benign item stays in dev by rule B1.
    assert identity["holdout"] == ["knife_visible"]
    assert identity["items"]["holdout"] == {"benign": 0, "incident": 2}
    assert identity["items"]["dev"] == {"benign": 12, "incident": 1}


def test_a_pre_split_export_scores_as_unrecorded(tmp_path: Path) -> None:
    """B6: the manifestless fixture still scores, and says so — but the version bump is real, so a
    reader can tell this metrics.json from one written before the split existed. Its metrics keep
    today's shape exactly: the frozen records elsewhere are byte-compared against regenerated ones,
    and an absent arm is the difference between that check passing and failing."""
    ids = _world(tmp_path, {"qwen3-vl-8b": {}})
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_OK
    out = _scored_dir(tmp_path)
    metrics = json.loads((out / "metrics.json").read_text())
    assert metrics["identity"]["split"] == {"source": "unrecorded"}
    assert metrics["identity"]["score_version"] == 3
    rows = _rows(out)
    assert len(rows) == 15
    assert {row["split"] for row in rows} == {"unrecorded"}
    # Nothing per-arm appears: an unrecorded score has no arms to report, and a key that showed up
    # here would change every pre-split record regenerated since.
    assert set(metrics) == {"identity", "audit", "models", "comparison"}
    assert "split_comparison" not in metrics
    block = metrics["models"]["qwen3-vl-8b"]
    assert set(block) == {"replay_id", "excluded", "all", "audited", "slices"}
    assert "dev" not in block and "holdout" not in block
    assert "scenario_slice_dev" not in block


def test_a_silent_replay_beside_a_split_truth_is_asked_about(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A replay whose run.json carries no ``split_sha256`` at all, against a store and an export
    that agree: the third reading is silent where the other two state a truth, so it cannot confirm
    them and is refused (B8), not scored by a silent 2-way fallback.

    This is the honest form of the ``no_replay_record`` fixture: the run.json omits the key the way
    a pre-Task-4 replay's does. A live replay of THIS export always carries the digest
    (``replay.py`` writes ``split_sha256: None`` only for a manifestless export), so a silent
    run.json beside a manifest-bearing export is a hand-edit or a pre-split replay pointed at a
    split export — and a pre-split replay scored every item including today's holdout, so scoring
    it beside a split-aware replay is the leak the split exists to close. The ``carried != digest``
    loop says so in the message: a replay that recorded NOTHING fails the agreement just as a rival
    digest does, because it is the agreement that is being asked for."""
    ids = _split_fixture(tmp_path, "no_replay_record", {"qwen3-vl-8b": {}})
    run = tmp_path / "runs" / "replays" / ids[0] / "run.json"
    assert "split_sha256" not in json.loads(run.read_text())  # the fixture really omits the key
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_ASK
    assert not (tmp_path / "runs" / "scores").exists()
    err = capsys.readouterr().err
    export = tmp_path / "exports" / h.VERSION / "vss"
    manifest = vss.read_split(export)
    assert manifest is not None
    assert "recorded split_sha256 nothing" in err  # names the silence, not a mismatched digest
    assert vss.split_sha256(manifest) in err  # and the truth the silent replay failed to state


@pytest.mark.parametrize(
    "mode,drift",
    [
        pytest.param("file_only", "a manifest the store was never told about"),
        pytest.param("store_only", "a roster in the store that the export cannot show"),
        pytest.param("rival_in_store", "two different splits, one in each place"),
        pytest.param(
            "replay_only",
            "a replay carrying a digest for an export that has no manifest",
        ),
        pytest.param(
            "rival_in_replay",
            "a store and a manifest that agree, under a digest neither of them states",
        ),
    ],
)
def test_a_split_disagreement_refuses_the_score(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str, drift: str
) -> None:
    """B8: each way the three records can hold a real disagreement stops the run with exit 2 and
    writes nothing — the same disposition as the stale-fingerprint check. One drift per param:
    ``file_only`` a manifest the store never heard of, ``store_only`` a roster the export cannot
    show, ``rival_in_store`` two different splits in the two places, ``replay_only`` a replay
    naming a digest for a manifestless export, ``rival_in_replay`` a digest the other two do not
    state. A replay that records NOTHING is not on this list: beside a stated truth the third
    reading's silence is refused too, pinned by
    ``test_a_silent_replay_beside_a_split_truth_is_asked_about``."""
    scores: dict[str, dict[str, int | None]] = {"qwen3-vl-8b": {}}
    records = None
    if mode == "rival_in_replay":
        # Two replays, both measured under a digest that exists nowhere else: the store and the
        # manifest agree with each other, so only the third reading can catch this.
        scores = {"qwen3-vl-8b": {}, "flagship": {}}
        records = {model: {"split_sha256": "b" * 64} for model in scores}
    ids = _split_fixture(tmp_path, mode, scores, records)
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_ASK
    assert not (tmp_path / "runs" / "scores").exists()
    err = capsys.readouterr().err
    assert "split" in err
    if mode == "rival_in_replay":
        # Store and manifest agree, so the only thing wrong is what the replays carry — and the
        # owner has to be able to see which digest that was to know which side to move.
        assert "b" * 64 in err
    if mode == "replay_only":
        # The manifestless export's refusal names the replay's digest and says the export predates
        # it, so the owner sees the missing splits.json, not a silent unrecorded score.
        assert "predates the split" in err


def test_a_store_roster_that_disagrees_names_both_digests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The owner-readable form of the refusal: the store's digest and the export's, so the fix
    (which side to move) is decidable from the message."""
    ids = _split_fixture(tmp_path, "rival_in_store", {"qwen3-vl-8b": {}})
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_ASK
    err = capsys.readouterr().err
    stored = re.findall(r"\b[0-9a-f]{64}\b", err)
    assert len(stored) == 2
    with EvalStore(tmp_path / "eval" / h.VERSION / "eval.sqlite") as store:
        rows = store.get_split(h.VERSION)
    assert rows is not None
    in_store = {row["manifest_sha256"] for row in rows}
    export = tmp_path / "exports" / h.VERSION / "vss"
    assert in_store | {vss.split_sha256(vss.read_split(export))} == set(stored)


def test_a_row_whose_scenario_the_roster_does_not_arm_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The roster covers every exported scenario (Task 2), so a scenario it does not arm is
    hand-edited or mismatched data: name it and stop rather than call it unrecorded."""
    ids = _split_fixture(tmp_path, "recorded", {"qwen3-vl-8b": {}})
    edited = tmp_path / "exports" / h.VERSION / "vss" / "threats" / "B-t-002" / vss.LABELS_FILE
    labels = json.loads(edited.read_text())
    labels["synthbench"]["cell"]["scenario"] = "unedited_never_armed"
    edited.write_text(json.dumps(labels))
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_ASK
    assert "unedited_never_armed" in capsys.readouterr().err
    assert not (tmp_path / "runs" / "scores").exists()


# Task 6: an armed score reads each headline twice, once per arm, so a model that improved only on
# the scenarios tuning never saw says so (design §4's per-arm tables). The armless run of the same
# rows stays byte-identical (B6).


def test_an_armed_score_reports_each_model_once_per_arm() -> None:
    """dev + holdout partition `all` exactly, and the holdout's benign leg is empty by rule B1:
    every benign scenario stays in dev, so its S2 reads as no data, not as a clean 0%."""
    items, arm_of, rows = _split_unit()
    side = _arms_of(items, arm_of)
    block = score_models([("m", "r", rows)], items, {}, [], scenario_arm=arm_of)["models"]["m"]
    assert block["all"]["n"] == 15
    assert (block["dev"]["n"], block["holdout"]["n"]) == (len(side["dev"]), len(side["holdout"]))
    assert block["dev"]["n"] + block["holdout"]["n"] == block["all"]["n"]
    # Both bars' denominators partition with the items.
    for arm in ("dev", "holdout"):
        assert block[arm]["s2"]["n"] + block[arm]["s3"]["all"]["n"] == len(side[arm])
    assert (block["dev"]["s3"]["all"]["n"], block["holdout"]["s3"]["all"]["n"]) == (1, 2)
    # B1: the holdout holds no benign item, so S2 has nothing to measure. Both objects that state
    # it — `s2_false_positive_rate`'s own dict and the `cell()` wrapper beside it — read as no data.
    assert block["holdout"]["s2"]["n"] == 0
    assert block["holdout"]["s2"]["fp_rate"] is None
    assert block["holdout"]["s2_cell"]["n"] == 0
    assert block["holdout"]["s2_cell"]["rate"] is None
    assert block["holdout"]["s2_cell"]["insufficient"] is True
    assert block["dev"]["s2_cell"]["n"] == 12  # every benign item, all of them in dev by B1
    # The manifest's per-arm item counts are the same partition (design §4's arithmetic).
    counts = vss.split_manifest_document(
        h.VERSION, arm_of, items_by_scenario=_scenario_counts(SPLIT_SCENARIOS)
    )["items"]
    assert {
        arm: {
            "incident": block[arm]["s3"]["all"]["n"],
            "benign": block[arm]["s2"]["n"],
        }
        for arm in ("dev", "holdout")
    } == counts


def test_the_per_arm_comparison_sees_only_its_side_of_the_split() -> None:
    """`split_comparison` holds one `comparison()` per arm, over that arm's rows only. Model `b`
    misses the lone DEV incident and nothing in the holdout: the dev pair carries the disagreement,
    the holdout pair is concordant — which is what computing them apart is for."""
    missed = "B-t-002"  # the event in the dev incident scenario
    items, arm_of, rows_m = _split_unit()
    _, _, rows_b = _split_unit((missed,))
    replays = [("m", "r-m", rows_m), ("b", "r-b", rows_b)]
    lost = next(i.item_id for i in items.values() if i.event_id == missed)
    metrics = score_models(replays, items, {}, [], scenario_arm=arm_of)
    split = metrics["split_comparison"]
    assert set(split) == {"dev", "holdout"}
    assert [len(split[arm]) for arm in ("dev", "holdout")] == [1, 1]  # one pair, two models
    assert [(p["a"], p["b"]) for p in split["dev"]] == [("m", "b")]
    assert split["dev"][0]["b_wrong_a_right"] == [lost]
    assert split["dev"][0]["agree"]["n"] == 13  # 12 benign + 1 incident
    assert split["holdout"][0]["b_wrong_a_right"] == []
    assert split["holdout"][0]["agree"]["n"] == 2
    assert split["holdout"][0]["s3_discordants"] == {"only_a": 0, "only_b": 0, "p": 1.0}
    # The whole-corpus comparison ISS-043 built is still there, reading every item: the arms add a
    # view, they do not replace it.
    assert metrics["comparison"][0]["b_wrong_a_right"] == [lost]
    assert metrics["comparison"][0]["agree"]["n"] == 15


def test_the_split_moves_nothing_the_armless_metrics_already_said() -> None:
    """Arming a score adds keys and changes none: `audited`, `slices` and the top-level
    `comparison` read the same rows they always did (B6's shape rule, applied to a split export).
    The dev scenario slice is the one addition, and it sees only dev scenarios."""
    items, arm_of, rows = _split_unit()
    answers = {("B-t-000", "scene"): "y", ("B-b-000", "scene"): "n"}
    sampled = ["B-t-000", "B-b-000", "B-t-002"]
    replays = [("m", "r", rows), ("b", "r-b", rows)]
    armless = score_models(replays, items, answers, sampled)
    armed = score_models(replays, items, answers, sampled, scenario_arm=arm_of)
    for model in ("m", "b"):
        before, after = armless["models"][model], armed["models"][model]
        # `audited` is the scene-confirmed subset of every kept row — not of dev — so arming the
        # score must leave it byte-identical.
        assert after["audited"] == before["audited"]
        assert after["all"] == before["all"]
        assert after["slices"] == before["slices"]
        assert after["excluded"] == before["excluded"] == 1
    assert armed["comparison"] == armless["comparison"]
    assert set(armed) == set(armless) | {"split_comparison"}
    assert set(armed["models"]["m"]) == set(armless["models"]["m"]) | {
        "dev",
        "holdout",
        "scenario_slice_dev",
    }
    # Task 7's dev scenario slice: scenario values only, over dev rows, so the holdout's scenario
    # cannot appear in it and no other slice name can.
    scenario = armed["models"]["m"]["scenario_slice_dev"]
    assert set(scenario) == {"hooded_jogger", "loitering"}
    assert scenario["loitering"]["s3"]["n"] == 1
    assert scenario["hooded_jogger"]["s2"]["n"] == 11  # 12 benign, one a generation error
    assert "knife_visible" not in scenario


def test_a_recorded_split_scores_both_arms_from_one_pass(tmp_path: Path) -> None:
    """End to end: the arms' item counts are the manifest's, and every model carries both sides
    beside `all`."""
    ids = _split_fixture(tmp_path, "recorded", {"qwen3-vl-8b": {}, "flagship": {}})
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_OK
    metrics = json.loads((_scored_dir(tmp_path) / "metrics.json").read_text())
    manifest_items = metrics["identity"]["split"]["items"]
    assert set(metrics) == {"identity", "audit", "models", "comparison", "split_comparison"}
    for model in ("qwen3-vl-8b", "flagship"):
        block = metrics["models"][model]
        for arm in ("dev", "holdout"):
            counts = manifest_items[arm]
            assert block[arm]["s2"]["n"] == counts["benign"]
            assert block[arm]["s3"]["all"]["n"] == counts["incident"]
            assert block[arm]["n"] == counts["benign"] + counts["incident"]
        assert block["dev"]["n"] + block["holdout"]["n"] == block["all"]["n"] == 15
        assert block["scenario_slice_dev"]
    assert [len(metrics["split_comparison"][arm]) for arm in ("dev", "holdout")] == [1, 1]


def test_score_writes_results_metrics_and_both_reports(tmp_path: Path) -> None:
    ids = _world(tmp_path, {"qwen3-vl-8b": {"B-t-000": 20}, "flagship": {"B-b-000": 70}})
    # All 15 sets are sampled (only 3 threats and 12 benigns exist), so B-t-000 is in the audit
    # sample. The owner says its scene never happened: a generation error, excluded everywhere.
    log = audit_log(h.VERSION, h.env(tmp_path))
    log.parent.mkdir(parents=True)
    answer = {
        "event_id": "B-t-000",
        "question": "scene",
        "answer": "n",
        "time": "2026-09-30T09:00:00+00:00",
    }
    log.write_text(json.dumps(answer) + "\n", encoding="utf-8")
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_OK
    [out] = (tmp_path / "runs" / "scores").iterdir()
    results = [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines()]
    assert len(results) == 2 * 15
    metrics = json.loads((out / "metrics.json").read_text())
    assert metrics["models"]["qwen3-vl-8b"]["excluded"] == 1
    assert metrics["models"]["qwen3-vl-8b"]["all"]["s3"]["all"]["miss"] == 0
    assert metrics["identity"]["replays"][0]["build"] == "b7972"
    assert "qwen3-vl-8b" in (out / "report.md").read_text()
    html = (out / "report.html").read_text()
    sources = re.findall(r'<img src="([^"]+)"', html)
    assert len(sources) == 1  # the false alarm only; B-t-000's miss is a generation error
    assert not [src for src in sources if Path(src).is_absolute()]  # the tree moves as one
    assert all((out / src).resolve().is_file() for src in sources)


def test_score_refuses_an_unknown_replay_and_a_model_twice(tmp_path: Path) -> None:
    [replay_id] = _world(tmp_path, {"qwen3-vl-8b": {}})
    assert h.run(tmp_path, "score", "--replay", "nope") == cli.EXIT_ERROR
    twice = ("--replay", replay_id, "--replay", replay_id)
    assert h.run(tmp_path, "score", *twice) == cli.EXIT_ERROR


def test_score_stops_when_rows_name_items_the_export_lacks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    [replay_id] = _world(tmp_path, {"qwen3-vl-8b": {}})
    gone = tmp_path / "exports" / h.VERSION / "vss" / "threats" / "B-t-000" / vss.LABELS_FILE
    gone.unlink()
    assert h.run(tmp_path, "score", "--replay", replay_id) == cli.EXIT_ASK
    assert "1 item(s) the export" in capsys.readouterr().err
    assert not (tmp_path / "runs" / "scores").exists()


def test_weights_identity_reads_what_each_transport_left(tmp_path: Path) -> None:
    vlm = tmp_path / "ai_models" / "vlm"
    vlm.mkdir(parents=True)
    (vlm / "SHA256SUMS").write_text("ab12  Qwen3VL-8B-Instruct-Q4_K_M.gguf\ncd34  other.gguf\n")
    ref = tmp_path / "hf" / "hub" / "models--nvidia--Cosmos-Reason2-8B" / "refs"
    ref.mkdir(parents=True)
    (ref / "main").write_text("f00d\n")
    env = {"AI_MODELS_PATH": str(tmp_path / "ai_models"), "HF_HOME": str(tmp_path / "hf")}
    assert weights_identity("ai-vlm", "Qwen3VL-8B-Instruct-Q4_K_M", env) == "sha256:ab12"
    assert weights_identity("ai-vlm", "Qwen3VL-4B-Instruct-Q4_K_M", env) == "unrecorded"
    assert weights_identity("vllm", "nvidia/Cosmos-Reason2-8B", env) == "revision:f00d"
    assert weights_identity("vllm", "claude-flagship", env) == "unrecorded"


COSMOS_FORMAT = (
    "Answer the question using the following format:\n\n<think>\nYour reasoning.\n</think>\n\n"
    "Write your final answer immediately after the </think> tag."
)
# What each replay's run.json records about the conditions it ran under (decision A7).
CONDITIONS = {
    "qwen3-vl-8b": {
        "transport": "ai-vlm",
        "enforcement_probe": True,
        "request_extra": {},
        "max_tokens": 1024,
        "read_timeout": 25.0,
        "system_message": None,
        "thinking": "—",
        "temperature": 0.0,
        "seed": None,
    },
    "cosmos-reason2-8b": {
        "transport": "vllm",
        "enforcement_probe": False,
        "request_extra": {"max_tokens": 4096},
        "max_tokens": 4096,
        "read_timeout": 120.0,
        "system_message": COSMOS_FORMAT,
        "thinking": "on (asked by its system message; parsed by vLLM)",
        "temperature": 0.0,
        "seed": None,
    },
    "flagship": {
        "transport": "vllm",
        "enforcement_probe": False,
        "request_extra": {"chat_template_kwargs": {"enable_thinking": False}},
        "max_tokens": 1024,
        "read_timeout": 25.0,
        "system_message": None,
        "thinking": "off",
        "temperature": 0.0,
        "seed": None,
    },
}


def _scored(tmp_path: Path) -> Path:
    """A score over three replays that ran under different conditions: its output dir."""
    ids = _world(tmp_path, {model: {} for model in CONDITIONS}, CONDITIONS)
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_OK
    [out] = (tmp_path / "runs" / "scores").iterdir()
    return out


def test_the_report_states_each_models_conditions(tmp_path: Path) -> None:
    """Cosmos's system message, budget and timeout and the flagship's thinking-off are the
    price of their columns (decision A7): the report states them beside the product model's.
    The build and the server settings come last (ISS-087): the fixture's run.json records
    `b7972` and declares no server settings, which is what an older replay reads like."""
    out = _scored(tmp_path)
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "Comparison models may run under different conditions" in text
    rows = {
        "| qwen3-vl-8b | ai-vlm | shipped | — | 1024 | 25 s | on | temp 0.0, unseeded | b7972 "
        "| unrecorded |",
        "| cosmos-reason2-8b | vllm | shipped + system message (A7) | on (asked by its system "
        "message; parsed by vLLM) | 4096 | 120 s | off | temp 0.0, unseeded | b7972 | "
        "unrecorded |",
        "| flagship | vllm | shipped | off | 1024 | 25 s | off | temp 0.0, unseeded | b7972 | "
        "unrecorded |",
    }
    assert rows <= set(text.splitlines())
    assert json.dumps(COSMOS_FORMAT) in text  # the system message, verbatim
    identity = json.loads((out / "metrics.json").read_text())["identity"]
    by_model = {replay["model"]: replay for replay in identity["replays"]}
    for model, conditions in CONDITIONS.items():
        assert {key: by_model[model][key] for key in conditions} == conditions
    store = tmp_path / "eval" / h.VERSION / "eval.sqlite"
    assert identity["eval_store"] == {"path": str(store)}


# ISS-087: a llama.cpp build and the flags an endpoint was started with change its answers, and
# `replay` cannot observe either (it never starts a server). The operator declares the second with
# `--server-settings`; both land in run.json and the conditions row names them per model.

BUILD_NEW = "b11376-a55e952b8"
SERVER_SETTINGS = "prompt cache off (LLAMA_ARG_CACHE_RAM=0)"


def _forget(root: Path, replay_id: str, keys: Sequence[str]) -> None:
    """Rewrite a replay's `run.json` without `keys`: the shape of a record written before they
    were recorded, as opposed to one written since with an empty value."""
    path = root / "runs" / "replays" / replay_id / "run.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    for key in keys:
        del record[key]
    path.write_text(json.dumps(record), encoding="utf-8")


def test_the_conditions_line_names_the_build_and_the_declared_server_settings(
    tmp_path: Path,
) -> None:
    """Two replays of one export that ran on different builds, one with flags declared and one
    recorded before either fact existed, are not one comparable row of numbers, so each row
    carries both facts (ISS-087). The declared string is quoted as the operator gave it; a
    replay that recorded neither says so per cell — `—` for a build never observed, `unrecorded`
    for settings never declared — and still scores."""
    declared, older = "qwen3-vl-8b", "flagship"
    ids = _world(
        tmp_path,
        {declared: {}, older: {}},
        {
            declared: {"build": BUILD_NEW, "server_settings": SERVER_SETTINGS}
            | CONDITIONS[declared],
            older: CONDITIONS[older],
        },
    )
    _forget(tmp_path, ids[1], ["build"])  # a run.json from before the build was recorded
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_OK
    [out] = (tmp_path / "runs" / "scores").iterdir()
    text = (out / "report.md").read_text(encoding="utf-8")
    rows = {
        f"| {declared} | ai-vlm | shipped | — | 1024 | 25 s | on | temp 0.0, unseeded | "
        f"{BUILD_NEW} | {SERVER_SETTINGS} |",
        f"| {older} | vllm | shipped | off | 1024 | 25 s | off | temp 0.0, unseeded | — | "
        "unrecorded |",
    }
    assert rows <= set(text.splitlines())
    identity = json.loads((out / "metrics.json").read_text())["identity"]
    by_model = {replay["model"]: replay for replay in identity["replays"]}
    assert by_model[declared]["server_settings"] == SERVER_SETTINGS
    assert by_model[older]["server_settings"] is None  # the key rides with the conditions
    assert by_model[older]["build"] is None


def test_the_report_shows_no_absolute_host_path(tmp_path: Path) -> None:
    """report.md is committed: paths under $SYNTHBENCH_ROOT read relative to it. The identity
    in metrics.json keeps them absolute."""
    out = _scored(tmp_path)
    text = (out / "report.md").read_text(encoding="utf-8")
    assert str(tmp_path) not in text
    assert "/synthbench/" not in text
    assert f"`exports/{h.VERSION}/vss`" in text
    assert f"`eval/{h.VERSION}/eval.sqlite`" in text
    assert f"`audits/{h.VERSION}/audit.jsonl`" in text
    identity = json.loads((out / "metrics.json").read_text())["identity"]
    assert identity["export"]["path"] == str(tmp_path / "exports" / h.VERSION / "vss")


# Task 7: report.md labels which side of the split every number belongs to and report.html shows
# dev stills only (ISS-016 B7). The strings are the design's §5 strings; the counts in them are
# computed from this run's own data, never transcribed from the real corpus.

# What the split fixture's draw lands on: one incident scenario in the holdout (the k=1 clamp of
# §2's edge, so 2 of the 3 incident items) and every benign item in dev (rule B1).
SPLIT_HOLDOUT_EVENTS = ("B-t-000", "B-t-001")  # knife_visible
SPLIT_DEV_EVENT = "B-t-002"  # loitering, the one incident item dev keeps


def _split_scored(tmp_path: Path, misses: Mapping[str, int] | None = None) -> Path:
    """A recorded-split score over two models, the second missing `misses`: its output dir.
    Two models because the comparison is part of what §5 relabels, and one miss per arm so both
    comparison tables and both gallery legs have something in them."""
    ids = _split_fixture(
        tmp_path,
        "recorded",
        {"qwen3-vl-8b": {}, "flagship": {**(misses or {}), SPLIT_DEV_EVENT: 20}},
    )
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_OK
    return _scored_dir(tmp_path)


def test_a_recorded_split_report_labels_its_headlines_and_identity(tmp_path: Path) -> None:
    """§5's headings, verbatim, and the Split row's numbers computed from the manifest this score
    checked. The all-items headline keeps its heading and its place: today's numbers keep their
    meaning and stay comparable with the frozen records."""
    out = _split_scored(tmp_path)
    text = (out / "report.md").read_text(encoding="utf-8")
    identity = json.loads((out / "metrics.json").read_text())["identity"]["split"]
    lines = text.splitlines()
    assert "## Headline: every scored item" in text
    assert "## Headline: dev split (tuning may see this)" in text
    assert "## Headline: holdout split (tuning never saw this)" in text
    # The all-items table comes first, then dev, then holdout.
    order = [
        text.index("## Headline: every scored item"),
        text.index("## Headline: dev split (tuning may see this)"),
        text.index("## Headline: holdout split (tuning never saw this)"),
    ]
    assert order == sorted(order)
    held, dev = identity["items"]["holdout"], identity["items"]["dev"]
    [row] = [line for line in lines if line.startswith("- Split: ")]
    assert row == (
        f"- Split: {identity['source']} sha256 {identity['sha256']}; seed {identity['seed']}; "
        f"holdout {identity['holdout_k']} scenarios / {held['incident']} incident items; "
        f"dev {dev['incident'] + dev['benign']} ({dev['benign']} benign)"
    )
    assert "holdout 1 scenarios / 2 incident items; dev 13 (12 benign)" in row
    assert "B-t-" not in text and "B-b-" not in text  # still aggregate: no item is named


def test_a_recorded_split_report_states_what_the_split_can_and_cannot_say(
    tmp_path: Path,
) -> None:
    """The section sits directly after Run identity and carries the draw's two bound-setting
    properties, the S2-by-design note and the tuning rule — every number in it this run's own."""
    out = _split_scored(tmp_path)
    text = (out / "report.md").read_text(encoding="utf-8")
    identity = json.loads((out / "metrics.json").read_text())["identity"]["split"]
    assert "## What this split can and cannot say" in text
    assert (
        text.index("## Run identity")
        < text.index("## What this split can and cannot say")
        < text.index("## Headline: every scored item")
    )
    # The realized draw's two properties, plus B1's S2 note and B7's tuning rule.
    assert "leak detector" in text
    assert "suspicious-heavy" in text
    assert "S2 is measured on dev by design" in text
    assert "excluded from" in text and "has not seen them" in text
    # The n the section discounts the holdout by is the manifest's, not a transcribed corpus size.
    block = text.split("## What this split can and cannot say")[1].split("\n## ")[0]
    assert f"{identity['items']['holdout']['incident']} incident items" in block
    assert "209" not in block and "64 incident items" not in block


def test_the_holdout_s2_cell_reads_as_no_data_with_its_reason(tmp_path: Path) -> None:
    """The holdout holds no benign item (B1), so its S2 cell is `insufficient (n=0)` and the
    section says why. The benign count in that sentence is THIS run's dev benign n — the real
    corpus's 209 belongs to the design doc, not to a report over 15 items."""
    out = _split_scored(tmp_path)
    text = (out / "report.md").read_text(encoding="utf-8")
    models = json.loads((out / "metrics.json").read_text())["models"]
    leg = text.split("## Headline: holdout split (tuning never saw this)")[1].split("\n## ")[0]
    assert "insufficient (n=0)" in leg
    dev_benign = {m["dev"]["s2"]["n"] for m in models.values()}
    assert dev_benign == {12}  # every benign item sits in dev, by rule B1
    assert "no benign items in the holdout: S2 is measured on dev, which" in leg
    assert f"holds all {next(iter(dev_benign))} benign items by design (ISS-016 B1)" in leg
    assert "209 benign" not in text


def test_the_scenario_slice_dev_only_sits_under_the_dev_headline(tmp_path: Path) -> None:
    """§5's one slice addition: per-scenario failure detail — what a tuner reads to pick what to
    fix — printed where tuning may see it. The all-items slice block stays as it was, so the
    holdout's scenario still appears THERE and must not appear in the dev-only table."""
    out = _split_scored(tmp_path)
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "### Scenario slice, dev only" in text
    assert text.index("## Headline: dev split") < text.index("### Scenario slice, dev only")
    assert text.index("### Scenario slice, dev only") < text.index("## Headline: holdout split")
    block = text.split("### Scenario slice, dev only")[1].split("\n## ")[0]
    assert "loitering" in block and "hooded_jogger" in block  # the dev scenarios
    assert "knife_visible" not in block  # the holdout's, absent by construction
    assert "**scenario**" in text  # the unchanged all-items slice block still prints


def test_the_comparison_prints_once_per_split_with_the_rule_on_dev(tmp_path: Path) -> None:
    """Dev first and named as where the OD-26 rule decides, holdout second as the generalization
    check with the rule not applied, and ISS-043's spans-zero note printed once for both."""
    out = _split_scored(tmp_path, {SPLIT_HOLDOUT_EVENTS[0]: 20})
    text = (out / "report.md").read_text(encoding="utf-8")
    dev_label = "### Comparison: dev split (where the OD-26 rule decides)"
    held_label = "### Comparison: holdout split (the generalization check; the rule is not applied)"
    assert dev_label in text and held_label in text
    assert text.index("## Comparison") < text.index(dev_label) < text.index(held_label)
    # `## Comparison` is a substring of the `### Comparison: …` labels, so anchor on its line.
    block = text.split("\n## Comparison\n")[1]
    assert block.count("spans 0") == 1  # the closing note, printed once for both tables
    assert block.count("| Models |") == 2


def test_an_unrecorded_report_says_so_and_gains_no_sections(tmp_path: Path) -> None:
    """B6 at the report layer: the manifestless export's report differs from today's by one line
    and nothing else — no can/cannot-say section, no labelled headlines, no dev slice."""
    ids = _world(tmp_path, {"qwen3-vl-8b": {}})
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_OK
    text = (_scored_dir(tmp_path) / "report.md").read_text(encoding="utf-8")
    assert "- Split: unrecorded — this export predates ISS-016" in text
    for heading in (
        "## What this split can and cannot say",
        "## Headline: dev split (tuning may see this)",
        "## Headline: holdout split (tuning never saw this)",
        "### Scenario slice, dev only",
        "### Comparison: dev split",
    ):
        assert heading not in text
    assert "## Headline: every scored item" in text
    assert "## Comparison" in text and "### Comparison" not in text


def test_the_gallery_shows_no_holdout_still(tmp_path: Path) -> None:
    """B7's enforcement half: the failure gallery is what tuning actually looks at, so a holdout
    miss must not appear in it, and neither must its still path (which carries its event id)."""
    out = _split_scored(tmp_path, {SPLIT_HOLDOUT_EVENTS[0]: 20})
    gallery = (out / "report.html").read_text(encoding="utf-8")
    rows = _rows(out)
    held = [row for row in rows if row["split"] == "holdout"]
    assert held and all(row["event_id"] in SPLIT_HOLDOUT_EVENTS for row in held)
    for row in held:
        assert row["event_id"] not in gallery
        assert row["still"] not in gallery
        assert f"/{row['event_id']}/" not in gallery  # the still's path names the event
    kept = next(r for r in rows if r["split"] == "dev" and r["event_id"] == SPLIT_DEV_EVENT)
    assert f"/{kept['event_id']}/" in gallery  # the dev miss is still there to look at


def _gallery_rows(
    misses: Sequence[str] = (), *, unrecorded: bool = False
) -> tuple[dict[str, Item], list[dict[str, Any]]]:
    """One model's `result_rows` over the split fixture with `misses` scored low: the rows the
    gallery renders, built the way `scoring` builds them. `unrecorded` withholds the roster,
    which is the shape a pre-split export's rows carry."""
    items, drawn, rows = _split_unit(misses)
    arm_of = None if unrecorded else drawn
    return items, result_rows([("m", "r", rows)], items, {}, set(), scenario_arm=arm_of)


def test_the_gallery_renders_dev_and_unrecorded_but_never_a_splitless_row() -> None:
    """The filter's three ways: a dev row renders, a holdout row does not, a row that simply
    lacks the field raises (report.py's first and only raise), and an `unrecorded` row renders
    because that gallery predates the split."""
    _, rows = _gallery_rows((SPLIT_DEV_EVENT, SPLIT_HOLDOUT_EVENTS[0]))
    assert {row["split"] for row in rows} == {"dev", "holdout"}
    gallery = render_gallery({"score_id": "S"}, rows, Path("/out"))
    assert "/x/B-t-002/still.jpg" in gallery  # the dev miss
    assert "B-t-000" not in gallery  # the holdout miss: no card, no path, no caption
    # A pre-split export's gallery renders everything, because there was no holdout to hide.
    _, unrecorded = _gallery_rows((SPLIT_DEV_EVENT, SPLIT_HOLDOUT_EVENTS[0]), unrecorded=True)
    assert all(row["split"] == "unrecorded" for row in unrecorded)
    old = render_gallery({"score_id": "S"}, unrecorded, Path("/out"))
    assert "/x/B-t-000/still.jpg" in old and "/x/B-t-002/still.jpg" in old
    # The defect case: a row that reaches the gallery with no `split` to filter on.
    nameless = [{k: v for k, v in row.items() if k != "split"} for row in rows]
    with pytest.raises(ValueError, match="B-t-000"):
        render_gallery({"score_id": "S"}, nameless, Path("/out"))
