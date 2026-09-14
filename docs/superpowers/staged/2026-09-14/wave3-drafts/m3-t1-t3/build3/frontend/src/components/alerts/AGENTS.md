# Alerts Components Directory

## Purpose

Contains components for viewing and managing high-priority security alerts. The alert system has been redesigned with a modular architecture separating concerns into focused components. Alerts filter events to show only high and critical risk events requiring immediate attention, and support alert rule configuration for customized notification triggers.

## Architecture Overview

The alert system follows a modular component architecture:

```
AlertsPage (main orchestrator)
├── AlertFilters (severity-based filtering with counts)
├── AlertActions (bulk operations toolbar)
├── AlertCard (individual alert display with actions)
│   └── RiskBadge (severity indicator)
├── EventCard (event display - reused from events/)
└── EventDetailModal (full event details - reused from events/)

AlertForm / AlertRuleForm (alert rule configuration)
└── Zod validation schemas (backend-aligned validation)
```

## Files

| File                       | Purpose                                              |
| -------------------------- | ---------------------------------------------------- |
| `AlertsPage.tsx`           | Main alerts page with infinite scroll and filtering  |
| `AlertsPage.test.tsx`      | Test suite for AlertsPage                            |
| `AlertCard.tsx`            | Individual alert card with acknowledge/dismiss/snooze|
| `AlertCard.test.tsx`       | Test suite for AlertCard                             |
| `AlertActions.tsx`         | Bulk operation controls (select all, acknowledge)    |
| `AlertActions.test.tsx`    | Test suite for AlertActions                          |
| `AlertFilters.tsx`         | Severity-based filter buttons with counts            |
| `AlertFilters.test.tsx`    | Test suite for AlertFilters                          |
| `AlertForm.tsx`            | Alert rule form (basic validation)                   |
| `AlertForm.test.tsx`       | Test suite for AlertForm                             |
| `AlertRuleForm.tsx`        | Alert rule form with Zod/react-hook-form validation  |
| `AlertRuleForm.test.tsx`   | Test suite for AlertRuleForm                         |
| `index.ts`                 | Barrel exports for all components and types          |

## Key Components

### AlertsPage.tsx

**Purpose:** Main page component orchestrating alert display with infinite scroll pagination

**Props Interface:**

```typescript
interface AlertsPageProps {
  onViewEventDetails?: (eventId: number) => void;
  className?: string;
}
```

**Key Features:**

- Cursor-based pagination with infinite scroll for efficient large dataset loading
- Risk severity filter dropdown: All Alerts, Critical Only, High Only
- Refresh button with loading animation
- Risk count badges showing critical/high event counts
- Uses EventCard component from events/ for display
- Event detail modal with navigation
- Snooze functionality per alert
- Responsive grid: 1 col (mobile) -> 2 (lg) -> 3 (xl)

**Hooks Used:**

- `useAlertsInfiniteQuery` - Fetches alerts with cursor pagination
- `useInfiniteScroll` - Manages infinite scroll sentinel
- `useCamerasQuery` - Camera name lookup
- `useSnoozeEvent` - Snooze mutation

**Loading States:**

- Loading: Spinner with "Loading alerts..." message
- Error: Red error card with error message
- Empty: Friendly "No Alerts at This Time" message with Bell icon
- Loading more: "Loading more alerts..." with spinner at bottom

### AlertCard.tsx

**Purpose:** Individual alert display card with actionable buttons for acknowledge, dismiss, snooze, and view

**Props Interface:**

```typescript
interface AlertCardProps {
  id: string;
  eventId: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'pending' | 'delivered' | 'acknowledged' | 'dismissed';
  timestamp: string;
  camera_name: string;
  risk_score: number;
  summary: string;
  dedup_key: string;
  selected?: boolean;
  onAcknowledge?: (alertId: string) => void;
  onDismiss?: (alertId: string) => void;
  onSnooze?: (alertId: string, seconds: number) => void;
  onViewEvent?: (eventId: number) => void;
  onSelectChange?: (alertId: string, selected: boolean) => void;
}
```

**Key Features:**

- Severity-based styling with colored left accent bar
- Status badges (Unacknowledged/Acknowledged)
- Relative timestamp formatting ("5 minutes ago", "2 hours ago")
- Action buttons: Acknowledge, Dismiss, View Event
- Snooze dropdown with preset durations (15min, 30min, 1hr, 4hr)
- Checkbox for bulk selection
- Memoized with `React.memo` for performance

**Severity Styling:**

- Critical: red-600 border, red-950/20 background
- High: orange-500 border, orange-950/20 background
- Medium: yellow-500 border, yellow-950/20 background
- Low: blue-500 border, blue-950/20 background

### AlertActions.tsx

**Purpose:** Bulk operation toolbar for selected alerts

**Props Interface:**

```typescript
interface AlertActionsProps {
  selectedCount: number;
  totalCount: number;
  hasUnacknowledged: boolean;
  onSelectAll: (selectAll: boolean) => void;
  onAcknowledgeSelected: () => void;
  onDismissSelected: () => void;
  onClearSelection: () => void;
}
```

**Key Features:**

- Select/Deselect All toggle with visual feedback
- Selection count display
- Acknowledge Selected button (only if unacknowledged alerts selected)
- Dismiss Selected button
- Clear Selection link
- Hidden when no alerts exist
- Memoized for performance

### AlertFilters.tsx

**Purpose:** Severity-based filter buttons with count badges

**Props Interface:**

```typescript
type AlertFilterType = 'all' | 'critical' | 'high' | 'medium' | 'unread';

interface AlertFilterCounts {
  all: number;
  critical: number;
  high: number;
  medium: number;
  unread: number;
}

interface AlertFiltersProps {
  activeFilter: AlertFilterType;
  onFilterChange: (filter: AlertFilterType) => void;
  counts: AlertFilterCounts;
}
```

**Key Features:**

- Color-coded filter buttons (NVIDIA green for All, red for Critical, etc.)
- Count badges showing number of alerts per category
- Disabled state for filters with zero count
- aria-pressed for accessibility
- Memoized for performance
- Uses darker green (#4B7600) for WCAG AA color contrast compliance

### AlertForm.tsx

**Purpose:** Reusable form for creating and editing alert rules with basic validation

**Props Interface:**

```typescript
interface AlertFormProps {
  initialData?: Partial<AlertFormData>;
  cameras?: CameraOption[];
  onSubmit: (data: AlertFormData) => void | Promise<void>;
  onCancel: () => void;
  isSubmitting?: boolean;
  submitText?: string;
  apiError?: string | null;
  onClearApiError?: () => void;
}
```

**Form Sections:**

1. **Basic Information:** Name, description, enabled toggle, severity
2. **Trigger Conditions:** Risk threshold, min confidence, object types, cameras
3. **Schedule:** Days, start/end time, timezone
4. **Notifications:** Channels (email, webhook, pushover), cooldown

**Validation:**

- Uses centralized validation utilities from `../../utils/validation`
- Validation rules align with backend Pydantic schemas

### AlertRuleForm.tsx

**Purpose:** Enhanced alert rule form using Zod schemas and react-hook-form for robust validation

**Props Interface:**

```typescript
interface AlertRuleFormProps {
  initialData?: Partial<AlertRuleFormData>;
  onSubmit: (data: AlertRuleFormOutput) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
  submitText?: string;
  apiError?: string | null;
  onClearApiError?: () => void;
  cameras?: Camera[];
  camerasLoading?: boolean;
  camerasError?: string | null;
  onRetryCameras?: () => void;
}
```

**Key Features:**

- Zod validation schemas mirroring backend Pydantic schemas
- react-hook-form with zodResolver for form state management
- Real-time validation feedback
- Camera loading states with retry capability
- Zone support (zone_ids field)
- Headless UI Switch components for toggles

## Important Patterns

### Infinite Scroll Pattern

AlertsPage uses cursor-based pagination with infinite scroll:

```typescript
const {
  alerts,
  totalCount,
  isLoading,
  hasNextPage,
  fetchNextPage,
} = useAlertsInfiniteQuery({ riskFilter, limit: 25 });

const { sentinelRef, isLoadingMore } = useInfiniteScroll({
  onLoadMore: fetchNextPage,
  hasMore: hasNextPage,
  isLoading: isFetchingNextPage,
});
```

### Memoization Pattern

Components use `React.memo` for performance optimization:

```typescript
const AlertCard = memo(function AlertCard({ ... }: AlertCardProps) {
  // Component implementation
});
```

### Camera Name Lookup

Efficient Map-based camera name resolution:

```typescript
const cameraNameMap = useMemo(() => {
  const map = new Map<string, string>();
  cameras.forEach((camera) => {
    map.set(camera.id, camera.name);
  });
  return map;
}, [cameras]);
```

### Risk Count Calculation

Aggregates alerts by risk level for filter badges:

```typescript
const riskCounts = useMemo(() => {
  return alerts.reduce(
    (acc, event) => {
      const level = event.risk_level || getRiskLevel(event.risk_score || 0);
      acc[level] = (acc[level] || 0) + 1;
      return acc;
    },
    { critical: 0, high: 0, medium: 0, low: 0 }
  );
}, [alerts]);
```

### Form Validation Alignment

AlertRuleForm uses Zod schemas that mirror backend Pydantic:

```typescript
import { alertRuleFormSchema, type AlertRuleFormOutput } from '../../schemas/alertRule';

const {
  register,
  handleSubmit,
  control,
  formState: { errors },
} = useForm<AlertRuleFormInput>({
  resolver: zodResolver(alertRuleFormSchema),
  mode: 'onBlur',
});
```

## Data Flow

```
useAlertsInfiniteQuery (TanStack Query)
         |
         v
    AlertsPage
    /    |    \
   /     |     \
AlertFilters  AlertActions  EventCard[]
   |                           |
   v                           v
(filter change)         EventDetailModal
   |                           |
   v                           v
refetch()               (mark reviewed, navigation)
```

## Styling Conventions

### AlertCard

- Card background: severity-based (e.g., bg-red-950/20 for critical)
- Left accent bar: severity color (e.g., bg-red-600)
- Action buttons: contextual colors (green for acknowledge, gray for dismiss)
- NVIDIA green (#76B900) for "View Event" button

### AlertFilters

- All: #4B7600 (darker NVIDIA green for WCAG AA)
- Critical: red-700
- High: orange-600
- Medium: yellow-600
- Unread: blue-600
- Inactive: gray-800/30
- Disabled: gray-800/50, cursor-not-allowed

### AlertActions

- Container: bg-[#1F1F1F], border-gray-800
- Buttons: consistent with AlertCard action styling
- Dividers: h-5 w-px bg-gray-700

### AlertForm / AlertRuleForm

- Section headers: text-sm font-semibold with icons
- Inputs: bg-card, border-gray-700, focus:border-primary
- Toggle switches: Headless UI Switch with NVIDIA green
- Chip buttons: rounded-full for multi-select options

## Testing

Test files provide comprehensive coverage:

- **AlertsPage.test.tsx:** Infinite scroll, filtering, loading states, error handling
- **AlertCard.test.tsx:** Severity styling, actions, snooze dropdown, selection
- **AlertActions.test.tsx:** Select all, bulk operations, disabled states
- **AlertFilters.test.tsx:** Filter clicks, counts, active states, accessibility
- **AlertForm.test.tsx:** Validation, submission, error display
- **AlertRuleForm.test.tsx:** Zod validation, camera loading, schedule toggle

## Dependencies

- `lucide-react` - Icons (AlertTriangle, Bell, Check, X, Eye, Clock, ChevronDown, etc.)
- `react` - useState, useMemo, memo
- `clsx` - Conditional class composition
- `@headlessui/react` - Switch for toggles (AlertRuleForm)
- `@hookform/resolvers/zod` - Zod integration for react-hook-form
- `react-hook-form` - Form state management (AlertRuleForm)
- `../../hooks` - useAlertsInfiniteQuery, useInfiniteScroll, useCamerasQuery, useSnoozeEvent
- `../../services/api` - updateEvent, Camera, Event types
- `../../utils/risk` - getRiskLevel, RiskLevel
- `../../utils/validation` - Centralized validation utilities (AlertForm)
- `../../schemas/alertRule` - Zod validation schemas (AlertRuleForm)
- `../common/RiskBadge` - Risk level badge component
- `../events/EventCard` - Event display card
- `../events/EventDetailModal` - Full event details modal

## API Endpoints Used

- `GET /api/events?risk_level=high|critical` - Fetch alerts (via useAlertsInfiniteQuery)
- `GET /api/cameras` - Camera list for name lookup and form options
- `PATCH /api/events/{id}` - Update event (mark reviewed, snooze)

## Entry Points

**Start here:** `AlertsPage.tsx` - Main orchestrator with infinite scroll and filtering
**Components:** `AlertCard.tsx` - Individual alert with actions and severity styling
**Bulk ops:** `AlertActions.tsx` - Understand bulk selection and operations
**Filtering:** `AlertFilters.tsx` - Severity-based filter buttons
**Forms:** `AlertRuleForm.tsx` - Zod-validated alert rule configuration

## Exports

The `index.ts` barrel exports all components and types:

```typescript
export { default as AlertsPage } from './AlertsPage';
export { default as AlertCard } from './AlertCard';
export { default as AlertActions } from './AlertActions';
export { default as AlertFilters } from './AlertFilters';

export type { AlertsPageProps } from './AlertsPage';
export type { AlertCardProps } from './AlertCard';
export type { AlertActionsProps } from './AlertActions';
export type { AlertFiltersProps, AlertFilterType, AlertFilterCounts } from './AlertFilters';
```

## Future Enhancements

- Real-time alert notifications via WebSocket
- Sound/visual alerts for new critical events
- Alert escalation rules
- Email/SMS notification integration via channels
- Custom alert thresholds per camera/zone
- Alert grouping by dedup_key
- Alert history and audit trail
