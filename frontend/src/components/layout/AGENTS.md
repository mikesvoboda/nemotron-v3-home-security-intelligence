# Layout Components Directory

## Purpose

Contains the core application layout components that provide consistent structure, navigation, and branding across all pages. These components form the shell of the application.

## Key Components

### Layout.tsx

**Purpose:** Main layout wrapper that composes Header and Sidebar with page content

**Key Features:**

- Flex-based layout with fixed header and flexible content area
- Manages navigation state (`activeNav`) shared between Sidebar and Header
- Dark background (#0E0E0E) with proper overflow handling
- Props: `children` (ReactNode)

**Pattern:**

```tsx
<Layout>
  <YourPage />
</Layout>
```

### Header.tsx

**Purpose:** Top navigation bar with branding and system status indicators

**Key Features:**

- NVIDIA Security branding with Activity icon in green box
- "POWERED BY NEMOTRON" tagline in NVIDIA green (#76B900)
- System status indicator (animated pulse dot + "System Online")
- GPU quick stats placeholder (will be populated in Phase 5)
- Fixed height (h-16) with dark panel background (#1A1A1A)
- Border bottom for visual separation

**No props** - fully self-contained component

### Sidebar.tsx

**Purpose:** Left navigation menu with route selection

**Key Features:**

- Navigation items defined in `navItems` array with id, label, icon, path, and optional badge
- Active state highlighting with NVIDIA green background (#76B900)
- Icons from lucide-react: Home, Clock, Users, Bell, Settings
- "WIP" badge on Entities route (yellow badge)
- Width: 256px (w-64) with dark panel background (#1A1A1A)

**Props:**

- `activeNav: string` - Currently active navigation ID
- `onNavChange: (navId: string) => void` - Callback when user clicks nav item

**Navigation Routes:**

- dashboard → `/` (Home icon)
- timeline → `/timeline` (Clock icon)
- entities → `/entities` (Users icon, WIP badge)
- alerts → `/alerts` (Bell icon)
- settings → `/settings` (Settings icon)

## Important Patterns

### State Management

- Layout component manages navigation state using `useState('dashboard')`
- State is passed down to Sidebar via props
- Allows for future integration with React Router or other routing solutions

### Styling

- All components use Tailwind CSS with NVIDIA dark theme
- Primary brand color: #76B900 (NVIDIA green)
- Dark backgrounds: #0E0E0E (darkest), #1A1A1A (panels)
- Gray borders: border-gray-800
- Hover states with subtle background changes

### Accessibility

- Semantic HTML elements (header, aside, main, nav)
- Proper button roles and labels
- Keyboard-accessible navigation

## Testing

Tests are co-located with components:

- `Header.test.tsx` - Verifies branding, status indicators, GPU stats placeholder
- `Layout.test.tsx` - Tests composition of Header, Sidebar, and children
- `Sidebar.test.tsx` - Tests navigation items, active state, badges, click handlers

## Entry Points

**Start here:** `Layout.tsx` - Understand how the shell is composed
**Then explore:** `Sidebar.tsx` - See navigation structure and route definitions
**Finally:** `Header.tsx` - Review branding and status displays

## Dependencies

- `lucide-react` - Icon components (Activity, Home, Clock, Users, Bell, Settings)
- `react` - useState, ReactNode types

## Future Enhancements

- Header GPU stats will be populated with real-time data in Phase 5
- Sidebar will integrate with React Router for actual routing
- May add breadcrumb navigation in Header for deep pages
