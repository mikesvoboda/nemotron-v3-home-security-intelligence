# P2: Executor, front and status

> **Task level. Expand before execution:** when P1 has merged, run superpowers:writing-plans on this file against the then-current tree to produce the step-level plan (failing test, implementation, passing test, commit for each task). The files, interfaces, tests and acceptance criteria below are the expansion's requirements. Index: [`README.md`](README.md).

**Goal:** Recipes submitted as commits are executed reproducibly by a host daemon, scored by a scorer that alone holds the labels, and ranked onto a Pareto front per GPU tier that `autovlm status` reports.

**Spec:** design [`01`](../../auto-vlm-research/01-architecture.md) §3.2–3.7 and §6–7; [`02`](../../auto-vlm-research/02-evaluation.md) §5–6.

**Prerequisites:** P1 merged; P0's S1 (labels can stay on this host, or the decision to move them), S4 (port denies) and S6 (endpoint budget) recorded.

---

### Task 1: Content-addressed cache

**Files:** create `autovlm/cache.py`; modify `autovlm/evaluate.py` (`run_items` takes an optional cache); test `backend/tests/unit/autovlm/test_cache.py`.

**Interfaces:**

- `cache_key(stage: str, stage_hash: str, input_sha256: str, build: str) -> str` (hex sha256 over the four parts)
- `Cache(root: Path)` with `get(key) -> dict | None` and `put(key, payload: dict) -> None`; writes go to a temporary file in the same directory and land by `os.replace`; `CacheConflict` when a key already holds a different payload
- Detector entries keyed per frame (input = the frame's sha256); VLM entries keyed per item (input = sha256 over the selected frames' sha256s and the canonical JSON of its detections)

**Tests:** a round trip; each of the four key parts changes the key; a conflicting put raises; two threads putting the same payload both succeed; running `evaluate` twice over one cache makes zero detector or VLM calls the second time (spies) and yields identical `readings.json`.

**Acceptance:** re-scoring a recipe that changed only `decision` performs no GPU work.

---

### Task 2: Run ledger and `autovlm init`

**Files:** create `autovlm/ledger.py`, `autovlm/commands/init.py`; test `backend/tests/unit/autovlm/test_ledger.py`.

**`autovlm init --tag-suffix <s> --baseline <recipe> --blinded <dir> --split <manifest>`** creates the run directory (`runs/<UTC timestamp>-<suffix>/`) with an immutable `config.json` (worker width, select-query budgets per cost class, the stall rule's N and H, the OD-26 margins, the seed), appends the `baseline` row, and queues the baseline recipe as trial 0. A test checks that a second `init` with the same tag is refused and that `config.json` is never rewritten.

**Interfaces:**

- Row kinds as a pydantic discriminated union: `baseline`, `brief` (`brief_id`, `parent_commits`, `kind`, `description`, `epoch`), `brief_start`, `brief_continue`, `trial` (`brief_id`, `trial`, `commit`, `status`, `recipe_hash`, `trial_id`), `brief_stop`, `retroactive` (`brief_id`, `trial`, `status` in `reward_hacking`/`invalid`, `reason`), `epoch`, `front_change`
- `RunLedger(path)` with `append(row)` under `fcntl.flock` and `rows(kind=None)`

**Rules the ledger enforces (one test each):** brief ids are sequential from 0; a trial row needs an open brief; `brief_start` after a `brief_stop` needs a pending `brief_continue` (autocuda's continuation rule); a `retroactive` row must name an existing measured trial, keeps that trial's original row, and an identical retry is a no-op while a conflicting one is refused.

**Acceptance:** a ledger rebuilt from disk after a crash gives the same `rows()` as before it.

---

### Task 3: The Pareto front per tier

**Files:** create `autovlm/front.py`; test `backend/tests/unit/autovlm/test_front.py`.

**Interfaces:**

- `BUDGETS_GIB = {"10GB": 8.5, "12GB": 10.2, "16GB": 13.6, "24GB": 20.4, "32GB": 27.2, "48GB": 40.8, "unbounded": inf}`
- `estimate_stack_gib(weights_bytes, mmproj_bytes, kv_bytes, overhead_gib) -> float`; `bucket_for(gib) -> str` (the smallest bucket that fits)
- `FrontMember(trial_id, recipe_hash, own_bucket, provisional: bool)`; `Front` with `consider(candidate, compare) -> list[FrontChange]`, where `compare(a, b) -> Paired` runs P1's `paired_test` on the two trials' select flags
- **The rule:** the incumbent of bucket _b_ is the best stack whose own bucket is ≤ _b_. A candidate whose own bucket is _c_ is considered for every bucket _b_ ≥ _c_. It replaces the incumbent of _b_ when OD-26 passes against it, or when _c_ is smaller than the incumbent's own bucket and the paired test shows no clear harm (a smaller stack that does no clear harm is preferred). An empty bucket takes any candidate.
- `confirm(trial_id, bucket, measured_gib, latency_p95_s)` clears `provisional`, or removes the member from every bucket its measured VRAM does not fit

**Tests:** an empty front takes the candidate in every bucket from its own upward; a better candidate replaces; a smaller no-harm candidate replaces only in buckets whose incumbent is larger; a harmful candidate changes nothing; `confirm` demotes a stack whose measured VRAM exceeds a budget.

**Acceptance:** for the sweep's stored arms (P1 fixture) with GB300 VRAM readings, the front matches a hand-computed table committed beside the test.

---

### Task 4: Search-manifest check

**Files:** create `autovlm/manifest.py`; test `backend/tests/unit/autovlm/test_manifest.py`.

**Interfaces:** `ALLOWED_GLOBS = ("autovlm/recipes/**", "autovlm/templates/**", "autovlm/plugins/**")`; `changed_paths(repo: Path, parent: str, commit: str) -> list[str]` (from `git diff --name-only`); `check_manifest(paths, allowed=ALLOWED_GLOBS) -> CheckResult`.

**Tests (in a temporary git repo):** a recipe-only commit passes; a commit touching `autovlm/scorer/` fails and names the path; a commit touching `synthbench/` fails; a rename out of an allowed path fails.

---

### Task 5: Endpoint pool

**Files:** create `autovlm/executor/__init__.py`, `autovlm/executor/endpoints.py`; test `backend/tests/unit/autovlm/test_endpoints.py`.

**Interfaces:**

- `EndpointKey(model_sha256, mmproj_sha256, build, server_hash)`
- `AgentGpu` protocol: `run(name, image, vram_gib, port, mounts, argv) -> int` (the published host port), `ps() -> list[dict]`, `stop(name)`, `rm(name)`, `renew(name, ttl_hours)`; `CliAgentGpu` implements it with `subprocess` argv lists over the `agent-gpu` CLI (`run --name --image --vram --port --mount -- CMD`, `ps`, `stop`, `rm`, `renew --ttl`)
- `EndpointPool(agent_gpu, budget_gib, image_for_build: Mapping[str, str])` with `lease(key, vram_gib) -> Endpoint(url, name)` and `ensure_lifetime(name, min_hours)`

**Behaviour:** a lease reuses a running endpoint with the same key; over budget, it stops the least recently used idle endpoint; a single endpoint larger than the whole budget is refused; before a long replay, `ensure_lifetime` renews the container's TTL (the prompt programme lost a server mid-arm to its TTL, design `01` §7). The budget is a reserved share of `agent-gpu`'s global 40 GiB for the executor's session (design `05` §2): that reservation is a stack-repo change planned there; until it lands, the pool's budget is what S6 measured free, and the executor re-reads `agent-gpu ps` before each start.

**Tests (with a fake `AgentGpu`):** reuse; LRU eviction; refusal; renewal is called when the remaining TTL is short; `/props` build mismatch on start makes the lease fail.

**Acceptance:** P0's S6 configuration runs through the pool without manual `agent-gpu` commands.

---

### Task 6: Executor queue and trial runner

**Files:** create `autovlm/executor/queue.py`, `autovlm/executor/runner.py`; test `backend/tests/unit/autovlm/test_runner.py`.

**Interfaces:**

- Queue: job directories under `queued/`, `running/`, `done/` and `failed/`, each holding `job.json`; transitions are `os.rename` within one filesystem; at startup, jobs left in `running/` go back to `queued/`
- `run_trial(job) -> TrialResult`: read the recipe from the commit (`git show <commit>:<path>`), apply the manifest check (Task 4), lease endpoints (Task 5), run P1's `evaluate` with the cache (Task 1) on train and select, run P1's mechanical checks against the tier incumbent, write the result, append the `trial` ledger row (Task 2), then `Front.consider` (Task 3)

**Tests:** a job's lifecycle; a restart requeues a running job and does not double-log it; a manifest violation fails the job without running anything; a failed check is logged as a failure with its reason and never reaches the front; an incomplete run (unmeasured items) is retried once on a fresh endpoint, then failed; with the scorer unreachable the job waits in `running/` and is never ranked (fail closed, design `01` §7).

---

### Task 7: The scorer as a service

**Files:** create `autovlm/scorer/service.py`, `autovlm/scorer/client.py`, `autovlm/commands/confirm.py` (`sudo autovlm confirm --trial <id>`, the owner's verb), `autovlm/host/autovlm-scorer.service`; test `backend/tests/unit/autovlm/test_scorer_service.py`.

**Interfaces:**

- A Unix-socket server speaking JSON lines: `{"op": "answer", "tier": "train"|"select", "run_dir": ..., "trial_id": ...}` returns P1's tier answer; `{"op": "confirm", "trial_id": ...}` returns the holdout answer **only when the peer's uid (`SO_PEERCRED`) is 0**, that is, the owner running `sudo autovlm confirm`; every answer is recorded in the query ledger
- **Why root and not the owner's uid:** the Claude manager runs on the host as the owner's user, so a uid check on the owner would admit the manager too. Requiring root works only because the owner's `sudo` prompts for a password (P0 S1 Step 6 verifies this); if it does not, confirmation moves to a host no agent runs on
- The service runs as the `autovlm-scorer` user created in S1, owns the labels and split files (mode 600), and listens on a socket in a directory the executor's user can reach and no sandbox mounts. The executor runs as its own user, `autovlm-executor`, and reads worker commits through a group with read access to the worker workspaces; neither it nor the manager ever runs as root
- `ScorerClient(socket_path)` with `answer(...)` and `confirm(...)`; the executor uses it in place of reading labels

**Tests:** a round trip over a socket in `tmp_path`; a `confirm` from a non-root peer is refused (the test process is not root); a select answer contains no item ids; a malformed request is refused without crashing the server.

**Acceptance:** after this task, no executor or CLI code path reads `labels.jsonl` directly (a test greps the package for `read_labels` outside `autovlm/scorer/`).

---

### Task 8: The executor's HTTP API

**Files:** create `autovlm/executor/api.py`, `autovlm/host/autovlm-executor.service`; modify `.env.example` (add `AUTOVLM_EXECUTOR_PORT`, per the root AGENTS.md rule that every port lives in `.env`); test `backend/tests/unit/autovlm/test_api.py`.

**Interfaces:**

- FastAPI app bound to `127.0.0.1:${AUTOVLM_EXECUTOR_PORT}`; `Authorization: Bearer <token>`, with tokens read from a mode-600 `tokens.json` that maps each token to one worker session
- `POST /v1/trials` `{tag, brief_id, commit, idempotency_key}` → `{trial_id}`; `GET /v1/trials/{id}` → `{state}`; `GET /v1/trials/{id}/result` → `{train: per-item, select: aggregates, checks, outcome}`; `GET /v1/status`
- No route reaches the holdout. Long work is polled, never streamed.

**Tests:** a missing or wrong token returns 401; another session's trial returns 404; a repeated `idempotency_key` returns the same trial id; the result's select block has no item ids; the route table contains no `holdout` or `confirm` path.

**Acceptance:** with S4's rules applied, a worker sandbox reaches this port and no other autovlm port.

---

### Task 9: `autovlm status` and the null envelope

**Files:** create `autovlm/status.py`, `autovlm/commands/status.py`; modify `autovlm/executor/runner.py` (an `envelope` job type); test `backend/tests/unit/autovlm/test_status.py`.

**Interfaces:**

- `status(run_dir) -> dict` with exactly `front` (per bucket: incumbent trial, select readings, latency p50 and p95 from its `results.jsonl`, provisional), `envelope` (per bucket), `select_queries` (count this epoch against the budget), `open_briefs`, and `progress` (`trials_since_front_change`, `hours_since_front_change`)
- An `envelope` job runs a bucket's incumbent under the three null perturbations of design `02` §6 (the other pinned build, two paraphrases via the P3 template seam once it exists, a JPEG re-encode via P1's `jpeg_reencode`) and stores P1's `Envelope`

**Tests:** `status` over synthetic ledgers matches hand-built expectations; outcome labels use P1's `classify` with the stored envelope.

---

### Task 10: Host install and a smoke run (operational)

**Files:** create `autovlm/host/README.md` (install steps for both units, the socket directory, the tokens file); create `docs/benchmarks/autovlm/<date>-executor-smoke/report.md`.

**Steps:** install the scorer and executor units; issue one token; submit `autovlm/recipes/shipped-8b.yaml` and a burst-of-four variant as two commits through the API; wait for both; read `autovlm status`.

**Acceptance:** both trials complete; the front shows the shipped stack as provisional in its bucket; the scorer's query ledger shows the select answers; no autovlm process except the scorer can read the labels (checked with `sudo -u <executor user> cat <labels>` failing).
