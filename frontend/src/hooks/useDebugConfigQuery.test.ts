/**
 * Tests for useDebugConfigQuery hook
 *
 * This hook fetches the application configuration from GET /api/debug/config
 * and provides the config key-value pairs for display in the Config Inspector panel.
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useDebugConfigQuery } from './useDebugConfigQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchDebugConfig: vi.fn(),
}));

describe('useDebugConfigQuery', () => {
  const mockConfigResponse = {
    database_url: '[REDACTED]',
    redis_url: '[REDACTED]',
    debug_mode: true,
    log_level: 'INFO',
    api_key: '[REDACTED]',
    retention_days: 30,
    batch_window_seconds: 90,
    max_connections: 100,
    null_value: null,
    empty_string: '',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockConfigResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with no error', () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('fetching data', () => {
    it('fetches config on mount when enabled', async () => {
      renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchDebugConfig).toHaveBeenCalledTimes(1);
      });
    });

    it('does not fetch when enabled is false', async () => {
      renderHook(() => useDebugConfigQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      // Wait a bit to ensure no call happens
      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchDebugConfig).not.toHaveBeenCalled();
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockConfigResponse);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch config';
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
          expect(result.current.error?.message).toBe(errorMessage);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('derived values', () => {
    it('derives configEntries as key-value array', async () => {
      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.configEntries.length).toBeGreaterThan(0);
      });

      // Check that entries contain expected structure
      const entries = result.current.configEntries;
      const databaseUrlEntry = entries.find((e) => e.key === 'database_url');
      expect(databaseUrlEntry).toBeDefined();
      expect(databaseUrlEntry?.value).toBe('[REDACTED]');

      const logLevelEntry = entries.find((e) => e.key === 'log_level');
      expect(logLevelEntry).toBeDefined();
      expect(logLevelEntry?.value).toBe('INFO');

      const debugModeEntry = entries.find((e) => e.key === 'debug_mode');
      expect(debugModeEntry).toBeDefined();
      expect(debugModeEntry?.value).toBe(true);

      const retentionEntry = entries.find((e) => e.key === 'retention_days');
      expect(retentionEntry).toBeDefined();
      expect(retentionEntry?.value).toBe(30);
    });

    it('identifies sensitive values', async () => {
      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.configEntries.length).toBeGreaterThan(0);
      });

      const entries = result.current.configEntries;
      const databaseEntry = entries.find((e) => e.key === 'database_url');
      expect(databaseEntry).toBeDefined();
      expect(databaseEntry?.isSensitive).toBe(true);

      const logLevelEntry = entries.find((e) => e.key === 'log_level');
      expect(logLevelEntry).toBeDefined();
      expect(logLevelEntry?.isSensitive).toBe(false);
    });

    it('returns empty configEntries when data is not loaded', () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.configEntries).toEqual([]);
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new API call', async () => {
      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchDebugConfig).toHaveBeenCalledTimes(1);
      });

      await result.current.refetch();

      await waitFor(() => {
        expect(api.fetchDebugConfig).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('return values', () => {
    it('returns all expected properties', async () => {
      const { result } = renderHook(() => useDebugConfigQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current).toHaveProperty('data');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('configEntries');
      expect(result.current).toHaveProperty('refetch');
      expect(result.current).toHaveProperty('isRefetching');
    });
  });
});
