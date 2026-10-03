# Metrics Implementation Status

What metric families exist, which ones production code actually observes,
and where Prometheus scrapes them. Grep-verified against the tree; re-run
the census (below) before trusting any count.

## Scraping Topology

| Job                                                                                                     | Target                                                              | What it carries                                                 |
| ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------- |
| `hsi-backend-metrics`                                                                                   | `backend:8000/api/metrics`                                          | All `hsi_*` backend families (`honor_labels: true`)             |
| `ai-vlm-metrics`                                                                                        | `ai-vlm:8098/metrics`                                               | llama.cpp native `llama_*` series (`--metrics` flag)            |
| `triton-metrics`                                                                                        | `ai-gateway:8002/metrics`                                           | Triton native `nv_inference_*` / `nv_gpu_*` by `model`          |
| `ai-gateway-metrics`                                                                                    | `ai-gateway:8090/metrics`                                           | Gateway app metrics only (`nv_*` dropped to avoid double-count) |
| `blackbox-http-2xx`                                                                                     | `ai-vlm:8098/health`, `ai-gateway:8090{,/yolo26,/enrich-lt}/health` | `probe_success` availability per AI endpoint                    |
| json-exporter modules                                                                                   | `backend:8000/api/system/{health,telemetry,stats,gpu}`              | JSON → gauge conversion (`monitoring/json-exporter-config.yml`) |
| node/redis exporters, cAdvisor (rootful systemd), dcgm (target `host.containers.internal`, port `9400`) | host                                                                | infra series                                                    |

Sources: `monitoring/prometheus.yml`. A few blackbox probe targets still
point at gateway routers that don't exist; those probes fail permanently and
cleaning them is a monitoring-config task.

## Backend Metrics With Live Production Observers

Defined in `backend/core/metrics.py` (119 `hsi_*` families total). These are
observed by shipped code paths — the ones to build alerts/dashboards on:

| Family                                                                                                                                                                                                   | Observer (production)                                                                                                 |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `hsi_detection_queue_depth`, `hsi_analysis_queue_depth`                                                                                                                                                  | `set_queue_depth` from `backend/services/pipeline_workers.py:1476`                                                    |
| `hsi_dlq_depth`, `hsi_queue_items_moved_to_dlq_total`, `hsi_queue_items_dropped_total`, `hsi_queue_items_rejected_total`, `hsi_queue_overflow_total`                                                     | queue/DLQ paths (`backend/services/retry_handler.py`, queue workers)                                                  |
| `hsi_stage_duration_seconds`                                                                                                                                                                             | pipeline stage timing                                                                                                 |
| `hsi_pipeline_errors_total`                                                                                                                                                                              | `record_pipeline_error` — e.g. `backend/services/vlm_analyzer.py:561` (`vlm_verification_failed`, `vlm_circuit_open`) |
| `hsi_detections_processed_total`                                                                                                                                                                         | `backend/services/detector_client.py:1376`                                                                            |
| `hsi_ai_request_duration_seconds{service}`                                                                                                                                                               | `DetectorClient` (service=`yolo26`), `backend/services/detector_client.py:1139`                                       |
| `hsi_ai_inference_duration_seconds`, `hsi_ai_inference_errors_total`                                                                                                                                     | `GatewayMetricsMiddleware`, `ai/gateway/main.py:83,90`                                                                |
| `hsi_specialist_unavailable_total{leg,reason}`                                                                                                                                                           | face/plate/re-ID lookup legs (bounded reason codes)                                                                   |
| `hsi_prompts_truncated_total`                                                                                                                                                                            | `record_prompt_truncated` from `backend/services/vlm_client.py:780` (prompt over the served slot)                     |
| `hsi_prompt_version_latency_seconds`, `hsi_prompt_rollbacks_total`, shadow comparison families                                                                                                           | `backend/services/prompt_service.py:247,304,414`                                                                      |
| `hsi_model_load_duration_seconds`, `hsi_model_warmup_duration_seconds`, `hsi_model_cold_start_total`, `hsi_model_warmth_state`                                                                           | residency/warmup paths (`vlm_client`, `detector_client`)                                                              |
| `hsi_worker_status`, `hsi_worker_active_count`, `hsi_worker_busy_count`, `hsi_worker_idle_count`, `hsi_worker_heartbeat_missed_total`, `hsi_worker_max_restarts_exceeded_total`, `hsi_pipeline_worker_*` | `backend/services/worker_supervisor.py`, `pipeline_workers.py`                                                        |
| `hsi_face_detections_total`, `hsi_face_embedding_duration_seconds`, `hsi_face_recognition_confidence`                                                                                                    | `backend/services/face_detector.py`                                                                                   |
| `hsi_reid_match_duration_seconds`, `hsi_track_duration_seconds`                                                                                                                                          | re-ID match / tracking paths                                                                                          |
| `hsi_zone_occupancy`, `hsi_zone_dwell_time_seconds`, `hsi_loitering_dwell_time_seconds`                                                                                                                  | `backend/services/zone_crossing_service.py`, `dwell_time_service.py`                                                  |
| `hsi_detection_confidence`                                                                                                                                                                               | scoring paths                                                                                                         |
| `hsi_budget_utilization_ratio`, `hsi_budget_exceeded_total`                                                                                                                                              | inference-budget tracking                                                                                             |
| `hsi_db_query_duration_seconds`, `hsi_slow_queries_total`                                                                                                                                                | SQLAlchemy event hooks, `backend/core/database.py:1470`                                                               |
| `hsi_rum_*` (fcp, lcp, inp, cls, fid, ttfb, page_load)                                                                                                                                                   | `POST /api/rum` (`backend/api/routes/rum.py`) fed by `frontend/src/services/rum.ts`                                   |

## Defined But Never Observed Outside Tests

Several defined families have **no production observer** — including
`hsi_events_created_total`, `hsi_events_by_risk_level_total`,
`hsi_events_by_camera_total`, the `hsi_face_*` gauges without a recorder call
(`hsi_face_embeddings_generated_total`, `hsi_face_matches_total`,
`hsi_face_quality_score`), the
`hsi_action_recognition_*` trio, and the `hsi_ab_rollout_*` set.
Two consequences:

- `prometheus_client` exports unlabelled families unconditionally, so some
  of these **scrape as zero-valued** — a flat line, not an absence.
- A dashboard panel over an unobserved family is indistinguishable from a
  broken pipeline unless you check the observer, not the series.

Regenerate the census (defined = name strings in `backend/core/metrics.py`;
observer = any non-test caller of the name or its `record_*`/`observe_*`
helper):

```bash
grep -c '"hsi_' backend/core/metrics.py            # defined
grep -rln --include="*.py" '"hsi_<name>"' backend/ ai/ | grep -v -e test -e core/metrics.py
```

## JSON Exporter Series

`monitoring/json-exporter-config.yml`, probed via blackbox-style modules.
Endpoints are under `/api/system/`:

| Module      | Target                  | Series                                                                                       |
| ----------- | ----------------------- | -------------------------------------------------------------------------------------------- |
| `health`    | `/api/system/health`    | `hsi_system_healthy`, `hsi_database_healthy`, `hsi_redis_healthy`, `hsi_ai_healthy`          |
| `telemetry` | `/api/system/telemetry` | `hsi_detection_queue_depth`, `hsi_analysis_queue_depth`, detect/batch/analyze avg/p95/p99 ms |
| `stats`     | `/api/system/stats`     | `hsi_total_cameras`, `hsi_total_events`, `hsi_total_detections`, `hsi_uptime_seconds`        |
| `gpu`       | `/api/system/gpu`       | `hsi_gpu_utilization`, memory/temp/clocks/pcie families                                      |

## Recording Rules

`monitoring/prometheus-rules.yml` (31 `record:` rules) computes the SLI/SLO
layer, among them `hsi:api_availability:ratio_rate30d`,
`hsi:detection_latency:p95_5m`, `hsi:analysis_latency:p95_5m`,
`hsi:error_budget:api_availability_remaining`,
`hsi:burn_rate:api_availability_1h`.
`monitoring/profiling-recording-rules.yml` adds the regression ratios
(`job:service_cpu_regression_ratio:5m_vs_24h` at
`monitoring/profiling-recording-rules.yml:121`,
`job:service_memory_regression_ratio:current_vs_6h` at
`monitoring/profiling-recording-rules.yml:140`) consumed by
`monitoring/profiling-regression-alerts.yml`.

## AI-Side Native Series

- **Triton** (`triton-metrics`): `nv_inference_request_success` /
  `_failure` / `_duration_us`, queue latency, batch sizes, `nv_gpu_*` — by
  `model`, from inside `ai-gateway`.
- **Gateway app** (`ai-gateway-metrics`): `hsi_ai_inference_duration_seconds`
  / `hsi_ai_inference_errors_total` by `service`/`endpoint`, plus process
  runtime.
- **llama.cpp** (`ai-vlm-metrics`): `llama_tokens_predicted_total`,
  `llama_tokens_prompt_total`, `llama_generation_time_seconds`,
  `llama_kv_cache_usage_ratio`, `llama_requests_processing`; tokens/sec =
  `rate(llama_tokens_predicted_total[1m])`. Only present while the `vlm`
  compose profile is up.
- **Availability**: `probe_success{job="blackbox-http-2xx", model=...}` for
  the live AI endpoints.

## External Dependencies

| Metric Prefix | Exporter          | Status                            |
| ------------- | ----------------- | --------------------------------- |
| `node_*`      | node_exporter     | Required for host metrics         |
| `redis_*`     | redis_exporter    | Required for Redis metrics        |
| `probe_*`     | blackbox_exporter | Required for synthetic monitoring |
| `container_*` | cAdvisor          | Rootful systemd service           |
| `DCGM_*`      | dcgm-exporter     | Rootful Podman, port 9400         |
| `llama_*`     | llama.cpp server  | `ai-vlm` with `--metrics`         |

## Related Documentation

- [Model Testing](model-testing.md) - The specialist counter contract
- `ai/gateway/AGENTS.md` - Gateway metrics middleware

---

[Back to Developer Hub](README.md)
