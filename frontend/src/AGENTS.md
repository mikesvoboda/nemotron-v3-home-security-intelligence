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
  - Wraps `<DashboardPage />` in `<Layout />`
  - Defines overall application structure
  - No routing yet (single page app for now)

### Type Definitions

- **`vite-env.d.ts`** - Vite client type definitions
  - References Vite types for `import.meta.env`

## Directory Structure

### `/components/` - React Components

Component organization by feature area:

- **`common/`** - Reusable UI components

  - `RiskBadge.tsx` - Displays risk level badges (low/medium/high/critical)
  - `index.ts` - Barrel export for common components

- **`layout/`** - Layout and navigation components

  - `Layout.tsx` - Main layout wrapper with header and sidebar
  - `Header.tsx` - Top navigation bar with branding and system status
  - `Sidebar.tsx` - Left navigation menu with icon buttons

- **`dashboard/`** - Dashboard page components

  - `DashboardPage.tsx` - Main dashboard view (currently placeholder)

- **`detection/`** - Object detection visualization components

  - `BoundingBoxOverlay.tsx` - Renders detection boxes over images
  - `DetectionImage.tsx` - Displays image with detection overlays
  - `Example.tsx` - Example usage component (not covered by tests)
  - `index.ts` - Barrel export
  - `README.md` - Documentation for detection components

- **`events/`** - Event-related components (placeholder directory)

**Component Patterns**:

- Each component has co-located `.test.tsx` file
- Use TypeScript for all components
- Export default for main component
- Use named exports for types/interfaces
- Follow Tailwind utility-first styling

### `/hooks/` - Custom React Hooks

- **`useWebSocket.ts`** - WebSocket connection management

  - Handles connection lifecycle (connect, disconnect, reconnect)
  - Auto-reconnection with configurable attempts and interval
  - JSON message parsing
  - Returns: `{ isConnected, lastMessage, send, connect, disconnect }`

- **`useEventStream.ts`** - Event stream subscription hook

  - Wraps `useWebSocket` for event updates
  - Manages event state and history

- **`useSystemStatus.ts`** - System status polling hook

  - Fetches health and GPU stats periodically
  - Returns system status and error state

- **`index.ts`** - Barrel export for all hooks

**Hook Patterns**:

- Co-located `.test.ts` files for unit tests
- Return object with named properties
- Use TypeScript for all parameters and returns
- Handle cleanup in `useEffect` return functions

### `/services/` - API Client

- **`api.ts`** - REST API client for backend
  - Base URL from `import.meta.env.VITE_API_BASE_URL` (defaults to empty string for proxy)
  - Type-safe fetch wrappers for all endpoints
  - Custom `ApiError` class with status codes
  - Camera endpoints: `fetchCameras()`, `fetchCamera(id)`, `createCamera()`, `updateCamera()`, `deleteCamera()`
  - System endpoints: `fetchHealth()`, `fetchGPUStats()`, `fetchConfig()`, `fetchStats()`
  - Media URL builders: `getMediaUrl()`, `getThumbnailUrl()`
  - Exported types: `Camera`, `HealthResponse`, `GPUStats`, `SystemConfig`, `SystemStats`

**API Patterns**:

- All functions return Promises with typed responses
- Error handling with `ApiError` class
- JSON content-type by default
- Handles 204 No Content responses

### `/styles/` - Global Styles

- **`index.css`** - Global CSS with Tailwind directives
  - `@tailwind base` - Base styles reset
  - `@tailwind components` - Component classes
  - `@tailwind utilities` - Utility classes
  - Custom component classes: `.nvidia-card`, `.nvidia-panel`, `.btn-primary`, etc.
  - Custom utilities: `.glass`, `.text-gradient-nvidia`, `.glow-nvidia`
  - Scrollbar styling for dark theme
  - Selection color with NVIDIA green

### `/test/` - Test Setup

- **`setup.ts`** - Vitest test configuration
  - Extends Vitest expect with jest-dom matchers
  - Imported automatically before each test file

### `/utils/` - Utility Functions

- **`risk.ts`** - Risk level utilities
  - `getRiskLevel(score: number): RiskLevel` - Convert 0-100 score to category
  - `getRiskColor(level: RiskLevel): string` - Get hex color for level
  - `getRiskLabel(level: RiskLevel): string` - Get human-readable label
  - Risk levels: low (0-25), medium (26-50), high (51-75), critical (76-100)

## Testing

All test files use naming convention: `*.test.ts` or `*.test.tsx`

### Component Tests

- `App.test.tsx` - Root component tests
- `components/common/RiskBadge.test.tsx`
- `components/layout/Header.test.tsx`
- `components/layout/Layout.test.tsx`
- `components/layout/Sidebar.test.tsx`
- `components/dashboard/DashboardPage.test.tsx`
- `components/detection/BoundingBoxOverlay.test.tsx`
- `components/detection/DetectionImage.test.tsx`

### Hook Tests

- `hooks/useWebSocket.test.ts`
- `hooks/useEventStream.test.ts`
- `hooks/useSystemStatus.test.ts`

### Service Tests

- `services/api.test.ts`

### Utility Tests

- `utils/risk.test.ts`

**Test Coverage**: 95% threshold for statements, functions, and lines; 94% for branches

## Type Safety

All TypeScript files use strict mode with these checks enabled:

- `strict: true`
- `noUnusedLocals: true`
- `noUnusedParameters: true`
- `noFallthroughCasesInSwitch: true`

Use explicit types for:

- Function parameters
- Return values (inferred is okay for simple cases)
- Props interfaces
- State types

## Styling Guidelines

### Tailwind Usage

- **Layout**: Use flexbox (`flex`, `flex-col`) and grid (`grid`)
- **Colors**: Reference custom colors from theme

  - Background: `bg-background`, `bg-panel`, `bg-card`
  - Primary: `bg-primary-500`, `text-primary-500`
  - Risk levels: `bg-risk-low`, `bg-risk-medium`, `bg-risk-high`
  - Text: `text-text-primary`, `text-text-secondary`, `text-text-muted`

- **Custom Classes**: Use predefined component classes
  - Cards: `.nvidia-card`, `.nvidia-card-hover`
  - Panels: `.nvidia-panel`
  - Buttons: `.btn-primary`, `.btn-secondary`, `.btn-ghost`
  - Risk badges: `.risk-badge-low`, `.risk-badge-medium`, `.risk-badge-high`
  - Inputs: `.nvidia-input`
  - Status dots: `.status-online`, `.status-offline`, `.status-warning`, `.status-error`

### Dark Theme

All components assume dark theme:

- Dark backgrounds (`#0E0E0E`, `#1A1A1A`, `#1E1E1E`)
- Light text on dark surfaces
- NVIDIA green for highlights and primary actions
- Subtle borders and shadows

## Best Practices for AI Agents

1. **Co-locate tests**: Every component/hook/utility must have a test file
2. **Use TypeScript**: No `any` types unless absolutely necessary
3. **Follow component structure**:

   - Props interface at top
   - Component function with typed props
   - Return JSX with Tailwind classes
   - Export default at bottom

4. **API calls**:

   - Use functions from `services/api.ts`
   - Handle loading and error states
   - Use hooks for component data fetching

5. **WebSocket**:

   - Use `useWebSocket` hook for connections
   - Parse JSON messages automatically
   - Handle disconnection gracefully

6. **Styling**:

   - Prefer existing custom classes
   - Use Tailwind utilities for one-off styles
   - Never inline CSS styles
   - Use `clsx` or `tailwind-merge` for conditional classes

7. **Testing**:

   - Test user-visible behavior, not implementation
   - Use `screen` queries from React Testing Library
   - Use `userEvent` for interactions
   - Mock external dependencies (API, WebSocket)

8. **File organization**:
   - Components in `/components/{feature}/`
   - Reusable hooks in `/hooks/`
   - API client in `/services/`
   - Utilities in `/utils/`
   - Tests co-located with source files

## Common Imports

```typescript
// React
import { useState, useEffect, useCallback } from 'react';

// API client
import { fetchCameras, fetchHealth, type Camera } from '@/services/api';

// Hooks
import { useWebSocket, useEventStream } from '@/hooks';

// Components
import { RiskBadge } from '@/components/common';

// Utilities
import { getRiskLevel, getRiskColor } from '@/utils/risk';

// Icons
import { Activity, Camera, Settings } from 'lucide-react';

// Tremor (data viz)
import { Card, Title, Text } from '@tremor/react';
```

## Notes

- **No routing yet**: App is single-page, routing will be added in Phase 7
- **WebSocket channels**: Backend supports event streams at `/ws/events`
- **Media URLs**: Images served from `/api/media/cameras/{cameraId}/{filename}`
- **Environment variables**: Use `import.meta.env.VITE_*` for Vite env vars
- **Build**: Vite bundles all imports, tree-shakes unused code
- **Hot reload**: Vite dev server supports HMR for instant updates
