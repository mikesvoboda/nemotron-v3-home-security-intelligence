# Status Components Directory

## Purpose

Contains components for displaying AI service health and degradation status. These components provide visibility into the operational state of the AI pipeline services (RT-DETRv2, Nemotron, Florence-2, CLIP) and their circuit breaker states.

## Files

| File                       | Purpose                                                  | Status |
| -------------------------- | -------------------------------------------------------- | ------ |
| `AIServiceStatus.tsx`      | AI service health status display with expandable details | Active |
| `AIServiceStatus.test.tsx` | Test suite for AIServiceStatus (35 tests)                | Active |
| `AGENTS.md`                | Directory documentation                                  | Active |

## Key Components

### AIServiceStatus.tsx

**Purpose:** Display the health status of AI services with optional detailed breakdown per service

**Props Interface:**

```typescript
interface AIServiceStatusProps {
  showDetails?: boolean;      // Show per-service status (default: true)
  defaultExpanded?: boolean;  // Start details expanded (default: false)
  className?: string;         // Additional CSS classes
  compact?: boolean;          // Compact mode for header badge (default: false)
}
```

**Key Features:**

- Four degradation modes with distinct colors and icons
- Per-service status breakdown with circuit breaker state
- Expandable/collapsible details panel
- Compact badge mode for header/navbar display
- Shows failure counts and error messages for unhealthy services
- Displays available features based on service health
- Real-time updates via `useAIServiceStatus` hook (WebSocket)

**Degradation Modes:**

| Mode     | Icon          | Color  | Description                                     |
| -------- | ------------- | ------ | ----------------------------------------------- |
| normal   | CheckCircle   | green  | All AI services healthy and functioning         |
| degraded | AlertTriangle | yellow | Non-critical services (Florence-2, CLIP) down   |
| minimal  | AlertCircle   | orange | Critical services partially available           |
| offline  | XCircle       | red    | All AI services unavailable                     |

**Circuit Breaker States:**

| State     | Color  | Meaning                                |
| --------- | ------ | -------------------------------------- |
| closed    | green  | Normal operation, requests allowed     |
| half_open | yellow | Testing if service recovered           |
| open      | red    | Service failures, requests blocked     |

**AI Services Displayed:**

| Service   | Display Name | Description                           |
| --------- | ------------ | ------------------------------------- |
| rtdetr    | RT-DETRv2    | Object detection (persons, vehicles)  |
| nemotron  | Nemotron     | Risk analysis and LLM reasoning       |
| florence  | Florence-2   | Image captioning and OCR              |
| clip      | CLIP         | Entity re-identification              |

**Subcomponents:**

- `ServiceStatusRow` - Individual service status row with icon, circuit state badge, and error info
- `FeaturesList` - List of currently available features with Zap icons
- `CompactBadge` - Minimal badge for header display (shows mode only)

**Usage:**

```tsx
import { AIServiceStatus } from '../status/AIServiceStatus';

// Full panel with expandable details (default)
<AIServiceStatus />

// Start expanded
<AIServiceStatus defaultExpanded={true} />

// No expand/collapse, always show header only
<AIServiceStatus showDetails={false} />

// Compact badge for navbar/header
<AIServiceStatus compact={true} />

// With custom styling
<AIServiceStatus className="mb-4" defaultExpanded={true} />
```

**Display Modes:**

1. **Full Panel (default):** Shows degradation mode with expandable service details
2. **Header Only:** Shows degradation mode without expand/collapse (`showDetails={false}`)
3. **Compact Badge:** Minimal badge showing only the mode label (`compact={true}`)

**Data Flow:**

```
WebSocket (/ws/events)
    ↓
useAIServiceStatus hook
    ↓
AIServiceStatus component
    ├── ServiceStatusRow (x4)
    │   └── Circuit state badges
    └── FeaturesList
        └── Available feature chips
```

**Dependencies:**

- `clsx` - Conditional class composition
- `lucide-react` - Icons (Activity, AlertCircle, AlertTriangle, CheckCircle, ChevronDown, ChevronUp, Clock, RefreshCw, XCircle, Zap)
- `react` - useState hook
- `../../hooks/useAIServiceStatus` - WebSocket hook for AI service status

---

## Testing

### AIServiceStatus.test.tsx

**Test Coverage (35 tests in 10 describe blocks):**

**Normal mode:**
- Renders normal status header with "All Systems Operational"
- Applies green styling for normal mode

**Degraded mode:**
- Renders degraded status header with "Degraded Mode"
- Applies yellow styling for degraded mode

**Minimal mode:**
- Renders minimal status header with "Minimal Mode"
- Applies orange styling for minimal mode

**Offline mode:**
- Renders offline status header with "AI Services Offline"
- Applies red styling for offline mode

**Expandable details:**
- Expands to show service details when clicked
- Renders expanded by default when `defaultExpanded` is true
- Does not render expand button when `showDetails` is false

**Service status rows:**
- Shows circuit breaker state badges (Closed, Half-Open, Open)
- Shows failure count for unhealthy services
- Shows error message for unavailable services

**Available features list:**
- Renders available features when expanded

**Compact mode:**
- Renders as compact badge when `compact` is true
- Shows degradation status in compact badge

**Last update timestamp:**
- Shows last update time with relative formatting

**Loading state:**
- Shows loading text for services with null state

**Mocking Pattern:**

```typescript
const mockUseAIServiceStatus = vi.fn();

vi.mock('../../hooks/useAIServiceStatus', async () => {
  const actual = await vi.importActual('../../hooks/useAIServiceStatus');
  return {
    ...actual,
    useAIServiceStatus: () => mockUseAIServiceStatus(),
  };
});
```

---

## Important Patterns

### Real-time WebSocket Updates

The component receives real-time updates via the `useAIServiceStatus` hook which subscribes to the `/ws/events` WebSocket channel and filters for `ai_service_status` message types.

### Graceful Degradation Display

The component visually communicates system health at a glance:
- Green = fully operational
- Yellow = minor issues (non-critical services)
- Orange = significant issues (critical services partially affected)
- Red = AI pipeline offline

### Compact vs Full Modes

Use `compact={true}` for space-constrained areas (header, navbar) and the full panel for dedicated system monitoring pages.

### Timestamp Formatting

Uses relative time formatting ("5s ago", "2m ago", "1h ago") for recent updates and full date format for older timestamps.

---

## Entry Points

**Start here:** `AIServiceStatus.tsx` - Main component for AI service health display

**Used by:**
- `SystemMonitoringPage.tsx` - Full panel on system monitoring page
- `Header.tsx` - Compact badge in application header (optional)

**Dependencies:**
- `useAIServiceStatus` hook - See `frontend/src/hooks/useAIServiceStatus.ts`
- Backend `AIFallbackService` - Broadcasts `ai_service_status` messages
