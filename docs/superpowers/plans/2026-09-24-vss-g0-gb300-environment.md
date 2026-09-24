# Phase G0 — GB300 Development Environment (VSS gaming-GPU workstream)

> **For agentic workers:** execute task-by-task, checkbox syntax; every step closes on an executed command + result in the ledger, never on written code. No superpowers skills or codex here — milestone review is the built-in code review.

**Goal:** stand up the GB300 development environment of spec §"Phase G0" — backend dev env with a runnable integration tier (G0.1), a pinned llama.cpp serving the development VLM with both enforcement probes run against it (G0.2), synthetic eval items so replay can be proven before any real item is frozen (G0.4) — and close the brief's five risk spikes with evidence. G0.3 stays optional and is gated on an owner decision (below).

**Spec/authority:** `docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md` (rev 4) for WHAT; this plan is the order and the guardrails for THIS box. Where the spec says podman/nvidia-smi, read `agent-gpu` — the environment-of-record deltas are ledger rows E1–E10 of `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`.

**Tech stack:** agent-gpu-brokered GB300 (sm_103, aarch64, 4 KiB pages), docker-in-sandbox (compose) for DBs, uv/Python 3.14 venv, llama.cpp b7972 (first) and a bumped pin (S-5), Qwen3-VL-4B-Instruct GGUF.

## Sequencing (binding)

1. **Spikes before building** (brief §"Spike before building"). S-4 (build works here) gates G0.2's serve step; S-1/S-2 run against the served VLM; S-3 needs S-2's green + the smoke model up; S-5 runs after S-4/S-2 mechanics are proven.
2. G0.1 is independent and proceeds in parallel; its integration-tier evidence needs live Postgres+Redis (done in-sandbox, task 1).
3. G0.4's item-store work is independent of the GPU chain; its media is owner-key-gated (task 6).
4. **G0.3 is parked** — blocked on owner decisions (F1/F3 below). Do not build ai-gateway here; do not touch rootful dgx-inference containers.

## Global constraints

- GPU only through `agent-gpu` (never around it); honest `--vram` (watchdog kills in ~15 s; CUDA context costs ~1 GiB); `agent-gpu rm` when done. `--wait` goes BEFORE `--`.
- Real-camera imagery/labels/snapshots never enter git; synthetic + aggregate metrics only.
- Legacy path byte-identical; retired code stays (R8). G0 touches no `backend/` runtime code — with one proposed exception in task 3, owner-gated.
- Doc-vs-repo conflicts → ledger row or dated errata, never a silent spec edit; keep [V]/[C]/[E]/[?]/[O]/[A] markers.
- Every commit: manual pre-commit pass + conventional-pre-commit msg check, `Co-Authored-By: Claude Code <noreply@anthropic.com>` trailer.
- STOP AND ASK (goal list) — additionally surfaced by this plan's research: F1–F6 in the ledger's owner-decision queue.

## Known environment facts (verified this session; ledger E-series + cluster dumps)

- Builds on the runner are **broken** (buildah panics `creating lock file directory: mkdir /run/user` at the first non-cached RUN; deterministic; admin repair is owner-side). **Build-adjacent work runs via `agent-gpu run` on the pulled `docker.io/nvidia/cuda:13.3.1-devel-ubuntu22.04`**, which has full egress and apt. `ai/vlm/Dockerfile` is authored and legal (no cache mounts, no ONBUILD) and stays ready for a one-command retry: `agent-gpu build --context workspace:ai/vlm --tag ai-vlm:sm103 --build-arg CUDA_ARCHITECTURES=103`.
- Weights live in `$AGENT_GPU_DIR/models/vlm/` (RO to containers, same ~47 GiB virtiofs quota as the workspace — image layers do NOT count). Qwen3-VL-4B set downloaded: `Qwen3VL-4B-Instruct-Q4_K_M.gguf` (2,497,281,664 B) + `mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf` (453,974,304 B) **[V 2026-09-24, HF API byte sizes]**.
- In-sandbox integration DBs: `docker compose -f docker-compose.test.yml up -d` (postgres:5433, redis:6380, healthy; the CI-profile compose dies on seccomp — chown/setpriv denied). Persisted overrides: `TEST_DATABASE_URL=postgresql://security_test:test_password@localhost:5433/security_test` <!-- pragma: allowlist secret -->, `TEST_REDIS_URL=redis://localhost:6380/15` (throwaway compose-test creds).
- cv2 needs an out-of-tree lib closure (`/agents/agent-vss1/out/libs/x/usr/lib/aarch64-linux-gnu`, `LD_LIBRARY_PATH` persisted) — sandbox is Ubuntu 26.04 with no root apt; `opencv-python-headless` would need a lockfile change (owner call).
- S-1 static answer is already source-verified at b7972: zero occurrences of `nvext`/`guided_json` in the tree → expect **IGNORED** for nvext and **ENFORCED** for native `json_schema` (grammar and media are independent variables at this pin; the required-const trick is genuinely enforceable). Probes are runtime regression guards, two-arm, content-only (status codes carry no information; gate on `/props build_info`).

## File structure

| File                                                            | Fate                                | Responsibility                                                                                                    |
| --------------------------------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `ai/vlm/Dockerfile`                                             | committed c2e8949f                  | llama.cpp llama-server CUDA image; agent-gpu-legal; `--jinja` + mmproj wiring                                     |
| `scripts/vlm_probes/s1_nvext.py`                                | committed c2e8949f                  | S-1: nvext vs native json_schema on `/completion`, nonce-const arms A/B1/B2                                       |
| `scripts/vlm_probes/s2_multimodal_schema.py`                    | committed c2e8949f                  | S-2: nested `response_format.json_schema.schema` on image-bearing `/v1/chat/completions`; malformed-wrapper arm C |
| `docs/superpowers/plans/2026-09-24-vss-g0-gb300-environment.md` | new                                 | this plan                                                                                                         |
| `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`                | edit each task                      | rows G0.1–G0.4, S-1…S-5, F-queue                                                                                  |
| `backend/evaluation/{assess_input,eval_store}.py` + unit test   | committed 4d97e04b, loader fca9e426 | SQLite eval-item store (items/runs/results), `data/synthetic` loader                                              |
| probe reports → `$AGENT_GPU_DIR/out/probes/`                    | off-repo artifacts                  | committed ledger carries aggregate verdicts only                                                                  |

---

### Task 1: G0.1 backend dev environment — DONE evidence

- [x] `uv sync` → venv (ledger E5).
- [x] Test Postgres+Redis live: `docker compose -f docker-compose.test.yml up -d` → both healthy; ports 5433/6380 reachable **[V]**.
- [x] cv2 lib closure extracted (no-root apt-get download + dpkg -x); `import cv2` OK 5.0.0 **[V]**.
- [x] Free API port: 8098 unused repo-wide (grep across .env.example, all compose files, env-reference); legacy flagship owns 8000 **[V]**.
- [x] Integration tier RAN: `uv run pytest backend/tests/integration/test_events_api.py -p no:cacheprovider -n0` → **72 passed** **[V 2026-09-24]**. Caveat ledgered: at `-n auto` the same file shows 15 xdist errors + 1 failure vs clean serial — investigate worker-DB suffixing under the test-profile DB before trusting parallel integration runs; do NOT loosen anything to hide it.
- [x] Full unit tier at `-n auto`: **27,942 passed, 122 skipped, 8 xfailed, 1 failed** — the single failure is `test_deploy_phases` wanting `systemctl` (E6 environment class, not a regression) **[V]**.
- [x] `cd frontend && npm ci && npm run typecheck` → **exit 0** (evidence only) **[V]**.

### Task 2: G0.2 build — blocked path + working bypass (S-4 evidence)

- [x] Both cuda bases pulled on the runner (`agent-gpu pull …:13.3.1-devel/runtime-ubuntu22.04`, both "succeeded") **[V]**.
- [x] `ai/vlm/Dockerfile` authored; agent-gpu contract-clean; `--jinja` added (probe precondition) **[V]**.
- [x] `agent-gpu build … ai-vlm:sm103` attempted twice, deterministic runner panic (ledger E13; owner decision F1) **[V]** → G0.2's artifact ships via `agent-gpu run` until the owner repairs the runner.
- [x] S-4 job `build7972` (detached, devel base, `--mount out:/out`, `-j72`): cmake configures clean (nvcc 13.3.73 accepts 103; CUDA-host gcc 11.4) and **BUILD_SUCCESS, exit 0 in ~7 min**; binary at `$AGENT_GPU_DIR/out/build/b7972-bin/llama-server` **[V]**. S-4 = DONE: the binary loads and serves a model (task 3) **[V]**. (Runtime base also needed `libgomp.so.1` — mounted from `out/libs/gomp` — ledgered.)
- [x] `ai/vlm/Dockerfile` committed after the pre-commit gates anyway (c2e8949f). F1 CLOSED 2026-09-24: post-repair `agent-gpu build` tagged both `ai-vlm:sm103` and fresh-layer `ai-vlm:sm103-b11090`; `img-serve` from the image hit `/health` 200 + `/props` `b7972-e06088da0` (ledger F1 row).

### Task 3: G0.2 serve + S-1/S-2 probes

- [x] Serve: recipe as written (runtime base + `LD_LIBRARY_PATH=.:/out/libs/gomp`), `--port 8080` = container port (the broker maps it to a host port and maps **container→host**, so the server must listen where `--port` points) — `/health` ok in ~10 s, `/props` `build_info b7972-e06088da0`, `modalities.vision: true`, real VRAM 5,442 MiB against a 12 GiB declaration **[V]**.
- [x] S-1 ran: expected outcome confirmed — **native `json_schema` ENFORCED (arm B2 echoed the const) while `nvext.guided_json` is SILENTLY IGNORED (arm B1 prose, const not echoed) = E5 empirically confirmed**. Report `$AGENT_GPU_DIR/out/probes/s1.json` (`verdict: ENFORCED`).
- [x] S-2 ran: **ENFORCED** at b7972 with images (nested-const echoed). Trap ledgered: `max_tokens: 96` truncated arm B and faked an IGNORED verdict — grammar can't close past the budget; probe raised to 400. Per-checkpoint guard recorded (re-run on engine/model swap) **[V]**.
- [x] Ledger rows S-1, S-2 closed with report key fields + server `build_info`.
- [x] **Owner question surfaced, not self-resolved (F4):** spec 0.3 applies fail-closed null semantics to the LIVE legacy Nemotron path (score-50→verification_failed with NULL). RULING 2026-09-24: **APPROVED** — zero code in G0 (correct: 0.3-implementation belongs to Phase 0), approval on record in ledger F4.

### Task 4: S-5 — Nemotron-12B-VL GGUF on a bumped pin

- [x] Downloaded into `models/vlm/` — the repo id corrected to `Vastined/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16-GGUF` (the planned id 404s); Q4_K_M 7,501,771,584 B + mmproj 1,689,151,968 B, anonymous pull **[V]** (community quant ledgered; NVIDIA ships no official GGUF).
- [x] b7972 **fails to load the mmproj**: `load_hparams: unknown projector type: nemotron_v2_vl` **[V]** → the pin bump was triggered exactly as planned. b11090 compiled with the same run-job recipe, exit 0 **[V]**.
- [x] Served with `--vram 14` (honest declaration; real use settled at **10,008 MiB** — inside the cap, broker fence respected) **[V]**.
- [x] Load evidence: `/health` ok, `build_info b11090-b1c2863e2`, `vision: true`, multimodal probe **ENFORCED** (echoed_const true; malformed-wrapper arm non-empty) **[V]**. Broker `agent-gpu rm`'d to 0 containers. **S-5 DONE** — the spec's pin-bump requirement is now empirical, not assumed.

### Task 5: G0.3 — CLOSED N/A on GB300 (owner ruling 2026-09-24)

- [x] Nothing executed by design — surfaced F1/F3 to the owner; owner ruled **N/A on GB300** (the step serves the 3090's memory fight; here the spec's own ~47.9 GiB figure makes the model-stop dance pointless). Supporting evidence on record: Triton base `nvcr.io/nvidia/tritonserver:26.01-py3` is amd64-only; spec's "vlm mode stops Florence/enrichment" is Triton explicit-control unloading, not `compose stop`; and the explicit-mode switch edits a public surface `model_management.py` tests assert as 501. No code written; R8 retirement untouched. **[ledger G0.3 + F3 rows]**

### Task 6: G0.4 synthetic eval items (schema + store now; media owner-gated)

- [x] TDD: `test_eval_store.py` written first (red), then `eval_store.py` (items/runs/results, fingerprint-frozen items, D10 write-time media-path guard). Store path remains a **required argument** — production path waits on owner F6 **[V, 4d97e04b]**.
- [x] `AssessInput` authored FIRST (frozen, extra=forbid) and pinned for owner review in the ledger G0.4 row; **no item frozen** **[V]**.
- [x] Loader `load_synthetic_items()` maps all 408 committed label sets (134 normal / 132 suspicious / 142 threats) to DRAFT items: media stays empty (labels carry no media; inventing a path = D10 fabrication), `zone_crossing` never claimed, unreadable sets skipped with a warning. 6 loader tests, suite green **[V, fca9e426]**.
- [x] S-3 smoke ran (10 procedural scenes incl. 2 benign look-alikes): pass bar met — 6/6 benign REJECTED (look-alikes score 0), 10/10 schema-valid, median 7.3 s. Honest limitation ledgered: 0/4 incident scenes detected because the 4B model reads the primitives as "stylized minimalist renderings" — **placeholder media is not valid salience evidence** **[V]**.
- [x] Decision surfaced (F5, ledger queue item 5): full-quality salience waits on owner stock/staged-media keys (AI generation unusable for 11 of 13 scenarios).
- [x] Errata dated 2026-09-24 in `docs/vss-integration/11-errata-2026-09-23.md` (N1–N7, incl. 17→13 scenarios and the missing `--image` in the probe command) **[V, 7af48184]**.

### Task 7: G0 close-out

- [ ] Ledger: G0.1/G0.2 rows closed with commands+results+commits; S-1…S-5 rows DONE or BLOCKED(reason) — never an unobserved pass.
- [ ] Built-in code review across the diff (Dockerfile, probes, eval store).
- [ ] Milestone report to owner: proven (with S#s), failed and why, next (Phase 0 planning — only G0's successor, per one-phase-at-a-time), decisions owed (F1–F6).

## Definition of done

G0.1 green with integration evidence + the xdist caveat recorded; G0.2 VLM served + S-1/S-2 content-verdicts ledgered (image build retried post-F1); S-3 smoke executed or BLOCKED with reason; S-4 done via run-job with the runner-build defect ledgered; S-5 load evidence or owner-parked pin decision; G0.4 store + items + schema pinned; G0.3 explicitly parked. No backend runtime code merged beyond what 0.25/0.3 approves; nothing pushed.

## Out of scope

Phase 0+ code; compose/service wiring for `ai-vlm` (Phase 1's 1.2); contract/`VLM_OPS` generation (1.1); Triton/gateway work (F1/F3 first); Brev anything; pushes/PRs.
