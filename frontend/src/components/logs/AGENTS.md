# Logs Components Directory

## Purpose

Contains components for viewing, filtering, and analyzing system logs from both backend services and frontend components. Provides a centralized logging dashboard with statistics, filtering, and detailed log inspection.

## Key Components

### LogsDashboard.tsx

**Purpose:** Main page component that assembles the complete logging interface

**Key Features:**

- Displays LogStatsCards at the top with real-time statistics
- Provides LogFilters for filtering log entries
- Shows LogsTable with paginated log entries
- Opens LogDetailModal when clicking on a log row
- Fetches data from `/api/logs` and `/api/logs/stats` endpoints
- Uses NVIDIA dark theme styling

**Props:**

```typescript
interface LogsDashboardProps {
  className?: string;
}
```

**State Management:**

- `logs: LogEntry[]` - Array of log entries from API
- `totalCount: number` - Total logs matching filters
- `loading: boolean` - Loading state
- `error: string | null` - Error message
- `cameras: Camera[]` - Available cameras for filter dropdown
- `queryParams: LogsQueryParams` - Current query parameters
- `selectedLog: LogEntry | null` - Log entry for detail modal
- `isModalOpen: boolean` - Modal visibility state

**Data Flow:**

```
LogsDashboard
├── LogStatsCards (auto-fetches stats)
├── LogFilters (onFilterChange callback)
├── LogsTable (logs data, pagination)
└── LogDetailModal (selected log details)
```

### LogFilters.tsx

**Purpose:** Filtering controls for the logging dashboard

**Key Features:**

- Collapsible filter panel (matches EventTimeline pattern)
- Log level dropdown (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Component dropdown (predefined list of common components)
- Camera dropdown (dynamically populated)
- Date range filters (start date, end date)
- Search bar for log message text
- Clear all filters button
- "Active" badge when filters are applied

**Props:**

```typescript
interface LogFiltersProps {
  onFilterChange: (filters: LogFilterParams) => void;
  cameras?: Array<{ id: string; name: string }>;
  className?: string;
}

interface LogFilterParams {
  level?: LogLevel;
  component?: string;
  camera?: string;
  startDate?: string;
  endDate?: string;
  search?: string;
}
```

**Predefined Components:**

- frontend
- api
- user_event
- file_watcher
- detector
- aggregator
- risk_analyzer
- event_broadcaster
- gpu_monitor
- cleanup_service

### LogsTable.tsx

**Purpose:** Paginated table displaying log entries

**Key Features:**

- Table with columns: Timestamp, Level, Component, Message
- Level badges with color coding:
  - ERROR/CRITICAL: red
  - WARNING: yellow
  - INFO: blue
  - DEBUG: gray
- Relative timestamp display (Just now, 5m ago, 2h ago, etc.)
- Message truncation with ellipsis
- Click row to open detail modal
- Pagination controls (Previous/Next buttons)
- Page X of Y indicator
- Loading spinner, error state, empty state

**Props:**

```typescript
interface LogsTableProps {
  logs: LogEntry[];
  totalCount: number;
  limit: number;
  offset: number;
  loading?: boolean;
  error?: string | null;
  onRowClick?: (log: LogEntry) => void;
  onPageChange?: (offset: number) => void;
  className?: string;
}

interface LogEntry {
  id: number;
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  component: string;
  message: string;
  camera_id?: string | null;
  event_id?: number | null;
  request_id?: string | null;
  detection_id?: number | null;
  duration_ms?: number | null;
  extra?: Record<string, unknown> | null;
  source: string;
}
```

**Helper Functions:**

- `getLevelBadgeClasses(level)` - Returns color classes for level badge
- `formatTimestamp(timestamp)` - Converts ISO to relative/formatted time
- `truncateMessage(message, maxLength)` - Truncates long messages

### LogDetailModal.tsx

**Purpose:** Full-screen modal displaying complete log entry details

**Key Features:**

- Headless UI Dialog with backdrop blur and animations
- Level badge with icon (Code2, Info, AlertCircle, XCircle)
- Full message display
- Log metadata section:
  - Log ID
  - Component
  - Source
  - Camera ID (if applicable)
  - Event ID (if applicable)
  - Detection ID (if applicable)
  - Request ID (if applicable)
  - Duration (if applicable)
- User Agent display (if present)
- Additional Data (JSON extra field, pretty-printed)
- Keyboard shortcut: Escape to close

**Props:**

```typescript
interface LogDetailModalProps {
  log: LogEntry | null;
  isOpen: boolean;
  onClose: () => void;
}
```

**Level Badge Styling:**

| Level | Background | Text Color | Icon |
|-------|------------|------------|------|
| DEBUG | gray-800 | gray-300 | Code2 |
| INFO | blue-900/30 | blue-400 | Info |
| WARNING | yellow-900/30 | yellow-400 | AlertCircle |
| ERROR | red-900/30 | red-400 | XCircle |
| CRITICAL | red-600 | white | XCircle |

### LogStatsCards.tsx

**Purpose:** Dashboard cards displaying log statistics

**Key Features:**

- Uses Tremor Card and Grid components
- Displays four stat cards:
  - Errors Today (red count if > 0, with "Active" badge)
  - Warnings Today (yellow count if > 0)
  - Total Today (NVIDIA green)
  - Most Active Component (with log count)
- Auto-refreshes every 30 seconds
- Loading and error states
- Icons for each stat (AlertCircle, AlertTriangle, FileText, Activity)

**Props:**

```typescript
interface LogStatsCardsProps {
  className?: string;
}
```

**API Response (LogStats):**

```typescript
interface LogStats {
  errors_today: number;
  warnings_today: number;
  total_today: number;
  top_component: string | null;
  by_component: Record<string, number>;
}
```

## Important Patterns

### Filter State Flow

```
LogFilters (local state)
    -> onFilterChange callback
    -> LogsDashboard updates queryParams
    -> useEffect triggers API call
    -> LogsTable re-renders
```

### Pagination Pattern

Same as EventTimeline:

- Server-side pagination with limit/offset
- Reset to offset 0 when filters change
- Previous/Next buttons with disabled states
- Page counter in the middle

### Level Color Coding

Consistent color scheme across components:

- ERROR/CRITICAL: Red (bg-red-500/10, text-red-400)
- WARNING: Yellow (bg-yellow-500/10, text-yellow-400)
- INFO: Blue (bg-blue-500/10, text-blue-400)
- DEBUG: Gray (bg-gray-500/10, text-gray-400)

### Modal Animation

Same pattern as EventDetailModal:

- Fade in/out backdrop (300ms ease-out)
- Scale + fade modal panel (300ms ease-out)
- Click outside to close
- Escape key to close

### Auto-refresh

LogStatsCards auto-refreshes every 30 seconds:

```typescript
useEffect(() => {
  const interval = setInterval(() => void loadStats(), 30000);
  return () => clearInterval(interval);
}, []);
```

## Styling Conventions

### LogsDashboard

- Page background: inherits from Layout
- Section margins: mb-6 between sections
- Header: text-3xl font-bold text-white

### LogFilters

- Panel: bg-[#1F1F1F], border-gray-800
- Inputs: bg-[#1A1A1A], border-gray-700, focus:border-[#76B900]
- Active badge: bg-[#76B900], text-black

### LogsTable

- Container: bg-[#1F1F1F], border-gray-800
- Header row: bg-[#1A1A1A]
- Row dividers: divide-gray-800
- Hover: hover:bg-[#76B900]/5 (subtle green tint)
- Component column: font-mono text-[#76B900]

### LogDetailModal

- Modal: bg-[#1A1A1A], border-gray-800, shadow-2xl
- Max width: 1024px (4xl)
- Max height: calc(100vh-200px)
- JSON display: bg-[#76B900]/10, font-mono

### LogStatsCards

- Outer card: bg-[#1A1A1A], border-gray-800
- Stat cards: bg-zinc-900, border-gray-700
- Grid: 2 cols (sm) -> 4 cols (lg)

## Testing

Comprehensive test coverage:

- `LogsDashboard.test.tsx` - Assembly, data fetching, modal integration, error handling
- `LogFilters.test.tsx` - Filter controls, callbacks, clear functionality
- `LogsTable.test.tsx` - Table rendering, pagination, row clicks, level badges
- `LogDetailModal.test.tsx` - Modal lifecycle, content display, keyboard shortcuts
- `LogStatsCards.test.tsx` - Stats display, auto-refresh, loading/error states

## Entry Points

**Start here:** `LogsDashboard.tsx` - Understand overall page structure
**Then explore:** `LogFilters.tsx` - See filter patterns matching EventTimeline
**Next:** `LogsTable.tsx` - Learn table patterns with level badges
**Deep dive:** `LogDetailModal.tsx` - See modal patterns for log details
**Finally:** `LogStatsCards.tsx` - Understand stats cards with auto-refresh

## Dependencies

- `@headlessui/react` - Dialog, Transition for modal
- `@tremor/react` - Card, Title, Text, Badge, Grid for stats cards
- `lucide-react` - Icons (Calendar, Filter, Search, X, ChevronLeft, ChevronRight, Clock, Code2, Info, AlertCircle, XCircle, AlertTriangle, FileText, Activity)
- `clsx` - Conditional class composition
- `react` - useState, useEffect, Fragment
- `../../services/api` - fetchLogs, fetchLogStats, fetchCameras, LogsQueryParams, LogStats, Camera types
- `../../services/logger` - LogLevel type

## API Endpoints Used

- `GET /api/logs` - Fetch paginated logs with filters
- `GET /api/logs/stats` - Fetch log statistics

## Future Enhancements

- Real-time log streaming via WebSocket
- Log export to file (JSON/CSV)
- Log level aggregation charts
- Component-specific filtering
- Correlation ID linking (request_id, event_id, detection_id)
- Regex search support
- Timestamp range presets (last hour, today, this week)
- Log retention indicator
- Bulk actions (delete, export selected)
