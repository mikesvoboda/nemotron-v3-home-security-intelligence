# Backend Services - Agent Guide

## Purpose

`backend/services/` holds the domain services: the detection→batch→analysis
pipeline and its Redis queues, the VLM path (client, analyzer, verdict,
specialists), alerting and delivery, camera/media machinery, entity
resolution and the operational workers. `backend/core/` is the foundation
these build on; this directory is where behaviour lives. Most modules expose
`reset_*()` singletons for tests (53 functions across 50 files — call them,
or a test inherits the previous test's state).

## Entry Points

| File                   | Role                                                                                                                                                                                        |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pipeline_workers.py`  | The queue workers, run as `python -m backend.services.pipeline_workers`: `DetectionQueueWorker`, `BatchTimeoutWorker`, `AnalysisQueueWorker`, `QueueMetricsWorker`, `PipelineWorkerManager` |
| `pipeline_factory.py`  | `build_pipeline_analyzer()` — the ONE analyzer construction point                                                                                                                           |
| `batch_aggregator.py`  | `add_detection()` / `close_batch()` — where a closed batch enters the analysis queue                                                                                                        |
| `vlm_analyzer.py`      | `VlmAnalyzer.analyze_batch()` — the analysis stage and its invariant table                                                                                                                  |
| `alerting/`            | The B4.1 alert pipeline: `pipeline.py` (`AlertPipeline`), `policy.py`, `planner.py` and the channel adapters in `alerting/channels/`                                                        |
| `worker_supervisor.py` | `WorkerSupervisor` — heartbeat-tracked worker registry main.py starts at boot                                                                                                               |
| `orchestrator/`        | Shared orchestration domain models (enums, registry)                                                                                                                                        |

## The Pipeline Flow (and its one rule)

```
FileWatcher → detection_queue → DetectionQueueWorker (DetectorClient.detect_objects,
                                 BatchAggregator.add_detection)
            → BatchTimeoutWorker closes batches → analysis_queue
            → AnalysisQueueWorker (VlmAnalyzer.analyze_batch) → Event rows + WS broadcast
```

- **One analyzer construction point.** Every production seam — the analysis
  worker's default (`pipeline_workers.py:757`), the API dependency
  (`backend/api/dependencies.py:959`), the DI container, and
  `batch_aggregator.py:1241`'s lazy fast path — asks
  `pipeline_factory.build_pipeline_analyzer()`. Before the seam each site
  spelled the analyzer by hand and flipping the mode meant finding every
  site; a fifth seam that copies an old construction line trips the
  source-scan pin `backend/tests/unit/services/test_pipeline_factory.py`.
- **The analysis worker's three dispositions** (ruling 199,
  `AnalysisDisposition`): `stored` (event exists; acknowledge), `terminal`
  (payload or batch lookup failed; dead-letter stream with the reason), and
  `retry` (anything else; the message stays pending for reclaim). Queue
  payloads are Pydantic-validated before they reach the analyzer — an
  invalid payload is rejected as a security event, not an error.

## The VLM Path (the shipped analyzer)

- **`vlm_verdict.py` is the single source of truth** for the `vlm_assess`
  contract: the JSON Schema is `model_json_schema()`, generated into the
  AI contract by `scripts/gen-ai-contract.py`; the constraint and the
  expected shape are never maintained separately (the E5 `nvext` defect is
  the counterexample). `risk_level` is NOT a field — the model never emits
  one; `SeverityService` derives it from `risk_score`.
- **The invariant table** (`vlm_analyzer.apply_verdict_invariants`): a
  `rejected` verdict clamps the score to ≤ `SeverityService.low_max` (the
  verdict gates alerts, the score still ranks — the clamp and its reason
  are visible in the stored reasoning); `uncertain` KEEPS its score; the
  risk level is ALWAYS derived; a verification failure scores NULL with
  the event row still written (the event exists so the UI shows "needs
  review").
- **ONE `vlm_assess` call.** The transport retry at temperature 0 lives in
  `vlm_client.py` (pinned by `test_vlm_client.TestFailureLadder`); when it
  still raises, `vlm_analyzer` maps the failure to `verification_failed` —
  it never re-retries (a second retry would double the S4 p95 budget).
  Sampling temperature is exactly 0 (greedy); the former 0.1 added noise.
- **Error hierarchy is load-bearing** (`vlm_client.py`): `VlmClientError` →
  `VlmTransportError` / `VlmSchemaError` (+ `VlmTruncatedError`) /
  `VlmContextOverflowError` / `VlmSlowReplyError` / `VlmUnavailableError` /
  `VlmImageError`. The retry calculus differs by class — a schema error
  re-sends identical bytes, so it is named apart from a transport error.
- **Idempotency**: the analyzer checks `batch_event:<batch_id>` in Redis
  before analyzing (mirroring the legacy path's key and TTL); the key is
  written AFTER the Event+EventVerification commit, in the same session 2
  transaction order. `close_batch` falls back to Postgres when Redis is
  down.
- **Sessions**: session 1 READ, NO session across the VLM call (it can
  consume the whole read budget), session 2 WRITE in one transaction,
  broadcast LAST and best-effort — a broadcast failure never un-does the
  committed event; the WS consumer catches up from the DB. Replay mode
  never broadcasts.
- **The VLM never originates an event**: absent a Redis batch or a queue
  payload, `analyze_batch` refuses loudly with zero writes.
- **Specialists never block the verdict** (`vlm_specialists.py`): every
  failure degrades to the text "unavailable"; nothing in the module raises
  into the analyzer. Four face outcomes, not two (`classify_face_outcome`).
  Replay never re-runs them — replay reads what production stored.

## Alerting and Delivery

- `alerting/pipeline.py` commits delivery rows and wakes the delivery
  worker immediately; the poll interval is only the fallback. The worker is
  registered in `delivery_worker_registry.py` by `main.py` — importing the
  worker into the pipeline would invert the dependency (the pipeline must
  not know channel adapters).
- The outbound webhook retry worker (`webhook_retry_worker.py`) is
  independent of Redis; it needs only the database.
- The WS event channel is `security_events` — `get_event_channel()` and the
  backward-compat `EventBroadcaster.CHANNEL_NAME` read
  `settings.redis_event_channel` (default in `backend/core/config.py`), not a
  literal; the message is `"type": "event"`, payload under `data`, pinned by
  `TestChannelDocumentation` in `test_websocket.py`.

## Patterns

- **Singleton reset for tests.** 53 `reset_*()` functions across 50 files
  (`severity.reset_severity_service()`,
  `circuit_breaker.reset_circuit_breaker_registry()`, ...). The Model Zoo
  needs TWO: `model_zoo.reset_model_zoo()` AND `model_zoo.reset_model_manager()`.
  Miss one and the next test inherits state that looks like flakiness.
- **Shared inference semaphore** (`inference_semaphore.py`,
  `get_inference_semaphore()`): all AI inference (detection, analysis) shares
  one asyncio semaphore; acquire it around any new direct inference call.
- **Circuit breakers**: `circuit_breaker.py` holds the AI-provider
  resilience registry (pre-registered at startup so the monitoring UI shows
  them before first use); `websocket_circuit_breaker.py` is the
  WebSocket-connection-specific one. Do not move AI resilience back into core.
- **Batch coalescing** (`batch_coalescer.py`): compatible detections (same
  camera, same primary class, similar confidence, under max batch size)
  merge into one inference call. New stages must respect its priority
  levels rather than queueing separately.

## Traps

- `build_pipeline_analyzer()` imports lazily on purpose — a test that
  patches the analyzer class must patch before the BUILD, not before an
  import; patching after an import silently misses.
- `vlm_verdict.py`'s import closure stays pydantic-only (the contract
  generator imports it at generation time); it deliberately re-states
  `VlmAssessContext`'s fields instead of importing `AssessInput`, and a
  test pins the two field sets together. Do not "deduplicate" the import.
- The workers run as a separate process (`python -m backend.services.pipeline_workers`)
  in CI/shards — a test that assumes the API process spawns them lies to itself.
- Retired services (`enrichment_pipeline`, `yolo_world_service`, the
  `nemotron_analyzer` name) are gone; the container registers
  `context_enricher` and `vlm_analyzer` instead. Old references to them in
  docs are drift — the retired-name ratchet (`.agents-md-validator.yml`)
  keeps counts falling.
- The REID gateway path (`reid_gateway.py` + `osnet_loader.py`) builds its
  URL from `settings.enrichment_light_url` → `{base}/person-reid` — never hardcode
  the port.

## How to Test

```bash
uv run pytest backend/tests/unit/services/ -n auto --dist=worksteal --timeout=60
uv run pytest backend/tests/unit/services/test_pipeline_factory.py --timeout=60
uv run pytest backend/tests/unit/services/test_vlm_analyzer.py --timeout=60
```

284 test files mirror the services: the analyzer suite pins the invariant table
line-by-line (`test_vlm_analyzer.py`, 114 tests), the client suite pins the
failure ladder (`test_vlm_client.py`, 86), the single-owner suite pins worker
counts, restart-on-death and clean shutdown (`test_pipeline_worker_single_owner.py`).

## Related

| Path                                             | What it holds                                               |
| ------------------------------------------------ | ----------------------------------------------------------- |
| `backend/AGENTS.md`                              | the lane root: lane-wide rules, the AI tier, how to test    |
| `backend/core/AGENTS.md`                         | config, DI container, queues the pipeline rides on          |
| `backend/models/AGENTS.md`                       | Event/EventVerification models this layer writes            |
| `backend/api/AGENTS.md`                          | the API dependencies that hand services to routes           |
| `backend/ai_contract/AGENTS.md`                  | the generated contract `vlm_verdict.py` feeds               |
| `backend/tests/unit/services/test_vlm_client.py` | the failure-ladder pin                                      |
| `docs/uplevel/4n-alerting.md`                    | the B4.1 alerting design the `alerting/` package implements |
