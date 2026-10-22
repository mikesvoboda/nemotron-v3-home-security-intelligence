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
  (`:474-475`); `ServiceHealthMonitor` probes only `yolo26` (`backend/main.py:706`). The VLM is not
  probed on purpose, so that a check never wakes it; its circuit breaker pushes its state instead
  (`backend/main.py:1113-1132`).
- **The UI still keys on `rtdetr` and `nemotron`.** The header badge (F-011) types its services as
  `rtdetr | nemotron | florence | clip` (`frontend/src/hooks/useAIServiceStatus.ts:25`) and waits
  for an `ai_service_status` message (`:131`) that nothing sends. The dashboard row and model cards
  (F-037, F-126) read `details.rtdetr` and `details.nemotron`
  (`frontend/src/hooks/useAIMetrics.ts:144-145`); the services panel (F-139) has `rtdetr` and
  `nemotron` cards (`ServicesPanel.tsx:102-115`); the latency chart (F-173) reads
  `rtdetr_latency_ms` (`PerformanceCharts.tsx:114-115`). F-015's banner was re-keyed by `[r267a]`
  (`useServiceStatus.ts:38-67`) and lacks only `ai-vlm`.
- **The latency series are pipeline stages.** `yolo26_latency_ms` comes from the watch-to-detect
  stage and `nemotron_latency_ms` from batch-to-analyse (`performance_collector.py:632-656`). The
  detector has a request histogram (`backend/services/detector_client.py:280`); the VLM has none.
- **Service controls restart real containers, unguarded.** `/api/system/services/{name}/restart`
  (`backend/api/routes/services.py:155-321`) restarts through the host Podman socket mounted into
  the backend (`backend/services/container_orchestrator.py:407-458`;
  `docker-compose.prod.yml:427`), with no check beyond `EXPOSE_LAN`'s login
  (`backend/api/middleware/auth.py`), weaker than `require_admin_access`
  (`backend/api/routes/admin.py:322`). Enable and disable only flip a self-healing flag
  (`container_orchestrator.py:342-405`); the UI's "stop" calls disable. Every card but `redis`
  answers 404 (`services.py:185`). Workers have their own restart routes
  (`system.py:4481`, `:4532`, `:4584`).
- **Infrastructure alerts never reach the badge (F-009).** Alertmanager posts to
  `/api/webhooks/alerts` (`monitoring/alertmanager.yml:180-192`;
  `docker-compose.prod.yml:1280`), which emits `infrastructure_alert` on the events channel
  (`backend/api/routes/webhooks.py:25-55`). The badge listens on `/ws/system`
  (`frontend/src/hooks/usePrometheusAlertWebSocket.ts:403-404`) for another shape (`:161-181`). The
  second receiver, `/api/v1/alertmanager/webhook` (`backend/api/routes/alertmanager.py`), is in no
  configuration; R2 deletes it and its `prometheus_alerts` table (`r2-sheet.md:201`). An alert that
  fired before the page opened shows only when Alertmanager repeats it, every 4 h
  (`monitoring/alertmanager.yml:63`).
- **Three small breaks.** The palette's System entry and `g y` open `/system`
  (`frontend/src/components/common/CommandPalette.tsx:93-94`;
  `frontend/src/hooks/useKeyboardShortcuts.ts:28`); the page is `/operations`. Tracing's link opens
  `http://localhost:16686` (`frontend/src/components/tracing/TracingPage.tsx:105`); the stack has
  Grafana's Tempo data source (uid `tempo`). Flush queues deletes `hsi:queue:*`
  (`admin.py:1360-1364`) while the pipeline's keys are `detection_queue`, `analysis_queue` and
  `dlq:*` (`backend/core/constants.py:146-177`).

## What the user can do when this is done

The household sees whether its detector and its VLM are working: the header badge, the dashboard
row and the model cards say ready, loading, idle (asleep) or failing, the same everywhere. An admin
can restart a stuck service from Operations. Infrastructure alerts appear in the header as they
fire, including ones already firing when the page opens. The latency chart shows how long each
model takes to answer.

## Decisions

| question                                   | decision                                                                                                                                                                                                                                                                                                         | why                                                                                                 |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| What can the services panel do?            | Restart only, admin-only and audited, for `ai-gateway`, `ai-vlm`, `redis` and `postgres`; worker cards use the worker restart routes. Enable and disable retire; self-healing stays automatic (owner, ST-1).                                                                                                     | One real action, guarded; enable and disable never stopped anything.                                |
| What does "AI service healthy" mean?       | One backend health module behind every badge and card. The detector is ready when the gateway reports its model loaded; the VLM is ready when its last call succeeded and its breaker is closed. A sleeping VLM is "Idle (asleep)", neutral, never probed awake; loading is amber; failing is red (owner, ST-2). | The case people need to see, a model that is not loaded, shows; a quiet night does not look broken. |
| Are the API names renamed?                 | Yes: `nemotron` becomes `ai_vlm` and `rtdetr` becomes `yolo26` in every status field and schema; branding and prompt management keep their names.                                                                                                                                                                | R2 ruled the re-key; a UI-only relabel would leave the old names in the contract.                   |
| What does the latency chart show?          | Each model's inference latency: the detector's request histogram, and a new one for the VLM.                                                                                                                                                                                                                     | The chart's labels claim model latency; the stage timings stay on the pipeline panel.               |
| How do infrastructure alerts reach the UI? | The badge reads `infrastructure_alert` on `/ws/events`, and loads the alerts firing now once, on page open, through a backend proxy of Alertmanager's `/api/v2/alerts`. The unused receiver and its table retire.                                                                                                | The one path Alertmanager posts to; no four-hour gap.                                               |
| The small rows                             | `/system` becomes `/operations`; Tracing opens Grafana's Explore on the `tempo` data source; flush queues deletes the pipeline's own keys, overflow dead-letter queues included, and the unused prefix helper goes.                                                                                              | What R2 ruled, made exact.                                                                          |

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
    reads the circuit breaker's pushed state and the last call's outcome; a VLM with no call since
    its idle timeout is `idle`, and the module never sends it a request.
  - `snapshot() -> dict[str, ServiceState]`, the one shape every route and broadcast returns.
  - `on_change(callback)`: the broadcaster publishes `ai_service_status` on a change of state.
  - Invariants: no path probes `ai-vlm`; a probe error is `failing` with its message, never
    `ready`.
- **Its adapters:** `GET /api/system/health`, `/health/full` and `/api/health/ai-services` return
  `snapshot()`'s entries; `SystemBroadcaster` and `PerformanceCollector` read it; the
  `ai_service_status` message feeds the header badge.
- **Service controls:** `POST /api/system/services/{name}/restart` under `require_admin_access`,
  audited with the person, for the four named services, `ai-vlm` gaining its registry row. The
  enable and disable routes retire.
- **Infrastructure alerts:** `GET /api/system/infrastructure-alerts` proxies Alertmanager's firing
  alerts, mapped to the `infrastructure_alert` shape the socket carries.

## What changes

- **backend (`B4.11`):** `ai_health.py` (new); `system.py`, `health_ai_services.py`,
  `system_broadcaster.py`, `performance_collector.py` and `main.py`'s monitor read it;
  `backend/api/schemas/performance.py` renames its fields; `detector_client.py`'s histogram feeds
  the chart, and the VLM client gains one; `services.py` and `container_orchestrator.py` (restart
  only, the admin guard, the audit, the `ai-vlm` row); the infrastructure-alerts proxy route;
  `alertmanager.py` and the `prometheus_alerts` table retire with a recorded upgrade, through
  `scripts/retired_paths.txt`; `admin.py`'s flush keys and `constants.py`'s helper;
  `docs/openapi.json` and the generated types are regenerated (UR-83).
- **frontend (`F4.8`):** `useAIServiceStatus`, `AIServiceStatus`, `useAIMetrics`,
  `AIPerformanceSummaryRow`, `AIModelsSettings`, `ModelStatusCards`, `ServicesPanel`,
  `PerformanceCharts`, `usePerformanceMetrics`, `PerformanceDashboard`, `useFullHealthQuery`,
  `metricsParser`, `useServiceStatus` (`ai-vlm`), `usePrometheusAlertWebSocket` (events socket,
  shape, page-open load), `CommandPalette`, `useKeyboardShortcuts`, `TracingPage`; test fixtures
  (`test-utils/factories.ts`, `services/__mocks__/api.ts`).
- **monitoring:** none; the Tempo data source and Alertmanager's sink stay.

## Failure handling

- **The gateway unreachable:** `yolo26` is `failing` with the error; the VLM's state is unaffected.
- **No VLM call yet since start:** `ai_vlm` is `unknown` until its first call or breaker push, then
  follows them; it is never probed.
- **Alertmanager unreachable on page open:** the badge shows what the socket brings and says the
  current list could not be loaded.
- **A restart that fails:** the route answers the engine's error, and the audit records it.

## Tests

- **Consolidation scope:** the six producers and their routes, `services.py`,
  `container_orchestrator.py`, `webhooks.py`, `alertmanager.py`, `admin.py`'s flush, and the
  frontend hooks and components named above.
- **Tests through the interface:** each state for each service, including `idle` reached without a
  probe and a probe error never `ready`; every route returns `snapshot()`'s shape; a state change
  publishes `ai_service_status`; restart is refused without admin and audited with it; enable and
  disable answer 404; the proxy's mapping; flush deletes exactly the pipeline's keys.

## Golden path

- **Spec, UI** (Playwright): the header badge, the dashboard row and the model cards show the fake
  stack's `yolo26` ready and `ai_vlm` idle; Operations' restart works as admin and is refused
  otherwise; an infrastructure alert posted to the sink appears in the header, and one already
  firing appears on page open; `g y` opens `/operations`; Tracing's link opens Grafana's Explore on
  `tempo`. The edits to `dashboard/ai-summary-row.spec.ts`, `operations/performance.spec.ts`,
  `operations/grafana-embeds.spec.ts` and `shell/palette.spec.ts` follow the new keys and links.
- **Fake-stack scenario:** the fake gateway reports its model loaded; the fake VLM answers one call
  and then idles.
- **Real-tier check:** on the GB300 test deployment the operator reads the badge with the VLM asleep
  (idle, no request in the VLM's log from the check) and awake after one analysis (ready).

## Privacy and security

No personal data. Restart moves behind `require_admin_access` and is audited with the person; enable
and disable retire. The infrastructure-alerts proxy needs a session or API key with
`EXPOSE_LAN=true`, as every route does.

## Rollout and reversal

The renamed API fields and the retired routes ship with their regenerated contract and types in the
same packages. The `prometheus_alerts` table retires through a recorded upgrade. Code reversal is a
revert; the upgrade stays.

## Packages

| package | lane (proposed) | depends on | contents                                                                                                                                                | its own golden path       |
| ------- | --------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `B4.11` | backend         | none       | The health module and its readers, the renamed fields, the latency histograms, restart only under admin, the alerts proxy, the retirements, flush keys. | Backend pytest of routes. |
| `F4.8`  | frontend        | `B4.11`    | The badge, row, cards, panel, chart, banner, the alert badge's socket and load, the palette, Tracing.                                                   | Playwright above.         |

Each runs the six steps as two PRs: a test-only consolidation PR, then the build.

## Done when

Each package: its golden path green on the fake stack and its real-tier check posted. F-293's row
reads **retired** (R2a row 9 deletes its receiver); the other twelve rows read **works** once both
packages have merged and the real-tier check is posted.
