# Layout Components Directory

## Purpose

Contains the core application layout components that provide consistent structure, navigation, and branding across all pages. These components form the shell of the application and integrate with React Router for navigation.

## Key Components

### Layout.tsx

**Purpose:** Main layout wrapper that composes Header and Sidebar with page content

**Key Features:**

- Flex-based layout with fixed header and flexible content area
- Dark background (#0E0E0E) with proper overflow handling
- Sidebar on left, main content area takes remaining space
- Props: `children` (ReactNode)

**Pattern:**

```tsx
<Layout>
  <YourPage />
</Layout>
```

**Structure:**

```
+----------------------------------+
|            Header                |
+--------+-------------------------+
|        |                         |
|Sidebar |      Main Content       |
|        |                         |
|        |                         |
+--------+-------------------------+
```

### Header.tsx

**Purpose:** Top navigation bar with branding, system status indicators, and GPU stats

**Key Features:**

- NVIDIA Security branding with Activity icon in green box
- "POWERED BY NEMOTRON" tagline in NVIDIA green (#76B900)
- Real-time system status indicator with animated pulse dot
- Health states: "System Online" (green), "System Degraded" (yellow), "System Offline" (red), "Connecting..." (gray)
- GPU quick stats display showing utilization percentage and temperature
- Fixed height (h-16) with dark panel background (#1A1A1A)
- Border bottom for visual separation

**Hooks Used:**

- `useSystemStatus()` - WebSocket-based real-time system status

**GPU Stats Display:**

- Shows GPU utilization as percentage
- Shows GPU temperature in Celsius
- Displays "--" when not connected or data unavailable

**No props** - Uses hooks for data, fully self-contained component

### Sidebar.tsx

**Purpose:** Left navigation menu with route selection using React Router

**Key Features:**

- Navigation items defined in `navItems` array with id, label, icon, path, and optional badge
- Active state highlighting with NVIDIA green background (#76B900)
- Uses React Router's `NavLink` for client-side navigation
- Icons from lucide-react: Home, Clock, Users, Bell, ScrollText, Settings
- "WIP" badge on Entities route (yellow badge)
- Width: 256px (w-64) with dark panel background (#1A1A1A)

**Navigation Routes:**

| ID        | Label     | Icon       | Path        | Badge |
| --------- | --------- | ---------- | ----------- | ----- |
| dashboard | Dashboard | Home       | `/`         | -     |
| timeline  | Timeline  | Clock      | `/timeline` | -     |
| entities  | Entities  | Users      | `/entities` | WIP   |
| alerts    | Alerts    | Bell       | `/alerts`   | -     |
| logs      | Logs      | ScrollText | `/logs`     | -     |
| settings  | Settings  | Settings   | `/settings` | -     |

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

**No props** - Uses React Router's NavLink which handles active state internally

## Important Patterns

### Routing Integration

The Sidebar uses React Router's `NavLink` component:

- `to` prop specifies the route path
- `end` prop on root route (`/`) for exact matching
- `isActive` render prop provides active state for styling
- Client-side navigation with no page reload

```tsx
<NavLink
  to={item.path}
  end={item.path === '/'}
  className={({ isActive }) =>
    isActive ? 'bg-[#76B900] text-black' : 'text-gray-300'
  }
>
```

### Real-time System Status

Header displays real-time system status via WebSocket:

- `useSystemStatus()` hook provides `status` and `isConnected` state
- Status object includes: `health`, `gpu_utilization`, `gpu_temperature`
- Animated pulse dot indicates live connection
- Graceful fallback to "--" when data unavailable

### Styling

- All components use Tailwind CSS with NVIDIA dark theme
- Primary brand color: #76B900 (NVIDIA green)
- Dark backgrounds: #0E0E0E (darkest), #1A1A1A (panels)
- Gray borders: border-gray-800
- Hover states with subtle background changes

### Accessibility

- Semantic HTML elements (header, aside, main, nav)
- Proper button roles and labels
- Keyboard-accessible navigation (via React Router)
- Transition animations for state changes

## Testing

Tests are co-located with components:

- `Header.test.tsx` - Verifies branding, status indicators, GPU stats display, connection states
- `Layout.test.tsx` - Tests composition of Header, Sidebar, and children rendering
- `Sidebar.test.tsx` - Tests navigation items, active state, badges, route paths

## Entry Points

**Start here:** `Layout.tsx` - Understand how the shell is composed
**Then explore:** `Sidebar.tsx` - See navigation structure and route definitions
**Finally:** `Header.tsx` - Review branding, status displays, and real-time data

## Dependencies

- `lucide-react` - Icon components (Activity, Home, Clock, Users, Bell, ScrollText, Settings)
- `react` - ReactNode types
- `react-router-dom` - NavLink for client-side routing
- `../../hooks/useSystemStatus` - Real-time system status hook

## Component Hierarchy

```
Layout
├── Header
│   └── uses useSystemStatus hook
└── Sidebar
    └── NavLink (per navigation item)
```

## Future Enhancements

- Collapsible sidebar for more content space
- Breadcrumb navigation in Header for deep pages
- User profile/avatar in Header
- Notification bell with unread count
- Quick search in Header
- Theme toggle (dark/light mode)
- Mobile-responsive hamburger menu
