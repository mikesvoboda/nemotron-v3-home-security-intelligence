import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useRecentEventsQuery, recentEventsQueryKeys } from './useRecentEventsQuery';
import * as api from '../services/api';

import type { EventListResponse } from '../types/generated';

// Mock the API module
vi.mock('../services/api');

describe('useRecentEventsQuery', () => {
  let queryClient: QueryClient;

  const mockEventsResponse: EventListResponse = {
    items: [
      {
        id: 1,
        camera_id: 'camera-1',
        started_at: '2024-01-01T10:00:00Z',
        ended_at: null,
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
        reviewed: false,
        detection_count: 5,
        notes: null,
      },
      {
        id: 2,
        camera_id: 'camera-2',
        started_at: '2024-01-01T09:00:00Z',
        ended_at: null,
        risk_score: 45,
        risk_level: 'medium',
        summary: 'Motion detected',
        reviewed: false,
        detection_count: 3,
        notes: null,
      },
    ],
    pagination: {
      total: 100,
      limit: 10,
      offset: 0,
      has_more: true,
    },
  };

  const createWrapper = () => {
    return ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children);
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
        },
      },
    });
  });

  describe('basic functionality', () => {
    it('fetches recent events with default limit of 10', async () => {
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 10 });
      expect(result.current.events).toHaveLength(2);
      expect(result.current.totalCount).toBe(100);
    });

    it('uses custom limit when provided', async () => {
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

      const { result } = renderHook(() => useRecentEventsQuery({ limit: 5 }), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 5 });
    });

    it('passes camera filter to API', async () => {
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

      const { result } = renderHook(
        () => useRecentEventsQuery({ limit: 10, cameraId: 'front-door' }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEvents).toHaveBeenCalledWith({
        limit: 10,
        camera_id: 'front-door',
      });
    });

    it('passes risk level filter to API', async () => {
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

      const { result } = renderHook(
        () => useRecentEventsQuery({ limit: 10, riskLevel: 'high' }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEvents).toHaveBeenCalledWith({
        limit: 10,
        risk_level: 'high',
      });
    });
  });

  describe('query state', () => {
    it('returns loading state initially', () => {
      vi.mocked(api.fetchEvents).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.events).toEqual([]);
      expect(result.current.totalCount).toBe(0);
    });

    it('returns error state on failure', async () => {
      const error = new Error('Network error');
      vi.mocked(api.fetchEvents).mockRejectedValue(error);

      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toBe(error);
      expect(result.current.events).toEqual([]);
    });

    it('can be disabled', async () => {
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

      const { result } = renderHook(() => useRecentEventsQuery({ enabled: false }), {
        wrapper: createWrapper(),
      });

      // Wait a bit to ensure no fetch happens
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(api.fetchEvents).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEvents).toHaveBeenCalledTimes(1);

      // Trigger refetch
      result.current.refetch();

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('query keys', () => {
    it('generates correct query keys for basic query', () => {
      expect(recentEventsQueryKeys.all).toEqual(['events', 'recent']);
      expect(recentEventsQueryKeys.list(10)).toEqual([
        'events',
        'recent',
        { limit: 10, cameraId: undefined, riskLevel: undefined },
      ]);
    });

    it('includes filters in query key', () => {
      expect(recentEventsQueryKeys.list(5, 'camera-1', 'high')).toEqual([
        'events',
        'recent',
        { limit: 5, cameraId: 'camera-1', riskLevel: 'high' },
      ]);
    });
  });

  describe('no client-side slicing', () => {
    it('returns all events from server response without slicing', async () => {
      const responseWithMany: EventListResponse = {
        items: Array.from({ length: 10 }, (_, i) => ({
          id: i + 1,
          camera_id: `camera-${i}`,
          started_at: `2024-01-01T${String(i).padStart(2, '0')}:00:00Z`,
          ended_at: null,
          risk_score: 50,
          risk_level: 'medium',
          summary: `Event ${i + 1}`,
          reviewed: false,
          detection_count: 1,
          notes: null,
        })),
        pagination: {
          total: 500,
          limit: 10,
          offset: 0,
          has_more: true,
        },
      };

      vi.mocked(api.fetchEvents).mockResolvedValue(responseWithMany);

      const { result } = renderHook(() => useRecentEventsQuery({ limit: 10 }), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should return exactly what the server returned (no client-side slicing)
      expect(result.current.events).toHaveLength(10);
      expect(result.current.totalCount).toBe(500);

      // Verify the events match server response exactly
      expect(result.current.events[0].id).toBe(1);
      expect(result.current.events[9].id).toBe(10);
    });
  });
});
