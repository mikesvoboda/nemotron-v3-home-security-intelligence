import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { createElement } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useWebSocketCapabilities,
  WEBSOCKET_QUERY_KEYS,
  type EventRegistryResponse,
} from './useWebSocketCapabilities';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchWebSocketEventTypes: vi.fn(),
}));

describe('useWebSocketCapabilities', () => {
  let queryClient: QueryClient;

  // Mock response data matching EventRegistryResponse
  const mockEventRegistry: EventRegistryResponse = {
    event_types: [
      {
        type: 'event.new',
        description: 'New security event created',
        channel: 'events',
        payload_schema: {
          id: { type: 'integer' },
          risk_score: { type: 'integer' },
        },
        example: { id: 1, risk_score: 75 },
        deprecated: false,
        replacement: null,
      },
      {
        type: 'detection.new',
        description: 'New detection from AI pipeline',
        channel: 'detections',
        payload_schema: {
          detection_id: { type: 'string' },
          label: { type: 'string' },
        },
        example: { detection_id: '123', label: 'person' },
        deprecated: false,
        replacement: null,
      },
      {
        type: 'alert.legacy',
        description: 'Legacy alert format (deprecated)',
        channel: 'alerts',
        payload_schema: {},
        example: null,
        deprecated: true,
        replacement: 'alert.new',
      },
    ],
    channels: ['alerts', 'detections', 'events'],
    total_count: 3,
    deprecated_count: 1,
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Create a fresh QueryClient for each test
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
        },
      },
    });
  });

  afterEach(() => {
    queryClient.clear();
  });

  // Helper to create wrapper with QueryClientProvider
  const createWrapper = () => {
    return ({ children }: { children: React.ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children);
  };

  describe('successful queries', () => {
    it('should fetch and return event registry data', async () => {
      vi.mocked(api.fetchWebSocketEventTypes).mockResolvedValueOnce(mockEventRegistry);

      const { result } = renderHook(() => useWebSocketCapabilities(), {
        wrapper: createWrapper(),
      });

      // Initial loading state
      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();

      // Wait for query to complete
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Verify data is returned correctly
      expect(result.current.data).toEqual(mockEventRegistry);
      expect(result.current.eventTypes).toHaveLength(3);
      expect(result.current.totalCount).toBe(3);
      expect(result.current.channels).toEqual(['alerts', 'detections', 'events']);
      expect(result.current.deprecatedCount).toBe(1);
      expect(result.current.error).toBeNull();
    });

    it('should provide convenience accessors for event types', async () => {
      vi.mocked(api.fetchWebSocketEventTypes).mockResolvedValueOnce(mockEventRegistry);

      const { result } = renderHook(() => useWebSocketCapabilities(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Verify eventTypes accessor
      const eventTypes = result.current.eventTypes;
      expect(eventTypes[0].type).toBe('event.new');
      expect(eventTypes[0].channel).toBe('events');
      expect(eventTypes[0].deprecated).toBe(false);

      // Verify deprecated event type
      const deprecatedEvent = eventTypes.find((e) => e.deprecated);
      expect(deprecatedEvent?.type).toBe('alert.legacy');
      expect(deprecatedEvent?.replacement).toBe('alert.new');
    });

    it('should return empty arrays when data is undefined', () => {
      // Don't mock any response - query will be in pending state
      vi.mocked(api.fetchWebSocketEventTypes).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(() => useWebSocketCapabilities(), {
        wrapper: createWrapper(),
      });

      // Convenience accessors should return empty arrays
      expect(result.current.eventTypes).toEqual([]);
      expect(result.current.channels).toEqual([]);
      expect(result.current.totalCount).toBe(0);
      expect(result.current.deprecatedCount).toBe(0);
    });
  });

  describe('query options', () => {
    it('should respect enabled option', () => {
      vi.mocked(api.fetchWebSocketEventTypes).mockResolvedValueOnce(mockEventRegistry);

      const { result } = renderHook(() => useWebSocketCapabilities({ enabled: false }), {
        wrapper: createWrapper(),
      });

      // Should not be loading when disabled
      expect(result.current.isLoading).toBe(false);
      expect(api.fetchWebSocketEventTypes).not.toHaveBeenCalled();
    });

    it('should use default stale time of 5 minutes', async () => {
      vi.mocked(api.fetchWebSocketEventTypes).mockResolvedValue(mockEventRegistry);

      const { result } = renderHook(() => useWebSocketCapabilities(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Query should have been called once
      expect(api.fetchWebSocketEventTypes).toHaveBeenCalledTimes(1);
    });

    it('should allow custom stale time', async () => {
      vi.mocked(api.fetchWebSocketEventTypes).mockResolvedValue(mockEventRegistry);

      const { result } = renderHook(
        () => useWebSocketCapabilities({ staleTime: 1000 }), // 1 second
        {
          wrapper: createWrapper(),
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockEventRegistry);
    });
  });

  describe('error handling', () => {
    it('should handle fetch errors', async () => {
      const error = new Error('Network error');
      vi.mocked(api.fetchWebSocketEventTypes).mockRejectedValue(error);

      const { result } = renderHook(() => useWebSocketCapabilities(), {
        wrapper: createWrapper(),
      });

      // Wait for the error to be captured
      await waitFor(
        () => {
          expect(result.current.error).not.toBeNull();
        },
        { timeout: 2000 }
      );

      expect(result.current.error).toEqual(error);
      expect(result.current.data).toBeUndefined();
      expect(result.current.eventTypes).toEqual([]);
    });
  });

  describe('refetch', () => {
    it('should provide refetch function', async () => {
      vi.mocked(api.fetchWebSocketEventTypes)
        .mockResolvedValueOnce(mockEventRegistry)
        .mockResolvedValueOnce({
          ...mockEventRegistry,
          total_count: 5,
        });

      const { result } = renderHook(() => useWebSocketCapabilities(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.totalCount).toBe(3);

      // Trigger refetch
      await result.current.refetch();

      await waitFor(() => {
        expect(result.current.totalCount).toBe(5);
      });

      expect(api.fetchWebSocketEventTypes).toHaveBeenCalledTimes(2);
    });
  });

  describe('query keys', () => {
    it('should export correct query keys', () => {
      expect(WEBSOCKET_QUERY_KEYS.all).toEqual(['websocket']);
      expect(WEBSOCKET_QUERY_KEYS.events).toEqual(['websocket', 'events']);
    });
  });
});
