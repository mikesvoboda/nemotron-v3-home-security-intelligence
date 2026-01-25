# WebSocket Feature Gap Analysis

This document analyzes the 8 major WebSocket real-time feature gaps between backend broadcasting capabilities and frontend consumption, providing a roadmap for addressing them.

## Executive Summary

Research into WebSocket real-time features revealed **8 major integration gaps** between backend broadcasting capabilities and frontend consumption. The backend has comprehensive event broadcasting infrastructure, but several events lack corresponding frontend hooks.

---

## Gap Overview

| #   | Feature                 | Backend Status       | Frontend Status     | Priority |
| --- | ----------------------- | -------------------- | ------------------- | -------- |
| 1   | Detection Events        | Implemented          | Wrong endpoint      | P0       |
| 2   | WebSocket Discovery     | Type registry exists | No API endpoint     | P0       |
| 3   | Worker Status           | Implemented          | Missing hook        | P1       |
| 4   | Scene Changes           | Implemented          | Partial integration | P1       |
| 5   | Infrastructure Alerts   | Implemented          | Missing hook        | P2       |
| 6   | Summary Updates         | Implemented          | Missing hook        | P2       |
| 7   | Batch Processing Status | Not broadcast        | N/A                 | P3       |
| 8   | Queue/Pipeline Metrics  | REST only            | Polling required    | P3       |

---

## Detailed Gap Analysis

### Gap 1: Detection Events - Wrong Endpoint (P0)

**Status**: Critical bug - frontend connects to non-existent endpoint

**Backend Implementation**:

- `broadcast_detection_new()` in `backend/services/event_broadcaster.py`
- `broadcast_detection_batch()` in `backend/services/event_broadcaster.py`
- Events broadcast on `/ws/events` channel

**Frontend Issue**:

- `frontend/src/hooks/useDetectionStream.ts` line 279
- Attempts to connect to `/ws/detections` (DOES NOT EXIST)
- Should connect to `/ws/events` instead

**Fix Required**:

```typescript
// frontend/src/hooks/useDetectionStream.ts line 279
// BEFORE:
const wsOptions = buildWebSocketOptions('/ws/detections');

// AFTER:
const wsOptions = buildWebSocketOptions('/ws/events');
```

**Impact**: Detection stream is completely non-functional in production.

---

### Gap 2: WebSocket Discovery API (P0)

**Status**: No programmatic way to discover available WebSocket endpoints

**Backend Assets**:

- `backend/core/websocket/event_types.py` - Complete event type registry with:
  - `WebSocketEventType` enum (35+ event types)
  - `EVENT_TYPE_METADATA` dict with descriptions, channels, payload fields
  - Helper functions: `get_event_channel()`, `get_all_event_types()`, `get_all_channels()`

**Gap**: This rich metadata is not exposed via any API endpoint.

**Proposed Solution**:

1. Create capabilities endpoint:

```python
# backend/api/routes/websocket.py
@router.get("/api/websocket/capabilities")
async def get_websocket_capabilities():
    return {
        "endpoints": [
            {
                "path": "/ws/events",
                "description": "Real-time security and system events",
                "events": [...],
                "authentication": "optional"
            },
            {
                "path": "/ws/system",
                "description": "System health and GPU stats",
                "events": [...],
                "authentication": "optional"
            }
        ],
        "event_registry": {
            "alert.created": {
                "description": "New alert triggered",
                "channel": "alerts",
                "payload_fields": ["id", "severity", "status"]
            },
            ...
        },
        "channels": ["alerts", "cameras", "events", "system", ...]
    }
}
```

2. Create frontend discovery hook:

```typescript
// frontend/src/hooks/useWebSocketCapabilities.ts
export function useWebSocketCapabilities() {
  return useQuery({
    queryKey: ['websocket', 'capabilities'],
    queryFn: fetchWebSocketCapabilities,
    staleTime: Infinity, // Capabilities rarely change
  });
}
```

---

### Gap 3: Worker Status Events (P1)

**Status**: Backend broadcasts, frontend doesn't consume

**Backend Implementation**:

- `broadcast_worker_status()` in `backend/services/event_broadcaster.py`
- `WebSocketWorkerStatusMessage` schema exists
- Events: `worker.started`, `worker.stopped`, `worker.health_check_failed`, `worker.restarting`, `worker.recovered`, `worker.error`

**Frontend Gap**:

- No `useWorkerStatusWebSocket` hook exists
- Pipeline health not visible in real-time to users

**Proposed Solution**:

```typescript
// frontend/src/hooks/useWorkerStatusWebSocket.ts
export interface WorkerStatus {
  worker_name: string;
  worker_type: string;
  event_type: 'worker.started' | 'worker.stopped' | 'worker.error' | ...;
  timestamp: string;
}

export function useWorkerStatusWebSocket(options = {}) {
  const [workers, setWorkers] = useState<Record<string, WorkerStatus>>({});

  // Subscribe to worker_status events on /ws/events
  const { isConnected } = useWebSocket({
    url: buildWebSocketOptions('/ws/events').url,
    onMessage: (data) => {
      if (data.type === 'worker_status') {
        setWorkers(prev => ({
          ...prev,
          [data.data.worker_name]: data.data
        }));
      }
    }
  });

  return { workers, isConnected };
}
```

---

### Gap 4: Scene Change Events (P1)

**Status**: Backend broadcasts, frontend has partial implementation

**Backend Implementation**:

- `broadcast_scene_change()` in `backend/services/event_broadcaster.py`
- `WebSocketSceneChangeMessage` schema exists
- Includes: `camera_id`, `change_type`, `similarity_score`, `detected_at`

**Frontend Status**:

- `useSceneChangeEvents` hook exists but may not be fully integrated with UI
- Scene change events documented in contracts but not in `WebSocketEventMap`

**Gap**:

- Scene changes not fully surfaced in the dashboard
- No visual indicator for camera tampering

**Proposed Enhancement**:

1. Add `scene_change` to `WebSocketEventMap`
2. Create dedicated scene change notification component
3. Add camera tampering indicator to camera status displays

---

### Gap 5: Infrastructure Alerts (P2)

**Status**: Backend broadcasts Prometheus alerts, frontend doesn't consume

**Backend Implementation**:

- `broadcast_infrastructure_alert()` in `backend/services/event_broadcaster.py`
- `WebSocketInfrastructureAlertMessage` schema exists
- Receives alerts from Prometheus/Alertmanager webhook

**Frontend Gap**:

- No hook to consume infrastructure alerts
- System health issues not visible in real-time

**Proposed Solution**:

```typescript
// frontend/src/hooks/useInfrastructureAlertsWebSocket.ts
export interface InfrastructureAlert {
  alertname: string;
  status: 'firing' | 'resolved';
  severity: 'warning' | 'critical';
  component: string;
  summary: string;
  started_at: string;
}

export function useInfrastructureAlertsWebSocket() {
  const [alerts, setAlerts] = useState<InfrastructureAlert[]>([]);

  // Subscribe to infrastructure_alert events
  // Show toast/banner for firing alerts
  // Clear resolved alerts automatically
}
```

---

### Gap 6: Summary Updates (P2)

**Status**: Backend broadcasts, frontend doesn't consume

**Backend Implementation**:

- `broadcast_summary_update()` in `backend/services/event_broadcaster.py`
- `WebSocketSummaryUpdateMessage` schema exists
- Broadcasts when hourly/daily summaries are generated

**Frontend Gap**:

- Summary page requires manual refresh
- No real-time summary update notification

**Proposed Solution**:

```typescript
// frontend/src/hooks/useSummaryUpdatesWebSocket.ts
export function useSummaryUpdatesWebSocket({ onHourlySummary, onDailySummary }) {
  // Subscribe to summary_update events
  // Invalidate React Query cache for summaries
  // Optionally show toast notification
}
```

---

### Gap 7: Batch Processing Status (P3)

**Status**: Not currently broadcast

**Current State**:

- Batch aggregator tracks active batches internally
- No WebSocket event when batches are opened/in-progress
- Only `detection.batch` sent on batch close

**Proposed Enhancement**:
Add `batch.opened` and `batch.progress` events:

```python
# New event types
BATCH_OPENED = "batch.opened"
BATCH_PROGRESS = "batch.progress"

# New broadcast methods
async def broadcast_batch_opened(batch_data):
    # Camera started new detection batch
    ...

async def broadcast_batch_progress(batch_data):
    # Batch accumulating detections (throttled)
    ...
```

**Benefit**: Real-time visibility into AI pipeline processing state.

---

### Gap 8: Queue/Pipeline Metrics Real-time (P3)

**Status**: Currently REST polling only

**Current State**:

- Queue depth available via REST API: `GET /api/system/queue`
- Pipeline metrics available via REST API: `GET /api/system/pipeline`
- No WebSocket streaming of queue metrics

**Proposed Enhancement**:

1. Add queue metrics to `system_status` broadcast:

```json
{
  "type": "system_status",
  "data": {
    "gpu": {...},
    "cameras": {...},
    "queue": {
      "pending": 2,
      "processing": 1,
      "pending_batches": 3,
      "avg_wait_time_ms": 150
    },
    "health": "healthy"
  }
}
```

2. Or create dedicated `queue.metrics` event type

**Benefit**: Reduce REST polling, improve real-time dashboard responsiveness.

---

## Implementation Roadmap

### Phase 1: P0 Critical Fixes (Immediate)

**Timeline**: 1-2 days

1. **Fix useDetectionStream endpoint** (Gap 1)

   - Change `/ws/detections` to `/ws/events`
   - Test detection stream functionality
   - Update tests

2. **Create WebSocket capabilities API** (Gap 2)
   - Add `GET /api/websocket/capabilities` endpoint
   - Create `WebSocketCapabilitiesResponse` schema
   - Create `useWebSocketCapabilities` hook (optional)

### Phase 2: P1 High Value (Short-term)

**Timeline**: 1 week

3. **Add useWorkerStatusWebSocket hook** (Gap 3)

   - Create hook for pipeline worker health
   - Add worker status to System page

4. **Enhance scene change integration** (Gap 4)
   - Add to `WebSocketEventMap`
   - Create tampering indicator component
   - Add to camera status display

### Phase 3: P2 Nice to Have (Medium-term)

**Timeline**: 2-3 weeks

5. **Add useInfrastructureAlertsWebSocket** (Gap 5)

   - Create hook for Prometheus alerts
   - Add infrastructure alert banner

6. **Add useSummaryUpdatesWebSocket** (Gap 6)
   - Create hook for summary notifications
   - Auto-refresh summary page

### Phase 4: P3 Future Enhancements

**Timeline**: Backlog

7. **Batch processing events** (Gap 7)

   - Add batch.opened, batch.progress events
   - Requires backend changes

8. **Queue metrics streaming** (Gap 8)
   - Add to system_status or new event type
   - Reduce REST polling

---

## Technical Debt Considerations

The large gap between backend capabilities and frontend consumption suggests:

1. **Backend-first development**: Backend was built with comprehensive event broadcasting, but frontend hooks were added incrementally
2. **Missing integration tests**: No automated tests to verify frontend consumes all backend events
3. **No discovery mechanism**: Without a capabilities API, developers don't know what events exist

### Recommended Long-term Solutions

1. **Integration test suite**:

   - Discover all backend WebSocket event types
   - Verify frontend has corresponding hooks/consumers
   - Fail build if gaps are introduced

2. **Code generation**:

   - Generate TypeScript types from backend event schemas
   - Keep frontend types in sync automatically

3. **Documentation generation**:
   - Auto-generate WebSocket documentation from event registry
   - Keep docs always current

---

## Related Issues

| Issue    | Title                                 | Status      |
| -------- | ------------------------------------- | ----------- |
| NEM-3639 | WebSocket endpoint discovery gap      | In Progress |
| NEM-3644 | Summary - 8 WebSocket gaps identified | In Progress |

---

## Related Documentation

- [WebSocket Endpoints Reference](websocket-endpoints.md) - Complete endpoint documentation
- [WebSocket Message Contracts](../developer/api/websocket-contracts.md) - Message schemas
- [Event Type Registry](../../backend/core/websocket/event_types.py) - Source of truth for events

---

**Version**: 1.0
**Last Updated**: 2026-01-25
**Status**: Active
