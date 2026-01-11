import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useSettings, DEFAULT_SETTINGS } from './useSettings';

describe('useSettings', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('initialization', () => {
    it('initializes with default settings when localStorage is empty', () => {
      const { result } = renderHook(() => useSettings());

      expect(result.current.ambientEnabled).toBe(DEFAULT_SETTINGS.ambientStatus.ambient.enabled);
      expect(result.current.audioEnabled).toBe(DEFAULT_SETTINGS.ambientStatus.audio.enabled);
      expect(result.current.audioVolume).toBe(DEFAULT_SETTINGS.ambientStatus.audio.volume);
      expect(result.current.desktopNotificationsEnabled).toBe(
        DEFAULT_SETTINGS.ambientStatus.desktopNotifications.enabled
      );
      expect(result.current.faviconBadgeEnabled).toBe(
        DEFAULT_SETTINGS.ambientStatus.favicon.enabled
      );
    });

    it('loads settings from localStorage', () => {
      const savedSettings = {
        ambientStatus: {
          ambient: { enabled: false },
          audio: { enabled: false, volume: 0.3 },
          desktopNotifications: { enabled: false, suppressWhenFocused: true },
          favicon: { enabled: false },
        },
      };

      localStorage.setItem('security-dashboard-settings', JSON.stringify(savedSettings));

      const { result } = renderHook(() => useSettings());

      expect(result.current.ambientEnabled).toBe(false);
      expect(result.current.audioEnabled).toBe(false);
      expect(result.current.audioVolume).toBe(0.3);
      expect(result.current.desktopNotificationsEnabled).toBe(false);
      expect(result.current.suppressNotificationsWhenFocused).toBe(true);
      expect(result.current.faviconBadgeEnabled).toBe(false);
    });

    it('merges partial saved settings with defaults', () => {
      const partialSettings = {
        ambientStatus: {
          audio: { volume: 0.8 },
        },
      };

      localStorage.setItem('security-dashboard-settings', JSON.stringify(partialSettings));

      const { result } = renderHook(() => useSettings());

      // Custom value should be loaded
      expect(result.current.audioVolume).toBe(0.8);
      // Defaults should be used for missing values
      expect(result.current.ambientEnabled).toBe(true);
      expect(result.current.audioEnabled).toBe(true);
    });
  });

  describe('ambient settings', () => {
    it('updates ambient enabled state', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setAmbientEnabled(false);
      });

      expect(result.current.ambientEnabled).toBe(false);
    });

    it('persists ambient enabled to localStorage', async () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setAmbientEnabled(false);
      });

      // Wait for localStorage to be updated
      await waitFor(() => {
        const saved = JSON.parse(localStorage.getItem('security-dashboard-settings') ?? '{}');
        expect(saved.ambientStatus?.ambient?.enabled).toBe(false);
      });
    });
  });

  describe('audio settings', () => {
    it('updates audio enabled state', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setAudioEnabled(false);
      });

      expect(result.current.audioEnabled).toBe(false);
    });

    it('updates audio volume', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setAudioVolume(0.7);
      });

      expect(result.current.audioVolume).toBe(0.7);
    });

    it('clamps audio volume to valid range', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setAudioVolume(1.5);
      });
      expect(result.current.audioVolume).toBe(1);

      act(() => {
        result.current.setAudioVolume(-0.5);
      });
      expect(result.current.audioVolume).toBe(0);
    });

    it('persists audio settings to localStorage', async () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setAudioEnabled(false);
      });

      act(() => {
        result.current.setAudioVolume(0.3);
      });

      // Wait for localStorage to be updated
      await waitFor(() => {
        const saved = JSON.parse(localStorage.getItem('security-dashboard-settings') ?? '{}');
        expect(saved.ambientStatus?.audio?.enabled).toBe(false);
        expect(saved.ambientStatus?.audio?.volume).toBe(0.3);
      });
    });
  });

  describe('desktop notification settings', () => {
    it('updates desktop notifications enabled state', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setDesktopNotificationsEnabled(false);
      });

      expect(result.current.desktopNotificationsEnabled).toBe(false);
    });

    it('updates suppress when focused setting', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setSuppressNotificationsWhenFocused(true);
      });

      expect(result.current.suppressNotificationsWhenFocused).toBe(true);
    });

    it('persists desktop notification settings to localStorage', async () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setDesktopNotificationsEnabled(false);
      });

      act(() => {
        result.current.setSuppressNotificationsWhenFocused(true);
      });

      // Wait for localStorage to be updated
      await waitFor(() => {
        const saved = JSON.parse(localStorage.getItem('security-dashboard-settings') ?? '{}');
        expect(saved.ambientStatus?.desktopNotifications?.enabled).toBe(false);
        expect(saved.ambientStatus?.desktopNotifications?.suppressWhenFocused).toBe(true);
      });
    });
  });

  describe('favicon settings', () => {
    it('updates favicon badge enabled state', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setFaviconBadgeEnabled(false);
      });

      expect(result.current.faviconBadgeEnabled).toBe(false);
    });

    it('persists favicon settings to localStorage', async () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setFaviconBadgeEnabled(false);
      });

      // Wait for localStorage to be updated
      await waitFor(() => {
        const saved = JSON.parse(localStorage.getItem('security-dashboard-settings') ?? '{}');
        expect(saved.ambientStatus?.favicon?.enabled).toBe(false);
      });
    });
  });

  describe('bulk operations', () => {
    it('updates multiple settings at once with updateSettings', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.updateSettings({
          ambientStatus: {
            ambient: { enabled: false },
            audio: { enabled: false, volume: 0.2 },
            desktopNotifications: { enabled: false, suppressWhenFocused: true },
            favicon: { enabled: false },
          },
        });
      });

      expect(result.current.ambientEnabled).toBe(false);
      expect(result.current.audioEnabled).toBe(false);
      expect(result.current.audioVolume).toBe(0.2);
      expect(result.current.desktopNotificationsEnabled).toBe(false);
      expect(result.current.faviconBadgeEnabled).toBe(false);
    });

    it('resets all settings to defaults', () => {
      const { result } = renderHook(() => useSettings());

      // Change some settings
      act(() => {
        result.current.setAmbientEnabled(false);
        result.current.setAudioVolume(0.2);
        result.current.setDesktopNotificationsEnabled(false);
      });

      // Reset
      act(() => {
        result.current.resetSettings();
      });

      expect(result.current.ambientEnabled).toBe(DEFAULT_SETTINGS.ambientStatus.ambient.enabled);
      expect(result.current.audioVolume).toBe(DEFAULT_SETTINGS.ambientStatus.audio.volume);
      expect(result.current.desktopNotificationsEnabled).toBe(
        DEFAULT_SETTINGS.ambientStatus.desktopNotifications.enabled
      );
    });

    it('enables all ambient status features', () => {
      const { result } = renderHook(() => useSettings());

      // Disable all first
      act(() => {
        result.current.disableAllAmbientStatus();
      });

      expect(result.current.ambientEnabled).toBe(false);
      expect(result.current.audioEnabled).toBe(false);
      expect(result.current.desktopNotificationsEnabled).toBe(false);
      expect(result.current.faviconBadgeEnabled).toBe(false);

      // Enable all
      act(() => {
        result.current.enableAllAmbientStatus();
      });

      expect(result.current.ambientEnabled).toBe(true);
      expect(result.current.audioEnabled).toBe(true);
      expect(result.current.desktopNotificationsEnabled).toBe(true);
      expect(result.current.faviconBadgeEnabled).toBe(true);
    });

    it('disables all ambient status features', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.disableAllAmbientStatus();
      });

      expect(result.current.ambientEnabled).toBe(false);
      expect(result.current.audioEnabled).toBe(false);
      expect(result.current.desktopNotificationsEnabled).toBe(false);
      expect(result.current.faviconBadgeEnabled).toBe(false);
    });
  });

  describe('settings object', () => {
    it('exposes full settings object', () => {
      const { result } = renderHook(() => useSettings());

      expect(result.current.settings).toEqual(
        expect.objectContaining({
          ambientStatus: expect.objectContaining({
            ambient: expect.any(Object),
            audio: expect.any(Object),
            desktopNotifications: expect.any(Object),
            favicon: expect.any(Object),
          }),
        })
      );
    });

    it('settings object updates when individual settings change', () => {
      const { result } = renderHook(() => useSettings());

      const initialSettings = result.current.settings;

      act(() => {
        result.current.setAudioVolume(0.8);
      });

      expect(result.current.settings.ambientStatus.audio.volume).toBe(0.8);
      expect(result.current.settings).not.toBe(initialSettings);
    });
  });

  describe('localStorage error handling', () => {
    it('handles localStorage read errors gracefully', () => {
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      // Store invalid JSON
      localStorage.setItem('security-dashboard-settings', 'invalid json');

      const { result } = renderHook(() => useSettings());

      // Should fall back to defaults
      expect(result.current.ambientEnabled).toBe(DEFAULT_SETTINGS.ambientStatus.ambient.enabled);

      consoleWarnSpy.mockRestore();
    });

    it('handles localStorage write errors gracefully', () => {
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      // Mock localStorage.setItem to throw
      const originalSetItem = localStorage.setItem.bind(localStorage);
      localStorage.setItem = vi.fn().mockImplementation(() => {
        throw new Error('QuotaExceededError');
      });

      const { result } = renderHook(() => useSettings());

      // Should not throw
      act(() => {
        result.current.setAudioVolume(0.8);
      });

      localStorage.setItem = originalSetItem;
      consoleWarnSpy.mockRestore();
    });
  });
});
