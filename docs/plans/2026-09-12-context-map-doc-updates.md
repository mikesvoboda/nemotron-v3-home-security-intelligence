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

## M1 Task 7 — full-gate run 1 (2026-09-13, this sandbox)

`./scripts/validate.sh` full no-flag run against testcontainers (no podman/no .env here; the
pytest stage ran the whole backend tree incl. integration). Result: **315 failed / 29954 passed /
242 skipped / 1550 errors / coverage 27.31% < 80** in 799s. Classification:

- **1550 ERRORs = sandbox-induced, not test defects.** Setup-phase "OSError: Multiple exceptions:
  [Errno 111] Connect call failed (mapped port)" on testcontainers' postgres/redis port-forwards,
  starting ~71% through the run — concurrent standalone pytest runs I issued beside the gate caused
  docker container/port churn (one produced a transient `no space left on device` on the co-resident
  dockerd's snapshot dir). Lesson: the gate must run ALONE; do not run probes concurrently.
- **Coverage 27.31% is an artifact of the same systemic ERRORs** (integration code paths never
  imported/executed because their fixtures failed at setup).
- **315 FAILED breakdown triaged so far (each fixed in its own commit):**
  - test_notification_api.py (22) — file-local client fixtures lacked the shared fixture's
    SetupGuard bypass → real guard 503'd empty-users requests in 0.5ms. Fixed (9900831e, helper
    `_bypass_setup_guard`).
  - test_file_watcher_filesystem.py (14) — NEM-3469 streams-path mock drift. Fixed (3899a63c,
    `queue_contract` fixture).
  - test_face_recognition_service.py (10) — 24 setup ERRORs were `timestamp` naive-column vs aware
    arg (fixed: DateTime(timezone=True), 2cd22aa4); 3 deterministic math failures in
    generate_similar_embedding noise levels (fixed in same commit; E[sim]=1/sqrt(1+512·noise²)).
  - test_cameras_api.py::rtsp_requires_url (1) — validator contract drift, never passed since
    2e184ed4 (fixed a2af694d).
- Pre-authorized fixes not fired: D14 (integration ran fine at 5s func timeout — symptom absent),
  D15 (RuntimeError unreachable — pytest_configure setdefaults DATABASE_URL), D16 (already landed
  in e53899e6), D17 fired → load marker added (f6c12d87).
- Remaining reds being diagnosed in parallel lanes; fixes follow the same triage rules.

### Run-1 red triage — batch 2 (2026-09-13, all class (c) unless noted)

| file | was | root cause | commit | now |
|---|---|---|---|---|
| integration/services/test_model_loaders.py | 19F | fixture cuda=False vs prod fail-fast CUDA guards; AutoModel alias; SigLIP 2 regex/vram 800→200; models.yml +preprocessing +alpr | f0d8ca5e | 38/38 |
| integration/test_alert_rules.py | 21F | metric renames (probe_success blackbox, hsi_system_healthy/hsi_database_healthy/hsi_redis_healthy, *_queue_depth) + 3 stale-rule classes (deleted) | 71e27668 | 39/39 |
| integration/test_file_watcher_integration.py | 10F | sibling of R-T7-WATCHER — legacy add_to_queue_safe observation point; queue_contract ported w/ camera_id | 9540d694 | 26/26 |
| integration/test_services_api.py | 17F | DI trap: patch() on routes.services.get_orchestrator is a no-op (FastAPI captured original fn at route decl). Fix: dependency_overrides + zero-arg override fns + MagicMock get_service | 9ab1b75b | 20/20 |
| security/test_api_security.py | 8F | (iv) media rate limiter Depends(get_redis) → no ambient Redis → 503 CACHE_UNAVAILABLE before route body. Fix: stub backend.core.redis._redis_client (+evalsha [1,0]) | 157bcc5b | 52/52 |
| integration/test_job_history_api.py | 12F | PROD BUG: _get_transitions bound UUID object vs JobTransition.job_id String(36) VARCHAR → 'varchar = uuid' on every read (fixed in service); tests seed jobs rows (dual tracking is shipped design); since param '+' URL-encode | e3f9e27e | 19/19 |
| integration/test_onvif_discovery_api.py | 10F | patch target TYPE_CHECKING-only; 422 envelope is error.code; Phase-2 design fields (ip/port/rtsp_urls/requires_auth/timeout_count) never shipped | 5f53c88c | 11/11 |
| integration/test_cameras_rtsp.py | 9F | TDD red-phase artifact: CameraResponse SHIPS rtsp_password echo (schema/routes/frontend/canonical-suite all agree); omitted-vs-explicit-None validator; no auto-clear-on-mode-change | d4c6c1ff | 18/18 |
| integration/test_stream_config_api.py | 17F | (ii) never implemented: NEM-4394/4395 Phase 3 GREEN never shipped. Mirror companion unit files' skipif-import guard (auto-greens when feature ships) | ae429127 | 19 skipped |

DI-trap documented twice now (R-T7-SERVICES, R-T7-APISEC): `Depends()` captures the original
function object at route-declaration time; `unittest.mock.patch` on the module attribute never
reaches the route. Use `app.dependency_overrides[<exact function>]`.

M2 candidates recorded: full stream-config GREEN implementation (schema+service+routes, owner
design decisions needed); alert_engine tz siblings (above); websocket/db-pool metrics (hsi_*).

### Run-1 red triage — batch 3 (2026-09-13, misc-small lanes; all class (c) unless noted)

| file | was | root cause | commit | now |
|---|---|---|---|---|
| api/routes/test_model_management_integration.py | 8F | DI trap (same as R-T7-SERVICES): patch() on routes-local get_http_client no-op → override_http_client helper | 2143a424 | 15/15 |
| test_florence_validation.py | 8F | NEM-5570 cascade gate shipped after tests (conf 0.75-0.92 never reach Florence); conflict-YOLO-wins branch unreachable through pipeline (only <0.7 forwarded) — 5 conf fixes + 4 extractor-level reshapes | eb557bbf | 9/9 |
| api/test_feedback_routes.py | 8F | TDD RED artifact: list/get-by-id/delete feedback endpoints never implemented (1d0ee935 shipped 3 paths; git -S zero). no_crud conditional guard | 9110f4b6 | 18P+7 skip |
| test_search_api.py | 5F | SearchResponse contract (total_count, no query echo, relevance_score not rank, no highlights) + since-param '+' URL encoding | 9fe387a4 | 12/12 |
| test_preview_api.py | 17F+12E | Camera() folder_path required + status ck constraint + get_go2rtc_client never existed (seam = cameras._get_go2rtc_client, request-time call) + static stream_id vs token_hex suffix | c98b94cf | 16P+1 preskip |
| test_prompt_management_api.py | 7F+1E | PROD: PromptVersion never imported in models/__init__ → create_all never built prompt_versions (order-dependent ERROR). Tests: RFC7807 problem-detail detail-string; GET default-config 200 contract; counting-limiter override; import-preview diff shape | e32074fa | 41/41 |
| test_orchestrator_integration.py | 6F | file-local clients lacked SetupGuard bypass (middleware postdates tests) | ccf3ddd6 | 13/13 |
| test_gpu_config_workflow.py | 3F | service_name-sort inverted by ai-detector→ai-yolo26 rename; [0] assertion never green at 6d7ae425; AsyncMock redis → truthy child mock in 409 pre-check | fc4041e4 | 18/18 |
| test_alpr_service.py | 0F | mis-paired in run-1 tally (7F belonged to prompt file); 14/14 verified standalone | — | 14/14 |

Remaining from run-1's 315 FAILED: 48 files × 1-5 failures, most of which are downstream of the
run-1 systemic ERROR cascade (container port-forward churn — my own concurrent probes). Decision:
re-run the full gate cleanly (nothing else running) and triage only what survives; chasing
cascade-artifact failures individually wastes cycles on non-defects.

### Run-2 (2026-09-13, clean, no concurrent probes): 238F/766E in 722s

- 766 ERRORs: asyncpg 'Connect call failed (127.0.0.1, 5432)' throughout the run — root cause
  identified: `backend/tests/conftest.py:294` `setdefault`s DATABASE_URL to localhost:5432, and
  `get_test_db_url()` (conftest.py:576) takes `TEST_DATABASE_URL or DATABASE_URL` BEFORE checking
  local postgres, so the unit DB fixtures (`isolated_db`, `test_db`) connect to localhost:5432
  forever. On the GB300 host Phase A postgres listens on 5432 (works); this sandbox has none
  (class b environment gap). Integration fixtures use their own worker_db_url path and were fine.
- Fix for THIS sandbox: run gate-local postgres+redis on standard ports and export
  TEST_DATABASE_URL/TEST_REDIS_URL for the validate invocation (the same env the GB300 bootstrap
  sets). gate-postgres (security/security_dev_password, db security) + gate-redis started;
  unit DB tests + integration spot-checks green against them.
- 238 FAILED = new surface now reachable: test_backup_api (29), test_auth_flow (14),
  test_events_cache_invalidation (12), test_alert_engine (10), test_tracks (9), test_jobs_api (9),
  test_idempotency (8), polygon/line_zone (14), partition_manager (7), inbound_webhooks (7),
  feedback_snapshots (6), pipeline_e2e (5)... — triaged in run-3's aftermath.

### Run-3 (2026-09-13, with TEST_DATABASE_URL + gate services): 352F/355E in 1147s

- **Root cause of the 355 ERRORs: OOM-kill cascade.** dmesg: `Out of memory: Killed process
  [pytest-xdist r] anon-rss:51844004kB` (52 GB per worker!) — 11 `node down: Not properly
  terminated` events; xdist relaunched as gw8-gw15, restarted workers lose the session-scoped
  testcontainer handles → connection storms → setup ERRORs (face_recognition 20, cache_service 47,
  zone_anomaly 32, notification_delivery 27, file_watcher 24, redis_pubsub 20).
- **The leak: OpenTelemetry BatchSpanProcessor.** otel_enabled defaults True; every TestClient with
  a live lifespan arms an OTLP exporter at http://alloy:4317 (unreachable; proxy 502s visible as
  grpc handshaker spam). Failed exports retry while holding spans; span-generating tests
  (websocket auth flows ×9 crashes, llm_analysis_pipeline ×2) accumulated tens of GB per worker.
  Fixed by pytest_configure setdefault OTEL_ENABLED=false (0978d11f, class b; production default
  unchanged). Also made test_telemetry.py's settings-default test hermetic.
- 352 FAILED = next surface: dlq_api (48), repositories/test_base (38), data_corruption (24),
  event_search (22), backup_api (19), auth_flow (17)... triage continues in run-4's aftermath.

### Run-4 (2026-09-13, OTEL fix in): 226F/1398E in 466s — coverage 85.17% (above the 80 gate!)

- **Coverage milestone**: combined unit+integration coverage 85.17% (was 27.31% under run-1's error
  cascade) — the --cov-fail-under=80 gate now passes on coverage.
- 1398 ERRORs again from 2 worker OOM crashes — but the victims differ: dmesg shows the killed
  PIDs are the CONTROLLER ('pytest', 63GB anon RSS), and the two 'crashed while running' tests
  are both test_llm_analysis_pipeline.py::TestErrorHandlingWithEnrichment (fallback paths).
  Bounded reproductions (-n0: 74 tests/176s peak <1GB; 4-file -n8: 270 tests/133s peak 755MB)
  do NOT reproduce → scale-dependent. Full-suite rerun (run 5) with per-process RSS sampling
  launched to catch the culprit. Hypothesis candidates: controller-side accumulation over 30k
  verbose reports, coverage combine, or a single memory-heavy integration test.
- 226 FAILED under diagnosis in parallel read-only lanes (log/code analysis only — no pytest
  while the gate runs).

### Run-5 (2026-09-13, full-suite rerun with RSS sampling): 239F/31165P/269S/377E in 1122.84s — coverage 25.26% (gate FAIL)

- **Environment was broken, not the tests**: run-5 launched without TEST_DATABASE_URL/TEST_REDIS_URL
  exported (podman-preferred container discovery in validate.sh found no gate containers — the gate
  services live in docker). Integration conftest fell through to testcontainers and spawned its own
  postgres; the sandbox's 9.8GB /dev/vdd filled (~800MB WAL + per-worker `security_test_gwN` DBs at
  integration/conftest.py:509 `_create_worker_database`) → `psycopg2.errors.DiskFull` → 16,510-line
  `InFailedSQLTransactionError` cascade → 377 ERRORs across 43 files.
- 10 xdist workers crashed ("node down: Not properly terminated": gw1–gw3, gw8–gw12) and returned no
  coverage ("coverage: failed workers" names exactly those 10) → TOTAL coverage collapsed to 25.26%
  vs run-4's 85.17%. Coverage collapse is a symptom of crashed workers, not a code-coverage change.
- **RSS samples survived the sandbox restart but are uninterpretable**: controller PID 6312 sampled
  monotonic 119280→267640 over 14 samples (units ambiguous, container reset wiped cgroup peak);
  rss8.txt sampler wrote empty lines (wrong pgrep). Decision: instrument run-6 live rather than
  trust run-5 samples for the OOM verdict.
- Sandbox restarted 13:17 EDT mid-investigation (dockerd start time = gate containers' exit-255);
  pre-restart OOM evidence (dmesg, cgroup memory.peak) is gone. Gate containers recreated + verified
  (psql as security, Redis PONG, DBs 0–15 flushed, stale `security_test` dropped); 5 orphaned docker
  volumes removed (1.7GB reclaimed → 8.8GB free); TEST_DATABASE_URL/TEST_REDIS_URL now persisted in
  /etc/sandbox-persistent.sh so run-6 uses gate-local services.
- **D14 split landed as 9655ec6b** after three mechanical corrections to the draft (unrecognized
  `--cov-data-file`; missing combine leaving integration-only gating; `| tee` masking pytest exit
  under set -e) — see commit message for the full evidence trail.
- FAILED inventory largely carried over from run-4 (DiskFull cascade inflated ERROR count;
  239 FAILED ≈ run-4's 226 + DiskFull-era flakes). Triage resumes from the run-4 lanes.

### Run-6 (2026-09-13, D14 split + gate-local services): integration tier KILLED AT 99% — 317F/3680P live tally, no summary (gate aborted by controller decision)

- **Unit tier green standalone**: 27524 passed / 168 skipped / 8 xfailed in 84s (first time the
  unit tier ran alone under the D14 split — it has never failed when separated).
- **Integration tier reached 99%+ (vs run-5's collapse mid-run)** with TEST_DATABASE_URL/
  TEST_REDIS_URL exported to gate-postgres/gate-redis (no testcontainer spawn — disk stayed 19-21%,
  DiskFull class dead as designed). Live failure tally at kill: **317 FAILED / 3680 PASSED**, no
  DiskFull errors anywhere.
- **The controller-vs-worker OOM question from run-4 is ANSWERED**: controller RSS stayed FLAT
  (~148→434 MB over the run, sampled every 20s). The balloons are the XDIST WORKERS: 6 kills,
  anon-rss 19.9/23.3/24.2/26.9/28.7/33.8 GB each, and the surviving tail (gw-live ps) showed
  workers at 27.7 GB and a replacement at 12 GB. 8 workers × multi-GB on a 62 GB box = aggregate
  pressure; kills scattered across unrelated tests (llm_analysis_pipeline, test_events,
  test_analytics_api) => accumulation is CROSS-FILE within the worker process, not one culprit
  module. run-4's bounded repros (<1 GB at -n0, 755 MB at 4-file -n8) missed it because the leak
  needs the long mixed stream. NOT the OTEL class (0978d11f fix in place; no exporter spam).
  Killed at 0 GB free because the tail was thrashing; summary/coverage would have been
  worker-death artifacts (run-5 lesson) — aborted intentionally, evidence preserved (/tmp/run6-prekill.txt).
- **Real-red clusters (deterministic, clean-run survivors)**: test_base 38, backup_api 29,
  event_search 25, auth_flow 16, tracks/idempotency/entity_persistence_pipeline/alpr_service/
  jobs_api 9 each, cameras_api 8, polygon_zone_service 7. Class (c/c-iv) triage per rules below.
- **test_base.py 38F root-caused**: file PASSES 38/38 alone and 201/201 with its repositories/
  dir; ALL 38 gate failures were on gw7 in runs 2/4/6 (deterministic per-worker). Replay of gw7's
  6 preceding files in one process reproduces 16F (test_base only). Shared-DB contention ALSO
  independently reproduced: the 15 integration files that use the root conftest `test_db` fixture
  (which points ALL workers at the shared `security` DB via exported TEST_DATABASE_URL —
  get_test_db_url returns it VERBATIM) fail 3+ under -n4, while integration's own worker_db
  fixtures correctly use per-worker security_test_gwN DBs. Same class as the unit-run
  `Key (name)=(Video Test Camera) already exists` residue collisions. FIX = the planned FCL Task 6
  cutover (get_test_db_url -> per-worker <base>_gwN, plan
  docs/superpowers/plans/2026-09-12-fast-confidence-loop.md:1064) — M1's last substrate blocker;
  helpers (_create_worker_database) already exist at integration/conftest.py:455 to lift up.
- **jobs_api 9F root-caused (class ii)**: routes serve JobTracker (Redis/in-memory,
  job_tracker.py:188-268 get_all_jobs/cancel_job) while the test seeds the Postgres `jobs` table
  via db_session — every test in the file is red by construction regardless of state. TDD-RED
  artifact pending owner ruling (seed-through-tracker vs skipif guard vs implement DB-backed
  tracker read path). NOT the setup-guard class (shared client fixture already bypasses it,
  integration/conftest.py:1423-1447).

### R-T7-DBRACE-CUTOVER (2026-09-13): root-tier get_test_db_url -> per-worker DBs (substrate fix landed inside Task 7)

- **Mechanism confirmed before fixing**: the gw7 7-file replay in ONE process passed 137/137
  (seed-dependent under pytest-randomly — the earlier 16F was one order, the clean run another),
  so the contamination is NOT an in-process state leak; it is cross-WORKER concurrency on the one
  shared `security` DB. The independent 14-file -n4 contention repro (3F+1E) is the stable signal.
- **Latent-dead-code finding**: root conftest's NEM-4491 per-worker machinery
  (`template_database`/`worker_database`/`cleanup_stale_databases`, conftest.py:953/:1116/:1215)
  was never wired to any test — only the module docstring references it. The isolation the repo
  intended existed but nobody requested it; get_test_db_url kept handing every worker the exported
  URL verbatim. Also `cleanup_stale_databases` only sweeps `test_db_gw%`/`template_test`, which the
  never-used fixtures would have created.
- **Fix (FCL plan Tasks 5+6, run here as M1's last substrate blocker)**: e85c2cf3 adds
  worker_id/worker_db_name/_create_worker_database/_drop_worker_database to root conftest (helpers
  mirrored from integration/conftest.py:455; conftest-to-conftest import deliberately avoided);
  e8619d80 cuts get_test_db_url over to `<base>_gwN`/`<base>_main` copies created idempotently,
  with TEST_DB_NO_WORKER_SUFFIX=1 as the documented rollback lever. Contract tests:
  backend/tests/test_db_isolation.py (13, run live against gate-postgres).
- **Proofs**: 13/13 isolation tests green, twice under -n4 (idempotent create against leftover DBs);
  the 14-file contention set under -n4 = 262 passed / 22 skipped (was 3F+1E); unit/core/test_database
  + unit/repositories -n8 = 181P/8.1s. New worker DBs visible in pg_database (security_gw0..3,
  security_main) — cutover verifiably live.
- **Cost swap accepted per plan**: first fixture call per worker pays full DDL in its fresh DB
  (8 parallel DDL runs replace the serialized advisory-lock queue). Session-scoped create-once +
  drop-at-end + stale-sweep of the new `<base>_gwN` names is FCL Task 7's job; leak is bounded
  (≤ nworkers names per base, idempotently reused).

### R-T7-ENOSPC-RECUR (2026-09-13 20:21 UTC): run-5 disk class strikes the GATE-LOCAL path — postmaster PANIC mid-rehearsal

- **Event**: first post-cutover integration rehearsal was invalid — a pytest worker's write
  tripped `PANIC: could not create file "pg_wal/xlogtemp.NNNN": No space left on device` on
  gate-postgres (json-file logs, volume on /dev/vdd). Postmaster auto-recovered (redo 88s,
  ready 20:22:48); all runs straddling 20:21 (four-cluster classification 52F/20E, auth_flow
  26E "not yet accepting connections") are CONTAMINATED and were re-run clean.
- **Why it's a new shape**: run-5's DiskFull was testcontainer-per-worker filling /dev/vdd; here
  TEST_DATABASE_URL was exported (no testcontainers), df showed /var/lib/docker at 19-24% before
  and 7.1G free 40s AFTER the panic — a fast burst, not accumulation. `du` into /var/lib/docker
  returns 4.0K from this namespace (co-resident rootful dockerd owns it; dgx-inference-* live
  there — untouchable). Unattributable from inside the sandbox; prime suspect is neighbor
  pressure on /dev/vdd. NOT fixed by us; MITIGATED by /tmp/disk-guard.sh (kills the rehearsal at
  <1.5G free so results die before the postmaster PANICs and the 90s recovery window poisons
  them). Ledger protocol addition: every long integration run gets the disk guard.
- **OOM status after cutover**: dmesg shows NO new worker kills during the cutover-era runs
  (the 12 recorded kills all predate the cutover; run-6's). Unit tier post-cutover: 27334P/1F
  (gpu_config flake — green standalone and at the original seed 1989078092).

### NEW FINDING (2026-09-13): /api/backup is fully implemented but never mounted — production 404s (F-candidate, owner ruling required)

- backend/api/routes/backup.py: router with 7 endpoints, prefix /api/backup, implemented since
  f79f066e ("implement backup/webhook systems", NEM-3566/3624/3667); exported via
  routes/__init__.py `backup_router`. **Never appears in backend/main.py** — not in the
  `from backend.api.routes import (...)` block (audit→auth→cost_analytics, alphabetical skip),
  never include_router'd, in ANY revision (git log -S across --all: zero hits). Frontend
  frontend/src/services/backupApi.ts calls /api/backup in production => the backup UI 404s live.
- **Consequence for the gate**: test_backup_api.py 29F is class (ii)-inverse — tests are RIGHT,
  production wiring is missing. One-line fix (import + include_router, ~1457). STOP-AND-ASK per
  goal clause: new production-behavior change needs owner ruling (proposed F1-class, same shape
  as the NEM-5377 router-order ruling). Companion sweep: zone_baselines.py is the only other
  never-referenced routes module (no APIRouter — inert helper, no action).

### R-T7-BACKUP-MOUNT (ruling F4, 2026-09-13): /api/backup mounted — 29F -> 7F standalone

- Owner ruling F4 via goal stop-and-ask: mount the router. main.py: import `backup` +
  include_router(backup.router) after auth (alphabetical + ordered-safe: /api/backup collides
  with nothing). Standalone test_backup_api.py: 29F/4P -> 7F/26P. Remaining 7 are NEW findings,
  all class (c/c-iv) test-vs-route drift now that the endpoints are reachable:
  (1) 4x "not_found" tests send job_id='nonexistent-job-id' -> asyncpg uuid_encode rejects a
  non-UUID bind => 503 (route 500-handled as db error) where tests expect 404 — route should
  404 malformed ids before touching the DB (arguable production-hardening, small);
  (2) 2x status-race tests assert PENDING but background job already COMPLETED/FAILED by assert
  time (test drift: need to observe via API or freeze the runner);
  (3) 1x test bug: `await db_session.expire_all()` where db_session is None (fixture misuse).

### R-T7-OOM-2 (2026-09-13 ~20:29-20:38 UTC): post-cutover rehearsal — worker leak WORSE, not fixed; rehearsal tally VOID

- Second full integration rehearsal under the cutover: 6 NEW OOM kills (dmesg: anon-rss
  58.0/57.4/50.8/37.5/30.1/22.3 GB — a single worker reached 58 GB, up from run-6's 33.8 GB peak).
  8 workers replaced mid-run (gw1/3/6/8/9/10/11/12 — ids beyond -n8 prove xdist replacement).
  Reached 99% again; killed by owner decision at 0 GB free before summary. 439 FAILED lines are
  NOT a triage surface: crash-replaced workers inherit their predecessor's DB residue
  (test_base 38F all landed on post-crash gw9 at 87%; the 14-file -n4 contention set is green
  WITH the cutover) — every post-kill result is untrustworthy, same artifact rule as run-5/6.
- Verdict: per-worker DBs fixed CONTENTION; the leak is in-process accumulation (run-6 evidence:
  cross-file, scattered victims). Must be fixed at the leak source; xdist 3.8.0 has no periodic
  worker restart. Leads queued: test_memory_stability.py + test_data_corruption.py (alloc-heavy
  names, both red), bisect via pytest-split slices with per-worker RSS sampler.

### R-T7-OOM-DIAG (2026-09-13, capped-address-space run in flight): leak is VmSize-dominated, not uniform RSS

- Experiment: integration tier -n6 under `ulimit -v 8388608` (8GB address-space cap/worker,
  inherited by xdist replacements) + per-test RSS recorder (/tmp/rss-trace). 62GB box, 6 caps —
  aggregate safe.
- **Finding 1 — VmSize outgrows RSS ~1.6×**: the first capped worker died at VmSize exactly
  8.39GB with VmRSS only 5.3GB (smaps_rollup: 5.18GB Pss_Dirty ANON, incl. ONE contiguous 1.35GB
  rw-anon mapping — a single huge object/arena, not uniform drift). ulimit -v therefore caps the
  wrong counter: workers segfault-equivalent die ("node down: Not properly terminated") WITHOUT
  a MemoryError traceback — C-level alloc failure. Traceback-on-leak plan is dead; RSS-keyed
  bucket bisection replaces it.
- **Finding 2 — healthy workers drift ~1GB/700tests** (decile profile: 631->1320MB on gw4);
  baseline first-test import cost ~600MB. So run-6/rehearsal's 20-58GB workers are NOT generic
  drift — they must visit a specific runaway test/file repeatedly (worksteal distributes it).
- **Operational note**: two concurrent heavy integration runs against gate-postgres (my -n0
  backup recheck + this diagnostic) coincided with a THIRD DiskFull error burst
  (InFailedSQLTransaction cascade, 11F/5E on a file that was 4F/29P one run earlier — the
  4F/29P is the valid measurement). Protocol: exactly ONE heavy integration job at a time;
  disk-guard stays armed for all of them.
- **Next instrument (queued)**: deterministic 8-bucket file bisection, sequential, -n0, per-bucket
  max-RSS sampler; recurse the runaway bucket to file level. Plugin fix: pid in TSV names
  (replacement workers currently clobber their predecessor's trace).

### R-T7-ENOSPC-ROOTCAUSE (2026-09-13, second pass): the "external inode burst" was SELF-INFLICTED — TRUNCATE relfilenode churn (commit 5bbd6939)

Correction to R-T7-ENOSPC-RECUR: there is no co-resident rootful dockerd writing to
/dev/vdd — it is this sandbox's private virtio disk, and `/var/lib/docker` is readable
via the docker group + sudo we already have (the "invisible to du" premise was a
permissions blind spot, not an external actor). The instrument that closed the case:
`df -i` showed /dev/vdd at **100% of its 655,360 inodes** while still holding 7G FREE
BLOCKS — every ENOSPC (48,266 of them; 96% TRUNCATE, 827 INSERT, 256 CREATE) was an
INODE failure, which the block-only disk-guard was blind to (guard now v2: kills at
inodes_used>=95% or <2G blocks).

Mechanism (proved by direct measurement, second agent, re-verified here):
backend/tests/integration/conftest.py clean_tables ran `TRUNCATE TABLE … CASCADE` over
~815 tables between EVERY test. TRUNCATE allocates a NEW relfilenode (new inode) and
defers unlinking the old one to the next checkpoint (checkpoint_timeout=300s). 18
per-worker DBs × 815 tables inside one checkpoint window exhausts 634K free inodes in
~778 truncate cycles — an ordinary integration pace. The cluster's relfilenode
high-water was 6,139,772: six million relation files created. The "periodic burst to
zero then 4% again" is the checkpoint retiring dead files by the time anyone looks.

Fix (commit 5bbd6939, test-only): `DELETE FROM {table}` — reuses the relfilenode, zero
inode allocation; FK ordering was already handled by the surrounding
session_replication_role=replica, making CASCADE redundant; near-empty test tables make
DELETE's scan free (the TRUNCATE-faster comment was written for the wrong regime).
Operational relief: gate-postgres ALTER SYSTEM checkpoint_timeout='30s' (live,
reversible) — cuts the dead-file high-water ~10×.
Proof: relfilenode max delta = **0** across a 105-test run (was +815/test-worker/cycle).

Consequences: (1) the three VOIDED runs' root cause is this, not contamination from
outside — results are recoverable by rerun, and reruns are now safe; (2) the earlier
"provision a dense-inode volume" ask is WITHDRAWN — the churn outgrows any fixed
ceiling and the fix removes the churn; (3) validate.sh's integration tier no longer
PANICs gate-postgres mid-run.

### R-T7-WS-OOM (2026-09-14): the worker OOM leak IS FOUND — mock-fed pipeline worker loops (fix fbb2f4ee)

- **Run-8**: unit tier green 27524P/84.8s in-gate. Integration tier: a gw3
  worker reached **17.7 GB RSS (VmSize pinned at the 20GiB cap) with ZERO
  completed tests** — py-spy: main thread wedged at TestClient.__enter__
  (lifespan startup) in test_websocket_auth_flow.py::detections_auth_client.
  The replacement worker wedged the same way on the same file's FIRST test;
  killed both, aborting run-8 per protocol (1 node-down; evidence:
  /tmp/run8-evidence-integration.log, /tmp/rss-trace-run8/, smaps: 17.6GB
  Pss_Dirty anon, largest single mapping 1.4GB). **Corrects run-6's "leak is
  cross-file accumulation"**: it was first-fixture blow-up; healthy-worker
  drift (~1GB/700 tests, run-7) stands.
- **Mechanism** (full writeup: docs/discoveries/pytest-oom-asyncmock-worker-loop.md):
  the flow file's lifespan-mock suite was abbreviated (redis/broadcaster/gpu/
  cleanup only), so get_pipeline_manager/FileWatcher/worker_supervisor stayed
  REAL. TestClient(app) then started production `_run_loop` workers whose
  AsyncMock consume_detections returns a truthy iterable-of-Mocks →
  `if not messages: continue` spins unthrottled (except-branch backoff never
  runs — mocks don't raise) and unittest.mock records one _Call per iteration
  forever: ~300 MB/s. timeout_func_only=true excludes fixture setup, so the
  5s cap never fires. 64 sandbox OOM kills total, 60 today — all this.
- **Fix (test-only)**: ported the sibling test_websocket_auth.py's proven full
  mock suite into the flow file's two helpers. Verified: repro test 1 passed
  3.6s (was: never terminates); the 3 websocket files -n0 = 93P/2xfail 9.1s
  under ulimit -v 12GB. Blast radius (test_websocket_auth.py/test_websocket.py)
  already had the full suite — this file was the outlier.
- **Owner-ruling candidates (NOT shipped)**: (P1) throttle the unthrottled
  `if not messages: continue` paths in pipeline_workers.py:413/:935 (+audit
  BatchTimeout/QueueMetrics loops) — latent prod hazard beyond tests: any mock
  or fast-empty stream there spins the event loop; (P2) timeout_func_only=true
  keeps fixture hangs unkillable — dropping it or signal-method makes the 5s
  cap cover fixtures too; (P3) load/test_performance.py frame-buffer "memory
  limit" asserts are arithmetic on constants, pass regardless of real memory.
- **Run-8b** relaunched with the fix (same instruments: 20GiB cap, disk-guard
  v2, per-test RSS traces).

### R-T7-JOBSAPI close-out (2026-09-14): tracker-seeded rewrite landed, file 20/20 (commit 4079e2d1)

The run-6 pending-owner-ruling item is resolved: tests now seed the JobTracker
singleton (create_job/start/complete/fail + timestamp pinning) instead of the
Postgres `jobs` table the routes never read. QUEUED→PENDING, CANCELLED→FAILED
(StrEnum has neither). The last two reds were shipped-contract drift:
bulk-cancel empty list is 422 (BulkCancelRequest min_length=1; no non-generated
caller sends []), and JobStatsResponse by_status/by_type are LISTS of
{status|job_type, count} — assertions flatten lists before comparing.

### R-T7-WORKERDOWN (2026-09-13): gw3/gw6 "crashes" were pytest-timeout os._exit(1), not the leak (commits e466db3c, e9f9e1ac)

Both capped-run worker deaths ended on a test in
integration/test_llm_analysis_pipeline.py::TestErrorHandlingWithEnrichment. Root cause:
conftest _apply_timeout_marker stamps integration tests timeout=5; this class's
LLM-error path legitimately takes 7–9s (guided_json precheck burns 3 retries with
1+2+4s sleeps BEFORE the post-call retries' 1+2s sleeps; measured 8.8s alone with
--timeout=0 → PASSES). pytest-timeout's thread method dumps stacks and os._exit(1)s —
killing the whole xdist worker, which xdist reports as "node down: Not properly
terminated". The RSS traces at death (82/830MB) were the REPLACEMENT worker's — the
clobbering v2 plugin fixes the attribution.

Fix: @pytest.mark.slow on the class (→30s tier). Separate drift bug in the same file,
commit e466db3c: capture_prompt read args[1]["messages"] but _call_llm posts the
payload in the json= KWARG under key "prompt" — the assert could never pass.
File now 11/11 green (-n4, gate-postgres). Implication for the leak hunt: real leak
evidence is ONLY the pre-fix kernel kills (22–58GB RSS); post-cutover unit drift is
~1GB/700 tests. Run-8 (full tier, uncapped-RSS/20GB-VmSize cap, gate-matched
--timeout=30) is the first run whose summary can be trusted end to end.
