# Audit Components Directory

## Purpose

Contains components for viewing, filtering, and analyzing audit logs. Provides a centralized audit log dashboard with statistics, filtering, and detailed log inspection for tracking user actions and system events.

## Files

| File                        | Purpose                                    |
| --------------------------- | ------------------------------------------ |
| `AuditLogPage.tsx`          | Main audit log page assembling all parts   |
| `AuditLogPage.test.tsx`     | Test suite for AuditLogPage                |
| `AuditTable.tsx`            | Paginated table of audit entries           |
| `AuditTable.test.tsx`       | Test suite for AuditTable                  |
| `AuditFilters.tsx`          | Filtering controls for audit logs          |
| `AuditFilters.test.tsx`     | Test suite for AuditFilters                |
| `AuditDetailModal.tsx`      | Full audit entry detail modal              |
| `AuditDetailModal.test.tsx` | Test suite for AuditDetailModal            |
| `AuditStatsCards.tsx`       | Audit statistics summary cards             |
| `AuditStatsCards.test.tsx`  | Test suite for AuditStatsCards             |
| `EventAuditDetail.tsx`      | AI pipeline audit details for single event |
| `EventAuditDetail.test.tsx` | Test suite for EventAuditDetail            |
| `index.ts`                  | Barrel exports                             |

## Key Components

### AuditLogPage.tsx

**Purpose:** Main page component that assembles the complete audit log interface

**Key Features:**

- Displays AuditStatsCards at the top with real-time statistics
- Provides AuditFilters for filtering audit entries
- Shows AuditTable with paginated audit entries
- Opens AuditDetailModal when clicking on a table row
- Fetches data from `/api/audit` and `/api/audit/stats` endpoints
- Uses NVIDIA dark theme styling

**Props:**

```typescript
interface AuditLogPageProps {
  className?: string;
}
```

**State Management:**

- `logs: AuditEntry[]` - Array of audit entries from API
- `totalCount: number` - Total logs matching filters
- `loading: boolean` - Loading state for logs
- `error: string | null` - Error message
- `stats: AuditLogStats | null` - Statistics data
- `statsLoading: boolean` - Loading state for stats
- `queryParams: AuditLogsQueryParams` - Current query parameters
- `selectedLog: AuditEntry | null` - Log entry for detail modal
- `isModalOpen: boolean` - Modal visibility state

**Data Flow:**

```
AuditLogPage
├── AuditStatsCards (auto-fetches stats)
├── AuditFilters (onFilterChange callback)
├── AuditTable (logs data, pagination)
└── AuditDetailModal (selected log details)
```

---

### AuditTable.tsx

**Purpose:** Paginated table displaying audit log entries

**Key Features:**

- Table with columns: Timestamp, Action, Resource, Actor, Status
- Action badges with color coding by type
- Status indicators (success/failure)
- Relative timestamp display
- Click row to open detail modal
- Pagination controls (Previous/Next buttons)
- Page indicator
- Loading spinner, error state, empty state

**Exports:**

```typescript
export interface AuditEntry {
  id: number;
  timestamp: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  actor: string;
  status: 'success' | 'failure';
  ip_address?: string;
  user_agent?: string;
  details?: Record;
}
```

---

### AuditFilters.tsx

**Purpose:** Filtering controls for the audit log dashboard

**Key Features:**

- Collapsible filter panel
- Action dropdown (CREATE, READ, UPDATE, DELETE, etc.)
- Resource type dropdown (camera, event, detection, settings, etc.)
- Actor input field (username/system)
- Status dropdown (all/success/failure)
- Date range filters (start date, end date)
- Clear all filters button
- "Active" badge when filters are applied

**Exports:**

```typescript
export interface AuditFilterParams {
  action?: string;
  resourceType?: string;
  actor?: string;
  status?: 'success' | 'failure';
  startDate?: string;
  endDate?: string;
}
```

---

### AuditDetailModal.tsx

**Purpose:** Full-screen modal displaying complete audit entry details

**Key Features:**

- Headless UI Dialog with backdrop blur and animations
- Action badge with type indicator
- Full audit metadata section:
  - Audit ID
  - Timestamp
  - Action
  - Resource type and ID
  - Actor
  - Status
  - IP address (if applicable)
- User Agent display (if present)
- Additional Details (JSON details field, pretty-printed)
- Keyboard shortcut: Escape to close

---

### AuditStatsCards.tsx

**Purpose:** Dashboard cards displaying audit log statistics

**Key Features:**

- Displays stat cards:
  - Total Actions Today
  - Failures Today (red highlight if > 0)
  - Most Active Actor
  - Most Common Action
- Auto-refresh capability
- Loading and error states
- Color-coded indicators

## Important Patterns

### Filter State Flow

```
AuditFilters (local state)
    -> onFilterChange callback
    -> AuditLogPage updates queryParams
    -> useEffect triggers API call
    -> AuditTable re-renders
```

### Pagination Pattern

Same as LogsDashboard:

- Server-side pagination with limit/offset
- Reset to offset 0 when filters change
- Previous/Next buttons with disabled states
- Page counter in the middle

### Action Color Coding

| Action  | Color  |
| ------- | ------ |
| CREATE  | green  |
| READ    | blue   |
| UPDATE  | yellow |
| DELETE  | red    |
| LOGIN   | purple |
| LOGOUT  | gray   |
| (other) | gray   |

### Status Indicators

| Status  | Color | Icon        |
| ------- | ----- | ----------- |
| success | green | CheckCircle |
| failure | red   | XCircle     |

## Styling Conventions

### AuditLogPage

- Page background: inherits from Layout
- Section margins: mb-6 between sections
- Header: text-3xl font-bold text-white

### AuditFilters

- Panel: bg-[#1F1F1F], border-gray-800
- Inputs: bg-[#1A1A1A], border-gray-700, focus:border-[#76B900]
- Active badge: bg-[#76B900], text-black

### AuditTable

- Container: bg-[#1F1F1F], border-gray-800
- Header row: bg-[#1A1A1A]
- Row dividers: divide-gray-800
- Hover: hover:bg-[#76B900]/5 (subtle green tint)
- Actor column: font-mono text-[#76B900]

### AuditDetailModal

- Modal: bg-[#1A1A1A], border-gray-800, shadow-2xl
- Max width: 1024px (4xl)
- Max height: calc(100vh-200px)
- JSON display: bg-[#76B900]/10, font-mono

### EventAuditDetail.tsx

**Purpose:** Drill-down component showing AI pipeline audit details for a single event

**Key Features:**

- Displays quality scores (1-5 scale) with visual bar indicators
- Shows model contributions checklist (YOLO26, Florence, CLIP, Violence, Clothing, Vehicle, Pet, Weather, Quality, Zones, Baseline, Cross-cam)
- Self-critique section from LLM evaluation
- Improvement suggestions categorized by type
- "Run Evaluation" / "Re-run Evaluation" action button
- Consistency check with risk score comparison
- Prompt length and token estimates
- Enrichment utilization percentage
- Loading and error states

**Props:**

```typescript
interface EventAuditDetailProps {
  /** The event ID to fetch audit details for */
  eventId: number;
}
```

**Quality Scores Displayed:**

- Context Usage (1-5)
- Reasoning Coherence (1-5)
- Risk Justification (1-5)
- Consistency (1-5)
- Overall (1-5, highlighted)

**Improvement Categories:**

- Missing Context
- Confusing Sections
- Unused Data
- Format Suggestions
- Model Gaps

**API Integration:**

- `fetchEventAudit(eventId)` - GET /api/audit/events/{id}
- `triggerEvaluation(eventId, force)` - POST /api/audit/events/{id}/evaluate

---

## Testing

Test coverage:

- `AuditLogPage.test.tsx` - Assembly, data fetching, modal integration, error handling
- `AuditTable.test.tsx` - Table rendering, pagination, action badges
- `AuditFilters.test.tsx` - Filter controls, clear functionality
- `AuditDetailModal.test.tsx` - Modal lifecycle, content display
- `AuditStatsCards.test.tsx` - Stats display, loading states
- `EventAuditDetail.test.tsx` - Quality scores, model contributions, evaluation actions

## Entry Points

**Start here:** `AuditLogPage.tsx` - Understand overall page structure
**Then explore:** `AuditFilters.tsx` - See filter patterns
**Next:** `AuditTable.tsx` - Learn table patterns with action badges
**Deep dive:** `AuditDetailModal.tsx` - See modal patterns for audit details

## Dependencies

- `@headlessui/react` - Dialog, Transition for modal
- `lucide-react` - Icons (Calendar, Filter, Search, X, ChevronLeft, ChevronRight, Clock, CheckCircle, XCircle, Activity, User, FileText)
- `clsx` - Conditional class composition
- `react` - useState, useEffect, useCallback
- `../../services/api` - fetchAuditLogs, fetchAuditStats, AuditLogsQueryParams, AuditLogStats types

## API Endpoints Used

- `GET /api/audit` - Fetch paginated audit logs with filters
- `GET /api/audit/stats` - Fetch audit log statistics

## Future Enhancements

- Real-time audit log streaming via WebSocket
- Audit log export to file (JSON/CSV)
- Action aggregation charts
- Actor activity timeline
- IP address geolocation
- Audit log retention indicator
- Bulk operations support
