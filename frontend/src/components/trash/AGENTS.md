# Trash Component

This directory contains the Trash page component for viewing and restoring soft-deleted items.

## Purpose

The Trash view provides users with the ability to:
- View soft-deleted cameras and events
- See when each item was deleted (deleted_at timestamp)
- Restore deleted items back to active status
- Navigate between deleted cameras and events using tabs

## Key Files

### TrashPage.tsx

Main page component that displays soft-deleted items.

**Features:**
- Tabbed interface for cameras and events
- Empty state when no deleted items
- Loading skeleton during data fetch
- Error state with retry capability
- Confirmation modal before restore
- Toast notifications for success/error

**State Management:**
- Uses local state (useState) for data, loading, error, and modal states
- Uses useToast hook for notifications

**API Integration:**
- `fetchDeletedItems()` - Fetches all soft-deleted cameras and events
- `restoreCamera(id)` - Restores a soft-deleted camera
- `restoreEvent(id)` - Restores a soft-deleted event

### TrashPage.test.tsx

Comprehensive test suite covering:
- Loading state display
- Error state and retry functionality
- Empty state when no deleted items
- Tab switching between cameras and events
- Restore confirmation modal
- Successful restore operations
- Error handling on restore failure
- Accessibility (proper heading hierarchy, modal labeling)
- Risk level badge styling

## API Endpoints Required

The component expects these backend API endpoints:

```
GET  /api/trash                            - List all deleted items
POST /api/trash/cameras/{id}/restore       - Restore a camera
POST /api/trash/events/{id}/restore        - Restore an event
DELETE /api/trash/cameras/{id}             - Permanently delete camera (not yet implemented in UI)
DELETE /api/trash/events/{id}              - Permanently delete event (not yet implemented in UI)
```

## Navigation

The Trash page is accessible via:
- Route: `/trash`
- Sidebar: Trash link with trash icon (at bottom of navigation)

## Design Patterns

The component follows existing patterns in the codebase:
- Uses Tremor and Tailwind for styling
- Uses Headless UI for accessible tabs
- Uses AnimatedModal for confirmation dialogs
- Uses EmptyState for empty/error states
- Uses useToast for notifications
- Follows NVIDIA dark theme color scheme

## Future Enhancements

Potential improvements not yet implemented:
- Permanent delete option (UI exists in API client)
- Bulk restore/delete operations
- Search/filter within deleted items
- Pagination for large numbers of deleted items
- Automatic cleanup of old deleted items
