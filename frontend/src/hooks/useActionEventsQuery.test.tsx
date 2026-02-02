/**
 * Tests for useActionEventsQuery hooks
 *
 * Linear issue: NEM-5024 (Phase 7)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { type ReactNode } from 'react';
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';

import {
  useActionEventsQuery,
  useActionEventsForEventQuery,
  useSuspiciousActionsQuery,
} from './useActionEventsQuery';

import type {
  ActionEventListResponse,
  SuspiciousActionsResponse,
} from '../services/actionEventsApi';

// ============================================================================
// Mock Data
// ============================================================================

const mockActionEventsResponse: ActionEventListResponse = {
  items: [
    {
      id: 1,
      camera_id: 'front_door',
      track_id: 42,
      action: 'walking normally',
      confidence: 0.89,
      is_suspicious: false,
      timestamp: '2026-01-26T12:00:00Z',
      frame_count: 8,
      all_scores: { 'walking normally': 0.89, climbing: 0.02 },
      created_at: '2026-01-26T12:00:00Z',
    },
    {
      id: 2,
      camera_id: 'front_door',
      track_id: null,
      action: 'running',
      confidence: 0.75,
      is_suspicious: false,
      timestamp: '2026-01-26T12:01:00Z',
      frame_count: 8,
      all_scores: null,
      created_at: '2026-01-26T12:01:00Z',
    },
  ],
  pagination: {
    total: 2,
    limit: 50,
    offset: 0,
    has_more: false,
  },
};

const mockSuspiciousActionsResponse: SuspiciousActionsResponse = {
  items: [
    {
      id: 5,
      camera_id: 'back_yard',
      track_id: 17,
      action: 'climbing',
      confidence: 0.92,
      is_suspicious: true,
      timestamp: '2026-01-26T14:30:00Z',
      frame_count: 8,
      all_scores: { climbing: 0.92, 'walking normally': 0.05 },
      created_at: '2026-01-26T14:30:00Z',
    },
  ],
  pagination: {
    total: 1,
    limit: 50,
    offset: 0,
    has_more: false,
  },
  suspicious_count: 1,
  total_count: 25,
};

// ============================================================================
// MSW Server Setup
// ============================================================================

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(() => {
  server.resetHandlers();
});

// ============================================================================
// Test Utilities
// ============================================================================

/**
 * Create a wrapper with QueryClientProvider for testing hooks.
 */
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

// ============================================================================
// Tests
// ============================================================================

describe('useActionEventsQuery', () => {
  it('fetches action events successfully', async () => {
    server.use(
      http.get('/api/action-events', () => {
        return HttpResponse.json(mockActionEventsResponse);
      })
    );

    const { result } = renderHook(() => useActionEventsQuery(), {
      wrapper: createWrapper(),
    });

    // Initially loading
    expect(result.current.isLoading).toBe(true);
    expect(result.current.actionEvents).toEqual([]);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.actionEvents).toHaveLength(2);
    expect(result.current.totalCount).toBe(2);
    expect(result.current.hasMore).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('passes filter parameters to API', async () => {
    let requestUrl: string | undefined;

    server.use(
      http.get('/api/action-events', ({ request }) => {
        requestUrl = request.url;
        return HttpResponse.json(mockActionEventsResponse);
      })
    );

    const { result } = renderHook(
      () =>
        useActionEventsQuery({
          cameraId: 'front_door',
          action: 'climbing',
          isSuspicious: true,
          minConfidence: 0.8,
          startTime: '2026-01-01T00:00:00Z',
          endTime: '2026-01-31T23:59:59Z',
          limit: 20,
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Verify the request URL contains the expected parameters
    expect(requestUrl).toBeDefined();
    const url = new URL(requestUrl!);
    expect(url.searchParams.get('camera_id')).toBe('front_door');
    expect(url.searchParams.get('action')).toBe('climbing');
    expect(url.searchParams.get('is_suspicious')).toBe('true');
    expect(url.searchParams.get('min_confidence')).toBe('0.8');
    expect(url.searchParams.get('limit')).toBe('20');
  });

  it('handles errors gracefully', async () => {
    server.use(
      http.get('/api/action-events', () => {
        return HttpResponse.json({ detail: 'Internal Server Error' }, { status: 500 });
      })
    );

    const { result } = renderHook(() => useActionEventsQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.error).toBeTruthy();
      },
      { timeout: 5000 }
    );

    expect(result.current.actionEvents).toEqual([]);
  });

  it('does not fetch when disabled', async () => {
    let requestMade = false;

    server.use(
      http.get('/api/action-events', () => {
        requestMade = true;
        return HttpResponse.json(mockActionEventsResponse);
      })
    );

    const { result } = renderHook(() => useActionEventsQuery({ enabled: false }), {
      wrapper: createWrapper(),
    });

    // Wait a bit to ensure no request is made
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(result.current.isLoading).toBe(false);
    expect(requestMade).toBe(false);
  });

  it('provides refetch function', async () => {
    let requestCount = 0;

    server.use(
      http.get('/api/action-events', () => {
        requestCount++;
        return HttpResponse.json(mockActionEventsResponse);
      })
    );

    const { result } = renderHook(() => useActionEventsQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(requestCount).toBe(1);

    // Refetch
    await result.current.refetch();

    expect(requestCount).toBe(2);
  });
});

describe('useActionEventsForEventQuery', () => {
  it('fetches action events for an event', async () => {
    server.use(
      http.get('/api/action-events', () => {
        return HttpResponse.json(mockActionEventsResponse);
      })
    );

    const { result } = renderHook(
      () =>
        useActionEventsForEventQuery({
          eventId: 123,
          cameraId: 'front_door',
          startTime: '2026-01-26T12:00:00Z',
          endTime: '2026-01-26T12:05:00Z',
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.actionEvents).toHaveLength(2);
  });

  it('handles ongoing events with null end time', async () => {
    let requestUrl: string | undefined;

    server.use(
      http.get('/api/action-events', ({ request }) => {
        requestUrl = request.url;
        return HttpResponse.json(mockActionEventsResponse);
      })
    );

    const { result } = renderHook(
      () =>
        useActionEventsForEventQuery({
          eventId: 123,
          cameraId: 'front_door',
          startTime: '2026-01-26T12:00:00Z',
          endTime: null,
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should have made a request with calculated end time
    expect(requestUrl).toBeDefined();
    const url = new URL(requestUrl!);
    expect(url.searchParams.get('end_time')).toBeTruthy();
  });

  it('does not fetch without required params', async () => {
    let requestMade = false;

    server.use(
      http.get('/api/action-events', () => {
        requestMade = true;
        return HttpResponse.json(mockActionEventsResponse);
      })
    );

    // Missing cameraId should disable the query
    const { result } = renderHook(
      () =>
        useActionEventsForEventQuery({
          eventId: 123,
          cameraId: '', // Empty string
          startTime: '2026-01-26T12:00:00Z',
        }),
      { wrapper: createWrapper() }
    );

    // Wait a bit to ensure no fetch is triggered
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(requestMade).toBe(false);
    expect(result.current.isLoading).toBe(false);
  });
});

describe('useSuspiciousActionsQuery', () => {
  it('fetches suspicious actions successfully', async () => {
    server.use(
      http.get('/api/action-events/suspicious', () => {
        return HttpResponse.json(mockSuspiciousActionsResponse);
      })
    );

    const { result } = renderHook(() => useSuspiciousActionsQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.actionEvents).toHaveLength(1);
    expect(result.current.suspiciousCount).toBe(1);
    expect(result.current.totalActionCount).toBe(25);
    expect(result.current.actionEvents[0].is_suspicious).toBe(true);
  });

  it('passes filter parameters to API', async () => {
    let requestUrl: string | undefined;

    server.use(
      http.get('/api/action-events/suspicious', ({ request }) => {
        requestUrl = request.url;
        return HttpResponse.json(mockSuspiciousActionsResponse);
      })
    );

    const { result } = renderHook(
      () =>
        useSuspiciousActionsQuery({
          cameraId: 'back_yard',
          minConfidence: 0.9,
          startTime: '2026-01-01T00:00:00Z',
          endTime: '2026-01-31T23:59:59Z',
          limit: 10,
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(requestUrl).toBeDefined();
    const url = new URL(requestUrl!);
    expect(url.searchParams.get('camera_id')).toBe('back_yard');
    expect(url.searchParams.get('min_confidence')).toBe('0.9');
    expect(url.searchParams.get('limit')).toBe('10');
  });

  it('returns zero counts when no data', async () => {
    server.use(
      http.get('/api/action-events/suspicious', () => {
        return HttpResponse.json({
          items: [],
          pagination: { total: 0, limit: 50, offset: 0, has_more: false },
          suspicious_count: 0,
          total_count: 0,
        } satisfies SuspiciousActionsResponse);
      })
    );

    const { result } = renderHook(() => useSuspiciousActionsQuery(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.suspiciousCount).toBe(0);
    expect(result.current.totalActionCount).toBe(0);
    expect(result.current.actionEvents).toEqual([]);
  });
});
