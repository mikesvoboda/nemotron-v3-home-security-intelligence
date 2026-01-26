# Stores Directory

This directory contains Zustand state management stores for the frontend application.

## Overview

Stores manage application state that needs to persist across sessions or be shared across components. Uses Zustand with advanced middleware patterns for optimal performance:

- **Immer middleware** for immutable updates with mutable syntax
- **subscribeWithSelector** for fine-grained component subscriptions
- **Transient updates** for high-frequency WebSocket events
- **Persist middleware** for localStorage persistence

## Files

| File                               | Purpose                                               |
| ---------------------------------- | ----------------------------------------------------- |
| `middleware.ts`                    | Zustand middleware utilities (Immer, selectors)       |
| `middleware.test.ts`               | Tests for middleware utilities                        |
| `../utils/createSelectors.ts`      | Auto-selector generator for optimized re-renders      |
| `../utils/createSelectors.test.ts` | Tests for auto-selector utility                       |
| `dashboard-config-store.ts`        | Dashboard widget configuration store (Zustand)        |
| `dashboard-config-store.test.ts`   | Tests for dashboard configuration store               |
| `dashboardConfig.ts`               | Legacy dashboard config (deprecated, use new store)   |
| `dashboardConfig.test.ts`          | Legacy tests (deprecated)                             |
| `prometheus-alert-store.ts`        | Prometheus alert state management (Immer + selector)  |
| `prometheus-alert-store.test.ts`   | Tests for Prometheus alert store                      |
| `rate-limit-store.ts`              | API rate limit tracking store                         |
| `rate-limit-store.test.ts`         | Tests for rate limit store                            |
| `realtime-metrics-store.ts`        | High-frequency real-time metrics (transient updates)  |
| `realtime-metrics-store.test.ts`   | Tests for real-time metrics store                     |
| `storage-status-store.ts`          | Storage status tracking store                         |
| `storage-status-store.test.ts`     | Tests for storage status store                        |
| `worker-status-store.ts`           | Pipeline worker status (Immer + selector)             |
| `worker-status-store.test.ts`      | Tests for worker status store                         |

## Middleware Utilities (`middleware.ts`)

Provides advanced Zustand patterns for performance optimization (NEM-3402, NEM-3403, NEM-3426).

### createImmerStore

Creates a store with Immer middleware for mutable syntax that produces immutable updates.

```typescript
const useStore = createImmerStore<State>((set) => ({
  nested: { deep: { value: 0 } },
  setDeepValue: (value) => set((state) => {
    // Mutate directly - Immer handles immutability
    state.nested.deep.value = value;
  }),
}));
```

### createImmerSelectorStore

Combines Immer with subscribeWithSelector for fine-grained subscriptions.

```typescript
const useStore = createImmerSelectorStore<State>((set) => ({
  metrics: { cpu: 0, gpu: 0 },
  updateMetric: (key, value) => set((state) => {
    state.metrics[key] = value;
  }),
}));

// Subscribe only to CPU changes
const unsub = useStore.subscribe(
  (state) => state.metrics.cpu,
  (newCpu, prevCpu) => console.log('CPU changed:', newCpu)
);
```

### Transient Updates

For high-frequency WebSocket events, use batching to prevent render thrashing.

```typescript
import { createWebSocketEventHandler } from './middleware';

const handleGPUStats = createWebSocketEventHandler(
  useStore.setState,
  (event) => ({
    gpuUtilization: event.gpu_utilization,
    memoryUsed: event.memory_used,
  }),
  { batchMs: 100, maxBatchSize: 5 }
);

// Events are batched within 100ms window
websocket.on('gpu_stats', handleGPUStats);
```

### `dashboard-config-store.ts` (Recommended)

Zustand-based dashboard configuration store with persist middleware. Manages:

- **Widget visibility toggles** - Show/hide individual dashboard widgets
- **Widget ordering** - Reorder widgets via up/down controls
- **Theme setting** - Light/dark/system theme preference
- **Refresh interval** - Auto-refresh configuration
- **Compact mode** - UI density toggle
- **localStorage persistence** - Automatic via Zustand persist middleware
- **Schema versioning** - Supports migrations between versions

#### Key Types

```typescript
type WidgetId = 'stats-row' | 'ai-summary-row' | 'camera-grid' | 'activity-feed' | 'gpu-stats' | 'pipeline-telemetry' | 'pipeline-queues';

type ThemeSetting = 'light' | 'dark' | 'system';

interface WidgetConfig {
  id: WidgetId;
  name: string;
  description: string;
  visible: boolean;
}

interface DashboardConfigState {
  widgets: WidgetConfig[];
  theme: ThemeSetting;
  refreshInterval: number;
  compactMode: boolean;
  version: number;
}
```

#### Store Actions

| Action | Purpose |
|--------|---------|
| `setWidgetVisibility(id, visible)` | Toggle widget visibility |
| `moveWidgetUp(id)` | Move widget up in order |
| `moveWidgetDown(id)` | Move widget down in order |
| `setTheme(theme)` | Set theme preference |
| `setRefreshInterval(ms)` | Set auto-refresh interval |
| `setCompactMode(enabled)` | Toggle compact mode |
| `reset()` | Reset to defaults |

#### Selectors

| Selector | Purpose |
|----------|---------|
| `selectVisibleWidgets` | Get visible widgets in order |
| `selectIsWidgetVisible(id)` | Check if widget is visible |
| `selectWidgetById(id)` | Get widget config by ID |
| `selectCanMoveUp(id)` | Check if widget can move up |
| `selectCanMoveDown(id)` | Check if widget can move down |
| `selectEffectiveTheme` | Resolve 'system' to actual theme |

#### Default Visible Widgets

- Stats Row (metrics)
- AI Summary Row (AI model health)
- Camera Grid (live feeds)
- Activity Feed (events)

#### Default Hidden Widgets

- GPU Statistics
- Pipeline Telemetry
- Pipeline Queues

## Store Patterns

### Alert/Worker Stores (Immer + Selector)

Use Immer for complex nested updates and subscribeWithSelector for performance:

```typescript
// Subscribe to specific count - won't re-render on other changes
const criticalCount = usePrometheusAlertStore(
  (state) => state.criticalCount
);

// Subscribe to changes programmatically
usePrometheusAlertStore.subscribe(
  (state) => state.criticalCount,
  (newCount, prevCount) => {
    if (newCount > prevCount) playAlertSound();
  }
);
```

### Real-time Metrics (Transient Updates)

For high-frequency data, use transient slices with batched updates:

```typescript
// Subscribe only to GPU utilization
const gpuUtil = useRealtimeMetricsStore(
  (state) => state.gpu.data.utilization
);

// Batched WebSocket handler
websocket.on('gpu_stats', handleGPUStatsEvent);
```

## Usage Pattern

```typescript
import { useDashboardConfigStore, selectVisibleWidgets } from '@/stores/dashboard-config-store';

// In a React component - direct store usage
function Dashboard() {
  const { widgets, setWidgetVisibility, theme, setTheme } = useDashboardConfigStore();

  // Use selectors for optimized re-renders
  const visibleWidgets = useDashboardConfigStore(selectVisibleWidgets);

  return (
    <div>
      {visibleWidgets.map(widget => (
        <Widget key={widget.id} {...widget} />
      ))}
    </div>
  );
}

// With shallow comparison for object selections
import { useShallow } from 'zustand/react/shallow';

function Dashboard() {
  const { widgets, version } = useDashboardConfigStore(
    useShallow((state) => ({
      widgets: state.widgets,
      version: state.version,
    }))
  );
}
```

## Key Types

### TransientSlice

For frequently updating data:

```typescript
interface TransientSlice<T> {
  data: T;
  lastUpdated: number;
}
```

### Store State Patterns

All stores follow consistent patterns:

```typescript
interface StoreState {
  // Data
  items: Record<string, Item>;

  // Derived state (computed on each update)
  itemCount: number;
  hasErrors: boolean;

  // Actions
  addItem: (item: Item) => void;
  removeItem: (id: string) => void;
  clear: () => void;
}
```

## Auto-Selectors for Optimized Re-renders (NEM-3787)

The `createSelectors` utility auto-generates individual property selectors to prevent unnecessary re-renders. Instead of manually creating selectors for each property, wrap your store with `createSelectors`.

### Usage

```typescript
import { createSelectors } from '../utils/createSelectors';

// Create base store
const useEventStoreBase = create<EventState>()((set) => ({
  events: [],
  filters: { riskLevel: null },
  selectedEventId: null,
  setFilters: (filters) => set({ filters }),
  setSelectedEventId: (id) => set({ selectedEventId: id }),
}));

// Wrap with auto-selectors
export const useEventStore = createSelectors(useEventStoreBase);
```

### In Components

```typescript
// Only re-renders when events change
const events = useEventStore.use.events();

// Only re-renders when filters change
const filters = useEventStore.use.filters();

// Actions are stable references (don't cause re-renders)
const setFilters = useEventStore.use.setFilters();

// Traditional usage still works
const { events, filters } = useEventStore();
```

### Benefits

- **Automatic memoization**: Components only re-render when their selected value changes
- **Type-safe**: All selectors are fully typed based on the store state
- **Clean API**: Simple `.use.propertyName()` syntax
- **Zero boilerplate**: No need to manually create selectors for each property

### Type Helpers

```typescript
import { ExtractState, SelectorKeys } from '../utils/createSelectors';

// Extract state type from store
type EventState = ExtractState<typeof useEventStore>;

// Get all selector keys
type Keys = SelectorKeys<typeof useEventStore>;
// 'events' | 'filters' | 'selectedEventId' | 'setFilters' | 'setSelectedEventId'
```

## Performance Guidelines

1. **Use auto-selectors** - Wrap stores with `createSelectors` for automatic optimization
2. **Use selectors** - Subscribe to specific state slices, not entire store
3. **Batch high-frequency updates** - Use `createWebSocketEventHandler` for rapid events
4. **Avoid object recreation** - Store derived state (counts, flags) in the store
5. **Use shallow comparison** - Import `shallow` from `zustand/shallow` for object selectors

```typescript
import { shallow } from 'zustand/shallow';

// Good: Uses shallow comparison for object
const { cpu, gpu } = useStore(
  (state) => ({ cpu: state.cpu, gpu: state.gpu }),
  shallow
);

// Bad: Creates new object each render, always triggers re-render
const metrics = useStore((state) => ({ cpu: state.cpu, gpu: state.gpu }));

// Best: Use auto-selectors
const cpu = useStore.use.cpu();
const gpu = useStore.use.gpu();
```

## Adding New Stores

1. Determine update frequency:
   - Low: Use `createImmerStore`
   - High (WebSocket): Use `createImmerSelectorStore` with batching

2. Define state interface with data, derived state, and actions

3. Create store with appropriate middleware

4. Export selectors for common queries

5. Add comprehensive tests including:
   - Initial state
   - All actions
   - Selectors
   - subscribeWithSelector behavior (if applicable)
   - Immutability verification (if using Immer)

## Adding New Widgets

1. Add widget ID to `WidgetId` type in `dashboard-config-store.ts`
2. Add widget config to `DEFAULT_WIDGETS` array
3. Update `DashboardLayout.tsx` to handle the new widget
4. Add render function prop to `DashboardLayoutProps`

## Storage Key

Configuration is stored in localStorage under the key `'dashboard-config-v2'`.

## Version Migration

The store uses Zustand's persist middleware with automatic migration support:
- Version 1 (`dashboard-config`): Legacy manual localStorage
- Version 2 (`dashboard-config-v2`): Zustand persist with theme, refresh, compact mode

The `migrate` function in the persist config handles upgrading from v1 to v2 automatically.

## Compatibility Layer

For gradual migration, the store exports compatibility functions:

```typescript
import { getDashboardConfig, setDashboardConfig } from '@/stores/dashboard-config-store';

// Get config in legacy format
const config = getDashboardConfig();

// Set config from legacy format
setDashboardConfig({ widgets: [...], version: 2 });
```

## Related Documentation

- [Zustand Documentation](https://zustand-demo.pmnd.rs/)
- [Immer Documentation](https://immerjs.github.io/immer/)
- [WebSocket Events](../types/websocket-events.ts)
