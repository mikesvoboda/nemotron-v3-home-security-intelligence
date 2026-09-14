/**
 * Tests for useDebugQueries hook
 *
 * This hook provides debug-specific queries that only fetch when debug mode is ON.
 * It provides three debug queries:
 * - usePipelineErrorsQuery: Fetches pipeline errors from /api/debug/pipeline-errors
 * - useRedisDebugInfoQuery: Fetches Redis info from /api/debug/redis/info
 * - useWebSocketConnectionsQuery: Fetches WebSocket status from /api/debug/websocket/connections
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  usePipelineErrorsQuery,
  useRedisDebugInfoQuery,
  useWebSocketConnectionsQuery,
} from './useDebugQueries';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchPipelineErrors: vi.fn(),
  fetchRedisDebugInfo: vi.fn(),
  fetchWebSocketConnections: vi.fn(),
}));

describe('useDebugQueries', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('usePipelineErrorsQuery', () => {
    const mockPipelineErrorsResponse = {
      errors: [
        {
          timestamp: '2025-01-01T12:00:00Z',
          error_type: 'connection_error',
          component: 'detector',
          message: 'Failed to connect to model server',
        },
        {
          timestamp: '2025-01-01T11:55:00Z',
          error_type: 'timeout_error',
          component: 'analyzer',
          message: 'Analysis timed out after 30s',
        },
      ],
      total: 2,
      limit: 10,
      timestamp: '2025-01-01T12:01:00Z',
    };

    beforeEach(() => {
      (api.fetchPipelineErrors as ReturnType<typeof vi.fn>).mockResolvedValue(
        mockPipelineErrorsResponse
      );
    });

    describe('initialization', () => {
      it('starts with isLoading true when enabled', () => {
        (api.fetchPipelineErrors as ReturnType<typeof vi.fn>).mockReturnValue(
          new Promise(() => {})
        );

        const { result } = renderHook(() => usePipelineErrorsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        expect(result.current.isLoading).toBe(true);
      });

      it('starts with undefined data when enabled', () => {
        (api.fetchPipelineErrors as ReturnType<typeof vi.fn>).mockReturnValue(
          new Promise(() => {})
        );

        const { result } = renderHook(() => usePipelineErrorsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        expect(result.current.data).toBeUndefined();
      });
    });

    describe('fetching data', () => {
      it('fetches pipeline errors when enabled is true', async () => {
        renderHook(() => usePipelineErrorsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(api.fetchPipelineErrors).toHaveBeenCalledTimes(1);
        });
      });

      it('does not fetch when enabled is false', async () => {
        renderHook(() => usePipelineErrorsQuery({ enabled: false }), {
          wrapper: createQueryWrapper(),
        });

        // Wait a bit to ensure no call happens
        await new Promise((r) => setTimeout(r, 100));
        expect(api.fetchPipelineErrors).not.toHaveBeenCalled();
      });

      it('updates data after successful fetch', async () => {
        const { result } = renderHook(() => usePipelineErrorsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.data).toEqual(mockPipelineErrorsResponse);
        });
      });

      it('sets isLoading false after fetch completes', async () => {
        const { result } = renderHook(() => usePipelineErrorsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.isLoading).toBe(false);
        });
      });

      it('sets error on fetch failure', async () => {
        const errorMessage = 'Failed to fetch pipeline errors';
        (api.fetchPipelineErrors as ReturnType<typeof vi.fn>).mockRejectedValue(
          new Error(errorMessage)
        );

        const { result } = renderHook(() => usePipelineErrorsQuery({ enabled: true }), {
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
      it('derives errors array from data', async () => {
        const { result } = renderHook(() => usePipelineErrorsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.errors).toEqual(mockPipelineErrorsResponse.errors);
        });
      });

      it('returns empty errors array when data is not loaded', () => {
        (api.fetchPipelineErrors as ReturnType<typeof vi.fn>).mockReturnValue(
          new Promise(() => {})
        );

        const { result } = renderHook(() => usePipelineErrorsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        expect(result.current.errors).toEqual([]);
      });

      it('derives errorCount from data.total', async () => {
        const { result } = renderHook(() => usePipelineErrorsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.errorCount).toBe(2);
        });
      });
    });
  });

  describe('useRedisDebugInfoQuery', () => {
    const mockRedisInfoResponse = {
      status: 'connected',
      info: {
        redis_version: '7.0.0',
        connected_clients: 5,
        used_memory_human: '10.5MB',
        used_memory_peak_human: '15.2MB',
        total_connections_received: 1000,
        total_commands_processed: 50000,
        uptime_in_seconds: 86400,
      },
      pubsub: {
        channels: ['events', 'system'],
        subscriber_counts: { events: 3, system: 2 },
      },
      timestamp: '2025-01-01T12:00:00Z',
    };

    beforeEach(() => {
      (api.fetchRedisDebugInfo as ReturnType<typeof vi.fn>).mockResolvedValue(
        mockRedisInfoResponse
      );
    });

    describe('initialization', () => {
      it('starts with isLoading true when enabled', () => {
        (api.fetchRedisDebugInfo as ReturnType<typeof vi.fn>).mockReturnValue(
          new Promise(() => {})
        );

        const { result } = renderHook(() => useRedisDebugInfoQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        expect(result.current.isLoading).toBe(true);
      });
    });

    describe('fetching data', () => {
      it('fetches Redis info when enabled is true', async () => {
        renderHook(() => useRedisDebugInfoQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(api.fetchRedisDebugInfo).toHaveBeenCalledTimes(1);
        });
      });

      it('does not fetch when enabled is false', async () => {
        renderHook(() => useRedisDebugInfoQuery({ enabled: false }), {
          wrapper: createQueryWrapper(),
        });

        await new Promise((r) => setTimeout(r, 100));
        expect(api.fetchRedisDebugInfo).not.toHaveBeenCalled();
      });

      it('updates data after successful fetch', async () => {
        const { result } = renderHook(() => useRedisDebugInfoQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.data).toEqual(mockRedisInfoResponse);
        });
      });

      it('sets error on fetch failure', async () => {
        const errorMessage = 'Failed to fetch Redis info';
        (api.fetchRedisDebugInfo as ReturnType<typeof vi.fn>).mockRejectedValue(
          new Error(errorMessage)
        );

        const { result } = renderHook(() => useRedisDebugInfoQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(
          () => {
            expect(result.current.error).toBeInstanceOf(Error);
          },
          { timeout: 5000 }
        );
      });
    });

    describe('derived values', () => {
      it('derives redisInfo from data.info', async () => {
        const { result } = renderHook(() => useRedisDebugInfoQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.redisInfo).toEqual(mockRedisInfoResponse.info);
        });
      });

      it('derives pubsubInfo from data.pubsub', async () => {
        const { result } = renderHook(() => useRedisDebugInfoQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.pubsubInfo).toEqual(mockRedisInfoResponse.pubsub);
        });
      });

      it('derives connectionStatus from data.status', async () => {
        const { result } = renderHook(() => useRedisDebugInfoQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.connectionStatus).toBe('connected');
        });
      });

      it('returns null for derived values when data not loaded', () => {
        (api.fetchRedisDebugInfo as ReturnType<typeof vi.fn>).mockReturnValue(
          new Promise(() => {})
        );

        const { result } = renderHook(() => useRedisDebugInfoQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        expect(result.current.redisInfo).toBeNull();
        expect(result.current.pubsubInfo).toBeNull();
        expect(result.current.connectionStatus).toBeNull();
      });
    });
  });

  describe('useWebSocketConnectionsQuery', () => {
    const mockWebSocketResponse = {
      event_broadcaster: {
        connection_count: 5,
        is_listening: true,
        is_degraded: false,
        circuit_state: 'CLOSED',
        channel_name: 'events',
      },
      system_broadcaster: {
        connection_count: 3,
        is_listening: true,
        is_degraded: false,
        circuit_state: 'CLOSED',
        channel_name: null,
      },
      timestamp: '2025-01-01T12:00:00Z',
    };

    beforeEach(() => {
      (api.fetchWebSocketConnections as ReturnType<typeof vi.fn>).mockResolvedValue(
        mockWebSocketResponse
      );
    });

    describe('initialization', () => {
      it('starts with isLoading true when enabled', () => {
        (api.fetchWebSocketConnections as ReturnType<typeof vi.fn>).mockReturnValue(
          new Promise(() => {})
        );

        const { result } = renderHook(() => useWebSocketConnectionsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        expect(result.current.isLoading).toBe(true);
      });
    });

    describe('fetching data', () => {
      it('fetches WebSocket connections when enabled is true', async () => {
        renderHook(() => useWebSocketConnectionsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(api.fetchWebSocketConnections).toHaveBeenCalledTimes(1);
        });
      });

      it('does not fetch when enabled is false', async () => {
        renderHook(() => useWebSocketConnectionsQuery({ enabled: false }), {
          wrapper: createQueryWrapper(),
        });

        await new Promise((r) => setTimeout(r, 100));
        expect(api.fetchWebSocketConnections).not.toHaveBeenCalled();
      });

      it('updates data after successful fetch', async () => {
        const { result } = renderHook(() => useWebSocketConnectionsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.data).toEqual(mockWebSocketResponse);
        });
      });

      it('sets error on fetch failure', async () => {
        const errorMessage = 'Failed to fetch WebSocket connections';
        (api.fetchWebSocketConnections as ReturnType<typeof vi.fn>).mockRejectedValue(
          new Error(errorMessage)
        );

        const { result } = renderHook(() => useWebSocketConnectionsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(
          () => {
            expect(result.current.error).toBeInstanceOf(Error);
          },
          { timeout: 5000 }
        );
      });
    });

    describe('derived values', () => {
      it('derives eventBroadcaster from data', async () => {
        const { result } = renderHook(() => useWebSocketConnectionsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.eventBroadcaster).toEqual(mockWebSocketResponse.event_broadcaster);
        });
      });

      it('derives systemBroadcaster from data', async () => {
        const { result } = renderHook(() => useWebSocketConnectionsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.systemBroadcaster).toEqual(
            mockWebSocketResponse.system_broadcaster
          );
        });
      });

      it('derives totalConnections from both broadcasters', async () => {
        const { result } = renderHook(() => useWebSocketConnectionsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.totalConnections).toBe(8); // 5 + 3
        });
      });

      it('derives hasAnyDegradation from broadcaster statuses', async () => {
        const { result } = renderHook(() => useWebSocketConnectionsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.hasAnyDegradation).toBe(false);
        });
      });

      it('returns true for hasAnyDegradation when any broadcaster is degraded', async () => {
        (api.fetchWebSocketConnections as ReturnType<typeof vi.fn>).mockResolvedValue({
          ...mockWebSocketResponse,
          event_broadcaster: {
            ...mockWebSocketResponse.event_broadcaster,
            is_degraded: true,
          },
        });

        const { result } = renderHook(() => useWebSocketConnectionsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        await waitFor(() => {
          expect(result.current.hasAnyDegradation).toBe(true);
        });
      });

      it('returns null for derived values when data not loaded', () => {
        (api.fetchWebSocketConnections as ReturnType<typeof vi.fn>).mockReturnValue(
          new Promise(() => {})
        );

        const { result } = renderHook(() => useWebSocketConnectionsQuery({ enabled: true }), {
          wrapper: createQueryWrapper(),
        });

        expect(result.current.eventBroadcaster).toBeNull();
        expect(result.current.systemBroadcaster).toBeNull();
        expect(result.current.totalConnections).toBe(0);
        expect(result.current.hasAnyDegradation).toBe(false);
      });
    });
  });

  describe('return values', () => {
    it('usePipelineErrorsQuery returns all expected properties', async () => {
      (api.fetchPipelineErrors as ReturnType<typeof vi.fn>).mockResolvedValue({
        errors: [],
        total: 0,
        limit: 10,
        timestamp: '2025-01-01T12:00:00Z',
      });

      const { result } = renderHook(() => usePipelineErrorsQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current).toHaveProperty('data');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('errors');
      expect(result.current).toHaveProperty('errorCount');
      expect(result.current).toHaveProperty('refetch');
    });

    it('useRedisDebugInfoQuery returns all expected properties', async () => {
      (api.fetchRedisDebugInfo as ReturnType<typeof vi.fn>).mockResolvedValue({
        status: 'connected',
        info: null,
        pubsub: null,
        timestamp: '2025-01-01T12:00:00Z',
      });

      const { result } = renderHook(() => useRedisDebugInfoQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current).toHaveProperty('data');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('redisInfo');
      expect(result.current).toHaveProperty('pubsubInfo');
      expect(result.current).toHaveProperty('connectionStatus');
      expect(result.current).toHaveProperty('refetch');
    });

    it('useWebSocketConnectionsQuery returns all expected properties', async () => {
      (api.fetchWebSocketConnections as ReturnType<typeof vi.fn>).mockResolvedValue({
        event_broadcaster: {
          connection_count: 0,
          is_listening: false,
          is_degraded: false,
          circuit_state: 'CLOSED',
          channel_name: null,
        },
        system_broadcaster: {
          connection_count: 0,
          is_listening: false,
          is_degraded: false,
          circuit_state: 'CLOSED',
          channel_name: null,
        },
        timestamp: '2025-01-01T12:00:00Z',
      });

      const { result } = renderHook(() => useWebSocketConnectionsQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current).toHaveProperty('data');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('eventBroadcaster');
      expect(result.current).toHaveProperty('systemBroadcaster');
      expect(result.current).toHaveProperty('totalConnections');
      expect(result.current).toHaveProperty('hasAnyDegradation');
      expect(result.current).toHaveProperty('refetch');
    });
  });
});
