# Frontend Routing and Navigation Analysis

## Executive Summary

The frontend has **27 routes** organized into **4 navigation groups**. Several backend features lack dedicated pages, and the mobile navigation only exposes 4 of 27 routes.

## Current Routing Structure

### Navigation Groups

| Group      | Routes | Purpose                                                                                |
| ---------- | ------ | -------------------------------------------------------------------------------------- |
| MONITORING | 4      | Dashboard, Timeline, Entities, Alerts                                                  |
| ANALYTICS  | 6      | Analytics, Video Analytics, AI Audit, AI Performance, AI Services, Profiling           |
| OPERATIONS | 7      | Jobs, Pipeline, Dashboard, GPU Metrics, Request Profiling, Tracing, Logs               |
| ADMIN      | 6      | Audit Log, Data Management, Scheduled Reports, Webhooks, Trash, Settings, GPU Settings |

### Complete Route Table

| Path                        | Component                   | Group          | Status    |
| --------------------------- | --------------------------- | -------------- | --------- |
| `/`                         | DashboardPage               | MONITORING     | ✅ Active |
| `/timeline`                 | EventTimeline               | MONITORING     | ✅ Active |
| `/entities`                 | EntitiesPage                | MONITORING     | ✅ Active |
| `/alerts`                   | AlertsPage                  | MONITORING     | ✅ Active |
| `/analytics`                | AnalyticsPage               | ANALYTICS      | ✅ Active |
| `/video-analytics`          | VideoAnalyticsPage          | ANALYTICS      | ✅ Active |
| `/ai-audit`                 | AIAuditPage                 | ANALYTICS      | ✅ Active |
| `/ai-performance`           | AIPerformancePage           | ANALYTICS      | ✅ Active |
| `/ai-services`              | AIServicesPage              | ANALYTICS      | ✅ Active |
| `/profiling`                | ProfilingPage               | ANALYTICS      | ✅ Active |
| `/jobs`                     | JobsPage                    | OPERATIONS     | ✅ Active |
| `/pipeline`                 | PipelinePage                | OPERATIONS     | ✅ Active |
| `/pipeline/dashboard`       | PipelineDashboard           | OPERATIONS     | ✅ Active |
| `/gpu-metrics`              | GpuMetricsPage              | OPERATIONS     | ✅ Active |
| `/request-profiling`        | RequestProfilingPage        | OPERATIONS     | ✅ Active |
| `/tracing`                  | TracingPage                 | OPERATIONS     | ✅ Active |
| `/logs`                     | LogsPage                    | OPERATIONS     | ✅ Active |
| `/audit-log`                | AuditLogPage                | ADMIN          | ✅ Active |
| `/data-management`          | DataManagementPage          | ADMIN          | ✅ Active |
| `/scheduled-reports`        | ScheduledReportsPage        | ADMIN          | ✅ Active |
| `/webhooks`                 | WebhooksPage                | ADMIN          | ✅ Active |
| `/trash`                    | TrashPage                   | ADMIN          | ✅ Active |
| `/settings`                 | SettingsPage                | ADMIN          | ✅ Active |
| `/gpu-settings`             | GpuSettingsPage             | ADMIN          | ✅ Active |
| `/zones`                    | ZonesPage                   | (Settings sub) | ✅ Active |
| `/notification-preferences` | NotificationPreferencesPage | (Settings sub) | ✅ Active |
| `/developer-tools`          | DeveloperToolsPage          | (Debug only)   | ✅ Active |

## Navigation Implementation

### Desktop Sidebar

- Collapsible sidebar with expandable groups
- State persisted in localStorage
- Icons for each route
- Group expand/collapse animation

### Mobile Bottom Navigation

**Only 4 tabs exposed:**

1. Home (Dashboard)
2. Timeline
3. Alerts
4. Settings

**Missing from mobile:**

- Entities
- Analytics (6 routes)
- Operations (7 routes)
- Most Admin routes

## Missing Pages (Backend Features Without UI)

### HIGH Priority

| Feature                   | Backend Support       | Recommended Route                |
| ------------------------- | --------------------- | -------------------------------- |
| Household Members         | Full CRUD, embeddings | `/household`                     |
| License Plate Recognition | Statistics, search    | `/plate-reads`                   |
| Face Recognition          | Known persons, events | `/face-recognition`              |
| ONVIF Camera Control      | PTZ, presets          | `/cameras/onvif` or Settings tab |

### MEDIUM Priority

| Feature                | Backend Support   | Recommended Route                |
| ---------------------- | ----------------- | -------------------------------- |
| Heatmaps               | Activity density  | `/heatmaps`                      |
| Activity Baselines     | Per-camera tuning | `/baselines` or Settings tab     |
| Feedback Management    | User corrections  | `/feedback`                      |
| Scene Change Detection | Alerts, history   | `/scene-changes` or Settings tab |

### LOW Priority

| Feature             | Backend Support | Recommended Route     |
| ------------------- | --------------- | --------------------- |
| Track Visualization | Motion paths    | Part of entity detail |
| Dwell Statistics    | Zone analytics  | Part of zones page    |

## Recommended Navigation Restructuring

### Add New Group: PEOPLE & OBJECTS

```
PEOPLE & OBJECTS (New)
├── Household Members (/household)
├── License Plates (/plate-reads)
└── Face Recognition (/face-recognition)
```

**Benefits:**

- Reduces ANALYTICS overcrowding (currently 6 items)
- Logical feature grouping
- Better discoverability

### Updated Structure

| Group            | Routes      |
| ---------------- | ----------- |
| MONITORING       | 4           |
| PEOPLE & OBJECTS | 3 (new)     |
| ANALYTICS        | 5 (reduced) |
| OPERATIONS       | 7           |
| ADMIN            | 6           |

## Key Issues

### 1. No Catch-All 404 Route

```typescript
// Missing:
<Route path="*" element={<NotFoundPage />} />
```

**Impact:** Invalid URLs show blank page instead of helpful 404

### 2. No Route Guards

Currently no protection for routes. Would be needed for multi-user deployment.

### 3. Routes Hard-Coded in Components

Routes are defined in multiple places instead of centralized config.

**Recommendation:** Create `routes.ts` config file

```typescript
export const routes = {
  dashboard: '/',
  timeline: '/timeline',
  entities: '/entities',
  // ...
} as const;
```

### 4. Mobile Navigation Limited

Only 4 of 27 routes accessible via mobile bottom nav.

**Recommendation:** Add "More" menu or drawer for additional routes

### 5. Settings Could Use Nested Sub-Routes

Currently Settings is a single page with tabs. Could be:

- `/settings/cameras`
- `/settings/notifications`
- `/settings/processing`
- etc.

**Benefits:**

- Deep linkable
- Browser history works with tabs
- Cleaner URL structure

## Router Technology

- **React Router 7.11.0**
- **Lazy-loaded components** (React.lazy)
- **Code splitting** per route
- **Suspense boundaries** for loading states

## Recommendations

### Immediate

1. **Add 404 route**
2. **Create `/household` page**
3. **Create `/face-recognition` page**

### Short-term

1. **Restructure navigation groups**
2. **Add "PEOPLE & OBJECTS" group**
3. **Improve mobile navigation**

### Medium-term

1. **Centralize route config**
2. **Add nested Settings routes**
3. **Create route guards (if multi-user needed)**

### Long-term

1. **Add `/plate-reads` page**
2. **Add `/heatmaps` page**
3. **Add ONVIF controls to camera settings**
