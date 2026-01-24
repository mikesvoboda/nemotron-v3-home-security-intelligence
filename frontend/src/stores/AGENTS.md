# Stores Directory

This directory contains state management stores for the frontend application using Zustand.

## Overview

Stores manage application state that needs to be shared across components. All stores use Zustand with the following enhancements (NEM-3399, NEM-3400, NEM-3428):

- **DevTools middleware** - Redux DevTools integration for debugging (disabled in production)
- **useShallow hooks** - Selective subscriptions to prevent unnecessary re-renders
- **Memoized selectors** - Cached selectors for derived state

## Files

| File                              | Purpose                                               |
| --------------------------------- | ----------------------------------------------------- |
| `dashboardConfig.ts`              | Dashboard widget configuration store                  |
| `dashboardConfig.test.ts`         | Tests for dashboard configuration store               |
| `prometheus-alert-store.ts`       | Prometheus alert state management                     |
| `prometheus-alert-store.test.ts`  | Tests for Prometheus alert store                      |
| `rate-limit-store.ts`             | API rate limit tracking store                         |
| `rate-limit-store.test.ts`        | Tests for rate limit store                            |
| `storage-status-store.ts`         | Storage status tracking store                         |
| `storage-status-store.test.ts`    | Tests for storage status store                        |
| `worker-status-store.ts`          | Background worker status store                        |
| `worker-status-store.test.ts`     | Tests for worker status store                         |

## Store Architecture

Each Zustand store follows this pattern:

```typescript
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { useShallow } from 'zustand/shallow';

export const useMyStore = create<MyState>()(
  devtools(
    (set, get) => ({
      // State
      data: null,

      // Actions
      update: (value) => {
        set({ data: value }, undefined, 'update');
      },
    }),
    { name: 'my-store', enabled: process.env.NODE_ENV !== 'production' }
  )
);

// Selectors
export const selectDerivedData = (state: MyState) => /* ... */;

// Memoized selectors (for derived state that creates new arrays/objects)
export const selectDerivedDataMemoized = (state: MyState) => {
  if (state.data === cache.data) return cache.result;
  const result = /* compute */;
  cache = { data: state.data, result };
  return result;
};

// Shallow hooks for selective subscriptions
export function useMyData() {
  return useMyStore(useShallow((state) => ({
    data: state.data,
  })));
}

export function useMyActions() {
  return useMyStore(useShallow((state) => ({
    update: state.update,
  })));
}
```

### `dashboardConfig.ts`

Dashboard widget customization store. Manages:

- **Widget visibility toggles** - Show/hide individual dashboard widgets
- **Widget ordering** - Reorder widgets via up/down controls
- **localStorage persistence** - Configuration survives browser refresh
- **Default configuration** - Sensible defaults for new users

Note: This store does not use Zustand (uses pure TypeScript with localStorage).

#### Key Types

```typescript
type WidgetId = 'stats-row' | 'ai-summary-row' | 'camera-grid' | 'activity-feed' | 'gpu-stats' | 'pipeline-telemetry' | 'pipeline-queues';

interface WidgetConfig {
  id: WidgetId;
  name: string;
  description: string;
  visible: boolean;
}

interface DashboardConfig {
  widgets: WidgetConfig[];
  version: number;
}
```

### `prometheus-alert-store.ts`

Prometheus/Alertmanager alert state management.

#### Shallow Hooks (NEM-3399)

| Hook | Purpose |
|------|---------|
| `usePrometheusAlertCounts()` | Select only alert counts (criticalCount, warningCount, etc.) |
| `usePrometheusAlerts()` | Select only the alerts map |
| `usePrometheusAlertActions()` | Select actions (handlePrometheusAlert, removeAlert, clear) |

#### Memoized Selectors (NEM-3428)

| Selector | Purpose |
|----------|---------|
| `selectCriticalAlertsMemoized` | Cached critical alerts array |
| `selectWarningAlertsMemoized` | Cached warning alerts array |
| `selectInfoAlertsMemoized` | Cached info alerts array |
| `selectAlertsSortedBySeverityMemoized` | Cached sorted alerts array |

### `rate-limit-store.ts`

API rate limit tracking store.

#### Shallow Hooks (NEM-3399)

| Hook | Purpose |
|------|---------|
| `useRateLimitStatus()` | Select isLimited and secondsUntilReset |
| `useRateLimitCurrent()` | Select current rate limit info |
| `useRateLimitActions()` | Select actions (update, clear) |

### `storage-status-store.ts`

Storage status tracking store.

#### Shallow Hooks (NEM-3399)

| Hook | Purpose |
|------|---------|
| `useStorageWarningStatus()` | Select isCritical and isHigh flags |
| `useStorageStatus()` | Select current storage status |
| `useStorageActions()` | Select actions (update, clear) |

### `worker-status-store.ts`

Background worker status store.

#### Shallow Hooks (NEM-3399)

| Hook | Purpose |
|------|---------|
| `usePipelineHealth()` | Select pipeline health status (pipelineHealth, hasError, hasWarning, counts) |
| `useWorkers()` | Select only the workers map |
| `useWorkerActions()` | Select all worker event handlers and clear action |

#### Memoized Selectors (NEM-3428)

| Selector | Purpose |
|----------|---------|
| `selectErrorWorkersMemoized` | Cached error workers array |
| `selectWarningWorkersMemoized` | Cached warning workers array |
| `selectRunningWorkersMemoized` | Cached running workers array |

## Usage Patterns

### Basic Store Usage

```typescript
// Full store (triggers re-render on any state change)
const { alerts, criticalCount, handlePrometheusAlert } = usePrometheusAlertStore();
```

### Optimized Usage with Shallow Hooks

```typescript
// Only re-renders when counts change (not when alert details change)
const { criticalCount, warningCount } = usePrometheusAlertCounts();

// Actions never change, so no re-renders
const { handlePrometheusAlert, clear } = usePrometheusAlertActions();
```

### Using Memoized Selectors

```typescript
// Use memoized selector in component
const criticalAlerts = usePrometheusAlertStore(selectCriticalAlertsMemoized);
```

## DevTools Integration (NEM-3400)

All Zustand stores integrate with Redux DevTools for debugging:

1. Install Redux DevTools browser extension
2. Open DevTools and navigate to "Redux" tab
3. See stores: `prometheus-alert-store`, `rate-limit-store`, `storage-status-store`, `worker-status-store`
4. Track state changes with action names like `handlePrometheusAlert/firing`, `update`, `clear`

DevTools is disabled in production (`enabled: process.env.NODE_ENV !== 'production'`).

## Storage Key

Dashboard configuration is stored in localStorage under the key `'dashboard-config'`.

## Version Migration

The `version` field in `DashboardConfig` supports future schema migrations. The `mergeWidgetsWithDefaults` function ensures new widgets are added when a user's saved config is outdated.
