import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useSettings, DEFAULT_SETTINGS } from './useSettings';

describe('useSettings', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('initialization', () => {
    it('initializes with default settings when localStorage is empty without retired audio/desktop fields (F-239)', () => {
      const { result } = renderHook(() => useSettings());

      expect(result.current.ambientEnabled).toBe(DEFAULT_SETTINGS.ambientStatus.ambient.enabled);
      expect(result.current.faviconBadgeEnabled).toBe(
        DEFAULT_SETTINGS.ambientStatus.favicon.enabled
      );
      expect('audioEnabled' in result.current).toBe(false);
      expect('desktopNotificationsEnabled' in result.current).toBe(false);
    });

    it('loads settings from localStorage', () => {
      const savedSettings = {
        ambientStatus: {
          ambient: { enabled: false },
          favicon: { enabled: false },
        },
      };

      localStorage.setItem('security-dashboard-settings', JSON.stringify(savedSettings));

      const { result } = renderHook(() => useSettings());

      expect(result.current.ambientEnabled).toBe(false);
      expect(result.current.faviconBadgeEnabled).toBe(false);
    });

    it('merges partial saved settings with defaults', () => {
      const partialSettings = {
        ambientStatus: {
          favicon: { enabled: false },
        },
      };

      localStorage.setItem('security-dashboard-settings', JSON.stringify(partialSettings));

      const { result } = renderHook(() => useSettings());

      expect(result.current.faviconBadgeEnabled).toBe(false);
      expect(result.current.ambientEnabled).toBe(true);
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

      await waitFor(() => {
        const saved = JSON.parse(localStorage.getItem('security-dashboard-settings') ?? '{}');
        expect(saved.ambientStatus?.ambient?.enabled).toBe(false);
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
            favicon: { enabled: false },
          },
        });
      });

      expect(result.current.ambientEnabled).toBe(false);
      expect(result.current.faviconBadgeEnabled).toBe(false);
    });

    it('resets all settings to defaults', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setAmbientEnabled(false);
        result.current.setFaviconBadgeEnabled(false);
      });

      act(() => {
        result.current.resetSettings();
      });

      expect(result.current.ambientEnabled).toBe(DEFAULT_SETTINGS.ambientStatus.ambient.enabled);
      expect(result.current.faviconBadgeEnabled).toBe(
        DEFAULT_SETTINGS.ambientStatus.favicon.enabled
      );
    });

    it('enables all ambient status features', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.disableAllAmbientStatus();
      });

      expect(result.current.ambientEnabled).toBe(false);
      expect(result.current.faviconBadgeEnabled).toBe(false);

      act(() => {
        result.current.enableAllAmbientStatus();
      });

      expect(result.current.ambientEnabled).toBe(true);
      expect(result.current.faviconBadgeEnabled).toBe(true);
    });

    it('disables all ambient status features', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.disableAllAmbientStatus();
      });

      expect(result.current.ambientEnabled).toBe(false);
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
            favicon: expect.any(Object),
          }),
        })
      );
    });

    it('settings object updates when individual settings change', () => {
      const { result } = renderHook(() => useSettings());

      act(() => {
        result.current.setAmbientEnabled(false);
      });

      expect(result.current.settings.ambientStatus.ambient.enabled).toBe(false);
    });
  });
});
