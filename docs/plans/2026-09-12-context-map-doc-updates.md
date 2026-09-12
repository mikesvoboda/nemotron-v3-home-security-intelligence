# Documentation Updates Ledger — 2026-09-12
Captures doc/code drift found by the codebase context survey + arm64 port probes.
Captured, not fixed (spec §5 M1). Promotion to Linear deferred to owner.

## Verified drift (each row re-verified by direct check)
| # | Location | Claim | Reality (evidence) |
|---|---|---|---|
| D1 | CLAUDE.md port table + backend client defaults | five standalone AI servers | consolidated into ai-gateway (Triton shim); `florence_client.py:259` DEFAULT_FLORENCE_URL=http://ai-florence:8092 dead; enrichment_client same :8094 |
| D2 | .env.example YOLO26_PORT/FLORENCE_PORT/CLIP_PORT/ENRICHMENT_PORT/ENRICHMENT_LIGHT_PORT | REQUIRED per table | zero compose references (grep docker-compose*.yml) |
| D3 | .env.example | defines all compose-referenced vars | TEMPO_PORT, TEMPO_OTLP_GRPC, AI_GATEWAY_METRICS_PORT, GPU_AI_SERVICES referenced in compose but absent (setup.py port-scan blind) — FIXED by Task 2 (done 2026-09-12) |
| D4 | monitoring/prometheus.yml rule_files | 7 files | compose mounts only 4 (profiling-recording-rules, profiling-regression-alerts, ai-pipeline-alerts missing in-container) — FIXED additively by Task 4 override |
| D5 | backend/AGENTS.md + backend/Dockerfile:117,222 | Alembic migrations | no alembic.ini/alembic dir; schema via create_all(); integration test skipped wholesale |
| D6 | docs/development/multi-gpu.md + gpu_config_service.py | generates ai-yolo26/ai-enrichment overrides | those services no longer exist; generator output dead |
| D7 | docker-compose.ghcr.yml | GHCR deploy path | pre-consolidation topology (elasticsearch/jaeger/cadvisor; no ai-gateway/tempo) — broken |
| D8 | video-analytics.md + docs/reference/models.md | X-CLIP action model | production uses ST-GCN++ (NEM-5563); gateway /action-classify still calls xclip_action; stgcn_action has no adapter cache path |
| D9 | docs VRAM figures (glossary ~7GB / video-analytics 4+6.8GB / multi-gpu 14-21.7GB LLM) | consistent VRAM | mutually contradictory; all A5500-24GB-shaped |
| D10 | .env.example cadvisor 8083 / systemd unit 8088 / setup.py fallback 8082 | one cadvisor port | three values |
| D11 | ai/AGENTS.md | five standalone AI containers, CLIP ViT-L, TRITON_ENABLED | one ai-gateway; SigLIP2-base 768-dim; gating gone. ai/gateway/ has no AGENTS.md |
| D12 | ci.yml PYTHON_VERSION 3.11 (pyproject >=3.14; .python-version 3.14) | CI python 3.14 | one workflow drifted |
| D13 | scripts/restart-all.sh + setup.py URL writes | per-model services restartable | names no longer exist |
| D14 | scripts/validate.sh:274 pytest step | "tests skipped if services down" | explicit path overrides pyproject testpaths → whole backend tree incl. integration with 5s timeout; DB-backed guaranteed fail (blocker-audit, verified) |
| D15 | backend/tests/conftest.py:578 | skips without DB | RuntimeError hard-fails collection; isolated_db fixture visible to all backend/tests |
| D16 | scripts/validate.sh:123 container discovery | finds DB containers | greps `_postgres_` (podman-compose v1 spelling); docker compose v2 names are `project-service-1` — depends on provider (P2 records identity) |
| D17 | backend/tests/load/test_performance.py:155 | load tests opt-in | no `load` marker on module → runs in default validate.sh gate w/ hardcoded p99<50ms budgets tuned on different CPU |
| D18 | docker-compose.prod.yml:384 comment | ":U ignored by Docker (backward compatible)" | comment false — but M1 unaffected: :U lines only on ai-llm-vllm hf_cache (never starts in M1) + frontend_certs; reproduction: docker compose 2.40.3 ACCEPTS :U on named volumes (verified /tmp/uprobe) |
| D19 | .env.example:58 TMPDIR=/ephemeral/podman-tmp | valid tmp | /ephemeral does not exist on this host — FIXED Task 3 template delta |
| D20 | backend/tests/unit/api/routes/test_system.py:2655 | health latency <100ms absolute | wall-clock asserts on a different CPU class — watch in Task 7 triage |
| D21 | backend/tests/benchmarks/test_memory.py:145 | memray opt-in | skip guard is OS-only; limit_memory markers activate without --memray flag; aarch64+mimalloc interaction — watch Task 7 |
| D22 | .github/workflows/gpu-tests.yml:15 | GPU suite runnable | runner labels [self-hosted, gpu, rtx-a5500] — no GB300 label exists; exit-5 tolerated = "nothing ran" reads as success (M2) |

## M2 forward-looking notes (do not act in M1)
- llama.cpp Dockerfile default arch `75,80,86,89` (no Blackwell); pinned commit b7972; CUDA_ARCHITECTURES already plumbed (compose:136); setup.py --defaults already detects cc via nvidia_detect (verified: '10.3')
- TensorRT engines arch-bound → re-export via ai/gateway/export/export_all.sh on GB300; fresh cache ⇒ "degraded" health is expected until export completes
- discard on any GPU host move: triton-kernel-cache, llama-cache, llama-nv-cache, AI_MODELS_PATH/triton
- NVFP4 (Blackwell-native) was ruled out for A5500 in compose comments; likely right on GB300; unknown = vLLM Mamba-arch bug
- clip_text + stgcn_action are KIND_CPU → Grace-NEON perf question, not Blackwell
- health flags mask degradation: AIFallbackService default score 50 + READINESS_REQUIRE_PIPELINE_WORKERS=false (compose:497) → M2 gate must prove real inference

## Probe Log
<!-- Task 1 appends rows here: date | probe | provider | result | decision -->

| date | probe | provider | result | decision |
|---|---|---|---|---|
| 2026-09-12 | P0 `!override` parse (`/tmp/p0probe`: `podman compose -f base.yml -f over.yml config`) | docker compose v2.40.3 (podman 4.9.3 external provider) | override-parseable-yes. Resolved service `a` shows `depends_on: c: {condition: service_started, required: true}` and no `b`; no YAML tag error | Task 4 MAY use `depends_on: !override`. Two-phase bring-up stays primary (spec 3.2) |
| 2026-09-12 | P1 CDI GPU visibility (`podman run --rm --device nvidia.com/gpu=all docker.io/nvidia/cuda:13.0.0-base-ubuntu24.04 nvidia-smi ...`) | podman 4.9.3, CDI | cdi-gpu-visible. Output `NVIDIA GB300, 10.3`; tag resolved for arm64, no substitution needed; exit 0 | Record-only, non-gating for M1. M2 GPU lanes may assume `--device nvidia.com/gpu=all` works host-side |
| 2026-09-12 | P2 provider identity + prod file parse (`podman compose -f docker-compose.prod.yml config -q`) | docker compose v2.40.3 (`Executing external compose provider "/usr/libexec/docker/cli-plugins/docker-compose"`) | FAIL as written: `required variable POSTGRES_PASSWORD is missing a value` (host has no `.env`). Same command with `PODMAN_SOCKET` and `POSTGRES_PASSWORD` supplied: exit 0, config-ok. `podman --version` = 4.9.3, `podman compose version` = `Docker Compose version 2.40.3+ds1-0ubuntu1~24.04.1` | P2 = provider + config-ok. The as-written FAIL is missing env, not a compose defect; do not read it as one. Consequence for D16: active provider names containers `project-service-1` (compose v2 spelling), so validate.sh:123 `_postgres_` grep cannot match on this host (re-confirmed at Task 2, 2026-09-12) |

## Convergence Queue
<!-- additive-only fixes that graduate into prod files once arch-neutral proven -->
- C1: prometheus rule mounts (Task 4 override) → docker-compose.prod.yml once M1 green
- C2: .env.example four vars (Task 2) — already prod-file-neutral; stays
