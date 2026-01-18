# Jobs

The background jobs monitoring page for tracking long-running tasks like exports, cleanup operations, and batch audits.

## What You're Looking At

The Jobs page provides a centralized view for monitoring all background tasks running in the system. It uses a split-view layout with a searchable job list on the left and a detailed panel on the right.

### Page Header

At the top of the page you will find:

- **Title** - "Jobs" with a briefcase icon
- **Description** - "Monitor background jobs and their progress"
- **Refresh Button** - Manually refresh the jobs list (shows spinner when loading)
- **Stats Button** - View job statistics (reserved for future functionality)

### Main Layout

- **Job List** - Scrollable list of all background jobs with status indicators (left panel, 1/3 to 2/5 width)
- **Detail Panel** - Full job information including progress, metadata, and real-time logs (right panel)
- **Search & Filters** - Text search with status and type filtering (above the split view)
- **Empty State** - Shown when no jobs exist, prompting users that jobs appear when they export data or run background tasks

## Key Components

### Job List (Left Panel)

Each job card in the list displays:

- **Status Icon** - Visual indicator of current state
  - Spinning loader (blue) for running jobs
  - Check circle (green) for completed jobs
  - X circle (red) for failed jobs
  - Empty circle (gray) for pending jobs
- **Status Label** - Text status with colored styling
- **Job Type** - Category of job (Export, Cleanup, etc.)
- **Job ID** - Truncated identifier showing last 6 characters
- **Progress Bar** - For running jobs with progress > 0, shows completion percentage with numeric label
- **Time** - Relative timestamp (e.g., "2 minutes ago") based on creation time
- **Message** - Current step or status message (truncated)

Click any job to view its details in the right panel.

### Search & Filter Bar

Located above the job list:

- **Search Input** - Free text search across job types and messages
  - 300ms debounce to prevent excessive API calls
  - Press Escape to clear all filters
  - X button to clear the search input
- **Status Dropdown** - Filter by job status
  - All, Pending, Processing (maps to "running"), Completed, Failed, Cancelled
- **Type Dropdown** - Filter by job type
  - All, Export, Batch Audit, Cleanup, Re-evaluation
- **Clear All Button** - Appears when any filter is active, clears all filters at once
- **Results Count** - Shows total matching jobs (e.g., "5 jobs")
- **Active Filters Indicator** - Green "Filters active" badge when any filter is applied

Filter state is persisted in the URL query parameters (`?q=`, `?status=`, `?type=`) for sharing and bookmarking. Changing filters clears the current job selection.

### Detail Panel (Right Panel)

When a job is selected, displays:

#### Job Header

- **Title** - Job type and ID (e.g., "Export #142") - ID is extracted from job_id if numeric, otherwise shows full ID
- **Status Badge** - Color-coded status with optional animation and percentage
  - Running: Blue with pulse animation, shows "(67%)"
  - Completed: Green
  - Failed: Red
  - Pending: Gray (no progress shown)
- **Progress Bar** - Visual progress from 0-100% (shown for all states except pending, color changes based on status: blue for running, green for completed, red for failed)

#### Job Metadata

- **Type** - Job category with formatted label
- **Created** - When the job was queued (relative + absolute time)
- **Started** - When execution began (or "Not started")
- **Completed** - When finished (for completed/failed jobs)
- **Duration** - Total execution time
- **Status Message** - Current step or operation
- **Error Details** - Red alert box for failed jobs showing error message

#### Job Logs Viewer

Real-time log streaming for active jobs (enabled when job status is "running" or "pending"):

- **Title** - "Job Logs" with file icon
- **Connection Indicator** - WebSocket status with colored dot and label:
  - Green pulsing dot + "Live" when connected
  - Yellow dot + "Reconnecting" (shows attempt count) when reconnecting
  - Gray dot + "Offline" when disconnected
  - Red dot + "Failed" when connection failed
- **Log Count** - Shows filtered/total log count (e.g., "5 of 10 logs")
- **Log Level Filter** - Dropdown to filter by minimum severity:
  - All Levels, Debug, Info, Warning, Error
- **Auto-scroll Toggle** - Button to keep view at latest logs (green when active, shows spinning icon)
- **Clear Button** - Clears all displayed logs (disabled when empty)
- **Log Entries** - Each entry shows:
  - Timestamp (HH:MM:SS format)
  - Level badge with color coding (gray=DEBUG, blue=INFO, yellow=WARNING, red=ERROR)
  - Message text

#### Result Section

For completed jobs with output data, displays JSON result below the logs.

### Job Actions

Available actions depend on job status:

| Status    | Available Actions |
| --------- | ----------------- |
| Pending   | Cancel, Delete    |
| Running   | Cancel, Abort     |
| Completed | Delete            |
| Failed    | Retry, Delete     |

**Note:** Cancelled jobs do not have a retry option in the current implementation.

Action descriptions:

- **Cancel** - Gracefully stops the job after current operation (amber button)
- **Abort** - Forcefully terminates immediately, may cause data inconsistency (red button, only for running jobs)
- **Retry** - Re-queues a failed job for another attempt (blue button, no confirmation needed)
- **Delete** - Permanently removes job record from database (gray button)

Destructive actions (Cancel, Abort, Delete) show confirmation dialogs with warnings:

- Cancel dialog warns that the job will complete its current operation before stopping
- Abort dialog shows a WARNING about potential data inconsistency
- Delete dialog warns that the action cannot be undone

### Status Indicators

Status dots appear throughout the UI with consistent styling:

| Status             | Color  | Style             |
| ------------------ | ------ | ----------------- |
| Pending/Queued     | Gray   | Ring outline      |
| Processing/Running | Blue   | Pulsing animation |
| Completed          | Green  | Filled            |
| Failed             | Red    | Filled            |
| Cancelled          | Yellow | Filled            |

## Job Types

The system supports several background job types:

| Type        | Internal Key  | Description                                            |
| ----------- | ------------- | ------------------------------------------------------ |
| Export      | `export`      | Export events to CSV, JSON, or ZIP format              |
| Cleanup     | `cleanup`     | Clean up old data and temporary files                  |
| Backup      | `backup`      | Create a backup of system data                         |
| Import      | `import`      | Import events from external files                      |
| Batch Audit | `batch_audit` | Batch AI pipeline audit processing for multiple events |

### Job Lifecycle

Jobs follow a state machine with these transitions:

1. **Created** - Job is created and enters `pending` state
2. **Started** - Job begins execution and transitions to `running` state
3. **Completion** - Job either:
   - Completes successfully (`completed` state)
   - Fails with an error (`failed` state)
   - Is cancelled by user (`failed` state with cancellation message)

### Creating Jobs

Currently, jobs can be created through:

- **Export Job**: `POST /api/events/export` - Starts an export job with optional filters (camera_id, risk_level, date range, reviewed status)

## Settings & Configuration

The Jobs page does not have dedicated settings. However, job behavior is configured through:

- **Job Refresh** - Click the Refresh button to manually update the list
- **Filter Persistence** - All filter state saved in URL query parameters
- **Real-time Updates** - Active jobs receive live updates via WebSocket

### API Configuration

Jobs API endpoints support:

- **Pagination** - `limit` (1-1000, default 50) and `offset` parameters
- **Sorting** - `sort` field (created_at, started_at, completed_at, progress, job_type, status)
- **Sort Order** - `order` direction (asc or desc, default desc)
- **Advanced Search** - Duration ranges, timestamp ranges, error filtering

## Troubleshooting

### Job List is Empty

1. Check if filters are too restrictive - click "Clear all" to reset
2. Verify the backend is running and healthy
3. No jobs may have been created yet

### Job Shows "Pending" for Extended Period

1. Background task workers may be overloaded
2. Check system resources (CPU, memory, disk)
3. Review backend logs for worker errors

### Job Failed with Error

1. Expand the job detail panel to see error message
2. Check the job logs for detailed stack trace
3. Common causes:
   - Database connection issues
   - Insufficient disk space for exports
   - Timeout on large operations

### WebSocket Disconnected

The log viewer shows connection status with colored indicators:

- **Live** (green pulsing) - Real-time logs streaming
- **Reconnecting** (yellow) - Attempting to restore connection, shows attempt count
- **Offline** (gray) - Connection lost or streaming disabled
- **Failed** (red) - Connection could not be established

If disconnected:

1. Check network connectivity
2. Verify backend WebSocket server is running
3. Refresh the page to force reconnection
4. For failed connections, clicking the indicator may trigger a retry (if supported)

### Cancel/Abort Not Working

- **Completed jobs** cannot be cancelled - only active jobs
- **Failed jobs** can only be retried or deleted
- **Abort** is more aggressive than cancel - use for stuck jobs

### Export Job Produces Empty File

1. Verify events exist matching the filter criteria
2. Check date range if specified
3. Review the job result for row count

---

## Technical Deep Dive

For developers wanting to understand the underlying systems.

### Architecture

- **Job Tracking**: Jobs are tracked in-memory with Redis fallback for completed jobs
- **Background Tasks**: FastAPI BackgroundTasks for async job execution
- **Real-time Logs**: WebSocket streaming via job log emitter
- **State Machine**: Jobs transition through pending -> running -> completed/failed

### API Endpoints

| Endpoint                 | Method | Description                                                         |
| ------------------------ | ------ | ------------------------------------------------------------------- |
| `/api/jobs`              | GET    | List jobs with filtering and pagination                             |
| `/api/jobs/types`        | GET    | List available job types with descriptions                          |
| `/api/jobs/stats`        | GET    | Get aggregate job statistics (counts by status/type, avg duration)  |
| `/api/jobs/search`       | GET    | Advanced search with aggregations and faceted filtering             |
| `/api/jobs/{id}`         | GET    | Get job status                                                      |
| `/api/jobs/{id}/detail`  | GET    | Get detailed job information (progress, timing, retry info)         |
| `/api/jobs/{id}/cancel`  | POST   | Cancel a pending/running job (graceful stop)                        |
| `/api/jobs/{id}/abort`   | POST   | Force abort a running job (immediate termination)                   |
| `/api/jobs/{id}`         | DELETE | Cancel/abort based on current state (pending=cancel, running=abort) |
| `/api/jobs/bulk-cancel`  | POST   | Cancel multiple jobs at once                                        |
| `/api/jobs/{id}/history` | GET    | Get job execution history with state transitions and attempts       |
| `/api/jobs/{id}/logs`    | GET    | Get job execution logs with optional level/time filtering           |
| `/api/events/export`     | POST   | Start a new export job (returns 202 Accepted with job_id)           |

**Note:** There is no dedicated retry endpoint. Retry functionality is handled through the frontend's job mutation hooks.

### Related Code

**Frontend Components** (`frontend/src/components/jobs/`):

| File                      | Purpose                                                  |
| ------------------------- | -------------------------------------------------------- |
| `JobsPage.tsx`            | Main page component with split-view layout               |
| `JobsList.tsx`            | Scrollable list container for jobs                       |
| `JobsListItem.tsx`        | Individual job card with status, type, progress          |
| `JobDetailPanel.tsx`      | Right-side detail view with header, metadata, logs       |
| `JobHeader.tsx`           | Job title, status badge, and progress bar                |
| `JobMetadata.tsx`         | Timestamps (created, started, completed), duration, type |
| `JobLogsViewer.tsx`       | Real-time log viewer with WebSocket streaming            |
| `JobsSearchBar.tsx`       | Search input and filter dropdowns                        |
| `JobsEmptyState.tsx`      | Empty state when no jobs exist                           |
| `JobActions.tsx`          | Cancel/Abort/Retry/Delete action buttons                 |
| `ConfirmDialog.tsx`       | Confirmation modal for destructive actions               |
| `ConnectionIndicator.tsx` | WebSocket connection status indicator                    |
| `StatusDot.tsx`           | Colored status indicator dot                             |
| `StatusDropdown.tsx`      | Status filter dropdown component                         |
| `TypeDropdown.tsx`        | Job type filter dropdown component                       |
| `JobHistoryTimeline.tsx`  | Collapsible timeline of job state transitions            |
| `TimelineEntry.tsx`       | Individual entry in the history timeline                 |
| `LogLine.tsx`             | Individual log entry row                                 |
| `index.ts`                | Component exports                                        |

**Backend Services** (`backend/services/`):

| File                       | Purpose                                     |
| -------------------------- | ------------------------------------------- |
| `job_service.py`           | Core job service for detailed job retrieval |
| `job_tracker.py`           | In-memory job tracking with Redis fallback  |
| `job_history_service.py`   | Job execution history and audit trail       |
| `job_search_service.py`    | Advanced job search with aggregations       |
| `job_log_emitter.py`       | WebSocket log streaming                     |
| `job_progress_reporter.py` | Progress update handling                    |
| `job_state_service.py`     | Job state machine management                |
| `job_status.py`            | Job status enum definitions                 |
| `job_timeout_service.py`   | Job timeout handling                        |

**Backend API**: `backend/api/routes/jobs.py`
