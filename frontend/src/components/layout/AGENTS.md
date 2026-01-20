# Layout Components Directory

## Purpose

Contains the core application layout components that provide consistent structure, navigation, and branding across all pages. These components form the shell of the application and integrate with React Router for navigation.

## Files

| File                          | Purpose                                        |
| ----------------------------- | ---------------------------------------------- |
| `Header.tsx`                  | Top navigation with branding and status        |
| `Header.test.tsx`             | Test suite for Header                          |
| `Layout.tsx`                  | Main layout wrapper composing Header + Sidebar |
| `Layout.test.tsx`             | Test suite for Layout                          |
| `MobileBottomNav.tsx`         | Bottom navigation bar for mobile devices       |
| `MobileBottomNav.test.tsx`    | Test suite for MobileBottomNav                 |
| `Sidebar.tsx`                 | Left navigation menu with route links          |
| `Sidebar.test.tsx`            | Test suite for Sidebar                         |

## Key Components

### Layout.tsx

**Purpose:** Main layout wrapper that composes Header and Sidebar with page content

**Props Interface:**

```typescript
interface LayoutProps {
  children: ReactNode;
}
```

**Structure:**

```
+----------------------------------+
|            Header (h-16)         |
+--------+-------------------------+
|        |                         |
|Sidebar |      Main Content       |
| (w-64) |       (flex-1)          |
|        |                         |
+--------+-------------------------+
```

**Implementation:**

```tsx
<div className="flex min-h-screen flex-col bg-[#0E0E0E]">
  <Header />
  <div className="flex flex-1 overflow-hidden">
    <Sidebar />
    <main className="flex-1 overflow-auto">{children}</main>
  </div>
</div>
```

**Usage:**

```tsx
<Layout>
  <DashboardPage />
</Layout>
```

---

### Header.tsx

**Purpose:** Top navigation bar with branding, system health status, and GPU quick stats

**Key Features:**

- NVIDIA Security branding with Activity icon in green (#76B900) box
- "POWERED BY NEMOTRON" tagline
- Real-time system health indicator with tooltip showing per-service status
- GPU quick stats display (utilization % and temperature)
- Fixed height: h-16 (64px)
- Dark panel background: #1A1A1A

**Health Status Indicator:**

| Status     | Dot Color | Label           | Animation     |
| ---------- | --------- | --------------- | ------------- |
| healthy    | green     | LIVE MONITORING | animate-pulse |
| degraded   | yellow    | System Degraded | none          |
| unhealthy  | red       | System Offline  | none          |
| connecting | gray      | Connecting...   | none          |
| checking   | gray      | Checking...     | none          |

**Health Tooltip:**

On hover, displays per-service status breakdown (redis, rtdetr, nemotron, etc.) with colored status dots.

**GPU Stats Display:**

- Shows: `{utilization}% | {temperature}C`
- Displays "--" when not connected or data unavailable
- Styled in NVIDIA green (#76B900)

**Hooks Used:**

- `useSystemStatus()` - WebSocket-based real-time system status (health, gpu_utilization, gpu_temperature)
- `useHealthStatus()` - REST API health check with per-service breakdown

**No props** - Self-contained component using hooks for all data

---

### Sidebar.tsx

**Purpose:** Left navigation menu with route selection using React Router

**Key Features:**

- Navigation items with icon, label, and optional badge
- Active state highlighting with NVIDIA green background
- Uses React Router's `NavLink` for client-side navigation
- Width: w-64 (256px)
- Dark panel background: #1A1A1A

**Navigation Routes:**

| ID          | Label          | Icon           | Path         | Badge |
| ----------- | -------------- | -------------- | ------------ | ----- |
| dashboard   | Dashboard      | Home           | `/`          | -     |
| timeline    | Timeline       | Clock          | `/timeline`  | -     |
| entities    | Entities       | Users          | `/entities`  | -     |
| alerts      | Alerts         | Bell           | `/alerts`    | -     |
| analytics   | Analytics      | BarChart3      | `/analytics` | -     |
| ai-audit    | AI Audit       | ClipboardCheck | `/ai-audit`  | -     |
| ai          | AI Performance | Brain          | `/ai`        | -     |
| jobs        | Jobs           | Briefcase      | `/jobs`      | -     |
| operations  | Pipeline       | Workflow       | `/operations`| -     |
| logs        | Logs           | ScrollText     | `/logs`      | -     |
| audit       | Audit Log      | Shield         | `/audit`     | -     |
| trash       | Trash          | Trash2         | `/trash`     | -     |
| settings    | Settings       | Settings       | `/settings`  | -     |

**NavItem Interface:**

```typescript
interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType;
  badge?: string;
  path: string;
}
```

**Active State Styling:**

- Active: `bg-[#76B900] font-semibold text-black`
- Inactive: `text-gray-300 hover:bg-gray-800 hover:text-white`

**Routing Integration:**

```tsx
<NavLink
  to={item.path}
  end={item.path === '/'}  // Exact match for root route
  className={({ isActive }) => isActive ? activeStyles : inactiveStyles}
>
```

**Mobile Responsiveness:**

- Hidden by default on mobile (slides in from left)
- Controlled by `useSidebarContext` hook
- Close button on mobile to dismiss menu
- Auto-closes when navigation link is clicked

**No props** - Uses React Router's NavLink and useSidebarContext hook

## Important Patterns

### Real-time System Status

Header displays real-time system status via two sources:

1. **WebSocket** (`useSystemStatus`) - Live updates for health, GPU metrics
2. **REST API** (`useHealthStatus`) - Periodic health checks with service breakdown

API health takes precedence when available, with WebSocket as fallback.

### Tooltip Pattern

The health indicator uses a hover tooltip with delay:

- Show on mouseEnter (immediate)
- Hide on mouseLeave (150ms delay to allow mouse to move to tooltip)

### Styling Conventions

- All components use Tailwind CSS with NVIDIA dark theme
- Primary brand color: #76B900 (NVIDIA green)
- Dark backgrounds: #0E0E0E (darkest), #1A1A1A (panels)
- Gray borders: border-gray-800
- Hover states with subtle background changes

### Accessibility

- Semantic HTML elements (header, aside, main, nav)
- Health tooltip has `role="tooltip"` and `data-testid` for testing
- Keyboard-accessible navigation via React Router
- Status indicators have appropriate aria-labels

## Testing

### Layout.test.tsx

- Renders Header and Sidebar
- Renders children in main content area
- Proper structure and classes

### Header.test.tsx

- Branding elements present
- Health status indicator with correct colors
- GPU stats display with formatting
- Tooltip visibility on hover
- Connection state handling

### Sidebar.test.tsx

- All navigation items rendered
- Correct route paths
- Active state styling
- Badge rendering (WIP on Entities)
- Icon rendering

## Component Hierarchy

```
Layout
├── Header
│   ├── Branding (logo + text)
│   ├── HealthIndicator (with HealthTooltip)
│   │   └── uses useSystemStatus, useHealthStatus hooks
│   └── GPU Stats display
└── Sidebar
    └── NavLink (per navigation item)
        └── Icon + Label + Badge
```

## Dependencies

- `lucide-react` - Activity, Home, Clock, Users, Bell, ScrollText, Server, Settings, Shield, Brain, ClipboardCheck, X icons
- `react` - useState, useRef, useEffect, ReactNode
- `react-router-dom` - NavLink for client-side routing
- `../../hooks/useSystemStatus` - WebSocket system status
- `../../hooks/useHealthStatus` - REST API health status
- `../../hooks/useSidebarContext` - Mobile sidebar state management

## Entry Points

**Start here:** `Layout.tsx` - Understand how the shell is composed
**Then explore:** `Sidebar.tsx` - See navigation structure and routes
**Finally:** `Header.tsx` - Review branding and real-time status display
