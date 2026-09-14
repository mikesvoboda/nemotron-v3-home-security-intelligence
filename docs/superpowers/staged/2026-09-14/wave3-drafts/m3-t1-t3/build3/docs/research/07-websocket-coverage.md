# WebSocket Feature Coverage Analysis

## Executive Summary

The backend broadcasts **57 WebSocket message types** but the frontend only handles a subset. Significant gaps exist, particularly for **worker events** (complete gap), **Prometheus alerts**, and detailed **camera status**.

## Backend WebSocket Message Types (57 total)

### Alert Events (6)

- `alert.created`
- `alert.updated`
- `alert.deleted`
- `alert.acknowledged`
- `alert.resolved`
- `alert.dismissed`

### Camera Events (7)

- `camera.online`
- `camera.offline`
- `camera.status_changed`
- `camera.enabled`
- `camera.disabled`
- `camera.error`
- `camera.config_updated`

### Job Events (8)

- `job.started`
- `job.progress`
- `job.completed`
- `job.failed`
- `job.cancelled`
- `job_progress` (legacy)
- `job_completed` (legacy)
- `job_failed` (legacy)

### System Events (5)

- `system.health_changed`
- `system.error`
- `system.status`
- `service.status_changed`
- `gpu.stats_updated`

### Worker Events (6) - **COMPLETE GAP**

- `worker.started`
- `worker.stopped`
- `worker.health_check_failed`
- `worker.restarting`
- `worker.recovered`
- `worker.error`

### Event Events (3)

- `event.created`
- `event.updated`
- `event.deleted`

### Detection Events (2)

- `detection.new`
- `detection.batch`

### Scene Change Events (2)

- `scene_change.detected`
- `scene_change.acknowledged`

### Enrichment Events (4)

- `enrichment.started`
- `enrichment.progress`
- `enrichment.completed`
- `enrichment.failed`

### Queue/Throughput Events (2)

- `queue.status`
- `pipeline.throughput`

### Other Events (3+)

- `prometheus.alert`
- `connection.established`
- `connection.error`
- `ping` / `pong` (control)

## Frontend WebSocket Hooks (11 total)

| Hook                        | Events Handled                                                                  | Status          |
| --------------------------- | ------------------------------------------------------------------------------- | --------------- |
| useAlertWebSocket           | alert_created, alert_updated, alert_deleted, alert_acknowledged, alert_resolved | ✅ Complete     |
| useJobWebSocket             | job_progress, job_completed, job_failed                                         | ✅ Complete     |
| useEventLifecycleWebSocket  | event.created, event.updated, event.deleted                                     | ✅ Complete     |
| useEventEnrichmentWebSocket | enrichment.\*                                                                   | ✅ Complete     |
| useJobLogsWebSocket         | log messages                                                                    | ✅ Complete     |
| useCameraStatusWebSocket    | camera status changes                                                           | ⚠️ Generic only |
| useServiceStatusWebSocket   | service.status_changed                                                          | ✅ Complete     |
| useSystemHealthWebSocket    | system.health_changed                                                           | ✅ Complete     |
| useGpuStatsWebSocket        | gpu.stats_updated                                                               | ✅ Complete     |
| useQueueMetricsWebSocket    | queue.status, pipeline.throughput                                               | ✅ Complete     |
| useWebSocket                | ping/pong heartbeat                                                             | ✅ Base hook    |

## WebSocket Endpoints (4)

| Endpoint                 | Purpose                                            |
| ------------------------ | -------------------------------------------------- |
| `/ws/events`             | Security events, alerts, detections, scene changes |
| `/ws/system`             | System status, service health, GPU stats           |
| `/ws/detections`         | Raw detection events                               |
| `/ws/jobs/{job_id}/logs` | Job-specific log streaming                         |

## Critical Gaps

### 1. Worker Events (COMPLETE GAP)

**Backend broadcasts:**

- `worker.started`
- `worker.stopped`
- `worker.health_check_failed`
- `worker.restarting`
- `worker.recovered`
- `worker.error`

**Frontend:** No hook exists for pipeline worker status

**Impact:** Operators cannot see worker health in real-time

**Recommendation:** Implement `useWorkerStatusWebSocket` hook

### 2. Prometheus Alerts (NOT IMPLEMENTED)

**Backend broadcasts:** `prometheus.alert` events from AlertManager integration

**Frontend:** No handler exists

**Impact:** Infrastructure monitoring alerts not reaching UI

**Recommendation:** Add handler and alert banner component

### 3. Camera-Specific Events (PARTIAL GAP)

**Backend broadcasts:**

- `camera.online`
- `camera.offline`
- `camera.enabled`
- `camera.disabled`
- `camera.error`

**Frontend:** Uses generic `useCameraStatusWebSocket` without per-camera callbacks

**Impact:** Limited per-camera status visibility

**Recommendation:** Extend hook with per-camera status callbacks

### 4. Scene Change Acknowledgment (PARTIAL)

**Backend broadcasts:** `scene_change.acknowledged`

**Frontend:** No dedicated handler

### 5. Detection Events (LIMITED)

**Backend broadcasts:** `detection.new`, `detection.batch` on `/ws/detections`

**Frontend:** Not widely used in main dashboard

## Error Handling and Reconnection

### Strengths

- Exponential backoff reconnection (1s-30s with jitter)
- Automatic ping/pong heartbeat (30-second intervals)
- Idle timeout detection (300 seconds default)
- Connection state tracking per WebSocket URL
- Sequence number tracking for message gap detection
- Retry mechanism (up to 3 retries with metrics)

### Gaps

1. **No message buffering/replay** - When client reconnects, no mechanism to retrieve missed messages

2. **No subscription filtering UI** - Backend supports event pattern subscriptions but frontend doesn't expose filtering

3. **Limited disconnection visibility** - `hasExhaustedRetries` flag exists but no UI showing connection health

4. **No graceful degradation** - No fallback to polling when WebSocket unavailable

5. **Heartbeat timeout handling** - No logic to force reconnection if heartbeats stop

## Backend Not Shown in UI

| Feature                 | Backend Support       | UI Status                |
| ----------------------- | --------------------- | ------------------------ |
| Worker Pipeline Health  | 6 state transitions   | ❌ Never rendered        |
| Infrastructure Alerts   | Prometheus alerts     | ❌ Not displayed         |
| Camera Detailed Status  | Per-camera states     | ⚠️ Limited               |
| Queue Depth Metrics     | queue.status data     | ⚠️ Limited visualization |
| Enrichment Progress     | Full lifecycle        | ⚠️ No progress indicator |
| Batch Processing Status | Batch analysis events | ⚠️ Inconsistent use      |

## Architecture

### Broadcast Mechanisms

- **EventBroadcaster** - Security events
- **SystemBroadcaster** - System status
- **Redis pub/sub** - Job-specific logs

### Features

- **MessagePack compression** - 30-50% smaller than JSON
- **Per-client negotiation** - Binary or JSON
- **Circuit breaker** - Prevents cascading failures
- **Rate limiting** - Applied before accepting connections
- **Correlation IDs** - Debug logging

## Recommendations

### HIGH Priority

1. **Implement `useWorkerStatusWebSocket`**

   ```typescript
   // New hook needed
   export function useWorkerStatusWebSocket() {
     // Handle worker.* events
     // Display worker health in system panel
   }
   ```

2. **Add Prometheus alert handler**

   - Listen for `prometheus.alert`
   - Display in alert banner or notification

3. **Extend camera status hook**
   - Per-camera callbacks
   - Detailed error information

### MEDIUM Priority

4. **Message buffer and replay**

   - Cache recent messages server-side
   - Resync on reconnection

5. **Connection status UI**

   - Show retry attempts
   - Display connection health

6. **Event subscription UI**
   - Allow users to filter WebSocket streams
   - Reduce unnecessary messages

### LOW Priority

7. **Queue metrics visualization**

   - Dashboard widget for queue depth
   - Throughput charts

8. **Graceful degradation**
   - Fallback to polling for critical events
