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
 * Settings for audio notifications
 */
export interface AudioSettings {
  /**
   * Whether audio notifications are enabled
   * @default true
   */
  enabled: boolean;
  /**
   * Volume level (0.0 to 1.0)
   * @default 0.5
   */
  volume: number;
}

/**
 * Settings for desktop notifications
 */
export interface DesktopNotificationSettings {
  /**
   * Whether desktop notifications are enabled
   * @default true
   */
  enabled: boolean;
  /**
   * Whether to suppress notifications when window has focus
   * @default false
   */
  suppressWhenFocused: boolean;
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
  audio: AudioSettings;
  desktopNotifications: DesktopNotificationSettings;
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
    audio: {
      enabled: true,
      volume: 0.5,
    },
    desktopNotifications: {
      enabled: true,
      suppressWhenFocused: false,
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

  // Audio settings
  /**
   * Whether audio is enabled
   */
  audioEnabled: boolean;
  /**
   * Set audio enabled state
   */
  setAudioEnabled: (enabled: boolean) => void;
  /**
   * Current audio volume (0.0 to 1.0)
   */
  audioVolume: number;
  /**
   * Set audio volume
   */
  setAudioVolume: (volume: number) => void;

  // Desktop notification settings
  /**
   * Whether desktop notifications are enabled
   */
  desktopNotificationsEnabled: boolean;
  /**
   * Set desktop notifications enabled state
   */
  setDesktopNotificationsEnabled: (enabled: boolean) => void;
  /**
   * Whether to suppress notifications when window has focus
   */
  suppressNotificationsWhenFocused: boolean;
  /**
   * Set suppress when focused state
   */
  setSuppressNotificationsWhenFocused: (suppress: boolean) => void;

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
 *
 * @example
 * ```tsx
 * const {
 *   ambientEnabled,
 *   setAmbientEnabled,
 *   audioEnabled,
 *   setAudioEnabled,
 *   audioVolume,
 *   setAudioVolume,
 * } = useSettings();
 *
 * // Toggle ambient effects
 * <Switch checked={ambientEnabled} onChange={setAmbientEnabled} />
 *
 * // Volume slider
 * <input
 *   type="range"
 *   min={0}
 *   max={1}
 *   step={0.1}
 *   value={audioVolume}
 *   onChange={(e) => setAudioVolume(Number(e.target.value))}
 * />
 * ```
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
        audio: {
          ...DEFAULT_SETTINGS.ambientStatus.audio,
          ...settings?.ambientStatus?.audio,
        },
        desktopNotifications: {
          ...DEFAULT_SETTINGS.ambientStatus.desktopNotifications,
          ...settings?.ambientStatus?.desktopNotifications,
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

  // Audio settings
  const setAudioEnabled = useCallback(
    (enabled: boolean) => {
      setSettings((prev) => ({
        ...prev,
        ambientStatus: {
          ...prev.ambientStatus,
          audio: {
            ...prev.ambientStatus.audio,
            enabled,
          },
        },
      }));
    },
    [setSettings]
  );

  const setAudioVolume = useCallback(
    (volume: number) => {
      const clampedVolume = Math.max(0, Math.min(1, volume));
      setSettings((prev) => ({
        ...prev,
        ambientStatus: {
          ...prev.ambientStatus,
          audio: {
            ...prev.ambientStatus.audio,
            volume: clampedVolume,
          },
        },
      }));
    },
    [setSettings]
  );

  // Desktop notification settings
  const setDesktopNotificationsEnabled = useCallback(
    (enabled: boolean) => {
      setSettings((prev) => ({
        ...prev,
        ambientStatus: {
          ...prev.ambientStatus,
          desktopNotifications: {
            ...prev.ambientStatus.desktopNotifications,
            enabled,
          },
        },
      }));
    },
    [setSettings]
  );

  const setSuppressNotificationsWhenFocused = useCallback(
    (suppress: boolean) => {
      setSettings((prev) => ({
        ...prev,
        ambientStatus: {
          ...prev.ambientStatus,
          desktopNotifications: {
            ...prev.ambientStatus.desktopNotifications,
            suppressWhenFocused: suppress,
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
        audio: { ...prev.ambientStatus.audio, enabled: true },
        desktopNotifications: { ...prev.ambientStatus.desktopNotifications, enabled: true },
        favicon: { ...prev.ambientStatus.favicon, enabled: true },
      },
    }));
  }, [setSettings]);

  const disableAllAmbientStatus = useCallback(() => {
    setSettings((prev) => ({
      ...prev,
      ambientStatus: {
        ambient: { ...prev.ambientStatus.ambient, enabled: false },
        audio: { ...prev.ambientStatus.audio, enabled: false },
        desktopNotifications: { ...prev.ambientStatus.desktopNotifications, enabled: false },
        favicon: { ...prev.ambientStatus.favicon, enabled: false },
      },
    }));
  }, [setSettings]);

  return {
    settings: normalizedSettings,

    // Ambient
    ambientEnabled: normalizedSettings.ambientStatus.ambient.enabled,
    setAmbientEnabled,

    // Audio
    audioEnabled: normalizedSettings.ambientStatus.audio.enabled,
    setAudioEnabled,
    audioVolume: normalizedSettings.ambientStatus.audio.volume,
    setAudioVolume,

    // Desktop notifications
    desktopNotificationsEnabled: normalizedSettings.ambientStatus.desktopNotifications.enabled,
    setDesktopNotificationsEnabled,
    suppressNotificationsWhenFocused:
      normalizedSettings.ambientStatus.desktopNotifications.suppressWhenFocused,
    setSuppressNotificationsWhenFocused,

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
