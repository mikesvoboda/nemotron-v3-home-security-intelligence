import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  DEFAULT_CONFIG,
  DEFAULT_WIDGETS,
  getVisibleWidgets,
  isWidgetVisible,
  loadDashboardConfig,
  moveWidgetDown,
  moveWidgetUp,
  resetDashboardConfig,
  saveDashboardConfig,
  setWidgetVisibility,
  type DashboardConfig,
  type WidgetId,
} from './dashboardConfig';

describe('dashboardConfig store', () => {
  // Mock localStorage
  const mockStorage: Record<string, string> = {};

  beforeEach(() => {
    // Clear mock storage
    Object.keys(mockStorage).forEach((key) => delete mockStorage[key]);

    // Mock localStorage
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(
      (key: string) => mockStorage[key] ?? null
    );
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key: string, value: string) => {
      mockStorage[key] = value;
    });
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((key: string) => {
      delete mockStorage[key];
    });
  });

  describe('DEFAULT_CONFIG', () => {
    it('has expected default widgets', () => {
      expect(DEFAULT_CONFIG.widgets).toHaveLength(6);
      expect(DEFAULT_CONFIG.version).toBe(1);
    });

    it('has stats-row, camera-grid, and activity-feed visible by default', () => {
      const visibleWidgets = DEFAULT_CONFIG.widgets.filter((w) => w.visible);
      expect(visibleWidgets.map((w) => w.id)).toEqual([
        'stats-row',
        'camera-grid',
        'activity-feed',
      ]);
    });

    it('has gpu-stats, pipeline-telemetry, and pipeline-queues hidden by default', () => {
      const hiddenWidgets = DEFAULT_CONFIG.widgets.filter((w) => !w.visible);
      expect(hiddenWidgets.map((w) => w.id)).toEqual([
        'gpu-stats',
        'pipeline-telemetry',
        'pipeline-queues',
      ]);
    });

    it('each widget has required properties', () => {
      for (const widget of DEFAULT_CONFIG.widgets) {
        expect(widget).toHaveProperty('id');
        expect(widget).toHaveProperty('name');
        expect(widget).toHaveProperty('description');
        expect(widget).toHaveProperty('visible');
        expect(typeof widget.id).toBe('string');
        expect(typeof widget.name).toBe('string');
        expect(typeof widget.description).toBe('string');
        expect(typeof widget.visible).toBe('boolean');
      }
    });
  });

  describe('loadDashboardConfig', () => {
    it('returns default config when no saved config exists', () => {
      const config = loadDashboardConfig();

      expect(config.widgets).toHaveLength(DEFAULT_WIDGETS.length);
      expect(config.version).toBe(DEFAULT_CONFIG.version);
    });

    it('loads saved config from localStorage', () => {
      const savedConfig: DashboardConfig = {
        widgets: DEFAULT_WIDGETS.map((w) => ({ ...w, visible: true })),
        version: 1,
      };
      mockStorage['dashboard-config'] = JSON.stringify(savedConfig);

      const config = loadDashboardConfig();

      expect(config.widgets.every((w) => w.visible)).toBe(true);
    });

    it('returns default config on invalid JSON', () => {
      mockStorage['dashboard-config'] = 'invalid-json';

      const config = loadDashboardConfig();

      expect(config.widgets).toHaveLength(DEFAULT_WIDGETS.length);
    });

    it('returns default config when widgets array is missing', () => {
      mockStorage['dashboard-config'] = JSON.stringify({ version: 1 });

      const config = loadDashboardConfig();

      expect(config.widgets).toHaveLength(DEFAULT_WIDGETS.length);
    });

    it('merges new widgets when config is outdated', () => {
      // Simulate saved config with fewer widgets
      const oldWidgets = DEFAULT_WIDGETS.slice(0, 3);
      mockStorage['dashboard-config'] = JSON.stringify({
        widgets: oldWidgets,
        version: 1,
      });

      const config = loadDashboardConfig();

      // Should have all widgets including new ones
      expect(config.widgets).toHaveLength(DEFAULT_WIDGETS.length);
    });

    it('preserves visibility preferences for existing widgets', () => {
      const savedWidgets = DEFAULT_WIDGETS.map((w) => ({
        ...w,
        visible: w.id === 'gpu-stats', // Only gpu-stats visible
      }));
      mockStorage['dashboard-config'] = JSON.stringify({
        widgets: savedWidgets,
        version: 1,
      });

      const config = loadDashboardConfig();

      const gpuStats = config.widgets.find((w) => w.id === 'gpu-stats');
      expect(gpuStats?.visible).toBe(true);

      const statsRow = config.widgets.find((w) => w.id === 'stats-row');
      expect(statsRow?.visible).toBe(false);
    });

    it('preserves widget order from saved config', () => {
      const reversedWidgets = [...DEFAULT_WIDGETS].reverse();
      mockStorage['dashboard-config'] = JSON.stringify({
        widgets: reversedWidgets,
        version: 1,
      });

      const config = loadDashboardConfig();

      expect(config.widgets[0].id).toBe(reversedWidgets[0].id);
    });
  });

  describe('saveDashboardConfig', () => {
    it('saves config to localStorage', () => {
      const config: DashboardConfig = {
        widgets: DEFAULT_WIDGETS.map((w) => ({ ...w, visible: true })),
        version: 1,
      };

      saveDashboardConfig(config);

      expect(mockStorage['dashboard-config']).toBeDefined();
      const saved = JSON.parse(mockStorage['dashboard-config']);
      expect(saved.widgets).toHaveLength(DEFAULT_WIDGETS.length);
    });

    it('overwrites existing config', () => {
      mockStorage['dashboard-config'] = JSON.stringify(DEFAULT_CONFIG);

      const newConfig: DashboardConfig = {
        widgets: DEFAULT_WIDGETS.map((w) => ({ ...w, visible: false })),
        version: 1,
      };
      saveDashboardConfig(newConfig);

      const saved = JSON.parse(mockStorage['dashboard-config']);
      expect(saved.widgets.every((w: { visible: boolean }) => !w.visible)).toBe(true);
    });
  });

  describe('resetDashboardConfig', () => {
    it('removes saved config from localStorage', () => {
      mockStorage['dashboard-config'] = JSON.stringify(DEFAULT_CONFIG);

      resetDashboardConfig();

      expect(mockStorage['dashboard-config']).toBeUndefined();
    });

    it('returns default configuration', () => {
      mockStorage['dashboard-config'] = JSON.stringify({
        widgets: DEFAULT_WIDGETS.map((w) => ({ ...w, visible: false })),
        version: 1,
      });

      const config = resetDashboardConfig();

      expect(config.widgets).toEqual(DEFAULT_WIDGETS);
    });
  });

  describe('setWidgetVisibility', () => {
    it('sets widget to visible', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };

      const updated = setWidgetVisibility(config, 'gpu-stats', true);

      const gpuStats = updated.widgets.find((w) => w.id === 'gpu-stats');
      expect(gpuStats?.visible).toBe(true);
    });

    it('sets widget to hidden', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };

      const updated = setWidgetVisibility(config, 'stats-row', false);

      const statsRow = updated.widgets.find((w) => w.id === 'stats-row');
      expect(statsRow?.visible).toBe(false);
    });

    it('does not modify other widgets', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };

      const updated = setWidgetVisibility(config, 'gpu-stats', true);

      const statsRow = updated.widgets.find((w) => w.id === 'stats-row');
      expect(statsRow?.visible).toBe(true); // Still visible
    });

    it('returns new config object (immutable)', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };

      const updated = setWidgetVisibility(config, 'gpu-stats', true);

      expect(updated).not.toBe(config);
      expect(updated.widgets).not.toBe(config.widgets);
    });
  });

  describe('moveWidgetUp', () => {
    it('moves widget up one position', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };
      const originalIndex = config.widgets.findIndex((w) => w.id === 'camera-grid');

      const updated = moveWidgetUp(config, 'camera-grid');

      const newIndex = updated.widgets.findIndex((w) => w.id === 'camera-grid');
      expect(newIndex).toBe(originalIndex - 1);
    });

    it('does not move widget if already at top', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };

      const updated = moveWidgetUp(config, 'stats-row'); // First widget

      expect(updated.widgets[0].id).toBe('stats-row');
      expect(updated).toBe(config); // Same reference (no change)
    });

    it('returns same config if widget not found', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };

      const updated = moveWidgetUp(config, 'nonexistent' as WidgetId);

      expect(updated).toBe(config);
    });

    it('swaps adjacent widgets correctly', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };

      const updated = moveWidgetUp(config, 'camera-grid');

      expect(updated.widgets[0].id).toBe('camera-grid');
      expect(updated.widgets[1].id).toBe('stats-row');
    });
  });

  describe('moveWidgetDown', () => {
    it('moves widget down one position', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };
      const originalIndex = config.widgets.findIndex((w) => w.id === 'camera-grid');

      const updated = moveWidgetDown(config, 'camera-grid');

      const newIndex = updated.widgets.findIndex((w) => w.id === 'camera-grid');
      expect(newIndex).toBe(originalIndex + 1);
    });

    it('does not move widget if already at bottom', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };
      const lastWidget = config.widgets[config.widgets.length - 1];

      const updated = moveWidgetDown(config, lastWidget.id);

      expect(updated.widgets[updated.widgets.length - 1].id).toBe(lastWidget.id);
      expect(updated).toBe(config); // Same reference (no change)
    });

    it('returns same config if widget not found', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };

      const updated = moveWidgetDown(config, 'nonexistent' as WidgetId);

      expect(updated).toBe(config);
    });

    it('swaps adjacent widgets correctly', () => {
      const config = { ...DEFAULT_CONFIG, widgets: [...DEFAULT_WIDGETS] };

      const updated = moveWidgetDown(config, 'stats-row');

      expect(updated.widgets[0].id).toBe('camera-grid');
      expect(updated.widgets[1].id).toBe('stats-row');
    });
  });

  describe('getVisibleWidgets', () => {
    it('returns only visible widgets', () => {
      const visibleWidgets = getVisibleWidgets(DEFAULT_CONFIG);

      expect(visibleWidgets.every((w) => w.visible)).toBe(true);
      expect(visibleWidgets).toHaveLength(3);
    });

    it('returns empty array when no widgets are visible', () => {
      const config: DashboardConfig = {
        widgets: DEFAULT_WIDGETS.map((w) => ({ ...w, visible: false })),
        version: 1,
      };

      const visibleWidgets = getVisibleWidgets(config);

      expect(visibleWidgets).toHaveLength(0);
    });

    it('preserves widget order', () => {
      const config: DashboardConfig = {
        widgets: [...DEFAULT_WIDGETS].reverse(),
        version: 1,
      };

      const visibleWidgets = getVisibleWidgets(config);

      // Should match order of the reversed (and visible) widgets
      const expectedOrder = [...DEFAULT_WIDGETS]
        .reverse()
        .filter((w) => w.visible)
        .map((w) => w.id);
      expect(visibleWidgets.map((w) => w.id)).toEqual(expectedOrder);
    });
  });

  describe('isWidgetVisible', () => {
    it('returns true for visible widgets', () => {
      expect(isWidgetVisible(DEFAULT_CONFIG, 'stats-row')).toBe(true);
      expect(isWidgetVisible(DEFAULT_CONFIG, 'camera-grid')).toBe(true);
      expect(isWidgetVisible(DEFAULT_CONFIG, 'activity-feed')).toBe(true);
    });

    it('returns false for hidden widgets', () => {
      expect(isWidgetVisible(DEFAULT_CONFIG, 'gpu-stats')).toBe(false);
      expect(isWidgetVisible(DEFAULT_CONFIG, 'pipeline-telemetry')).toBe(false);
      expect(isWidgetVisible(DEFAULT_CONFIG, 'pipeline-queues')).toBe(false);
    });

    it('returns false for non-existent widgets', () => {
      expect(isWidgetVisible(DEFAULT_CONFIG, 'nonexistent' as WidgetId)).toBe(false);
    });
  });
});
