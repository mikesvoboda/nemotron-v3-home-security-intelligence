# Layout Components

> Application shell and navigation components.

---

## Overview

The layout system provides the application shell including header, sidebar navigation, and responsive content area. All pages are rendered within this shell.

## Architecture

```
Layout
├── SkipLinkGroup (skip-to-navigation + skip-to-main-content)
├── Header
│   ├── Branding (NVIDIA logo) + mobile hamburger
│   ├── Command palette trigger (search box)
│   ├── ThemeToggle
│   ├── WebSocketStatus
│   └── GPU stats / service-status indicators
├── Sidebar (hidden on mobile viewports)
│   ├── Navigation groups (sidebarNav.ts)
│   ├── Active route indicator
│   └── Collapse toggle
├── Main content area
│   └── Page components (via React Router)
├── ConnectionStatusBanner / ServiceStatusAlert (common/)
├── CommandPalette + ShortcutsHelpModal
└── MobileBottomNav (mobile viewport only)
```

Note: the detailed service status UI lives in `Layout` (via `ServiceStatusAlert` from `components/common/ServiceStatusAlert.tsx`); `Header` carries the connection status (`WebSocketStatus`) and a compact AI-service badge.

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

- Responsive design (desktop sidebar, mobile bottom nav; viewport state from `useViewport()`, re-exported via `hooks/useIsMobile.ts`)
- Provides `SidebarContext` (mobile menu open/toggle) and `CommandPaletteContext` to children
- Renders `ConnectionStatusBanner` and `ServiceStatusAlert` (dismissible) above page content
- Skip links: `SkipLinkGroup` targeting `main-navigation` and `main-content`
- Mobile bottom padding (`pb-14`) so content clears the bottom nav

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

Top navigation bar with branding and status indicators. Takes no props — it reads sidebar state from `SidebarContext` and system status from its own queries.

**Location:** `frontend/src/components/layout/Header.tsx`

**Contents:**

- NVIDIA branding (`/images/nvidia-logo-white.svg`)
- Mobile hamburger button (`md:hidden`) that toggles the sidebar via `toggleMobileMenu()`
- Command palette trigger (search box; opens via `useCommandPaletteContext`)
- Theme toggle
- `WebSocketStatus` (connection indicator)
- GPU mini-display (utilization, temperature, memory, inference FPS) and service-health tooltip
- Recent Threats indicator and AI Service Status badge (hidden on mobile)

**Usage:**

```tsx
import { Header } from '@/components/layout';

<Header />;
```

---

### Sidebar

Left navigation menu with grouped route links.

**Location:** `frontend/src/components/layout/Sidebar.tsx`

**Props:**

| Prop           | Type      | Default | Description                                               |
| -------------- | --------- | ------- | --------------------------------------------------------- |
| forceCollapsed | `boolean` | -       | Force collapsed mode (overrides auto-collapse for tablet) |

Navigation structure is defined in `frontend/src/components/layout/sidebarNav.ts` as expandable groups (`navGroups`):

| Group (label)          | Items (label - path)                                                                                                                                                                                                                                                                                                                                                                                                   |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| MONITORING (expanded)  | Dashboard - `/`, Timeline - `/timeline`, Entities - `/entities`, Alerts - `/alerts`                                                                                                                                                                                                                                                                                                                                    |
| ANALYTICS (expanded)   | Analytics - `/analytics`, Video Analytics - `/video-analytics`, AI Audit - `/ai-audit`, AI Performance - `/ai`, AI Services - `/ai-services`, Profiling - `/pyroscope`, Plate Reads - `/plate-reads`, Face Recognition - `/face-recognition`, Heatmaps - `/heatmaps`, Scene Changes - `/scene-changes`, Object Tracks - `/tracks`, Performance - `/performance`, Household - `/household`, Re-Identification - `/reid` |
| OPERATIONS (collapsed) | Jobs - `/jobs`, Pipeline - `/operations`, Dashboard - `/operations-dashboard`, Notifications - `/notifications`, GPU Metrics - `/gpu-metrics`, Request Profiling - `/request-profiling`, Tracing - `/tracing`, Logs - `/logs`                                                                                                                                                                                          |
| ADMIN (collapsed)      | Zones - `/zones`, Audit Log - `/audit`, Data Management - `/data`, Scheduled Reports - `/scheduled-reports`, Webhooks - `/webhooks`, Trash - `/trash`, GPU Settings - `/settings/gpu`, Settings - `/settings`                                                                                                                                                                                                          |

**Features:**

- Active route highlighted (`bg-[#76B900] text-black`)
- Collapsible icon-only mode; tablet auto-collapse (overridable via `forceCollapsed`)
- On mobile viewports `Layout` hides the sidebar and uses `MobileBottomNav`; the hamburger opens it as an overlay with backdrop

**Usage:**

```tsx
import { Sidebar } from '@/components/layout';

<Sidebar forceCollapsed={isTablet} />;
```

---

### MobileBottomNav

Bottom navigation bar for mobile viewports. Rendered by `Layout` when `useViewport().isMobile` is true (screens < 640px).

**Location:** `frontend/src/components/layout/MobileBottomNav.tsx`

**Props:**

| Prop              | Type     | Default | Description                                    |
| ----------------- | -------- | ------- | ---------------------------------------------- |
| notificationCount | `number` | `0`     | Unread count shown as badge on the Alerts item |

**Features:**

- Fixed bottom position, 56px (`h-14`) tall, safe-area padding
- Primary items: Dashboard (`/`), Timeline (`/timeline`), Alerts (`/alerts`, badge-capable)
- "More" menu for all remaining navigation routes
- Active state indication

**Usage:**

```tsx
import { MobileBottomNav } from '@/components/layout';

<MobileBottomNav notificationCount={unread} />;
```

---

### PageDocsLink

Link to documentation for the current page. Takes no props — it looks up the current route (`useLocation().pathname`) in the `PAGE_DOCUMENTATION` map from `frontend/src/config/pageDocumentation.ts`.

**Location:** `frontend/src/components/layout/PageDocsLink.tsx`

**Usage:**

```tsx
import { PageDocsLink } from '@/components/layout';

<PageDocsLink />;
```

---

## Responsive Behavior

Viewport classes come from `useViewport()` (`hooks/useViewport.ts`, breakpoints `sm` 640 / `md` 768 / `lg` 1024; `isMobile` < 640, `isTablet` 640-1023, `isDesktop` >= 1024).

| Viewport      | Sidebar                          | Bottom Nav   | Header hamburger     |
| ------------- | -------------------------------- | ------------ | -------------------- |
| < 640px       | Hidden (hamburger opens overlay) | Rendered     | Visible              |
| 640-767px     | Rendered (overlay-capable)       | Not rendered | Visible              |
| >= 768px (md) | Rendered inline                  | Not rendered | Hidden (`md:hidden`) |

---

## Theme Integration

Dark shell applied with Tailwind classes:

- App shell background: `bg-[#0E0E0E]` (`Layout.tsx`)
- Header: `bg-[#1A1A1A]` with `border-b border-gray-800` (`Header.tsx`)
- Sidebar: `bg-[#1A1A1A]` with `border-r border-gray-800` (`Sidebar.tsx`)
- Active nav link: `bg-[#76B900] text-black` (`Sidebar.tsx`)

---

## Keyboard Shortcuts

Global handlers live in `frontend/src/hooks/useKeyboardShortcuts.ts`; the canonical reference is `docs/reference/keyboard-shortcuts.md`.

| Shortcut       | Action                                  |
| -------------- | --------------------------------------- |
| `Cmd/Ctrl + K` | Open command palette                    |
| `?`            | Open keyboard shortcuts help modal      |
| `Escape`       | Close dialogs (via `onEscape` callback) |
| `g` then `d`   | Go to Dashboard (`/`)                   |
| `g` then `t`   | Go to Timeline (`/timeline`)            |
| `g` then `e`   | Go to Entities (`/entities`)            |
| `g` then `a`   | Go to Alerts (`/alerts`)                |
| `g` then `s`   | Go to Settings (`/settings`)            |
| `g` then `n`   | Go to Analytics (`/analytics`)          |
| `g` then `o`   | Go to Logs (`/logs`)                    |
| `g` then `y`   | Go to System/Operations (`/system`)     |

(Chords are matched within a 1 s window - `CHORD_TIMEOUT`.) There is no keyboard shortcut for toggling the sidebar.

---

## Accessibility

- Skip links to navigation and main content (`SkipLinkGroup` from `components/common/SkipLink`)
- ARIA landmarks (`nav`, `main`, `header`)
- Keyboard navigable sidebar
- Focus management on route changes (focusable `main` with `tabIndex={-1}`)
- Screen reader announcements for navigation

---

## Testing

```bash
cd frontend && npm test -- src/components/layout
```

Test files:

- `Layout.test.tsx`
- `Header.test.tsx`
- `Sidebar.test.tsx`
- `MobileBottomNav.test.tsx`
- `PageDocsLink.test.tsx`
