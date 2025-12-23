# Dashboard Components

## Purpose

Components specific to the main dashboard page, including the primary monitoring view and dashboard-specific widgets.

## Components

### DashboardPage

Main dashboard page component that serves as the primary monitoring interface.

**File:** `DashboardPage.tsx`

**Props Interface:**

```typescript
// Currently no props - standalone page component
```

**Current Status:**

- **Minimal implementation** - Currently a placeholder with basic layout
- Displays "Dashboard" heading in 3xl bold text
- Ready for Phase 6 feature additions:
  - Risk gauge display
  - Camera grid with live feeds
  - Live activity feed
  - GPU statistics panel
  - Recent events list

**Planned Features (Phase 6):**

- Real-time risk scoring gauge (0-100)
- Multi-camera grid view with detection overlays
- Live activity feed with WebSocket updates
- GPU utilization and temperature monitoring
- Recent security events timeline
- Quick actions panel

**Usage:**

```typescript
import DashboardPage from '@/components/dashboard/DashboardPage';

<DashboardPage />
```

## Directory Structure

Currently contains only the main page component. As Phase 6 progresses, will be expanded with:

- `RiskGauge.tsx` - Visual risk score display
- `CameraGrid.tsx` - Multi-camera live view
- `ActivityFeed.tsx` - Real-time event stream
- `GPUStats.tsx` - GPU monitoring widget
- `QuickActions.tsx` - Common security actions

## Styling Approach

- **Tailwind CSS** for layout and styling
- **Tremor** components for data visualization (gauges, charts)
- Dark theme consistent with app design:
  - Background: `#0E0E0E`
  - Panel backgrounds: `#1A1A1A`
  - NVIDIA green accents: `#76B900`
- Responsive grid layouts for camera feeds
- Card-based design for widgets

## Test Files

**Location:** Co-located with components

- `DashboardPage.test.tsx` - Tests for dashboard page rendering and layout

**Coverage Requirements:**

- Page renders without errors
- Layout structure is correct
- Integration with WebSocket hooks (once implemented)
- Data fetching and display (once API integration complete)
- Responsive behavior across screen sizes
