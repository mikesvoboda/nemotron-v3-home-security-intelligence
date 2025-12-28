# Frontend Source Directory - AI Agent Guide

## Purpose

This directory contains all React application source code including components, hooks, services, styles, and tests. It is the main workspace for frontend development.

## Entry Points

### Main Entry

- **`main.tsx`** - Application bootstrap
  - Imports React and ReactDOM
  - Imports global styles from `styles/index.css`
  - Renders `<App />` into `#root` div with `React.StrictMode`
  - Throws error if root element not found

### Root Component

- **`App.tsx`** - Root application component
  - Uses `BrowserRouter` for client-side routing
  - Wraps all routes in `<Layout />` component
  - Defines routes for all pages (see Routes section)

### Tests

- **`App.test.tsx`** - Tests for root App component

### Type Definitions

- **`vite-env.d.ts`** - Vite client type definitions for `import.meta.env`

## Directory Structure

### `/components/` - React Components

Components are organized by feature area. Each component directory contains:

- Component files (`.tsx`)
- Co-located test files (`.test.tsx`)
- Optional index files for barrel exports
- Optional README documentation

#### Feature Directories

| Directory    | Description                      |
| ------------ | -------------------------------- |
| `alerts/`    | Alert management page            |
| `common/`    | Reusable UI components           |
| `dashboard/` | Main dashboard components        |
| `detection/` | Object detection visualization   |
| `entities/`  | Entity tracking page             |
| `events/`    | Event list and detail components |
| `layout/`    | Layout, header, and sidebar      |
| `logs/`      | Application logs viewer          |
| `settings/`  | Settings pages and forms         |
| `system/`    | System monitoring components     |
| `video/`     | Video player component           |

#### `/components/common/`

Reusable UI components:

- `RiskBadge.tsx` - Displays risk level badges (low/medium/high/critical)
- `ObjectTypeBadge.tsx` - Displays object type badges (person/vehicle/animal/package)
- `ServiceStatusAlert.tsx` - Service status alert banner
- `index.ts` - Barrel export

#### `/components/layout/`

Application layout and navigation:

- `Layout.tsx` - Main layout wrapper with header and sidebar
- `Header.tsx` - Top navigation bar with branding and system status
- `Sidebar.tsx` - Left navigation menu with icon buttons

#### `/components/dashboard/`

Main dashboard components:

- `DashboardPage.tsx` - Main dashboard view with real-time monitoring
- `RiskGauge.tsx` - Risk score visualization with Tremor DonutChart
- `CameraGrid.tsx` - Multi-camera grid display
- `ActivityFeed.tsx` - Real-time event activity stream
- `GpuStats.tsx` - GPU utilization and metrics display
- `StatsRow.tsx` - Dashboard statistics row
- `PipelineQueues.tsx` - Pipeline queue depths visualization
- `RiskGauge.example.tsx` - Interactive example for development

#### `/components/detection/`

Object detection visualization:

- `BoundingBoxOverlay.tsx` - Renders detection boxes over images
- `DetectionImage.tsx` - Displays image with detection overlays
- `DetectionThumbnail.tsx` - Thumbnail with detection box
- `Example.tsx` - Example usage component
- `index.ts` - Barrel export
- `README.md` - Documentation

#### `/components/events/`

Event-related components:

- `EventCard.tsx` - Individual event card with thumbnail and risk badge
- `EventTimeline.tsx` - Chronological event list with filtering
- `EventDetailModal.tsx` - Full event details modal
- `ThumbnailStrip.tsx` - Horizontal strip of event thumbnails
- `index.ts` - Barrel export

#### `/components/logs/`

Application logging components:

- `LogsDashboard.tsx` - Main logs dashboard view
- `LogsTable.tsx` - Paginated table of log entries
- `LogFilters.tsx` - Log filtering controls
- `LogDetailModal.tsx` - Detailed log entry modal
- `LogStatsCards.tsx` - Statistics cards by log level

#### `/components/settings/`

Settings page components:

- `SettingsPage.tsx` - Main settings page with tabbed navigation
- `CamerasSettings.tsx` - Camera management (add, edit, delete)
- `AIModelsSettings.tsx` - AI model status and GPU memory
- `ProcessingSettings.tsx` - Batch processing and retention config
- `DlqMonitor.tsx` - Dead letter queue monitoring
- `index.ts` - Barrel export
- `README.md` - Documentation

#### `/components/system/`

System monitoring:

- `SystemMonitoringPage.tsx` - System health and metrics page
- `ObservabilityPanel.tsx` - Observability metrics panel
- `index.ts` - Barrel export

#### `/components/alerts/`

Alert management:

- `AlertsPage.tsx` - Alert listing and management

#### `/components/entities/`

Entity tracking:

- `EntitiesPage.tsx` - Entity tracking page

#### `/components/video/`

Video playback:

- `VideoPlayer.tsx` - Video player component with controls
- `index.ts` - Barrel export

### `/hooks/` - Custom React Hooks

| Hook                  | Purpose                                             |
| --------------------- | --------------------------------------------------- |
| `useWebSocket.ts`     | WebSocket connection management with auto-reconnect |
| `useEventStream.ts`   | Event stream subscription for `/ws/events`          |
| `useSystemStatus.ts`  | System status monitoring via `/ws/system`           |
| `useGpuHistory.ts`    | GPU metrics history with polling                    |
| `useHealthStatus.ts`  | Health status polling                               |
| `useServiceStatus.ts` | Service status aggregation                          |
| `index.ts`            | Barrel export for all hooks                         |

Each hook has a co-located `.test.ts` file.

### `/services/` - API Client and Services

| File             | Purpose                                   |
| ---------------- | ----------------------------------------- |
| `api.ts`         | REST API client with typed fetch wrappers |
| `api.test.ts`    | API client tests                          |
| `logger.ts`      | Client-side structured logging            |
| `logger.test.ts` | Logger tests                              |

The `api.ts` file re-exports all types from `types/generated/` for convenience.

### `/styles/` - Global Styles

- **`index.css`** - Global CSS with Tailwind directives
  - `@tailwind base` - Base styles reset
  - `@tailwind components` - Component classes
  - `@tailwind utilities` - Utility classes
  - Custom component classes (`.nvidia-card`, `.btn-primary`, etc.)
  - Custom utilities (`.glass`, `.text-gradient-nvidia`, `.glow-nvidia`)
  - Dark theme scrollbar styling
  - Selection color with NVIDIA green

### `/test/` - Test Setup

- **`setup.ts`** - Vitest test configuration
  - Extends expect with jest-dom matchers
  - Mocks ResizeObserver and IntersectionObserver for jsdom
  - Fixes HeadlessUI focus issues
  - Cleanup after each test

### `/types/` - TypeScript Types

- **`generated/`** - Auto-generated from backend OpenAPI
  - `api.ts` - Full OpenAPI types (DO NOT EDIT)
  - `index.ts` - Re-exports with convenient aliases

### `/utils/` - Utility Functions

| File      | Purpose                                                               |
| --------- | --------------------------------------------------------------------- |
| `risk.ts` | Risk level utilities (getRiskLevel, getRiskColor, getRiskLabel)       |
| `time.ts` | Time formatting (formatRelativeTime, formatTimestamp, formatDuration) |

Each utility has a co-located `.test.ts` file.

### `/__tests__/` - Additional Tests

- `lighthouserc.test.ts` - Lighthouse CI configuration tests

## Application Routes

Defined in `App.tsx`:

```typescript
<Routes>
  <Route path="/" element={<DashboardPage />} />
  <Route path="/timeline" element={<EventTimeline />} />
  <Route path="/alerts" element={<AlertsPage />} />
  <Route path="/entities" element={<EntitiesPage />} />
  <Route path="/logs" element={<LogsDashboard />} />
  <Route path="/system" element={<SystemMonitoringPage />} />
  <Route path="/settings" element={<SettingsPage />} />
</Routes>
```

## Testing

All test files use naming convention: `*.test.ts` or `*.test.tsx`

### Test Coverage Thresholds

- Statements: 93%
- Branches: 89%
- Functions: 91%
- Lines: 94%

### Test Setup

- Environment: jsdom
- Setup file: `test/setup.ts`
- Provider: v8 coverage
- Pool: forks (single fork for memory optimization)

## Type Safety

TypeScript strict mode with:

- `strict: true`
- `noUnusedLocals: true`
- `noUnusedParameters: true`
- `noFallthroughCasesInSwitch: true`

## Styling Guidelines

### Tailwind Colors

| Color                     | Usage                        |
| ------------------------- | ---------------------------- |
| `bg-background`           | Page background (`#0E0E0E`)  |
| `bg-panel`                | Panel background (`#1A1A1A`) |
| `bg-card`                 | Card background (`#1E1E1E`)  |
| `bg-primary-500`          | Primary action (`#76B900`)   |
| `bg-risk-low/medium/high` | Risk level indicators        |
| `text-text-primary`       | Main text (`#FFFFFF`)        |
| `text-text-secondary`     | Secondary text (`#A0A0A0`)   |
| `text-text-muted`         | Muted text (`#707070`)       |

### Custom CSS Classes

| Class                                  | Purpose                |
| -------------------------------------- | ---------------------- |
| `.nvidia-card`                         | Standard card styling  |
| `.nvidia-card-hover`                   | Card with hover effect |
| `.nvidia-panel`                        | Panel styling          |
| `.btn-primary`                         | Primary button         |
| `.btn-secondary`                       | Secondary button       |
| `.btn-ghost`                           | Ghost button           |
| `.nvidia-input`                        | Input field styling    |
| `.risk-badge-low/medium/high`          | Risk badges            |
| `.status-online/offline/warning/error` | Status dots            |
| `.glass`                               | Glass morphism effect  |
| `.glow-nvidia`                         | NVIDIA green glow      |

## Common Imports

```typescript
// React
import { useState, useEffect, useCallback } from 'react';

// Routing
import { useNavigate, useParams, Link } from 'react-router-dom';

// API client and types
import { fetchCameras, fetchHealth } from '../services/api';
import type { Camera, Event, HealthResponse } from '../services/api';

// Hooks
import { useWebSocket, useEventStream, useSystemStatus } from '../hooks';

// Components
import { RiskBadge, ObjectTypeBadge } from '../components/common';

// Utilities
import { getRiskLevel, getRiskColor } from '../utils/risk';
import { formatRelativeTime, formatTimestamp } from '../utils/time';

// Icons
import { Activity, Camera, Settings, AlertTriangle } from 'lucide-react';

// Tremor (data visualization)
import { Card, Title, Text, DonutChart, BarChart } from '@tremor/react';

// Headless UI (accessible components)
import { Dialog, Transition, Tab } from '@headlessui/react';
```

## Best Practices

1. **Co-locate tests**: Every component/hook/utility must have a test file
2. **Use TypeScript**: No `any` types unless absolutely necessary
3. **Follow component structure**:
   - Props interface at top
   - Component function with typed props
   - Return JSX with Tailwind classes
   - Export default at bottom
4. **API calls**: Use functions from `services/api.ts`
5. **WebSocket**: Use hooks from `/hooks/` for connections
6. **Styling**: Prefer existing custom classes, use Tailwind utilities for one-offs
7. **Testing**: Test user-visible behavior, not implementation details
8. **File organization**: Components in feature directories, hooks in `/hooks/`

## Notes

- **Routing**: Uses react-router-dom v7
- **WebSocket channels**: `/ws/events` and `/ws/system`
- **Media URLs**: `/api/media/cameras/{cameraId}/{filename}`
- **Environment variables**: Use `import.meta.env.VITE_*`
- **Hot reload**: Vite HMR for instant updates
