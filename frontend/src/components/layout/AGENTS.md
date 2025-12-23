# Layout Components

## Purpose

Core application layout components that provide the structural framework for the entire app, including navigation, header, and page wrapper.

## Components

### Layout

Main layout wrapper that composes the header, sidebar, and content area.

**File:** `Layout.tsx`

**Props Interface:**

```typescript
interface LayoutProps {
  children: ReactNode; // Main content area
}
```

**Features:**

- Flexbox-based layout structure
- Fixed header at top
- Sidebar + main content in horizontal flex
- Dark theme background (`#0E0E0E`)
- Responsive overflow handling
- Navigation state management

**Structure:**

```
Layout
├── Header (fixed top)
└── Flex container
    ├── Sidebar (fixed width)
    └── Main content (flex-1, scrollable)
```

**Usage:**

```typescript
import Layout from '@/components/layout/Layout';

<Layout>
  <DashboardPage />
</Layout>
```

### Header

Top navigation bar with branding, status indicators, and quick stats.

**File:** `Header.tsx`

**Props Interface:**

```typescript
// No props - standalone component
```

**Features:**

- NVIDIA branding with green accent color
- Logo icon using `Activity` from `lucide-react`
- Two-line branding:
  - "NVIDIA SECURITY" (primary)
  - "POWERED BY NEMOTRON" (secondary, green)
- System status indicator (green pulsing dot)
- GPU stats placeholder (ready for integration)
- Dark panel background (`#1A1A1A`)
- Bottom border separation

**Layout:**

- Height: 64px (`h-16`)
- Flex layout with space-between
- Left: Logo and title
- Right: Status and GPU stats

### Sidebar

Vertical navigation menu with icons, labels, and active state.

**File:** `Sidebar.tsx`

**Props Interface:**

```typescript
interface SidebarProps {
  activeNav: string; // Current active navigation ID
  onNavChange: (navId: string) => void; // Navigation callback
}
```

**Navigation Items:**

```typescript
interface NavItem {
  id: string; // Unique identifier
  label: string; // Display text
  icon: ComponentType; // Lucide icon
  badge?: string; // Optional badge (e.g., "WIP")
  path: string; // Route path
}
```

**Default Navigation:**

- Dashboard (`/`) - Home icon
- Timeline (`/timeline`) - Clock icon
- Entities (`/entities`) - Users icon, "WIP" badge
- Alerts (`/alerts`) - Bell icon
- Settings (`/settings`) - Settings icon

**Features:**

- Active state highlighting with NVIDIA green (`#76B900`)
- Hover effects on inactive items
- Icon + label layout
- Optional badges for in-progress features
- Full-width buttons with padding
- Smooth transitions (200ms)

**Styling:**

- Width: 256px (`w-64`)
- Dark panel background (`#1A1A1A`)
- Right border separation
- Active: Green background, black text, bold
- Inactive: Gray text, hover gray background

## Layout System

The three components work together to create the app shell:

1. **Layout** wraps entire app and manages layout structure
2. **Header** provides branding and global status
3. **Sidebar** handles primary navigation

All page components are rendered as children of Layout:

```typescript
// App.tsx or Router
<Layout>
  <Routes>
    <Route path="/" element={<DashboardPage />} />
    <Route path="/timeline" element={<TimelinePage />} />
    {/* ... */}
  </Routes>
</Layout>
```

## Styling Approach

- **Tailwind CSS** for all styling
- **Lucide React** for icons
- Dark theme palette:
  - Base background: `#0E0E0E`
  - Panel background: `#1A1A1A`
  - Primary (NVIDIA green): `#76B900`
  - Border: `gray-800`
- Flexbox layouts throughout
- Fixed header and sidebar, scrollable content
- Consistent spacing and padding

## Test Files

**Location:** Co-located with components

- `Layout.test.tsx` - Tests for layout structure and children rendering
- `Header.test.tsx` - Tests for header elements, branding, status indicators
- `Sidebar.test.tsx` - Tests for navigation rendering, active state, interactions

**Coverage Requirements:**

- Component rendering
- Navigation state management
- Active state styling
- Click interactions
- Icon and badge display
- Accessibility (semantic HTML, ARIA labels, keyboard navigation)
- Responsive behavior

## Integration Points

Layout components integrate with:

- **React Router** - Navigation paths and active route detection
- **WebSocket hooks** (future) - Real-time status updates in header
- **GPU monitoring service** (future) - GPU stats in header
- **Theme system** - Consistent dark theme application
