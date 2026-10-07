# 00 — Platform Audit: the Evidence Baseline

> Written 2026-10-07 at `main` tip `d6ba78d5`. Every design in `docs/uplevel/` cites this file by
> section (`00 §4.1`). Evidence tags follow [`docs/vss-integration/AGENTS.md`](../vss-integration/AGENTS.md):
> **[V]** verified by source read at `d6ba78d5`; **[C]** computed; **[A]** reported by an audit
> subagent, not independently re-verified; **[O]** owner statement. Re-measure any **[A]** number
> before acting on it. Counts drift as `main` moves.

## 1. What the platform is

A local-first home-security system. Foscam cameras FTP images to `/export/foscam/{camera}/`.
`FileWatcher` queues each file. YOLO26, served by `ai-gateway` through Triton, detects objects.
`BatchAggregator` folds detections into 90 s / 30 s-idle batches. `VlmAnalyzer` asks the
`ai-vlm` llama.cpp server (Qwen3-VL 8B, grammar-constrained JSON) for a risk verdict. The verdict is
written to Postgres and broadcast over WebSocket to a React dashboard. Identity lookups (faces,
plates, person re-ID) run in-process beside each verdict. `synthbench/` generates a synthetic
corpus and `backend/evaluation/` replays it against the VLM. [A]

The live hop list, file to WebSocket [A]:

| #   | hop                   | module (entry)                                                          |
| --- | --------------------- | ----------------------------------------------------------------------- |
| 1   | file arrival          | `backend/services/file_watcher.py` `FileWatcher._queue_for_detection`   |
| 2   | detection worker      | `backend/services/pipeline_workers.py` `DetectionQueueWorker`           |
| 3   | detect                | `backend/services/detector_client.py` → `ai/gateway` `/detect` → Triton |
| 4   | batching              | `backend/services/batch_aggregator.py` `add_detection` / `close_batch`  |
| 5   | analysis worker       | `pipeline_workers.py` `AnalysisQueueWorker` → `pipeline_factory.py`     |
| 6   | identity              | `backend/services/vlm_specialists.py` `collect_specialist_outputs`      |
| 7   | verdict               | `vlm_analyzer.py` `analyze_batch` → `vlm_client.py` `VlmClient.assess`  |
| 8   | persist and broadcast | `vlm_analyzer.py` `_notify_decision` → `event_broadcaster.py`           |

Two recent workstreams shaped the tree. The **VLM redesign** (docs in `docs/vss-integration/`)
retired the Nemotron/enrichment pipeline in slices R8 S0–S5
([spec](../superpowers/specs/2026-09-28-r8-legacy-retirement-design.md)). The **mutation
campaign** raised the mutmut score to 82.6% over 69,854 mutants (history run M53) [A].

## 2. Size map [A]

| area                          | production files / lines | test files / lines | note                                                       |
| ----------------------------- | ------------------------ | ------------------ | ---------------------------------------------------------- |
| `backend/`                    | 511 / 257,619            | 1,089 / 769,038    | tests : production = 2.99 : 1                              |
| `backend/services/`           | 175 / 103,215            | 344 / 309,651      | one flat directory                                         |
| `ai/`                         | — / 35,221 (Python)      | —                  | ~27K lines unreferenced (§4.2)                             |
| `frontend/src`                | 878 / 335,711            | 794 / 354,629      | 61,673 of production is generated `types/generated/api.ts` |
| `frontend/tests` (Playwright) | 28 / 11,273              | 70 / 27,211        |                                                            |
| `synthbench/`                 | 107 files / 15.6K Python | —                  | imports `backend.evaluation`; production imports neither   |
| `.github/workflows`           | 40 / 14,470              | —                  | `ci.yml` alone 3,320 lines, 40 jobs                        |
| `AGENTS.md` files             | 244 / 62,889             | —                  | 29 still describe Florence                                 |

Twelve backend files exceed 2,000 lines; the largest are `api/routes/system.py` (5,515),
`core/metrics.py` (4,012), `core/config.py` (3,366, 337 settings fields) [A].

## 3. Defects found

Correctness and security faults in shipped paths. These are bugs, not cleanup.

| id  | defect                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | evidence                                                                       |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| D1  | **VLM read timeout cannot hold the token budget.** `_ASSESS_MAX_TOKENS = 2048` is justified at `vlm_client.py:94-97` as "~70s … inside the 180s read timeout", but `ai_vlm_read_timeout` defaults to 25 s (`config.py:1130-1131`, compose `:551`, `.env.example:241`). At ~57 tok/s a reply past ~1,400 tokens times out, gets one identical temperature-0 retry, and charges the circuit breaker twice.                                                                                                                                                                                                                                                                                                                                                                                                                                        | [V]                                                                            |
| D2  | **Frontend calls endpoints the backend does not serve.** `fetchCameraAnomalies` (`frontend/src/services/api.ts:1947`) calls `/api/cameras/{id}/anomalies`; the backend serves `/{camera_id}/baseline/anomalies` (`backend/api/routes/cameras.py:1577`). Reached from `CamerasSettings` → `CameraAnomalyTimeline`. Four more paths are absent from `docs/openapi.json`: `/api/jobs/{id}/retry`, `/api/events/{id}/entity-matches`, `/api/debug/profile/download`, `/api/household/members/{id}/detections`.                                                                                                                                                                                                                                                                                                                                      | anomalies [V]; the four absent from openapi [V], reachability [A]              |
| D3  | **Inbound webhooks accept any key of 16+ characters and report actions they never take.** `backend/api/routes/inbound_webhooks.py:140-146` (`# TODO: Validate against stored API keys`); router mounted at `main.py:1618`. The four handlers (`create_alert`, `arm_zones`, `disarm_zones`, `set_system_mode`) log and return success — `arm_zones` answers "Arm command for N zones queued" with nothing queued (`:278`, `# TODO: NEM-5170`). An integration that arms zones through it is told the house is armed when it is not.                                                                                                                                                                                                                                                                                                              | [V]                                                                            |
| D4  | **Alert rules that can never fire.** `alert_engine` reads `pose_results`, `action_results`, `threat_detections`, `smoke_fire_results`; nothing in production writes them.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | [A]                                                                            |
| D5  | **Plain `up` starts no verdict engine; the ghcr artifact has none at all.** `ai-vlm` sits behind `profiles: [vlm]` (`docker-compose.prod.yml`); the deploy tool passes the profile (`setup_lib/deploy_phases.py:106`). `docker-compose.ghcr.yml` has no `ai-vlm` service and no `AI_VLM_URL`. Registered as OD-14 / ISS-028.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | profile [V]; ghcr [A]                                                          |
| D6  | **Evaluation measures a different judge than production.** `replay_item` (`backend/evaluation/vlm_replay.py:137-143`) records the raw `verdict.risk_score`; production passes every verdict through `apply_verdict_invariants` (`vlm_analyzer.py:666`), whose table clamps scores (e.g. `rejected`). Thresholds picked from replay scores (OD-29's alert floor) are picked on numbers production never emits. Replay also takes the first `MAX_REPLAY_IMAGES` media paths rather than production's key-frame selection. Registered.                                                                                                                                                                                                                                                                                                             | [V]                                                                            |
| D7  | **`BackgroundEvaluator` is on by default** (`config.py:2718`) and polls a queue nothing fills.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | [A]                                                                            |
| D8  | **`auth_enabled` does nothing**; only `api_key_enabled` gates auth. An operator who sets it gets no protection.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | [A]                                                                            |
| D9  | **Broken workflows.** `preview-deploy.yml` is dispatch-only but reads `github.event.pull_request.*` 18 times and sets `FLORENCE_URL`/`CLIP_URL`/`ENRICHMENT_URL`; `deploy.yml:498,553` cite two docs that do not exist.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | `deploy.yml` [V]; `preview-deploy.yml` [A]                                     |
| D10 | **OD-12 is ruled but not built.** The owner ruled on 2026-10-06: loopback unless `EXPOSE_LAN=true`, deny-by-default auth on `/api` and `/ws` when exposed. `EXPOSE_LAN` appears in no code or compose file. The frontend nginx publishes on `0.0.0.0` (`docker-compose.prod.yml:907`) and proxies `/api` and `/ws` with no auth; the data routes (`events`, `media`, `face_recognition`, `household`, `notification`, `zones`) carry no auth dependency; the WebSocket gate is a no-op by default. Spec: ISS-029 (`P1` `bug`, open).                                                                                                                                                                                                                                                                                                            | `EXPOSE_LAN` absence and binding [V]; the rest from ISS-029's own [V] evidence |
| D11 | **The backend can stop, remove and recreate any container on the host.** It mounts the host Podman socket (`docker-compose.prod.yml:468`); its orchestrator is on by default (`backend/core/config.py:134-135`), lists every container (`container_discovery.py:647`) and adopts any whose name contains a configured pattern (`:713-715`), with no filter for its own compose project. Its recovery path stops and removes a container, then recreates it with `podman-compose -f <file> up -d <service>` and no project or env file (`lifecycle_manager.py:247-268`): it can recreate into the wrong project, and a failed recreation leaves the service deleted. A compromised backend container controls the host's containers. Found by Codex's second and third `xhigh` reviews.                                                          | [V]                                                                            |
| D12 | **Deploy has been red on `main` since January, and its rollback rolls nothing back** (measured 2026-10-07 at `2e125d8d`). `deploy.yml` last passed on `main` on 2026-01-05 (`3279ebd0`); all 161 runs since 2026-09-01 failed [V]. Its smoke test starts `docker-compose.ci.yml`, which runs no AI service, then requires `/api/system/health/full` to return 200; it returns 503, "Critical services unhealthy: yolo26" (`deploy.yml:276-288`, run 37665956816) [V]. The images are pushed as `:latest` before the smoke test runs (`deploy.yml:83,150,189`) [V]. `rollback.yml` re-tags nothing: it inspects tags and opens an "Automated Rollback" incident issue, 48 of them open since 2026-01-06 [V]. "Deploy to Staging" only echoes a checklist (`deploy.yml:421-502`) [V]. A deploy that is always red cannot report a new regression. |

## 4. Dead code

### 4.1 Backend [A]

- **57 runtime modules (23,552 lines) have no production importer.** Largest:
  `services/scenario_classifier` 1,031, `service_provider_matcher` 789, `zone_crossing_service` 733,
  `prompt_storage` 724, `redis_json` 654, `ai_fallback` 653, `core/redis_cluster` 596,
  `websocket_service` 576, `orphan_cleanup_service` 575. `services/calibration.py` is empty.
- **95 files (~38,600 lines) are unreachable from `main.py`** once names, not packages, are traced.
  `services/__init__.py` (632 lines) imports 56 submodules and re-exports 274 names that no
  production code imports, which hides the dead modules from a package-level scan. Includes all of
  `backend/config/` (the prompt A/B and shadow-rollout package), `core/config_nested.py`, 4 of 8
  repositories, 8 middleware modules, `partition_manager`, `managed_service`, `pg_notify_listener`.
- **50 of 337 settings fields are never read**, 20 of them `florence_*`/`clip_*`/`enrichment_*`.
- **R8 residue:** `AIModelEnum` still offers `florence2`, `xclip`, `fashion_clip`, `yolo_world`;
  `get_nemotron_analyzer_dep` returns a `VlmAnalyzer`; `summary_generator._call_nemotron` calls
  `ai_vlm`; 11 unused exception classes; `PromptABTester` and siblings (414 lines).
- Registered in part as ISS-092 / OD-28 (49 modules; no ruling recorded).

### 4.2 `ai/` [A]

About 27K of 35K Python lines are referenced by no compose service and no backend import: the 13
top-level `ai/*.py` modules and `ai/tests` (11.6K), `ai/common` (2.5K), `ai/shared`,
`ai/triton/client.py` (869), `ai/yolo26` except `build_engine.py` (8.5K), and 9 of 13 gateway export
scripts. The gateway Dockerfile installs torch, transformers, ultralytics, open_clip, timm,
onnxruntime; the gateway runtime imports none of them.

### 4.3 Frontend [A]

- **236 production files (~71,800 lines, ~26% of hand-written code) are unreachable from
  `src/main.tsx`**, and 219 test files (~91,500 lines) test only them. `knip.json` treats every test
  as an entry point and disables `exports`, so knip cannot see this.
- **R8 surfaces still live in the UI** (~6.4K production lines): the `/reid` route
  (`ReIDDashboard`), `ReidMatchesPanel`, `ActionEventsPanel`, `PoseSkeletonOverlay`, both Model Zoo
  panels, the Florence2/XCLIP/FashionCLIP/Nemotron prompt forms, `types/enrichment.ts` (912).
  The backend still feeds them (`/api/system/model-zoo/status`, `AIModelEnum`).

### 4.4 Mutation campaigns spent on dead code

The campaign picks its next module by survivor count, not by whether the module ships. Campaigns
#10 `redis_json`, #47 `scenario_classifier`, #48 `managed_service` and #49
`orphan_cleanup_service` hardened modules with no production importer outside
`services/__init__.py` [V: grep at `d6ba78d5`]. #21 `partition_manager` and #30
`pg_notify_listener` are unreachable from `main.py` [A]. #7 `clip_client` was deleted by R8-S3 after
its campaign closed (`4c9251b0`) [V].

## 5. Duplication and shallow modules [A]

| concept            | copies                                                                                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| circuit breaker    | 4 + a deprecated shim: `services/circuit_breaker.py` (1,125), a class in `routes/system.py:167`, `HealthCircuitBreaker`, `core/websocket_circuit_breaker.py` (725) |
| retry              | `core/retry.py` (dead, sync `requests`) and `services/retry_handler.py`; both define `RetryConfig`. Detection retries stack 3 deep.                                |
| service registry   | `ServiceConfig` ×3, `ManagedService`/`ServiceRegistry` ×2 across `managed_service`, `orchestrator/`, `service_managers`                                            |
| settings classes   | 19 `BaseSettings` subclasses; `core/config_nested.py` (9 of them) is unused                                                                                        |
| exception handling | `api/exception_handlers.py`, `middleware/error_handler.py` (dead), `middleware/exception_handler.py`                                                               |
| broadcast          | `EventBroadcaster` (2,456; ~22 copy-paste `broadcast_*`), `WebSocketEmitterService` wrapping it, `SystemBroadcaster`, dead `websocket_service.py`                  |
| Triton client      | `ai/gateway/triton_client.py` (live) and `ai/triton/client.py` (dead)                                                                                              |
| identity lookup    | 6 live modules with no shared interface; `cosine_similarity` ×7                                                                                                    |
| helpers            | `verify_api_key` ×3, `parse_accept_header` ×2; `RiskLevel` defined 6 times                                                                                         |
| HTTP clients       | 31 `httpx.AsyncClient(` sites in 21 files, 23 built per call                                                                                                       |
| frontend API types | generated `types/generated/api.ts` exists, yet 369 hand-written interfaces shadow generated names; `services/api.ts` is 9,306 lines                                |
| frontend state     | health data has 5 implementations; 6 of 10 contexts and 4 of 8 stores are dead; `Result` ×3; modals 4 ways                                                         |

The VLM path has no single seam between "build the request", "call the model" and "judge the
verdict": key frames are selected 3× and the prompt fitted 2× per batch; the analyzer is built in
4 places; the prompt is an inline literal with no version stored on `EventVerification`.

## 6. Tests and the mutation campaign [A]

- **Batteries.** 130 files named `test_<module>_batchNN[_x].py` (120,913 lines, 3,240 tests) were
  written 09-22 → 10-07 to kill named mutants. Against other unit tests they carry 2.9× the
  private-attribute references and 8.8× the log-string assertions per 1K lines; some assert that
  production _comments_ are present verbatim (`test_gpu_monitor_batch28_22.py`). 79 cite harness
  files under `/tmp` or `/home/agent/runs` that exist nowhere, so their kills cannot be re-derived.
  `backend/tests/utils` is imported by none; helpers are copy-pasted (`FakeRedis` ×16).
- **Fragmentation.** `pipeline_workers` has 21 test files (25,852 lines) for 2,271 production
  lines; `detector_client` 17; `gpu_monitor` 23. Route tests live in two trees (`unit/routes/` and
  `unit/api/routes/`).
- **Parametrize candidates.** 488 groups of 3+ tests differing only in literals: 2,010 functions in
  247 files. `scripts/parametrize-guard.py` already proves merges safe.
- **Fixture shadowing.** ~215 local redefinitions of conftest fixtures (`mock_redis` ×58).
- **Dead tests.** 3 permanently skipped `stream_config` files test modules that do not exist; 12
  "moved" skips in `test_system_models.py`; `tests/benchmark` is never run by CI.
- **Score at risk.** Deleting all batteries naively drops the score by up to ~22 pp. Merging them
  while keeping each assertion costs ~0 pp but needs one mutmut run per module (~10 min each).
- **Apparatus weight.** `.github/mutation-history.json` 4.8 MB (57 runs in 18 days, committed by the
  agent, not CI); the ledger `docs/plans/2026-09-12-context-map-doc-updates.md` 1.3 MB / 17,137
  lines; `docs(mutmut)` commit subjects average 1,725 characters; `archive/wp25-feed/` 40.6 MB.
- **No test touches the joined system.** All 68 Playwright specs run against mocked APIs
  (`playwright.config.ts:241` starts `npm run dev:e2e`; 70 spec and helper files use `page.route`
  or mock helpers) [V]. Backend unit tests mock Postgres and Redis. `tests/smoke` checks health
  endpoints only and no workflow runs it [A]. A UI can call an endpoint that does not exist (D2) and
  every layer stays green.
- **A fake AI tier already exists.** `backend/ai_contract/fake/app.py` is a deterministic FastAPI
  "FakeProvider" mounting one route per AI-contract operation, with conformance tests and golden
  payloads under `backend/tests/contracts/ai_providers/` [V]. Nothing runs it as a service today.
- **Unfinished plan.** [`2026-09-15-test-platform-improvement.md`](../superpowers/plans/2026-09-15-test-platform-improvement.md)
  WP4.4 "Consolidate on mutation evidence" never started; all 105 checkboxes in that plan are
  unticked although several packages landed [V].

## 7. Deploy, config and CI [A]

- **Compose.** `prod` 1,593 lines (42% comments); 93% of `ghcr`'s code lines are verbatim copies of
  `prod` with no `include`/`extends`; image versions drift between them (prometheus v3.1.0 vs
  v2.48.0, loki 3.5.1 vs 2.9.4). `ai-llm-vllm` defaults to the retired Nemotron-30B and nothing
  depends on it.
- **Config.** `.env.example` 1,022 lines, 182 variables; 34 are read by neither `config.py` nor
  compose; ~17 name retired components (`GPU_FLORENCE`, `GPU_CLIP`, `LLM_PORT`, …).
  `models.yml` has no row for the shipped Qwen3-VL GGUF; 4 rows are dead.
- **CI.** pip-audit and npm audit each run in 4 workflows; three release mechanisms; 40
  `continue-on-error: true`. `scripts/` (231 files) is never linted; ~14 scripts are referenced by
  nothing.
- **Installer naming.** `setup.py` (1,509 lines) is an interactive `.env` installer, not packaging;
  `pip install .` would execute it as a setuptools build.
- **Install paths.** `docs/operator/ai-ghcr-deployment.md` advertises the ghcr compose path that
  has no `ai-vlm` (D5) [V]. The top-level installer's own tests sit in `archive/test_setup.py` and
  `archive/test_setup_core.py`, so `setup.py` runs untested; `setup_lib/` has live tests under
  `backend/tests/unit/setup_lib/` [V].
- **Dependency alerts.** GitHub reports 21 open Dependabot alerts on `main` (2 critical, 10 high,
  9 moderate) [V: Dependabot API, 2026-10-07]. **16 sit in `archive/package-lock.json`**, including
  the critical `vitest`; `O1.5` deletes that tree. The other five are live:
  - critical `python-jose` (`uv.lock`, runtime; GHSA-3qf3-8w2g-rqmx, **no patched release**) — the
    backend's JWT library (`backend/services/auth_service.py:21`);
  - high `ecdsa` (no patched release) — present only because `python-jose` requires it;
  - medium `Mako` (patched in 1.4.2) — present only because `alembic` requires it;
  - high `braces` 3.0.3 (no patched release) and medium `postcss-selector-parser` 6.1.4 (patched in
    7.1.6) — frontend build tooling (`frontend/package-lock.json`).
    The 2026-09-21 triage ([`docs/plans/2026-09-21-dependabot-triage.md`](../plans/2026-09-21-dependabot-triage.md))
    found `.github/dependabot.yml` misconfigured; its fix options are owner-held under OD-11 [V].
- **Schema.** No Alembic: schema comes from `create_all` plus hand-written SQL in
  `docs/api/migrations/`; `alembic>=1.13` is still a dependency.

## 8. Repository and docs weight [A]

- `archive/wp25-feed/`: 2,872 files, 40.6 MB of mutation-triage dumps, including all 1,687 `.diff`
  files and the 894 quoted `ǁ` paths. Pending owner sign-off per `archive/README.md`.
  It supplies 19,395 of 19,732 entries in `.secrets.baseline` (5 MB).
- `docs/` PNGs: 421 files, 412.6 MB — 73% of tracked bytes; 28 (15.4 MB) referenced nowhere.
- `docs/`: 590 markdown files; mkdocs nav covers 128; `docs/development/` is 30 redirect stubs;
  VSS planning is split across `docs/plans`, `docs/superpowers/plans` and `docs/vss-integration`.
- Retired components appear in 70 non-archive docs and 29 `AGENTS.md` files. `AGENTS.md:240`
  calls `data/` gitignored; it holds 1,409 tracked fixture files.

## 9. Already registered — cite, do not re-file

[`docs/vss-integration/17-action-plan.md`](../vss-integration/17-action-plan.md) is the living
register (103 issues, 32 owner decisions). Findings above that it already holds:

| finding                                       | register entry   | owner decision at `d6ba78d5`                                                                     |
| --------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------ |
| dead service modules (§4.1)                   | ISS-092          | OD-28 **ruled 2026-10-06: delete** (guided-constraints and trajectory first, then scene-change)  |
| dead enrichment surface                       | ISS-073          | OD-20 **ruled 2026-10-06: retire** (hook, route, types, tombstone in one commit)                 |
| frontend LAN exposure / auth                  | ISS-029          | OD-12 **ruled 2026-10-06: loopback unless `EXPOSE_LAN=true`, deny-by-default auth when exposed** |
| prompt-management stack for retired models    | ISS-084, ISS-085 | OD-25 partly ruled (ISS-083 done by deletion)                                                    |
| ghcr gap, plain `up` (D5)                     | ISS-028          | OD-14 open in the register; settled here as UR-17 and UR-18 (`README.md`)                        |
| Triton `reid`/`threat` lane, `ai-llm-vllm`    | ISS-050          | OD-17 open; deferred to the Phase 2 RULING session                                               |
| threat specialist, immediate-alert fast paths | —                | OD-7 open; deferred to the Phase 2 RULING session                                                |
| OD-12 implementation (D10)                    | ISS-029          | ruled, **not built** (`P1` `bug`, open)                                                          |

The rulings sit inline in the register's OD table (options column), not in a separate status column.

## 10. Feature inventory seeds

Surfaces already classified during this audit. The Phase 2 feature inventory (`F2.2`) starts here,
re-verifies each row on the fake stack, and covers everything this list does not. Statuses use the
vocabulary in [`README.md`](README.md). [A] unless marked.

| surface                                                              | status        | evidence                                                                                                                                                                                                                 |
| -------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Model Zoo status card (AI Performance page, AI Models tab)           | works, partly | built from `models.yml` plus the live model manager (`system.py:4932-4958`); its latency chart is always empty (`record_model_zoo_latency` has no callers)                                                               |
| Model load/unload panel (`ModelZooPanel`)                            | works         | `/api/system/models` on the live model manager                                                                                                                                                                           |
| `/reid` dashboard and Re-ID matches panel                            | half-built    | the pipeline computes re-ID matches during analysis (`vlm_specialists.py:694-760`) but persists nothing; the UI reads the `entities` table and Redis `entity_embeddings:*`, which nothing in the shipped pipeline writes |
| Prompt management page (`settings/prompts`, Florence2/XCLIP/… forms) | half-built    | `AIModelEnum` lists only retired models (`schemas/prompt_management.py:13-17`); the shipped VLM prompt is an inline literal the page cannot reach (`vlm_analyzer.py:649`)                                                |
| Automatic AI-audit evaluation (`BackgroundEvaluator`)                | half-built    | started by default (`main.py:1054-1067`, `config.py:2718`); nothing calls `EvaluationQueue.enqueue`; manual `POST /events/{id}/evaluate` works                                                                           |
| Camera anomaly timeline (Cameras settings)                           | half-built    | calls a path the backend does not serve (D2) [V]                                                                                                                                                                         |
| Inbound webhooks (arm, disarm, mode, create alert)                   | half-built    | report success, act on nothing (D3) [V]; ruled **complete** (UR-12)                                                                                                                                                      |
| MQTT commands (arm, disarm, mode, alert ack)                         | half-built    | `mqtt_command_handler.py` logs and records success with `# TODO: Integrate with ZoneService`; its only importer is `inbound_webhooks.py` [V]                                                                             |
| Action events panel                                                  | leftover      | the `action_events` table has no writer except a manual `POST /api/action-events`                                                                                                                                        |
| Pose skeleton overlay                                                | leftover      | no `<DetectionImage>` call site passes `poseKeypoints`; nothing writes `enrichment_data["pose"]`                                                                                                                         |
| Alert conditions: pose, action, threat, smoke/fire                   | leftover      | `alert_engine.py:521-542,696,738,780,850` reads tables nothing writes (smoke/fire probes attributes `Detection` lacks); the UI hard-codes them off (`AlertRulesSettings.tsx:400-402`); the API schema still accepts them |
