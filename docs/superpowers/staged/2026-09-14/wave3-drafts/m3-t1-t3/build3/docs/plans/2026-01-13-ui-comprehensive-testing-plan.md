# Comprehensive UI Testing Plan

**Created:** 2026-01-13
**Objective:** Comprehensive UI audit of all 12 pages using browser automation with screenshots to find bugs, verify completed Linear tasks, and identify E2E test gaps.

## Overview

### Goals

1. **Bug hunting** - Exploratory testing to find bugs, edge cases, and UX issues
2. **Feature verification** - Verify Linear tasks marked "Done" actually work
3. **E2E coverage gaps** - Identify missing automated test coverage

### Execution Method

- Browser automation with screenshots (using Browser tool)
- Create Linear tasks for each bug found
- Each bug task includes action item: "Write E2E test to prevent regression"

### Environment

- **URL:** `http://localhost:5173`
- **Backend:** `http://localhost:8000`
- **Prerequisites:** Containers running via `docker-compose`

---

## Page Testing Order

| Order | Route        | Page              | Complexity                              |
| ----- | ------------ | ----------------- | --------------------------------------- |
| 1     | `/`          | Dashboard         | High - real-time, WebSocket, GPU stats  |
| 2     | `/timeline`  | Event Timeline    | High - infinite scroll, modals, video   |
| 3     | `/settings`  | Settings          | High - 12 tabs, forms, CRUD operations  |
| 4     | `/system`    | System Monitoring | Medium - multiple panels, health checks |
| 5     | `/analytics` | Analytics         | Medium - charts, heatmaps, filters      |
| 6     | `/ai`        | AI Performance    | Medium - metrics, model status          |
| 7     | `/ai-audit`  | AI Audit          | Medium - prompt playground, A/B tests   |
| 8     | `/alerts`    | Alerts            | Medium - CRUD, filtering                |
| 9     | `/entities`  | Entities          | Medium - entity cards, modals           |
| 10    | `/logs`      | Logs              | Low - table, filters, pagination        |
| 11    | `/audit`     | Audit Log         | Low - table, filters                    |
| 12    | `/trash`     | Trash             | Low - recovery actions                  |

---

## Page 1: Dashboard (`/`)

### Initial Load Tests

- [ ] Page loads without console errors
- [ ] WebSocket connection established (check status indicator)
- [ ] Camera grid renders with feed thumbnails or placeholder states
- [ ] GPU stats panel shows metrics (or graceful "unavailable" state)
- [ ] Activity feed displays recent events (or empty state)
- [ ] Stats row shows risk metrics with sparklines
- [ ] Pipeline queues visualization renders
- [ ] Pipeline telemetry panel displays metrics

### Interactive Tests

- [ ] Click camera tile → opens camera detail/modal
- [ ] Click event in activity feed → navigates to event detail
- [ ] Dashboard config modal opens and saves preferences
- [ ] Resize browser → responsive layout adapts correctly
- [ ] WebSocket reconnection works after network interruption

### Real-time Updates

- [ ] New events appear in activity feed without refresh
- [ ] GPU stats update periodically
- [ ] Pipeline queue counts reflect current state

### Error States

- [ ] Backend offline → shows service status alert
- [ ] WebSocket disconnected → shows reconnecting indicator
- [ ] API errors → displays error boundaries, not white screen

### Linear Tasks to Verify

- NEM-139: Frontend Dashboard - React UI
- NEM-1734: Frontend Design Polish Epic

---

## Page 2: Event Timeline (`/timeline`)

### Initial Load

- [ ] Events list loads with pagination/infinite scroll
- [ ] Event cards show thumbnail, risk badge, timestamp, camera name
- [ ] Filters panel renders (date range, camera, risk level, object type)
- [ ] Empty state displays when no events match filters

### Interactive Tests

- [ ] Click event card → EventDetailModal opens
- [ ] Modal shows video player, detection overlays, enrichment data
- [ ] Thumbnail strip navigation works
- [ ] Feedback panel allows rating event accuracy
- [ ] Export panel generates downloadable data
- [ ] Entity tracking panel shows REID matches (if available)
- [ ] Scroll triggers infinite scroll loading
- [ ] Filter changes update event list
- [ ] Mobile swipe gestures work on event cards

### Linear Tasks to Verify

- NEM-610: Video player component
- NEM-2386: Export progress UI component

---

## Page 3: Settings (`/settings`)

### Tab Navigation

- [ ] All 12 settings tabs render and switch correctly
- [ ] URL updates with tab state (deep linking works)

### Cameras Tab

- [ ] Camera list displays all configured cameras
- [ ] Add camera form validates input
- [ ] Edit camera saves changes
- [ ] Delete camera with confirmation

### AI Models Tab

- [ ] Model status cards show loaded/unloaded state
- [ ] GPU memory allocation visible
- [ ] Model Zoo section displays available models

### Processing Tab

- [ ] Batch window size configurable
- [ ] Idle timeout configurable
- [ ] Retention policy settings save

### Storage Tab

- [ ] Storage stats display (used/available)
- [ ] Cleanup preview panel shows what would be deleted
- [ ] Cleanup action executes with confirmation

### Notifications Tab

- [ ] Desktop notification toggle works
- [ ] Audio notification toggle works
- [ ] Push notification subscription

### Alert Rules Tab

- [ ] Alert rules list displays
- [ ] Create/edit/delete rules
- [ ] Quiet hours scheduler works

### DLQ Monitor Tab

- [ ] Dead letter queue items display
- [ ] Retry/dismiss actions work

### Calibration Tab

- [ ] Calibration panel renders
- [ ] Risk sensitivity slider adjusts threshold

### Linear Tasks to Verify

- NEM-2355: CalibrationPanel component
- NEM-1969: Rate limit indicator UI

---

## Page 4: System Monitoring (`/system`)

### Panel Tests

- [ ] Worker status panel shows background job workers
- [ ] AI Models panel displays model health (verify NEM-2456 fix: should NOT show "0/18 loaded" when healthy)
- [ ] Containers panel shows running container status
- [ ] Databases panel shows PostgreSQL/Redis health
- [ ] Host system panel shows CPU, memory, disk metrics
- [ ] Performance alerts panel shows threshold violations
- [ ] Time range selector filters metrics display
- [ ] Circuit breaker status panel shows breaker states

### Real-time Updates

- [ ] Metrics refresh on configured interval
- [ ] Status changes reflect without manual refresh

### Linear Tasks to Verify

- NEM-819: DatabasesPanel component
- NEM-929: HostSystemPanel component
- NEM-930: ContainersPanel component
- NEM-817: PerformanceAlerts component
- NEM-818: AiModelsPanel component
- NEM-933: SystemMonitoringPage enhancements
- NEM-1048: Circuit Breaker status panel
- NEM-2456: AI Models "0/18 loaded" fix

---

## Page 5: Analytics (`/analytics`)

### Chart Tests

- [ ] Activity heatmap renders by time/camera
- [ ] Detection class frequency chart displays
- [ ] Pipeline latency panel shows trends
- [ ] Scene change panel detects transitions
- [ ] Anomaly config panel allows threshold adjustment

### Interactive Tests

- [ ] Time range selection updates all charts
- [ ] Camera filter narrows data scope
- [ ] Hover tooltips show data points
- [ ] Chart legends toggle series visibility

### Linear Tasks to Verify

- NEM-2434: Analytics inconsistent stats fix (Total Events vs High Risk)

---

## Page 6: AI Performance (`/ai`)

### Metrics Display

- [ ] Model status cards show inference latency
- [ ] Model Zoo section displays VRAM allocation
- [ ] Model leaderboard ranks by performance
- [ ] Model contribution chart visualizes detection sources
- [ ] Latency panel shows p50/p95/p99 metrics
- [ ] Insights charts render trends

### Linear Tasks to Verify

- NEM-1147: AIPerformanceSummaryRow integration

---

## Page 7: AI Audit (`/ai-audit`)

### Prompt Playground

- [ ] Prompt input accepts custom prompts
- [ ] Test execution returns AI response
- [ ] Response displays formatted output

### A/B Testing

- [ ] Create A/B test with two prompt variants
- [ ] Stats panel shows comparison metrics
- [ ] Winner selection works

### Batch Audit

- [ ] Batch audit modal opens
- [ ] Progress bar shows audit progress
- [ ] Results table displays audit findings
- [ ] Verify NEM-2473 fix: no HTTP 504 timeout on batch audit

### Linear Tasks to Verify

- NEM-1627: PromptPlayground tests
- NEM-2473: Batch audit 504 timeout fix

---

## Page 8: Alerts (`/alerts`)

### List & Filtering

- [ ] Alert list displays with status badges
- [ ] Filter by status (active, acknowledged, resolved)
- [ ] Filter by severity/risk level
- [ ] Pagination or infinite scroll works

### CRUD Operations

- [ ] Create new alert rule via AlertForm
- [ ] Edit existing alert
- [ ] Delete alert with confirmation
- [ ] Acknowledge alert updates status

### Real-time

- [ ] New alerts appear via WebSocket (NEM-2378 verified)
- [ ] Status changes reflect without refresh

### Linear Tasks to Verify

- NEM-2367: AlertsPage.new routing switch
- NEM-2368: Old AlertsPage removal verified

---

## Page 9: Entities (`/entities`)

### Entity Display

- [ ] Entity cards render with thumbnails
- [ ] Entity type badges display (person, vehicle, etc.)
- [ ] Infinite scroll loads more entities

### Interactive Tests

- [ ] Click entity → EntityDetailModal opens
- [ ] Modal shows entity history/appearances
- [ ] REID match timeline displays
- [ ] Filter by entity type works

---

## Page 10: Logs (`/logs`)

### Table Display

- [ ] Logs table renders with columns (timestamp, level, message)
- [ ] Log level badges color-coded (error=red, warn=yellow, info=blue)
- [ ] Pagination controls work
- [ ] Stats cards show log counts by level

### Filtering

- [ ] Filter by log level
- [ ] Filter by date range
- [ ] Search by message content

### Detail View

- [ ] Click log row → LogDetailModal opens
- [ ] Full log entry with stack trace (if error)

### Linear Tasks to Verify

- NEM-762: LogDetailModal component

---

## Page 11: Audit Log (`/audit`)

### Table Display

- [ ] Audit entries table renders
- [ ] Shows actor, action, resource, timestamp
- [ ] Stats cards summarize audit activity

### Filtering

- [ ] Filter by action type
- [ ] Filter by actor
- [ ] Filter by date range

### Detail View

- [ ] Click entry → AuditDetailModal opens
- [ ] Shows full audit payload/diff

---

## Page 12: Trash (`/trash`)

### Soft-deleted Events

- [ ] Deleted event cards display
- [ ] Shows deletion timestamp and original event info

### Recovery Actions

- [ ] Restore event returns it to timeline
- [ ] Permanent delete with confirmation
- [ ] Bulk actions (if implemented)

---

## Cross-Cutting Concerns

### Navigation & Layout

- [ ] Sidebar navigation works for all 12 routes
- [ ] Active route highlighted in sidebar
- [ ] Header renders with search bar
- [ ] Page transitions animate smoothly (NEM-1785 verified)
- [ ] Browser back/forward navigation works
- [ ] Deep links load correct page state

### Global Search

- [ ] Search bar autocomplete suggests results
- [ ] Search executes and shows results panel
- [ ] Click result navigates to correct location
- [ ] Saved searches persist and recall

### Command Palette (Cmd+K)

- [ ] Opens on keyboard shortcut
- [ ] Lists available actions
- [ ] Executes selected command
- [ ] Shortcuts help modal (?) displays all shortcuts

### Keyboard Shortcuts

- [ ] List navigation with arrow keys
- [ ] Escape closes modals
- [ ] Tab focus order logical

### Responsive Design

- [ ] Desktop (1920px) - full layout
- [ ] Tablet (768px) - collapsed sidebar
- [ ] Mobile (375px) - mobile-optimized layout
- [ ] MobileEventCard renders on small screens

### Error Handling

- [ ] ErrorBoundary catches component crashes
- [ ] ChunkLoadErrorBoundary handles lazy-load failures
- [ ] FeatureErrorBoundary isolates feature failures
- [ ] No white screens - always graceful degradation

### Connection Status

- [ ] WebSocketStatus indicator accurate
- [ ] ServiceStatusAlert banner appears when backend down
- [ ] Offline fallback UI when network unavailable
- [ ] Rate limit indicator shows when throttled (NEM-1969)

### Notifications

- [ ] Toast notifications display and auto-dismiss
- [ ] Desktop notifications trigger (if permitted)
- [ ] Audio notifications play (if enabled)

### PWA Features

- [ ] Install banner appears (if applicable)
- [ ] Service worker caches assets
- [ ] Offline fallback page renders

---

## Execution Instructions

### Agent Protocol

**For each page:**

1. Navigate to the route using Browser tool
2. Wait for initial load, take screenshot
3. Execute each checklist item
4. Take screenshots at key states (success, error, edge cases)
5. Document findings inline

**Screenshot Naming Convention:**

```
{page}-{state}-{timestamp}.png
Examples:
- dashboard-initial-load.png
- settings-cameras-add-form.png
- timeline-event-modal-open.png
```

### Bug Report Format

When a bug is found, create Linear task with:

```markdown
**Title:** bug: {page} - {brief description}

**Description:**

## Summary

{One sentence describing the issue}

## Steps to Reproduce

1. Navigate to {route}
2. {action}
3. {action}
4. Observe: {unexpected behavior}

## Expected Behavior

{What should happen}

## Actual Behavior

{What actually happens}

## Screenshot Evidence

{Attached screenshot}

## Action Items

- [ ] Fix the bug
- [ ] Write E2E test to prevent regression

## Environment

- URL: http://localhost:5173
- Browser: Chromium (Playwright)
```

**Linear Task Settings:**

- Team ID: `998946a2-aa75-491b-a39d-189660131392`
- Priority: 2 (High) for functional bugs, 3 (Medium) for UX issues
- Labels: `bug`, `frontend`, `needs-e2e-test`

---

## Success Criteria

Testing is complete when:

1. All 12 pages visited and screenshotted
2. All checklist items executed
3. All bugs documented as Linear tasks
4. Summary report generated with:
   - Pages tested
   - Bugs found (with Linear task links)
   - Overall health assessment
