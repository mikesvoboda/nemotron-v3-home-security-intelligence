# Alerts Components Directory

## Purpose

Contains components for viewing and managing high-priority security alerts. This page filters events to show only high and critical risk events that require immediate attention.

## Files

| File                  | Purpose                                       |
| --------------------- | --------------------------------------------- |
| `AlertsPage.tsx`      | Main alerts page showing high/critical events |
| `AlertsPage.test.tsx` | Test suite for AlertsPage                     |

## Key Components

### AlertsPage.tsx

**Purpose:** Displays a filtered view of security events focusing on high and critical risk levels

**Props Interface:**

```typescript
interface AlertsPageProps {
  onViewEventDetails?: (eventId: number) => void;
  className?: string;
}
```

**Key Features:**

- Fetches both high and critical risk events from API
- Combines and sorts events by timestamp (most recent first)
- Risk severity filter dropdown: All Alerts, Critical Only, High Only
- Refresh button with loading animation
- Risk count badges showing critical/high event counts
- Uses EventCard component from events/ for display
- Pagination with Previous/Next navigation
- Responsive grid: 1 col (mobile) -> 2 (lg) -> 3 (xl)

**State Management:**

```typescript
const [events, setEvents] = useState<Event[]>([]);
const [totalCount, setTotalCount] = useState(0);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
const [cameras, setCameras] = useState<Camera[]>([]);
const [pagination, setPagination] = useState({ limit: 20, offset: 0 });
const [riskFilter, setRiskFilter] = useState<'high' | 'critical' | 'all'>('all');
```

**Data Flow:**

1. Fetches cameras on mount for name lookup
2. Fetches high and critical events in parallel
3. Combines, sorts, and applies local filter
4. Converts Event to EventCard props format

**Loading States:**

- Loading: Spinner with "Loading alerts..." message
- Error: Red error card with error message
- Empty: Friendly "No Alerts at This Time" message with Bell icon

**Usage:**

```tsx
import AlertsPage from './components/alerts/AlertsPage';

<AlertsPage onViewEventDetails={(eventId) => openEventModal(eventId)} />;
```

## Important Patterns

### Dual API Fetch

The component fetches high and critical events separately to ensure both are included:

```typescript
const highResponse = await fetchEvents({ risk_level: 'high', ... });
const criticalResponse = await fetchEvents({ risk_level: 'critical', ... });
const allAlerts = [...highResponse.events, ...criticalResponse.events];
```

### Risk Count Calculation

Uses reduce to count events by risk level for summary badges:

```typescript
const riskCounts = events.reduce(
  (acc, event) => {
    const level = event.risk_level || getRiskLevel(event.risk_score || 0);
    acc[level] = (acc[level] || 0) + 1;
    return acc;
  },
  { critical: 0, high: 0, medium: 0, low: 0 }
);
```

### EventCard Integration

Transforms API Event to EventCard props:

```typescript
const getEventCardProps = (event: Event) => ({
  id: String(event.id),
  timestamp: event.started_at,
  camera_name: camera?.name || 'Unknown Camera',
  risk_score: event.risk_score || 0,
  risk_label: event.risk_level || getRiskLevel(event.risk_score || 0),
  summary: event.summary || 'No summary available',
  detections: [],
  started_at: event.started_at,
  ended_at: event.ended_at,
  onViewDetails: onViewEventDetails ? () => onViewEventDetails(event.id) : undefined,
});
```

## Styling Conventions

- Header: AlertTriangle icon in orange (#f97316)
- Filter bar: bg-[#1F1F1F], border-gray-800
- Filter dropdown: bg-[#1A1A1A], focus:border-[#76B900]
- Refresh button: bg-[#76B900]/10, text-[#76B900]
- Pagination: hover:bg-[#76B900]/10
- Grid: gap-6 between EventCards

## Testing

### AlertsPage.test.tsx

Tests cover:

- Initial loading state display
- Error state handling
- Empty state when no alerts
- Risk filter functionality
- Pagination controls
- Event count display
- Camera name resolution
- Risk badge rendering

## Dependencies

- `lucide-react` - AlertTriangle, Bell, ChevronLeft, ChevronRight, RefreshCw
- `react` - useState, useEffect
- `../../services/api` - fetchCameras, fetchEvents, Camera, Event, EventsQueryParams
- `../../utils/risk` - getRiskLevel, RiskLevel
- `../common/RiskBadge` - Risk level badge component
- `../events/EventCard` - Event display card

## API Endpoints Used

- `GET /api/cameras` - Fetch camera list for name lookup
- `GET /api/events?risk_level=high` - Fetch high risk events
- `GET /api/events?risk_level=critical` - Fetch critical risk events

## Entry Points

**Start here:** `AlertsPage.tsx` - Understand the alert filtering and display logic

## Future Enhancements

- Real-time alert notifications via WebSocket
- Sound/visual alerts for new critical events
- Alert acknowledgment workflow
- Alert escalation rules
- Email/SMS notification integration
- Custom alert thresholds per camera
