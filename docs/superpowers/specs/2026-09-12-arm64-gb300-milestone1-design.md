# arm64/GB300 Bring-Up — Milestone 1 Design

- **Date:** 2026-09-12
- **Branch:** `feat/context-map-2026-09-12`
- **Status:** approved design (owner), pending spec review
- **Supersedes nothing.** Entirely additive; the amd64 path is untouched.

## 0. Context and product decision

The codebase was built (~8 months of agent-assisted work, last commit 2026-02-25) on
an amd64 host with an RTX A5500 (Ampere, sm_86) and podman. Development now happens on
an NVIDIA GB300 Grace box: aarch64, sm_103, 256 GB HBM, 64 KiB-page kernel, Docker
installed, podman absent.

**Product decision (owner, 2026-09-12):** the product supports **both amd64 and arm64**
deployments. The GB300 machine is the owner's personal installation; assumed external
users are on x64. Therefore:

- arm64 support is strictly **additive** — every change must leave the amd64 path
  behaviorally identical (Approach A: overlay + converge later, not adaptive-in-place).
- No published multi-arch image manifests (the owner is the only arm64 consumer).
- CUDA arch targets, when they arrive in milestone 2, are **additive**
  (`sm_86;sm_103`-style widening, never a swap).

**Milestones:**

| # | Scope |
|---|---|
| **M1 (this spec)** | Core (CPU-only) stack online on arm64 + `scripts/validate.sh` green |
| M2 | GPU serving: `ai-gateway` (Triton), `ai-llm` (llama.cpp), optional vLLM, DCGM |
| M3 | Vision-model landscape refresh (post-port decision, informed by M2) |

## 1. Verified host facts (probed 2026-09-12)

| Fact | Value | Contrast with repo assumption |
|---|---|---|
| arch | `aarch64` | repo built on amd64 |
| kernel | `6.17.0-1032-nvidia-64k`, **PAGE_SIZE 65536** | NVIDIA's Grace default flavor; only `-64k` kernels installed; 4k flavor exists in apt (`linux-image-nvidia-*`) with driver-metapackage lockstep |
| GPU | 1× GB300, cc **10.3 (sm_103)**, 256,703 MiB, driver 610.43.02 (open) | compose defaults assume **two** GPUs (`GPU_LLM=0`, `GPU_AI_SERVICES=1`); GPU 1 does not exist |
| engine | Docker 29.1.3, Compose 2.40.3; **podman NOT installed** | CLAUDE.md mandates podman |
| GPU toolkit | nvidia-container-toolkit 1.19.0; CDI devices `nvidia.com/gpu=0,all` already listed by `nvidia-ctk cdi list`; no default-runtime in `/etc/docker/daemon.json` | repo uses CDI + `deploy.resources` dual mechanism for rootless podman |
| CUDA toolkit | **absent on host** (`nvcc` missing) | all CUDA must come from containers |
| `.env` | **missing** (`.env.example` present) | `setup.py` has never run here; its quick mode hardcodes `gpu_llm=0`/`gpu_ai_services=1` |
| compose vars | `TEMPO_PORT`, `TEMPO_OTLP_GRPC`, `AI_GATEWAY_METRICS_PORT`, `GPU_AI_SERVICES` referenced in compose, **absent from `.env.example`** | `setup.py` port-scan can't see these conflicts |
| co-resident stack | `dgx-inference-*` on Docker: **holds 127.0.0.1:8000** (vllm) = `API_PORT` default; Postgres/Prometheus/DCGM unpublished (no conflict) | fresh install must dodge :8000 |
| toolchain | `uv 0.12.6 (aarch64)`, venv with **CPU torch 2.9.1 imports**, numpy/cv2/PIL/psutil/uvloop/asyncpg import; **27,502 backend unit tests collect**; node+npm present; **bun absent** (frontend scripts are plain vite/vitest/eslint, so npm is viable); apt has `podman 4.9.3`, `podman-compose 1.0.6` | milestone-1 import surface already works on 64k pages |

## 2. Owner-approved decisions

1. **Dual-arch additive** (§0), amd64 reference path.
2. **M1 bar:** core stack Up+healthy + `validate.sh` green; GPU serving deferred (M2).
3. **Runtime: install podman** (apt), honoring `CLAUDE.md`; docs remain source of truth.
   Podman 4.9's `podman compose` delegates to an installed compose provider — which
   provider services compose ops here is **discovered by probe P2, not assumed**.
4. **Kernel/page size: do not touch.** 64 KiB pages are NVIDIA's shipped Grace
   configuration (NGC images are built for it) and every M1-relevant import collects.
   Reversal criteria in risk R3; only observed breakage flips it.
5. **Mechanism:** overlay files + two-phase bring-up; probes folded in as step 0.

## 3. Overlay design (all new files)

### 3.1 Files

- `config/docker-compose.gb300.yml` — compose override, GPU-exclusion mechanics only.
- `env-templates/gb300.env.template` — starting point for this host's `.env`.
- `scripts/bootstrap-gb300.sh` — sequenced probe + bring-up + verify (idempotent).

Named `gb300`, not `arm64`: the deltas are host-class facts (1×sm_103, co-resident
inference stack), and future non-GB300 arm64 hosts should diverge deliberately.

### 3.2 GPU exclusion — what was measured, not assumed

Compose **merges** mappings, so these were empirically tested (docker compose 2.40.3):

| Mechanism | Result |
|---|---|
| plain override omitting `ai-llm`/`ai-gateway` | ✗ deps survive (merge semantics) |
| `required: false` on the deps | ✗ GPU containers still **created** → CUDA builds enter M1 |
| profiles on `ai-llm`/`ai-gateway` | ✗ `invalid compose project` (backend still references them) |
| `depends_on: !override` (compose ≥2.24) | ✓ `up backend` creates only postgres+backend; full-stack `config --services` unchanged |
| `up --no-deps` two-phase (any provider) | ✓ trivially, no file changes |

**Primary mechanism: two-phase bring-up.** Phase A: infra + media + LGTM
(`postgres redis go2rtc` + observability list), health-gated. Phase B:
`up -d --no-deps backend frontend` after A is healthy. Provider-agnostic;
the override file carries **no** `depends_on` surgery by default.

**Opportunistic upgrade:** probe **P0** tests whether the compose provider in use
parses `!override`; if yes, the override may carry the trimmed
`backend.depends_on: !override {foscam-init, postgres, redis, go2rtc}` for
single-command bring-up. `podman-compose 1.0.6` support for the tag is unproven;
absence only costs ergonomics, not capability.

### 3.3 Override/env contents (beyond mechanics)

- `.env` template: `GPU_AI_SERVICES=0` (comment: single-GPU box; **do not** migrate old
  caches `triton-kernel-cache`, `llama-cache`, `llama-nv-cache` — arch-keyed, M2 note);
  `API_PORT` left at 8000 — the bootstrap port-scan reassigns around the live
  `dgx-inference-vllm` hold. The template encodes host *config*, not conflicts.
- `.env.example` gains the four missing compose-referenced variables (§1). This is the
  one shared-file edit that is **functional, not cosmetic**: `setup.py` parses
  `.env.example` as runtime data, so the port scanner starts seeing
  Tempo/gateway-metrics conflicts for all architectures. Flagged as an exception to
  "new files only."
- **Prometheus rule-file mounts:** `monitoring/prometheus.yml` lists seven
  `rule_files`; the repo contains all seven, but compose mounts only four into the
  container (`profiling-recording-rules.yml`, `profiling-regression-alerts.yml`,
  `ai-pipeline-alerts.yml` missing → Prometheus config-load failure at startup,
  i.e. a milestone-1 health-gate blocker). Fixed **in the override** by adding the
  three mounts there (additive, arch-neutral, `:ro,z` per repo convention); graduates
  into the prod file at convergence. No prod-file edit in M1.
- No `platform:` removals — verified **zero** `platform:` keys in any compose file;
  arch coupling lives entirely in base images and in-image compilation (M2 surface).

### 3.4 Convergence rule

The overlay holds only (i) GPU-exclusion mechanics and (ii) host-proven deltas.
Each graduates into the prod compose/env files when the delta is shown
**arch-neutral** (works unchanged for x64) — convergence deletes overlay lines rather
than rewriting prod files.

## 4. Bring-up sequence

0. **Installs:** `apt install podman podman-compose`; mirror `setup_lib`'s rootless
   storage/socket conventions (backend mounts `PODMAN_SOCKET` + `userns keep-id`);
   npm for frontend (`bun` optional, deviation logged).
1. **P0** — `!override` parseability by the active compose provider (decides §3.2).
2. **P1** — CDI passthrough: stock CUDA arm64 container via
   `--device nvidia.com/gpu=all` asserting it sees the GB300. **Not M1-gating** (GPU is
   M2) but run now: a failure here is M2-relevant information that would otherwise
   surface at the worst possible review moment. Record result either way.
3. **P2** — `podman compose -f docker-compose.prod.yml config -q` on the untouched
   prod file: identifies the provider and its tolerance of `deploy.resources`/CDI
   syntax in the 1246-line file before any of our edits confound the signal.
4. **.env** — template → `.env`, port-scan (`setup_lib.port_scanner`) against live
   stack; expect and resolve the :8000 shift.
5. **Phase A** — infra/media/observability up, health-gate via compose healthchecks.
6. **Phase B** — `--no-deps` backend+frontend up.
7. **Health gate** — per CLAUDE.md loop, **plus** explicit pipeline-worker evidence
   (readiness is relaxed by `READINESS_REQUIRE_PIPELINE_WORKERS=false`,
   `docker-compose.prod.yml:497`, and the degradation stack can mask missing AI
   servers behind fallback scores — green ≠ serving, so the gate greps worker startup
   in logs and hits `/api/system/health/ready` as well as `/api/system/health`).
8. **Tests** — `./scripts/validate.sh` (ruff/mypy/pytest `--cov-fail-under=80` with
   `TEST_DATABASE_URL` from discovered Postgres; eslint/tsc/vitest/build/
   chunk-circulars on npm). GPU suites (`gpu-tests.yml`, `benchmarks.yml`) untouched.
9. **Docs** — commit spec + doc-updates ledger
   (`docs/plans/2026-09-12-context-map-doc-updates.md`); memory already updated.

## 5. Error handling / known hazards

- **Provider confusion:** `podman compose` may be serviced by docker-compose 2.40.3 or
  podman-compose 1.0.6; behavior differences (tags, `deploy.resources`, CDI strings)
  are P2's subject. Fallback if apt podman-compose is too old for the prod file: newer
  podman-compose via pip, or pin the provider to docker-compose (which the repo's
  own CLAUDE.md comment "podman-compose → docker-compose plugin" anticipates).
- **Rootless podman 4.9 on Ubuntu 24.04:** storage/uid-map migration errors →
  `podman system migrate`; if the repo's `setup_lib` rootless config (commit
  `bcbb87a1`) diverges from 4.9.3 expectations, follow the repo config and record
  deviations.
- **:8000 collision** — expected, dodged by port-scan, not by editing the template.
- **64k pages** — latent until observed; watch for `mmap`/allocator failures
  (R3 reversal criteria).
- **Degradation masking** — `AIFallbackService` (default risk 50) + relaxed readiness
  make an AI-less stack look healthy; M1 accepts this (GPU out of scope) but the gate
  records it explicitly so M2 never mistakes it for serving.
- **Never migrate GPU-arch caches** (§3.3).

## 6. Milestone-1 exit criteria

- [ ] P0/P1/P2 results recorded (pass or fail, dated, in the ledger)
- [ ] Core services `Up` + `healthy`: `postgres redis go2rtc backend
      frontend prometheus grafana loki tempo alloy alertmanager pyroscope
      node-exporter redis-exporter json-exporter blackbox-exporter`
      (`foscam-init` separately: exited 0, as a `service_completed_successfully` one-shot)
- [ ] `ai-*` and `dcgm-exporter` **absent** from `podman ps` (proof of exclusion)
- [ ] API health endpoints 200; pipeline-worker startup evidenced in backend logs
- [ ] `./scripts/validate.sh` exit 0 on aarch64 (coverage gate 80 combined; CI's
      unit=85 separately noted)
- [ ] No error logs in `podman compose logs --tail=50` across services
- [ ] Spec + ledger committed on `feat/context-map-2026-09-12`

## 7. Risk register *(provisional — blocker-inventory workflow pending)*

| ID | Risk | Stance |
|---|---|---|
| R1 | Triton (`nvcr.io/...tritonserver:26.01-py3`) & llama.cpp (pinned commit `b7972`, arch list `75,80,86,89` — no Blackwell) on sm_103 may reshape M2/M3 | P1 probes the cheapest slice now; full answer in M2 |
| R2 | apt `podman-compose 1.0.6` handling of the 1246-line prod file (`deploy.resources`, CDI strings, tags) | P2 gates; fallbacks enumerated (§5) |
| R3 | 64k-page latent breakage in M2 third-party wheels | **Reversal criteria:** two distinct observed mmap/allocator/segfault failures in M1, or CUDA-context failures in M2 that survive image-version bisect → install `linux-image-nvidia` (4k) + matching driver metapackage, re-run M1 |
| R4 | `setup.py`/`gpu_config_service.py` still generate dead service names (`ai-yolo26`…) and GPU pairs | Revive generator as the overlay's eventual home (M2); ledger-captured, not fixed here |
| R5 | `docker-compose.ghcr.yml` already describes a broken pre-consolidation topology | M2+ decision (deprecate vs resync); ledger-captured |
| R6 | healthy-while-degraded masking (§5) | M2 acceptance gate must prove real inference, not health flags |

## 8. Explicitly out of scope (M1)

GPU serving and CUDA image rebuilds; vision-model refresh; TensorRT export pipeline;
multi-GPU docs/generator revival; `ghcr.yml`; image publishing/multi-arch manifests;
kernel/page-size swap (absent R3 triggers); any behavioral change to the amd64 path.
