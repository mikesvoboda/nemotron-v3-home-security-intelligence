/**
 * Tests for Settings State Management Store (NEM-3786)
 *
 * Tests Zustand 5 patterns including:
 * - Immer middleware for immutable updates
 * - Persist middleware for localStorage
 * - useShallow hooks for selective subscriptions
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  DEFAULT_SETTINGS_STATE,
  SETTINGS_STORAGE_KEY,
  useAmbientSettings,
  useAudioSettings,
  useDesktopNotificationSettingsHook,
  useFaviconSettings,
  useFullSettings,
  useSettingsActions,
  useSettingsStore,
} from './settings-store';

describe('useSettingsStore', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    // Reset store to initial state
    useSettingsStore.setState({ ...DEFAULT_SETTINGS_STATE });
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('initialization', () => {
    it('initializes with default settings', () => {
      const state = useSettingsStore.getState();

      expect(state.ambientStatus.ambient.enabled).toBe(true);
      expect(state.ambientStatus.audio.enabled).toBe(true);
      expect(state.ambientStatus.audio.volume).toBe(0.5);
      expect(state.ambientStatus.desktopNotifications.enabled).toBe(true);
      expect(state.ambientStatus.desktopNotifications.suppressWhenFocused).toBe(false);
      expect(state.ambientStatus.favicon.enabled).toBe(true);
    });
  });

  describe('ambient settings', () => {
    it('updates ambient enabled state using Immer', () => {
      const initialState = useSettingsStore.getState();

      act(() => {
        useSettingsStore.getState().setAmbientEnabled(false);
      });

      const newState = useSettingsStore.getState();
      expect(newState.ambientStatus.ambient.enabled).toBe(false);
      // Verify immutability - state objects should be different references
      expect(newState.ambientStatus).not.toBe(initialState.ambientStatus);
    });

    it('persists ambient enabled to localStorage', async () => {
      act(() => {
        useSettingsStore.getState().setAmbientEnabled(false);
      });

      // Wait for persist middleware to update localStorage
      await waitFor(() => {
        const saved = JSON.parse(localStorage.getItem(SETTINGS_STORAGE_KEY) ?? '{}');
        expect(saved.state?.ambientStatus?.ambient?.enabled).toBe(false);
      });
    });
  });

  describe('audio settings', () => {
    it('updates audio enabled state', () => {
      act(() => {
        useSettingsStore.getState().setAudioEnabled(false);
      });

      expect(useSettingsStore.getState().ambientStatus.audio.enabled).toBe(false);
    });

    it('updates audio volume', () => {
      act(() => {
        useSettingsStore.getState().setAudioVolume(0.7);
      });

      expect(useSettingsStore.getState().ambientStatus.audio.volume).toBe(0.7);
    });

    it('clamps audio volume to valid range', () => {
      act(() => {
        useSettingsStore.getState().setAudioVolume(1.5);
      });
      expect(useSettingsStore.getState().ambientStatus.audio.volume).toBe(1);

      act(() => {
        useSettingsStore.getState().setAudioVolume(-0.5);
      });
      expect(useSettingsStore.getState().ambientStatus.audio.volume).toBe(0);
    });

    it('persists audio settings to localStorage', async () => {
      act(() => {
        useSettingsStore.getState().setAudioEnabled(false);
      });

      act(() => {
        useSettingsStore.getState().setAudioVolume(0.3);
      });

      await waitFor(() => {
        const saved = JSON.parse(localStorage.getItem(SETTINGS_STORAGE_KEY) ?? '{}');
        expect(saved.state?.ambientStatus?.audio?.enabled).toBe(false);
        expect(saved.state?.ambientStatus?.audio?.volume).toBe(0.3);
      });
    });
  });

  describe('desktop notification settings', () => {
    it('updates desktop notifications enabled state', () => {
      act(() => {
        useSettingsStore.getState().setDesktopNotificationsEnabled(false);
      });

      expect(useSettingsStore.getState().ambientStatus.desktopNotifications.enabled).toBe(false);
    });

    it('updates suppress when focused setting', () => {
      act(() => {
        useSettingsStore.getState().setSuppressNotificationsWhenFocused(true);
      });

      expect(
        useSettingsStore.getState().ambientStatus.desktopNotifications.suppressWhenFocused
      ).toBe(true);
    });

    it('persists desktop notification settings to localStorage', async () => {
      act(() => {
        useSettingsStore.getState().setDesktopNotificationsEnabled(false);
      });

      act(() => {
        useSettingsStore.getState().setSuppressNotificationsWhenFocused(true);
      });

      await waitFor(() => {
        const saved = JSON.parse(localStorage.getItem(SETTINGS_STORAGE_KEY) ?? '{}');
        expect(saved.state?.ambientStatus?.desktopNotifications?.enabled).toBe(false);
        expect(saved.state?.ambientStatus?.desktopNotifications?.suppressWhenFocused).toBe(true);
      });
    });
  });

  describe('favicon settings', () => {
    it('updates favicon badge enabled state', () => {
      act(() => {
        useSettingsStore.getState().setFaviconBadgeEnabled(false);
      });

      expect(useSettingsStore.getState().ambientStatus.favicon.enabled).toBe(false);
    });

    it('persists favicon settings to localStorage', async () => {
      act(() => {
        useSettingsStore.getState().setFaviconBadgeEnabled(false);
      });

      await waitFor(() => {
        const saved = JSON.parse(localStorage.getItem(SETTINGS_STORAGE_KEY) ?? '{}');
        expect(saved.state?.ambientStatus?.favicon?.enabled).toBe(false);
      });
    });
  });

  describe('bulk operations', () => {
    it('updates multiple settings at once with updateSettings', () => {
      act(() => {
        useSettingsStore.getState().updateSettings({
          ambientStatus: {
            ambient: { enabled: false },
            audio: { enabled: false, volume: 0.2 },
            desktopNotifications: { enabled: false, suppressWhenFocused: true },
            favicon: { enabled: false },
          },
        });
      });

      const state = useSettingsStore.getState();
      expect(state.ambientStatus.ambient.enabled).toBe(false);
      expect(state.ambientStatus.audio.enabled).toBe(false);
      expect(state.ambientStatus.audio.volume).toBe(0.2);
      expect(state.ambientStatus.desktopNotifications.enabled).toBe(false);
      expect(state.ambientStatus.desktopNotifications.suppressWhenFocused).toBe(true);
      expect(state.ambientStatus.favicon.enabled).toBe(false);
    });

    it('resets all settings to defaults', () => {
      // Change some settings
      act(() => {
        useSettingsStore.getState().setAmbientEnabled(false);
        useSettingsStore.getState().setAudioVolume(0.2);
        useSettingsStore.getState().setDesktopNotificationsEnabled(false);
      });

      // Reset
      act(() => {
        useSettingsStore.getState().resetSettings();
      });

      const state = useSettingsStore.getState();
      expect(state.ambientStatus.ambient.enabled).toBe(
        DEFAULT_SETTINGS_STATE.ambientStatus.ambient.enabled
      );
      expect(state.ambientStatus.audio.volume).toBe(
        DEFAULT_SETTINGS_STATE.ambientStatus.audio.volume
      );
      expect(state.ambientStatus.desktopNotifications.enabled).toBe(
        DEFAULT_SETTINGS_STATE.ambientStatus.desktopNotifications.enabled
      );
    });

    it('enables all ambient status features', () => {
      // Disable all first
      act(() => {
        useSettingsStore.getState().disableAllAmbientStatus();
      });

      const disabledState = useSettingsStore.getState();
      expect(disabledState.ambientStatus.ambient.enabled).toBe(false);
      expect(disabledState.ambientStatus.audio.enabled).toBe(false);
      expect(disabledState.ambientStatus.desktopNotifications.enabled).toBe(false);
      expect(disabledState.ambientStatus.favicon.enabled).toBe(false);

      // Enable all
      act(() => {
        useSettingsStore.getState().enableAllAmbientStatus();
      });

      const enabledState = useSettingsStore.getState();
      expect(enabledState.ambientStatus.ambient.enabled).toBe(true);
      expect(enabledState.ambientStatus.audio.enabled).toBe(true);
      expect(enabledState.ambientStatus.desktopNotifications.enabled).toBe(true);
      expect(enabledState.ambientStatus.favicon.enabled).toBe(true);
    });

    it('disables all ambient status features', () => {
      act(() => {
        useSettingsStore.getState().disableAllAmbientStatus();
      });

      const state = useSettingsStore.getState();
      expect(state.ambientStatus.ambient.enabled).toBe(false);
      expect(state.ambientStatus.audio.enabled).toBe(false);
      expect(state.ambientStatus.desktopNotifications.enabled).toBe(false);
      expect(state.ambientStatus.favicon.enabled).toBe(false);
    });
  });

  describe('immutability (Immer middleware)', () => {
    it('maintains immutability when updating nested state', () => {
      const initialState = useSettingsStore.getState();
      const initialAmbientStatus = initialState.ambientStatus;
      const initialAudio = initialState.ambientStatus.audio;

      act(() => {
        useSettingsStore.getState().setAudioVolume(0.8);
      });

      const newState = useSettingsStore.getState();

      // New state should be different reference
      expect(newState.ambientStatus).not.toBe(initialAmbientStatus);
      expect(newState.ambientStatus.audio).not.toBe(initialAudio);

      // Original objects should be unchanged
      expect(initialAudio.volume).toBe(0.5);
      expect(newState.ambientStatus.audio.volume).toBe(0.8);
    });
  });
});

// ============================================================================
// Shallow Hook Tests
// ============================================================================

describe('useShallow hooks', () => {
  beforeEach(() => {
    localStorage.clear();
    useSettingsStore.setState({ ...DEFAULT_SETTINGS_STATE });
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('useAmbientSettings', () => {
    it('returns ambient settings and setter', () => {
      const { result } = renderHook(() => useAmbientSettings());

      expect(result.current.enabled).toBe(true);
      expect(typeof result.current.setAmbientEnabled).toBe('function');
    });

    it('updates when ambient enabled changes', () => {
      const { result } = renderHook(() => useAmbientSettings());

      act(() => {
        result.current.setAmbientEnabled(false);
      });

      expect(result.current.enabled).toBe(false);
    });
  });

  describe('useAudioSettings', () => {
    it('returns audio settings and setters', () => {
      const { result } = renderHook(() => useAudioSettings());

      expect(result.current.audioEnabled).toBe(true);
      expect(result.current.audioVolume).toBe(0.5);
      expect(typeof result.current.setAudioEnabled).toBe('function');
      expect(typeof result.current.setAudioVolume).toBe('function');
    });

    it('updates when audio settings change', () => {
      const { result } = renderHook(() => useAudioSettings());

      act(() => {
        result.current.setAudioEnabled(false);
        result.current.setAudioVolume(0.3);
      });

      expect(result.current.audioEnabled).toBe(false);
      expect(result.current.audioVolume).toBe(0.3);
    });
  });

  describe('useDesktopNotificationSettingsHook', () => {
    it('returns desktop notification settings and setters', () => {
      const { result } = renderHook(() => useDesktopNotificationSettingsHook());

      expect(result.current.desktopNotificationsEnabled).toBe(true);
      expect(result.current.suppressNotificationsWhenFocused).toBe(false);
      expect(typeof result.current.setDesktopNotificationsEnabled).toBe('function');
      expect(typeof result.current.setSuppressNotificationsWhenFocused).toBe('function');
    });

    it('updates when desktop notification settings change', () => {
      const { result } = renderHook(() => useDesktopNotificationSettingsHook());

      act(() => {
        result.current.setDesktopNotificationsEnabled(false);
        result.current.setSuppressNotificationsWhenFocused(true);
      });

      expect(result.current.desktopNotificationsEnabled).toBe(false);
      expect(result.current.suppressNotificationsWhenFocused).toBe(true);
    });
  });

  describe('useFaviconSettings', () => {
    it('returns favicon settings and setter', () => {
      const { result } = renderHook(() => useFaviconSettings());

      expect(result.current.faviconBadgeEnabled).toBe(true);
      expect(typeof result.current.setFaviconBadgeEnabled).toBe('function');
    });

    it('updates when favicon enabled changes', () => {
      const { result } = renderHook(() => useFaviconSettings());

      act(() => {
        result.current.setFaviconBadgeEnabled(false);
      });

      expect(result.current.faviconBadgeEnabled).toBe(false);
    });
  });

  describe('useSettingsActions', () => {
    it('returns bulk action functions', () => {
      const { result } = renderHook(() => useSettingsActions());

      expect(typeof result.current.updateSettings).toBe('function');
      expect(typeof result.current.resetSettings).toBe('function');
      expect(typeof result.current.enableAllAmbientStatus).toBe('function');
      expect(typeof result.current.disableAllAmbientStatus).toBe('function');
    });

    it('actions work correctly', () => {
      const { result } = renderHook(() => useSettingsActions());

      act(() => {
        result.current.disableAllAmbientStatus();
      });

      const state = useSettingsStore.getState();
      expect(state.ambientStatus.ambient.enabled).toBe(false);
      expect(state.ambientStatus.audio.enabled).toBe(false);
    });
  });

  describe('useFullSettings', () => {
    it('returns full ambient status settings', () => {
      const { result } = renderHook(() => useFullSettings());

      expect(result.current.ambientStatus).toEqual(DEFAULT_SETTINGS_STATE.ambientStatus);
    });

    it('updates when any setting changes', () => {
      const { result } = renderHook(() => useFullSettings());

      act(() => {
        useSettingsStore.getState().setAudioVolume(0.8);
      });

      expect(result.current.ambientStatus.audio.volume).toBe(0.8);
    });
  });
});

// ============================================================================
// LocalStorage Error Handling Tests
// ============================================================================

describe('localStorage error handling', () => {
  beforeEach(() => {
    localStorage.clear();
    useSettingsStore.setState({ ...DEFAULT_SETTINGS_STATE });
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('handles localStorage read errors gracefully', () => {
    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    // Store invalid JSON
    localStorage.setItem(SETTINGS_STORAGE_KEY, 'invalid json');

    // Should not throw - store will use defaults
    const state = useSettingsStore.getState();
    expect(state.ambientStatus.ambient.enabled).toBe(true);

    consoleWarnSpy.mockRestore();
  });

  it('handles localStorage write errors gracefully', () => {
    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    // Mock localStorage.setItem to throw
    const originalSetItem = localStorage.setItem.bind(localStorage);
    localStorage.setItem = vi.fn().mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });

    // Should not throw when updating
    act(() => {
      useSettingsStore.getState().setAudioVolume(0.8);
    });

    // State should still be updated in memory
    expect(useSettingsStore.getState().ambientStatus.audio.volume).toBe(0.8);

    localStorage.setItem = originalSetItem;
    consoleWarnSpy.mockRestore();
    consoleErrorSpy.mockRestore();
  });
});
