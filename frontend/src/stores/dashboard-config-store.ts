/**
 * Dashboard Configuration Zustand Store (NEM-3427, NEM-3401)
 *
 * Manages dashboard widget configuration with persist middleware for localStorage persistence.
 * Replaces the previous manual localStorage handling with Zustand's built-in persist middleware.
 *
 * Features:
 * - Widget visibility and ordering management
 * - Theme setting (light/dark/system)
 * - Auto-refresh interval configuration
 * - Compact mode toggle
 * - Schema versioning for migrations
 * - Automatic localStorage persistence
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

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
 * Theme setting for the dashboard.
 */
export type ThemeSetting = 'light' | 'dark' | 'system';

/**
 * Complete dashboard configuration state.
 */
export interface DashboardConfigState {
  /** Ordered list of widget configurations */
  widgets: WidgetConfig[];
  /** Theme setting (light/dark/system) */
  theme: ThemeSetting;
  /** Auto-refresh interval in milliseconds (0 = disabled) */
  refreshInterval: number;
  /** Whether compact mode is enabled */
  compactMode: boolean;
  /** Version for migration support */
  version: number;
}

/**
 * Dashboard configuration actions.
 */
export interface DashboardConfigActions {
  /** Set visibility for a specific widget */
  setWidgetVisibility: (widgetId: WidgetId, visible: boolean) => void;
  /** Move a widget up in the display order */
  moveWidgetUp: (widgetId: WidgetId) => void;
  /** Move a widget down in the display order */
  moveWidgetDown: (widgetId: WidgetId) => void;
  /** Set the theme setting */
  setTheme: (theme: ThemeSetting) => void;
  /** Set the refresh interval */
  setRefreshInterval: (interval: number) => void;
  /** Toggle compact mode */
  setCompactMode: (enabled: boolean) => void;
  /** Reset configuration to defaults */
  reset: () => void;
}

/**
 * Combined store type for state and actions.
 */
export type DashboardConfigStore = DashboardConfigState & DashboardConfigActions;

// ============================================================================
// Constants
// ============================================================================

/** LocalStorage key for persisting dashboard configuration */
export const STORAGE_KEY = 'dashboard-config-v2';

/** Current configuration version for migration support */
export const CONFIG_VERSION = 2;

/** Default refresh interval (disabled by default) */
export const DEFAULT_REFRESH_INTERVAL = 0;

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
 * Default dashboard configuration state.
 */
export const DEFAULT_CONFIG_STATE: DashboardConfigState = {
  widgets: DEFAULT_WIDGETS,
  theme: 'dark',
  refreshInterval: DEFAULT_REFRESH_INTERVAL,
  compactMode: false,
  version: CONFIG_VERSION,
};

// ============================================================================
// Migration Functions
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
 * Migration function for schema version upgrades.
 * Handles migrating from old dashboard-config format to new dashboard-config-v2.
 */
function migrateFromV1(): DashboardConfigState | null {
  try {
    const v1Data = localStorage.getItem('dashboard-config');
    if (!v1Data) return null;

    const parsed = JSON.parse(v1Data) as { widgets?: WidgetConfig[]; version?: number };
    if (!parsed.widgets || !Array.isArray(parsed.widgets)) {
      return null;
    }

    // Merge old widgets with defaults (handles new widgets)
    const mergedWidgets = mergeWidgetsWithDefaults(parsed.widgets);

    return {
      widgets: mergedWidgets,
      theme: 'dark', // V1 didn't have theme
      refreshInterval: DEFAULT_REFRESH_INTERVAL, // V1 didn't have refresh interval
      compactMode: false, // V1 didn't have compact mode
      version: CONFIG_VERSION,
    };
  } catch {
    return null;
  }
}

// ============================================================================
// Store
// ============================================================================

/**
 * Zustand store for dashboard configuration state management.
 *
 * Features:
 * - Automatic localStorage persistence via persist middleware
 * - Widget visibility and ordering controls
 * - Theme, refresh interval, and compact mode settings
 * - Schema versioning with automatic migration
 *
 * @example
 * ```tsx
 * import { useDashboardConfigStore } from '@/stores/dashboard-config-store';
 *
 * // In a component
 * const { widgets, theme, setWidgetVisibility, setTheme } = useDashboardConfigStore();
 *
 * // Toggle widget visibility
 * setWidgetVisibility('gpu-stats', true);
 *
 * // Change theme
 * setTheme('light');
 *
 * // Use selectors for optimized re-renders
 * const theme = useDashboardConfigStore((state) => state.theme);
 * ```
 */
export const useDashboardConfigStore = create<DashboardConfigStore>()(
  persist(
    (set, get) => ({
      // Initial state
      ...DEFAULT_CONFIG_STATE,

      // Actions
      setWidgetVisibility: (widgetId: WidgetId, visible: boolean) => {
        set((state) => ({
          widgets: state.widgets.map((widget) =>
            widget.id === widgetId ? { ...widget, visible } : widget
          ),
        }));
      },

      moveWidgetUp: (widgetId: WidgetId) => {
        const { widgets } = get();
        const index = widgets.findIndex((w) => w.id === widgetId);

        if (index <= 0) {
          return; // Already at top or not found
        }

        const newWidgets = [...widgets];
        [newWidgets[index - 1], newWidgets[index]] = [newWidgets[index], newWidgets[index - 1]];

        set({ widgets: newWidgets });
      },

      moveWidgetDown: (widgetId: WidgetId) => {
        const { widgets } = get();
        const index = widgets.findIndex((w) => w.id === widgetId);

        if (index < 0 || index >= widgets.length - 1) {
          return; // Already at bottom or not found
        }

        const newWidgets = [...widgets];
        [newWidgets[index], newWidgets[index + 1]] = [newWidgets[index + 1], newWidgets[index]];

        set({ widgets: newWidgets });
      },

      setTheme: (theme: ThemeSetting) => {
        set({ theme });
      },

      setRefreshInterval: (refreshInterval: number) => {
        set({ refreshInterval: Math.max(0, refreshInterval) });
      },

      setCompactMode: (compactMode: boolean) => {
        set({ compactMode });
      },

      reset: () => {
        set({ ...DEFAULT_CONFIG_STATE });
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      version: CONFIG_VERSION,
      migrate: (persistedState, version) => {
        // Type the persisted state
        const state = persistedState as DashboardConfigState | undefined;

        // Handle migration from no version or version 1
        if (version === 0 || version === 1 || !state) {
          // Try to migrate from V1 localStorage
          const v1State = migrateFromV1();
          if (v1State) {
            // Clean up old V1 storage
            try {
              localStorage.removeItem('dashboard-config');
            } catch {
              // Ignore cleanup errors
            }
            return v1State;
          }
          // Return fresh defaults if no V1 data
          return { ...DEFAULT_CONFIG_STATE };
        }

        // For current version, merge widgets with defaults to handle new widgets
        if (state.widgets) {
          return {
            ...state,
            widgets: mergeWidgetsWithDefaults(state.widgets),
            version: CONFIG_VERSION,
          };
        }

        return state as DashboardConfigStore;
      },
      partialize: (state) => ({
        widgets: state.widgets,
        theme: state.theme,
        refreshInterval: state.refreshInterval,
        compactMode: state.compactMode,
        version: state.version,
      }),
    }
  )
);

// ============================================================================
// Selectors
// ============================================================================

/**
 * Selector for visible widgets in display order.
 */
export const selectVisibleWidgets = (state: DashboardConfigStore): WidgetConfig[] => {
  return state.widgets.filter((widget) => widget.visible);
};

/**
 * Selector to check if a specific widget is visible.
 */
export const selectIsWidgetVisible = (state: DashboardConfigStore, widgetId: WidgetId): boolean => {
  const widget = state.widgets.find((w) => w.id === widgetId);
  return widget?.visible ?? false;
};

/**
 * Selector for widget by ID.
 */
export const selectWidgetById = (
  state: DashboardConfigStore,
  widgetId: WidgetId
): WidgetConfig | undefined => {
  return state.widgets.find((w) => w.id === widgetId);
};

/**
 * Selector for widget index by ID.
 */
export const selectWidgetIndex = (state: DashboardConfigStore, widgetId: WidgetId): number => {
  return state.widgets.findIndex((w) => w.id === widgetId);
};

/**
 * Selector to check if widget can move up.
 */
export const selectCanMoveUp = (state: DashboardConfigStore, widgetId: WidgetId): boolean => {
  const index = state.widgets.findIndex((w) => w.id === widgetId);
  return index > 0;
};

/**
 * Selector to check if widget can move down.
 */
export const selectCanMoveDown = (state: DashboardConfigStore, widgetId: WidgetId): boolean => {
  const index = state.widgets.findIndex((w) => w.id === widgetId);
  return index >= 0 && index < state.widgets.length - 1;
};

/**
 * Selector for effective theme (resolves 'system' to actual theme).
 */
export const selectEffectiveTheme = (state: DashboardConfigStore): 'light' | 'dark' => {
  if (state.theme === 'system') {
    // Check system preference
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'dark'; // Default to dark if no window
  }
  return state.theme;
};

// ============================================================================
// Compatibility Layer
// ============================================================================

/**
 * Legacy DashboardConfig type for backward compatibility with existing components.
 */
export interface DashboardConfig {
  widgets: WidgetConfig[];
  version: number;
}

/**
 * Creates a DashboardConfig object for compatibility with existing components.
 * Use this when interfacing with components that expect the old DashboardConfig structure.
 */
export function getDashboardConfig(): DashboardConfig {
  const state = useDashboardConfigStore.getState();
  return {
    widgets: state.widgets,
    version: state.version,
  };
}

/**
 * Updates the store from a DashboardConfig object.
 * Use this when interfacing with components that provide the old DashboardConfig structure.
 */
export function setDashboardConfig(config: DashboardConfig): void {
  useDashboardConfigStore.setState({
    widgets: config.widgets,
    version: config.version,
  });
}
