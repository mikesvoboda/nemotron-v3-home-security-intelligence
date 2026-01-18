# System Logs

The centralized logging interface for viewing, filtering, and analyzing system logs from both backend services and frontend components.

## What You're Looking At

The System Logs page provides a unified view of all application logs, helping you monitor system health, debug issues, and track activity across the entire security monitoring platform. It collects logs from:

- **Backend API services** - API route handlers, authentication, and request processing
- **AI detection pipeline** - RT-DETRv2 detection, Nemotron risk analysis, batch aggregation
- **File watcher** - Camera FTP uploads and image processing
- **Frontend components** - UI errors, user interactions, and browser events
- **WebSocket events** - Real-time connection status and broadcast messages
- **Cleanup services** - Data retention and file management

## Key Components

### Statistics Cards

At the top of the page, four cards provide a quick health overview:

| Card               | Description                                                                                              |
| ------------------ | -------------------------------------------------------------------------------------------------------- |
| **Errors Today**   | Count of ERROR-level logs in the past 24 hours. Shows red with "Active" badge when > 0. Click to filter. |
| **Warnings Today** | Count of WARNING-level logs. Yellow highlight when > 0. Click to filter.                                 |
| **Total Today**    | Total log entries generated today (all levels).                                                          |
| **Most Active**    | The component generating the most logs, with entry count.                                                |

Statistics auto-refresh every 30 seconds to keep the dashboard current.

**Interactive filtering:** Click the "Errors Today" or "Warnings Today" cards to filter the logs table to show only that level. Click again to clear the filter. A ring indicator appears around the active filter card.

### Log Levels

Logs are categorized by severity level, each with distinct color coding:

| Level        | Color                  | Table Icon    | Modal Icon  | Use Case                                                |
| ------------ | ---------------------- | ------------- | ----------- | ------------------------------------------------------- |
| **DEBUG**    | Gray                   | Bug           | Code2       | Verbose development information, disabled in production |
| **INFO**     | Blue                   | Info          | Info        | Normal operations, successful actions                   |
| **WARNING**  | Yellow/Amber           | AlertTriangle | AlertCircle | Potential issues that don't block operations            |
| **ERROR**    | Red                    | AlertOctagon  | XCircle     | Failed operations requiring attention                   |
| **CRITICAL** | Red (solid background) | AlertOctagon  | XCircle     | Severe failures, system instability                     |

Note: The table view and detail modal use slightly different icons for visual variety. All icons are from the [Lucide](https://lucide.dev/) icon library.

### Filter Panel

Click "Show Filters" (toggles to "Hide Filters" when expanded) to reveal filtering options:

- **Log Level** - Filter by severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Component** - Filter by source system:
  - `frontend` - Browser-side logs
  - `api` - Backend API routes
  - `user_event` - User interactions
  - `file_watcher` - Camera file monitoring
  - `detector` - AI object detection
  - `aggregator` - Batch processing
  - `risk_analyzer` - Nemotron AI analysis
  - `event_broadcaster` - WebSocket events
  - `gpu_monitor` - GPU health monitoring
  - `cleanup_service` - Data retention
- **Camera** - Filter logs related to a specific camera
- **Start Date / End Date** - Filter by time range
- **Search** - Full-text search across log messages

An "Active" badge appears when any filters are applied. Click "Clear All Filters" to reset.

**URL Persistence:** Date range filters are persisted to the URL (via the `logDateRange` query parameter), allowing you to share filtered views or bookmark specific date ranges.

### Logs Table

The main table displays log entries with:

- **Timestamp** - Relative time (e.g., "Just now", "5m ago", "2h ago", "3d ago") or formatted date for logs older than 7 days
- **Level** - Color-coded severity badge with icon
- **Component** - Source system in NVIDIA green monospace font (`#76B900`)
- **Message** - Truncated to 100 characters (click row for full details)

Table features:

- Click any row to open the detail modal
- Results summary shows "Showing X-Y of Z logs"
- Pagination controls at the bottom (50 logs per page by default)
- "Page X of Y" indicator with Previous/Next buttons
- Newest logs appear first (sorted by timestamp descending, then by ID for tie-breaking)
- Empty state with helpful information when no logs match filters

### Log Detail Modal

Clicking a log row opens a centered modal (max-width 4xl) with:

**Header Section:**

- Component name as title
- Full timestamp with date and time
- Level badge with icon
- Close button (X) or press Escape

**Message Section:**

- Complete log message without truncation

**Log Details Section:**

- Log ID (unique identifier)
- Component name
- Source (backend or frontend)
- Camera ID (if applicable)
- Event ID (if linked to a security event)
- Detection ID (if linked to an AI detection)
- Request ID (for API request correlation)
- Duration (in milliseconds, for performance tracking)

**Additional Data Section:**

- Pretty-printed JSON of the `extra` field
- Contains structured context like stack traces, request details, etc.

**User Agent Section (frontend logs only):**

- Browser/device information for frontend-originated logs

## Settings & Configuration

### Frontend Logger Configuration

The frontend logger (in `frontend/src/services/logger.ts`) can be configured:

| Setting           | Default | Description                               |
| ----------------- | ------- | ----------------------------------------- |
| `batchSize`       | 10      | Entries to accumulate before sending      |
| `flushIntervalMs` | 5000    | Automatic flush interval (5 seconds)      |
| `maxQueueSize`    | 100     | Maximum queue size before dropping oldest |
| `enabled`         | true    | Toggle logging on/off                     |

### API Query Parameters

The `/api/logs` endpoint accepts:

| Parameter             | Default | Description                                    |
| --------------------- | ------- | ---------------------------------------------- |
| `limit`               | 100     | Results per page (1-1000)                      |
| `offset`              | 0       | Skip N results (deprecated, use cursor)        |
| `cursor`              | -       | Cursor-based pagination token                  |
| `level`               | -       | Filter by log level                            |
| `component`           | -       | Filter by component name                       |
| `camera_id`           | -       | Filter by camera                               |
| `source`              | -       | Filter by source (backend/frontend)            |
| `search`              | -       | Full-text search in messages                   |
| `start_date`          | -       | Filter from date (ISO format)                  |
| `end_date`            | -       | Filter to date (ISO format)                    |
| `include_total_count` | false   | Calculate total (expensive for large datasets) |

### Database Retention

Logs follow a **7-day retention policy** by default (configurable via `LOG_RETENTION_DAYS` environment variable). This is shorter than the 30-day retention for events and detections due to the higher volume of log data. Older logs are automatically cleaned up by the cleanup service which runs daily at 03:00.

## Troubleshooting

### No Logs Appear

1. **Check time range** - Clear date filters or expand the range
2. **Verify backend is running** - Check the health indicator in the header
3. **Check component filter** - Some components may not generate logs frequently
4. **Database connection** - Verify PostgreSQL is accessible

### Statistics Show Zero

1. **Check date boundary** - Stats are calculated from midnight UTC
2. **Recent deployment** - Logs from previous deployment may have different schema
3. **Refresh manually** - Stats auto-refresh every 30 seconds

### Search Returns No Results

1. **Check exact spelling** - Search is case-insensitive but partial
2. **Try shorter terms** - The search uses ILIKE pattern matching
3. **Clear other filters** - Multiple filters combine with AND logic

### Frontend Logs Not Appearing

1. **Check browser console** - Logs appear in console first
2. **Verify network requests** - Look for `/api/logs/frontend/batch` calls
3. **Check sendBeacon support** - Required for page unload logging
4. **Flush timer** - Logs batch every 5 seconds by default

### Log Detail Modal Won't Close

1. **Press Escape key** - Keyboard shortcut to close
2. **Click outside modal** - Backdrop click closes the modal
3. **Click Close button** - Bottom right of the modal

### High Error Count

1. **Click the Errors card** - Filter to show only errors
2. **Check component distribution** - Identify which system is failing
3. **Review recent timestamps** - Determine if errors are ongoing
4. **Check related events** - Use Event ID links to find correlated events

---

## Technical Deep Dive

For developers wanting to understand the underlying systems.

### Architecture

- **Log Storage**: [Database Guide](../operator/database.md) - Database setup and the `logs` table with BRIN and GIN indexes
- **API Implementation**: `backend/api/routes/logs.py` - FastAPI endpoints with cursor pagination
- **Frontend Logger**: `frontend/src/services/logger.ts` - Batched logging with sendBeacon fallback

### Data Model

The `Log` model (`backend/models/log.py`) stores:

```python
class Log(Base):
    __tablename__ = "logs"

    id: int                    # Auto-incrementing primary key
    timestamp: datetime        # When the log was created (with timezone, server default NOW())
    level: str                 # DEBUG, INFO, WARNING, ERROR, CRITICAL (max 10 chars, CHECK constraint)
    component: str             # Source component (max 50 chars)
    message: str               # Log message (TEXT, unlimited storage)

    # Optional metadata for correlation
    camera_id: str | None      # Related camera (max 100 chars)
    event_id: int | None       # Related security event (foreign key)
    request_id: str | None     # API request correlation ID (max 36 chars, UUID format)
    detection_id: int | None   # Related AI detection (foreign key)
    duration_ms: int | None    # Operation duration for performance tracking
    extra: dict | None         # JSONB additional context (stack traces, request details, etc.)

    # Source tracking
    source: str                # "backend" or "frontend" (max 10 chars, CHECK constraint)
    user_agent: str | None     # Browser info (frontend logs only, TEXT)

    # Full-text search
    search_vector: TSVECTOR    # Auto-populated by database trigger
                               # Combines: message (weight A), component (weight B), level (weight C)
```

The model includes CHECK constraints to ensure `level` and `source` contain valid values only.

### Database Indexes

Optimized for common query patterns:

- `idx_logs_timestamp` - Time-based filtering
- `idx_logs_level` - Level filtering
- `idx_logs_component` - Component filtering
- `idx_logs_camera_id` - Camera correlation
- `idx_logs_source` - Source filtering
- `ix_logs_timestamp_brin` - BRIN index for time-series queries (compact)
- `idx_logs_search_vector` - GIN index for full-text search

### API Endpoints

| Endpoint                   | Method | Description                             |
| -------------------------- | ------ | --------------------------------------- |
| `/api/logs`                | GET    | List logs with filtering and pagination |
| `/api/logs/stats`          | GET    | Get daily statistics                    |
| `/api/logs/{log_id}`       | GET    | Get single log by ID                    |
| `/api/logs/frontend`       | POST   | Create frontend log entry               |
| `/api/logs/frontend/batch` | POST   | Create multiple frontend logs (max 100) |

### Frontend Integration

The frontend logger automatically captures:

- **Unhandled errors** via `window.onerror` - captures message, source, line/column numbers, and stack trace
- **Promise rejections** via `window.onunhandledrejection` - captures rejection reason and stack
- **Page unload logs** via `beforeunload` event with `navigator.sendBeacon()` for reliable delivery
- **Visibility changes** via `visibilitychange` event - flushes logs when tab becomes hidden (mobile browsers)

The logger automatically includes the current page URL in all log entries.

Usage in components:

```typescript
import { logger } from '../../services/logger';

// Global logger (component defaults to 'frontend')
logger.info('Message', { extra: 'data' });
logger.error('Error occurred', { stack: error.stack });
logger.debug('Debug info'); // Also logs to console
logger.warn('Warning message');

// User events (component set to 'user_event')
logger.event('button_clicked', { buttonId: 'submit' });

// API errors (component set to 'api')
logger.apiError('/api/events', 500, 'Internal server error');

// Component-specific logger
const log = logger.forComponent('MyComponent');
log.debug('Component mounted');
log.info('Data loaded', { count: 10 });
log.warn('Deprecated prop used', { prop: 'oldProp' });
log.error('Failed to save', { error: err.message });
```

### Related Code

- Frontend Dashboard: `frontend/src/components/logs/LogsDashboard.tsx`
- Filters Component: `frontend/src/components/logs/LogFilters.tsx`
- Table Component: `frontend/src/components/logs/LogsTable.tsx`
- Detail Modal: `frontend/src/components/logs/LogDetailModal.tsx`
- Stats Cards: `frontend/src/components/logs/LogStatsCards.tsx`
- Logger Service: `frontend/src/services/logger.ts`
- Backend Routes: `backend/api/routes/logs.py`
- Log Model: `backend/models/log.py`
- Audit Logger: `backend/services/audit_logger.py`

### Performance Considerations

1. **Total count disabled by default** - Use `include_total_count=true` only when needed
2. **Cursor-based pagination** - More efficient than offset for large datasets
3. **BRIN index** - 1000x smaller than B-tree for time-series queries
4. **Batch frontend logging** - Single request for multiple entries
5. **30-second stats refresh** - Balances freshness vs. server load
