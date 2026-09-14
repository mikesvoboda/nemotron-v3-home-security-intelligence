# Backend-Frontend Gap Analysis Report

**Date:** 2026-01-17
**Purpose:** Identify half-baked backend features and endpoints not consumed by frontend

---

## Executive Summary

| Metric                  | Value                    |
| ----------------------- | ------------------------ |
| Total backend endpoints | 164                      |
| Used by frontend        | 104 (63.4%)              |
| **Unused by frontend**  | **60 (36.6%)**           |
| Half-baked backend code | 0 critical, 1 minor TODO |

**Key finding:** The backend is well-implemented with excellent code quality, but over 1/3 of endpoints have no frontend consumer. The gaps fall into three categories: duplicate routes that need consolidation, intentionally dev-only endpoints, and genuine feature gaps where frontend work is needed.

---

## Methodology

Two parallel research agents audited the codebase:

1. **Backend Completeness Audit** - Scanned all 28 route files (22,545 lines) for:

   - `NotImplementedError`, empty functions, stub returns
   - TODO/FIXME comments
   - Missing database commits, exception swallowing
   - Missing input validation

2. **Frontend API Usage Mapping** - Traced all API calls through:
   - `frontend/src/services/api.ts` (~170 functions)
   - `frontend/src/services/aiAuditApi.ts` (15 endpoints)
   - `frontend/src/services/promptManagementApi.ts` (8 endpoints - unused)
   - All hooks and components

---

## Findings by Severity

### CRITICAL - Duplicate/Conflicting Routes (16 endpoints)

These route files provide overlapping functionality. One should be consolidated or removed.

#### 1. Prompt Management Duplication

| Route File                       | Endpoints | Frontend Usage             |
| -------------------------------- | --------- | -------------------------- |
| `prompt_management.py`           | 8         | **0% - completely unused** |
| `ai_audit.py` (prompt endpoints) | 19        | 68% used                   |

**Details:**

- `prompt_management.py` exposes `/api/prompt-management/*`
- `ai_audit.py` exposes `/api/ai-audit/prompts/*`
- Frontend service `promptManagementApi.ts` exists but is never imported
- Frontend only uses `aiAuditApi.ts`

**Endpoints in `prompt_management.py` (all unused):**

```
GET    /api/prompt-management/templates
GET    /api/prompt-management/templates/{template_id}
POST   /api/prompt-management/templates
PUT    /api/prompt-management/templates/{template_id}
DELETE /api/prompt-management/templates/{template_id}
GET    /api/prompt-management/active
POST   /api/prompt-management/activate/{template_id}
GET    /api/prompt-management/history
```

#### 2. Notification Preferences Duplication

| Route File                    | Endpoints | Frontend Usage             |
| ----------------------------- | --------- | -------------------------- |
| `notification_preferences.py` | 8         | **0% - completely unused** |
| `notification.py`             | 2         | 100% used                  |

**Details:**

- `notification_preferences.py` exposes `/api/notification-preferences/*`
- `notification.py` exposes `/api/notifications/*`
- Unclear if these serve different purposes or are redundant

**Endpoints in `notification_preferences.py` (all unused):**

```
GET    /api/notification-preferences
PUT    /api/notification-preferences
GET    /api/notification-preferences/channels
PUT    /api/notification-preferences/channels/{channel}
GET    /api/notification-preferences/schedules
POST   /api/notification-preferences/schedules
PUT    /api/notification-preferences/schedules/{schedule_id}
DELETE /api/notification-preferences/schedules/{schedule_id}
```

---

### MODERATE - Completely Unused Route Files (34 endpoints)

These route files have 0% frontend coverage. Decision needed: implement frontend UI or remove backend.

#### 1. `admin.py` (5 endpoints) - Dev/Testing Tools

```
POST /api/admin/seed/cameras
POST /api/admin/seed/events
POST /api/admin/seed/pipeline-latency
DELETE /api/admin/cleanup/events
DELETE /api/admin/cleanup/all
```

**Assessment:** Likely intentional dev-only endpoints for seeding test data. Should remain but may need access control in production.

#### 2. `analytics.py` (4 endpoints) - Analytics Dashboard

```
GET /api/analytics/camera-uptime
GET /api/analytics/detection-trends
GET /api/analytics/risk-distribution
GET /api/analytics/risk-history
```

**Assessment:** These power an analytics dashboard that doesn't exist in frontend yet. **Likely a feature gap.**

#### 3. `debug.py` (14 endpoints) - Development Tools

```
GET    /api/debug/profile
POST   /api/debug/profile/start
POST   /api/debug/profile/stop
GET    /api/debug/recordings
GET    /api/debug/recordings/{recording_id}
POST   /api/debug/recordings/{recording_id}/play
POST   /api/debug/recordings/{recording_id}/stop
DELETE /api/debug/recordings/{recording_id}
GET    /api/debug/memory
GET    /api/debug/connections
GET    /api/debug/queries
POST   /api/debug/queries/explain
GET    /api/debug/cache
DELETE /api/debug/cache
```

**Assessment:** Development and debugging tools. Should remain but only accessible in dev mode.

#### 4. `media.py` (4 endpoints) - Media Serving

```
GET /api/media/images/{path}
GET /api/media/videos/{path}
GET /api/media/thumbnails/{path}
GET /api/media/stream/{path}
```

**Assessment:** May be handled by nginx/CDN directly rather than through API. Verify if these are used by frontend via direct URLs.

#### 5. `metrics.py` (1 endpoint) - Prometheus Metrics

```
GET /api/metrics/metrics
```

**Assessment:** Prometheus scrape endpoint. Not intended for frontend consumption.

#### 6. `queues.py` (1 endpoint) - Queue Monitoring

```
GET /api/queues/status
```

**Assessment:** Queue monitoring for DevOps. **Could be useful in a system status dashboard.**

#### 7. `rum.py` (1 endpoint) - Real User Monitoring

```
POST /api/rum/events
```

**Assessment:** RUM SDK may call this directly without going through api.ts service. Verify frontend RUM integration.

#### 8. `services.py` (4 endpoints) - Service Lifecycle

```
GET    /api/services/status
POST   /api/services/{service}/restart
POST   /api/services/{service}/stop
POST   /api/services/{service}/start
```

**Assessment:** Service management for DevOps. **Could be useful in admin panel.**

---

### MODERATE - Partially Used Routes (27 endpoints unused)

These routes have some frontend coverage but significant gaps.

#### 1. `jobs.py` - 23% coverage (3/13 used)

**Used:**

```
GET /api/jobs                    # List jobs
GET /api/jobs/{job_id}           # Get job details
GET /api/jobs/{job_id}/progress  # Get job progress
```

**Unused:**

```
GET    /api/jobs/search           # Search jobs
GET    /api/jobs/stats            # Job statistics
GET    /api/jobs/{job_id}/history # Job state history
GET    /api/jobs/{job_id}/logs    # Job logs
POST   /api/jobs/{job_id}/cancel  # Cancel job
POST   /api/jobs/{job_id}/abort   # Abort job
POST   /api/jobs/{job_id}/retry   # Retry failed job
DELETE /api/jobs/{job_id}         # Delete job
POST   /api/jobs/bulk/cancel      # Bulk cancel
POST   /api/jobs/bulk/delete      # Bulk delete
```

**Assessment:** Job management UI is minimal. **Frontend feature gap** for full job lifecycle management.

#### 2. `logs.py` - 25% coverage (1/4 used)

**Used:**

```
GET /api/logs  # List logs with pagination
```

**Unused:**

```
GET  /api/logs/{log_id}     # Get individual log entry
GET  /api/logs/search       # Search logs
POST /api/logs/frontend     # Frontend error logging
```

**Assessment:** Frontend error logging endpoint exists but isn't wired up. **Integration gap.**

#### 3. `cameras.py` - 67% coverage (10/15 used)

**Unused:**

```
GET    /api/cameras/deleted              # List soft-deleted cameras
POST   /api/cameras/{camera_id}/restore  # Restore deleted camera
GET    /api/cameras/{camera_id}/baseline-anomalies  # Baseline anomalies
POST   /api/cameras/validate-path        # Validate camera path
GET    /api/cameras/{camera_id}/recordings  # Camera recordings
```

**Assessment:** Deleted camera management and recordings not exposed in UI. **Minor feature gap.**

#### 4. `ai_audit.py` - 68% coverage (13/19 used)

**Unused:**

```
POST /api/ai-audit/events/{event_id}/evaluate  # Trigger re-evaluation
GET  /api/ai-audit/prompt-config/{model}       # Get DB prompt config
PUT  /api/ai-audit/prompt-config/{model}       # Update DB prompt config
POST /api/ai-audit/batch/evaluate              # Batch evaluation
GET  /api/ai-audit/batch/{batch_id}/status     # Batch status
GET  /api/ai-audit/batch/{batch_id}/results    # Batch results
```

**Assessment:** Batch evaluation and database prompt config not exposed. **Feature gap for power users.**

#### 5. `detections.py` - 77% coverage (10/13 used)

**Unused:**

```
POST   /api/detections/bulk        # Bulk create detections
PATCH  /api/detections/bulk        # Bulk update detections
DELETE /api/detections/bulk        # Bulk delete detections
```

**Assessment:** Bulk operations not exposed. May not be needed for single-user app.

#### 6. `calibration.py` - 80% coverage (4/5 used)

**Unused:**

```
PATCH /api/calibration/{calibration_id}  # Update calibration
```

**Assessment:** Can create but not update calibrations. **Minor gap.**

#### 7. `events.py` - 88% coverage (15/17 used)

**Unused:**

```
POST   /api/events/bulk   # Bulk create events
DELETE /api/events/bulk   # Bulk delete events
```

**Assessment:** Bulk operations not exposed. May not be needed for single-user app.

---

### MINOR - Polish Items (2 items)

#### 1. TODO Comment

**File:** `backend/api/routes/system.py:4246`
**Code:** `last_used_at=None,  # TODO: Track last usage time`
**Context:** ModelZooStatusItem field defaults to None
**Impact:** Enhancement only, endpoint fully functional

#### 2. Unused System Endpoint

**Endpoint:** `GET /api/system/models`
**Assessment:** May be superseded by model-zoo endpoint

---

## Summary Statistics

### By Severity

| Severity                  | Endpoint Count | Description                            |
| ------------------------- | -------------- | -------------------------------------- |
| Critical                  | 16             | Duplicate routes needing consolidation |
| Moderate (unused routes)  | 34             | Entire route files with 0% coverage    |
| Moderate (partial routes) | 27             | Gaps in partially-used routes          |
| Minor                     | 2              | Polish items                           |
| **Total gaps**            | **79**         |                                        |

### By Route File

| Route File                  | Total | Used | Unused | Coverage |
| --------------------------- | ----- | ---- | ------ | -------- |
| admin.py                    | 5     | 0    | 5      | 0%       |
| ai_audit.py                 | 19    | 13   | 6      | 68%      |
| alerts.py                   | 4     | 4    | 0      | 100%     |
| analytics.py                | 4     | 0    | 4      | 0%       |
| audit.py                    | 2     | 2    | 0      | 100%     |
| calibration.py              | 5     | 4    | 1      | 80%      |
| cameras.py                  | 15    | 10   | 5      | 67%      |
| debug.py                    | 14    | 0    | 14     | 0%       |
| detections.py               | 13    | 10   | 3      | 77%      |
| dlq.py                      | 5     | 5    | 0      | 100%     |
| entities.py                 | 7     | 7    | 0      | 100%     |
| events.py                   | 17    | 15   | 2      | 88%      |
| exports.py                  | 4     | 4    | 0      | 100%     |
| feedback.py                 | 3     | 3    | 0      | 100%     |
| jobs.py                     | 13    | 3    | 10     | 23%      |
| logs.py                     | 4     | 1    | 3      | 25%      |
| media.py                    | 4     | 0    | 4      | 0%       |
| metrics.py                  | 1     | 0    | 1      | 0%       |
| notification.py             | 2     | 2    | 0      | 100%     |
| notification_preferences.py | 8     | 0    | 8      | 0%       |
| prompt_management.py        | 8     | 0    | 8      | 0%       |
| queues.py                   | 1     | 0    | 1      | 0%       |
| rum.py                      | 1     | 0    | 1      | 0%       |
| services.py                 | 4     | 0    | 4      | 0%       |
| system.py                   | 26    | 25   | 1      | 96%      |
| zones.py                    | 5     | 5    | 0      | 100%     |

---

## Recommended Actions

### Immediate (Critical Priority)

1. **Consolidate prompt management routes**

   - Decide: keep `ai_audit.py` prompts OR `prompt_management.py`
   - Delete unused route file and frontend service
   - Update any documentation

2. **Clarify notification preferences**
   - Determine if `notification_preferences.py` serves a different purpose than `notification.py`
   - If duplicate: consolidate
   - If distinct: implement frontend UI

### Short-term (Moderate Priority)

3. **Implement analytics dashboard**

   - `analytics.py` has 4 useful endpoints
   - Design and implement frontend analytics page

4. **Complete jobs management UI**

   - Only 23% of jobs endpoints are used
   - Add job search, logs, cancel/retry functionality

5. **Wire up frontend error logging**

   - `POST /api/logs/frontend` exists but isn't called
   - Integrate with frontend error boundary

6. **Add service status to system health page**
   - `services.py` and `queues.py` endpoints available
   - Useful for monitoring system health

### Long-term (Low Priority)

7. **Evaluate bulk operations need**

   - Bulk endpoints exist for events, detections
   - May be needed as data grows

8. **Camera management enhancements**

   - Deleted cameras, restore, recordings
   - Nice-to-have for data management

9. **Document intentionally unused routes**
   - `admin.py`, `debug.py`, `metrics.py`, `rum.py`
   - Add AGENTS.md notes explaining these are not for frontend

---

## Appendix: Frontend Service Files

### Primary API Client

**File:** `frontend/src/services/api.ts`
**Functions:** ~170 exported
**Coverage:** Primary interface for all API calls

### AI Audit Wrapper

**File:** `frontend/src/services/aiAuditApi.ts`
**Functions:** 15 exported
**Coverage:** Wraps `/api/ai-audit/*` endpoints

### Unused Service

**File:** `frontend/src/services/promptManagementApi.ts`
**Functions:** 8 exported
**Coverage:** 0% - never imported anywhere
**Action:** Delete after consolidating prompt routes

---

## Corrections (Post-Analysis)

During design discussions, several findings were corrected:

| Original Finding                     | Correction                                                             |
| ------------------------------------ | ---------------------------------------------------------------------- |
| `notification_preferences.py` unused | **Fully integrated** - Settings > Notifications tab uses all endpoints |
| `media.py` unused                    | **Used via direct URLs** - img/video src attributes, not api.ts        |
| `rum.py` unused                      | **Wired in main.tsx** - RUM SDK initialized on app startup             |
| `metrics.py` unused                  | **Infrastructure endpoint** - Prometheus scrapes this, not frontend    |

**Revised Gap Count:** ~45 endpoints need work (down from 60)

---

## Linear Tracking

All work items have been created as detailed Linear issues.

### Epics Created

| Epic                                             | Description                                              | Priority |
| ------------------------------------------------ | -------------------------------------------------------- | -------- |
| **Prompt Management Consolidation & UI**         | Consolidate routes, build full management UI             | P1       |
| **Analytics Integration & Date Range System**    | Wire endpoints, create shared hook, migrate 6 components | P1       |
| **Jobs Management Dashboard**                    | New /jobs page with full lifecycle management            | P1       |
| **System Page Enhancements & Debug Integration** | Wire services, add debug mode                            | P2       |
| **Developer Tools Page**                         | New /dev-tools page for profiling, recording, admin      | P2       |
| **Frontend Error Logging Integration**           | Wire error boundaries to backend                         | P2       |

### Task Summary

| Epic                   | Tasks | Key Deliverables                                                          |
| ---------------------- | ----- | ------------------------------------------------------------------------- |
| Prompt Management      | 5     | Route consolidation, full UI, A/B testing, import/export                  |
| Analytics & Date Range | 6     | useDateRangeState hook, 3 endpoint integrations, 6 component migrations   |
| Jobs Management        | 6     | Split view page, search/filter, logs viewer, WebSocket streaming, actions |
| System Page            | 3     | Service wiring, debug toggle, expanded panels                             |
| Developer Tools        | 5     | Page structure, profiling, recording/replay, config inspector, test data  |
| Frontend Error Logging | 2     | Error boundary wiring, global handlers                                    |

**Total: 6 epics, 27 detailed tasks**

### Linear Workspace

- **Workspace:** [nemotron-v3-home-security](https://linear.app/nemotron-v3-home-security)
- **Team:** NEM
- **View all issues:** [Active Issues](https://linear.app/nemotron-v3-home-security/team/NEM/active)

---

## Next Steps

1. Prioritize epics based on MVP requirements
2. Assign tasks to development sessions
3. Follow TDD workflow per project standards
4. Run `./scripts/validate.sh` before closing tasks
