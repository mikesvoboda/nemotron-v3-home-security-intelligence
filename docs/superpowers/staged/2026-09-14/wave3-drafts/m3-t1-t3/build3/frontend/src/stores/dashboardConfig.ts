/**
 * Dashboard Configuration Store
 *
 * Manages widget visibility and ordering for the dashboard.
 * Persists configuration to localStorage for cross-session persistence.
 */

// ============================================================================
// Types
// ============================================================================

/**
 * Available dashboard widget identifiers.
 * Each maps to a specific component in the dashboard.
 */
export type WidgetId =
  | 'stats-row'
  | 'ai-summary-row'
  | 'camera-grid'
  | 'activity-feed'
  | 'gpu-stats'
  | 'pipeline-telemetry'
  | 'pipeline-queues';

/**
 * Widget configuration including visibility and display metadata.
 */
export interface WidgetConfig {
  /** Unique identifier for the widget */
  id: WidgetId;
  /** Display name shown in configuration UI */
  name: string;
  /** Description of what the widget shows */
  description: string;
  /** Whether the widget is currently visible */
  visible: boolean;
}

/**
 * Complete dashboard configuration state.
 */
export interface DashboardConfig {
  /** Ordered list of widget configurations */
  widgets: WidgetConfig[];
  /** Version for future migration support */
  version: number;
}

// ============================================================================
// Constants
// ============================================================================

/** LocalStorage key for persisting dashboard configuration */
const STORAGE_KEY = 'dashboard-config';

/** Current configuration version for migration support */
const CONFIG_VERSION = 1;

/**
 * Default widget configurations in display order.
 * New widgets should be added here with visible: true by default.
 */
export const DEFAULT_WIDGETS: WidgetConfig[] = [
  {
    id: 'stats-row',
    name: 'Stats Row',
    description:
      'Key metrics including active cameras, events today, risk level, and system status',
    visible: true,
  },
  {
    id: 'ai-summary-row',
    name: 'AI Performance Summary',
    description:
      'AI model health indicators for RT-DETRv2, Nemotron, queue depths, throughput, and errors',
    visible: true,
  },
  {
    id: 'camera-grid',
    name: 'Camera Grid',
    description: 'Live camera feeds with status indicators',
    visible: true,
  },
  {
    id: 'activity-feed',
    name: 'Activity Feed',
    description: 'Real-time security event feed with thumbnails and risk badges',
    visible: true,
  },
  {
    id: 'gpu-stats',
    name: 'GPU Statistics',
    description: 'GPU utilization, memory, temperature, and inference metrics',
    visible: false,
  },
  {
    id: 'pipeline-telemetry',
    name: 'Pipeline Telemetry',
    description: 'AI pipeline latency, throughput, and error metrics',
    visible: false,
  },
  {
    id: 'pipeline-queues',
    name: 'Pipeline Queues',
    description: 'Detection and analysis queue depths',
    visible: false,
  },
];

/**
 * Default dashboard configuration.
 */
export const DEFAULT_CONFIG: DashboardConfig = {
  widgets: DEFAULT_WIDGETS,
  version: CONFIG_VERSION,
};

// ============================================================================
// Storage Functions
// ============================================================================

/**
 * Loads dashboard configuration from localStorage.
 * Returns default configuration if no saved config exists or on parse error.
 *
 * @returns The loaded or default dashboard configuration
 */
export function loadDashboardConfig(): DashboardConfig {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };
    }

    const parsed = JSON.parse(stored) as DashboardConfig;

    // Validate structure
    if (!parsed.widgets || !Array.isArray(parsed.widgets)) {
      console.warn('Invalid dashboard config structure, using defaults');
      return { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };
    }

    // Merge with defaults to handle new widgets added in updates
    const mergedWidgets = mergeWidgetsWithDefaults(parsed.widgets);

    return {
      widgets: mergedWidgets,
      version: parsed.version ?? CONFIG_VERSION,
    };
  } catch (error) {
    console.error('Failed to load dashboard config:', error);
    return { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };
  }
}

/**
 * Saves dashboard configuration to localStorage.
 *
 * @param config - The configuration to save
 */
export function saveDashboardConfig(config: DashboardConfig): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  } catch (error) {
    console.error('Failed to save dashboard config:', error);
  }
}

/**
 * Resets dashboard configuration to defaults.
 * Removes the stored config and returns default configuration.
 *
 * @returns The default dashboard configuration
 */
export function resetDashboardConfig(): DashboardConfig {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.error('Failed to reset dashboard config:', error);
  }
  return { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };
}

// ============================================================================
// Widget Management Functions
// ============================================================================

/**
 * Merges saved widgets with defaults to handle new widgets.
 * Preserves user preferences for existing widgets while adding new ones.
 *
 * @param savedWidgets - Previously saved widget configurations
 * @returns Merged widget configurations with all available widgets
 */
function mergeWidgetsWithDefaults(savedWidgets: WidgetConfig[]): WidgetConfig[] {
  const savedWidgetMap = new Map(savedWidgets.map((w) => [w.id, w]));
  const result: WidgetConfig[] = [];

  // First, add all saved widgets in their saved order
  for (const widget of savedWidgets) {
    const defaultWidget = DEFAULT_WIDGETS.find((w) => w.id === widget.id);
    if (defaultWidget) {
      result.push({
        ...defaultWidget, // Use default name/description in case they changed
        visible: widget.visible, // Preserve visibility preference
      });
    }
  }

  // Then, add any new widgets that weren't in saved config
  for (const defaultWidget of DEFAULT_WIDGETS) {
    if (!savedWidgetMap.has(defaultWidget.id)) {
      result.push({ ...defaultWidget });
    }
  }

  return result;
}

/**
 * Updates visibility for a specific widget.
 *
 * @param config - Current dashboard configuration
 * @param widgetId - ID of widget to update
 * @param visible - New visibility state
 * @returns Updated configuration
 */
export function setWidgetVisibility(
  config: DashboardConfig,
  widgetId: WidgetId,
  visible: boolean
): DashboardConfig {
  return {
    ...config,
    widgets: config.widgets.map((widget) =>
      widget.id === widgetId ? { ...widget, visible } : widget
    ),
  };
}

/**
 * Moves a widget up in the display order.
 *
 * @param config - Current dashboard configuration
 * @param widgetId - ID of widget to move
 * @returns Updated configuration
 */
export function moveWidgetUp(config: DashboardConfig, widgetId: WidgetId): DashboardConfig {
  const widgets = [...config.widgets];
  const index = widgets.findIndex((w) => w.id === widgetId);

  if (index <= 0) {
    return config; // Already at top or not found
  }

  // Swap with previous widget
  [widgets[index - 1], widgets[index]] = [widgets[index], widgets[index - 1]];

  return { ...config, widgets };
}

/**
 * Moves a widget down in the display order.
 *
 * @param config - Current dashboard configuration
 * @param widgetId - ID of widget to move
 * @returns Updated configuration
 */
export function moveWidgetDown(config: DashboardConfig, widgetId: WidgetId): DashboardConfig {
  const widgets = [...config.widgets];
  const index = widgets.findIndex((w) => w.id === widgetId);

  if (index < 0 || index >= widgets.length - 1) {
    return config; // Already at bottom or not found
  }

  // Swap with next widget
  [widgets[index], widgets[index + 1]] = [widgets[index + 1], widgets[index]];

  return { ...config, widgets };
}

/**
 * Gets only the visible widgets in display order.
 *
 * @param config - Dashboard configuration
 * @returns Array of visible widget configurations
 */
export function getVisibleWidgets(config: DashboardConfig): WidgetConfig[] {
  return config.widgets.filter((widget) => widget.visible);
}

/**
 * Checks if a specific widget is visible.
 *
 * @param config - Dashboard configuration
 * @param widgetId - ID of widget to check
 * @returns Whether the widget is visible
 */
export function isWidgetVisible(config: DashboardConfig, widgetId: WidgetId): boolean {
  const widget = config.widgets.find((w) => w.id === widgetId);
  return widget?.visible ?? false;
}
