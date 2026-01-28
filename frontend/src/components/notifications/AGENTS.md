# Notifications Components

## Purpose

Components for displaying and managing notification delivery history in the NVIDIA Security Intelligence dashboard. Provides visibility into notification delivery attempts across email, webhook, and push channels.

## Key Components

| File                                 | Purpose                                          |
| ------------------------------------ | ------------------------------------------------ |
| `NotificationHistoryPanel.tsx`       | Paginated table of notification delivery history |
| `NotificationHistoryPanel.test.tsx`  | Test suite for NotificationHistoryPanel          |
| `index.ts`                           | Barrel exports for notification components       |

## Component Details

### NotificationHistoryPanel

A card component displaying notification delivery history with filtering and pagination capabilities.

**Props:**

| Prop        | Type       | Default | Description                                    |
| ----------- | ---------- | ------- | ---------------------------------------------- |
| `className` | `string?`  | -       | Optional CSS class name                        |
| `alertId`   | `string?`  | -       | Optional alert ID to filter by                 |
| `pageSize`  | `number?`  | `10`    | Number of entries per page                     |

**Features:**

- **Filtering:** Filter by channel (email/webhook/push) and status (success/failed)
- **Pagination:** Navigate through history pages with Previous/Next buttons
- **Real-time Refresh:** Manual refresh button with loading indicator
- **Channel Display:** Color-coded badges with icons for each channel type
- **Status Indicators:** Green checkmark for success, red X for failed
- **Error Details:** Truncated error messages with full text on hover
- **Empty States:** Different messages for no history vs. filtered results

**Channel Configuration:**

| Channel   | Icon          | Color   |
| --------- | ------------- | ------- |
| `email`   | Mail          | blue    |
| `webhook` | Webhook       | purple  |
| `push`    | AlertCircle   | orange  |

**Usage:**

```tsx
import { NotificationHistoryPanel } from '@/components/notifications';

// Basic usage
<NotificationHistoryPanel />

// With custom page size
<NotificationHistoryPanel pageSize={25} />

// For a specific alert
<NotificationHistoryPanel alertId="alert-123" />
```

## Test Coverage

The test suite covers:

- Component rendering with title
- Loading state display
- Empty state when no history exists
- Rendering history entries in table format
- Table header display
- Error state handling
- Filter dropdowns rendering
- Refresh button functionality
- API call parameters verification
- Alert ID filtering
- Pagination controls
- Custom className application
- Text truncation for long values

## Dependencies

- `@tremor/react` - Card, Title, Text, Badge, Select, SelectItem, Button
- `lucide-react` - Icons (AlertCircle, CheckCircle, ChevronLeft/Right, etc.)
- `../../hooks/useNotificationHistoryQuery` - Data fetching hook
- `clsx` - Conditional class composition

## Data Flow

```
useNotificationHistoryQuery (hook)
    |
    v
NotificationHistoryPanel (filters, pagination state)
    |
    v
Table rows (channel badge, status badge, error display)
```

## Styling

Uses Tremor components with NVIDIA dark theme overrides:

- Panel background: `bg-[#1A1A1A]`
- Border: `border-gray-800`
- NVIDIA green accent: `#76B900` for icons and active states
- Table headers: `text-gray-400`, `bg-gray-800/50` on hover
