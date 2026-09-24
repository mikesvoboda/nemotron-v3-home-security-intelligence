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

| File                                                            | Fate                                      | Responsibility                                                                                                    |
| --------------------------------------------------------------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `ai/vlm/Dockerfile`                                             | new (authored, uncommitted pending gates) | llama.cpp llama-server CUDA image; agent-gpu-legal; `--jinja` + mmproj wiring                                     |
| `scripts/vlm_probes/s1_nvext.py`                                | new (authored)                            | S-1: nvext vs native json_schema on `/completion`, nonce-const arms A/B1/B2                                       |
| `scripts/vlm_probes/s2_multimodal_schema.py`                    | new (authored)                            | S-2: nested `response_format.json_schema.schema` on image-bearing `/v1/chat/completions`; malformed-wrapper arm C |
| `docs/superpowers/plans/2026-09-24-vss-g0-gb300-environment.md` | new                                       | this plan                                                                                                         |
| `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`                | edit each task                            | rows G0.1–G0.4, S-1…S-5, F-queue                                                                                  |
| `backend/evaluation/eval_store.py` + unit test                  | new (task 6)                              | SQLite eval-item store (items/runs/results), `data/synthetic` loader                                              |
| probe reports → `$AGENT_GPU_DIR/out/probes/`                    | off-repo artifacts                        | committed ledger carries aggregate verdicts only                                                                  |

---

### Task 1: G0.1 backend dev environment — DONE evidence

- [x] `uv sync` → venv (ledger E5).
- [x] Test Postgres+Redis live: `docker compose -f docker-compose.test.yml up -d` → both healthy; ports 5433/6380 reachable **[V]**.
- [x] cv2 lib closure extracted (no-root apt-get download + dpkg -x); `import cv2` OK 5.0.0 **[V]**.
- [x] Free API port: 8098 unused repo-wide (grep across .env.example, all compose files, env-reference); legacy flagship owns 8000 **[V]**.
- [ ] Integration tier RAN: `uv run pytest backend/tests/integration/test_events_api.py -p no:cacheprovider -n0` → **72 passed** **[V 2026-09-24]**. Caveat ledgered: at `-n auto` the same file shows 15 xdist errors + 1 failure vs clean serial — investigate worker-DB suffixing under the test-profile DB before trusting parallel integration runs; do NOT loosen anything to hide it.
- [ ] Full unit tier green at `-n auto` (run in flight; floor ≥84, ledger the count).
- [ ] `cd frontend && npm ci && npm run typecheck` (no frontend changes planned — evidence only).

### Task 2: G0.2 build — blocked path + working bypass (S-4 evidence)

- [x] Both cuda bases pulled on the runner (`agent-gpu pull …:13.3.1-devel/runtime-ubuntu22.04`, both "succeeded") **[V]**.
- [x] `ai/vlm/Dockerfile` authored; agent-gpu contract-clean; `--jinja` added (probe precondition) **[V]**.
- [x] `agent-gpu build … ai-vlm:sm103` attempted twice, deterministic runner panic (ledger F1) **[V]** → G0.2's artifact ships via `agent-gpu run` until the owner repairs the runner.
- [ ] S-4 job `build7972` (detached, devel base, `--mount out:/out`, `-j72`): cmake `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=103` configures clean (nvcc 13.3.73 accepts 103; CUDA-host gcc 11.4) **[V]**; wait for `BUILD_SUCCESS` + binary at `$AGENT_GPU_DIR/out/build/b7972-bin/llama-server`. Ledger: build wall-time, warnings, `--flash-attn`/FA-kernel warnings for sm_103, exit code. **S-4 = DONE only with a run binary that loads a model (task 3).**
- [ ] Retry `agent-gpu build` once the owner reports F1 fixed; commit `ai/vlm/Dockerfile` after the pre-commit gates either way.

### Task 3: G0.2 serve + S-1/S-2 probes

- [ ] Serve: `agent-gpu run --name vlm-serve --image docker.io/nvidia/cuda:13.3.1-devel-ubuntu22.04 --vram 12 --port 8080 --mount models:/models --mount out:/out --detach --entrypoint sh -- -c 'cd /out/build/b7972-bin && LD_LIBRARY_PATH=. ./llama-server --model /models/vlm/Qwen3VL-4B-Instruct-Q4_K_M.gguf --mmproj /models/vlm/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf --jinja --host 0.0.0.0 --port 8080 --n-gpu-layers 99 --ctx-size 8192 --flash-attn on'` — poll `http://host.docker.internal:<allocated>/health`, record `build_info` from `/props` **[needs: F2 done]**.
- [ ] S-1: `uv run python scripts/vlm_probes/s1_nvext.py --base-url … --report /out…/probes/s1.json` — record verdict + content snippets in ledger; expected nvext IGNORED (E5), native ENFORCED.
- [ ] S-2: synthetic probe image generated locally (pillow), then `s2_multimodal_schema.py`; ENFORCED required for the spec §3 assumption; per-checkpoint record (re-run on model/engine swap).
- [ ] Ledger rows S-1, S-2 with the probe reports' key fields + server `build_info`.
- [ ] **Owner question surfaced, not self-resolved (F4):** spec 0.3 applies fail-closed null semantics to the LIVE legacy Nemotron path (score-50→verification_failed with NULL). Needs explicit owner confirmation before any code lands; zero code now.

### Task 4: S-5 — Nemotron-12B-VL GGUF on a bumped pin

- [ ] Download `Vastined/Nemotron-Nano-12B-v2-VL-GGUF` Q4_K_M (7,501,771,584 B) + mmproj (1,689,151,968 B) into `models/vlm/` (community quant ledgered as fact; NVIDIA ships no official GGUF).
- [ ] Compile bumped pin (default `LLAMA_CPP_REF=b11090`, same run-job recipe) **only if** b7972 fails to load the Nemotron mmproj; otherwise S-5 closes on b7972 load + S-2 green and the pin bump moves to M2 with the model pick.
- [ ] `--vram 16` for the 12B server (6.99+1.58 GiB weights + KV + ~1 GiB context overhead).
- [ ] Ledger: load evidence = /health green, build_info, first multimodal completion; memory used per nvidia-smi-in-container.

### Task 5: G0.3 — parked (owner decisions)

- [ ] Nothing executed. Surface F1/F3 to the owner; revisit after rulings. (Triton base `nvcr.io/nvidia/tritonserver:26.01-py3` is amd64-only; spec's "vlm mode stops Florence/enrichment" is Triton explicit-control unloading, not `compose stop`; and the explicit-mode switch edits a public surface `model_management.py` tests assert as 501.)

### Task 6: G0.4 synthetic eval items (schema + store now; media owner-gated)

- [ ] TDD: failing test first for `backend/evaluation/eval_store.py` (SQLite, items/runs/results, off-repo path under `$AGENT_GPU_DIR/eval-store` **pending owner path confirmation, F6** — wrong path = D10 privacy problem).
- [ ] Author `AssessInput` as a Pydantic model FIRST (it is also Phase 1's contract; a wrong shape means re-frozen items) and pin it in the ledger for owner review before freezing any item.
- [ ] Loader maps the 408 committed label sets in `data/synthetic` (labels + metadata, media 0) into eval items; procedural placeholder frames via pillow are plumbing evidence only, labeled as such — never cite `synthetic_data.py test` as replay evidence.
- [ ] S-3 salience smoke: ~10 items (2 normal / 2 suspicious / 2 threats / 2 benign look-alikes + 2 variants), through Qwen3-VL-4B with the constrained verdict; record per-item: alert/score + one-line human check "plausible?"; benign-look-alike rejection is the pass bar.
- [ ] Decision surfaced (F5): real/stock incident imagery needs owner keys (Pexels/Pixabay) — AI generation is unusable for 11 of 13 scenarios; G0.4 closes on schema+store+placeholder-media plumbing with the record that full salience quality waits for keys.
- [ ] Errata entries queued (spec says 17 scenarios → 13 verified; spec's single-probe cmd lacks `--image`): date them in `docs/vss-integration/11-errata-2026-09-23.md` at commit time.

### Task 7: G0 close-out

- [ ] Ledger: G0.1/G0.2 rows closed with commands+results+commits; S-1…S-5 rows DONE or BLOCKED(reason) — never an unobserved pass.
- [ ] Built-in code review across the diff (Dockerfile, probes, eval store).
- [ ] Milestone report to owner: proven (with S#s), failed and why, next (Phase 0 planning — only G0's successor, per one-phase-at-a-time), decisions owed (F1–F6).

## Definition of done

G0.1 green with integration evidence + the xdist caveat recorded; G0.2 VLM served + S-1/S-2 content-verdicts ledgered (image build retried post-F1); S-3 smoke executed or BLOCKED with reason; S-4 done via run-job with the runner-build defect ledgered; S-5 load evidence or owner-parked pin decision; G0.4 store + items + schema pinned; G0.3 explicitly parked. No backend runtime code merged beyond what 0.25/0.3 approves; nothing pushed.

## Out of scope

Phase 0+ code; compose/service wiring for `ai-vlm` (Phase 1's 1.2); contract/`VLM_OPS` generation (1.1); Triton/gateway work (F1/F3 first); Brev anything; pushes/PRs.
