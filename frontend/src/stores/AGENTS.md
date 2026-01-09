# Stores Directory

This directory contains state management stores for the frontend application.

## Overview

Stores manage application state that needs to persist across sessions or be shared across components. Currently using pure TypeScript with localStorage persistence rather than a state management library like Zustand or Redux.

## Files

### `dashboardConfig.ts`

Dashboard widget customization store. Manages:

- **Widget visibility toggles** - Show/hide individual dashboard widgets
- **Widget ordering** - Reorder widgets via up/down controls
- **localStorage persistence** - Configuration survives browser refresh
- **Default configuration** - Sensible defaults for new users

#### Key Types

```typescript
type WidgetId = 'stats-row' | 'camera-grid' | 'activity-feed' | 'gpu-stats' | 'pipeline-telemetry' | 'pipeline-queues';

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

#### Key Functions

| Function | Purpose |
|----------|---------|
| `loadDashboardConfig()` | Load config from localStorage or return defaults |
| `saveDashboardConfig(config)` | Save config to localStorage |
| `resetDashboardConfig()` | Reset to defaults and clear localStorage |
| `setWidgetVisibility(config, id, visible)` | Toggle widget visibility |
| `moveWidgetUp(config, id)` | Move widget up in order |
| `moveWidgetDown(config, id)` | Move widget down in order |
| `getVisibleWidgets(config)` | Get only visible widgets in order |

#### Default Visible Widgets

- Stats Row (metrics)
- Camera Grid (live feeds)
- Activity Feed (events)

#### Default Hidden Widgets

- GPU Statistics
- Pipeline Telemetry
- Pipeline Queues

### `dashboardConfig.test.ts`

Comprehensive test suite (33 tests) covering:

- Default configuration
- localStorage loading/saving
- Widget visibility toggling
- Widget reordering
- Configuration merging (for version migrations)
- Edge cases (invalid JSON, missing fields)

## Usage Pattern

```typescript
// In a React component
const [config, setConfig] = useState<DashboardConfig>(() => loadDashboardConfig());

// Update and persist
const handleToggle = (widgetId: WidgetId, visible: boolean) => {
  const newConfig = setWidgetVisibility(config, widgetId, visible);
  setConfig(newConfig);
  saveDashboardConfig(newConfig);
};

// Reset
const handleReset = () => {
  const defaultConfig = resetDashboardConfig();
  setConfig(defaultConfig);
};
```

## Adding New Widgets

1. Add widget ID to `WidgetId` type
2. Add widget config to `DEFAULT_WIDGETS` array
3. Update `DashboardLayout.tsx` to handle the new widget
4. Add render function prop to `DashboardLayoutProps`

## Storage Key

Configuration is stored in localStorage under the key `'dashboard-config'`.

## Version Migration

The `version` field in `DashboardConfig` supports future schema migrations. The `mergeWidgetsWithDefaults` function ensures new widgets are added when a user's saved config is outdated.
