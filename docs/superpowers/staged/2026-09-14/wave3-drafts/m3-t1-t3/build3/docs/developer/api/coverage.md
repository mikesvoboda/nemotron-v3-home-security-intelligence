# API Coverage Documentation

## Overview

This document maps all backend API endpoints to their frontend consumers, ensuring complete API coverage and identifying any unused endpoints.

**Total Endpoints:** 142 (from OpenAPI spec)

## Generation & Validation

API coverage is automatically validated in CI via `./scripts/check-api-coverage.sh`. This script:

1. Extracts all backend route definitions from `backend/api/routes/*.py`
2. Scans frontend code for endpoint consumers
3. Reports unused endpoints with actionable feedback
4. Fails CI if unmapped endpoints are found (unless allowlisted)

**Note:** Some internal/admin endpoints may be intentionally unused and should be added to the allowlist in `scripts/check-api-coverage.sh`.

## OpenAPI Specification

The complete OpenAPI specification is committed at `docs/openapi.json` and can be regenerated with:

```bash
# Generate OpenAPI spec
./scripts/generate-types.sh

# Or directly with Python
python -c "
from backend.main import app
import json
with open('docs/openapi.json', 'w') as f:
    json.dump(app.openapi(), f, indent=2, sort_keys=True)
"
```

Interactive documentation is available at runtime:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## API Endpoints by Domain

### System Health & Configuration

| Endpoint                   | Method | Consumer(s)                 | Purpose              |
| -------------------------- | ------ | --------------------------- | -------------------- |
| `/`                        | GET    | `Dashboard.tsx`, `error.ts` | Health check         |
| `/api/system/health`       | GET    | `useSystemHealth.ts`        | Health status        |
| `/api/system/health/ready` | GET    | CI/deployment scripts       | Readiness probe      |
| `/api/system/stats`        | GET    | `useSystemStats.ts`         | System statistics    |
| `/api/system/gpu`          | GET    | `GPUMonitor.tsx`            | GPU metrics          |
| `/api/system/config`       | GET    | `useSystemConfig.ts`        | System configuration |
| `/api/system/config`       | PATCH  | `Settings.tsx`              | Update configuration |

### Cameras

| Endpoint            | Method | Consumer(s)                       | Purpose           |
| ------------------- | ------ | --------------------------------- | ----------------- |
| `/api/cameras`      | GET    | `useCameras.ts`, `CameraGrid.tsx` | List cameras      |
| `/api/cameras/{id}` | GET    | `CameraDetail.tsx`                | Get single camera |
| `/api/cameras`      | POST   | `CameraSettings.tsx`              | Create camera     |
| `/api/cameras/{id}` | PUT    | `CameraSettings.tsx`              | Update camera     |
| `/api/cameras/{id}` | DELETE | `CameraSettings.tsx`              | Delete camera     |

### Events

| Endpoint             | Method | Consumer(s)                                          | Purpose                      |
| -------------------- | ------ | ---------------------------------------------------- | ---------------------------- |
| `/api/events`        | GET    | `useEvents.ts`, `EventFeed.tsx`, `EventTimeline.tsx` | List events with pagination  |
| `/api/events/{id}`   | GET    | `EventModal.tsx`                                     | Get event details            |
| `/api/events/{id}`   | PATCH  | `EventModal.tsx`                                     | Update event (review, notes) |
| `/api/events/search` | POST   | `useEventSearch.ts`, `EventSearch.tsx`               | Search events                |

### Detections

| Endpoint                    | Method | Consumer(s)           | Purpose                    |
| --------------------------- | ------ | --------------------- | -------------------------- |
| `/api/detections`           | GET    | `useDetections.ts`    | List detections            |
| `/api/detections/{id}`      | GET    | `DetectionDetail.tsx` | Get detection details      |
| `/api/detections/aggregate` | GET    | `RiskGauge.tsx`       | Aggregated detection stats |

### Alerts & Alert Rules

| Endpoint                       | Method | Consumer(s)                              | Purpose                             |
| ------------------------------ | ------ | ---------------------------------------- | ----------------------------------- |
| `/api/alerts`                  | GET    | `useAlerts.ts`                           | List active alerts                  |
| `/api/alerts/{id}`             | DELETE | `AlertCenter.tsx`                        | Dismiss alert                       |
| `/api/alerts/{id}/acknowledge` | POST   | `AlertCenter.tsx`                        | Acknowledge an alert                |
| `/api/alerts/{id}/dismiss`     | POST   | `AlertCenter.tsx`                        | Dismiss an alert                    |
| `/api/alerts/rules`            | GET    | `useAlertRules.ts`, `AlertRulesList.tsx` | List alert rules                    |
| `/api/alerts/rules`            | POST   | `AlertRuleEditor.tsx`                    | Create alert rule                   |
| `/api/alerts/rules/{id}`       | GET    | `AlertRuleDetail.tsx`                    | Get single alert rule               |
| `/api/alerts/rules/{id}`       | PUT    | `AlertRuleEditor.tsx`                    | Update alert rule                   |
| `/api/alerts/rules/{id}`       | DELETE | `AlertRulesList.tsx`                     | Delete alert rule                   |
| `/api/alerts/rules/{id}/test`  | POST   | `AlertRuleEditor.tsx`                    | Test rule against historical events |

### Zones

| Endpoint          | Method | Consumer(s)                      | Purpose     |
| ----------------- | ------ | -------------------------------- | ----------- |
| `/api/zones`      | GET    | `useZones.ts`, `ZoneManager.tsx` | List zones  |
| `/api/zones`      | POST   | `ZoneEditor.tsx`                 | Create zone |
| `/api/zones/{id}` | PUT    | `ZoneEditor.tsx`                 | Update zone |
| `/api/zones/{id}` | DELETE | `ZoneManager.tsx`                | Delete zone |

### Analytics & Metrics

| Endpoint                    | Method | Consumer(s)                             | Purpose             |
| --------------------------- | ------ | --------------------------------------- | ------------------- |
| `/api/analytics/events`     | GET    | `useAnalytics.ts`, `Dashboard.tsx`      | Event analytics     |
| `/api/analytics/detections` | GET    | `useAnalytics.ts`                       | Detection analytics |
| `/api/metrics`              | GET    | `useMetrics.ts`, `MetricsDashboard.tsx` | Prometheus metrics  |
| `/api/metrics/slis`         | GET    | `SLIMonitor.tsx`                        | SLI metrics         |

### Audit & Logging

| Endpoint          | Method | Consumer(s)                          | Purpose                     |
| ----------------- | ------ | ------------------------------------ | --------------------------- |
| `/api/audit/logs` | GET    | `useAuditLogs.ts`, `AuditViewer.tsx` | Audit trail                 |
| `/api/logs`       | GET    | `useLogs.ts`, `LogViewer.tsx`        | Application logs            |
| `/api/logs`       | POST   | `useLogger.ts`                       | Send client logs to backend |
| `/api/logs/stats` | GET    | `LogStats.tsx`                       | Log statistics              |

### AI Audit & Analysis

| Endpoint                        | Method | Consumer(s)                             | Purpose                       |
| ------------------------------- | ------ | --------------------------------------- | ----------------------------- |
| `/api/ai-audit/stats`           | GET    | `useAiAudit.ts`, `AiAuditDashboard.tsx` | AI performance stats          |
| `/api/ai-audit/leaderboard`     | GET    | `AiLeaderboard.tsx`                     | Model performance leaderboard |
| `/api/ai-audit/recommendations` | GET    | `AiRecommendations.tsx`                 | AI improvement suggestions    |

### Notifications & Preferences

| Endpoint                        | Method | Consumer(s)                                           | Purpose              |
| ------------------------------- | ------ | ----------------------------------------------------- | -------------------- |
| `/api/notification-preferences` | GET    | `useNotificationPrefs.ts`, `NotificationSettings.tsx` | Get preferences      |
| `/api/notification-preferences` | PUT    | `NotificationSettings.tsx`                            | Update preferences   |
| `/api/notifications`            | GET    | `useNotifications.ts`                                 | List notifications   |
| `/api/notifications/{id}`       | DELETE | `NotificationCenter.tsx`                              | Dismiss notification |

### Administrative

| Endpoint                  | Method | Consumer(s)        | Purpose         |
| ------------------------- | ------ | ------------------ | --------------- |
| `/api/admin/seed/cameras` | POST   | Test fixtures only | Seed test data  |
| `/api/admin/seed/events`  | POST   | Test fixtures only | Seed test data  |
| `/api/admin/seed/clear`   | DELETE | Test fixtures only | Clear test data |

### WebSocket

| Route | Consumer(s)                                     | Purpose                                           |
| ----- | ----------------------------------------------- | ------------------------------------------------- |
| `/ws` | `useWebSocket.ts`, `useRealtimeSubscription.ts` | Real-time updates (events, detections, GPU stats) |

### WebSocket Message Contracts

See `docs/WEBSOCKET_CONTRACTS.md` for detailed WebSocket message format specifications.

### Dead Letter Queue (DLQ) Management

| Endpoint                            | Method | Consumer(s)      | Purpose                                        |
| ----------------------------------- | ------ | ---------------- | ---------------------------------------------- |
| `/api/dlq/stats`                    | GET    | `DLQMonitor.tsx` | Get DLQ statistics (queue counts)              |
| `/api/dlq/jobs/{queue_name}`        | GET    | `DLQViewer.tsx`  | List jobs in a specific DLQ with context       |
| `/api/dlq/requeue/{queue_name}`     | POST   | `DLQViewer.tsx`  | Requeue oldest job from DLQ (requires API key) |
| `/api/dlq/requeue-all/{queue_name}` | POST   | `DLQViewer.tsx`  | Requeue all jobs from DLQ (requires API key)   |
| `/api/dlq/{queue_name}`             | DELETE | `DLQViewer.tsx`  | Clear all jobs from a DLQ (requires API key)   |

**Queue Names:**

- `dlq:detection` - Failed detection processing jobs
- `dlq:analysis` - Failed analysis processing jobs

**Authentication:** Destructive operations (requeue, clear) require API key via `X-API-Key` header or `api_key` query parameter when `api_key_enabled` is true.

## Missing Implementations

Endpoints defined in backend but not yet consumed by frontend (intentional or future work):

| Endpoint                         | Reason                       | Priority               |
| -------------------------------- | ---------------------------- | ---------------------- |
| `/api/prompt-management/{model}` | Admin-only prompt management | Low - Future phase     |
| `/api/entities`                  | Entity relationship tracking | Low - Advanced feature |

## Coverage Reports

### Latest Validation

- **Total Endpoints:** 151
- **Documented Categories:** 20
- **Last Updated:** 2026-01-28
- **CI Status:** Passing

Run locally:

```bash
./scripts/check-api-coverage.sh
```

## Frontend-Backend Type Synchronization

All TypeScript types are auto-generated from the OpenAPI specification:

```bash
# Generate types from backend OpenAPI schema
./scripts/generate-types.sh

# Check if types are current (CI mode)
./scripts/generate-types.sh --check
```

**Important:** Generated types must match backend schemas exactly. CI will fail if types are out of sync with the backend.

Generated types location: `frontend/src/types/generated/api.ts`

## Contract Testing

API contract tests ensure responses conform to their documented schemas:

- **Backend:** `backend/tests/contracts/test_api_contracts.py`
- **Frontend:** `frontend/tests/contract/` (E2E contract validation)

These tests validate:

- Response structure matches OpenAPI schema
- Required fields are present
- Data types are correct
- Pagination contracts

## CI/CD Integration

### Type Validation (Every PR)

```yaml
api-types-check:
  - Generates types from OpenAPI
  - Compares with committed types
  - Fails if out of sync
```

### Coverage Validation (Every PR)

```yaml
api-coverage:
  - Scans for unmapped endpoints
  - Fails if new endpoints without consumers
```

### Contract Tests (Main branch only)

```yaml
contract-tests:
  - Validates request/response cycles
  - Ensures schema compliance
  - Creates Linear issue on failure
```

## Adding New Endpoints

When adding a new API endpoint:

1. **Define in backend** with proper OpenAPI documentation
2. **Run type generation:** `./scripts/generate-types.sh`
3. **Implement frontend consumer** in same PR
4. **Verify coverage:** `./scripts/check-api-coverage.sh`
5. **Add to allowlist** if intentionally unused (with justification in comment)

## Guidelines

- All new endpoints must have at least one frontend consumer
- If endpoint cannot be consumed yet, add to allowlist with justification
- Update this document when adding major features
- Contract tests should validate critical response structures
- WebSocket message formats must match the specification in `WEBSOCKET_CONTRACTS.md`

---

**Maintained by:** Deployment Engineering Team
**Last Updated:** 2026-01-28
