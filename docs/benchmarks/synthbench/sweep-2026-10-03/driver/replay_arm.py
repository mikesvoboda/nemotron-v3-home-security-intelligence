"""One sweep arm: synthbench replay minus ONE check (renderer_stopped), owner-directed 2026-10-03.
Everything else in execute() is kept (health, served identity, check_stills, check_current, importer, shipped VlmClient,
run_replay, run.json). Per-arm identity, request extras and timeout come from the environment; the repo is untouched.
EXP_TAG EXP_URL EXP_SERVED_ID [EXP_REQUEST_EXTRA json] [EXP_READ_TIMEOUT s] [EXP_LIMIT] [EXP_RUBRIC=1]  ROOT=argv[1] EXPORT=argv[2]"""
import asyncio, json, os, sys
from datetime import UTC, datetime
from pathlib import Path
import httpx
from backend.evaluation.eval_store import EvalStore
from backend.evaluation.vlm_replay import git_commit, run_replay
from synthbench.run import replay as R
from synthbench.run.models import Model

OLD = "how threatening it is (risk_score 0-100)."
RUBRIC = open(os.path.dirname(os.path.abspath(__file__)) + "/rubric.txt").read().strip() if os.environ.get("EXP_RUBRIC") == "1" else None
EXTRA = json.loads(os.environ.get("EXP_REQUEST_EXTRA") or "{}")
TAG, URL, SERVED = os.environ["EXP_TAG"], os.environ["EXP_URL"], os.environ["EXP_SERVED_ID"]
TIMEOUT = float(os.environ.get("EXP_READ_TIMEOUT") or 180)
LIMIT = os.environ.get("EXP_LIMIT"); LIMIT = int(LIMIT) if LIMIT else None

class Shim(httpx.AsyncBaseTransport):
    def __init__(self): self.inner = httpx.AsyncHTTPTransport(); self.n = 0
    async def handle_async_request(self, request):
        if request.url.path.endswith("/chat/completions") and (EXTRA or RUBRIC):
            body = json.loads(request.content)
            body.update(EXTRA)
            if RUBRIC:
                for p in body["messages"][0]["content"]:
                    if p.get("type") == "text" and OLD in p["text"]: p["text"] = p["text"].replace(OLD, RUBRIC)
            data = json.dumps(body).encode()
            headers = [(k, v) for k, v in request.headers.raw if k.lower() != b"content-length"]
            request = httpx.Request(request.method, request.url, headers=headers, content=data, extensions=request.extensions); self.n += 1
        return await self.inner.handle_async_request(request)
    async def aclose(self): await self.inner.aclose()

root, export = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
model = Model(name=f"sweep-{TAG}", transport="ai-vlm", served_id=SERVED, url_env="AI_VLM_URL", default_url=URL, read_timeout=TIMEOUT, thinking="off (server + request)" if EXTRA else "n/a")
shim = Shim()
assert httpx.get(f"{URL}/health", timeout=10).status_code == 200
identity, build = R.served_identity(model, URL, R._get)
assert identity == SERVED, f"{URL} serves {identity!r}, expected {SERVED!r}"
ran_under = R.conditions(model, export)
started = datetime.now(UTC)
replay_id = f"{started:%Y%m%dT%H%M%SZ}-{TAG}"
runs_dir = root / "runs" / "replays"; store_path = root / "eval" / "tierb-v0" / "eval.sqlite"
run_dir = runs_dir / replay_id; store_path.parent.mkdir(parents=True, exist_ok=True)
with EvalStore(store_path) as store:
    R.check_stills(store, export); new, already = R.import_export(store, export); run_dir.mkdir(parents=True)
    candidate = f"{SERVED}@ai-vlm:{build}"
    print(f"replay {replay_id} limit={LIMIT} extra={EXTRA} timeout={TIMEOUT}", flush=True)
    report = asyncio.run(run_replay(store, candidate=candidate, engine="llama.cpp", limit=LIMIT, make_client=R.client_factory(model, URL, export, shim)))
record = {"replay_id": replay_id, "model": model.name, "served_id": SERVED, "transport": "ai-vlm", "url": URL, "build": build, **ran_under,
  "export": str(export), "store": str(store_path), "eval_run_id": report["run_id"], "imported_new": new, "already_imported": already, "limit": LIMIT, "commit": git_commit(),
  "started_utc": started.isoformat(timespec="seconds"), "report": report,
  "experiment": {"tag": TAG, "request_extra": EXTRA, "rubric": bool(RUBRIC), "requests_rewritten": shim.n, "note": "model-sweep arm via transport shim; repo client untouched"},
  "renderer_check": "SKIPPED by owner direction 2026-10-03: not a `synthbench replay` run; VLM served from a fenced agent-gpu container; renderer idle"}
(run_dir / "run.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
s2, s3 = report["s2"], report["s3"]["all"]
print(f"DONE {replay_id} run={report['run_id']} items={report['n_items']} S2 {s2['fp']}/{s2['n']} S3 {s3['hit']}/{s3['n']} refusals {report['s5']['refusals']} shim={shim.n}")
