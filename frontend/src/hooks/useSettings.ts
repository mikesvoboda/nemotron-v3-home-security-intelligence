/**
 * useSettings hook
 *
 * Centralized settings management for the security dashboard.
 * Persists settings to localStorage and provides type-safe access.
 */

import { useCallback, useMemo } from 'react';

import { useLocalStorage } from './useLocalStorage';

/**
 * Settings for ambient visual effects
 */
export interface AmbientSettings {
  /**
   * Whether ambient background effects are enabled
   * @default true
   */
  enabled: boolean;
}

/**
 * Settings for favicon badge
 */
export interface FaviconSettings {
  /**
   * Whether favicon badge is enabled
   * @default true
   */
  enabled: boolean;
}

/**
 * All ambient status awareness settings
 */
export interface AmbientStatusSettings {
  ambient: AmbientSettings;
  favicon: FaviconSettings;
}

/**
 * Complete application settings
 */
export interface AppSettings {
  ambientStatus: AmbientStatusSettings;
}

/**
 * Default settings values
 */
export const DEFAULT_SETTINGS: AppSettings = {
  ambientStatus: {
    ambient: {
      enabled: true,
    },
    favicon: {
      enabled: true,
    },
  },
};

/**
 * LocalStorage key for settings
 */
const SETTINGS_STORAGE_KEY = 'security-dashboard-settings';

export interface UseSettingsReturn {
  /**
   * Current settings
   */
  settings: AppSettings;

  // Ambient settings
  /**
   * Whether ambient effects are enabled
   */
  ambientEnabled: boolean;
  /**
   * Set ambient effects enabled state
   */
  setAmbientEnabled: (enabled: boolean) => void;

  // Favicon settings
  /**
   * Whether favicon badge is enabled
   */
  faviconBadgeEnabled: boolean;
  /**
   * Set favicon badge enabled state
   */
  setFaviconBadgeEnabled: (enabled: boolean) => void;

  // Bulk operations
  /**
   * Update multiple settings at once
   */
  updateSettings: (updates: Partial<AppSettings>) => void;
  /**
   * Reset all settings to defaults
   */
  resetSettings: () => void;
  /**
   * Enable all ambient status features
   */
  enableAllAmbientStatus: () => void;
  /**
   * Disable all ambient status features
   */
  disableAllAmbientStatus: () => void;
}

/**
 * Hook to manage application settings with localStorage persistence.
 */
export function useSettings(): UseSettingsReturn {
  const [settings, setSettings] = useLocalStorage<AppSettings>(
    SETTINGS_STORAGE_KEY,
    DEFAULT_SETTINGS
  );

  // Ensure settings have all required properties (handles migration from old versions)
  const normalizedSettings = useMemo((): AppSettings => {
    return {
      ambientStatus: {
        ambient: {
          ...DEFAULT_SETTINGS.ambientStatus.ambient,
          ...settings?.ambientStatus?.ambient,
        },
        favicon: {
          ...DEFAULT_SETTINGS.ambientStatus.favicon,
          ...settings?.ambientStatus?.favicon,
        },
      },
    };
  }, [settings]);

  // Ambient settings
  const setAmbientEnabled = useCallback(
    (enabled: boolean) => {
      setSettings((prev) => ({
        ...prev,
        ambientStatus: {
          ...prev.ambientStatus,
          ambient: {
            ...prev.ambientStatus.ambient,
            enabled,
          },
        },
      }));
    },
    [setSettings]
  );

  // Favicon settings
  const setFaviconBadgeEnabled = useCallback(
    (enabled: boolean) => {
      setSettings((prev) => ({
        ...prev,
        ambientStatus: {
          ...prev.ambientStatus,
          favicon: {
            ...prev.ambientStatus.favicon,
            enabled,
          },
        },
      }));
    },
    [setSettings]
  );

  // Bulk operations
  const updateSettings = useCallback(
    (updates: Partial<AppSettings>) => {
      setSettings((prev) => ({
        ...prev,
        ...updates,
        ambientStatus: {
          ...prev.ambientStatus,
          ...(updates.ambientStatus ?? {}),
        },
      }));
    },
    [setSettings]
  );

  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
  }, [setSettings]);

  const enableAllAmbientStatus = useCallback(() => {
    setSettings((prev) => ({
      ...prev,
      ambientStatus: {
        ambient: { ...prev.ambientStatus.ambient, enabled: true },
        favicon: { ...prev.ambientStatus.favicon, enabled: true },
      },
    }));
  }, [setSettings]);

  const disableAllAmbientStatus = useCallback(() => {
    setSettings((prev) => ({
      ...prev,
      ambientStatus: {
        ambient: { ...prev.ambientStatus.ambient, enabled: false },
        favicon: { ...prev.ambientStatus.favicon, enabled: false },
      },
    }));
  }, [setSettings]);

  return {
    settings: normalizedSettings,

    // Ambient
    ambientEnabled: normalizedSettings.ambientStatus.ambient.enabled,
    setAmbientEnabled,

    // Favicon
    faviconBadgeEnabled: normalizedSettings.ambientStatus.favicon.enabled,
    setFaviconBadgeEnabled,

    // Bulk operations
    updateSettings,
    resetSettings,
    enableAllAmbientStatus,
    disableAllAmbientStatus,
  };
}

export default useSettings;
