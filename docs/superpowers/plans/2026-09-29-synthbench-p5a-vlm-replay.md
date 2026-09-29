# Synthbench P5a: VLM Replay Scoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score the product VLM (Qwen3-VL-8B through the shipped `ai-vlm` and `VlmClient`), and the
flagship and Cosmos-Reason2-8B as comparison models, on 450 synthetic Tier B stills, with S2/S3
from the shared `s_metrics` definitions and an owner audit of 60 stills.

**Architecture:** `synthbench export vss` writes ready Tier B events in the layout
`import_generated_items` reads. `synthbench replay` imports that export into an eval store and
runs the existing `vlm_replay.run_replay` against one served model. `synthbench audit` serves a
loopback page for the owner's 60-still audit. `synthbench score` joins replay results, the
export's facts and the audit into metrics and a report. Only `synthbench/run/` and
`synthbench/score/` import `backend`.

**Tech Stack:** Python 3.14 (`uv run`), pydantic, httpx, the repo's `backend/evaluation`
(`EvalStore`, `label_import`, `vlm_replay`, `s_metrics`, `levels`), `backend/services/vlm_client.py`,
llama.cpp (`ai-vlm` image `sm103-v12`), vLLM (`vllm/vllm-openai:nightly-aarch64`), podman.

**Spec:** `docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` (read it with this
plan; it is the authority). Parent: `docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md`.

## Global Constraints

- Tests live in `backend/tests/unit/synthbench/` (CI runs only `backend/tests/unit/`), except the
  importer's, which live in `backend/tests/unit/evaluation/test_label_import.py`. No GPU, podman,
  docker or network in tests; every HTTP call and subprocess is faked. pytest-timeout is 5 s; the
  suite runs under xdist and `-p randomly`.
- Only `synthbench/score/` and `synthbench/run/` may import `backend`
  (`backend/tests/unit/synthbench/test_import_rule.py` parses every import, including ones inside
  functions). Commands that use `run/` or `score/` import them inside `run()`: `cli.py` imports
  every command at startup, and the generation agent's commands must not pay for `backend`.
- Exit codes: 0 done, 1 the request needs fixing (`RequestError`), 2 stop and ask the owner
  (`AskOwner`, `CorpusError`).
- The corpus (`$SYNTHBENCH_ROOT/corpus/`) is append-only: P5a reads it and never writes it.
  P5a writes only under `$SYNTHBENCH_ROOT/exports/`, `$SYNTHBENCH_ROOT/eval/`,
  `$SYNTHBENCH_ROOT/runs/` and `$SYNTHBENCH_ROOT/audits/`, and weights under
  `/export/models/ai_models/`.
- S2 and S3 are computed only by `backend/evaluation/s_metrics.py` (one definition).
- Every metric cell carries n and a 95% Wilson interval; a cell under n = 10 reads
  `insufficient (n=…)`.
- Replay runs only while `synthbench-renderer` is stopped, one served model at a time, each well
  under 50 GiB of GPU memory.
- Synthetic stills only; no real camera pixel is read, copied or sent anywhere.
- Every new command and option is documented in `docs/synthbench/command-reference.md`
  (`test_command_reference.py` compares it with argparse). The new commands are the owner's: they
  never appear in `docs/synthbench/agent-handoff.md`.
- Line length 100; ruff, mypy and prettier through the pre-commit gate:
  `SKIP=semgrep uvx pre-commit run --files <files>` must exit 0 before every commit (the semgrep
  hook fails locally on its own `pkg_resources` import). Conventional commit messages ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Rulings made while planning (the executor does not revisit these)

- **P5a-R1. Images.** Qwen3-VL-8B and Qwen3-VL-4B run on `localhost/agent-vss1/ai-vlm:sm103-v12`
  (llama.cpp `b7972-e06088da0`): the build the VSS bake-off measured Qwen3-VL-8B on (VSS ledger
  2.2.4) and the Dockerfile's default `LLAMA_CPP_REF`. Nemotron-12B-VL needs
  `ai-vlm:sm103-b11090` (`b11090-b1c2863e2`, ledger 2.2.3). Task 1 copies both images from the
  agent-gpu store; nothing is rebuilt.
- **P5a-R2. The comparison adapter is the shipped client.** `VlmClient.assess` already posts an
  OpenAI-style `/v1/chat/completions` body with `response_format: json_schema`, which vLLM serves.
  Its only llama.cpp dependency is the enforcement probe (`/props`), which
  `vlm_enforcement_probe_enabled=False` skips. So vLLM models run through `VlmClient` with the
  probe off and an httpx transport that adds the served model's name as `model`. This meets spec
  §3 (the shipped prompt, schema and verdict parser; only the transport differs) with the least
  code.
- **P5a-R3. Import is part of replay.** `synthbench replay` imports the export into the eval store
  first (idempotent: ids are deterministic and items immutable). A skip whose reason is not
  "already imported" exits 2, so no item goes missing silently.
- **P5a-R4. The timestamp reaches the prompt verbatim.** `vlm_replay.client_factory` pins
  `camera_timezone=None`, so the prompt's `Time:` line is the stored string. The export writes
  local time with its UTC offset. The spec's measurement row saying the epoch sentinel reads
  "19:00 the previous evening" is corrected in Task 1: in replay it reads
  `1970-01-01T00:00:00+00:00`, midnight UTC, for every scene.
- **P5a-R5. Weights** are copied to `/export/models/ai_models/vlm/`, files mode 0644 and
  directories 0755: `ai-vlm` runs as uid 1000 `llama`, and fetched weights arrived mode 640
  (VSS ledger finding F).
- **P5a-R6. Layout.** The eval store is `$SYNTHBENCH_ROOT/eval/<version>/eval.sqlite`; a replay
  writes `$SYNTHBENCH_ROOT/runs/replays/<replay_id>/run.json`; a score writes
  `$SYNTHBENCH_ROOT/runs/scores/<score_id>/`; the audit appends to
  `$SYNTHBENCH_ROOT/audits/<version>/audit.jsonl`.
- **P5a-R7. The export library holds the pure pieces** (the category map, the timestamp rule,
  the labels document, writing and reading a set) in `synthbench/export/vss.py`; the command
  (`synthbench/commands/export.py`) owns corpus traversal and error mapping, as P3's commands do.
- **P5a-R8. The audit page is a pure handler** (`handle(method, path, body) -> Response`) behind a
  thin `http.server` wrapper, so its tests need no socket.
- **P5a-R9. The capture root is the export.** `VlmClient` refuses any image outside
  `settings.foscam_base_path` (`/export/foscam` by default), so replay's client factory sets it
  to the export directory; without it every item comes back refused. Replay always injects its own
  `make_client`, so `run_replay`'s report says `vlm_url_source: injected`, and `run.json`
  records the URL instead.
- **P5a-R10. Tasks 2–5 were built during planning.** Their code was written test-first and
  mutation-checked while the plan was written, then committed at the owner's request (`aadf8b87`,
  `c2a1566b`, `fe8d50f1`, `e175c6c7`) and merged with main (`c444456d`). Execution runs the task
  review on each commit against its task text and implements only what a review or Task 1
  finds. Task 6 was built the same way after the merge (`4b653251`).
- **P5a-R11. Run identity is what the host can show.** Each replay's `run.json` gives its
  endpoint, the llama.cpp build `/props` reports and the commit it ran at. Weights: for `ai-vlm`
  models, the model file's line in the `SHA256SUMS` Task 1 writes; for vLLM models, the Hugging
  Face snapshot revision; otherwise `unrecorded`. No endpoint reports the vLLM image, so its
  digest is pinned once, in the runbook's start command (Task 1), not per run.
- **P5a-R12. The two headlines.** "Every item" is every replayed item except the generation
  errors (events whose scene the owner answered no), per spec §4: such an event leaves every
  metric. "Audited" is the audited items whose scene the owner confirmed. Spec §4's "audited facts
  become `audited`" is met in the report's terms: P5a writes nothing into the append-only corpus.
- **P5a-R13. `score` takes its inputs from the replays.** Each replay's `run.json` names its eval
  store and export; `score` has only `--replay` (repeatable), scores one replay per model, and
  refuses replays that name different stores or exports. Labels and S3 floors come from the eval
  store, as `vlm_replay` derives them; facts and stills from the export.
- **P5a-R14. Right and wrong, for the comparison.** A hit or a clear benign item is right; a
  miss, a false alarm or a refusal is wrong. Agreement is equal outcomes (`hit`, `miss`,
  `false_alarm`, `clear`, `refused`) over the items both models replayed.

## Files

| Path                                                                                 | Task | Responsibility                                                            |
| ------------------------------------------------------------------------------------ | ---- | ------------------------------------------------------------------------- |
| `.env.bench`                                                                         | 1    | this host's values for `ai-vlm` under compose                             |
| `docs/benchmarks/synthbench/p5a-probes.md`                                           | 1    | the live probe's evidence                                                 |
| `backend/evaluation/label_import.py`                                                 | 2    | the optional `timestamp` key                                              |
| `backend/tests/unit/evaluation/test_label_import.py`                                 | 2    | its tests                                                                 |
| `synthbench/export/__init__.py`, `vss.py`, `AGENTS.md`                               | 3    | category map, timestamp rule, labels document, write and read a set       |
| `synthbench/commands/export.py`                                                      | 3    | `export vss`: traverse the corpus, write the sets, summarize              |
| `backend/tests/unit/synthbench/test_export_vss.py`                                   | 3    | export tests and the round trip through `import_generated_items`          |
| `synthbench/audit/__init__.py`, `sample.py`, `page.py`, `AGENTS.md`                  | 4    | the stratified sample, the questions, the page and its answer log         |
| `synthbench/commands/audit.py`                                                       | 4    | `audit`: serve the page                                                   |
| `backend/tests/unit/synthbench/test_audit.py`                                        | 4    | sampler, questions, handler                                               |
| `synthbench/run/__init__.py`, `models.py`, `replay.py`, `AGENTS.md`                  | 5    | the model table, pre-run checks, import, `run_replay`, the vLLM transport |
| `synthbench/commands/replay.py`                                                      | 5    | `replay --model`                                                          |
| `backend/tests/unit/synthbench/test_replay.py`                                       | 5    | checks, import gate, vLLM client through a fake server                    |
| `synthbench/score/__init__.py`, `metrics.py`, `report.py`, `scoring.py`, `AGENTS.md` | 6    | metrics, `report.md`, `report.html`, loading and the outputs              |
| `synthbench/commands/score.py`                                                       | 6    | `score --replay …`                                                        |
| `backend/tests/unit/synthbench/test_score.py`                                        | 6    | metrics and report                                                        |
| `synthbench/cli.py`, `synthbench/AGENTS.md`                                          | 3-6  | register each command; layout rows                                        |
| `docs/synthbench/command-reference.md`                                               | 3-6  | each command's section                                                    |
| `docs/synthbench/operator-runbook.md`                                                | 1, 7 | serving each model for replay; the scored run                             |
| `backend/tests/unit/synthbench/AGENTS.md`                                            | 3-6  | a row per new test file                                                   |
| `docs/benchmarks/synthbench/p5a-<date>.md`                                           | 7    | the committed aggregate report                                            |

---

### Task 1: Live probe: bring up what exists, and test the design's assumptions (controller, gate)

This task is live work on the GB300, run by the controller (not dispatched). It changes no
Python. Tasks 2–5 were built during planning (P5a-R10), so this task is also their first live run:
it drives the built `export vss` and `replay` against real servers. Its evidence goes into
`docs/benchmarks/synthbench/p5a-probes.md`. Anything it refutes becomes a ruling in the SDD
ledger and, where it touches built code, a fix commit on that task before Task 7 starts.

**Files:**

- Create: `.env.bench`
- Create: `docs/benchmarks/synthbench/p5a-probes.md`
- Modify: `docs/synthbench/operator-runbook.md` (a "Serve a model for replay" section)
- Modify: `docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` (the timestamp
  measurement row, per P5a-R4; the image row, per P5a-R1; the `ai-llm` note in §3)

**Prerequisites:** the renderer is stopped (`systemctl --user is-active synthbench-renderer` prints
`inactive`) and about 64 GB of GPU memory is free (`nvidia-smi --query-gpu=memory.free
--format=csv`).

- [ ] **Step 1: Copy the weights (read-only source), fix their modes, record sha256s**

```bash
SRC=/agents/agent-vss1/gpu/models/vlm DST=/export/models/ai_models/vlm
mkdir -p "$DST"
for f in Qwen3VL-8B-Instruct-Q4_K_M.gguf mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf \
         Qwen3VL-4B-Instruct-Q4_K_M.gguf mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf \
         NVIDIA-Nemotron-Nano-12B-v2-VL-Q4_K_M.gguf NVIDIA-Nemotron-Nano-12B-v2-VL-BF16-mmproj.gguf; do
  cp "$SRC/$f" "$DST/" || sudo cp "$SRC/$f" "$DST/"
done
sudo chown -R "$(id -u):$(id -g)" /export/models/ai_models
chmod 0755 /export/models/ai_models "$DST"; chmod 0644 "$DST"/*.gguf
(cd "$DST" && sha256sum *.gguf | tee SHA256SUMS)
```

Expected: six files (5.0, 0.8, 2.5, 0.5, 7.5 and 1.7 GB), mode `-rw-r--r--`.

- [ ] **Step 2: Copy the two `ai-vlm` images from the agent-gpu store into the default rootless store**

```bash
as_gpu() { (cd / && sudo -u agent-gpu env XDG_RUNTIME_DIR=/run/user/1001 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus podman "$@"); }
for tag in sm103-v12 sm103-b11090; do as_gpu save "localhost/agent-vss1/ai-vlm:$tag" | podman load; done
# compose derives <project>-<service> for a build-only service; tag the shipped build with it.
podman tag localhost/agent-vss1/ai-vlm:sm103-v12 \
  docker.io/library/nemotron-v3-home-security-intelligence-ai-vlm:latest
podman images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep ai-vlm
```

Expected: both tags listed, about 3.6 GB each. If compose's derived image name differs (Step 4
prints it), re-tag to that name and note it in the probes file.

- [ ] **Step 3: Write `.env.bench`**

```bash
# .env.bench — this host's values for the product's compose services (synthbench P5a).
# Only ai-vlm runs in P5a; P5b grows this into the hsi-bench env file (parent spec §5.1).
AI_MODELS_PATH=/export/models/ai_models
CUDA_ARCHITECTURES=103
GPU_LLM=0
AI_VLM_PORT=8098
CAMERA_TIMEZONE=America/New_York
PODMAN_SOCKET=/run/user/1000/podman/podman.sock
SYNTHBENCH_COSMOS_PORT=8099
```

- [ ] **Step 4: Render compose, then start only `ai-vlm`**

```bash
podman compose --env-file .env.bench -f docker-compose.prod.yml --profile vlm config -q; echo "config $?"
podman compose --env-file .env.bench -f docker-compose.prod.yml --profile vlm config --images | grep ai-vlm
podman compose --env-file .env.bench -f docker-compose.prod.yml --profile vlm up -d --no-deps ai-vlm
```

Expected: `config 0`. `config` may name further unset variables (`${VAR:?}` in other services):
add each to `.env.bench` with this host's value and record it. If compose cannot start the
service after that, start the same container directly and record that compose did not work:

```bash
podman run -d --name ai-vlm --device nvidia.com/gpu=0 -p 127.0.0.1:8098:8098 \
  -v /export/models/ai_models/vlm:/models:ro \
  -e PORT=8098 -e MODEL_PATH=/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf \
  -e MMPROJ_PATH=/models/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf -e MODEL_ALIAS=Qwen3VL-8B \
  -e GPU_LAYERS=auto -e LLAMA_ARG_IMAGE_MAX_TOKENS=1280 -e CTX_SIZE=32768 -e PARALLEL=2 \
  -e THREADS=4 -e BATCH_SIZE=2048 -e UBATCH_SIZE=512 -e CACHE_TYPE_K=q8_0 -e CACHE_TYPE_V=q8_0 \
  -e FLASH_ATTENTION=true -e SLEEP_IDLE_SECONDS=300 \
  docker.io/library/nemotron-v3-home-security-intelligence-ai-vlm:latest
```

These are the compose service's own settings (`docker-compose.prod.yml`, service `ai-vlm`).

- [ ] **Step 5: Health, identity and memory**

```bash
for i in $(seq 1 60); do curl -sf 127.0.0.1:8098/health >/dev/null && break; sleep 5; done; echo "healthy after ~$((i*5)) s"
curl -s 127.0.0.1:8098/props | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('build_info'), d.get('model_path'))"
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
curl -s -o /dev/null -w 'flagship %{http_code}\n' 127.0.0.1:8000/health
```

Expected: `b7972-e06088da0 /models/Qwen3VL-8B-Instruct-Q4_K_M.gguf`, a new process under about
10 GB, and the flagship `200`. Record the cold-load time (the VSS checklist says it was never
measured).

- [ ] **Step 6: Export, then five items through the built `replay`**

```bash
uv run python -m synthbench export vss
time uv run python -m synthbench replay --model qwen3-vl-8b --limit 5
uv run python -m synthbench replay --model qwen3-vl-8b --limit 5
uv run python - <<'PY'
import sqlite3
from backend.evaluation.eval_store import EvalStore
path = "/synthbench/eval/tierb-v0/eval.sqlite"
print(sqlite3.connect(path).execute("SELECT run_id, count(*) FROM results GROUP BY run_id").fetchall())
with EvalStore(path) as store:
    items = store.iter_items(with_media_only=True)
print(len(items), sorted({item.snapshot.timestamp[:10] for item in items}))
PY
```

Expected: the export writes 450 sets (241 under `threats/` and `suspicious/`, 209 under `normal/`)
and reports the 9 ambiguous events and the 1 failed event as not exported. Each replay prints
`5 items` and the path of its `run.json`; replay ids and eval run ids differ between the two runs,
and the query shows two run ids with 5 results each. `run_replay` takes items in `item_id` order,
so these ten are `normal/` sets: S2 has n = 5 and S3 n = 0, which is enough for a plumbing check.
The store holds 450 items, dated `2026-01-15` (snow) and `2026-04-15`. Record the per-item latency
(wall time over 5), and whether the second run re-imported anything (`already_imported` in its
`run.json` must be 450).

- [ ] **Step 7: The flagship through the built `replay` (P5a-R2)**

```bash
uv run python -m synthbench replay --model flagship --limit 3
```

Expected: `3 items` and `0 refused`. A refusal means vLLM rejected the request or its answer did
not parse: read the rows (`EvalStore(path).replay(<eval_run_id from run.json>)`) and the command's
log lines, and record the error verbatim. The smallest fix goes in `ModelField`
(`synthbench/run/replay.py`) as a fix commit on Task 5, with a ruling in the ledger. The flagship is
shared with agents: never raise `--limit` here.

- [ ] **Step 8: Cosmos-Reason2-8B under vLLM, in synthbench's podman store**

One served model at a time (spec §3): stop `ai-vlm` first.

```bash
podman compose --env-file .env.bench -f docker-compose.prod.yml --profile vlm stop ai-vlm
P="$(uv run python -m synthbench.generate.podman)"
$P pull docker.io/vllm/vllm-openai@sha256:c2b7c425d4a30d26bc2097ac6b28331fbe1b8aee11b8bfbb02bc3295de6f642d
$P run -d --name synthbench-cosmos --device nvidia.com/gpu=all -p 127.0.0.1:8099:8000 \
  -v /export/models:/export/models -e HF_HOME=/export/models -e HF_HUB_OFFLINE=1 \
  docker.io/vllm/vllm-openai@sha256:c2b7c425d4a30d26bc2097ac6b28331fbe1b8aee11b8bfbb02bc3295de6f642d \
  --model nvidia/Cosmos-Reason2-8B --served-model-name nvidia/Cosmos-Reason2-8B \
  --gpu-memory-utilization 0.10 --max-model-len 16384 --limit-mm-per-prompt '{"image": 4}'
for i in $(seq 1 90); do curl -sf 127.0.0.1:8099/v1/models >/dev/null && break; sleep 10; done; echo "ready after ~$((i*10)) s"
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
uv run python -m synthbench replay --model cosmos-reason2-8b --limit 3
$P rm -f synthbench-cosmos
```

Expected: `/v1/models` lists `nvidia/Cosmos-Reason2-8B`; the new process stays near 25 GiB (0.10
of the GPU's 250.7 GiB); the replay prints `3 items` and `0 refused`. A refusal is handled as in
Step 7. Record the cold-start time. If `--gpu-memory-utilization 0.10` does not fit beside the
flagship, record vLLM's error and the free memory, and retry once at 0.09.

- [ ] **Step 9: Record the evidence, write the runbook section, correct the spec**

Write `docs/benchmarks/synthbench/p5a-probes.md` with one section per step: the commands' key
output, timings, memory, the builds from `/props` and `/v1/models`, and anything refuted.

Add a section `## Serve a model for replay (P5a)` to `docs/synthbench/operator-runbook.md`, after
`## Review a batch`, from the commands that worked in Steps 1–5 and 8 (not the ones in this plan
where they differed): the one-time weights copy and image load, `.env.bench`, starting and
stopping `ai-vlm` for each of `qwen3-vl-8b`, `qwen3-vl-4b` (`VLM_MODEL_PATH`,
`VLM_MMPROJ_PATH`, `VLM_MODEL_ALIAS` in `.env.bench`) and `nemotron-12b-vl` (the `sm103-b11090`
image), starting and removing `synthbench-cosmos`, and the rule that the renderer is stopped and
one model is served at a time.

In the spec's "Measurements" table:

- replace the importer-timestamp row's value with: "`import_generated_items` stamps every item
  `1970-01-01T00:00:00+00:00`; replay pins `camera_timezone=None`, so the prompt shows that string
  (midnight UTC) for every scene. P5a's export declares each scene's time (Task 2)";
- set the `ai-vlm` image row to name `sm103-v12` (b7972-e06088da0) as the product's build and
  `sm103-b11090` as Nemotron-12B-VL's.

In §3's "Bringing up `ai-vlm`", replace the last bullet's reason: `ai-llm` left compose in R8 S2b
(main `aaf29361`); `up --no-deps ai-vlm` stays, so compose starts nothing else.

Stop `ai-vlm` if it is running and Task 6 will not follow at once:
`podman compose --env-file .env.bench -f docker-compose.prod.yml --profile vlm stop ai-vlm`.

- [ ] **Step 10: Commit**

```bash
git add .env.bench docs/benchmarks/synthbench/p5a-probes.md docs/synthbench/operator-runbook.md \
  docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md
SKIP=semgrep uvx pre-commit run --files $(git diff --cached --name-only)
git commit -m "docs(synthbench): P5a live probe - ai-vlm, vLLM and the built replay on the GB300

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The importer's optional `timestamp`

> **Built during planning: commit `aadf8b87`** (merged with main at `c444456d`). Execution runs
> the task review on `aadf8b87^..aadf8b87` and implements nothing unless the review finds a defect;
> the steps below are the brief the reviewer checks the commit against.

The VSS importer stamps every generated item with the 1970 epoch. P5a's export carries each
scene's time, so the importer must accept it. This is the one change to VSS code (spec §2).

**Files:**

- Modify: `backend/evaluation/label_import.py` (a helper beside `_midpoint`; one check and one
  field in `import_generated_items`)
- Test: `backend/tests/unit/evaluation/test_label_import.py` (a new class after
  `TestSyntheticIncidentImport`)

**Interfaces:**

- Consumes: `_make_corpus(root, category, set_name, *, risk=...)` and the `store` fixture, both
  already in the test module; `ImportResult.skipped`, `.reason`, `.item_id`.
- Produces: `import_generated_items` stores `labels["timestamp"]` verbatim as
  `EvalItem.snapshot.timestamp` when it is an ISO-8601 string with a UTC offset; a set without the
  key keeps `"1970-01-01T00:00:00+00:00"`; any other value skips the set with a reason.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/unit/evaluation/test_label_import.py`, after `TestSyntheticIncidentImport`:

```python
class TestDeclaredTimestamp:
    """Synthbench P5a: a generated set may declare its capture moment. The replay prompt shows the
    stored string verbatim (vlm_replay pins camera_timezone=None), so it is stored as written."""

    @staticmethod
    def _set(tmp_path: Path, stamp: object) -> None:
        d = _make_corpus(
            tmp_path, "threats", "knife_visible", risk={"min_score": 70, "max_score": 95}
        )
        labels = json.loads((d / "expected_labels.json").read_text())
        labels["timestamp"] = stamp
        (d / "expected_labels.json").write_text(json.dumps(labels))

    def test_a_declared_timestamp_is_stored_verbatim(self, store, tmp_path):
        self._set(tmp_path, "2026-04-15T14:32:00-04:00")
        row = import_generated_items(corpus_dir=tmp_path, store=store)[0]
        assert not row.skipped, row.reason
        assert store.get_item(row.item_id).snapshot.timestamp == "2026-04-15T14:32:00-04:00"

    def test_no_timestamp_keeps_the_epoch_sentinel(self, store, tmp_path):
        _make_corpus(tmp_path, "threats", "knife_visible", risk={"min_score": 70, "max_score": 95})
        row = import_generated_items(corpus_dir=tmp_path, store=store)[0]
        assert not row.skipped, row.reason
        assert store.get_item(row.item_id).snapshot.timestamp == "1970-01-01T00:00:00+00:00"

    @pytest.mark.parametrize(
        ("stamp", "why"),
        [
            ("2026-04-15T14:32:00", "no UTC offset"),
            ("15 April, 2:32 pm", "not ISO-8601"),
            (1776277920, "not an ISO-8601 string"),
        ],
    )
    def test_a_malformed_timestamp_refuses_the_set(self, store, tmp_path, stamp, why):
        self._set(tmp_path, stamp)
        row = import_generated_items(corpus_dir=tmp_path, store=store)[0]
        assert row.skipped
        assert why in row.reason
        assert store.get_item(row.item_id) is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest backend/tests/unit/evaluation/test_label_import.py -q -n0 -k DeclaredTimestamp`

Expected: `test_a_declared_timestamp_is_stored_verbatim` fails (the stored timestamp is the epoch)
and the three malformed cases fail (the set imports); `test_no_timestamp_keeps_the_epoch_sentinel`
passes already (it pins today's behavior).

- [ ] **Step 3: Implement**

In `backend/evaluation/label_import.py`, add after `_midpoint`:

```python
# A generated set's capture moment when it declares none: the honest epoch sentinel.
_EPOCH_SENTINEL = "1970-01-01T00:00:00+00:00"


def _declared_timestamp(value: Any) -> tuple[str, str | None]:
    """A set's optional capture moment (synthbench P5a design §2): an ISO-8601 time with a UTC
    offset, stored verbatim because the replay prompt shows the stored string. An absent key keeps
    the epoch sentinel; any other value refuses the set. Returns (timestamp, loud-skip reason)."""
    if value is None:
        return _EPOCH_SENTINEL, None
    if not isinstance(value, str):
        return "", f"timestamp is {type(value).__name__}, not an ISO-8601 string"
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return "", f"timestamp {value!r} is not ISO-8601"
    if moment.utcoffset() is None:
        return "", f"timestamp {value!r} has no UTC offset"
    return value, None
```

In `import_generated_items`, after the `_attribution_gap` check and before `score = _midpoint(...)`:

```python
        timestamp, timestamp_reason = _declared_timestamp(labels.get("timestamp"))
        if timestamp_reason:
            out.append(_skip(item_id, GENERATED_KIND, reason=timestamp_reason))
            continue
```

and in the `AssessInput(...)` below it, replace

```python
                timestamp="1970-01-01T00:00:00+00:00",  # honest epoch sentinel
```

with

```python
                timestamp=timestamp,  # the set's declared moment, else the epoch sentinel
```

(`datetime` is already imported at the top of the module.)

- [ ] **Step 4: Run the tests to see them pass, then the module and the evaluation suite**

Run: `uv run pytest backend/tests/unit/evaluation/test_label_import.py -q -n0`
Expected: all pass.
Run: `uv run pytest backend/tests/unit/evaluation/ -q -n auto`
Expected: all pass (no other test depended on the literal), except `test_build_gen2.py`'s
`TestBuildGen2` tests, which time out at the 5 s limit on this host with and without this change
(about 6 s each, pre-existing): do not chase them.

- [ ] **Step 5: Commit**

```bash
git add backend/evaluation/label_import.py backend/tests/unit/evaluation/test_label_import.py
SKIP=semgrep uvx pre-commit run --files backend/evaluation/label_import.py backend/tests/unit/evaluation/test_label_import.py
git commit -m "feat(evaluation): an optional capture timestamp on generated eval sets

A generated set may declare its capture moment (ISO-8601 with a UTC offset),
stored verbatim; the replay prompt shows it. Without the key the epoch
sentinel stays, so every existing import is unchanged. Synthbench P5a.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `export vss`

> **Built during planning: commits `c2a1566b` and `11f5742c`** (the label-mismatch test the
> plan's self-review found missing); `c2a1566b` was merged with main at `c444456d`. Execution runs
> the task review on both commits and implements nothing unless the review finds a defect; the
> steps below are the brief the reviewer checks the commits against.

Write every ready, non-ambiguous Tier B event in the VSS eval store's import layout (spec §2).

**Files:**

- Create: `synthbench/export/__init__.py`, `synthbench/export/vss.py`, `synthbench/export/AGENTS.md`
- Create: `synthbench/commands/export.py`
- Modify: `synthbench/cli.py` (import and register `export`)
- Modify: `docs/synthbench/command-reference.md` (an `export vss` section before `corpus snapshot`)
- Modify: `synthbench/AGENTS.md` (an `export/` layout row; the `commands/` row points at the command reference)
- Modify: `backend/tests/unit/synthbench/AGENTS.md` (a `test_export_vss.py` row)
- Test: `backend/tests/unit/synthbench/test_export_vss.py`

**Interfaces:**

- Consumes: Task 2 (`import_generated_items` stores a declared `timestamp`); `synthbench.commands.common`
  (`read`, `read_bytes`, `read_index`, `check_manifest`, `taxonomy`, `AskOwner`, `CorpusError`,
  `RequestError`); `CorpusStore`; `Spec`, `Provenance`; test helpers `h.run`, `h.store`,
  `h.write_prompts`, `h.good_prompt`, `h.record_output`, `h.NOW`, `h.VERSION`, `h.TAX`.
- Produces (used by Tasks 4, 5 and 6):

  - `synthbench.export.vss.CATEGORY: dict[str, str]` (group → directory) and
    `CATEGORY_LABEL: dict[str, str]` (directory → eval label);
  - `scene_timestamp(scene_time: str, weather: str) -> str`;
  - `read_sets(export_dir: Path) -> list[ExportedSet]`, where `ExportedSet` has `category`,
    `set_dir`, `labels`, and properties `item_id` (`"generated:<category>:<event id>"`), `facts`
    (the `synthbench` block: `event_id`, `label`, `risk_band`, `scene_time`, `cell`, `subjects`,
    `props`, …) and `still` (`Path`);
  - `synthbench.commands.export.export_dir(version: str, env: Mapping[str, str]) -> Path`
    (`$SYNTHBENCH_ROOT/exports/<version>/vss`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/synthbench/test_export_vss.py`:

```python
"""`export vss` (P5a design §2): ready Tier B events in the VSS eval store's import layout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from synthbench import cli
from synthbench.contract.corpus import BatchRecord
from synthbench.contract.provenance import Provenance
from synthbench.contract.spec import Spec
from synthbench.export import vss

from backend.tests.unit.synthbench import helpers as h

# One scenario per exported group: threat, suspicious, hard_negative, benign.
MIXED = "knife_visible,loitering,hooded_jogger,delivery_driver"


def _ready_batch(root: Path, only: str, n: int, batch: str = "pilot-1") -> list[Spec]:
    """A sampled, frozen batch whose events have a stand-in still and index status `ready`."""
    assert h.run(root, "sample", "--batch", batch, "--n", str(n), "--only", only) == cli.EXIT_OK
    store = h.store(root)
    record = store.read(store.batch_file(batch), BatchRecord)
    specs = [store.read(store.spec_file(event), Spec) for event in record.event_ids]
    h.write_prompts(root, batch, {spec.event_id: h.good_prompt(spec) for spec in specs})
    assert h.run(root, "check", "--batch", batch) == cli.EXIT_OK
    specs = [store.read(store.spec_file(spec.event_id), Spec) for spec in specs]
    for spec in specs:
        tag = spec.event_id.encode()
        h.record_output(root, spec, render=b"png " + tag, still=b"jpeg " + tag)
        row = store.latest_index()[spec.event_id]
        store.append_index([row.model_copy(update={"status": "ready", "time": h.NOW.isoformat()})])
    return specs


def _out(root: Path) -> Path:
    return root / "exports" / h.VERSION / "vss"


def _export(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    assert h.run(root, "export", "vss") == cli.EXIT_OK
    return capsys.readouterr().out


def _tree(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_ready_events_export_to_their_category(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = _ready_batch(tmp_path, MIXED, 8)
    assert "8 written now, 0 unchanged" in _export(tmp_path, capsys)
    assert {vss.CATEGORY[s.cell.group] for s in specs} == {"threats", "suspicious", "normal"}
    for spec in specs:
        category = vss.CATEGORY[spec.cell.group]
        set_dir = _out(tmp_path) / category / spec.event_id
        labels = json.loads((set_dir / "expected_labels.json").read_text(encoding="utf-8"))
        assert labels["category"] == category
        assert labels["risk"] == {"min_score": spec.risk_band[0], "max_score": spec.risk_band[1]}
        assert labels["timestamp"] == vss.scene_timestamp(spec.scene_time, spec.cell.weather)
        assert labels["synthbench"]["event_id"] == spec.event_id
        assert labels["synthbench"]["cell"]["scenario"] == spec.cell.scenario
        assert (set_dir / "still.jpg").read_bytes() == b"jpeg " + spec.event_id.encode()
        sidecar = json.loads((set_dir / "still.json").read_text(encoding="utf-8"))
        assert sidecar["license"] and sidecar["artist"]


def test_only_ready_events_are_exported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    specs = _ready_batch(tmp_path, MIXED, 4)
    store = h.store(tmp_path)
    row = store.latest_index()[specs[0].event_id]
    store.append_index([row.model_copy(update={"status": "failed", "time": h.NOW.isoformat()})])
    out = _export(tmp_path, capsys)
    assert "3 written now" in out
    assert "not exported: failed 1" in out
    assert not list(_out(tmp_path).glob(f"*/{specs[0].event_id}"))


def test_ambiguous_events_are_counted_not_exported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _ready_batch(tmp_path, "costume_weapon", 2)
    out = _export(tmp_path, capsys)
    assert "0 written now" in out
    assert "not exported: ambiguous 2" in out
    assert not list(_out(tmp_path).rglob("expected_labels.json"))


def test_a_second_export_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _ready_batch(tmp_path, MIXED, 4)
    _export(tmp_path, capsys)
    before = _tree(_out(tmp_path))
    assert "0 written now, 4 unchanged" in _export(tmp_path, capsys)
    assert _tree(_out(tmp_path)) == before


def test_a_set_that_differs_from_the_corpus_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = _ready_batch(tmp_path, MIXED, 4)[0]
    _export(tmp_path, capsys)
    next(_out(tmp_path).glob(f"*/{spec.event_id}/expected_labels.json")).write_text("{}\n")
    assert h.run(tmp_path, "export", "vss") == cli.EXIT_ASK
    assert "differs from the corpus" in capsys.readouterr().err


def test_a_label_its_group_disagrees_with_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The label authority is the directory (the importer's rule), so a threat labeled benign
    would import as an incident: the taxonomy disagreeing with itself stops the export."""
    specs = _ready_batch(tmp_path, MIXED, 4)
    threat = next(spec for spec in specs if spec.cell.group == "threat")
    spec_file = h.store(tmp_path).spec_file(threat.event_id)
    document = json.loads(spec_file.read_text(encoding="utf-8"))
    spec_file.write_text(json.dumps(document | {"label": "benign"}), encoding="utf-8")
    assert h.run(tmp_path, "export", "vss") == cli.EXIT_ASK
    assert f"{threat.event_id} is labeled benign" in capsys.readouterr().err


def test_a_still_that_no_longer_matches_its_sha256_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = _ready_batch(tmp_path, MIXED, 2)[0]
    store = h.store(tmp_path)
    still = store.read(store.provenance_file(spec.event_id), Provenance).attempts[-1].still
    assert still is not None
    (store.event_dir(spec.event_id) / still.path).write_bytes(b"tampered")
    assert h.run(tmp_path, "export", "vss") == cli.EXIT_ASK
    assert "does not match its recorded sha256" in capsys.readouterr().err


def test_an_empty_corpus_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert h.run(tmp_path, "export", "vss") == cli.EXIT_ERROR
    assert "nothing to export" in capsys.readouterr().err


def test_the_scene_time_is_dated_by_the_weather() -> None:
    assert vss.scene_timestamp("14:32", "clear") == "2026-04-15T14:32:00-04:00"
    assert vss.scene_timestamp("06:05", "snow") == "2026-01-15T06:05:00-05:00"
    assert "snow" in {weather.id for weather in h.TAX.weather}  # the rule keys on a real id


def test_the_category_vocabulary_is_the_importers() -> None:
    from backend.evaluation.eval_store import _CATEGORY_LABELS

    assert vss.CATEGORY_LABEL == _CATEGORY_LABELS
    # every scenario group is either placed in a category or deliberately excluded
    assert set(vss.CATEGORY) | {"ambiguous"} == {s.group for s in h.TAX.scenarios}


def test_the_export_round_trips_through_the_importer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from backend.evaluation.eval_store import EvalStore
    from backend.evaluation.label_import import import_generated_items

    specs = _ready_batch(tmp_path, MIXED, 6)
    _export(tmp_path, capsys)
    sets = {s.facts["event_id"]: s for s in vss.read_sets(_out(tmp_path))}
    with EvalStore(tmp_path / "eval.sqlite") as store:
        rows = import_generated_items(corpus_dir=_out(tmp_path), store=store)
        assert [row.reason for row in rows if row.skipped] == []
        assert {row.item_id for row in rows} == {s.item_id for s in sets.values()}
        for spec in specs:
            exported = sets[spec.event_id]
            item = store.get_item(exported.item_id)
            assert item is not None
            assert item.expected_label == spec.label
            assert item.expected_risk_score == (spec.risk_band[0] + spec.risk_band[1]) // 2
            assert item.snapshot.timestamp == exported.labels["timestamp"]
            assert item.snapshot.specialist_outputs == {}
            assert item.media_paths == [str(exported.still)]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_export_vss.py -q -n0`
Expected: collection fails with `ModuleNotFoundError: No module named 'synthbench.export'`.

- [ ] **Step 3: Write the library**

Create `synthbench/export/__init__.py`:

```python
"""Exports of corpus events into layouts other tools read (synthbench P5a)."""
```

Create `synthbench/export/vss.py`:

```python
"""The VSS eval-store layout for synthbench events (P5a design §2).

`import_generated_items` (`backend/evaluation/label_import.py`) reads
`<category>/<set>/expected_labels.json` plus the set's media, with one attribution sidecar per
frame. This module holds the pure pieces of writing that layout and of reading it back for the
audit and the scorer. It imports nothing from `backend`; a test pins the category vocabulary
below equal to the importer's.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from synthbench.contract.spec import Spec

# Scenario group -> the eval store's category directory. Ambiguous events are not exported: S2
# and S3 count neither label, and the store has no ambiguous category.
CATEGORY = {
    "benign": "normal",
    "hard_negative": "normal",
    "suspicious": "suspicious",
    "threat": "threats",
}
# The importer's own vocabulary (`backend/evaluation/eval_store.py` `_CATEGORY_LABELS`).
CATEGORY_LABEL = {"normal": "benign", "suspicious": "incident", "threats": "incident"}

CAMERA_TIMEZONE = "America/New_York"  # the owner's cameras (parent spec P0)
SNOW_DATE = date(2026, 1, 15)
OTHER_DATE = date(2026, 4, 15)

LABELS_FILE = "expected_labels.json"
STILL_FILE = "still.jpg"
SIDECAR_FILE = "still.json"
LICENSE = "FLUX.2 [dev] Non-Commercial License (black-forest-labs/FLUX.2-dev)"


class ExportConflict(Exception):
    """A set already on disk holds different content than the corpus now gives it."""


def category_of(spec: Spec) -> str | None:
    """The event's category directory, or None for an ambiguous event, which is not exported."""
    return CATEGORY.get(spec.cell.group)


def scene_timestamp(scene_time: str, weather: str) -> str:
    """The scene's clock time on a fixed date in the camera timezone, with its UTC offset.

    Snow scenes are dated in January and the rest in April, so the date the VLM reads never
    contradicts the weather it sees.
    """
    hours, minutes = (int(part) for part in scene_time.split(":"))
    day = SNOW_DATE if weather == "snow" else OTHER_DATE
    moment = datetime.combine(day, time(hours, minutes), tzinfo=ZoneInfo(CAMERA_TIMEZONE))
    return moment.isoformat()


def labels_document(spec: Spec, still_sha256: str) -> dict[str, Any]:
    """`expected_labels.json`: the keys the importer reads, plus the event's facts for scoring."""
    category = CATEGORY[spec.cell.group]
    lo, hi = spec.risk_band
    return {
        "category": category,
        "risk": {"min_score": lo, "max_score": hi},
        "timestamp": scene_timestamp(spec.scene_time, spec.cell.weather),
        "synthbench": {
            "event_id": spec.event_id,
            "corpus_version": spec.corpus_version,
            "batch": spec.batch,
            "label": spec.label,
            "risk_band": [lo, hi],
            "scene_time": spec.scene_time,
            "cell": spec.cell.model_dump(mode="json"),
            "subjects": [s.model_dump(mode="json", by_alias=True) for s in spec.subjects],
            "props": [p.model_dump(mode="json", by_alias=True) for p in spec.props],
            "still_sha256": still_sha256,
        },
    }


def attribution(version: str) -> dict[str, str]:
    """The sidecar the importer requires beside each frame: a license and an artist."""
    return {"license": LICENSE, "artist": f"synthbench {version}, FLUX.2 [dev] (synthetic)"}


def _json_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def set_files(spec: Spec, still: bytes, still_sha256: str) -> dict[str, bytes]:
    """Every file of one event's set, by name."""
    return {
        LABELS_FILE: _json_bytes(labels_document(spec, still_sha256)),
        STILL_FILE: still,
        SIDECAR_FILE: _json_bytes(attribution(spec.corpus_version)),
    }


def write_set(export_dir: Path, category: str, name: str, files: dict[str, bytes]) -> bool:
    """Write one set once: True if written now, False if identical content was already there.

    A new set is built in a staging directory beside the export (never under it, where the
    importer would read it) and renamed into place, so no reader sees half a set. Raises
    ExportConflict if a set on disk holds different content.
    """
    set_dir = export_dir / category / name
    if set_dir.exists():
        for file_name, data in files.items():
            path = set_dir / file_name
            if not path.is_file() or path.read_bytes() != data:
                raise ExportConflict(f"{path} differs from the corpus; an export is create-once")
        return False
    staging = export_dir.parent / f".{export_dir.name}-staging" / name
    if staging.exists():
        shutil.rmtree(staging)  # a crashed run's leftover: never renamed into the export
    staging.mkdir(parents=True)
    for file_name, data in files.items():
        (staging / file_name).write_bytes(data)
    set_dir.parent.mkdir(parents=True, exist_ok=True)
    staging.rename(set_dir)
    return True


@dataclass(frozen=True)
class ExportedSet:
    """One set read back from an export directory."""

    category: str
    set_dir: Path
    labels: dict[str, Any]

    @property
    def item_id(self) -> str:
        """The importer's id (`item_id_for_generated`); the round-trip test pins the format."""
        return f"generated:{self.category}:{self.set_dir.name}"

    @property
    def facts(self) -> dict[str, Any]:
        facts: dict[str, Any] = self.labels["synthbench"]
        return facts

    @property
    def still(self) -> Path:
        return self.set_dir / STILL_FILE


def read_sets(export_dir: Path) -> list[ExportedSet]:
    """Every set under an export directory, sorted by item id."""
    sets = [
        ExportedSet(
            category=path.parent.parent.name,
            set_dir=path.parent,
            labels=json.loads(path.read_text(encoding="utf-8")),
        )
        for path in export_dir.glob(f"*/*/{LABELS_FILE}")
        if path.parent.parent.name in CATEGORY_LABEL
    ]
    return sorted(sets, key=lambda s: s.item_id)
```

- [ ] **Step 4: Write the command and register it**

Create `synthbench/commands/export.py`:

```python
"""`export vss`: ready Tier B events in the VSS eval store's import layout (P5a design §2).

An owner command, not the generation agent's. It reads the corpus and never writes it; the sets
go to `$SYNTHBENCH_ROOT/exports/<version>/vss/`.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    CorpusError,
    Parser,
    RequestError,
    check_manifest,
    read,
    read_bytes,
    read_index,
    taxonomy,
)
from synthbench.contract.provenance import Provenance
from synthbench.contract.spec import Spec
from synthbench.contract.store import DEFAULT_SYNTHBENCH_ROOT, CorpusStore
from synthbench.export import vss


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    export = commands.add_parser(
        "export", help="write corpus events in layouts other tools read (owner)", allow_abbrev=False
    )
    targets = export.add_subparsers(dest="export_target", required=True, parser_class=Parser)
    parser = targets.add_parser(
        "vss",
        help="ready Tier B events in the VSS eval store's import layout",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="export directory (default: $SYNTHBENCH_ROOT/exports/<version>/vss)",
    )
    parser.set_defaults(run=run_vss)


def export_dir(version: str, env: Mapping[str, str]) -> Path:
    root = Path(env.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
    return root / "exports" / version / "vss"


def run_vss(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store = CorpusStore.from_env(tax.version, env)
    if not store.index_file.exists():
        raise RequestError(f"corpus version {tax.version} has no events; nothing to export")
    check_manifest(store)
    out: Path = args.out if args.out is not None else export_dir(tax.version, env)
    written = unchanged = 0
    skipped: Counter[str] = Counter()
    for event_id, row in sorted(read_index(store).items()):
        if row.status != "ready":
            skipped[row.status] += 1
            continue
        spec = read(store, store.spec_file(event_id), Spec)
        category = vss.category_of(spec)
        if spec.tier != "B":
            skipped[f"tier {spec.tier}"] += 1
            continue
        if category is None:
            skipped["ambiguous"] += 1
            continue
        if vss.CATEGORY_LABEL[category] != spec.label:
            raise AskOwner(
                f"{event_id} is labeled {spec.label} but its group {spec.cell.group} exports as "
                f"{category}/ ({vss.CATEGORY_LABEL[category]}): the taxonomy disagrees with itself."
            )
        still = read(store, store.provenance_file(event_id), Provenance).attempts[-1].still
        if still is None:
            raise AskOwner(f"{event_id} is ready but its last attempt has no still.")
        data = read_bytes(store.event_dir(event_id) / still.path)
        if hashlib.sha256(data).hexdigest() != still.sha256:
            raise AskOwner(f"{event_id}'s still does not match its recorded sha256.")
        try:
            if vss.write_set(out, category, event_id, vss.set_files(spec, data, still.sha256)):
                written += 1
            else:
                unchanged += 1
        except vss.ExportConflict as error:
            raise AskOwner(f"{error}.") from error
        except OSError as error:
            raise CorpusError("write", out / category / event_id, error) from error
    not_exported = ", ".join(f"{why} {n}" for why, n in sorted(skipped.items())) or "none"
    sys.stdout.write(
        f"export vss {tax.version}: {written} written now, {unchanged} unchanged; not exported: "
        f"{not_exported}\n  {out}\n"
    )
    return EXIT_OK
```

In `synthbench/cli.py`, add `export` to the `from synthbench.commands import (...)` list and to
`COMMANDS`, after `doctor`:

```python
from synthbench.commands import (
    camera,
    check,
    corpus,
    doctor,
    export,
    render,
    report,
    sample,
    triage,
)
```

```python
COMMANDS: tuple[ModuleType, ...] = (
    sample,
    check,
    render,
    camera,
    triage,
    report,
    corpus,
    doctor,
    export,
)
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest backend/tests/unit/synthbench/test_export_vss.py -q -n0 -p randomly`
Expected: 11 passed.

- [ ] **Step 6: Document the command**

In `docs/synthbench/command-reference.md`, insert before `## \`corpus snapshot\``:

```markdown
## `export vss`

Owner only. Writes every ready Tier B event in the layout the VSS eval store imports
(`import_generated_items` in `backend/evaluation/label_import.py`), for P5a's replay
(`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §2). It reads the corpus
and never writes it.

| Option        | Default                                  | Meaning          |
| ------------- | ---------------------------------------- | ---------------- |
| `--out <dir>` | `$SYNTHBENCH_ROOT/exports/<version>/vss` | export directory |

- **Reads:** `corpus.json`, `index.jsonl`, and each ready event's `spec.json`, `provenance.json`
  and still.
- **Writes:** `<out>/<category>/<id>/` holding `expected_labels.json`, `still.jpg` and
  `still.json` (its attribution). Each set is written once; a re-export skips an identical set.
- **Categories:** benign and hard_negative go to `normal/`, suspicious to `suspicious/`, threat to
  `threats/`. Ambiguous events are not exported: S2 and S3 count neither label.
- **`expected_labels.json`:** `category`, `risk` (the risk band), `timestamp` (the scene time on
  2026-04-15, or 2026-01-15 for snow, in America/New_York) and a `synthbench` block with the
  event's facts.
- **Prints:** how many sets were written and how many were unchanged, and how many events were not
  exported, by reason.
- **Exit 1:** the corpus has no events.
- **Exit 2:** a set on disk differs from the corpus, a still no longer matches its sha256, a ready
  event has no still, an event's label disagrees with its group, or a corpus file cannot be read
  or written.
```

Create `synthbench/export/AGENTS.md`:

```markdown
# synthbench/export — Agent Guide

## Purpose

Writes corpus events in layouts other tools read. Synthbench P5a
(`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §2) adds the first: the
VSS eval store's import layout, which `synthbench replay` imports and replays.

## Files

| File     | What                                                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `vss.py` | the category map, the scene-timestamp rule, `expected_labels.json`, the attribution sidecar, writing a set once and reading sets back |

The command is `synthbench/commands/export.py` (`python -m synthbench export vss`).

## Rules

- Never import `backend` here (spec §7.1); a test pins `CATEGORY_LABEL` equal to the importer's
  `_CATEGORY_LABELS`.
- Exports go under `$SYNTHBENCH_ROOT/exports/`, never into the append-only corpus or the repo (the
  eval store refuses repo-resident media).
- A set is create-once: identical content is skipped, different content is an `ExportConflict`
  (exit 2). A new set is staged beside the export directory, never under it, because the importer
  reads every `*/*/expected_labels.json` there.
```

In `synthbench/AGENTS.md`, replace the `commands/` row's description, which lists every command
module and would go stale with each owner command P5a adds, with a pointer, and add a row after it:

```markdown
| `commands/` | one module per command, all listed in `docs/synthbench/command-reference.md`; `cli.py` dispatches |
| `export/` | exports of corpus events for other tools: `vss.py`, the VSS eval store's import layout (P5a) |
```

In `backend/tests/unit/synthbench/AGENTS.md`, add after the `test_command_reference.py` row:

```markdown
| `test_export_vss.py` | `python -m synthbench export vss`: categories, ready-only, reruns, the importer round trip |
```

- [ ] **Step 7: Run the synthbench suite, mypy and the import rule**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n auto -p randomly`
Expected: all pass, including `test_command_reference.py` and `test_import_rule.py`.
Run: `uv run mypy synthbench/ backend/tests/unit/synthbench/`
Expected: no issues.

- [ ] **Step 8: Commit**

```bash
git add synthbench/export/ synthbench/commands/export.py synthbench/cli.py synthbench/AGENTS.md \
  docs/synthbench/command-reference.md backend/tests/unit/synthbench/AGENTS.md \
  backend/tests/unit/synthbench/test_export_vss.py
SKIP=semgrep uvx pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(synthbench): export vss - ready Tier B events for the VSS eval store

Writes each ready, non-ambiguous Tier B event once as <category>/<id>/ with
expected_labels.json (category, risk band, scene timestamp, the event's
facts), the still and its attribution sidecar. Round-trips through
import_generated_items. Synthbench P5a design section 2.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `audit`

> **Built during planning: commit `fe8d50f1`** (merged with main at `c444456d`). Execution runs
> the task review on `fe8d50f1^..fe8d50f1` and implements nothing unless the review finds a
> defect; the steps below are the brief the reviewer checks the commit against.

The owner's check of the declared truth (spec §4): a seeded, stratified sample of 60 exported
stills, four questions each, on a loopback page. Its answers put an error bar on the truth P5a
scores against (Task 6) and later measure a judge model (P4).

**Files:**

- Create: `synthbench/audit/__init__.py`, `synthbench/audit/sample.py`, `synthbench/audit/page.py`,
  `synthbench/audit/AGENTS.md`
- Create: `synthbench/commands/audit.py`
- Modify: `synthbench/cli.py` (import and register `audit`, after `export`)
- Modify: `docs/synthbench/command-reference.md` (an `audit` section after `export vss`)
- Modify: `synthbench/AGENTS.md` (an `audit/` layout row after `export/`)
- Modify: `backend/tests/unit/synthbench/AGENTS.md` (a `test_audit.py` row)
- Test: `backend/tests/unit/synthbench/test_audit.py`

**Interfaces:**

- Consumes: Task 3's `read_sets(export_dir) -> list[ExportedSet]` (`item_id`, `facts`, `still`),
  `vss.write_set`, `vss.LABELS_FILE`, `vss.STILL_FILE`, `vss.SIDECAR_FILE`, `vss.attribution`, and
  `synthbench.commands.export.export_dir(version, env)`; `synthbench.commands.common`
  (`taxonomy`, `RequestError`, `EXIT_OK`, `Parser`).
- Produces (used by Task 6):

  - `synthbench.audit.sample.SEED = 20260929`, `STRATA` (threat 20, suspicious 10, hard_negative 15,
    benign 15), `Question(key, text)` with `key` in `scene`, `prop`, `people`, `conditions`;
    `allocate(counts, k)`, `sample(sets, seed=SEED)`, `questions(facts)`;
  - `synthbench.audit.page.ANSWERS = ("y", "n", "u")`,
    `load_answers(log: Path) -> dict[tuple[str, str], str]` (the latest answer per
    `(event_id, question key)`), `AuditItem`, `Response`, `AuditApp`, `serve(app, port)`;
  - `synthbench.commands.audit.audit_log(version: str, env: Mapping[str, str]) -> Path`
    (`$SYNTHBENCH_ROOT/audits/<version>/audit.jsonl`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/synthbench/test_audit.py`:

```python
"""`audit` (P5a design §4): the stratified sample, the questions and the page's handler."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from synthbench.audit.page import AuditApp, AuditItem, load_answers
from synthbench.audit.sample import STRATA, allocate, questions, sample
from synthbench.export.vss import ExportedSet


def _set(root: Path, n: int, group: str, lighting: str, **cell: Any) -> ExportedSet:
    event_id = f"B-t-{group}-{lighting}-{n:03d}"
    set_dir = root / "vss" / "x" / event_id
    set_dir.mkdir(parents=True, exist_ok=True)
    (set_dir / "still.jpg").write_bytes(b"jpeg " + event_id.encode())
    facts = {
        "event_id": event_id,
        "cell": {
            "scenario": cell.get("scenario", "knife_visible"),
            "group": group,
            "lighting": lighting,
            "weather": cell.get("weather", "clear"),
        },
        "subjects": cell.get("subjects", [{"class": "person", "role": "intruder"}]),
        "props": cell.get("props", [{"class": "knife", "held_by": "S1"}]),
    }
    return ExportedSet(category="threats", set_dir=set_dir, labels={"synthbench": facts})


def _corpus(root: Path) -> list[ExportedSet]:
    """Every stratum with two lighting values, more members than the stratum samples."""
    sets = []
    for group, k in STRATA:
        for lighting, count in (("day", 2 * k), ("ir_night", k)):
            sets += [_set(root, i, group, lighting) for i in range(count)]
    return sets


def test_allocate_is_proportional_with_one_per_value_and_caps() -> None:
    assert allocate({"day": 60, "ir_night": 30, "dusk": 10}, 10) == {
        "day": 6,
        "dusk": 1,
        "ir_night": 3,
    }
    assert allocate({"day": 100, "fog": 1}, 5) == {"day": 4, "fog": 1}  # one per value first
    assert allocate({"day": 2, "dusk": 1}, 10) == {"day": 2, "dusk": 1}  # never more than exists


def test_the_sample_is_deterministic_and_fills_each_stratum(tmp_path: Path) -> None:
    sets = _corpus(tmp_path)
    first, second = sample(sets), sample(list(reversed(sets)))
    assert [s.item_id for s in first] == [s.item_id for s in second]
    for group, k in STRATA:
        members = [s for s in first if s.facts["cell"]["group"] == group]
        assert len(members) == k
        assert {s.facts["cell"]["lighting"] for s in members} == {"day", "ir_night"}


def test_a_small_stratum_gives_what_it_has(tmp_path: Path) -> None:
    sets = [_set(tmp_path, i, "suspicious", "day") for i in range(3)]
    assert len(sample(sets)) == 3


def test_a_threat_gets_a_prop_question_and_a_benign_scene_does_not(tmp_path: Path) -> None:
    threat = questions(_set(tmp_path, 0, "threat", "day").facts)
    assert [q.key for q in threat] == ["scene", "prop", "people", "conditions"]
    assert "knife visible" in threat[1].text
    assert "knife visible" in threat[0].text.replace("_", " ")
    benign = _set(
        tmp_path, 1, "benign", "ir_night", scenario="delivery_driver", props=[], weather="snow"
    )
    asked = questions(benign.facts)
    assert [q.key for q in asked] == ["scene", "people", "conditions"]
    assert asked[1].text == "Exactly 1 person(s)?"
    assert asked[2].text == "ir night light and snow weather?"


def _app(tmp_path: Path, n: int = 2) -> AuditApp:
    items = [
        AuditItem(s, questions(s.facts))
        for s in (_set(tmp_path, i, "threat", "day") for i in range(n))
    ]
    return AuditApp(items, tmp_path / "audits" / "audit.jsonl", lambda: "2026-09-29T20:00:00Z")


def _answer(app: AuditApp, index: int, question: str, answer: str) -> Any:
    body = json.dumps({"index": index, "question": question, "answer": answer}).encode()
    return app.handle("POST", "/answer", body)


def test_the_page_shows_the_first_open_still(tmp_path: Path) -> None:
    app = _app(tmp_path)
    page = app.handle("GET", "/", b"")
    assert page.status == 200
    assert b"0/2 stills fully answered" in page.body
    assert b'src="/still/0"' in page.body
    for q in app.items[0].questions:
        assert _answer(app, 0, q.key, "y").status == 200
    assert b'src="/still/1"' in app.handle("GET", "/", b"").body


def test_a_still_is_served_only_by_index(tmp_path: Path) -> None:
    app = _app(tmp_path)
    still = app.handle("GET", "/still/1", b"")
    assert still.status == 200
    assert still.body == app.items[1].exported.still.read_bytes()
    assert app.handle("GET", "/still/2", b"").status == 404
    assert app.handle("GET", "/still/../../etc/passwd", b"").status == 404


def test_answers_append_and_the_latest_wins(tmp_path: Path) -> None:
    app = _app(tmp_path)
    assert _answer(app, 0, "scene", "n").status == 200
    assert _answer(app, 0, "scene", "y").status == 200
    lines = app.log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert load_answers(app.log) == {(app.items[0].event_id, "scene"): "y"}
    reopened = _app(tmp_path)  # a restart resumes from the log
    assert reopened.answers == load_answers(app.log)


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b'{"index": 9, "question": "scene", "answer": "y"}',
        b'{"index": 0, "question": "scene", "answer": "maybe"}',
        b'{"index": 0, "question": "weather", "answer": "y"}',
    ],
)
def test_a_bad_answer_is_refused_and_not_logged(tmp_path: Path, body: bytes) -> None:
    app = _app(tmp_path)
    assert app.handle("POST", "/answer", body).status == 400
    assert not app.log.exists()


def test_every_still_answered_says_so(tmp_path: Path) -> None:
    app = _app(tmp_path, n=1)
    for q in app.items[0].questions:
        _answer(app, 0, q.key, "u")
    assert app.next_open() == -1
    assert b"Every still is answered" in app.handle("GET", "/", b"").body
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_audit.py -q -n0`
Expected: collection fails with `ModuleNotFoundError: No module named 'synthbench.audit'`.

- [ ] **Step 3: The sample and its questions**

Create `synthbench/audit/__init__.py`:

```python
"""The owner's audit of exported stills (synthbench P5a design §4)."""
```

Create `synthbench/audit/sample.py`:

```python
"""The owner's audit sample and its questions (P5a design §4)."""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from synthbench.export.vss import ExportedSet

SEED = 20260929
# Stratum (scenario group) -> stills to audit. S3 rests on threat and suspicious, S2 on the rest.
STRATA: tuple[tuple[str, int], ...] = (
    ("threat", 20),
    ("suspicious", 10),
    ("hard_negative", 15),
    ("benign", 15),
)


@dataclass(frozen=True)
class Question:
    """One yes/no/unclear question about a still. `key` is scene, prop, people or conditions."""

    key: str
    text: str


def allocate(counts: Mapping[str, int], k: int) -> dict[str, int]:
    """k draws spread over values in proportion to their counts: at least one per value while k
    allows, never more than a value has. Deterministic: ties go to the earlier value by name."""
    values = sorted(value for value, count in counts.items() if count > 0)
    k = min(k, sum(counts[value] for value in values))
    total = sum(counts[value] for value in values)
    alloc = dict.fromkeys(values, 0)
    for value in sorted(values, key=lambda v: (-counts[v], v))[:k]:
        alloc[value] = 1
    for _ in range(k - sum(alloc.values())):
        open_values = [value for value in values if alloc[value] < counts[value]]
        best = max(open_values, key=lambda v: (counts[v] * k / total - alloc[v], -values.index(v)))
        alloc[best] += 1
    return alloc


def sample(sets: Sequence[ExportedSet], seed: int = SEED) -> list[ExportedSet]:
    """The audit's stills: each stratum's count allocated across its lighting values, drawn with
    a fixed seed. Ordered by stratum, then lighting, then draw."""
    chosen: list[ExportedSet] = []
    for group, k in STRATA:
        by_lighting: dict[str, list[ExportedSet]] = defaultdict(list)
        for exported in sets:
            if exported.facts["cell"]["group"] == group:
                by_lighting[exported.facts["cell"]["lighting"]].append(exported)
        counts = {lighting: len(members) for lighting, members in by_lighting.items()}
        for lighting, n in sorted(allocate(counts, k).items()):
            members = sorted(by_lighting[lighting], key=lambda s: s.item_id)
            rng = random.Random(f"{seed}:{group}:{lighting}")  # noqa: S311  # reproducible
            chosen.extend(rng.sample(members, n))
    return chosen


def _words(identifier: str) -> str:
    return identifier.replace("_", " ")


def questions(facts: Mapping[str, Any]) -> tuple[Question, ...]:
    """The questions for one still, from its exported facts."""
    cell = facts["cell"]
    subjects = facts.get("subjects", [])
    props = facts.get("props", [])
    cast = ", ".join(f"{s['class']} ({_words(s['role'])})" for s in subjects) or "nobody"
    held = f", with {', '.join(_words(p['class']) for p in props)}" if props else ""
    out = [Question("scene", f"Does this show {_words(cell['scenario'])}: {cast}{held}?")]
    if cell["group"] == "threat" and props:
        things = " and the ".join(_words(p["class"]) for p in props)
        out.append(Question("prop", f"Is the {things} visible?"))
    people = sum(1 for s in subjects if s["class"] == "person")
    out.append(Question("people", f"Exactly {people} person(s)?"))
    out.append(
        Question(
            "conditions",
            f"{_words(cell['lighting'])} light and {_words(cell['weather'])} weather?",
        )
    )
    return tuple(out)
```

`allocate` is largest-remainder with a floor of one per lighting value: IR night and low light are
always covered while k allows (spec §4). `random.Random` is seeded per (group, lighting), so adding
a stratum or a lighting value never reshuffles the others' draws.

- [ ] **Step 4: The page**

Create `synthbench/audit/page.py`:

```python
"""The audit page (P5a design §4): one still at a time, keyboard answers, an append-only log.

`AuditApp.handle(method, path, body)` is the whole application and is tested without a socket;
`serve()` puts it behind `http.server` on 127.0.0.1 only.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from synthbench.audit.sample import Question
from synthbench.export.vss import ExportedSet

ANSWERS = ("y", "n", "u")


@dataclass(frozen=True)
class AuditItem:
    exported: ExportedSet
    questions: tuple[Question, ...]

    @property
    def event_id(self) -> str:
        return str(self.exported.facts["event_id"])


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str
    body: bytes


def load_answers(log: Path) -> dict[tuple[str, str], str]:
    """The latest answer per (event id, question key)."""
    answers: dict[tuple[str, str], str] = {}
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                answers[(row["event_id"], row["question"])] = row["answer"]
    return answers


class AuditApp:
    """The page's routes over a fixed list of items and one answer log."""

    def __init__(self, items: Sequence[AuditItem], log: Path, now: Callable[[], str]) -> None:
        self.items = list(items)
        self.log = log
        self.now = now
        self.answers = load_answers(log)
        self._lock = threading.Lock()

    def answered(self, item: AuditItem) -> bool:
        return all((item.event_id, q.key) in self.answers for q in item.questions)

    def next_open(self) -> int:
        """The first item with an unanswered question, or -1 when every item is answered."""
        return next((i for i, item in enumerate(self.items) if not self.answered(item)), -1)

    def handle(self, method: str, path: str, body: bytes) -> Response:
        if method == "GET" and path in ("", "/"):
            return self._page(self.next_open())
        if method == "GET" and path.startswith("/item/"):
            index = self._index(path.removeprefix("/item/"))
            return self._page(index) if index is not None else _not_found()
        if method == "GET" and path.startswith("/still/"):
            index = self._index(path.removeprefix("/still/"))
            if index is None:
                return _not_found()
            data = self.items[index].exported.still.read_bytes()
            return Response(200, "image/jpeg", data)
        if method == "POST" and path == "/answer":
            return self._answer(body)
        return _not_found()

    def _index(self, text: str) -> int | None:
        return int(text) if text.isdigit() and int(text) < len(self.items) else None

    def _answer(self, body: bytes) -> Response:
        try:
            request = json.loads(body)
            item = self.items[int(request["index"])]
            key, answer = str(request["question"]), str(request["answer"])
        except ValueError, KeyError, IndexError, TypeError:
            return Response(400, "text/plain", b"expected {index, question, answer}")
        if answer not in ANSWERS or key not in {q.key for q in item.questions}:
            return Response(400, "text/plain", b"unknown question or answer")
        row = {
            "event_id": item.event_id,
            "question": key,
            "answer": answer,
            "time": self.now(),
        }
        with self._lock:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with self.log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(row, sort_keys=True) + "\n")
            self.answers[(item.event_id, key)] = answer
        body_out = json.dumps({"next": self.next_open()}).encode()
        return Response(200, "application/json", body_out)

    def _page(self, index: int) -> Response:
        done = sum(1 for item in self.items if self.answered(item))
        head = f"<p>{done}/{len(self.items)} stills fully answered.</p>"
        if index < 0:
            return _html(head + "<h1>Every still is answered.</h1>")
        item = self.items[index]
        rows = "".join(
            f'<li data-key="{q.key}">{escape(q.text)} '
            f"<b>{escape(self.answers.get((item.event_id, q.key), '·'))}</b></li>"
            for q in item.questions
        )
        body = (
            f"{head}<h1>{index + 1}. {escape(item.event_id)}</h1>"
            f'<img src="/still/{index}" alt="still"><ol>{rows}</ol>'
            "<p>Keys: <b>y</b> yes, <b>n</b> no, <b>u</b> unclear answer the selected question "
            "(the first unanswered); <b>1-4</b> select a question to change it; <b>[</b> and "
            "<b>]</b> move between stills.</p>"
            f"<script>{_SCRIPT % {'index': index, 'last': len(self.items) - 1}}</script>"
        )
        return _html(body)


_SCRIPT = """
const items = [...document.querySelectorAll('li')];
let selected = items.findIndex(li => li.querySelector('b').textContent === '·');
if (selected < 0) selected = 0;
items[selected].style.outline = '2px solid #36c';
document.addEventListener('keydown', async (e) => {
  if (e.key === '[' && %(index)d > 0) location.href = '/item/' + (%(index)d - 1);
  if (e.key === ']' && %(index)d < %(last)d) location.href = '/item/' + (%(index)d + 1);
  if ('1234'.includes(e.key) && items[+e.key - 1]) {
    items[selected].style.outline = ''; selected = +e.key - 1;
    items[selected].style.outline = '2px solid #36c';
  }
  if (!'ynu'.includes(e.key) || e.key === '') return;
  const r = await fetch('/answer', {method: 'POST', body: JSON.stringify(
    {index: %(index)d, question: items[selected].dataset.key, answer: e.key})});
  const next = (await r.json()).next;
  const open = items.some((li, i) => i !== selected && li.querySelector('b').textContent === '·');
  location.href = open ? '/item/%(index)d' : (next < 0 ? '/' : '/item/' + next);
});
"""


def _html(body: str) -> Response:
    page = (
        "<!doctype html><meta charset=utf-8><title>synthbench audit</title>"
        "<style>body{font-family:sans-serif;margin:16px} img{max-width:100%;max-height:70vh}"
        " li{margin:6px 0;font-size:18px}</style>" + body
    )
    return Response(200, "text/html; charset=utf-8", page.encode())


def _not_found() -> Response:
    return Response(404, "text/plain", b"not found")


def serve(app: AuditApp, port: int) -> None:
    """Serve `app` on 127.0.0.1:`port` until interrupted."""

    class Handler(BaseHTTPRequestHandler):
        def _respond(self, response: Response) -> None:
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

        def do_GET(self) -> None:
            self._respond(app.handle("GET", self.path, b""))

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self._respond(app.handle("POST", self.path, self.rfile.read(length)))

        def log_message(self, format: str, *args: object) -> None:
            del format, args  # quiet: the command prints its own progress

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        server.serve_forever()
```

`handle` is pure (plan ruling P5a-R8): the tests call it without a socket. Stills are served by
sample index, never by a path from the request. The log is append-only under a lock; the
in-memory answers mirror it, so a restart resumes where the owner stopped.

- [ ] **Step 5: The command**

Create `synthbench/commands/audit.py`:

```python
"""`audit`: the owner's 60-still audit page on 127.0.0.1 (P5a design §4).

An owner command. It reads an export, never the corpus, and appends the owner's answers to
`$SYNTHBENCH_ROOT/audits/<version>/audit.jsonl`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

from synthbench.audit.page import AuditApp, AuditItem, serve
from synthbench.audit.sample import questions, sample
from synthbench.commands.common import EXIT_OK, Parser, RequestError, now_iso, taxonomy
from synthbench.commands.export import export_dir
from synthbench.contract.store import DEFAULT_SYNTHBENCH_ROOT
from synthbench.export.vss import read_sets

DEFAULT_PORT = 8765


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "audit",
        help="serve the owner's audit page for an export on 127.0.0.1 (owner)",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"loopback port (default {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        help="export directory (default: $SYNTHBENCH_ROOT/exports/<version>/vss)",
    )
    parser.set_defaults(run=run)


def audit_log(version: str, env: Mapping[str, str]) -> Path:
    root = Path(env.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
    return root / "audits" / version / "audit.jsonl"


def build_app(version: str, export: Path, env: Mapping[str, str]) -> AuditApp:
    """The page over this export's audit sample and this version's answer log."""
    sets = read_sets(export)
    if not sets:
        raise RequestError(f"no exported sets under {export}; run `export vss` first")
    items = [AuditItem(exported, questions(exported.facts)) for exported in sample(sets)]
    return AuditApp(items, audit_log(version, env), now_iso)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    export: Path = args.export if args.export is not None else export_dir(tax.version, env)
    app = build_app(tax.version, export, env)
    done = sum(1 for item in app.items if app.answered(item))
    port = args.port
    sys.stdout.write(
        f"audit {tax.version}: {len(app.items)} stills, {done} fully answered; answers go to "
        f"{app.log}\n  open http://127.0.0.1:{port}/ (remote: ssh -L {port}:127.0.0.1:{port} "
        "<this host>); Ctrl-C stops.\n"
    )
    sys.stdout.flush()
    try:
        serve(app, port)
    except KeyboardInterrupt:
        pass
    except OSError as error:
        raise RequestError(
            f"cannot listen on 127.0.0.1:{port} ({error}); pick another --port"
        ) from error
    return EXIT_OK
```

In `synthbench/cli.py`, add `audit` to the `from synthbench.commands import (...)` list (in
alphabetical order, first) and to `COMMANDS` after `export`.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest backend/tests/unit/synthbench/test_audit.py -q -n0 -p randomly`
Expected: 12 passed.

- [ ] **Step 7: Document the command**

In `docs/synthbench/command-reference.md`, insert after the `export vss` section:

```markdown
## `audit`

Owner only. Serves the owner's audit page on `127.0.0.1` for the P5a replay's truth check
(`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §4): 60 exported stills,
20 threat, 10 suspicious, 15 hard negative and 15 benign, each stratum spread across its lighting
values, drawn with a fixed seed. It runs until Ctrl-C.

| Option           | Default                                  | Meaning          |
| ---------------- | ---------------------------------------- | ---------------- |
| `--port <n>`     | 8765                                     | loopback port    |
| `--export <dir>` | `$SYNTHBENCH_ROOT/exports/<version>/vss` | export directory |

- **Reads:** the export's sets (never the corpus) and the answer log.
- **Writes:** appends one line per answer to `$SYNTHBENCH_ROOT/audits/<version>/audit.jsonl`
  (`event_id`, `question`, `answer`, `time`). The latest answer per question wins, so the owner can
  stop and resume, and change an answer.
- **Questions** (`y` yes, `n` no, `u` unclear): scene ("Does this show …?"), prop (threat scenes:
  "Is the … visible?"), people ("Exactly N person(s)?") and conditions (lighting and weather).
- **From another machine:** `ssh -L 8765:127.0.0.1:8765 <this host>`, then open
  `http://127.0.0.1:8765/`.
- **Exit 1:** the export has no sets, or the port cannot be opened.
```

Create `synthbench/audit/AGENTS.md`:

```markdown
# synthbench/audit — Agent Guide

## Purpose

The owner's audit of exported stills (synthbench P5a,
`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §4). Its answers put an
error bar on the declared truth P5a scores against, and later measure a judge model.

## Files

| File        | What                                                                                                 |
| ----------- | ---------------------------------------------------------------------------------------------------- |
| `sample.py` | the stratified, seeded 60-still sample (`STRATA`, `allocate`, `sample`) and each still's `questions` |
| `page.py`   | `AuditApp.handle(method, path, body)`, the whole page, and `serve()`, its loopback-only server       |

The command is `synthbench/commands/audit.py` (`python -m synthbench audit`).

## Rules

- `handle` is pure and tested without a socket; `serve` binds `127.0.0.1` only.
- Stills are served by sample index, never by a path from the request.
- The answer log is append-only; the latest answer per (event, question) wins.
```

In `synthbench/AGENTS.md`, add after the `export/` row:

```markdown
| `audit/` | the owner's audit: the stratified 60-still sample, its questions and the loopback page (P5a) |
```

In `backend/tests/unit/synthbench/AGENTS.md`, add after the `test_export_vss.py` row:

```markdown
| `test_audit.py` | `synthbench/audit/`: the stratified sample, the questions, the page's handler and answer log |
```

- [ ] **Step 8: Run the synthbench suite and mypy**

Run: `uv run pytest backend/tests/unit/synthbench/ -q -n auto -p randomly`
Expected: all pass, including `test_command_reference.py`.
Run: `uv run mypy synthbench/ backend/tests/unit/synthbench/`
Expected: no issues.

- [ ] **Step 9: Commit**

```bash
git add synthbench/audit/ synthbench/commands/audit.py synthbench/cli.py synthbench/AGENTS.md \
  docs/synthbench/command-reference.md backend/tests/unit/synthbench/AGENTS.md \
  backend/tests/unit/synthbench/test_audit.py
SKIP=semgrep uvx pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(synthbench): audit, the owner's check of the declared truth

A loopback page over a seeded, stratified sample of 60 exported stills asks
whether the scene, the prop, the people count and the conditions match what
each event declares. Answers append to audits/<version>/audit.jsonl; the
latest per question wins. Synthbench P5a, spec section 4.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `replay`, and the vLLM comparison path

> **Built during planning: commit `e175c6c7`** (merged with main at `c444456d`). Execution runs
> the task review on `e175c6c7^..e175c6c7` and implements nothing unless the review finds a
> defect, or Task 1 recorded a vLLM rejection of the request body (Task 1 Step 7), whose smallest
> fix goes in `ModelField`; the steps below are the brief the reviewer checks the commit against.

One served model over the exported items, through the shipped replay (spec §3). Per plan rulings
P5a-R2 and P5a-R9, every model, including the vLLM ones, goes through the shipped `VlmClient`;
only its settings and its transport differ.

**Files:**

- Create: `synthbench/run/__init__.py`, `synthbench/run/models.py`, `synthbench/run/replay.py`,
  `synthbench/run/AGENTS.md`
- Create: `synthbench/commands/replay.py`
- Modify: `synthbench/cli.py` (import and register `replay`, after `audit`)
- Modify: `docs/synthbench/command-reference.md` (a `replay` section after `audit`)
- Modify: `synthbench/AGENTS.md` (a `run/` layout row after `audit/`)
- Modify: `backend/tests/unit/synthbench/AGENTS.md` (a `test_replay.py` row)
- Test: `backend/tests/unit/synthbench/test_replay.py`

**Interfaces:**

- Consumes: Task 2 (a declared `timestamp` imports); Task 3's `vss.write_set`, `vss.attribution`,
  the `vss.*_FILE` names and `export_dir(version, env)`; `backend.evaluation.eval_store.EvalStore`
  (`replay(run_id)`); `backend.evaluation.label_import.import_generated_items`;
  `backend.evaluation.vlm_replay.run_replay(store, *, candidate, engine, limit, make_client)` and
  `git_commit()`; `backend.services.vlm_client.VlmClient(settings=, base_url=, transport=)`;
  `synthbench.generate.comfy.serve.container_running(run)`; the test helper
  `make_fake_llama(model_path=)` in `backend/tests/unit/services/test_vlm_client.py`.
- Produces (used by Tasks 6 and 7):

  - `synthbench.run.models.Model(name, transport, served_id, url_env, default_url)` and
    `MODELS: dict[str, Model]` with `qwen3-vl-8b`, `qwen3-vl-4b`, `nemotron-12b-vl` (transport
    `ai-vlm`), `cosmos-reason2-8b` and `flagship` (transport `vllm`);
  - `synthbench.run.replay.execute(model, url, export, store_path, runs_dir, limit, deps) ->
ReplayResult(replay_id, run_dir, report)`;
  - `$SYNTHBENCH_ROOT/runs/replays/<replay_id>/run.json` with keys `replay_id`, `model`,
    `served_id`, `transport`, `url`, `build`, `enforcement_probe`, `export`, `store`,
    `eval_run_id`, `imported_new`, `already_imported`, `limit`, `commit`, `started_utc`, `report`;
    `replay_id` is `<YYYYmmddTHHMMSSZ>-<model name>`;
  - the eval store `$SYNTHBENCH_ROOT/eval/<version>/eval.sqlite`, whose `replay(eval_run_id)`
    rows Task 6 scores.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/synthbench/test_replay.py`:

```python
"""`replay` (P5a design §3): pre-run checks, the import gate, and both client paths."""

from __future__ import annotations

import ast
import asyncio
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from synthbench import cli
from synthbench.export import vss
from synthbench.run.models import MODELS
from synthbench.run.replay import (
    Deps,
    ImportRefused,
    ReplayRefused,
    check,
    client_factory,
    execute,
    import_export,
)

from backend.evaluation.eval_store import EvalStore
from backend.services.vlm_verdict import VlmAssessContext, VlmAssessRequest
from backend.tests.unit.services.test_vlm_client import make_fake_llama
from backend.tests.unit.synthbench import helpers as h

QWEN = MODELS["qwen3-vl-8b"]
FLAGSHIP = MODELS["flagship"]
URL = "http://fake-vlm:8098"


@pytest.fixture(autouse=True)
def _fresh_breaker_registry() -> Iterator[None]:
    """The shared "ai-vlm" breaker must not carry failures between tests."""
    from backend.services.circuit_breaker import reset_circuit_breaker_registry

    reset_circuit_breaker_registry()
    yield
    reset_circuit_breaker_registry()


def _export(root: Path, n: int = 2, timestamp: Any = "2026-04-15T14:32:00-04:00") -> Path:
    """An export of n threat sets, each a stand-in still with its attribution."""
    export = root / "exports" / "vss"
    for i in range(n):
        labels = {
            "category": "threats",
            "risk": {"min_score": 70, "max_score": 95},
            "timestamp": timestamp,
            "synthbench": {"event_id": f"B-t-{i:03d}"},
        }
        files = {
            vss.LABELS_FILE: json.dumps(labels).encode(),
            vss.STILL_FILE: b"\xff\xd8\xff" + b"\x00" * 32,
            vss.SIDECAR_FILE: json.dumps(vss.attribution("tierb-v0")).encode(),
        }
        vss.write_set(export, "threats", f"B-t-{i:03d}", files)
    return export


def _run(renderer: str = "inactive") -> Any:
    """systemctl reports `renderer`; podman reports no ComfyUI container."""

    def run(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        if "is-active" in argv:
            return subprocess.CompletedProcess(argv, 0, renderer + "\n", "")
        return subprocess.CompletedProcess(argv, 1, "", "")  # `container exists`: no container

    return run


def _get(props: dict[str, Any] | None = None, status: int = 200) -> Any:
    props = props or {
        "model_path": "/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf",
        "build_info": "b7972",
    }

    def get(url: str) -> httpx.Response:
        if url.endswith("/props"):
            return httpx.Response(200, json=props)
        if url.endswith("/v1/models"):
            return httpx.Response(200, json={"data": [{"id": "claude-flagship"}]})
        return httpx.Response(status)

    return get


def test_a_ready_endpoint_passes_and_reports_its_build() -> None:
    assert check(QWEN, URL, Deps(get=_get(), run=_run())) == "b7972"
    assert check(FLAGSHIP, URL, Deps(get=_get(), run=_run())) == ""


def test_an_endpoint_that_does_not_answer_is_refused() -> None:
    def down(url: str) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ReplayRefused, match="does not answer"):
        check(QWEN, URL, Deps(get=down, run=_run()))
    with pytest.raises(ReplayRefused, match="HTTP 503"):
        check(QWEN, URL, Deps(get=_get(status=503), run=_run()))


def test_a_running_renderer_is_refused() -> None:
    with pytest.raises(ReplayRefused, match="renderer is running"):
        check(QWEN, URL, Deps(get=_get(), run=_run("active")))


def test_the_wrong_served_model_is_refused() -> None:
    other = {"model_path": "/models/Qwen3VL-4B-Instruct-Q4_K_M.gguf", "build_info": "b7972"}
    with pytest.raises(ReplayRefused, match="Qwen3VL-4B-Instruct-Q4_K_M"):
        check(QWEN, URL, Deps(get=_get(props=other), run=_run()))


def test_the_import_is_idempotent_and_refuses_a_bad_set(tmp_path: Path) -> None:
    export = _export(tmp_path)
    with EvalStore(tmp_path / "eval.sqlite") as store:
        assert import_export(store, export) == (2, 0)
        assert import_export(store, export) == (0, 2)
    bad = _export(tmp_path / "bad", timestamp="noon")
    with EvalStore(tmp_path / "bad.sqlite") as store, pytest.raises(ImportRefused, match="noon"):
        import_export(store, bad)


def test_a_replay_reads_the_exports_stills_and_records_the_run(tmp_path: Path) -> None:
    """Every item is scored, none refused: the client's capture root is the export, so it can
    read the stills (it refuses any image outside its root)."""
    export = _export(tmp_path)
    app = make_fake_llama(model_path="/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf")
    deps = Deps(get=_get(), run=_run(), inner_transport=httpx.ASGITransport(app=app))
    result = execute(
        QWEN, URL, export, tmp_path / "eval" / "eval.sqlite", tmp_path / "runs", None, deps
    )
    assert result.report["n_items"] == 2
    assert result.report["s5"]["refusals"] == 0
    record = json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["model"] == "qwen3-vl-8b"
    assert record["build"] == "b7972"
    assert record["enforcement_probe"] is True
    with EvalStore(tmp_path / "eval" / "eval.sqlite") as store:
        rows = store.replay(record["eval_run_id"])
    assert [row["risk_score"] for row in rows] == [50, 50]  # the fake's schema-filled verdict


def test_a_vllm_model_gets_its_name_the_schema_and_no_probe(tmp_path: Path) -> None:
    export = _export(tmp_path, n=1)
    seen: list[dict[str, Any]] = []

    def vllm(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        seen.append({"path": request.url.path, **body})
        if body.get("model") != "claude-flagship":
            return httpx.Response(404, json={"error": "no such model"})
        verdict = {
            "verdict": "rejected",
            "risk_score": 12,
            "summary": "s",
            "reasoning": "r",
            "description": "d",
            "criteria": [{"name": "n", "passed": False, "evidence": "e"}],
            "provenance": {"engine": "x", "model_id": "y"},
        }
        choice = {"message": {"content": json.dumps(verdict)}, "finish_reason": "stop"}
        return httpx.Response(200, json={"choices": [choice]})

    client = client_factory(FLAGSHIP, URL, export, httpx.MockTransport(vllm))()
    still = str(export / "threats" / "B-t-000" / vss.STILL_FILE)
    context = VlmAssessContext(camera_id="c", timestamp="2026-04-15T14:32:00-04:00")
    request = VlmAssessRequest(image_paths=[still], context=context)

    async def assess() -> Any:
        try:
            return await client.assess(request)
        finally:
            await client.close()

    verdict = asyncio.run(assess())
    assert (verdict.verdict, verdict.risk_score) == ("rejected", 12)
    assert verdict.provenance.model_id == "claude-flagship"
    assert [call["path"] for call in seen] == ["/v1/chat/completions"]  # no /props probe
    assert seen[0]["response_format"]["type"] == "json_schema"


def test_the_model_table_imports_no_backend() -> None:
    """Commands import `synthbench.run.models` at startup, so it must stay backend-free."""
    source = (Path(cli.__file__).parent / "run" / "models.py").read_text(encoding="utf-8")
    imported = [
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    assert not [module for module in imported if module.startswith("backend")]


def test_replay_needs_an_export(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert h.run(tmp_path, "replay", "--model", "flagship") == cli.EXIT_ERROR
    assert "run `export vss` first" in capsys.readouterr().err
```

Two of these guard the fixes that pre-validation found. Remove `"foscam_base_path": str(export)`
from `client_factory` and `test_a_replay_reads_the_exports_stills_and_records_the_run` fails
(every item comes back refused: `VlmClient` reads no image outside its capture root). Remove the
`ModelField` wrapping and `test_a_vllm_model_gets_its_name_the_schema_and_no_probe` fails (vLLM
answers 404 without `model`). The autouse fixture resets the shared `ai-vlm` circuit breaker, which
otherwise carries one test's failures into the next.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_replay.py -q -n0`
Expected: collection fails with `ModuleNotFoundError: No module named 'synthbench.run'`.

- [ ] **Step 3: The model table**

Create `synthbench/run/__init__.py`:

```python
"""Replaying served models over exported items (synthbench P5a design §3).

`models.py` imports nothing from `backend`, so commands may import it at startup; `replay.py`
imports `backend` and is imported only when a replay runs (spec §7.1 allows it here).
"""
```

Create `synthbench/run/models.py`:

```python
"""The models `synthbench replay` can score (P5a design §3). Imports nothing from `backend`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Model:
    """One replayable model.

    `served_id` is the identity the endpoint must report before a replay trusts it: for `ai-vlm`
    (llama.cpp) the model file's stem from `/props`, for vLLM an id from `/v1/models`.
    """

    name: str
    transport: Literal["ai-vlm", "vllm"]
    served_id: str
    url_env: str
    default_url: str


MODELS: dict[str, Model] = {
    model.name: model
    for model in (
        # The product VLM (VSS spec rev 7) and the other two VSS bake-off candidates, all served by
        # the product's `ai-vlm` on port 8098, one at a time.
        Model(
            "qwen3-vl-8b",
            "ai-vlm",
            "Qwen3VL-8B-Instruct-Q4_K_M",
            "AI_VLM_URL",
            "http://127.0.0.1:8098",
        ),
        Model(
            "qwen3-vl-4b",
            "ai-vlm",
            "Qwen3VL-4B-Instruct-Q4_K_M",
            "AI_VLM_URL",
            "http://127.0.0.1:8098",
        ),
        Model(
            "nemotron-12b-vl",
            "ai-vlm",
            "NVIDIA-Nemotron-Nano-12B-v2-VL-Q4_K_M",
            "AI_VLM_URL",
            "http://127.0.0.1:8098",
        ),
        # Comparison models under vLLM (owner, 2026-09-29).
        Model(
            "cosmos-reason2-8b",
            "vllm",
            "nvidia/Cosmos-Reason2-8B",
            "SYNTHBENCH_COSMOS_URL",
            "http://127.0.0.1:8099",
        ),
        Model(
            "flagship",
            "vllm",
            "claude-flagship",
            "SYNTHBENCH_FLAGSHIP_URL",
            "http://127.0.0.1:8000",
        ),
    )
}
```

It imports nothing from `backend`: `cli.py` imports every command at startup, `replay`'s command
imports this table for `--model`'s choices, and the generation agent's commands must not load
`backend`.

- [ ] **Step 4: The replay**

Create `synthbench/run/replay.py`:

```python
"""`replay`: one served model over the exported items, through the shipped replay (P5a §3).

It imports the export into the eval store (idempotent), checks the endpoint, the renderer and the
served model's identity, then runs `backend.evaluation.vlm_replay.run_replay` with a
`VlmClient` whose capture root is the export directory (the client refuses any image outside
it). `ai-vlm` models run the client as the product does; vLLM models run it with the
enforcement probe off (vLLM has no llama.cpp `/props`) and a transport that names the served
model (plan ruling P5a-R2).
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from backend.core.config import get_settings
from backend.evaluation.eval_store import EvalStore
from backend.evaluation.label_import import import_generated_items
from backend.evaluation.vlm_replay import git_commit, run_replay
from backend.services.vlm_client import VlmClient

from synthbench.generate.comfy import serve
from synthbench.run.models import Model

Runner = Callable[..., subprocess.CompletedProcess[str]]
Getter = Callable[[str], httpx.Response]


class ReplayRefused(Exception):
    """A pre-run check failed: the run would measure the wrong thing, or disturb the GPU."""


class ImportRefused(Exception):
    """The export did not import cleanly into the eval store."""


def _get(url: str) -> httpx.Response:
    return httpx.get(url, timeout=10.0)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Deps:
    """The replay's outside world; tests replace each piece."""

    get: Getter = _get
    run: Runner = subprocess.run
    inner_transport: httpx.AsyncBaseTransport | None = None
    now: Callable[[], datetime] = field(default=_utc_now)


class ModelField(httpx.AsyncBaseTransport):
    """Names the served model in each chat request: vLLM's OpenAI server routes by `model`."""

    def __init__(self, model: str, inner: httpx.AsyncBaseTransport | None = None) -> None:
        self._model = model
        self._inner = inner or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/v1/chat/completions"):
            body = json.loads(request.content)
            body["model"] = self._model
            headers = [
                (key, value)
                for key, value in request.headers.multi_items()
                if key.lower() != "content-length"
            ]
            request = httpx.Request(
                "POST", request.url, headers=headers, content=json.dumps(body).encode()
            )
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def renderer_stopped(run: Runner) -> bool:
    """True only when the renderer unit is not active and no ComfyUI container runs. A state
    that cannot be read counts as running: replay needs the renderer's GPU memory."""
    try:
        active = run(
            ["systemctl", "--user", "is-active", "synthbench-renderer"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
        return active != "active" and not serve.container_running(run)
    except OSError, subprocess.SubprocessError, serve.ServeError:
        return False


def served_identity(model: Model, url: str, get: Getter) -> tuple[str, str]:
    """(identity, build) as the endpoint reports them."""
    if model.transport == "ai-vlm":
        props = get(f"{url}/props").json()
        return Path(props.get("model_path") or "").stem, str(props.get("build_info", ""))
    ids = [str(entry["id"]) for entry in get(f"{url}/v1/models").json().get("data", [])]
    return (model.served_id if model.served_id in ids else ", ".join(ids)), ""


def check(model: Model, url: str, deps: Deps) -> str:
    """Refuse unless the endpoint answers, the renderer is stopped and the endpoint serves
    `model`. Returns the build the endpoint reports ("" for vLLM)."""
    probe = f"{url}/health" if model.transport == "ai-vlm" else f"{url}/v1/models"
    try:
        status = deps.get(probe).status_code
    except httpx.HTTPError as error:
        raise ReplayRefused(f"{model.name}: {probe} does not answer ({error})") from error
    if status != 200:
        raise ReplayRefused(f"{model.name}: {probe} answered HTTP {status}")
    if not renderer_stopped(deps.run):
        raise ReplayRefused(
            "the renderer is running, or its state cannot be read: stop synthbench-renderer "
            "first (replay needs its GPU memory)"
        )
    try:
        identity, build = served_identity(model, url, deps.get)
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise ReplayRefused(
            f"{model.name}: cannot read {url}'s model identity ({error})"
        ) from error
    if identity != model.served_id:
        raise ReplayRefused(f"{url} serves {identity!r}, not {model.name} ({model.served_id})")
    return build


def client_factory(
    model: Model, url: str, export: Path, inner: httpx.AsyncBaseTransport | None = None
) -> Callable[[], VlmClient]:
    """The replay's client: the shipped `VlmClient`, reading stills from the export."""

    def build() -> VlmClient:
        # camera_timezone=None as vlm_replay.client_factory pins it: the prompt shows the stored
        # timestamp verbatim. The capture root is the export: the client refuses images elsewhere.
        update: dict[str, Any] = {"camera_timezone": None, "foscam_base_path": str(export)}
        transport = inner
        if model.transport == "vllm":
            update |= {
                "vlm_enforcement_probe_enabled": False,
                "vlm_model_id": model.served_id,
                "nemotron_verification_engine": "vllm",
            }
            transport = ModelField(model.served_id, inner)
        settings = get_settings().model_copy(update=update)
        return VlmClient(settings=settings, base_url=url, transport=transport)

    return build


def import_export(store: EvalStore, export: Path) -> tuple[int, int]:
    """Import the export: (new items, already imported). Any other skip is refused."""
    rows = import_generated_items(corpus_dir=export, store=store)
    skipped = [(row, row.reason or "") for row in rows if row.skipped]
    already = [row for row, reason in skipped if reason.startswith("already imported")]
    other = [(row, reason) for row, reason in skipped if not reason.startswith("already imported")]
    if other:
        shown = "; ".join(f"{row.item_id}: {reason}" for row, reason in other[:5])
        more = f" (+{len(other) - 5} more)" if len(other) > 5 else ""
        raise ImportRefused(shown + more)
    return len(rows) - len(already), len(already)


@dataclass(frozen=True)
class ReplayResult:
    replay_id: str
    run_dir: Path
    report: dict[str, Any]


def execute(
    model: Model,
    url: str,
    export: Path,
    store_path: Path,
    runs_dir: Path,
    limit: int | None,
    deps: Deps,
) -> ReplayResult:
    """Check, import, replay, and record the run under `runs_dir/<replay_id>/run.json`."""
    build = check(model, url, deps)
    started = deps.now()
    replay_id = f"{started:%Y%m%dT%H%M%SZ}-{model.name}"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with EvalStore(store_path) as store:
        new, already = import_export(store, export)
        candidate = f"{model.served_id}@{model.transport}" + (f":{build}" if build else "")
        report = asyncio.run(
            run_replay(
                store,
                candidate=candidate,
                engine="llama.cpp" if model.transport == "ai-vlm" else "vllm",
                limit=limit,
                make_client=client_factory(model, url, export, deps.inner_transport),
            )
        )
    run_dir = runs_dir / replay_id
    run_dir.mkdir(parents=True)
    record = {
        "replay_id": replay_id,
        "model": model.name,
        "served_id": model.served_id,
        "transport": model.transport,
        "url": url,
        "build": build,
        "enforcement_probe": model.transport == "ai-vlm",
        "export": str(export),
        "store": str(store_path),
        "eval_run_id": report["run_id"],
        "imported_new": new,
        "already_imported": already,
        "limit": limit,
        "commit": git_commit(),
        "started_utc": started.isoformat(timespec="seconds"),
        "report": report,
    }
    (run_dir / "run.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return ReplayResult(replay_id, run_dir, report)
```

- [ ] **Step 5: The command**

Create `synthbench/commands/replay.py`:

```python
"""`replay --model <name>`: one served VLM over the exported items (P5a design §3).

An owner command. The backend half (`synthbench.run.replay`) is imported inside `run()`: `cli.py`
imports every command at startup, and the generation agent's commands must not load `backend`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

from synthbench.commands.common import EXIT_OK, AskOwner, Parser, RequestError, taxonomy
from synthbench.commands.export import export_dir
from synthbench.contract.store import DEFAULT_SYNTHBENCH_ROOT
from synthbench.run.models import MODELS


def _limit(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"limit must be a positive integer: {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"limit must be a positive integer, got {value}")
    return value


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "replay",
        help="replay one served VLM over the exported items and record the run (owner)",
        allow_abbrev=False,
    )
    parser.add_argument("--model", required=True, choices=sorted(MODELS), help="the served model")
    parser.add_argument("--url", default=None, help="its endpoint (default: per model)")
    parser.add_argument("--limit", type=_limit, default=None, help="replay only the first n items")
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        help="export directory (default: $SYNTHBENCH_ROOT/exports/<version>/vss)",
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    from synthbench.run.replay import Deps, ImportRefused, ReplayRefused, execute

    tax = taxonomy()
    model = MODELS[args.model]
    url: str = args.url or env.get(model.url_env, model.default_url)
    export: Path = args.export if args.export is not None else export_dir(tax.version, env)
    if not any(export.glob("*/*/expected_labels.json")):
        raise RequestError(f"no exported sets under {export}; run `export vss` first")
    root = Path(env.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
    try:
        result = execute(
            model,
            url,
            export,
            root / "eval" / tax.version / "eval.sqlite",
            root / "runs" / "replays",
            args.limit,
            Deps(),
        )
    except ReplayRefused as error:
        raise AskOwner(f"{error}.") from error
    except ImportRefused as error:
        raise AskOwner(f"the export did not import cleanly: {error}.") from error
    report = result.report
    s2, s3 = report["s2"], report["s3"]["all"]
    sys.stdout.write(
        f"replay {model.name}: {report['n_items']} items; S2 {s2['fp']}/{s2['n']} false alarms, "
        f"S3 {s3['hit']}/{s3['n']} incidents at level; {report['s5']['refusals']} refused\n"
        f"  {result.run_dir / 'run.json'}\n"
    )
    return EXIT_OK
```

It imports `synthbench.run.replay` inside `run()`, never at module level
(`test_import_rule.py` allows `synthbench/run/` to import `backend`, but `cli.py` must not load it).
In `synthbench/cli.py`, add `replay` to the `from synthbench.commands import (...)` list (between
`render` and `report`) and to `COMMANDS` after `audit`.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest backend/tests/unit/synthbench/test_replay.py -q -n0 -p randomly`
Expected: 9 passed.

- [ ] **Step 7: Document the command**

In `docs/synthbench/command-reference.md`, insert after the `audit` section:

```markdown
## `replay`

Owner only. Replays one served VLM over the exported items through the shipped replay
(`backend/evaluation/vlm_replay.py`), for P5a
(`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §3). The model must
already be served: `replay` never starts, stops or reconfigures a model server.

| Option           | Default                                  | Meaning                                                                            |
| ---------------- | ---------------------------------------- | ---------------------------------------------------------------------------------- |
| `--model <name>` | required                                 | `qwen3-vl-8b`, `qwen3-vl-4b`, `nemotron-12b-vl`, `cosmos-reason2-8b` or `flagship` |
| `--url <url>`    | per model (below)                        | the model's endpoint                                                               |
| `--limit <n>`    | every item                               | replay only the first n items                                                      |
| `--export <dir>` | `$SYNTHBENCH_ROOT/exports/<version>/vss` | export directory                                                                   |

- **Endpoints:** the three `ai-vlm` models at `$AI_VLM_URL`, else `http://127.0.0.1:8098`;
  `cosmos-reason2-8b` at `$SYNTHBENCH_COSMOS_URL`, else `http://127.0.0.1:8099`; `flagship` at
  `$SYNTHBENCH_FLAGSHIP_URL`, else `http://127.0.0.1:8000`.
- **Checks, before the first item:** the endpoint answers; the renderer is stopped
  (`synthbench-renderer` is not active and no `synthbench-comfyui` container runs); the endpoint
  serves the named model (for `ai-vlm`, the model file stem `/props` reports; for vLLM, an id in
  `/v1/models`).
- **Client:** the shipped `VlmClient`, reading stills from the export. vLLM models run it with the
  enforcement probe off (vLLM has no `/props`) and the served model's name added to each request.
- **Reads:** the export's sets.
- **Writes:** imports the export into `$SYNTHBENCH_ROOT/eval/<version>/eval.sqlite` (a set
  already imported is skipped), then the replay's results there under a new eval run id, and
  `$SYNTHBENCH_ROOT/runs/replays/<replay_id>/run.json`: the model, endpoint, build, eval run id,
  commit and the replay's report.
- **Prints:** the items replayed, S2 false alarms, S3 incidents at level, refusals, and the path
  of `run.json`.
- **Exit 1:** the export has no sets.
- **Exit 2:** a check failed, or a set did not import for a reason other than "already imported".
```

Create `synthbench/run/AGENTS.md`:

```markdown
# synthbench/run — Agent Guide

## Purpose

Replays served VLMs over the exported items (synthbench P5a,
`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §3). With
`synthbench/score/`, the only synthbench package that may import `backend` (spec §7.1;
`backend/tests/unit/synthbench/test_import_rule.py`).

## Files

| File        | What                                                                                                                                 |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `models.py` | `Model` and `MODELS`: each replayable model's transport, served identity and default endpoint; imports nothing from `backend`        |
| `replay.py` | the pre-run checks, the import, the `VlmClient` factory (capture root: the export; `ModelField` for vLLM) and `execute` (`run.json`) |

The command is `synthbench/commands/replay.py` (`python -m synthbench replay`); it imports
`replay.py` inside `run()`.

## Rules

- `models.py` stays backend-free: `cli.py` imports every command at startup, and `replay`'s
  command imports `models.py` (a test pins this).
- Replay never starts, stops or reconfigures a model server, and refuses while the renderer runs.
- The client is the shipped `VlmClient`; only its settings and transport differ per model (plan
  ruling P5a-R2). Its capture root is the export directory: `VlmClient` refuses any image outside
  `foscam_base_path`.
- Each replay gets a new eval run id; its `run.json` names the endpoint, build and commit.
```

In `synthbench/AGENTS.md`, add after the `audit/` row:

```markdown
| `run/` | `replay`: served VLMs over the export, through the shipped `VlmClient`; imports `backend` (P5a) |
```

In `backend/tests/unit/synthbench/AGENTS.md`, add after the `test_audit.py` row:

```markdown
| `test_replay.py` | `python -m synthbench replay`: the pre-run checks, the import gate, both client paths |
```

The runbook's bring-up section is Task 1's (Step 9), written from the commands that worked there.

- [ ] **Step 8: Run the affected suites and mypy**

Run: `uv run pytest backend/tests/unit/synthbench/ backend/tests/unit/evaluation/ backend/tests/unit/services/test_vlm_client.py -q -n auto -p randomly --deselect backend/tests/unit/evaluation/test_build_gen2.py`
Expected: all pass (`test_build_gen2.py` is deselected for its pre-existing timeouts; see Task 2
Step 4).
Run: `uv run mypy synthbench/ backend/tests/unit/synthbench/`
Expected: no issues.

- [ ] **Step 9: Commit**

```bash
git add synthbench/run/ synthbench/commands/replay.py synthbench/cli.py synthbench/AGENTS.md \
  docs/synthbench/command-reference.md backend/tests/unit/synthbench/AGENTS.md \
  backend/tests/unit/synthbench/test_replay.py
SKIP=semgrep uvx pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(synthbench): replay, served VLMs over the export

Imports the export into the eval store, checks the endpoint, the renderer
and the served model, runs the shipped vlm_replay.run_replay and records
runs/replays/<replay_id>/run.json. Every model goes through the shipped
VlmClient with the export as its capture root; vLLM models run it with the
/props probe off and a transport that names the served model. Synthbench
P5a, spec section 3.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `score`, metrics and the report

> **Built during planning: commit `4b653251`** (after the merge with main). Execution runs the
> task review on `4b653251^..4b653251` and implements nothing unless the review finds a defect;
> the steps below are the brief the reviewer checks the commit against.

Join replay rows, the eval store's labels, the export's facts and the audit into metrics and a
report (spec §5), per plan rulings P5a-R11 to P5a-R14.

**Files:**

- Create: `synthbench/score/__init__.py`, `synthbench/score/metrics.py`,
  `synthbench/score/report.py`, `synthbench/score/scoring.py`, `synthbench/score/AGENTS.md`
- Create: `synthbench/commands/score.py`
- Modify: `synthbench/cli.py` (import and register `score`, after `replay`)
- Modify: `docs/synthbench/command-reference.md` (a `score` section after `replay`)
- Modify: `synthbench/AGENTS.md` (a `score/` layout row after `run/`)
- Modify: `backend/tests/unit/synthbench/AGENTS.md` (a `test_score.py` row)
- Test: `backend/tests/unit/synthbench/test_score.py`

**Interfaces:**

- Consumes: Task 5's `run.json` keys (`replay_id`, `model`, `served_id`, `transport`, `url`,
  `build`, `commit`, `eval_run_id`, `store`, `export`, `started_utc`, `limit`); Task 3's
  `read_sets`, `ExportedSet` (`item_id`, `facts`, `still`, `labels`), `vss.CATEGORY`,
  `vss.CATEGORY_LABEL`; Task 4's `load_answers(log)`, `sample(sets)` and
  `synthbench.commands.audit.audit_log(version, env)`; `backend.evaluation.s_metrics`
  (`s2_false_positive_rate`, `s3_recall`, `s5_refusals`, `uncertain_rate`, `wilson_interval`);
  `backend.evaluation.levels` (`score_to_level`, `level_at_or_above`,
  `floor_for_expected_score`); `EvalStore.iter_items(with_media_only=True)`,
  `EvalStore.replay(run_id)` (rows: `item_id`, `verdict`, `risk_score`, `raw_response`);
  `backend.evaluation.vlm_replay.git_commit()`.
- Produces (used by Task 7):

  - `python -m synthbench score --replay <id> [--replay <id> ...]`;
  - `$SYNTHBENCH_ROOT/runs/scores/<YYYYmmddTHHMMSSZ>/` holding `results.jsonl`, `metrics.json`
    (`identity`, `audit`, `models`, `comparison`), `report.md` (aggregate only) and
    `report.html`;
  - `metrics.json`'s `models.<name>.all` and `.audited`, each with `s2`, `s3`, `s5`, `verdicts`
    (the `s_metrics` dicts), `s2_cell`, `s3_cell`, `s3_excluding_zero_floor_cell`,
    `refusal_cell`, `uncertain_cell` and `band`; a cell is `{k, n, rate, wilson_95,
insufficient}`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/synthbench/test_score.py`:

```python
"""`score` (P5a design §5): S2 and S3 from `s_metrics`, slices, the risk band, the audit's
exclusions and truth error, the comparison, the report and the command."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from synthbench import cli
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


def _world(root: Path, scores: dict[str, dict[str, int | None]]) -> list[str]:
    """An export of three threats and twelve benign scenes, imported; one replay per model."""
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
            }
            run_dir = root / "runs" / "replays" / replay_id
            run_dir.mkdir(parents=True)
            (run_dir / "run.json").write_text(json.dumps(record))
            ids.append(replay_id)
    return ids


def test_score_writes_results_metrics_and_both_reports(tmp_path: Path) -> None:
    ids = _world(tmp_path, {"qwen3-vl-8b": {"B-t-000": 20}, "flagship": {"B-b-000": 70}})
    argv = [a for replay_id in ids for a in ("--replay", replay_id)]
    assert h.run(tmp_path, "score", *argv) == cli.EXIT_OK
    [out] = (tmp_path / "runs" / "scores").iterdir()
    results = [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines()]
    assert len(results) == 2 * 15
    metrics = json.loads((out / "metrics.json").read_text())
    assert metrics["models"]["qwen3-vl-8b"]["all"]["s3"]["all"]["miss"] == 1
    assert metrics["identity"]["replays"][0]["build"] == "b7972"
    assert "qwen3-vl-8b" in (out / "report.md").read_text()
    html = (out / "report.html").read_text()
    sources = re.findall(r'<img src="([^"]+)"', html)
    assert len(sources) == 2  # the one miss and the one false alarm
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
```

What each guards, by the production change that would make it fail:

| Test                                                                  | Fails if                                                                        |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `test_s2_and_s3_are_s_metrics_own_output_and_outcomes_agree`          | S2/S3 are recomputed, or `outcome` drifts from `s_metrics`' rule                |
| `test_a_slice_counts_only_its_items_and_a_small_one_is_insufficient`  | the insufficient threshold or a slice's grouping changes                        |
| `test_the_risk_band_position_and_distance`                            | the band position or distance is wrong                                          |
| `test_a_scene_answered_no_is_a_generation_error_and_leaves_s2_and_s3` | a scene-no event is scored, or the audited headline is not the confirmed subset |
| `test_truth_error_counts_no_over_answered_and_unclear_apart`          | `u` answers enter the error rate's denominator                                  |
| `test_the_comparison_lists_the_misses_one_model_catches`              | the two directions are swapped                                                  |
| `test_the_markdown_is_aggregate_with_n_intervals_and_insufficient`    | the report names an item, or loses n or the interval                            |
| `test_score_writes_results_metrics_and_both_reports`                  | an output is missing, the gallery filter changes, or a still link is absolute   |
| `test_score_refuses_an_unknown_replay_and_a_model_twice`              | either request is accepted                                                      |
| `test_score_stops_when_rows_name_items_the_export_lacks`              | the check is skipped (a `KeyError` would also exit 2: the message is asserted)  |
| `test_weights_identity_reads_what_each_transport_left`                | the weights identity reads the wrong file                                       |

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest backend/tests/unit/synthbench/test_score.py -q -n0`
Expected: collection fails with `ModuleNotFoundError: No module named 'synthbench.score'`.

- [ ] **Step 3: The metrics**

Create `synthbench/score/__init__.py`:

```python
"""Scores replays of the exported items: metrics and the report (synthbench P5a design §5)."""
```

Create `synthbench/score/metrics.py`:

```python
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
```

- [ ] **Step 4: The report**

Create `synthbench/score/report.py`:

```python
"""`report.md` (aggregate only: Task 7 commits it) and `report.html` (the failure gallery)."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path
from typing import Any

CONDITIONS = (
    "**Conditions.** The truth is declared by the sampler and unverified; the owner's audit below "
    "gives its error rate. Stills only: the VLM gets no detector or specialist context, which is "
    "harder than production. Accuracy only: the GB300 is shared, so no latency or memory figure "
    "here stands for a deployment. Ambiguous events are not scored."
)
CELLS = (
    'Each cell reads rate [95% Wilson interval] (n); under n = 10 it reads "insufficient". '
    "S2 is benign scenes scored medium or above; S3 is incidents scored at or above their level."
)


def fmt(cell: Mapping[str, Any] | None) -> str:
    """One metric cell as text."""
    if cell is None:
        return "—"
    if cell["insufficient"]:
        return f"insufficient (n={cell['n']})"
    lo, hi = cell["wilson_95"]
    return f"{cell['rate']:.1%} [{lo * 100:.1f}-{hi * 100:.1f}] (n={cell['n']})"


def _table(header: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    lines += ["| " + " | ".join(str(value) for value in row) + " |" for row in rows]
    return lines


def _headline(models: Mapping[str, Any], key: str) -> list[str]:
    rows = [
        [
            model,
            m[key]["n"],
            fmt(m[key]["s2_cell"]),
            fmt(m[key]["s3_cell"]),
            fmt(m[key]["s3_excluding_zero_floor_cell"]),
            fmt(m[key]["refusal_cell"]),
            fmt(m[key]["uncertain_cell"]),
        ]
        for model, m in models.items()
    ]
    header = ("Model", "Items", "S2", "S3", "S3, low floor excluded", "Refusals", "Uncertain")
    return _table(header, rows)


def _identity(identity: Mapping[str, Any]) -> list[str]:
    export, audit = identity.get("export", {}), identity.get("audit", {})
    lines = [
        f"- Scored at commit `{identity.get('commit', '?')}`, scoring version "
        f"{identity.get('score_version', '?')}, {identity.get('created_utc', '?')}.",
        f"- Corpus {', '.join(identity.get('corpus_version', [])) or '?'}; export "
        f"`{export.get('path', '?')}`: {export.get('items', '?')} sets, labels sha256 "
        f"`{export.get('labels_sha256', '?')}`.",
        f"- Audit log `{audit.get('path', '?')}`, sha256 `{audit.get('sha256') or 'none yet'}`.",
        "- vLLM models: the image is pinned by digest in the operator runbook's start command; "
        "no endpoint reports it.",
        "",
    ]
    header = ("Model", "Replay", "Transport", "Endpoint", "Build", "Weights", "Replay commit")
    rows = [
        [
            r.get("model"),
            f"`{r.get('replay_id')}`",
            r.get("transport"),
            r.get("url"),
            r.get("build") or "—",
            r.get("weights"),
            f"`{r.get('commit')}`",
        ]
        for r in identity.get("replays", [])
    ]
    return lines + _table(header, rows)


def _audit(audit: Mapping[str, Any]) -> list[str]:
    lines = [f"{audit['answered']} of {audit['sampled']} sampled stills have a scene answer.", ""]
    rows = [
        [key, q["answered"], q["yes"], q["no"], q["unclear"], fmt(q["error"])]
        for key, q in audit["questions"].items()
    ]
    lines += _table(("Question", "Answered", "Yes", "No", "Unclear", "Truth error"), rows)
    errors = len(audit["generation_errors"])
    lines += [
        "",
        f"{errors} event(s) whose scene the owner answered no are generation errors: they are "
        "excluded from every metric, never counted as model errors.",
    ]
    return lines


def _band(models: Mapping[str, Any]) -> list[str]:
    rows = []
    for model, m in models.items():
        for label, b in m["all"]["band"].items():
            below, above = b["mean_distance_below"], b["mean_distance_above"]
            rows.append(
                [
                    model,
                    label,
                    b["n"],
                    fmt(b["inside"]),
                    fmt(b["below"]),
                    fmt(b["above"]),
                    "—" if below is None else below,
                    "—" if above is None else above,
                ]
            )
    header = ("Model", "Label", "Scored", "Inside", "Below", "Above", "Mean below", "Mean above")
    return _table(header, rows)


def _verdicts(models: Mapping[str, Any]) -> list[str]:
    rows = []
    for model, m in models.items():
        mix = m["all"]["verdicts"]["verdict_mix"]
        s5 = m["all"]["s5"]
        rows.append(
            [
                model,
                ", ".join(f"{verdict} {count}" for verdict, count in mix.items()) or "—",
                s5["unparseable"],
                s5["unavailable"],
                s5["unclassifiable"],
            ]
        )
    return _table(("Model", "Verdicts", "Unparseable", "Unavailable", "No cause"), rows)


def _slices(models: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for model, m in models.items():
        lines += ["", f"### {model}"]
        for name, values in m["slices"].items():
            rows = [[value, fmt(c["s2"]), fmt(c["s3"])] for value, c in values.items()]
            lines += ["", f"**{name}**", "", *_table((name, "S2", "S3"), rows)]
    return lines


def _comparison(pairs: Sequence[Mapping[str, Any]]) -> list[str]:
    if not pairs:
        return ["One model scored: nothing to compare."]
    rows = [
        [
            f"{p['a']} / {p['b']}",
            p["agree"]["n"],
            fmt(p["agree"]),
            len(p["a_wrong_b_right"]),
            len(p["b_wrong_a_right"]),
        ]
        for p in pairs
    ]
    header = (
        "Models",
        "Common items",
        "Agreement",
        "Only the first wrong",
        "Only the second wrong",
    )
    return _table(header, rows)


def markdown(metrics: Mapping[str, Any], identity: Mapping[str, Any]) -> str:
    """The aggregate report: rates, n and intervals, never a per-item row."""
    models = metrics["models"]
    lines = [
        f"# Synthbench P5a scores: {identity.get('score_id', '?')}",
        "",
        CONDITIONS,
        "",
        CELLS,
        "",
        "## Run identity",
        "",
        *_identity(identity),
        "",
        "## Headline: every scored item",
        "",
        *_headline(models, "all"),
        "",
        "## Headline: audited stills whose scene the owner confirmed",
        "",
        *_headline(models, "audited"),
        "",
        "## Audit",
        "",
        *_audit(metrics["audit"]),
        "",
        "## Risk band",
        "",
        *_band(models),
        "",
        "## Verdicts and refusals",
        "",
        *_verdicts(models),
        "",
        "## Slices",
        *_slices(models),
        "",
        "## Comparison",
        "",
        *_comparison(metrics["comparison"]),
    ]
    return "\n".join(lines) + "\n"


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font: 14px system-ui, sans-serif; margin: 16px; background: #111; color: #ddd; }}
main {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 12px; }}
figure {{ margin: 0; background: #1c1c1c; padding: 8px; border-left: 4px solid #c33; }}
img {{ width: 100%; height: auto; }}
</style></head><body><h1>{title}</h1><p>{conditions}</p>
{sections}
</body></html>
"""
_GALLERIES = (
    ("miss", "Incidents scored below their level"),
    ("false_alarm", "Benign scenes scored medium or above"),
)


def _card(row: Mapping[str, Any], out_dir: Path) -> str:
    source = os.path.relpath(row["still"], out_dir)
    cell = row["cell"]
    lo, hi = row["band"]
    caption = (
        f"<b>{escape(row['event_id'])}</b> {escape(cell['scenario'])}, {escape(cell['lighting'])}, "
        f"{escape(cell['weather'])}; band {lo}-{hi}, level {escape(row['floor'])}; scored "
        f"{row['risk_score']} ({escape(row['verdict'])})<br>{escape(row['reasoning'] or '')}"
    )
    return (
        f'<figure><img src="{escape(source)}" loading="lazy" alt="{escape(row["event_id"])}">'
        f"<figcaption>{caption}</figcaption></figure>"
    )


def html(identity: Mapping[str, Any], results: Sequence[Mapping[str, Any]], out_dir: Path) -> str:
    """The failure gallery, per model: each still with its facts and the VLM's reasoning."""
    sections: list[str] = []
    for model in dict.fromkeys(row["model"] for row in results):
        for wanted, heading in _GALLERIES:
            cards = [
                _card(row, out_dir)
                for row in results
                if row["model"] == model and row["outcome"] == wanted and not row["excluded"]
            ]
            sections.append(
                f"<h2>{escape(model)}: {escape(heading)} ({len(cards)})</h2>"
                f"<main>{''.join(cards)}</main>"
            )
    title = escape(f"Synthbench P5a failures: {identity.get('score_id', '?')}")
    conditions = escape(CONDITIONS.replace("**", ""))
    return _HTML.format(title=title, conditions=conditions, sections="\n".join(sections))
```

The interval uses a hyphen: ruff's RUF001 refuses an en dash in a string.

- [ ] **Step 5: Loading, identity and the outputs**

Create `synthbench/score/scoring.py`:

```python
"""`score`: load replays, their eval store, the export and the audit; write the outputs.

Writes `$SYNTHBENCH_ROOT/runs/scores/<score_id>/`: `results.jsonl` (one row per item per model),
`metrics.json` (the metrics and the run identity), `report.md` and `report.html` (P5a design §5).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.evaluation.eval_store import EvalStore
from backend.evaluation.levels import floor_for_expected_score
from backend.evaluation.vlm_replay import git_commit

from synthbench.audit.page import load_answers
from synthbench.audit.sample import sample as audit_sample
from synthbench.export.vss import ExportedSet, read_sets
from synthbench.score import report
from synthbench.score.metrics import Item, result_rows, score_models

SCORE_VERSION = 1
_REPLAY_KEYS = (
    "replay_id",
    "model",
    "served_id",
    "transport",
    "url",
    "build",
    "commit",
    "eval_run_id",
    "started_utc",
    "limit",
)


class ScoreRequestError(Exception):
    """The request names replays that cannot be scored together."""


class ScoreRefused(Exception):
    """A replay, its eval store and the export disagree: stop and ask the owner."""


@dataclass(frozen=True)
class Replay:
    """A replay's `run.json`."""

    record: Mapping[str, Any]

    @property
    def replay_id(self) -> str:
        return str(self.record["replay_id"])

    @property
    def model(self) -> str:
        return str(self.record["model"])

    @property
    def store(self) -> Path:
        return Path(self.record["store"])

    @property
    def export(self) -> Path:
        return Path(self.record["export"])


@dataclass(frozen=True)
class ScoreResult:
    score_id: str
    out_dir: Path
    metrics: dict[str, Any]


def load_replay(replays_dir: Path, replay_id: str) -> Replay:
    path = replays_dir / replay_id / "run.json"
    if not path.is_file():
        raise ScoreRequestError(f"no replay {replay_id!r} under {replays_dir}")
    try:
        return Replay(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise ScoreRefused(f"{path} does not read: {error}") from error


def load_items(store: EvalStore, sets: Sequence[ExportedSet]) -> dict[str, Item]:
    """Every item in both the store and the export: label and floor from the store (the label
    authority, as `vlm_replay` derives them), facts and still from the export."""
    by_id = {exported.item_id: exported for exported in sets}
    items: dict[str, Item] = {}
    for item in store.iter_items(with_media_only=True):
        exported = by_id.get(item.item_id)
        if exported is not None:
            items[item.item_id] = Item(
                item_id=item.item_id,
                label=item.expected_label,
                floor=floor_for_expected_score(item.expected_risk_score),
                facts=exported.facts,
                still=exported.still,
            )
    return items


def weights_identity(transport: str, served_id: str, env: Mapping[str, str]) -> str:
    """What the host recorded about a model's weights: for `ai-vlm`, the model file's line in
    the `SHA256SUMS` the weights copy wrote; for vLLM, the Hugging Face snapshot revision."""
    if transport == "ai-vlm":
        sums = Path(env.get("AI_MODELS_PATH", "/export/models/ai_models")) / "vlm" / "SHA256SUMS"
        try:
            lines = sums.read_text(encoding="utf-8").splitlines()
        except OSError:
            return "unrecorded"
        for line in lines:
            digest, _, name = line.partition(" ")
            if name.strip().lstrip("*") == f"{served_id}.gguf":
                return f"sha256:{digest}"
        return "unrecorded"
    repo = "models--" + served_id.replace("/", "--")
    ref = Path(env.get("HF_HOME", "/export/models")) / "hub" / repo / "refs" / "main"
    try:
        return f"revision:{ref.read_text(encoding='utf-8').strip()}"
    except OSError:
        return "unrecorded"


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _labels_digest(sets: Sequence[ExportedSet]) -> str:
    """One digest over every set's labels (which carry each still's sha256)."""
    digest = hashlib.sha256()
    for exported in sorted(sets, key=lambda s: s.item_id):
        digest.update(exported.item_id.encode())
        digest.update(json.dumps(exported.labels, sort_keys=True).encode())
    return digest.hexdigest()


def _one(values: set[Path], what: str) -> Path:
    if len(values) != 1:
        shown = ", ".join(sorted(str(v) for v in values))
        raise ScoreRequestError(f"the replays name different {what}s ({shown}): score them apart")
    return next(iter(values))


def execute(
    replay_ids: Sequence[str],
    replays_dir: Path,
    scores_dir: Path,
    audit_log: Path,
    env: Mapping[str, str],
    now: datetime,
) -> ScoreResult:
    """Score the named replays together and write the outputs under `scores_dir/<score_id>/`."""
    replays = [load_replay(replays_dir, replay_id) for replay_id in replay_ids]
    models = [replay.model for replay in replays]
    if len(set(models)) != len(models):
        raise ScoreRequestError(f"one replay per model: {', '.join(sorted(models))}")
    store_path = _one({replay.store for replay in replays}, "eval store")
    export = _one({replay.export for replay in replays}, "export")
    if not store_path.is_file():
        raise ScoreRefused(f"the eval store {store_path} is missing")
    sets = read_sets(export)
    with EvalStore(store_path) as store:
        items = load_items(store, sets)
        loaded = [
            (replay.model, replay.replay_id, store.replay(str(replay.record["eval_run_id"])))
            for replay in replays
        ]
    for model, _, rows in loaded:
        if not rows:
            raise ScoreRefused(f"{model}'s replay has no results in {store_path}")
        missing = sorted({row["item_id"] for row in rows} - items.keys())
        if missing:
            raise ScoreRefused(
                f"{model}'s replay scored {len(missing)} item(s) the export at {export} does not "
                f"hold, first {missing[0]}"
            )
    answers = load_answers(audit_log)
    sampled = [str(exported.facts["event_id"]) for exported in audit_sample(sets)]
    metrics = score_models(loaded, items, answers, sampled)
    score_id = f"{now:%Y%m%dT%H%M%SZ}"
    identity = {
        "score_id": score_id,
        "score_version": SCORE_VERSION,
        "commit": git_commit(),
        "created_utc": now.isoformat(timespec="seconds"),
        "corpus_version": sorted(
            {str(item.facts.get("corpus_version")) for item in items.values()}
        ),
        "export": {"path": str(export), "items": len(sets), "labels_sha256": _labels_digest(sets)},
        "audit": {"path": str(audit_log), "sha256": _sha256(audit_log)},
        "replays": [
            {key: replay.record.get(key) for key in _REPLAY_KEYS}
            | {
                "weights": weights_identity(
                    str(replay.record.get("transport", "")),
                    str(replay.record.get("served_id", "")),
                    env,
                )
            }
            for replay in replays
        ],
    }
    results = result_rows(loaded, items, answers, set(metrics["audit"]["generation_errors"]))
    out_dir = scores_dir / score_id
    out_dir.mkdir(parents=True)
    (out_dir / "results.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in results), encoding="utf-8"
    )
    document = {"identity": identity, **metrics}
    (out_dir / "metrics.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "report.md").write_text(report.markdown(metrics, identity), encoding="utf-8")
    (out_dir / "report.html").write_text(report.html(identity, results, out_dir), encoding="utf-8")
    return ScoreResult(score_id, out_dir, document)
```

- [ ] **Step 6: The command**

Create `synthbench/commands/score.py`:

```python
"""`score --replay <id>...`: metrics and the report for one or more replays (P5a design §5).

An owner command. The backend half (`synthbench.score`) is imported inside `run()`: `cli.py`
imports every command at startup, and the generation agent's commands must not load `backend`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from synthbench.commands.audit import audit_log
from synthbench.commands.common import EXIT_OK, AskOwner, Parser, RequestError, taxonomy
from synthbench.contract.store import DEFAULT_SYNTHBENCH_ROOT


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "score",
        help="score one or more replays: metrics and the report (owner)",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--replay",
        action="append",
        required=True,
        metavar="ID",
        help="a replay id under runs/replays/; repeat it to compare models",
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    from synthbench.score.report import fmt
    from synthbench.score.scoring import ScoreRefused, ScoreRequestError, execute

    tax = taxonomy()
    root = Path(env.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
    try:
        result = execute(
            args.replay,
            root / "runs" / "replays",
            root / "runs" / "scores",
            audit_log(tax.version, env),
            env,
            datetime.now(UTC),
        )
    except ScoreRequestError as error:
        raise RequestError(str(error)) from error
    except ScoreRefused as error:
        raise AskOwner(f"{error}.") from error
    audit = result.metrics["audit"]
    lines = [
        f"score {result.score_id}: audit {audit['answered']}/{audit['sampled']} stills answered, "
        f"{len(audit['generation_errors'])} generation error(s) excluded"
    ]
    for model, metrics in result.metrics["models"].items():
        headline = metrics["all"]
        lines.append(
            f"  {model}: S2 {fmt(headline['s2_cell'])}; S3 {fmt(headline['s3_cell'])}; "
            f"{headline['s5']['refusals']} refused"
        )
    lines.append(f"  {result.out_dir / 'report.md'}")
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_OK
```

In `synthbench/cli.py`, add `score` to the `from synthbench.commands import (...)` list (between
`sample` and `triage`) and to `COMMANDS` after `replay`.

- [ ] **Step 7: Run the tests, then check that they bite**

Run: `uv run pytest backend/tests/unit/synthbench/test_score.py -q -n0 -p randomly`
Expected: 11 passed.

Then break each rule below by hand, one at a time, run the file, and restore it. Each run must
fail: removing the scene-no exclusion in `score_models`; raising the benign alarm level in
`outcome` to `high`; `insufficient` at `n < 3`; the below-band distance's sign; swapping the
comparison's two lists; `u` answers in the error denominator; `audited = kept`; an absolute still
path in `_card`; dropping the gallery's `excluded` filter; skipping the missing-items check in
`execute`; accepting a model twice.

- [ ] **Step 8: Document the command**

In `docs/synthbench/command-reference.md`, insert after the `replay` section:

```markdown
## `score`

Owner only. Scores one or more replays together, for P5a
(`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §5): S2 and S3 through
`backend/evaluation/s_metrics.py`, refusals, the verdict mix, the risk band, slices, the audit's
truth error, and, with two or more replays, the comparison between models.

| Option          | Default  | Meaning                                                        |
| --------------- | -------- | -------------------------------------------------------------- |
| `--replay <id>` | required | a replay id under `runs/replays/`; repeat it to compare models |

- **Reads:** each replay's `run.json`, its results in the eval store, the export it names, and
  `$SYNTHBENCH_ROOT/audits/<version>/audit.jsonl` if it exists. Labels and S3 floors come from the
  eval store; facts and stills from the export.
- **Audit:** an event whose scene the owner answered no is a generation error: it leaves every
  metric. The headline is reported twice: on every scored item, and on the audited stills whose
  scene the owner confirmed.
- **Writes:** `$SYNTHBENCH_ROOT/runs/scores/<score_id>/`: `results.jsonl` (one row per item per
  model), `metrics.json` (with the run identity: commits, builds, weights, export and audit
  digests), `report.md` (aggregate only, for committing) and `report.html` (the failure gallery:
  incidents scored below their level and benign scenes scored medium or above, with the VLM's
  reasoning).
- **Cells:** rate, 95% Wilson interval and n; under n = 10 a cell reads "insufficient".
- **Prints:** the audit's progress, each model's S2, S3 and refusals, and the path of `report.md`.
- **Exit 1:** a replay id is unknown, two replays are of the same model, or the replays name
  different eval stores or exports.
- **Exit 2:** a replay's `run.json` does not read, its eval store is missing or holds none of its
  results, or it scored items the export does not hold.
```

Create `synthbench/score/AGENTS.md`:

```markdown
# synthbench/score — Agent Guide

## Purpose

Scores replays of the exported items (synthbench P5a,
`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §5). With
`synthbench/run/`, the only synthbench package that may import `backend` (spec §7.1;
`backend/tests/unit/synthbench/test_import_rule.py`).

## Files

| File         | What                                                                                                        |
| ------------ | ----------------------------------------------------------------------------------------------------------- |
| `metrics.py` | pure: `Item`, `cell`, `outcome`, `band_position`, headline, slices, the audit summary, the comparison, rows |
| `report.py`  | `markdown` (aggregate only, committed by the scored run) and `html` (the failure gallery)                   |
| `scoring.py` | `execute`: loads the replays, their eval store, the export and the audit; writes the four outputs           |

The command is `synthbench/commands/score.py` (`python -m synthbench score`); it imports this
package inside `run()`.

## Rules

- S2 and S3 come only from `backend/evaluation/s_metrics.py`. `outcome` restates their per-row
  rule for slices, the gallery and the comparison; a test holds the two equal.
- Labels and S3 floors come from the eval store, as `vlm_replay` derives them; facts and stills
  come from the export.
- `report.md` never names an item: it is committed. Per-item content lives in `results.jsonl`
  and `report.html`, under `$SYNTHBENCH_ROOT/runs/scores/`.
- Every rate is a `cell`: k, n, rate and the 95% Wilson interval, insufficient under n = 10.
```

In `synthbench/AGENTS.md`, add after the `run/` row:

```markdown
| `score/` | `score`: metrics and the report over replays, S2 and S3 from `s_metrics`; imports `backend` (P5a) |
```

In `backend/tests/unit/synthbench/AGENTS.md`, add after the `test_replay.py` row:

```markdown
| `test_score.py` | `python -m synthbench score`: s_metrics parity, slices, the audit, the report, refusals |
```

- [ ] **Step 9: Run the affected suites and mypy**

Run: `uv run pytest backend/tests/unit/synthbench/ backend/tests/unit/evaluation/ backend/tests/unit/services/test_vlm_client.py -q -n auto -p randomly --deselect backend/tests/unit/evaluation/test_build_gen2.py`
Expected: all pass.
Run: `uv run mypy synthbench/ backend/tests/unit/synthbench/`
Expected: no issues.

- [ ] **Step 10: Commit**

```bash
git add synthbench/score/ synthbench/commands/score.py synthbench/cli.py synthbench/AGENTS.md \
  docs/synthbench/command-reference.md backend/tests/unit/synthbench/AGENTS.md \
  backend/tests/unit/synthbench/test_score.py
SKIP=semgrep uvx pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(synthbench): score, metrics and the report over replays

S2 and S3 from s_metrics, with n and Wilson intervals; refusals, verdicts,
the risk band, slices, the audit's truth error and exclusions, and the
comparison between models. Writes runs/scores/<score_id>/: results.jsonl,
metrics.json, report.md (aggregate) and report.html (the failure gallery).
Synthbench P5a, spec section 5.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The full scored run (owner-gated)

Live work on the GB300, run by the controller with the owner: the owner audits, and approves the
flagship replay's timing. It changes no Python. It ends with P5a's acceptance (spec §7).

**Files:**

- Modify: `docs/synthbench/operator-runbook.md` (a "Score the models (P5a)" section after Task
  1's serving section)
- Create: `docs/benchmarks/synthbench/p5a-<YYYY-MM-DD>.md` (the aggregate report and the
  acceptance record)

**Interfaces:**

- Consumes: Task 1's `.env.bench`, weights (`/export/models/ai_models/vlm/` and its
  `SHA256SUMS`), images and runbook serving section; the commands `export vss`, `audit`, `replay`
  and `score` (Tasks 3–6).
- Produces: replays under `$SYNTHBENCH_ROOT/runs/replays/`, one score under
  `$SYNTHBENCH_ROOT/runs/scores/`, the committed aggregate report.

**Prerequisites:** Tasks 1–6 are complete and reviewed; the renderer is stopped; the guard is
active; the flagship answers `200` on `127.0.0.1:8000/health`.

- [ ] **Step 1: Record the starting state**

```bash
date '+%F %T' | tee /tmp/p5a-start
docker inspect -f '{{.State.StartedAt}} restarts={{.RestartCount}}' dgx-inference-vllm-1 | tee /tmp/p5a-flagship
systemctl --user is-active synthbench-renderer synthbench-guard
curl -s -o /dev/null -w 'flagship %{http_code}\n' 127.0.0.1:8000/health
nvidia-smi --query-gpu=memory.free --format=csv
uv run python -m synthbench export vss
```

Expected: `inactive`, `active`, `flagship 200`, about 64 GB free; the export writes nothing new
(`450` unchanged) unless the corpus grew since Task 1, in which case record the new counts.

- [ ] **Step 2: The owner audits 60 stills (owner)**

The owner runs `uv run python -m synthbench audit` (from another machine:
`ssh -L 8765:127.0.0.1:8765 <this host>`, then `http://127.0.0.1:8765/`) and answers every
question on every still, about 20 minutes. The page says when all 60 are answered. The
controller waits for the owner's word; nothing else in this task needs the owner until Step 5.

- [ ] **Step 3: The product model over every item**

Serve `qwen3-vl-8b` as the runbook's serving section says, then:

```bash
time uv run python -m synthbench replay --model qwen3-vl-8b
```

Expected: `450 items`, the printed S2, S3 and refusals, and a `run.json` path. Record the replay
id. Refusals above 5% stop the task: read their classes (`s5.by_error_class` in `run.json`) and
bring them to the owner before going on.

- [ ] **Step 4: Cosmos-Reason2-8B over every item**

Stop `ai-vlm`, start `synthbench-cosmos` as the runbook says, then:

```bash
time uv run python -m synthbench replay --model cosmos-reason2-8b
```

Remove the container afterwards (`$P rm -f synthbench-cosmos`). Record the replay id.

- [ ] **Step 5: The flagship over every item (owner picks the time)**

The flagship is shared with the agents. Ask the owner for a quiet period, then:

```bash
time uv run python -m synthbench replay --model flagship
```

Record the replay id. If the owner declines the flagship run, record that; Cosmos alone meets
acceptance item 4. `qwen3-vl-4b` and `nemotron-12b-vl` run only if the owner asks for them.

- [ ] **Step 6: Score**

```bash
uv run python -m synthbench score --replay <qwen3-vl-8b id> --replay <cosmos id> [--replay <flagship id>]
```

Expected: the audit line reads `60/60`; one line per model; the path of `report.md`. Open
`report.html` with the owner (it links stills inside `/synthbench`, so serve that tree:
`cd /synthbench && python3 -m http.server 8766 --bind 127.0.0.1`, then
`runs/scores/<score_id>/report.html`).

- [ ] **Step 7: Check the flagship stayed healthy throughout**

```bash
journalctl --user -u synthbench-renderer -u synthbench-guard --since "$(cat /tmp/p5a-start)" --no-pager
docker inspect -f '{{.State.StartedAt}} restarts={{.RestartCount}}' dgx-inference-vllm-1 | diff - /tmp/p5a-flagship && echo "flagship: never restarted"
curl -s -o /dev/null -w 'flagship %{http_code}\n' 127.0.0.1:8000/health
```

Expected: `-- No entries --` (the renderer stayed stopped; the guard logs only a stop that
failed), `flagship: never restarted` and `flagship 200`.

- [ ] **Step 8: The runbook section and the committed report**

Add `## Score the models (P5a)` to `docs/synthbench/operator-runbook.md`, after the serving
section: Steps 1–7 of this task as the owner would repeat them, with the commands that worked.

Create `docs/benchmarks/synthbench/p5a-<YYYY-MM-DD>.md`: a header naming the score directory
(`/synthbench/runs/scores/<score_id>/`), then `report.md` verbatim, then an acceptance record
with one line per item of spec §7's acceptance list, each with its evidence:

1. exported and imported: the export's counts and the skips it listed (Step 1, Task 1 Step 6);
2. the product model covered every item, with S2, S3 and refusals reported with n and intervals;
3. the owner audited 60 stills, and the report carries the truth error and both headlines;
4. the comparison model(s) that replayed the same items;
5. this file committed, and the run's directories under `/synthbench/runs/`;
6. the flagship stayed healthy: Step 7's output.

- [ ] **Step 9: Commit**

```bash
git add docs/synthbench/operator-runbook.md docs/benchmarks/synthbench/p5a-*.md
SKIP=semgrep uvx pre-commit run --files $(git diff --cached --name-only)
git commit -m "docs(synthbench): P5a scored run - the product VLM and comparisons on tierb-v0

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
