/**
 * Settings State Management Store (NEM-3786)
 *
 * Zustand 5 migration of the useSettings hook with:
 * - Immer middleware for immutable updates with mutable syntax
 * - Persist middleware for localStorage persistence
 * - useShallow hooks for optimized selective subscriptions
 * - createWithEqualityFn pattern for custom equality checks
 *
 * This store manages application settings including:
 * - Ambient visual effects
 * - Audio notifications
 * - Desktop notifications
 * - Favicon badge settings
 */

import { produce, type Draft } from 'immer';
import { create } from 'zustand';
import { createJSONStorage, devtools, persist } from 'zustand/middleware';
import { useShallow } from 'zustand/shallow';

// ============================================================================
// Types
// ============================================================================

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
 * Complete application settings state
 */
export interface AppSettingsState {
  ambientStatus: AmbientStatusSettings;
}

/**
 * Settings store actions
 */
export interface SettingsActions {
  // Ambient settings
  setAmbientEnabled: (enabled: boolean) => void;

  // Audio settings
  setAudioEnabled: (enabled: boolean) => void;
  setAudioVolume: (volume: number) => void;

  // Desktop notification settings
  setDesktopNotificationsEnabled: (enabled: boolean) => void;
  setSuppressNotificationsWhenFocused: (suppress: boolean) => void;

  // Favicon settings
  setFaviconBadgeEnabled: (enabled: boolean) => void;

  // Bulk operations
  updateSettings: (updates: Partial<AppSettingsState>) => void;
  resetSettings: () => void;
  enableAllAmbientStatus: () => void;
  disableAllAmbientStatus: () => void;
}

/**
 * Combined store type for state and actions
 */
export type SettingsStore = AppSettingsState & SettingsActions;

// ============================================================================
// Constants
// ============================================================================

/** LocalStorage key for persisting settings */
export const SETTINGS_STORAGE_KEY = 'security-dashboard-settings-v2';

/** Current settings version for migration support */
export const SETTINGS_VERSION = 2;

/**
 * Default settings values
 */
export const DEFAULT_SETTINGS_STATE: AppSettingsState = {
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

// ============================================================================
// Immer-enhanced set helper
// ============================================================================

type ImmerSetState<T> = (
  partial: T | Partial<T> | ((state: Draft<T>) => void),
  replace?: boolean
) => void;

/**
 * Creates an Immer-enhanced setState function
 */
function createImmerSet<T>(
  set: (
    partial: T | Partial<T> | ((state: T) => T | Partial<T>),
    replace?: boolean
  ) => void,
  get: () => T
): ImmerSetState<T> {
  return (partial, replace) => {
    if (typeof partial === 'function') {
      const nextState = produce(get(), partial as (draft: Draft<T>) => void);
      set(nextState, replace);
    } else {
      set(partial, replace);
    }
  };
}

// ============================================================================
// Migration Functions
// ============================================================================

/**
 * Migrate from old settings format (v1) to new format (v2)
 */
function migrateFromV1(): AppSettingsState | null {
  try {
    const v1Data = localStorage.getItem('security-dashboard-settings');
    if (!v1Data) return null;

    const parsed = JSON.parse(v1Data) as Partial<AppSettingsState>;
    if (!parsed.ambientStatus) {
      return null;
    }

    // Merge with defaults to ensure all fields exist
    return {
      ambientStatus: {
        ambient: {
          ...DEFAULT_SETTINGS_STATE.ambientStatus.ambient,
          ...parsed.ambientStatus?.ambient,
        },
        audio: {
          ...DEFAULT_SETTINGS_STATE.ambientStatus.audio,
          ...parsed.ambientStatus?.audio,
        },
        desktopNotifications: {
          ...DEFAULT_SETTINGS_STATE.ambientStatus.desktopNotifications,
          ...parsed.ambientStatus?.desktopNotifications,
        },
        favicon: {
          ...DEFAULT_SETTINGS_STATE.ambientStatus.favicon,
          ...parsed.ambientStatus?.favicon,
        },
      },
    };
  } catch {
    return null;
  }
}

// ============================================================================
// Store
// ============================================================================

/**
 * Zustand store for application settings with Zustand 5 patterns.
 *
 * Features:
 * - Immer middleware for immutable updates with mutable syntax
 * - Persist middleware for automatic localStorage persistence
 * - DevTools integration for debugging
 * - Schema versioning with automatic migration
 * - useShallow hooks for optimized selective subscriptions
 *
 * @example
 * ```tsx
 * import { useSettingsStore, useAmbientSettings } from '@/stores/settings-store';
 *
 * // Full store access
 * const { ambientStatus, setAudioVolume } = useSettingsStore();
 *
 * // Optimized selective subscription (won't re-render on other changes)
 * const { audioEnabled, audioVolume } = useAudioSettings();
 *
 * // Change audio volume
 * setAudioVolume(0.8);
 * ```
 */
export const useSettingsStore = create<SettingsStore>()(
  devtools(
    persist(
      (set, get, _store) => {
        // Create Immer-enhanced set function
        const immerSet = createImmerSet<SettingsStore>(
          set as (
            partial: SettingsStore | Partial<SettingsStore> | ((state: SettingsStore) => SettingsStore | Partial<SettingsStore>),
            replace?: boolean
          ) => void,
          get
        );

        return {
          // Initial state
          ...DEFAULT_SETTINGS_STATE,

          // Ambient settings actions
          setAmbientEnabled: (enabled: boolean) => {
            immerSet((draft) => {
              draft.ambientStatus.ambient.enabled = enabled;
            });
          },

          // Audio settings actions
          setAudioEnabled: (enabled: boolean) => {
            immerSet((draft) => {
              draft.ambientStatus.audio.enabled = enabled;
            });
          },

          setAudioVolume: (volume: number) => {
            const clampedVolume = Math.max(0, Math.min(1, volume));
            immerSet((draft) => {
              draft.ambientStatus.audio.volume = clampedVolume;
            });
          },

          // Desktop notification settings actions
          setDesktopNotificationsEnabled: (enabled: boolean) => {
            immerSet((draft) => {
              draft.ambientStatus.desktopNotifications.enabled = enabled;
            });
          },

          setSuppressNotificationsWhenFocused: (suppress: boolean) => {
            immerSet((draft) => {
              draft.ambientStatus.desktopNotifications.suppressWhenFocused = suppress;
            });
          },

          // Favicon settings actions
          setFaviconBadgeEnabled: (enabled: boolean) => {
            immerSet((draft) => {
              draft.ambientStatus.favicon.enabled = enabled;
            });
          },

          // Bulk operations
          updateSettings: (updates: Partial<AppSettingsState>) => {
            immerSet((draft) => {
              if (updates.ambientStatus) {
                if (updates.ambientStatus.ambient) {
                  Object.assign(draft.ambientStatus.ambient, updates.ambientStatus.ambient);
                }
                if (updates.ambientStatus.audio) {
                  Object.assign(draft.ambientStatus.audio, updates.ambientStatus.audio);
                }
                if (updates.ambientStatus.desktopNotifications) {
                  Object.assign(
                    draft.ambientStatus.desktopNotifications,
                    updates.ambientStatus.desktopNotifications
                  );
                }
                if (updates.ambientStatus.favicon) {
                  Object.assign(draft.ambientStatus.favicon, updates.ambientStatus.favicon);
                }
              }
            });
          },

          resetSettings: () => {
            set({ ...DEFAULT_SETTINGS_STATE }, false);
          },

          enableAllAmbientStatus: () => {
            immerSet((draft) => {
              draft.ambientStatus.ambient.enabled = true;
              draft.ambientStatus.audio.enabled = true;
              draft.ambientStatus.desktopNotifications.enabled = true;
              draft.ambientStatus.favicon.enabled = true;
            });
          },

          disableAllAmbientStatus: () => {
            immerSet((draft) => {
              draft.ambientStatus.ambient.enabled = false;
              draft.ambientStatus.audio.enabled = false;
              draft.ambientStatus.desktopNotifications.enabled = false;
              draft.ambientStatus.favicon.enabled = false;
            });
          },
        };
      },
      {
        name: SETTINGS_STORAGE_KEY,
        storage: createJSONStorage(() => localStorage),
        version: SETTINGS_VERSION,
        migrate: (persistedState, version) => {
          // Handle migration from no version or version 1
          if (version === 0 || version === 1 || !persistedState) {
            // Try to migrate from V1 localStorage
            const v1State = migrateFromV1();
            if (v1State) {
              // Clean up old V1 storage
              try {
                localStorage.removeItem('security-dashboard-settings');
              } catch {
                // Ignore cleanup errors
              }
              return v1State as SettingsStore;
            }
            // Return fresh defaults if no V1 data
            return { ...DEFAULT_SETTINGS_STATE } as SettingsStore;
          }

          // For current version, merge with defaults to handle new fields
          const state = persistedState as Partial<AppSettingsState>;
          return {
            ambientStatus: {
              ambient: {
                ...DEFAULT_SETTINGS_STATE.ambientStatus.ambient,
                ...state.ambientStatus?.ambient,
              },
              audio: {
                ...DEFAULT_SETTINGS_STATE.ambientStatus.audio,
                ...state.ambientStatus?.audio,
              },
              desktopNotifications: {
                ...DEFAULT_SETTINGS_STATE.ambientStatus.desktopNotifications,
                ...state.ambientStatus?.desktopNotifications,
              },
              favicon: {
                ...DEFAULT_SETTINGS_STATE.ambientStatus.favicon,
                ...state.ambientStatus?.favicon,
              },
            },
          } as SettingsStore;
        },
        partialize: (state) => ({
          ambientStatus: state.ambientStatus,
        }),
      }
    ),
    { name: 'settings-store', enabled: import.meta.env.DEV }
  )
);

// ============================================================================
// Selectors
// ============================================================================

/**
 * Selector for all ambient status settings
 */
export const selectAmbientStatus = (state: SettingsStore): AmbientStatusSettings => {
  return state.ambientStatus;
};

/**
 * Selector for ambient enabled status
 */
export const selectAmbientEnabled = (state: SettingsStore): boolean => {
  return state.ambientStatus.ambient.enabled;
};

/**
 * Selector for audio settings
 */
export const selectAudioSettings = (state: SettingsStore): AudioSettings => {
  return state.ambientStatus.audio;
};

/**
 * Selector for desktop notification settings
 */
export const selectDesktopNotificationSettings = (
  state: SettingsStore
): DesktopNotificationSettings => {
  return state.ambientStatus.desktopNotifications;
};

/**
 * Selector for favicon settings
 */
export const selectFaviconSettings = (state: SettingsStore): FaviconSettings => {
  return state.ambientStatus.favicon;
};

/**
 * Selector to check if any notification feature is enabled
 */
export const selectHasAnyNotificationEnabled = (state: SettingsStore): boolean => {
  return (
    state.ambientStatus.audio.enabled ||
    state.ambientStatus.desktopNotifications.enabled ||
    state.ambientStatus.favicon.enabled
  );
};

// ============================================================================
// Shallow Hooks for Selective Subscriptions (Zustand 5 Pattern)
// ============================================================================

/**
 * Hook to select ambient settings with shallow equality.
 * Prevents re-renders when other settings change.
 *
 * @example
 * ```tsx
 * const { enabled, setAmbientEnabled } = useAmbientSettings();
 * ```
 */
export function useAmbientSettings() {
  return useSettingsStore(
    useShallow((state) => ({
      enabled: state.ambientStatus.ambient.enabled,
      setAmbientEnabled: state.setAmbientEnabled,
    }))
  );
}

/**
 * Hook to select audio settings with shallow equality.
 * Prevents re-renders when other settings change.
 *
 * @example
 * ```tsx
 * const { audioEnabled, audioVolume, setAudioEnabled, setAudioVolume } = useAudioSettings();
 * ```
 */
export function useAudioSettings() {
  return useSettingsStore(
    useShallow((state) => ({
      audioEnabled: state.ambientStatus.audio.enabled,
      audioVolume: state.ambientStatus.audio.volume,
      setAudioEnabled: state.setAudioEnabled,
      setAudioVolume: state.setAudioVolume,
    }))
  );
}

/**
 * Hook to select desktop notification settings with shallow equality.
 * Prevents re-renders when other settings change.
 *
 * @example
 * ```tsx
 * const {
 *   desktopNotificationsEnabled,
 *   suppressNotificationsWhenFocused,
 *   setDesktopNotificationsEnabled,
 *   setSuppressNotificationsWhenFocused,
 * } = useDesktopNotificationSettingsHook();
 * ```
 */
export function useDesktopNotificationSettingsHook() {
  return useSettingsStore(
    useShallow((state) => ({
      desktopNotificationsEnabled: state.ambientStatus.desktopNotifications.enabled,
      suppressNotificationsWhenFocused:
        state.ambientStatus.desktopNotifications.suppressWhenFocused,
      setDesktopNotificationsEnabled: state.setDesktopNotificationsEnabled,
      setSuppressNotificationsWhenFocused: state.setSuppressNotificationsWhenFocused,
    }))
  );
}

/**
 * Hook to select favicon settings with shallow equality.
 * Prevents re-renders when other settings change.
 *
 * @example
 * ```tsx
 * const { faviconBadgeEnabled, setFaviconBadgeEnabled } = useFaviconSettings();
 * ```
 */
export function useFaviconSettings() {
  return useSettingsStore(
    useShallow((state) => ({
      faviconBadgeEnabled: state.ambientStatus.favicon.enabled,
      setFaviconBadgeEnabled: state.setFaviconBadgeEnabled,
    }))
  );
}

/**
 * Hook to select bulk settings actions.
 * Actions are stable references and don't cause re-renders.
 *
 * @example
 * ```tsx
 * const { updateSettings, resetSettings, enableAllAmbientStatus, disableAllAmbientStatus } = useSettingsActions();
 * ```
 */
export function useSettingsActions() {
  return useSettingsStore(
    useShallow((state) => ({
      updateSettings: state.updateSettings,
      resetSettings: state.resetSettings,
      enableAllAmbientStatus: state.enableAllAmbientStatus,
      disableAllAmbientStatus: state.disableAllAmbientStatus,
    }))
  );
}

/**
 * Hook to get full settings state (for compatibility with existing code).
 * Use the more specific hooks above for better performance.
 *
 * @example
 * ```tsx
 * const settings = useFullSettings();
 * // settings.ambientStatus.audio.volume
 * ```
 */
export function useFullSettings() {
  return useSettingsStore(
    useShallow((state) => ({
      ambientStatus: state.ambientStatus,
    }))
  );
}
