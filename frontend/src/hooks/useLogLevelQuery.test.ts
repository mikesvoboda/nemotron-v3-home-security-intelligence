/**
 * Tests for useLogLevelQuery hook
 *
 * This hook fetches the current log level from GET /api/debug/log-level
 * for display in the Log Level Adjuster panel.
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useLogLevelQuery } from './useLogLevelQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchLogLevel: vi.fn(),
}));

describe('useLogLevelQuery', () => {
  const mockLogLevelResponse = {
    level: 'INFO',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockResolvedValue(mockLogLevelResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with no error', () => {
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('fetching data', () => {
    it('fetches log level on mount when enabled', async () => {
      renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchLogLevel).toHaveBeenCalledTimes(1);
      });
    });

    it('does not fetch when enabled is false', async () => {
      renderHook(() => useLogLevelQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      // Wait a bit to ensure no call happens
      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchLogLevel).not.toHaveBeenCalled();
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockLogLevelResponse);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch log level';
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
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
    it('derives currentLevel from data', async () => {
      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.currentLevel).toBe('INFO');
      });
    });

    it('returns null currentLevel when data is not loaded', () => {
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.currentLevel).toBeNull();
    });

    it('handles different log levels', async () => {
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockResolvedValue({ level: 'DEBUG' });

      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.currentLevel).toBe('DEBUG');
      });
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new API call', async () => {
      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchLogLevel).toHaveBeenCalledTimes(1);
      });

      await result.current.refetch();

      await waitFor(() => {
        expect(api.fetchLogLevel).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('return values', () => {
    it('returns all expected properties', async () => {
      const { result } = renderHook(() => useLogLevelQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current).toHaveProperty('data');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('currentLevel');
      expect(result.current).toHaveProperty('refetch');
      expect(result.current).toHaveProperty('isRefetching');
    });
  });
});
