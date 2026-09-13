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

### Port map (generated .env) — 2026-09-12, Task 3

Generated by `setup.run_defaults_mode()` + `generate_env_content()` (never `setup.py main()`), then
`env-templates/gb300.env.template` deltas. Host listens on 22 53 111 631 1883 3000 4000 8000 39929 44744 61122.
Exactly ONE port moved vs `.env.example`: `API_PORT` 8000→8001 (`:8000` held by co-resident dgx-inference-vllm).
`ALERTMANAGER_PORT` was expected to move (blocker-audit predicted :3000) but did NOT — :3000/:4000 are bound on
192.168.1.186 (LAN), not loopback, and setup.py's probe is loopback-only; compose binds alertmanager to
127.0.0.1:9093, which is free. Guarded against collision: `podman compose -f docker-compose.prod.yml config -q`
→ exit 0 (also closes P2's as-written FAIL, which was just the missing `.env`).

| var | value | localhost bind check |
|---|---|---|
| `GO2RTC_API_PORT` | 1984 | free |
| `GRAFANA_PORT` | 3002 | free |
| `LOKI_PORT` | 3100 | free |
| `PYROSCOPE_PORT` | 4040 | free |
| `JAEGER_OTLP_GRPC_PORT` | 4317 | free |
| `JAEGER_OTLP_HTTP_PORT` | 4318 | free |
| `FRONTEND_PORT` | 5173 | free |
| `POSTGRES_PORT` | 5432 | free |
| `REDIS_PORT` | 6379 | free |
| `JSON_EXPORTER_PORT` | 7979 | free |
| `API_PORT` | **8001** (was 8000) | free |
| `FRONTEND_HTTP_PORT` | 8080 | free |
| `CADVISOR_PORT` | 8083 | free |
| `LLM_PORT` | 8091 | free |
| `FLORENCE_PORT` | 8092 | free |
| `CLIP_PORT` | 8093 | free |
| `ENRICHMENT_PORT` | 8094 | free |
| `YOLO26_PORT` | 8095 | free |
| `ENRICHMENT_LIGHT_PORT` | 8096 | free |
| `FRONTEND_HTTPS_PORT` | 8444 | free |
| `GO2RTC_WEBRTC_PORT` | 8555 | free |
| `PROMETHEUS_PORT` | 9090 | free |
| `ALERTMANAGER_PORT` | 9093 | free |
| `NODE_EXPORTER_PORT` | 9100 | free |
| `BLACKBOX_EXPORTER_PORT` | 9115 | free |
| `REDIS_EXPORTER_PORT` | 9121 | free |
| `ELASTICSEARCH_PORT` | 9200 | free |
| `DCGM_EXPORTER_PORT` | 9400 | free |
| `ALLOY_UI_PORT` | 12345 | free |
| `JAEGER_UI_PORT` | 16686 | free |

Blind spots (same class as D3): `generate_env_content` emits no line for `AI_GATEWAY_PORT` (8090),
`AI_GATEWAY_METRICS_PORT` (8002), `TEMPO_PORT` (3200), `VLLM_PORT` (8097), `FRONTEND_INTERNAL_PORT` (8080)
even though compose references them — every reference carries a `:-` fallback matching `.env.example`, and
all four host-bound ports are free, so no collision in M1. Recorded, not fixed (spec §5 M1).

Non-port deltas applied: `GPU_AI_SERVICES=0`, `GPU_LLM=0` (single GB300 — there is no GPU 1),
`CUDA_ARCHITECTURES=103` (host cc 10.3; never 89), `PODMAN_SOCKET=/run/user/1000/podman/podman.sock` (real
socket), `TMPDIR=/home/msvoboda/.cache/nemotron-tmp` (`.env.example`'s `/ephemeral/podman-tmp` does not exist — D19),
`FOSCAM_BASE_PATH`/`AI_MODELS_PATH` redirected to `~/.local/share/nemotron/*` (generation defaults `/export/*`
belong to a co-resident install, uid 1001; `foscam-init` chowns `-R` whatever `FOSCAM_BASE_PATH` names).
`HOST_UID/HOST_GID=1000`; `.env` mode 600; secrets generated (values not recorded here).

### Phase A bring-up (2026-09-12) — 15 services via `podman compose -f docker-compose.prod.yml -f config/docker-compose.gb300.yml`

Provider note: `podman compose` delegates to docker-compose v2.40.3 against the **rootless podman
socket** — all 15 containers live in podman's DB (`podman ps`), while `docker` CLI talks to the
co-resident **rootful dockerd** (dgx-inference). The two daemons share host ports: a stray
dockerd-side container on :9100 caused one spurious `rootlessport ... bind: address already in use`
during bring-up (removed; dockerd now holds only dgx-inference-*).

First pulls: all 16 registry images (15 bases + grafana base) pulled clean on arm64, zero errors;
grafana + pyroscope built local (`build --no-cache`, exit 0). `up -d` attempt 5: **UP_EXIT=0**.

| service | status | health |
|---|---|---|
| postgres | Up | healthy |
| redis | Up | healthy |
| foscam-init | Exited (0) | (one-shot chown, by design) |
| go2rtc (`hsi-go2rtc`) | Up | healthy |
| prometheus | Up | healthy |
| grafana | Up | healthy |
| loki | Up | healthy |
| tempo | Up | healthy |
| alloy | Up | healthy |
| alertmanager | Up | healthy |
| pyroscope | Up | healthy |
| node-exporter | Up | healthy |
| redis-exporter | Up | (healthcheck `disable: true` — plain Up correct) |
| json-exporter | Up | (no healthcheck defined — plain Up correct) |
| blackbox-exporter | Up | healthy |

Prometheus probes: `curl :9090/-/ready` → `Prometheus Server is Ready.` (exit 0); `/-/healthy` →
`Prometheus Server is Healthy.` (exit 0); config `lastError: ''`. All 7 rule_files resolve (Task 4
C1 mounts confirmed in-container).

`TARGETS-DOWN` (9, every one maps to an M1-absent service; nothing unexpected):

| job | reason |
|---|---|
| ai-llm-metrics | ai-llm absent in M1 (GPU) — DNS `no such host` |
| triton-metrics | ai-gateway absent in M1 (GPU) — DNS `no such host` |
| cadvisor | host.containers.internal:8088 refused — cadvisor not started in M1 |
| dcgm-exporter | host.containers.internal:9400 refused — no GPU stack in M1 |
| hsi-backend-metrics | backend absent until Task 6 — DNS `no such host` |
| hsi-health / hsi-telemetry / hsi-stats / hsi-gpu | via json-exporter → backend:8000 returns 503 from co-resident :8000 service until Task 6 |

`TARGETS-UP` (12 jobs incl. node-exporter after the delta below): alertmanager, blackbox-exporter,
blackbox-http-2xx/health/live/ready, blackbox-tcp (postgres:5432 + redis:6379 `probe_success=1`),
json-exporter, node-exporter, prometheus, pyroscope, redis. Note: blackbox-http-* jobs report
target `up` even while every `probe_success=0` (probe-failure is inside the exporter response) —
real probe targets (backend/ai-*/frontend) turn green with Task 6.

Findings:
- **NE-MOUNT (fixed additively, C3):** prod `/:/host:ro,rslave` fails ONLY through the
  compose→podman-API path (podman records bind Options `["bind"]` non-rbind + rslave; runc init:
  `mounting "/" to rootfs at "/host" ... MS_RDONLY|MS_BIND: invalid argument`; 3/3 deterministic;
  rw+rslave also fails; `podman run` CLI with the identical string succeeds — CLI vs API path
  differ). Overlay delta `/:/host:ro` (propagation dropped) starts + serves :9100/metrics,
  healthy (own commit `fix(gb300): node-exporter root bind without rslave (rootless compose)`).
  **M1 degradation:** rslave only provided live mount propagation — host mounts created AFTER
  node-exporter starts won't appear in its filesystem collector until node-exporter restarts.
  Controller independently reproduced the EINVAL standalone and ruled this fix (2026-09-12).
  Host-state observation during bring-up: attempt 3 hit `rootlessport listen tcp 127.0.0.1:9100:
  bind: address already in use`. Cause: a DEBUG container accidentally created in the co-resident
  rootful dockerd (docker CLI defaults there; project lives in rootless podman) held host :9100 —
  the two daemons share host ports. Removing the dockerd-side container freed it (verified via
  `ss`) before the final up; no netavark reservation leak remained, so the controller's ordered
  remedy (project-scoped `podman network reload --fresh` + orphan-rootlessport hunt) was not
  ultimately needed. Not blocking; lesson: debug this stack with `podman`, never bare `docker`.
- **alloy UI unreachable on host:** alloy binds 127.0.0.1:12345 *inside* the container, so the
  rootless port-forward connects-then-resets (`curl` → connection reset). Healthcheck is
  `pgrep -f alloy` → healthy; OTLP 4317/4318 bind 0.0.0.0 (forwarded fine). Cosmetic host-access
  gap only.
- **alloy eBPF profiler gives up:** `pyroscope.ebpf.native_profiling` → `map create: operation not
  permitted (MEMLOCK ...)` after 4 tries — expected under rootless without BPF/cap privileges;
  recorded, non-gating (M2 lane if eBPF profiling wanted).
- **go2rtc / loki / tempo / pyroscope** host probes OK (`/api/streams` 200, `/ready` 200s;
  pyroscope `/healthy` 301→index, container healthcheck green).

## Convergence Queue
<!-- additive-only fixes that graduate into prod files once arch-neutral proven -->
- C1: prometheus rule mounts (Task 4 override) → docker-compose.prod.yml once M1 green
- C2: .env.example four vars (Task 2) — already prod-file-neutral; stays
- C3: node-exporter `/:/host:ro` (drop rslave; rootless-podman compose-API EINVAL, see Phase A
  findings) → prod file only if amd64 rootless users hit it; rootful keeps working either way

## M1 Task 7 close-out — owner-ruling fixes (2026-09-13)

Three uncommitted owner-ruling fixes verified + committed separately (each with repro/verification):

| # | Fix | Commit | Verification |
|---|---|---|---|
| F1 | `backend/main.py` — `zones_redirect_router` registered AFTER `zone_anomalies`/`zone_household`; the /api/zones→/api/analytics-zones 308 (NEM-5377, 89b2001b) shadowed `/api/zones/{zone_id}/household*` (Zone Trust Matrix broken) | dfa8bc0c | Repro: with fix stashed, `test_zone_household_api.py::test_get_config_returns_config_when_exists` fails `assert 308 == 200`; with fix, all 32 tests in `test_zone_household_api.py` pass (count of 32 confirmed). Redirect itself still pinned by `test_zones_redirect.py` (11 unit tests, router mounted alone — no full-app ordering test exists; see F2-adjacent gap below) |
| F2 | `backend/services/threat_monitor_service.py` `_check_cooldown` — cutoff kept tz-aware; naive datetimes bind as server-LOCAL vs timestamptz, shifting the cooldown boundary by the local-UTC offset (4h on EDT) so cooldown never matched | 5ccb3645 | Numeric demo: naive-as-EDT cutoff 09:40Z vs aware 05:40Z (4h error). 148 unit tests pass under UTC and `TZ=America/New_York`; existing unit tests mock the session so they don't discriminate (gap recorded) |
| F3 | `backend/tests/integration/test_api_protection.py` — session-cookie/setup_required/409/503-body contract repair + `unmocked_setup_client` fixture; two tests asserted unobservable contracts (503 through guard-mocked client; `/api/auth/me` + X-API-Key → 200, unachievable: `get_current_user` is cookie-only, no path validates DB-created keys, AuthMiddleware disabled NEM-5527) | 294d1a7f | File 15/15 pass (was 13P+2F). API-key test now asserts shipped contract: creation 201 + `nemo_k1_` format + settings-listed key authenticating `POST /api/system/cleanup?dry_run=true` (side-effect-free `verify_api_key` route) |

Environment deltas (this sandbox, not GB300): `libgl1` + `libglib2.0-0t64` required for backend
imports (cv2 import chain from auth_service module graph); integration tests run via
**testcontainers** here (no podman/no .env — postgres+redis containers start fine); sandbox
postgres at host.docker.internal:5432 is the co-resident dgx stack (credentials unavailable,
not the test DB) — do not probe it further.

### Sibling bugs of the F2 class (recorded, NOT fixed — M2 candidates)
- `backend/services/alert_engine.py:994` — `utc_now_naive()`-derived cutoff (naive) compared
  to timestamptz `Alert.created_at`: same asyncpg local-time encoding; on non-UTC host engine
  cooldown never matches → duplicate alerts. Unit tests pass aware datetimes (:788,:801,:819)
  into the same signature — contract inconsistent, masked by mocks.
- `backend/services/alert_engine.py:600,626` + `backend/models/dwell_time.py:124` —
  `utc_now_naive()` passed as `current_time` into `calculate_dwell_time` for active records
  (exit_time IS NULL → aware from timestamptz): naive − aware → TypeError at runtime. No test
  pins the mixed-arithmetic path.
- `backend/tests/integration/test_alert_engine.py:1082,1116` — fixtures write naive
  `created_at` into timestamptz; cooldown tests mis-evaluate on non-UTC hosts.
- Gap: no test pins the tz-aware cutoff contract for `_check_cooldown` (unit tests mock the
  session; integration tests exercise real comparison but pass either way on UTC hosts).
  `backend/tests/integration/test_alert_engine.py` fixture naive timestamps are the same class.

### Verification-scope note
Testcontainers can exercise the DB-backed suites in this sandbox; the full no-flag
`validate.sh` gate requires the Phase A container topology for container discovery
(D16) — see close-out rows below for how the gate is run here.
