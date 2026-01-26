/**
 * Tests for Centralized Store Index (NEM-3789)
 *
 * Verifies that all stores and utilities are properly exported
 * from the centralized index file.
 */

import { describe, expect, it } from 'vitest';

import * as stores from './index';

describe('stores/index', () => {
  describe('middleware utilities', () => {
    it('exports Immer utilities', () => {
      expect(typeof stores.produce).toBe('function');
      expect(typeof stores.castDraft).toBe('function');
      expect(typeof stores.current).toBe('function');
      expect(typeof stores.isDraft).toBe('function');
      expect(typeof stores.original).toBe('function');
    });

    it('exports shallow utilities', () => {
      expect(typeof stores.shallow).toBe('function');
      expect(typeof stores.useShallow).toBe('function');
      expect(typeof stores.subscribeWithSelector).toBe('function');
    });

    it('exports store creators', () => {
      expect(typeof stores.createImmerStore).toBe('function');
      expect(typeof stores.createImmerSelectorStore).toBe('function');
      expect(typeof stores.createImmerDevtoolsStore).toBe('function');
    });

    it('exports utility functions', () => {
      expect(typeof stores.applyImmerUpdate).toBe('function');
      expect(typeof stores.createImmerAction).toBe('function');
      expect(typeof stores.safeReadCurrent).toBe('function');
      expect(typeof stores.safeReadOriginal).toBe('function');
      expect(typeof stores.combineImmerUpdates).toBe('function');
      expect(typeof stores.createShallowSelector).toBe('function');
      expect(typeof stores.shallowEqual).toBe('function');
      expect(typeof stores.createComputedSelector).toBe('function');
    });

    it('exports transient utilities', () => {
      expect(typeof stores.createTransientSlice).toBe('function');
      expect(typeof stores.createTransientBatcher).toBe('function');
    });

    it('exports WebSocket utilities', () => {
      expect(typeof stores.createWebSocketEventHandler).toBe('function');
      expect(typeof stores.createDebouncedUpdater).toBe('function');
    });
  });

  describe('settings store exports', () => {
    it('exports useSettingsStore', () => {
      expect(stores.useSettingsStore).toBeDefined();
      expect(typeof stores.useSettingsStore).toBe('function');
      expect(typeof stores.useSettingsStore.getState).toBe('function');
      expect(typeof stores.useSettingsStore.setState).toBe('function');
    });

    it('exports settings constants', () => {
      expect(typeof stores.SETTINGS_STORAGE_KEY).toBe('string');
      expect(typeof stores.SETTINGS_VERSION).toBe('number');
      expect(stores.DEFAULT_SETTINGS_STATE).toBeDefined();
    });

    it('exports settings selectors', () => {
      expect(typeof stores.selectAmbientStatus).toBe('function');
      expect(typeof stores.selectAmbientEnabled).toBe('function');
      expect(typeof stores.selectAudioSettings).toBe('function');
      expect(typeof stores.selectDesktopNotificationSettings).toBe('function');
      expect(typeof stores.selectFaviconSettings).toBe('function');
      expect(typeof stores.selectHasAnyNotificationEnabled).toBe('function');
    });

    it('exports settings shallow hooks', () => {
      expect(typeof stores.useAmbientSettings).toBe('function');
      expect(typeof stores.useAudioSettings).toBe('function');
      expect(typeof stores.useDesktopNotificationSettingsHook).toBe('function');
      expect(typeof stores.useFaviconSettings).toBe('function');
      expect(typeof stores.useSettingsActions).toBe('function');
      expect(typeof stores.useFullSettings).toBe('function');
    });
  });

  describe('dashboard config store exports', () => {
    it('exports useDashboardConfigStore', () => {
      expect(stores.useDashboardConfigStore).toBeDefined();
      expect(typeof stores.useDashboardConfigStore).toBe('function');
    });

    it('exports dashboard config constants', () => {
      expect(typeof stores.DASHBOARD_CONFIG_STORAGE_KEY).toBe('string');
      expect(typeof stores.DASHBOARD_CONFIG_VERSION).toBe('number');
      expect(typeof stores.DEFAULT_REFRESH_INTERVAL).toBe('number');
      expect(Array.isArray(stores.DEFAULT_WIDGETS)).toBe(true);
      expect(stores.DEFAULT_CONFIG_STATE).toBeDefined();
    });

    it('exports dashboard config selectors', () => {
      expect(typeof stores.selectVisibleWidgets).toBe('function');
      expect(typeof stores.selectIsWidgetVisible).toBe('function');
      expect(typeof stores.selectWidgetById).toBe('function');
      expect(typeof stores.selectWidgetIndex).toBe('function');
      expect(typeof stores.selectCanMoveUp).toBe('function');
      expect(typeof stores.selectCanMoveDown).toBe('function');
      expect(typeof stores.selectEffectiveTheme).toBe('function');
    });

    it('exports dashboard config compatibility functions', () => {
      expect(typeof stores.getDashboardConfig).toBe('function');
      expect(typeof stores.setDashboardConfig).toBe('function');
    });
  });

  describe('prometheus alert store exports', () => {
    it('exports usePrometheusAlertStore', () => {
      expect(stores.usePrometheusAlertStore).toBeDefined();
      expect(typeof stores.usePrometheusAlertStore).toBe('function');
    });

    it('exports prometheus alert selectors', () => {
      expect(typeof stores.selectCriticalAlerts).toBe('function');
      expect(typeof stores.selectWarningAlerts).toBe('function');
      expect(typeof stores.selectInfoAlerts).toBe('function');
      expect(typeof stores.selectAlertsSortedBySeverity).toBe('function');
      expect(typeof stores.selectAlertByFingerprint).toBe('function');
      expect(typeof stores.selectAlertsByName).toBe('function');
      expect(typeof stores.selectHasActiveAlerts).toBe('function');
      expect(typeof stores.selectHasCriticalAlerts).toBe('function');
    });
  });

  describe('rate limit store exports', () => {
    it('exports useRateLimitStore', () => {
      expect(stores.useRateLimitStore).toBeDefined();
      expect(typeof stores.useRateLimitStore).toBe('function');
    });

    it('exports rate limit selectors', () => {
      expect(typeof stores.selectRateLimitUsagePercent).toBe('function');
      expect(typeof stores.selectIsHighUsage).toBe('function');
    });

    it('exports rate limit shallow hooks', () => {
      expect(typeof stores.useRateLimitStatus).toBe('function');
      expect(typeof stores.useRateLimitCurrent).toBe('function');
      expect(typeof stores.useRateLimitActions).toBe('function');
    });
  });

  describe('realtime metrics store exports', () => {
    it('exports useRealtimeMetricsStore', () => {
      expect(stores.useRealtimeMetricsStore).toBeDefined();
      expect(typeof stores.useRealtimeMetricsStore).toBe('function');
    });

    it('exports WebSocket event handlers', () => {
      expect(typeof stores.handleGPUStatsEvent).toBe('function');
      expect(typeof stores.handlePipelineMetricsEvent).toBe('function');
      expect(typeof stores.handleInferenceMetricsEvent).toBe('function');
    });

    it('exports realtime metrics selectors', () => {
      expect(typeof stores.selectGPUUtilization).toBe('function');
      expect(typeof stores.selectGPUMemoryUtilization).toBe('function');
      expect(typeof stores.selectGPUTemperature).toBe('function');
      expect(typeof stores.selectPipelineThroughput).toBe('function');
      expect(typeof stores.selectTotalQueueDepth).toBe('function');
      expect(typeof stores.selectPipelineErrorRate).toBe('function');
      expect(typeof stores.selectCombinedModelLatency).toBe('function');
      expect(typeof stores.selectGPUHealthStatus).toBe('function');
      expect(typeof stores.selectPipelineHealthStatus).toBe('function');
    });
  });

  describe('storage status store exports', () => {
    it('exports useStorageStatusStore', () => {
      expect(stores.useStorageStatusStore).toBeDefined();
      expect(typeof stores.useStorageStatusStore).toBe('function');
    });

    it('exports storage status constants', () => {
      expect(typeof stores.CRITICAL_USAGE_THRESHOLD).toBe('number');
      expect(typeof stores.HIGH_USAGE_THRESHOLD).toBe('number');
    });

    it('exports storage status selectors', () => {
      expect(typeof stores.selectFormattedUsage).toBe('function');
    });

    it('exports storage status shallow hooks', () => {
      expect(typeof stores.useStorageWarningStatus).toBe('function');
      expect(typeof stores.useStorageStatus).toBe('function');
      expect(typeof stores.useStorageActions).toBe('function');
    });
  });

  describe('worker status store exports', () => {
    it('exports useWorkerStatusStore', () => {
      expect(stores.useWorkerStatusStore).toBeDefined();
      expect(typeof stores.useWorkerStatusStore).toBe('function');
    });

    it('exports worker status selectors', () => {
      expect(typeof stores.selectErrorWorkers).toBe('function');
      expect(typeof stores.selectWarningWorkers).toBe('function');
      expect(typeof stores.selectRunningWorkers).toBe('function');
      expect(typeof stores.selectWorkerByName).toBe('function');
      expect(typeof stores.selectWorkersByType).toBe('function');
    });
  });

  describe('store consistency', () => {
    it('all stores have getState and setState', () => {
      const storeNames = [
        'useSettingsStore',
        'useDashboardConfigStore',
        'usePrometheusAlertStore',
        'useRateLimitStore',
        'useRealtimeMetricsStore',
        'useStorageStatusStore',
        'useWorkerStatusStore',
      ] as const;

      for (const name of storeNames) {
        const store = stores[name];
        expect(typeof store.getState).toBe('function');
        expect(typeof store.setState).toBe('function');
        expect(typeof store.subscribe).toBe('function');
      }
    });
  });
});
