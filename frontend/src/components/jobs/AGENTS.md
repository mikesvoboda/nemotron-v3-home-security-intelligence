# Jobs Components Directory

## Purpose

Contains React components for the background jobs monitoring page, providing a split-view interface for listing, searching, filtering, and viewing details of background jobs like exports, batch audits, cleanup tasks, and AI re-evaluations. Includes WebSocket-based real-time log streaming and job history timeline visualization.

## Files

| File                           | Purpose                                            |
| ------------------------------ | -------------------------------------------------- |
| `JobsPage.tsx`                 | Main page with split view (list + detail panel)    |
| `JobsPage.test.tsx`            | Test suite for JobsPage                            |
| `JobsList.tsx`                 | Scrollable list of jobs                            |
| `JobsListItem.tsx`             | Individual job item in the list                    |
| `JobsSearchBar.tsx`            | Search and filter controls                         |
| `JobsSearchBar.test.tsx`       | Test suite for JobsSearchBar                       |
| `JobsEmptyState.tsx`           | Empty state when no jobs exist                     |
| `JobDetailPanel.tsx`           | Right panel showing job details                    |
| `JobHeader.tsx`                | Job title, status badge, and progress bar          |
| `JobHeader.test.tsx`           | Test suite for JobHeader                           |
| `JobMetadata.tsx`              | Job timestamps and type information                |
| `JobMetadata.test.tsx`         | Test suite for JobMetadata                         |
| `JobActions.tsx`               | Action buttons (cancel, abort, retry, delete)      |
| `JobActions.test.tsx`          | Test suite for JobActions                          |
| `JobLogsViewer.tsx`            | WebSocket-based real-time log viewer               |
| `JobLogsViewer.test.tsx`       | Test suite for JobLogsViewer                       |
| `JobHistoryTimeline.tsx`       | Collapsible job state transition timeline          |
| `JobHistoryTimeline.test.tsx`  | Test suite for JobHistoryTimeline                  |
| `ConnectionIndicator.tsx`      | WebSocket connection status indicator              |
| `ConnectionIndicator.test.tsx` | Test suite for ConnectionIndicator                 |
| `ConfirmDialog.tsx`            | Confirmation dialog for destructive actions        |
| `ConfirmDialog.test.tsx`       | Test suite for ConfirmDialog                       |
| `StatusDot.tsx`                | Colored dot for job status indication              |
| `StatusDot.test.tsx`           | Test suite for StatusDot                           |
| `TimelineEntry.tsx`            | Single entry in the job history timeline           |
| `TimelineEntry.test.tsx`       | Test suite for TimelineEntry                       |
| `LogLine.tsx`                  | Individual log line with level coloring            |
| `LogLine.test.tsx`             | Test suite for LogLine                             |

## Key Components

### JobsPage.tsx

**Purpose:** Main background jobs monitoring page with split view layout

**Key Features:**

- Split view: job list (left) + detail panel (right)
- URL-persisted search and filter state
- Debounced search input (300ms)
- Status and type dropdown filters
- Auto-refresh with manual refresh button
- Empty state when no jobs exist

**Layout:**

```
+--------------------------------------------------+
|   Jobs                      [Refresh] [Stats]    |
|   Monitor background jobs and their progress     |
+--------------------------------------------------+
|  [Search...]  [Status v] [Type v] [Clear all]    |
|  25 jobs | Filters active                        |
+--------------------------------------------------+
|  Job List (1/3)    |   Job Details (2/3)         |
|  +-------------+   |   +----------------------+  |
|  | Job #142    |   |   | Export #142          |  |
|  | Running 67% |   |   | Status: Running (67%)|  |
|  +-------------+   |   | [=======     ]       |  |
|  | Job #141    |   |   +----------------------+  |
|  | Completed   |   |   | Type: Export         |  |
|  +-------------+   |   | Created: 2 min ago   |  |
|  | ...         |   |   +----------------------+  |
|  +-------------+   |   | [Logs Viewer]        |  |
|                    |   +----------------------+  |
|                    |   | [History Timeline]   |  |
+--------------------------------------------------+
```

**Route:** `/jobs`

---

### JobsList.tsx

**Purpose:** Scrollable list of jobs with selection handling

**Props Interface:**

```typescript
interface JobsListProps {
  jobs: JobResponse[];
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
}
```

---

### JobsListItem.tsx

**Purpose:** Individual job item showing status, type, and progress

**Key Features:**

- Status icon (running spinner, completed check, failed X)
- Progress bar for running jobs
- Time ago display
- Selected state highlighting
- React.memo with custom equality function for performance

**Props Interface:**

```typescript
interface JobsListItemProps {
  job: JobResponse;
  isSelected?: boolean;
  onClick?: (jobId: string) => void;
}
```

**Related:** NEM-3424 - Standardize React.memo usage

---

### JobsSearchBar.tsx

**Purpose:** Search and filter controls for the jobs list

**Key Features:**

- Text search with debounce (handled by parent)
- Status dropdown (All, Pending, Processing, Completed, Failed, Cancelled)
- Type dropdown (All, Export, Batch Audit, Cleanup, Re-evaluation)
- Clear all filters button
- Active filters indicator
- Result count display
- Escape key to clear

**Props Interface:**

```typescript
interface JobsSearchBarProps {
  query: string;
  status?: JobStatusEnum;
  type?: string;
  onSearchChange: (query: string) => void;
  onStatusChange: (status?: JobStatusEnum) => void;
  onTypeChange: (type?: string) => void;
  onClear: () => void;
  isLoading?: boolean;
  totalCount?: number;
  className?: string;
}
```

---

### JobDetailPanel.tsx

**Purpose:** Right panel showing comprehensive job details

**Key Features:**

- JobHeader with status and progress
- JobMetadata with timestamps
- JobActions for lifecycle management
- JobLogsViewer with WebSocket streaming
- JobHistoryTimeline for state transitions

**Props Interface:**

```typescript
interface JobDetailPanelProps {
  job: JobResponse | null;
  isLoading: boolean;
}
```

---

### JobHeader.tsx

**Purpose:** Displays job title, status badge, and progress bar

**Key Features:**

- Job type and ID display
- Color-coded status badge with animated dot
- Progress bar with percentage
- Status-based colors (blue=running, green=completed, red=failed)

**Props Interface:**

```typescript
interface JobHeaderProps {
  job: JobResponse;
}
```

**Related:** NEM-2710

---

### JobMetadata.tsx

**Purpose:** Displays job timestamps and type information

**Key Features:**

- Created, started, completed timestamps
- Relative time with absolute time in parentheses
- Duration calculation for completed jobs
- Error message display with red styling
- Status message display

**Props Interface:**

```typescript
interface JobMetadataProps {
  job: JobResponse;
}
```

**Related:** NEM-2710

---

### JobActions.tsx

**Purpose:** Action buttons based on job status

**Key Features:**

- Status-based actions:
  - Pending: Cancel, Delete
  - Running: Cancel, Abort
  - Completed: Delete
  - Failed: Retry, Delete
  - Cancelled: Retry, Delete
- Confirmation dialogs for destructive actions
- Compact mode with icon-only buttons
- Loading states during mutations

**Props Interface:**

```typescript
interface JobActionsProps {
  job: JobResponse;
  compact?: boolean;
  onSuccess?: (action: JobActionType, response: JobCancelResponse | JobAbortResponse | JobResponse) => void;
  onError?: (action: JobActionType, error: Error) => void;
  onDelete?: () => void;
  onRetry?: (newJob: JobResponse) => void;
}
```

**Related:** NEM-2712

---

### JobLogsViewer.tsx

**Purpose:** Real-time log viewer with WebSocket streaming

**Key Features:**

- WebSocket connection for live logs
- Connection indicator showing status
- Log level filtering (ALL, DEBUG, INFO, WARNING, ERROR)
- Auto-scroll toggle
- Clear logs button
- Monospace font for log readability
- Color-coded log levels

**Props Interface:**

```typescript
interface JobLogsViewerProps {
  jobId: string;
  enabled: boolean;
  maxHeight?: number;
  className?: string;
}
```

**Related:** NEM-2711

---

### JobHistoryTimeline.tsx

**Purpose:** Collapsible timeline of job state transitions

**Key Features:**

- Vertical timeline with status dots
- Transition messages (e.g., "Job created", "Started processing")
- Timestamp display
- Collapsible section with summary badge
- Loading skeleton and error states

**Props Interface:**

```typescript
interface JobHistoryTimelineProps {
  jobId: string;
  defaultOpen?: boolean;
  className?: string;
}
```

---

### ConnectionIndicator.tsx

**Purpose:** Visual indicator for WebSocket connection status

**Key Features:**

- Color-coded dot:
  - Green (pulsing): Connected
  - Yellow: Reconnecting
  - Gray: Disconnected
  - Red: Failed
- Optional label display
- Tooltip with status details
- Retry button when failed
- Size variants (sm, md, lg)

**Props Interface:**

```typescript
interface ConnectionIndicatorProps {
  status: JobLogsConnectionStatus;
  reconnectCount?: number;
  showLabel?: boolean;
  showTooltip?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  onRetry?: () => void;
}
```

**Related:** NEM-2711

---

### ConfirmDialog.tsx

**Purpose:** Confirmation dialog for destructive actions

**Key Features:**

- Customizable title and description
- Variant styling (default, warning, danger)
- Loading state during action
- Cancel and confirm buttons
- Focus trap for accessibility

**Props Interface:**

```typescript
interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  variant?: 'default' | 'warning' | 'danger';
  isLoading?: boolean;
  loadingText?: string;
  onConfirm: () => void;
  onCancel: () => void;
}
```

---

### StatusDot.tsx

**Purpose:** Colored dot indicating job status

**Key Features:**

- Status-based colors:
  - pending/queued: Gray outline
  - processing/running: Blue pulsing
  - completed: Green filled
  - failed: Red filled
  - cancelled: Yellow filled
- Size variants (sm, lg)

**Props Interface:**

```typescript
interface StatusDotProps {
  status: string;
  className?: string;
  size?: 'sm' | 'lg';
}
```

---

### TimelineEntry.tsx

**Purpose:** Single entry in the job history timeline

**Key Features:**

- Status dot for target state
- Formatted timestamp
- Transition message
- Vertical connector line
- Error details display
- Triggered by attribution (optional)

**Props Interface:**

```typescript
interface TimelineEntryProps {
  transition: Transition;
  isLast: boolean;
  showTriggeredBy?: boolean;
  className?: string;
}
```

---

### LogLine.tsx

**Purpose:** Individual log line with level-based coloring

**Key Features:**

- Timestamp display
- Level badge (DEBUG, INFO, WARN, ERROR)
- Message content
- Attempt number for retries
- Context indicator with tooltip
- Memoized for performance

**Props Interface:**

```typescript
interface LogLineProps {
  log: JobLogEntryResponse;
}
```

## Related Hooks

- `useJobsSearchQuery` - Job search with debouncing and filtering
- `useJobLogsWebSocket` - WebSocket connection for log streaming
- `useJobHistoryQuery` - Fetch job state transition history
- `useJobMutations` - Cancel, abort, retry, delete mutations

## Styling

- Dark theme with NVIDIA branding
- Background colors: `#1A1A1A`, `#121212`, `#1F1F1F`
- Primary accent: `#76B900` (NVIDIA Green)
- Status colors:
  - Running: blue-400
  - Completed: green-400
  - Failed: red-400
  - Pending: gray-400
- Log level colors:
  - DEBUG: gray-500
  - INFO: white
  - WARN: yellow-400
  - ERROR: red-400

## API Endpoints Used

- `GET /api/jobs/search` - Search jobs with filters
- `GET /api/jobs/{job_id}` - Get job details
- `POST /api/jobs/{job_id}/cancel` - Cancel job
- `POST /api/jobs/{job_id}/abort` - Force abort job
- `POST /api/jobs/{job_id}/retry` - Retry failed job
- `DELETE /api/jobs/{job_id}` - Delete job
- `GET /api/jobs/{job_id}/history` - Get state transitions
- `WS /ws/jobs/{job_id}/logs` - Log streaming

## Entry Points

**Start here:** `JobsPage.tsx` - Main page component
**Then explore:** `JobDetailPanel.tsx` - Detail panel composition
**Then explore:** `JobLogsViewer.tsx` - Real-time log streaming
**Also see:** `JobHistoryTimeline.tsx` - State transition history
**Also see:** `JobActions.tsx` - Lifecycle management buttons

## Dependencies

- `@tanstack/react-query` - Data fetching and caching
- `date-fns` - Date formatting (formatDistanceToNow)
- `lucide-react` - Various icons
- `clsx` - Conditional class composition
- `react-router-dom` - useSearchParams for URL state
- `../../hooks/useJobsSearchQuery` - Search hook
- `../../hooks/useJobLogsWebSocket` - WebSocket hook
- `../../hooks/useJobHistoryQuery` - History hook
- `../../hooks/useJobMutations` - Mutation hooks
- `../../services/api` - API client
- `../system/CollapsibleSection` - Collapsible wrapper
- `../common/SafeErrorMessage` - Error display
