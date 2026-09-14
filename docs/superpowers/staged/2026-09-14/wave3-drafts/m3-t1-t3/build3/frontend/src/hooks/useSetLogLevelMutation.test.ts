/**
 * Tests for useSetLogLevelMutation hook
 *
 * This hook provides a mutation to set the log level via POST /api/debug/log-level
 * with body { "level": "DEBUG" }.
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useSetLogLevelMutation } from './useSetLogLevelMutation';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { LogLevel } from './useSetLogLevelMutation';
import type { SetLogLevelResponse } from '../services/api';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    setLogLevel: vi.fn(),
  };
});

describe('useSetLogLevelMutation', () => {
  const mockSetLogLevelResponse: SetLogLevelResponse = {
    level: 'DEBUG',
    previous_level: 'INFO',
    message: 'Log level changed from INFO to DEBUG',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.setLogLevel as ReturnType<typeof vi.fn>).mockResolvedValue(mockSetLogLevelResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initial state', () => {
    it('starts with isPending false', () => {
      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isPending).toBe(false);
    });

    it('starts with no error', () => {
      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.error).toBeNull();
    });

    it('starts with undefined data', () => {
      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });
  });

  describe('mutation execution', () => {
    it('calls setLogLevel API with correct level', async () => {
      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        void result.current.setLevel('DEBUG');
      });

      await waitFor(() => {
        expect(api.setLogLevel).toHaveBeenCalledWith('DEBUG');
      });
    });

    it('sets isPending true during mutation', async () => {
      let resolvePromise: (value: SetLogLevelResponse) => void;
      (api.setLogLevel as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises -- mock returns Promise
        (): Promise<SetLogLevelResponse> =>
          new Promise<SetLogLevelResponse>((resolve) => {
            resolvePromise = resolve;
          })
      );

      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        void result.current.setLevel('DEBUG');
      });

      await waitFor(() => {
        expect(result.current.isPending).toBe(true);
      });

      act(() => {
        resolvePromise(mockSetLogLevelResponse);
      });

      await waitFor(() => {
        expect(result.current.isPending).toBe(false);
      });
    });

    it('updates data after successful mutation', async () => {
      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        void result.current.setLevel('DEBUG');
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockSetLogLevelResponse);
      });
    });

    it('sets isPending false after mutation completes', async () => {
      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        void result.current.setLevel('DEBUG');
      });

      await waitFor(() => {
        expect(result.current.isPending).toBe(false);
      });
    });

    it('sets error on mutation failure', async () => {
      const error = new Error('Failed to set log level');
      (api.setLogLevel as ReturnType<typeof vi.fn>).mockRejectedValue(error);

      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      await act(async () => {
        try {
          await result.current.setLevel('DEBUG');
        } catch {
          // Expected error - swallow to prevent unhandled rejection
        }
      });

      await waitFor(() => {
        expect(result.current.error).toEqual(error);
      });
    });
  });

  describe('log level types', () => {
    const levels: LogLevel[] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

    it.each(levels)('accepts %s as a valid log level', async (level) => {
      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        void result.current.setLevel(level);
      });

      await waitFor(() => {
        expect(api.setLogLevel).toHaveBeenCalledWith(level);
      });
    });
  });

  describe('reset', () => {
    it('provides reset function', () => {
      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      expect(typeof result.current.reset).toBe('function');
    });

    it('clears data and error on reset', async () => {
      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      act(() => {
        void result.current.setLevel('DEBUG');
      });

      await waitFor(() => {
        expect(result.current.data).toBeDefined();
      });

      act(() => {
        result.current.reset();
      });

      await waitFor(() => {
        expect(result.current.data).toBeUndefined();
        expect(result.current.error).toBeNull();
      });
    });
  });

  describe('return values', () => {
    it('returns all expected properties', () => {
      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current).toHaveProperty('setLevel');
      expect(result.current).toHaveProperty('isPending');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('data');
      expect(result.current).toHaveProperty('reset');
      expect(result.current).toHaveProperty('isSuccess');
    });

    it('isSuccess is true after successful mutation', async () => {
      const { result } = renderHook(() => useSetLogLevelMutation(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isSuccess).toBe(false);

      act(() => {
        void result.current.setLevel('DEBUG');
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });
    });
  });
});
