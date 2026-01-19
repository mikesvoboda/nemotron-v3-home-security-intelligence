/**
 * @fileoverview Tests for useSummaries hook.
 *
 * This hook fetches hourly and daily summaries via React Query and
 * subscribes to WebSocket `summary_update` events for real-time updates.
 *
 * @see docs/plans/2026-01-18-dashboard-summaries-design.md
 * @see NEM-2895
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import * as api from '../../services/api';
import { createQueryWrapper } from '../../test-utils/renderWithProviders';
import { useSummaries } from '../useSummaries';

import type { SummariesLatestResponse, Summary } from '../../types/summary';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchSummaries: vi.fn(),
}));

// Mock the WebSocket hook
const mockWebSocketConnect = vi.fn();
const mockWebSocketDisconnect = vi.fn();
let mockOnMessage: ((data: unknown) => void) | undefined;

vi.mock('../useWebSocket', () => ({
  useWebSocket: vi.fn((options) => {
    // Capture the onMessage callback for testing
    mockOnMessage = options?.onMessage;
    return {
      isConnected: true,
      lastMessage: null,
      send: vi.fn(),
      connect: mockWebSocketConnect,
      disconnect: mockWebSocketDisconnect,
      hasExhaustedRetries: false,
      reconnectCount: 0,
      lastHeartbeat: null,
    };
  }),
}));

describe('useSummaries', () => {
  // Mock data for tests
  const mockHourlySummary: Summary = {
    id: 1,
    content:
      'Over the past hour, one critical event occurred at 2:15 PM when an unrecognized person approached the front door.',
    eventCount: 1,
    windowStart: '2026-01-18T14:00:00Z',
    windowEnd: '2026-01-18T15:00:00Z',
    generatedAt: '2026-01-18T14:55:00Z',
  };

  const mockDailySummary: Summary = {
    id: 2,
    content:
      'Today has seen minimal high-priority activity. The only notable event was at 2:15 PM at the front door.',
    eventCount: 1,
    windowStart: '2026-01-18T00:00:00Z',
    windowEnd: '2026-01-18T15:00:00Z',
    generatedAt: '2026-01-18T14:55:00Z',
  };

  const mockSummariesResponse: SummariesLatestResponse = {
    hourly: mockHourlySummary,
    daily: mockDailySummary,
  };

  const mockEmptySummariesResponse: SummariesLatestResponse = {
    hourly: null,
    daily: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnMessage = undefined;
    (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue(mockSummariesResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initial loading state', () => {
    it('starts with isLoading true', () => {
      // Don't let fetch resolve immediately
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with null hourly and daily summaries', () => {
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.hourly).toBeNull();
      expect(result.current.daily).toBeNull();
    });

    it('starts with no error', () => {
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('successful data fetch', () => {
    it('fetches summaries on mount when enabled', async () => {
      renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchSummaries).toHaveBeenCalledTimes(1);
      });
    });

    it('does not fetch when enabled is false', async () => {
      renderHook(() => useSummaries({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      // Wait a bit to ensure no call happens
      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchSummaries).not.toHaveBeenCalled();
    });

    it('updates hourly and daily data after successful fetch', async () => {
      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.hourly).toEqual(mockHourlySummary);
        expect(result.current.daily).toEqual(mockDailySummary);
      });
    });

    it('sets isLoading to false after successful fetch', async () => {
      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('handles null summaries (no events)', async () => {
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockResolvedValue(mockEmptySummariesResponse);

      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.hourly).toBeNull();
        expect(result.current.daily).toBeNull();
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('error handling', () => {
    it('sets error on fetch failure', async () => {
      const errorMessage = 'Network error';
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      // Wait for retries to complete (hook has retry: 1, so 2 total attempts)
      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
          expect(result.current.error?.message).toBe(errorMessage);
        },
        { timeout: 5000 }
      );
    });

    it('maintains null data when error occurs', async () => {
      (api.fetchSummaries as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('API Error'));

      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).not.toBeNull();
        },
        { timeout: 5000 }
      );

      expect(result.current.hourly).toBeNull();
      expect(result.current.daily).toBeNull();
    });
  });

  describe('WebSocket update triggers refetch', () => {
    it('invalidates cache when summary_update message is received', async () => {
      const { result } = renderHook(() => useSummaries({ enabled: true, enableWebSocket: true }), {
        wrapper: createQueryWrapper(),
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchSummaries).toHaveBeenCalledTimes(1);

      // Simulate receiving a WebSocket summary_update message
      const wsMessage = {
        type: 'summary_update',
        data: {
          hourly: { ...mockHourlySummary, eventCount: 2 },
          daily: { ...mockDailySummary, eventCount: 3 },
        },
      };

      // Trigger the WebSocket message handler
      act(() => {
        mockOnMessage?.(wsMessage);
      });

      // Should trigger a refetch via cache invalidation
      await waitFor(() => {
        expect(api.fetchSummaries).toHaveBeenCalledTimes(2);
      });
    });

    it('ignores non-summary_update messages', async () => {
      const { result } = renderHook(() => useSummaries({ enabled: true, enableWebSocket: true }), {
        wrapper: createQueryWrapper(),
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchSummaries).toHaveBeenCalledTimes(1);

      // Simulate receiving a different WebSocket message
      const otherMessage = {
        type: 'event_created',
        data: { id: 123 },
      };

      act(() => {
        mockOnMessage?.(otherMessage);
      });

      // Should NOT trigger a refetch
      // Wait a bit to ensure no extra calls happen
      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchSummaries).toHaveBeenCalledTimes(1);
    });

    it('does not subscribe to WebSocket when enableWebSocket is false', async () => {
      renderHook(() => useSummaries({ enabled: true, enableWebSocket: false }), {
        wrapper: createQueryWrapper(),
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(api.fetchSummaries).toHaveBeenCalledTimes(1);
      });

      // The WebSocket hook should still be called but with reconnect: false
      const useWebSocketMock = vi.mocked(await import('../useWebSocket')).useWebSocket;
      expect(useWebSocketMock).toHaveBeenCalled();
      const lastCall = useWebSocketMock.mock.calls[useWebSocketMock.mock.calls.length - 1];
      expect(lastCall[0].reconnect).toBe(false);
    });
  });

  describe('returns correct data structure', () => {
    it('returns all expected properties', async () => {
      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Check all required properties exist
      expect(result.current).toHaveProperty('hourly');
      expect(result.current).toHaveProperty('daily');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('refetch');
    });

    it('provides refetch function that triggers new API call', async () => {
      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchSummaries).toHaveBeenCalledTimes(1);
      });

      // Trigger refetch
      await act(async () => {
        await result.current.refetch();
      });

      await waitFor(() => {
        expect(api.fetchSummaries).toHaveBeenCalledTimes(2);
      });
    });

    it('refetch function returns a Promise', async () => {
      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const refetchPromise = result.current.refetch();
      expect(refetchPromise).toBeInstanceOf(Promise);
      await refetchPromise;
    });
  });

  describe('configuration options', () => {
    it('accepts custom staleTime', async () => {
      const { result } = renderHook(
        () => useSummaries({ enabled: true, staleTime: 60000 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.hourly).toEqual(mockHourlySummary);
      });
    });

    it('accepts refetchInterval for polling', async () => {
      const { result } = renderHook(
        () => useSummaries({ enabled: true, refetchInterval: 30000 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.hourly).toEqual(mockHourlySummary);
      });
    });

    it('defaults to no polling when refetchInterval is not set', async () => {
      const { result } = renderHook(() => useSummaries({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should only have one call (initial fetch, no polling)
      expect(api.fetchSummaries).toHaveBeenCalledTimes(1);
    });
  });
});
