# Jobs Components Directory

## Purpose

Contains React components for the background jobs monitoring page, providing a split-view interface for listing, searching, filtering, and viewing details of background jobs like exports, batch audits, cleanup tasks, and AI re-evaluations.

## Files

| File                     | Purpose                                         |
| ------------------------ | ----------------------------------------------- |
| `JobsPage.tsx`           | Main page with split view (list + detail panel) |
| `JobsPage.test.tsx`      | Test suite for JobsPage                         |
| `JobsList.tsx`           | Scrollable list of jobs                         |
| `JobsListItem.tsx`       | Individual job item in the list                 |
| `JobsSearchBar.tsx`      | Search and filter controls                      |
| `JobsSearchBar.test.tsx` | Test suite for JobsSearchBar                    |
| `JobsEmptyState.tsx`     | Empty state when no jobs exist                  |
| `JobDetailPanel.tsx`     | Right panel showing job details                 |
| `JobHeader.tsx`          | Job title, status badge, and progress bar       |
| `JobHeader.test.tsx`     | Test suite for JobHeader                        |
| `JobMetadata.tsx`        | Job timestamps and type information             |
| `JobMetadata.test.tsx`   | Test suite for JobMetadata                      |
| `ConfirmDialog.tsx`      | Confirmation dialog for destructive actions     |
| `ConfirmDialog.test.tsx` | Test suite for ConfirmDialog                    |
| `StatusDot.tsx`          | Colored dot for job status indication           |
| `StatusDot.test.tsx`     | Test suite for StatusDot                        |

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

## Related Hooks

- `useJobsSearchQuery` - Job search with debouncing and filtering

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

## Entry Points

**Start here:** `JobsPage.tsx` - Main page component
**Then explore:** `JobDetailPanel.tsx` - Detail panel composition

## Dependencies

- `@tanstack/react-query` - Data fetching and caching
- `date-fns` - Date formatting (formatDistanceToNow)
- `lucide-react` - Various icons
- `clsx` - Conditional class composition
- `react-router-dom` - useSearchParams for URL state
- `../../hooks/useJobsSearchQuery` - Search hook
- `../../services/api` - API client
- `../system/CollapsibleSection` - Collapsible wrapper
- `../common/SafeErrorMessage` - Error display
