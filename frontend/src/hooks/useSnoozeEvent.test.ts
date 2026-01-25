/**
 * Tests for useSnoozeEvent hook (NEM-3592)
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useSnoozeEvent } from './useSnoozeEvent';
import * as api from '../services/api';

// Mock API functions
vi.mock('../services/api', () => ({
  snoozeEvent: vi.fn(),
  clearSnooze: vi.fn(),
}));

// Mock query keys
vi.mock('./useAlertsQuery', () => ({
  alertsQueryKeys: {
    all: ['alerts'] as const,
  },
}));

vi.mock('./useEventsQuery', () => ({
  eventsQueryKeys: {
    all: ['events'] as const,
  },
}));

describe('useSnoozeEvent', () => {
  let queryClient: QueryClient;

  const createWrapper = () => {
    return function Wrapper({ children }: { children: React.ReactNode }) {
      return React.createElement(QueryClientProvider, { client: queryClient }, children);
    };
  };

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
        mutations: {
          retry: false,
        },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    queryClient.clear();
  });

  describe('snooze', () => {
    it('calls snoozeEvent API with eventId and seconds', async () => {
      const mockEvent = { id: 1, snooze_until: '2024-01-15T11:00:00Z' };
      vi.mocked(api.snoozeEvent).mockResolvedValue(mockEvent as api.Event);

      const { result } = renderHook(() => useSnoozeEvent(), { wrapper: createWrapper() });

      await result.current.snooze(1, 3600);

      expect(api.snoozeEvent).toHaveBeenCalledWith(1, 3600);
    });

    it('returns the updated event on success', async () => {
      const mockEvent = { id: 1, snooze_until: '2024-01-15T11:00:00Z' };
      vi.mocked(api.snoozeEvent).mockResolvedValue(mockEvent as api.Event);

      const { result } = renderHook(() => useSnoozeEvent(), { wrapper: createWrapper() });

      const updatedEvent = await result.current.snooze(1, 3600);

      expect(updatedEvent).toEqual(mockEvent);
    });

    it('sets isSnoozing to true while snoozing', async () => {
      let resolveSnooze: (value: api.Event) => void = () => {};
      vi.mocked(api.snoozeEvent).mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveSnooze = resolve;
          })
      );

      const { result } = renderHook(() => useSnoozeEvent(), { wrapper: createWrapper() });

      expect(result.current.isSnoozing).toBe(false);

      const snoozePromise = result.current.snooze(1, 3600);

      await waitFor(() => {
        expect(result.current.isSnoozing).toBe(true);
      });

      resolveSnooze({ id: 1 } as api.Event);
      await snoozePromise;

      await waitFor(() => {
        expect(result.current.isSnoozing).toBe(false);
      });
    });

    it('calls onSuccess callback with event, eventId, and seconds', async () => {
      const mockEvent = { id: 1, snooze_until: '2024-01-15T11:00:00Z' };
      vi.mocked(api.snoozeEvent).mockResolvedValue(mockEvent as api.Event);

      const onSuccess = vi.fn();
      const { result } = renderHook(() => useSnoozeEvent({ onSuccess }), {
        wrapper: createWrapper(),
      });

      await result.current.snooze(1, 3600);

      expect(onSuccess).toHaveBeenCalledWith(mockEvent, 1, 3600);
    });

    it('calls onError callback on failure', async () => {
      const error = new Error('Network error');
      vi.mocked(api.snoozeEvent).mockRejectedValue(error);

      const onError = vi.fn();
      const { result } = renderHook(() => useSnoozeEvent({ onError }), {
        wrapper: createWrapper(),
      });

      await expect(result.current.snooze(1, 3600)).rejects.toThrow('Network error');

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(error, 1, 3600);
      });
    });

    it('sets error state on failure', async () => {
      const error = new Error('Network error');
      vi.mocked(api.snoozeEvent).mockRejectedValue(error);

      const { result } = renderHook(() => useSnoozeEvent(), { wrapper: createWrapper() });

      await expect(result.current.snooze(1, 3600)).rejects.toThrow();

      await waitFor(() => {
        expect(result.current.error).toEqual(error);
      });
    });

    it('invalidates queries by default on success', async () => {
      const mockEvent = { id: 1, snooze_until: '2024-01-15T11:00:00Z' };
      vi.mocked(api.snoozeEvent).mockResolvedValue(mockEvent as api.Event);

      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useSnoozeEvent(), { wrapper: createWrapper() });

      await result.current.snooze(1, 3600);

      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['alerts'] });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['events'] });
    });

    it('does not invalidate queries when invalidateQueries is false', async () => {
      const mockEvent = { id: 1, snooze_until: '2024-01-15T11:00:00Z' };
      vi.mocked(api.snoozeEvent).mockResolvedValue(mockEvent as api.Event);

      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useSnoozeEvent({ invalidateQueries: false }), {
        wrapper: createWrapper(),
      });

      await result.current.snooze(1, 3600);

      expect(invalidateSpy).not.toHaveBeenCalled();
    });
  });

  describe('unsnooze', () => {
    it('calls clearSnooze API with eventId', async () => {
      const mockEvent = { id: 1, snooze_until: null };
      vi.mocked(api.clearSnooze).mockResolvedValue(mockEvent as api.Event);

      const { result } = renderHook(() => useSnoozeEvent(), { wrapper: createWrapper() });

      await result.current.unsnooze(1);

      expect(api.clearSnooze).toHaveBeenCalledWith(1);
    });

    it('returns the updated event on success', async () => {
      const mockEvent = { id: 1, snooze_until: null };
      vi.mocked(api.clearSnooze).mockResolvedValue(mockEvent as api.Event);

      const { result } = renderHook(() => useSnoozeEvent(), { wrapper: createWrapper() });

      const updatedEvent = await result.current.unsnooze(1);

      expect(updatedEvent).toEqual(mockEvent);
    });

    it('sets isUnsnoozing to true while unsnoozing', async () => {
      let resolveUnsnooze: (value: api.Event) => void = () => {};
      vi.mocked(api.clearSnooze).mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveUnsnooze = resolve;
          })
      );

      const { result } = renderHook(() => useSnoozeEvent(), { wrapper: createWrapper() });

      expect(result.current.isUnsnoozing).toBe(false);

      const unsnoozePromise = result.current.unsnooze(1);

      await waitFor(() => {
        expect(result.current.isUnsnoozing).toBe(true);
      });

      resolveUnsnooze({ id: 1 } as api.Event);
      await unsnoozePromise;

      await waitFor(() => {
        expect(result.current.isUnsnoozing).toBe(false);
      });
    });

    it('calls onSuccess callback with event, eventId, and 0 seconds', async () => {
      const mockEvent = { id: 1, snooze_until: null };
      vi.mocked(api.clearSnooze).mockResolvedValue(mockEvent as api.Event);

      const onSuccess = vi.fn();
      const { result } = renderHook(() => useSnoozeEvent({ onSuccess }), {
        wrapper: createWrapper(),
      });

      await result.current.unsnooze(1);

      // For unsnooze, seconds should be 0
      expect(onSuccess).toHaveBeenCalledWith(mockEvent, 1, 0);
    });

    it('calls onError callback on failure', async () => {
      const error = new Error('Network error');
      vi.mocked(api.clearSnooze).mockRejectedValue(error);

      const onError = vi.fn();
      const { result } = renderHook(() => useSnoozeEvent({ onError }), {
        wrapper: createWrapper(),
      });

      await expect(result.current.unsnooze(1)).rejects.toThrow('Network error');

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(error, 1, 0);
      });
    });
  });

  describe('reset', () => {
    it('resets error state', async () => {
      const error = new Error('Network error');
      vi.mocked(api.snoozeEvent).mockRejectedValue(error);

      const { result } = renderHook(() => useSnoozeEvent(), { wrapper: createWrapper() });

      await expect(result.current.snooze(1, 3600)).rejects.toThrow();

      await waitFor(() => {
        expect(result.current.error).not.toBeNull();
      });

      result.current.reset();

      await waitFor(() => {
        expect(result.current.error).toBeNull();
      });
    });
  });
});
