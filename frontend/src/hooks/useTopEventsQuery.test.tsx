import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { useTopEventsQuery, topEventsQueryKeys } from './useTopEventsQuery';
import { fetchEvents } from '../services/api';

import type { Event } from '../types/generated';
import type { ReactNode } from 'react';

// Mock the API
vi.mock('../services/api', () => ({
  fetchEvents: vi.fn(),
}));
const mockFetchEvents = vi.mocked(fetchEvents);

// Helper to create mock events
function createMockEvent(id: number, riskScore: number): Event {
  return {
    id,
    camera_id: `camera-${id}`,
    started_at: new Date().toISOString(),
    ended_at: null,
    risk_score: riskScore,
    risk_level: riskScore >= 70 ? 'high' : riskScore >= 40 ? 'medium' : 'low',
    summary: `Event ${id} summary`,
    reasoning: 'Test reasoning',
    reviewed: false,
    flagged: false,
    detection_count: 1,
    thumbnail_url: `/api/events/${id}/thumbnail`,
    version: 1,
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('useTopEventsQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('basic functionality', () => {
    it('returns empty events array when loading', () => {
      mockFetchEvents.mockReturnValue(new Promise(() => {})); // Never resolves

      const { result } = renderHook(() => useTopEventsQuery(), { wrapper: createWrapper() });

      expect(result.current.events).toEqual([]);
      expect(result.current.isLoading).toBe(true);
    });

    it('returns events sorted by risk_score descending', async () => {
      const mockEvents = [
        createMockEvent(1, 50),
        createMockEvent(2, 95),
        createMockEvent(3, 30),
        createMockEvent(4, 75),
      ];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents,
        pagination: { total: 4, limit: 10, has_more: false },
      });

      const { result } = renderHook(() => useTopEventsQuery(), { wrapper: createWrapper() });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.events).toHaveLength(4);
      // Verify sorting: 95, 75, 50, 30
      expect(result.current.events[0].risk_score).toBe(95);
      expect(result.current.events[1].risk_score).toBe(75);
      expect(result.current.events[2].risk_score).toBe(50);
      expect(result.current.events[3].risk_score).toBe(30);
    });

    it('returns totalCount from pagination', async () => {
      mockFetchEvents.mockResolvedValue({
        items: [createMockEvent(1, 80)],
        pagination: { total: 50, limit: 10, has_more: true },
      });

      const { result } = renderHook(() => useTopEventsQuery(), { wrapper: createWrapper() });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.totalCount).toBe(50);
    });

    it('handles error state', async () => {
      const testError = new Error('Network error');
      mockFetchEvents.mockRejectedValue(testError);

      const { result } = renderHook(() => useTopEventsQuery(), { wrapper: createWrapper() });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 3000 }
      );

      expect(result.current.error).toBe(testError);
      expect(result.current.events).toEqual([]);
    });
  });

  describe('options', () => {
    it('respects custom limit option', async () => {
      mockFetchEvents.mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 5, has_more: false },
      });

      renderHook(() => useTopEventsQuery({ limit: 5 }), { wrapper: createWrapper() });

      await waitFor(() => {
        expect(mockFetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ limit: 5 })
        );
      });
    });

    it('does not fetch when enabled is false', () => {
      renderHook(() => useTopEventsQuery({ enabled: false }), { wrapper: createWrapper() });

      expect(mockFetchEvents).not.toHaveBeenCalled();
    });
  });

  describe('query keys', () => {
    it('generates correct query keys', () => {
      expect(topEventsQueryKeys.all).toEqual(['events', 'top']);
      expect(topEventsQueryKeys.list(5)).toEqual(['events', 'top', { limit: 5 }]);
      expect(topEventsQueryKeys.list(10)).toEqual(['events', 'top', { limit: 10 }]);
    });
  });

  describe('edge cases', () => {
    it('handles events with null risk_score', async () => {
      const mockEvents = [
        createMockEvent(1, 50),
        { ...createMockEvent(2, 0), risk_score: null },
        createMockEvent(3, 80),
      ];

      mockFetchEvents.mockResolvedValue({
        items: mockEvents as any,
        pagination: { total: 3, limit: 10, has_more: false },
      });

      const { result } = renderHook(() => useTopEventsQuery(), { wrapper: createWrapper() });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Events with null risk_score treated as 0
      expect(result.current.events).toHaveLength(3);
      expect(result.current.events[0].risk_score).toBe(80);
      expect(result.current.events[1].risk_score).toBe(50);
    });

    it('handles empty response', async () => {
      mockFetchEvents.mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 10, has_more: false },
      });

      const { result } = renderHook(() => useTopEventsQuery(), { wrapper: createWrapper() });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.events).toEqual([]);
      expect(result.current.totalCount).toBe(0);
    });
  });
});
