# Logging System Design

**Date:** 2024-12-24
**Status:** Approved
**Goal:** Comprehensive logging for development debugging, production monitoring, and audit trail

## Overview

Add extensive structured logging to the project with three output destinations:

- Console (development)
- Rotating files (7-day retention)
- SQLite database (queryable via admin UI)

Frontend errors and key events are captured and sent to the backend for unified logging.

## Architecture

**Approach:** Single Unified Logger - one logging module writes to all destinations simultaneously.

```
Log Event → Unified Logger → Console (dev)
                          → Rotating Files (7 days)
                          → SQLite logs table (7 days)
```

## Backend Logging

### Central Logger Module (`backend/core/logging.py`)

- Configures Python's `logging` module once at startup
- Three handlers: `StreamHandler` (console), `RotatingFileHandler` (files), `SQLiteHandler` (custom)
- Structured log format using `python-json-logger` for consistent JSON output
- Context injection via `logging.Filter` to add request_id, camera_id, etc.

### Log Format (JSON structure)

```json
{
  "timestamp": "2024-12-24T10:30:00.123Z",
  "level": "INFO",
  "component": "file_watcher",
  "message": "New image detected",
  "camera_id": "front_door",
  "file_path": "/export/foscam/front_door/snap_001.jpg",
  "request_id": "abc-123",
  "duration_ms": 45
}
```

### Component Tags (standardized)

| Tag            | Description            |
| -------------- | ---------------------- |
| `api`          | REST endpoints         |
| `websocket`    | WebSocket connections  |
| `file_watcher` | Camera file monitoring |
| `detector`     | RT-DETRv2 client       |
| `nemotron`     | LLM analyzer           |
| `batch`        | Batch aggregator       |
| `events`       | Event processing       |
| `cleanup`      | Retention cleanup      |
| `frontend`     | Frontend-reported logs |

### File Output

- Location: `data/logs/security.log`
- Rotation: 10MB max, keep 7 files
- Human-readable format for files (not JSON) for easy `grep`/`tail`

## Database Schema

### New SQLite Table (`logs`)

```sql
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(10) NOT NULL,  -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    component VARCHAR(50) NOT NULL,  -- file_watcher, api, detector, etc.
    message TEXT NOT NULL,

    -- Structured metadata (nullable, for filtering)
    camera_id VARCHAR(100),
    event_id INTEGER,
    request_id VARCHAR(36),
    detection_id INTEGER,

    -- Performance/debug fields
    duration_ms INTEGER,
    extra JSON,  -- Catch-all for additional structured data

    -- Source tracking
    source VARCHAR(10) DEFAULT 'backend',  -- backend, frontend
    user_agent TEXT,  -- For frontend logs

    -- Indexes for common queries
    INDEX idx_logs_timestamp (timestamp),
    INDEX idx_logs_level (level),
    INDEX idx_logs_component (component),
    INDEX idx_logs_camera (camera_id)
);
```

### SQLAlchemy Model (`backend/models/log.py`)

- Standard model matching schema
- Class methods for common queries: `get_recent()`, `count_by_level()`, `search()`

### Retention Cleanup

- Add to existing `CleanupService`
- Run daily: `DELETE FROM logs WHERE timestamp < datetime('now', '-7 days')`
- Vacuum after cleanup to reclaim space

## API Endpoints

### New Route File (`backend/api/routes/logs.py`)

```
GET  /api/logs
     Query params: level, component, camera_id, start_date, end_date,
                   search (message text), limit (default 100), offset
     Returns: Paginated log entries with total count

GET  /api/logs/stats
     Returns: Summary for dashboard cards
     {
       "total_today": 1250,
       "errors_today": 3,
       "warnings_today": 28,
       "by_component": {"file_watcher": 400, "api": 350, ...},
       "by_level": {"INFO": 1100, "WARNING": 28, ...}
     }

GET  /api/logs/{id}
     Returns: Single log entry with full details (including extra JSON)

POST /api/logs/frontend
     Body: {level, component, message, extra, user_agent}
     Purpose: Receive frontend error/event reports
     Rate limited: 100 requests/minute per IP
```

### Pydantic Schemas (`backend/api/schemas/logs.py`)

- `LogEntry` - Response model for log records
- `LogsResponse` - Paginated response with items + total
- `LogStats` - Dashboard statistics
- `FrontendLogCreate` - Validation for frontend-submitted logs

## Frontend Logging

### Logger Service (`frontend/src/services/logger.ts`)

```typescript
// Usage throughout app:
logger.error("API request failed", { endpoint: "/api/events", status: 500 });
logger.event("user_navigation", { page: "event-timeline" });
logger.event("button_click", { action: "dismiss_alert", event_id: 123 });
```

Features:

- Captures errors with stack traces automatically via `window.onerror` and React error boundaries
- Batches logs (send every 5 seconds or 10 items, whichever first)
- Falls back to console if backend unavailable
- Includes user agent, current URL, timestamp

### Key Events to Capture

- Page navigation
- API errors (non-2xx responses)
- WebSocket connect/disconnect
- User actions: dismiss event, acknowledge alert, change settings
- Unhandled exceptions

## Admin UI

### Components (`frontend/src/components/logs/`)

| Component            | Purpose                                       |
| -------------------- | --------------------------------------------- |
| `LogsDashboard.tsx`  | Main page with stats cards + table            |
| `LogStatsCards.tsx`  | Error count, warnings, activity by component  |
| `LogsTable.tsx`      | Filterable, sortable, paginated log list      |
| `LogFilters.tsx`     | Level, component, camera, date range, search  |
| `LogDetailModal.tsx` | Full log entry with formatted JSON extra data |

### Dashboard Cards

```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Errors      │ │ Warnings    │ │ Total       │ │ Top         │
│ 3 today     │ │ 28 today    │ │ 1,250       │ │ file_watcher│
│ (red if >0) │ │             │ │             │ │             │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

### UI Consistency

Match existing patterns from `EventTimeline` and `DashboardPage`:

| Pattern        | Implementation                                               |
| -------------- | ------------------------------------------------------------ |
| Dark theme     | `bg-[#121212]` background, Tailwind dark classes             |
| Icons          | Lucide React (`Filter`, `Search`, `X`, `Calendar`, etc.)     |
| Cards          | Same rounded corners, shadow, padding as `EventCard`         |
| Filters        | Match `EventTimeline` filter panel (expandable, same inputs) |
| Pagination     | Reuse `ChevronLeft`/`ChevronRight` pattern with page info    |
| Loading states | Skeleton placeholders matching existing components           |
| Error states   | Red alert box with retry button                              |

### Navigation

- Add "Logs" tab to main navigation alongside Dashboard, Events, Settings
- Route: `/logs`

## Integration

### Startup (`backend/main.py`)

- Call `setup_logging()` before FastAPI app creation
- Logging configured once, all modules inherit configuration

### Migration Path

Current pattern (unchanged usage):

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Processing image")
```

Enhanced pattern (add structured context):

```python
from backend.core.logging import get_logger
logger = get_logger(__name__)
logger.info("Processing image", extra={"camera_id": "front_door", "file": path})
```

Both patterns work - existing code continues functioning, gradually enhance with structured fields.

### Context Propagation

- FastAPI middleware injects `request_id` into all logs during request lifecycle
- Use `contextvars` for thread-safe context passing
- Services receive context via dependency injection or explicit parameters

## Configuration

### Environment Variables (`.env` additions)

```bash
# Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE_PATH=data/logs/security.log
LOG_FILE_MAX_BYTES=10485760       # 10MB
LOG_FILE_BACKUP_COUNT=7           # Keep 7 rotated files
LOG_DB_ENABLED=true               # Write to SQLite
LOG_DB_MIN_LEVEL=DEBUG            # Minimum level for DB (can exclude DEBUG)
LOG_RETENTION_DAYS=7
```

## Files to Create/Modify

### New Files

| File                                              | Purpose                                    |
| ------------------------------------------------- | ------------------------------------------ |
| `backend/core/logging.py`                         | Central logger setup, handlers, formatters |
| `backend/models/log.py`                           | SQLAlchemy Log model                       |
| `backend/api/routes/logs.py`                      | API endpoints                              |
| `backend/api/schemas/logs.py`                     | Pydantic schemas                           |
| `frontend/src/services/logger.ts`                 | Frontend logging service                   |
| `frontend/src/components/logs/LogsDashboard.tsx`  | Main logs page                             |
| `frontend/src/components/logs/LogStatsCards.tsx`  | Summary cards                              |
| `frontend/src/components/logs/LogsTable.tsx`      | Log table                                  |
| `frontend/src/components/logs/LogFilters.tsx`     | Filter panel                               |
| `frontend/src/components/logs/LogDetailModal.tsx` | Log detail view                            |

### Modified Files

| File                                            | Change                           |
| ----------------------------------------------- | -------------------------------- |
| `backend/core/__init__.py`                      | Export logging utilities         |
| `backend/core/config.py`                        | Add logging settings             |
| `backend/api/routes/__init__.py`                | Register logs router             |
| `backend/services/cleanup_service.py`           | Add log retention cleanup        |
| `backend/main.py`                               | Initialize logging at startup    |
| `frontend/src/App.tsx`                          | Add /logs route                  |
| `frontend/src/components/layout/Navigation.tsx` | Add Logs nav item                |
| Existing services (10 files)                    | Gradually add structured context |

## Testing

| Layer                                        | Tests                                                         |
| -------------------------------------------- | ------------------------------------------------------------- |
| `backend/tests/unit/test_logging.py`         | Logger setup, handlers, formatters, context injection         |
| `backend/tests/unit/test_log_model.py`       | SQLAlchemy model CRUD, retention queries                      |
| `backend/tests/integration/test_logs_api.py` | API endpoints, filtering, pagination, frontend log submission |
| `frontend/src/components/logs/*.test.tsx`    | Component rendering, filter interactions, API mocking         |

### Key Test Cases

- Logs written to all three destinations (console, file, DB)
- Structured fields properly indexed and queryable
- Retention cleanup deletes only logs > 7 days
- Frontend log submission rate limiting works
- Large log queries perform acceptably (< 500ms for 1000 rows)

## Dependencies

### Backend (add to `pyproject.toml`)

```
python-json-logger>=2.0.0
```

### Frontend

No additional dependencies required.
