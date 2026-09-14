# Frontend API Client Coverage Analysis

## Executive Summary

The frontend has **11 API client files** with **100+ documented endpoints**. Strong error handling patterns with retry logic, timeout, and request deduplication.

## API Client Files

### 1. api.ts (Core Infrastructure - 2,600+ lines)

**Main entry point:** `fetchApi<T>(endpoint, options?)`

**Features:**

- Timeout: 30 seconds
- Retry: 3 attempts with exponential backoff (1s → 2s → 4s)
- Request deduplication for GET requests
- Sentry integration for error tracking

**Domains covered:**

- Cameras
- Events
- Detections
- Zones
- System Status
- Analytics
- Alert Rules
- Entities
- Jobs
- Scene Changes

**Total endpoints:** 40+

### 2. alertsApi.ts

| Function         | Endpoint                       | Method |
| ---------------- | ------------------------------ | ------ |
| acknowledgeAlert | `/api/alerts/{id}/acknowledge` | POST   |
| dismissAlert     | `/api/alerts/{id}/dismiss`     | POST   |

**Special feature:** Optimistic locking with conflict detection (409 status)

### 3. aiAuditApi.ts

**13 endpoints** across audit and prompt management:

| Function          | Endpoint                              | Method |
| ----------------- | ------------------------------------- | ------ |
| getAuditSessions  | `/api/ai-audit/sessions`              | GET    |
| getAuditSession   | `/api/ai-audit/sessions/{id}`         | GET    |
| startAuditSession | `/api/ai-audit/sessions`              | POST   |
| getAuditResults   | `/api/ai-audit/sessions/{id}/results` | GET    |
| getPrompts        | `/api/prompts`                        | GET    |
| updatePrompt      | `/api/prompts/{id}`                   | PUT    |
| testPrompt        | `/api/prompts/test`                   | POST   |
| ...               | ...                                   | ...    |

### 4. auditApi.ts

**6 endpoints** for event audits:

| Function              | Endpoint                         | Method |
| --------------------- | -------------------------------- | ------ |
| getAuditLogs          | `/api/audit-logs`                | GET    |
| getAuditLog           | `/api/audit-logs/{id}`           | GET    |
| getModelContributions | `/api/audit/model-contributions` | GET    |
| getQualityScores      | `/api/audit/quality-scores`      | GET    |
| ...                   | ...                              | ...    |

### 5. gpuConfigApi.ts

**9 endpoints** for GPU configuration:

| Function         | Endpoint                          | Method |
| ---------------- | --------------------------------- | ------ |
| getGpus          | `/api/system/gpus`                | GET    |
| getGpuConfig     | `/api/system/gpu-config`          | GET    |
| updateGpuConfig  | `/api/system/gpu-config`          | PUT    |
| applyGpuConfig   | `/api/system/gpu-config/apply`    | POST   |
| getGpuStatus     | `/api/system/gpu-config/status`   | GET    |
| detectGpus       | `/api/system/gpu-config/detect`   | POST   |
| previewStrategy  | `/api/system/gpu-config/preview`  | GET    |
| getAiServices    | `/api/system/ai-services`         | GET    |
| getServiceHealth | `/api/system/gpu-config/services` | GET    |

### 6. backupApi.ts

**7 endpoints** for backup management:

| Function         | Endpoint                      | Method |
| ---------------- | ----------------------------- | ------ |
| createBackup     | `/api/backups`                | POST   |
| listBackups      | `/api/backups`                | GET    |
| getBackup        | `/api/backups/{id}`           | GET    |
| downloadBackup   | `/api/backups/{id}/download`  | GET    |
| deleteBackup     | `/api/backups/{id}`           | DELETE |
| restoreBackup    | `/api/backups/{id}/restore`   | POST   |
| getRestoreStatus | `/api/backups/restore-status` | GET    |

### 7. detectorApi.ts

**5 endpoints** for detector switching:

| Function             | Endpoint               | Method |
| -------------------- | ---------------------- | ------ |
| getDetectorStatus    | `/api/detector/status` | GET    |
| switchDetector       | `/api/detector/switch` | POST   |
| getDetectorHealth    | `/api/detector/health` | GET    |
| getDetectorConfig    | `/api/detector/config` | GET    |
| updateDetectorConfig | `/api/detector/config` | PUT    |

### 8. promptManagementApi.ts

**9 endpoints** for prompt CRUD:

| Function             | Endpoint                      | Method |
| -------------------- | ----------------------------- | ------ |
| getPrompts           | `/api/prompts`                | GET    |
| getPrompt            | `/api/prompts/{id}`           | GET    |
| updatePrompt         | `/api/prompts/{id}`           | PUT    |
| getPromptHistory     | `/api/prompts/{id}/history`   | GET    |
| restorePromptVersion | `/api/prompts/{id}/restore`   | POST   |
| exportPrompts        | `/api/prompts/export`         | GET    |
| importPrompts        | `/api/prompts/import`         | POST   |
| previewImport        | `/api/prompts/preview-import` | POST   |
| testPrompt           | `/api/prompts/test`           | POST   |

### 9. systemSettingsApi.ts

**4 endpoints** for key-value store:

| Function      | Endpoint                        | Method |
| ------------- | ------------------------------- | ------ |
| getSettings   | `/api/v1/system-settings`       | GET    |
| getSetting    | `/api/v1/system-settings/{key}` | GET    |
| upsertSetting | `/api/v1/system-settings/{key}` | PATCH  |
| deleteSetting | `/api/v1/system-settings/{key}` | DELETE |

### 10. webhookApi.ts

**14 endpoints** for webhook lifecycle:

| Function         | Endpoint                              | Method |
| ---------------- | ------------------------------------- | ------ |
| listWebhooks     | `/api/webhooks`                       | GET    |
| createWebhook    | `/api/webhooks`                       | POST   |
| getWebhook       | `/api/webhooks/{id}`                  | GET    |
| updateWebhook    | `/api/webhooks/{id}`                  | PATCH  |
| deleteWebhook    | `/api/webhooks/{id}`                  | DELETE |
| testWebhook      | `/api/webhooks/{id}/test`             | POST   |
| enableWebhook    | `/api/webhooks/{id}/enable`           | POST   |
| disableWebhook   | `/api/webhooks/{id}/disable`          | POST   |
| listDeliveries   | `/api/webhooks/{id}/deliveries`       | GET    |
| getDelivery      | `/api/webhooks/deliveries/{id}`       | GET    |
| retryDelivery    | `/api/webhooks/deliveries/{id}/retry` | POST   |
| getHealthSummary | `/api/webhooks/health`                | GET    |
| ...              | ...                                   | ...    |

### 11. scheduledReportsApi.ts

**6 endpoints** for report scheduling:

| Function      | Endpoint                              | Method |
| ------------- | ------------------------------------- | ------ |
| listReports   | `/api/scheduled-reports`              | GET    |
| createReport  | `/api/scheduled-reports`              | POST   |
| getReport     | `/api/scheduled-reports/{id}`         | GET    |
| updateReport  | `/api/scheduled-reports/{id}`         | PUT    |
| deleteReport  | `/api/scheduled-reports/{id}`         | DELETE |
| triggerReport | `/api/scheduled-reports/{id}/trigger` | POST   |

## Error Handling Patterns

### Custom Error Classes

- `ApiError` - Base error class
- `AlertsApiError` - With `isConflict` flag for 409 detection
- `NetworkError` - Connection failures
- `TimeoutError` - Request timeout
- `ValidationError` - 400 responses

### Retry Logic

```typescript
// Exponential backoff: 1s → 2s → 4s
const delays = [1000, 2000, 4000];
for (let attempt = 0; attempt < 3; attempt++) {
  try {
    return await fetch(url, options);
  } catch (error) {
    if (attempt < 2) await sleep(delays[attempt]);
  }
}
```

### Request Deduplication

```typescript
// GET requests are deduplicated to prevent duplicate calls
const pendingRequests = new Map<string, Promise<any>>();

if (method === 'GET' && pendingRequests.has(url)) {
  return pendingRequests.get(url);
}
```

## Base URLs

| Variable            | Purpose              |
| ------------------- | -------------------- |
| `VITE_API_BASE_URL` | Primary API base     |
| `VITE_API_URL`      | Legacy (alerts only) |
| `VITE_WS_BASE_URL`  | WebSocket (optional) |

## Key Patterns

### Cursor Validation

```typescript
// Base64url format enforcement with max 500 char limit
function validateCursor(cursor: string): boolean {
  return /^[A-Za-z0-9_-]{1,500}$/.test(cursor);
}
```

### Optimistic Locking

```typescript
// Alert operations detect concurrent modifications
if (response.status === 409) {
  throw new AlertsApiError('Conflict', { isConflict: true });
}
```

### Progress Polling

```typescript
// Backup, restore, GPU config use polling
async function pollStatus(id: string) {
  while (true) {
    const status = await getStatus(id);
    if (status.completed) return status;
    await sleep(2000);
  }
}
```

### WebSocket Security

```typescript
// API keys via Sec-WebSocket-Protocol, not URL params
const ws = new WebSocket(url, ['api-key', apiKey]);
```

## Coverage Summary

| Client                 | Endpoints | Status                |
| ---------------------- | --------- | --------------------- |
| api.ts                 | 40+       | ✅ Core functionality |
| alertsApi.ts           | 2         | ✅ Complete           |
| aiAuditApi.ts          | 13        | ✅ Complete           |
| auditApi.ts            | 6         | ✅ Complete           |
| gpuConfigApi.ts        | 9         | ✅ Complete           |
| backupApi.ts           | 7         | ✅ Complete           |
| detectorApi.ts         | 5         | ✅ Complete           |
| promptManagementApi.ts | 9         | ✅ Complete           |
| systemSettingsApi.ts   | 4         | ✅ Complete           |
| webhookApi.ts          | 14        | ✅ Complete           |
| scheduledReportsApi.ts | 6         | ✅ Complete           |
