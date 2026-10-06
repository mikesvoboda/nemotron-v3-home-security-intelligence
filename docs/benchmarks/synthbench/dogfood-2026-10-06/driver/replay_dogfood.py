"""ISS-087 dogfood replay, OD-23 shape (owner-directed 2026-10-07): `synthbench replay`'s
execute() MINUS ONE check (renderer_stopped). Every other shipped guard is kept and comes from
the library itself (health, served identity via R.served_identity, R.conditions incl. the
ISS-087 server_settings declaration, R.check_stills, R.import_export incl. check_current,
R.import_split (ISS-016), the shipped VlmClient via R.client_factory, run_replay, the run.json
format `score` reads). The repo is untouched; this file lives outside it.
run.json gains `renderer_check: SKIPPED ...` per OD-23 (the sandbox cannot read the renderer
unit; the VLM is a fenced agent-gpu container with its own VRAM budget, so the check's premise
does not hold for this arm).

argv: URL EXPORT SBROOT [LIMIT]
env:  ENVIRONMENT=development DATABASE_URL=... (placeholder; the replay process has no backend DB)
"""
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from backend.evaluation.eval_store import EvalStore
from backend.evaluation.vlm_replay import git_commit, run_replay
from synthbench.commands.common import taxonomy
from synthbench.run import replay as R
from synthbench.run.models import MODELS

# Declared, not observed (ISS-087): the exact llama-server invocation the fenced container runs,
# i.e. the image CMD assembled from the env passed to `agent-gpu run` (compose ai-vlm defaults,
# handoff 2026-10-03 serving recipe). Written by the launcher into DOGFOOD_SERVER_SETTINGS.
SERVER_SETTINGS = (
    "agent-gpu container vss8-dogfood, image localhost/agent-vss8/ai-vlm:sm103 "
    "(llama.cpp build reported at /props), image CMD with compose ai-vlm defaults: --model "
    "/models/qwen3vl-8b-instruct-q4km/Qwen3VL-8B-Instruct-Q4_K_M.gguf --mmproj "
    "/models/qwen3vl-8b-instruct-q4km/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf --alias Qwen3VL-8B "
    "--sleep-idle-seconds 300 --cache-type-k q8_0 --cache-type-v q8_0 --host 0.0.0.0 --port 8098 "
    "--n-gpu-layers auto --ctx-size 32768 --parallel 2 --threads 4 --threads-batch 4 "
    "--batch-size 2048 --ubatch-size 512 --cont-batching --metrics --cache-reuse 256 --jinja "
    "--flash-attn on; weights sha256 67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2 "
    "+ mmproj c6ba85508d82f42590e6eb77d5340369ab6fecf107a7561d809523d8aa5f3bfd (verified before serve)"
)

url, export, root = sys.argv[1], Path(sys.argv[2]).resolve(), Path(sys.argv[3])
limit = int(sys.argv[4]) if len(sys.argv) > 4 else None
model = MODELS["qwen3-vl-8b"]
# nosemgrep[ssrf-requests]: the URL is the operator's own argv, pointing at the fenced agent-gpu
# endpoint this session started and then asserts serves the expected model at /props. A local
# health probe of a locally-served endpoint is the driver's premise, not a request forged by it.
assert httpx.get(f"{url}/health", timeout=10).status_code == 200, f"{url}/health not 200"  # nosemgrep: ssrf-requests
identity, build = R.served_identity(model, url, R._get)
assert identity == model.served_id, f"{url} serves {identity!r}, expected {model.served_id!r}"
ran_under = R.conditions(model, export, SERVER_SETTINGS)
started = datetime.now(UTC)
tax_version = taxonomy().version
replay_id = f"{started:%Y%m%dT%H%M%SZ}-{model.name}"
runs_dir, store_path = root / "runs" / "replays", root / "eval" / tax_version / "eval.sqlite"
run_dir = runs_dir / replay_id
store_path.parent.mkdir(parents=True, exist_ok=True)
with EvalStore(store_path) as store:
    R.check_stills(store, export)
    new, already = R.import_export(store, export)
    split = R.import_split(store, export)
    run_dir.mkdir(parents=True)
    candidate = f"{model.served_id}@{model.transport}" + (f":{build}" if build else "")
    print(f"replay {replay_id} build={build} limit={limit} split={split['split_sha256'] or 'none'}", flush=True)
    report = asyncio.run(
        run_replay(store, candidate=candidate, engine="llama.cpp", limit=limit,
                   make_client=R.client_factory(model, url, export, None))
    )
record = {
    "replay_id": replay_id, "model": model.name, "served_id": model.served_id,
    "transport": model.transport, "url": url, "build": build, **ran_under,
    "export": str(export), "store": str(store_path), "eval_run_id": report["run_id"],
    "imported_new": new, "already_imported": already, "limit": limit, **split,
    "commit": git_commit(), "started_utc": started.isoformat(timespec="seconds"),
    "report": report,
    "renderer_check": "SKIPPED by owner direction 2026-10-07 (OD-23): not a `synthbench replay` "
    "run; VLM served from a fenced agent-gpu container with its own VRAM budget; renderer idle; "
    "all other shipped checks ran",
}
(run_dir / "run.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
s2, s3 = report["s2"], report["s3"]["all"]
print(f"DONE {replay_id} run={report['run_id']} items={report['n_items']} "
      f"S2 {s2['fp']}/{s2['n']} S3 {s3['hit']}/{s3['n']} refusals {report['s5']['refusals']}")
