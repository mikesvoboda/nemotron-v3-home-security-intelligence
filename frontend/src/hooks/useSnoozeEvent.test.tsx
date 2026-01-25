/**
 * Tests for useSnoozeEvent hook
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';


import { useSnoozeEvent } from './useSnoozeEvent';
import * as api from '../services/api';

import type { ReactNode } from 'react';

// Mock the API module
vi.mock('../services/api', () => ({
  snoozeEvent: vi.fn(),
  clearSnooze: vi.fn(),
}));

describe('useSnoozeEvent', () => {
  const MOCK_NOW = new Date('2024-01-15T12:00:00Z');
  let queryClient: QueryClient;

  // Create a wrapper component for the hook
  function createWrapper() {
    return function Wrapper({ children }: { children: ReactNode }) {
      return (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      );
    };
  }

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(MOCK_NOW);

    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
          staleTime: 0,
        },
        mutations: {
          retry: false,
        },
      },
    });

    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    queryClient.clear();
  });

  it('returns snooze and unsnooze functions', () => {
    const { result } = renderHook(() => useSnoozeEvent(), {
      wrapper: createWrapper(),
    });

    expect(result.current.snooze).toBeDefined();
    expect(result.current.unsnooze).toBeDefined();
    expect(typeof result.current.snooze).toBe('function');
    expect(typeof result.current.unsnooze).toBe('function');
  });

  it('returns isSnoozing and isUnsnoozing states', () => {
    const { result } = renderHook(() => useSnoozeEvent(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isSnoozing).toBe(false);
    expect(result.current.isUnsnoozing).toBe(false);
  });

  it('returns error and reset function', () => {
    const { result } = renderHook(() => useSnoozeEvent(), {
      wrapper: createWrapper(),
    });

    expect(result.current.error).toBeNull();
    expect(result.current.reset).toBeDefined();
    expect(typeof result.current.reset).toBe('function');
  });

  describe('snooze', () => {
    it('calls snoozeEvent API with correct parameters', async () => {
      const mockEvent = {
        id: 123,
        snooze_until: new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString(),
      };

      vi.mocked(api.snoozeEvent).mockResolvedValueOnce(mockEvent as api.Event);

      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.snooze(123, 3600); // 1 hour
      });

      expect(api.snoozeEvent).toHaveBeenCalledWith(123, 3600);
    });

    it('has isSnoozing property', async () => {
      const mockEvent = { id: 123 } as api.Event;
      vi.mocked(api.snoozeEvent).mockResolvedValueOnce(mockEvent);

      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      // isSnoozing should start false
      expect(result.current.isSnoozing).toBe(false);

      // After successful snooze, should return to false
      await act(async () => {
        await result.current.snooze(123, 3600);
      });

      expect(result.current.isSnoozing).toBe(false);
    });

    it('calls onSuccess callback when snooze succeeds', async () => {
      const mockEvent = { id: 123 } as api.Event;
      vi.mocked(api.snoozeEvent).mockResolvedValueOnce(mockEvent);

      const onSuccess = vi.fn();
      const { result } = renderHook(
        () => useSnoozeEvent({ onSuccess }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.snooze(123, 3600);
      });

      expect(onSuccess).toHaveBeenCalledWith(mockEvent, 123, 3600);
    });

    it('calls onError callback when snooze fails', async () => {
      const error = new Error('API Error');
      vi.mocked(api.snoozeEvent).mockRejectedValueOnce(error);

      const onError = vi.fn();
      const { result } = renderHook(
        () => useSnoozeEvent({ onError }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        try {
          await result.current.snooze(123, 3600);
        } catch {
          // Expected to throw
        }
      });

      expect(onError).toHaveBeenCalledWith(error, 123, 3600);
    });

    it('invalidates queries on success by default', async () => {
      const mockEvent = { id: 123 } as api.Event;
      vi.mocked(api.snoozeEvent).mockResolvedValueOnce(mockEvent);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.snooze(123, 3600);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalled();
    });

    it('does not invalidate queries when invalidateQueries is false', async () => {
      const mockEvent = { id: 123 } as api.Event;
      vi.mocked(api.snoozeEvent).mockResolvedValueOnce(mockEvent);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(
        () => useSnoozeEvent({ invalidateQueries: false }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.snooze(123, 3600);
      });

      expect(invalidateQueriesSpy).not.toHaveBeenCalled();
    });
  });

  describe('unsnooze', () => {
    it('calls clearSnooze API with correct parameters', async () => {
      const mockEvent = { id: 123, snooze_until: null } as api.Event;
      vi.mocked(api.clearSnooze).mockResolvedValueOnce(mockEvent);

      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.unsnooze(123);
      });

      expect(api.clearSnooze).toHaveBeenCalledWith(123);
    });

    it('has isUnsnoozing property', async () => {
      const mockEvent = { id: 123 } as api.Event;
      vi.mocked(api.clearSnooze).mockResolvedValueOnce(mockEvent);

      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      // isUnsnoozing should start false
      expect(result.current.isUnsnoozing).toBe(false);

      // After successful unsnooze, should return to false
      await act(async () => {
        await result.current.unsnooze(123);
      });

      expect(result.current.isUnsnoozing).toBe(false);
    });

    it('calls onSuccess callback with 0 seconds when unsnooze succeeds', async () => {
      const mockEvent = { id: 123 } as api.Event;
      vi.mocked(api.clearSnooze).mockResolvedValueOnce(mockEvent);

      const onSuccess = vi.fn();
      const { result } = renderHook(
        () => useSnoozeEvent({ onSuccess }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.unsnooze(123);
      });

      expect(onSuccess).toHaveBeenCalledWith(mockEvent, 123, 0);
    });
  });

  describe('reset', () => {
    it('reset function exists and can be called', () => {
      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      // reset should be a callable function
      expect(typeof result.current.reset).toBe('function');

      // Should not throw when called
      act(() => {
        result.current.reset();
      });
    });
  });
});
