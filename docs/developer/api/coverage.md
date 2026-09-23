# API Coverage Documentation

> **How this document is produced (2026-09-22 rewrite).** The endpoint inventory below
> was built mechanically from `docs/openapi.json` (paths × methods), and every
> Consumer(s) cell is the output of a per-path grep over real frontend source
> (`frontend/src`, excluding generated types, mocks, and `*.test.*` files).
> There is **no committed script that regenerates this document** — see
> [Generation & Validation](#generation--validation) for the exact pipeline.

## Overview

This document maps backend API endpoints to their frontend consumers and lists the
endpoints that intentionally (or not yet) have none.

**Surface:** 386 paths / 468 operations in `docs/openapi.json`.
**Consumed:** 385 operations have at least one verified frontend
source consumer; 83 do not and are listed in
[Backend-only endpoints](#backend-only-endpoints).

## Generation & Validation

Two automations back this document; neither rewrites it:

1. **Spec generation** — `uv run python scripts/generate-openapi.py` writes
   `docs/openapi.json` from `backend.main:app` (add `--check` to verify the
   committed spec is current; `--force` to rewrite it). The
   `generate-openapi` pre-commit hook runs the same generator, so the committed
   spec cannot silently drift.
2. **Coverage gate** — `./scripts/check-api-coverage.sh` (CI job `api-coverage`)
   enumerates route decorators under `backend/api/routes/` and greps
   `frontend/src` per path. It is a read-only pass/fail gate over _decorator
   paths_; it writes nothing and does not read `docs/openapi.json`.

The tables here were rebuilt on 2026-09-22 by a one-off pass: for each
`docs/openapi.json` path, a template-literal-aware regex
(`{param}` → `${…}`-or-segment) matched against every non-test, non-mock,
non-generated file under `frontend/src`, including helper-base joins
(e.g. `fetchGpuConfigApi('/gpu-config')` under a `/api/system` base) and
wrapper-function attribution (an exported fetch wrapper in `services/`
attributes its file, and components importing it count as consumers).

**Note:** some internal/admin endpoints are intentionally frontend-free; new
intentionally-unused endpoints go in the allowlist in
`scripts/check-api-coverage.sh` with a justification comment.

## OpenAPI Specification

The complete specification is committed at `docs/openapi.json` and regenerated with:

```bash
uv run python scripts/generate-openapi.py            # rewrite docs/openapi.json
uv run python scripts/generate-openapi.py --check    # CI mode: fail if stale
```

(`./scripts/generate-types.sh` generates `frontend/src/types/generated/api.ts`
from the app — it writes a throwaway spec under `/tmp`, not `docs/openapi.json`.)

Interactive documentation at runtime:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## API Endpoints by Domain

One row per method. `—` means no consumer was found under `frontend/src`
(those rows are collected with reasons in
[Backend-only endpoints](#backend-only-endpoints) rather than left dangling).
The gateway surface `POST /api/system/models/{model_name}/load|unload|reload`
answers **501** by design (Triton runs `--model-control-mode=none`).

### Root, Health & Readiness

| Endpoint  | Method | Consumer(s)                       | Purpose |
| --------- | ------ | --------------------------------- | ------- |
| `/`       | GET    | —                                 | Root    |
| `/health` | GET    | `detectorApi.ts`, `webhookApi.ts` | Health  |
| `/ready`  | GET    | —                                 | Ready   |

### System

| Endpoint                                               | Method | Consumer(s)                                                                                                              | Purpose                            |
| ------------------------------------------------------ | ------ | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------- |
| `/api/system/ai-services`                              | GET    | `gpuConfigApi.ts`                                                                                                        | List available AI services         |
| `/api/system/anomaly-config`                           | GET    | `api.ts`                                                                                                                 | Get Anomaly Config                 |
| `/api/system/anomaly-config`                           | PATCH  | `api.ts`                                                                                                                 | Update Anomaly Config              |
| `/api/system/circuit-breakers`                         | GET    | `api.ts`                                                                                                                 | Get Circuit Breakers               |
| `/api/system/circuit-breakers/{name}/reset`            | POST   | `api.ts`, `useCircuitBreakerDebugQuery.ts`                                                                               | Reset Circuit Breaker              |
| `/api/system/cleanup`                                  | POST   | `FileOperationsPanel.tsx`, `api.ts`                                                                                      | Trigger Cleanup                    |
| `/api/system/cleanup/orphaned-files`                   | POST   | `api.ts`                                                                                                                 | Run Orphaned File Cleanup          |
| `/api/system/cleanup/status`                           | GET    | `api.ts`                                                                                                                 | Get Cleanup Status                 |
| `/api/system/config`                                   | GET    | `ProcessingSettings.tsx`, `api.ts`, `useSystemConfigQuery.ts`                                                            | Get Config                         |
| `/api/system/config`                                   | PATCH  | `ProcessingSettings.tsx`, `api.ts`, `useSystemConfigQuery.ts`                                                            | Patch Config                       |
| `/api/system/gpu`                                      | GET    | `api.ts`, `useGpuHistory.ts`, `useGpuStatsQuery.ts`                                                                      | Get Gpu Stats                      |
| `/api/system/gpu-config`                               | GET    | `gpuConfigApi.ts`                                                                                                        | Get GPU configuration              |
| `/api/system/gpu-config`                               | PUT    | `gpuConfigApi.ts`                                                                                                        | Update GPU configuration           |
| `/api/system/gpu-config/apply`                         | POST   | `gpuConfigApi.ts`                                                                                                        | Apply GPU configuration            |
| `/api/system/gpu-config/detect`                        | POST   | `gpuConfigApi.ts`                                                                                                        | Re-detect GPUs                     |
| `/api/system/gpu-config/export`                        | GET    | `gpuConfigApi.ts`                                                                                                        | Export current GPU configuration   |
| `/api/system/gpu-config/history`                       | GET    | `gpuConfigApi.ts`                                                                                                        | List configuration version history |
| `/api/system/gpu-config/history/diff`                  | GET    | `gpuConfigApi.ts`                                                                                                        | Compare two configuration versions |
| `/api/system/gpu-config/history/{version_id}`          | GET    | `gpuConfigApi.ts`                                                                                                        | Get configuration version details  |
| `/api/system/gpu-config/import`                        | POST   | `gpuConfigApi.ts`                                                                                                        | Import GPU configuration           |
| `/api/system/gpu-config/preview`                       | GET    | `gpuConfigApi.ts`                                                                                                        | Preview auto-assignment            |
| `/api/system/gpu-config/rollback`                      | POST   | `gpuConfigApi.ts`                                                                                                        | Rollback to previous configuration |
| `/api/system/gpu-config/services`                      | GET    | `gpuConfigApi.ts`                                                                                                        | Get AI service health status       |
| `/api/system/gpu-config/status`                        | GET    | `gpuConfigApi.ts`                                                                                                        | Get apply operation status         |
| `/api/system/gpu/history`                              | GET    | `api.ts`, `gpuHistoryApi.ts`, `useGpuStatsQuery.ts`                                                                      | Get Gpu Stats History              |
| `/api/system/gpus`                                     | GET    | `gpuConfigApi.ts`                                                                                                        | List detected GPUs                 |
| `/api/system/health`                                   | GET    | `api.ts`, `useAIMetrics.ts`, `useHealthStatus.ts`, `useHealthStatusQuery.ts`                                             | Get Health                         |
| `/api/system/health/full`                              | GET    | `api.ts`, `useFullHealthQuery.ts`                                                                                        | Get Full System Health Status      |
| `/api/system/health/live`                              | GET    | `api.ts`                                                                                                                 | Get Liveness                       |
| `/api/system/health/ready`                             | GET    | `api.ts`                                                                                                                 | Get Readiness                      |
| `/api/system/health/websocket`                         | GET    | `api.ts`                                                                                                                 | Get Websocket Health               |
| `/api/system/model-zoo/latency/history`                | GET    | `api.ts`                                                                                                                 | Get Model Zoo Latency History      |
| `/api/system/model-zoo/status`                         | GET    | `api.ts`                                                                                                                 | Get Model Zoo Status               |
| `/api/system/models`                                   | GET    | `api.ts`, `modelZooApi.ts`, `useModelZooStatus.ts`, `useModelZooStatusQuery.ts`                                          | Get Model Zoo Registry             |
| `/api/system/models/unload-all`                        | POST   | `modelZooApi.ts`                                                                                                         | Unload All Models                  |
| `/api/system/models/vram-summary`                      | GET    | `modelZooApi.ts`                                                                                                         | Get Vram Summary                   |
| `/api/system/models/{model_name}`                      | GET    | `modelZooApi.ts`                                                                                                         | Get Model Status                   |
| `/api/system/models/{model_name}/load`                 | POST   | `modelZooApi.ts`                                                                                                         | Load Model                         |
| `/api/system/models/{model_name}/reload`               | POST   | `modelZooApi.ts`                                                                                                         | Reload Model                       |
| `/api/system/models/{model_name}/status`               | GET    | —                                                                                                                        | Get Model Status                   |
| `/api/system/models/{model_name}/unload`               | POST   | `modelZooApi.ts`                                                                                                         | Unload Model                       |
| `/api/system/monitoring/health`                        | GET    | `monitoringApi.ts`                                                                                                       | Get Monitoring Health              |
| `/api/system/monitoring/targets`                       | GET    | `monitoringApi.ts`                                                                                                       | Get Monitoring Targets             |
| `/api/system/nemotron-optimizer`                       | GET    | —                                                                                                                        | Get Nemotron Optimizer Status      |
| `/api/system/nemotron-optimizer/reset`                 | POST   | —                                                                                                                        | Reset Nemotron Optimizer Circuit   |
| `/api/system/performance`                              | GET    | `useAIMetrics.ts`                                                                                                        | Get Performance Metrics            |
| `/api/system/performance/history`                      | GET    | `performanceHistoryApi.ts`                                                                                               | Get Performance History            |
| `/api/system/pipeline`                                 | GET    | `BatchStatisticsDashboard.tsx`, `api.ts`, `useBatchAggregatorStatus.ts`, `useBatchStatistics.ts`, `usePipelineStatus.ts` | Get Pipeline Status                |
| `/api/system/pipeline-latency`                         | GET    | `api.ts`, `useAIMetrics.ts`                                                                                              | Get Pipeline Latency               |
| `/api/system/pipeline-latency/history`                 | GET    | `LatencyPanel.tsx`, `api.ts`, `pipelineLatencyApi.ts`                                                                    | Get Pipeline Latency History       |
| `/api/system/services`                                 | GET    | `api.ts`                                                                                                                 | List Services                      |
| `/api/system/services/{name}/disable`                  | POST   | `api.ts`, `useServiceMutations.ts`                                                                                       | Disable Service                    |
| `/api/system/services/{name}/enable`                   | POST   | `api.ts`, `useServiceMutations.ts`                                                                                       | Enable Service                     |
| `/api/system/services/{name}/restart`                  | POST   | `api.ts`, `useServiceMutations.ts`                                                                                       | Restart Service                    |
| `/api/system/services/{name}/start`                    | POST   | `api.ts`, `useServiceMutations.ts`                                                                                       | Start Service                      |
| `/api/system/severity`                                 | GET    | `SeverityThresholds.tsx`, `api.ts`, `risk.ts`, `severity.ts`, `useSeverityConfig.ts`                                     | Get Severity Metadata              |
| `/api/system/severity`                                 | PUT    | `SeverityThresholds.tsx`, `api.ts`, `risk.ts`, `severity.ts`, `useSeverityConfig.ts`                                     | Update Severity Thresholds         |
| `/api/system/stats`                                    | GET    | `api.ts`                                                                                                                 | Get Stats                          |
| `/api/system/storage`                                  | GET    | `FileOperationsPanel.tsx`, `api.ts`, `useStorageStatsQuery.ts`                                                           | Get Storage Stats                  |
| `/api/system/supervisor`                               | GET    | `supervisorApi.ts`                                                                                                       | Get Supervisor Status              |
| `/api/system/supervisor/reset/{worker_name}`           | POST   | `supervisorApi.ts`                                                                                                       | Reset Worker                       |
| `/api/system/supervisor/restart-history`               | GET    | `supervisorApi.ts`                                                                                                       | Get Restart History                |
| `/api/system/supervisor/status`                        | GET    | —                                                                                                                        | Get Supervisor Full Status         |
| `/api/system/supervisor/workers/{worker_name}/restart` | POST   | `supervisorApi.ts`                                                                                                       | Restart Supervisor Worker          |
| `/api/system/supervisor/workers/{worker_name}/start`   | POST   | `supervisorApi.ts`                                                                                                       | Start Supervisor Worker            |
| `/api/system/supervisor/workers/{worker_name}/stop`    | POST   | `supervisorApi.ts`                                                                                                       | Stop Supervisor Worker             |
| `/api/system/telemetry`                                | GET    | `PipelineTelemetry.tsx`, `api.ts`, `useAIMetrics.ts`                                                                     | Get Telemetry                      |
| `/api/system/websocket/events`                         | GET    | `api.ts`, `websocket-events.ts`                                                                                          | List Websocket Event Types         |

### Detector Registry

| Endpoint                                   | Method | Consumer(s) | Purpose                       |
| ------------------------------------------ | ------ | ----------- | ----------------------------- |
| `/system/detectors`                        | GET    | —           | List all registered detectors |
| `/system/detectors/active`                 | GET    | —           | Get active detector           |
| `/system/detectors/active`                 | PUT    | —           | Switch active detector        |
| `/system/detectors/{detector_type}`        | GET    | —           | Get detector configuration    |
| `/system/detectors/{detector_type}/health` | GET    | —           | Check detector health         |

### Action Events

| Endpoint                                | Method | Consumer(s)          | Purpose                  |
| --------------------------------------- | ------ | -------------------- | ------------------------ |
| `/api/action-events`                    | GET    | `actionEventsApi.ts` | List Action Events       |
| `/api/action-events`                    | POST   | `actionEventsApi.ts` | Create Action Event      |
| `/api/action-events/camera/{camera_id}` | GET    | `actionEventsApi.ts` | Get Camera Action Events |
| `/api/action-events/suspicious`         | GET    | `actionEventsApi.ts` | List Suspicious Actions  |
| `/api/action-events/{event_id}`         | DELETE | `actionEventsApi.ts` | Delete Action Event      |
| `/api/action-events/{event_id}`         | GET    | `actionEventsApi.ts` | Get Action Event         |

<!-- POST /api/action-events/analyze removed 2026-09-23 (X-CLIP full removal); openapi regen confirmed clean -->

### Admin

| Endpoint                              | Method | Consumer(s)            | Purpose               |
| ------------------------------------- | ------ | ---------------------- | --------------------- |
| `/api/admin/cleanup/orphans`          | POST   | `useAdminMutations.ts` | Cleanup Orphans       |
| `/api/admin/maintenance/clear-cache`  | POST   | `useAdminMutations.ts` | Clear Cache           |
| `/api/admin/maintenance/flush-queues` | POST   | `useAdminMutations.ts` | Flush Queues          |
| `/api/admin/seed/cameras`             | POST   | `useAdminMutations.ts` | Seed Cameras          |
| `/api/admin/seed/clear`               | DELETE | `useAdminMutations.ts` | Clear Seeded Data     |
| `/api/admin/seed/events`              | POST   | `useAdminMutations.ts` | Seed Events           |
| `/api/admin/seed/pipeline-latency`    | POST   | `useAdminMutations.ts` | Seed Pipeline Latency |
| `/api/admin/users`                    | GET    | —                      | List Users            |
| `/api/admin/users`                    | POST   | —                      | Create User           |
| `/api/admin/users/{user_id}`          | DELETE | —                      | Delete User           |

### AI Audit

| Endpoint                                   | Method | Consumer(s)                              | Purpose                |
| ------------------------------------------ | ------ | ---------------------------------------- | ---------------------- |
| `/api/ai-audit/batch`                      | POST   | `aiAuditApi.ts`, `auditApi.ts`           | Trigger Batch Audit    |
| `/api/ai-audit/batch/{job_id}`             | GET    | —                                        | Get Batch Audit Status |
| `/api/ai-audit/events/{event_id}`          | GET    | `aiAuditApi.ts`, `api.ts`, `auditApi.ts` | Get Event Audit        |
| `/api/ai-audit/events/{event_id}/evaluate` | POST   | `aiAuditApi.ts`, `auditApi.ts`           | Evaluate Event         |
| `/api/ai-audit/leaderboard`                | GET    | `aiAuditApi.ts`, `api.ts`, `auditApi.ts` | Get Model Leaderboard  |
| `/api/ai-audit/recommendations`            | GET    | `aiAuditApi.ts`, `api.ts`, `auditApi.ts` | Get Recommendations    |
| `/api/ai-audit/stats`                      | GET    | `aiAuditApi.ts`, `api.ts`, `auditApi.ts` | Get Audit Stats        |

### Alert Service

| Endpoint                                           | Method | Consumer(s) | Purpose           |
| -------------------------------------------------- | ------ | ----------- | ----------------- |
| `/api/alert-service/alerts`                        | GET    | —           | List Alerts       |
| `/api/alert-service/alerts`                        | POST   | —           | Create Alert      |
| `/api/alert-service/alerts/{alert_id}`             | DELETE | —           | Delete Alert      |
| `/api/alert-service/alerts/{alert_id}`             | GET    | —           | Get Alert         |
| `/api/alert-service/alerts/{alert_id}`             | PUT    | —           | Update Alert      |
| `/api/alert-service/alerts/{alert_id}/acknowledge` | POST   | —           | Acknowledge Alert |
| `/api/alert-service/alerts/{alert_id}/dismiss`     | POST   | —           | Dismiss Alert     |

### Alerts

| Endpoint                             | Method | Consumer(s)                              | Purpose           |
| ------------------------------------ | ------ | ---------------------------------------- | ----------------- |
| `/api/alerts/rules`                  | GET    | `api.ts`                                 | List Rules        |
| `/api/alerts/rules`                  | POST   | `api.ts`                                 | Create Rule       |
| `/api/alerts/rules/{rule_id}`        | DELETE | `api.ts`                                 | Delete Rule       |
| `/api/alerts/rules/{rule_id}`        | GET    | `api.ts`                                 | Get Rule          |
| `/api/alerts/rules/{rule_id}`        | PUT    | `api.ts`                                 | Update Rule       |
| `/api/alerts/rules/{rule_id}/test`   | POST   | `api.ts`                                 | Test Rule         |
| `/api/alerts/{alert_id}/acknowledge` | POST   | `alertsApi.ts`, `api.ts`, `useAlerts.ts` | Acknowledge Alert |
| `/api/alerts/{alert_id}/dismiss`     | POST   | `alertsApi.ts`, `api.ts`, `useAlerts.ts` | Dismiss Alert     |

### Analytics

| Endpoint                                 | Method | Consumer(s)                                               | Purpose                     |
| ---------------------------------------- | ------ | --------------------------------------------------------- | --------------------------- |
| `/api/analytics/calibration`             | GET    | —                                                         | Get Calibration Status      |
| `/api/analytics/camera-activity`         | GET    | `analytics.ts`, `api.ts`                                  | Get Camera Activity         |
| `/api/analytics/camera-uptime`           | GET    | `analytics.ts`, `api.ts`                                  | Get Camera Uptime           |
| `/api/analytics/costs`                   | GET    | `api.ts`                                                  | Get Cost Analytics          |
| `/api/analytics/costs/trends`            | GET    | `api.ts`                                                  | Get Cost Trends             |
| `/api/analytics/detection-trends`        | GET    | `analytics.ts`, `api.ts`, `useDetectionTrendsQuery.ts`    | Get Detection Trends        |
| `/api/analytics/object-distribution`     | GET    | `analytics.ts`, `api.ts`, `useObjectDistributionQuery.ts` | Get Object Distribution     |
| `/api/analytics/risk-history`            | GET    | `analytics.ts`, `api.ts`, `useRiskHistoryQuery.ts`        | Get Risk History            |
| `/api/analytics/risk-score-distribution` | GET    | `analytics.ts`, `api.ts`, `useRiskScoreDistribution.ts`   | Get Risk Score Distribution |
| `/api/analytics/risk-score-trends`       | GET    | `analytics.ts`, `api.ts`, `useRiskScoreTrends.ts`         | Get Risk Score Trends       |

### Analytics Zones

| Endpoint                                                           | Method | Consumer(s)                                                                                                                                  | Purpose                                           |
| ------------------------------------------------------------------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `/api/analytics-zones/`                                            | GET    | `LoiteringConfigModal.tsx`, `useApproachVectors.ts`, `useDwellTimeAnalytics.ts`, `useLineZoneAnalytics.ts`, `useZoneComparison.ts` (+1 more) | List analytics zone types                         |
| `/api/analytics-zones/approach-vectors/camera/{camera_id}`         | GET    | `useApproachVectors.ts`                                                                                                                      | Get approach vectors for all zones on a camera    |
| `/api/analytics-zones/comparison`                                  | GET    | `useZoneComparison.ts`                                                                                                                       | Compare metrics across multiple zones             |
| `/api/analytics-zones/entity-distribution`                         | GET    | `useZoneEntityDistribution.ts`                                                                                                               | Get entity distribution across all polygon zones  |
| `/api/analytics-zones/line-zones`                                  | POST   | —                                                                                                                                            | Create a new line zone                            |
| `/api/analytics-zones/line-zones/camera/{camera_id}`               | GET    | `useLineZoneAnalytics.ts`                                                                                                                    | Get all line zones for a camera                   |
| `/api/analytics-zones/line-zones/{zone_id}`                        | DELETE | `useLineZoneAnalytics.ts`                                                                                                                    | Delete a line zone                                |
| `/api/analytics-zones/line-zones/{zone_id}`                        | GET    | `useLineZoneAnalytics.ts`                                                                                                                    | Get a line zone by ID                             |
| `/api/analytics-zones/line-zones/{zone_id}`                        | PATCH  | `useLineZoneAnalytics.ts`                                                                                                                    | Update a line zone                                |
| `/api/analytics-zones/line-zones/{zone_id}/crossing-trends`        | GET    | `useLineZoneAnalytics.ts`                                                                                                                    | Get crossing trends for a line zone               |
| `/api/analytics-zones/line-zones/{zone_id}/reset-counts`           | POST   | `useLineZoneAnalytics.ts`                                                                                                                    | Reset crossing counts for a line zone             |
| `/api/analytics-zones/polygon-zones`                               | POST   | —                                                                                                                                            | Create a new polygon zone                         |
| `/api/analytics-zones/polygon-zones/camera/{camera_id}`            | GET    | `useDwellTimeAnalytics.ts`                                                                                                                   | Get all polygon zones for a camera                |
| `/api/analytics-zones/polygon-zones/{zone_id}`                     | DELETE | `LoiteringConfigModal.tsx`, `useApproachVectors.ts`, `useDwellTimeAnalytics.ts`, `useZoneActivityHeatmap.ts`, `useZoneEntityDistribution.ts` | Delete a polygon zone                             |
| `/api/analytics-zones/polygon-zones/{zone_id}`                     | GET    | `LoiteringConfigModal.tsx`, `useApproachVectors.ts`, `useDwellTimeAnalytics.ts`, `useZoneActivityHeatmap.ts`, `useZoneEntityDistribution.ts` | Get a polygon zone by ID                          |
| `/api/analytics-zones/polygon-zones/{zone_id}`                     | PATCH  | `LoiteringConfigModal.tsx`, `useApproachVectors.ts`, `useDwellTimeAnalytics.ts`, `useZoneActivityHeatmap.ts`, `useZoneEntityDistribution.ts` | Update a polygon zone                             |
| `/api/analytics-zones/polygon-zones/{zone_id}/activity-heatmap`    | GET    | `useZoneActivityHeatmap.ts`                                                                                                                  | Get activity heatmap data for a polygon zone      |
| `/api/analytics-zones/polygon-zones/{zone_id}/approach-vectors`    | GET    | `useApproachVectors.ts`                                                                                                                      | Get approach vectors for a polygon zone           |
| `/api/analytics-zones/polygon-zones/{zone_id}/check-loitering`     | POST   | —                                                                                                                                            | Check for loitering in a polygon zone             |
| `/api/analytics-zones/polygon-zones/{zone_id}/dwell-history`       | GET    | —                                                                                                                                            | Get dwell time history for a polygon zone         |
| `/api/analytics-zones/polygon-zones/{zone_id}/dwell-statistics`    | GET    | `useDwellTimeAnalytics.ts`                                                                                                                   | Get dwell time statistics for a polygon zone      |
| `/api/analytics-zones/polygon-zones/{zone_id}/dwellers`            | GET    | `useDwellTimeAnalytics.ts`                                                                                                                   | Get active dwellers in a polygon zone             |
| `/api/analytics-zones/polygon-zones/{zone_id}/entity-distribution` | GET    | `useZoneEntityDistribution.ts`                                                                                                               | Get entity type distribution for a polygon zone   |
| `/api/analytics-zones/polygon-zones/{zone_id}/loitering-config`    | GET    | `LoiteringConfigModal.tsx`                                                                                                                   | Get loitering configuration for a polygon zone    |
| `/api/analytics-zones/polygon-zones/{zone_id}/loitering-config`    | PATCH  | `LoiteringConfigModal.tsx`                                                                                                                   | Update loitering configuration for a polygon zone |
| `/api/analytics-zones/polygon-zones/{zone_id}/toggle-active`       | POST   | —                                                                                                                                            | Toggle the active status of a polygon zone        |

### Audit

| Endpoint                | Method | Consumer(s)                  | Purpose         |
| ----------------------- | ------ | ---------------------------- | --------------- |
| `/api/audit`            | GET    | `AuditLogPage.tsx`, `api.ts` | List Audit Logs |
| `/api/audit/stats`      | GET    | `AuditLogPage.tsx`, `api.ts` | Get Audit Stats |
| `/api/audit/{audit_id}` | GET    | `AuditLogPage.tsx`, `api.ts` | Get Audit Log   |

### Auth

| Endpoint                      | Method | Consumer(s)  | Purpose          |
| ----------------------------- | ------ | ------------ | ---------------- |
| `/api/auth/api-keys`          | GET    | —            | List Api Keys    |
| `/api/auth/api-keys`          | POST   | —            | Create Api Key   |
| `/api/auth/api-keys/{key_id}` | DELETE | —            | Revoke Api Key   |
| `/api/auth/login`             | POST   | `authApi.ts` | Login            |
| `/api/auth/logout`            | POST   | `authApi.ts` | Logout           |
| `/api/auth/me`                | GET    | `authApi.ts` | Get Me           |
| `/api/auth/register`          | POST   | `authApi.ts` | Register User    |
| `/api/auth/setup-status`      | GET    | `authApi.ts` | Get Setup Status |

### Auto-Enrollment

| Endpoint                        | Method | Consumer(s) | Purpose                      |
| ------------------------------- | ------ | ----------- | ---------------------------- |
| `/api/auto-enrollment/settings` | GET    | —           | Get Auto Enrollment Settings |

### Backup

| Endpoint                        | Method | Consumer(s)    | Purpose              |
| ------------------------------- | ------ | -------------- | -------------------- |
| `/api/backup`                   | GET    | `backupApi.ts` | List backups         |
| `/api/backup`                   | POST   | `backupApi.ts` | Create backup job    |
| `/api/backup/restore`           | POST   | `backupApi.ts` | Start restore        |
| `/api/backup/restore/{job_id}`  | GET    | `backupApi.ts` | Get restore status   |
| `/api/backup/{job_id}`          | DELETE | `backupApi.ts` | Delete backup        |
| `/api/backup/{job_id}`          | GET    | `backupApi.ts` | Get backup status    |
| `/api/backup/{job_id}/download` | GET    | `backupApi.ts` | Download backup file |

### Calibration

| Endpoint                    | Method | Consumer(s) | Purpose                  |
| --------------------------- | ------ | ----------- | ------------------------ |
| `/api/calibration`          | GET    | `api.ts`    | Get Calibration          |
| `/api/calibration`          | PATCH  | `api.ts`    | Patch Calibration        |
| `/api/calibration`          | PUT    | `api.ts`    | Update Calibration       |
| `/api/calibration/defaults` | GET    | `api.ts`    | Get Calibration Defaults |
| `/api/calibration/reset`    | POST   | `api.ts`    | Reset Calibration        |

### Cameras

| Endpoint                                                               | Method | Consumer(s)                                                             | Purpose                                      |
| ---------------------------------------------------------------------- | ------ | ----------------------------------------------------------------------- | -------------------------------------------- |
| `/api/cameras`                                                         | GET    | `api.ts`, `baselineConfigApi.ts`, `ptzApi.ts`, `useQueryPatterns.ts`    | List Cameras                                 |
| `/api/cameras`                                                         | POST   | `api.ts`, `baselineConfigApi.ts`, `ptzApi.ts`, `useQueryPatterns.ts`    | Create Camera                                |
| `/api/cameras/deleted`                                                 | GET    | `api.ts`                                                                | List all soft-deleted cameras                |
| `/api/cameras/onvif/discover`                                          | POST   | `useOnvifDiscovery.ts`                                                  | Discover ONVIF devices on the network        |
| `/api/cameras/preview/start`                                           | POST   | `go2rtcClient.ts`                                                       | Start RTSP preview stream (no camera lookup) |
| `/api/cameras/preview/{stream_id}/stop`                                | DELETE | `go2rtcClient.ts`                                                       | Stop RTSP preview stream by stream ID        |
| `/api/cameras/rtsp/test`                                               | POST   | `useRtspTest.ts`                                                        | Test RTSP connection                         |
| `/api/cameras/validation/paths`                                        | GET    | `api.ts`                                                                | Validate Camera Paths                        |
| `/api/cameras/{camera_id}`                                             | DELETE | `api.ts`, `baselineConfigApi.ts`, `useQueryPatterns.ts`, `useTracks.ts` | Delete Camera                                |
| `/api/cameras/{camera_id}`                                             | GET    | `api.ts`, `baselineConfigApi.ts`, `useQueryPatterns.ts`, `useTracks.ts` | Get Camera                                   |
| `/api/cameras/{camera_id}`                                             | PATCH  | `api.ts`, `baselineConfigApi.ts`, `useQueryPatterns.ts`, `useTracks.ts` | Update Camera                                |
| `/api/cameras/{camera_id}/baseline`                                    | GET    | `api.ts`                                                                | Get Camera Baseline                          |
| `/api/cameras/{camera_id}/baseline/activity`                           | GET    | `api.ts`                                                                | Get Camera Activity Baseline                 |
| `/api/cameras/{camera_id}/baseline/anomalies`                          | GET    | —                                                                       | Get Camera Baseline Anomalies                |
| `/api/cameras/{camera_id}/baseline/classes`                            | GET    | `api.ts`                                                                | Get Camera Class Baseline                    |
| `/api/cameras/{camera_id}/baseline/config`                             | GET    | `baselineConfigApi.ts`                                                  | Get Baseline Config                          |
| `/api/cameras/{camera_id}/baseline/config`                             | PUT    | `baselineConfigApi.ts`                                                  | Update Baseline Config                       |
| `/api/cameras/{camera_id}/baseline/reset`                              | POST   | `baselineConfigApi.ts`                                                  | Reset Baseline                               |
| `/api/cameras/{camera_id}/onvif/capabilities`                          | GET    | —                                                                       | Get ONVIF device capabilities                |
| `/api/cameras/{camera_id}/onvif/presets`                               | GET    | —                                                                       | Get PTZ presets                              |
| `/api/cameras/{camera_id}/onvif/presets/{preset_token}`                | POST   | —                                                                       | Go to PTZ preset                             |
| `/api/cameras/{camera_id}/onvif/ptz`                                   | POST   | —                                                                       | Execute PTZ command                          |
| `/api/cameras/{camera_id}/onvif/ptz/stop`                              | POST   | —                                                                       | Stop PTZ movement                            |
| `/api/cameras/{camera_id}/preview/start`                               | POST   | —                                                                       | Start preview for a specific camera          |
| `/api/cameras/{camera_id}/preview/stop`                                | DELETE | —                                                                       | Stop preview for a specific camera           |
| `/api/cameras/{camera_id}/restore`                                     | POST   | `api.ts`                                                                | Restore a soft-deleted camera                |
| `/api/cameras/{camera_id}/scene-changes`                               | GET    | `api.ts`                                                                | Get Camera Scene Changes                     |
| `/api/cameras/{camera_id}/scene-changes/{scene_change_id}/acknowledge` | POST   | `api.ts`                                                                | Acknowledge Scene Change                     |
| `/api/cameras/{camera_id}/snapshot`                                    | GET    | `api.ts`                                                                | Get Camera Snapshot                          |
| `/api/cameras/{camera_id}/snapshot/refresh`                            | POST   | `api.ts`                                                                | Refresh Camera Snapshot                      |
| `/api/cameras/{camera_id}/tracks`                                      | GET    | `useTracks.ts`                                                          | List tracks for a camera                     |
| `/api/cameras/{camera_id}/tracks/active`                               | GET    | `useTracks.ts`                                                          | Get active tracks for a camera               |
| `/api/cameras/{camera_id}/tracks/stats`                                | GET    | `useTracks.ts`                                                          | Get track statistics for a camera            |
| `/api/cameras/{camera_id}/zones`                                       | GET    | `api.ts`                                                                | List Zones                                   |
| `/api/cameras/{camera_id}/zones`                                       | POST   | `api.ts`                                                                | Create Zone                                  |
| `/api/cameras/{camera_id}/zones/{zone_id}`                             | DELETE | `api.ts`                                                                | Delete Zone                                  |
| `/api/cameras/{camera_id}/zones/{zone_id}`                             | GET    | `api.ts`                                                                | Get Zone                                     |
| `/api/cameras/{camera_id}/zones/{zone_id}`                             | PUT    | `api.ts`                                                                | Update Zone                                  |

### Debug

| Endpoint                               | Method | Consumer(s)                                                  | Purpose                   |
| -------------------------------------- | ------ | ------------------------------------------------------------ | ------------------------- |
| `/api/debug/batch/add-detection`       | POST   | —                                                            | Add Detection To Batch    |
| `/api/debug/batch/metrics`             | GET    | —                                                            | Get Batch Metrics         |
| `/api/debug/batch/reset-metrics`       | POST   | —                                                            | Reset Batch Metrics       |
| `/api/debug/circuit-breakers`          | GET    | `api.ts`, `useCircuitBreakerDebugQuery.ts`                   | Get Circuit Breakers      |
| `/api/debug/config`                    | GET    | `api.ts`, `useDebugConfigQuery.ts`                           | Get Config                |
| `/api/debug/log-level`                 | GET    | `api.ts`, `useLogLevelQuery.ts`, `useSetLogLevelMutation.ts` | Get Log Level             |
| `/api/debug/log-level`                 | POST   | `api.ts`, `useLogLevelQuery.ts`, `useSetLogLevelMutation.ts` | Set Log Level             |
| `/api/debug/memory`                    | GET    | `api.ts`, `useMemoryStatsQuery.ts`                           | Get Memory Stats          |
| `/api/debug/memory/gc`                 | POST   | `api.ts`, `useMemoryStatsQuery.ts`                           | Trigger Gc                |
| `/api/debug/memory/tracemalloc/start`  | POST   | `api.ts`, `useMemoryStatsQuery.ts`                           | Start Tracemalloc         |
| `/api/debug/memory/tracemalloc/stop`   | POST   | `api.ts`, `useMemoryStatsQuery.ts`                           | Stop Tracemalloc          |
| `/api/debug/pipeline-errors`           | GET    | `api.ts`, `useDebugQueries.ts`                               | Get Pipeline Errors       |
| `/api/debug/pipeline-state`            | GET    | —                                                            | Get Pipeline State        |
| `/api/debug/profile/start`             | POST   | `api.ts`, `useProfilingMutations.ts`                         | Start Profiling           |
| `/api/debug/profile/stats`             | GET    | —                                                            | Get Profile Stats         |
| `/api/debug/profile/stop`              | POST   | `api.ts`, `useProfilingMutations.ts`                         | Stop Profiling            |
| `/api/debug/recordings`                | GET    | `api.ts`, `useRecordingsQuery.ts`                            | List Recordings           |
| `/api/debug/recordings/{recording_id}` | DELETE | `api.ts`                                                     | Delete Recording          |
| `/api/debug/recordings/{recording_id}` | GET    | `api.ts`                                                     | Get Recording             |
| `/api/debug/redis/info`                | GET    | `DatabasesPanel.tsx`, `api.ts`, `useDebugQueries.ts`         | Get Redis Info            |
| `/api/debug/replay/{recording_id}`     | POST   | `api.ts`                                                     | Replay Request            |
| `/api/debug/websocket/connections`     | GET    | `api.ts`, `useDebugQueries.ts`                               | Get Websocket Connections |

### Detections

| Endpoint                                         | Method | Consumer(s)                                                                                                         | Purpose                  |
| ------------------------------------------------ | ------ | ------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| `/api/detections`                                | GET    | `api.ts`                                                                                                            | List Detections          |
| `/api/detections/bulk`                           | DELETE | `api.ts`                                                                                                            | Bulk delete detections   |
| `/api/detections/bulk`                           | PATCH  | `api.ts`                                                                                                            | Bulk update detections   |
| `/api/detections/bulk`                           | POST   | `api.ts`                                                                                                            | Bulk create detections   |
| `/api/detections/export`                         | GET    | —                                                                                                                   | Export Detections        |
| `/api/detections/labels`                         | GET    | `api.ts`, `useDetectionLabelsQuery.ts`                                                                              | List Detection Labels    |
| `/api/detections/search`                         | GET    | `api.ts`                                                                                                            | Search Detections        |
| `/api/detections/stats`                          | GET    | `InsightsCharts.tsx`, `api.ts`, `useAIMetrics.ts`, `useDetectionStatsQuery.ts`                                      | Get Detection Stats      |
| `/api/detections/{detection_id}`                 | GET    | `DetectionThumbnail.tsx`, `InsightsCharts.tsx`, `api.ts`, `useAIMetrics.ts`, `useDetectionLabelsQuery.ts` (+1 more) | Get Detection            |
| `/api/detections/{detection_id}/enrichment`      | GET    | `api.ts`                                                                                                            | Get Detection Enrichment |
| `/api/detections/{detection_id}/image`           | GET    | `DetectionThumbnail.tsx`, `api.ts`                                                                                  | Get Detection Image      |
| `/api/detections/{detection_id}/thumbnail`       | GET    | `api.ts`                                                                                                            | Get detection thumbnail  |
| `/api/detections/{detection_id}/video`           | GET    | `api.ts`                                                                                                            | Stream Detection Video   |
| `/api/detections/{detection_id}/video/thumbnail` | GET    | `api.ts`                                                                                                            | Get Video Thumbnail      |

### DLQ (Dead Letter Queue)

| Endpoint                            | Method | Consumer(s)                 | Purpose              |
| ----------------------------------- | ------ | --------------------------- | -------------------- |
| `/api/dlq/jobs/{queue_name}`        | GET    | `api.ts`                    | Get Dlq Jobs         |
| `/api/dlq/requeue-all/{queue_name}` | POST   | `api.ts`                    | Requeue All Dlq Jobs |
| `/api/dlq/requeue/{queue_name}`     | POST   | `api.ts`                    | Requeue Dlq Job      |
| `/api/dlq/stats`                    | GET    | `api.ts`, `useAIMetrics.ts` | Get Dlq Stats        |
| `/api/dlq/{queue_name}`             | DELETE | `api.ts`, `useAIMetrics.ts` | Clear Dlq            |

### Enrollment Queue

| Endpoint                                       | Method | Consumer(s) | Purpose                      |
| ---------------------------------------------- | ------ | ----------- | ---------------------------- |
| `/api/enrollment-queue`                        | GET    | —           | List Enrollment Candidates   |
| `/api/enrollment-queue/{candidate_id}`         | GET    | —           | Get Enrollment Candidate     |
| `/api/enrollment-queue/{candidate_id}/approve` | POST   | —           | Approve Enrollment Candidate |
| `/api/enrollment-queue/{candidate_id}/reject`  | POST   | —           | Reject Enrollment Candidate  |

### Entities

| Endpoint                                  | Method | Consumer(s)                     | Purpose                 |
| ----------------------------------------- | ------ | ------------------------------- | ----------------------- |
| `/api/entities`                           | GET    | `api.ts`                        | List Entities           |
| `/api/entities/matches/{detection_id}`    | GET    | `api.ts`                        | Get Entity Matches      |
| `/api/entities/stats`                     | GET    | `EntityStatsCard.tsx`, `api.ts` | Get Entity Stats        |
| `/api/entities/trusted`                   | GET    | `api.ts`                        | List Trusted Entities   |
| `/api/entities/untrusted`                 | GET    | `api.ts`                        | List Untrusted Entities |
| `/api/entities/v2`                        | GET    | `api.ts`                        | List Entities V2        |
| `/api/entities/v2/{entity_id}`            | GET    | `api.ts`                        | Get Entity V2           |
| `/api/entities/v2/{entity_id}/detections` | GET    | `api.ts`                        | Get Entity Detections   |
| `/api/entities/{entity_id}`               | GET    | `EntityStatsCard.tsx`, `api.ts` | Get Entity              |
| `/api/entities/{entity_id}/history`       | GET    | `api.ts`                        | Get Entity History      |
| `/api/entities/{entity_id}/trust`         | PATCH  | `api.ts`                        | Update Entity Trust     |

### Events

| Endpoint                                | Method | Consumer(s)                                                                                                               | Purpose                      |
| --------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| `/api/events`                           | GET    | `api.ts`                                                                                                                  | List Events                  |
| `/api/events/analyze/{batch_id}/stream` | GET    | `api.ts`                                                                                                                  | Analyze Batch Streaming      |
| `/api/events/bulk`                      | DELETE | —                                                                                                                         | Bulk delete events           |
| `/api/events/bulk`                      | PATCH  | —                                                                                                                         | Bulk update events           |
| `/api/events/bulk`                      | POST   | —                                                                                                                         | Bulk create events           |
| `/api/events/clusters`                  | GET    | `api.ts`                                                                                                                  | Get Event Clusters           |
| `/api/events/deleted`                   | GET    | `api.ts`                                                                                                                  | List all soft-deleted events |
| `/api/events/export`                    | GET    | `ExportButton.tsx`, `api.ts`                                                                                              | Export Events                |
| `/api/events/export`                    | POST   | `ExportButton.tsx`, `api.ts`                                                                                              | Start export job             |
| `/api/events/search`                    | GET    | `api.ts`                                                                                                                  | Search Events Endpoint       |
| `/api/events/stats`                     | GET    | `InsightsCharts.tsx`, `api.ts`                                                                                            | Get Event Stats              |
| `/api/events/timeline-summary`          | GET    | `useTimelineData.ts`                                                                                                      | Get Timeline Summary         |
| `/api/events/{event_id}`                | DELETE | `EventEnrichmentSummary.tsx`, `ExportButton.tsx`, `InsightsCharts.tsx`, `api.ts`, `useEventEnrichmentsQuery.ts` (+1 more) | Soft delete a single event   |
| `/api/events/{event_id}`                | GET    | `EventEnrichmentSummary.tsx`, `ExportButton.tsx`, `InsightsCharts.tsx`, `api.ts`, `useEventEnrichmentsQuery.ts` (+1 more) | Get Event                    |
| `/api/events/{event_id}`                | PATCH  | `EventEnrichmentSummary.tsx`, `ExportButton.tsx`, `InsightsCharts.tsx`, `api.ts`, `useEventEnrichmentsQuery.ts` (+1 more) | Update Event                 |
| `/api/events/{event_id}/clip`           | GET    | `api.ts`                                                                                                                  | Get Event Clip               |
| `/api/events/{event_id}/clip/generate`  | POST   | `api.ts`                                                                                                                  | Generate Event Clip          |
| `/api/events/{event_id}/detections`     | GET    | `api.ts`                                                                                                                  | Get Event Detections         |
| `/api/events/{event_id}/enrichments`    | GET    | `EventEnrichmentSummary.tsx`, `api.ts`, `useEventEnrichmentsQuery.ts`                                                     | Get Event Enrichments        |
| `/api/events/{event_id}/restore`        | POST   | `api.ts`                                                                                                                  | Restore a soft-deleted event |

### Exports

| Endpoint                              | Method | Consumer(s)                 | Purpose              |
| ------------------------------------- | ------ | --------------------------- | -------------------- |
| `/api/exports`                        | GET    | `api.ts`                    | List export jobs     |
| `/api/exports`                        | POST   | `api.ts`                    | Start export job     |
| `/api/exports/{job_id}`               | DELETE | `ExportPanel.tsx`, `api.ts` | Cancel export job    |
| `/api/exports/{job_id}`               | GET    | `ExportPanel.tsx`, `api.ts` | Get export status    |
| `/api/exports/{job_id}/download`      | GET    | `api.ts`                    | Download export file |
| `/api/exports/{job_id}/download/info` | GET    | `api.ts`                    | Get download info    |

### Face Events

| Endpoint                               | Method | Consumer(s)                                         | Purpose               |
| -------------------------------------- | ------ | --------------------------------------------------- | --------------------- |
| `/api/face-events`                     | GET    | `useFaceEventsQuery.ts`, `useFaceRecognitionApi.ts` | List Face Events      |
| `/api/face-events/compare`             | POST   | `useFaceRecognitionApi.ts`                          | Compare Faces         |
| `/api/face-events/match`               | POST   | —                                                   | Match Face            |
| `/api/face-events/stats`               | GET    | `useFaceRecognitionApi.ts`                          | Get Face Events Stats |
| `/api/face-events/unknown`             | GET    | `useFaceRecognitionApi.ts`                          | Get Unknown Strangers |
| `/api/face-events/{event_id}/identify` | POST   | `useFaceRecognitionApi.ts`                          | Identify Face Event   |

### Feedback

| Endpoint                         | Method | Consumer(s) | Purpose                   |
| -------------------------------- | ------ | ----------- | ------------------------- |
| `/api/feedback`                  | POST   | `api.ts`    | Submit event feedback     |
| `/api/feedback/event/{event_id}` | GET    | `api.ts`    | Get feedback for an event |
| `/api/feedback/stats`            | GET    | `api.ts`    | Get feedback statistics   |

### Health

| Endpoint                  | Method | Consumer(s) | Purpose                               |
| ------------------------- | ------ | ----------- | ------------------------------------- |
| `/api/health/ai-services` | GET    | —           | Get Unified AI Services Health Status |

### Heatmaps

| Endpoint                                       | Method | Consumer(s)          | Purpose                   |
| ---------------------------------------------- | ------ | -------------------- | ------------------------- |
| `/api/heatmaps/camera/{camera_id}`             | GET    | `useHeatmapQuery.ts` | Get Current Heatmap       |
| `/api/heatmaps/camera/{camera_id}/accumulator` | DELETE | —                    | Reset Heatmap Accumulator |
| `/api/heatmaps/camera/{camera_id}/history`     | GET    | `useHeatmapQuery.ts` | Get Heatmap History       |
| `/api/heatmaps/camera/{camera_id}/merged`      | GET    | `useHeatmapQuery.ts` | Get Merged Heatmap        |
| `/api/heatmaps/camera/{camera_id}/snapshot`    | POST   | —                    | Save Heatmap Snapshot     |
| `/api/heatmaps/camera/{camera_id}/stats`       | GET    | —                    | Get Heatmap Stats         |

### Household

| Endpoint                                         | Method | Consumer(s)          | Purpose                  |
| ------------------------------------------------ | ------ | -------------------- | ------------------------ |
| `/api/household/members`                         | GET    | `useHouseholdApi.ts` | List Members             |
| `/api/household/members`                         | POST   | `useHouseholdApi.ts` | Create Member            |
| `/api/household/members/{member_id}`             | DELETE | `useHouseholdApi.ts` | Delete Member            |
| `/api/household/members/{member_id}`             | GET    | `useHouseholdApi.ts` | Get Member               |
| `/api/household/members/{member_id}`             | PATCH  | `useHouseholdApi.ts` | Update Member            |
| `/api/household/members/{member_id}/embeddings`  | POST   | —                    | Add Embedding From Event |
| `/api/household/members/{member_id}/link-person` | PATCH  | `useHouseholdApi.ts` | Link Person              |
| `/api/household/vehicles`                        | GET    | `useHouseholdApi.ts` | List Vehicles            |
| `/api/household/vehicles`                        | POST   | `useHouseholdApi.ts` | Create Vehicle           |
| `/api/household/vehicles/{vehicle_id}`           | DELETE | `useHouseholdApi.ts` | Delete Vehicle           |
| `/api/household/vehicles/{vehicle_id}`           | GET    | `useHouseholdApi.ts` | Get Vehicle              |
| `/api/household/vehicles/{vehicle_id}`           | PATCH  | `useHouseholdApi.ts` | Update Vehicle           |

### Household Matcher

| Endpoint                               | Method | Consumer(s) | Purpose            |
| -------------------------------------- | ------ | ----------- | ------------------ |
| `/api/household-matcher/config`        | GET    | —           | Get Matcher Config |
| `/api/household-matcher/match-batch`   | POST   | —           | Match Batch        |
| `/api/household-matcher/match-person`  | POST   | —           | Match Person       |
| `/api/household-matcher/match-vehicle` | POST   | —           | Match Vehicle      |

### Jobs

| Endpoint                     | Method | Consumer(s)                                           | Purpose                      |
| ---------------------------- | ------ | ----------------------------------------------------- | ---------------------------- |
| `/api/jobs`                  | GET    | `FileOperationsPanel.tsx`, `api.ts`                   | List all jobs                |
| `/api/jobs/bulk-cancel`      | POST   | —                                                     | Bulk cancel jobs             |
| `/api/jobs/search`           | GET    | `api.ts`, `useJobsSearchQuery.ts`                     | Search and filter jobs       |
| `/api/jobs/stats`            | GET    | —                                                     | Get job statistics           |
| `/api/jobs/types`            | GET    | —                                                     | List available job types     |
| `/api/jobs/{job_id}`         | DELETE | `ExportButton.tsx`, `api.ts`, `useJobsSearchQuery.ts` | Cancel or abort a job        |
| `/api/jobs/{job_id}`         | GET    | `ExportButton.tsx`, `api.ts`, `useJobsSearchQuery.ts` | Get job status               |
| `/api/jobs/{job_id}/abort`   | POST   | `api.ts`                                              | Abort a running job          |
| `/api/jobs/{job_id}/cancel`  | POST   | `api.ts`                                              | Cancel a job                 |
| `/api/jobs/{job_id}/detail`  | GET    | `api.ts`                                              | Get detailed job information |
| `/api/jobs/{job_id}/history` | GET    | `api.ts`                                              | Get job history              |
| `/api/jobs/{job_id}/logs`    | GET    | `api.ts`                                              | Get job logs                 |

### Known Persons

| Endpoint                                                   | Method | Consumer(s)                                         | Purpose                |
| ---------------------------------------------------------- | ------ | --------------------------------------------------- | ---------------------- |
| `/api/known-persons`                                       | GET    | `useFaceRecognitionApi.ts`, `useKnownPersonsApi.ts` | List Known Persons     |
| `/api/known-persons`                                       | POST   | `useFaceRecognitionApi.ts`, `useKnownPersonsApi.ts` | Create Known Person    |
| `/api/known-persons/bulk-enroll`                           | POST   | `useFaceRecognitionApi.ts`                          | Bulk Enroll Faces      |
| `/api/known-persons/{person_id}`                           | DELETE | `useFaceRecognitionApi.ts`, `useKnownPersonsApi.ts` | Delete Known Person    |
| `/api/known-persons/{person_id}`                           | GET    | `useFaceRecognitionApi.ts`, `useKnownPersonsApi.ts` | Get Known Person       |
| `/api/known-persons/{person_id}`                           | PATCH  | `useFaceRecognitionApi.ts`, `useKnownPersonsApi.ts` | Update Known Person    |
| `/api/known-persons/{person_id}/appearances`               | GET    | `useFaceRecognitionApi.ts`                          | Get Person Appearances |
| `/api/known-persons/{person_id}/embeddings`                | GET    | `useFaceRecognitionApi.ts`                          | List Person Embeddings |
| `/api/known-persons/{person_id}/embeddings`                | POST   | `useFaceRecognitionApi.ts`                          | Add Face Embedding     |
| `/api/known-persons/{person_id}/embeddings/{embedding_id}` | DELETE | `useFaceRecognitionApi.ts`                          | Delete Face Embedding  |
| `/api/known-persons/{person_id}/enroll-from-detection`     | POST   | `useFaceRecognitionApi.ts`                          | Enroll From Detection  |

### LLM Reasoning

| Endpoint                                      | Method | Consumer(s)          | Purpose              |
| --------------------------------------------- | ------ | -------------------- | -------------------- |
| `/api/llm-reasoning/events/{event_id}`        | GET    | `llmReasoningApi.ts` | Get Llm Reasoning    |
| `/api/llm-reasoning/events/{event_id}/prompt` | GET    | `llmReasoningApi.ts` | Get Llm Prompt Debug |

### Logs

| Endpoint                   | Method | Consumer(s)                                | Purpose                           |
| -------------------------- | ------ | ------------------------------------------ | --------------------------------- |
| `/api/logs`                | GET    | `api.ts`                                   | List logs with optional filtering |
| `/api/logs/frontend`       | POST   | `api.ts`, `errorReporting.ts`, `logger.ts` | Ingest single frontend log        |
| `/api/logs/frontend/batch` | POST   | `logger.ts`                                | Ingest batch of frontend logs     |
| `/api/logs/stats`          | GET    | `api.ts`                                   | Get log statistics                |

### Media

| Endpoint                                    | Method | Consumer(s)                           | Purpose            |
| ------------------------------------------- | ------ | ------------------------------------- | ------------------ |
| `/api/media/cameras/{camera_id}/{filename}` | GET    | `api.ts`                              | Serve Camera File  |
| `/api/media/clips/{filename}`               | GET    | `api.ts`                              | Serve Clip         |
| `/api/media/thumbnails/{filename}`          | GET    | `api.ts`                              | Serve Thumbnail    |
| `/api/media/{path}`                         | GET    | `CameraActivityHeatmap.tsx`, `api.ts` | Serve Media Compat |

### Metrics

| Endpoint       | Method | Consumer(s)                           | Purpose |
| -------------- | ------ | ------------------------------------- | ------- |
| `/api/metrics` | GET    | `metricsParser.ts`, `useAIMetrics.ts` | Metrics |

### MQTT Config

| Endpoint                      | Method | Consumer(s)        | Purpose                     |
| ----------------------------- | ------ | ------------------ | --------------------------- |
| `/api/mqtt-config`            | GET    | `mqttConfigApi.ts` | Get MQTT configuration      |
| `/api/mqtt-config`            | PUT    | `mqttConfigApi.ts` | Update MQTT configuration   |
| `/api/mqtt-config/disconnect` | POST   | `mqttConfigApi.ts` | Disconnect from MQTT broker |
| `/api/mqtt-config/reconnect`  | POST   | `mqttConfigApi.ts` | Reconnect to MQTT broker    |
| `/api/mqtt-config/status`     | GET    | `mqttConfigApi.ts` | Get MQTT connection status  |
| `/api/mqtt-config/test`       | POST   | `mqttConfigApi.ts` | Test MQTT connection        |

### Notification

| Endpoint                    | Method | Consumer(s) | Purpose                    |
| --------------------------- | ------ | ----------- | -------------------------- |
| `/api/notification/config`  | GET    | `api.ts`    | Get Notification Config    |
| `/api/notification/config`  | PATCH  | `api.ts`    | Update Notification Config |
| `/api/notification/history` | GET    | `api.ts`    | Get Notification History   |
| `/api/notification/test`    | POST   | `api.ts`    | Test Notification          |

### Notification Preferences

| Endpoint                                                | Method | Consumer(s) | Purpose                         |
| ------------------------------------------------------- | ------ | ----------- | ------------------------------- |
| `/api/notification-preferences/`                        | GET    | `api.ts`    | Get Notification Preferences    |
| `/api/notification-preferences/`                        | PUT    | `api.ts`    | Update Notification Preferences |
| `/api/notification-preferences/cameras`                 | GET    | `api.ts`    | Get All Camera Settings         |
| `/api/notification-preferences/cameras/{camera_id}`     | GET    | `api.ts`    | Get Camera Setting              |
| `/api/notification-preferences/cameras/{camera_id}`     | PUT    | `api.ts`    | Update Camera Setting           |
| `/api/notification-preferences/quiet-hours`             | GET    | `api.ts`    | Get Quiet Hours                 |
| `/api/notification-preferences/quiet-hours`             | POST   | `api.ts`    | Create Quiet Hours Period       |
| `/api/notification-preferences/quiet-hours/{period_id}` | DELETE | `api.ts`    | Delete Quiet Hours Period       |

### Outbound Webhooks

| Endpoint                                                | Method | Consumer(s)     | Purpose                    |
| ------------------------------------------------------- | ------ | --------------- | -------------------------- |
| `/api/outbound-webhooks`                                | GET    | `webhookApi.ts` | List webhooks              |
| `/api/outbound-webhooks`                                | POST   | `webhookApi.ts` | Create webhook             |
| `/api/outbound-webhooks/deliveries/{delivery_id}`       | GET    | `webhookApi.ts` | Get delivery details       |
| `/api/outbound-webhooks/deliveries/{delivery_id}/retry` | POST   | `webhookApi.ts` | Retry failed delivery      |
| `/api/outbound-webhooks/health`                         | GET    | `webhookApi.ts` | Get webhook health summary |
| `/api/outbound-webhooks/{webhook_id}`                   | DELETE | `webhookApi.ts` | Delete webhook             |
| `/api/outbound-webhooks/{webhook_id}`                   | GET    | `webhookApi.ts` | Get webhook                |
| `/api/outbound-webhooks/{webhook_id}`                   | PATCH  | `webhookApi.ts` | Update webhook             |
| `/api/outbound-webhooks/{webhook_id}/deliveries`        | GET    | `webhookApi.ts` | List deliveries            |
| `/api/outbound-webhooks/{webhook_id}/disable`           | POST   | `webhookApi.ts` | Disable webhook            |
| `/api/outbound-webhooks/{webhook_id}/enable`            | POST   | `webhookApi.ts` | Enable webhook             |
| `/api/outbound-webhooks/{webhook_id}/test`              | POST   | `webhookApi.ts` | Test webhook               |

### Plate Reads

| Endpoint                              | Method | Consumer(s)                                      | Purpose              |
| ------------------------------------- | ------ | ------------------------------------------------ | -------------------- |
| `/api/plate-reads`                    | GET    | `plateReadsApi.ts`, `usePlateReadsQuery.ts`      | List Plate Reads     |
| `/api/plate-reads`                    | POST   | `plateReadsApi.ts`, `usePlateReadsQuery.ts`      | Create Plate Read    |
| `/api/plate-reads/camera/{camera_id}` | GET    | —                                                | Get Reads By Camera  |
| `/api/plate-reads/recognize`          | POST   | —                                                | Recognize Plate      |
| `/api/plate-reads/search`             | GET    | `plateReadsApi.ts`                               | Search By Plate Text |
| `/api/plate-reads/statistics`         | GET    | —                                                | Get Statistics       |
| `/api/plate-reads/{plate_read_id}`    | GET    | `plateReadsApi.ts`, `usePlateStatisticsQuery.ts` | Get Plate Read       |

### Prompts

| Endpoint                            | Method | Consumer(s)                                                                                    | Purpose                 |
| ----------------------------------- | ------ | ---------------------------------------------------------------------------------------------- | ----------------------- |
| `/api/prompts`                      | GET    | `aiAuditApi.ts`, `api.ts`, `promptManagementApi.ts`                                            | Get All Prompts         |
| `/api/prompts/export`               | GET    | `api.ts`, `promptManagementApi.ts`                                                             | Export Prompts          |
| `/api/prompts/history`              | GET    | `api.ts`, `promptManagementApi.ts`                                                             | Get Prompt History      |
| `/api/prompts/history/{version_id}` | POST   | `api.ts`, `promptManagementApi.ts`                                                             | Restore Prompt Version  |
| `/api/prompts/import`               | POST   | `api.ts`, `promptManagementApi.ts`                                                             | Import Prompts          |
| `/api/prompts/import/preview`       | POST   | `promptManagementApi.ts`                                                                       | Preview Import Prompts  |
| `/api/prompts/test`                 | POST   | `api.ts`, `promptManagementApi.ts`                                                             | Test Prompt             |
| `/api/prompts/test-prompt`          | POST   | `abTestService.ts`, `usePromptQueries.ts`                                                      | Test Custom Prompt      |
| `/api/prompts/{model}`              | GET    | `abTestService.ts`, `aiAuditApi.ts`, `api.ts`, `promptManagementApi.ts`, `usePromptQueries.ts` | Get Prompt For Model    |
| `/api/prompts/{model}`              | PUT    | `abTestService.ts`, `aiAuditApi.ts`, `api.ts`, `promptManagementApi.ts`, `usePromptQueries.ts` | Update Prompt For Model |

### Queues

| Endpoint             | Method | Consumer(s)                                          | Purpose          |
| -------------------- | ------ | ---------------------------------------------------- | ---------------- |
| `/api/queues/status` | GET    | `PipelineQueues.tsx`, `api.ts`, `useQueuesStatus.ts` | Get queue status |

### Re-ID Search

| Endpoint                           | Method | Consumer(s) | Purpose                   |
| ---------------------------------- | ------ | ----------- | ------------------------- |
| `/api/reid/search`                 | POST   | —           | Search Similar Entities   |
| `/api/reid/similar/{detection_id}` | GET    | `api.ts`    | Find Similar By Detection |

### RUM (Real User Monitoring)

| Endpoint   | Method | Consumer(s) | Purpose            |
| ---------- | ------ | ----------- | ------------------ |
| `/api/rum` | POST   | `rum.ts`    | Ingest RUM metrics |

### Scheduled Reports

| Endpoint                                 | Method | Consumer(s)              | Purpose                    |
| ---------------------------------------- | ------ | ------------------------ | -------------------------- |
| `/api/scheduled-reports`                 | GET    | `scheduledReportsApi.ts` | List all scheduled reports |
| `/api/scheduled-reports`                 | POST   | `scheduledReportsApi.ts` | Create a scheduled report  |
| `/api/scheduled-reports/{report_id}`     | DELETE | `scheduledReportsApi.ts` | Delete a scheduled report  |
| `/api/scheduled-reports/{report_id}`     | GET    | `scheduledReportsApi.ts` | Get a scheduled report     |
| `/api/scheduled-reports/{report_id}`     | PUT    | `scheduledReportsApi.ts` | Update a scheduled report  |
| `/api/scheduled-reports/{report_id}/run` | POST   | —                        | Manually trigger a report  |

### Summaries

| Endpoint                             | Method | Consumer(s)            | Purpose                      |
| ------------------------------------ | ------ | ---------------------- | ---------------------------- |
| `/api/summaries/daily`               | GET    | —                      | Get Daily Summary            |
| `/api/summaries/entities`            | GET    | `api.ts`               | Get Entity Recognition Stats |
| `/api/summaries/hourly`              | GET    | —                      | Get Hourly Summary           |
| `/api/summaries/latest`              | GET    | `api.ts`, `summary.ts` | Get Latest Summaries         |
| `/api/summaries/trends`              | GET    | `api.ts`               | Get Trends                   |
| `/api/summaries/{summary_id}/detail` | GET    | `api.ts`               | Get Summary Detail           |
| `/api/summaries/{summary_id}/export` | GET    | —                      | Export Summary               |

### Tracks

| Endpoint                         | Method | Consumer(s)    | Purpose                        |
| -------------------------------- | ------ | -------------- | ------------------------------ |
| `/api/tracks`                    | GET    | —              | List all tracks                |
| `/api/tracks/{track_id}`         | GET    | `useTracks.ts` | Get track by ID                |
| `/api/tracks/{track_id}/history` | GET    | `useTracks.ts` | Get track with full trajectory |

### V1 Hierarchy (Households, Properties, Areas)

| Endpoint                                       | Method | Consumer(s)                                         | Purpose                      |
| ---------------------------------------------- | ------ | --------------------------------------------------- | ---------------------------- |
| `/api/v1/alertmanager/webhook`                 | POST   | —                                                   | Receive Alertmanager Webhook |
| `/api/v1/areas/{area_id}`                      | DELETE | `api.ts`                                            | Delete Area                  |
| `/api/v1/areas/{area_id}`                      | GET    | `api.ts`                                            | Get Area                     |
| `/api/v1/areas/{area_id}`                      | PATCH  | `api.ts`                                            | Update Area                  |
| `/api/v1/areas/{area_id}/cameras`              | GET    | `api.ts`                                            | List Area Cameras            |
| `/api/v1/areas/{area_id}/cameras`              | POST   | `api.ts`                                            | Link Camera To Area          |
| `/api/v1/areas/{area_id}/cameras/{camera_id}`  | DELETE | `api.ts`                                            | Unlink Camera From Area      |
| `/api/v1/households`                           | GET    | `api.ts`, `useHouseholdApi.ts`                      | List Households              |
| `/api/v1/households`                           | POST   | `api.ts`, `useHouseholdApi.ts`                      | Create Household             |
| `/api/v1/households/{household_id}`            | DELETE | `api.ts`, `useHouseholdApi.ts`                      | Delete Household             |
| `/api/v1/households/{household_id}`            | GET    | `api.ts`, `useHouseholdApi.ts`                      | Get Household                |
| `/api/v1/households/{household_id}`            | PATCH  | `api.ts`, `useHouseholdApi.ts`                      | Update Household             |
| `/api/v1/households/{household_id}/properties` | GET    | `api.ts`                                            | List Household Properties    |
| `/api/v1/households/{household_id}/properties` | POST   | `api.ts`                                            | Create Property              |
| `/api/v1/properties/{property_id}`             | DELETE | `api.ts`                                            | Delete Property              |
| `/api/v1/properties/{property_id}`             | GET    | `api.ts`                                            | Get Property                 |
| `/api/v1/properties/{property_id}`             | PATCH  | `api.ts`                                            | Update Property              |
| `/api/v1/properties/{property_id}/areas`       | GET    | `api.ts`                                            | List Property Areas          |
| `/api/v1/properties/{property_id}/areas`       | POST   | `api.ts`                                            | Create Area                  |
| `/api/v1/settings`                             | GET    | `DetectionThresholdsPanel.tsx`, `useSettingsApi.ts` | Get current system settings  |
| `/api/v1/settings`                             | PATCH  | `DetectionThresholdsPanel.tsx`, `useSettingsApi.ts` | Update runtime settings      |
| `/api/v1/system-settings`                      | GET    | `systemSettingsApi.ts`                              | List System Settings         |
| `/api/v1/system-settings/{key}`                | DELETE | `systemSettingsApi.ts`                              | Delete System Setting        |
| `/api/v1/system-settings/{key}`                | GET    | `systemSettingsApi.ts`                              | Get System Setting           |
| `/api/v1/system-settings/{key}`                | PATCH  | `systemSettingsApi.ts`                              | Update System Setting        |

### Webhooks

| Endpoint                       | Method | Consumer(s) | Purpose                      |
| ------------------------------ | ------ | ----------- | ---------------------------- |
| `/api/webhooks/alerts`         | POST   | —           | Receive Alertmanager Webhook |
| `/api/webhooks/inbound/alert`  | POST   | —           | Create Alert                 |
| `/api/webhooks/inbound/arm`    | POST   | —           | Arm Zones                    |
| `/api/webhooks/inbound/disarm` | POST   | —           | Disarm Zones                 |
| `/api/webhooks/inbound/mode`   | POST   | —           | Set System Mode              |

### Zones

| Endpoint                                                         | Method | Consumer(s)                                                       | Purpose                                |
| ---------------------------------------------------------------- | ------ | ----------------------------------------------------------------- | -------------------------------------- |
| `/api/zones/anomalies`                                           | GET    | `useZoneAlerts.ts`, `useZoneAnomalies.ts`                         | List All Anomalies                     |
| `/api/zones/anomalies/{anomaly_id}/acknowledge`                  | POST   | `useAnomalyContext.ts`, `useZoneAlerts.ts`, `useZoneAnomalies.ts` | Acknowledge Anomaly                    |
| `/api/zones/anomalies/{anomaly_id}/context`                      | GET    | `useAnomalyContext.ts`                                            | Get anomaly with investigation context |
| `/api/zones/member/{member_id}/zones`                            | GET    | —                                                                 | Get Member Zones                       |
| `/api/zones/vehicle/{vehicle_id}/zones`                          | GET    | —                                                                 | Get Vehicle Zones                      |
| `/api/zones/{zone_id}/anomalies`                                 | GET    | `useZoneAlerts.ts`, `useZoneAnomalies.ts`                         | List Zone Anomalies                    |
| `/api/zones/{zone_id}/household`                                 | DELETE | `useZoneHouseholdConfig.ts`, `useZoneTrustMatrix.ts`              | Delete Zone Household Config           |
| `/api/zones/{zone_id}/household`                                 | GET    | `useZoneHouseholdConfig.ts`, `useZoneTrustMatrix.ts`              | Get Zone Household Config              |
| `/api/zones/{zone_id}/household`                                 | PATCH  | `useZoneHouseholdConfig.ts`, `useZoneTrustMatrix.ts`              | Patch Zone Household Config            |
| `/api/zones/{zone_id}/household`                                 | PUT    | `useZoneHouseholdConfig.ts`, `useZoneTrustMatrix.ts`              | Upsert Zone Household Config           |
| `/api/zones/{zone_id}/household/trust/{entity_type}/{entity_id}` | GET    | `useZoneHouseholdConfig.ts`, `useZoneTrustMatrix.ts`              | Check Entity Trust                     |

(WebSocket routes are defined in `backend/api/routes/websocket.py` and are
not listed in the OpenAPI spec.)

### WebSocket Message Contracts

See [WebSocket Contracts](websocket-contracts.md) for message format specifications.

## Backend-only endpoints

83 operations have no consumer under `frontend/src`. The CI
coverage gate is green because it keys on decorator paths and string
fragments, not on these full path/method rows — treat this as the real
backend-only surface:

| Endpoint                                                       | Methods             | Reason                                                                                                                                                                       |
| -------------------------------------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/`                                                            | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/admin/users`                                             | GET, POST           | Admin user/seed tooling consumed by CLI and fixtures                                                                                                                         |
| `/api/admin/users/{user_id}`                                   | DELETE              | Admin user/seed tooling consumed by CLI and fixtures                                                                                                                         |
| `/api/ai-audit/batch/{job_id}`                                 | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/alert-service/alerts`                                    | GET, POST           | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/alert-service/alerts/{alert_id}`                         | DELETE, GET, PUT    | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/alert-service/alerts/{alert_id}/acknowledge`             | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/alert-service/alerts/{alert_id}/dismiss`                 | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/analytics-zones/line-zones`                              | POST                | Zone-analytics detail endpoints; UI covers main CRUD elsewhere in this table                                                                                                 |
| `/api/analytics-zones/polygon-zones`                           | POST                | Zone-analytics detail endpoints; UI covers main CRUD elsewhere in this table                                                                                                 |
| `/api/analytics-zones/polygon-zones/{zone_id}/check-loitering` | POST                | Zone-analytics detail endpoints; UI covers main CRUD elsewhere in this table                                                                                                 |
| `/api/analytics-zones/polygon-zones/{zone_id}/dwell-history`   | GET                 | Zone-analytics detail endpoints; UI covers main CRUD elsewhere in this table                                                                                                 |
| `/api/analytics-zones/polygon-zones/{zone_id}/toggle-active`   | POST                | Zone-analytics detail endpoints; UI covers main CRUD elsewhere in this table                                                                                                 |
| `/api/analytics/calibration`                                   | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/auth/api-keys`                                           | GET, POST           | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/auth/api-keys/{key_id}`                                  | DELETE              | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/auto-enrollment/settings`                                | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/cameras/{camera_id}/baseline/anomalies`                  | GET                 | Device-control (ONVIF/PTZ/preview/baseline) endpoints — UI covers camera CRUD via `api.ts`; device control is served through `ptzApi.ts`/`go2rtcClient.ts` where implemented |
| `/api/cameras/{camera_id}/onvif/capabilities`                  | GET                 | Device-control (ONVIF/PTZ/preview/baseline) endpoints — UI covers camera CRUD via `api.ts`; device control is served through `ptzApi.ts`/`go2rtcClient.ts` where implemented |
| `/api/cameras/{camera_id}/onvif/presets`                       | GET                 | Device-control (ONVIF/PTZ/preview/baseline) endpoints — UI covers camera CRUD via `api.ts`; device control is served through `ptzApi.ts`/`go2rtcClient.ts` where implemented |
| `/api/cameras/{camera_id}/onvif/presets/{preset_token}`        | POST                | Device-control (ONVIF/PTZ/preview/baseline) endpoints — UI covers camera CRUD via `api.ts`; device control is served through `ptzApi.ts`/`go2rtcClient.ts` where implemented |
| `/api/cameras/{camera_id}/onvif/ptz`                           | POST                | Device-control (ONVIF/PTZ/preview/baseline) endpoints — UI covers camera CRUD via `api.ts`; device control is served through `ptzApi.ts`/`go2rtcClient.ts` where implemented |
| `/api/cameras/{camera_id}/onvif/ptz/stop`                      | POST                | Device-control (ONVIF/PTZ/preview/baseline) endpoints — UI covers camera CRUD via `api.ts`; device control is served through `ptzApi.ts`/`go2rtcClient.ts` where implemented |
| `/api/cameras/{camera_id}/preview/start`                       | POST                | Device-control (ONVIF/PTZ/preview/baseline) endpoints — UI covers camera CRUD via `api.ts`; device control is served through `ptzApi.ts`/`go2rtcClient.ts` where implemented |
| `/api/cameras/{camera_id}/preview/stop`                        | DELETE              | Device-control (ONVIF/PTZ/preview/baseline) endpoints — UI covers camera CRUD via `api.ts`; device control is served through `ptzApi.ts`/`go2rtcClient.ts` where implemented |
| `/api/debug/batch/add-detection`                               | POST                | Debug & diagnostics surface (operator tooling only)                                                                                                                          |
| `/api/debug/batch/metrics`                                     | GET                 | Debug & diagnostics surface (operator tooling only)                                                                                                                          |
| `/api/debug/batch/reset-metrics`                               | POST                | Debug & diagnostics surface (operator tooling only)                                                                                                                          |
| `/api/debug/pipeline-state`                                    | GET                 | Debug & diagnostics surface (operator tooling only)                                                                                                                          |
| `/api/debug/profile/stats`                                     | GET                 | Debug & diagnostics surface (operator tooling only)                                                                                                                          |
| `/api/detections/export`                                       | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/enrollment-queue`                                        | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/enrollment-queue/{candidate_id}`                         | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/enrollment-queue/{candidate_id}/approve`                 | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/enrollment-queue/{candidate_id}/reject`                  | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/events/bulk`                                             | DELETE, PATCH, POST | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/face-events/match`                                       | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/health/ai-services`                                      | GET                 | External monitoring probe (Prometheus/Grafana scrape)                                                                                                                        |
| `/api/heatmaps/camera/{camera_id}/accumulator`                 | DELETE              | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/heatmaps/camera/{camera_id}/snapshot`                    | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/heatmaps/camera/{camera_id}/stats`                       | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/household-matcher/config`                                | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/household-matcher/match-batch`                           | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/household-matcher/match-person`                          | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/household-matcher/match-vehicle`                         | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/household/members/{member_id}/embeddings`                | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/jobs/bulk-cancel`                                        | POST                | Ops metrics/bulk ops not surfaced; per-job UI uses `/api/jobs/{job_id}` rows                                                                                                 |
| `/api/jobs/stats`                                              | GET                 | Ops metrics/bulk ops not surfaced; per-job UI uses `/api/jobs/{job_id}` rows                                                                                                 |
| `/api/jobs/types`                                              | GET                 | Ops metrics/bulk ops not surfaced; per-job UI uses `/api/jobs/{job_id}` rows                                                                                                 |
| `/api/plate-reads/camera/{camera_id}`                          | GET                 | Plate lookup detail — list/search UIs use the base path via `api.ts`                                                                                                         |
| `/api/plate-reads/recognize`                                   | POST                | Plate lookup detail — list/search UIs use the base path via `api.ts`                                                                                                         |
| `/api/plate-reads/statistics`                                  | GET                 | Plate lookup detail — list/search UIs use the base path via `api.ts`                                                                                                         |
| `/api/reid/search`                                             | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/scheduled-reports/{report_id}/run`                       | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/summaries/daily`                                         | GET                 | Summary detail/export endpoints — daily summary list consumed by `api.ts`                                                                                                    |
| `/api/summaries/hourly`                                        | GET                 | Summary detail/export endpoints — daily summary list consumed by `api.ts`                                                                                                    |
| `/api/summaries/{summary_id}/export`                           | GET                 | Summary detail/export endpoints — daily summary list consumed by `api.ts`                                                                                                    |
| `/api/system/models/{model_name}/status`                       | GET                 | Model lifecycle surface — load/unload/reload answer 501 by design                                                                                                            |
| `/api/system/nemotron-optimizer`                               | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/system/nemotron-optimizer/reset`                         | POST                | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/system/supervisor/status`                                | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/tracks`                                                  | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/v1/alertmanager/webhook`                                 | POST                | Inbound Alertmanager receiver — no UI                                                                                                                                        |
| `/api/webhooks/alerts`                                         | POST                | Inbound Alertmanager receiver — no UI                                                                                                                                        |
| `/api/webhooks/inbound/alert`                                  | POST                | Inbound receiver for external alarm systems (arm/disarm/mode/alert) — no UI                                                                                                  |
| `/api/webhooks/inbound/arm`                                    | POST                | Inbound receiver for external alarm systems (arm/disarm/mode/alert) — no UI                                                                                                  |
| `/api/webhooks/inbound/disarm`                                 | POST                | Inbound receiver for external alarm systems (arm/disarm/mode/alert) — no UI                                                                                                  |
| `/api/webhooks/inbound/mode`                                   | POST                | Inbound receiver for external alarm systems (arm/disarm/mode/alert) — no UI                                                                                                  |
| `/api/zones/member/{member_id}/zones`                          | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/api/zones/vehicle/{vehicle_id}/zones`                        | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/ready`                                                       | GET                 | Container readiness probe (compose healthcheck), not UI                                                                                                                      |
| `/system/detectors`                                            | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/system/detectors/active`                                     | GET, PUT            | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/system/detectors/{detector_type}`                            | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |
| `/system/detectors/{detector_type}/health`                     | GET                 | No UI consumer yet — candidate for future work or intentionally internal                                                                                                     |

## Queue Names (DLQ)

- `dlq:detection_queue` - Failed detection processing jobs
- `dlq:analysis_queue` - Failed analysis processing jobs

(Names per `backend/core/constants.py` — `DLQ_PREFIX = "dlq:"` + queue.)

**Authentication:** Destructive operations (requeue, clear) require API key via
`X-API-Key` header or `api_key` query parameter when `api_key_enabled` is true.

## Frontend-Backend Type Synchronization

All TypeScript types are auto-generated from the OpenAPI specification:

```bash
# Generate types from the backend OpenAPI schema
./scripts/generate-types.sh

# Check if types are current (CI mode)
./scripts/generate-types.sh --check
```

Generated types location: `frontend/src/types/generated/api.ts`

## Contract Testing

API contract tests ensure responses conform to their documented schemas:

- **Backend:** `backend/tests/contracts/test_api_contracts.py`
- **Frontend:** `frontend/tests/contract/` (E2E contract validation)

These validate response structure against the OpenAPI schema, required-field
presence, data types, and pagination contracts.

## CI/CD Integration

| CI job (`.github/workflows/ci.yml`) | What it runs                                                                | Fails when                                                                  |
| ----------------------------------- | --------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `api-types-check`                   | `scripts/generate-openapi.py --check` + `scripts/generate-types.sh --check` | committed spec or generated types are stale                                 |
| `api-coverage`                      | `scripts/check-api-coverage.sh`                                             | a backend decorator path has no `frontend/src` match and is not allowlisted |
| `contract-tests` (main only)        | backend + frontend contract suites                                          | responses drift from the schema                                             |

## Adding New Endpoints

1. **Define it in the backend** with proper OpenAPI documentation.
2. **Regenerate:** `./scripts/generate-types.sh` and
   `uv run python scripts/generate-openapi.py` (both are pre-commit hooks).
3. **Implement a frontend consumer** in the same PR, or add the path to the
   allowlist in `scripts/check-api-coverage.sh` with a justification comment.
4. **Verify:** `./scripts/check-api-coverage.sh`.
5. **Update this document** (or note in the PR that its row is pending —
   regeneration is the 2026-09-22 one-off pass described above).

## Guidelines

- New endpoints should have at least one frontend consumer, or an allowlisted
  justification.
- This document is a snapshot: regenerate the tables (one-off pass described in
  Generation & Validation) when a domain's surface changes materially, not per PR.
- Contract tests should validate critical response structures.
- WebSocket message formats must match
  [`websocket-contracts.md`](./websocket-contracts.md).

---

**Maintained by:** Deployment Engineering Team
**Last Updated:** 2026-09-22 (full regeneration from `docs/openapi.json`; see
[Generation & Validation](#generation--validation))
