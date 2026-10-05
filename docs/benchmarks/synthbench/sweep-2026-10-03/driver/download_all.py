#!/usr/bin/env python3
"""Download every sweep model into a PERMANENT library, verify sha256, hard-link into the sweep's folders.

library:  $AGENT_GPU_DIR/models/library/<recipe key>/<file>   (read-only once verified; nothing in the sweep touches it)
sweep:    $AGENT_GPU_DIR/models/sweep/<arm>/<file>           (hard links to the library, so no extra space and
                                                              the sweep's download() sees complete files and skips)
Idempotent and resumable (curl -C -). Stdlib only.
"""
import concurrent.futures as cf, hashlib, json, os, subprocess, sys, threading, time
from pathlib import Path

HOME = Path(os.environ["AGENT_GPU_DIR"]); EXP = HOME / "out/experiments/model-sweep"
LIB = HOME / "models/library"; SWEEP = HOME / "models/sweep"
LOG = EXP / "download_all.log"; MANIFEST = LIB / "MANIFEST.json"
recipes = {r["key"]: r for r in json.load(open(EXP / "recipes.json"))["recipes"]}
sys.path.insert(0, str(EXP)); import sweep  # noqa  (ORDER / SPEC only; main() is not run)
arms = [(a, sweep.SPEC[a][0]) for a in sweep.SPEC]          # (arm, recipe key) in sweep order
lock = threading.Lock(); manifest = json.load(open(MANIFEST)) if MANIFEST.exists() else {}

def log(m):
    with lock, open(LOG, "a") as f: f.write(f"{time.strftime('%F %T')} {m}\n")

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""): h.update(b)
    return h.hexdigest()

def save_manifest():
    with lock:
        tmp = MANIFEST.with_suffix(".tmp"); tmp.write_text(json.dumps(manifest, indent=1, sort_keys=True)); os.replace(tmp, MANIFEST)

def fetch(arm, key, f):
    repo = f.get("repo") or recipes[key]["repo"]; dst = LIB / key / f["path"]; want = f["sha256"]; size = f["sizeBytes"]
    url = f"https://huggingface.co/{repo}/resolve/main/{f['path']}"
    m = manifest.get(f"{key}/{f['path']}")
    if m and dst.exists() and dst.stat().st_size == size and m["sha256"] == want:
        return True                                    # verified earlier; read-only file, not re-hashed
    for attempt in (1, 2):
        # reuse a file the sweep already fetched (hard link, no copy)
        if not dst.exists():
            for src in (SWEEP / arm / f["path"], HOME / "models/sweep-hold" / arm / f["path"]):
                if src.exists() and src.stat().st_size == size: os.link(src, dst); log(f"[{key}] {f['path']} linked from existing {src.parent}"); break
        if not dst.exists() or dst.stat().st_size != size:
            log(f"[{key}] download {f['path']} ({size/1e9:.1f} GB)"); t0 = time.time()
            r = subprocess.run(["curl", "-fL", "--retry", "8", "--retry-delay", "5", "--retry-all-errors", "-C", "-", "-o", str(dst) + ".part", url], capture_output=True, text=True)
            if r.returncode != 0: log(f"[{key}] ERROR curl rc={r.returncode} {r.stderr[-200:]}"); return False
            os.replace(str(dst) + ".part", dst); log(f"[{key}] {f['path']} downloaded in {time.time()-t0:.0f}s")
        got = sha256(dst)
        if got == want:
            manifest[f"{key}/{f['path']}"] = {"arm": arm, "repo": repo, "sizeBytes": size, "sha256": got, "verified_at": time.strftime("%FT%T"), "url": url}
            save_manifest(); log(f"[{key}] {f['path']} sha256 OK")
            if os.path.exists(str(dst) + ".part"): os.remove(str(dst) + ".part"); log(f"[{key}] removed stale {f['path']}.part")
            return True
        log(f"[{key}] SHA MISMATCH {f['path']}: got {got[:16]} want {want[:16]}; removing" + (" and retrying once" if attempt == 1 else ""))
        os.remove(dst)
    return False

def finish_arm(arm, key, ok):
    if not ok: log(f"[{key}] NOT complete; not linked, not locked"); return
    (SWEEP / arm).mkdir(parents=True, exist_ok=True)
    for f in recipes[key]["files"]:
        s, d = LIB / key / f["path"], SWEEP / arm / f["path"]
        if not d.exists(): os.link(s, d)
        os.chmod(s, 0o440)                      # same inode as the sweep's name
    os.chmod(LIB / key, 0o555); log(f"[{key}] complete: verified, linked into sweep/{arm}, library dir read-only")

def main():
    LIB.mkdir(parents=True, exist_ok=True)
    os.chmod(LIB, 0o755)
    complete = {k for _, k in arms if all(f"{k}/{f['path']}" in manifest for f in recipes[k]["files"])}
    for _, key in arms:
        if key in complete: continue
        os.chmod(LIB / key, 0o755) if (LIB / key).exists() else (LIB / key).mkdir()
    jobs = [(a, k, f) for a, k in arms if k not in complete for f in recipes[k]["files"]]
    log(f"already complete and left untouched: {len(complete)} models")
    log(f"start: {len(jobs)} files, {sum(f['sizeBytes'] for _,_,f in jobs)/1e9:.1f} GB across {len(arms)} models")
    res = {}
    with cf.ThreadPoolExecutor(3) as ex:
        futs = {ex.submit(fetch, a, k, f): (a, k, f["path"]) for a, k, f in jobs}
        for fu in cf.as_completed(futs):
            a, k, p = futs[fu]
            try: res[(k, p)] = fu.result()
            except Exception as e: res[(k, p)] = False; log(f"[{k}] EXCEPTION {p}: {e}")
            if all(res.get((k, f["path"])) is not None for f in recipes[k]["files"]) and not any(kk == k and v is None for (kk, _), v in res.items()):
                done = [res[(k, f["path"])] for f in recipes[k]["files"]]
                if len(done) == len(recipes[k]["files"]): finish_arm(a, k, all(done))
    ok = sum(1 for v in res.values() if v); log(f"finished: {ok}/{len(jobs)} files verified this pass")
    total_ok = sum(1 for a, k in arms for f in recipes[k]["files"] if f"{k}/{f['path']}" in manifest)
    log(f"library total: {total_ok}/24 files verified")
    if total_ok == 24: os.chmod(LIB, 0o555); log("library root read-only (chmod u+w to add models)")

if __name__ == "__main__":
    main()
