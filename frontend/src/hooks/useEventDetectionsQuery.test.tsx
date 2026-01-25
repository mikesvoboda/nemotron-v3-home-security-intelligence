/**
 * Tests for useEventDetectionsQuery hook
 *
 * @see NEM-3594
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { describe, expect, it, beforeAll, afterAll, afterEach } from 'vitest';

import {
  useEventDetectionsQuery,
  usePrefetchEventDetections,
  eventDetectionsQueryKeys,
  PREFETCH_STALE_TIME,
  PREFETCH_DEFAULT_LIMIT,
} from './useEventDetectionsQuery';

import type { ReactNode } from 'react';

// Mock API responses
const mockDetections = [
  {
    id: 1,
    event_id: 123,
    object_type: 'person',
    confidence: 0.95,
    detected_at: '2024-01-15T10:30:00Z',
  },
  {
    id: 2,
    event_id: 123,
    object_type: 'vehicle',
    confidence: 0.88,
    detected_at: '2024-01-15T10:30:01Z',
  },
];

const mockResponse = {
  items: mockDetections,
  pagination: {
    total: 2,
    limit: 100,
    offset: 0,
    has_more: false,
  },
};

// Setup MSW server
const server = setupServer(
  http.get('/api/events/:eventId/detections', () => {
    return HttpResponse.json(mockResponse);
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(() => {
  server.resetHandlers();
});

// Test wrapper with fresh QueryClient
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

describe('useEventDetectionsQuery', () => {
  it('fetches detections for a valid event ID', async () => {
    const { result } = renderHook(
      () =>
        useEventDetectionsQuery({
          eventId: 123,
          limit: 100,
        }),
      { wrapper: createWrapper() }
    );

    // Initially loading
    expect(result.current.isLoading).toBe(true);
    expect(result.current.detections).toEqual([]);

    // Wait for data
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should have detections
    expect(result.current.detections).toHaveLength(2);
    expect(result.current.detections[0].object_type).toBe('person');
  });

  it('does not fetch for invalid event ID', () => {
    const { result } = renderHook(
      () =>
        useEventDetectionsQuery({
          eventId: NaN,
        }),
      { wrapper: createWrapper() }
    );

    // Should not be loading - query is disabled
    expect(result.current.isLoading).toBe(false);
    expect(result.current.detections).toEqual([]);
  });

  it('does not fetch when enabled is false', () => {
    const { result } = renderHook(
      () =>
        useEventDetectionsQuery({
          eventId: 123,
          enabled: false,
        }),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(false);
    expect(result.current.detections).toEqual([]);
  });

  it('returns error state on API failure', async () => {
    // Override handler to return error
    server.use(
      http.get('/api/events/:eventId/detections', () => {
        return HttpResponse.json(
          { error: 'Internal server error' },
          { status: 500 }
        );
      })
    );

    const { result } = renderHook(
      () =>
        useEventDetectionsQuery({
          eventId: 123,
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeTruthy();
  });
});

describe('eventDetectionsQueryKeys', () => {
  it('creates base query key for event', () => {
    const key = eventDetectionsQueryKeys.forEvent(123);
    expect(key).toEqual(['detections', 'event', 123]);
  });

  it('includes limit in query key when provided', () => {
    const key = eventDetectionsQueryKeys.forEvent(123, 50);
    expect(key).toContainEqual({ limit: 50, orderBy: undefined });
  });

  it('includes orderBy in query key when provided', () => {
    const key = eventDetectionsQueryKeys.forEvent(123, 100, 'created_at');
    expect(key).toContainEqual({ limit: 100, orderBy: 'created_at' });
  });
});

describe('usePrefetchEventDetections', () => {
  it('returns prefetchDetections function', () => {
    const { result } = renderHook(() => usePrefetchEventDetections(), {
      wrapper: createWrapper(),
    });

    expect(typeof result.current.prefetchDetections).toBe('function');
  });

  it('returns getCachedCount function', () => {
    const { result } = renderHook(() => usePrefetchEventDetections(), {
      wrapper: createWrapper(),
    });

    expect(typeof result.current.getCachedCount).toBe('function');
  });

  it('returns isCached function', () => {
    const { result } = renderHook(() => usePrefetchEventDetections(), {
      wrapper: createWrapper(),
    });

    expect(typeof result.current.isCached).toBe('function');
  });

  it('does not throw when prefetching invalid event ID', () => {
    const { result } = renderHook(() => usePrefetchEventDetections(), {
      wrapper: createWrapper(),
    });

    // Should not throw for invalid IDs
    expect(() => result.current.prefetchDetections(NaN)).not.toThrow();
    expect(() => result.current.prefetchDetections(0)).not.toThrow();
    expect(() => result.current.prefetchDetections(-1)).not.toThrow();
  });

  it('returns undefined count when not cached', () => {
    const { result } = renderHook(() => usePrefetchEventDetections(), {
      wrapper: createWrapper(),
    });

    expect(result.current.getCachedCount(999)).toBeUndefined();
  });

  it('returns false for isCached when not cached', () => {
    const { result } = renderHook(() => usePrefetchEventDetections(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isCached(999)).toBe(false);
  });

  it('prefetches and caches data', async () => {
    const { result } = renderHook(() => usePrefetchEventDetections(), {
      wrapper: createWrapper(),
    });

    // Trigger prefetch
    result.current.prefetchDetections(123);

    // Wait for prefetch to complete
    await waitFor(() => {
      expect(result.current.isCached(123)).toBe(true);
    });

    // Should have cached count
    expect(result.current.getCachedCount(123)).toBe(2);
  });
});

describe('Constants', () => {
  it('has correct PREFETCH_STALE_TIME', () => {
    expect(PREFETCH_STALE_TIME).toBe(30 * 1000); // 30 seconds
  });

  it('has correct PREFETCH_DEFAULT_LIMIT', () => {
    expect(PREFETCH_DEFAULT_LIMIT).toBe(100);
  });
});
