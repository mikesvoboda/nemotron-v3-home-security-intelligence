# 4n — System Status Design

> Step 1 of the System status feature packages (`packages/backend.md`, "B4.\* Feature track"),
> copied from [`templates/feature-design.md`](templates/feature-design.md).

**Packages:** `B4.11`, `F4.8` · **Inventory rows:** F-011, F-015, F-037, F-126, F-139, F-140, F-173
(R2a row 30: "re-key to `yolo26` and `ai-vlm`"); F-009, F-292, F-293 (R2a row 9: "align the message
type and socket; delete the unused receiver"); F-019 (R2a row 44), F-168 (R2a row 35), F-193 (R2a
row 38) · **R2 ruling:** complete, priority 2 · **Designed:** 2026-10-22, with the owner

## Where it starts

Facts read at `main` `aec5580aa`.

- **The AI services are `ai-gateway` and `ai-vlm`.** The backend reaches the detector at
  `YOLO26_URL=http://ai-gateway:8090/yolo26` and the VLM at `AI_VLM_URL=http://ai-vlm:8098`
  (`docker-compose.prod.yml:556`, `:508`). The gateway's `/health` (`ai/gateway/main.py:291-321`)
  and `/yolo26/health` (`ai/gateway/adapters/yolo26.py:511-519`) answer 200 even when a model is not
  loaded; `llama-server`'s `/health` answers 503 while loading.
- **Six producers report AI health, and "healthy" means "answered HTTP".** `GET /api/system/health`
  (`backend/api/routes/system.py:1279`) checks only the status code (`:927-928`); `/health/full`
  (`system.py:5201-5222`) and `/api/health/ai-services`
  (`backend/api/routes/health_ai_services.py:50-78`) each keep their own table of services;
  `SystemBroadcaster` still loops over `nemotron` (`backend/services/system_broadcaster.py:831`);
  `PerformanceCollector` fills `ai_models["nemotron"]` from the VLM's `/slots`
  (`backend/services/performance_collector.py:98-99`, `:210-233`) and names a container `ai-yolo26`
  (`:474-475`); `ServiceHealthMonitor` probes only `yolo26` (`backend/main.py:720-732`).
- **The VLM is probed today, despite the rule.** The service monitor leaves it out so that a check
  never wakes it; its circuit breaker pushes its state instead (`backend/main.py:1113-1132`). But
  `/health/full` (`system.py:5276-5279`), `/api/health/ai-services`
  (`health_ai_services.py:211-212`) and the collector's `/slots` (`performance_collector.py:220`)
  all request it, and the container orchestrator's health loop probes it every interval and can
  restart it: compose discovery gives `ai-vlm` a `/health` row
  (`backend/services/health_monitor_orchestrator.py:297-302`). The VLM client records no call's
  outcome; it pushes "unhealthy" only when a failure opens the breaker
  (`backend/services/vlm_client.py:1083-1094`).
- **The UI still keys on `rtdetr` and `nemotron`.** The header badge (F-011) types its services as
  `rtdetr | nemotron | florence | clip` (`frontend/src/hooks/useAIServiceStatus.ts:25`) and waits
  for an `ai_service_status` message (`:131`) that nothing sends. The dashboard row and model cards
  (F-037, F-126) read `details.rtdetr` and `details.nemotron`
  (`frontend/src/hooks/useAIMetrics.ts:144-145`); the services panel (F-139) has `rtdetr` and
  `nemotron` cards (`ServicesPanel.tsx:102-115`); the latency chart (F-173) reads
  `rtdetr_latency_ms` (`PerformanceCharts.tsx:165-166`, `:209-210`), and the Operations golden path
  requires `ai-model-nemotron` (`frontend/tests/golden/operations/performance.spec.ts:55`, `:66`).
  F-015's banner was re-keyed by `[r267a]` (`useServiceStatus.ts:38-67`) and lacks only `ai-vlm`.
- **The latency series are pipeline stages.** `yolo26_latency_ms` comes from the watch-to-detect
  stage and `nemotron_latency_ms` from batch-to-analyse (`performance_collector.py:632-656`). The
  detector records a request histogram (`backend/services/detector_client.py:1139`); the VLM has
  none.
- **Service controls restart real containers, with no admin check.**
  `/api/system/services/{name}/restart` (`backend/api/routes/services.py:155-321`) restarts through
  the host Podman socket mounted into the backend
  (`backend/services/container_orchestrator.py:407-458`; `docker-compose.prod.yml:427`), with no
  check beyond `EXPOSE_LAN`'s login (`backend/api/middleware/auth.py:660-669`).
  `require_admin_access` (`backend/api/routes/admin.py:322-337`) checks only that admin features
  are on (`ADMIN_ENABLED`, default true), not who calls; the session-only `get_current_admin_user`
  (`backend/api/routes/auth.py:485-503`) is the real admin check, and users carry `is_admin`, the
  first to register being admin (`auth.py:210-217`). Enable and disable only flip a self-healing
  flag that persists in Redis (`container_orchestrator.py:342-405`;
  `backend/services/orchestrator/registry.py:322-356`), and restart refuses a disabled service
  (`services.py:188`); the UI's "stop" calls disable. Every card but `redis` and `postgres` answers
  404 (`services.py:185`), and the UI disables Postgres's buttons (`ServicesPanel.tsx:27`). Workers
  have restart, stop and start routes (`system.py:4481`, `:4532`, `:4584`), unguarded. By rule every
  test deployment runs with the orchestrator off and no engine socket (UR-134).
- **Infrastructure alerts never reach the badge (F-009).** Alertmanager posts to
  `/api/webhooks/alerts` (`monitoring/alertmanager.yml:180-192`; `docker-compose.prod.yml:1280`),
  which emits `infrastructure_alert` on the events channel (`backend/api/routes/webhooks.py:25-55`).
  The badge listens on `/ws/system` (`frontend/src/hooks/usePrometheusAlertWebSocket.ts:403-404`)
  for another shape (`:161-181`). The second receiver, `/api/v1/alertmanager/webhook`
  (`backend/api/routes/alertmanager.py`), is in no configuration; R2 deletes it and its
  `prometheus_alerts` table (`r2-sheet.md:201`). An alert that fired before the page opened shows
  only when Alertmanager repeats it: every 4 h by default, 1 to 24 h on its child routes
  (`monitoring/alertmanager.yml:63`, `:73-119`).
- **Three small breaks.** The palette's System entry and `g y` open `/system`
  (`frontend/src/components/common/CommandPalette.tsx:93-94`;
  `frontend/src/hooks/useKeyboardShortcuts.ts:28`); the page is `/operations`. Tracing's link opens
  `http://localhost:16686` (`frontend/src/components/tracing/TracingPage.tsx:105`); the stack has
  Grafana's Tempo data source (uid `tempo`). Flush queues deletes `hsi:queue:*`
  (`admin.py:1360-1364`), while the pipeline in production uses Redis streams
  (`use_redis_streams` defaults to true, `backend/core/config.py:1946-1949`): `detections:stream`,
  `analysis:stream` and their `:dlq` streams (`backend/services/redis_streams.py:73-74`,
  `:873-874`), with the list keys `detection_queue`, `analysis_queue` and `dlq:*` only in list mode
  (`backend/core/constants.py:146-177`).

## What the user can do when this is done

The household sees whether its detector and its VLM are working: the header badge, the dashboard
row and the model cards say ready, loading, idle (asleep) or failing, the same everywhere. An admin
can restart a stuck service from Operations. Infrastructure alerts appear in the header as they
fire, including ones already firing when the page opens. The latency chart shows how long each
model takes to answer.

## Decisions

| question                                   | decision                                                                                                                                                                                                                                                                                                         | why                                                                                                  |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| What can the services panel do?            | Restart only, for `ai-gateway`, `ai-vlm`, `redis` and `postgres`; worker cards use the worker restart. Enable, disable, `/start` and the worker stop and start routes retire (owner, ST-1; T6).                                                                                                                  | One real action, guarded; the others never stopped anything, or bypass the guard.                    |
| Who may restart?                           | An admin with a session, through `get_current_admin_user`, in every setup; API keys never. With LAN exposure off, Restart asks for an admin sign-in, or offers to create the first admin account. The audit names the person (owner, review T1).                                                                 | `require_admin_access` does not check who calls; a restart of Postgres is the household admin's act. |
| Where is a real restart witnessed?         | The owner, on the live install after these packages deploy: sign in as admin, restart `ai-gateway` from Operations, read the audit row and the badge going loading → ready. Pytest with a fake engine proves the rest (owner, review T5).                                                                        | UR-134 keeps every test deployment away from the container engine.                                   |
| What does "AI service healthy" mean?       | One backend health module behind every badge and card. The detector is ready when the gateway reports its model loaded; the VLM is ready when its last call succeeded and its breaker is closed. A sleeping VLM is "Idle (asleep)", neutral, never probed awake; loading is amber; failing is red (owner, ST-2). | The case people need to see, a model that is not loaded, shows; a quiet night does not look broken.  |
| Are the API names renamed?                 | Yes, by expand then contract (T3): `B4.11` adds `ai_vlm` and `yolo26` beside `nemotron` and `rtdetr`; `F4.8` moves every consumer and removes the old names in the same PR (UR-9). Branding and prompt management keep their names.                                                                              | R2 ruled the re-key; each package stays green on its own.                                            |
| What does the latency chart show?          | Each model's inference latency: the detector's request histogram, and a new one for the VLM.                                                                                                                                                                                                                     | The chart's labels claim model latency; the stage timings stay on the pipeline panel.                |
| How do infrastructure alerts reach the UI? | The badge reads `infrastructure_alert` on `/ws/events`, and loads the alerts firing now once, on page open, through a backend proxy of Alertmanager's `/api/v2/alerts`. The unused receiver and its table retire.                                                                                                | The one path Alertmanager posts to; no wait for a repeat.                                            |
| The small rows                             | `/system` becomes `/operations`; Tracing opens Grafana's Explore on the `tempo` data source; flush queues clears what the pipeline really uses, streams or lists by its mode (T2), and the unused prefix helper goes.                                                                                            | What R2 ruled, made exact.                                                                           |

## Approaches weighed

| approach                                   | for                                                          | against                                                                   |
| ------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------------------- |
| **A. One AI health module** (chosen)       | One meaning everywhere; the VLM's no-wake rule in one place. | Six producers change in one package.                                      |
| B. A shared key constant only              | Smallest backend change.                                     | Six producers keep six meanings of "healthy".                             |
| C. Re-key the frontend only                | No backend change.                                           | The badge still waits for a message nothing sends; old names stay in API. |
| Controls: read-only panel                  | Smallest attack surface.                                     | A stuck service means a terminal.                                         |
| Controls: keep enable and disable, renamed | More control.                                                | Two switches that only change self-healing, to explain.                   |

## Shape

- **The module behind the seam:** `backend/services/ai_health.py`. Domain terms, added to
  `docs/reference/glossary.md`: **AI service state** (`ready`, `loading`, `idle`, `failing`,
  `unknown`).
- **Its interface:**
  - `state(service) -> ServiceState(service, state, detail, since)` for `yolo26` and `ai_vlm`.
    `yolo26` reads the gateway's model readiness (`model_loaded`), not its status code. `ai_vlm`
    reads what the VLM client records: each call's outcome and time, which the client starts
    recording (T4), and the breaker's state from the circuit-breaker registry. A VLM with no call
    for `VLM_SLEEP_IDLE_SECONDS` is `idle`; before its first call since start it is `unknown`. The
    module never sends the VLM a request.
  - `snapshot() -> dict[str, ServiceState]`, the one shape every route and broadcast returns.
  - `on_change(callback)`: the broadcaster publishes `ai_service_status` on a change of state.
  - Invariants: nothing in the backend requests `ai-vlm` for status, the orchestrator's health loop
    included (T4); a probe error is `failing` with its message, never `ready`.
- **Its adapters:** `GET /api/system/health`, `/health/full` and `/api/health/ai-services` return
  `snapshot()`'s entries; `SystemBroadcaster` and `PerformanceCollector` read it; the
  `ai_service_status` message feeds the header badge.
- **Service controls** (T1, T6, T7):
  - `POST /api/system/services/{name}/restart` takes `Depends(get_current_admin_user)` before the
    orchestrator dependency, so a refusal (401, 403) comes before "engine not available" (503). It
    accepts only `ai-gateway`, `ai-vlm`, `redis` and `postgres`. Worker restart takes the same
    guard. Restart no longer refuses a service once disabled. Until `F4.8` retires them, the
    enable, disable and `/start` routes and the worker stop and start routes take the same admin
    guard.
  - **The audit:** before calling the engine, the route commits an audit row "restart requested"
    naming `user.username`, then records the outcome in a fresh session, so restarting Postgres
    cannot lose its own record.
  - **Retired in `F4.8`** (T8): the enable and disable routes, `POST /services/{name}/start`, and
    the worker stop and start routes, in the PR that removes their UI callers. That PR also clears
    every persisted `enabled=false` once, so no service is left disabled with nothing to enable it
    (T7).
  - **The orchestrator's health loop** skips `ai-vlm` through a never-probed set beside
    `RETIRED_LLM_SERVICES` (`container_orchestrator.py:69`); its registry row stays for restart.
- **Flush queues** (T2): in streams mode (the default) it trims `detections:stream` and
  `analysis:stream` to zero and acknowledges their consumer group's pending entries, then deletes
  the two `:dlq` streams; it never deletes a work stream, whose consumer group the workers cache.
  In list mode it deletes the list keys and the overflow dead-letter lists. It answers what it
  cleared, by key.
- **Infrastructure alerts:** `GET /api/system/infrastructure-alerts` proxies Alertmanager's firing
  alerts, mapped to the `infrastructure_alert` shape the socket carries.

## What changes

- **backend (`B4.11`, expand):** `ai_health.py` (new); `system.py`, `health_ai_services.py`,
  `system_broadcaster.py`, `performance_collector.py` and `main.py`'s monitor read it; the VLM
  client records each call's outcome and time, and the backend reads `VLM_SLEEP_IDLE_SECONDS`
  (`config.py`, `.env.example` and the compose `environment:` block, UR-9);
  `backend/api/schemas/performance.py` adds `ai_vlm` and `yolo26` fields beside `nemotron` and
  `rtdetr`, filled from the same values (the `ai_models` key does not move yet, so the dashboard
  does not show two cards); `detector_client.py`'s histogram feeds the chart, and the VLM client
  gains one; `services.py`, `container_orchestrator.py` and the orchestrator registry (the admin
  guard on restart and on the routes `F4.8` retires, the audit, the allowlist, the never-probed
  set); worker restart's guard in `system.py`; the infrastructure-alerts proxy; `alertmanager.py`
  and the `prometheus_alerts` table retire with a recorded upgrade; `admin.py`'s mode-aware flush
  and `constants.py`'s helper; `docs/openapi.json` and the generated types are regenerated (UR-83).
- **frontend (`F4.8`, contract):** `useAIServiceStatus`, `AIServiceStatus`, `useAIMetrics`,
  `AIPerformanceSummaryRow`, `AIModelsSettings`, `ModelStatusCards`, `ServicesPanel` (Restart
  only, the sign-in prompt, Postgres no longer blocked), the shared `useIsAdmin` (it loads
  `/api/auth/me` whether or not the backend requires auth, and reads 401 as "not signed in"
  without redirecting) and `AdminSignInPrompt`, which `F4.10` reuses (`4n-debug-tools.md`, DT5),
  `PerformanceCharts`,
  `usePerformanceMetrics`, `PerformanceDashboard`, `useFullHealthQuery`, `metricsParser`,
  `useServiceStatus` (`ai-vlm`), `usePrometheusAlertWebSocket` (events socket, shape, page-open
  load), `CommandPalette`, `useKeyboardShortcuts`, `TracingPage`; test fixtures
  (`test-utils/factories.ts`, `services/__mocks__/api.ts`). **Its cross-lane part** (UR-9, T3): the
  same PR removes the old `nemotron` and `rtdetr` fields, moves the `ai_models` key, regenerates
  the contract and types, and edits `operations/performance.spec.ts:55` and `:66`; and it retires
  the enable, disable and `/start` service routes and the worker stop and start routes
  (`services.py`, `system.py`) together with their callers (the start, stop, enable and disable
  mutations in `useServiceMutations` and `useWorkerActions`; `api.ts`'s `/start`, `/disable` and
  `/enable` clients and `supervisorApi.ts`'s worker start and stop; the panels' buttons), with a
  404 test for each, and clears every persisted `enabled=false` once (T7, T8).
- **monitoring:** none; the Tempo data source and Alertmanager's sink stay.

## Failure handling

- **The gateway unreachable:** `yolo26` is `failing` with the error; the VLM's state is unaffected.
- **No VLM call yet since start:** `ai_vlm` is `unknown` until its first call or breaker push, then
  follows them; it is never probed.
- **Alertmanager unreachable on page open:** the badge shows what the socket brings and says the
  current list could not be loaded.
- **No engine socket** (the orchestrator off, as on every test deployment): restart answers 503
  "engine not available" to an admin, after the sign-in check.
- **A restart that fails:** the route answers the engine's error, and the outcome row records it.

## Tests

- **Consolidation scope:** the six producers and their routes, `services.py`,
  `container_orchestrator.py` and its health loop, the worker routes, `webhooks.py`,
  `alertmanager.py`, `admin.py`'s flush, and the frontend hooks and components named above.
- **Tests through the interface:**
  - each state for each service, including `idle` reached without a probe, and a probe error never
    `ready`;
  - every route returns `snapshot()`'s shape, and a state change publishes `ai_service_status`;
  - the orchestrator's health loop never requests `ai-vlm`;
  - restart, with a fake engine: refused with 401 without a session or with an API key alone, and
    403 for a non-admin (`4n-debug-tools.md`, DT6); done and audited with the admin's name, the "requested" row committed first; 503
    without an engine; a name outside the four is refused; a once-disabled service restarts;
  - the retired routes answer 404;
  - the proxy's mapping;
  - flush in streams mode trims, acknowledges and keeps the consumer group, and in list mode
    deletes the lists.

## Golden path

- **Spec, backend** (`backend/tests/golden/external/test_system_status.py`): every health route
  returns the snapshot's shape with `yolo26` ready and `ai_vlm` idle on the fake stack; restart
  answers 401 without a session or with an API key alone, 403 for a non-admin, and 503 "engine not
  available" for an admin (UR-134); the old receiver answers 404.
- **Spec, UI** (Playwright):
  - the header badge, the dashboard row and the model cards show the fake stack's `yolo26` ready
    and `ai_vlm` idle;
  - on Operations, Restart asks a signed-out user to sign in, refuses a non-admin, and shows an
    admin "engine not available" (UR-134);
  - an infrastructure alert posted to the sink appears in the header, and one already firing
    appears on page open;
  - `g y` opens `/operations`, and Tracing's link opens Grafana's Explore on `tempo`.

  The edits to `dashboard/ai-summary-row.spec.ts`, `operations/performance.spec.ts`,
  `operations/grafana-embeds.spec.ts` and `shell/palette.spec.ts` follow the new keys and links,
  in the PR that changes each.

- **Fake-stack scenario:** the fake gateway reports its model loaded; the fake VLM answers one call
  and then idles.
- **Real-tier check:** on the GB300 test deployment the operator reads the badge with the VLM asleep
  (idle, and no request in the VLM's log from any check, the orchestrator's loop included) and
  awake after one analysis (ready). A real restart is the owner's, on the live install: sign in as
  admin, restart `ai-gateway`, and read the audit row and the badge going loading → ready (T5).

## Privacy and security

No personal data. Restart, the one container action left, needs an admin session in every setup,
never an API key, and is audited with the person before the engine is called; enable, disable,
start and the worker stop and start routes retire. The orchestrator never probes the VLM. The
infrastructure-alerts proxy needs a session or API key with `EXPOSE_LAN=true`, as every route does.

## Rollout and reversal

`B4.11` adds the new fields beside the old ones, the health module and the guard, and retires only
what no UI calls: the unused Alertmanager receiver and its `prometheus_alerts` table, through a
recorded upgrade. `F4.8` moves every consumer, removes the old fields and retires the control routes
with their callers, in the same PR, with the regenerated contract and types; that PR also clears the
persisted `enabled=false` flags once, since it retires disable. Code reversal is a revert; the
upgrades stay.

## Packages

| package | lane (ruling 317) | depends on | contents                                                                                                                                                                                                                                            | its own golden path       |
| ------- | ----------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `B4.11` | heavy-b           | none       | Expand: the health module and its readers, the new fields beside the old, the latency histograms, restart only under the admin session with its audit, the never-probed VLM, the alerts proxy, the receiver's retirement, the mode-aware flush.     | Backend pytest of routes. |
| `F4.8`  | frontend          | `B4.11`    | Contract: the badge, row, cards, panel with its sign-in prompt, chart, banner, the alert badge's socket and load, the palette, Tracing; removes the old fields, retires the control routes with their callers and clears the disabled flags (UR-9). | Playwright above.         |

Each runs the six steps as two PRs: a test-only consolidation PR, then the build.

## Review

An adversarial review (2026-10-22) and a fresh-context check of it found seven issues; the check
confirmed every review finding and found more; the plan PR's review added one (T8). Several cites in
"Where it starts" were wrong or too broad and are corrected here. The owner ruled on two (T1, T5):

| #   | finding                                                                                           | amendment                                                                                                                         |
| --- | ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| T1  | `require_admin_access` does not check who calls, so any session or API key could restart Postgres | `get_current_admin_user`, session only, API keys never; with LAN exposure off, a sign-in prompt (owner); the audit names the user |
| T2  | Flush cleared list keys while production runs on Redis streams                                    | A mode-aware flush: trim and acknowledge the work streams, delete their dead-letter streams, keep the consumer group              |
| T3  | Renaming the fields in the backend first broke the frontend and its golden path                   | Expand in `B4.11`, contract in `F4.8` with every consumer and the golden edit (UR-9)                                              |
| T4  | The orchestrator probes `ai-vlm` every interval and can restart it; no call outcome was recorded  | A never-probed set for the health loop; the VLM client records each call; the backend reads the sleep setting                     |
| T5  | Test deployments run without the engine (UR-134), so no tier can witness a real restart           | The golden path proves the refusals; the owner witnesses one `ai-gateway` restart on the live install (owner)                     |
| T6  | `/start` and the worker stop and start routes stayed open beside the guarded restart              | They retire; worker restart takes the guard and the audit                                                                         |
| T7  | A service disabled today could never be restarted once enable retires                             | Restart drops the disabled check; `F4.8` clears the flags in the PR that retires disable                                          |
| T8  | `B4.11` retired control routes the Operations page still calls (the plan PR's review)             | The five control routes retire in `F4.8`, with their UI callers (UR-9)                                                            |

## Done when

Each package: its golden path green on the fake stack and its real-tier check posted, and for F-140
the owner's witnessed restart on the live install. F-293's row reads **retired** (R2a row 9 deletes
its receiver); the other twelve rows read **works** once both packages have merged and their checks
are posted.
