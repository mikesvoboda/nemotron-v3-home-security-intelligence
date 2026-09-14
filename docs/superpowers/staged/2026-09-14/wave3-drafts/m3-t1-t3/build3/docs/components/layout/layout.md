# Layout Components

> Application shell and navigation components.

---

## Overview

The layout system provides the application shell including header, sidebar navigation, and responsive content area. All pages are rendered within this shell.

## Architecture

```
Layout
├── SkipLink (accessibility)
├── Header
│   ├── Branding
│   ├── WebSocketStatus
│   ├── ServiceStatusIndicator
│   ├── ThemeToggle
│   └── CommandPalette trigger
├── Sidebar
│   ├── Navigation links
│   ├── Active route indicator
│   └── Collapse toggle
├── Main content area
│   └── Page components (via React Router)
└── MobileBottomNav (mobile only)
```

---

## Components

### Layout

Main layout wrapper composing all shell components.

**Location:** `frontend/src/components/layout/Layout.tsx`

**Props:**

| Prop     | Type        | Default | Description  |
| -------- | ----------- | ------- | ------------ |
| children | `ReactNode` | -       | Page content |

**Features:**

- Responsive design (desktop sidebar, mobile bottom nav)
- Persistent header with system status
- Collapsible sidebar
- Content scroll management
- Skip link for accessibility

**Usage:**

```tsx
import { Layout } from '@/components/layout';

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/events" element={<EventsPage />} />
        {/* ... */}
      </Routes>
    </Layout>
  );
}
```

---

### Header

Top navigation bar with branding and status indicators.

**Location:** `frontend/src/components/layout/Header.tsx`

**Props:**

| Prop             | Type         | Default | Description         |
| ---------------- | ------------ | ------- | ------------------- |
| onMenuClick      | `() => void` | -       | Mobile menu handler |
| sidebarCollapsed | `boolean`    | -       | Sidebar state       |

**Contents:**

- NVIDIA Home Security Intelligence branding
- System health indicators (WebSocket, services)
- Theme toggle
- Command palette trigger (`Cmd/Ctrl + K`)
- GPU utilization mini-display

**Usage:**

```tsx
import { Header } from '@/components/layout';

<Header onMenuClick={toggleSidebar} sidebarCollapsed={isCollapsed} />;
```

---

### Sidebar

Left navigation menu with route links.

**Location:** `frontend/src/components/layout/Sidebar.tsx`

**Props:**

| Prop       | Type         | Default | Description         |
| ---------- | ------------ | ------- | ------------------- |
| collapsed  | `boolean`    | `false` | Collapsed state     |
| onToggle   | `() => void` | -       | Toggle handler      |
| onNavigate | `() => void` | -       | Navigation callback |

**Navigation Items:**

| Route        | Label           | Icon            |
| ------------ | --------------- | --------------- |
| `/`          | Dashboard       | LayoutDashboard |
| `/timeline`  | Events          | Clock           |
| `/entities`  | Entities        | Users           |
| `/alerts`    | Alerts          | Bell            |
| `/analytics` | Analytics       | BarChart        |
| `/audit`     | Audit Log       | FileText        |
| `/system`    | System          | Server          |
| `/settings`  | Settings        | Settings        |
| `/jobs`      | Jobs            | Briefcase       |
| `/dev-tools` | Developer Tools | Wrench          |

**Features:**

- Active route highlighting
- Collapsible with icon-only mode
- Keyboard navigation
- Alert badges for notifications

**Usage:**

```tsx
import { Sidebar } from '@/components/layout';

<Sidebar
  collapsed={isCollapsed}
  onToggle={() => setCollapsed(!isCollapsed)}
  onNavigate={() => closeMobileMenu()}
/>;
```

---

### MobileBottomNav

Bottom navigation bar for mobile devices.

**Location:** `frontend/src/components/layout/MobileBottomNav.tsx`

**Props:**

| Prop       | Type         | Default | Description         |
| ---------- | ------------ | ------- | ------------------- |
| onNavigate | `() => void` | -       | Navigation callback |

**Features:**

- Shows on screens < 768px
- Fixed bottom position
- 5 primary navigation items
- Active state indication

**Usage:**

```tsx
import { MobileBottomNav } from '@/components/layout';

<div className="md:hidden">
  <MobileBottomNav onNavigate={handleNavigate} />
</div>;
```

---

### PageDocsLink

Link to documentation for current page.

**Location:** `frontend/src/components/layout/PageDocsLink.tsx`

**Props:**

| Prop    | Type     | Default | Description        |
| ------- | -------- | ------- | ------------------ |
| docPath | `string` | -       | Documentation path |
| label   | `string` | `Docs`  | Link label         |

**Usage:**

```tsx
import { PageDocsLink } from '@/components/layout';

<PageDocsLink docPath="/user/dashboard" label="Dashboard Help" />;
```

---

## Responsive Behavior

| Breakpoint   | Sidebar  | Bottom Nav | Header          |
| ------------ | -------- | ---------- | --------------- |
| < 768px (sm) | Hidden   | Visible    | Hamburger menu  |
| 768px+ (md)  | Visible  | Hidden     | Full navigation |
| 1024px+ (lg) | Expanded | Hidden     | Full navigation |

---

## Theme Integration

The layout uses the NVIDIA dark theme:

```css
/* Header */
background: #0e0e0e;
border-bottom: 1px solid #1a1a1a;

/* Sidebar */
background: #1a1a1a;
border-right: 1px solid #2a2a2a;

/* Content area */
background: #121212;

/* Active link */
background: rgba(118, 185, 0, 0.1);
border-left: 3px solid #76b900;
```

---

## Keyboard Shortcuts

| Shortcut       | Action                  |
| -------------- | ----------------------- |
| `Cmd/Ctrl + K` | Open command palette    |
| `Cmd/Ctrl + /` | Toggle sidebar          |
| `Cmd/Ctrl + B` | Toggle sidebar          |
| `?`            | Show keyboard shortcuts |
| `g d`          | Go to Dashboard         |
| `g e`          | Go to Events            |
| `g s`          | Go to Settings          |

---

## Accessibility

- Skip link to main content (`SkipLink` component)
- ARIA landmarks (`nav`, `main`, `header`)
- Keyboard navigable sidebar
- Focus management on route changes
- Screen reader announcements for navigation

---

## Testing

```bash
cd frontend && npm test -- --testPathPattern=Layout
cd frontend && npm test -- --testPathPattern=Header
cd frontend && npm test -- --testPathPattern=Sidebar
```

Test files:

- `Layout.test.tsx`
- `Header.test.tsx`
- `Sidebar.test.tsx`
- `MobileBottomNav.test.tsx`
- `PageDocsLink.test.tsx`
