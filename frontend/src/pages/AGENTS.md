# Pages Directory

## Purpose

Contains top-level page components that serve as route destinations. These pages are standalone views that compose other components to provide full-page experiences.

## Files

| File                 | Purpose                                  |
| -------------------- | ---------------------------------------- |
| `TrashPage.tsx`      | Soft-deleted events management page      |
| `TrashPage.test.tsx` | Test suite for TrashPage                 |

## Key Components

### TrashPage.tsx

**Purpose:** Page component for viewing and managing soft-deleted events

**Key Features:**

- Lists all soft-deleted events
- Restore events back to active state
- Permanently delete events
- Shows empty state when trash is empty
- 30-day auto-deletion notice

**Hooks Used:**

- `useDeletedEventsQuery` - Fetches soft-deleted events
- `useRestoreEventMutation` - Mutation for restoring events
- `usePermanentDeleteMutation` - Mutation for permanent deletion

**States:**

- Loading: Shows LoadingSpinner
- Error: Shows error message with retry button
- Empty: Shows EmptyState with Trash2 icon
- Data: Shows list of DeletedEventCard components

**Dependencies:**

- `lucide-react` - AlertCircle, Info, Trash2 icons
- `../components/common/EmptyState` - Empty state display
- `../components/common/LoadingSpinner` - Loading indicator
- `../components/events/DeletedEventCard` - Deleted event card component
- `../hooks/useTrashQuery` - Query hooks for trash operations

## Route Configuration

Pages in this directory are typically mapped to routes in `App.tsx`:

```typescript
// Example route configuration
<Route path="/trash" element={<TrashPage />} />
```

## Important Patterns

### Page Structure

Pages follow a consistent structure:

1. **Header section** - Title and description
2. **Notices/alerts** - Important information (auto-deletion notice)
3. **Error handling** - Mutation errors displayed inline
4. **Summary** - Count of items
5. **Content** - Main content area (event list)

### Loading/Error/Empty Pattern

All pages implement the standard three-state pattern:

```tsx
if (isLoading) return <LoadingSpinner />;
if (error) return <ErrorDisplay error={error} onRetry={refetch} />;
if (isEmpty) return <EmptyState {...props} />;
return <MainContent data={data} />;
```

### Mutation Error Display

Mutation errors are displayed inline above the content:

```tsx
{mutation.error && (
  <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
    <span className="text-red-400">{mutation.error.message}</span>
  </div>
)}
```

## Styling Conventions

- Page padding: `p-6`
- Page title: `text-2xl font-bold text-white`
- Description: `text-text-secondary`
- Info notice: `border-blue-500/20 bg-blue-500/10` with blue text
- Error notice: `border-red-500/20 bg-red-500/10` with red text
- Section spacing: `mb-6` between sections

## Testing

`TrashPage.test.tsx` covers:

- Loading state display
- Error state with retry functionality
- Empty state when no deleted events
- Event list rendering
- Restore and permanent delete actions
- Mutation error handling

## Entry Points

**Start here:** `TrashPage.tsx` - Example of a full page component with CRUD operations

## Notes

- Most pages are located in component directories (e.g., EventTimeline.tsx in the events directory)
- This directory is for pages that don't fit into existing component directories
- Pages compose multiple components and handle page-level state
