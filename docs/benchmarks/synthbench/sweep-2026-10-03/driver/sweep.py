#!/usr/bin/env python3
"""Rolling model sweep (owner decision 2026-10-03: evaluate every tier-pick VLM on tierb-v0).

One arm at a time: download -> verify sha256 -> serve (agent-gpu, image ai-vlm:sm103-b11376) -> replay the shipped
prompt at temperature 0 over the 450 exported stills -> score -> stop -> delete weights -> next. The disk holds ~42 GB, the
picks total ~187 GB, so weights were deleted after each arm; since the quota went to 200 GB (2026-10-03) they are KEPT (set SWEEP_DELETE_WEIGHTS=1 to delete). Resumable: arms with a line in results.jsonl are skipped.
Arm 0 is the CONTROL (the shipped Q4_K_M, already on disk) on the new build with the sweep's cache settings; if it does not
reproduce the b7972 baseline (S2 18/209, S3 88/241) the sweep STOPS, because comparability would be in doubt.
Stdlib only. Usage: sweep.py [--only KEY[,KEY]] [--no-gate]
"""
import json, math, os, re, shutil, subprocess, sys, threading, time, urllib.request
from pathlib import Path

HOME = Path(os.environ["AGENT_GPU_DIR"])
EXP = HOME / "out/experiments/model-sweep"
MODELS = HOME / "models"; SWEEP_DIR = MODELS / "sweep"
SB = HOME / "out/sbroot"; EXPORT = SB / "exports/tierb-v0/vss"
REPO = Path("/agents/agent-vss5/workspace")
RECIPES = json.load(open("/tmp/claude-1000/-agents-agent-vss5-workspace/4faabe8e-121a-4a8c-a2aa-5de9bc2eb573/scratchpad/recipes.json"))["recipes"] \
    if os.path.exists("/tmp/claude-1000/-agents-agent-vss5-workspace/4faabe8e-121a-4a8c-a2aa-5de9bc2eb573/scratchpad/recipes.json") else json.load(open(EXP / "recipes.json"))["recipes"]
IMAGE = "ai-vlm:sm103-b11376"; BUILD_PIN = "b11376"
RESULTS = Path(os.environ.get("SWEEP_RESULTS", EXP / "results.jsonl")); LOG = EXP / "sweep.log"
READ_TIMEOUT = 180  # one value for every arm so a timeout means the same thing everywhere
BASELINE = {"s2_fp": 18, "s3_hit": 88}

COMMON = {"SERVICE_NAME": "ai-vlm", "PORT": "8098", "CTX_SIZE": "32768", "PARALLEL": "2", "THREADS": "4", "BATCH_SIZE": "2048",
          "UBATCH_SIZE": "512", "CACHE_TYPE_K": "q8_0", "CACHE_TYPE_V": "q8_0", "FLASH_ATTENTION": "true", "GPU_LAYERS": "99",
          "LLAMA_ARG_IMAGE_MAX_TOKENS": "1280", "LLAMA_ARG_CACHE_RAM": "0", "LLAMA_ARG_CACHE_IDLE_SLOTS": "0"}
THINK_OFF = {"LLAMA_ARG_REASONING": "off"}; THINK_EXTRA = {"chat_template_kwargs": {"enable_thinking": False}}
# key -> (recipe key, env overrides, request extra, vram GiB to declare)
SPEC = {
    "qwen3vl-8b-q8":      ("qwen3vl-8b-instruct-q8_0", {}, {}, 16),
    "qwen35-4b-q8":       ("qwen35-4b-unsloth-q8_0", THINK_OFF, THINK_EXTRA, 10),
    "qwen35-9b-q4km":     ("qwen3.5-9b-q4km", THINK_OFF, THINK_EXTRA, 12),
    "qwen35-9b-q6k":      ("qwen3.5-9b-q6k", THINK_OFF, THINK_EXTRA, 14),
    "gemma4-12b":         ("gemma-4-12b-it-qat-q4_0", {**THINK_OFF, "UBATCH_SIZE": "2048", "LLAMA_ARG_IMAGE_MAX_TOKENS": "1120"}, THINK_EXTRA, 16),
    "qwen3vl-32b-q4km":   ("qwen3-vl-32b-instruct-q4km", {}, {}, 30),
    "gemma4-26b-a4b":     ("gemma-4-26B-A4B-it-qat-q4_0", {**THINK_OFF, "UBATCH_SIZE": "2048", "LLAMA_ARG_IMAGE_MAX_TOKENS": "1120"}, THINK_EXTRA, 24),
    "qwen38-27b-q4km":    ("qwen3.8-27b-ud-q4_k_m", THINK_OFF, THINK_EXTRA, 24),
    "qwen38-27b-q6k":     ("qwen3.8-27b-ud-q6_k", THINK_OFF, THINK_EXTRA, 32),
    "qwen3vl-30b-a3b-q8": ("qwen3vl-30b-a3b-instruct-q8_0", {}, {}, 40),
    "qwen36-35b-a3b-q6k": ("qwen3.6-35b-a3b-ud-q6k", THINK_OFF, THINK_EXTRA, 40),
    "qwen38-27b-iq2s":    ("qwen3.8-27b-gsq-rco-iq2_s", THINK_OFF, THINK_EXTRA, 18),
}
CONTROLS = {"control-q4km": {}, "control-rep": {}, "control-defaultcache": {"LLAMA_ARG_CACHE_RAM": None, "LLAMA_ARG_CACHE_IDLE_SLOTS": None}}
ORDER = list(CONTROLS) + list(SPEC)

def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"; print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def gpu(*args):
    r = sh(["agent-gpu", *args]); return r

def free_gb(path):
    st = os.statvfs(path); return st.f_bavail * st.f_frsize / 1e9

def sha256(path):
    r = sh(["sha256sum", str(path)]); return r.stdout.split()[0]

def download(arm, files, repo):
    d = SWEEP_DIR / arm; d.mkdir(parents=True, exist_ok=True)
    need = sum(f["sizeBytes"] for f in files) / 1e9
    if free_gb(MODELS) < need + 3: raise RuntimeError(f"disk: need {need:.1f} GB, free {free_gb(MODELS):.1f} GB")
    t0 = time.time()
    for f in files:
        dst = d / f["path"]
        if dst.exists() and dst.stat().st_size == f["sizeBytes"]: continue
        url = f"https://huggingface.co/{f.get('repo') or repo}/resolve/main/{f['path']}"
        log(f"[{arm}] download {f['path']} ({f['sizeBytes']/1e9:.1f} GB)")
        r = sh(["curl", "-fL", "--retry", "8", "--retry-delay", "5", "--retry-all-errors", "-C", "-", "-o", str(dst) + ".part", url])
        if r.returncode != 0: raise RuntimeError(f"curl rc={r.returncode}: {r.stderr[-300:]}")
        os.replace(str(dst) + ".part", dst)
    secs = time.time() - t0
    for f in files:
        dst = d / f["path"]
        if dst.stat().st_size != f["sizeBytes"]: raise RuntimeError(f"size mismatch {f['path']}: {dst.stat().st_size} != {f['sizeBytes']}")
        got = sha256(dst)
        if got != f["sha256"]: raise RuntimeError(f"sha256 mismatch {f['path']}: {got} != {f['sha256']}")
    log(f"[{arm}] downloaded + verified {need:.1f} GB in {secs/60:.1f} min")
    return d

def stop_container():
    gpu("stop", "vlm"); gpu("rm", "vlm")

def serve(arm, model_dir_in_container, files, env_over, vram):
    model = next(f for f in files if f["role"] == "model"); mm = next(f for f in files if f["role"] == "mmproj")
    env = {k: v for k, v in {**COMMON, **env_over}.items() if v is not None}
    env.update({"MODEL_PATH": f"{model_dir_in_container}/{model['path']}", "MMPROJ_PATH": f"{model_dir_in_container}/{mm['path']}"})
    cmd = ["agent-gpu", "run", "--name", "vlm", "--image", IMAGE, "--vram", str(vram), "--port", "8098", "--mount", "models:/models", "--user", "0", "--ttl", "24"]
    for k, v in env.items(): cmd += ["--env", f"{k}={v}"]
    r = sh(cmd)
    if r.returncode != 0: raise RuntimeError(f"agent-gpu run failed: {r.stdout[-300:]} {r.stderr[-300:]}")
    port = json.loads(r.stdout[r.stdout.index("{"):r.stdout.rindex("}") + 1])["ports"]["8098"]
    url = f"http://host.docker.internal:{port}"
    t0 = time.time()
    while time.time() - t0 < 1500:
        ps = json.loads(gpu("ps").stdout)["containers"]
        st = next((c for c in ps if c["name"] == "vlm"), None)
        if st and st["state"] == "exited":
            tail = gpu("logs", "vlm").stdout[-1500:]; raise RuntimeError(f"container exited early: {tail}")
        try:
            if urllib.request.urlopen(url + "/health", timeout=5).status == 200: break
        except Exception: pass
        time.sleep(10)
    else: raise RuntimeError("server not healthy within 25 min")
    props = json.loads(urllib.request.urlopen(url + "/props", timeout=20).read())
    log(f"[{arm}] serving: model_path={props.get('model_path')} build={props.get('build_info')} load={time.time()-t0:.0f}s")
    return url, props

def sample_vram(stop, out):
    while not stop.is_set():
        try:
            for c in json.loads(gpu("status").stdout)["containers"]:
                if c["name"] == "vlm" and c.get("vram_actual_mib"): out["peak"] = max(out.get("peak", 0), c["vram_actual_mib"])
        except Exception: pass
        stop.wait(60)

def replay(arm, url, served_id, extra):
    env = {**os.environ, "EXP_TAG": arm, "EXP_URL": url, "EXP_SERVED_ID": served_id, "EXP_READ_TIMEOUT": str(READ_TIMEOUT),
           "EXP_REQUEST_EXTRA": json.dumps(extra), "ENVIRONMENT": "development", "VLM_REQUIRED_BUILD": BUILD_PIN,
           "DATABASE_URL": "postgresql+asyncpg://replay:placeholder-never-connected-xyz@127.0.0.1:5432/unused", "PYTHONPATH": str(REPO),
           "UV_CACHE_DIR": str(HOME / "out/uvcache"), "EXP_LIMIT": os.environ.get("SWEEP_LIMIT", "")}
    out = {}; stop = threading.Event(); th = threading.Thread(target=sample_vram, args=(stop, out), daemon=True); th.start()
    t0 = time.time()
    p = subprocess.run(["uv", "run", "python", str(EXP / "replay_arm.py"), str(SB), str(EXPORT)], cwd=REPO, env=env, capture_output=True, text=True, timeout=4 * 3600)
    stop.set(); th.join(timeout=5)
    (EXP / f"replay-{arm}.log").write_text(p.stdout[-20000:] + "\n--- stderr ---\n" + p.stderr[-5000:])
    m = re.search(r"DONE (\S+) run=(\S+) items=(\d+) S2 (\d+)/(\d+) S3 (\d+)/(\d+) refusals (\d+)", p.stdout)
    if p.returncode != 0 or not m: raise RuntimeError(f"replay failed rc={p.returncode}: {p.stdout[-400:]} {p.stderr[-600:]}")
    return {"replay_id": m[1], "eval_run_id": m[2], "s2_fp": int(m[4]), "s2_n": int(m[5]), "s3_hit": int(m[6]), "s3_n": int(m[7]), "refusals": int(m[8]),
            "replay_seconds": round(time.time() - t0), "vram_peak_mib": out.get("peak")}

def analyze(eval_run_id):
    import sqlite3, collections
    c = sqlite3.connect(f"file:{SB}/eval/tierb-v0/eval.sqlite?mode=ro", uri=True)
    items = {r[0]: json.loads(r[1]) for r in c.execute("select item_id,payload from items")}
    def meta(iid):
        p = items[iid]["media_paths"][0]; lab = json.load(open(os.path.dirname(p) + "/expected_labels.json")); sb = lab["synthbench"]
        return {"scenario": sb["cell"]["scenario"], "group": sb["cell"]["group"], "label": items[iid]["expected_label"], "floor": items[iid]["expected_risk_score"]}
    M = {i: meta(i) for i in items}
    R = {r[0]: (r[1], r[2]) for r in c.execute("select item_id,verdict,risk_score from results where run_id=?", (eval_run_id,))}
    fl = lambda s: 0 if s <= 29 else 30 if s <= 59 else 60 if s <= 84 else 85
    sc = lambda k: R[k][1] if R[k][1] is not None else -1
    ben = [k for k in R if M[k]["label"] == "benign"]; inc = [k for k in R if M[k]["label"] == "incident"]
    GA = {"package_theft", "loitering", "peering_into_windows", "trying_car_doors", "casing_with_phone", "tailgating"}
    GC = {"firearm_visible", "knife_visible", "fire_or_smoke", "masked_intruder_night", "forced_entry"}
    grp = collections.Counter(); grpn = collections.Counter()
    for k in inc:
        g = "A_stranger_intent" if M[k]["scenario"] in GA else "C_object_cued" if M[k]["scenario"] in GC else "B_context_risk"
        grpn[g] += 1; grp[g] += sc(k) >= fl(M[k]["floor"])
    hn = collections.Counter()
    for k in ben:
        if M[k]["group"] == "hard_negative" and sc(k) >= 30: hn[M[k]["scenario"]] += 1
    pos = [sc(k) for k in inc]; neg = [sc(k) for k in ben]
    def auroc():
        vals = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg]); ranks = {}; i = 0
        while i < len(vals):
            j = i
            while j < len(vals) and vals[j][0] == vals[i][0]: j += 1
            for k in range(i, j): ranks[k] = (i + j - 1) / 2 + 1
            i = j
        sp = sum(ranks[k] for k, (v, l) in enumerate(vals) if l == 1); n1, n0 = len(pos), len(neg)
        return (sp - n1 * (n1 + 1) / 2) / (n1 * n0)
    best = 0.0
    for t in sorted(set(pos + neg) | {101}):
        if sum(1 for v in neg if v >= t) / len(neg) <= 0.05: best = max(best, sum(1 for v in pos if v >= t) / len(pos))
    vm = collections.Counter(R[k][0] for k in R)
    return {"auroc": round(auroc(), 3), "tpr_at_5pct_fpr": round(100 * best, 1), "null_scores": sum(1 for k in R if R[k][1] is None),
            "verdicts": dict(vm), "s3_by_group": {g: f"{grp[g]}/{grpn[g]}" for g in sorted(grpn)}, "hard_negative_fps": dict(hn)}

def agreement(eval_run_id):
    """Items whose (verdict, risk_score) equals the control arm's on the same build: determinism for the repeat control, the model effect elsewhere."""
    import sqlite3
    ctrl = next((json.loads(l) for l in RESULTS.read_text().splitlines() if json.loads(l).get("arm") == "control-q4km"), None) if RESULTS.exists() else None
    if not ctrl or not ctrl.get("eval_run_id"): return {}
    c = sqlite3.connect(f"file:{SB}/eval/tierb-v0/eval.sqlite?mode=ro", uri=True)
    q = lambda rid: {r[0]: (r[1], r[2]) for r in c.execute("select item_id,verdict,risk_score from results where run_id=?", (rid,))}
    a, b = q(ctrl["eval_run_id"]), q(eval_run_id)
    return {"identical_to_control": sum(1 for k in a if a[k] == b.get(k)), "items_compared": len(a)}

def done_keys():
    return {json.loads(l)["arm"] for l in RESULTS.read_text().splitlines()} if RESULTS.exists() else set()

def summary():
    rows = [json.loads(l) for l in RESULTS.read_text().splitlines()] if RESULTS.exists() else []
    out = ["| Arm | Model | S2 false alarms | S3 incidents | AUROC | recall @5% FPR | refusals | identical to control | VRAM peak (MiB) | replay (min) | error |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if r.get("error"): out.append(f"| {r['arm']} | {r.get('served_id','')} |  |  |  |  |  |  |  |  | {r['error'][:120]} |"); continue
        out.append(f"| {r['arm']} | {r['served_id']} | {r['s2_fp']}/{r['s2_n']} = {100*r['s2_fp']/max(1,r['s2_n']):.1f}% | {r['s3_hit']}/{r['s3_n']} = {100*r['s3_hit']/max(1,r['s3_n']):.1f}% | {r.get('auroc')} | {r.get('tpr_at_5pct_fpr')}% | {r['refusals']} | {r.get('identical_to_control','')}/{r.get('items_compared','')} | {r.get('vram_peak_mib')} | {round(r['replay_seconds']/60)} |  |")
    (EXP / "summary.md").write_text("\n".join(out) + "\n")

def run_arm(arm):
    t0 = time.time(); rec = {"arm": arm, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    keep = False
    try:
        if arm in CONTROLS:
            files = [{"path": "Qwen3VL-8B-Instruct-Q4_K_M.gguf", "role": "model"}, {"path": "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf", "role": "mmproj"}]
            cdir, served, env_over, extra, vram, keep = "/models/vlm", "Qwen3VL-8B-Instruct-Q4_K_M", CONTROLS[arm], {}, 16, True
        else:
            rkey, env_over, extra, vram = SPEC[arm]; recipe = next(r for r in RECIPES if r["key"] == rkey)
            files = recipe["files"]; served = recipe["servedId"]; rec["repo"] = recipe["repo"]
            download(arm, files, recipe["repo"]); cdir = f"/models/sweep/{arm}"
        rec["served_id"] = served; stop_container()
        url, props = serve(arm, cdir, files, env_over, vram); rec["build_info"] = props.get("build_info")
        res = replay(arm, url, served, extra); rec.update(res)
        try: rec.update(analyze(res["eval_run_id"]))
        except Exception as e: rec["analyze_error"] = str(e)[:200]
        try: rec.update(agreement(res["eval_run_id"]))
        except Exception as e: rec["agreement_error"] = str(e)[:200]
        log(f"[{arm}] S2 {rec['s2_fp']}/{rec['s2_n']}  S3 {rec['s3_hit']}/{rec['s3_n']}  AUROC {rec.get('auroc')}  recall@5%FPR {rec.get('tpr_at_5pct_fpr')}%  refusals {rec['refusals']}  VRAM peak {rec['vram_peak_mib']} MiB")
    except Exception as e:
        rec["error"] = str(e)[:600]; log(f"[{arm}] ERROR: {str(e)[:600]}")
    finally:
        stop_container()
        if arm not in CONTROLS and os.environ.get("SWEEP_DELETE_WEIGHTS") == "1": shutil.rmtree(SWEEP_DIR / arm, ignore_errors=True)
    rec["wall_seconds"] = round(time.time() - t0)
    with open(RESULTS, "a") as f: f.write(json.dumps(rec) + "\n")
    summary(); return rec

def main():
    only = None; gate = True
    for a in sys.argv[1:]:
        if a.startswith("--only"): only = sys.argv[sys.argv.index(a) + 1].split(",")
        if a == "--no-gate": gate = False
    SWEEP_DIR.mkdir(parents=True, exist_ok=True); done = done_keys()
    for arm in ORDER:
        if arm in done or (only and arm not in only): continue
        log(f"=== arm {arm} === (free disk {free_gb(MODELS):.1f} GB)")
        rec = run_arm(arm)
        if arm == "control-q4km" and gate:
            bad = rec.get("error") or abs(rec["s2_fp"] - BASELINE["s2_fp"]) > 4 or abs(rec["s3_hit"] - BASELINE["s3_hit"]) > 4 or rec["refusals"] > 2
            if bad:
                log("CONTROL DID NOT REPRODUCE the b7972 baseline (S2 18/209, S3 88/241): STOPPING so the owner/assistant can decide. See results.jsonl.")
                (EXP / "STOPPED_AT_CONTROL").write_text(json.dumps(rec, indent=1)); return
    log("sweep finished"); summary()

if __name__ == "__main__":
    main()
