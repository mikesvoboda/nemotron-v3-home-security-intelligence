# Audit Log

The Audit Log page provides a comprehensive record of all security-sensitive operations performed on the system, enabling accountability, compliance tracking, and security monitoring.

## What You're Looking At

The Audit Log is your central hub for tracking system activity and security events. It automatically records every meaningful action taken on the system, including who performed it, when, and from where. This page provides:

- **Statistics Cards** - Quick overview of audit activity (total entries, today's activity, success/failure counts)
- **Action Breakdown** - Visual badges showing the most common action types
- **Filterable Table** - Paginated list of all audit entries with powerful filtering
- **Detailed Modal** - Full audit entry details including metadata and JSON payload

## Key Components

### Statistics Cards

Four summary cards at the top provide at-a-glance metrics:

| Card                      | Description                            | Interaction                                 |
| ------------------------- | -------------------------------------- | ------------------------------------------- |
| **Total Audit Entries**   | Total number of logged operations      | Click to clear filters and show all entries |
| **Entries Today**         | Operations logged in the last 24 hours | Click to filter to today's date range       |
| **Successful Operations** | Count of entries with status=success   | Click to filter by success status           |
| **Failed Operations**     | Count of entries with status=failure   | Click to filter by failure status           |

Clicking any card toggles that filter. Click again to clear the filter.

### Actions by Type

Below the statistics cards, a row of action badges shows the most common operation types. Each badge displays:

- **Action name** (formatted, e.g., "Settings Changed")
- **Count** (number of occurrences)

Click any badge to filter the table by that action type. The top 10 most frequent actions are shown.

### Audit Filters

The collapsible filter panel provides granular control over which entries are displayed:

| Filter            | Options     | Description                                                             |
| ----------------- | ----------- | ----------------------------------------------------------------------- |
| **Action**        | Dropdown    | Filter by specific action type (Settings Changed, Event Reviewed, etc.) |
| **Resource Type** | Dropdown    | Filter by resource category (camera, event, settings, security, etc.)   |
| **Actor**         | Dropdown    | Filter by who performed the action (IP address, API key, system)        |
| **Status**        | Dropdown    | Filter by success or failure                                            |
| **Start Date**    | Date picker | Show entries from this date forward                                     |
| **End Date**      | Date picker | Show entries up to this date                                            |

An "Active" badge appears when any filter is applied. Use "Clear All Filters" to reset.

### Audit Table

The main table displays audit entries with the following columns:

| Column         | Description                                                  |
| -------------- | ------------------------------------------------------------ |
| **Timestamp**  | When the action occurred (relative time, hover for absolute) |
| **Actor**      | Who performed the action (highlighted in green)              |
| **Action**     | Operation type with color-coded badge                        |
| **Resource**   | Resource type and ID (e.g., `settings/batch_window_seconds`) |
| **IP Address** | Client IP address (if available)                             |
| **Status**     | Success or failure with icon indicator                       |

**Action Badge Colors:**

- **Green** - Create/Add operations
- **Blue** - Update/Edit/Modify operations
- **Red** - Delete/Remove operations
- **Gray** - Read/View operations and other actions

Click any row to open the detail modal for that entry.

### Audit Detail Modal

The modal displays complete information about an audit entry:

- **Header** - Action name, timestamp, status badge, close button
- **Actor Card** - Who performed the action
- **Resource Card** - Resource type and ID
- **Entry Details** - Audit ID, action, status, IP address
- **User Agent** - Browser/client information (if captured)
- **Additional Details** - JSON payload with action-specific data (pretty-printed)

Press **Escape** or click outside to close the modal.

### Event AI Audit Detail (EventAuditDetail)

For events processed by the AI pipeline, a specialized audit detail component is available that shows:

- **Quality Scores** - Visual bars (1-5 scale) showing context usage, reasoning coherence, risk justification, consistency, and overall score
- **Model Contributions** - Checklist showing which AI models contributed to the analysis (RT-DETR, Florence, CLIP, Violence, Clothing, Vehicle, Pet, Weather, Quality, Zones, Baseline, Cross-camera)
- **Self-Critique** - The AI's self-evaluation text explaining its reasoning
- **Improvement Suggestions** - Lists of missing context, confusing sections, unused data, format suggestions, and model gaps
- **Actions** - "Run Evaluation" or "Re-run Evaluation" button to trigger AI analysis

This component integrates with the `auditApi.ts` service to fetch event-specific audit data.

## What Gets Logged

The audit log automatically records operations across several categories. These actions are defined in the `AuditAction` enum in `backend/models/audit.py`.

### Event Actions

- `event_reviewed` - An event was marked as reviewed
- `event_dismissed` - An event was dismissed

### Settings Actions

- `settings_changed` - System settings were modified
- `config_updated` - Configuration was updated

### Camera Actions

- `camera_created` - A new camera was added
- `camera_updated` - Camera settings were modified
- `camera_deleted` - A camera was removed

### Zone Actions

- `zone_created` - A detection zone was created
- `zone_updated` - A zone was modified
- `zone_deleted` - A zone was removed

### Alert Rule Actions

- `rule_created` - A new alert rule was created
- `rule_updated` - An alert rule was modified
- `rule_deleted` - An alert rule was deleted

### AI Pipeline Actions

- `ai_reevaluated` - AI re-analyzed an event

### Media Actions

- `media_exported` - Media files were exported
- `bulk_export_completed` - A bulk export operation completed

### Security Actions

- `rate_limit_exceeded` - A client exceeded rate limits
- `security_alert` - A security alert was triggered
- `content_type_rejected` - A request with invalid Content-Type was rejected
- `file_magic_rejected` - A file with mismatched magic number was rejected

### Authentication Actions

- `login` - A user logged in (reserved for future authentication)
- `logout` - A user logged out (reserved for future authentication)

### Administrative Actions

- `data_cleared` - System data was cleared
- `cleanup_executed` - A cleanup operation was performed
- `notification_test` - A notification test was sent

### API Key Actions

- `api_key_created` - A new API key was generated
- `api_key_revoked` - An API key was revoked

## Actor Identification

The audit system identifies actors in the following priority order (see `get_actor_from_request()` in `backend/services/audit.py`):

1. **API Key** - If X-API-Key header is present (or `api_key` query param), shown as `api_key:` followed by the first 8 characters and `...` (e.g., `api_key:abc12345...`)
2. **Client IP** - If no API key, the client's IP address as `ip:192.168.1.1` (checks X-Forwarded-For header for proxied requests)
3. **System** - For automated operations, shown as `system`
4. **Unknown** - Fallback if no identification is available

## Settings & Configuration

The Audit Log page has minimal configuration as it's designed to capture all security events automatically. Key settings that affect audit logging:

### Retention Period

Audit logs follow the same 30-day retention policy as other system data.

### Captured Metadata

For each audit entry, the system captures:

- Timestamp (UTC)
- Action type
- Resource type and ID
- Actor identification
- Client IP address
- User agent string
- Action-specific details (JSON)
- Success/failure status

## Troubleshooting

### No Audit Entries Found

If the table shows "No Audit Entries Found":

1. **Check filters** - Expand the filter panel and verify no restrictive filters are active
2. **Expand date range** - The default view may be filtering by date
3. **Perform an action** - Try changing a setting or reviewing an event to generate an entry
4. **Verify backend connection** - Check the system health indicator in the header

### Statistics Not Loading

If the stats cards show loading spinners indefinitely:

1. Check the browser console for errors
2. Verify the backend API is running (`/api/audit/stats` endpoint)
3. Check network connectivity

### Missing Entries for Recent Actions

Audit entries are created immediately but may take a moment to appear:

1. Wait a few seconds and refresh
2. Check if the action type is one that generates audit entries
3. Some read-only operations (viewing data) are not logged

### Timestamp Shows Wrong Time

Timestamps are displayed in your browser's local timezone. If they appear incorrect:

1. Verify your system clock is accurate
2. Check your timezone settings
3. Hover over the timestamp to see the full UTC timestamp

### Actor Shows "Unknown"

This can happen when:

1. The request didn't include an API key or identifiable headers
2. The action was performed by a background process
3. The request came through a proxy without proper forwarding headers

---

## Technical Deep Dive

For developers wanting to understand the underlying systems.

### Architecture

- **Backend Service**: `backend/services/audit.py` - Core audit logging service
- **Security Logger**: `backend/services/audit_logger.py` - High-level security event logging
- **Database Model**: `backend/models/audit.py` - SQLAlchemy model with indexed columns
- **API Routes**: `backend/api/routes/audit.py` - REST endpoints for audit queries

### Database Schema

The `audit_logs` table includes:

- Composite index on `(resource_type, resource_id)` for resource queries
- BRIN index on `timestamp` for efficient time-range queries (much smaller than B-tree, ideal for ordered timestamps)
- Individual indexes on `action`, `actor`, `status`, and `timestamp` for filtering
- CHECK constraint ensuring status is either `success` or `failure`

### API Endpoints

| Endpoint           | Method | Description                                                |
| ------------------ | ------ | ---------------------------------------------------------- |
| `/api/audit`       | GET    | List audit logs with filtering and cursor-based pagination |
| `/api/audit/stats` | GET    | Get aggregated statistics (optimized with UNION ALL query) |
| `/api/audit/{id}`  | GET    | Get a specific audit entry by ID                           |

**Pagination Notes:**

- The `/api/audit` endpoint supports both cursor-based pagination (recommended) and offset pagination (deprecated)
- Cursor-based pagination offers better performance for large datasets
- By default, total count is not calculated for performance reasons; use `include_total_count=true` if needed
- The stats endpoint uses a single UNION ALL query to fetch all statistics in one database round-trip

### Frontend Components

- **AuditLogPage**: `frontend/src/components/audit/AuditLogPage.tsx` - Main page assembly (renders stats, filters, table, and modal)
- **AuditTable**: `frontend/src/components/audit/AuditTable.tsx` - Paginated table with clickable rows
- **AuditFilters**: `frontend/src/components/audit/AuditFilters.tsx` - Filter controls with URL persistence via `useDateRangeState`
- **AuditStatsCards**: `frontend/src/components/audit/AuditStatsCards.tsx` - Statistics display with clickable cards and action badges
- **AuditDetailModal**: `frontend/src/components/audit/AuditDetailModal.tsx` - Detail modal using Headless UI Dialog
- **EventAuditDetail**: `frontend/src/components/audit/EventAuditDetail.tsx` - AI pipeline audit details for events (quality scores, model contributions, self-critique)

### Related Documentation

- [AI Pipeline Architecture](../architecture/ai-pipeline.md) - AI analysis pipeline that generates audit-logged events
- [Architecture Overview](../architecture/overview.md) - System architecture and design decisions
- [Developer Patterns](../developer/patterns/AGENTS.md) - Testing patterns and developer guidelines
