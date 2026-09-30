"""`score` (P5a design §5): S2 and S3 from `s_metrics`, slices, the risk band, the audit's
exclusions and truth error, the comparison, the report and the command."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from synthbench import cli
from synthbench.commands.audit import audit_log
from synthbench.export import vss
from synthbench.score.metrics import MIN_N, Item, band_position, outcome, score_models
from synthbench.score.report import markdown
from synthbench.score.scoring import weights_identity

from backend.evaluation.eval_store import EvalStore
from backend.evaluation.label_import import import_generated_items
from backend.evaluation.levels import floor_for_expected_score
from backend.evaluation.s_metrics import s2_false_positive_rate, s3_recall
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


# The command, end to end, over a real export and eval store.


def _world(
    root: Path,
    scores: dict[str, dict[str, int | None]],
    records: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """An export of three threats and twelve benign scenes, imported; one replay per model,
    its `run.json` updated with `records[model]`."""
    events = [(f"B-t-{i:03d}", "threat") for i in range(3)]
    events += [(f"B-b-{i:03d}", "benign") for i in range(12)]
    export = root / "exports" / h.VERSION / "vss"
    for event_id, group in events:
        facts = _facts(event_id, group)
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
    ids = []
    with EvalStore(store_path) as store:
        assert not [r for r in import_generated_items(corpus_dir=export, store=store) if r.skipped]
        for model, by_event in scores.items():
            run_id = store.start_run(engine="llama.cpp", model=model)
            for event_id, group in events:
                item = _item(event_id, group)
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
            } | (records or {}).get(model, {})
            run_dir = root / "runs" / "replays" / replay_id
            run_dir.mkdir(parents=True)
            (run_dir / "run.json").write_text(json.dumps(record))
            ids.append(replay_id)
    return ids


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
    },
    "cosmos-reason2-8b": {
        "transport": "vllm",
        "enforcement_probe": False,
        "request_extra": {"max_tokens": 4096},
        "max_tokens": 4096,
        "read_timeout": 120.0,
        "system_message": COSMOS_FORMAT,
    },
    "flagship": {
        "transport": "vllm",
        "enforcement_probe": False,
        "request_extra": {"chat_template_kwargs": {"enable_thinking": False}},
        "max_tokens": 1024,
        "read_timeout": 25.0,
        "system_message": None,
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
    price of their columns (decision A7): the report states them beside the product model's."""
    out = _scored(tmp_path)
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "Comparison models may run under different conditions" in text
    rows = {
        "| qwen3-vl-8b | ai-vlm | shipped | model default | 1024 | 25 s | on |",
        "| cosmos-reason2-8b | vllm | shipped + system message (A7) | model default | 4096 "
        "| 120 s | off |",
        "| flagship | vllm | shipped | off | 1024 | 25 s | off |",
    }
    assert rows <= set(text.splitlines())
    assert json.dumps(COSMOS_FORMAT) in text  # the system message, verbatim
    identity = json.loads((out / "metrics.json").read_text())["identity"]
    by_model = {replay["model"]: replay for replay in identity["replays"]}
    for model, conditions in CONDITIONS.items():
        assert {key: by_model[model][key] for key in conditions} == conditions
    store = tmp_path / "eval" / h.VERSION / "eval.sqlite"
    assert identity["eval_store"] == {"path": str(store)}


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
