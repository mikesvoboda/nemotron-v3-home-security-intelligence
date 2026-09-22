# Integration Gaps Report

**Generated:** 2026-01-20
**Methodology:** Parallel agent research across 15 specialized areas
**Scope:** Full-stack integration analysis including backend APIs, frontend consumption, WebSocket events, database models, UI components, and configuration exposure

---

## Executive Summary

This comprehensive codebase analysis identified **47 significant integration gaps** where backend capabilities are not fully utilized by the frontend. The analysis covered 200+ API endpoints, 249+ React components, 140+ custom hooks, 36 database models, and 42+ WebSocket event types.

### Key Findings by Category

| Category                      | Gap Count | Priority |
| ----------------------------- | --------- | -------- |
| WebSocket Events Not Consumed | 5         | High     |
| Underutilized Custom Hooks    | 18        | Medium   |
| Backend Config Not Exposed    | 12        | Medium   |
| Missing UI Components         | 4         | High     |
| Orphaned Components           | 1         | Low      |
| Integration Pattern Issues    | 7         | High     |

---

## 1. WebSocket Events Not Consumed by Frontend

The backend broadcasts several WebSocket event types that the frontend does not consume, representing missed opportunities for real-time updates.

### Critical Gaps

| Event Type               | Backend Location                        | Description                        | Impact                              |
| ------------------------ | --------------------------------------- | ---------------------------------- | ----------------------------------- |
| `detection.new`          | `backend/services/detection_service.py` | Real-time individual AI detections | Users miss instant detection alerts |
| `detection.batch`        | `backend/services/batch_processor.py`   | Batch detection completions        | No real-time batch status           |
| `service.status_changed` | `backend/services/service_manager.py`   | Container service status changes   | Service health not reflected live   |
| `gpu.stats_updated`      | `backend/services/gpu_monitor.py`       | GPU utilization metrics            | Dashboard shows stale GPU data      |
| `system.health_changed`  | `backend/services/health_service.py`    | System health state transitions    | Health alerts delayed               |

### Recommended Actions

1. **Create `useDetectionStream` hook** - Subscribe to `detection.new` and `detection.batch` events for real-time detection display
2. **Enhance ServiceStatus component** - Consume `service.status_changed` for instant status updates
3. **Add GPU real-time widget** - Use `gpu.stats_updated` for live GPU monitoring
4. **Integrate health transitions** - Connect `system.health_changed` to notification system

---

## 2. Underutilized Custom Hooks (18 Identified)

These hooks were built but have zero or minimal usage in the codebase.

### High-Value Underutilized Hooks

| Hook                        | File                                         | Lines | Usage Count | Potential Value                     |
| --------------------------- | -------------------------------------------- | ----- | ----------- | ----------------------------------- |
| `useRiskHistoryQuery`       | `hooks/queries/useRiskHistoryQuery.ts`       | ~80   | 0           | Historical risk trend visualization |
| `useWorkerEvents`           | `hooks/useWorkerEvents.ts`                   | ~120  | 0           | AI worker status monitoring         |
| `usePrometheusAlerts`       | `hooks/queries/usePrometheusAlerts.ts`       | ~95   | 0           | Prometheus alert integration        |
| `useZones`                  | `hooks/queries/useZones.ts`                  | ~70   | 1           | Zone-based detection filtering      |
| `useTrashQuery`             | `hooks/queries/useTrashQuery.ts`             | ~60   | 0           | Soft-deleted item recovery          |
| `usePromptImportExport`     | `hooks/usePromptImportExport.ts`             | ~150  | 0           | AI prompt backup/restore            |
| `useInteractionTracking`    | `hooks/useInteractionTracking.ts`            | ~90   | 0           | User interaction analytics          |
| `useAuditLogsInfiniteQuery` | `hooks/queries/useAuditLogsInfiniteQuery.ts` | ~110  | 0           | Infinite-scroll audit logs          |

### Medium-Value Underutilized Hooks

| Hook                         | File                                     | Usage Count | Notes                        |
| ---------------------------- | ---------------------------------------- | ----------- | ---------------------------- |
| `useHouseholdApi`            | `hooks/useHouseholdApi.ts`               | 0           | Multi-household support      |
| `useServiceMutations`        | `hooks/mutations/useServiceMutations.ts` | 1           | Service control actions      |
| `useTimelineData`            | `hooks/useTimelineData.ts`               | 0           | Timeline visualization       |
| `useCameraGroupings`         | `hooks/queries/useCameraGroupings.ts`    | 0           | Camera organization          |
| `useDetectionFilters`        | `hooks/useDetectionFilters.ts`           | 1           | Advanced detection filtering |
| `useSystemMetrics`           | `hooks/queries/useSystemMetrics.ts`      | 0           | System performance metrics   |
| `useNotificationPreferences` | `hooks/useNotificationPreferences.ts`    | 0           | User notification settings   |
| `useExportJobs`              | `hooks/queries/useExportJobs.ts`         | 0           | Data export functionality    |
| `useAlertHistory`            | `hooks/queries/useAlertHistory.ts`       | 1           | Alert history queries        |
| `useModelStatus`             | `hooks/queries/useModelStatus.ts`        | 0           | AI model status monitoring   |

### Recommended Actions

1. **Integrate risk history** - Add trend visualization to dashboard using `useRiskHistoryQuery`
2. **Enable Prometheus alerts UI** - Create alert management page using `usePrometheusAlerts`
3. **Add trash/recovery page** - Implement soft-delete recovery using `useTrashQuery`
4. **Build worker status panel** - Display AI worker health using `useWorkerEvents`
5. **Add audit log pagination** - Replace current audit table with `useAuditLogsInfiniteQuery`

---

## 3. Backend Configuration Not Exposed to UI

The backend has 100+ configurable settings across 12 categories that lack UI exposure.

### Debug & Development Tools (High Value)

| Feature               | Backend Endpoint                    | Description                     |
| --------------------- | ----------------------------------- | ------------------------------- |
| Request Recording     | `POST /api/debug/recording/start`   | Record HTTP requests for replay |
| Request Replay        | `POST /api/debug/recording/replay`  | Replay recorded requests        |
| Live Log Levels       | `PUT /api/debug/log-level/{logger}` | Change log levels at runtime    |
| Performance Profiling | `POST /api/debug/profiling/start`   | CPU/memory profiling            |
| Memory Analysis       | `GET /api/debug/memory/snapshot`    | Memory usage analysis           |

### System Monitoring (High Value)

| Feature                | Backend Endpoint                  | Description                 |
| ---------------------- | --------------------------------- | --------------------------- |
| Circuit Breaker Status | `GET /api/debug/circuit-breakers` | View circuit breaker states |
| GPU Stats History      | `GET /api/gpu/history`            | Historical GPU metrics      |
| Model Zoo Status       | `GET /api/models/status`          | AI model loading status     |
| Worker Queue Depth     | `GET /api/workers/queue`          | Processing queue metrics    |
| Connection Pool Stats  | `GET /api/debug/connections`      | Database connection health  |

### Configuration Management (Medium Value)

| Feature           | Backend Endpoint                  | Description             |
| ----------------- | --------------------------------- | ----------------------- |
| Feature Flags     | `GET/PUT /api/config/features`    | Runtime feature toggles |
| Rate Limit Config | `GET/PUT /api/config/rate-limits` | API rate limit settings |

### Recommended Actions

1. **Create Debug Tools page** - Admin panel for development/debugging tools
2. **Add System Monitoring dashboard** - Real-time system health visualization
3. **Build Configuration Manager** - UI for runtime configuration changes

---

## 4. Missing UI Components for Existing Backend Features

### Severity Thresholds Configuration

- **Backend:** `PUT /api/config/severity-thresholds`
- **Component exists:** `SeverityThresholds.tsx` (built but not integrated)
- **Gap:** Component not mounted in Settings page
- **Fix:** Add to Settings page under Alert Configuration section

### Notification Preferences

- **Backend:** Full notification preferences API exists
  - `GET/PUT /api/notifications/preferences`
  - `GET/PUT /api/notifications/quiet-hours`
  - `GET/PUT /api/notifications/per-camera`
- **Gap:** No UI for any notification settings
- **Fix:** Create NotificationSettings page with:
  - Per-camera notification toggles
  - Quiet hours configuration
  - Notification channel preferences

### System Anomaly Configuration

- **Backend:** `GET/PUT /api/anomalies/config`
- **Gap:** No UI for anomaly detection thresholds
- **Fix:** Add Anomaly Settings section to System Config page

### Export/Backup Configuration

- **Backend:**
  - `POST /api/export/schedule`
  - `GET /api/export/jobs`
  - `POST /api/backup/create`
- **Gap:** No UI for scheduled exports or backups
- **Fix:** Create Data Management page with export scheduling and backup controls

---

## 5. Orphaned UI Components

### Confirmed Orphaned

| Component            | File                                                   | Size         | Lines |
| -------------------- | ------------------------------------------------------ | ------------ | ----- |
| `AuditTableInfinite` | `frontend/src/components/audit/AuditTableInfinite.tsx` | 16,779 bytes | 448   |

### Analysis

- Zero imports detected across entire codebase
- Built for infinite-scroll audit logs
- Superseded by standard `AuditTable` component
- Contains potentially reusable infinite scroll logic

### Recommended Actions

1. **Evaluate for removal** - If functionality not needed, delete to reduce bundle size
2. **Consider integration** - If infinite scroll is desired, integrate into audit page
3. **Extract patterns** - If deleting, consider extracting infinite scroll logic to shared utility

---

## 6. Integration Pattern Issues

### 6.1 Missing Optimistic Updates

**Problem:** Mutations do not use optimistic updates, causing UI lag after user actions.

**Affected Areas:**

- Detection status changes
- Alert acknowledgments
- Camera settings updates
- User preference changes

**Fix:** Add optimistic update patterns to TanStack Query mutations:

```typescript
// Example pattern
useMutation({
  mutationFn: updateDetection,
  onMutate: async (newData) => {
    await queryClient.cancelQueries(['detections']);
    const previous = queryClient.getQueryData(['detections']);
    queryClient.setQueryData(['detections'], (old) => /* optimistic update */);
    return { previous };
  },
  onError: (err, newData, context) => {
    queryClient.setQueryData(['detections'], context.previous);
  },
  onSettled: () => {
    queryClient.invalidateQueries(['detections']);
  }
});
```

### 6.2 WebSocket-to-Cache Synchronization

**Problem:** WebSocket events don't invalidate or update React Query cache, causing stale data.

**Affected Events:**

- All `*.created`, `*.updated`, `*.deleted` events
- Real-time detection events
- System status changes

**Fix:** Create centralized WebSocket-to-cache bridge:

```typescript
// Subscribe to WebSocket events and update cache
useEffect(() => {
  const unsubscribe = wsClient.on('detection.created', (detection) => {
    queryClient.setQueryData(['detections'], (old) => [...old, detection]);
  });
  return unsubscribe;
}, []);
```

### 6.3 No Centralized Error Boundary for API Errors

**Problem:** API errors handled inconsistently across components.

**Current State:**

- Some components show toast notifications
- Some components show inline errors
- Some components fail silently
- No global error recovery

**Fix:** Implement centralized error handling:

1. Create `ApiErrorBoundary` component
2. Add global error handler to API client
3. Standardize error display patterns

### 6.4 Inconsistent Loading State Patterns

**Problem:** Loading states vary between components.

**Observed Patterns:**

- Skeleton loaders (some components)
- Spinner (some components)
- No indicator (some components)
- Text "Loading..." (some components)

**Fix:** Create standardized loading components and patterns:

1. Define loading component library
2. Create loading state guidelines
3. Apply consistently across all data-fetching components

### 6.5 Silent WebSocket Failures

**Problem:** WebSocket disconnections not surfaced to users.

**Current Behavior:**

- WebSocket disconnects silently
- Automatic reconnection attempted
- No user notification of connection issues
- Stale data displayed without warning

**Fix:**

1. Add connection status indicator to UI
2. Show banner when disconnected
3. Indicate which data may be stale

### 6.6 Missing Request Deduplication

**Problem:** Identical requests can be fired multiple times.

**Fix:** Enable request deduplication in TanStack Query:

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000, // Prevent refetch within 5s
      refetchOnWindowFocus: false,
    },
  },
});
```

### 6.7 No Retry Logic for Failed Mutations

**Problem:** Failed mutations don't retry automatically.

**Fix:** Add retry configuration:

```typescript
useMutation({
  mutationFn: saveSettings,
  retry: 3,
  retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
});
```

---

## 7. Database Models Underexposed to Frontend

The following database models have limited or no frontend representation:

| Model                    | Backend Location           | Frontend Exposure | Gap                     |
| ------------------------ | -------------------------- | ----------------- | ----------------------- |
| `SystemAnomaly`          | `models/system_anomaly.py` | None              | No anomaly viewer       |
| `ExportJob`              | `models/export_job.py`     | None              | No export management UI |
| `AuditLogEntry`          | `models/audit_log.py`      | Partial           | Limited filtering       |
| `NotificationPreference` | `models/notification.py`   | None              | No preferences UI       |
| `CameraGroup`            | `models/camera_group.py`   | None              | No grouping UI          |
| `DetectionZone`          | `models/detection_zone.py` | Partial           | No zone editor          |
| `ScheduledTask`          | `models/scheduled_task.py` | None              | No task scheduler UI    |
| `ModelVersion`           | `models/model_version.py`  | None              | No model management UI  |
| `PerformanceMetric`      | `models/performance.py`    | Partial           | Limited metrics display |
| `UserSession`            | `models/user_session.py`   | None              | No session management   |

---

## 8. Priority Recommendations

### Phase 1: Quick Wins (Low Effort, High Impact)

1. **Mount SeverityThresholds component** - Component exists, just needs integration
2. **Fix WebSocket event consumption** - Add handlers for 5 unused events
3. **Integrate `useAuditLogsInfiniteQuery`** - Replace standard table with infinite scroll
4. **Add connection status indicator** - Show WebSocket connection state

### Phase 2: Medium Effort, High Impact

5. **Create Notification Preferences page** - Backend APIs exist, need UI
6. **Build Debug Tools admin panel** - Expose existing debug endpoints
7. **Implement optimistic updates** - Add to all mutations
8. **Create WebSocket-to-cache bridge** - Centralize real-time updates

### Phase 3: Higher Effort, High Value

9. **Build System Monitoring dashboard** - GPU stats, worker queues, circuit breakers
10. **Create Data Management page** - Export scheduling, backup controls
11. **Implement zone editor** - Visual zone configuration
12. **Add model management UI** - AI model status and configuration

### Phase 4: Cleanup

13. **Remove or integrate AuditTableInfinite** - Resolve orphaned component
14. **Audit and remove unused hooks** - Clean up codebase
15. **Standardize loading patterns** - Create consistent UX

---

## Appendix A: Research Agent Summary

| Agent ID | Focus Area           | Key Findings                  |
| -------- | -------------------- | ----------------------------- |
| a4c82f4  | Backend API Routes   | 200+ endpoints documented     |
| a62df34  | Frontend API Client  | 120+ REST endpoints mapped    |
| a9d8527  | Backend Services     | 124+ services catalogued      |
| a65b59c  | UI Components        | 249+ components documented    |
| a6f96b7  | UI Component Usage   | 1 orphaned component found    |
| a41c2df  | Backend WebSocket    | 42+ event types documented    |
| a01c8d7  | Frontend WebSocket   | 5 unconsumed event types      |
| ab3cec8  | Database Models      | 36 models, 10+ underexposed   |
| a34c608  | Frontend Data Types  | Types comprehensive           |
| aa66faf  | Backend Config       | 12 unexposed categories       |
| a9b6ecf  | Frontend Settings UI | 4 missing UI sections         |
| a1f1f48  | Custom Hooks         | 18 underutilized hooks        |
| ac7da4e  | Backend Middleware   | Well-maintained utilities     |
| a80bf75  | Linear Closed Tasks  | Features verified operational |
| a4e9306  | Integration Patterns | 7 pattern issues identified   |

---

## Appendix B: Linear Epic Structure

The following epic and task structure is recommended for addressing these gaps:

```
Epic: Integration Gaps Resolution
├── Phase 1: Quick Wins
│   ├── NEM-XXX: Mount SeverityThresholds component in Settings
│   ├── NEM-XXX: Add WebSocket handlers for unconsumed events
│   ├── NEM-XXX: Integrate infinite scroll audit logs
│   └── NEM-XXX: Add WebSocket connection status indicator
├── Phase 2: Medium Effort
│   ├── NEM-XXX: Create Notification Preferences page
│   ├── NEM-XXX: Build Debug Tools admin panel
│   ├── NEM-XXX: Implement optimistic updates for mutations
│   └── NEM-XXX: Create WebSocket-to-cache bridge
├── Phase 3: Higher Effort
│   ├── NEM-XXX: Build System Monitoring dashboard
│   ├── NEM-XXX: Create Data Management page
│   ├── NEM-XXX: Implement visual zone editor
│   └── NEM-XXX: Add AI model management UI
└── Phase 4: Cleanup
    ├── NEM-XXX: Resolve AuditTableInfinite orphaned component
    ├── NEM-XXX: Audit and cleanup unused hooks
    └── NEM-XXX: Standardize loading state patterns
```

---

_Report generated by 15 parallel research agents analyzing the complete codebase._
