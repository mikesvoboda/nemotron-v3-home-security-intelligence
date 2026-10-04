#!/usr/bin/env python3
"""Export the model sweep's per-item results and arm identities from the OFF-REPO eval store.

Reads (read-only): $SB/eval/tierb-v0/eval.sqlite, the sweep's results.jsonl and recipes.json, and each item's
expected_labels.json next to its still. Writes items.csv (one row per item, a score and a verdict per arm) and arms.csv
(one row per arm: identity, conditions, aggregate readings). analysis.py recomputes every statistic from those two files, so
nothing else in this folder needs the store. The store itself is not committed (D10: it stays off-repo).

Usage: extract.py OUT_DIR   (needs $AGENT_GPU_DIR, the sweep driver directory and the synthbench root mounted)
"""
import csv, hashlib, json, os, sqlite3, sys
from pathlib import Path

HOME = Path(os.environ["AGENT_GPU_DIR"])
SB = HOME / "out/sbroot"
EXP = HOME / "out/experiments/model-sweep"
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)

# Scenario groups exactly as the sweep's analysis defined them (sweep.py analyze()).
GROUP_A = {"package_theft", "loitering", "peering_into_windows", "trying_car_doors", "casing_with_phone", "tailgating"}
GROUP_C = {"firearm_visible", "knife_visible", "fire_or_smoke", "masked_intruder_night", "forced_entry"}
floor_level = lambda s: 0 if s <= 29 else 30 if s <= 59 else 60 if s <= 84 else 85  # levels.py: low 0-29, medium 30-59, high 60-84, critical 85+

con = sqlite3.connect(f"file:{SB}/eval/tierb-v0/eval.sqlite?mode=ro", uri=True)
items = {r[0]: json.loads(r[1]) for r in con.execute("select item_id, payload from items")}

def meta(iid):
    p = items[iid]["media_paths"][0]
    lab = json.load(open(os.path.dirname(p) + "/expected_labels.json"))["synthbench"]["cell"]
    label = items[iid]["expected_label"]
    sc = lab["scenario"]
    s3g = ""
    if label == "incident":
        s3g = "A_stranger_intent" if sc in GROUP_A else "C_object_cued" if sc in GROUP_C else "B_context_risk"
    floor = floor_level(items[iid]["expected_risk_score"]) if label == "incident" else ""
    return {"item_id": iid, "label": label, "kind": lab["group"], "scenario": sc, "s3_group": s3g, "floor_level": floor}

META = {i: meta(i) for i in sorted(items)}
results = [json.loads(l) for l in open(EXP / "results.jsonl")]
SPEC = {  # sweep.py SPEC: arm -> (recipe key, env overrides, request extra)
    "qwen3vl-8b-q8": "qwen3vl-8b-instruct-q8_0", "qwen35-4b-q8": "qwen35-4b-unsloth-q8_0", "qwen35-9b-q4km": "qwen3.5-9b-q4km",
    "qwen35-9b-q6k": "qwen3.5-9b-q6k", "gemma4-12b": "gemma-4-12b-it-qat-q4_0", "qwen3vl-32b-q4km": "qwen3-vl-32b-instruct-q4km",
    "gemma4-26b-a4b": "gemma-4-26B-A4B-it-qat-q4_0", "qwen38-27b-q4km": "qwen3.8-27b-ud-q4_k_m", "qwen38-27b-q6k": "qwen3.8-27b-ud-q6_k",
    "qwen3vl-30b-a3b-q8": "qwen3vl-30b-a3b-instruct-q8_0", "qwen36-35b-a3b-q6k": "qwen3.6-35b-a3b-ud-q6k", "qwen38-27b-iq2s": "qwen3.8-27b-gsq-rco-iq2_s",
}
THINKING_OFF = {"qwen35-4b-q8", "qwen35-9b-q4km", "qwen35-9b-q6k", "gemma4-12b", "gemma4-26b-a4b", "qwen38-27b-q4km", "qwen38-27b-q6k", "qwen36-35b-a3b-q6k", "qwen38-27b-iq2s"}
GEMMA = {"gemma4-12b", "gemma4-26b-a4b"}
recipes = {r["key"]: r for r in json.load(open(EXP / "recipes.json"))["recipes"]}

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""): h.update(b)
    return h.hexdigest()

per_arm = {}
for r in results:
    rows = {iid: (v, s) for iid, v, s in con.execute("select item_id, verdict, risk_score from results where run_id=?", (r["eval_run_id"],))}
    assert set(rows) == set(META), (r["arm"], len(rows))
    per_arm[r["arm"]] = rows

with open(OUT / "items.csv", "w", newline="") as f:
    w = csv.writer(f)
    cols = ["item_id", "label", "kind", "scenario", "s3_group", "floor_level"]
    for r in results: cols += [f"{r['arm']}__score", f"{r['arm']}__verdict"]
    w.writerow(cols)
    for iid in sorted(META):
        m = META[iid]; row = [m[c] for c in cols[:6]]
        for r in results:
            v, s = per_arm[r["arm"]][iid]; row += ["" if s is None else s, v]
        w.writerow(row)

ctrl_model = HOME / "models/vlm/Qwen3VL-8B-Instruct-Q4_K_M.gguf"; ctrl_mm = HOME / "models/vlm/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"
ctrl_ident = {"repo": "Qwen/Qwen3-VL-8B-Instruct-GGUF", "model_file": ctrl_model.name, "model_sha256": sha(ctrl_model), "model_bytes": ctrl_model.stat().st_size,
              "mmproj_file": ctrl_mm.name, "mmproj_sha256": sha(ctrl_mm), "mmproj_bytes": ctrl_mm.stat().st_size}
with open(OUT / "arms.csv", "w", newline="") as f:
    cols = ["arm", "role", "repo", "model_file", "model_bytes", "model_sha256", "mmproj_file", "mmproj_bytes", "mmproj_sha256", "llama_cpp_build", "replay_commit", "thinking_forced_off", "image_max_tokens",
            "s2_false_alarms", "s2_n", "s3_hits", "s3_n", "refusals", "uncertain", "auroc", "recall_at_5pct_fpr", "vram_peak_mib", "replay_minutes",
            "latency_median_ms", "latency_p95_ms", "latency_max_ms", "identical_to_control_items", "replay_id", "eval_run_id", "run_json"]
    w = csv.writer(f); w.writerow(cols)
    for r in results:
        a = r["arm"]
        if a.startswith("control"): ident = ctrl_ident; role = a
        else:
            rec = recipes[SPEC[a]]; files = rec["files"]; mdl = next(x for x in files if x.get("role") in (None, "model") and "mmproj" not in x["path"].lower()); mm = next(x for x in files if "mmproj" in x["path"].lower())
            ident = {"repo": rec["repo"], "model_file": mdl["path"], "model_sha256": mdl["sha256"], "model_bytes": mdl["sizeBytes"], "mmproj_file": mm["path"], "mmproj_sha256": mm["sha256"], "mmproj_bytes": mm["sizeBytes"]}; role = "model"
        rj = SB / "runs/replays" / r["replay_id"] / "run.json"; d = json.load(open(rj)); lat = d["report"].get("latency_ms_indicative_only", {})
        w.writerow([a, role, ident["repo"], ident["model_file"], ident["model_bytes"], ident["model_sha256"], ident["mmproj_file"], ident["mmproj_bytes"], ident["mmproj_sha256"], r["build_info"], d["commit"],
                    "yes" if a in THINKING_OFF else "no", 1120 if a in GEMMA else 1280, r["s2_fp"], r["s2_n"], r["s3_hit"], r["s3_n"], r["refusals"],
                    d["report"]["verdict_mix"]["verdict_mix"].get("uncertain", 0), r.get("auroc"), r.get("tpr_at_5pct_fpr"), r.get("vram_peak_mib"), round(r["replay_seconds"] / 60, 1),
                    lat.get("median"), lat.get("p95"), lat.get("max"), r.get("identical_to_control", ""), r["replay_id"], r["eval_run_id"], f"runs/replays/{r['replay_id']}/run.json"])
print("wrote", OUT / "items.csv", OUT / "arms.csv", "items:", len(META), "arms:", len(results))
